"""Read-only Office page previews. Preview coordinates never become edit targets."""
from pathlib import Path
from itertools import islice
import posixpath
import re
import subprocess
from lxml import etree as E
from backend.file_formats import FormatError, TOOLS, read_zip, parse_xml, local_name
from backend.preview_snapshot import display_snapshot


def compact(value):
    return ''.join(c for c in value if not c.isspace())


def matches(text, value, limit=64):
    if not value:return []
    result=[];start=0
    while len(result)<limit:
        found=text.find(value,start)
        if found<0:break
        result.append(found);start=found+1
    return result


def slide_order(entries):
    rels=parse_xml(entries['ppt/_rels/presentation.xml.rels'])
    targets={e.get('Id'):posixpath.normpath(posixpath.join('ppt',e.get('Target',''))).lstrip('/') for e in rels
             if not e.get('TargetMode')=='External'}
    root=parse_xml(entries['ppt/presentation.xml'])
    ids=[next((v for k,v in e.attrib.items() if E.QName(k).localname=='id' and E.QName(k).namespace),None)
         for e in root.iter() if local_name(e)=='sldId']
    return {targets[ident]:i for i,ident in enumerate(ids) if ident in targets}


def pdf_stream(pdf):
    text=[];refs=[]
    for page_no,page in enumerate(pdf):
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    for char in span['chars']:
                        for value in char['c']:
                            if not value.isspace():
                                text.append(value);refs.append((page_no,char['bbox']))
        if len(text)>180000:raise FormatError('문서 화면의 글자가 너무 많습니다. 문서를 나누어 확인해 주세요.')
    return ''.join(text),refs


def hit_boxes(refs, dimensions):
    pages={}
    for page,rect in refs:
        width,height,pw,ph=dimensions[page]
        box=[max(0,rect[0]*width/pw),max(0,rect[1]*height/ph),min(width,rect[2]*width/pw),min(height,rect[3]*height/ph)]
        groups=pages.setdefault(page,[])
        if groups and abs(groups[-1][1]-box[1])<2 and abs(groups[-1][3]-box[3])<2 and -.5<=box[0]-groups[-1][2]<8:
            groups[-1][2]=max(groups[-1][2],box[2])
        else:groups.append(box)
    return [{'page':page,'boxes':boxes} for page,boxes in pages.items()]


def locate(parts,candidates,stream,refs,dimensions,slides):
    groups={}
    for p in parts:
        target=p['target'];name=target.get('name','')
        visible=target.get('kind')=='xml' and target.get('mode')=='paragraph' and (
            name=='word/document.xml' or re.fullmatch(r'word/(?:header|footer)\d*\.xml',name) or name in slides)
        if visible:groups.setdefault(name,[]).append(p)
    index={p['id']:(name,i,items) for name,items in groups.items() for i,p in enumerate(items)}
    links={}
    for c in candidates:
        item=index.get(c['part']);link={'state':'unavailable','hits':[]}
        if item:
            name,i,items=item;part=items[i];units=part['text'].encode('utf-16-le')
            lo=len(units[:c['start']*2].decode('utf-16-le'));hi=len(units[:c['end']*2].decode('utf-16-le'))
            value=compact(part['text'][lo:hi]);prefix=len(compact(part['text'][:lo]))
            margin=re.fullmatch(r'word/(header|footer)\d*\.xml',name)
            if margin:
                # Verify the literal label/prefix too. A page field after the
                # candidate can display a different number on every page.
                context=compact(part['text'][:hi]) if prefix>=3 else compact(part['text'])
                duplicates=any(p['id']!=part['id'] and compact(p['text']).startswith(context)
                               for group in groups.values() for p in group)
                found=[]
                for start in matches(stream,context):
                    end=start+len(context)-1
                    if refs[start][0]!=refs[end][0]:continue
                    page=refs[start][0];ph=dimensions[page][3]
                    boxes=[rect for _,rect in refs[start:end+1]]
                    in_margin=max(r[3] for r in boxes)<ph*.22 if margin[1]=='header' else min(r[1] for r in boxes)>ph*.78
                    offset=start+prefix
                    if in_margin and value and stream[offset:offset+len(value)]==value:
                        found.extend(refs[offset:offset+len(value)])
                if found:link={'state':'ambiguous' if duplicates else 'linked','hits':hit_boxes(found,dimensions)}
                links[c['id']]=link
                continue
            allowed_page=slides.get(name)
            def found_in(value):
                return [a for a in matches(stream,value) if allowed_page is None or
                        refs[a][0]==allowed_page and refs[a+len(value)-1][0]==allowed_page]
            # Require exact whole-paragraph context. Add surrounding paragraphs to
            # disambiguate repeated names; never silently choose the first hit.
            for radius in range(4):
                begin=max(0,i-radius);end=min(len(items),i+radius+1)
                context=''.join(compact(p['text']) for p in items[begin:end])
                found=found_in(context)
                if len(found)==1:
                    offset=found[0]+sum(len(compact(p['text'])) for p in items[begin:i])+prefix
                    if value and stream[offset:offset+len(value)]==value:
                        link={'state':'linked','hits':hit_boxes(refs[offset:offset+len(value)],dimensions)}
                        break
            if link['state']!='linked' and value:
                found=found_in(value)
                # Even one value-only hit lacks verified source-paragraph context.
                if found:link={'state':'ambiguous','hits':[h for a in found for h in hit_boxes(refs[a:a+len(value)],dimensions)]}
        links[c['id']]=link
    return links


def link_images(pdf,assets,asset_root,candidates,dimensions,entries):
    """Link exact image pixels to uncropped, axis-aligned page placements."""
    import hashlib
    from PIL import Image
    root=Path(asset_root).resolve();by_digest={};links={};cropped=set()
    for name,raw in entries.items():
        if not name.endswith('.xml'):continue
        tree=parse_xml(raw)
        rel_name=posixpath.join(posixpath.dirname(name),'_rels',posixpath.basename(name)+'.rels')
        rels=parse_xml(entries[rel_name]) if rel_name in entries else []
        targets={r.get('Id'):posixpath.normpath(posixpath.join(posixpath.dirname(name),r.get('Target',''))).lstrip('/') for r in rels}
        for container in tree.iter():
            if local_name(container) not in {'pic','blipFill'}:continue
            if any(local_name(n)=='srcRect' and any(v not in {'0',''} for v in n.attrib.values()) for n in container.iter()):
                for n in container.iter():
                    if local_name(n)=='blip':
                        cropped.update(targets.get(v) for k,v in n.attrib.items() if E.QName(k).localname=='embed')
    for asset in assets:
        if asset.get('target',{}).get('name') in cropped:continue
        path=(root/asset.get('file','')).resolve()
        if not path.is_relative_to(root) or not path.is_file():continue
        try:
            with Image.open(path) as im:
                if im.mode not in {'RGB','L'}:continue
                rgb=im.convert('RGB');digest=hashlib.md5(rgb.tobytes()).digest()
                by_digest.setdefault((digest,rgb.width,rgb.height),[]).append(asset)
        except (OSError,ValueError):continue
    for page_no,page in enumerate(islice(pdf,len(dimensions))):
        width,height,pw,ph=dimensions[page_no]
        for info in page.get_image_info(hashes=True):
            options=by_digest.get((info.get('digest'),info['width'],info['height']),[])
            if len(options)!=1:continue
            asset=options[0];a,b,c,d,e,f=info['transform']
            # Rotated, clipped, altered or duplicate source images remain in
            # the original-image view; no guessed page mask is shown.
            if abs(b)>1e-5 or abs(c)>1e-5 or a<=0 or d<=0:continue
            if e<0 or f<0 or e+a>pw+.1 or f+d>ph+.1:continue
            for candidate in candidates:
                if candidate.get('asset')!=asset['id']:continue
                boxes=[]
                for x0,y0,x1,y1 in candidate.get('boxes',[]):
                    if not 0<=x0<x1<=asset['width'] or not 0<=y0<y1<=asset['height']:continue
                    boxes.append([(e+a*x0/asset['width'])*width/pw,(f+d*y0/asset['height'])*height/ph,
                                  (e+a*x1/asset['width'])*width/pw,(f+d*y1/asset['height'])*height/ph])
                if boxes:
                    links.setdefault(candidate['id'],{'state':'linked','hits':[]})['hits'].append({'page':page_no,'boxes':boxes})
    return links


def create_preview(source,work,parts,candidates,assets=None,asset_root=None):
    import pymupdf as fitz
    source=Path(source).resolve();work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True)
    if source.suffix not in {'.docx','.pptx'}:raise FormatError('이 형식은 텍스트·셀 또는 이미지 화면에서 확인해 주세요.')
    exe=TOOLS/'libreoffice/program/soffice.com'
    if not exe.is_file():raise FormatError('문서 화면을 만드는 도구가 없습니다. 텍스트 · 위치에서 계속 검토할 수 있습니다.')
    entries=read_zip(source)
    display=work/('display'+source.suffix)
    notices=display_snapshot(entries,display)
    slides=slide_order(entries) if source.suffix=='.pptx' else {}
    profile=work/'office-profile';(profile/'user').mkdir(parents=True,exist_ok=True)
    (profile/'user/registrymodifications.xcu').write_text('''<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item><item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop><prop oor:name="Field" oor:op="fuse"><value>false</value></prop><prop oor:name="Chart" oor:op="fuse"><value>false</value></prop></item></oor:items>''',encoding='utf-8')
    result=subprocess.run([str(exe),'-env:UserInstallation='+profile.as_uri(),'--headless','--norestore','--nodefault',
                           '--convert-to','pdf','--outdir',str(work),str(display)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    pdf_path=work/(display.stem+'.pdf')
    if result.returncode or not pdf_path.exists():raise FormatError('문서 화면을 만들지 못했습니다. 텍스트 · 위치에서 계속 검토해 주세요.')
    pages=[];dimensions=[]
    with fitz.open(pdf_path) as pdf:
        if len(pdf)>40:notices.append(f'전체 {len(pdf)}쪽 중 처음 40쪽을 화면으로 보여줍니다. 나머지 내용은 텍스트 · 위치에서 확인해 주세요.')
        for i,page in enumerate(pdf):
            if i>=40:break
            if page.rect.width*page.rect.height*2.25>20000000:raise FormatError('페이지가 너무 커서 문서 화면을 만들지 않았습니다.')
            pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
            filename=f'page-{i+1}.png';pix.save(work/filename)
            pages.append({'id':str(i),'location':f'{i+1}쪽','width':pix.width,'height':pix.height,'file':filename})
            dimensions.append((pix.width,pix.height,page.rect.width,page.rect.height))
        stream,refs=pdf_stream(islice(pdf,40))
        links=locate(parts,candidates,stream,refs,dimensions,slides)
        if assets:
            links.update(link_images(pdf,assets,asset_root or source.parent,candidates,dimensions,entries))
    return {'state':'ready','pages':pages,'links':links,
            'notices':notices,
            'warnings':notices+['변환한 문서 화면은 원래 프로그램의 배치와 다를 수 있습니다. 메모·노트·문서 속성은 텍스트 · 위치에서도 확인하세요.']}
