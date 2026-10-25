"""Preview mapping must not mistake repeated values or hidden metadata for edit anchors."""
from backend.document_preview import locate,slide_order
from backend.file_review import utf16


def part(ident,text,name='word/document.xml',kind='xml'):
    return {'id':ident,'text':text,'target':{'kind':kind,'name':name,'mode':'paragraph'}}


def candidate(ident,p,value):
    start=p['text'].index(value)
    return {'id':ident,'part':p['id'],'text':value,'start':utf16(p['text'][:start]),'end':utf16(p['text'][:start+len(value)])}


def stream(text):
    return ''.join(text.split()),[(0,(i*10,10,i*10+8,20)) for i,c in enumerate(''.join(text.split()))]


def test_context_resolves_repeated_names_and_keeps_edit_targets_separate():
    parts=[part('a','지원자'),part('b','김민수'),part('c','휴대전화'),part('d','담당자 김민수')]
    candidates=[candidate('first',parts[1],'김민수'),candidate('second',parts[3],'김민수')]
    text,refs=stream('지원자 김민수 휴대전화 담당자 김민수')
    links=locate(parts,candidates,text,refs,[(1000,500,1000,500)],{})
    assert all(v['state']=='linked' for v in links.values())
    assert links['first']['hits'][0]['boxes'][0][0]<links['second']['hits'][0]['boxes'][0][0]
    assert all('asset' not in c and 'boxes' not in c for c in candidates)


def test_unresolved_repetitions_and_metadata_stay_explicit():
    parts=[part('a','김민수'),part('m','김민수','docProps/core.xml')]
    text,refs=stream('김민수 김민수')
    links=locate(parts,[candidate('a',parts[0],'김민수'),candidate('m',parts[1],'김민수')],text,refs,[(1000,500,1000,500)],{})
    assert links['a']['state']=='ambiguous' and len(links['a']['hits'])==2
    assert links['m']=={'state':'unavailable','hits':[]}


def test_utf16_and_line_wrap_mapping():
    p=part('a','😀 이름 김민수')
    text,refs=stream('😀 이름 김\n민수')
    links=locate([p],[candidate('a',p,'김민수')],text,refs,[(1000,500,1000,500)],{})
    assert links['a']['state']=='linked'
    assert links['a']['hits'][0]['boxes'][0][0]==30


def test_slide_order_uses_relationships_instead_of_slide_filename_numbers():
    entries={'ppt/_rels/presentation.xml.rels':b'<Relationships><Relationship Id="r2" Target="/ppt/slides/slide9.xml"/><Relationship Id="r1" Target="slides/slide1.xml"/></Relationships>',
             'ppt/presentation.xml':b'<p:presentation xmlns:p="urn:p" xmlns:r="urn:r"><p:sldIdLst><p:sldId id="100" r:id="r2"/><p:sldId id="101" r:id="r1"/></p:sldIdLst></p:presentation>'}
    assert slide_order(entries)=={'ppt/slides/slide9.xml':0,'ppt/slides/slide1.xml':1}


def test_no_value_only_link_when_paragraph_is_not_on_screen():
    p=part('a','화면에 없는 문단의 김민수')
    text,refs=stream('다른 문단의 김민수')
    links=locate([p],[candidate('a',p,'김민수')],text,refs,[(1000,500,1000,500)],{})
    assert links['a']['state']=='ambiguous'


def test_preview_api_requires_session_and_valid_payload():
    from fastapi.testclient import TestClient
    from backend.app import create_app
    app=create_app(19027)
    with TestClient(app,base_url='http://127.0.0.1:19027') as client:
        assert client.post('/api/documents/preview',json={'id':'missing'}).status_code==403
        assert client.get('/api/documents/missing/preview/0').status_code==403
        client.headers['X-App-Token']=app.state.token
        assert client.post('/api/documents/preview',json={'id':'missing','path':'C:/unrelated'}).status_code==422
        assert client.post('/api/documents/preview',json={'id':'missing'}).status_code==400
        response=client.post('/api/documents/upload?filename=example.txt',content=b'example',headers={'Content-Type':'application/octet-stream'})
        ident=response.json()['id']
        assert client.post('/api/documents/cancel',json={'id':ident}).status_code==200
        assert client.post('/api/documents/preview',json={'id':ident}).status_code==400
        assert client.get(f'/api/documents/{ident}/preview/0').status_code==400
