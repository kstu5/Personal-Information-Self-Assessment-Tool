# 개인정보 자가진단 도구 인수인계

현재 기능·실행 방법은 [루트 README](../README.md), 배치는 [저장소 기준](REPOSITORY.md), 적용 내역은 [변경 이력](CHANGELOG.md)을 기준으로 합니다. 과거의 상세 인수인계는 [보관 문서](archive/HANDOFF-2026-10-24.md)이며 현재 개발 지시가 아닙니다.

## 제품 방향

게시글과 파일을 PC 안에서 검사하고, 사용자가 위험도·원문 위치·문맥을 확인해 가림과 수정을 결정합니다. 자동으로 모든 개인정보를 삭제하거나 검출 0건을 안전으로 판정하지 않습니다. 정식 모델명은 atonlee/koelectra-ko-pii-ner이며 이름·주소에 사용합니다. 다른 유형은 ko-pii 규칙을 결합합니다.

## 구성과 변경 원칙

- React 화면은 `src/`, 로컬 FastAPI·문서 어댑터·별도 파일 처리 프로세스는 `backend/`입니다. `run.py`가 로컬 서버와 전용 창을 시작합니다.
- 문서 위치 식별자는 원본의 텍스트/XML/셀/이미지 좌표에서 만듭니다. Office 페이지 변환 좌표로 저장 대상을 추정하지 않습니다.
- 원본·적용 미리보기는 저장 전 비교이고, 수정 사본 생성·재검사·사본 화면 확인은 별도 단계입니다. 파일은 새 사본으로 저장합니다.
- DOCX/PPTX는 LibreOffice 페이지, PDF·이미지는 실제 페이지/이미지, CSV/TSV/XLSX는 셀, TXT/HWP/HWPX는 추출 내용으로 표시합니다. HWP는 읽기 전용입니다.
- 현재 미지원은 HWP 수정 저장, HWP/HWPX 원본 페이지, PDF·이미지 새 문구 교체입니다. XLSX는 재계산 후 값 전용 사본입니다.
- `.piipost`의 `before-post-document`, Windows 설치 AppId·기존 설치 폴더·실행 중복 방지 식별자, 모델 캐시의 `model-a`는 호환성을 위해 유지합니다. 표시 이름과 실제 모델명을 구분합니다.

## 자료와 검증

가상 공유 문서는 `examples/`, 자동 시험은 `tests/`, 문서 재현·회귀 확인은 `validation/`입니다. 실데이터·개인 메모·생성 사본은 `local-only/`, 상세 시험은 `validation/qa/`에 보관하며 Git에서 제외합니다. 예시 원본의 해시·정답 목록을 보존하고 저장 사본의 잔존 정보와 보존할 내용을 독립 확인합니다.

정규 확인은 README의 TypeScript 검사·빌드, 화면 처리 로직 시험, `scripts/check/test_backend.py`, `scripts/check/check_repository.py`입니다. 실제 모델·미리보기 경로는 `validation/check_format_previews.py`, Word/PPT 수정 경로는 `validation/check_visual_review.py`로 확인합니다. 로컬에만 남아 있는 과거 입력을 요구하는 일부 `scripts/check/`·`scripts/evaluate/` 도구는 전체 정규 시험의 필수 단계가 아닙니다.

OCR 난조건·문맥 식별과 복잡한 문서·새 PC 설치는 별도 검증이 필요합니다. 일부 합성 표본의 검출 성공률을 일반적인 정확도로 소개하지 마세요. 수정할 때 관련 회귀 시험과 실제 사본 검증을 함께 고려하세요.
