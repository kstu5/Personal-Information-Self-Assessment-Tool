"""Prepare a display-only OOXML package; never rewrite inspection/edit inputs."""
from collections import Counter
from copy import deepcopy
from pathlib import PurePosixPath
import posixpath
import re
from lxml import etree as E
from backend.file_formats import parse_xml, local_name, write_zip

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
V = 'urn:schemas-microsoft-com:vml'
WORD = {W, 'http://purl.oclc.org/ooxml/wordprocessingml/main'}
RELS = {R, 'http://purl.oclc.org/ooxml/officeDocument/relationships'}
PAGE = re.compile(r'(?:PAGE|NUMPAGES|SECTIONPAGES)(?:\s+\\\*\s+(?:MERGEFORMAT|CHARFORMAT|ARABIC|ROMAN|ALPHABETIC))*', re.I)
MISSING = '[저장된 표시 내용 없음]'


def namespace(node):
    return E.QName(node).namespace if isinstance(node.tag, str) else ''


def remove(node):
    parent = node.getparent()
    if parent is not None:
        parent.remove(node)


def unwrap(node):
    parent = node.getparent()
    if parent is None:
        return
    index = parent.index(node)
    for child in list(node):
        parent.insert(index, child)
        index += 1
    remove(node)


def word_run(text, ns=W):
    run = E.Element('{'+ns+'}r')
    E.SubElement(run, '{'+ns+'}t').text = text
    return run


def word_fields(tree, counts):
    """Match complex fields across runs/paragraphs, preserving cached results.

    Only complete, unnested page-count fields retain instructions. Everything
    else becomes static. Unmatched controls cannot keep executable instructions.
    """
    events = list(tree.iter())
    frames = []
    stack = []
    for index, node in enumerate(events):
        if namespace(node) not in WORD:
            continue
        ns = namespace(node)
        tag = local_name(node)
        if tag == 'fldChar':
            kind = node.get('{'+ns+'}fldCharType')
            if kind == 'begin':
                if stack:
                    stack[-1]['nested'] = True
                frame = {'start': index, 'end': len(events), 'separator': None,
                         'instruction': '', 'nested': False, 'outer': bool(stack),
                         'complete': False, 'broken': False}
                frames.append(frame)
                stack.append(frame)
            elif kind == 'separate' and stack:
                if stack[-1]['separator'] is not None:
                    stack[-1]['broken'] = True
                stack[-1]['separator'] = index
            elif kind == 'end' and stack:
                frame = stack.pop()
                frame.update(end=index, complete=True)
        elif tag == 'instrText' and stack and stack[-1]['separator'] is None:
            stack[-1]['instruction'] += node.text or ''
    keep = set()
    hidden = set()
    for frame in frames:
        safe = (frame['complete'] and not frame['nested'] and not frame['outer']
                and not frame['broken'] and PAGE.fullmatch(frame['instruction'].strip()))
        if safe:
            keep.update(range(frame['start'], frame['end']+1))
            continue
        counts['fields'] += 1
        # Hide the instruction phase, including nested field results used as
        # arguments. Retain only the outer field's stored displayed result.
        if frame['complete']:
            end = frame['separator'] if frame['separator'] is not None else frame['end']
            hidden.update(range(frame['start']+1, end))
            result = events[end+1:frame['end']] if frame['separator'] is not None else []
            if not any(namespace(n) in WORD and local_name(n) in {'t','drawing','pict','object'} for n in result):
                marker = events[frame['end']]
                parent = marker.getparent()
                if parent is not None:
                    # fldChar normally sits in a run, so a text child is valid.
                    if local_name(parent) == 'r':
                        E.SubElement(parent, '{'+namespace(marker)+'}t').text = MISSING
                    else:
                        parent.insert(parent.index(marker), word_run(MISSING, namespace(marker)))
                    counts['missing'] += 1
        else:
            counts['incomplete'] += 1
    for index, node in enumerate(events):
        if namespace(node) not in WORD:
            continue
        tag = local_name(node)
        if tag in {'fldChar','instrText'} and index not in keep:
            remove(node)
        elif index in hidden and tag in {'t','drawing','pict','object','br','tab','sym'}:
            remove(node)
    # Complex fields are now static or verified page fields. Process simple
    # fields from the inside out, so nested instructions cannot survive a freeze.
    for node in reversed(list(tree.iter())):
        if namespace(node) not in WORD or local_name(node) != 'fldSimple':
            continue
        ns = namespace(node)
        instruction = node.get('{'+ns+'}instr', '').strip()
        nested = any(local_name(n) in {'fldSimple','fldChar','instrText'} for n in node.iter() if n is not node)
        if PAGE.fullmatch(instruction) and not nested:
            continue
        counts['fields'] += 1
        # An enclosing cached result must never retain an inner page command.
        for inner in list(node.iter()):
            if inner is node or namespace(inner) not in WORD:
                continue
            if local_name(inner) == 'fldSimple':
                unwrap(inner)
            elif local_name(inner) in {'fldChar','instrText'}:
                remove(inner)
        if not any(local_name(n) in {'t','drawing','pict','object'} for n in node.iter()):
            node.append(word_run(MISSING, ns))
            counts['missing'] += 1
        unwrap(node)


def placeholder(node, counts):
    """Replace the nearest visible container without dropping surrounding text."""
    owner = next((n for n in [node, *node.iterancestors()]
                  if namespace(n) in WORD and local_name(n) in {'drawing','pict','object','altChunk'}), None)
    if owner is not None:
        parent = owner.getparent()
        if parent is not None:
            replacement = E.Element('{'+namespace(owner)+'}t') if local_name(parent) == 'r' else word_run(MISSING, namespace(owner))
            if local_name(parent) == 'r':
                replacement.text = MISSING
            parent.replace(owner, replacement)
        counts['missing'] += 1
        return
    owner = next((n for n in [node, *node.iterancestors()]
                  if namespace(n) == P and local_name(n) in {'pic','graphicFrame','sp'}), None)
    if owner is not None and owner.getparent() is not None:
        shape = E.Element('{'+P+'}sp')
        nv = E.SubElement(shape, '{'+P+'}nvSpPr')
        old = next((n for n in owner.iter() if local_name(n) == 'cNvPr'), None)
        E.SubElement(nv, '{'+P+'}cNvPr', id=old.get('id','1') if old is not None else '1', name='저장된 표시 내용 없음')
        E.SubElement(nv, '{'+P+'}cNvSpPr', txBox='1')
        E.SubElement(nv, '{'+P+'}nvPr')
        sp = E.SubElement(shape, '{'+P+'}spPr')
        transform = next((n for n in owner if local_name(n) == 'xfrm'), None)
        if transform is None:
            transform = next((n for n in owner.iter() if n.tag == '{'+A+'}xfrm'), None)
        if transform is not None:
            transform = deepcopy(transform)
            transform.tag = '{'+A+'}xfrm'
            sp.append(transform)
        body = E.SubElement(shape, '{'+P+'}txBody')
        E.SubElement(body, '{'+A+'}bodyPr')
        E.SubElement(body, '{'+A+'}lstStyle')
        para = E.SubElement(body, '{'+A+'}p')
        E.SubElement(E.SubElement(para, '{'+A+'}r'), '{'+A+'}t').text = MISSING
        owner.getparent().replace(owner, shape)
        counts['missing'] += 1
    else:
        remove(node)
        counts['missing'] += 1


def owner_of_relationships(name):
    if name == '_rels/.rels':
        return ''
    path = PurePosixPath(name)
    return str(path.parent.parent/path.name[:-5])


def display_snapshot(entries, output):
    """Return warnings after writing a detached, local display-only package."""
    counts = Counter()
    def dropped(name):
        low = name.lower()
        return any(s in low for s in ('/embeddings/','vbaproject','vbadata','/activex/','_xmlsignatures/')) or low.startswith('customxml/')
    result = {n:raw for n,raw in entries.items() if not dropped(n)}
    for name in entries.keys()-result.keys():
        low=name.lower()
        if low.startswith('customxml/'):
            if name.endswith('.rels'):continue
            root=parse_xml(entries[name])
            boilerplate=(local_name(root)=='Sources' and len(root)==0 or local_name(root)=='datastoreItem'
                         and all(local_name(n) in {'datastoreItem','schemaRefs','schemaRef'} for n in root.iter()))
            if not boilerplate:counts['detached']+=1
        elif any(s in low for s in ('/embeddings/','vbaproject','vbadata','/activex/')):
            counts['detached']+=1
    trees = {n:parse_xml(raw) for n,raw in result.items() if n.endswith(('.xml','.rels','.vml','.svg'))}
    deleted = {}
    for name, tree in trees.items():
        if not name.endswith('.rels'):
            continue
        owner = owner_of_relationships(name)
        for rel in list(tree):
            target = rel.get('Target','')
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(owner), target)).lstrip('/')
            local = (not rel.get('TargetMode','').lower() == 'external' and not re.search(r'[:\\]', target)
                     and not target.startswith('//') and not destination.startswith('../') and destination in result)
            active = rel.get('Type','').rsplit('/',1)[-1].lower() in {
                'oleobject','package','control','activexcontrol','activexcontrolbinary','vbaproject',
                'vbadata','attachedtemplate','afchunk','customxml','customxmlprops', 'digital-signature/origin'}
            if not local or active:
                deleted.setdefault(owner, set()).add(rel.get('Id'))
                if rel.get('TargetMode','').lower() == 'external':
                    counts['links'] += 1
                tree.remove(rel)
    for name, tree in trees.items():
        if name.endswith('.rels'):
            continue
        if name == '[Content_Types].xml':
            for node in list(tree):
                if node.get('PartName','').lstrip('/') and node.get('PartName').lstrip('/') not in result:
                    tree.remove(node)
                content = node.get('ContentType','')
                if 'macroEnabled.main+xml' in content:
                    node.set('ContentType', content.replace('ms-word.document.macroEnabled', 'openxmlformats-officedocument.wordprocessingml.document')
                             .replace('ms-powerpoint.presentation.macroEnabled', 'openxmlformats-officedocument.presentationml.presentation'))
            continue
        word_fields(tree, counts)
        bad = deleted.get(name, set())
        for node in list(tree.iter()):
            ns, tag = namespace(node), local_name(node)
            if node.getparent() is None:
                continue
            if ns in WORD and tag in {'attachedTemplate','mailMerge','dataBinding','updateFields'}:
                remove(node)
                continue
            # A DrawingML field has a saved text result; keep it as a plain run.
            if ns == A and tag == 'fld':
                node.tag = '{'+A+'}r'
                node.attrib.clear()
                counts['fields'] += 1
            if tag.lower() in {'oleobject','oleobj','control','altchunk'}:
                # Word OLE preview pictures live beside OLEObject. PPT pictures
                # are nested inside oleObj and need lifting into the shape tree.
                if ns == P and tag == 'oleObj':
                    pic = node.find('{'+P+'}pic')
                    frame = next((n for n in node.iterancestors() if n.tag == '{'+P+'}graphicFrame'), None)
                    if pic is not None and frame is not None:
                        cached = deepcopy(pic)
                        transform = frame.find('{'+P+'}xfrm')
                        sp = cached.find('{'+P+'}spPr')
                        if transform is not None and sp is not None:
                            for old in list(sp):
                                if local_name(old) == 'xfrm':
                                    sp.remove(old)
                            transform = deepcopy(transform);transform.tag = '{'+A+'}xfrm';sp.insert(0,transform)
                        frame.getparent().replace(frame,cached)
                    else:
                        placeholder(node, counts)
                elif any(n.tag == '{'+V+'}imagedata' for n in node.getparent().iter()) and tag.lower() == 'oleobject':
                    remove(node)
                else:
                    placeholder(node, counts)
                counts['objects'] += 1
                continue
            if tag in {'externalData','ddeLink','ddeLinks','oleLink','oleLinks','externalLink','externalReferences'}:
                remove(node)
                continue
            # Charts retain their saved caches, never workbook formulas/links.
            if tag == 'f' and 'drawingml' in (ns or '') and 'chart' in (ns or ''):
                remove(node)
                continue
            refs = [(key,value) for key,value in node.attrib.items() if E.QName(key).namespace in RELS and value in bad]
            for key,value in refs:
                del node.attrib[key]
            direct_image = ns == V and tag in {'imagedata','fill'} and any(E.QName(k).localname in {'src','href'} for k in node.attrib)
            for key in list(node.attrib):
                if E.QName(key).localname in {'src','href'} and (ns == V or name.endswith('.svg')):
                    value = node.attrib[key]
                    if not (name.endswith('.svg') and value.startswith(('#','data:'))):
                        del node.attrib[key]
                        if name.endswith('.svg') or tag == 'fill':
                            counts['missing'] += 1
            if refs and ns in WORD and tag == 'hyperlink':
                unwrap(node)
            elif refs and tag in {'hlinkClick','hlinkHover','attachedTemplate'}:
                remove(node)
            elif refs and tag == 'blip' and not any(E.QName(k).namespace in RELS and E.QName(k).localname == 'embed' for k in node.attrib):
                placeholder(node, counts)
            elif ns == V and tag == 'imagedata' and (refs or direct_image) and not any(E.QName(k).namespace in RELS for k in node.attrib):
                placeholder(node, counts)
        # OLE fallback pictures lifted during traversal need their own reference
        # cleanup too. No removed relationship id may remain on the display copy.
        for node in list(tree.iter()):
            for key,value in list(node.attrib.items()):
                if E.QName(key).namespace in RELS and value in bad:
                    del node.attrib[key]
            if local_name(node) == 'blip' and not any(E.QName(k).namespace in RELS and E.QName(k).localname == 'embed' for k in node.attrib):
                # A removed external image is visibly represented, including
                # fallback pictures lifted from an OLE container above.
                if node.getroottree().getroot() is tree:
                    placeholder(node, counts)
    for name, tree in trees.items():
        result[name] = E.tostring(tree, encoding='UTF-8', xml_declaration=True)
    write_zip(output, result)
    notices = []
    if counts['fields']:
        notices.append(f"자동 필드 {counts['fields']}곳은 문서에 저장된 표시 내용으로 보여줍니다. 최신 값과 다를 수 있습니다.")
    if counts['links']:
        notices.append(f"외부 연결 {counts['links']}곳은 갱신하지 않고 파일 안에 저장된 내용으로 보여줍니다.")
    if counts['objects']:
        notices.append(f"연결·내장 개체 {counts['objects']}곳은 저장된 대체 그림이나 안내로 보여줍니다. 개체 내부 수정 지원과는 별개입니다.")
    if counts['detached']:
        notices.append('표시용 사본에서는 내장 파일·실행 기능·추가 데이터 연결을 분리했습니다. 개인정보 검사는 원본 내용을 기준으로 합니다.')
    if counts['missing'] or counts['incomplete']:
        notices.append(f"저장된 표시 내용이 없거나 구조가 불완전한 부분 {counts['missing']+counts['incomplete']}곳이 있습니다. 표시 내용과 텍스트 · 위치를 함께 확인해 주세요.")
    return notices
