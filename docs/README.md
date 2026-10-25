# 프로젝트 문서

현재 사용법은 [루트 README](../README.md)를 기준으로 합니다.

| 위치 | 내용 |
|---|---|
| [REPOSITORY.md](REPOSITORY.md) | 파일 배치·공개/로컬 경계·이전 경로 |
| [HANDOFF.md](HANDOFF.md) | 현재 제품 방향·구성·개발 주의점 |
| [CHANGELOG.md](CHANGELOG.md) | 날짜별 변경과 그 시점의 검증 |
| `features/` | 파일 검사·형식별 미리보기·가림·사용 모델 |
| `design/` | 화면 설계·수정 사본 정책 |
| `verification/` | 개별 변경 검증·지원 제한 |
| `archive/`, `verification/archive/` | 과거 인수인계·평가 원문. 현재 지침과 구별 |
| [DEPENDENCIES.md](DEPENDENCIES.md) | 초기 환경의 라이선스 메타데이터 기록. 전체 최신 설치 목록은 lock 파일·설치 구성 확인 |

문서에 적힌 합성 표본 결과는 일반적인 정확도를 보장하지 않습니다. 상세 API 응답·화면·사본은 로컬에 보관합니다. `scripts/prepare/record_environment.py`의 새 환경 기록은 `local-only/outputs/environment/`에 생성하며 커밋된 lock 파일·이 문서를 덮어쓰지 않습니다.
