$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
$env:PIP_CACHE_DIR = Join-Path $PSScriptRoot '.runtime\pip-cache'
$env:TEMP = Join-Path $PSScriptRoot '.runtime\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) { throw 'Python 3.10 or later is required. Install Python, then retry.' }
    & $PythonCommand.Source -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10 or later required'"
    if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
    & $PythonCommand.Source -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
}
& $PythonExe -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Installation failed. Check network access and retry install.cmd.' }
& $PythonExe -c "import openpyxl, defusedxml; print('Dependencies ready. openpyxl', openpyxl.__version__)"
if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }
Write-Host 'Ready. Double-click start.cmd to open the local tool.'
