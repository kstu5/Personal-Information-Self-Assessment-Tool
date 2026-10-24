import multiprocessing
import threading
import time

import pytest

from backend.detection import Detector
from backend.documents import DocumentError
from backend.model_assets import matches_asset, model_manifest, verify_model


def test_pinned_assets_and_corruption(tmp_path):
    verify_model()
    asset=model_manifest()['files'][0]
    corrupt=tmp_path/asset['file']
    corrupt.write_bytes(b'x'*asset['bytes'])
    assert not matches_asset(corrupt, asset)
    with pytest.raises(ValueError):
        verify_model(tmp_path)


def test_worker_reuse_timeout_recovery_and_close():
    before={p.pid for p in multiprocessing.active_children()}
    detector=Detector()
    try:
        detector.check('', '이름: 김하늘')
        first=detector._process.pid
        assert detector.check('', '안녕하세요.')['candidates']==[]
        assert detector._process.pid==first
        detector.timeout=.00001
        with pytest.raises(DocumentError) as error:
            detector.check('', '가나다라마바사 '*3700)
        assert error.value.code=='timeout'
        assert detector._process is None and not detector.gate.locked()
        detector.timeout=20
        result=detector.check('', '전화: 010-0000-0000')
        assert any(c['label']=='PHONE' for c in result['candidates'])
        assert detector._process.pid != first
        detector._process.terminate()
        detector._process.join(timeout=3)
        assert detector.check('', '안녕하세요.')['candidates']==[]
    finally:
        detector.close()
    assert {p.pid for p in multiprocessing.active_children()}==before
    with pytest.raises(DocumentError):
        detector.check('', '안녕하세요.')


def test_busy_and_close_during_model_startup():
    before={p.pid for p in multiprocessing.active_children()}
    detector=Detector()
    errors=[]
    def check():
        try:
            detector.check('', '김하늘입니다.')
        except DocumentError as error:
            errors.append(error.code)
    thread=threading.Thread(target=check)
    thread.start()
    try:
        deadline=time.monotonic()+5
        while detector._process is None and time.monotonic()<deadline:
            time.sleep(.01)
        assert detector.gate.locked()
        with pytest.raises(DocumentError) as error:
            detector.check('', '안녕하세요.')
        assert error.value.code=='busy'
        detector.close()
        thread.join(timeout=5)
        assert not thread.is_alive() and not detector.gate.locked()
        assert errors==['check_failed']
    finally:
        detector.close()
        thread.join(timeout=5)
    assert {p.pid for p in multiprocessing.active_children()}==before
