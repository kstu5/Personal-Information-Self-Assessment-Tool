"""Real-model before/after audit of the seven synthetic shared documents."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'validation')]
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.file_formats import Document
from run_document_audit import checkpoints, external_audit

LABELS = {'성명': 'PERSON', '생년월일': 'DT_BIRTH', '나이': 'AGE', '전화번호': 'PHONE', '이메일': 'EMAIL', '주소': 'ADDRESS'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, choices=('before', 'after'))
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    out = ROOT / 'local-only/context-review' / args.phase
    out.mkdir(parents=True, exist_ok=True)
    folder = ROOT / 'examples/documents'
    answers = {r['file']: r for r in json.loads((folder / '확인목록.json').read_text('utf-8'))}
    app = create_app(19329)
    report = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), 'phase': args.phase,
              'sourceSHA256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                  ROOT/'backend/detection_context.py',ROOT/'backend/model_a.py',ROOT/'backend/file_formats.py') if p.exists()}, 'files': []}
    with TestClient(app, base_url='http://127.0.0.1:19329') as client:
        client.headers['X-App-Token'] = app.state.token
        def post(route, data):
            response = client.post('/api/documents/' + route, json=data)
            response.raise_for_status()
            return response.json()
        def wait(ident):
            end = time.monotonic() + 180
            while time.monotonic() < end:
                job = post('status', {'id': ident})
                if job['state'] in {'ready', 'error', 'cancelled'}:
                    return job
                time.sleep(.1)
            raise TimeoutError(ident)
        for path in sorted(folder.iterdir()):
            if path.suffix not in {'.docx', '.pdf', '.xlsx'}:
                continue
            is_pdf = path.suffix == '.pdf'
            fields = answers[path.with_suffix('.docx').name if is_pdf else path.name]['fields']
            counts = collections.Counter()
            for field in fields:
                scope = None if is_pdf else field['location'] if path.suffix == '.xlsx' else Document.package_location(field['location'])
                counts[(field['value'], LABELS[field['type']], scope)] += field['count']
            checks = [{'text': value, 'label': label, 'scope': scope, 'count': count} for (value, label, scope), count in counts.items()]
            source = path.read_bytes()
            digest = hashlib.sha256(source).hexdigest()
            response = client.post('/api/documents/upload', params={'filename': path.name}, content=source, headers={'Content-Type': 'application/octet-stream'})
            response.raise_for_status()
            job = wait(response.json()['id'])
            assert job['state'] == 'ready', (path.name, job.get('error'))
            (out / (path.name + '.job.json')).write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
            scored = checkpoints({'file': path.name, 'checks': checks}, job)
            native = [c for c in job['candidates'] if not is_pdf or 'PDF 글자층' in c['location']]
            extras = [c for c in native if not any(c['label'] == item['label'] and (c['text'] in item['text'] or item['text'] in c['text']) and (not item['scope'] or item['scope'] in c['location']) for item in checks)]
            row = {'file': path.name, 'sha256': digest, 'expected': sum(c['count'] for c in scored),
                   'full': sum(c['fullyDetected'] for c in scored), 'partial': sum(c['partiallyDetected'] for c in scored),
                   'notExtracted': sum(c['notExtracted'] for c in scored), 'candidates': len(job['candidates']),
                   'scoringCandidates': len(native), 'checks': scored,
                   'extras': [{key: c[key] for key in ('text', 'label', 'location')} for c in extras]}
            if args.export:
                post('export', {'id': job['id'], 'revision': job['revision'], 'choices': {c['id']: {'mode': 'full'} for c in job['candidates']}, 'regions': [], 'textEdits': {}})
                saved = wait(job['id'])
                row['exportError'] = saved.get('error')
                row['exported'] = bool(saved.get('exportResult'))
                if saved.get('exportResult'):
                    download = client.get(f"/api/documents/{job['id']}/download")
                    download.raise_for_status()
                    target = out / (path.stem + '__reviewed' + path.suffix)
                    target.write_bytes(download.content)
                    row['residuals'] = external_audit(target, {c['text'] for c in checks})['remaining']
                    row['rescan'] = [{key: c[key] for key in ('text', 'label', 'location')} for c in saved['exportResult']['candidates']]
            row['originalUnchanged'] = hashlib.sha256(path.read_bytes()).hexdigest() == digest
            report['files'].append(row)
            (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: v for k, v in row.items() if k not in {'checks', 'sha256'}}, ensure_ascii=False), flush=True)
            post('remove', {'id': job['id']})

if __name__ == '__main__':
    main()
