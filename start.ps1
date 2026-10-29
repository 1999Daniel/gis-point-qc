param([switch]$NoBrowser, [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
$PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) {
    & (Join-Path $PSScriptRoot 'install.ps1')
}
& $PythonExe -c "import openpyxl, defusedxml" 2>$null
if ($LASTEXITCODE -ne 0) { & (Join-Path $PSScriptRoot 'install.ps1') }
$LaunchArgs = @((Join-Path $PSScriptRoot 'app.py'), '--port', "$Port")
if ($NoBrowser) { $LaunchArgs += '--no-browser' }
& $PythonExe @LaunchArgs
exit $LASTEXITCODE
