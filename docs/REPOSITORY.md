# 파일 배치와 Git 관리 기준

프로젝트 공식 명칭은 **개인정보 자가진단 도구**입니다. GitHub 저장소 주소와 기존 작업 파일·설치 경로의 내부 식별자는 호환성을 위해 유지합니다. 공식 표시명 변경만으로 저장소 URL이나 현재 작업 폴더 이름을 바꾸지는 않습니다.

## 공개 소스와 로컬 자료

| 구분 | 위치 | 기준 |
|---|---|---|
| 실행 소스 | `src/`, `backend/`, `run.py` | 앱 동작에 필요한 코드 |
| 설치 정보 | `models/`, lock 파일, `scripts/`, `installer/` | 재현 가능한 버전·해시·준비 절차 |
| 사용 예시 | `examples/documents/`, `examples/formats/` | 합성 문서와 별도 정답 목록만 포함 |
| 자동 시험 | `tests/` | 제품 동작의 회귀 확인 |
| 문서 검증 | `validation/` | 제작·재현 도구, `fixtures/`, `templates/`, 핵심 보고서·요약 |
| 설명 | `README.md`, `docs/` | 현재 안내와 과거 기록을 구별 |
| 실제 입력 | `local-only/inputs/` | Git 제외, 실데이터를 예시에 섞지 않음 |
| 결과·개인 메모 | `local-only/outputs/`, `local-only/notes/`, `local-only/archive/` | Git 제외, 필요한 하위 폴더를 사용 시 생성 |
| 상세 시험 산출물 | `validation/qa/`, `validation/reviewed/`, `.gitignore`에 정한 상세 결과 | Git 제외, 재생성 가능한 응답·화면·사본 |
| 실행·빌드 환경 | `.venv/`, `.runtime/`, `node_modules/`, `dist/`, `installer/stage/`, `installer/out/` | Git 제외, 소스 설치·빌드로 생성 |

`local-only/`는 공개 범위 구분용 폴더이며 암호화·접근 통제 기능은 아닙니다. 본인 PC의 보관·삭제 정책을 따르세요.

## 2026-10-25 배치 변경

| 이전 | 현재 |
|---|---|
| `test/shared-document-examples/` | `examples/documents/` |
| `test/format-document-examples/` | `examples/formats/` |
| 그 밖의 `test/` | `validation/` |
| `output/` | `local-only/outputs/` — 원시 결과·화면·생성 문서 로컬 보존 |
| `reports/standards-case-study/` | `local-only/archive/reports/standards-case-study/` — 이 제품과 무관한 문서 작업 보존 |
| 이전 `docs/HANDOFF.md` | `docs/archive/HANDOFF-2026-10-24.md` — 역사 기록으로 보존 |
| `launch.vbs` | `개인정보 자가진단 도구 실행.vbs` |

과거 모델 비교·커뮤니티 평가의 읽을 수 있는 핵심 기록은 `docs/verification/archive/`에 남겼습니다. 과거 기록의 명칭·수치·경로는 당시 기준이며 현재 기능 보장이나 작업 지시가 아닙니다. 열린 문서는 원래 위치에 잠긴 원본이 남을 수 있으며, 이전 `test/`·`output/`·`reports/` 경로도 Git에서 제외합니다. `research/`·`tmp/`는 기존 로컬 조사·런타임 참조가 있어 유지하는 제외 경로입니다.

## 커밋과 배포

1. 하나의 기능·정리 단위와 필요한 확인이 끝나면 커밋 시점을 알립니다.
2. 변경 파일과 포함 범위를 검토하고 `scripts/check/check_repository.py --staged`로 공개 경계·예시 해시·문서 링크를 확인합니다.
3. 소스·합성 예시·재현 도구·핵심 결과만 커밋합니다. 상세 응답, 원본 사용자 파일, 수정 사본은 넣지 않습니다.
4. 커밋과 GitHub 업로드는 구분합니다. 업로드는 별도 요청에 따라 진행합니다.

인수인계 ZIP 생성 도구는 Git 관리 파일에서 로컬 전용 경로를 제외한 소스만 묶습니다. 개인 바탕화면·연구 자료를 자동 수집하지 않습니다. 생성된 PDF·ZIP과 설치 EXE는 로컬 산출물이며 소스 커밋에 넣지 않습니다. 이미 추적된 파일은 제외 설정만 추가해도 빠지지 않으므로 인덱스도 확인해야 합니다. 이번 이동은 과거 커밋의 데이터를 지우거나 Git 이력을 다시 쓰지 않습니다.
