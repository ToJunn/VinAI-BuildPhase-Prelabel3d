$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location (Join-Path $projectRoot 'backend')
$pythonExe = Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (-not (Test-Path $pythonExe)) { throw 'Run scripts/setup.ps1 first.' }
& $pythonExe -c "from app.config import Settings; import uvicorn; s=Settings(); uvicorn.run('app.main:app', host=s.api_host, port=s.api_port)"
exit $LASTEXITCODE
