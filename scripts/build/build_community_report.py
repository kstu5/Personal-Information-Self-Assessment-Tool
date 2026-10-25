"""Create a reviewed PDF and readable records from the actual evaluation output."""
from pathlib import Path
from html import escape
from collections import Counter
import hashlib
import json
import re
import zipfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'local-only/outputs' / 'community-review'
DATA = json.loads((OUT / 'community-evaluation.json').read_text(encoding='utf-8'))
UI = json.loads((OUT / 'ui-verification.json').read_text(encoding='utf-8'))
CASES = DATA['cases']
TOTAL = DATA['totals']
assert not UI['errors'] and len(UI['cases']) == 3
assert DATA['fixtureSha256'] == hashlib.sha256((ROOT / 'research' / 'community_cases_v1.json').read_bytes()).hexdigest()
PDF = ROOT / 'local-only/outputs' / 'pdf' / '커뮤니티_게시글_3종_개인정보_탐지_점검보고서_v1.pdf'
PDF.parent.mkdir(parents=True, exist_ok=True)
STATUS = {'exact': '완전 탐지', 'partial': '부분 탐지', 'wrong_label': '유형 오분류', 'missed': '미탐'}
RISK = {'CRITICAL':'심각', 'HIGH':'높음', 'MEDIUM':'보통', 'LOW':'낮음', 'INFO':'참고'}
LABEL = {'PERSON':'성명', 'PHONE':'전화번호', 'EMAIL':'이메일', 'ADDRESS':'주소', 'AGE':'나이', 'ACCOUNT':'계좌번호'}
PALETTE = dict(re.findall(r'--(CRITICAL|HIGH|MEDIUM|LOW|INFO):\s*(#[0-9a-fA-F]{6})', (ROOT/'src'/'styles.css').read_text(encoding='utf-8')))
assert len(PALETTE) == 5

NOTES = {
    'C01': [
        '같은 이름도 문장에 따라 달랐다. “김하늘입니다”의 김하늘은 놓쳤고 “김하늘에게”의 김하늘은 찾았다. 이름을 찾는 과정이 주변 문맥에 영향을 받는다는 관찰이며, 이 시험만으로 내부 원인을 확정하지는 않는다.',
        '한글 숫자 연락처 “공일공-공공공공-공공공공”은 표시되지 않았다. 반면 [at]와 [dot]이 들어간 이메일은 원문 구간 그대로 탐지했다. 변형 표현을 모두 놓친다고 일반화할 수 없다.',
        '주소는 도로명과 번지까지만 탐지했고 “302호”는 표시하지 않았다. 주소를 찾았다는 사실과 상세 위치 전체를 검토할 수 있다는 사실을 구분해야 한다.',
    ],
    'C02': [
        '“수령인은 이 가 온”의 띄어 쓴 이름과 “예금주: 이가온입니다”의 이름이 모두 누락됐다. 이름 앞에 수령인이나 예금주라는 단어가 있어도 이 글에서는 탐지를 보장하지 못했다.',
        '동일한 더미 계좌번호의 첫 등장은 “110-000” 부분만 우편번호로 분류됐다. 뒤에서 “계좌번호:”를 붙인 등장은 전체를 계좌번호로 찾았다. 값이 같아도 위치와 문맥이 달라지면 유형과 표시 범위가 달랐다.',
        '주소의 건물명과 101동 1203호는 빠졌다. 책상의 높이·무게를 사람의 신장·체중으로, “택배”와 “포장재”를 성명으로 잡아 검토 목록에 불필요한 항목 4곳이 추가됐다.',
    ],
    'C03': [
        '개인정보를 넣지 않은 음성 대조 글이다. 차 이름 “박하차” 2곳과 일반 명사 “주문번호” 2곳을 성명으로 표시했고, 선반의 높이와 무게를 인적 속성으로 표시했다.',
        '후보 6곳 중 4곳에 “높음”이 붙었다. 이는 엔진이 성명 유형에 부여한 위험도이며, 실제 개인정보라는 확신이나 탐지의 정답 여부를 의미하지 않는다.',
        '이전 짧은 예시에서 오탐이 있었던 “아래”와 “두었던”은 이번 긴 글에서는 표시되지 않았다. 주문번호 값 12345, 가격 15000원, 정리 시점 10월 20일 오후 2시도 표시되지 않았다. 동일 단어의 결과를 모든 문맥으로 확대해서 해석하면 안 된다.',
    ],
}
EXTRA_REASON = {
    '75cm':'책상의 높이', '12kg':'책상의 무게', '택배':'배송 방식을 뜻하는 일반 명사',
    '포장재':'물건을 싸는 재료', '박하차':'차의 종류', '180cm':'선반의 높이',
    '70kg':'선반의 무게', '주문번호':'번호를 소개하는 일반 명사',
}

pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun', normal='Malgun', bold='MalgunBold', italic='Malgun', boldItalic='MalgunBold')
STYLES = {
    'title': ParagraphStyle('title', fontName='MalgunBold', fontSize=23, leading=32, spaceAfter=16, textColor=colors.black, wordWrap='CJK'),
    'h1': ParagraphStyle('h1', fontName='MalgunBold', fontSize=18, leading=25, spaceAfter=13, wordWrap='CJK'),
    'h2': ParagraphStyle('h2', fontName='MalgunBold', fontSize=11.6, leading=17, spaceBefore=12, spaceAfter=7, wordWrap='CJK'),
    'body': ParagraphStyle('body', fontName='Malgun', fontSize=10, leading=17, spaceAfter=8, wordWrap='CJK'),
    'post': ParagraphStyle('post', fontName='Malgun', fontSize=10.1, leading=18, spaceAfter=8, wordWrap='CJK'),
    'small': ParagraphStyle('small', fontName='Malgun', fontSize=8.5, leading=13, spaceAfter=7, textColor=colors.HexColor('#56636e'), wordWrap='CJK'),
    'cell': ParagraphStyle('cell', fontName='Malgun', fontSize=8.5, leading=12.8, wordWrap='CJK'),
    'head': ParagraphStyle('head', fontName='MalgunBold', fontSize=8.5, leading=12.8, wordWrap='CJK'),
}
FLOW = []
WIDTH = A4[0] - 90


def para(text, style='body', raw=False):
    return Paragraph(text if raw else escape(str(text)).replace('\n','<br/>'), STYLES[style])


def p(text, style='body', raw=False):
    FLOW.append(para(text, style, raw))


def table(headers, rows, weights, numeric=()):
    cells = [[para(x,'head') for x in headers]] + [[para(x,'cell') for x in row] for row in rows]
    t = Table(cells, colWidths=[WIDTH*w for w in weights], repeatRows=1, hAlign='LEFT')
    settings = [
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7edf0')),
        ('GRID',(0,0),(-1,-1),.45,colors.HexColor('#d9d9d9')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]
    for n in range(2,len(cells),2):
        settings.append(('BACKGROUND',(0,n),(-1,n),colors.HexColor('#f7f9fa')))
    for n in numeric:
        for row in cells:
            row[n].style = ParagraphStyle('center', parent=row[n].style, alignment=1)
    t.setStyle(TableStyle(settings)); FLOW.extend([t,Spacer(1,9)])


def newpage(title):
    FLOW.append(PageBreak()); p(title,'h1')


def marked(case, source):
    text = case[source]
    raw = text.encode('utf-16-le')
    pointer = 0
    pieces = []
    for item in [c for c in case['actual'] if c['source'] == source]:
        a,b = item['start']*2,item['end']*2
        pieces.append(escape(raw[pointer:a].decode('utf-16-le')))
        pieces.append(f'<font color="{PALETTE[item["risk"]]}"><b>{escape(raw[a:b].decode("utf-16-le"))}</b></font>')
        pointer = b
    pieces.append(escape(raw[pointer:].decode('utf-16-le')))
    return ''.join(pieces).replace('\n','<br/>')


def actual_description(item):
    if not item['actual']: return '표시 없음'
    return '\n'.join(f'{c["text"]} / {c["labelName"]}' for c in item['actual'])


def extra_rows(case):
    return [[f'{n:02}', '제목' if c['source']=='title' else '본문', c['text'], c['labelName']+' / '+RISK[c['risk']], EXTRA_REASON[c['text']]] for n,c in enumerate(case['extras'],1)]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Malgun',8)
    canvas.setFillColor(colors.HexColor('#64717d'))
    canvas.drawString(45,A4[1]-29,'개인정보 자가진단 도구')
    canvas.drawString(45,27,'합성 게시글 시험  |  ko-pii 1.16.0  |  2026년 10월 16일')
    canvas.drawRightString(A4[0]-45,27,str(doc.page))
    canvas.restoreState()


p('커뮤니티 게시글 3종\n개인정보 탐지 점검보고서','title')
p('Windows 1차 구현 검증  |  2026년 10월 16일  |  버전 1.0','small')
p('가상의 커뮤니티 게시글 3개를 만들고 현재 앱의 실제 검사 경로로 실행했다. 미리 지정한 개인정보 16곳 중 9곳을 완전히 찾았고, 주소 2곳은 일부만 찾았다. 계좌번호 1곳은 다른 유형으로 분류했고 4곳은 놓쳤다. 그 밖에 개인정보가 아닌 표현 10곳이 후보로 표시됐다.')
p('표시 위치와 대시보드 연결은 세 글 모두 검사 응답과 일치했다. 이번 결과에서 우선 보완할 부분은 이름의 문맥 처리, 상세 주소의 범위, 번호 유형 구분, 물건의 규격과 사람의 속성을 구별하는 처리다.')
p('글별 결과','h2')
headers=['글','기대\n항목','실제\n후보','완전\n탐지','부분\n탐지','유형\n오분류','미탐','추가\n오탐']
rows=[]
for c in CASES:
    n=c['counts'];rows.append([c['id']+' '+c['genre']]+[n[k] for k in ['expected','candidates','exact','partial','wrong_label','missed','extra']])
rows.append(['합계']+[TOTAL[k] for k in ['expected','candidates','exact','partial','wrong_label','missed','extra']])
table(headers,rows,[.28,.09,.09,.108,.108,.108,.09,.126],numeric=range(1,8))
p('숫자를 읽는 기준','h2')
p('기대 항목 = 완전 탐지 + 부분 탐지 + 유형 오분류 + 미탐이다. 추가 오탐은 기대 항목과 겹치지 않는 별도 후보다. 이번 출력은 9 + 2 + 1 + 10 = 22곳이다. 부분 탐지나 오분류를 완전 탐지에 포함하지 않았다.')
p('C03은 개인정보를 넣지 않은 음성 대조 글이다. 기대 항목 0개는 시험 설계에 따른 값이며, 실제 후보 6개는 모두 이 글의 문맥에서 오탐으로 판정했다.')
p('해석의 범위','h2')
p('취약점을 발견하려고 고른 합성 사례 3개다. 실제 커뮤니티 글의 무작위 표본이나 일반적인 정확도 측정이 아니다. 기대 항목은 이 문서를 작성하면서 문맥에 따라 지정했으며, 독립된 다른 평가자의 검증은 하지 않았다. 위험도는 엔진 반환값 그대로 기록했고 정답 여부와 구분했다.')
p('모든 이름·주소·번호는 시험을 위한 설정이다. 숫자가 실제로 발급됐는지 확인한 자료는 아니므로 연락이나 송금에 사용하지 않는다. 이메일에는 example.com을 사용했다.','small')

for case in CASES:
    cid=case['id'];counts=case['counts']
    newpage(f'{cid} {case["genre"]} 원문과 실제 표시')
    risk_text=' / '.join(f'{RISK[r]} {case["byRisk"].get(r,0)}곳' for r in RISK)
    p(f'기대 항목 {counts["expected"]}곳  |  실제 후보 {counts["candidates"]}곳  |  {risk_text}','small')
    p('아래 색은 실제로 반환된 후보 구간에만 적용했다. 표시되지 않은 정보도 있으며, 색이 있는 일반 단어는 오탐일 수 있다. 앱 화면에서도 원문과 색상·목록·건수가 일치하는지 확인했다.','small')
    p(marked(case,'title'),'h2',True)
    p(marked(case,'body'),'post',True)
    p('실제 후보 전체 목록','h2')
    table(['번호','위치','실제 표시된 구간','반환 유형','위험도'],[
        [f'{n:02}','제목' if c['source']=='title' else '본문',c['text'],c['labelName'],RISK[c['risk']]] for n,c in enumerate(case['actual'],1)
    ],[.07,.09,.48,.23,.13],numeric=(0,1,4))
    p('번호는 원문 등장 순서다. 앱 대시보드는 위험도별로 묶으므로 목록에서 보이는 순서는 다를 수 있다. 원문 위치의 상세 수치는 동봉한 JSON에 기록했다.','small')

    newpage(f'{cid} 기대 항목과 실제 결과 비교')
    if case['expected']:
        p(f'완전 탐지 {counts["exact"]}곳 / 부분 탐지 {counts["partial"]}곳 / 유형 오분류 {counts["wrong_label"]}곳 / 미탐 {counts["missed"]}곳')
        rows=[]
        repeated=Counter(e['text'] for e in case['expected']);seen=Counter()
        for item in case['expected']:
            seen[item['text']]+=1
            name=item['text']+(f'\n{seen[item["text"]]}번째 등장' if repeated[item['text']]>1 else '')
            rows.append([name+'\n기대 유형 '+LABEL[item['label']],actual_description(item),STATUS[item['status']]])
        table(['찾아야 할 정보','실제 표시와 유형','판정'],rows,[.42,.42,.16])
    else:
        p('이 글은 개인정보가 없는 음성 대조 글로 작성했다. 따라서 완전 탐지율을 계산하지 않고, 불필요한 후보가 얼마나 생겼는지 확인한다.')
    if case['extras']:
        p(f'추가 오탐 {len(case["extras"])}곳','h2')
        table(['번호','위치','표시된 표현','반환 유형과 위험도','이 글에서의 의미'],extra_rows(case),[.07,.09,.17,.27,.40],numeric=(0,1))
    else:
        p('기대 항목 밖의 추가 오탐은 없었다.','small')
    p('관찰과 판단','h2')
    for note in NOTES[cid]: p(note)
    if cid=='C03':
        p('후속 설계에 주는 의미','h2')
        p('사용자가 오탐을 발견할 가능성이 높으므로 후보를 확인 완료 또는 개인정보 아님으로 표시하는 기능을 검토할 수 있다. 다만 이번 단어들만 일괄 차단하면 실제 이름이나 다른 문맥을 놓칠 수 있다. 오탐을 감추는 필터보다 문맥별 평가와 표시 근거의 보완을 먼저 검증하는 편이 적절하다.')
        p('목록에 높음 후보가 있어도 사용자가 바로 삭제해야 한다는 뜻은 아니다. 어떤 유형으로 판단했는지와 주변 문장을 함께 읽을 수 있도록 현재의 전체 원문 표시를 유지할 필요가 있다.')

newpage('보완 우선순위와 재현 방법')
p('다음 구현에서 확인할 순서','h2')
table(['우선순위','제안','이번 시험의 근거'],[
    ['1','이름의 문장 끝 표현과 띄어쓰기 검토','김하늘입니다, 이 가 온, 이가온입니다 누락. 택배·포장재·박하차·주문번호 오탐.'],
    ['1','상세 주소 구간 보완','두 주소 모두 번지 뒤의 상세 위치가 빠짐. 범위를 넓힐 때 뒷문장까지 과하게 선택하지 않는지 검증.'],
    ['2','번호 유형과 변형 연락처 보완','한글 숫자 전화번호 누락. 동일 계좌가 한 위치에서는 우편번호 일부로 분류됨.'],
    ['2','사람과 물건의 속성 문맥 구분','책상·선반의 cm와 kg가 사람의 신장·체중으로 표시됨.'],
    ['3','후보 검토 상태와 설명 검토','후기의 높음 4곳은 모두 오탐. 위험도와 탐지 신뢰를 혼동하지 않도록 안내.'],
],[.12,.36,.52],numeric=(0,))
p('정규화로 연락처 표현을 보완할 때에는 정규화된 문자를 원문 위치로 되돌리는 연결이 필요하다. 이번에는 탐지 규칙이나 위험도를 수정하지 않았으며, 위 항목은 결과를 바탕으로 한 후속 제안이다.')
p('시험 방법과 판정 기준','h2')
p('1. 실행 전에 가상 원문과 기대 항목 16개를 고정했다. 같은 값도 위치가 다르면 별도 항목이다. 주소는 건물명·동·호수까지를 기대 구간으로 정했다. 물건의 규격·일정·가격·일반 명사는 개인정보로 기대하지 않았다.')
p('2. 현재 앱의 POST /api/check와 실제 별도 검사 프로세스를 사용했다. 유형과 시작·끝 위치가 모두 같으면 완전 탐지, 같은 유형이지만 범위가 다르면 부분 탐지, 겹치는 후보가 다른 유형이면 유형 오분류, 겹치는 후보가 없으면 미탐으로 분류했다.')
p('3. 세 작업 파일을 실제 React 빌드에서 불러와 검사했다. 파일 선택 창의 선택만 시험 코드로 대신했고 파일 내용과 탐지 응답은 실제 데이터를 사용했다. 제목·본문 보존, 후보 구간, 위험도 색상 클래스, 목록·건수, 목록에서 원문 이동, 재검토 안내가 모두 통과했다. 시험 브라우저의 외부 요청과 JavaScript 오류는 없었다.')
p('직접 다시 확인하기','h2')
p('압축 파일을 푼 뒤 프로그램에서 “저장한 글 불러오기”로 C01, C02, C03의 .piipost 파일을 선택하고 “개인정보 검사”를 누른다. 현재 버전의 예상 후보 수는 차례로 7곳, 9곳, 6곳이다. 엔진을 바꾸거나 문장을 수정하면 결과가 달라질 수 있다.')
p('동봉 자료와 후속 평가','h2')
p('시험 묶음에는 원문 작업 파일 3개, 사람이 읽는 점검기록.md, 기대 항목과 실제 후보·UTF-16 위치를 담은 community-evaluation.json, 화면 검증 기록 ui-verification.json, 실행 전에 정한 community_cases_v1.json을 넣었다. 원문 구간의 끝 위치는 포함하지 않는다. 동일 시험은 scripts/evaluate/evaluate_community_cases.py와 scripts/check/check_community_ui.cjs로 재현할 수 있다.','small')
p('이번 실패를 개선한 뒤에는 다른 이름·문장·거래 글을 포함한 별도 평가 자료로 다시 확인해야 한다. 이 세 글만 맞추는 규칙으로 전체 품질을 판단하지 않는다.','small')

doc=SimpleDocTemplate(str(PDF),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=52,bottomMargin=45,
                      title='커뮤니티 게시글 3종 개인정보 탐지 점검보고서',author='개인정보 자가진단 도구')
doc.build(FLOW,onFirstPage=footer,onLaterPages=footer)

# Plain-text counterpart and reproducible file bundle.
lines=['# 커뮤니티 게시글 3종 개인정보 탐지 점검 기록','',
       '확인일: 2026-10-16. 실제 앱의 ko-pii 1.16.0을 사용했다. 탐지 규칙이나 UI를 변경하지 않았다.',
       '', DATA['scope'],'',DATA['annotationPolicy'],'',
       '## 합계','',f'기대 항목 {TOTAL["expected"]}개, 실제 후보 {TOTAL["candidates"]}개. 완전 탐지 {TOTAL["exact"]}개, 부분 탐지 {TOTAL["partial"]}개, 유형 오분류 {TOTAL["wrong_label"]}개, 미탐 {TOTAL["missed"]}개, 추가 오탐 {TOTAL["extra"]}개.',
       '', '이 수치는 취약점 탐색용 합성 글의 결과다. 일반적인 정확도나 실제 사용 비율을 추정하지 않는다.',
       '', '부분 탐지는 같은 유형이지만 구간이 다름, 유형 오분류는 기대 구간과 겹치지만 유형이 다름, 미탐은 겹치는 후보 없음, 추가 오탐은 기대 구간 밖의 후보로 정의한다.',
       '', '실행 전 기대 항목 파일 SHA-256: '+DATA['fixtureSha256'],'']
def mdtable(headers,rows):
    lines.append('| '+' | '.join(headers)+' |');lines.append('| '+' | '.join('---' for _ in headers)+' |')
    for row in rows:lines.append('| '+' | '.join(str(x).replace('|','\\|').replace('\n','<br>') for x in row)+' |')
    lines.append('')
for c in CASES:
    lines.extend(['## '+c['id']+' '+c['genre'],'','### 입력 원문','','**'+c['title']+'**','',c['body'],'','### 집계','',json.dumps(c['counts'],ensure_ascii=False),'','### 기대 항목별 비교',''])
    if c['expected']:
        mdtable(['기대 구간','유형','기대 위치','실제 표시','판정','판정 근거'],[[e['text'],e['label'],f'{e["source"]} [{e["start"]}, {e["end"]})',actual_description(e),STATUS[e['status']],e['reason']] for e in c['expected']])
    else:lines.extend(['개인정보를 넣지 않은 음성 대조 글이다. 기대 항목이 없어 재현율을 계산하지 않는다.',''])
    lines.extend(['### 실제 후보 전체',''])
    mdtable(['구간','위치 UTF-16','유형','위험도'],[[x['text'],f'{x["source"]} [{x["start"]}, {x["end"]})',x['labelName']+' '+x['label'],RISK[x['risk']]] for x in c['actual']])
    lines.extend(['### 관찰과 판단',''])
    for note in NOTES[c['id']]:lines.extend([note,''])
    lines.extend(['### 개인정보가 아닌 표현의 확인',''])
    mdtable(['표현','문맥상 의미','실제 겹치는 후보'],[[x['text'],x['reason'],', '.join(c['text']+' / '+c['labelName'] for c in x['actual']) or '없음'] for x in c['negativeExamples']])
    lines.extend(['### 추가 오탐',''])
    if c['extras']:mdtable(['번호','위치','표현','반환 유형과 위험도','이 글에서의 의미'],extra_rows(c))
    else:lines.extend(['없음.',''])
lines.extend(['## 화면 확인','', '세 글의 파일 불러오기, 원문 보존, API 결과 일치, 마커·목록·건수 일치, 위험도 색상 클래스, 원문 위치 이동, 재검토 안내가 모두 통과했다. 실제 빌드와 탐지기를 사용했고 OS 파일 선택 창만 시험 경로로 대체했다. 브라우저 외부 요청과 JavaScript 오류는 없었다.',
              '', '## 다음 보완 제안','',
              '1. 이름의 문장 끝 표현과 띄어쓰기, 일반 단어 오탐을 함께 평가한다.',
              '2. 주소의 동·호수를 포함하되 뒷문장을 잘못 포함하지 않는지 확인한다.',
              '3. 한글 숫자 전화번호와 계좌·우편번호 문맥 구분을 보완한다. 정규화 시 원문 위치 복원도 함께 검증한다.',
              '4. 물건의 규격과 사람의 신장·체중을 구별한다.',
              '5. 오탐 표시와 확인 완료 상태를 검토한다. 위험도를 탐지 정답 여부와 구분한다.',
              '', '이번 결과를 근거로 제품 규칙을 수정하지 않았다. 후속 개선은 별도 표본으로 평가하며, 특정 단어의 무조건 제외는 권하지 않는다.',
              '', '## 재현','', '프로그램에서 .piipost 파일을 열어 검사한다. 기대 후보 수는 C01 7곳, C02 9곳, C03 6곳이다. 원문이나 엔진 버전을 바꾸면 달라질 수 있다.',
              '', '개발 환경: python scripts/evaluate/evaluate_community_cases.py. 화면 시험: run.py --headless --ready-file tmp/community-ready.json 실행 후 scripts/check/check_community_ui.cjs 실행.',
              '', '측정 방법은 backend/app.py, backend/detection.py의 현재 경로를 사용한다. 결과 파일은 API 인증 토큰을 포함하지 않는다.'])
(OUT/'점검기록.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(OUT/'사용안내.txt').write_text('커뮤니티 가상 게시글 시험 자료\n\n1. 압축을 풀어 주세요.\n2. 개인정보 자가진단 도구에서 저장한 글 불러오기를 누르세요.\n3. C01, C02, C03의 .piipost 파일 중 하나를 선택하세요.\n4. 개인정보 검사를 누르고 보고서의 결과와 비교하세요.\n\nko-pii 1.16.0에서 후보 수는 7곳, 9곳, 6곳입니다. 탐지 결과는 파일에 저장되지 않고 실행할 때 다시 계산합니다. 모든 글은 시험용이며 실제 연락 또는 송금에 사용하지 마세요.\n\n점검기록.md: 읽을 수 있는 상세 기록\ncommunity-evaluation.json: 기대 항목과 실제 구간\nui-verification.json: 화면 확인 결과\ncommunity_cases_v1.json: 실행 전에 고정한 원문과 기대 항목\n',encoding='utf-8')
archive=ROOT/'local-only/outputs'/'커뮤니티_게시글_3종_시험자료.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(OUT.iterdir()):
        if f.is_file():z.write(f,arcname=f.name)
    z.write(ROOT/'research'/'community_cases_v1.json',arcname='community_cases_v1.json')
reader=PdfReader(PDF)
print(json.dumps({'pdf':str(PDF),'pages':len(reader.pages),'pageCharacterCounts':[len(p.extract_text()) for p in reader.pages],'zip':str(archive)},ensure_ascii=False))
