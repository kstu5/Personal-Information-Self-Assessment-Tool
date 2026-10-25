"""Package and check the completed synthetic document samples without re-rendering."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import zipfile
from lxml import etree as E
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'examples/documents'
QA = ROOT / 'validation/qa/shared-documents'
QA.mkdir(parents=True, exist_ok=True)
workbook = OUT / '추첨당첨자_명단예시.xlsx'
with zipfile.ZipFile(workbook) as archive:
    entries = {name: archive.read(name) for name in archive.namelist()}
tree = E.fromstring(entries['xl/workbook.xml'])
sheets = [node for node in tree.iter() if E.QName(node).localname == 'sheet']
assert sheets[1].get('name') == '내부_배송정보'
sheets[1].set('state', 'hidden')
entries['xl/workbook.xml'] = E.tostring(tree, xml_declaration=True, encoding='UTF-8')
with zipfile.ZipFile(workbook, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, raw in entries.items():
        archive.writestr(name, raw)

book = load_workbook(workbook, data_only=False)
assert book.sheetnames == ['공유용_명단', '내부_배송정보']
assert book.worksheets[1].sheet_state == 'hidden'
assert sum(isinstance(book.worksheets[0].cell(row, 1).value, (int, float)) for row in range(5, 15)) == 10
assert sum(isinstance(book.worksheets[1].cell(row, 1).value, (int, float)) for row in range(5, 8)) == 3
for sheet in book:
    for row in sheet:
        assert all(cell.data_type != 'f' for cell in row)
    for row in range(5, 15 if sheet.title == '공유용_명단' else 8):
        assert isinstance(sheet.cell(row, 3).value, str)
book.close()
for path in OUT.glob('*.docx'):
    document = Document(path)
    assert document.paragraphs and document.tables
with zipfile.ZipFile(OUT / '회의록_공유예시.docx') as archive:
    assert '이지은' in archive.read('word/comments.xml').decode('utf-8')
    assert '김민수' in archive.read('docProps/core.xml').decode('utf-8')
for path in OUT.glob('*.pdf'):
    reader = PdfReader(path)
    assert len(reader.pages) == 1
    assert '010-0000-' in reader.pages[0].extract_text()

sys.argv = ['create_shared_documents.py', 'answers']
runpy.run_path(str(ROOT / 'validation/_build/create_shared_documents.py'), run_name='__main__')
for path in OUT.glob('*.inspect.ndjson'):
    path.replace(QA / path.name)
deliverables = sorted(path for path in OUT.iterdir() if path.suffix in {'.docx', '.pdf', '.xlsx', '.md', '.json'})
assert len(deliverables) == 10
bundle = QA / '공유문서_검사예시_모음.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in deliverables:
        archive.write(path, path.name)
with zipfile.ZipFile(bundle) as archive:
    assert archive.testzip() is None
    for path in deliverables:
        assert archive.read(path.name) == path.read_bytes()
report = {
    'office_files': 5,
    'pdf_files': 2,
    'winner_rows': 10,
    'hidden_delivery_rows': 3,
    'hidden_sheet': '내부_배송정보',
    'pdf_pages_each': 1,
    'visual_review': 'Four DOCX pages and both worksheet previews checked',
    'scope': 'Artifact integrity and layout only; model detection was not executed on these samples',
    'files': [{'file': path.name, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in deliverables],
}
(QA / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
