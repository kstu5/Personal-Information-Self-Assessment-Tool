# 파일 검사 도구 준비

개인정보 자가진단 도구의 Windows 소스 실행 기준입니다. 설치 진입점은 `scripts/setup.ps1`, 도구 준비 코드는 `scripts/prepare/prepare_file_tools.py`입니다. 완성 Windows 설치판은 [별도 설치 경로](../../installer/README.md)를 사용합니다.

## 자동 준비와 별도 설치

| 도구 | 쓰는 기능 | 소스 설치에서 준비되는 범위 |
|---|---|---|
| Tesseract tessdata_fast 영어·한국어 데이터 | PDF·이미지 OCR | 누락·해시 불일치 파일을 내려받고 SHA-256 확인 |
| hwplib 1.1.11 JAR | HWP 본문 읽기 | 내려받고 SHA-256 확인 |
| Java 11 이상 | HWP 읽기 실행 | 사용자가 설치. 설치판의 내장 JRE는 우선 사용 |
| LibreOffice | DOCX/PPTX 페이지, XLSX 재계산·값 전용 사본 | 사용자가 설치·연결. 기존 로컬 연구용 사본이 있으면 복사할 수 있음 |

OCR·hwplib·모델 준비에는 인터넷이 필요합니다. 도구 다운로드에 실패해도 준비 스크립트는 나머지를 확인하므로 마지막 `[MISSING]` 안내까지 읽으세요. Java 표시가 `[OK]`여도 버전을 검사한 것은 아닙니다. LibreOffice가 없으면 Word/PPT 페이지가 제한되고 XLSX는 검사할 수 없습니다. DOCX/PPTX의 지원 XML 텍스트 읽기는 페이지 변환과 별개입니다.

## 기대 경로

프로젝트 루트 기준이며 `.runtime/`은 Git에서 제외됩니다.

```text
.runtime/file-tools/
  tessdata/eng.traineddata
  tessdata/kor.traineddata
  hwplib-1.1.11.jar
  libreoffice/program/soffice.com
  jre/bin/java.exe                 # 설치판 내장 JRE가 있는 경우
```

Java는 내장 JRE, `C:/Program Files/Java/jdk*/bin/java.exe`, PATH 순서로 찾습니다. HWP는 읽기 전용이며 Java가 준비되어도 수정 저장은 제공하지 않습니다.

## Windows에서 준비하기

먼저 루트 README의 소스 설치를 실행합니다. OCR·hwplib 재준비는 다음 명령을 사용합니다. 내려받기 주소와 고정 해시는 `prepare_file_tools.py`의 `DOWNLOADS`가 기준입니다.

```powershell
.venv/Scripts/python.exe -X utf8 scripts/prepare/prepare_file_tools.py
java -version
```

Java는 [Eclipse Temurin](https://adoptium.net/), LibreOffice는 [공식 배포처](https://www.libreoffice.org/download/)에서 설치할 수 있습니다. 설치판의 고정 버전·파일 해시는 `installer/components.json`에 있습니다. 이번 정리는 새 버전 호환성이나 새 PC 설치 완료를 검증한 것이 아닙니다.

LibreOffice를 기본 위치에 설치했다면 기대 경로에 폴더 연결을 만듭니다. **대상 경로가 아직 없을 때만** 실행하세요. 기존 폴더나 연결을 지우지 않습니다.

```powershell
New-Item -ItemType Directory -Force .runtime/file-tools | Out-Null
if (-not (Test-Path -LiteralPath .runtime/file-tools/libreoffice)) {
    New-Item -ItemType Junction -Path .runtime/file-tools/libreoffice -Target 'C:/Program Files/LibreOffice'
}
```

다른 위치에 설치했다면 Target을 조정하세요. 준비 후 가상 DOCX·PPTX·XLSX·HWP·이미지를 각각 열어 실제 페이지·표·본문·OCR을 확인합니다. 파일 존재 확인과 실제 처리 성공은 구별합니다.

## Linux 보조 스크립트

`setup.sh`는 시스템 도구를 연결하는 별도 경로입니다. Windows의 soffice.com 기반 페이지 변환과 모든 파일 기능을 같은 조건으로 검증하지 않았습니다. Linux 전체 지원이나 동일 OCR 결과를 보장하지 않습니다.
