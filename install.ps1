[CmdletBinding()]
param(
    [string]$InstallDir = (Get-Location).Path,
    [string]$RepoUrl = 'https://github.com/kser93/pylingual-portable-mcp.git',
    [string]$GitPath = '',
    [switch]$SkipModels,
    [switch]$SkipToolchains,
    [switch]$SkipMcpProbe,
    [switch]$CheckOnly,
    [switch]$DryRun,
    [switch]$SourceOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$LASTEXITCODE = 0

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    OK: $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    WARN: $Message" -ForegroundColor Yellow
}

function Assert-ExitCode {
    param([string]$What)
    if ($LASTEXITCODE -ne 0) {
        throw "$What failed with exit code $LASTEXITCODE."
    }
}

function Resolve-Command {
    param(
        [string]$Name,
        [string[]]$Fallbacks = @()
    )
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }
    foreach ($candidate in $Fallbacks) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "Required command not found: $Name"
}

function Resolve-Git {
    if ($GitPath) {
        if (-not (Test-Path -LiteralPath $GitPath)) {
            throw "Git executable not found: $GitPath"
        }
        return (Resolve-Path -LiteralPath $GitPath).Path
    }
    return Resolve-Command 'git' @(
        'C:\Program Files\Git\cmd\git.exe',
        'C:\Program Files (x86)\Git\cmd\git.exe'
    )
}

function Test-Repository {
    param([string]$Root)
    return (Test-Path -LiteralPath (Join-Path $Root 'pylingual.cmd')) -and
        (Test-Path -LiteralPath (Join-Path $Root 'src\pylingual_portable'))
}

function Get-ToolchainCount {
    param([string]$Root)
    return @(Get-ChildItem -LiteralPath (Join-Path $Root 'toolchains') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'python.exe') }).Count
}

function Get-InstalledModelCount {
    param([string]$Root)
    $manifest = Join-Path $Root 'models\installed.json'
    if (-not (Test-Path -LiteralPath $manifest)) {
        return 0
    }
    try {
        $data = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
        if ($null -eq $data.installed) {
            return 0
        }
        return @($data.installed.PSObject.Properties).Count
    }
    catch {
        return 0
    }
}

function Write-OpenCodeConfig {
    param([string]$Root)

    $configPath = Join-Path $Root '.opencode\opencode.jsonc'
    $config = [ordered]@{
        '$schema' = 'https://opencode.ai/config.json'
        mcp = [ordered]@{
            timeout = [ordered]@{
                startup = 60000
                catalog = 60000
                execution = 1800000
            }
            servers = [ordered]@{
                pylingual = [ordered]@{
                    type = 'local'
                    command = @('cmd.exe', '/c', (Join-Path $Root 'pylingual.cmd'), 'mcp', '--stdio')
                    cwd = $Root
                    codemode = $false
                    protocol = 'legacy'
                    timeout = [ordered]@{
                        startup = 60000
                        catalog = 60000
                        execution = 1800000
                    }
                }
            }
        }
    }

    Write-Host ''
    Write-Host 'OpenCode MCP configuration (project-local):' -ForegroundColor Cyan
    Write-Host "  File: $configPath"
    Write-Host ''
    Write-Host ($config | ConvertTo-Json -Depth 12)
    Write-Host ''
    Write-Host 'Merge the mcp.servers.pylingual section into that file if it already exists.'
    Write-Host 'Do not add this server to the global OpenCode configuration.'
}

$root = [IO.Path]::GetFullPath($InstallDir)
if ($SourceOnly -and $CheckOnly) {
    throw 'Use either -SourceOnly or -CheckOnly, not both.'
}
if (-not (Test-Path -LiteralPath $root)) {
    if ($DryRun) {
        Write-Step "Would create $root"
    }
    else {
        New-Item -ItemType Directory -Force -Path $root | Out-Null
    }
}

Write-Step 'Checking prerequisites'
Write-Ok 'PowerShell is available'

$isRepo = Test-Repository -Root $root
if (-not $isRepo) {
    $existing = @(Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) {
        throw "Target directory is not empty and is not a PyLingual checkout: $root"
    }
    if ($DryRun) {
        Write-Step "Would clone $RepoUrl into $root"
        Write-Host '    Run without -DryRun to install.'
        exit 0
    }
    $gitExe = Resolve-Git
    Write-Step "Cloning $RepoUrl"
    & $gitExe clone --recurse-submodules $RepoUrl $root
    Assert-ExitCode 'git clone'
    $isRepo = Test-Repository -Root $root
}

if (-not $isRepo) {
    throw "PyLingual checkout not found under $root"
}

$launcher = Join-Path $root 'pylingual.cmd'
$pythonCmd = Join-Path $root 'scripts\python.cmd'
$runtime = Join-Path $root 'runtime\python-3.15.1\python.exe'
$probe = Join-Path $root 'scripts\probe_mcp.py'

if (-not (Test-Path -LiteralPath (Join-Path $root 'vendor\pylingual\pylingual\__init__.py'))) {
    if (Test-Path -LiteralPath (Join-Path $root '.git')) {
        $gitExe = Resolve-Git
        Write-Step 'Initializing upstream submodules'
        & $gitExe -C $root submodule update --init --recursive
        Assert-ExitCode 'git submodule update'
    }
    else {
        throw 'Upstream submodules are missing; clone the repository with --recurse-submodules.'
    }
}

if ($SourceOnly) {
    Write-Step 'Source checkout complete'
    Write-Ok "PyLingual source is ready under $root"
    exit 0
}

if ($CheckOnly) {
    Write-Step 'Checking the existing installation'
    $problems = @()
    if (-not (Test-Path -LiteralPath $runtime)) {
        $problems += "Python runtime not found: $runtime"
    }
    if (-not $SkipToolchains -and (Get-ToolchainCount -Root $root) -lt 10) {
        $problems += 'Expected 10 CPython toolchains; run install.ps1 without -CheckOnly.'
    }
    if (-not $SkipModels -and (Get-InstalledModelCount -Root $root) -lt 10) {
        $problems += 'Expected 10 model packs; run install.ps1 without -CheckOnly or use -SkipModels.'
    }
    if ($problems.Count -gt 0) {
        foreach ($problem in $problems) { Write-Warn $problem }
        exit 1
    }
    Write-Ok 'runtime, toolchains and model manifests are present'
    Write-Step 'Running pylingual doctor'
    & $launcher doctor
    Assert-ExitCode 'pylingual doctor'
    Write-Ok 'doctor completed'
    if (-not $SkipMcpProbe) {
        Write-Step 'Probing the MCP server'
        & $pythonCmd $probe
        Assert-ExitCode 'MCP probe'
        Write-Ok 'MCP server exposes tools, resources, prompts and agent manifest'
    }
    Write-OpenCodeConfig -Root $root
    exit 0
}

if ($DryRun) {
    Write-Step 'Dry run: no files will be downloaded or changed'
    if (-not (Test-Path -LiteralPath $runtime)) {
        Write-Host '  Would download and unpack Python 3.15.1 into runtime\python-3.15.1'
    }
    else {
        Write-Host '  Python runtime already present'
    }
    if (-not $SkipToolchains) {
        Write-Host '  Would install CPython 3.6-3.15 toolchains'
    }
    if (-not $SkipModels) {
        Write-Host '  Would download the ten model packs from Hugging Face'
    }
    if (-not $SkipMcpProbe) {
        Write-Host '  Would start the MCP server and verify tools/resources/prompts'
    }
    Write-OpenCodeConfig -Root $root
    exit 0
}

if (-not (Test-Path -LiteralPath $runtime)) {
    Write-Step 'Installing Python 3.15.1 runtime'
    $tarExe = Resolve-Command 'tar' @('C:\Windows\System32\tar.exe')
    $release = '20261021'
    $downloads = Join-Path $root 'downloads'
    $runtimeDir = Join-Path $root 'runtime'
    New-Item -ItemType Directory -Force -Path $downloads, $runtimeDir | Out-Null
    $archive = Join-Path $downloads 'cpython-3.15.1+20261021-win-x64-install_only_stripped.tar.gz'
    $url = "https://github.com/astral-sh/python-build-standalone/releases/download/$release/cpython-3.15.1%2B$release-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host "    Downloading $url"
        Invoke-WebRequest -Uri $url -OutFile $archive
    }
    & $tarExe -xzf $archive -C $runtimeDir
    Assert-ExitCode 'tar extraction'
    $extracted = Join-Path $runtimeDir 'python'
    $target = Join-Path $runtimeDir 'python-3.15.1'
    if (Test-Path -LiteralPath $extracted) {
        if (Test-Path -LiteralPath $target) {
            throw "Both $extracted and $target exist; remove the incomplete runtime and retry."
        }
        Move-Item -LiteralPath $extracted -Destination $target
    }
    if (-not (Test-Path -LiteralPath $runtime)) {
        throw "Python runtime was not installed at $runtime"
    }
    Write-Ok 'Python 3.15.1 installed'
}

Write-Step 'Installing runtime dependencies'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\install_runtime.ps1')
Assert-ExitCode 'runtime dependency installation'
Write-Ok 'runtime dependencies installed'

if (-not $SkipToolchains) {
    Write-Step 'Installing target CPython toolchains'
    $tarExe = Resolve-Command 'tar' @('C:\Windows\System32\tar.exe')
    $env:PATH = "$(Split-Path -Parent $tarExe);$env:PATH"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\fetch_all_toolchains.ps1')
    Assert-ExitCode 'toolchain installation'
    Write-Ok "$(Get-ToolchainCount -Root $root) toolchains available"
}
else {
    Write-Warn 'Toolchain installation skipped'
}

if (-not $SkipModels) {
    Write-Step 'Downloading model packs from Hugging Face'
    Write-Host '    This downloads about 12 GB and can take a long time.'
    & $pythonCmd (Join-Path $root 'scripts\fetch_models.py') --versions all
    Assert-ExitCode 'model download'
    Write-Ok "$(Get-InstalledModelCount -Root $root) model packs recorded"
}
else {
    Write-Warn 'Model download skipped'
}

Write-Step 'Running pylingual doctor'
& $launcher doctor
Assert-ExitCode 'pylingual doctor'
Write-Ok 'doctor completed'

if (-not $SkipMcpProbe) {
    Write-Step 'Starting and probing the MCP server'
    & $pythonCmd $probe
    Assert-ExitCode 'MCP probe'
    Write-Ok 'MCP server is healthy'
}
else {
    Write-Warn 'MCP probe skipped'
}

Write-OpenCodeConfig -Root $root
Write-Host ''
Write-Host 'Installation complete.' -ForegroundColor Green
Write-Host "Project root: $root"
Write-Host 'The MCP stdio server is launched by the agent on demand; the probe above verified it.'
