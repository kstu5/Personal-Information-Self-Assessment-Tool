# 문서 개인정보 검토와 수정 결과

2026년 10월 25일 · 기준 커밋 `f1d424bb245cedc5c082ebb94ef91381bd2a2300`에 로컬 수정 적용

HWPX 변경 표시 뒤 글자와 확인된 OOXML 부가 정보의 검사·수정 누락, Word의 서식 조각 변경 후 사본 검증 실패를 수정했다. 이전에 문제를 재현한 5개 문서는 모두 수정 사본이 제공되며, 독립 확인에서 알려진 개인정보 원문이 남지 않았다.

## 수정 전후 비교

| 항목 | 수정 전 | 수정 후 |
|---|---:|---:|
| 시험 문서 | 21 | 21 |
| 지정 확인 지점을 모두 덮는 후보 | 83/89 | 89/89 |
| 읽기 단계에서 누락된 지점 | 6 | 0 |
| 전체 가림 사본 제공 | 16 | 18 |
| 제공된 사본에서 알려진 원문 잔존 | 3 | 0 |
| 저장 실패 | 3 | 1 |
| 지원 제한에 따른 차단 | 2 | 2 |
| 원본 해시 보존 | 21/21 | 21/21 |

89곳은 이 합성 표본에 지정한 확인 지점이다. 89/89는 일반적인 탐지 정확도나 개인정보 전체 제거 보장이 아니다. 후보가 주변 글자까지 과하게 포함하는 경우도 별도로 기록한다.

## 변경한 동작

### HWPX 표시 앞뒤 글자 처리

문자 요소의 본문(text)과 내부 표시 뒤에 이어지는 글자(tail)를 순서대로 수집하고 위치를 기록한다. 가림·직접 수정은 그 위치의 text/tail에 적용하며, 변경 표시 자체와 주변 글자는 보존한다. 이전에 삭제 기록에 남았던 전화번호도 검출·수정된다.

### Word와 PowerPoint 부가 정보

Word 링크 도움말과 문서 변수 값, Word/PowerPoint 도형 이름·대체 텍스트·제목, VML 대체 텍스트·제목, DrawingML 링크 도움말을 검사·수정한다. 지원하는 기본·Strict OOXML 네임스페이스를 구분한다. 내부 도형 ID와 문서 변수 이름처럼 구조를 연결하는 값은 이 추가 목록에서 제외한다. 모든 부가 정보 유형을 지원한다는 뜻은 아니다.

### Word 사본 검증

재검사에서 남은 비어 있지 않은 글자 조각의 번호를 비교하던 방식을 바꿨다. 원래 문단·필드 위치를 다시 찾아 실제 저장된 글자가 요청한 결과와 정확히 같은지 검증한다. 비운 문단은 정상 처리하지만 없어진 문단이나 속성, 값 불일치는 사본 제공을 거부한다. 축소판 관계가 제거되어 순서가 달라진 외부 링크는 관계 ID로 확인한다.

관련 구현: [파일 형식별 추출과 수정](../../backend/file_formats.py), [작업 프로세스 검증](../../backend/file_worker.py).

## 문서별 결과

| 예시 | 지정 지점 중 검출 | 전체 가림 사본 | 독립 확인 |
|---|---:|---|---|
| [text_utf8.txt](../fixtures/text_utf8.txt) | 4/4 | 제공 | 알려진 원문 잔존 없음 |
| [text_cp949.txt](../fixtures/text_cp949.txt) | 4/4 | 제공 | 알려진 원문 잔존 없음 |
| [table_quoted.csv](../fixtures/table_quoted.csv) | 3/3 | 제공 | 알려진 원문 잔존 없음 |
| [table_tabs.tsv](../fixtures/table_tabs.tsv) | 3/3 | 제공 | 알려진 원문 잔존 없음 |
| [text_variants.txt](../fixtures/text_variants.txt) | 6/6 | 제공 | 알려진 원문 잔존 없음 |
| [text_negative.txt](../fixtures/text_negative.txt) | 0/0 | 제공 | 알려진 원문 잔존 없음 |
| [word_structures.docx](../fixtures/word_structures.docx) | 14/14 | 제공 | 알려진 원문 잔존 없음 |
| [word_repeated.docx](../fixtures/word_repeated.docx) | 3/3 | 제공 | 알려진 원문 잔존 없음 |
| [word_linebreak.docx](../fixtures/word_linebreak.docx) | 2/2 | 제공 | 알려진 원문 잔존 없음 |
| [word_link.docx](../fixtures/word_link.docx) | 3/3 | 제공 | 알려진 원문 잔존 없음 |
| [word_attributes.docx](../fixtures/word_attributes.docx) | 3/3 | 제공 | 알려진 원문 잔존 없음 |
| [word_footnotes.docx](../fixtures/word_footnotes.docx) | 2/2 | 제공 | 알려진 원문 잔존 없음 |
| [xlsx_values.xlsx](../fixtures/xlsx_values.xlsx) | 7/7 | 제공 | 알려진 원문 잔존 없음 |
| [xlsx_formulas.xlsx](../fixtures/xlsx_formulas.xlsx) | 5/5 | 제공 | 알려진 원문 잔존 없음 |
| [xlsx_blocked.xlsx](../fixtures/xlsx_blocked.xlsx) | 0/0 | 지원 제한 | 정상 차단 |
| [xlsx_sheet_names.xlsx](../fixtures/xlsx_sheet_names.xlsx) | 9/9 | 실패 | 시트 이름은 중복되지 않는 1~31자여야 하며 []:*?/\ 문자를 사용할 수 없습니다. |
| [pptx_body.pptx](../fixtures/pptx_body.pptx) | 7/7 | 제공 | 알려진 원문 잔존 없음 |
| [pptx_attributes.pptx](../fixtures/pptx_attributes.pptx) | 2/2 | 제공 | 알려진 원문 잔존 없음 |
| [hancom_notes.hwpx](../fixtures/hancom_notes.hwpx) | 8/8 | 제공 | 알려진 원문 잔존 없음 |
| [pdf_text.pdf](../fixtures/pdf_text.pdf) | 4/4 | 제공 | 알려진 원문 잔존 없음 |
| [pdf_annotation.pdf](../fixtures/pdf_annotation.pdf) | 0/2 | 지원 제한 | 정상 차단 |

## 확인한 시험

- Python 시험 54개 통과. 기존 44개와 새 회귀 실행 10개이며, 실제 작업 프로세스의 문서 읽기·수정·사본 검증까지 시험한다.
- 새 회귀 시험은 서식 조각을 가로지르는 전체·부분 가림과 직접 수정·빈 값 치환, HWPX 표시 사이에 나뉜 이름·전화, OOXML 부가 정보와 내부 ID 보존, 축소판 제거 후 외부 링크 검증, 비운 필드와 없어진 필드·틀린 값의 구분을 포함한다.
- 별도 가상 문서 21개는 실제 A 모델과 인증된 로컬 API로 업로드·검사·전체 가림·직접 수정·다운로드했다. 정규식 가짜 탐지기로 바꾸지 않았다.
- 제공된 사본은 앱의 재검사 외에 XML 텍스트·속성·관계 파일과 PDF 글자층·메타데이터를 독립 확인했다. 원본 21개의 해시는 모두 유지됐다.
- 반복 이름 중 한 곳만 부분 가림하고 다른 곳을 유지하는 시험, 이름을 직접 치환하고 선택하지 않은 전화는 유지하는 시험도 통과했다.
- 원본·사본의 시각 검증은 기존 렌더 자료를 재사용하고, 이번에 새로 저장 가능해진 Word 사본 2개를 별도로 렌더링해 확인했다. 한컴에서 HWPX를 직접 여는 시험은 하지 않았다.

## 이번에 남겨 둔 문제

Excel의 두 시트 이름을 같은 전체 가림 문자열로 바꾸면 중복 이름이 되어 저장이 실패한다. 고유한 이름을 직접 지정하는 우회 방법은 동작한다. 이 충돌 처리 자체는 이번 수정에 포함하지 않았다.

현재 본문과 삭제 기록을 연결해서 `김민수이전`처럼 이름 범위를 넓게 잡은 사례 1개도 남아 있다. 후보 전체를 가리면 주변의 “이전”까지 지울 수 있으므로 선택 범위를 검토해야 한다. 변경 기록을 별도 검사 영역으로 분리하는 작업은 후속 과제다.

## 자료와 한계

수정 전 자료는 [이전 보고서](../before-fix/results/REPORT.md)에 보관했다. 공유 자료는 [요약](summary.json), [원인 재현](root-causes.json), [예시 해시](fixture-hashes.json)다. 상세 결과 `audit.json`, 실행 환경 `environment.json`, 수정 사본과 로그는 로컬에만 보관하며 GitHub에는 포함하지 않는다.

모든 이름과 연락처는 합성 예시다. 알려진 원문 잔존 없음은 해당 정답 문자열을 찾지 못했다는 뜻이다. 이미지 OCR의 일반 성능, HWP 수정 저장, 큰 문서의 성능, MS Office·한컴의 모든 버전 호환성, 실제 데스크톱 창과 OS 파일 선택 창 조작은 이번 결론에 포함하지 않는다. 설치는 기존 로컬 패키지를 재사용했으며 새 PC의 깨끗한 설치 시험을 수행한 것은 아니다.
