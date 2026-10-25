# 문서 개인정보 검토와 수정 시험

## GitHub 공유 대상과 로컬 보관 대상

| 구분 | 경로와 내용 |
|---|---|
| 공유 대상 | 시험용 `.py`, `_build/`의 `.py`·`.mjs` 제작 스크립트, `fixtures/`, `templates/`, `manifest.json` |
| 공유 대상 | `shared-document-examples/`의 가상 문서·정답 목록·사용 안내. 묶음 ZIP은 로컬 보관 |
| 공유 대상 | `format-document-examples/`의 지원 형식 12종 가상 문서·확인 목록·안내·제작 검증 요약과 `_build/`의 HWP 제작용 `.java` |
| 공유 대상 | `results/`의 `REPORT.md`, `summary.json`, `cases.csv`, `fixture-hashes.json`, `root-causes.json`, `artifact-integrity.json` |
| 공유 대상 | `before-fix/results/`의 보고서·요약·시험별 표·입력 해시, `additional-review/REPORT.md` |
| 공유 대상 | `resume-review/REPORT.md`·`summary.json`과 이력서 재점검 도구 `check_resume_detection.py` |
| 공유 대상 | `context-review/REPORT.md`·`summary.json`과 문맥 재점검·보고서 제작 도구 |
| 공유 대상 | 문서 화면 조사 도구 `benchmark_document_preview.py`·`build_preview_probe.py`와 `docs/verification/document-preview-feasibility-2026-10-25.md` |
| 공유 대상 | 실제 페이지·수정 사본 시험 `check_visual_review.py`, `tests/test_document_preview.py`와 `docs/verification/file-visual-review-2026-10-25.md` |
| 로컬 보관 | `reviewed/`와 `before-fix/reviewed/`의 수정 사본, 상세 API 응답·조사 JSON·환경 정보·실행 로그 |
| 로컬 보관 | `additional-review/`의 보고서 외 재현 산출물, `qa/`, `archive/`, `_build/`의 중간 데이터·의존성, ZIP |
| 로컬 보관 | `qa/preview-research/`의 페이지·시안 HTML·변환 프로필·상세 측정과 원문 대응 JSON |
| 로컬 보관 | `qa/visual-review/`의 실제 API 응답·수정 사본·화면 캡처 |
| 로컬 보관 | 저장소 루트 `local-only/`의 실제 입력 문서·처리 결과·개인 메모. 안내 파일만 공유 |

이 구분은 `.gitignore`와 `test/.gitignore`에 반영되어 있습니다. 공유 대상이라는 표시는 다음 커밋에 포함할 후보라는 뜻이며, 아직 커밋되거나 GitHub에 올라갔다는 뜻은 아닙니다. 제외된 파일은 삭제하지 않고 기존 경로에 보관합니다.

아래 설명의 상세 응답·로그·수정 사본은 해당 PC에서 시험을 실행하면 생성됩니다. GitHub에서 내려받은 저장소에는 핵심 보고서만 포함합니다. 실제 개인정보를 넣어 시험할 때는 기존 가상 시험 입력을 덮어쓰지 말고 `local-only/` 아래에서 별도 작업하세요.

직접 수정 입력란 표시의 재현·확인 절차는 `docs/verification/direct-edit-ui-2026-10-25.md`에 기록합니다. 보고서는 공유 대상이며 실제 화면 검증의 사본·다운로드 해시·화면 캡처는 로컬 전용 `qa/direct-edit-ui/`에 보관합니다.

## 시험 구성

2026년 10월 25일 GitHub 커밋 `f1d424bb245cedc5c082ebb94ef91381bd2a2300`을 기준으로 만든 가상 문서 시험 모음입니다. HWPX tail·OOXML 부가 정보·Word 사본 검증을 수정한 현재 결과는 `results/`, 수정 전 결과는 `before-fix/`에 있습니다. 실제 개인정보를 사용하지 않았으며 이메일은 예약 도메인 `example.invalid`를 사용합니다.

- `fixtures/`: 검사에 넣은 원본 예시 21개
- `reviewed/`: 실제 앱 API가 제공한 수정 사본. 이름에 `auto_full`이 붙은 파일은 검출 후보 전체 가림 결과입니다. **미탐 정보가 남은 사본도 포함하므로 배포용으로 사용하지 마세요.**
- `manifest.json`: 각 예시의 알려진 개인정보와 확인할 등장 횟수
- `results/REPORT.md`: 결과와 수정 권고
- `results/audit.json`: 문서별 상세 결과
- `results/*_input_job.json`: 실제 검출 후보와 앱이 읽은 내용
- `results/*_independent.json`: 앱과 별개로 저장 파일 내부를 확인한 결과
- `results/root-causes.json`: 저장 실패와 누락의 원인 재현
- `before-fix/`: 수정 전 보고서·검출 결과·실패 및 원문 잔존 사본. 과거 증거이므로 현재 성공 여부와 구분합니다.
- `templates/`: 기존 합성 시험에서 만든 HWPX 기본 문서. 새 예시를 재생성할 때 필요합니다.
- `archive/`: 교체 전 로컬 버전 ZIP. Git에는 포함하지 않습니다. Git의 `codex/pre-replacement-20261025-3248804` 브랜치에도 이전 버전을 보관했습니다.
- `qa/`: 렌더링과 원인 조사 자료. Git에는 포함하지 않습니다.

## 시험을 다시 실행하기

프로젝트 루트에서 실행합니다. 모델과 파일 도구가 준비된 Python 환경이 필요합니다.

문서 화면과 부분 가림·전체 가림·직접 수정의 실제 연결은 `.venv/Scripts/python.exe -X utf8 test/check_visual_review.py`로 점검합니다. 가상 이력서 DOCX와 발표자료 PPTX를 실제 atonlee/koelectra-ko-pii-ner·인증 API로 검사하고 원본/사본 페이지, 저장 파일 내부, 사본 재생성 시 캐시 정리를 확인합니다. 결과는 로컬 전용 `qa/visual-review/api/`에 저장하며 핵심 결과는 위 검증 보고서에 기록합니다.

즉시 적용 미리보기의 원본 보존·반복 값의 위치별 변경·미설정/유지/취소·빈 내용과 영역 수정 우선 처리는 `node --test tests/document-draft.test.mjs tests/masking.test.mjs`로 확인합니다. 시험과 `docs/verification/file-draft-toggle-2026-10-25.md`는 공유 대상이며 화면 캡처는 `qa/visual-review/ui/`에만 보관합니다.

```powershell
.venv/Scripts/python.exe -X utf8 -u test/run_document_audit.py
.venv/Scripts/python.exe -X utf8 -u test/investigate_failures.py
```

정규식 가짜 탐지기를 쓰지 않고 실제 atonlee/koelectra-ko-pii-ner 모델과 ko-pii, 인증된 FastAPI 경로를 사용합니다. 파일 업로드, 상태 조회, 가림과 직접 수정, 사본 다운로드를 시험합니다. OS 파일 선택 창 조작은 시험하지 않습니다. `unique_names` 추가 시험은 내부 작업 관리자를 직접 호출합니다.

이력서 DOCX·PDF의 기본 검출만 다시 확인하려면 `.venv/Scripts/python.exe -X utf8 test/check_resume_detection.py`를 실행합니다. 별도 정답 목록의 기본 개인정보 12곳을 비교하며 PDF는 OCR 중복을 빼고 글자층을 기준으로 집계합니다. 핵심 결과는 `resume-review/summary.json`, 상세 응답은 로컬 전용 `local-only/resume-detection/`에 저장합니다. 입력 수정이나 사본 생성은 하지 않습니다.

문맥 개선 후 공유 예시 7개는 `check_shared_context.py --phase after --export`로, 별도 실제 모델 문장 10개는 `check_context_probes.py`로 점검합니다. 상세 응답과 수정 사본은 `local-only/context-review/`에 저장합니다. `--phase before`는 코드 수정 전에 기준 결과를 보관할 때만 사용하며, 과거 결과를 다시 만들기 위해 현재 코드에서 실행하지 마세요. 기존 21개 입력을 분리해 재실행할 때는 `run_document_audit.py --output-dir test/qa/context-regression`을 사용합니다. `write_context_report.py`는 이 자료와 원본 해시·사본의 알려진 원문 잔존·공개 날짜 보존을 확인해 `context-review/summary.json`을 갱신합니다.

`word_linebreak.docx`는 이름·전화 중간에 강제 줄바꿈을 넣은 예시입니다. 이 사례만 정답 비교 시 줄바꿈을 접되 실제 원문 위치로 다시 대응합니다. 후보가 줄바꿈 양쪽의 정보를 전부 덮어야 완전 검출로 인정하며, 다른 사례의 비교 기준은 바꾸지 않습니다.

`auto_full`은 자동으로 개인정보를 가리는 제품 기능이라는 뜻이 아닙니다. 시험 코드가 사용자를 대신해 **검출된 후보를 전부 선택하고 전체 가림을 지시한 실행 모드**입니다. `manual_repair`는 앱이 읽은 텍스트에 한해 알려진 정답으로 직접 수정한 결과입니다. `selective`, `custom`은 의도적으로 일부 개인정보를 남기는 개별 조작 시험입니다.

예시 제작 코드는 `build_fixtures.py`와 `_build/build_office.mjs`입니다. Office 기본 파일은 Codex의 문서 제작 런타임으로 만들고, 숨김 시트나 툴팁 같은 시험 조건은 XML을 지정해 넣었습니다. 검사 재실행에는 제작 런타임이 필요하지 않습니다. 최종 fixture의 SHA-256과 결과의 대응은 `results/fixture-hashes.json`에 기록합니다.

이번 PC에서는 기존 `.runtime/python`, `.runtime/file-python`, `.runtime/ml-python` 패키지를 `.venv`가 참조하도록 로컬 `.pth`를 연결했습니다. 모델과 패키지의 재다운로드를 피하기 위한 로컬 환경 설정이며 제품 소스에는 포함하지 않습니다. 새 PC의 깨끗한 설치 시험을 수행했다는 뜻은 아닙니다.

## 공유 문서 예시를 다시 만들기

완성된 `shared-document-examples/` 파일은 제작 환경 없이 앱에 넣어 검사할 수 있습니다. 다시 제작하려면 Python의 python-docx·lxml·reportlab·openpyxl·pypdf, Node.js의 `@oai/artifact-tool`, DOCX 렌더러와 LibreOffice·Poppler가 필요합니다. 제작 도구는 앱의 실행 의존성과 별개입니다.

1. 문서 제작용 Python으로 `_build/create_shared_documents.py`를 실행합니다. 가상 Word 문서와 로컬 중간 데이터 `shared_data.json`이 생성됩니다.
2. artifact-tool을 찾을 수 있는 Node.js 환경에서 `_build/build_shared_workbook.mjs`를 실행합니다. Excel과 미리보기를 만듭니다.
3. 같은 Python으로 `_build/finalize_shared_documents.py`를 실행합니다. 숨김 시트 설정, Word 렌더링, PDF·정답 목록·로컬 ZIP 생성을 수행합니다.

`render_documents.py`와 최종 패키징 도구는 기본값으로 현재 사용자 홈의 Codex 제작 런타임을 찾습니다. 다른 설치 위치에서는 `DOCUMENT_RUNTIME`을 런타임의 `dependencies` 폴더로, `DOCX_RENDERER`를 `render_docx.py` 파일 경로로 지정하세요. Word 렌더링에는 한국어 글꼴도 필요합니다.

HWP 수정 저장, 스캔 이미지의 OCR 성능, 암호화 문서, 전체 Office/한컴 버전 호환성, 대용량 처리 성능은 이번 결론에 포함하지 않습니다. HWPX는 패키지 구조와 텍스트 잔존을 확인했으며 한컴 화면에서 여는 시험은 수행하지 않았습니다.

## 지원 형식별 공유 문서 예시 12종

기본 미리보기와 원본 배치의 차이·파일별 처리 방향은 [형식별 안내](../docs/features/file-preview-formats.md)에 정리했습니다. 실제 모델·API 확인 도구는 `check_format_previews.py`이며 상세 응답과 요약은 로컬 전용 `qa/format-previews/`에 저장합니다. 이 스크립트·`tests/test_format_previews.py`·`tests/file-preview.test.mjs`·핵심 안내는 공유 대상, 생성된 API 응답·스크린샷은 로컬 대상입니다.

`format-document-examples/files/`에는 `.txt`, `.csv`, `.tsv`, `.docx`, `.pptx`, `.hwpx`, `.hwp`, `.xlsx`, `.pdf`, `.png`, `.jpg`, `.jpeg`가 하나씩 있습니다. 교육 메일·당첨자 명단·봉사자 배치표·추천서·운영 발표자료·공문·배송 명단·회의록·신청서·수령 확인서·현장 연락 명단으로 구성했습니다. 모두 가상 정보이며 기존 7개 예시와 별도입니다.

`사용안내.md`, `검사_확인목록.md`, `확인목록.json`으로 원본의 알려진 개인정보와 공개 일정 문맥을 비교할 수 있습니다. 이 안내·목록과 ZIP은 파일 검사에 넣지 마세요. `제작_검증.json`은 12개 실제 형식의 해시와 앱 읽기 확인 결과입니다. 개인정보 검출 정확도·수정 성공률을 측정한 보고서와 구분합니다. HWP는 실제 OLE 바이너리이나 현재 앱에서는 추출 본문 검사만 가능합니다. HWP·HWPX의 한컴 화면 배치는 검증하지 않았습니다.

다시 제작하려면 위 문서 제작 의존성과 JDK·`.runtime/file-tools/hwplib-1.1.11.jar`가 필요합니다. 제작용 Node 모듈은 `_build/node_modules`에서 번들 런타임을 참조하도록 설정합니다. 제작 순서는 다음과 같습니다.

1. 제작용 Python으로 `_build/create_format_examples.py` 실행
2. 제작용 Node로 `_build/build_format_office.mjs` 실행
3. JDK로 `_build/CreateFormatHwp.java`를 컴파일하고 실행. 인자는 `qa/format-documents/hwp-lines.txt`, `format-document-examples/files/07_시민교육_참가안내.hwp`, `qa/format-documents/hwp-readback.txt` 순서입니다. 클래스 경로에 hwplib JAR을 포함합니다.
4. 제작용 Python으로 `_build/finalize_format_examples.py` 실행. 숨김 시트와 HWPX 미리보기를 정리합니다.
5. 앱 Python으로 `check_format_examples.py` 실행. 실제 앱 읽기와 OCR을 확인합니다. 상세 글자·미리보기는 `qa/format-documents/`에만 남습니다.
6. 제작용 Python으로 `_build/finalize_format_examples.py --package` 실행. 핵심 검증 요약과 로컬 ZIP을 만듭니다.

DOCX는 문서 렌더러로, PDF·이미지는 페이지 렌더링으로, PPTX·XLSX는 제작 도구의 렌더링으로 화면을 확인했습니다. HWP는 hwplib 저장 후 전체 문장 재읽기를 확인했으며 HWPX는 패키지 및 앱의 본문 추출을 확인했습니다. 이 모음의 이미지는 선명한 기본 스캔이며 저화질·기울기·필기 시험을 대신하지 않습니다.
