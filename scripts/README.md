# 설치·개발 도구

프로젝트 루트에서 실행합니다. 명령은 [루트 README](../README.md)에 정리했습니다.

| 위치 | 용도 |
|---|---|
| `setup.ps1`, `start.ps1` | Windows 소스 설치·실행. 정식 이름의 루트 VBS가 start를 호출 |
| `setup.sh`, `start.sh` | Linux 브라우저 모드 보조 도구. Windows와 동일한 전체 파일 지원은 미검증 |
| `prepare/` | 파일 도구·atonlee/koelectra-ko-pii-ner 준비, 로컬 환경 기록 |
| `check/test_backend.py` | `tests/`만 수집하는 정규 Python 시험 |
| `check/check_installed.py` | 설치 폴더의 Python·패키지·도구만으로 게시글·12종 파일·수정 사본 확인 |
| `check/check_repository.py` | 공개 경계·문서 링크·예시 해시·Python 구문 확인. 커밋 전 `--staged` 사용 |
| 그 밖의 `check/` | 모델·전용 창·파일·화면 검증. 일부 과거 도구는 로컬 research/원시 결과가 필요 |
| `evaluate/` | 탐지 평가·문맥 조사. 일부 과거 입력은 로컬 보관 |
| `build/` | 설치판·인수인계·보고서 제작. 생성물은 로컬 전용 |

문서 재현과 예시 제작은 `validation/`, 자동 시험은 `tests/`, 완성 가상 문서는 `examples/`에 있습니다. 출력은 `local-only/outputs/` 또는 지정된 로컬 QA 위치에 생성합니다. 과거 평가 자료가 없는 새 복제본에서는 정규 시험과 `validation/`의 공개 입력 기반 확인을 먼저 사용하세요.
