$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PythonRoot = Join-Path $Root 'runtime\python-3.15.1'
$Python = Join-Path $PythonRoot 'python.exe'

if (-not (Test-Path $Python)) {
    throw "Portable Python not found: $Python"
}

$env:PYLINGUAL_HOME = $Root
$env:PYTHONHOME = $PythonRoot
$env:PYTHONPATH = @((Join-Path $Root 'src'), (Join-Path $Root 'vendor\pylingual')) -join ';'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'

# Keep all caches and temporary files inside the project.
$env:HF_HOME = (Join-Path $Root 'models\hf-cache')
$env:HF_HUB_CACHE = (Join-Path $Root 'models\hf-cache\hub')
$env:HF_HUB_DISABLE_SYMLINKS = '1'
$env:PIP_CACHE_DIR = (Join-Path $Root 'downloads\pip-cache')
$env:TMP = (Join-Path $Root 'workspace\tmp')
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:HF_HOME, $env:PIP_CACHE_DIR, $env:TMP | Out-Null

# Process-local PATH only. No system/user environment variables are modified.
$env:PATH = @(
    $PythonRoot
    (Join-Path $PythonRoot 'Scripts')
    (Join-Path $PythonRoot 'Lib\site-packages\torch\lib')
    $env:PATH
) -join ';'

Write-Host "PYLINGUAL_HOME=$env:PYLINGUAL_HOME"
Write-Host "PYTHON=$Python"
