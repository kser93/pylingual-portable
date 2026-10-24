$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Downloads = Join-Path $Root 'downloads'
$Toolchains = Join-Path $Root 'toolchains'
$TempRoot = Join-Path $Root 'workspace\tmp\toolchain-extract'
New-Item -ItemType Directory -Force -Path $Downloads, $Toolchains, $TempRoot | Out-Null

$Pbs = @(
    @{ Version = '3.8.19';  Release = '20240726' },
    @{ Version = '3.9.20';  Release = '20241016' },
    @{ Version = '3.10.15'; Release = '20241016' },
    @{ Version = '3.11.17'; Release = '20261021' },
    @{ Version = '3.12.15'; Release = '20261021' },
    @{ Version = '3.13.17'; Release = '20261021' },
    @{ Version = '3.14.9';  Release = '20261021' },
    @{ Version = '3.15.1';  Release = '20261021' }
)

foreach ($item in $Pbs) {
    $version = $item.Version
    $release = $item.Release
    $target = Join-Path $Toolchains "cpython-$version-win-x64"
    if (Test-Path (Join-Path $target 'python.exe')) {
        Write-Host "Already installed: $version"
        continue
    }

    $archive = Join-Path $Downloads "cpython-$version+$release-win-x64-install_only_stripped.tar.gz"
    $url = "https://github.com/astral-sh/python-build-standalone/releases/download/$release/cpython-$version%2B$release-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
    if (-not (Test-Path $archive)) {
        Write-Host "Downloading Python $version..."
        Invoke-WebRequest -Uri $url -OutFile $archive
    }

    $temp = Join-Path $TempRoot $version
    if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $temp | Out-Null
    tar -xzf $archive -C $temp
    $extracted = Join-Path $temp 'python'
    if (-not (Test-Path $extracted)) { throw "Unexpected archive layout for $version" }
    Move-Item $extracted $target
    Remove-Item $temp -Recurse -Force
    Write-Host "Installed Python $version"
}

# Python 3.6/3.7 are EOL; use the official Windows embeddable distributions.
$Legacy = @(
    @{ Version = '3.6.8'; Url = 'https://www.python.org/ftp/python/3.6.8/python-3.6.8-embed-amd64.zip' },
    @{ Version = '3.7.9'; Url = 'https://www.python.org/ftp/python/3.7.9/python-3.7.9-embed-amd64.zip' }
)
foreach ($item in $Legacy) {
    $version = $item.Version
    $target = Join-Path $Toolchains "cpython-$version-win-x64"
    if (Test-Path (Join-Path $target 'python.exe')) {
        Write-Host "Already installed: $version"
        continue
    }
    $archive = Join-Path $Downloads "python-$version-embed-amd64.zip"
    if (-not (Test-Path $archive)) {
        Write-Host "Downloading Python $version (legacy embeddable)..."
        Invoke-WebRequest -Uri $item.Url -OutFile $archive
    }
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Expand-Archive -Path $archive -DestinationPath $target -Force
    Write-Host "Installed Python $version (legacy)"
}

Get-ChildItem $Toolchains -Directory | ForEach-Object {
    $python = Join-Path $_.FullName 'python.exe'
    if (-not (Test-Path $python)) { return }
    $version = (& $python -c "import sys; print('%d.%d' % sys.version_info[:2])") -join ''
    Write-Host "$($_.Name): Python $version"
}
