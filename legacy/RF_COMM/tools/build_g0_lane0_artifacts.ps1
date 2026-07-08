param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [ValidateSet("a2b_rx", "b2a_rx", "a2b_ack")]
    [string]$Variant = "a2b_rx",
    [int]$Jobs = 16,
    [switch]$SkipVitisBuild,
    [switch]$FullBdGenerate
)

$ErrorActionPreference = "Stop"

$effectiveVariant = if ($Variant -eq "a2b_ack") { "a2b_rx" } else { $Variant }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "g0_lane0_build_$stamp.summary.txt"
$configLog = Join-Path $reportsDir "g0_lane0_build_$stamp.configure.log"
$ilaLog = Join-Path $reportsDir "g0_lane0_build_$stamp.ila.log"
$bitLog = Join-Path $reportsDir "g0_lane0_build_$stamp.bitstream.log"
$vitisLog = Join-Path $reportsDir "g0_lane0_build_$stamp.vitis.log"

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

$skipIlaInsertText = [Environment]::GetEnvironmentVariable("SKIP_ILA_INSERT", "Process")
$skipIlaInsert = $skipIlaInsertText -in @("1", "true", "TRUE", "yes", "YES")
$requireIlaInsertText = [Environment]::GetEnvironmentVariable("REQUIRE_ILA_INSERT", "Process")
$requireIlaInsert = $requireIlaInsertText -in @("1", "true", "TRUE", "yes", "YES")
$ilaSkipReason = if ($skipIlaInsert) { "SKIP_ILA_INSERT" } else { "" }

foreach ($path in @($VivadoPath, $XsctPath, $configureTcl, $ilaTcl, $bitstreamTcl, $vitisTcl, $constraintPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
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

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [int]$TimeoutSeconds
    )

    function ConvertTo-CmdArg {
        param([string]$Value)
        if ($Value -match '[\s&()^|<>"]') {
            return '"' + ($Value -replace '"', '""') + '"'
        }
        return $Value
    }

    $argLine = ($Arguments | ForEach-Object { ConvertTo-CmdArg $_ }) -join " "
    $cmdLine = '"' + $FilePath + '" ' + $argLine + ' > "' + $LogPath + '" 2> "' + $LogPath + '.err"'
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "cmd.exe"
    $psi.Arguments = '/d /s /c "' + $cmdLine + '"'
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    try {
        $proc.WaitForExit()
    } catch {
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 125
    }
    return $proc.ExitCode
}

function Assert-LogMarker {
    param(
        [string]$LogPath,
        [string]$Marker,
        [int]$ExitCode
    )

    if (-not (Test-Path -LiteralPath $LogPath)) {
        Write-SummaryLine "LOG_MARKER_MISSING log=$LogPath marker=$Marker reason=log_missing"
        Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
        exit $ExitCode
    }
    $text = [string](Get-Content -LiteralPath $LogPath -Raw)
    if ($text -notmatch [regex]::Escape($Marker)) {
        Write-SummaryLine "LOG_MARKER_MISSING log=$LogPath marker=$Marker"
        Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
        exit $ExitCode
    }
}

function Test-LogMarker {
    param(
        [string]$LogPath,
        [string]$Marker
    )

    if (-not (Test-Path -LiteralPath $LogPath)) {
        return $false
    }
    $text = [string](Get-Content -LiteralPath $LogPath -Raw)
    return ($text -match [regex]::Escape($Marker))
}

function Set-BuildEnv {
    param([hashtable]$EnvMap)
    foreach ($key in $EnvMap.Keys) {
        [Environment]::SetEnvironmentVariable($key, [string]$EnvMap[$key], "Process")
    }
}

function Write-ArtifactHash {
    param([string]$Path, [string]$Name)
    if (Test-Path -LiteralPath $Path) {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
        Write-SummaryLine "ARTIFACT $Name path=$Path sha256=$hash"
    } else {
        Write-SummaryLine "ARTIFACT_MISSING $Name path=$Path"
    }
}

function Assert-ArtifactExists {
    param(
        [string]$Path,
        [string]$Name,
        [int]$ExitCode
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-SummaryLine "ARTIFACT_REQUIRED_MISSING $Name path=$Path"
        Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
        exit $ExitCode
    }
}

function Get-G0Lane0Env {
    param([string]$BuildVariant)

    $env = @{
        VIVADO_MAX_THREADS = [string]$Jobs
        MAKEFLAGS = "-j$Jobs"
        IR_B_MODE = "stream_bidir"
        IR_LANE_COUNT = "2"
        IR_CNT_CHIP_MAX = "7"
        IR_CNT_PREAMBLE = "64"
        IR_RX_PREAMBLE_REALIGN_EDGE = "1"
        IR_B_SESSION_ID = "0x2201"
        IR_B_RX_LANE_MASK = "1"
        IR_B_EXPECTED_A_LANE_MASK = "1"
        IR_B_TX_LANE_MASK = "1"
        IR_B_ACK_LANE_MASK = "1"
        IR_B_BACKOFF_SLOT_CYCLES = "1024"
        IR_B_START_IDLE_CYCLES = "100000"
        IR_STREAM_TX_REQUIRE_ACK = "1"
        PSPS_PAYLOAD_BYTES = "247"
        PSPS_STAGE_SECONDS = "16"
        PSPS_STATS_INTERVAL_US = "90000000"
        PSPS_RUN_ONCE = "1"
        PSPS_STAGE_LANE_MASK = "0x1"
        PSPS_STAGE_SESSION_ID = "0x2201"
        PSPS_PAYLOAD_LANE_MASK = "0x1"
        PSPS_RX_LANE_MASK = "0x1"
        PSPS_A2B_RX_SUMMARY = "0"
        PSPS_POLL_SLEEP_US = "0"
        IR_TX_POLL_US = "1"
    }

    if ($BuildVariant -eq "b2a_rx") {
        $env.IR_MAX_PACKET_BYTES = "252"
        $env.IR_FRAGMENT_BYTES = "252"
        $env.IR_HW_RX_TRANSFER_BYTES = "252"
        $env.IR_STREAM_TX_REQUIRE_ACK = "1"
        $env.IR_B2A_ENABLE = "1"
        $env.IR_B2A_FREE_RUN = "1"
        $env.IR_B2A_ECHO_ENABLE = "0"
        $env.IR_B_TX_GAP_CYCLES = "150000"
        $env.PSPS_PAYLOAD_BYTES = "244"
        $env.PSPS_STAGE_SECONDS = "70"
        $env.PSPS_STATS_INTERVAL_US = "90000000"
        $env.PSPS_RUN_ONCE = "1"
        $env.PSPS_TX_ONLY = "0"
        $env.PSPS_TDM_BIDIR = "0"
        $env.PSPS_RX_ONLY = "1"
        $env.PSPS_A2B_RX_SUMMARY = "0"
        $env.PSPS_INTER_PACKET_US = "0"
        $env.PSPS_MAX_OUTSTANDING = "0"
    } else {
        $env.IR_B_ACK_LANE_MASK = "0"
        $env.IR_B_DEBUG_SELECT_RX_STATUS = "7"
        $env.IR_B2A_ENABLE = "0"
        $env.IR_B2A_FREE_RUN = "0"
        $env.IR_B2A_ECHO_ENABLE = "0"
        $env.IR_STREAM_TX_REQUIRE_ACK = "0"
        $env.IR_MAX_RETRY = "0"
        $env.IR_FRAG_TIMEOUT_CYCLES = "120000"
        $env.PSPS_WARMUP_STAGES = "0"
        $env.PSPS_TX_ONLY = "1"
        $env.PSPS_TDM_BIDIR = "0"
        $env.PSPS_RX_ONLY = "0"
        $env.PSPS_A2B_RX_SUMMARY = "1"
        $env.PSPS_INTER_PACKET_US = "0"
        $env.PSPS_MAX_OUTSTANDING = "0"
        $env.PSPS_WINDOW_START_GAP_US = "0"
    }

    foreach ($overrideKey in @(
        "IR_B_DEBUG_SELECT_RX_STATUS",
        "IR_CNT_CHIP_MAX",
        "IR_CNT_PREAMBLE",
        "IR_RX_DATA_PHASE_DELAY_CYCLES",
        "IR_RX_DETECT_START_CYCLES",
        "IR_RX_DETECT_END_CYCLES",
        "IR_RX_PREAMBLE_REALIGN_EDGE",
        "IR_B_RX_DETECT_START_CYCLES",
        "IR_B_RX_DETECT_END_CYCLES",
        "IR_B_RX_PREAMBLE_REALIGN_EDGE",
        "IR_STREAM_TX_REQUIRE_ACK",
        "IR_STREAM_PHY_DBG_SELECT",
        "IR_MAX_PACKET_BYTES",
        "IR_FRAGMENT_BYTES",
        "IR_HW_MAX_PACKET_BYTES",
        "IR_HW_RX_TRANSFER_BYTES",
        "IR_MAX_RETRY",
        "IR_FRAG_TIMEOUT_CYCLES",
        "IR_FORCE_SD_SHUTDOWN",
        "IR_GUARD_CYCLES",
        "IR_B_BACKOFF_SLOT_CYCLES",
        "IR_B_START_IDLE_CYCLES",
        "IR_B_RECOVERY_RESET_CYCLES",
        "IR_B_SESSION_ID",
        "IR_B_RX_LANE_MASK",
        "IR_B_EXPECTED_A_LANE_MASK",
        "IR_B_TX_LANE_MASK",
        "IR_B_ACK_LANE_MASK",
        "IR_B2A_ENABLE",
        "IR_B2A_FREE_RUN",
        "IR_B2A_ECHO_ENABLE",
        "IR_B_TX_GAP_CYCLES",
        "PSPS_PAYLOAD_BYTES",
        "PSPS_STAGE_SECONDS",
        "PSPS_STATS_INTERVAL_US",
        "PSPS_RUN_ONCE",
        "PSPS_WARMUP_STAGES",
        "PSPS_TX_ONLY",
        "PSPS_TDM_BIDIR",
        "PSPS_RX_ONLY",
        "PSPS_A2B_RX_SUMMARY",
        "PSPS_INTER_PACKET_US",
        "PSPS_MAX_OUTSTANDING",
        "PSPS_WINDOW_START_GAP_US",
        "PSPS_STAGE_LANE_MASK",
        "PSPS_STAGE_SESSION_ID",
        "PSPS_PAYLOAD_LANE_MASK",
        "PSPS_RX_LANE_MASK",
        "PSPS_POLL_SLEEP_US",
        "PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY",
        "PSPS_IR_ROUNDTRIP_RETRY_GAP_US",
        "IR_TX_POLL_US"
    )) {
        if ($BuildVariant -eq "a2b_rx" -and $overrideKey -in @(
            "IR_B_DEBUG_SELECT_RX_STATUS",
            "IR_B_ACK_LANE_MASK",
            "IR_B2A_ENABLE",
            "IR_B2A_FREE_RUN",
            "IR_B2A_ECHO_ENABLE",
            "IR_STREAM_TX_REQUIRE_ACK"
        )) {
            continue
        }
        $overrideValue = [Environment]::GetEnvironmentVariable($overrideKey, "Process")
        if ($overrideValue) {
            $env[$overrideKey] = $overrideValue
        }
    }

    return $env
}

"G0_LANE0_BUILD_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "REQUESTED_VARIANT=$Variant"
Write-SummaryLine "VARIANT=$effectiveVariant"
if ($Variant -ne $effectiveVariant) {
    Write-SummaryLine "VARIANT_ALIAS_MAPPED=$Variant->$effectiveVariant"
}
Write-SummaryLine "JOBS=$Jobs"
Write-SummaryLine "SKIP_VITIS_BUILD=$([int]$SkipVitisBuild.IsPresent)"
Write-SummaryLine "FULL_BD_GENERATE=$([int]$FullBdGenerate.IsPresent)"
Write-SummaryLine "SKIP_ILA_INSERT=$([int]$skipIlaInsert)"
Write-SummaryLine "REQUIRE_ILA_INSERT=$([int]$requireIlaInsert)"
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
    Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
    exit 12
}

$envMap = Get-G0Lane0Env -BuildVariant $effectiveVariant
foreach ($key in ($envMap.Keys | Sort-Object)) {
    Write-SummaryLine "BUILD_ENV $key=$($envMap[$key])"
}
Set-BuildEnv -EnvMap $envMap

$configExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @("-mode", "batch", "-notrace", "-source", $configureTcl) -LogPath $configLog -TimeoutSeconds 900
Write-SummaryLine "CONFIG_EXIT=$configExit"
if ($configExit -ne 0) {
    Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
    exit $configExit
}
Assert-LogMarker -LogPath $configLog -Marker "CONFIGURE_LANE0_AB_HW_LOOPBACK_DONE" -ExitCode 31

if ($skipIlaInsert) {
    Write-SummaryLine "ILA_SKIPPED=1"
    Write-SummaryLine "ILA_SKIP_REASON=$ilaSkipReason"
} else {
    $ilaExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @("-mode", "batch", "-notrace", "-source", $ilaTcl) -LogPath $ilaLog -TimeoutSeconds 600
    Write-SummaryLine "ILA_EXIT=$ilaExit"
    $ilaReady = ($ilaExit -eq 0) -and (Test-LogMarker -LogPath $ilaLog -Marker "ADD_2LANE_PHY_ILA_DONE")
    if (-not $ilaReady) {
        $ilaRetryLog = $ilaLog -replace '\.ila\.log$', '.ila_retry.log'
        Write-SummaryLine "ILA_RETRY=1"
        Write-SummaryLine "ILA_RETRY_LOG=$ilaRetryLog"
        Start-Sleep -Seconds 3
        $ilaRetryExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @("-mode", "batch", "-notrace", "-source", $ilaTcl) -LogPath $ilaRetryLog -TimeoutSeconds 600
        Write-SummaryLine "ILA_RETRY_EXIT=$ilaRetryExit"
        $ilaReady = ($ilaRetryExit -eq 0) -and (Test-LogMarker -LogPath $ilaRetryLog -Marker "ADD_2LANE_PHY_ILA_DONE")
        if ($ilaReady) {
            Write-SummaryLine "ILA_RETRY_PASSED=1"
        } else {
            Write-SummaryLine "ILA_RETRY_PASSED=0"
        }
    }
    if (-not $ilaReady) {
        if ($requireIlaInsert) {
            Write-SummaryLine "ILA_REQUIRED_FAILED=1"
            Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
            exit 32
        }
        $skipIlaInsert = $true
        $ilaSkipReason = "ILA_INSERT_FAILED_OPTIONAL"
        Write-SummaryLine "ILA_OPTIONAL_FALLBACK=1"
        Write-SummaryLine "ILA_SKIPPED=1"
        Write-SummaryLine "ILA_SKIP_REASON=$ilaSkipReason"
    }
}

[Environment]::SetEnvironmentVariable("VIVADO_DISABLE_IP_CACHE", "1", "Process")
Write-SummaryLine "BITSTREAM_ENV VIVADO_DISABLE_IP_CACHE=1"
if ($FullBdGenerate.IsPresent) {
    [Environment]::SetEnvironmentVariable("VIVADO_SKIP_BD_GENERATE", "0", "Process")
    [Environment]::SetEnvironmentVariable("VIVADO_SKIP_COMPILE_ORDER", "0", "Process")
    Write-SummaryLine "BITSTREAM_ENV VIVADO_SKIP_BD_GENERATE=0"
    Write-SummaryLine "BITSTREAM_ENV VIVADO_SKIP_COMPILE_ORDER=0"
} else {
    [Environment]::SetEnvironmentVariable("VIVADO_SKIP_BD_GENERATE", "1", "Process")
    [Environment]::SetEnvironmentVariable("VIVADO_SKIP_COMPILE_ORDER", "1", "Process")
    Write-SummaryLine "BITSTREAM_ENV VIVADO_SKIP_BD_GENERATE=1"
    Write-SummaryLine "BITSTREAM_ENV VIVADO_SKIP_COMPILE_ORDER=1"
}

if ($skipIlaInsert -and (Test-Path -LiteralPath $ltxPath)) {
    try {
        Remove-Item -LiteralPath $ltxPath -Force
        Write-SummaryLine "LTX_STALE_REMOVED=1 path=$ltxPath"
    } catch {
        Write-SummaryLine "LTX_STALE_REMOVE_WARN=$($_.Exception.Message)"
    }
}

$bitExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @("-mode", "batch", "-notrace", "-source", $bitstreamTcl) -LogPath $bitLog -TimeoutSeconds 7200
Write-SummaryLine "BITSTREAM_EXIT=$bitExit"
if ($bitExit -ne 0) {
    Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
    exit $bitExit
}
Assert-LogMarker -LogPath $bitLog -Marker "BUILD_CURRENT_BITSTREAM_DONE" -ExitCode 33
Assert-ArtifactExists -Path $bitPath -Name "bit" -ExitCode 34
if ($skipIlaInsert) {
    Write-SummaryLine "ARTIFACT_OPTIONAL_NOT_REQUIRED ltx path=$ltxPath reason=$ilaSkipReason"
} else {
    Assert-ArtifactExists -Path $ltxPath -Name "ltx" -ExitCode 35
}
Assert-ArtifactExists -Path $xsaPath -Name "xsa" -ExitCode 36

if (-not $SkipVitisBuild) {
    $vitisExit = Invoke-LoggedProcess -FilePath $XsctPath -Arguments @($vitisTcl) -LogPath $vitisLog -TimeoutSeconds 1200
    Write-SummaryLine "VITIS_EXIT=$vitisExit"
    if ($vitisExit -ne 0) {
        Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
        exit $vitisExit
    }
    Assert-LogMarker -LogPath $vitisLog -Marker "Built ELF:" -ExitCode 37
    Assert-ArtifactExists -Path $elfPath -Name "elf" -ExitCode 38
} else {
    Write-SummaryLine "VITIS_SKIPPED=1"
}

Write-ArtifactHash -Path $bitPath -Name "bit"
if ($skipIlaInsert) {
    Write-SummaryLine "ARTIFACT_SKIPPED ltx path=$ltxPath reason=$ilaSkipReason"
} else {
    Write-ArtifactHash -Path $ltxPath -Name "ltx"
}
Write-ArtifactHash -Path $xsaPath -Name "xsa"
Write-ArtifactHash -Path $elfPath -Name "elf"
Write-SummaryLine "G0_LANE0_BUILD_DONE=1"
Write-SummaryLine "G0_LANE0_BUILD_END $(Get-Date -Format o)"
exit 0
