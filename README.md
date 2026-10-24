# 게시 전 개인정보 노출 자가진단 도구

Windows PC에서 게시글의 제목과 본문을 검사하고, 개인정보 후보를 원문과 위험도별 목록으로 확인하는 도구입니다. React + TypeScript + Vite 화면과 Python + FastAPI를 사용합니다. **이름·주소는 A 모델(`atonlee/koelectra-ko-pii-ner`), 나머지 유형은 ko-pii 1.16.0 규칙이 검사합니다.** 기본 실행 방식은 pywebview와 WebView2를 사용하는 전용 프로그램 창입니다.

## 한눈에 보기

| 항목 | 내용 |
|---|---|
| 목적 | 게시글이나 문서를 올리기 전에 이름·주소·전화번호 같은 개인정보가 들어 있는지 스스로 점검하고, 필요한 곳을 가려서 올릴 수 있게 돕습니다. |
| 사용 방식 | 시작 화면에서 **게시글 검사**(제목·본문 입력) 또는 **파일 검사**(문서·이미지 열기)를 선택합니다. |
| 탐지 | 이름·주소는 A 모델, 그 밖의 유형은 ko-pii 규칙입니다. 결과는 5단계 위험도(심각·높음·보통·낮음·참고)로 표시합니다. |
| 개인정보 처리 | 모두 내 PC에서 처리합니다. 서버는 `127.0.0.1`에서만 실행하고 입력·결과를 외부로 보내지 않으며, 설치 후 검사에는 인터넷이 필요하지 않습니다. |
| 기술 | React 19 + TypeScript + Vite 화면, Python + FastAPI 로컬 서버, pywebview(WebView2) 전용 창 |
| 지원 환경 | Windows x64(검증), Linux x86_64(실험적, 브라우저 모드). macOS는 지원하지 않습니다. |
| 주의 | 자동 검사는 개인정보를 잘못 표시하거나 놓칠 수 있습니다. 게시 전 사람이 한 번 더 확인해야 합니다. |

처음 읽는다면 이 문서 → [파일 검사 적용 기록](docs/features/file-inspection.md) → [상세 인수인계](docs/HANDOFF.md) 순서를 권합니다. 전체 문서 목록은 [문서 안내](#문서-안내)에 있습니다.

## 주요 기능

### 게시글 검사

제목과 본문을 입력하면 개인정보 후보를 원문 위에 표시하고 위험도별 건수를 보여 줍니다. 항목마다 **부분 가림 / 전체 가림 / 가리지 않음 / 직접 수정**을 고르고, 결과를 `.piipost` 작업 파일로 저장하거나 다시 불러올 수 있습니다. 자세한 조작은 [사용 방법](#사용-방법)과 [가림과 수정](#가림과-수정)에 있습니다.

### 파일 검사

시작 화면에서 **게시글 검사 / 파일 검사**를 선택합니다. **파일 검사 → 파일 추가**에서 문서 여러 개를 열고, 파일·시트·셀·이미지를 오가며 가릴 위치를 선택할 수 있습니다. **사본 생성·재검사 → 실제 사본 확인 → 새 파일로 사본 저장** 순서로 사용하세요.

- DOCX·PPTX·HWPX·TXT·CSV·TSV와 PNG/JPEG 사본 처리, 제한된 XLSX·PDF 처리를 제공합니다. 파일 내부 일반 메모·발표자 노트·작성자·읽을 수 있는 변경 기록도 검토합니다.
- XLSX는 지원 수식을 강제 재계산한 **값 전용 사본**입니다. 시트/셀 보기와 숨김 셀 표시를 제공합니다. 외부 연결·그림·차트·피벗·정의된 이름·조건부 서식 등은 아직 제한합니다.
- PDF는 선택 글자/이미지 데이터를 지운 뒤 새 PDF로 저장합니다. 이미지에는 불투명 픽셀 가림과 직접 드래그 기능이 있습니다. **OCR 재검사 0건도 개인정보가 없다는 보증이 아닙니다.**
- HWP는 추출 본문 검사만 지원하고 **수정 저장은 지원하지 않습니다.** HWPX 사본으로 변환해 다시 검토할 수 있습니다.
- 전용 창은 원본을 바꾸거나 기존 파일을 덮어쓰지 않습니다. 작업 취소·제거·정상 종료 때 임시 사본을 정리합니다. 문서 처리는 로컬에서 수행합니다.

정확한 지원 표·제한·처리 한도·도구 설치·검증은 [파일 검사 적용 기록](docs/features/file-inspection.md)을 확인하세요. 입력 한도와 `.piipost` 저장 방식은 게시글 검사에만 적용됩니다.

## 시작하기

### 일반 사용자: 설치 프로그램으로 설치하기 (Windows)

`BeforePost-Setup-<버전>.exe`를 실행하고 안내를 따르면 됩니다. Python·Node.js·Java·LibreOffice를 따로 설치할 필요가 없고, 관리자 권한도 필요하지 않습니다.

- 설치 파일은 작고(수 MB), 필요한 구성요소(Python, 탐지 모델, OCR 데이터, Java, LibreOffice 등)는 설치 중에 인터넷에서 내려받습니다. **설치 중 인터넷 연결이 필요하며, 몇 분 걸립니다.** 설치가 끝난 뒤 검사에는 인터넷이 필요하지 않습니다.
- 모든 구성요소는 설치 폴더(`%LOCALAPPDATA%\Programs\BeforePost`) 안에만 들어가고, 시스템 전체 설정과 PATH는 바꾸지 않습니다. 내려받은 파일은 해시를 확인하며, 설치가 끝나면 임시로 받은 설치 파일은 지웁니다. 설치 후 차지하는 용량은 약 3 GB입니다(이 중 LibreOffice가 약 1.5 GB).
- 설치가 끝나면 시작 메뉴의 **게시 전 개인정보 검토**로 실행합니다. 제거는 Windows의 **설치된 앱**에서 합니다.
- 설치 중 문제가 생기면 설치 폴더의 `install.log`를 개발자에게 보내 주세요.

설치 파일을 만드는 방법은 [인스톨러 만들기](#인스톨러-만들기-개발자)에, 소스에서 직접 설치하는 방법은 그 아래 개발자용 안내에 있습니다.

### 인스톨러 만들기 (개발자)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build_installer.ps1
```

결과는 `installer/out/BeforePost-Setup-<버전>.exe`입니다. 버전은 `package.json`의 `version`을 씁니다. 화면을 이미 빌드해 두었다면 `-SkipFrontend`로 `pnpm install`과 화면 빌드를 건너뛸 수 있습니다.

- 빌드하는 PC에 필요한 것: Node.js(화면 빌드), JDK 11 이상(`javac`가 PATH에 있어야 함, `HwpText.java` 사전 컴파일), Inno Setup 6(`winget install JRSoftware.InnoSetup`. 스크립트는 `.tools/inno`, `%LOCALAPPDATA%\Programs\Inno Setup 6`, `Program Files (x86)\Inno Setup 6` 순으로 찾습니다), `.runtime/file-tools/hwplib-1.1.11.jar`(없으면 먼저 `python scripts/prepare/prepare_file_tools.py` 실행).
- 설치 파일에는 앱 코드와 빌드된 `dist/`만 들어가고, 나머지는 설치할 때 내려받습니다. 내려받는 Python·pip·Java·LibreOffice의 주소와 SHA-256은 `installer/components.json`에 고정되어 있으므로 구성요소 버전을 바꿀 때는 이 파일만 고치면 됩니다.
- 릴리스: `package.json`의 `version`을 올리고 → 위 명령으로 빌드하고 → `installer/out/`의 exe를 GitHub Releases에 올립니다. 용량 때문에 exe는 저장소에 커밋하지 않으며(`installer/out/`은 `.gitignore`), 서명이 없어 Windows SmartScreen 경고가 뜰 수 있습니다.
- 설치 흐름과 단계별 로직은 `installer/setup.iss`(마법사)와 `installer/install_runtime.ps1`(단계 실행)에 있습니다. 설치 중 오류는 설치 폴더의 `install.log`에 남습니다.

### 개발자: 소스에서 설치하기

### 준비물 (소스에서 설치할 때)

- Python 3.12 이상, Node.js (화면 빌드와 설치에만 필요하고, 평소 검사는 Python만으로 실행됩니다. pnpm은 npx를 통해 자동으로 관리됩니다)
- Windows는 Microsoft WebView2 런타임, Linux는 아래 [Linux 안내](#linux에서-설치하기-실험적)의 시스템 패키지
- 최초 설치 시 인터넷 연결 (PyPI, PyTorch CPU 저장소, Hugging Face)

### Windows에서 설치하기

확인한 환경은 Windows x64, Python 3.12.14, Node.js 24.19.0, Microsoft WebView2입니다. 다른 Python·Windows 조합은 아직 시험하지 않았습니다. 최초 의존성 설치에는 인터넷 연결이 필요합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Python이 명령으로 잡히지 않으면 `-Python`에 실행 파일 경로를 전달하세요. 이 스크립트는 `.venv` 가상환경을 만들고 모든 Python 패키지를 설치합니다. `.runtime/models/model-a`에 고정 버전의 A 모델을, `.runtime/file-tools`에 외부 도구(LibreOffice, Tesseract 등)를 준비합니다. 모델 파일은 SHA-256으로 확인합니다. 시스템 전체 패키지는 변경하지 않습니다. WebView2 런타임은 Windows 환경에 준비되어 있어야 합니다.

A 모델 가중치·토크나이저 등은 약 57 MB, 모델 실행 패키지는 현재 설치 기준 약 745 MB입니다. GPU는 사용하지 않습니다. 작성 PC에서 모델 준비는 약 4초, 준비 후 3만 자 검사는 약 2.6초였지만 다른 PC의 속도·메모리 여유는 별도 확인이 필요합니다. 실행 중인 구버전 창이 있다면 글을 저장하고 닫은 뒤 다시 실행하세요.

### Linux에서 설치하기 (실험적)

Windows 전용 창(WebView2)은 쓸 수 없고, 브라우저 모드로 실행합니다. Windows 쪽 파일(`setup.ps1`, `start.ps1`, `게시전 실행.vbs`)은 바꾸지 않았습니다.

```bash
bash scripts/setup.sh     # PYTHON=python3.12 로 경로 지정 가능
bash scripts/start.sh     # 출력된 주소(127.0.0.1)를 브라우저로 열고, 종료는 Ctrl+C
```

- Python 3.12 이상, Node.js, 인터넷 연결(PyPI, PyTorch CPU 저장소, Hugging Face)이 필요합니다. 파일 검사를 쓰려면 `sudo apt install libreoffice-calc tesseract-ocr tesseract-ocr-kor libtesseract-dev libleptonica-dev default-jre` 를 먼저 설치하세요.
- 시스템에 설치된 LibreOffice와 Tesseract 데이터를 `.runtime/file-tools`에 링크해서 씁니다. Windows 쪽에서 고정한 버전과 다를 수 있습니다. 설치되어 있지 않으면 해당 기능만 비활성화되고 경고가 출력됩니다.
- HWP 읽기에 필요한 `hwplib` jar는 저장소에 없습니다. 받는 곳은 위의 [파일 검사용 외부 도구](#파일-검사용-외부-도구-선택)를 참조하세요. HWPX는 영향이 없습니다.
- 확인 범위: 위 설치 절차와 서버 기동, LibreOffice 변환은 Linux x86_64에서 확인했습니다. 모델 내려받기와 검사 정확도, aarch64·macOS는 확인하지 못했습니다.

### 파일 검사용 외부 도구 (선택)

**OCR 데이터와 hwplib은 설치 시 자동으로 다운로드됩니다.** LibreOffice만 수동 설치가 필요합니다. 없어도 게시글 검사와 DOCX·PPTX·HWPX·텍스트 검사는 동작합니다.

| 도구 | 설치 방식 | 비고 |
|---|---|---|
| OCR 데이터 (영어·한국어) | ✅ 자동 다운로드 (6.5 MB) | setup.ps1이 GitHub에서 받아서 SHA-256 검증 |
| hwplib 1.1.11 | ✅ 자동 다운로드 (1 MB) | setup.ps1이 Maven Central에서 받아서 검증 (Java 11 이상 필요) |
| LibreOffice 26.8.1 | ⚠️ 수동 설치 (300 MB+) | [설치 안내](docs/features/file-tools.md) 참조 |

### 설치가 잘 됐는지 확인하기

프로젝트 폴더에서 실행합니다.

```bash
python scripts/check/test_backend.py   # 자동 시험(pytest)
npx pnpm run test:masking              # 마스킹 단위 시험
```

설치 스크립트의 모델 단계(A 모델 내려받기)까지 끝났다면 모두 통과해야 합니다. 모델 단계를 마치지 못했다면 모델을 쓰는 시험 3개(`test_real_detection_api`, `test_pinned_assets_and_corruption`, `test_worker_reuse_timeout_recovery_and_close`)만 실패하고 나머지는 통과합니다(모델 없이 Linux에서 확인한 결과: 40개 통과, 3개 실패). 실패한 시험이 이 3개가 아니라면 설치를 다시 확인하세요.

### 실행하기

- **Windows**: 설치가 끝난 프로젝트 폴더에서 **`게시전 실행.vbs`를 더블클릭**하면 별도 프로그램 창이 열립니다. 설치로 만들어지는 `.venv`, `.runtime`, `dist` 폴더를 함께 유지해야 합니다.
- **Linux**: `bash scripts/start.sh`를 실행하고 출력된 주소를 브라우저로 엽니다. 종료는 Ctrl+C입니다.

## 사용 방법

1. **새 글 작성**을 선택하고 제목·본문을 쓰거나 붙여넣습니다. 가상 예시 글로 먼저 사용해 볼 수도 있습니다.
2. **개인정보 검사**를 누르면 위에 위험도별 건수, 가운데에 전체 제목·본문이 표시됩니다. 앱을 켠 뒤 첫 검사는 모델 준비 시간이 추가되고 이후에는 모델을 재사용합니다. 색칠된 값을 누르면 아래에서 **부분 가림 / 전체 가림 / 가리지 않음 / 직접 수정**을 지정할 수 있습니다.
3. **저장**을 누르면 현재 제목을 바탕으로 파일명을 추천합니다. 금지 문자는 제외하지만 글 제목은 그대로 보존합니다. 다음 Windows 파일 선택 창에서 원하는 위치를 고릅니다. **가림·수정을 적용했다면 처리 결과의 제목·본문을 저장합니다.** 화면을 ‘원문’으로 보고 있어도 저장 대상은 처리 결과입니다.
4. 이후 **저장 / Ctrl+S**는 같은 파일을 갱신합니다. 파일 도구 모음의 **··· → 다른 이름으로 저장**으로 별도 파일을 만들 수 있습니다.
5. 프로그램을 다시 실행한 뒤 **저장한 글 불러오기**에서 `.piipost` 작업 파일을 선택하면 이어서 작성할 수 있습니다. 검사 결과는 다시 계산합니다.

저장하지 않은 변경이 있을 때 새 글·다른 파일 열기·창 닫기를 선택하면 저장, 저장하지 않고 계속, 취소를 안내합니다. 제목을 바꾸어도 이미 저장된 파일명은 자동으로 바꾸지 않습니다.

**자동 검사는 개인정보를 잘못 표시하거나 놓칠 수 있습니다. 게시 전, 표시되지 않은 부분까지 직접 한 번 더 확인해 주세요.**

## 가림과 수정

- 처음 검사했을 때에는 아무 항목도 자동으로 가리지 않습니다. **한 개씩 선택 / 여러 개 선택** 버튼으로 선택 방식을 바꿉니다. 여러 개 선택에서는 Ctrl 없이 항목을 차례로 누르고, 다시 누르면 해제합니다. 전체 선택과 선택 개수도 표시합니다. Ctrl+클릭은 보조 단축 조작으로 지원합니다.
- 전체 가림은 `█████`, 부분 가림은 유형에 맞는 `*` 표시입니다. ‘직접 수정’에서는 가릴 위치를 원하는 형태로 직접 입력하고 **수정 내용 반영**을 누릅니다.
- 아래의 왼쪽 목록은 부분 가림, 오른쪽은 전체 가림입니다. 각 항목 오른쪽의 **전체로 / 부분으로**는 해당 위치 하나만 전환합니다. **취소**는 원문으로 복원하며 본문 탐지 표시는 유지합니다. **되돌리기**는 최근 20회 변경까지 복구합니다.
- 목록의 **직접 수정**을 누르면 편집 영역의 입력란이 바로 열리고 현재 가림 결과가 채워집니다. 내용을 고친 뒤 **수정 내용 반영**을 누르면 적용됩니다.
- 긴 목록은 6곳씩 페이지를 나눕니다. 같은 값이 반복되어도 등장 위치별로 따로 처리합니다. 기존의 5단계 위험도는 처리 전 검출 건수로 유지합니다.
- **원문 / 처리 결과**는 보기 전환입니다. **수정한 글로 이어쓰기**는 적용한 가림·수정을 작성 내용으로 가져오며, 실제 글이 바뀌면 이전 탐지 결과를 무효화합니다. 이 버튼은 변경을 취소하는 동작이 아닙니다.
- `.piipost` 형식은 버전 1 그대로입니다. 파일에는 처리 후 제목·본문만 저장하며, 취소용 원문·검출 위치·선택 상태·되돌리기 기록은 저장하지 않습니다. 원문 파일도 보관하려면 **다른 이름으로 저장**을 사용하세요. ‘가리지 않음’ 같은 검토 결정만으로는 저장할 글이 변경되지 않습니다.

## 동작 구조

```text
 전용 창(pywebview + WebView2) 또는 브라우저
   └─ React 화면 (src/ → dist/)
        │  HTTP, 세션 토큰 필요
        ▼
 로컬 FastAPI 서버 (127.0.0.1, 자동 선택 포트)      run.py · backend/app.py
   ├─ /api/check ────────► 별도 프로세스에서 탐지      backend/detection.py · model_a.py
   │                        ko-pii 규칙 + A 모델(이름·주소)
   ├─ /api/files/* ──────► .piipost 저장·불러오기       backend/documents.py · desktop.py
   └─ /api/documents/* ──► 파일 검사 작업 큐            backend/file_review.py
                              └─ 격리된 작업 프로세스    backend/file_worker.py · file_formats.py · image_ocr.py
                                   └─ 보조 도구: LibreOffice(XLSX 값 재계산), Tesseract OCR, Java + hwplib(HWP 읽기)
```

- **게시글 검사**: 화면이 제목·본문을 `/api/check`로 보내면 서버가 별도 프로세스에서 탐지하고, 원문과 맞는 위치인지 확인한 뒤 Python 문자 위치를 JavaScript의 UTF-16 위치로 바꿔 돌려줍니다. 이모지 등에서 위치가 어긋나지 않게 하기 위한 처리입니다.
- **파일 검사**: 서버가 파일의 비공개 작업 사본을 만들고(클라이언트가 보낸 경로는 쓰지 않습니다), 격리된 작업 프로세스가 형식별 어댑터로 글자와 이미지를 꺼내 같은 탐지기로 검사합니다. 사용자가 고른 위치를 가린 **새 사본**을 만들어 다시 검사한 뒤 저장하며, 원본은 수정하지 않습니다.
- **실행 환경**: 표준 Python 가상환경(`.venv`)에 모든 패키지를 설치합니다. `.runtime/`에는 외부 도구와 모델만 보관합니다. `setup` 스크립트가 만들며 git에는 포함되지 않습니다.

  | 폴더 | 내용 |
  |---|---|
  | `.venv/` | Python 가상환경 (모든 pip 패키지: FastAPI, ko-pii, pywebview, torch, transformers, PyMuPDF 등) |
  | `.runtime/file-tools/` | 외부 도구 (LibreOffice, Tesseract OCR 학습 데이터, hwplib jar) |
  | `.runtime/models/model-a/` | 고정 버전의 A 모델 가중치 (SHA-256으로 검증) |

API 계약, 입력 한도, 오류 처리, 수정할 때 주의할 점은 [상세 인수인계](docs/HANDOFF.md)의 6장에 있습니다.

## 현재 범위와 한계

- 제목·본문 검사, 실제 탐지 위치 표시, 5단계 위험도별 건수, 개별·일괄 가림과 수정, 적용 목록의 전환·취소를 제공합니다.
- 수동 저장·불러오기, 저장 위치 선택, 원제목 보존, 저장 실패·손상 파일·지원하지 않는 버전·외부 수정 감지에 대응합니다.
- 저장 성공 이후만 저장 상태를 갱신합니다. 쓰기 중 오류 시 기존 파일을 보존하도록 같은 폴더의 임시 파일에서 교체합니다.
- 원문 수정 시 이전 결과를 무효화하고 오래된 응답을 버립니다. 이모지 등 UTF-16 위치를 변환합니다.
- 서버는 `127.0.0.1`의 자동 선택 포트에서만 실행합니다. Host·Origin·세션 토큰을 확인하고 입력·결과를 외부 서비스로 전송하지 않습니다. 설치 후 검사에 인터넷이 필요하지 않습니다.
- 게시글 입력 원문과 검사 결과를 로그·URL·앱의 자동 저장소에 기록하지 않습니다. 문서 파일 검사는 로컬 세션 임시 사본을 사용합니다. 직접 저장한 작업 파일에는 저장 시점의 글이 포함됩니다. `.piipost`는 UTF-8 JSON 형식의 작업 파일이며 암호화 형식이 아닙니다.

입력 한도는 제목 300자, 본문 30,000자, 작업 파일 2 MB입니다. 첫 모델 준비는 최대 60초, 준비 후 검사는 최대 20초, 화면의 응답 대기는 최대 90초입니다. 긴 글은 겹치는 구간으로 나눠 끝까지 검사합니다. 모델 누락·손상·시간 초과를 후보 0건으로 표시하지 않습니다.

자동 저장·전원 종료 전의 미저장 내용 복구, 사용자 선택 없는 자동 마스킹, macOS·스마트폰 전용 앱은 포함하지 않았습니다. 문서·이미지·OCR 지원 범위는 위의 파일 검사 안내를 확인하세요. OneDrive 별도 대응은 이전 결정대로 1차 사용 후 검토합니다. 갑작스러운 강제 종료 시 쓰기 중이던 `.before-post-*.tmp`가 선택한 저장 폴더에 남을 수 있으며, 임시 파일을 자동 복구본으로 보장하지 않습니다.

### 저장소에 포함되지 않은 것

저장소에는 소스와 문서, 검증 기록만 있고 아래 항목은 없습니다. 받은 직후 알아 두세요.

| 항목 | 설명 |
|---|---|
| `.venv/`, `.runtime/`, `node_modules/`, `dist/` | 설치 스크립트가 만듭니다. |
| 파일 도구 (LibreOffice, OCR 학습 데이터 eng/kor, hwplib jar) | 원래 작성 PC의 `research/` 폴더에 있었고 저장소에 올리지 않았으며, 설치 스크립트가 내려받지도 않습니다. 받는 곳과 놓을 위치는 [외부 도구 설치 안내](docs/features/file-tools.md)에 있습니다. 없으면 XLSX 값 확인·이미지 OCR·HWP 읽기가 동작하지 않거나 오류 안내가 나옵니다. 게시글 검사에는 영향이 없습니다. Linux의 `setup.sh`는 시스템에 설치된 LibreOffice와 Tesseract를 대신 연결합니다. |
| `research/`, `tmp/` | 조사 원자료와 임시 산출물입니다. `scripts/evaluate/`와 `scripts/check/`의 일부 도구는 `research/`의 입력 자료를 요구하므로 그대로는 실행되지 않습니다. |

## 개발용 실행과 시험

```powershell
python run.py                 # 전용 창
python run.py --browser       # Edge 등의 브라우저에서 확인
python run.py --headless --ready-file tmp/app-ready.json
python scripts/check/test_backend.py
python scripts/check/check_model_a.py
python scripts/check/check_desktop.py
npx pnpm run build
```

브라우저 모드는 파일 선택 API를 지원하는 최신 Edge/Chrome에서 사용할 수 있습니다. 탭을 닫아도 개발용 서버는 종료되지 않으므로 실행한 터미널에서 Ctrl+C로 종료하세요. 전용 창은 창 종료와 서버 종료를 함께 처리합니다. 같은 프로젝트의 전용 창은 중복 실행을 막습니다.

화면 통합 시험은 `scripts/check/check_ui.cjs`를 실행합니다. `PLAYWRIGHT_MODULE`에 Playwright 설치 위치를 전달할 수 있고 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`로 브라우저 경로를 변경할 수 있습니다. 시험은 `tmp`의 가상 문서만 사용합니다.

시험 결과와 미검증 범위는 [변경·검증 이력](docs/CHANGELOG.md)과 [검증 기록](docs/verification/verification.md)에 있습니다.

## 프로젝트 구조

| 위치 | 역할 |
|---|---|
| `src` | React 화면, 상태 관리, 브라우저 파일 연결 |
| `backend` | 로컬 API, 탐지 프로세스, 문서 검증·저장, 전용 창 연결 |
| `run.py` | 루프백 서버와 Windows 창 실행·종료 |
| `tests` | 자동 시험(pytest, 마스킹 단위 시험) |
| `scripts` | 설치·실행(`setup.ps1`, `start.ps1`)과 용도별 도구: `prepare/` 환경 준비, `check/` 검증, `evaluate/` 탐지 평가, `build/` 문서 생성. [안내](scripts/README.md) |
| `docs` | `features/` 기능 적용 기록, `design/` 설계·정책, `verification/` 검증 기록, 인수인계·의존성 문서. [안내](docs/README.md) |
| `reports` | 사례조사 보고서 원고와 생성 스크립트. [안내](reports/README.md) |
| `output` | 검증 결과와 최종 보고서 산출물. [안내](output/README.md) |
| `research`, `tmp`, `.venv`, `.runtime` | 로컬 전용(git 제외): 조사 원자료, 임시 산출물, 가상환경, 외부 도구/모델 |

주요 파일:

| 파일 | 역할 |
|---|---|
| `run.py` | 서버·창 시작과 종료, Windows 중복 실행 방지 |
| `backend/app.py` | API, 세션 토큰, Host·Origin 제한, 정적 화면 제공 |
| `backend/detection.py` | ko-pii 호출, 원문 구간 검증, UTF-16 위치 변환, 검사 프로세스 |
| `backend/model_a.py`, `backend/model_assets.py` | A 모델 추론, 고정 모델 파일 검증(불러오기 경로에 네트워크 접근 없음) |
| `backend/documents.py` | `.piipost` 형식, 파일명 규칙, 파싱, 원자적 저장, 외부 수정 감지 |
| `backend/file_review.py` | 파일 검사 작업 큐 (클라이언트에는 불투명 id만 전달) |
| `backend/file_worker.py`, `file_formats.py`, `image_ocr.py` | 격리된 작업 프로세스, 형식별 어댑터, 로컬 OCR |
| `backend/desktop.py` | Windows 파일 선택 창과 종료 보호 연결 |
| `src/App.tsx` | 시작 화면, 게시글 입력, 미저장 보호 |
| `src/PrivacyReview.tsx`, `src/FileReview.tsx`, `src/masking.ts` | 게시글 검토 화면, 파일 검사 화면, 가림 규칙 |

## 문서 안내

| 문서 | 내용 |
|---|---|
| [docs/HANDOFF.md](docs/HANDOFF.md) | 상세 인수인계: 결정 사항, 기술 구조, API, 수정 위치 |
| [docs/features/file-inspection.md](docs/features/file-inspection.md) | 파일 검사 지원 형식·한도·도구 |
| [docs/features/file-tools.md](docs/features/file-tools.md) | 파일 검사용 외부 도구의 받는 곳·놓을 위치·확인 방법 |
| [docs/features/masking-ui-integration.md](docs/features/masking-ui-integration.md) | 가림 화면 적용 기록 |
| [docs/features/model-a-integration.md](docs/features/model-a-integration.md) | A 모델 적용과 출처·라이선스 |
| [docs/design/](docs/design/) | 화면 설계와 수정 사본 제공 정책 |
| [docs/verification/](docs/verification/) | 1차 구현 검증과 초기 탐지 평가 |
| [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) | 의존성 라이선스 메타데이터 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 날짜별 적용 내역과 검증 상태 |
| [scripts/README.md](scripts/README.md), [reports/README.md](reports/README.md), [output/README.md](output/README.md) | 폴더별 안내 |

기술 참고: [ko-pii 1.16.0](https://pypi.org/project/ko-pii/1.16.0/), [pywebview 구성](https://pywebview.flowrl.com/guide/architecture.html), [Vite](https://vite.dev/guide/), [Windows 파일명 규칙](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file).
