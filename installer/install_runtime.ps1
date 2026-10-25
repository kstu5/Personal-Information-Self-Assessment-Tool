param(
    [Parameter(Mandatory)][ValidateSet('python', 'packages', 'tools', 'jre', 'libreoffice', 'webview2')][string]$Step,
    [Parameter(Mandatory)][string]$AppDir,
    [string]$Components
)
$ErrorActionPreference = 'Stop'
if (-not $Components) { $Components = Join-Path $PSScriptRoot 'components.json' }
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$AppDir = (Resolve-Path -LiteralPath $AppDir).Path
$log = Join-Path $AppDir 'install.log'
$c = Get-Content -LiteralPath $Components -Raw -Encoding UTF8 | ConvertFrom-Json
$py = Join-Path $AppDir 'python\python.exe'
$tools = Join-Path $AppDir '.runtime\file-tools'
$cache = Join-Path $AppDir '.runtime\download-cache'

function Log($m) { Add-Content -LiteralPath $log -Value ('[{0}] [{1}] {2}' -f (Get-Date -Format 'HH:mm:ss'), $Step, $m) -Encoding UTF8 }

function Assert-AppChild([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $boundary = [IO.Path]::GetFullPath($AppDir).TrimEnd('\') + '\'
    if (-not $full.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime path must stay inside the application directory.' }
    $cursor = $full
    while ($cursor -and $cursor.Length -gt $boundary.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Runtime path must not cross a junction or symbolic link: $cursor"
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}

function Remove-AppDirectory([string]$Path) {
    $full = Assert-AppChild $Path
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
}

function Get-Verified($item, $name) {
    New-Item -ItemType Directory -Force $cache | Out-Null
    $dest = Join-Path $cache $name
    if ((Test-Path -LiteralPath $dest) -and ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -eq $item.sha256)) { return $dest }
    for ($try = 1; $try -le 3; $try++) {
        try {
            Log "download $($item.url) (try $try)"
            Invoke-WebRequest -Uri $item.url -OutFile $dest -UseBasicParsing -TimeoutSec 180
            $actual = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
            if ($actual -ne $item.sha256) { throw "체크섬이 다릅니다 ($name): 기대 $($item.sha256), 실제 $actual" }
            return $dest
        } catch {
            Log "failed: $_"
            Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
            if ($try -eq 3) { throw "$name 다운로드에 실패했습니다. 인터넷 연결을 확인하고 다시 시도해 주세요. ($_)" }
            Start-Sleep -Seconds (3 * $try)
        }
    }
}

function Invoke-Py([string[]]$ArgList) {
    Log "python $($ArgList -join ' ')"
    # PowerShell 5.1은 Stop 상태에서 네이티브 명령의 stderr를 예외로 바꾸므로 이 호출만 Continue로 받는다.
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $out = & $py -X utf8 @ArgList 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    $out | ForEach-Object { Add-Content -LiteralPath $log -Value $_ -Encoding UTF8 }
    if ($code -ne 0) { throw "설치 단계가 실패했습니다 (python $($ArgList[0..1] -join ' '), 종료 코드 $code). 자세한 내용은 $log 를 확인해 주세요." }
}

try {
    switch ($Step) {
        'python' {
            $zip = Get-Verified $c.python 'python-embed.zip'
            $dir = Join-Path $AppDir 'python'
            Remove-AppDirectory $dir
            Expand-Archive -LiteralPath $zip -DestinationPath $dir -Force
            # 임베디드 Python은 ._pth가 있으면 환경변수·현재 폴더를 무시하므로 필요한 경로를 직접 적는다.
            $pth = Get-ChildItem -LiteralPath $dir -Filter 'python*._pth' | Select-Object -First 1
            $zipName = [IO.Path]::GetFileNameWithoutExtension($pth.Name).Replace('._pth', '')
            Set-Content -LiteralPath $pth.FullName -Encoding ASCII -Value @("$zipName.zip", '.', 'Lib\site-packages', '..', 'import site')
            New-Item -ItemType Directory -Force (Join-Path $dir 'Lib\site-packages') | Out-Null
            $whl = Get-Verified $c.pip ([IO.Path]::GetFileName($c.pip.url))
            # 휠은 zip 파일이므로 site-packages에 직접 풀면 pip 자신을 pip로 설치할 때 나는 오류를 피할 수 있다.
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [IO.Compression.ZipFile]::ExtractToDirectory($whl, (Join-Path $dir 'Lib\site-packages'))
            Invoke-Py @('-m', 'pip', '--version')
        }
        'packages' {
            $req = { param($f) Join-Path $AppDir $f }
            # 임베디드 Python은 ._pth 때문에 PYTHONPATH를 무시해 pip의 격리 빌드가 실패한다.
            # 소스로만 배포되는 패키지(proxy_tools 등)를 위해 setuptools를 먼저 넣고 격리 빌드를 끈다.
            $opts = @('--no-warn-script-location', '--disable-pip-version-check', '--no-cache-dir')
            Invoke-Py (@('-m', 'pip', 'install') + $opts + @('setuptools==78.1.0'))
            $opts += '--no-build-isolation'
            Invoke-Py (@('-m', 'pip', 'install') + $opts + @('-r', (& $req 'requirements.lock.txt')))
            Invoke-Py (@('-m', 'pip', 'install') + $opts + @('-r', (& $req 'requirements.files.lock.txt')))
            Invoke-Py (@('-m', 'pip', 'install') + $opts + @('--index-url', 'https://download.pytorch.org/whl/cpu', 'torch==2.9.1+cpu'))
            Invoke-Py (@('-m', 'pip', 'install') + $opts + @('-r', (& $req 'requirements.model-a.lock.txt')))
        }
        'tools' {
            Push-Location $AppDir
            try {
                Invoke-Py @('scripts\prepare\prepare_file_tools.py')
                Invoke-Py @('scripts\prepare\prepare_model_a.py')
            } finally { Pop-Location }
            foreach ($f in 'tessdata\eng.traineddata', 'tessdata\kor.traineddata', 'hwplib-1.1.11.jar') {
                if (-not (Test-Path -LiteralPath (Join-Path $tools $f))) { throw "필수 파일을 받지 못했습니다: $f" }
            }
        }
        'jre' {
            $zip = Get-Verified $c.jre 'jre.zip'
            $tmp = Join-Path $cache 'jre-extract'
            Remove-AppDirectory $tmp
            Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
            $root = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
            $dest = Join-Path $tools 'jre'
            Remove-AppDirectory $dest
            New-Item -ItemType Directory -Force $tools | Out-Null
            $jreSource = Assert-AppChild $root.FullName
            $jreTarget = Assert-AppChild $dest
            Move-Item -LiteralPath $jreSource -Destination $jreTarget
            Remove-AppDirectory $tmp
            if (-not (Test-Path -LiteralPath (Join-Path $dest 'bin\java.exe'))) { throw 'Java 실행 파일을 찾지 못했습니다.' }
        }
        'libreoffice' {
            $msi = Get-Verified $c.libreoffice 'libreoffice.msi'
            $dest = Join-Path $tools 'libreoffice'
            Remove-AppDirectory $dest
            New-Item -ItemType Directory -Force $tools | Out-Null
            # 관리 설치(/a)는 파일만 풀어 놓으며 레지스트리·시스템 폴더를 바꾸지 않는다.
            $p = Start-Process msiexec.exe -ArgumentList '/a', "`"$msi`"", '/qn', "TARGETDIR=`"$dest`"" -WindowStyle Hidden -Wait -PassThru
            if ($p.ExitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $dest 'program\soffice.com'))) {
                throw "LibreOffice를 풀지 못했습니다 (종료 코드 $($p.ExitCode))."
            }
        }
        'webview2' {
            $key = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
            $userKey = 'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
            if ((Test-Path $key) -or (Test-Path $userKey)) { Log 'WebView2 already installed'; break }
            New-Item -ItemType Directory -Force $cache | Out-Null
            $exe = Join-Path $cache 'MicrosoftEdgeWebview2Setup.exe'
            Invoke-WebRequest -Uri $c.webview2.url -OutFile $exe -UseBasicParsing -TimeoutSec 180
            $sig = Get-AuthenticodeSignature -LiteralPath $exe
            if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'WebView2 설치 파일의 서명을 확인하지 못했습니다.' }
            $p = Start-Process $exe -ArgumentList '/silent', '/install' -WindowStyle Hidden -Wait -PassThru
            if ($p.ExitCode -ne 0) { throw "WebView2 설치에 실패했습니다 (종료 코드 $($p.ExitCode))." }
        }
    }
    # 마지막 단계까지 성공했을 때만 내려받은 설치 파일을 지운다(중간에 실패하면 재시도에 재사용).
    if ($Step -eq 'webview2') { Remove-AppDirectory $cache }
    Log 'ok'
} catch {
    Log "ERROR: $_"
    Write-Error "$_"
    exit 1
}
