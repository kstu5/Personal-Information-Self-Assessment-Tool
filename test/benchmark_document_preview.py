"""Read-only local preview feasibility benchmark using existing synthetic inputs.

No model calls, external uploads, package installs, or product changes.
Raw output/profile files stay under ignored test/qa/preview-research/.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import psutil
import pymupdf as fitz

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'test/qa/preview-research'/str(time.time_ns())
RUN.mkdir(parents=True)
SOFFICE=ROOT/'.runtime/file-tools/libreoffice/program/soffice.com'

def norm(s):return re.sub(r'\s+','',s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def convert(source,folder,profile,markers):
    folder.mkdir(parents=True)
    user=profile/'user';user.mkdir(parents=True,exist_ok=True)
    (user/'registrymodifications.xcu').write_text('''<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item></oor:items>''',encoding='utf-8')
    started=time.perf_counter()
    with (folder/'conversion.log').open('wb') as log:
        p=subprocess.Popen([str(SOFFICE),'-env:UserInstallation='+profile.as_uri(),'--headless','--norestore','--nodefault',
                            '--convert-to','pdf','--outdir',str(folder),str(source)],stdout=log,stderr=log,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        parent=psutil.Process(p.pid);peak_rss=peak_private=0;sample_count=0;observed=set()
        while p.poll() is None:
            if time.perf_counter()-started>60:
                for proc in parent.children(recursive=True):proc.kill()
                p.kill();p.wait();raise TimeoutError(source.name)
            rss=private=0
            try:procs=[parent,*parent.children(recursive=True)]
            except psutil.Error:procs=[]
            for proc in procs:
                try:
                    mi=proc.memory_info();rss+=mi.rss;private+=getattr(mi,'private',0);observed.add(proc.name())
                except psutil.Error:pass
            peak_rss=max(peak_rss,rss);peak_private=max(peak_private,private);sample_count+=1
            time.sleep(.025)
    seconds=time.perf_counter()-started
    pdf=folder/(source.stem+'.pdf')
    row={'source':source.name,'conversion_seconds':round(seconds,3),'exit_code':p.returncode,
         'peak_tree_rss_mib':round(peak_rss/1048576,1),'peak_tree_private_mib':round(peak_private/1048576,1),
         'memory_samples':sample_count,'observed_process_names':sorted(observed),'pdf_created':pdf.exists()}
    if not pdf.exists():return row
    started=time.perf_counter()
    with fitz.open(pdf) as d:
        text='\n'.join(page.get_text() for page in d)
        row['pages']=len(d)
        row['markers_found']={s:norm(s) in norm(text) for s in markers}
        row['valid_content']=all(row['markers_found'].values())
        (folder/'converted-text.txt').write_text(text,encoding='utf-8')
        pngbytes=rgba=0
        for i,page in enumerate(d):
            pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
            png=pix.tobytes('png');(folder/f'page-{i+1}.png').write_bytes(png)
            pngbytes+=len(png);rgba+=pix.width*pix.height*4
        row.update(render_seconds=round(time.perf_counter()-started,3),pdf_bytes=pdf.stat().st_size,
                   all_page_png_bytes=pngbytes,all_pages_decoded_rgba_mib=round(rgba/1048576,2))
    return row

def mapping_probe(pdf,jobfile,source_hash):
    if not jobfile.exists():return None
    job=json.loads(jobfile.read_text('utf-8'))
    # The old real-model result must belong to the same unchanged synthetic source.
    import sys
    sys.path.insert(0,str(ROOT))
    from backend.file_formats import Document
    work=RUN/'resume-source-read';work.mkdir()
    source=ROOT/'test/shared-document-examples/이력서_검사예시.docx'
    doc=Document(source,work).load()
    if [(x['text'],x['location']) for x in job['manifest']['parts']] != [(x['text'],x['location']) for x in doc.parts]:
        raise ValueError('Stored detection result does not match current source content')
    rows=[]
    with fitz.open(pdf) as d:
        for c in job['candidates']:
            hits=[{'page':i+1,'box':list(rect)} for i,page in enumerate(d) for rect in page.search_for(c['text'])]
            rows.append({'text':c['text'],'risk':c['risk'],'type':c['labelName'],'source_location':c['location'],
                         'render_hits':hits,'uniquely_locatable_by_value_alone':len(hits)==1})
    result={'source_sha256':source_hash,'actual_model_candidates':len(rows),
            'unique':sum(len(r['render_hits'])==1 for r in rows),
            'ambiguous':sum(len(r['render_hits'])>1 for r in rows),
            'missing':sum(not r['render_hits'] for r in rows),'candidates':rows,
            'note':'Read-only illustration. Value search is not a verified source anchor or editing coordinate.'}
    (RUN/'mapping-probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return {k:v for k,v in result.items() if k!='candidates'}

def main():
    folder=ROOT/'test/format-document-examples/files'
    sources=[ROOT/'test/shared-document-examples/이력서_검사예시.docx',folder/'04_외부교육_참가추천서.docx',
             folder/'05_행사운영_사전브리핑.pptx',folder/'08_기념품_배송요청명단.xlsx',
             folder/'06_워크숍_참가협조공문.hwpx',folder/'07_시민교육_참가안내.hwp']
    before={p.name:sha(p) for p in sources}
    rows=[]
    for i,source in enumerate(sources):
        markers=['김민수','minsu.kim@example.invalid'] if i==0 else ['박지후','010-0000-2103']
        for run in range(2 if source.suffix in {'.docx','.pptx','.xlsx'} else 1):
            row=convert(source,RUN/f'{i}-{run}',RUN/f'profile-{i}',markers)
            row['profile']='new' if run==0 else 'reused_profile_new_process'
            row['sha256']=before[source.name];rows.append(row)
            print(source.name,row['profile'],row['conversion_seconds'],'sec',row.get('pages'),
                  'pages','content',row.get('valid_content'),'private MiB',row['peak_tree_private_mib'],flush=True)
    assert all(sha(p)==before[p.name] for p in sources)
    lo_bytes=sum(p.stat().st_size for p in SOFFICE.parents[1].rglob('*') if p.is_file())
    report={'scope':'local synthetic preview conversion, no PII model or UI benchmark','memory_interval_seconds':.025,
            'rss_includes_shared_pages':True,'cold_os_cache_not_controlled':True,'originals_unchanged':True,
            'installed_libreoffice_bytes':lo_bytes,'conversions':rows,
            'mapping_probe':mapping_probe(RUN/'0-0/이력서_검사예시.pdf',ROOT/'local-only/context-review/after/이력서_검사예시.docx.job.json',before[sources[0].name])}
    (RUN/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Report',RUN.relative_to(ROOT)/'benchmark.json',flush=True)

if __name__=='__main__':main()
