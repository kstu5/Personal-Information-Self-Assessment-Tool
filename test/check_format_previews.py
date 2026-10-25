"""Real-model authenticated preview check for the twelve synthetic examples."""
from pathlib import Path
import hashlib
import json
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.model_assets import MODEL_REPO


def main():
    output=ROOT/'test/qa/format-previews';output.mkdir(parents=True,exist_ok=True)
    rows=[]
    with TestClient(create_app(19339),base_url='http://127.0.0.1:19339') as client:
        client.headers['X-App-Token']=client.app.state.token
        def post(route,**data):
            r=client.post('/api/documents/'+route,json=data);r.raise_for_status();return r.json()
        def wait(ident,preview=False):
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                state=post('preview' if preview else 'status',id=ident)
                if state['state'] in {'ready','error','cancelled'}:
                    assert state['state']=='ready',state.get('message') or state.get('error');return state
                time.sleep(.3)
            raise TimeoutError(ident)
        for path in sorted((ROOT/'test/format-document-examples/files').iterdir()):
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            r=client.post('/api/documents/upload',params={'filename':path.name},content=path.read_bytes(),headers={'Content-Type':'application/octet-stream'});r.raise_for_status()
            job=wait(r.json()['id']);ident=job['id'];m=job['manifest'];kind=path.suffix
            row={'file':path.name,'extension':kind,'candidates':len(job['candidates']),'sourceUnchanged':True}
            if kind in {'.docx','.pptx'}:
                p=wait(ident,True);assert p['pages']
                assert client.get(f'/api/documents/{ident}/preview/0').status_code==200
                row.update(view='pages',pages=len(p['pages']))
            elif kind in {'.csv','.tsv','.xlsx'}:
                cells=[p for p in m['parts'] if p.get('sheet') and p.get('row') and p.get('column')]
                assert cells;row.update(view='sheet',cells=len(cells))
                if kind!='.xlsx':assert m['tableSize']['rows']>0
            elif kind in {'.txt','.hwpx','.hwp'}:
                body=[p for p in m['parts'] if p.get('flow')];assert body
                row.update(view='content',bodyParts=len(body),outsideParts=len(m['parts'])-len(body))
                if kind=='.hwp':assert m['blockers'];row['readOnly']=True
            else:
                assert m['assets'];row.update(view='images',assets=len(m['assets']))
                assert client.get(f"/api/documents/{ident}/assets/{m['assets'][0]['id']}").status_code==200
            if kind in {'.txt','.csv','.tsv','.hwpx'}:
                visible={p['id'] for p in m['parts'] if p.get('flow') or p.get('row')}
                candidate=next(c for c in job['candidates'] if c['part'] in visible)
                post('export',id=ident,revision=job['revision'],choices={candidate['id']:{'mode':'partial'}},regions=[],textEdits={})
                saved=wait(ident)['exportResult'];assert saved
                assert any(p.get('flow') or p.get('row') for p in saved['parts'])
                if kind in {'.csv','.tsv'}:assert saved['tableSize']==m['tableSize']
                row['exportAndReinspection']=True
            assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
            (output/(path.name+'.job.json')).write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
            rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
            post('remove',id=ident)
        engine=client.post('/api/check',json={'title':'','body':'성명 김민수','revision':1}).json()['engine']
        assert MODEL_REPO in engine and 'A 모델' not in engine
    (output/'summary.json').write_text(json.dumps({'model':MODEL_REPO,'files':rows},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
