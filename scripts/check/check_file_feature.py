"""Acceptance check against the running app and the actual offline A model."""
from pathlib import Path
import sys,json,re,html,time,hashlib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.runtime'/'python'))
import httpx

def main():
    url=json.loads((ROOT/'tmp'/'file-feature-ready.json').read_text('utf-8'))['url']
    out=ROOT/'output'/'file-feature-validation';out.mkdir(parents=True,exist_ok=True)
    client=httpx.Client(base_url=url,timeout=90,trust_env=False)
    page=client.get('/').text
    boot=json.loads(html.unescape(re.search(r'<meta name="app-boot" content="([^"]+)"',page)[1]))
    client.headers['X-App-Token']=boot['token']
    def post(route,data):
        r=client.post('/api/documents/'+route,json=data);r.raise_for_status();return r.json()
    def wait(ident):
        deadline=time.monotonic()+300;last=''
        while time.monotonic()<deadline:
            job=post('status',{'id':ident})
            if job['progress']!=last:print(job['progress'],flush=True);last=job['progress']
            if job['state'] in {'ready','error','cancelled'}:return job
            time.sleep(1)
        raise RuntimeError('job timed out')
    report=[]
    originals=ROOT/'research'/'document-followup-2026-10-24'/'originals'
    for name in ['meeting.docx','briefing.pptx','memo.hwpx','memo.hwp','participants.xlsx','identity-image.png','searchable-image.pdf']:
        source=originals/name;raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest();start=time.monotonic()
        print('START',name,flush=True)
        response=client.post('/api/documents/upload',params={'filename':name},content=raw,headers={'Content-Type':'application/octet-stream'});response.raise_for_status();ident=response.json()['id']
        job=wait(ident);row={'file':name,'readSeconds':round(time.monotonic()-start,2),'state':job['state'],'error':job.get('error'),'detections':len(job['candidates'])}
        if job.get('manifest'):
            row.update(parts=len(job['manifest']['parts']),assets=len(job['manifest']['assets']),blockers=job['manifest']['blockers'],calculation=job['manifest']['calculation'])
        if job['state']=='ready' and not job['manifest']['blockers']:
            start=time.monotonic();post('export',{'id':ident,'revision':job['revision'],'choices':{c['id']:{'mode':'full'} for c in job['candidates']},'regions':[]})
            done=wait(ident);row['exportSeconds']=round(time.monotonic()-start,2);row['exportError']=done.get('error')
            if done.get('exportResult'):
                result=done['exportResult'];r=client.get(f'/api/documents/{ident}/download');r.raise_for_status()
                (out/(source.stem+'-reviewed'+job['manifest']['outputSuffix'])).write_bytes(r.content)
                row['residualCount']=len(result['candidates']);row['outputSHA256']=hashlib.sha256(r.content).hexdigest()
                assert row['outputSHA256']==result['sha256']
            else:row['failed']=True
        row['originalUnchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==digest
        assert row['originalUnchanged'];report.append(row)
        (out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=True),flush=True)
        post('remove',{'id':ident})
    client.close()
    assert all(r['state']=='ready' and not r.get('failed') for r in report)

if __name__=='__main__':main()
