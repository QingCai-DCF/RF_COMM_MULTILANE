param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$RepeatabilityTarget = 5,
    [int]$PayloadRunsPerSize = 2,
    [switch]$SkipSoftRecovery,
    [switch]$SkipUartOperator,
    [switch]$IgnoreRepeatabilityStopCondition
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "run_p2_remaining_hardware_sequence_safe_$stamp.summary.txt"
$preflightLog = Join-Path $reportsDir "hw_target_preflight_p2_remaining_hardware_sequence_$stamp.out.log"
$preflightErrLog = $preflightLog + ".err"
$artifactOutLog = Join-Path $reportsDir "p2_remaining_artifacts_$stamp.out.log"
$artifactErrLog = Join-Path $reportsDir "p2_remaining_artifacts_$stamp.err.log"

$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$softRecoveryScript = Join-Path $repoRoot "tools\recover_jtag_usb_soft.ps1"
$buildScript = Join-Path $repoRoot "tools\build_psps_trigger_elf.ps1"
$lane0RunScript = Join-Path $repoRoot "tools\run_lane0_hw_once_safe.ps1"
$artifactScript = Join-Path $repoRoot "tools\build_p2_constrained_operational_artifacts.py"
$uartWrapper = Join-Path $repoRoot "tools\run_p2_uart_operator_control_safe.ps1"

foreach ($path in @($preflightScript, $buildScript, $lane0RunScript, $artifactScript, $uartWrapper)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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
        [string]$StdoutPath,
        [string]$StderrPath,
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
    $cmdLine = '"' + $FilePath + '" ' + $argLine + ' > "' + $StdoutPath + '" 2> "' + $StderrPath + '"'
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "cmd.exe"
    $psi.Arguments = '/d /s /c "' + $cmdLine + '"'
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $done = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $done) {
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

function Invoke-P2ArtifactRefresh {
    $exitCode = Invoke-LoggedProcess `
        -FilePath "python" `
        -Arguments @($artifactScript) `
        -StdoutPath $artifactOutLog `
        -StderrPath $artifactErrLog `
        -TimeoutSeconds 120
    Write-SummaryLine "ARTIFACT_REFRESH_EXIT=$exitCode"
    if ($exitCode -ne 0) {
        throw "P2 artifact refresh failed, see $artifactOutLog and $artifactErrLog"
    }
}

function Get-RepeatabilityPassCount {
    $csvPath = Join-Path $reportsDir "P2_lane0_repeatability_matrix.csv"
    if (-not (Test-Path -LiteralPath $csvPath)) {
        return 0
    }
    $rows = Import-Csv -LiteralPath $csvPath
    $count = 0
    for ($idx = $rows.Count - 1; $idx -ge 0; $idx--) {
        if ($rows[$idx].pass -ne "1") {
            break
        }
        $count += 1
    }
    return $count
}

function Get-RepeatabilityStopRun {
    $csvPath = Join-Path $reportsDir "P2_lane0_repeatability_matrix.csv"
    if (-not (Test-Path -LiteralPath $csvPath)) {
        return $null
    }
    $rows = Import-Csv -LiteralPath $csvPath
    $failed = @($rows | Where-Object {
        $sent = [int]$_.sent
        $rxOk = [int]$_.rx_ok
        $txFail = [int]$_.tx_fail
        $shutdownExit = [int]$_.shutdown_exit
        $_.pass -eq "0" -and (
            $sent -ne $rxOk -or
            $txFail -gt 0 -or
            $shutdownExit -ne 0
        )
    })
    if ($failed.Count -eq 0) {
        return $null
    }
    return $failed[-1]
}

function Get-PayloadCleanCount {
    param([int]$PayloadBytes)
    $csvPath = Join-Path $reportsDir "P2_lane0_payload_matrix.csv"
    if (-not (Test-Path -LiteralPath $csvPath)) {
        return 0
    }
    $rows = Import-Csv -LiteralPath $csvPath
    return @($rows | Where-Object { [int]$_.payload_bytes -eq $PayloadBytes -and $_.clean_link_pass -eq "1" }).Count
}

function Build-Lane0Elf {
    param(
        [int]$PayloadBytes,
        [int]$StageSeconds
    )

    $rawBytes = $PayloadBytes + 8
    if ($rawBytes -lt 264) {
        $rawBytes = 264
    }
    Write-SummaryLine "BUILD_LANE0_ELF payload_bytes=$PayloadBytes stage_seconds=$StageSeconds raw_bytes=$rawBytes"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $buildScript `
        -TriggerMode a_tx_lane0 `
        -PayloadBytes $PayloadBytes `
        -StageSeconds $StageSeconds `
        -MaxPacketBytes $rawBytes `
        -RxTransferBytes $rawBytes
    if ($LASTEXITCODE -ne 0) {
        throw "Lane0 ELF build failed for payload $PayloadBytes"
    }
}

function Run-Lane0Hardware {
    param(
        [int]$PostStartSeconds,
        [int]$CaptureSeconds
    )

    & powershell -NoProfile -ExecutionPolicy Bypass -File $lane0RunScript `
        -ComPort $ComPort `
        -BaudRate $BaudRate `
        -XsctPath $XsctPath `
        -VivadoPath $VivadoPath `
        -HwServerUrl $HwServerUrl `
        -JtagFrequencyHz $JtagFrequencyHz `
        -XsctWaitSeconds 90 `
        -PostStartSeconds $PostStartSeconds `
        -CaptureSeconds $CaptureSeconds
    if ($LASTEXITCODE -ne 0) {
        throw "Lane0 hardware run failed with exit code $LASTEXITCODE"
    }
}

"P2_REMAINING_HARDWARE_SEQUENCE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "REPEATABILITY_TARGET=$RepeatabilityTarget"
Write-SummaryLine "PAYLOAD_RUNS_PER_SIZE=$PayloadRunsPerSize"
Write-SummaryLine "SKIP_SOFT_RECOVERY=$([int]$SkipSoftRecovery.IsPresent)"
Write-SummaryLine "SKIP_UART_OPERATOR=$([int]$SkipUartOperator.IsPresent)"
Write-SummaryLine "IGNORE_REPEATABILITY_STOP_CONDITION=$([int]$IgnoreRepeatabilityStopCondition.IsPresent)"

if (-not $SkipSoftRecovery -and (Test-Path -LiteralPath $softRecoveryScript)) {
    $softArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $softRecoveryScript,
        "-VivadoPath",
        $VivadoPath,
        "-ComPort",
        $ComPort,
        "-HwServerUrl",
        $HwServerUrl,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz,
        "-Apply"
    )
    if (-not (Test-IsAdmin)) {
        $softArgs += "-SkipUsbRestart"
        Write-SummaryLine "SOFT_RECOVERY_USB_RESTART_SKIPPED_NOT_ADMIN=1"
    }
    Write-SummaryLine "SOFT_RECOVERY_SCRIPT=$softRecoveryScript"
    $softOutLog = Join-Path $reportsDir "p2_remaining_soft_recovery_$stamp.out.log"
    $softErrLog = Join-Path $reportsDir "p2_remaining_soft_recovery_$stamp.err.log"
    $softExit = Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments $softArgs `
        -StdoutPath $softOutLog `
        -StderrPath $softErrLog `
        -TimeoutSeconds 240
    Write-SummaryLine "SOFT_RECOVERY_EXIT=$softExit"
    Write-SummaryLine "SOFT_RECOVERY_OUT=$softOutLog"
    Write-SummaryLine "SOFT_RECOVERY_ERR=$softErrLog"
    if (Test-Path -LiteralPath $softOutLog) {
        foreach ($line in (Get-Content -LiteralPath $softOutLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "POWER_PLAN_|USB_RESTART_|PREFLIGHT_MATCH|PREFLIGHT_EXIT|HW_PREFLIGHT_RESULT|HW_PREFLIGHT_TARGET_COUNT|NO_FPGA|NO_TFDU|JTAG_USB_SOFT_RECOVER_END"
        })) {
            Write-SummaryLine "SOFT_RECOVERY_MATCH=$line"
        }
    }
} elseif (-not $SkipSoftRecovery) {
    Write-SummaryLine "SOFT_RECOVERY_SCRIPT_MISSING=1"
}

$preflightExit = Invoke-LoggedProcess `
    -FilePath "powershell.exe" `
    -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $preflightScript,
        "-VivadoPath",
        $VivadoPath,
        "-ComPort",
        $ComPort,
        "-HwServerUrl",
        $HwServerUrl,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz
    ) `
    -StdoutPath $preflightLog `
    -StderrPath $preflightErrLog `
    -TimeoutSeconds 180
Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
$preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
foreach ($line in (($preflightText -split "`r?`n") | Where-Object { $_ -match "COM_PORT_PRESENT|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT" })) {
    Write-SummaryLine "PREFLIGHT_MATCH=$line"
}
if ($preflightText -notmatch "HW_PREFLIGHT_RESULT PASS" -or $preflightText -notmatch "HW_PREFLIGHT_ZYNQ") {
    Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
    Invoke-P2ArtifactRefresh
    Write-SummaryLine "P2_REMAINING_HARDWARE_SEQUENCE_END $(Get-Date -Format o)"
    exit 20
}

Invoke-P2ArtifactRefresh

if (-not $IgnoreRepeatabilityStopCondition) {
    $stopRun = Get-RepeatabilityStopRun
    if ($null -ne $stopRun) {
        Write-SummaryLine "P2_STOP_CONDITION_REPEATABILITY_FAILURE=1"
        Write-SummaryLine "P2_STOP_RUN_ID=$($stopRun.run_id)"
        Write-SummaryLine "P2_STOP_SENT=$($stopRun.sent)"
        Write-SummaryLine "P2_STOP_RX_OK=$($stopRun.rx_ok)"
        Write-SummaryLine "P2_STOP_TX_FAIL=$($stopRun.tx_fail)"
        Write-SummaryLine "P2_STOP_NEXT_ACTION=return_to_lane0_G1_health_debug"
        Write-SummaryLine "P2_REMAINING_HARDWARE_SEQUENCE_END $(Get-Date -Format o)"
        exit 30
    }
}

Build-Lane0Elf -PayloadBytes 256 -StageSeconds 300
Invoke-P2ArtifactRefresh
$repeatBefore = Get-RepeatabilityPassCount
Write-SummaryLine "REPEATABILITY_PASS_COUNT_BEFORE=$repeatBefore"
while ((Get-RepeatabilityPassCount) -lt $RepeatabilityTarget) {
    $before = Get-RepeatabilityPassCount
    Write-SummaryLine "RUN_REPEATABILITY before_count=$before target=$RepeatabilityTarget"
    Run-Lane0Hardware -PostStartSeconds 330 -CaptureSeconds 390
    Invoke-P2ArtifactRefresh
    if (-not $IgnoreRepeatabilityStopCondition) {
        $stopRun = Get-RepeatabilityStopRun
        if ($null -ne $stopRun) {
            Write-SummaryLine "P2_STOP_CONDITION_REPEATABILITY_FAILURE=1"
            Write-SummaryLine "P2_STOP_RUN_ID=$($stopRun.run_id)"
            Write-SummaryLine "P2_STOP_SENT=$($stopRun.sent)"
            Write-SummaryLine "P2_STOP_RX_OK=$($stopRun.rx_ok)"
            Write-SummaryLine "P2_STOP_TX_FAIL=$($stopRun.tx_fail)"
            Write-SummaryLine "P2_STOP_NEXT_ACTION=return_to_lane0_G1_health_debug"
            Write-SummaryLine "P2_REMAINING_HARDWARE_SEQUENCE_END $(Get-Date -Format o)"
            exit 30
        }
    }
    $after = Get-RepeatabilityPassCount
    Write-SummaryLine "RUN_REPEATABILITY_AFTER count=$after"
    if ($after -le $before) {
        throw "Repeatability run did not add a clean pass"
    }
}

foreach ($payload in @(64, 128, 256)) {
    $stageSeconds = 120
    $postStartSeconds = 150
    $captureSeconds = 210
    if ($payload -eq 256) {
        $stageSeconds = 300
        $postStartSeconds = 330
        $captureSeconds = 390
    }
    while ((Get-PayloadCleanCount -PayloadBytes $payload) -lt $PayloadRunsPerSize) {
        $before = Get-PayloadCleanCount -PayloadBytes $payload
        Write-SummaryLine "RUN_PAYLOAD_MATRIX payload_bytes=$payload before_count=$before target=$PayloadRunsPerSize"
        Build-Lane0Elf -PayloadBytes $payload -StageSeconds $stageSeconds
        Run-Lane0Hardware -PostStartSeconds $postStartSeconds -CaptureSeconds $captureSeconds
        Invoke-P2ArtifactRefresh
        $after = Get-PayloadCleanCount -PayloadBytes $payload
        Write-SummaryLine "RUN_PAYLOAD_MATRIX_AFTER payload_bytes=$payload count=$after"
        if ($after -le $before) {
            throw "Payload matrix run for $payload bytes did not add a clean pass"
        }
    }
}

Build-Lane0Elf -PayloadBytes 256 -StageSeconds 300
Invoke-P2ArtifactRefresh

if (-not $SkipUartOperator) {
    Write-SummaryLine "RUN_UART_OPERATOR_WRAPPER=1"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $uartWrapper `
        -ComPort $ComPort `
        -BaudRate $BaudRate `
        -XsctPath $XsctPath `
        -VivadoPath $VivadoPath `
        -HwServerUrl $HwServerUrl `
        -JtagFrequencyHz $JtagFrequencyHz `
        -PayloadBytes 256 `
        -StageSeconds 300
    Write-SummaryLine "UART_OPERATOR_WRAPPER_EXIT=$LASTEXITCODE"
    if ($LASTEXITCODE -ne 0) {
        throw "UART operator wrapper did not pass"
    }
    Invoke-P2ArtifactRefresh
}

Write-SummaryLine "P2_REMAINING_HARDWARE_SEQUENCE_END $(Get-Date -Format o)"
exit 0
