"""Native WebView2 smoke test; picker choices are replaced with temporary paths."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.runtime'/'python'))
sys.path.insert(0,str(ROOT))


def main():
    import json, socket, threading, time
    import httpx, uvicorn, webview
    from backend.app import create_app
    from backend.desktop import Desktop
    from backend.documents import parse_document
    out=ROOT/'tmp'/'desktop-check';out.mkdir(parents=True,exist_ok=True)
    selected=out/'선택한 위치.piipost'
    desktop=Desktop()
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
    port=sock.getsockname()[1];url=f'http://127.0.0.1:{port}'
    app=create_app(port,desktop=desktop)
    server=uvicorn.Server(uvicorn.Config(app,access_log=False,log_level='critical',log_config=None))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        if not thread.is_alive():raise RuntimeError('Test server failed to start')
        time.sleep(.05)
    assert server.started, 'Test server startup timed out'
    desktop.window=webview.create_window('개인정보 자가진단 도구 실행 확인',url,width=1100,height=800,hidden=True)
    desktop.window.events.closing += desktop.closing
    # The native window and app API are real; only OS dialog selection is deterministic.
    desktop.window.create_file_dialog=lambda *args,**kwargs:(str(selected),)
    report={'checks':[],'errors':[]}
    def wait_for(expression):
        for _ in range(200):
            if desktop.window.evaluate_js(expression):return
            time.sleep(.05)
        raise AssertionError(expression)
    def drive():
        try:
            desktop.window.events.loaded.wait(timeout=20)
            wait_for('!!document.querySelector(".welcome")')
            report['checks'].append('Native WebView2 loads production React app')
            headers={'X-App-Token':app.state.token,'Origin':url}
            with httpx.Client(base_url=url,headers=headers,trust_env=False,timeout=90) as c:
                r=c.post('/api/files/save',json={'title':'실제 창: 저장?','body':'한글 😀\n다음 줄','filename':'실제 창 저장'});r.raise_for_status()
                assert parse_document(selected.read_bytes())['title']=='실제 창: 저장?'
                r=c.post('/api/files/open',json={});r.raise_for_status();assert r.json()['document']['body']=='한글 😀\n다음 줄'
                r=c.post('/api/check',json={'title':'이름: 김하늘','body':'주소: 서울특별시 마포구 예시로 12, 302호','revision':1})
                r.raise_for_status()
                assert 'atonlee/koelectra-ko-pii-ner' in r.json()['engine']
                assert any(x['label']=='PERSON' and x['text']=='김하늘' for x in r.json()['candidates'])
                assert any(x['label']=='ADDRESS' and x['text'].endswith('302호') for x in r.json()['candidates'])
                model_pid=app.state.detector._process.pid
                report['modelPid']=model_pid
            report['checks'].append('Native app API uses the local A model for names and detailed addresses')
            report['checks'].append('Native picker adapter and real disk save/open')
            desktop.window.evaluate_js('document.querySelector(".welcome .text-button").click()')
            wait_for('!!document.querySelector("#post-title")')
            desktop.window.destroy()
            wait_for('!!document.querySelector("dialog[open]")')
            report['checks'].append('Native close with dirty draft opens save/discard/cancel guard')
            desktop.window.evaluate_js('Array.from(document.querySelectorAll("dialog button")).find(x=>x.textContent==="취소").click()')
            wait_for('!document.querySelector("dialog")')
            assert desktop.window.evaluate_js('document.querySelector("#post-title").value').startswith('10월 독서')
            report['checks'].append('Cancel native close preserves original draft')
            desktop.window.destroy();wait_for('!!document.querySelector("dialog[open]")')
            desktop.window.evaluate_js('Array.from(document.querySelectorAll("dialog button")).find(x=>x.textContent==="저장하지 않고 계속").click()')
        except Exception as error:
            report['errors'].append(f'{type(error).__name__}: {error}')
            desktop.close()
        finally:
            (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    watchdog=threading.Timer(120,desktop.close);watchdog.start()
    try:webview.start(drive,gui='edgechromium',private_mode=True,debug=False)
    finally:
        watchdog.cancel();server.should_exit=True;app.state.detector.close();thread.join(timeout=4);sock.close()
    report['serverStopped']=not thread.is_alive()
    report['modelWorkerStopped']=app.state.detector._process is None
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    assert not report['errors'] and report['serverStopped'] and report['modelWorkerStopped']


if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
