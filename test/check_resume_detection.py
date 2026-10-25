"""Score the synthetic resume with the real detector and authenticated file API.

Core checkpoints come from the independent document answer key. PDF scoring uses
the native text layer so OCR duplicates cannot inflate the result. Raw responses
stay in local-only; this check never exports or modifies an input document.
"""
from pathlib import Path
import collections
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'test'))
from fastapi.testclient import TestClient
from backend.app import create_app
from run_document_audit import checkpoints


def main():
    folder = ROOT / 'test/shared-document-examples'
    raw = ROOT / 'local-only/resume-detection'
    raw.mkdir(parents=True, exist_ok=True)
    answer = next(entry for entry in json.loads((folder / '확인목록.json').read_text('utf-8')) if entry['file'] == '이력서_검사예시.docx')
    labels = {'성명': 'PERSON', '생년월일': 'DT_BIRTH', '나이': 'AGE', '전화번호': 'PHONE', '이메일': 'EMAIL', '주소': 'ADDRESS'}
    expected = collections.Counter((field['value'], labels[field['type']]) for field in answer['fields'] for _ in range(field['count']))
    checks = [{'text': value, 'label': label, 'count': count} for (value, label), count in expected.items()]
    app = create_app(19328)
    report = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'dataPolicy': 'Synthetic resume only; real model and authenticated API; native PDF scoring; no export',
              'files': []}
    with TestClient(app, base_url='http://127.0.0.1:19328') as client:
        client.headers['X-App-Token'] = app.state.token
        for suffix in ('.docx', '.pdf'):
            path = folder / ('이력서_검사예시' + suffix)
            source = path.read_bytes()
            before = hashlib.sha256(source).hexdigest()
            start = time.monotonic()
            response = client.post('/api/documents/upload', params={'filename': path.name}, content=source,
                                   headers={'Content-Type': 'application/octet-stream'})
            response.raise_for_status()
            job = response.json()
            while job['state'] not in {'ready', 'error', 'cancelled'}:
                if time.monotonic() - start > 180:
                    raise TimeoutError(path.name)
                time.sleep(.1)
                response = client.post('/api/documents/status', json={'id': job['id']})
                response.raise_for_status()
                job = response.json()
            (raw / (path.stem + suffix + '.json')).write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
            assert job['state'] == 'ready', job.get('error')
            scored = checkpoints({'file': path.name, 'checks': checks}, job)
            parts = {part['id']: part for part in job['manifest']['parts']}
            native = [c for c in job['candidates'] if suffix != '.pdf' or 'PDF 글자층' in parts[c['part']]['location']]
            extras = [c for c in native if not any(c['label'] == check['label'] and (c['text'] in check['text'] or check['text'] in c['text']) for check in checks)]
            row = {'file': path.name, 'sha256': before, 'seconds': round(time.monotonic() - start, 2),
                   'originalUnchanged': hashlib.sha256(path.read_bytes()).hexdigest() == before,
                   'candidatesAllChannels': len(job['candidates']), 'candidatesScoringChannel': len(native),
                   'candidateChannels': dict(collections.Counter('OCR' if 'OCR' in c['location'] else 'native' for c in job['candidates'])),
                   'expectedOccurrences': sum(c['count'] for c in scored),
                   'fullyDetected': sum(c['fullyDetected'] for c in scored),
                   'partiallyDetected': sum(c['partiallyDetected'] for c in scored),
                   'notExtracted': sum(c['notExtracted'] for c in scored),
                   'checks': scored, 'additionalCandidates': extras}
            report['files'].append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            client.post('/api/documents/remove', json={'id': job['id']}).raise_for_status()
    (raw / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    save_summary(report)


def save_summary(report):
    """Publish only concise synthetic-data findings, without API job identifiers."""
    folder = ROOT / 'test/resume-review'
    folder.mkdir(exist_ok=True)
    rows = []
    for file in report['files']:
        counts = collections.defaultdict(lambda: {'expected': 0, 'full': 0, 'partial': 0})
        for check in file['checks']:
            counts[check['label']]['expected'] += check['count']
            counts[check['label']]['full'] += check['fullyDetected']
            counts[check['label']]['partial'] += check['partiallyDetected']
        rows.append({**{key: file[key] for key in ('file', 'sha256', 'originalUnchanged', 'candidatesAllChannels',
            'candidatesScoringChannel', 'candidateChannels', 'expectedOccurrences', 'fullyDetected', 'partiallyDetected', 'notExtracted')},
            'byType': dict(counts), 'additionalCandidates': [{key: c[key] for key in ('text', 'label', 'labelName', 'location')} for c in file['additionalCandidates']]})
    (folder / 'summary.json').write_text(json.dumps({'commit': report['commit'], 'dataPolicy': report['dataPolicy'], 'files': rows}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
