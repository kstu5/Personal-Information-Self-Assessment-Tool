"""One-time asset preparation; the application never downloads models on launch."""
from pathlib import Path
import argparse
import shutil
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.model_assets import MODEL_DIR, matches_asset, model_manifest, verify_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-local', type=Path, help='Copy a previously downloaded, verified model directory')
    args = parser.parse_args()
    manifest = model_manifest()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for asset in manifest['files']:
        target = MODEL_DIR / asset['file']
        if matches_asset(target, asset):
            continue
        # Verify before replacing a file; failed downloads cannot become active assets.
        with tempfile.TemporaryDirectory(dir=MODEL_DIR) as scratch:
            staged = Path(scratch) / asset['file']
            if args.from_local:
                shutil.copyfile(args.from_local / asset['file'], staged)
            else:
                url = f"https://huggingface.co/{manifest['repo']}/resolve/{manifest['revision']}/{asset['file']}"
                with urllib.request.urlopen(url, timeout=120) as response, staged.open('wb') as output:
                    shutil.copyfileobj(response, output)
            if not matches_asset(staged, asset):
                raise RuntimeError(f"Model integrity check failed: {asset['file']}")
            staged.replace(target)
    verify_model()
    print(f"{manifest['repo']} ready: pinned revision and all file hashes verified.")


if __name__ == '__main__':
    main()
