from copy import deepcopy
from pathlib import Path
import re
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'생활속에_표준적용_사례조사분석서.docx'
OUT=ROOT/'생활속에_표준적용_사례조사분석서_디자인.docx'
d=Document(SOURCE)
INK='202938'; NAVY='233E59'; LIGHT='F1F5F8'; GRAY='66717C'

def font(style, size, bold=False, color='000000'):
 st=d.styles[style];st.font.name='맑은 고딕';st.font.size=Pt(size)
 st.font.bold=bold;st.font.color.rgb=RGBColor.from_string(color)
 rf=st.element.get_or_add_rPr().get_or_add_rFonts()
 for k in ['ascii','hAnsi','eastAsia']:rf.set(qn('w:'+k),'맑은 고딕')
 for e in st.element.get_or_add_rPr().findall(qn('w:color')):
  for key in ['themeColor','themeShade','themeTint']:
   e.attrib.pop(qn('w:'+key),None)
 return st

normal=font('Normal',11)
normal.paragraph_format.line_spacing=1.22
normal.paragraph_format.space_after=Pt(7)
normal.paragraph_format.widow_control=True
for name,size in [('Title',26),('Heading 1',18),('Heading 2',12),('Heading 3',11)]:
 st=font(name,size,True)
 st.paragraph_format.space_before=Pt(13 if name!='Title' else 0)
 st.paragraph_format.space_after=Pt(8)
 st.paragraph_format.keep_with_next=True
st=font('Subtitle',12)
st.paragraph_format.space_after=Pt(18)
st=font('List Bullet',11)
st.paragraph_format.line_spacing=1.22
st.paragraph_format.space_after=Pt(7)
st.paragraph_format.left_indent=Cm(.46)
st.paragraph_format.first_line_indent=Cm(-.3)
st.paragraph_format.keep_together=True

s=d.sections[0]
s.top_margin=Cm(2);s.bottom_margin=Cm(1.9)
s.left_margin=Cm(2.05);s.right_margin=Cm(2.05)
s.header_distance=Cm(.8);s.footer_distance=Cm(.8)
s.different_first_page_header_footer=True

# Set a small black running title and a restrained page footer.
hp=s.header.paragraphs[0]
hp.text='생활 속 표준 적용 사례 조사분석서'
hp.paragraph_format.space_after=Pt(0)
for r in hp.runs:r.font.size=Pt(8);r.font.color.rgb=RGBColor(0,0,0)
for footer in [s.footer,s.first_page_footer]:
 p=footer.paragraphs[0];p.clear();p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
 r=p.add_run('STANDARDIZATION REPORT     ');r.font.size=Pt(8);r.font.color.rgb=RGBColor.from_string(GRAY)
 fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE')
 r=OxmlElement('w:r');t=OxmlElement('w:t');t.text='1';r.append(t);fld.append(r);p._p.append(fld)

# Define one consistent bullet marker rather than relying on app defaults.
numbering=d.part.numbering_part.element
existing=[int(e.get(qn('w:abstractNumId'))) for e in numbering.findall(qn('w:abstractNum'))]
aid=max(existing+[0])+1
abstract=OxmlElement('w:abstractNum');abstract.set(qn('w:abstractNumId'),str(aid))
lvl=OxmlElement('w:lvl');lvl.set(qn('w:ilvl'),'0')
for tag,val in [('start','1'),('numFmt','bullet'),('lvlText','•'),('lvlJc','left')]:
 el=OxmlElement('w:'+tag);el.set(qn('w:val'),val);lvl.append(el)
ppr=OxmlElement('w:pPr');ind=OxmlElement('w:ind');ind.set(qn('w:left'),'260');ind.set(qn('w:hanging'),'170');ppr.append(ind);lvl.append(ppr)
rpr=OxmlElement('w:rPr');rf=OxmlElement('w:rFonts');rf.set(qn('w:ascii'),'맑은 고딕');rf.set(qn('w:hAnsi'),'맑은 고딕');rpr.append(rf);lvl.append(rpr)
abstract.append(lvl);numbering.append(abstract)
nids=[int(e.get(qn('w:numId'))) for e in numbering.findall(qn('w:num'))]
nid=max(nids+[0])+1
num=OxmlElement('w:num');num.set(qn('w:numId'),str(nid));el=OxmlElement('w:abstractNumId');el.set(qn('w:val'),str(aid));num.append(el);numbering.append(num)

for p in d.paragraphs:
 if p.style.name=='Title':
  p.text='생활 속 표준 적용\n사례 조사분석서'
  p.paragraph_format.space_before=Pt(13);p.paragraph_format.space_after=Pt(10)
 if p.style.name=='Heading 1':
  parts=p.text.split(' ',1);p.text=parts[0].zfill(2)+'  '+parts[1]
  p.paragraph_format.keep_with_next=True
  if p.text.startswith(('02','03','04','05','07')):p.paragraph_format.page_break_before=True
 if p.style.name=='Heading 2':
  m=re.match(r'(\d) (\d) (.*)',p.text)
  if m:p.text=f'{m[1]} {m[2]}   {m[3]}'
 if p.style.name=='List Bullet':
  np=p._p.get_or_add_pPr().get_or_add_numPr();np.get_or_add_ilvl().val=0;np.get_or_add_numId().val=nid
  for r in p.runs:r.font.size=None
  if p.runs and p.runs[0].bold:
   p.runs[0].font.color.rgb=RGBColor.from_string(INK)
 if p.style.name.startswith(('Heading','Title','Subtitle')):
  for r in p.runs:r.font.color.rgb=RGBColor(0,0,0)
  borders=p._p.get_or_add_pPr().find(qn('w:pBdr'))
  if borders is not None:borders.getparent().remove(borders)
 # Remove former manual page-break paragraphs, using paragraph-level breaks.
 if p._p.xpath('.//w:br[@w:type="page"]'):
  p._p.getparent().remove(p._p)

# Insert a compact comparison matrix after the opening overview.
anchor=next(p for p in d.paragraphs if p.text.startswith('02  '))
p=d.add_paragraph('조사 대상 한눈에 보기','Heading 2');anchor._p.addprevious(p._p)
table=d.add_table(rows=1,cols=4);table.alignment=WD_TABLE_ALIGNMENT.CENTER;table.autofit=False
widths=[2.0,3.25,5.25,6.4]
for col,width in zip(table._tbl.tblGrid.gridCol_lst,widths):col.set(qn('w:w'),str(round(width/2.54*1440)))
tw=table._tbl.tblPr.find(qn('w:tblW'));tw.set(qn('w:type'),'dxa');tw.set(qn('w:w'),str(round(sum(widths)/2.54*1440)))
rows=[
 ['대상','핵심 관점','대표 표준 및 규격','생활 속 의미'],
 ['냉장고','안전과 에너지','IEC 60335-2-24\nIEC 62552','안전 위험 관리\n소비에너지와 성능 비교'],
 ['스피커','음향과 호환성','IEC 60268-5 및 21\nBluetooth A2DP','음향 특성 측정\n다른 제조사 기기 간 재생'],
 ['전자 출결','식별과 기록 신뢰성','ISO/IEC 14443\nBLE  ·  ISO/IEC 27001','카드 및 무선 통신\n출결 기록의 안전한 관리'],
]
for ri,values in enumerate(rows):
 cells=table.rows[0].cells if ri==0 else table.add_row().cells
 for ci,(cell,value) in enumerate(zip(cells,values)):
  cell.width=Cm(widths[ci]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
  tcpr=cell._tc.get_or_add_tcPr()
  shade=OxmlElement('w:shd');shade.set(qn('w:fill'),NAVY if ri==0 else ('FFFFFF' if ri%2 else LIGHT));tcpr.append(shade)
  margins=OxmlElement('w:tcMar')
  for tag in ['top','bottom','left','right']:
   e=OxmlElement('w:'+tag);e.set(qn('w:w'),'110');e.set(qn('w:type'),'dxa');margins.append(e)
  tcpr.append(margins)
  p=cell.paragraphs[0];p.text=value;p.paragraph_format.line_spacing=1.15
  p.paragraph_format.space_before=Pt(2);p.paragraph_format.space_after=Pt(2)
  if ci==0 or ri==0:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  for r in p.runs:
   r.font.size=Pt(9.5);r.bold=(ri==0 or ci==0);r.font.color.rgb=RGBColor.from_string('FFFFFF' if ri==0 else '202938')
 for row in [table.rows[ri]]:
  trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
header=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(header)
borders=OxmlElement('w:tblBorders')
for tag in ['top','left','bottom','right','insideH','insideV']:
 e=OxmlElement('w:'+tag);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
table._tbl.tblPr.append(borders)
anchor._p.addprevious(table._tbl)
p=d.add_paragraph('구성 안내','Heading 2');anchor._p.addprevious(p._p)
for t in ['02 냉장고     03 스피커     04 전자 출결 서비스','05 비교 분석과 시사점     06 결론     07 참고문헌']:
 p=d.add_paragraph(t);p.paragraph_format.space_after=Pt(6)
 for r in p.runs:r.font.size=Pt(10)
 anchor._p.addprevious(p._p)

# References retain all existing live hyperlinks, with slightly larger type.
in_refs=False
for p in d.paragraphs:
 if p.text.startswith('07  '):in_refs=True
 if not in_refs:continue
 if p.style.name=='Heading 1':continue
 p.paragraph_format.line_spacing=1.15
 p.paragraph_format.space_before=Pt(5 if p.text.startswith('[') else 0)
 p.paragraph_format.space_after=Pt(3)
 for r in p._p.iter(qn('w:r')):
  pr=r.find(qn('w:rPr'))
  if pr is None:pr=OxmlElement('w:rPr');r.insert(0,pr)
  for old in pr.findall(qn('w:sz')):pr.remove(old)
  e=OxmlElement('w:sz');e.set(qn('w:val'),'19');pr.append(e)

d.core_properties.title='생활 속 표준 적용 사례 조사분석서'
d.core_properties.comments=''
d.save(OUT)
print(OUT)

# Confirm that all research paragraphs and linked sources survived styling.
before=Document(SOURCE);after=Document(OUT)
old=[p.text for p in before.paragraphs if p.style.name=='List Bullet']
new=[p.text for p in after.paragraphs if p.style.name=='List Bullet']
assert old==new, 'A research paragraph changed during formatting'
assert sorted(r.target_ref for r in before.part.rels.values() if 'hyperlink' in r.reltype)==sorted(r.target_ref for r in after.part.rels.values() if 'hyperlink' in r.reltype)
print(f'Preserved {len(old)} research bullets and all source links')
