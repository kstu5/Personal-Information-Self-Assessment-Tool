from __future__ import annotations

import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr
from starlette.concurrency import run_in_threadpool

from backend.detection import Detector
from backend.file_review import FileReviewStore, MAX_UPLOAD
from backend.documents import DocumentError, FileStore, MAX_BODY, MAX_TITLE, suggested_filename, validate_text


class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: StrictStr
    body: StrictStr


class CheckRequest(Draft):
    revision: StrictInt


class SaveRequest(Draft):
    fileId: StrictStr | None = None
    saveAs: bool = False
    filename: StrictStr | None = None


class DocumentRef(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: StrictStr


class ExportRequest(DocumentRef):
    revision: StrictStr
    choices: dict[str, dict]
    regions: list[dict]
    textEdits: dict[str, StrictStr] = {}


class PreviewRequest(DocumentRef):
    output: bool = False
    retry: bool = False


def create_app(port: int, *, desktop: Any = None, dist: Path | None = None) -> FastAPI:
    store, detector = FileStore(), Detector()
    documents = FileReviewStore(detector)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await run_in_threadpool(documents.close)
            await run_in_threadpool(detector.close)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    token = secrets.token_urlsafe(32)
    host = f'127.0.0.1:{port}'
    origin = f'http://{host}'
    dist = dist or Path(__file__).resolve().parents[1] / 'dist'
    app.state.token, app.state.store, app.state.detector = token, store, detector
    app.state.origin = origin
    app.state.documents = documents

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        headers = request.headers
        error = None
        if headers.get('host') != host:
            error = '허용되지 않은 접속 주소입니다.'
        elif headers.get('origin') not in (None, origin):
            error = '허용되지 않은 요청 출처입니다.'
        elif headers.get('sec-fetch-site') not in (None, 'same-origin', 'none'):
            error = '다른 페이지에서 접근할 수 없습니다.'
        elif request.url.path.startswith('/api/') and not secrets.compare_digest(headers.get('x-app-token', ''), token):
            error = '접속 세션이 올바르지 않습니다. 프로그램을 다시 열어 주세요.'
        if error:
            response = JSONResponse({'message': error, 'code': 'forbidden'}, status_code=403)
        else:
            if request.method == 'POST':
                upload = request.url.path == '/api/documents/upload'
                # Bound streamed/chunked bodies too, not only Content-Length.
                content = bytearray()
                async for chunk in request.stream():
                    content.extend(chunk)
                    if len(content) > (MAX_UPLOAD if upload else 2_000_000 if request.url.path == '/api/documents/export' else 500_000):
                        return JSONResponse({'message': '요청이 너무 큽니다.', 'code': 'too_large'}, status_code=413)
                request._body = bytes(content)
                if headers.get('content-type', '').split(';')[0] != ('application/octet-stream' if upload else 'application/json'):
                    return JSONResponse({'message': '올바른 요청 형식이 아닙니다.'}, status_code=415)
            response = await call_next(request)
        response.headers.update({
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'none'",
        })
        return response

    @app.exception_handler(DocumentError)
    async def document_error(request, error):
        status = 408 if error.code == 'timeout' else 409 if error.code in ['file_changed', 'missing_file', 'busy'] else 400
        return JSONResponse({'message': str(error), 'code': error.code}, status_code=status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse({'message': '요청 내용을 확인해 주세요.', 'code': 'invalid_request'}, status_code=422)

    @app.get('/')
    async def index():
        boot = json.dumps({'token': token, 'desktop': desktop is not None, 'maxTitle': MAX_TITLE, 'maxBody': MAX_BODY}, ensure_ascii=True)
        html = (dist/'index.html').read_text(encoding='utf-8')
        # JSON is inert text in a meta attribute. No raw draft text is interpolated.
        import html as html_module
        html = html.replace('<!--APP_BOOT-->', f'<meta name="app-boot" content="{html_module.escape(boot, quote=True)}">')
        return HTMLResponse(html)

    @app.get('/assets/{asset_path:path}')
    async def asset(asset_path: str):
        path = (dist/'assets'/asset_path).resolve()
        if not path.is_relative_to((dist/'assets').resolve()) or not path.is_file():
            return JSONResponse({'message': '파일을 찾을 수 없습니다.'}, status_code=404)
        # Set correct MIME type for JavaScript and CSS
        media_type = None
        if path.suffix == '.js':
            media_type = 'application/javascript'
        elif path.suffix == '.css':
            media_type = 'text/css'
        return FileResponse(path, media_type=media_type)

    @app.get('/api/health')
    async def health():
        return {'status': 'ready', 'desktop': desktop is not None}

    @app.post('/api/check')
    async def check(payload: CheckRequest):
        result = await run_in_threadpool(detector.check, payload.title, payload.body)
        return {**result, 'revision': payload.revision}

    @app.post('/api/files/save')
    async def save(payload: SaveRequest):
        validate_text(payload.title, payload.body)
        if desktop is None:
            raise DocumentError('브라우저의 파일 선택 기능을 사용해 주세요.')
        chosen = None
        if payload.saveAs or payload.fileId is None:
            # Re-sanitize the edited suggestion; do not accept paths from the browser.
            filename = suggested_filename(payload.filename if payload.filename is not None else payload.title)
            chosen = await run_in_threadpool(desktop.choose_save, filename)
            if chosen is None:
                return {'cancelled': True}
        return await run_in_threadpool(store.save, payload.title, payload.body, file_id=payload.fileId, chosen_path=chosen)

    @app.post('/api/files/open')
    async def open_file():
        if desktop is None:
            raise DocumentError('브라우저의 파일 선택 기능을 사용해 주세요.')
        selected = await run_in_threadpool(desktop.choose_open)
        if selected is None:
            return {'cancelled': True}
        return await run_in_threadpool(store.open, selected)

    @app.post('/api/window/close')
    async def close_window():
        if desktop:
            desktop.close()
        return {'ok': True}

    @app.post('/api/documents/upload')
    async def upload_document(request: Request, filename: str):
        return await run_in_threadpool(documents.upload, filename, await request.body())

    @app.post('/api/documents/open')
    async def open_documents():
        if desktop is None: raise DocumentError('브라우저에서 파일 추가 버튼을 사용해 주세요.')
        paths = await run_in_threadpool(desktop.choose_documents)
        return {'files': await run_in_threadpool(documents.open_paths, paths or [])}

    @app.post('/api/documents/status')
    async def document_status(payload: DocumentRef):
        return documents.status(payload.id)

    @app.post('/api/documents/list')
    async def list_documents():
        return {'files': documents.list_jobs()}

    @app.post('/api/documents/export')
    async def export_document(payload: ExportRequest):
        return documents.export(payload.id, payload.revision, payload.choices, payload.regions, payload.textEdits)

    @app.post('/api/documents/preview')
    async def preview_document(payload: PreviewRequest):
        return documents.preview(payload.id,payload.output,payload.retry)

    @app.get('/api/documents/{ident}/preview/{page}')
    async def preview_document_page(ident: str,page: int,output: bool=False):
        return FileResponse(documents.preview_asset(ident,page,output),media_type='image/png')

    @app.post('/api/documents/cancel')
    async def cancel_document(payload: DocumentRef):
        return await run_in_threadpool(documents.cancel, payload.id)

    @app.post('/api/documents/remove')
    async def remove_document(payload: DocumentRef):
        return await run_in_threadpool(documents.remove, payload.id)

    @app.get('/api/documents/{ident}/assets/{asset_id}')
    async def document_asset(ident: str, asset_id: str, output: bool = False):
        return FileResponse(documents.asset(ident, asset_id, output), media_type='image/png')

    @app.get('/api/documents/{ident}/download')
    async def download_document(ident: str):
        path, name = await run_in_threadpool(documents.output, ident)
        return FileResponse(path, filename=name, media_type='application/octet-stream')

    @app.post('/api/documents/save')
    async def save_document_copy(payload: DocumentRef):
        if desktop is None: raise DocumentError('브라우저의 사본 다운로드를 사용해 주세요.')
        path, name = await run_in_threadpool(documents.output, payload.id)
        chosen = await run_in_threadpool(desktop.choose_copy_save, name)
        if chosen is None: return {'cancelled': True}
        return await run_in_threadpool(documents.save_new, payload.id, chosen)

    return app
