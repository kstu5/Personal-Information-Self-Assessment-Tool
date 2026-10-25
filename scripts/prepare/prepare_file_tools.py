"""Auto-download and verify external file inspection tools."""
from pathlib import Path
import hashlib
import shutil
import urllib.request
import sys

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / '.runtime' / 'file-tools'

# Download sources and checksums
DOWNLOADS = {
    'tessdata/eng.traineddata': {
        'url': 'https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata',
        'sha256': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
    },
    'tessdata/kor.traineddata': {
        'url': 'https://github.com/tesseract-ocr/tessdata_fast/raw/main/kor.traineddata',
        'sha256': '6b85e11d9bbf07863b97b3523b1b112844c43e713df8b66418a081fd1060b3b2',
    },
    'hwplib-1.1.11.jar': {
        'url': 'https://repo1.maven.org/maven2/kr/dogfoot/hwplib/1.1.11/hwplib-1.1.11.jar',
        'sha256': 'fd464ff56eec7f58d463f7533da7501d4bb8261a225c20b7b19bed9e137f7e04',
    },
}

def download_file(url, target, expected_sha256):
    """Download file with progress and verify checksum."""
    target.parent.mkdir(parents=True, exist_ok=True)

    print(f'Downloading {target.name}...', end=' ', flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            total = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunks = []

            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    print(f'\rDownloading {target.name}... {pct}%', end='', flush=True)

            data = b''.join(chunks)
            print(f'\rDownloading {target.name}... done ({len(data) // 1024} KB)')

            # Verify checksum
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected_sha256:
                raise RuntimeError(f'Checksum mismatch for {target.name}: expected {expected_sha256}, got {actual}')

            target.write_bytes(data)
            return True

    except Exception as e:
        print(f'\rDownloading {target.name}... FAILED ({e})')
        return False

def main():
    DEST.mkdir(parents=True, exist_ok=True)

    # Auto-download missing tools
    for rel_path, info in DOWNLOADS.items():
        target = DEST / rel_path

        # Check if already exists and valid
        if target.exists():
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual == info['sha256']:
                continue  # Already have valid file

        # Try to download
        if not download_file(info['url'], target, info['sha256']):
            print(f'  Skipping {rel_path} - download failed')

    # Check for LibreOffice in research folder (too large to auto-download)
    RESEARCH = ROOT / 'research' / 'document-edit-validation-2026-10-23'
    lo = RESEARCH / 'libreoffice-portable'
    if lo.exists() and not (DEST / 'libreoffice' / 'program' / 'soffice.com').exists():
        print('Copying LibreOffice from research folder...')
        shutil.copytree(lo, DEST / 'libreoffice', dirs_exist_ok=True)

    report()

def report():
    choices = sorted(Path('C:/Program Files/Java').glob('jdk*/bin/java.exe'), reverse=True)
    bundled = DEST/'jre'/'bin'/'java.exe'
    java = str(bundled) if bundled.is_file() else str(choices[0]) if choices else shutil.which('java')
    checks = [
        ('OCR data (eng)', (DEST/'tessdata'/'eng.traineddata').exists(), 'image OCR', '.runtime/file-tools/tessdata/eng.traineddata'),
        ('OCR data (kor)', (DEST/'tessdata'/'kor.traineddata').exists(), 'image OCR', '.runtime/file-tools/tessdata/kor.traineddata'),
        ('LibreOffice', (DEST/'libreoffice'/'program'/'soffice.com').is_file(), 'Word/PPT preview and XLSX value check', '.runtime/file-tools/libreoffice/program/soffice.com'),
        ('hwplib 1.1.11', (DEST/'hwplib-1.1.11.jar').exists(), 'HWP reading', '.runtime/file-tools/hwplib-1.1.11.jar'),
        ('Java (11 or later required; version not checked)', bool(java), 'HWP reading', 'java on PATH'),
    ]
    print('File inspection tools (setup guide: README.md):')
    for name, ok, feature, where in checks:
        print(f'  [OK]      {name}' if ok else f'  [MISSING] {name} -> {feature} unavailable; expected at {where}')
    if all(ok for _, ok, _, _ in checks): print('All file inspection tools are ready.')
    else: print('Missing tools only disable the features listed above; post inspection is not affected.')

if __name__ == '__main__': main()
