# atonlee/koelectra-ko-pii-ner 적용 기록

적용일: 2026-10-17. 사용자의 모델 적용 및 후속 진행 요청으로 실제 탐지 코드 변경을 진행했다. 앞선 읽기 전용 비교 시험의 제한은 이 적용 요청으로 변경되었다.

## 적용 내용

| 항목 | 현재 구현 |
|---|---|
| 모델 | atonlee/koelectra-ko-pii-ner, 학습 완료 가중치 그대로 사용 |
| 고정 revision | `1e75c01e707232401883cf364151bbe2e560c708` |
| 역할 | 모델의 NAME → PERSON, ADDRESS → ADDRESS만 사용. 다른 유형은 ko-pii 1.16.0 규칙 유지 |
| 병합 | 설치된 ko-pii의 `ROLE_SPLIT`, 위임 라벨을 PERSON·ADDRESS로 명시. 겹침 해소도 기존 라이브러리 사용 |
| 연산 | PyTorch 2.9.1+cpu, Transformers 4.57.6, FP32 CPU, 최대 4스레드, 한 번에 한 구간 |
| 긴 글 | 최대 512토큰, 64토큰 겹침. 중복 토큰은 구간 중앙에 더 가까운 예측을 사용하고 전체 BIO 구간을 복원 |
| 원문 | 정규화·자동 수정 없이 원래 위치 유지. 화면에 전달할 때 UTF-16 위치로 변환 |
| 저장 위치 | `.runtime/models/model-a`, 실행 패키지는 `.runtime/ml-python` |
| 실행 | 첫 검사 때 별도 프로세스에서 한 번 로딩, 연속 검사 재사용. 요청 처리 후 이전 입력·결과에 대한 참조 해제 |
| 제한 | 모델 준비 60초, 검사 20초, 화면 응답 대기 90초 |
| 오류 | 파일 누락·손상·로딩 실패는 명시적 오류. 시간 초과/실패 시 프로세스·파이프 폐기 후 다음 검사에서 새로 준비 |
| 종료 | 앱 종료 시 검사 중인 프로세스까지 정리. API 수명 종료에서도 정리 |

모델마다 신뢰도 기준을 임의 조정하거나 추가 규칙을 만들지 않았다. 이전 비교 시험에서 가장 좋은 결과를 보인 이름·주소 역할 분담을 그대로 연결했다. 라이브러리의 규칙 원본은 수정하지 않았다. 기존 10월 16일 규칙 진단 스크립트는 `scripts/evaluate/rule_baseline.py`로 당시 규칙 기준선을 명시했다.

## 로컬 실행과 설치

이 PC는 모델·실행 패키지·화면 빌드까지 준비되어 있다. `개인정보 자가진단 도구 실행.vbs`로 실행한다. 이미 열린 이전 버전 창은 글을 저장하고 닫은 뒤 다시 실행해야 한다. 결과 하단에 `ko-pii 1.16.0 + atonlee/koelectra-ko-pii-ner (이름·주소)`가 표시된다.

새 환경에서는 `scripts/setup.ps1`이 공식 PyTorch CPU 배포처와 PyPI에서 고정 패키지를 설치하고, Hugging Face의 고정 revision에서 파일을 준비한다. 모델은 최초 준비 때만 내려받는다. `scripts/prepare/prepare_model_a.py --from-local <폴더>`로 미리 받은 같은 모델을 복사할 수도 있다. `models/model-a.json`에 크기와 SHA-256이 고정되어 있고, 복사·다운로드 후와 모델 로딩 전에 검사한다. 실패한 다운로드는 활성 파일로 교체하지 않는다.

앱은 모델 ID를 원격 로딩에 사용하지 않고 로컬 폴더만 사용한다. `local_files_only=True`, `trust_remote_code=False`, safetensors 및 Hugging Face 오프라인·텔레메트리 비활성 설정을 사용한다. 원문을 외부 API로 전송하거나 재학습하지 않는다. 실행 중 글은 메모리에 존재하며, OS의 메모리 교환 영역까지 안전하게 지운다는 보장은 아니다.

모델 파일 합계 57,135,883바이트(약 57 MB), 모델 실행 패키지는 검증 당시 약 745 MB였다. 별도 GPU는 사용하지 않는다. 시스템 전체 Python 패키지는 변경하지 않는다.

## 검증 결과

| 확인 | 결과 |
|---|---|
| TypeScript + Vite | 빌드 통과 |
| Python 시험 | 27개 통과. 파일·API 보호, 실제 이름·주소·전화 탐지, 모델 재사용, 누락·손상, 시작/추론 시간 초과, 재시작, 중복 검사, 검사 중 종료 포함 |
| 고정 사례 대조 | 120/120개가 이전 규칙 + A 이름·주소 조합과 일치. 기존 규칙의 원본 결과도 그대로인지 확인 |
| 위치 | 모든 사례의 UTF-16 구간과 원문 일치. 이름·주소 앞 이모지, 제목/본문 분리 추가 확인 |
| 긴 글 | 1천·3천·1만·3만 자 모두 기존 시험 결과와 일치. 글 뒤쪽까지 확인 |
| 오프라인 | 모델 import·로딩·검사 동안 소켓 연결 함수를 차단. 외부 연결 시도 0회 |
| 화면 | 실제 서버 + Edge에서 12개 흐름 통과. 원문 표시·건수·저장·불러오기·취소·실패·미저장 보호·늦은 응답 무시·좁은 화면 확인 |
| WebView2 | 별도 숨김 창에서 실제 모델 검사·파일 연결·닫기 보호 확인. 일반 Python 및 콘솔 없는 pythonw 둘 다 통과. 서버와 모델 프로세스 종료 확인 |

Starlette의 httpx 시험 어댑터 사용 중단 예고 경고 1건은 기존 시험 환경 경고이며 제품 실패가 아니다. OS 파일 선택창의 선택 동작은 시험에서 임시 경로로 대체했고 실제 디스크 쓰기·읽기는 수행했다.

현재 PC에서 직접 엔진 로딩은 약 3.9초, 화면의 첫 예시 글 검사는 준비를 포함해 약 4.7초였다. 준비 후 3만 자 검사는 약 2.6초였다. 이 값은 해당 실행의 관측값이며 PC별 보장값이 아니다. 앞선 메모리 측정은 모델 프로세스 최대 작업 집합 약 408 MB, private commit 약 703 MB였다. 화면·서버·다른 앱 메모리는 별도이며 이번 통합 시험에서 메모리를 다시 정밀 측정한 것은 아니다.

실행 명령:

```powershell
python scripts/check/test_backend.py
python scripts/check/check_model_a.py
python run.py --headless --ready-file tmp/app-ready.json
node scripts/check/check_ui.cjs
python scripts/check/check_desktop.py
```

기록은 `local-only/outputs/model-a-integration-2026-10-17`에 보관한다. `parity.json`은 고정 입력의 SHA-256, 패키지 버전, 전체 사례 대조 결과를 담는다. 입력은 기존 합성 사례이며 사용자 원문을 수집하지 않았다. 앞선 A/B 보고서와 고정 정답은 그대로 보존했다.

## 개선과 남은 한계

실제 예시 화면에서는 “아래”, “두었던” 이름 오탐이 사라지고 “김하늘입니다”의 이름과 “302호”까지의 주소가 표시된다. 이전 고정 비교에서 새 합성 사례의 정답 85개 중 정확한 유형·범위 일치는 규칙 47개 → 이 조합 72개였다. 이번 120개 대조는 **그 조합을 앱에 같은 방식으로 연결했는지 확인**한 것이며 새로운 독립 정확도 시험은 아니다.

“박하차” 이름 오탐, 띄어 쓴 일부 이름의 누락, 물건의 높이·무게에 대한 기존 규칙의 오탐 등은 남아 있다. 다른 보급형 PC에서의 실제 설치·메모리·응답 시간, 실사용 문체에 대한 추가 평가, 설치형 EXE 배포는 별도 작업이다. 모델 적용이 개인정보를 모두 찾는다는 의미는 아니다.

## 출처와 라이선스

- [모델 원문과 게시자 atonlee](https://huggingface.co/atonlee/koelectra-ko-pii-ner/tree/1e75c01e707232401883cf364151bbe2e560c708): 모델 카드 기준 가중치 Apache-2.0. ko-pii 공식 개발자 모델이라고 단정하지 않는다.
- 기반 모델: [monologg/koelectra-small-v3-discriminator](https://huggingface.co/monologg/koelectra-small-v3-discriminator).
- 모델 카드의 학습 자료 표기: [BCCard/pii-masking-openpii-finance](https://huggingface.co/datasets/BCCard/pii-masking-openpii-finance), [townboy/korean-pii-dataset](https://huggingface.co/datasets/townboy/korean-pii-dataset), 각각 CC BY 4.0. 이 프로젝트는 해당 학습 데이터셋을 배포하지 않는다.
- 모델 원본 README는 모델과 함께 내려받아 보존한다. 실행 패키지의 라이선스·고지 파일도 설치 디렉터리에 유지한다. 추가 패키지 목록은 `requirements.model-a.lock.txt`, torch 버전·공식 CPU 출처는 `scripts/setup.ps1`에 고정한다.
