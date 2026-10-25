param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    # Enable corepack (ignore errors if no admin rights; corepack commands still work)
    try { corepack enable 2>$null } catch { }

    $taskPython = (& $Python -c 'import sys; print(sys.executable)').Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or later is required.' }

    # Create venv if it doesn't exist
    if (-not (Test-Path '.venv')) {
        Write-Output 'Creating virtual environment...'
        & $taskPython -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }

    # Use venv python
    $venvPython = Join-Path (Join-Path $taskRoot '.venv') 'Scripts\python.exe'

    # Install all Python dependencies in venv
    Write-Output 'Installing Python dependencies...'
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install --upgrade -r requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    & $venvPython -m pip install --upgrade -r requirements.files.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Document dependency installation failed.' }
    & $venvPython -m pip install --upgrade --index-url https://download.pytorch.org/whl/cpu 'torch==2.9.1+cpu'
    if ($LASTEXITCODE -ne 0) { throw 'CPU model runtime installation failed.' }
    & $venvPython -m pip install --upgrade -r requirements.model-a.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Model dependency installation failed.' }

    # Prepare external tools (not pip packages)
    Write-Output 'Preparing external tools...'
    & $venvPython scripts/prepare/prepare_file_tools.py
    if ($LASTEXITCODE -ne 0) { throw 'Document tool preparation failed.' }
    & $venvPython scripts/prepare/prepare_model_a.py
    if ($LASTEXITCODE -ne 0) { throw 'atonlee/koelectra-ko-pii-ner preparation failed.' }

    # Install and build frontend (using npx pnpm)
    Write-Output 'Installing frontend dependencies...'
    & npx --yes pnpm@12.15.0 install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npx --yes pnpm@12.15.0 run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }

    Write-Output 'Setup complete. Double-click the launcher in the project folder.'
} finally { Pop-Location }
