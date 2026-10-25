from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.runtime/file-python'))
from backend.file_formats import Document,read_zip,write_zip


@pytest.mark.parametrize('suffix,separator',[('.csv',','),('.tsv','\t')])
def test_delimited_preview_keeps_sparse_cells_and_blank_rows(tmp_path,suffix,separator):
    path=tmp_path/('input'+suffix)
    path.write_bytes((f'성명{separator}{separator}연락처\r\n"김\n민수"{separator}{separator}010-0000-1234\r\n{separator}{separator}\r\n').encode('utf-8'))
    doc=Document(path,tmp_path).load()
    assert doc.manifest()['tableSize']=={'rows':3,'columns':3}
    name=next(p for p in doc.parts if p['text']=='김\n민수')
    assert (name['row'],name['column'],name['sheet'])==(2,1,'데이터')
    assert name['target']=={'kind':'csv','row':1,'col':0}
    out=tmp_path/('saved'+suffix);doc.export(out,{name['id']:'김**'},[])
    saved=Document(out,tmp_path).load()
    assert saved.manifest()['tableSize']==doc.manifest()['tableSize']
    assert saved.rows[1]==['김**','','010-0000-1234'] and saved.rows[2]==['','','']


def test_text_content_preview_retains_line_gaps_and_edit_targets(tmp_path):
    path=tmp_path/'input.txt';path.write_bytes('제목\n\n\n성명 김민수\n'.encode('utf-8'))
    doc=Document(path,tmp_path).load()
    assert [p['flow']['line'] for p in doc.parts]==[1,4]
    assert [p['target']['index'] for p in doc.parts]==[0,3]
    output=tmp_path/'out.txt';doc.export(output,{doc.parts[-1]['id']:'성명 김**\n'},[])
    assert Document(output,tmp_path).load().parts[-1]['flow']=={'line':4}


def test_hwpx_content_preview_excludes_metadata_without_dropping_it(tmp_path):
    original=next((ROOT/'test/format-document-examples/files').glob('*.hwpx'))
    entries=read_zip(original)
    entries['docProps/core.xml']=b'<core xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Metadata author</dc:creator></core>'
    path=tmp_path/'input.hwpx';write_zip(path,entries)
    doc=Document(path,tmp_path).load()
    body=[p for p in doc.parts if p.get('flow')]
    assert body and all(p['target']['name']=='Contents/section0.xml' for p in body)
    metadata=next(p for p in doc.parts if p['text']=='Metadata author')
    assert 'flow' not in metadata
    assert any('김도윤' in p['text'] for p in body)
