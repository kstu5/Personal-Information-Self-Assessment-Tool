# Windows 설치판

일반 사용자는 **완성된 설치 파일을 다운로드해 실행**합니다. 제작 작업은 개발자가 수행하고 검증한 EXE를 GitHub Releases에 배포합니다.

## 다운로드·사용

**[Windows x64 설치 파일 v0.1.0](https://github.com/kstu5/Personal-Information-Self-Assessment-Tool/releases/download/v0.1.0/PrivacySelfAssessmentTool-Setup-0.1.0.exe)** · [최신 Release](https://github.com/kstu5/Personal-Information-Self-Assessment-Tool/releases/latest)

1. EXE를 실행합니다. 이전 버전을 사용 중이면 먼저 작업을 저장하고 종료합니다.
2. 인터넷에 연결한 상태로 설치 완료까지 기다립니다.
3. 시작 메뉴의 **개인정보 자가진단 도구**로 실행합니다.

Python·Node.js·JDK를 직접 준비하거나 명령을 실행할 필요가 없습니다. 약 2.1MB의 EXE가 실행 환경·라이브러리·모델·OCR·Java·LibreOffice·필요한 WebView2를 설치 중 준비합니다. 완전 오프라인 설치판이 아니며 실제 설치 용량은 다운로드 파일보다 큽니다. 설치 이후 검사는 PC 안에서 수행합니다.

Release에는 EXE, `SHA256SUMS.txt`, `INSTALLATION-CHECK.json`을 함께 올립니다. SHA256SUMS는 파일의 무결성 확인용이며 코드 서명을 대체하지 않습니다. 이 설치 파일은 코드 서명되지 않았습니다. Source code ZIP/TAR는 개발용 소스입니다.

실패하면 설치 폴더의 `install.log`에서 마지막 실패 단계를 확인하세요. 로그를 공유하기 전 사용자 이름·개인 경로 등 불필요한 정보를 지우세요. 기본 설치 위치는 기존 버전 호환성을 위해 `%LOCALAPPDATA%/Programs/BeforePost`를 유지합니다. 제거 시 설치 관리 파일과 실행 환경을 정리하되 사용자가 따로 저장한 파일까지 폴더 전체를 지우지는 않습니다.

## 개발자: 설치판 제작

이하 과정은 배포 담당자용이며 일반 사용자는 수행하지 않습니다.

Windows 제작 PC에 Node.js/npm, JDK 11 이상, Inno Setup 6가 필요합니다. 먼저 소스 설치 또는 개발 환경으로 화면을 빌드하고 `scripts/prepare/prepare_file_tools.py`로 검증된 hwplib JAR을 준비합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build_installer.ps1
```

이미 검사한 화면 빌드가 있으면 `-SkipFrontend`를 사용합니다. 결과는 다음과 같으며 모두 Git에서 제외됩니다.

- `installer/stage/`: 명시적으로 고른 실행 파일·소스·라이선스 고지
- `installer/out/PrivacySelfAssessmentTool-Setup-<버전>.exe`: 설치 EXE
- `installer/out/SHA256SUMS.txt`: EXE의 SHA-256

개인 문서·연구 자료·상세 시험 결과를 설치판에 넣지 않습니다. 내려받는 도구의 버전·해시는 `components.json`, Python 패키지는 루트 lock 파일, 모델은 `models/model-a.json`이 기준입니다. 실행 중 라이브러리를 내려받는 기능과 개인정보 검사 중 외부 전송을 구별하세요.

## 개발자: 검증 후 직접 배포

1. 현재 소스의 정규 시험·화면 빌드와 공개 자료 점검을 수행합니다.
2. 제작한 EXE를 별도 시험 위치에서 설치하고 설치된 Python으로 게시글·예시 12종·수정 사본을 확인합니다.
3. 아래 도구로 설치된 환경만 사용하는지 확인하고 검사 요약을 생성합니다.
4. 배포 소스를 커밋·업로드하고 같은 커밋에 버전 태그를 만듭니다. README의 다운로드 버전도 맞춥니다.
5. GitHub Releases에서 해당 태그의 새 Release를 만들고 EXE·해시·검사 요약을 첨부합니다. [배포 설명](RELEASE_NOTES.md)을 검토하고 직접 공개합니다.
6. 공개 다운로드 URL·크기·해시와 최신 Release 링크를 확인합니다.

```powershell
python scripts/check/check_installed.py --app-dir '<설치 폴더>' --examples examples/formats/files --report installer/out/INSTALLATION-CHECK.json
```

기존 설치를 바꾸지 않고 같은 EXE를 검증할 때는 **비어 있는 별도 시험 폴더**를 지정하고 `/VerifyInstall=1 /NOICONS`를 사용합니다. 검증 모드는 설치 등록·제거 프로그램·바로가기·설치 직후 실행을 만들지 않으며, 실행 환경을 준비하는 여섯 단계는 일반 설치와 같습니다. 시험 폴더의 데이터는 로컬 전용 위치에 둡니다. 일반 사용자는 이 옵션을 사용할 필요가 없습니다.

자동 공개 워크플로는 추가하지 않습니다. 설치 EXE를 Git에 커밋하지 않고 Releases 첨부 파일로 관리합니다. `AppId`와 기존 설치 경로는 업그레이드 인식을 위해 유지합니다. 별도 폴더의 설치 검증은 모든 Windows 구성·보안 정책·설치판 업그레이드의 호환성을 보장하지 않습니다.
