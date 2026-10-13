$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location) '.python'
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
& uv python install 3.11 --no-bin --no-registry
if ($LASTEXITCODE) { throw 'Python installation failed' }
& uv venv backend/.venv --python 3.11
if ($LASTEXITCODE) { throw 'Virtualenv creation failed' }
& uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements.lock.txt
if ($LASTEXITCODE) { throw 'Backend dependencies failed' }
foreach ($component in @('backend', 'frontend')) {
    if (-not (Test-Path "$component/.env")) { Copy-Item "$component/.env.example" "$component/.env" }
}
Set-Location frontend
& npm.cmd ci
if ($LASTEXITCODE) { throw 'Frontend dependencies failed' }
