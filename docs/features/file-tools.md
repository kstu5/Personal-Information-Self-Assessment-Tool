# 파일 검사용 외부 도구 설치

파일 검사의 일부 기능은 pip·npm으로 설치되지 않는 외부 도구 세 가지가 필요하며, **저장소에 들어 있지 않고 설치 스크립트도 내려받지 않습니다.** 이 문서의 주소에서 받아 지정한 위치에 놓으세요. 게시글 검사와 DOCX·PPTX·HWPX·텍스트·CSV 검사는 이 도구 없이 동작합니다.

## 한눈에 보기

| 도구 | 쓰는 기능 | 없으면 | 놓을 위치 (프로젝트 폴더 기준) |
|---|---|---|---|
| OCR 데이터 (Tesseract `tessdata_fast` 영어·한국어) | 이미지·PDF 페이지의 글자 읽기 | 이미지 OCR 실패 안내, 직접 가리기만 가능 | `.runtime/file-tools/tessdata/eng.traineddata`<br>`.runtime/file-tools/tessdata/kor.traineddata` |
| hwplib 1.1.11 + Java 11 이상 | HWP 본문 읽기 (읽기 전용) | HWP 검사 불가 (HWPX는 영향 없음) | `.runtime/file-tools/hwplib-1.1.11.jar` |
| LibreOffice | XLSX 수식 재계산·값 전용 사본 | XLSX 검사 불가 | `.runtime/file-tools/libreoffice/program/soffice.com` 이 존재해야 함 |

`.runtime/`은 설치 스크립트(`scripts/setup.ps1` 또는 `scripts/setup.sh`)가 만드는 폴더입니다. 먼저 설치 스크립트를 한 번 실행한 뒤 이 문서를 따르세요. 도구가 없어도 설치 스크립트는 중단되지 않고, 끝에서 어떤 도구가 비어 있는지 보여 줍니다.

## Windows

PowerShell을 프로젝트 폴더에서 엽니다.

### 1. OCR 데이터

받는 곳: Tesseract 공식 저장소 [tesseract-ocr/tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) (`eng.traineddata`, `kor.traineddata`)

```powershell
New-Item -ItemType Directory -Force .runtime\file-tools\tessdata | Out-Null
curl.exe -L -o .runtime\file-tools\tessdata\eng.traineddata https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/eng.traineddata
curl.exe -L -o .runtime\file-tools\tessdata\kor.traineddata https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/kor.traineddata
```

이 프로젝트는 아래 SHA-256 값의 파일만 받아들입니다(`scripts/prepare/prepare_file_tools.py`에 고정). 다르면 `OCR model integrity check failed`로 멈춥니다.

| 파일 | SHA-256 |
|---|---|
| `eng.traineddata` | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |
| `kor.traineddata` | `6b85e11d9bbf07863b97b3523b1b112844c43e713df8b66418a081fd1060b3b2` |

```powershell
Get-FileHash .runtime\file-tools\tessdata\*.traineddata | Format-Table Hash, Path -AutoSize
```

### 2. hwplib와 Java

hwplib는 Maven Central에 올라온 Java 라이브러리입니다 ([kr.dogfoot:hwplib](https://central.sonatype.com/artifact/kr.dogfoot/hwplib), 소스 [neolord0/hwplib](https://github.com/neolord0/hwplib), 라이선스 Apache-2.0).

```powershell
curl.exe -L -o .runtime\file-tools\hwplib-1.1.11.jar https://repo1.maven.org/maven2/kr/dogfoot/hwplib/1.1.11/hwplib-1.1.11.jar
```

Java 11 이상이 필요합니다. 프로그램은 `C:\Program Files\Java\jdk*\bin\java.exe`를 먼저 찾고, 없으면 `PATH`의 `java`를 씁니다. 예: [Eclipse Temurin](https://adoptium.net/)을 설치하세요.

### 3. LibreOffice

받는 곳: [libreoffice.org/download](https://www.libreoffice.org/download/) (설치 파일은 `download.documentfoundation.org`에서 제공되며, 파일 이름은 `LibreOffice_26.8.1_Win_x86-64.msi`입니다. 이전 버전은 [downloadarchive.documentfoundation.org/libreoffice/old/](https://downloadarchive.documentfoundation.org/libreoffice/old/)). 이 프로젝트가 검증한 버전은 26.8.1입니다.

설치한 뒤, 프로젝트가 기대하는 위치(`.runtime\file-tools\libreoffice\program\soffice.com`)에서 설치 폴더가 보이게 연결합니다. 폴더 연결(junction)은 관리자 권한이 필요하지 않습니다.

```powershell
New-Item -ItemType Directory -Force .runtime\file-tools | Out-Null
New-Item -ItemType Junction -Path .runtime\file-tools\libreoffice -Target "C:\Program Files\LibreOffice"
```

설치 위치를 바꿨다면 `-Target`을 그 폴더로 바꾸세요. 연결 대신 폴더를 통째로 복사해도 됩니다(`Copy-Item -Recurse`, 약 1.6GB).

## Linux

```bash
sudo apt install libreoffice-calc tesseract-ocr tesseract-ocr-kor libtesseract-dev libleptonica-dev default-jre
bash scripts/setup.sh                 # 설치된 LibreOffice와 OCR 데이터를 .runtime/file-tools에 연결합니다
curl -L -o .runtime/file-tools/hwplib-1.1.11.jar \
  https://repo1.maven.org/maven2/kr/dogfoot/hwplib/1.1.11/hwplib-1.1.11.jar
```

시스템 패키지의 OCR 데이터는 위의 고정 SHA-256 파일과 다를 수 있습니다. Linux에서는 `setup.sh`가 해시 검사 없이 연결하며, 결과가 Windows와 조금 다를 수 있습니다.

## 받는 주소 확인하기

내려받기 전에 세 주소가 살아 있고 크기가 맞는지 확인할 수 있습니다. 아래 명령은 파일을 받지 않고 응답 상태와 크기만 보여 줍니다(`HTTP/... 200`과 `Content-Length`).

```powershell
curl.exe -sIL https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/kor.traineddata | findstr /i "HTTP content-length"
curl.exe -sIL https://repo1.maven.org/maven2/kr/dogfoot/hwplib/1.1.11/hwplib-1.1.11.jar | findstr /i "HTTP content-length"
curl.exe -sIL https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/LibreOffice_26.8.1_Win_x86-64.msi | findstr /i "HTTP content-length"
```

작성 PC에서 검증에 쓴 파일의 크기는 다음과 같습니다. `Content-Length`가 같으면 같은 파일일 가능성이 높습니다.

| 파일 | 크기(바이트) |
|---|---|
| `eng.traineddata` | 4,113,088 |
| `kor.traineddata` | 1,677,415 |
| `hwplib-1.1.11.jar` | 1,034,097 |
| `LibreOffice_26.8.1_Win_x86-64.msi` | 374,870,016 |

## 준비됐는지 확인하기

```powershell
python scripts\prepare\prepare_file_tools.py
```

도구별로 `[OK]` 또는 `[MISSING]`이 출력됩니다. 이 스크립트는 OCR 데이터의 해시도 확인하므로, 다르면 위의 오류로 멈춥니다. 확인이 끝나면 앱의 **파일 검사**에서 XLSX, 이미지, HWP를 각각 열어 보세요.

## 확인 상태

- 놓을 위치와 파일 이름은 코드(`backend/file_formats.py`, `backend/image_ocr.py`)에서 확인했습니다.
- **OCR 데이터(eng)**: 위 주소가 GitHub가 알려 주는 공식 `download_url`과 같고, 그 파일의 크기(4,113,088바이트)가 검증에 쓴 파일과 정확히 같습니다. kor는 같은 저장소의 같은 형식이지만, 조회가 실패해서 크기는 대조하지 못했습니다.
- **hwplib**: Maven Central에서 `kr.dogfoot:hwplib:1.1.11`의 POM(`.../1.1.11/hwplib-1.1.11.pom`)이 실제로 열리는 것을 확인했습니다(Apache-2.0). `.jar`는 같은 폴더의 같은 이름 규칙이지만 직접 받아 보지는 않았습니다.
- **LibreOffice**: 다운로드 페이지가 `LibreOffice_26.8.1_Win_x86-64.msi`를 안내하는 것은 확인했지만, `download.documentfoundation.org`는 자동 조회를 막고 있어서(robots 제한) 위 직접 주소와 파일 크기는 확인하지 못했습니다.
- OCR 데이터의 SHA-256이 공식 파일과 일치하는지는 파일을 받아 해시를 계산해야 알 수 있어서 확인하지 못했습니다. 크기가 같다는 것까지만 확인했습니다.
- Windows의 폴더 연결(junction)과 설치된 LibreOffice 사용은 Windows에서 실행해 보지 못했습니다. Linux의 연결 방식은 실행해서 확인했습니다.
