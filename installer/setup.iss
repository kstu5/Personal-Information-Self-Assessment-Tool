#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef StageDir
  #define StageDir "stage"
#endif

[Setup]
AppId={{6F0B2C7E-3A5D-4E88-9B44-0D1C5E7A9F21}
AppName=개인정보 자가진단 도구
AppVersion={#AppVersion}
AppPublisher=개인정보 자가진단 도구
AppSupportURL=https://github.com/kstu5/Personal-Information-Self-Assessment-Tool/issues
AppUpdatesURL=https://github.com/kstu5/Personal-Information-Self-Assessment-Tool/releases
DefaultDirName={localappdata}\Programs\BeforePost
DefaultGroupName=개인정보 자가진단 도구
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableDirPage=no
OutputDir=out
OutputBaseFilename=PrivacySelfAssessmentTool-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=개인정보 자가진단 도구
CloseApplications=no
SetupLogging=yes
Uninstallable=not IsVerificationInstall
CreateUninstallRegKey=not IsVerificationInstall

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 바로가기 만들기"; Flags: unchecked

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\개인정보 자가진단 도구"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\run.py"""; WorkingDir: "{app}"; Check: not IsVerificationInstall
Name: "{autoprograms}\개인정보 자가진단 도구 예시 문서"; Filename: "{app}\examples\formats\files"; Check: not IsVerificationInstall
Name: "{autodesktop}\개인정보 자가진단 도구"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\run.py"""; WorkingDir: "{app}"; Tasks: desktopicon; Check: not IsVerificationInstall

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\.runtime"
Type: files; Name: "{app}\install.log"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\run.py"""; WorkingDir: "{app}"; Description: "지금 실행하기"; Flags: nowait postinstall skipifsilent; Check: CanLaunchApp

[Code]
const
  StepCount = 6;
  MaxInstallPathLength = 100;

var
  StepNames: array[0..5] of String;
  StepLabels: array[0..5] of String;
  FailedStep: Integer;

// Test the same EXE in a separate directory without changing an existing install.
function IsVerificationInstall(): Boolean;
begin
  Result := ExpandConstant('{param:VerifyInstall|0}') = '1';
end;

function CanLaunchApp(): Boolean;
begin
  Result := (not IsVerificationInstall()) and (FailedStep = 0);
end;

function InstallPathError(): String;
begin
  Result := '';
  if Length(ExpandFileName(ExpandConstant('{app}'))) > MaxInstallPathLength then
    Result := '설치 경로가 너무 깁니다. 폴더 전체 경로를 100자 이하로 선택해 주세요.' + #13#10 +
      '기본 설치 위치 또는 더 짧은 경로를 사용하면 실행 구성요소의 설치 오류를 피할 수 있습니다.';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Error: String;
begin
  Result := True;
  if CurPageID <> wpSelectDir then Exit;
  Error := InstallPathError();
  if Error = '' then Exit;
  SuppressibleMsgBox(Error, mbError, MB_OK, IDOK);
  Result := False;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := InstallPathError();
end;

function GetCustomSetupExitCode(): Integer;
begin
  Result := FailedStep;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (FailedStep <> 0) and (PageID = wpFinished);
end;

procedure InitSteps();
begin
  StepNames[0] := 'python';      StepLabels[0] := '실행 환경(Python)을 준비하는 중...';
  StepNames[1] := 'packages';    StepLabels[1] := '프로그램 구성요소를 내려받는 중 (수 분 걸릴 수 있습니다)...';
  StepNames[2] := 'tools';       StepLabels[2] := '탐지 모델과 OCR 데이터를 내려받는 중...';
  StepNames[3] := 'jre';         StepLabels[3] := 'HWP 읽기 도구(Java)를 준비하는 중...';
  StepNames[4] := 'libreoffice'; StepLabels[4] := '문서 미리보기·XLSX 확인 도구(LibreOffice)를 준비하는 중...';
  StepNames[5] := 'webview2';    StepLabels[5] := '화면 구성요소(WebView2)를 확인하는 중...';
end;

function RunStep(Index: Integer): Boolean;
var
  Code: Integer;
  Params: String;
begin
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\installer\install_runtime.ps1') +
    '" -Step ' + StepNames[Index] + ' -AppDir "' + ExpandConstant('{app}') + '"';
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Params, '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  I: Integer;
begin
  if CurStep <> ssPostInstall then Exit;
  InitSteps();
  WizardForm.ProgressGauge.Min := 0;
  WizardForm.ProgressGauge.Max := StepCount;
  for I := 0 to StepCount - 1 do
  begin
    WizardForm.StatusLabel.Caption := StepLabels[I];
    WizardForm.ProgressGauge.Position := I;
    if not RunStep(I) then
    begin
      FailedStep := 10 + I;
      Log('Runtime preparation failed: ' + StepNames[I]);
      WizardForm.StatusLabel.Caption := '설치를 완료하지 못했습니다.';
      SuppressibleMsgBox('설치 중 문제가 생겼습니다: ' + StepLabels[I] + #13#10#13#10 +
        '인터넷 연결을 확인한 뒤 설치 프로그램을 다시 실행해 주세요.' + #13#10 +
        '문제가 계속되면 아래 파일을 개발자에게 보내 주세요.' + #13#10 +
        ExpandConstant('{app}\install.log'), mbError, MB_OK, IDOK);
      Exit;
    end;
  end;
  WizardForm.ProgressGauge.Position := StepCount;
end;
