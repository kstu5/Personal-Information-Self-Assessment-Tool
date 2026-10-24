#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef StageDir
  #define StageDir "stage"
#endif

[Setup]
AppId={{6F0B2C7E-3A5D-4E88-9B44-0D1C5E7A9F21}
AppName=게시 전 개인정보 검토
AppVersion={#AppVersion}
AppPublisher=게시 전
DefaultDirName={localappdata}\Programs\BeforePost
DefaultGroupName=게시 전
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=out
OutputBaseFilename=BeforePost-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=게시 전 개인정보 검토
CloseApplications=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 바로가기 만들기"; Flags: unchecked

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\게시 전 개인정보 검토"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\run.py"""; WorkingDir: "{app}"
Name: "{autodesktop}\게시 전 개인정보 검토"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\run.py"""; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\.runtime"
Type: files; Name: "{app}\install.log"
Type: filesandordirs; Name: "{app}"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\run.py"""; WorkingDir: "{app}"; Description: "지금 실행하기"; Flags: nowait postinstall skipifsilent

[Code]
const
  StepCount = 6;

var
  StepNames: array[0..5] of String;
  StepLabels: array[0..5] of String;

procedure InitSteps();
begin
  StepNames[0] := 'python';      StepLabels[0] := '실행 환경(Python)을 준비하는 중...';
  StepNames[1] := 'packages';    StepLabels[1] := '프로그램 구성요소를 내려받는 중 (수 분 걸릴 수 있습니다)...';
  StepNames[2] := 'tools';       StepLabels[2] := '탐지 모델과 OCR 데이터를 내려받는 중...';
  StepNames[3] := 'jre';         StepLabels[3] := 'HWP 읽기 도구(Java)를 준비하는 중...';
  StepNames[4] := 'libreoffice'; StepLabels[4] := 'XLSX 확인 도구(LibreOffice)를 준비하는 중...';
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
      MsgBox('설치 중 문제가 생겼습니다: ' + StepLabels[I] + #13#10#13#10 +
        '인터넷 연결을 확인한 뒤 설치 프로그램을 다시 실행해 주세요.' + #13#10 +
        '문제가 계속되면 아래 파일을 개발자에게 보내 주세요.' + #13#10 +
        ExpandConstant('{app}\install.log'), mbError, MB_OK);
      RaiseException('install step failed: ' + StepNames[I]);
    end;
  end;
  WizardForm.ProgressGauge.Position := StepCount;
end;
