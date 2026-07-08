param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("a_tx_lane0", "a_tx_lane1", "b_tx_nonzero", "b_tx_lane0", "b_tx_lane1")]
    [string]$TriggerMode,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [int]$PayloadBytes = 64,
    [int]$StageSeconds = 60,
    [int]$StatsIntervalUs = 1000000,
    [int]$MaxPacketBytes = 255,
    [int]$RxTransferBytes = 255
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "build_psps_trigger_elf_${TriggerMode}_$stamp.summary.txt"
$outLog = Join-Path $reportsDir "build_psps_trigger_elf_${TriggerMode}_$stamp.out.log"
$errLog = Join-Path $reportsDir "build_psps_trigger_elf_${TriggerMode}_$stamp.err.log"
$buildTcl = Join-Path $repoRoot "software\ps_ps_loopback\build_vitis.tcl"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$makefilePath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\src\subdir.mk"

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

function Get-TriggerConfig {
    param([string]$Mode)
    switch ($Mode) {
        "a_tx_lane0" {
            return @{
                LaneMask = "0x1"
                Session = "0x2201"
                PayloadBytes = 64
                TxOnly = "1"
                TdmBidir = "0"
                RxOnly = "0"
            }
        }
        "a_tx_lane1" {
            return @{
                LaneMask = "0x2"
                Session = "0x2202"
                PayloadBytes = 64
                TxOnly = "1"
                TdmBidir = "0"
                RxOnly = "0"
            }
        }
        "b_tx_nonzero" {
            return @{
                LaneMask = "0x3"
                Session = "0x2203"
                PayloadBytes = 247
                TxOnly = "0"
                TdmBidir = "1"
                RxOnly = "0"
            }
        }
        "b_tx_lane0" {
            return @{
                LaneMask = "0x1"
                Session = "0x2201"
                PayloadBytes = 247
                TxOnly = "0"
                TdmBidir = "1"
                RxOnly = "0"
            }
        }
        "b_tx_lane1" {
            return @{
                LaneMask = "0x2"
                Session = "0x2202"
                PayloadBytes = 247
                TxOnly = "0"
                TdmBidir = "1"
                RxOnly = "0"
            }
        }
        default {
            throw "Unsupported trigger for PS ELF auto-build: $Mode"
        }
    }
}

function Set-BuildEnv {
    param(
        [hashtable]$Config,
        [int]$EffectivePayloadBytes
    )

    $env:PSPS_PAYLOAD_BYTES = [string]$EffectivePayloadBytes
    $env:PSPS_TX_ONLY = $Config.TxOnly
    $env:PSPS_TDM_BIDIR = $Config.TdmBidir
    $env:PSPS_RX_ONLY = $Config.RxOnly
    $env:PSPS_INTER_PACKET_US = "0"
    $env:PSPS_STAGE_SECONDS = [string]$StageSeconds
    $env:PSPS_STATS_INTERVAL_US = [string]$StatsIntervalUs
    $env:PSPS_RUN_ONCE = "1"
    $env:PSPS_WARMUP_STAGES = "0"
    $env:PSPS_MAX_OUTSTANDING = "0"
    $env:PSPS_WINDOW_START_GAP_US = "0"
    $env:PSPS_STAGE_LANE_MASK = $Config.LaneMask
    $env:PSPS_STAGE_SESSION_ID = $Config.Session
    $env:PSPS_PAYLOAD_LANE_MASK = $Config.LaneMask
    $env:PSPS_RX_LANE_MASK = $Config.LaneMask
    $env:PSPS_POLL_SLEEP_US = "0"
    $env:IR_TX_POLL_US = "1"
    $env:IR_HW_MAX_PACKET_BYTES = [string]$MaxPacketBytes
    $env:IR_HW_RX_TRANSFER_BYTES = [string]$RxTransferBytes
}

$cfg = Get-TriggerConfig -Mode $TriggerMode
$effectivePayloadBytes = $PayloadBytes
if (-not $PSBoundParameters.ContainsKey("PayloadBytes")) {
    $effectivePayloadBytes = [int]$cfg.PayloadBytes
}
$rawBytes = $effectivePayloadBytes + 8

"BUILD_PSPS_TRIGGER_ELF_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "TRIGGER_MODE=$TriggerMode"
Write-SummaryLine "XSCT_PATH=$XsctPath"
Write-SummaryLine "BUILD_TCL=$buildTcl"
Write-SummaryLine "OUT_LOG=$outLog"
Write-SummaryLine "ERR_LOG=$errLog"
Write-SummaryLine "PAYLOAD_BYTES=$effectivePayloadBytes"
Write-SummaryLine "RAW_BYTES=$rawBytes"
Write-SummaryLine "MAX_PACKET_BYTES=$MaxPacketBytes"
Write-SummaryLine "RX_TRANSFER_BYTES=$RxTransferBytes"
Write-SummaryLine "LANE_MASK=$($cfg.LaneMask)"
Write-SummaryLine "SESSION_ID=$($cfg.Session)"
Write-SummaryLine "PSPS_TX_ONLY=$($cfg.TxOnly)"
Write-SummaryLine "PSPS_TDM_BIDIR=$($cfg.TdmBidir)"
Write-SummaryLine "PSPS_RX_ONLY=$($cfg.RxOnly)"
Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
Write-SummaryLine "NO_UART_WRITE=1"
Write-SummaryLine "NO_TFDU_DRIVE=1"

if ($rawBytes -gt $MaxPacketBytes) {
    Write-SummaryLine "BUILD_BLOCKED_RAW_BYTES_EXCEED_PACKET=1"
    Write-SummaryLine "BUILD_PSPS_TRIGGER_ELF_END $(Get-Date -Format o)"
    Write-SummaryLine "BUILD_RESULT=FAIL_RAW_BYTES_EXCEED_PACKET"
    Write-SummaryLine "BUILD_EXIT_CODE=22"
    exit 22
}

Set-BuildEnv -Config $cfg -EffectivePayloadBytes $effectivePayloadBytes

$proc = Start-Process -FilePath $XsctPath `
    -ArgumentList @($buildTcl) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru
try {
    $proc.ProcessorAffinity = [IntPtr]0xFFFF
    Write-SummaryLine "AFFINITY_PARENT=0xFFFF"
} catch {
    Write-SummaryLine "AFFINITY_PARENT_WARN=$($_.Exception.Message)"
}

while (-not $proc.HasExited) {
    foreach ($child in Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "(_vitis_ws_ps_ps_loopback|rf_comm_ps_ps_loopback|xsct|arm-none-eabi|make)" }) {
        try {
            (Get-Process -Id $child.ProcessId -ErrorAction Stop).ProcessorAffinity = [IntPtr]0xFFFF
        } catch {
        }
    }
    Start-Sleep -Seconds 2
    $proc.Refresh()
}

Write-SummaryLine "XSCT_EXIT=$($proc.ExitCode)"
if ($proc.ExitCode -is [int] -and $proc.ExitCode -ne 0) {
    Write-SummaryLine "BUILD_PSPS_TRIGGER_ELF_END $(Get-Date -Format o)"
    Write-SummaryLine "BUILD_RESULT=FAIL_XSCT"
    Write-SummaryLine "BUILD_EXIT_CODE=$($proc.ExitCode)"
    exit $proc.ExitCode
}

if (-not (Test-Path -LiteralPath $elfPath)) {
    Write-SummaryLine "ELF=MISSING"
    Write-SummaryLine "BUILD_PSPS_TRIGGER_ELF_END $(Get-Date -Format o)"
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
    foreach ($line in (($makeText -split "`r?`n") | Where-Object { $_ -match "PSPS_STAGE_LANE_MASK|PSPS_STAGE_SESSION_ID|PSPS_PAYLOAD_BYTES|PSPS_TX_ONLY|PSPS_TDM_BIDIR|PSPS_RX_ONLY|IR_HW_MAX_PACKET_BYTES|IR_HW_RX_TRANSFER_BYTES" })) {
        Write-SummaryLine "MAKEFILE_MATCH=$line"
    }
}

Write-SummaryLine "BUILD_PSPS_TRIGGER_ELF_END $(Get-Date -Format o)"
Write-SummaryLine "BUILD_RESULT=PASS"
Write-SummaryLine "BUILD_EXIT_CODE=0"
exit 0
