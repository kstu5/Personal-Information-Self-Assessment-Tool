from pathlib import Path
import json
import pytest

from backend.documents import DocumentError, FileStore, MAX_FILE_BYTES, parse_document, serialize_document, suggested_filename


@pytest.mark.parametrize('title,expected', [
    ('모임: 신청? / 안내*', '모임 신청 안내.piipost'),
    ('<>:"/\\|?*', '제목 없음.piipost'), ('CON', '_CON.piipost'),
    ('con.txt', '_con.txt.piipost'), ('LPT²', '_LPT².piipost'),
    ('... ', '제목 없음.piipost'), ('글 제목. ', '글 제목.piipost'),
])
def test_filename(title, expected):
    assert suggested_filename(title) == expected


def test_unicode_filename_has_no_broken_surrogate():
    name = suggested_filename('😀'*200)
    assert len(name.encode('utf-16-le')) <= 260


def test_disk_roundtrip_new_process_registry(tmp_path):
    title, body = '제목: 원문?', '😀 연락처\n한글 e\u0301\r\n<script>글자</script>'
    path = tmp_path/'사용자가 고른 위치.piipost'
    first = FileStore().save(title, body, chosen_path=path)
    assert first['name'] == path.name
    store = FileStore()  # No in-memory state from the writer.
    opened = store.open(path)
    assert opened['document']['title'] == title
    assert opened['document']['body'] == body
    assert set(json.loads(path.read_text('utf-8'))) == {'format','version','title','body','savedAt'}
    store.save('제목 변경', body+'\n수정', file_id=opened['fileId'])
    assert path.name == first['name']
    assert parse_document(path.read_bytes())['title'] == '제목 변경'
    moved = tmp_path/'이동 후 이름.piipost'
    path.rename(moved)
    assert FileStore().open(moved)['document']['body'] == body+'\n수정'


def test_failed_replace_preserves_original(tmp_path, monkeypatch):
    store = FileStore(); path=tmp_path/'초안.piipost'
    opened=store.save('처음','정상',chosen_path=path)
    before=path.read_bytes()
    def denied(*args): raise PermissionError('simulated')
    monkeypatch.setattr('backend.documents.os.replace', denied)
    with pytest.raises(DocumentError, match='저장하지 못했습니다'):
        store.save('변경','실패',file_id=opened['fileId'])
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_external_change_and_missing_file_are_not_overwritten(tmp_path):
    store=FileStore(); path=tmp_path/'초안.piipost'
    opened=store.save('처음','내용',chosen_path=path)
    path.write_text('외부 변경',encoding='utf-8')
    with pytest.raises(DocumentError) as changed: store.save('변경','새 내용',file_id=opened['fileId'])
    assert changed.value.code == 'file_changed'
    assert path.read_text('utf-8') == '외부 변경'
    path.unlink()
    with pytest.raises(DocumentError) as missing: store.save('변경','새 내용',file_id=opened['fileId'])
    assert missing.value.code == 'missing_file'
    assert not path.exists()


@pytest.mark.parametrize('raw', [b'not json', b'[]', b'{}', b'\xff', b'x'*(MAX_FILE_BYTES+1)], ids=['not-json','array','wrong-format','bad-utf8','oversized'])
def test_invalid_files_rejected(raw):
    with pytest.raises(DocumentError): parse_document(raw)


def test_version_and_limits():
    d=json.loads(serialize_document('제목','본문'))
    d['version']=2
    with pytest.raises(DocumentError) as err: parse_document(json.dumps(d).encode())
    assert err.value.code == 'unsupported_version'
    with pytest.raises(DocumentError): serialize_document('제목','가'*30001)
    with pytest.raises(DocumentError): serialize_document('제목','\ud800')
