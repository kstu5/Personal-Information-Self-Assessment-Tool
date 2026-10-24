from __future__ import annotations

import multiprocessing as mp
import threading
import time
from pathlib import Path

from backend.documents import DocumentError, validate_text
from backend.model_assets import MODEL_DIR

RISK_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']


def detect_document(title: str, body: str, engine) -> dict:
    from ko_pii.labels import LABEL_INFO
    validate_text(title, body)
    candidates = []
    for source, text in [('title', title), ('body', body)]:
        # Convert Python code-point offsets into JS UTF-16 offsets once per field.
        offsets = [0]
        for char in text:
            offsets.append(offsets[-1] + (2 if ord(char) > 0xFFFF else 1))
        previous_end = 0
        for d in sorted(engine.detect(text), key=lambda x: (x.start, x.end)):
            if not 0 <= d.start < d.end <= len(text) or text[d.start:d.end] != d.text or d.start < previous_end:
                raise ValueError('Invalid detector offsets')
            previous_end = d.end
            risk = d.risk_level.name
            if risk not in RISK_ORDER:
                raise ValueError('Unsupported risk level')
            candidates.append({
                'id': f'{source}-{d.start}-{d.end}-{d.label}', 'source': source,
                'start': offsets[d.start], 'end': offsets[d.end], 'text': d.text,
                'label': d.label, 'labelName': LABEL_INFO.get(d.label, (d.label,))[0],
                'risk': risk,
            })
    return {'candidates': candidates, 'engine': engine.name}


def _worker(connection, model_path: Path):
    try:
        try:
            from backend.model_a import HybridDetector
            engine = HybridDetector(model_path)
        except Exception:
            connection.send({'ready': False})
            return
        connection.send({'ready': True})
        while True:
            request = connection.recv()
            try:
                if request is None:
                    return
                try:
                    result = detect_document(*request, engine)
                    connection.send({'ok': True, 'result': result})
                except Exception:
                    # Never send exception strings containing original text or log input.
                    connection.send({'ok': False})
                finally:
                    result = None
            finally:
                # Keep model weights, but no reference to the previous document while idle.
                request = None
    except (EOFError, OSError):
        pass
    finally:
        connection.close()


class Detector:
    def __init__(self, timeout: float = 20, startup_timeout: float = 60, *, model_path: Path = MODEL_DIR):
        self.timeout = timeout
        self.startup_timeout = startup_timeout
        self.model_path = model_path
        self.gate = threading.Lock()
        self._state_lock = threading.Lock()
        self._closed = threading.Event()
        self._process = None
        self._connection = None

    def _stop_locked(self):
        process, connection = self._process, self._connection
        self._process = self._connection = None
        if process is not None:
            if process.pid:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
            process.close()
        if connection is not None:
            connection.close()

    def close(self):
        self._closed.set()
        with self._state_lock:
            self._stop_locked()

    def _connection_for_check(self):
        with self._state_lock:
            if self._closed.is_set():
                raise DocumentError('프로그램을 종료하는 중입니다.', 'check_failed')
            if self._process is not None and self._process.is_alive():
                return self._connection, False
            self._stop_locked()
            context = mp.get_context('spawn')
            parent, child = context.Pipe(duplex=True)
            self._connection = parent
            self._process = context.Process(target=_worker, args=(child, self.model_path), daemon=True)
            try:
                self._process.start()
            finally:
                child.close()
            return parent, True

    @staticmethod
    def _receive(connection, timeout):
        if not connection.poll(timeout):
            raise DocumentError('검사 시간이 초과되었습니다. 잠시 후 다시 검사해 주세요.', 'timeout')
        return connection.recv()

    def check(self, title: str, body: str) -> dict:
        validate_text(title, body)
        if not self.gate.acquire(blocking=False):
            raise DocumentError('검사가 진행 중입니다. 잠시 후 다시 시도해 주세요.', 'busy')
        started = time.monotonic()
        try:
            connection, starting = self._connection_for_check()
            if starting and not self._receive(connection, self.startup_timeout).get('ready'):
                raise DocumentError('검사 모델을 준비하지 못했습니다. 설치 상태를 확인한 뒤 프로그램을 다시 실행해 주세요.', 'model_unavailable')
            connection.send((title, body))
            message = self._receive(connection, self.timeout)
            if not message['ok']:
                raise DocumentError('검사를 완료하지 못했습니다. 다시 시도해 주세요.', 'check_failed')
            return {**message['result'], 'elapsedMs': round((time.monotonic() - started) * 1000)}
        except Exception as error:
            # Discard the pipe too, so a late response can never become a later result.
            with self._state_lock:
                self._stop_locked()
            if isinstance(error, DocumentError):
                raise
            raise DocumentError('검사를 완료하지 못했습니다. 다시 시도해 주세요.', 'check_failed') from None
        finally:
            self.gate.release()
