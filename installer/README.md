# Windows 설치 프로그램 제작

설치판 표시명은 **개인정보 자가진단 도구**입니다. 소스 실행 방법은 [루트 README](../README.md)를 확인하세요. 이 폴더는 설치 소스이며 완성 설치 EXE를 Git에 포함하지 않습니다.

## 제작

Windows 빌드 PC에 Node.js/npm, JDK 11 이상과 Inno Setup 6가 필요합니다. 먼저 앱을 준비해 `dist/`와 `.runtime/file-tools/hwplib-1.1.11.jar`를 생성합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build_installer.ps1
```

이미 검증한 화면 빌드가 있으면 `-SkipFrontend`를 사용할 수 있습니다. 임시 구성은 `installer/stage/`, 결과는 `installer/out/PrivacySelfAssessmentTool-Setup-<버전>.exe`에 생성되며 둘 다 Git에서 제외됩니다.

설치에 포함할 소스는 빌드 스크립트가 명시적으로 복사합니다. 실행 환경·모델 가중치·Java·LibreOffice·WebView2는 설치 시 `install_runtime.ps1`과 `components.json`의 고정 버전·검증 정보를 사용해 준비합니다. 대상 PC에는 인터넷 연결과 충분한 설치 공간이 필요합니다. 구성 요소의 라이선스·고지와 새 PC 설치·실행 확인은 배포 전에 별도로 검토해야 합니다.

기존 설치를 인식하도록 AppId와 `{localappdata}/Programs/BeforePost` 경로를 유지합니다. 시작 메뉴·바탕화면·제거 목록의 표시 이름은 정식 명칭을 사용합니다. 이번 명칭·배치 정리만으로 새 PC 설치나 설치판 업그레이드가 끝까지 검증됐다는 뜻은 아닙니다.
