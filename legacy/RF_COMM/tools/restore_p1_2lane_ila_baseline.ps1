param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [int]$Jobs = 16,
    [string]$PythonPath = "python",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.summary.txt"
$configureLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.configure.log"
$ilaLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.ila.log"
$bitstreamLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.bitstream.log"
$psBuildLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.psbuild.log"
$bootLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.boot.log"
$manifestLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.manifest.log"
$guardLog = Join-Path $reportsDir "restore_p1_2lane_ila_baseline_$stamp.guard.log"

$configureTcl = Join-Path $repoRoot "tools\configure_lane0_ab_hw_loopback.tcl"
$ilaTcl = Join-Path $repoRoot "tools\add_2lane_phy_ila.tcl"
$bitstreamTcl = Join-Path $repoRoot "tools\build_current_bitstream.tcl"
$psBuildScript = Join-Path $repoRoot "tools\build_psps_trigger_elf.ps1"
$bootBuildScript = Join-Path $repoRoot "software\ps_ps_loopback\build_boot_image.ps1"
$pspsBootBin = Join-Path $repoRoot "software\_boot_ps_ps_loopback\BOOT.BIN"
$activeBootBin = Join-Path $repoRoot "software\_boot\BOOT.BIN"
$manifestScript = Join-Path $repoRoot "tools\build_p1_2lane_ila_baseline_manifest.py"
$guardScript = Join-Path $repoRoot "tools\check_active_artifact_stage.py"
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

foreach ($path in @($VivadoPath, $configureTcl, $ilaTcl, $bitstreamTcl, $psBuildScript, $bootBuildScript, $manifestScript, $guardScript, $constraintPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
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

    try {
        $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
        $proc.ProcessorAffinity = [IntPtr]0xFFFF
    } catch {
        Write-SummaryLine "PROCESS_AFFINITY_WARN=$($_.Exception.Message)"
    }

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
        return 0
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
        Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
        exit $ExitCode
    }
    $text = [string](Get-Content -LiteralPath $LogPath -Raw)
    if ($text -notmatch [regex]::Escape($Marker)) {
        Write-SummaryLine "LOG_MARKER_MISSING log=$LogPath marker=$Marker"
        Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
        exit $ExitCode
    }
}

function Set-P1BaselineEnv {
    $env:VIVADO_MAX_THREADS = [string]$Jobs
    $env:MAKEFLAGS = "-j$Jobs"
    $env:IR_LANE_COUNT = "2"
    $env:IR_B_MODE = "stream_bidir"
    $env:IR_B_SESSION_ID = "0x2203"
    $env:IR_B_RX_LANE_MASK = "3"
    $env:IR_B_EXPECTED_A_LANE_MASK = "3"
    $env:IR_B_TX_LANE_MASK = "3"
    $env:IR_B_ACK_LANE_MASK = "3"
    $env:IR_B2A_ENABLE = "1"
    $env:IR_B2A_FREE_RUN = "0"
    $env:IR_CNT_CHIP_MAX = "7"
    $env:IR_CNT_PREAMBLE = "64"
    $env:IR_RX_PREAMBLE_REALIGN_EDGE = "1"
    $env:IR_MAX_PACKET_BYTES = "255"
    $env:IR_FRAGMENT_BYTES = "255"
    $env:IR_HW_MAX_PACKET_BYTES = "255"
    $env:IR_HW_RX_TRANSFER_BYTES = "255"
}

"RESTORE_P1_2LANE_ILA_BASELINE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "VIVADO_PATH=$VivadoPath"
Write-SummaryLine "JOBS=$Jobs"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
Write-SummaryLine "NO_UART_WRITE=1"
Write-SummaryLine "NO_TFDU_DRIVE=1"
Write-SummaryLine "CONFIGURE_LOG=$configureLog"
Write-SummaryLine "ILA_LOG=$ilaLog"
Write-SummaryLine "BITSTREAM_LOG=$bitstreamLog"
Write-SummaryLine "PS_BUILD_LOG=$psBuildLog"
Write-SummaryLine "BOOT_LOG=$bootLog"
Write-SummaryLine "MANIFEST_LOG=$manifestLog"
Write-SummaryLine "GUARD_LOG=$guardLog"

$constraintHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $constraintPath).Hash
Write-SummaryLine "CONSTRAINT_SHA256=$constraintHash"
if ($constraintHash -ne $expectedConstraintHash) {
    Write-SummaryLine "CONSTRAINT_HASH_MISMATCH=1"
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit 12
}

Set-P1BaselineEnv
foreach ($key in @(
    "VIVADO_MAX_THREADS",
    "MAKEFLAGS",
    "IR_LANE_COUNT",
    "IR_B_MODE",
    "IR_B_SESSION_ID",
    "IR_B_RX_LANE_MASK",
    "IR_B_EXPECTED_A_LANE_MASK",
    "IR_B_TX_LANE_MASK",
    "IR_B_ACK_LANE_MASK",
    "IR_B2A_ENABLE",
    "IR_B2A_FREE_RUN",
    "IR_CNT_CHIP_MAX",
    "IR_CNT_PREAMBLE",
    "IR_MAX_PACKET_BYTES",
    "IR_FRAGMENT_BYTES",
    "IR_HW_MAX_PACKET_BYTES",
    "IR_HW_RX_TRANSFER_BYTES"
)) {
    Write-SummaryLine "BUILD_ENV $key=$([Environment]::GetEnvironmentVariable($key, 'Process'))"
}

if ($DryRun) {
    Write-SummaryLine "DRY_RUN_NO_VIVADO_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_DONE=1"
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit 0
}

Write-SummaryLine "CONFIGURE_START=$(Get-Date -Format o)"
$configureExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @("-mode", "batch", "-notrace", "-source", $configureTcl) -LogPath $configureLog -TimeoutSeconds 900
Write-SummaryLine "CONFIGURE_EXIT=$configureExit"
if ($configureExit -ne 0) {
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit $configureExit
}
Assert-LogMarker -LogPath $configureLog -Marker "CONFIGURE_LANE0_AB_HW_LOOPBACK_DONE" -ExitCode 31

Write-SummaryLine "ILA_START=$(Get-Date -Format o)"
$ilaExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @("-mode", "batch", "-notrace", "-source", $ilaTcl) -LogPath $ilaLog -TimeoutSeconds 600
Write-SummaryLine "ILA_EXIT=$ilaExit"
if ($ilaExit -ne 0) {
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit $ilaExit
}
Assert-LogMarker -LogPath $ilaLog -Marker "ADD_2LANE_PHY_ILA_DONE" -ExitCode 32

$env:VIVADO_DISABLE_IP_CACHE = "1"
$env:VIVADO_SKIP_BD_GENERATE = "1"
$env:VIVADO_SKIP_COMPILE_ORDER = "1"
Write-SummaryLine "BITSTREAM_ENV VIVADO_DISABLE_IP_CACHE=1"
Write-SummaryLine "BITSTREAM_ENV VIVADO_SKIP_BD_GENERATE=1"
Write-SummaryLine "BITSTREAM_ENV VIVADO_SKIP_COMPILE_ORDER=1"

Write-SummaryLine "BITSTREAM_START=$(Get-Date -Format o)"
$bitstreamExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @("-mode", "batch", "-notrace", "-source", $bitstreamTcl) -LogPath $bitstreamLog -TimeoutSeconds 7200
Write-SummaryLine "BITSTREAM_EXIT=$bitstreamExit"
if ($bitstreamExit -ne 0) {
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit $bitstreamExit
}
Assert-LogMarker -LogPath $bitstreamLog -Marker "BUILD_CURRENT_BITSTREAM_DONE" -ExitCode 33

Write-SummaryLine "PS_BUILD_START=$(Get-Date -Format o)"
$psBuildExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $psBuildScript,
    "-TriggerMode",
    "b_tx_nonzero",
    "-PayloadBytes",
    "247",
    "-StageSeconds",
    "70",
    "-StatsIntervalUs",
    "90000000",
    "-MaxPacketBytes",
    "255",
    "-RxTransferBytes",
    "255"
) -LogPath $psBuildLog -TimeoutSeconds 900
Write-SummaryLine "PS_BUILD_EXIT=$psBuildExit"
if ($psBuildExit -ne 0) {
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit $psBuildExit
}
Assert-LogMarker -LogPath $psBuildLog -Marker "BUILD_RESULT=PASS" -ExitCode 35

Write-SummaryLine "BOOT_START=$(Get-Date -Format o)"
$bootExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $bootBuildScript,
    "-Force",
    "-Jobs",
    [string]$Jobs
) -LogPath $bootLog -TimeoutSeconds 300
Write-SummaryLine "BOOT_EXIT=$bootExit"
if ($bootExit -ne 0) {
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit $bootExit
}
Assert-LogMarker -LogPath $bootLog -Marker "PSPS_BOOT_BIN" -ExitCode 36
if (-not (Test-Path -LiteralPath $pspsBootBin)) {
    Write-SummaryLine "PSPS_BOOT_BIN_MISSING=$pspsBootBin"
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit 37
}
Copy-Item -LiteralPath $pspsBootBin -Destination $activeBootBin -Force
Write-SummaryLine "ACTIVE_BOOT_COPIED_FROM=$pspsBootBin"
Write-SummaryLine "ACTIVE_BOOT_COPIED_TO=$activeBootBin"

Write-SummaryLine "MANIFEST_START=$(Get-Date -Format o)"
$manifestExit = Invoke-LoggedProcess -FilePath $PythonPath -Arguments @($manifestScript) -LogPath $manifestLog -TimeoutSeconds 120
Write-SummaryLine "MANIFEST_EXIT=$manifestExit"
if ($manifestExit -ne 0) {
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit $manifestExit
}
Assert-LogMarker -LogPath $manifestLog -Marker "PASS_READY_FOR_P1_MATRIX" -ExitCode 34

Write-SummaryLine "GUARD_START=$(Get-Date -Format o)"
$guardExit = Invoke-LoggedProcess -FilePath $PythonPath -Arguments @($guardScript, "--expect", "P1_2LANE_ILA_BASELINE") -LogPath $guardLog -TimeoutSeconds 120
Write-SummaryLine "GUARD_EXIT=$guardExit"
if (Test-Path -LiteralPath $guardLog) {
    foreach ($line in ((Get-Content -LiteralPath $guardLog -Raw) -split "`r?`n" | Where-Object { $_ -match "ACTIVE_ARTIFACT" })) {
        Write-SummaryLine "GUARD_MATCH=$line"
    }
}
if ($guardExit -ne 0) {
    Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
    exit $guardExit
}

foreach ($artifact in @(
    "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit",
    "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx",
    "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa",
    "software\_boot\BOOT.BIN"
)) {
    $path = Join-Path $repoRoot $artifact
    if (Test-Path -LiteralPath $path) {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
        Write-SummaryLine "ARTIFACT path=$artifact sha256=$hash"
    } else {
        Write-SummaryLine "ARTIFACT_MISSING path=$artifact"
    }
}

Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_DONE=1"
Write-SummaryLine "RESTORE_P1_2LANE_ILA_BASELINE_END $(Get-Date -Format o)"
exit 0
