param([switch]$Vision)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
}
$basketPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$basketExtras = if ($Vision) { '.[vision,test]' } else { '.[test]' }
& $basketPython -m pip install -e $basketExtras
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if ($Vision) {
    & $basketPython -m basket.cli setup-models
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed' }
}
& $basketPython -m basket.cli demo
if ($LASTEXITCODE -ne 0) { throw 'Demo generation failed' }
