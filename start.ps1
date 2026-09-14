param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$basketPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $basketPython)) { throw 'Run .\setup.ps1 first.' }
& $basketPython -m basket.cli serve --port $Port
