from pathlib import Path
import collections,csv,hashlib,json,zipfile
HERE=Path(__file__).resolve().parent
def main():
    data=json.loads((HERE/'results/audit.json').read_text('utf-8'));summary=json.loads((HERE/'results/summary.json').read_text('utf-8'))
    manifest=json.loads((HERE/'manifest.json').read_text('utf-8'))
    for c in manifest['cases']:
        if c['file']=='hancom_notes.hwpx':c['template_source']='validation/templates/hwpx_synthetic_base.hwpx'
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((HERE/'fixtures').iterdir()) if p.suffix in {'.txt','.csv','.tsv','.docx','.xlsx','.pptx','.hwpx','.pdf'}}
    (HERE/'results/fixture-hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 문서 개인정보 검토와 수정 점검 결과','',
    '2026년 10월 25일 · 대상 커밋 `f1d424bb245cedc5c082ebb94ef91381bd2a2300`','',
    '일반 텍스트와 기본 문서 내용의 검출·수정은 이번 표본에서 동작했다. 그러나 HWPX 변경 기록과 Word·PowerPoint 부가 정보에서는 원문이 남은 사본을 제공하면서 재검사 0건으로 표시했다. Word의 서식 조각을 가로지르는 수정은 사본 검증에서 실패했다. 따라서 이미지 OCR 개선에 앞서 문서 추출 범위와 사본 검증을 보완할 필요가 있다.','',
    '## 시험 범위와 방법','',
    '- TXT·CSV·TSV·DOCX·XLSX·PPTX·HWPX·PDF의 8개 형식, 가상 예시 21개를 사용했다. 실제 개인의 자료는 사용하지 않았다.',
    '- 실제 atonlee/koelectra-ko-pii-ner과 ko-pii를 실행했다. 가짜 탐지기로 바꾸지 않았다. 인증된 FastAPI의 업로드·상태 조회·수정·다운로드 경로를 사용했다.',
    '- 알려진 개인정보가 읽힌 위치, 같은 유형의 후보가 그 문자열 전체를 덮는지, 수정 사본이 제공되는지, 제공된 파일 내부에 정답 문자열이 남았는지를 각각 확인했다.',
    '- 전체 가림 시험은 시험 코드가 검출 후보를 모두 선택했다. 사용자의 선택 없이 자동으로 가리는 기능을 새로 구현한 것이 아니다.',
    '- 저장 사본은 앱의 재검사와 별도로 ZIP 내부 XML 텍스트·속성·관계 파일, 텍스트 인코딩, PDF 글자층·메타데이터·주석을 확인했다. 검출 목록에 없는 값도 이 독립 검사에 포함했다.',
    '- 추가로 알려진 정답을 직접 수정하는 시험, 반복된 이름 중 한 곳만 부분 가림, 이름을 직접 치환하고 선택하지 않은 전화번호는 유지하는 시험을 수행했다.',
    '- 성공 사례에서 원본과 사본 DOCX·PDF를 렌더링해 확인했다. XLSX·PPTX 원본의 미리보기도 확인했다. 한컴 프로그램에서 HWPX를 여는 시험은 하지 않았다.','',
    '## 집계','',
    '| 항목 | 결과 |','|---|---:|',
    f"| 예시 문서 | {summary['files']}개 |",
    '| 원래 지원 제한 때문에 차단되어야 하는 문서 | 2개 모두 차단 |',
    f"| 저장 가능한 구조를 대상으로 한 시험 | {summary['readyFiles']}개 |",
    f"| 전체 가림 사본 제공 | {summary['exportedFiles']}개 |",
    '| 사본 제공 실패 | 3개 Word 2개와 Excel 1개 |',
    '| 사본은 제공됐지만 정답 문자열 잔존 | 3개 Word PowerPoint HWPX 각 1개 |',
    '| 사본 제공 후 알려진 정답 문자열 잔존 없음 | 13개 |',
    f"| 알려진 개인정보 등장 확인 지점 | {summary['targetCheckpoints']}개 |",
    f"| 후보가 해당 문자열 전체를 덮은 지점 | {summary['fullyDetectedCheckpoints']}개 |",
    f"| 읽기 단계에서 누락된 지점 | {summary['notExtractedCheckpoints']}개 |",
    '| 개인정보 없는 대조 문서 | 후보 0건 |',
    f"| 원본 해시 보존 | {summary['originalsUnchanged']}개 모두 보존 |",
    '| 기존 Python 자동 시험 | 44개 통과 |',
    '| 기존 마스킹 시험 | 5개 통과 |',
    '| TypeScript 검사와 화면 빌드 | 통과 |','',
    '89개는 정답 목록에 미리 지정한 등장 확인 지점이다. 문서의 모든 종류의 개인정보를 망라한 수가 아니며, 83/89를 일반적인 정확도나 재현율로 해석하면 안 된다. 문자열 전체를 덮는 후보는 주변 단어까지 과하게 포함할 수 있다. 실제로 `김민수이전`이라는 후보 1곳을 확인했다. PDF 주석 문서는 안전 차단 검사용이므로 이 89개에서 제외했다.','',
    '## 문서별 결과','',
    '| 예시 | 확인 지점 중 검출 | 전체 가림 사본 | 독립 확인 |','|---|---:|---|---|']
    rows=[]
    for r in data['cases']:
        n=sum(c['count'] for c in r['checkpoints']);hit=sum(c['fullyDetected'] for c in r['checkpoints']);a=r.get('autoFull',{})
        if r['expectedBlock']:status='예정된 지원 제한';audit='차단 확인' if r.get('expectedBlockObserved') else '차단 실패'
        elif not a.get('saved'):status='실패';audit=a.get('error',r.get('error','오류'))
        else:status='제공';audit='원문 잔존' if a.get('remaining') else '알려진 원문 잔존 없음'
        lines.append(f"| [{r['file']}](../fixtures/{r['file']}) | {hit}/{n} | {status} | {audit.replace('|','/')} |")
        rows.append({'file':r['file'],'expected':n,'covered':hit,'copy':status,'independent_audit':audit})
    lines+=['',
    '## 우선 수정할 문제','',
    '### 1 HWPX 변경 기록에서 전화번호가 사본에 남음','',
    '**우선순위 높음.** `hancom_notes.hwpx`는 메모와 작성자 등은 검출하지만 삭제된 변경 기록의 전화번호 한 곳은 놓쳤다. 검출 후보 전체를 가린 뒤에도 `Contents/section0.xml`에 `010-0000-1234`가 남았고 앱의 사본 재검사 결과는 0건이었다. 사용자가 현재 읽힌 텍스트를 직접 수정한 시험에서도 이 값은 남았다.','',
    '원인은 `<hp:t>이전 연락처 <hp:deleteBegin .../>010-0000-1234<hp:deleteEnd .../></hp:t>`처럼 자식 노드 뒤에 있는 XML tail 텍스트다. 추출기는 `e.text`만 읽어 실제 변경 기록의 전화번호를 읽지 않는다. 모델에 전달되지 않으므로 탐지 모델을 교체해도 이 사례는 해결되지 않는다.','',
    '권고: 텍스트 본문과 tail을 모두 위치 정보와 함께 수집하고, 수정도 text/tail별로 정확히 적용하도록 해야 한다. 변경 기록 구간을 별도 검토 대상으로 분리한다. 그 전에는 해당 구조가 있음을 감지해 저장 제한 또는 검사 누락 경고를 표시한다.','',
    '관련 코드: [추출](../../backend/file_formats.py#L148), [수정](../../backend/file_formats.py#L362). 증거: `hancom_notes__auto_full_independent.json`, `root-causes.json`.','',
    '### 2 Word와 PowerPoint 부가 정보가 검사에서 빠짐','',
    '**우선순위 높음.** `word_attributes.docx`의 링크 툴팁 전화번호, 문서 변수 이름, 도형 대체 텍스트 이름 3곳과 `pptx_attributes.pptx`의 도형 설명 전화번호·도형 이름 2곳을 읽지 못했다. 두 문서 모두 수정 사본을 제공했고 재검사는 0건이었지만 독립 확인에서 원문이 남았다.','',
    '구체적인 필드는 `w:tooltip`, `w:docVar/@w:val`, VML `alt`, PowerPoint `cNvPr/@descr`와 `@name`이다. 작성자 등 일부 속성만 허용 목록으로 읽는 현재 방식에서 제외된다.','',
    '권고: 실제 사용자가 입력할 수 있는 부가 정보의 형식별 목록을 만들고 검사·수정을 연결한다. 도형 ID 같은 내부 값 전체를 무차별 검사하는 방식은 피한다. 지원하지 못하는 필드가 있는 문서는 그 범위를 사용자에게 알리고, 메타데이터 제거 또는 별도 검토를 제공한다. 같은 추출기만 다시 돌리는 검증으로는 누락을 발견할 수 없으므로 저장 전후 부가 정보 목록 비교도 필요하다.','',
    '관련 코드: [속성 추출 목록](../../backend/file_formats.py#L161). 증거: `word_attributes__auto_full_independent.json`, `pptx_attributes__auto_full_independent.json`.','',
    '### 3 여러 서식 조각에 걸친 Word 개인정보를 수정하면 저장 실패','',
    '**우선순위 높음.** `word_structures.docx`는 이름이 굵게·기울임 등 여러 run으로 나뉘었고, `word_linebreak.docx`는 이름과 전화번호 중간에 강제 줄바꿈이 있다. 개인정보 검출은 되지만 전체 가림과 직접 수정 모두 사본 검증에서 실패했다. 오류는 “저장한 사본의 수정 위치를 재확인하지 못했습니다. 파일을 제공하지 않습니다.”였다.','',
    '원인 재현에서 형식별 수정기는 실제 파일을 만들었고 다시 읽은 글도 의도한 수정과 일치했다. 그러나 가림 후 일부 텍스트 노드가 비면 재추출 때 그 노드를 제외한다. 원래 위치 키에 포함된 노드 배열 `[9, 13]`이 `[9]`처럼 바뀌어 검증기가 다른 위치로 판단한다. 실제 원본은 보존됐으며 오류 사본을 사용자에게 제공하지 않는 보호는 동작했다.','',
    '권고: 재추출 때 비는 노드가 있어도 유지되는 문단과 텍스트 슬롯의 안정적인 식별자를 사용한다. 검증 자체를 제거하지 말고 그 식별자에 대응하는 최종 글자와 주변 내용을 확인한다. 형식별 수정기 직접 시험뿐 아니라 파일 업로드부터 내보내기까지 연결한 회귀 시험에 이 두 예시를 포함한다.','',
    '관련 코드: [노드 선택](../../backend/file_formats.py#L148), [target 비교](../../backend/file_worker.py#L25). 증거: `root-causes.json`의 `verificationTargetMismatches`.','',
    '### 4 이름이 들어간 Excel 시트를 일괄 가리면 이름 충돌','',
    '**우선순위 보통.** `xlsx_sheet_names.xlsx`에는 `김민수`, `이지은` 시트가 있다. 둘을 전체 가림하면 둘 다 `█████`로 바뀌어 두 번째 시트 이름 변경이 거부된다. 사본은 제공되지 않는다. 전체 직접 수정에서 동일한 `[삭제]`를 쓰는 경우도 같은 이유로 실패했다.','',
    '별도 시험에서 `검토시트1`, `검토시트2`처럼 서로 다른 이름을 직접 지정하자 저장됐다.','',
    '권고: 시트 이름은 저장 전에 일괄 계획하고 중복을 확인한다. 사용자가 전체 가림을 선택하면 `시트1`, `시트2` 같은 고유한 대체 이름을 제안하고 적용 결과를 미리 보여준다. 길이·금지문자뿐 아니라 다른 변경 대상과의 충돌도 확인한다.','',
    '관련 코드: [시트 이름 수정](../../backend/file_formats.py#L389). 증거: `xlsx_sheet_names_auto_full_job.json`, `root-causes.json`의 `uniqueSheetNameWorkaround`.','',
    '### 5 변경 전후 글이 합쳐져 이름 범위를 과하게 잡음','',
    '`word_structures.docx`에서 현재 본문의 `김민수`와 삭제된 기록의 `이전 연락`을 구분자 없이 합쳤다. 그 결과 이름 후보가 `김민수이전`이 됐다. 이 문서는 앞의 저장 실패 문제도 있어 실제 사본이 제공되지는 않았지만, 사용자에게 제시하는 후보 범위 자체에 오류가 있다.','',
    '권고: 현재 본문과 삽입·삭제 기록을 별도 영역으로 추출하고 관계를 보존한다. 줄바꿈과 탭을 처리할 때도 단순히 문자열을 붙이지 않고 원문 위치에 대응하는 매핑을 유지한다.','',
    '## 동작한 부분','',
    '- UTF-8·CP949 텍스트, CSV·TSV의 인용·줄바꿈, 일반 이름·전화·이메일·주소와 이번 띄어쓰기 변형을 검사했다.',
    '- Word 머리말·꼬리말·각주·일반 메모·작성자·일반 삭제 텍스트 자체는 읽혔다. 서식 조각과 저장 검증의 결합에서 문제가 드러났다.',
    '- Excel의 숨김 행·매우 숨김 시트·일반 메모를 읽었고, 지원 수식 2개를 재계산한 뒤 사본에는 값만 남겼다.',
    '- PowerPoint 본문·숨김 슬라이드·발표자 노트의 예시 개인정보를 검사하고 처리했다.',
    '- 검색 가능한 PDF는 글자층의 예시 개인정보를 가린 뒤 원문 글자와 기본 작성자 메타데이터가 사본에 남지 않았다. 실제 PDF 가림 배치도 확인했다.',
    '- 반복 이름 중 첫 번째만 부분 가림하고 두 번째는 유지하는 시험, 직접 치환한 이름만 바꾸고 전화는 유지하는 시험의 확인 항목이 모두 통과했다.',
    '- 미지원 Excel 유효성 검사와 PDF 주석 문서는 내보내기를 차단했다. PDF 주석 내용을 자동으로 검토·수정했다는 뜻은 아니다.','',
    '## 개선 순서','',
    '먼저 HWPX tail과 OOXML 부가 정보의 누락을 막고, Word의 위치 식별자 검증을 고치는 것이 좋다. 다음으로 시트 이름 충돌과 변경 기록의 경계를 다듬는다. 이 예시들을 실제 모델과 전체 파일 처리 경로를 지나는 회귀 시험으로 유지한 뒤 이미지 OCR 개선을 다시 평가하면 문제 원인을 구분하기 쉽다.','',
    '이번 작업에서는 저장소 코드를 최신 버전으로 교체했고 예시와 시험 자료를 추가했다. 위 결함을 고치는 제품 코드 수정은 아직 적용하지 않았다.','',
    '## 해석과 재현상의 한계','',
    '작은 합성 표본의 결과다. “알려진 원문 잔존 없음”은 이 예시의 정답 문자열을 찾지 못했다는 뜻이며 개인정보 전체 제거를 보증하지 않는다. 부분 가림은 원래 일부 글자를 남기는 기능이므로 이 모드의 잔존을 실패로 계산하지 않았다.','',
    '문서 안의 스캔 이미지, OCR의 일반 성능, HWP 수정 저장, 암호화·서명·매크로 문서, 큰 문서의 처리 속도, 각 버전의 MS Office·한컴 프로그램 호환성은 검증 범위 밖이다. 실제 데스크톱 창의 클릭 조작이나 OS 파일 선택 창 시험도 수행하지 않았다.','',
    '기존 패키지를 로컬 `.venv`가 참조하도록 연결해 실행했다. 새 PC에서 최신 설치 스크립트만으로 설치되는지는 별도 검증이 필요하다. 교체 전 로컬 버전은 백업 브랜치와 `validation/archive/` ZIP에 보관했다.','',
    '공유 자료: [요약](summary.json), [최종 예시 해시](fixture-hashes.json). 상세 결과 `audit.json`, 실행 환경 `environment.json`, 원인 재현 `root-causes.json`, 수정 사본과 로그는 로컬에 보관한다. 수정 전후 보고서의 공유 범위는 `validation/README.md`를 참고한다.']
    (HERE/'results/REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    with (HERE/'results/cases.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    # A compact copy of just the inputs and expected checkpoints for convenient manual review.
    with zipfile.ZipFile(HERE/'document-examples.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted((HERE/'fixtures').iterdir()):
            if p.name in hashes:z.write(p,'fixtures/'+p.name)
        z.write(HERE/'manifest.json','manifest.json');z.write(HERE/'README.md','README.md')
    print('Report and example package written')
if __name__=='__main__':
    if (HERE/'before-fix/results/summary.json').exists():
        from write_fix_report import main as current_report
        current_report()
    else:
        main()
