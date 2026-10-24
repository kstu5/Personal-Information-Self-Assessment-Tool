from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

root=Path(__file__).resolve().parent
source=root/'생활속에_표준적용_사례조사분석서_디자인.docx'
out=root/'생활속에_표준적용_사례조사분석서_디자인_수정.docx'
d=Document(source)

main=d.styles['Heading 1']
main.font.size=Pt(21);main.font.bold=True;main.font.color.rgb=RGBColor(0,0,0)
main.paragraph_format.space_before=Pt(18)
main.paragraph_format.space_after=Pt(13)
main.paragraph_format.left_indent=Cm(0)
main.paragraph_format.keep_with_next=True
sub=d.styles['Heading 2']
sub.font.size=Pt(12.5);sub.font.bold=True;sub.font.color.rgb=RGBColor(0,0,0)
sub.paragraph_format.space_before=Pt(14)
sub.paragraph_format.space_after=Pt(6)
sub.paragraph_format.left_indent=Cm(.35)
sub.paragraph_format.keep_with_next=True
d.styles['Title'].font.size=Pt(28)

# Remove the navigation heading and its two navigation lines only.
remove=False
for p in list(d.paragraphs):
 if p.text=='구성 안내':remove=True
 elif remove and p.style.name=='Heading 1':remove=False
 if remove:p._p.getparent().remove(p._p)

# The first-page fields remain editable paragraphs with underlined blanks.
anchor=next(p for p in d.paragraphs if p.style.name=='Heading 1')
for label in ['이름','학번','학과']:
 p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
 p.paragraph_format.space_before=Pt(0)
 p.paragraph_format.space_after=Pt(5 if label!='학과' else 12)
 p.paragraph_format.keep_with_next=True
 r=p.add_run(label+'   ');r.bold=True;r.font.size=Pt(10.5)
 r=p.add_run('\u00a0'*30);r.underline=True;r.font.size=Pt(10.5)
 anchor._p.addprevious(p._p)

for p in d.paragraphs:
 if p.style.name not in ['Title','Heading 1','Heading 2']:continue
 for r in p.runs:
  r.font.size=None;r.font.bold=None;r.font.color.rgb=RGBColor(0,0,0)
 # Clear direct heading indentation so the hierarchy uses its style.
 p.paragraph_format.left_indent=None

d.save(out)
check=Document(out);before=Document(source)
assert '구성 안내' not in '\n'.join(p.text for p in check.paragraphs)
assert [p.text for p in check.paragraphs if p.style.name=='List Bullet']==[p.text for p in before.paragraphs if p.style.name=='List Bullet']
assert all(any(p.text.startswith(label+'   ') for p in check.paragraphs) for label in ['이름','학번','학과'])
assert sorted(r.target_ref for r in check.part.rels.values() if 'hyperlink' in r.reltype)==sorted(r.target_ref for r in before.part.rels.values() if 'hyperlink' in r.reltype)
print(out)
print('Heading hierarchy, three identity fields, navigation removal, research text and hyperlinks verified.')
