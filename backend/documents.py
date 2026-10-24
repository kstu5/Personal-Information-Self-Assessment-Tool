from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "before-post-document"
VERSION = 1
MAX_TITLE = 300
MAX_BODY = 30_000
MAX_FILE_BYTES = 2_000_000


class DocumentError(Exception):
    def __init__(self, message: str, code: str = "invalid_file"):
        super().__init__(message)
        self.code = code


def validate_text(title: object, body: object) -> None:
    if not isinstance(title, str) or not isinstance(body, str):
        raise DocumentError("제목과 본문이 올바른 글 형식이 아닙니다.")
    if len(title) > MAX_TITLE or len(body) > MAX_BODY:
        raise DocumentError("제목은 300자, 본문은 30,000자까지 사용할 수 있습니다.", "too_large")
    if any(0xD800 <= ord(c) <= 0xDFFF for c in title + body):
        raise DocumentError("올바르게 읽을 수 없는 문자가 포함되어 있습니다.")


def suggested_filename(title: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title)
    name = re.sub(r'\s+', ' ', name).strip().rstrip('. ')
    # Keep a conservative filename budget; the actual path is checked by the OS.
    name = name.encode('utf-16-le')[:240].decode('utf-16-le', errors='ignore').rstrip('. ')
    if not name:
        name = '제목 없음'
    stem = name.split('.')[0].upper()
    if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]', stem):
        name = '_' + name
    return name + '.piipost'


def serialize_document(title: str, body: str) -> bytes:
    validate_text(title, body)
    return json.dumps({
        'format': FORMAT, 'version': VERSION, 'title': title, 'body': body,
        'savedAt': datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2).encode('utf-8')


def parse_document(content: bytes) -> dict:
    if len(content) > MAX_FILE_BYTES:
        raise DocumentError("파일이 너무 큽니다. 2 MB 이하의 작업 파일을 선택해 주세요.", "too_large")
    try:
        data = json.loads(content.decode('utf-8-sig'))
    except (UnicodeError, ValueError, RecursionError):
        raise DocumentError("작업 파일을 읽을 수 없습니다. 파일이 손상되었거나 다른 형식입니다.") from None
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise DocumentError("이 프로그램에서 저장한 작업 파일을 선택해 주세요.")
    if type(data.get('version')) is not int or data['version'] != VERSION:
        raise DocumentError("지원하지 않는 작업 파일 버전입니다.", "unsupported_version")
    validate_text(data.get('title'), data.get('body'))
    if not isinstance(data.get('savedAt'), str):
        raise DocumentError("저장 시각이 올바르지 않습니다.")
    try:
        datetime.fromisoformat(data['savedAt'].replace('Z', '+00:00'))
    except ValueError:
        raise DocumentError("저장 시각이 올바르지 않습니다.") from None
    return {k: data[k] for k in ['format', 'version', 'title', 'body', 'savedAt']}


def atomic_write(path: Path, content: bytes) -> None:
    """Replace only after a complete flushed write, in the same filesystem."""
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.before-post-', suffix='.tmp', dir=path.parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise DocumentError("저장하지 못했습니다. 권한·저장 공간·장치 연결을 확인하거나 다른 위치에 저장해 주세요.", "write_failed") from None
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


@dataclass
class OpenFile:
    path: Path
    digest: str


class FileStore:
    """Only OS-picker-selected paths enter this registry. HTTP cannot supply paths."""
    def __init__(self):
        self.files: dict[str, OpenFile] = {}
        self.lock = threading.Lock()

    def open(self, path: Path) -> dict:
        try:
            with path.open('rb') as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
        except OSError:
            raise DocumentError("파일을 열지 못했습니다. 파일 위치와 읽기 권한을 확인해 주세요.", "read_failed") from None
        data = parse_document(raw)
        with self.lock:
            key = secrets.token_urlsafe(24)
            self.files[key] = OpenFile(path, hashlib.sha256(raw).hexdigest())
        return {'fileId': key, 'name': path.name, 'document': data}

    def save(self, title: str, body: str, *, file_id: str | None = None, chosen_path: Path | None = None) -> dict:
        raw = serialize_document(title, body)
        with self.lock:
            if chosen_path is not None:
                path = chosen_path
                key = secrets.token_urlsafe(24)
            else:
                previous = self.files.get(file_id or '')
                if previous is None:
                    raise DocumentError("저장할 파일을 다시 선택해 주세요.", "missing_file")
                path, key = previous.path, file_id
                try:
                    with path.open('rb') as stream:
                        current = stream.read(MAX_FILE_BYTES + 1)
                except OSError:
                    raise DocumentError("기존 파일에 접근할 수 없습니다. 다른 이름으로 저장해 주세요.", "missing_file") from None
                if hashlib.sha256(current).hexdigest() != previous.digest:
                    raise DocumentError("파일이 프로그램 밖에서 변경되었습니다. 변경된 파일을 보존하려면 다른 이름으로 저장해 주세요.", "file_changed")
            atomic_write(path, raw)
            self.files[key] = OpenFile(path, hashlib.sha256(raw).hexdigest())
            return {'fileId': key, 'name': path.name, 'savedAt': json.loads(raw)['savedAt']}
