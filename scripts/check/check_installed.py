"""Check an installed Windows runtime using only its Python, packages and tools."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-dir', required=True, type=Path)
    parser.add_argument('--examples', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--installed-process', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    app_dir = args.app_dir.resolve()
    python = app_dir / 'python/python.exe'
    if not args.installed_process:
        command = [str(python), '-X', 'utf8', str(Path(__file__).resolve()),
                   '--installed-process', '--app-dir', str(app_dir),
                   '--examples', str(args.examples.resolve()), '--report', str(args.report.resolve())]
        raise SystemExit(subprocess.call(command, cwd=app_dir))
    assert Path(sys.executable).resolve() == python, 'Expected installed Python'
    assert all(Path(p).resolve().is_relative_to(app_dir) for p in sys.path if p), 'External Python path detected'
    sys.path.insert(0, str(app_dir))
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    from fastapi.testclient import TestClient
    from backend.app import create_app
    from backend.model_assets import MODEL_REPO, verify_model
    verify_model()
    assert (app_dir / 'backend/HwpText.class').is_file()
    rows = []
    with TestClient(create_app(19411), base_url='http://127.0.0.1:19411') as client:
        client.headers['X-App-Token'] = client.app.state.token
        def post(route, **data):
            response = client.post('/api/documents/' + route, json=data)
            response.raise_for_status()
            return response.json()
        def wait(ident, preview=False):
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                result = post('preview' if preview else 'status', id=ident)
                if result['state'] in {'ready', 'error', 'cancelled'}:
                    assert result['state'] == 'ready', result.get('error') or result.get('message')
                    return result
                time.sleep(.3)
            raise TimeoutError('Installed document check timed out')
        check = client.post('/api/check', json={'title':'성명: 김하늘', 'body':'연락처: 010-0000-1234', 'revision':1})
        check.raise_for_status()
        assert MODEL_REPO in check.json()['engine']
        assert {'PERSON', 'PHONE'} <= {c['label'] for c in check.json()['candidates']}
        sources = sorted(args.examples.resolve().iterdir())
        assert len(sources) == 12
        for source in sources:
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            response = client.post('/api/documents/upload', params={'filename':source.name},
                                   content=source.read_bytes(), headers={'Content-Type':'application/octet-stream'})
            response.raise_for_status()
            job = wait(response.json()['id'])
            row = {'file':source.name, 'readable':True, 'candidates':len(job['candidates'])}
            assert job['manifest']['parts'] or job['manifest']['assets']
            if source.suffix in {'.docx', '.pptx'}:
                preview = wait(job['id'], True)
                assert preview['pages']
                assert client.get(f"/api/documents/{job['id']}/preview/0").status_code == 200
                row['previewPages'] = len(preview['pages'])
            if source.suffix in {'.txt', '.csv', '.tsv', '.hwpx'}:
                candidate = next(c for c in job['candidates'] if c.get('part'))
                post('export', id=job['id'], revision=job['revision'],
                     choices={candidate['id']:{'mode':'partial'}}, regions=[], textEdits={})
                assert wait(job['id'])['exportResult']
                row['exportAndReinspection'] = True
            assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
            row['sourceUnchanged'] = True
            rows.append(row)
            post('remove', id=job['id'])
            print('PASS', source.name, flush=True)
    report = {'installedPythonOnly':True, 'modelVerified':True, 'model':MODEL_REPO,
              'postDetection':True, 'files':rows,
              'scope':'Isolated installed runtime on the test host; not every Windows configuration'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('Installed runtime check passed: 12 file formats and 4 edited copies.', flush=True)


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
