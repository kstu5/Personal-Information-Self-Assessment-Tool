"""Exercise document actions in an actual hidden WebView2 window; OS picks are deterministic."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.runtime'/'python'));sys.path.insert(0,str(ROOT))

def main():
    import json,socket,threading,time,hashlib
    import httpx,uvicorn,webview
    from backend.app import create_app
    from backend.desktop import Desktop
    out=ROOT/'tmp'/'file-desktop-check';out.mkdir(parents=True,exist_ok=True)
    source=out/'원본.txt';source.write_bytes('이름 김민수\n전화 010-0000-1234'.encode('utf-8'));original=source.read_bytes()
    dest=out/('수정사본-'+str(time.time_ns())+'.txt');chosen=[source]
    desktop=Desktop();sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
    port=sock.getsockname()[1];url=f'http://127.0.0.1:{port}';app=create_app(port,desktop=desktop)
    server=uvicorn.Server(uvicorn.Config(app,access_log=False,log_level='critical',log_config=None))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    for _ in range(200):
        if server.started:break
        time.sleep(.05)
    assert server.started
    desktop.window=webview.create_window('파일 기능 자동 검증',url,width=1280,height=900,hidden=True)
    desktop.window.events.closing+=desktop.closing
    desktop.window.create_file_dialog=lambda *args,**kwargs:tuple(str(p) for p in chosen)
    report={'checks':[],'errors':[]}
    def wait(expr):
        for _ in range(900):
            if desktop.window.evaluate_js(expr):return
            time.sleep(.1)
        raise AssertionError(expr)
    def drive():
        try:
            desktop.window.events.loaded.wait(20)
            wait('!!document.querySelector(".entry-home")')
            desktop.window.evaluate_js('Array.from(document.querySelectorAll(".mode-nav button")).find(x=>x.textContent==="파일 검사").click()')
            desktop.window.evaluate_js('document.querySelector(".file-review .page-heading>.primary").click()')
            wait('!!document.querySelector(".file-export>.primary") && !document.querySelector(".file-export>.primary").disabled')
            ident=next(iter(app.state.documents.jobs));job=app.state.documents.status(ident)
            assert any(c['label']=='PERSON' for c in job['candidates'])
            report['checks'].append('Native multi-file picker adapter, actual A model, and review UI')
            with httpx.Client(base_url=url,headers={'X-App-Token':app.state.token,'Origin':url},trust_env=False,timeout=90) as client:
                r=client.post('/api/documents/export',json={'id':ident,'revision':job['revision'],'choices':{c['id']:{'mode':'full'} for c in job['candidates']},'regions':[]});r.raise_for_status()
                for _ in range(900):
                    job=app.state.documents.status(ident)
                    if job['state']=='ready':break
                    time.sleep(.1)
                assert job['exportResult'],job.get('error')
                chosen[:]=[dest];r=client.post('/api/documents/save',json={'id':ident});r.raise_for_status()
                assert r.json()['saved'] and '김민수' not in dest.read_text('utf-8')
                assert source.read_bytes()==original
                chosen[:]=[source];r=client.post('/api/documents/save',json={'id':ident});assert r.status_code==400
                assert source.read_bytes()==original
                report['checks'].append('Native copy save, verified disk contents, original path overwrite rejection')
            desktop.window.destroy();wait('!!document.querySelector("dialog[open]")')
            desktop.window.evaluate_js('Array.from(document.querySelectorAll("dialog button")).find(x=>x.textContent==="계속 검토").click()')
            wait('!document.querySelector("dialog[open]")');assert desktop.window.evaluate_js('!!document.querySelector(".document-title")')
            report['checks'].append('Native close confirmation and cancellation preserve file review')
            desktop.window.destroy();wait('!!document.querySelector("dialog[open]")')
            desktop.window.evaluate_js('Array.from(document.querySelectorAll("dialog button")).find(x=>x.textContent==="종료 계속").click()')
        except Exception as e:report['errors'].append(f'{type(e).__name__}: {e}');desktop.close()
    watchdog=threading.Timer(150,desktop.close);watchdog.start()
    try:webview.start(drive,gui='edgechromium',private_mode=True,debug=False)
    finally:
        watchdog.cancel();server.should_exit=True;app.state.detector.close();thread.join(10);sock.close()
    report['serverStopped']=not thread.is_alive();report['temporaryCopiesRemoved']=not app.state.documents.root.exists()
    (ROOT/'output'/'file-feature-validation'/'desktop-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    assert not report['errors'] and report['serverStopped'] and report['temporaryCopiesRemoved']

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support();main()
