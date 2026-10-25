$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
try {
    # Use venv python directly
    $venvPath = Join-Path $taskRoot '.venv'
    if (-not (Test-Path -LiteralPath $venvPath)) { throw 'Virtual environment not found. Run setup.ps1 first.' }

    $taskPython = Join-Path $venvPath 'Scripts\python.exe'
    $taskWindowPython = Join-Path $venvPath 'Scripts\pythonw.exe'
    if (Test-Path -LiteralPath $taskWindowPython) { $taskPython = $taskWindowPython }
    if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Python runtime was not found in .venv. Follow README.md setup instructions.' }

    $taskEntry = Join-Path $taskRoot 'run.py'
    # This is the visible app itself; only the launcher PowerShell stays hidden.
    Start-Process -FilePath $taskPython -ArgumentList @('-X', 'utf8', ('"' + $taskEntry + '"')) -WorkingDirectory $taskRoot -WindowStyle Normal
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('실행 환경을 찾을 수 없습니다. 프로젝트의 README.md에서 설치 안내를 확인해 주세요.', '개인정보 자가진단 도구') | Out-Null
}
