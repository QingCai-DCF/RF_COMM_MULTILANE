param(
    [ValidateSet("lane0", "lane1", "two_lane")]
    [string]$Mode = "lane0",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [int]$Jobs = 16,
    [switch]$RunBuild,
    [switch]$SkipVitisBuild
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
$artifactRoot = Join-Path $repoRoot "reports\p0_ack_only_artifacts"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "p0_ack_only_build_$stamp.summary.txt"
$configLog = Join-Path $reportsDir "p0_ack_only_build_$stamp.configure.log"
$ilaLog = Join-Path $reportsDir "p0_ack_only_build_$stamp.ila.log"
$bitLog = Join-Path $reportsDir "p0_ack_only_build_$stamp.bitstream.log"
$vitisLog = Join-Path $reportsDir "p0_ack_only_build_$stamp.vitis.log"
$artifactDir = Join-Path $artifactRoot ("{0}_{1}" -f $Mode, $stamp)

$constraintFileName = (-join @(
    [char]0x9879,
    [char]0x76EE,
    [char]0x7EA6,
    [char]0x675F,
    [char]0x0028,
    [char]0x76EE,
    [char]0x6807,
    [char]0xFF09
)) + ".txt"
$constraintPath = Join-Path $repoRoot $constraintFileName
$expectedConstraintHash = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$configureTcl = Join-Path $repoRoot "tools\configure_lane0_ab_hw_loopback.tcl"
$ilaTcl = Join-Path $repoRoot "tools\add_2lane_phy_ila.tcl"
$bitstreamTcl = Join-Path $repoRoot "tools\build_current_bitstream.tcl"
$vitisTcl = Join-Path $repoRoot "software\ps_ps_loopback\build_vitis.tcl"

$bitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$ltxPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx"
$xsaPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"

foreach ($path in @($VivadoPath, $XsctPath, $configureTcl, $ilaTcl, $bitstreamTcl, $vitisTcl, $constraintPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Quote-Arg {
    param([string]$Text)
    if ($Text -match "[\s`"]") {
        return '"' + ($Text -replace '"', '\"') + '"'
    }
    return $Text
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [int]$TimeoutSeconds
    )

    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError ($LogPath + ".err") `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 0
    }
    return $proc.ExitCode
}

function Set-BuildEnv {
    param([hashtable]$EnvMap)
    foreach ($key in $EnvMap.Keys) {
        [Environment]::SetEnvironmentVariable($key, [string]$EnvMap[$key], "Process")
    }
}

function Get-AckBuildEnv {
    param([string]$ModeName)
    $common = @{
        VIVADO_MAX_THREADS = [string]$Jobs
        MAKEFLAGS = "-j$Jobs"
        IR_B_MODE = "stream_bidir"
        IR_CNT_CHIP_MAX = "7"
        IR_CNT_PREAMBLE = "16"
        IR_RX_DETECT_START_CYCLES = "0"
        IR_RX_DETECT_END_CYCLES = "5"
        IR_RX_DATA_PHASE_DELAY_CYCLES = "0"
        IR_RX_PREAMBLE_REALIGN_EDGE = "0"
        IR_B_RX_DETECT_START_CYCLES = "0"
        IR_B_RX_DETECT_END_CYCLES = "7"
        IR_B_RX_PREAMBLE_REALIGN_EDGE = "0"
        IR_MAX_PACKET_BYTES = "264"
        IR_FRAGMENT_BYTES = "255"
        IR_MAX_RETRY = "12"
        IR_GUARD_CYCLES = "4096"
        IR_HW_MAX_PACKET_BYTES = "264"
        IR_HW_RX_TRANSFER_BYTES = "264"
        IR_STREAM_PHY_DBG_SELECT = "1"
        IR_B2A_ENABLE = "0"
        IR_B2A_FREE_RUN = "0"
        IR_B_BACKOFF_SLOT_CYCLES = "1024"
        IR_B_START_IDLE_CYCLES = "100000"
        PSPS_PAYLOAD_BYTES = "256"
        PSPS_TX_ONLY = "1"
        PSPS_TDM_BIDIR = "0"
        PSPS_RX_ONLY = "0"
        PSPS_INTER_PACKET_US = "0"
        PSPS_STAGE_SECONDS = "8"
        PSPS_STATS_INTERVAL_US = "5000000"
        PSPS_RUN_ONCE = "1"
        PSPS_WARMUP_STAGES = "0"
        PSPS_MAX_OUTSTANDING = "0"
        PSPS_WINDOW_START_GAP_US = "0"
        PSPS_POLL_SLEEP_US = "0"
        IR_TX_POLL_US = "1"
    }
    if ($ModeName -eq "lane0") {
        $common.IR_LANE_COUNT = "2"
        $common.IR_B_SESSION_ID = "0x2201"
        $common.IR_B_RX_LANE_MASK = "1"
        $common.IR_B_EXPECTED_A_LANE_MASK = "1"
        $common.IR_B_TX_LANE_MASK = "1"
        $common.IR_B_ACK_LANE_MASK = "1"
        $common.PSPS_2LANE_ONLY = "1"
        $common.PSPS_STAGE_LANE_MASK = "0x1"
        $common.PSPS_PAYLOAD_LANE_MASK = "0x1"
        $common.PSPS_RX_LANE_MASK = "0x1"
        $common.PSPS_STAGE_SESSION_ID = "0x2201"
    } elseif ($ModeName -eq "lane1") {
        $common.IR_LANE_COUNT = "2"
        $common.IR_B_SESSION_ID = "0x2202"
        $common.IR_B_RX_LANE_MASK = "2"
        $common.IR_B_EXPECTED_A_LANE_MASK = "2"
        $common.IR_B_TX_LANE_MASK = "2"
        $common.IR_B_ACK_LANE_MASK = "2"
        $common.PSPS_2LANE_ONLY = "1"
        $common.PSPS_STAGE_LANE_MASK = "0x2"
        $common.PSPS_PAYLOAD_LANE_MASK = "0x2"
        $common.PSPS_RX_LANE_MASK = "0x2"
        $common.PSPS_STAGE_SESSION_ID = "0x2202"
    } else {
        $common.IR_LANE_COUNT = "2"
        $common.IR_B_SESSION_ID = "0x2203"
        $common.IR_B_RX_LANE_MASK = "3"
        $common.IR_B_EXPECTED_A_LANE_MASK = "3"
        $common.IR_B_TX_LANE_MASK = "3"
        $common.IR_B_ACK_LANE_MASK = "3"
        $common.PSPS_2LANE_ONLY = "1"
        $common.PSPS_STAGE_LANE_MASK = "0x3"
        $common.PSPS_PAYLOAD_LANE_MASK = "0x3"
        $common.PSPS_RX_LANE_MASK = "0x3"
        $common.PSPS_STAGE_SESSION_ID = "0x2203"
    }
    return $common
}

function Copy-ArtifactIfPresent {
    param(
        [string]$Source,
        [string]$Name
    )
    if (Test-Path -LiteralPath $Source) {
        $dest = Join-Path $artifactDir $Name
        Copy-Item -LiteralPath $Source -Destination $dest -Force
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $dest).Hash
        Write-SummaryLine "ARTIFACT path=$dest sha256=$hash"
    } else {
        Write-SummaryLine "ARTIFACT_MISSING path=$Source"
    }
}

"P0_ACK_ONLY_BUILD_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "MODE=$Mode"
Write-SummaryLine "RUN_BUILD=$([int]$RunBuild.IsPresent)"
Write-SummaryLine "SKIP_VITIS_BUILD=$([int]$SkipVitisBuild.IsPresent)"
Write-SummaryLine "JOBS=$Jobs"
Write-SummaryLine "ARTIFACT_DIR=$artifactDir"
Write-SummaryLine "CONFIG_LOG=$configLog"
Write-SummaryLine "ILA_LOG=$ilaLog"
Write-SummaryLine "BITSTREAM_LOG=$bitLog"
Write-SummaryLine "VITIS_LOG=$vitisLog"

try {
    $proc = [System.Diagnostics.Process]::GetCurrentProcess()
    $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
    $proc.ProcessorAffinity = [IntPtr]65535
    Write-SummaryLine "PROCESS_PRIORITY=$($proc.PriorityClass)"
    Write-SummaryLine "PROCESS_AFFINITY=$($proc.ProcessorAffinity)"
} catch {
    Write-SummaryLine "PROCESS_AFFINITY_WARN=$($_.Exception.Message)"
}

$constraintHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $constraintPath).Hash
Write-SummaryLine "CONSTRAINT_SHA256=$constraintHash"
if ($constraintHash -ne $expectedConstraintHash) {
    Write-SummaryLine "CONSTRAINT_HASH_MISMATCH=1"
    Write-SummaryLine "P0_ACK_ONLY_BUILD_END $(Get-Date -Format o)"
    exit 12
}

$envMap = Get-AckBuildEnv -ModeName $Mode
foreach ($key in ($envMap.Keys | Sort-Object)) {
    Write-SummaryLine "BUILD_ENV $key=$($envMap[$key])"
}

$configArgs = @("-mode", "batch", "-notrace", "-source", $configureTcl)
$ilaArgs = @("-mode", "batch", "-notrace", "-source", $ilaTcl)
$bitArgs = @("-mode", "batch", "-notrace", "-source", $bitstreamTcl)
$vitisArgs = @($vitisTcl)
Write-SummaryLine "CONFIG_COMMAND=$VivadoPath $((@($configArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "ILA_COMMAND=$VivadoPath $((@($ilaArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "BITSTREAM_COMMAND=$VivadoPath $((@($bitArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "VITIS_COMMAND=$XsctPath $((@($vitisArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "ACK_ONLY_BUILD_LIMITATION=Running this changes the active Vivado project/bitstream to the selected ACK-only configuration; copy artifacts are saved under ARTIFACT_DIR."

if (-not $RunBuild) {
    Write-SummaryLine "DRY_RUN_NO_VIVADO_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_VITIS_DONE=1"
    Write-SummaryLine "P0_ACK_ONLY_BUILD_END $(Get-Date -Format o)"
    exit 0
}

New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
Set-BuildEnv -EnvMap $envMap

Write-SummaryLine "CONFIGURE_START=$(Get-Date -Format o)"
$configExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments $configArgs -LogPath $configLog -TimeoutSeconds 1200
Write-SummaryLine "CONFIGURE_EXIT=$configExit"
if ($configExit -ne 0) {
    Write-SummaryLine "P0_ACK_ONLY_BUILD_END $(Get-Date -Format o)"
    exit $configExit
}
if (Test-Path -LiteralPath $configLog) {
    foreach ($line in (Get-Content -LiteralPath $configLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "HWLOOP:|CONFIGURE_LANE0_AB_HW_LOOPBACK_DONE|ERROR|CRITICAL WARNING"
    } | Select-Object -Last 80)) {
        Write-SummaryLine "CONFIG_MATCH=$line"
    }
}

Write-SummaryLine "ILA_START=$(Get-Date -Format o)"
$ilaExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments $ilaArgs -LogPath $ilaLog -TimeoutSeconds 1200
Write-SummaryLine "ILA_EXIT=$ilaExit"
if ($ilaExit -ne 0) {
    Write-SummaryLine "P0_ACK_ONLY_BUILD_END $(Get-Date -Format o)"
    exit $ilaExit
}
if (Test-Path -LiteralPath $ilaLog) {
    foreach ($line in (Get-Content -LiteralPath $ilaLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "ILA2:|ADD_2LANE_PHY_ILA_DONE|ERROR|CRITICAL WARNING"
    } | Select-Object -Last 80)) {
        Write-SummaryLine "ILA_MATCH=$line"
    }
}

Write-SummaryLine "BITSTREAM_START=$(Get-Date -Format o)"
$bitExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments $bitArgs -LogPath $bitLog -TimeoutSeconds 7200
Write-SummaryLine "BITSTREAM_EXIT=$bitExit"
if ($bitExit -ne 0) {
    Write-SummaryLine "P0_ACK_ONLY_BUILD_END $(Get-Date -Format o)"
    exit $bitExit
}
if (Test-Path -LiteralPath $bitLog) {
    foreach ($line in (Get-Content -LiteralPath $bitLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "SYNTH_STATUS|IMPL_STATUS|BITSTREAM_FILE|BITSTREAM_COPY|DEBUG_PROBES_FILE|BUILD_CURRENT_BITSTREAM_DONE|ERROR|CRITICAL WARNING"
    } | Select-Object -Last 80)) {
        Write-SummaryLine "BITSTREAM_MATCH=$line"
    }
}

if (-not $SkipVitisBuild) {
    Write-SummaryLine "VITIS_START=$(Get-Date -Format o)"
    $vitisExit = Invoke-LoggedProcess -FilePath $XsctPath -Arguments $vitisArgs -LogPath $vitisLog -TimeoutSeconds 2400
    Write-SummaryLine "VITIS_EXIT=$vitisExit"
    if ($vitisExit -ne 0) {
        Write-SummaryLine "P0_ACK_ONLY_BUILD_END $(Get-Date -Format o)"
        exit $vitisExit
    }
    if (Test-Path -LiteralPath $vitisLog) {
        foreach ($line in (Get-Content -LiteralPath $vitisLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "Using compile flags|Built ELF|ERROR"
        } | Select-Object -Last 40)) {
            Write-SummaryLine "VITIS_MATCH=$line"
        }
    }
} else {
    Write-SummaryLine "VITIS_SKIPPED=1"
}

Copy-ArtifactIfPresent -Source $bitPath -Name "design_shiboqi_wrapper.bit"
Copy-ArtifactIfPresent -Source $ltxPath -Name "design_shiboqi_wrapper.ltx"
Copy-ArtifactIfPresent -Source $xsaPath -Name "design_shiboqi_wrapper.xsa"
if (-not $SkipVitisBuild) {
    Copy-ArtifactIfPresent -Source $elfPath -Name "rf_comm_ps_ps_loopback.elf"
}

$manifestPath = Join-Path $artifactDir "p0_ack_only_manifest.txt"
@(
    "P0_ACK_ONLY_MANIFEST_BEGIN $(Get-Date -Format o)"
    "mode=$Mode"
    "summary=$summaryLog"
    "config_log=$configLog"
    "ila_log=$ilaLog"
    "bitstream_log=$bitLog"
    "vitis_log=$vitisLog"
    "constraint_sha256=$constraintHash"
    ($envMap.Keys | Sort-Object | ForEach-Object { "env.$_=$($envMap[$_])" })
    "P0_ACK_ONLY_MANIFEST_END $(Get-Date -Format o)"
) | Out-File -FilePath $manifestPath -Encoding ascii
Write-SummaryLine "MANIFEST=$manifestPath"
Write-SummaryLine "P0_ACK_ONLY_BUILD_PASS=1"
Write-SummaryLine "P0_ACK_ONLY_BUILD_END $(Get-Date -Format o)"
exit 0
