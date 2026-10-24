from pathlib import Path
import threading

from backend.documents import DocumentError


class Desktop:
    def __init__(self):
        self.window = None
        self.allow_close = False

    def choose_save(self, filename: str):
        import webview
        result = self.window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename,
                                                file_types=('게시 전 작업 파일 (*.piipost)',))
        if not result:
            return None
        path = Path(result[0] if isinstance(result, (tuple, list)) else result)
        if path.suffix.lower() != '.piipost':
            # Do not append after selection: doing so could bypass the native overwrite confirmation.
            raise DocumentError('파일 이름 끝에 .piipost를 붙여 다시 저장해 주세요.')
        return path

    def choose_open(self):
        import webview
        result = self.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                                file_types=('게시 전 작업 파일 (*.piipost)', '모든 파일 (*.*)'))
        return Path(result[0]) if result else None

    def choose_documents(self):
        import webview
        result = self.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
            file_types=('검사할 문서 (*.hwp;*.hwpx;*.docx;*.xlsx;*.pptx;*.pdf;*.csv;*.tsv;*.txt;*.png;*.jpg;*.jpeg)', '모든 파일 (*.*)'))
        return [Path(p) for p in result] if result else []

    def choose_copy_save(self, filename):
        import webview
        result = self.window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename,
            file_types=(f'수정 사본 (*{Path(filename).suffix})',))
        return Path(result[0] if isinstance(result, (tuple,list)) else result) if result else None

    def closing(self):
        if self.allow_close:
            return True
        def ask():
            try:
                ready = self.window.evaluate_js('typeof window.requestAppClose === "function"')
                if ready:
                    self.window.evaluate_js('window.requestAppClose()')
                else:
                    self.close()
            except Exception:
                self.close()
        # closing is synchronous on the native UI thread; don't block it on JS.
        threading.Thread(target=ask, daemon=True).start()
        return False

    def close(self):
        self.allow_close = True
        threading.Timer(.1, self.window.destroy).start()
