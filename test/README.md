# 문서 개인정보 검토와 수정 시험

## GitHub 공유 대상과 로컬 보관 대상

| 구분 | 경로와 내용 |
|---|---|
| 공유 대상 | 시험용 `.py`, `_build/`의 `.py`·`.mjs` 제작 스크립트, `fixtures/`, `templates/`, `manifest.json` |
| 공유 대상 | `shared-document-examples/`의 가상 문서·정답 목록·사용 안내. 묶음 ZIP은 로컬 보관 |
| 공유 대상 | `results/`의 `REPORT.md`, `summary.json`, `cases.csv`, `fixture-hashes.json`, `root-causes.json`, `artifact-integrity.json` |
| 공유 대상 | `before-fix/results/`의 보고서·요약·시험별 표·입력 해시, `additional-review/REPORT.md` |
| 로컬 보관 | `reviewed/`와 `before-fix/reviewed/`의 수정 사본, 상세 API 응답·조사 JSON·환경 정보·실행 로그 |
| 로컬 보관 | `additional-review/`의 보고서 외 재현 산출물, `qa/`, `archive/`, `_build/`의 중간 데이터·의존성, ZIP |
| 로컬 보관 | 저장소 루트 `local-only/`의 실제 입력 문서·처리 결과·개인 메모. 안내 파일만 공유 |

이 구분은 `.gitignore`와 `test/.gitignore`에 반영되어 있습니다. 공유 대상이라는 표시는 다음 커밋에 포함할 후보라는 뜻이며, 아직 커밋되거나 GitHub에 올라갔다는 뜻은 아닙니다. 제외된 파일은 삭제하지 않고 기존 경로에 보관합니다.

아래 설명의 상세 응답·로그·수정 사본은 해당 PC에서 시험을 실행하면 생성됩니다. GitHub에서 내려받은 저장소에는 핵심 보고서만 포함합니다. 실제 개인정보를 넣어 시험할 때는 기존 가상 시험 입력을 덮어쓰지 말고 `local-only/` 아래에서 별도 작업하세요.

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

```powershell
.venv/Scripts/python.exe -X utf8 -u test/run_document_audit.py
.venv/Scripts/python.exe -X utf8 -u test/investigate_failures.py
```

정규식 가짜 탐지기를 쓰지 않고 실제 A 모델과 ko-pii, 인증된 FastAPI 경로를 사용합니다. 파일 업로드, 상태 조회, 가림과 직접 수정, 사본 다운로드를 시험합니다. OS 파일 선택 창 조작은 시험하지 않습니다. `unique_names` 추가 시험은 내부 작업 관리자를 직접 호출합니다.

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
