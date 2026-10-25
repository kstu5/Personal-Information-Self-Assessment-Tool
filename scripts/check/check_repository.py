"""Check the public file boundary, maintained documentation links and example hashes."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOTS = {'local-only', '.runtime', '.venv', '.tools', 'node_modules', 'dist',
                 'tmp', 'research', 'output', 'reports', 'report_qa', 'test'}
PRIVATE_PARTS = {'__pycache__', '.pytest_cache', 'qa', 'reviewed', 'stage', 'out'}


def public_files(staged=False):
    args = ['git', 'ls-files', '--cached']
    if not staged:
        args += ['--others', '--exclude-standard']
    names = subprocess.check_output(args + ['-z'], cwd=ROOT).decode('utf-8').split('\0')
    return sorted({name for name in names if name and (staged or (ROOT / name).is_file())})


def check_boundary(names):
    errors = []
    for name in names:
        if name == 'local-only/README.md':
            continue
        path = Path(name)
        if path.parts[0] in PRIVATE_ROOTS or PRIVATE_PARTS.intersection(path.parts):
            errors.append(f'Local-only path included: {name}')
        if path.name in {'runtime.local.json', 'list.txt'} or path.suffix in {'.piipost', '.log', '.zip', '.exe', '.pyc', '.safetensors', '.onnx'}:
            errors.append(f'Generated or local file included: {name}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='Check only files in the Git index')
    args = parser.parse_args()
    names = public_files(args.staged)
    errors = check_boundary(names)
    for name in names:
        if not (ROOT / name).is_file():
            errors.append(f'Indexed file missing from working tree: {name}')
            continue
        if name.endswith('.py'):
            try:
                compile((ROOT / name).read_text('utf-8-sig'), name, 'exec')
            except SyntaxError as exc:
                errors.append(f'{name}: {exc}')
        if name.endswith('.md') and '/archive/' not in name:
            for ref in re.findall(r'\]\(([^)]+)\)', (ROOT / name).read_text('utf-8-sig')):
                target = unquote(ref.split('#')[0]).strip('<>')
                if not target or re.match(r'^[a-zA-Z][\w+.-]*:', target) or target.startswith('/'):
                    continue
                if not ((ROOT / name).parent / target).exists():
                    errors.append(f'Broken documentation link: {name} -> {ref}')
    manifest = json.loads((ROOT / 'examples/formats/제작_검증.json').read_text('utf-8'))
    for row in manifest['files']:
        path = ROOT / 'examples/formats/files' / row['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            errors.append(f'Example hash mismatch: {row["file"]}')
    if len(manifest['files']) != 12:
        errors.append('Expected twelve format examples')
    for private in ['local-only/inputs/example.docx', 'local-only/outputs/report.json',
                    'validation/qa/probe.json', 'validation/reviewed/copy.docx',
                    '.runtime/models/model-a/model.safetensors', 'installer/out/setup.exe']:
        if subprocess.run(['git', 'check-ignore', '--no-index', '-q', private], cwd=ROOT).returncode != 0:
            errors.append(f'Private path is not ignored: {private}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(names)} public files; private boundary, Python syntax, maintained Markdown links, and 12 example hashes.')


if __name__ == '__main__':
    main()
