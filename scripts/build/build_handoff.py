"""Build the handoff PDF and an allowlisted source-and-evidence ZIP."""
from pathlib import Path
from html import escape
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil
import zipfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/handoff'
PDF = ROOT / 'output/pdf/게시전_프로젝트_상세_인수인계_v1.pdf'
ZIP = ROOT / 'output/게시전_프로젝트_인수인계_자료_v1.zip'
SOURCE = ROOT / 'docs/HANDOFF.md'
OUT.mkdir(parents=True, exist_ok=True)
PDF.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(SOURCE, OUT / '01_상세인수인계.md')

pdfmetrics.registerFont(TTFont('Handoff', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('HandoffBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Handoff', normal='Handoff', bold='HandoffBold', italic='Handoff', boldItalic='HandoffBold')
WIDTH = A4[0] - 92
styles = {
    'title': ParagraphStyle('Title', fontName='HandoffBold', fontSize=22, leading=31, spaceAfter=16, wordWrap='CJK'),
    'h1': ParagraphStyle('H1', fontName='HandoffBold', fontSize=16, leading=23, spaceBefore=20, spaceAfter=10, keepWithNext=True, wordWrap='CJK'),
    'h2': ParagraphStyle('H2', fontName='HandoffBold', fontSize=12, leading=18, spaceBefore=12, spaceAfter=6, keepWithNext=True, wordWrap='CJK'),
    'body': ParagraphStyle('Body', fontName='Handoff', fontSize=10.3, leading=16.9, spaceAfter=8, wordWrap='CJK'),
    'bullet': ParagraphStyle('Bullet', fontName='Handoff', fontSize=10.3, leading=16.9, spaceAfter=5, leftIndent=11, firstLineIndent=-8, wordWrap='CJK'),
    'code': ParagraphStyle('Code', fontName='Handoff', fontSize=9.2, leading=14.5, leftIndent=10, spaceAfter=3, wordWrap='CJK'),
    'cell': ParagraphStyle('Cell', fontName='Handoff', fontSize=9.1, leading=14, wordWrap='CJK'),
    'thead': ParagraphStyle('Thead', fontName='HandoffBold', fontSize=9.1, leading=14, wordWrap='CJK'),
    'toc': ParagraphStyle('Toc', fontName='Handoff', fontSize=10.3, leading=18.4, spaceBefore=1, leftIndent=0, firstLineIndent=0),
}

def inline(text):
    text = escape(text)
    text = re.sub(r'`([^`]+)`', lambda m: '<font color="#34465a">'+m.group(1)+'</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Linked references remain readable and selectable in the PDF.
    text = re.sub(r'(https://[^\s<]+)', lambda m: '<link href="'+m.group(1)+'" color="#205f8a">'+m.group(1)+'</link>', text)
    return text

def p(text, kind='body'):
    return Paragraph(inline(text), styles[kind])

class HandoffDoc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == 'H1':
            text = flowable.getPlainText()
            key = 's-' + hashlib.sha1(text.encode()).hexdigest()[:12]
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=0)
            self.notify('TOCEntry', (0, text, self.page, key))

def page_frame(canvas, doc):
    canvas.saveState()
    canvas.setFont('Handoff', 8)
    canvas.setFillColor(colors.HexColor('#56636e'))
    if doc.page > 1:
        canvas.drawString(46, A4[1]-31, '게시 전 개인정보 노출 자가진단 도구  |  상세 인수인계')
    canvas.drawString(46, 25, '2026.10.16  ·  v1.0')
    canvas.drawRightString(A4[0]-46, 25, str(doc.page))
    canvas.restoreState()

def table(lines):
    rows = [[cell.strip() for cell in line.strip().strip('|').split('|')] for line in lines]
    rows = [row for row in rows if not all(re.fullmatch(r'[:\- ]+', cell) for cell in row)]
    count = len(rows[0])
    if count == 8:
        fractions = [.25]+[.75/7]*7
    elif count == 3:
        fractions = [.19,.58,.23]
    else:
        fractions = [.39,.61]
    parsed = [[p(cell, 'thead' if n == 0 else 'cell') for cell in row] for n,row in enumerate(rows)]
    result = Table(parsed, colWidths=[WIDTH*f for f in fractions], repeatRows=1, hAlign='LEFT')
    commands = [
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8edf0')),
        ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#d9d9d9')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),7), ('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]
    for row in range(2,len(rows),2):
        commands.append(('BACKGROUND',(0,row),(-1,row),colors.HexColor('#f7f9fa')))
    if count == 8:
        commands.append(('ALIGN',(1,0),(-1,-1),'CENTER'))
    result.setStyle(TableStyle(commands))
    return result

lines = SOURCE.read_text(encoding='utf-8').splitlines()
story=[]
i=0
first_section=True
while i<len(lines):
    line=lines[i]
    if not line.strip():
        i+=1; continue
    if line.startswith('# '):
        title = inline(line[2:]).replace(' 상세 인수인계', '<br/>상세 인수인계')
        story.append(Paragraph(title, styles['title'])); i+=1; continue
    if line.startswith('## '):
        if first_section:
            story.append(p('문서 안내', 'h2'))
            toc=TableOfContents(); toc.levelStyles=[styles['toc']]
            toc.tableStyle=TableStyle([
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('TOPPADDING',(0,0),(-1,-1),0),
                ('BOTTOMPADDING',(0,0),(-1,-1),0),
                ('LEFTPADDING',(0,0),(-1,-1),0),
                ('RIGHTPADDING',(0,0),(-1,-1),0),
            ])
            story.extend([toc,PageBreak()]); first_section=False
        story.append(p(line[3:], 'h1')); i+=1; continue
    if line.startswith('### '):
        story.append(p(line[4:], 'h2')); i+=1; continue
    if line.startswith('```'):
        code=[]; i+=1
        while i<len(lines) and not lines[i].startswith('```'):
            code.append(lines[i]); i+=1
        story.append(Spacer(1,3))
        story.append(KeepTogether([p(row or ' ', 'code') for row in code]))
        story.append(Spacer(1,7)); i+=1; continue
    if line.startswith('|'):
        batch=[]
        while i<len(lines) and lines[i].startswith('|'):
            batch.append(lines[i]); i+=1
        story.extend([table(batch),Spacer(1,9)]); continue
    if line.startswith('- ') or re.match(r'^\d+\. ',line):
        story.append(p(('• '+line[2:]) if line.startswith('- ') else line, 'bullet')); i+=1; continue
    if line.startswith('> '):
        story.append(p('**'+line[2:]+'**')); i+=1; continue
    group=[line]; i+=1
    while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```','- ','> ')):
        group.append(lines[i]); i+=1
    story.append(p(' '.join(group)))

doc=HandoffDoc(str(PDF), pagesize=A4, leftMargin=46, rightMargin=46, topMargin=49, bottomMargin=45,
              title='게시 전 개인정보 노출 자가진단 도구 상세 인수인계', author='프로젝트 인수인계', pageCompression=1)
doc.addPageTemplates(PageTemplate(id='normal', frames=[Frame(46,45,WIDTH,A4[1]-94, leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)], onPage=page_frame))
doc.multiBuild(story)
reader=PdfReader(PDF)
pdf_text='\n'.join(page.extract_text() or '' for page in reader.pages)
for text in ('인수자가 먼저 알아야 할 사항','학습 모델 연결','다음 담당자의 시작 체크리스트','22개','16개'):
    assert text in pdf_text,text
assert len(reader.pages)>10

files={}
def add(path, archive):
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(path)
    if archive in files: raise ValueError(archive)
    files[archive]=path

for path in sorted(OUT.iterdir()):
    if path.is_file() and path.name not in ('manifest.json','묶음_확인결과.json'):
        add(path,path.name)
add(PDF,'02_상세인수인계.pdf')
for name in ('.gitignore','README.md','package.json','pnpm-lock.yaml','requirements.lock.txt','run.py','index.html','vite.config.ts','tsconfig.json','게시전 실행.vbs'):
    add(ROOT/name,'project/'+name)
extensions={'.md','.txt','.py','.ps1','.ts','.tsx','.css','.json','.cjs','.html','.pdf','.docx'}
for directory in ('backend','src','tests','scripts','docs','research'):
    for path in sorted((ROOT/directory).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix in extensions:
            add(path,'project/'+path.relative_to(ROOT).as_posix())
for path in sorted((ROOT/'output/community-review').iterdir()):
    if path.is_file() and path.suffix in ('.piipost','.md','.txt','.json'):
        add(path,'project/'+path.relative_to(ROOT).as_posix())
for directory in ('output/pdf','output/docx'):
    for path in sorted((ROOT/directory).iterdir()):
        if path.is_file() and path.suffix in ('.pdf','.docx') and path!=PDF:
            add(path,'project/'+path.relative_to(ROOT).as_posix())
add(Path.home()/'Desktop'/'게시전_개인정보_노출_자가진단_도구_프로젝트계획서_v2.docx',
    'reference/게시전_개인정보_노출_자가진단_도구_프로젝트계획서_v2.docx')
design=Path.home()/'.codex'/'visualizations'/'2026'/'10'/'13'/'01a1345c-aeb9-72b1-8ced-e610bbb91962'
for name in ('privacy-review-markers.html','privacy-marker-directions.html','privacy-workspace-design.html','privacy-post-design.html'):
    add(design/name,'reference/design/'+name)
for name in ('start.png','write.png','results.png','save.png','report.json'):
    add(ROOT/'tmp/ui-check'/name,'reference/previous-ui-check/'+name)
for name in ('C01.png','C02.png','C03.png'):
    add(ROOT/'tmp/community-ui'/name,'reference/previous-community-ui/'+name)

manifest={
    'createdAt':datetime.now(timezone.utc).isoformat(),
    'purpose':'Source and documentation handoff; not an executable installer',
    'excluded':['.git','.runtime','.venv','node_modules','dist','runtime.local.json','general tmp','user-created drafts'],
    'files':[{'path':name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for name,path in sorted(files.items())],
}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as archive:
    for name,path in sorted(files.items()): archive.write(path,name)
    archive.write(OUT/'manifest.json','manifest.json')
with zipfile.ZipFile(ZIP) as archive:
    assert archive.testzip() is None
    for item in manifest['files']:
        assert hashlib.sha256(archive.read(item['path'])).hexdigest()==item['sha256']
    assert len(archive.namelist())==len(manifest['files'])+1
verification={'pdfPages':len(reader.pages),'zipEntries':len(files)+1,'zipBytes':ZIP.stat().st_size,'zipIntegrity':'passed',
              'entryHashes':'all matched','zipSha256':hashlib.sha256(ZIP.read_bytes()).hexdigest()}
(OUT/'묶음_확인결과.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(verification,ensure_ascii=False))
