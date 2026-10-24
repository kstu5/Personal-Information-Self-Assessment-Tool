"""Start the local Windows app. --browser and --headless support development."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def main():
    import argparse
    import ctypes
    import hashlib
    import json
    import socket
    import threading
    import time
    import webbrowser
    import uvicorn
    from backend.app import create_app
    from backend.desktop import Desktop

    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--ready-file', type=Path)
    args = parser.parse_args()
    if not (ROOT/'dist'/'index.html').exists():
        raise RuntimeError('화면 빌드가 필요합니다. 먼저 설치 안내를 확인해 주세요.')
    mutex = None
    if sys.platform == 'win32' and not args.headless:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        name = 'Local\\BeforePost-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
        mutex = kernel.CreateMutexW(None, False, name)
        if ctypes.get_last_error() == 183:
            ctypes.windll.user32.MessageBoxW(None, '게시 전 프로그램이 이미 실행 중입니다.', '게시 전', 0x40)
            kernel.CloseHandle(mutex)
            return
    sock = socket.socket()
    sock.bind(('127.0.0.1', args.port))
    sock.listen(128)
    port = sock.getsockname()[1]
    desktop = None if args.browser or args.headless else Desktop()
    app = create_app(port, desktop=desktop)
    # pythonw has no stdout/stderr; the default console formatter would fail on startup.
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, access_log=False, log_level='critical', log_config=None))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError('로컬 검사 기능을 시작하지 못했습니다.')
            time.sleep(.05)
        if not server.started:
            raise RuntimeError('로컬 검사 기능 시작 시간이 초과되었습니다.')
        url = f'http://127.0.0.1:{port}'
        if args.ready_file:
            args.ready_file.parent.mkdir(parents=True, exist_ok=True)
            args.ready_file.write_text(json.dumps({'url': url}), encoding='utf-8')
        if desktop:
            import webview
            desktop.window = webview.create_window('게시 전 · 개인정보 검토', url, width=1280, height=880, min_size=(760, 600), background_color='#f5f7f8')
            desktop.window.events.closing += desktop.closing
            webview.start(gui='edgechromium', private_mode=True, debug=False)
        else:
            if args.browser:
                webbrowser.open(url)
            print(f'게시 전: {url}\n종료하려면 Ctrl+C를 누르세요.', flush=True)
            while thread.is_alive():
                thread.join(timeout=.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        app.state.detector.close()
        thread.join(timeout=4)
        sock.close()
        if mutex:
            kernel.CloseHandle(mutex)


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        main()
    except Exception:
        # No draft text or paths from files are included in startup diagnostics.
        if sys.platform == 'win32' and not any(x in sys.argv for x in ['--headless', '--browser']):
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, '프로그램을 실행하지 못했습니다. 실행 환경과 WebView2 설치를 확인해 주세요. 자세한 안내는 README.md에 있습니다.', '게시 전', 0x10)
        else:
            raise
