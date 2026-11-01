from __future__ import annotations

import multiprocessing as mp
import threading
import time
from pathlib import Path

from backend.documents import DocumentError, validate_text
from backend.model_assets import MODEL_DIR

RISK_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']


def detect_document(title: str, body: str, engine, *, primary=False) -> dict:
    from ko_pii.labels import LABEL_INFO
    validate_text(title, body)
    candidates = []
    for source, text in [('title', title), ('body', body)]:
        # Convert Python code-point offsets into JS UTF-16 offsets once per field.
        offsets = [0]
        for char in text:
            offsets.append(offsets[-1] + (2 if ord(char) > 0xFFFF else 1))
        previous_end = 0
        detect=getattr(engine,'detect_primary',engine.detect) if primary else engine.detect
        for d in sorted(detect(text), key=lambda x: (x.start, x.end)):
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
                **({'contextReview': d.extra['contextReview']} if d.extra and d.extra.get('contextReview') else {}),
            })
    return {'candidates': candidates, 'engine': engine.name}


def review_document(body,candidates,scopes,engine):
    from ko_pii.core.types import DetectionResult,RiskLevel
    validate_text('',body)
    offsets=[0]
    for c in body:offsets.append(offsets[-1]+(2 if ord(c)>0xffff else 1))
    reverse={value:i for i,value in enumerate(offsets)}
    originals={};detections=[]
    for c in candidates:
        a,b=reverse[c['start']],reverse[c['end']]
        if not 0<=a<b<=len(body) or body[a:b]!=c['text']:raise ValueError('Invalid review source')
        key=(a,b,c['label']);originals[key]=c
        detections.append(DetectionResult(c['label'],c['text'],a,b,RiskLevel[c['risk']],.9,
                          extra={'contextReview':c['contextReview']} if c.get('contextReview') else {}))
    mapped=[]
    for s in scopes or ():
        a,b=reverse[s['start']],reverse[s['end']]
        if not 0<=a<b<=len(body):raise ValueError('Invalid review scope')
        mapped.append({**s,'start':a,'end':b,
            'personRanges':[(reverse[x],reverse[y]) for x,y in s.get('personRanges',())]})
    result=[]
    for d in engine.review(body,detections,mapped):
        original=originals.get((d.start,d.end,d.label))
        if original is None or body[d.start:d.end]!=d.text:raise ValueError('Review changed source target')
        result.append({**original,**({'contextReview':d.extra['contextReview']} if d.extra.get('contextReview') else {})})
    return {'candidates':result}


def _worker(connection, model_path: Path):
    engine = None
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
                    if isinstance(request,dict):
                        if request['op']=='review':
                            result=review_document(request['body'],request['candidates'],request['scopes'],engine)
                        else:
                            result=detect_document(request['title'],request['body'],engine,primary=True)
                    else:
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
        if engine is not None and hasattr(engine, 'close'):
            engine.close()
        connection.close()


class Detector:
    def __init__(self, timeout: float = 20, startup_timeout: float = 60, *, model_path: Path = MODEL_DIR, review_timeout: float = 300):
        self.timeout = timeout
        self.startup_timeout = startup_timeout
        self.review_timeout = review_timeout
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
        return self._request((title,body))

    def check_initial(self,title,body):
        validate_text(title,body)
        return self._request({'op':'initial','title':title,'body':body})

    def review(self,body,candidates,scopes):
        validate_text('',body)
        return self._request({'op':'review','body':body,'candidates':candidates,'scopes':scopes})

    def review_cancellable(self,body,candidates,scopes,cancel):
        validate_text('',body)
        return self._request({'op':'review','body':body,'candidates':candidates,'scopes':scopes},cancel=cancel)

    def _wait(self,connection,timeout,cancel):
        if cancel is None:
            return self._receive(connection,timeout)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if cancel.is_set():
                raise DocumentError('검사를 취소했습니다.', 'cancelled')
            if connection.poll(min(.2,max(0,deadline-time.monotonic()))):
                return connection.recv()
        raise DocumentError('검사 시간이 초과되었습니다. 잠시 후 다시 검사해 주세요.', 'timeout')

    def _request(self,payload,*,cancel=None):
        if not self.gate.acquire(blocking=False):
            raise DocumentError('검사가 진행 중입니다. 잠시 후 다시 시도해 주세요.', 'busy')
        started = time.monotonic()
        try:
            connection, starting = self._connection_for_check()
            if starting and not self._wait(connection, self.startup_timeout,cancel).get('ready'):
                raise DocumentError('검사 모델을 준비하지 못했습니다. 설치 상태를 확인한 뒤 프로그램을 다시 실행해 주세요.', 'model_unavailable')
            connection.send(payload)
            from backend.qwen_runtime import selected_secondary
            secondary = not isinstance(payload,dict) or payload.get('op')=='review'
            timeout=self.review_timeout if secondary and selected_secondary()=='qwen3.5-0.8b' else self.timeout
            message = self._wait(connection,timeout,cancel)
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
