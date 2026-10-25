from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.documents import parse_document


class Dialogs:
    def __init__(self, path): self.path=path
    def choose_save(self, filename): self.filename=filename; return self.path
    def choose_open(self): return self.path


@pytest.fixture
def client(tmp_path):
    dialogs=Dialogs(tmp_path/'선택한 파일.piipost')
    app=create_app(19001,desktop=dialogs)
    with TestClient(app,base_url='http://127.0.0.1:19001') as c:
        c.headers['X-App-Token']=app.state.token
        yield c, app, dialogs


def test_security(client):
    c,app,_=client
    assert c.get('/api/health').status_code==200
    assert c.get('/api/health',headers={'X-App-Token':'wrong'}).status_code==403
    assert c.get('/api/health',headers={'Host':'evil.example'}).status_code==403
    assert c.get('/api/health',headers={'Origin':'http://evil.example'}).status_code==403
    assert c.get('/',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    home=c.get('/')
    assert home.status_code==200
    assert 'atonlee/koelectra-ko-pii-ner' in home.text
    response=c.get('/api/health')
    assert response.headers['cache-control']=='no-store'
    assert 'access-control-allow-origin' not in response.headers
    assert response.headers['x-frame-options']=='DENY'
    assert c.get('/openapi.json').status_code==404
    assert c.get('/assets/..%2f..%2fpackage.json').status_code==404


def test_saved_files_api_and_cancel(client):
    c,_,dialogs=client
    r=c.post('/api/files/save',json={'title':'원래: 제목?','body':'본문 😀\n연락처','filename':'원래: 제목?'}).json()
    assert dialogs.filename=='원래 제목.piipost'
    assert parse_document(dialogs.path.read_bytes())['title']=='원래: 제목?'
    loaded=c.post('/api/files/open',json={}).json()
    assert loaded['document']['body']=='본문 😀\n연락처'
    before=dialogs.path.read_bytes()
    dialogs.path=None
    cancelled=c.post('/api/files/save',json={'title':'새 글','body':'변경','saveAs':True}).json()
    assert cancelled=={'cancelled':True}
    assert c.post('/api/files/save',json={'title':'다음 제목','body':'내용','fileId':r['fileId']}).status_code==200


def test_bad_requests_do_not_echo_private_input(client):
    c,_,_=client
    response=c.post('/api/check',json={'title':{'private':'DO_NOT_ECHO'},'body':'','revision':1})
    assert response.status_code==422 and 'DO_NOT_ECHO' not in response.text
    response=c.post('/api/check',content='x'*500001,headers={'content-type':'application/json'})
    assert response.status_code==413
    assert c.post('/api/check',json={'title':'','body':'가'*30001,'revision':0}).status_code==400


def test_real_detection_api(client):
    c,app,_=client
    response=c.post('/api/check',json={'title':'연락처: 010-0000-0000','body':'😀 e\u0301 전화: 010-0000-0001\n다시: 010-0000-0001','revision':7})
    assert response.status_code==200,response.text
    result=response.json()
    assert 'atonlee/koelectra-ko-pii-ner' in result['engine']
    pid = app.state.detector._process.pid
    assert result['revision']==7
    phones=[x for x in result['candidates'] if x['label']=='PHONE']
    assert len(phones)==3
    assert len({x['id'] for x in phones})==3
    assert {x['source'] for x in phones}=={'title','body'}
    for x in phones:
        original='연락처: 010-0000-0000' if x['source']=='title' else '😀 e\u0301 전화: 010-0000-0001\n다시: 010-0000-0001'
        assert original.encode('utf-16-le')[x['start']*2:x['end']*2].decode('utf-16-le')==x['text']
    second=c.post('/api/check',json={'title':'이름: 김하늘','body':'주소: 서울특별시 마포구 예시로 12, 302호','revision':8})
    assert second.status_code==200, second.text
    found=second.json()['candidates']
    assert any(x['label']=='PERSON' and x['text']=='김하늘' for x in found)
    assert any(x['label']=='ADDRESS' and x['text']=='서울특별시 마포구 예시로 12, 302호' for x in found)
    assert app.state.detector._process.pid==pid


def test_missing_model_is_an_error_and_shutdown_cleans_worker(tmp_path):
    app=create_app(19001)
    # The route closes over this instance; change only its model directory for the test.
    app.state.detector.model_path=tmp_path/'missing'
    with TestClient(app,base_url='http://127.0.0.1:19001') as c:
        c.headers['X-App-Token']=app.state.token
        response=c.post('/api/check',json={'title':'','body':'DO_NOT_ECHO','revision':1})
        assert response.status_code==400
        assert response.json()['code']=='model_unavailable'
        assert 'candidates' not in response.json() and 'DO_NOT_ECHO' not in response.text
        assert app.state.detector._process is None
        assert not app.state.detector.gate.locked()
    assert app.state.detector._closed.is_set()


def test_api_shutdown_closes_detector():
    # Lifecycle uses the same close operation as a successful, already loaded worker.
    app=create_app(19001)
    with TestClient(app,base_url='http://127.0.0.1:19001'):
        assert not app.state.detector._closed.is_set()
    assert app.state.detector._closed.is_set()


def test_detector_timeout_releases_worker():
    from backend.detection import Detector
    from backend.documents import DocumentError
    import multiprocessing
    before={p.pid for p in multiprocessing.active_children()}
    detector=Detector(timeout=.00001, startup_timeout=.00001)
    with pytest.raises(DocumentError) as err: detector.check('제목','전화: 010-0000-0000')
    assert err.value.code=='timeout'
    assert not detector.gate.locked()
    assert {p.pid for p in multiprocessing.active_children()}==before
