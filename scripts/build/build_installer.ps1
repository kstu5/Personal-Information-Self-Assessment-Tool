param([switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $root
try {
    $version = (Get-Content -LiteralPath package.json -Raw -Encoding UTF8 | ConvertFrom-Json).version
    if (-not $version) { $version = '0.0.0' }

    if (-not $SkipFrontend) {
        & npx --yes pnpm@12.15.0 install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        & npx --yes pnpm@12.15.0 run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
    if (-not (Test-Path -LiteralPath 'dist\index.html')) { throw 'dist/index.html not found. Build the frontend first.' }

    $jar = '.runtime\file-tools\hwplib-1.1.11.jar'
    if (-not (Test-Path -LiteralPath $jar)) { throw "hwplib jar not found ($jar). Run scripts/prepare/prepare_file_tools.py first." }
    if (-not (Get-Command javac -ErrorAction SilentlyContinue)) { throw 'javac (JDK 11+) is required on the build PC to precompile HwpText.java.' }

    $stage = Join-Path $root 'installer\stage'
    $stage = [IO.Path]::GetFullPath($stage)
    $expectedStage = [IO.Path]::GetFullPath((Join-Path $root 'installer\stage'))
    if ($stage -ne $expectedStage -or -not $stage.StartsWith([IO.Path]::GetFullPath($root) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Installer stage must stay inside the project installer directory.'
    }
    if ((Test-Path -LiteralPath $stage) -and ((Get-Item -LiteralPath $stage).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Installer stage must not be a junction or symbolic link.'
    }
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    New-Item -ItemType Directory -Force $stage | Out-Null

    # 설치판에 들어가는 파일만 명시적으로 복사한다(.venv, .runtime, 연구 자료 등은 제외).
    Copy-Item run.py, requirements.lock.txt, requirements.files.lock.txt, requirements.model-a.lock.txt $stage
    if (Test-Path LICENSE) { Copy-Item LICENSE $stage }
    foreach ($d in 'dist', 'models') { Copy-Item -Recurse $d (Join-Path $stage $d) }
    New-Item -ItemType Directory -Force (Join-Path $stage 'backend'), (Join-Path $stage 'scripts\prepare'), (Join-Path $stage 'installer') | Out-Null
    Copy-Item backend\*.py, backend\HwpText.java (Join-Path $stage 'backend')
    Copy-Item scripts\prepare\prepare_file_tools.py, scripts\prepare\prepare_model_a.py (Join-Path $stage 'scripts\prepare')
    Copy-Item installer\install_runtime.ps1, installer\components.json (Join-Path $stage 'installer')
    Copy-Item installer\USER_GUIDE.txt (Join-Path $stage '사용안내.txt')
    $notices = @('Frontend components included in this installer: React and React DOM.', '')
    foreach ($package in 'react', 'react-dom', 'scheduler') {
        $licensePath = Join-Path $root "node_modules\$package\LICENSE"
        if (Test-Path -LiteralPath $licensePath) {
            $notices += "--- $package ---"
            $notices += Get-Content -LiteralPath $licensePath -Raw -Encoding UTF8
        } elseif ($package -ne 'scheduler') { throw "Required frontend license missing: $package" }
    }
    $notices | Set-Content -LiteralPath (Join-Path $stage 'THIRD-PARTY-NOTICES.txt') -Encoding UTF8

    & javac --release 11 -encoding UTF-8 -cp $jar -d (Join-Path $stage 'backend') backend\HwpText.java
    if ($LASTEXITCODE -ne 0) { throw 'HwpText.java compile failed.' }

    $iscc = @('.tools\inno\ISCC.exe', "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $iscc) { throw 'Inno Setup 6 (ISCC.exe) not found.' }
    & $iscc "/DAppVersion=$version" "/DStageDir=$stage" installer\setup.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compile failed.' }
    $artifact = Join-Path $root "installer\out\PrivacySelfAssessmentTool-Setup-$version.exe"
    if (-not (Test-Path -LiteralPath $artifact)) { throw 'Expected installer output is missing.' }
    $digest = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
    "$digest  $([IO.Path]::GetFileName($artifact))" | Set-Content -LiteralPath (Join-Path $root 'installer\out\SHA256SUMS.txt') -Encoding ASCII
    '{0}  {1:N1} MB' -f $artifact, ((Get-Item -LiteralPath $artifact).Length / 1MB)
} finally { Pop-Location }
