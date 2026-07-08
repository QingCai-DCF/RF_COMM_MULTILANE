param(
    [ValidateSet("P4A_TXACK_DIAG", "P4B_DATA_ROUNDTRIP_DIAG")]
    [string]$Profile = "P4A_TXACK_DIAG",
    [ValidateSet("BuildA", "BuildB")]
    [string]$RxTuning = "BuildB",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [int]$Jobs = 16,
    [int]$StageSeconds = 60,
    [int]$PayloadBytes = 256,
    [int]$FragmentBytes = 64,
    [switch]$SkipVitisBuild
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "build_${Profile}_${RxTuning}_$stamp.summary.txt"
$innerOutLog = Join-Path $reportsDir "build_${Profile}_${RxTuning}_$stamp.inner.out.log"
$innerErrLog = Join-Path $reportsDir "build_${Profile}_${RxTuning}_$stamp.inner.err.log"
$artifactDir = Join-Path $reportsDir ("p4_artifacts\{0}_{1}_{2}" -f $Profile, $RxTuning, $stamp)
$innerScript = Join-Path $scriptDir "build_g0_lane0_artifacts.ps1"

if (-not (Test-Path -LiteralPath $innerScript)) {
    throw "Missing build script: $innerScript"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Set-BuildEnv {
    param([hashtable]$EnvMap)
    foreach ($key in $EnvMap.Keys) {
        [Environment]::SetEnvironmentVariable($key, [string]$EnvMap[$key], "Process")
    }
}

function Write-ArtifactLine {
    param([string]$Name, [string]$Path)
    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
        Write-SummaryLine "ARTIFACT name=$Name path=$Path size=$($item.Length) sha256=$hash"
        New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
        $copyName = "{0}_{1}{2}" -f $Profile, $RxTuning, $item.Extension
        if ($Name -eq "elf") {
            $copyName = "{0}_{1}.elf" -f $Profile, $RxTuning
        } elseif ($Name -eq "bit") {
            $copyName = "{0}_{1}.bit" -f $Profile, $RxTuning
        } elseif ($Name -eq "ltx") {
            $copyName = "{0}_{1}.ltx" -f $Profile, $RxTuning
        } elseif ($Name -eq "xsa") {
            $copyName = "{0}_{1}.xsa" -f $Profile, $RxTuning
        }
        $copyPath = Join-Path $artifactDir $copyName
        Copy-Item -LiteralPath $Path -Destination $copyPath -Force
        $copyItem = Get-Item -LiteralPath $copyPath
        $copyHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $copyPath).Hash
        Write-SummaryLine "P4_PROFILE_ARTIFACT name=$Name path=$copyPath size=$($copyItem.Length) sha256=$copyHash"
    } else {
        Write-SummaryLine "ARTIFACT_MISSING name=$Name path=$Path"
    }
}

if ($StageSeconds -lt 1 -or $StageSeconds -gt 600) {
    throw "StageSeconds must be between 1 and 600."
}
if ($PayloadBytes -lt 16 -or $PayloadBytes -gt 256) {
    throw "PayloadBytes must be between 16 and 256."
}

$rawBytes = $PayloadBytes + 8
$rxStart = "0"
$rxEnd = "5"
$rxRealign = "0"
if ($RxTuning -eq "BuildA") {
    $rxStart = "3"
    $rxEnd = "7"
    $rxRealign = "1"
}

$pspsTxOnly = "1"
if ($Profile -eq "P4B_DATA_ROUNDTRIP_DIAG") {
    $pspsTxOnly = "0"
}

$envMap = @{
    VIVADO_MAX_THREADS = [string]$Jobs
    MAKEFLAGS = "-j$Jobs"
    IR_MAX_PACKET_BYTES = [string]$rawBytes
    IR_FRAGMENT_BYTES = [string]$FragmentBytes
    IR_MAX_RETRY = "12"
    IR_HW_MAX_PACKET_BYTES = [string]$rawBytes
    IR_HW_RX_TRANSFER_BYTES = [string]$rawBytes
    IR_GUARD_CYCLES = "4096"
    IR_CNT_CHIP_MAX = "7"
    IR_CNT_PREAMBLE = "16"
    IR_RX_DETECT_START_CYCLES = $rxStart
    IR_RX_DETECT_END_CYCLES = $rxEnd
    IR_RX_PREAMBLE_REALIGN_EDGE = $rxRealign
    IR_B_RX_DETECT_START_CYCLES = $rxStart
    IR_B_RX_DETECT_END_CYCLES = $rxEnd
    IR_B_RX_PREAMBLE_REALIGN_EDGE = $rxRealign
    IR_STREAM_PHY_DBG_SELECT = "1"
    IR_B_MODE = "stream_bidir"
    IR_LANE_COUNT = "2"
    IR_B2A_ENABLE = "0"
    IR_B2A_FREE_RUN = "0"
    IR_B2A_ECHO_ENABLE = "0"
    IR_B_SESSION_ID = "0x2201"
    IR_B_RX_LANE_MASK = "1"
    IR_B_EXPECTED_A_LANE_MASK = "1"
    IR_B_TX_LANE_MASK = "1"
    IR_B_ACK_LANE_MASK = "1"
    IR_B_BACKOFF_SLOT_CYCLES = "1024"
    IR_B_START_IDLE_CYCLES = "100000"
    PSPS_UART_OPERATOR = "1"
    PSPS_PAYLOAD_BYTES = [string]$PayloadBytes
    PSPS_STAGE_SECONDS = [string]$StageSeconds
    PSPS_STATS_INTERVAL_US = "1000000"
    PSPS_RUN_ONCE = "1"
    PSPS_WARMUP_STAGES = "0"
    PSPS_TX_ONLY = $pspsTxOnly
    PSPS_TDM_BIDIR = "0"
    PSPS_RX_ONLY = "0"
    PSPS_INTER_PACKET_US = "0"
    PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY = "0"
    PSPS_IR_ROUNDTRIP_RETRY_GAP_US = "2000"
    PSPS_MAX_OUTSTANDING = "0"
    PSPS_WINDOW_START_GAP_US = "0"
    PSPS_STAGE_LANE_MASK = "0x1"
    PSPS_STAGE_SESSION_ID = "0x2201"
    PSPS_PAYLOAD_LANE_MASK = "0x1"
    PSPS_RX_LANE_MASK = "0x1"
    PSPS_POLL_SLEEP_US = "0"
    IR_TX_POLL_US = "1"
}

if ($Profile -eq "P4B_DATA_ROUNDTRIP_DIAG") {
    $envMap.IR_B2A_ENABLE = "1"
    $envMap.IR_B2A_FREE_RUN = "0"
    $envMap.IR_B2A_ECHO_ENABLE = "1"
    $envMap.IR_STREAM_FULL_MODE = "1"
    $envMap.IR_TX_ONLY_ACK_MODE = "0"
    $envMap.PSPS_INTER_PACKET_US = "50000"
    $envMap.PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY = "24"
    $envMap.PSPS_IR_ROUNDTRIP_RETRY_GAP_US = "2000"
    $envMap.SKIP_ILA_INSERT = "1"
}

"P4_PROFILE_BUILD_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "PROFILE=$Profile"
Write-SummaryLine "RX_TUNING=$RxTuning"
Write-SummaryLine "JOBS=$Jobs"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"
Write-SummaryLine "PAYLOAD_BYTES=$PayloadBytes"
Write-SummaryLine "FRAGMENT_BYTES=$FragmentBytes"
Write-SummaryLine "RAW_BYTES=$rawBytes"
Write-SummaryLine "PSPS_TX_ONLY=$pspsTxOnly"
Write-SummaryLine "INNER_STDOUT_LOG=$innerOutLog"
Write-SummaryLine "INNER_STDERR_LOG=$innerErrLog"
Write-SummaryLine "P4_PROFILE_ARTIFACT_DIR=$artifactDir"

foreach ($key in ($envMap.Keys | Sort-Object)) {
    Write-SummaryLine "P4_BUILD_ENV $key=$($envMap[$key])"
}
Set-BuildEnv -EnvMap $envMap

$innerArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $innerScript,
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

$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $innerArgs `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $innerOutLog `
    -RedirectStandardError $innerErrLog `
    -WindowStyle Hidden `
    -PassThru
$proc.WaitForExit()
$proc.Refresh()
$innerExit = if ($null -eq $proc.ExitCode) { 125 } else { $proc.ExitCode }
Write-SummaryLine "INNER_EXIT=$innerExit"

$innerText = ""
if (Test-Path -LiteralPath $innerOutLog) {
    $innerText = Get-Content -LiteralPath $innerOutLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (Get-Content -LiteralPath $innerOutLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "G0_LANE0_BUILD_DONE|ILA_SKIPPED|ARTIFACT |ARTIFACT_MISSING|CONSTRAINT_SHA256|BUILD_ENV (IR_RX_DETECT_START_CYCLES|IR_RX_DETECT_END_CYCLES|IR_RX_PREAMBLE_REALIGN_EDGE|IR_B_RX_DETECT_START_CYCLES|IR_B_RX_DETECT_END_CYCLES|IR_B_RX_PREAMBLE_REALIGN_EDGE|PSPS_TX_ONLY|PSPS_PAYLOAD_BYTES|PSPS_STAGE_SECONDS|PSPS_INTER_PACKET_US|PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY|PSPS_IR_ROUNDTRIP_RETRY_GAP_US)"
    })) {
        Write-SummaryLine "INNER_MATCH=$line"
    }
}
if ($innerExit -ne 0 -and $innerText -match "G0_LANE0_BUILD_DONE=1") {
    Write-SummaryLine "INNER_EXIT_OVERRIDDEN_BY_DONE_MARKER=1"
    $innerExit = 0
}

$bitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$ltxPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx"
$xsaPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"

Write-ArtifactLine -Name "bit" -Path $bitPath
Write-ArtifactLine -Name "ltx" -Path $ltxPath
Write-ArtifactLine -Name "xsa" -Path $xsaPath
Write-ArtifactLine -Name "elf" -Path $elfPath

Write-SummaryLine "P4_PROFILE_BUILD_END $(Get-Date -Format o)"
$buildResult = "FAIL"
if ($innerExit -eq 0) {
    $buildResult = "PASS"
}
Write-SummaryLine "BUILD_RESULT=$buildResult"
Write-SummaryLine "BUILD_EXIT_CODE=$innerExit"
exit $innerExit
