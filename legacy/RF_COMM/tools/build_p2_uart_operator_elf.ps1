param(
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [int]$PayloadBytes = 256,
    [int]$StageSeconds = 300,
    [int]$StatsIntervalUs = 1000000,
    [string]$LaneMask = "0x1",
    [string]$AckMask = "0x1",
    [string]$SessionId = "0x2201",
    [switch]$Roundtrip
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "build_p2_uart_operator_elf_$stamp.summary.txt"
$outLog = Join-Path $reportsDir "build_p2_uart_operator_elf_$stamp.out.log"
$errLog = Join-Path $reportsDir "build_p2_uart_operator_elf_$stamp.err.log"
$buildTcl = Join-Path $repoRoot "software\ps_ps_loopback\build_vitis.tcl"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$makefilePath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\src\subdir.mk"
$rawBytes = $PayloadBytes + 8

foreach ($path in @($XsctPath, $buildTcl)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

"BUILD_P2_UART_OPERATOR_ELF_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "XSCT_PATH=$XsctPath"
Write-SummaryLine "BUILD_TCL=$buildTcl"
Write-SummaryLine "OUT_LOG=$outLog"
Write-SummaryLine "ERR_LOG=$errLog"
Write-SummaryLine "PAYLOAD_BYTES=$PayloadBytes"
Write-SummaryLine "RAW_BYTES=$rawBytes"
Write-SummaryLine "LANE_MASK=$LaneMask"
Write-SummaryLine "ACK_MASK=$AckMask"
Write-SummaryLine "SESSION_ID=$SessionId"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"
Write-SummaryLine "ROUNDTRIP=$([int]$Roundtrip.IsPresent)"
Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
Write-SummaryLine "NO_UART_WRITE=1"
Write-SummaryLine "NO_TFDU_DRIVE=1"

if ($PayloadBytes -lt 16) {
    Write-SummaryLine "BUILD_RESULT=FAIL_PAYLOAD_TOO_SMALL"
    Write-SummaryLine "BUILD_EXIT_CODE=21"
    exit 21
}

$env:PSPS_UART_OPERATOR = "1"
$env:PSPS_PAYLOAD_BYTES = [string]$PayloadBytes
if ($Roundtrip.IsPresent) {
    $env:PSPS_TX_ONLY = "0"
} else {
    $env:PSPS_TX_ONLY = "1"
}
$env:PSPS_TDM_BIDIR = "0"
$env:PSPS_RX_ONLY = "0"
$env:PSPS_INTER_PACKET_US = "0"
$env:PSPS_STAGE_SECONDS = [string]$StageSeconds
$env:PSPS_STATS_INTERVAL_US = [string]$StatsIntervalUs
$env:PSPS_RUN_ONCE = "0"
$env:PSPS_WARMUP_STAGES = "0"
$env:PSPS_MAX_OUTSTANDING = "0"
$env:PSPS_WINDOW_START_GAP_US = "0"
$env:PSPS_STAGE_LANE_MASK = $LaneMask
$env:PSPS_STAGE_SESSION_ID = $SessionId
$env:PSPS_PAYLOAD_LANE_MASK = $LaneMask
$env:PSPS_RX_LANE_MASK = $AckMask
$env:PSPS_POLL_SLEEP_US = "0"
$env:IR_TX_POLL_US = "1"
$env:IR_HW_MAX_PACKET_BYTES = [string]$rawBytes
$env:IR_HW_RX_TRANSFER_BYTES = [string]$rawBytes

$proc = Start-Process -FilePath $XsctPath `
    -ArgumentList @($buildTcl) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

while (-not $proc.HasExited) {
    Start-Sleep -Seconds 2
    $proc.Refresh()
}

Write-SummaryLine "XSCT_EXIT=$($proc.ExitCode)"
if ($proc.ExitCode -is [int] -and $proc.ExitCode -ne 0) {
    Write-SummaryLine "BUILD_P2_UART_OPERATOR_ELF_END $(Get-Date -Format o)"
    Write-SummaryLine "BUILD_RESULT=FAIL_XSCT"
    Write-SummaryLine "BUILD_EXIT_CODE=$($proc.ExitCode)"
    exit $proc.ExitCode
}

if (-not (Test-Path -LiteralPath $elfPath)) {
    Write-SummaryLine "ELF=MISSING"
    Write-SummaryLine "BUILD_P2_UART_OPERATOR_ELF_END $(Get-Date -Format o)"
    Write-SummaryLine "BUILD_RESULT=FAIL_ELF_MISSING"
    Write-SummaryLine "BUILD_EXIT_CODE=23"
    exit 23
}

$elfHash = Get-FileHash -Algorithm SHA256 -LiteralPath $elfPath
Write-SummaryLine "ELF=$elfPath"
Write-SummaryLine "ELF_SHA256=$($elfHash.Hash)"
Write-SummaryLine "ELF_SIZE=$((Get-Item -LiteralPath $elfPath).Length)"

if (Test-Path -LiteralPath $makefilePath) {
    $makeText = Get-Content -LiteralPath $makefilePath -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($makeText -split "`r?`n") | Where-Object { $_ -match "PSPS_UART_OPERATOR|PSPS_STAGE_LANE_MASK|PSPS_STAGE_SESSION_ID|PSPS_PAYLOAD_BYTES|PSPS_TX_ONLY|IR_HW_MAX_PACKET_BYTES|IR_HW_RX_TRANSFER_BYTES" })) {
        Write-SummaryLine "MAKEFILE_MATCH=$line"
    }
}

Write-SummaryLine "BUILD_P2_UART_OPERATOR_ELF_END $(Get-Date -Format o)"
Write-SummaryLine "BUILD_RESULT=PASS"
Write-SummaryLine "BUILD_EXIT_CODE=0"
exit 0
