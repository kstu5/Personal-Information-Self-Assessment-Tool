"""Pinned model assets. No network access in the application load path."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / '.runtime' / 'models' / 'model-a'
MANIFEST = ROOT / 'models' / 'model-a.json'


def model_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def matches_asset(path: Path, asset: dict) -> bool:
    if not path.is_file() or path.stat().st_size != asset['bytes']:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == asset['sha256']


def verify_model(path: Path = MODEL_DIR) -> None:
    for asset in model_manifest()['files']:
        if not matches_asset(path / asset['file'], asset):
            raise ValueError('Model assets are missing or do not match the pinned revision')
