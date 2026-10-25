"""Create synthetic, realistic examples for all supported file extensions.

Run with the bundled document Python, then build_format_office.mjs,
then finalize_format_examples.py. No real personal data is used.
"""
from pathlib import Path
from copy import deepcopy
import csv
import io
import json
import subprocess
import zipfile
from lxml import etree as E
from docx import Document
from docx.shared import Mm, Pt, RGBColor
from docx.oxml.ns import qn
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'examples/formats'
FILES = OUT / 'files'
QA = ROOT / 'validation/qa/format-documents'
for p in (FILES, QA):
    p.mkdir(parents=True, exist_ok=True)
FAKE = '검사 연습용 가상 문서입니다. 모든 인적사항과 기관명은 합성 정보입니다.'
PEOPLE = [
    {'name': n, 'phone': f'010-0000-{2101+i}', 'email': f'sample{21+i}@example.invalid',
     'address': a}
    for i, (n, a) in enumerate([
        ('김도윤', '서울특별시 마포구 가상로 18 101동 302호'),
        ('이서연', '경기도 수원시 영통구 예시로 26 502호'),
        ('박지후', '부산광역시 해운대구 가상길 32 201호'),
        ('최하은', '대전광역시 서구 예시로 44 703호'),
        ('정유진', '광주광역시 북구 가상로 56 402호'),
        ('한서준', '인천광역시 연수구 예시길 68 305호'),
        ('윤지호', '대구광역시 수성구 가상로 72 601호'),
        ('오수아', '세종특별자치시 예시로 84 202호'),
    ])
]
CASES = []

def target(value, kind, location, count=1):
    return {'text': value, 'type': kind, 'location': location, 'expected_occurrences': count}

def personal(p, fields, location):
    kinds = {'name': '성명', 'phone': '전화번호', 'email': '이메일', 'address': '주소'}
    return [target(p[f], kinds[f], location) for f in fields]

def case(name, scenario, targets, keep, features):
    CASES.append({'file': 'files/' + name, 'scenario': scenario, 'targets': targets,
                  'preserve_context': keep, 'features': features})

def write_delimited(name, header, rows, delimiter):
    stream = io.StringIO(newline='')
    w = csv.writer(stream, delimiter=delimiter, lineterminator='\r\n')
    w.writerow(header)
    w.writerows(rows)
    (FILES / name).write_bytes(stream.getvalue().encode('utf-8-sig'))

def text_files():
    name = '01_교육일정_공유메일.txt'
    a, b = PEOPLE[:2]
    lines = ['제목: 11월 문서 정리 교육 일정 공유', FAKE, '',
             '안녕하세요. 가상배움센터 운영팀입니다.',
             '교육 일정은 2026년 11월 12일 14시부터 16시까지입니다.',
             '교육 내용은 Excel 자료 정리와 Python 기초 활용입니다.',
             '노트북을 지참해 주세요. 접수 마감일은 2026년 11월 6일입니다.', '',
             f'교육 담당자: {a["name"]}', f'휴대전화: {a["phone"]}', f'이메일: {a["email"]}',
             f'장비 담당자: {b["name"]}', f'휴대전화: {b["phone"]}', '',
             '작성일: 2026년 10월 25일']
    (FILES / name).write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')
    case(name, '동료에게 전달하는 교육 일정 메일', personal(a, ['name','phone','email'], '교육 담당자') + personal(b,['name','phone'],'장비 담당자'),
         ['2026년 11월 12일','2026년 11월 6일','2026년 10월 25일','Excel','Python'], ['일정과 연락처의 문맥 구분'])

    name = '02_추첨당첨자_발표명단.csv'
    rows = [[i+1,p['name'],p['phone'],p['email'],'도서상품권' if i<3 else '기념품','2026-11-02','가상정보'] for i,p in enumerate(PEOPLE)]
    write_delimited(name, ['순번','당첨자','연락처','이메일','경품','발송예정일','자료구분'], rows, ',')
    case(name, '경품 발송 담당자에게 전달하는 당첨자 명단',
         [t for i,p in enumerate(PEOPLE) for t in personal(p,['name','phone','email'],f'{i+2}행')],
         ['2026-11-02','도서상품권','기념품'], ['8명 명단','UTF-8 BOM','선행 0이 있는 연락처'])

    name = '03_봉사자_현장배치표.tsv'
    tasks = ['접수','안내','자료 배부','출석 확인','장비 지원','행사 정리']
    rows = [[i+1,p['name'],p['phone'],p['email'],tasks[i],'2026-11-14','09:00 ~ 12:00','가상정보'] for i,p in enumerate(PEOPLE[:6])]
    write_delimited(name,['순번','봉사자','긴급연락처','회신메일','담당업무','활동일','활동시간','자료구분'],rows,'\t')
    case(name,'운영진 단체방에 공유하는 봉사자 배치표',
         [t for i,p in enumerate(PEOPLE[:6]) for t in personal(p,['name','phone','email'],f'{i+2}행')],
         ['2026-11-14','09:00 ~ 12:00'], ['탭 구분','업무와 성명 문맥'])

def word_file():
    # Reuse the established document typography/table helper, without executing its main.
    import create_shared_documents as style
    style.OUT=FILES
    name='04_외부교육_참가추천서.docx'
    a,b,c=PEOPLE[:3]
    d=style.base('외부 교육 참가 추천서')
    style.para(d,'가상배움센터 교육 담당자 귀하')
    style.para(d,'아래 두 명을 문서 정리 실무 교육 참가자로 추천합니다. 확정 일정과 준비물을 회신해 주세요.')
    style.heading(d,'추천 참가자')
    style.table(d,['항목','참가자 1','참가자 2'],[
        ['성명',a['name'],b['name']],['생년월일','1997-04-16','1999-08-21'],
        ['휴대전화',a['phone'],b['phone']],['이메일',a['email'],b['email']],
        ['주소',a['address'],b['address']]], [25,74,75])
    style.heading(d,'추천 사유')
    style.para(d,'두 참가자는 월별 접수 자료를 정리하고 동료에게 처리 방법을 안내합니다. Excel과 SQL을 사용하며 Python 기초 실습에 참여할 예정입니다.')
    style.heading(d,'교육 일정')
    style.para(d,'교육일 2026년 11월 12일 14시\n참가 확정 회신 기한 2026년 11월 6일')
    style.heading(d,'추천 담당자')
    style.para(d,f'성명 {c["name"]}\n전화 {c["phone"]}\n이메일 {c["email"]}')
    p=style.para(d,'2026년 10월 25일  가상문서연구회')
    d.add_comment(p.runs, text=f'추천 담당 {c["name"]}에게 {c["phone"]}로 일정 확인', author=c['name'])
    d.core_properties.author=c['name']; d.core_properties.last_modified_by=c['name']
    style.save(d,name)
    ts=personal(a,['name','phone','email','address'],'참가자 1')+personal(b,['name','phone','email','address'],'참가자 2')
    ts += [target('1997-04-16','생년월일','참가자 1'),target('1999-08-21','생년월일','참가자 2')]
    ts += personal(c,['name','phone','email'],'추천 담당자')
    ts += [target(c['name'],'성명','메모 본문'),target(c['phone'],'전화번호','메모 본문'),target(c['name'],'작성자','메모 작성자'),target(c['name'],'작성자','문서 속성',2)]
    case(name,'교육기관에 보내는 참가자 추천서',ts,
         ['2026년 11월 12일','2026년 11월 6일','2026년 10월 25일','Python','SQL'], ['표','검토 메모','메모 작성자','문서 속성'])

pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
STYLES={
 'title':ParagraphStyle('title',fontName='MalgunBold',fontSize=20,leading=29,spaceAfter=12),
 'body':ParagraphStyle('body',fontName='Malgun',fontSize=10.5,leading=18,spaceAfter=7,wordWrap='CJK'),
 'heading':ParagraphStyle('heading',fontName='MalgunBold',fontSize=12,leading=20,spaceBefore=12,spaceAfter=6),
 'small':ParagraphStyle('small',fontName='Malgun',fontSize=8.5,leading=14,textColor=colors.HexColor('#555555'),spaceAfter=9),
 'cell':ParagraphStyle('cell',fontName='Malgun',fontSize=10,leading=17,wordWrap='CJK'),
}

def para(text, style='body'):
    from xml.sax.saxutils import escape
    return Paragraph(escape(text).replace('\n','<br/>'), STYLES[style])

def pdf_doc(path,title,sections):
    story=[para(title,'title'),para(FAKE,'small')]
    for item in sections:
        if isinstance(item, str): story.append(para(item))
        elif item[0]=='h': story.append(para(item[1],'heading'))
        elif item[0]=='t':
            _,headers,rows,widths=item
            matrix=[[para(str(c),'cell') for c in r] for r in [headers]+rows]
            t=Table(matrix,colWidths=widths,repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8EEF4')),
                ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#D9D9D9')),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
                ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
            story += [t,Spacer(1,8)]
    SimpleDocTemplate(str(path),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=42,bottomMargin=42,
                      title=title,author='가상문서연구회').build(story)

def pdf_and_images():
    from PIL import Image
    from pypdf import PdfReader
    a,b,c,d=PEOPLE[:4]
    name='09_협력행사_회의록.pdf'
    pdf_doc(FILES/name,'협력 행사 운영 회의록',[
        '회의 일시 2026년 10월 25일 10시부터 11시까지',
        '장소 서울특별시 마포구 가상로 18 3층',
        f'참석자 {a["name"]}, {b["name"]}, {c["name"]}, {d["name"]}',
        ('h','결정 사항'),'접수 담당자는 행사 전날까지 참가 확정 여부를 확인합니다. 장소 변경 시 신청자에게 안내 메일을 발송합니다.',
        ('t',['담당 업무','담당자','완료 기한'],[
            ['안내문 발송',a['name'],'2026-10-30'],['장비 점검',b['name'],'2026-11-02'],['배치표 확정',c['name'],'2026-11-04']],[210,100,180]),
        ('h','후속 연락'),f'운영 담당자 {d["name"]}\n전화 {d["phone"]}\n이메일 {d["email"]}',
        '다음 회의 2026년 11월 5일 10시'])
    ts=[target(p['name'],'성명','참석자') for p in PEOPLE[:4]]
    ts += [target(p['name'],'성명','업무 배정표') for p in PEOPLE[:3]] + personal(d,['name','phone','email'],'후속 연락')
    ts += [target('서울특별시 마포구 가상로 18 3층','주소','회의 장소')]
    case(name,'협력기관에 배포하는 행사 회의록',ts,['2026년 10월 25일','2026-10-30','2026-11-02','2026-11-04','2026년 11월 5일'],['글자층 PDF','표와 본문에 반복되는 성명'])

    scans=[
      ('10_독서캠프_참가신청서.png','독서 캠프 참가 신청서',[
          ('h','신청자 정보'),f'성명 {a["name"]}', '생년월일 2012-05-18',f'주소 {a["address"]}',
          ('h','보호자 연락처'),f'보호자 성명 {b["name"]}',f'보호자 전화 {b["phone"]}',f'회신 이메일 {b["email"]}',
          ('h','신청 내용'),'참가 회차 2026년 11월 21일 오전반','신청일 2026년 10월 25일',
          '신청 내용이 바뀌면 접수 담당자에게 알려 주세요.'],
          personal(a,['name','address'],'신청자')+[target('2012-05-18','생년월일','신청자')]+personal(b,['name','phone','email'],'보호자'),
          ['2026년 11월 21일','2026년 10월 25일']),
      ('11_기념품_수령확인서.jpg','기념품 수령 확인서',[
          '배송 예정일 2026년 11월 2일',('h','수령 내역'),
          ('t',['항목','내용'],[['물품','독서 모임 기념품 1세트'],['수령인',c['name']],['연락처',c['phone']],['배송 주소',c['address']]],[105,385]),
          ('h','전달 확인'),f'전달 담당자 {d["name"]}',f'전달 담당 전화 {d["phone"]}',
          '수령 확인일 2026년 11월 3일','외부 배송 담당자에게 회신할 확인용 사본입니다.'],
          personal(c,['name','phone','address'],'수령 내역')+personal(d,['name','phone'],'전달 확인'),
          ['2026년 11월 2일','2026년 11월 3일']),
      ('12_현장운영_연락명단.jpeg','현장 운영 연락 명단',[
          '행사일 2026년 11월 14일 09시부터 12시까지',
          '운영 담당자끼리 연락할 때 사용합니다. 역할 변경 시 최신 명단을 다시 전달해 주세요.',
          ('t',['역할','성명','휴대전화'],[[role,p['name'],p['phone']] for role,p in zip(['총괄','접수','안내','출석','장비','정리'],PEOPLE[:6])],[130,130,230]),
          '명단 작성일 2026년 10월 25일'],
          [t for p in PEOPLE[:6] for t in personal(p,['name','phone'],'연락 명단')],
          ['2026년 11월 14일','2026년 10월 25일'])
    ]
    for name,title,sections,targets,keep in scans:
        source=QA/(Path(name).stem+'.pdf')
        pdf_doc(source,title,sections)
        assert len(PdfReader(source).pages)==1
        poppler=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe'
        png=QA/(Path(name).stem+'-source')
        subprocess.run([str(poppler),'-r','144','-png','-singlefile',str(source),str(png)],check=True,capture_output=True)
        with Image.open(png.with_suffix('.png')) as rendered:
            img=rendered.convert('RGB')
            if name.endswith('.png'): img.save(FILES/name,dpi=(144,144))
            else: img.save(FILES/name,quality=88,subsampling=0,dpi=(144,144))
        case(name,'메신저로 전달하는 '+title,targets,keep,['이미지만 존재','OCR 검사','선명한 기본 스캔'])

def hangul_files():
    a,b,c,d=PEOPLE[:4]
    hwplines=['시민 문서 교육 참가 안내',FAKE,'',
        '수신 가상마을모임 교육 담당자','제목 시민 문서 교육 참가 안내','',
        '문서 정리 교육을 다음과 같이 진행하니 참가자에게 안내해 주세요.',
        '교육일 2026년 11월 12일 14시부터 16시까지',
        '장소 대전광역시 서구 가상로 30 2층',
        '내용 Excel 자료 정리와 Python 기초 실습','준비물 개인 노트북','',
        '참가 확정 명단',f'성명 {a["name"]}  연락처 {a["phone"]}',
        f'성명 {b["name"]}  연락처 {b["phone"]}','',
        f'담당자 {c["name"]}',f'전화 {c["phone"]}',f'회신 이메일 {c["email"]}',
        '회신 기한 2026년 11월 6일','작성일 2026년 10월 25일','가상배움센터']
    (QA/'hwp-lines.txt').write_text('\n'.join(hwplines),encoding='utf-8')
    case('07_시민교육_참가안내.hwp','단체에 전달하는 구형 한글 교육 안내 공문',
         personal(a,['name','phone'],'참가 명단')+personal(b,['name','phone'],'참가 명단')+personal(c,['name','phone','email'],'담당자')+
         [target('대전광역시 서구 가상로 30 2층','주소','교육 장소')],
         ['2026년 11월 12일','2026년 11월 6일','2026년 10월 25일','Python'],
         ['HWP 5 OLE 바이너리','현재 앱에서는 읽기 전용'])

    lines=['주민 워크숍 참가 협조 요청',FAKE,'',
           '수신 가상동네모임 운영 담당자','발신 가상문화연구회','',
           '워크숍 참가 확정 명단을 보내드립니다. 안내 사항을 참가자에게 전달해 주세요.',
           '행사일 2026년 11월 14일 09시부터 12시까지',
           '장소 서울특별시 마포구 예시로 20 3층','',
           '참가 확정 명단',*[f'성명 {p["name"]}  연락처 {p["phone"]}' for p in PEOPLE[:4]],'',
           '사전 준비 자료를 행사 전날까지 이메일로 보내드립니다.',
           f'회신 담당자 {d["name"]}',f'전화 {d["phone"]}',f'이메일 {d["email"]}',
           '회신 기한 2026년 11월 6일','시행일 2026년 10월 25일']
    (QA/'hwpx-lines.txt').write_text('\n'.join(lines),encoding='utf-8')
    src=ROOT/'validation/templates/hwpx_synthetic_base.hwpx'
    with zipfile.ZipFile(src) as z: entries={n:z.read(n) for n in z.namelist()}
    hp='http://www.hancom.co.kr/hwpml/2011/paragraph'
    hh='http://www.hancom.co.kr/hwpml/2011/head'
    sec=E.fromstring(entries['Contents/section0.xml'])
    first=deepcopy(sec[0])
    for child in list(first):
        if E.QName(child).localname=='linesegarray': first.remove(child)
        elif E.QName(child).localname=='run':
            for x in list(child):
                if E.QName(x).localname=='t': child.remove(x)
            if not len(child): first.remove(child)
    sec.clear(keep_tail=True);sec.append(first)
    for i,line in enumerate(lines):
        p=E.SubElement(sec,f'{{{hp}}}p',id=str(i+1),paraPrIDRef='0',styleIDRef='0',pageBreak='0',columnBreak='0',merged='0')
        r=E.SubElement(p,f'{{{hp}}}run',charPrIDRef='1' if i==0 else '0')
        E.SubElement(r,f'{{{hp}}}t').text=line
        segs=E.SubElement(p,f'{{{hp}}}linesegarray')
        E.SubElement(segs,f'{{{hp}}}lineseg',textpos='0',vertpos=str(i*1850),vertsize='1100' if i else '1800',
                     textheight='1100' if i else '1800',baseline='935' if i else '1530',spacing='650',horzpos='0',horzsize='48190',flags='393216')
    # Rebuild the header's user-visible fonts and character styles.
    head=E.fromstring(entries['Contents/header.xml'])
    for el in head.iter():
        for key,val in list(el.attrib.items()):
            if '\ufffd' in val: el.set(key,'기본')
        if el.text and '\ufffd' in el.text: el.text=''
        if E.QName(el).localname=='font': el.set('face','맑은 고딕')
    charprops=head.find(f'.//{{{hh}}}charProperties')
    body=deepcopy(charprops[0]);body.set('id','0');body.set('height','1100')
    title=deepcopy(body);title.set('id','1');title.set('height','1800')
    for x in list(charprops):charprops.remove(x)
    charprops.extend([body,title]);charprops.set('itemCnt','2')
    for n,root in [('Contents/section0.xml',sec),('Contents/header.xml',head)]:
        entries[n]=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    meta=E.fromstring(entries['Contents/content.hpf'])
    for el in meta.iter():
        if E.QName(el).localname=='title':el.text=lines[0]
        if E.QName(el).localname=='meta':
            el.text='가상문화연구회' if el.get('name','').lower() in {'creator','author'} else ''
    entries['Contents/content.hpf']=E.tostring(meta,xml_declaration=True,encoding='UTF-8',standalone=True)
    entries['Preview/PrvText.txt']='\r\n'.join(lines).encode('utf-8')
    # Thumbnail is replaced in finalization from the same content; never keep the old preview.
    entries['Preview/PrvImage.png']=b''
    with zipfile.ZipFile(FILES/'06_워크숍_참가협조공문.hwpx','w') as z:
        for n,raw in entries.items():z.writestr(n,raw,compress_type=zipfile.ZIP_STORED if n=='mimetype' else zipfile.ZIP_DEFLATED)
    case('06_워크숍_참가협조공문.hwpx','지역 단체에 전달하는 워크숍 협조 공문',
         [t for p in PEOPLE[:4] for t in personal(p,['name','phone'],'참가 명단')]+personal(d,['name','phone','email'],'회신 담당자')+
         [target('서울특별시 마포구 예시로 20 3층','주소','행사 장소')],
         ['2026년 11월 14일','2026년 11월 6일','2026년 10월 25일'],['한글 XML 패키지','다중 문단','일치하는 미리보기'])
    for kind,ls in [('hwp',hwplines),('hwpx',lines)]:
        pdf_doc(QA/f'{kind}-content-preview.pdf',ls[0],ls[2:])

def office_data():
    a,b,c,d=PEOPLE[:4]
    case('05_행사운영_사전브리핑.pptx','행사 운영진에게 전달하는 3장 발표자료',
         personal(a,['name','phone','email'],'2번 슬라이드')+personal(b,['name','phone'],'2번 슬라이드')+
         personal(c,['name','phone','email'],'3번 슬라이드')+personal(d,['name','phone'],'2번 슬라이드 발표자 노트'),
         ['2026년 11월 14일','2026년 10월 25일','09:00','10:00','12:00'],['3장 슬라이드','편집 가능한 글자','발표자 노트'])
    case('08_기념품_배송요청명단.xlsx','외부 발송 담당자에게 전달하는 배송 요청 명단',
         [t for i,p in enumerate(PEOPLE) for t in personal(p,['name','phone','address'],f'배송요청 {i+6}행')]+
         personal(c,['name','phone','email'],'운영연락처 5행')+personal(d,['name','phone'],'이전연락처 5행 숨김 시트'),
         ['2026-11-02','도서 기념품'],['8건 배송 요청','숫자로 저장한 발송일','운영 연락처','숨김 이전연락처 시트'])
    (QA/'office-data.json').write_text(json.dumps({'people':PEOPLE,'fake':FAKE},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    text_files();word_file();pdf_and_images();hangul_files();office_data()
    (OUT/'확인목록.json').write_text(json.dumps({'synthetic':True,'schema_version':1,'cases':sorted(CASES,key=lambda x:x['file'])},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Base files and 12-format answer key created')
