$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root 'runtime\python-3.15.1\python.exe'

if (-not (Test-Path $Python)) {
    throw "Portable Python not found: $Python"
}

$env:PYTHONNOUSERSITE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:HF_HOME = (Join-Path $Root 'models\hf-cache')
$env:HF_HUB_CACHE = (Join-Path $Root 'models\hf-cache\hub')
$env:HF_HUB_DISABLE_SYMLINKS = '1'
$env:PIP_CACHE_DIR = (Join-Path $Root 'downloads\pip-cache')
$env:TMP = (Join-Path $Root 'workspace\tmp')
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:HF_HOME, $env:PIP_CACHE_DIR, $env:TMP | Out-Null

Write-Host 'Installing torch 2.14.1+cu130 from the PyTorch cu130 index...'
& $Python -m pip install --no-cache-dir `
    --index-url https://download.pytorch.org/whl/cu130 `
    --extra-index-url https://pypi.org/simple `
    'torch==2.14.1+cu130'
if ($LASTEXITCODE -ne 0) { throw 'torch installation failed' }

Write-Host 'Installing PyYAML without the optional C extension (no MSVC required)...'
$env:PYYAML_FORCE_LIBYAML = '0'
$env:PYYAML_FORCE_CYTHON = '0'
& $Python -m pip install --no-cache-dir --no-build-isolation 'pyyaml==6.0.3'
if ($LASTEXITCODE -ne 0) { throw 'PyYAML installation failed' }

Write-Host 'Installing pinned runtime dependencies...'
& $Python -m pip install --no-cache-dir -r (Join-Path $PSScriptRoot 'requirements-runtime.txt')
if ($LASTEXITCODE -ne 0) { throw 'runtime dependency installation failed' }

Write-Host 'Installing xdis from the pinned upstream commit...'
# Pin: xdis 6.3.1.dev0 @ 51e36c42a01a83d67f6530fdf7fbd42a0f387d86
# See vendor/components.json and vendor/UPSTREAM.md.
& $Python -m pip install --no-cache-dir --no-deps (Join-Path $Root 'vendor\xdis-src')
if ($LASTEXITCODE -ne 0) { throw 'xdis installation failed' }

Write-Host 'Installing xdis runtime dependencies...'
& $Python -m pip install --no-cache-dir click six
if ($LASTEXITCODE -ne 0) { throw 'xdis dependency installation failed' }

Write-Host 'Creating minimal PyLingual metadata (source is loaded from vendor via PYTHONPATH)...'
# Do not pip-install the upstream package: it declares training-only dependencies
# (datasets, matplotlib, evaluate, seqeval, tensorboardx) that the runtime does not need.
$SitePackages = Join-Path $Root 'runtime\python-3.15.1\Lib\site-packages'
$DistInfo = Join-Path $SitePackages 'pylingual-0.1.0.dist-info'
foreach ($path in @((Join-Path $SitePackages 'pylingual'), $DistInfo)) {
    if (Test-Path $path) { Remove-Item $path -Recurse -Force }
}
New-Item -ItemType Directory -Force -Path $DistInfo | Out-Null
@(
    'Metadata-Version: 2.1',
    'Name: pylingual',
    'Version: 0.1.0',
    'Summary: Local PyLingual source loaded from vendor via PYTHONPATH'
) | Set-Content (Join-Path $DistInfo 'METADATA') -Encoding utf8
'Installer: local-portable' | Set-Content (Join-Path $DistInfo 'INSTALLER') -Encoding utf8

Write-Host 'Runtime installation complete.'
Write-Host "Python: $Python"
