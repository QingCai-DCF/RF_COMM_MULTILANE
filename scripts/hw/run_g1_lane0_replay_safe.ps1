[CmdletBinding()]
param(
    [switch]$AllowHardware,
    [switch]$ExecuteHardware,
    [int]$MaxRuntimeSec = 0,
    [switch]$ShutdownOnExit,
    [string]$BoardId = "",
    [string]$Bitstream = "",
    [string]$TestProfile = "",
    [string]$ActivePinmapHash = "",
    [string]$ActiveXdcHash = "",
    [string]$ProfilePath = "config/profiles/G1_LANE0_BASELINE.json",
    [string]$EvidenceDir = "",
    [string]$InnerScript = "legacy/RF_COMM/tools/run_g1_lane0_hw_smoke_safe.ps1",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$XsctWaitSeconds = 45,
    [int]$PostStartSeconds = 35,
    [int]$CaptureSeconds = 75,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..\..")).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $EvidenceDir) {
    $EvidenceDir = Join-Path $repoRoot "evidence\generated\hw_preflight\run_g1_lane0_replay_safe_$stamp"
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
    $EvidenceDir = Join-Path $repoRoot $EvidenceDir
}
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$summaryLog = Join-Path $EvidenceDir "run_g1_lane0_replay_safe.summary.txt"
$manifestJson = Join-Path $EvidenceDir "hash_manifest.json"
$manifestCsv = Join-Path $EvidenceDir "hash_manifest.csv"
$innerStdoutLog = Join-Path $EvidenceDir "inner.stdout.log"
$innerStderrLog = Join-Path $EvidenceDir "inner.stderr.log"
$shutdownStdoutLog = Join-Path $EvidenceDir "shutdown.stdout.log"
$shutdownStderrLog = Join-Path $EvidenceDir "shutdown.stderr.log"

function Resolve-RepoPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $repoRoot $Path
}

function Get-FileSha256OrMissing {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    }
    return "MISSING"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Write-HashManifest {
    param([string[]]$Paths)
    $entries = @()
    foreach ($path in $Paths) {
        if (-not $path) {
            continue
        }
        $full = Resolve-RepoPath $path
        $exists = Test-Path -LiteralPath $full -PathType Leaf
        $entries += [ordered]@{
            path = $full
            exists = [bool]$exists
            sha256 = Get-FileSha256OrMissing -Path $full
        }
    }
    $profileFull = Resolve-RepoPath $ProfilePath
    $manifest = [ordered]@{
        script = $MyInvocation.MyCommand.Path
        generated_at = (Get-Date).ToString("o")
        allow_hardware = [bool]$AllowHardware.IsPresent
        no_hardware_actions_executed = -not $AllowHardware.IsPresent
        profile_path = $profileFull
        profile_sha256 = Get-FileSha256OrMissing -Path $profileFull
        inner_script = Resolve-RepoPath $InnerScript
        files = $entries
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestJson -Encoding ascii
    $csvLines = @("path,exists,sha256")
    foreach ($entry in $entries) {
        $csvLines += ('"{0}",{1},{2}' -f ($entry.path -replace '"', '""'), $entry.exists, $entry.sha256)
    }
    $csvLines | Set-Content -LiteralPath $manifestCsv -Encoding ascii
}

function ConvertTo-Argument {
    param([string]$Value)
    if ($Value -match '[\s&()^|<>"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$StdoutPath,
        [string]$StderrPath,
        [int]$Timeout
    )
    $argLine = ($Arguments | ForEach-Object { ConvertTo-Argument $_ }) -join " "
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $argLine `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($Timeout * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 125
    }
    return $proc.ExitCode
}

$profileFullPath = Resolve-RepoPath $ProfilePath
$innerFullPath = Resolve-RepoPath $InnerScript
$shutdownScript = Resolve-RepoPath "scripts/hw/program_tfdu_shutdown_safe.ps1"
$hardwareRequested = $AllowHardware.IsPresent -or $ExecuteHardware.IsPresent
Write-HashManifest -Paths @(
    $ProfilePath,
    $InnerScript,
    "scripts/hw/program_tfdu_shutdown_safe.ps1",
    "config/profiles/G1_LANE0_BASELINE.json",
    "board_profiles/ACTIVE_PROFILE.json",
    "constraints/active/PORT1.generated.xdc"
)

"RUN_G1_LANE0_REPLAY_SAFE_BEGIN $(Get-Date -Format o)" | Set-Content -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "PROFILE_PATH=$profileFullPath"
Write-SummaryLine "PROFILE_SHA256=$(Get-FileSha256OrMissing -Path $profileFullPath)"
Write-SummaryLine "HASH_MANIFEST_JSON=$manifestJson"
Write-SummaryLine "HASH_MANIFEST_CSV=$manifestCsv"
Write-SummaryLine "INNER_SCRIPT=$innerFullPath"
Write-SummaryLine "INNER_SCRIPT_SHA256=$(Get-FileSha256OrMissing -Path $innerFullPath)"
Write-SummaryLine "SHUTDOWN_SCRIPT=$shutdownScript"
Write-SummaryLine "SHUTDOWN_SCRIPT_SHA256=$(Get-FileSha256OrMissing -Path $shutdownScript)"

if (-not $hardwareRequested) {
    Write-SummaryLine "REFUSED_NO_ALLOW_HARDWARE=1"
    Write-SummaryLine "NO_HARDWARE_ACTIONS_EXECUTED=1"
    Write-SummaryLine "RUN_G1_LANE0_REPLAY_SAFE_STATUS=REFUSED_NO_ALLOW_HARDWARE"
    Write-SummaryLine "RUN_G1_LANE0_REPLAY_SAFE_END $(Get-Date -Format o)"
    exit 0
}

$authLog = Join-Path $EvidenceDir "hardware_authorization.json"
$authArgs = @("tools/check_hardware_authorization.py", "--execute-hardware", "--json-summary")
if ($MaxRuntimeSec -gt 0) { $authArgs += @("--max-runtime-sec", [string]$MaxRuntimeSec) }
if ($ShutdownOnExit.IsPresent) { $authArgs += "--shutdown-on-exit" }
if ($Bitstream) { $authArgs += @("--bitstream", $Bitstream) }
if ($BoardId) { $authArgs += @("--board-id", $BoardId) }
if ($TestProfile) { $authArgs += @("--test-profile", $TestProfile) }
if ($ActivePinmapHash) { $authArgs += @("--active-pinmap-hash", $ActivePinmapHash) }
if ($ActiveXdcHash) { $authArgs += @("--active-xdc-hash", $ActiveXdcHash) }
$authOutput = & python @authArgs 2>&1
$authExit = $LASTEXITCODE
$authOutput | Set-Content -LiteralPath $authLog -Encoding ascii
Write-SummaryLine "HARDWARE_AUTHORIZATION_LOG=$authLog"
Write-SummaryLine "HARDWARE_AUTHORIZATION_EXIT=$authExit"
if ($authExit -ne 0) {
    Write-SummaryLine "AUTHORIZATION_MISSING=1"
    Write-SummaryLine "NO_HARDWARE_ACTIONS_EXECUTED=1"
    Write-SummaryLine "RUN_G1_LANE0_REPLAY_SAFE_STATUS=AUTHORIZATION_MISSING"
    Write-SummaryLine "RUN_G1_LANE0_REPLAY_SAFE_END $(Get-Date -Format o)"
    exit 2
}

foreach ($requiredPath in @($innerFullPath, $shutdownScript, $VivadoPath, $XsctPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        Write-SummaryLine "REQUIRED_PATH_MISSING=$requiredPath"
        throw "Required path is missing: $requiredPath"
    }
}

$innerArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $innerFullPath,
    "-ComPort",
    $ComPort,
    "-BaudRate",
    [string]$BaudRate,
    "-XsctPath",
    $XsctPath,
    "-VivadoPath",
    $VivadoPath,
    "-HwServerUrl",
    $HwServerUrl,
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz,
    "-XsctWaitSeconds",
    [string]$XsctWaitSeconds,
    "-PostStartSeconds",
    [string]$PostStartSeconds,
    "-CaptureSeconds",
    [string]$CaptureSeconds
)
if ($SkipPreflight.IsPresent) {
    $innerArgs += "-SkipPreflight"
}

$innerExit = 125
$shutdownExit = 125
$hardwareRunStarted = $false
Write-SummaryLine "ALLOW_HARDWARE=1"
Write-SummaryLine "NO_HARDWARE_ACTIONS_EXECUTED=0"
try {
    $hardwareRunStarted = $true
    Write-SummaryLine "INNER_RUN_START=$(Get-Date -Format o)"
    $innerExit = Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments $innerArgs `
        -StdoutPath $innerStdoutLog `
        -StderrPath $innerStderrLog `
        -Timeout 1200
    Write-SummaryLine "INNER_STDOUT_LOG=$innerStdoutLog"
    Write-SummaryLine "INNER_STDERR_LOG=$innerStderrLog"
    Write-SummaryLine "INNER_EXIT=$innerExit"
} finally {
    if ($hardwareRunStarted) {
        Write-SummaryLine "FORCED_SHUTDOWN_START=$(Get-Date -Format o)"
        $shutdownExit = Invoke-LoggedProcess `
            -FilePath "powershell.exe" `
            -Arguments @(
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                $shutdownScript,
                "-AllowHardware",
                "-ProfilePath",
                $profileFullPath,
                "-EvidenceDir",
                (Join-Path $EvidenceDir "forced_shutdown"),
                "-VivadoPath",
                $VivadoPath
            ) `
            -StdoutPath $shutdownStdoutLog `
            -StderrPath $shutdownStderrLog `
            -Timeout 300
        Write-SummaryLine "FORCED_SHUTDOWN_STDOUT_LOG=$shutdownStdoutLog"
        Write-SummaryLine "FORCED_SHUTDOWN_STDERR_LOG=$shutdownStderrLog"
        Write-SummaryLine "FORCED_SHUTDOWN_RAW_EXIT=$shutdownExit"
    }
}

$shutdownText = ""
if (Test-Path -LiteralPath $shutdownStdoutLog) {
    $shutdownText += Get-Content -LiteralPath $shutdownStdoutLog -Raw -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $shutdownStderrLog) {
    $shutdownText += "`n" + (Get-Content -LiteralPath $shutdownStderrLog -Raw -ErrorAction SilentlyContinue)
}
$shutdownOk = ($shutdownExit -eq 0 -or $shutdownText -match "SHUTDOWN_EXIT=0" -or $shutdownText -match "TFDU_SHUTDOWN_PROGRAMMED")
Write-SummaryLine "SHUTDOWN_EXIT=$(if ($shutdownOk) { 0 } else { $shutdownExit })"
Write-SummaryLine "TFDU_SHUTDOWN_PROGRAMMED_SEEN=$([int]($shutdownText -match 'TFDU_SHUTDOWN_PROGRAMMED'))"
Write-SummaryLine "RUN_G1_LANE0_REPLAY_SAFE_STATUS=$(if ($innerExit -eq 0 -and $shutdownOk) { 'PASS' } else { 'FAIL' })"
Write-SummaryLine "RUN_G1_LANE0_REPLAY_SAFE_END $(Get-Date -Format o)"

if (-not $shutdownOk) {
    exit $(if ($shutdownExit -ne 0) { $shutdownExit } else { 31 })
}
if ($innerExit -ne 0) {
    exit $innerExit
}
exit 0
