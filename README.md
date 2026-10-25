# 개인정보 자가진단 도구

게시글과 공유할 파일에서 개인정보 후보를 찾고, 사용자가 위치와 문맥을 확인해 가리거나 수정하는 로컬 프로그램입니다. 검사는 PC 안에서 수행하며 외부 생성형 AI API에 문서 내용을 전송하지 않습니다. 설치 단계에는 실행 패키지·모델·파일 도구 다운로드를 위한 인터넷 연결이 필요합니다.

이름·주소에는 **atonlee/koelectra-ko-pii-ner**를, 전화번호·이메일 등 다른 유형에는 **ko-pii 1.16.0 규칙**을 사용합니다. 모델 파일은 고정 리비전과 해시로 확인합니다. 위험도와 후보 수는 검토를 돕는 표시이며 개인정보 전체 검출이나 법적 안전성을 보장하지 않습니다.

## 사용 흐름

1. 시작 화면에서 **게시글 검사** 또는 **파일 검사**를 선택합니다.
2. 심각·높음·보통·낮음·참고 위험도별 목록과 원문 위치를 함께 확인합니다.
3. 후보마다 **부분 가림·전체 가림·직접 수정·유지**를 선택합니다. 처리 지정 표시로 미설정 항목과 구별합니다.
4. **원본 / 적용 미리보기**를 전환해 변경 예정 내용을 비교합니다.
5. 파일은 **수정 사본 생성·재검사** 후 새 파일로 저장합니다. 원본을 덮어쓰지 않습니다. 게시글은 수정한 내용으로 이어 쓰거나 `.piipost` 작업 파일로 저장합니다.

적용 미리보기는 저장 전 확인 화면입니다. Word·PowerPoint의 문구 교체는 원본 위에 겹쳐 보여주므로 긴 문구의 줄바꿈·배치가 실제 사본과 다를 수 있습니다. 최종 사본 화면과 남은 검출 후보를 확인하세요. `.piipost`는 암호화되지 않은 JSON이며 게시글 제목·본문을 저장합니다. 파일 검사 선택 상태를 보관하는 형식은 아닙니다.

## 지원 파일과 미리보기

| 형식 | 기본 보기 | 가림·수정 사본 |
|---|---|---|
| TXT | 읽어낸 내용 | 부분/전체 가림, 직접 수정 |
| CSV·TSV | 빈 행·셀을 유지한 표 | 셀 내용의 가림·수정 |
| DOCX·PPTX | LibreOffice로 변환한 문서·슬라이드 페이지 | 지원 텍스트·부가 정보 수정, 메모·노트는 별도 위치 목록 |
| HWPX | 추출 본문을 재구성한 내용 | 지원 XML 텍스트·부가 정보 수정 |
| HWP | 추출 본문 내용 | **읽기 전용**, 수정 저장 미지원 |
| XLSX | 시트·셀 표와 숨김 영역 | 재계산 후 **값 전용 사본**. 수식을 유지하는 편집이 아님 |
| PDF | 실제 페이지, 글자층·OCR 후보 | 선택 영역 가림. 새 문구 교체 미지원 |
| PNG·JPG·JPEG | 실제 이미지와 OCR 위치 | 선택 영역 가림. JPG/JPEG 수정 사본은 PNG |

파일당 최대 **20MB**, 한 번에 **8개**를 엽니다. 큰 문서·복잡한 개체·암호화·지원하지 않는 구조는 검토나 저장이 제한될 수 있습니다. HWP/HWPX 내용 화면은 원래 쪽 배치·표·글꼴을 재현하지 않습니다. Word·PowerPoint 페이지 밖의 속성·메모·노트도 텍스트·위치 보기에서 검토해야 합니다. [형식별 상세 안내](docs/features/file-preview-formats.md), [수정 사본 정책](docs/design/file-review-copy-policy.md)을 참고하세요.

## Windows에서 소스로 실행

Python 3.12, Node.js와 npm, Microsoft Edge WebView2가 필요합니다. HWP 읽기에는 Java 11 이상, DOCX/PPTX 페이지와 XLSX 재계산에는 LibreOffice가 필요합니다. 기본 준비 도구는 OCR 데이터·hwplib·탐지 모델을 준비하지만 새 PC에 LibreOffice와 Java를 모두 설치해 주는 것은 아닙니다. 경로·설치 방법은 [파일 도구 안내](docs/features/file-tools.md)를 확인하세요.

```powershell
git clone https://github.com/kstu5/Personal-Information-Self-Assessment-Tool.git
cd Personal-Information-Self-Assessment-Tool
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
```

다음부터는 루트의 **`개인정보 자가진단 도구 실행.vbs`**를 더블클릭해 실행할 수 있습니다. `.venv/`, `.runtime/`, `dist/`는 설치로 생성되는 로컬 폴더입니다. 실행 환경을 GitHub에 올릴 필요는 없습니다. 모델을 처음 불러오거나 문서를 페이지로 변환할 때 시간이 걸릴 수 있습니다.

Windows 설치 프로그램의 소스와 제작 방법은 [installer 안내](installer/README.md)에 있습니다. 설치판은 실행 환경·Java·LibreOffice 등을 내려받는 별도 경로입니다. 이 저장소에 완성 설치 파일을 포함하지 않으며, 현재 PC 검증과 새 PC의 설치 완료 검증을 구분합니다. Linux용 `setup.sh`·`start.sh`도 있으나 Windows 전용 창과 동일한 파일 미리보기를 검증한 지원 환경은 아닙니다.

## 예시로 확인하기

- [이력서·당첨자 명단 등 공유 문서 7개](examples/documents/사용안내.md)
- [지원 형식별 실제 공유 상황 예시 12개](examples/formats/사용안내.md)
- [예시 목록과 정답 비교 방법](examples/README.md)

모든 예시는 합성 정보입니다. 검사할 문서만 열고 정답 목록·안내문은 함께 넣지 마세요. 12종을 확인할 때는 8개 이하로 나눠 엽니다. 후보 개수만 비교하지 말고 **해당 값의 정확한 위치, 가림 범위, 저장 사본의 잔존 정보와 보존할 내용**을 대조하세요.

## 개발·검증

프로젝트 루트에서 실행합니다. 실제 모델·OCR·LibreOffice를 사용하는 시험은 준비된 실행 환경이 필요합니다.

```powershell
npx --yes pnpm@12.15.0 run check
npx --yes pnpm@12.15.0 run build
npx --yes pnpm@12.15.0 run test:frontend
.venv/Scripts/python.exe -X utf8 scripts/check/test_backend.py
.venv/Scripts/python.exe -X utf8 scripts/check/check_repository.py
.venv/Scripts/python.exe -X utf8 validation/check_format_previews.py
```

백엔드 시험은 지정한 `tests/`만 수집합니다. 저장소 전체에서 무차별적으로 시험을 수집하면 과거 연구·임시 환경까지 포함될 수 있습니다. 예시 제작에는 별도 문서 제작 도구가 필요하지만, 이미 만든 예시를 검사하는 데는 필요하지 않습니다.

이전 검증에서 Python 시험 95개, 화면 처리 로직 시험 11개, 실제 모델·API의 예시 12종 기본 미리보기를 확인했습니다. 공유 문서 7개의 지정 확인 지점은 128/128, 별도 문서 21개의 지정 지점은 89/89였습니다. **작은 합성 표본의 결과이며 일반 정확도 수치가 아닙니다.** 현재 변경의 검증과 과거 기록은 [변경 이력](docs/CHANGELOG.md), [검증 안내](validation/README.md)에서 구분해 확인하세요.

## 폴더와 공유 범위

| 위치 | GitHub에 포함하는 내용 |
|---|---|
| `src/`, `backend/` | 화면과 로컬 검사·파일 처리 코드 |
| `models/`, `requirements*.txt`, `pnpm-lock.yaml` | 모델 정보·설치 의존성 고정값. 모델 가중치 자체는 제외 |
| `examples/` | 사용자가 직접 열어 볼 합성 공유 문서·정답 목록 |
| `tests/` | 자동 단위·API 시험 |
| `validation/` | 문서 재현 도구·회귀 입력·핵심 검증 결과 |
| `scripts/`, `installer/` | 설치·실행·검증·배포 제작 코드 |
| `docs/` | 현재 설계·정책·기능·검증 설명, 구분된 과거 기록 |
| `local-only/README.md` | 비공개 자료 보관 안내. 하위 실제 자료는 제외 |

실제 사용자 문서·수정 사본·개인 메모는 `local-only/`에 둡니다. 상세 시험 로그·화면·미리보기는 `validation/qa/` 등 제외 경로에 생성합니다. [파일 배치와 Git 관리 기준](docs/REPOSITORY.md)에 이전 경로와 현재 위치를 정리했습니다. `.gitignore`는 이미 공개한 Git 이력에서 파일을 지우지 않습니다.

## 남은 한계

OCR의 흐림·기울기·필기, 모호한 이름·주소 문맥, 복잡한 문서 구조에는 누락과 오탐이 있을 수 있습니다. 검출 0건은 개인정보가 없다는 뜻이 아닙니다. 파일명·문맥상 간접 식별 정보와 미표시 부분도 직접 살펴보세요. HWP 수정 저장, HWP/HWPX 원본 페이지 표시와 PDF·이미지의 문구 교체는 미지원입니다. 실행 종료·화면 새로고침 전에 필요한 사본을 저장하세요.
