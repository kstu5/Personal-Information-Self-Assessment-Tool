"""Real-model/API round trip for page preview plus partial/full/custom edits."""
from pathlib import Path
import collections
import hashlib
import json
import sys
import time
from lxml import etree as E
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app import create_app


def main():
    out=ROOT/'validation/qa/visual-review/api';out.mkdir(parents=True,exist_ok=True)
    app=create_app(19335);rows=[]
    with TestClient(app,base_url='http://127.0.0.1:19335') as client:
        client.headers['X-App-Token']=app.state.token
        def post(route,**data):
            r=client.post('/api/documents/'+route,json=data);r.raise_for_status();return r.json()
        def wait(ident):
            end=time.monotonic()+240
            while time.monotonic()<end:
                r=post('status',id=ident)
                if r['state'] in {'ready','error','cancelled'}:
                    assert r['state']=='ready',r.get('error');return r
                time.sleep(.2)
            raise TimeoutError('inspection/export')
        def preview(ident,output=False):
            end=time.monotonic()+180
            while time.monotonic()<end:
                r=post('preview',id=ident,output=output)
                if r['state'] in {'ready','error'}:
                    assert r['state']=='ready',r.get('message');return r
                time.sleep(.3)
            raise TimeoutError('preview')
        files=[ROOT/'examples/documents/이력서_검사예시.docx',ROOT/'examples/formats/files/05_행사운영_사전브리핑.pptx']
        for source in files:
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            r=client.post('/api/documents/upload',params={'filename':source.name},content=source.read_bytes(),headers={'Content-Type':'application/octet-stream'})
            r.raise_for_status();job=wait(r.json()['id']);ident=job['id']
            original=preview(ident)
            (out/(source.name+'.original-job.json')).write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
            (out/(source.name+'.original-preview.json')).write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding='utf-8')
            assert post('preview',id=ident)['version']==original['version']
            visible=[c for c in job['candidates'] if original['links'][c['id']]['state']=='linked']
            names=[c for c in visible if c['label']=='PERSON'];phones=[c for c in visible if c['label']=='PHONE'];emails=[c for c in visible if c['label']=='EMAIL']
            assert names and phones and emails
            selected=[(names[0],{'mode':'partial'}),(phones[0],{'mode':'full'}),(emails[0],{'mode':'custom','text':'공개 문의창구'})]
            choices={c['id']:choice for c,choice in selected}
            post('export',id=ident,revision=job['revision'],choices=choices,regions=[],textEdits={})
            done=wait(ident);assert done['exportResult'],done.get('error')
            response=client.get(f'/api/documents/{ident}/download');response.raise_for_status()
            saved=out/(source.stem+'__reviewed'+source.suffix);saved.write_bytes(response.content)
            after=preview(ident,True)
            assert after['version']!=original['version']
            assert post('preview',id=ident)['version']==original['version']
            assert not any('file' in page for page in after['pages']) and 'directory' not in after
            assert client.get(f'/api/documents/{ident}/preview/0?output=true').status_code==200
            assert client.get(f'/api/documents/{ident}/preview/9999').status_code==400
            parts={p['id']:p for p in done['exportResult']['parts']}
            assert '공개 문의창구' in parts[emails[0]['part']]['text']
            assert phones[0]['text'] not in parts[phones[0]['part']]['text']
            assert names[0]['text'] not in parts[names[0]['part']]['text']
            # Independent saved-package inspection, including comments/notes and all text nodes.
            with zipfile.ZipFile(saved) as z:
                texts=[''.join(E.fromstring(z.read(n)).itertext()) for n in z.namelist() if n.endswith('.xml')]
            assert any('공개 문의창구' in t for t in texts)
            assert any(names[0]['partialText'] in t for t in texts)
            assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
            row={'file':source.name,'candidates':len(job['candidates']),'originalPages':len(original['pages']),
                 'originalLinks':dict(collections.Counter(v['state'] for v in original['links'].values())),
                 'outputPages':len(after['pages']),'modes':['partial','full','custom'],'originalUnchanged':True,'independentPackageChecked':True,
                 'sourceSHA256':digest,'outputSHA256':hashlib.sha256(response.content).hexdigest()}
            previous_dir=app.state.documents._job(ident)['work']/app.state.documents._job(ident)['previews']['output']['directory']
            again={**choices,emails[0]['id']:{'mode':'custom','text':'공개 문의창구 2'}}
            post('export',id=ident,revision=job['revision'],choices=again,regions=[],textEdits={})
            second=wait(ident);assert second['exportResult']
            latest=preview(ident,True)
            assert latest['version']==second['exportResult']['sha256'] and latest['version']!=after['version']
            assert not previous_dir.exists()
            assert post('preview',id=ident)['version']==original['version']
            row['oldOutputPreviewRemovedAfterRegeneration']=True
            rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
            for name,value in [('original-job',job),('original-preview',original),('output-job',done),('output-preview',after)]:
                (out/(source.name+'.'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            post('remove',id=ident)
    (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
