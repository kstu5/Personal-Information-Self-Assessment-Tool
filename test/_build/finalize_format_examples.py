"""Finalize thumbnails/hidden sheet, render PDFs, and package the 12-format set."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile
from lxml import etree as E
from PIL import Image
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'test/format-document-examples'
FILES=OUT/'files'
QA=ROOT/'test/qa/format-documents'
RUNTIME=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies'

def rewrite(path, entries):
    with zipfile.ZipFile(path,'w') as z:
        for n,raw in entries.items():
            z.writestr(n,raw,compress_type=zipfile.ZIP_STORED if n=='mimetype' else zipfile.ZIP_DEFLATED)

def render(path,stem):
    subprocess.run([str(RUNTIME/'native/poppler/Library/bin/pdftoppm.exe'),'-r','120','-png',str(path),str(QA/stem)],check=True,capture_output=True)

def prepare():
    book=FILES/'08_기념품_배송요청명단.xlsx'
    with zipfile.ZipFile(book) as z:entries={n:z.read(n) for n in z.namelist()}
    tree=E.fromstring(entries['xl/workbook.xml'])
    sheets=[e for e in tree.iter() if E.QName(e).localname=='sheet']
    assert [e.get('name') for e in sheets]==['배송요청','운영연락처','이전연락처']
    sheets[2].set('state','hidden')
    entries['xl/workbook.xml']=E.tostring(tree,xml_declaration=True,encoding='utf-8')
    rewrite(book,entries)
    # Render the final PDF and content-only previews for HWP/HWPX.
    # This bundled LibreOffice does not have a usable HWP 5/HWPX import filter.
    sources=[(FILES/'09_협력행사_회의록.pdf','pdf-meeting'),(QA/'hwp-content-preview.pdf','hwp-content'),(QA/'hwpx-content-preview.pdf','hwpx-content')]
    hwpx_pdf=QA/'06_워크숍_참가협조공문.pdf'
    if hwpx_pdf.exists():sources.append((hwpx_pdf,'hwpx-native'))
    for p,stem in sources:render(p,stem)
    thumbsrc=QA/('hwpx-native-1.png' if hwpx_pdf.exists() else 'hwpx-content-1.png')
    thumb=QA/'hwpx-thumbnail.png'
    with Image.open(thumbsrc) as im:
        im.thumbnail((420,594));im.save(thumb)
    hwpx=FILES/'06_워크숍_참가협조공문.hwpx'
    with zipfile.ZipFile(hwpx) as z:entries={n:z.read(n) for n in z.namelist()}
    entries['Preview/PrvImage.png']=thumb.read_bytes();rewrite(hwpx,entries)
    for p in FILES.glob('*.inspect.ndjson'):p.replace(QA/p.name)
    print('Finalized hidden sheet and matching HWPX preview')

def package():
    data=json.loads((OUT/'확인목록.json').read_text('utf-8'))
    cases=data['cases']
    allfiles=sorted(FILES.iterdir())
    assert len(allfiles)==12, [p.name for p in allfiles]
    expected={'.txt','.csv','.tsv','.docx','.pptx','.hwpx','.hwp','.xlsx','.pdf','.png','.jpg','.jpeg'}
    assert {p.suffix for p in allfiles}==expected
    lines=['# 형식별 개인정보 확인 목록','','모든 값은 가상 정보입니다. 이 목록은 검사 입력으로 넣지 마세요.',
           '본문·메모·문서 속성·발표자 노트·숨김 시트는 같은 값이라도 별도 위치로 확인합니다.',
           '개인정보 후보 수와 아래 목록의 항목 수는 OCR 중복과 후보 분할 때문에 다를 수 있습니다.','']
    for row in cases:
        lines.extend([f'## {Path(row["file"]).name}', '',row['scenario'],'',
                      '| 확인할 값 | 종류 | 위치 | 횟수 |','|---|---|---|---|'])
        for t in row['targets']:lines.append(f'| {t["text"]} | {t["type"]} | {t["location"]} | {t["expected_occurrences"]} |')
        lines.extend(['','공개 문맥으로 구분할 값: '+', '.join(row['preserve_context']),''])
    (OUT/'검사_확인목록.md').write_text('\n'.join(lines),encoding='utf-8')
    guide=['# 지원 형식별 공유 문서 예시','','현재 파일 검사의 지원 확장자 12가지를 각각 실제 형식으로 제작했습니다.',
           '모든 인적사항·기관명은 합성 정보이며 이메일은 example.invalid를 사용합니다. 전화·주소는 가상 형식 예시입니다.',
           '기존 이력서와 공유 예시 7개는 유지하고, 이번 모음은 별도 폴더에 추가했습니다.','',
           '| 확장자 | 파일 | 공유 상황 |','|---|---|---|']
    for row in cases:
        name=Path(row['file']).name
        guide.append(f'| {Path(name).suffix} | [{name}]({row["file"]}) | {row["scenario"]} |')
    guide += ['', '## 검사 방법','',
              '1. files 폴더의 문서만 파일 검사에 하나씩 넣습니다. ZIP·확인 목록·안내문은 검사 입력이 아닙니다.',
              '2. 검사_확인목록.md를 보며 값뿐 아니라 해당 위치 전체가 잡혔는지 확인합니다.',
              '3. 일정·작성일·발송일과 생년월일을 구분하고, Python·SQL 같은 기술명이 성명으로 잡히지 않는지 봅니다.',
              '4. 수정 사본을 저장한 뒤 다시 열어 선택한 정보가 사라졌는지, 표·주소·일정이 유지되는지 확인합니다.','',
              '## 놓치기 쉬운 위치','',
              '- DOCX는 검토 메모, 메모 작성자, 문서 속성에도 개인정보가 있습니다.',
              '- PPTX 2번 슬라이드의 발표자 노트에도 이름과 전화가 있습니다.',
              '- XLSX에는 배송요청·운영연락처와 숨김 상태의 이전연락처 시트가 있습니다. 숨김은 정보 삭제가 아닙니다.',
              '- PDF는 글자층이 있는 회의록입니다. PNG·JPG·JPEG는 글자층 없는 서로 다른 스캔 문서입니다.',
              '- 이미지는 선명한 기본 스캔입니다. 흐림·기울기·필기·저해상도 성능까지 대표하지 않습니다.',
              '- HWP는 실제 HWP 5 OLE 바이너리입니다. 현재 앱에서는 본문 추출 검사만 가능하고 수정 저장은 지원하지 않습니다.',
              '- HWPX는 실제 한글 XML 패키지입니다. 한컴 프로그램 화면에서의 호환성 확인은 수행하지 않았습니다.','',
              '## 검증 범위','',
              '제작_검증.json은 파일 형식·해시·앱 읽기 결과를 기록합니다. 이번 제작 확인은 개인정보 탐지 정확도나 수정 성공률의 측정이 아닙니다.',
              '검사_확인목록.md와 확인목록.json은 문서 작성 내용에서 만든 비교 기준입니다. 일반적인 개인정보 전체를 열거한 법적 판정표가 아닙니다.',
              '가상 입력·확인 목록·재현 코드는 Git 공유 후보입니다. ZIP과 미리보기·상세 읽기 결과는 로컬 전용입니다.']
    (OUT/'사용안내.md').write_text('\n'.join(guide)+'\n',encoding='utf-8')
    report={'synthetic':True,'file_count':12,'extensions':sorted(expected),'detection_accuracy_measured':False,
            'native_hancom_ui_verified':False,'hwp_layout_verified':False,'hwpx_layout_verified':False,'files':[]}
    smoke=QA/'adapter-smoke.json'
    rows={r['file']:r for r in json.loads(smoke.read_text('utf-8'))} if smoke.exists() else {}
    for p in allfiles:
        item={'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        if p.name in rows:item.update({k:v for k,v in rows[p.name].items() if k!='file'})
        report['files'].append(item)
    (OUT/'제작_검증.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'지원형식12종_공유문서_예시.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in [*allfiles,OUT/'사용안내.md',OUT/'검사_확인목록.md',OUT/'확인목록.json',OUT/'제작_검증.json']:
            z.write(p,p.relative_to(OUT).as_posix())
    print('Packaged 12 input files plus 4 guides/checklists')

if __name__=='__main__':
    import sys
    if '--package' in sys.argv:package()
    else:prepare()
