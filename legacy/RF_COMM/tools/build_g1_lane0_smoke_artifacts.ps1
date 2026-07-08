param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [int]$Jobs = 16,
    [int]$StageSeconds = 24,
    [int]$FragmentBytes = 64,
    [int]$StreamPhyDebugSelect = 1,
    [switch]$SkipVitisBuild
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "g1_lane0_smoke_build_$stamp.summary.txt"
$innerOutLog = Join-Path $reportsDir "g1_lane0_smoke_build_$stamp.inner.out.log"
$innerErrLog = Join-Path $reportsDir "g1_lane0_smoke_build_$stamp.inner.err.log"
$buildScript = Join-Path $scriptDir "build_g0_lane0_artifacts.ps1"

if (-not (Test-Path -LiteralPath $buildScript)) {
    throw "Missing build script: $buildScript"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        try {
            Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
            return
        } catch [System.IO.IOException] {
            Start-Sleep -Milliseconds 100
        }
    }
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Set-BuildEnv {
    param([hashtable]$EnvMap)
    foreach ($key in $EnvMap.Keys) {
        [Environment]::SetEnvironmentVariable($key, [string]$EnvMap[$key], "Process")
    }
}

"G1_LANE0_SMOKE_BUILD_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "JOBS=$Jobs"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"
Write-SummaryLine "FRAGMENT_BYTES=$FragmentBytes"
Write-SummaryLine "STREAM_PHY_DBG_SELECT=$StreamPhyDebugSelect"
Write-SummaryLine "SKIP_VITIS_BUILD=$([int]$SkipVitisBuild.IsPresent)"
Write-SummaryLine "INNER_STDOUT_LOG=$innerOutLog"
Write-SummaryLine "INNER_STDERR_LOG=$innerErrLog"

try {
    $proc = [System.Diagnostics.Process]::GetCurrentProcess()
    $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
    $proc.ProcessorAffinity = [IntPtr]65535
    Write-SummaryLine "PROCESS_PRIORITY=$($proc.PriorityClass)"
    Write-SummaryLine "PROCESS_AFFINITY=$($proc.ProcessorAffinity)"
} catch {
    Write-SummaryLine "PROCESS_AFFINITY_WARN=$($_.Exception.Message)"
}

$envMap = @{
    IR_MAX_PACKET_BYTES = "264"
    IR_FRAGMENT_BYTES = [string]$FragmentBytes
    IR_MAX_RETRY = "12"
    IR_HW_MAX_PACKET_BYTES = "264"
    IR_HW_RX_TRANSFER_BYTES = "264"
    PSPS_PAYLOAD_BYTES = "256"
    PSPS_STAGE_SECONDS = [string]$StageSeconds
    PSPS_STATS_INTERVAL_US = "5000000"
    PSPS_RUN_ONCE = "1"
    PSPS_WARMUP_STAGES = "0"
    PSPS_TX_ONLY = "1"
    PSPS_TDM_BIDIR = "0"
    PSPS_RX_ONLY = "0"
    PSPS_INTER_PACKET_US = "0"
    PSPS_MAX_OUTSTANDING = "0"
    PSPS_WINDOW_START_GAP_US = "0"
    PSPS_STAGE_LANE_MASK = "0x1"
    PSPS_STAGE_SESSION_ID = "0x2201"
    PSPS_PAYLOAD_LANE_MASK = "0x1"
    PSPS_RX_LANE_MASK = "0x1"
    PSPS_POLL_SLEEP_US = "0"
    IR_TX_POLL_US = "1"
    IR_B_MODE = "stream_bidir"
    IR_LANE_COUNT = "2"
    IR_B2A_ENABLE = "0"
    IR_B2A_FREE_RUN = "0"
    IR_B_SESSION_ID = "0x2201"
    IR_B_RX_LANE_MASK = "1"
    IR_B_RX_DETECT_START_CYCLES = "0"
    IR_B_RX_DETECT_END_CYCLES = "7"
    IR_B_RX_PREAMBLE_REALIGN_EDGE = "0"
    IR_B_EXPECTED_A_LANE_MASK = "1"
    IR_B_TX_LANE_MASK = "1"
    IR_B_ACK_LANE_MASK = "1"
    IR_B_BACKOFF_SLOT_CYCLES = "1024"
    IR_B_START_IDLE_CYCLES = "100000"
    IR_CNT_CHIP_MAX = "7"
    IR_CNT_PREAMBLE = "16"
    IR_RX_DETECT_START_CYCLES = "0"
    IR_RX_DETECT_END_CYCLES = "5"
    IR_RX_PREAMBLE_REALIGN_EDGE = "0"
    IR_GUARD_CYCLES = "4096"
    IR_STREAM_PHY_DBG_SELECT = [string]$StreamPhyDebugSelect
}

foreach ($key in ($envMap.Keys | Sort-Object)) {
    Write-SummaryLine "G1_BUILD_ENV $key=$($envMap[$key])"
}
Set-BuildEnv -EnvMap $envMap

$innerArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $buildScript,
    "-VivadoPath",
    $VivadoPath,
    "-XsctPath",
    $XsctPath,
    "-Variant",
    "a2b_ack",
    "-Jobs",
    [string]$Jobs
)
if ($SkipVitisBuild) {
    $innerArgs += "-SkipVitisBuild"
}

$procInfo = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $innerArgs `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $innerOutLog `
    -RedirectStandardError $innerErrLog `
    -WindowStyle Hidden `
    -PassThru
$procInfo.WaitForExit()
$procInfo.Refresh()
$innerExit = if ($null -eq $procInfo.ExitCode) { 125 } else { $procInfo.ExitCode }
Write-SummaryLine "INNER_EXIT=$innerExit"

$innerText = ""
if (Test-Path -LiteralPath $innerOutLog) {
    $innerText = Get-Content -LiteralPath $innerOutLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (Get-Content -LiteralPath $innerOutLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "G0_LANE0_BUILD_DONE|ARTIFACT |ARTIFACT_MISSING|CONSTRAINT_SHA256|BUILD_ENV (IR_CNT_PREAMBLE|IR_MAX_PACKET_BYTES|IR_FRAGMENT_BYTES|IR_MAX_RETRY|IR_HW_MAX_PACKET_BYTES|IR_HW_RX_TRANSFER_BYTES|IR_GUARD_CYCLES|IR_RX_DETECT_START_CYCLES|IR_RX_DETECT_END_CYCLES|IR_RX_PREAMBLE_REALIGN_EDGE|IR_B_RX_DETECT_START_CYCLES|IR_B_RX_DETECT_END_CYCLES|IR_B_RX_PREAMBLE_REALIGN_EDGE|IR_STREAM_PHY_DBG_SELECT|PSPS_PAYLOAD_BYTES|PSPS_STAGE_SECONDS)"
    })) {
        Write-SummaryLine "INNER_MATCH=$line"
    }
}

if ($innerExit -eq 125 -and $innerText -match "G0_LANE0_BUILD_DONE=1") {
    Write-SummaryLine "INNER_EXIT_INFERRED=0"
    $innerExit = 0
}

if ($innerExit -ne 0) {
    Write-SummaryLine "G1_LANE0_SMOKE_BUILD_DONE=0"
    Write-SummaryLine "G1_LANE0_SMOKE_BUILD_END $(Get-Date -Format o)"
    exit $innerExit
}

Write-SummaryLine "G1_LANE0_SMOKE_BUILD_DONE=1"
Write-SummaryLine "G1_LANE0_SMOKE_BUILD_END $(Get-Date -Format o)"
exit 0
