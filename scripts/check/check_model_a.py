"""Compare the production hybrid against all frozen benchmark outputs, offline."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import socket
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'.runtime/python'), str(ROOT)]


def main():
    from backend.detection import detect_document
    from backend.model_a import HybridDetector
    from backend.model_assets import ML_RUNTIME, MODEL_DIR, model_manifest
    from ko_pii.core.types import DetectionResult, RiskLevel
    from ko_pii.integrations.hybrid import MergeMode, merge_detections
    from ko_pii import detect_all

    attempts=[]
    def no_network(*args, **kwargs):
        attempts.append('blocked')
        raise RuntimeError('Network is disabled for this integration test')
    socket.create_connection=no_network
    socket.socket.connect=no_network
    socket.socket.connect_ex=no_network

    base=ROOT/'output/model-benchmark-2026-10-17'
    frozen=base/'cases-frozen.json'
    data=json.loads(frozen.read_text(encoding='utf-8'))
    sha=hashlib.sha256(frozen.read_bytes()).hexdigest()
    previous={}
    for key in ['rule','A']:
        report=json.loads((base/f'results-{key}-t4.json').read_text(encoding='utf-8'))
        assert report['fixtureSha256']==sha
        previous[key]={c['id']:c['predictions'] for c in report['cases']}

    started=time.perf_counter()
    engine=HybridDetector()
    load_seconds=time.perf_counter()-started
    import torch, transformers, numpy
    for module in [torch, transformers, numpy]:
        assert Path(module.__file__).resolve().is_relative_to(ML_RUNTIME.resolve()), module.__name__
    records=[]
    for case in data['cases']:
        text=case['text']
        expected=[]
        for key in ['rule','A']:
            if key=='rule':
                rules=detect_all(text)
                assert sorted((d.label,d.start,d.end,d.text,d.confidence) for d in rules)==sorted(
                    (p['label'],p['start'],p['end'],p['text'],p['score']) for p in previous[key][case['id']])
                expected.append(rules)
                continue
            items=[]
            for prediction in previous[key][case['id']]:
                label=prediction['label']
                if key=='A' and label not in {'PERSON','ADDRESS'}:
                    continue
                risk=RiskLevel.HIGH if label=='PERSON' else RiskLevel.MEDIUM
                items.append(DetectionResult(label=label, text=prediction['text'], start=prediction['start'],
                    end=prediction['end'], risk_level=risk, confidence=prediction['score']))
            expected.append(items)
        combined=merge_detections(*expected, mode=MergeMode.ROLE_SPLIT, role_split_labels={'PERSON','ADDRESS'})
        expected_rows=sorted((d.label, len(text[:d.start].encode('utf-16-le'))//2,
                             len(text[:d.end].encode('utf-16-le'))//2, d.text) for d in combined)
        started=time.perf_counter()
        actual=detect_document('',text,engine)
        elapsed=time.perf_counter()-started
        actual_rows=sorted((d['label'],d['start'],d['end'],d['text']) for d in actual['candidates'])
        assert actual_rows==expected_rows, f"Benchmark parity failed: {case['id']}"
        for candidate in actual['candidates']:
            assert text.encode('utf-16-le')[candidate['start']*2:candidate['end']*2].decode('utf-16-le')==candidate['text']
        records.append({'id':case['id'],'characters':len(text),'candidates':len(actual_rows),'seconds':elapsed,'matchesBenchmark':True})
    # Check separate fields and astral characters before the ML-generated name/address spans.
    title='😀 이름: 김하늘'
    body='😀 주소: 서울특별시 마포구 예시로 12, 302호'
    unicode_result=detect_document(title,body,engine)
    assert any(c['label']=='PERSON' and c['text']=='김하늘' for c in unicode_result['candidates'])
    assert any(c['label']=='ADDRESS' and c['text'].endswith('302호') for c in unicode_result['candidates'])
    for c in unicode_result['candidates']:
        original=title if c['source']=='title' else body
        assert original.encode('utf-16-le')[c['start']*2:c['end']*2].decode('utf-16-le')==c['text']
    assert attempts==[]

    report={'model':model_manifest()['repo'],'revision':model_manifest()['revision'],
            'fixtureSha256':sha,'engine':engine.name,'caseCount':len(records),
            'allCasesMatchFrozenHybrid':True,'utf16AndSeparateFieldsVerified':True,
            'networkAttempts':len(attempts),'loadSeconds':load_seconds,
            'modelBytes':sum(p.stat().st_size for p in MODEL_DIR.iterdir() if p.is_file()),
            'runtimeBytes':sum(p.stat().st_size for p in ML_RUNTIME.rglob('*') if p.is_file()),
            'versions':{name:importlib.metadata.version(name) for name in ['torch','transformers','tokenizers','numpy','safetensors']},
            'cases':records}
    output=ROOT/'output/model-a-integration-2026-10-17'
    output.mkdir(parents=True,exist_ok=True)
    (output/'parity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
