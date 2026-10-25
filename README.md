# 개인정보 자가진단 도구

공유하기 전 게시글과 문서에서 개인정보 후보를 찾고, 사용자가 위치와 문맥을 확인해 가리거나 수정하는 **Windows용 로컬 프로그램**입니다. 현재 배포 버전은 **0.1.0**입니다.

**[Windows 설치 파일 다운로드](https://github.com/kstu5/Personal-Information-Self-Assessment-Tool/releases/download/v0.1.0/PrivacySelfAssessmentTool-Setup-0.1.0.exe)** · **[예시 문서 12종 ZIP 다운로드](https://github.com/kstu5/Personal-Information-Self-Assessment-Tool/releases/download/v0.1.0/PrivacySelfAssessmentTool-Examples-0.1.0.zip)** · [Release 0.1.0](https://github.com/kstu5/Personal-Information-Self-Assessment-Tool/releases/tag/v0.1.0)

## 설치와 실행

1. 실행 중인 이전 버전이 있다면 작업을 저장하고 종료합니다.
2. 위 설치 EXE를 실행하고 설치할 폴더를 선택합니다.
3. 인터넷에 연결한 상태로 설치가 끝날 때까지 기다립니다.
4. 시작 메뉴의 **개인정보 자가진단 도구**를 실행합니다.

설치 파일은 **Windows x64 온라인 설치판**입니다. Python·탐지 모델·OCR·Java·LibreOffice와 필요한 WebView2를 설치 중 준비하므로 인터넷 연결과 충분한 디스크 공간이 필요합니다. 사용자가 Python·Node.js·JDK를 따로 설치하거나 설치 프로그램을 직접 제작할 필요는 없습니다. 설치 이후 개인정보 검사는 PC 안에서 수행하며, 외부 생성형 AI API로 문서를 보내지 않습니다.

기본 설치 위치는 `%LOCALAPPDATA%\Programs\BeforePost`이고 설치 화면에서 바꿀 수 있습니다. 폴더 이름의 BeforePost는 기존 설치와의 호환성을 위한 내부 이름입니다. 실패하면 설치 폴더의 `install.log`에서 실패 단계를 확인하세요. 로그를 공유할 때는 개인 경로 등 불필요한 정보를 지우세요.

설치 EXE에는 코드 서명을 적용하지 않았습니다. Release의 `SHA256SUMS.txt`로 다운로드한 EXE와 예시 ZIP의 해시를 대조할 수 있습니다. GitHub의 **Source code ZIP/TAR는 개발용 소스**이며 설치 프로그램이 아닙니다. 같은 0.1.0 설치판을 다시 받을 때도 현재 Release의 해시를 기준으로 확인하세요.

## 사용 방법

1. **게시글 검사** 또는 **파일 검사**를 선택합니다.
2. 위험도별 검출 목록과 원문 위치를 함께 확인합니다.
3. 항목마다 **부분 가림·전체 가림·직접 수정·가리지 않음**을 선택합니다. 미설정 항목과 처리 지정 항목을 구별할 수 있습니다.
4. **원본 / 적용 미리보기**를 전환해 변경 모습을 비교합니다.
5. 파일은 **사본 생성·재검사**를 실행하고 실제 사본과 남은 후보를 확인한 뒤 새 파일로 저장합니다. 원본에는 덮어쓰지 않습니다.

게시글은 수정한 내용으로 이어 쓰거나 `.piipost` 작업 파일로 저장합니다. 이 파일은 제목·본문을 담은 암호화되지 않은 JSON이며, 파일 검사에서 선택한 처리 상태를 보관하는 형식은 아닙니다. 앱 종료·화면 새로고침 전에 필요한 사본을 저장하세요.

### 이미지의 가림과 직접 수정

독립된 **PNG·JPG·JPEG**는 선택한 개인정보의 원문 픽셀을 지우고 다음 내용을 다시 씁니다.

| 방법 | 예시 |
|---|---|
| 부분 가림 | `박**`, `010-****-2103` |
| 전체 가림의 비공개 표시 | `비공개` |
| 직접 수정 | `담당자`, `테스트 test !@# ✓`처럼 입력한 문구. 빈 문구는 삭제 |

글자 크기를 원문 높이에 맞춰 유지하고 같은 줄의 빈 공간을 활용합니다. 좁은 폭에 맞춰 글씨를 작게 줄이지 않습니다. 일반 기호와 로컬 글꼴이 지원하는 체크·이모지를 표시하며, 지원하지 않는 문자나 공간 부족은 문서 화면과 경고를 함께 보여 줍니다. 문구를 고치기 전에는 해당 수정 사본을 생성할 수 없습니다. 직접 수정은 한 줄 80자 이하입니다.

적용 미리보기와 저장은 같은 이미지 처리를 사용합니다. **검출 표시 보기**로 위치 표시를 켜고 끌 수 있고, 자동 검출이 놓친 곳은 **직접 영역 가리기**로 검게 가립니다. 글꼴·사진·복잡한 배경은 원본과 다르게 보일 수 있습니다. 수정 사본은 메타데이터를 제거한 PNG로 저장합니다.

## 지원 파일과 제한

| 형식 | 확인 화면과 수정 범위 |
|---|---|
| TXT | 읽어낸 내용과 위치, 선택 가림·직접 수정 |
| CSV·TSV | 행·열·빈 셀을 유지한 표, 셀 내용 가림·수정 |
| DOCX·PPTX | LibreOffice로 변환한 문서·슬라이드 페이지, 지원 텍스트와 부가 정보 수정. 메모·노트·속성도 별도 위치에서 확인 |
| HWPX | 추출 본문을 재구성한 내용, 지원 XML 텍스트·부가 정보 수정. 원래 쪽 배치 재현은 미지원 |
| HWP | 추출 본문 확인만 지원. **읽기 전용이며 수정 저장 미지원** |
| XLSX | 셀·숨김 영역 확인. 지원 수식 재계산 후 **값 전용 사본**으로 가림·수정. 수식 유지 편집은 미지원 |
| PDF | 실제 페이지와 글자층·OCR 위치 확인, 선택 영역의 글자·픽셀 삭제 후 가림. **새 문구 교체 미지원** |
| PNG·JPG·JPEG | 실제 이미지와 OCR 위치, 별표·비공개 표시·직접 문구 수정·직접 영역 가림. 출력은 PNG |

파일당 **20MB**, 한 번에 **8개**, PDF는 최대 **40쪽**입니다. 문서에 들어 있는 이미지는 영역 가림을 사용하며 새 문구 교체는 지원하지 않습니다. 암호화·미지원 개체·복잡한 구조는 검사나 사본 저장을 제한할 수 있습니다.

Word·PowerPoint의 저장 전 문구 미리보기는 실제 사본의 줄바꿈·배치와 다를 수 있습니다. 실제 수정 사본을 확인하세요. HWP/HWPX 내용 화면은 원래 페이지·표·글꼴을 재현하지 않습니다. 엑셀 값 전용 사본은 입력을 바꿔도 수식을 다시 계산하지 않습니다.

## 예시 문서 12종으로 확인하기

[예시 목록과 사용 안내](examples/README.md)에서 파일을 하나씩 받거나 위 ZIP으로 한 번에 받을 수 있습니다. 설치 폴더의 `examples/formats/files/`와 시작 메뉴의 **개인정보 자가진단 도구 예시 문서**에도 같은 12종을 제공합니다.

TXT·CSV·TSV·DOCX·PPTX·HWPX·HWP·XLSX·PDF·PNG·JPG·JPEG를 실제 공유 상황의 문서로 구성했습니다. 모든 인적사항·기관명은 합성 정보입니다. 한 번에 8개까지 열 수 있으므로 12종은 두 묶음으로 검사하세요. 후보 수뿐 아니라 실제 위치, 메모·숨김 영역, 수정 사본에 남은 정보와 보존할 내용을 함께 비교하세요.

## 사용하는 탐지 방식

이름·주소에는 **[atonlee/koelectra-ko-pii-ner](https://huggingface.co/atonlee/koelectra-ko-pii-ner)**를, 전화번호·이메일 등 다른 유형에는 **ko-pii 1.16.0 규칙**을 결합합니다. 모델 파일은 고정 리비전과 해시로 확인합니다. 흐림·기울기·필기·모호한 문맥에는 누락과 오탐이 있을 수 있습니다.

검출 결과와 위험도는 검토를 돕는 후보입니다. **검출 0건은 개인정보가 없다는 보장이 아니며**, 부분 가림은 일부 정보를 남기는 선택입니다. 공유 전 원문과 수정 사본을 직접 검토하세요.

## 개발자용 소스 실행·설치판 제작

일반 사용자는 위 완성 설치 EXE를 사용합니다. 소스 실행에는 Python 3.12 이상, Node.js/npm, Windows WebView2가 필요합니다. HWP 읽기는 Java 11 이상, Office 페이지·엑셀 재계산은 LibreOffice가 필요합니다. 소스 준비 스크립트는 OCR 데이터·hwplib·모델을 준비하지만 Java와 LibreOffice를 모두 설치해 주지는 않습니다.

```powershell
git clone https://github.com/kstu5/Personal-Information-Self-Assessment-Tool.git
cd Personal-Information-Self-Assessment-Tool
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
```

이후 루트의 **개인정보 자가진단 도구 실행.vbs**로 실행할 수 있습니다. `scripts/setup.sh`·`start.sh`는 Linux 브라우저 모드 보조 도구이며 Windows 설치판과 동일한 지원 환경으로 검증한 것은 아닙니다. Linux OCR에는 Tesseract 개발 헤더와 한국어·영어 데이터, 문서 기능에는 Java·LibreOffice가 별도로 필요합니다.

Windows 설치판 제작에는 위 개발 환경과 JDK 11 이상, Inno Setup 6가 필요합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build_installer.ps1
```

결과는 `installer/out/`의 설치 EXE·예시 ZIP·`SHA256SUMS.txt`입니다. 설치 파일은 Git 소스에 넣지 않고 GitHub Releases에 배포합니다. 설치판에 포함하는 프런트엔드 구성요소의 라이선스는 설치 폴더의 `THIRD-PARTY-NOTICES.txt`, 내려받는 라이브러리·모델·외부 도구의 라이선스는 각 배포물의 고지를 확인하세요.

공개 저장소에는 `src/`, `backend/`, 필수 설치·실행 스크립트와 의존성 설정, 사용 안내, 예시 12종을 관리합니다. 개발 메모·보고서·추가 시험 문서·자동 시험 코드·상세 결과·개인 자료는 공개 목록에서 제외합니다. 실행 환경·빌드 결과도 Git에서 제외합니다.
