# output

검증 스크립트가 결과를 쓰는 폴더이자 최종 보고서 산출물 보관소입니다. 스크립트가 이 경로를 직접 참조하므로 폴더 이름은 바꾸지 않습니다.

| 위치 | 내용 | 만든 곳 |
|---|---|---|
| `docx/`, `pdf/` | 종합보고서·인수인계·점검 보고서 최종본 | `scripts/build/` |
| `handoff/`, `게시전_프로젝트_인수인계_자료_v1.zip` | 인수인계 묶음 | `scripts/build/build_handoff.py` |
| `community-review/`, `커뮤니티_게시글_3종_시험자료.zip` | 커뮤니티 글 3종 탐지 점검 | `scripts/evaluate/evaluate_community_cases.py`, `scripts/build/build_community_report.py` |
| `model-benchmark-2026-10-17/`, `model-comparison-2026-10-19/` | 모델 비교 시험 결과 | 일회성 실험 기록 |
| `model-a-integration-2026-10-17/` | A 모델 적용 검증 | `scripts/check/check_model_a.py` |
| `masking-2026-10-19/` | 가림 UI 적용 검증 기록 | 수동 기록(생성 스크립트 없음) |
| `file-feature-validation/`, `ocr-fix-validation/` | 파일 검사·OCR 검증 | `scripts/check/check_file_*`, `check_ocr_ui.cjs` |

`render-*/`, `profile/` 같은 LibreOffice 캐시는 `.gitignore`로 제외됩니다.
