# scripts

설치·실행 진입점은 이 폴더 바로 아래에 두고, 나머지 도구는 용도별 폴더로 나눕니다.

| 위치 | 용도 |
|---|---|
| `setup.ps1` | 새 PC 환경 설치(의존성, 모델, 화면 빌드). 루트 README의 설치 안내가 이 파일을 가리킵니다. |
| `start.ps1` | 전용 창 실행. `게시전 실행.vbs`가 호출합니다. |
| `setup.sh`, `start.sh` | 위 두 파일의 Linux 대응판(브라우저 모드). 자세한 내용은 루트 README의 "Linux에서 설치하기" |
| `prepare/` | 환경 준비 보조: 파일 도구(`prepare_file_tools.py`), atonlee/koelectra-ko-pii-ner(`prepare_model_a.py`), 환경 기록(`record_environment.py`) |
| `check/` | 검증 도구: 백엔드(`test_backend.py`), 모델(`check_model_a.py`), 전용 창(`check_*desktop.py`), 화면(`check_*ui.cjs`), 파일 기능(`check_file_*.py`) |
| `evaluate/` | 탐지 평가: 규칙 기준선(`rule_baseline.py`), 소규모 평가, 커뮤니티 사례 평가, 문맥 진단 |
| `build/` | 문서 생성: 커뮤니티 점검 보고서, 인수인계 PDF·ZIP |

프로젝트 루트에서 실행하세요. 예: `python scripts/check/test_backend.py`, `node scripts/check/check_ui.cjs`
