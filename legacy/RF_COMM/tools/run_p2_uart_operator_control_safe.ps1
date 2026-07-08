param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$PayloadBytes = 256,
    [int]$StageSeconds = 300,
    [int]$XsctWaitSeconds = 90,
    [int]$HostTimeoutPaddingSeconds = 90,
    [switch]$SkipSoftRecovery,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "run_p2_uart_operator_control_safe_$stamp.summary.txt"
$xsctOutLog = Join-Path $reportsDir "xsct_p2_uart_operator_control_$stamp.out.log"
$xsctErrLog = Join-Path $reportsDir "xsct_p2_uart_operator_control_$stamp.err.log"
$hostOutLog = Join-Path $reportsDir "host_p2_uart_operator_control_$stamp.out.log"
$hostErrLog = Join-Path $reportsDir "host_p2_uart_operator_control_$stamp.err.log"
$preflightLog = Join-Path $reportsDir "p2_uart_operator_control_$stamp.preflight.log"
$shutdownOutLog = Join-Path $reportsDir "program_tfdu_shutdown_after_p2_uart_operator_$stamp.out.log"
$shutdownErrLog = Join-Path $reportsDir "program_tfdu_shutdown_after_p2_uart_operator_$stamp.err.log"
$shutdownLog = Join-Path $reportsDir "program_tfdu_shutdown_after_p2_uart_operator_$stamp.log"
$transcript = Join-Path $reportsDir "P2_uart_operator_control_transcript.log"

$runTcl = Join-Path $repoRoot "software\ps_ps_loopback\run_on_hw.tcl"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$softRecoveryScript = Join-Path $repoRoot "tools\recover_jtag_usb_soft.ps1"
$hostTool = Join-Path $repoRoot "software\host_uart_operator\rf_comm_uart_operator.py"
$workspaceElf = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$operatorElf = Get-ChildItem -LiteralPath (Join-Path $repoRoot "deliverables\p2_uart_operator") -Filter "rf_comm_ps_ps_loopback_uart_operator_*.elf" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$backupElf = Join-Path $reportsDir "workspace_elf_before_p2_uart_operator_$stamp.elf"

foreach ($path in @($XsctPath, $VivadoPath, $runTcl, $shutdownTcl, $preflightScript, $hostTool, $workspaceElf)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}
if ($null -eq $operatorElf) {
    throw "No preserved P2 UART operator ELF found under deliverables\p2_uart_operator"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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

"P2_UART_OPERATOR_CONTROL_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "PAYLOAD_BYTES=$PayloadBytes"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"
Write-SummaryLine "SKIP_SOFT_RECOVERY=$([int]$SkipSoftRecovery.IsPresent)"
Write-SummaryLine "WORKSPACE_ELF=$workspaceElf"
Write-SummaryLine "OPERATOR_ELF=$($operatorElf.FullName)"
Write-SummaryLine "TRANSCRIPT=$transcript"

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
    $softOutLog = Join-Path $reportsDir "p2_uart_operator_soft_recovery_$stamp.out.log"
    $softErrLog = Join-Path $reportsDir "p2_uart_operator_soft_recovery_$stamp.err.log"
    Write-SummaryLine "SOFT_RECOVERY_SCRIPT=$softRecoveryScript"
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

if (-not $SkipPreflight) {
    Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
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
        -StderrPath ($preflightLog + ".err") `
        -TimeoutSeconds 180
    Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
    $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($preflightText -split "`r?`n") | Where-Object { $_ -match "COM_PORT_PRESENT|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT" })) {
        Write-SummaryLine "PREFLIGHT_MATCH=$line"
    }
    if ($preflightText -notmatch "HW_PREFLIGHT_RESULT PASS" -or $preflightText -notmatch "HW_PREFLIGHT_ZYNQ") {
        Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
        Write-SummaryLine "P2_UART_OPERATOR_CONTROL_SAFE_END $(Get-Date -Format o)"
        exit 20
    }
}

$hostProc = $null
$shutdownExit = $null
try {
    Copy-Item -LiteralPath $workspaceElf -Destination $backupElf -Force
    Copy-Item -LiteralPath $operatorElf.FullName -Destination $workspaceElf -Force
    Write-SummaryLine "WORKSPACE_ELF_REPLACED_WITH_OPERATOR=1"

    $hostProc = Start-Process -FilePath "python" `
        -ArgumentList @(
            $hostTool,
            "--port", $ComPort,
            "--baud", [string]$BaudRate,
            "--payload-bytes", [string]$PayloadBytes,
            "--stage-seconds", [string]$StageSeconds,
            "--transcript", $transcript
        ) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $hostOutLog `
        -RedirectStandardError $hostErrLog `
        -WindowStyle Hidden `
        -PassThru
    Write-SummaryLine "HOST_STARTED_PID=$($hostProc.Id)"
    Start-Sleep -Seconds 1

    $xsctExit = Invoke-LoggedProcess `
        -FilePath $XsctPath `
        -Arguments @($runTcl) `
        -StdoutPath $xsctOutLog `
        -StderrPath $xsctErrLog `
        -TimeoutSeconds $XsctWaitSeconds
    Write-SummaryLine "XSCT_EXIT=$xsctExit"

    $hostTimeout = $StageSeconds + $HostTimeoutPaddingSeconds
    $hostDone = $hostProc.WaitForExit($hostTimeout * 1000)
    if (-not $hostDone) {
        Stop-Process -Id $hostProc.Id -Force -ErrorAction SilentlyContinue
        Write-SummaryLine "HOST_TIMEOUT_KILLED=1"
        $hostExit = 124
    } else {
        $hostProc.Refresh()
        $hostExit = $hostProc.ExitCode
    }
    Write-SummaryLine "HOST_EXIT=$hostExit"
} finally {
    if ($hostProc -and -not $hostProc.HasExited) {
        Stop-Process -Id $hostProc.Id -Force -ErrorAction SilentlyContinue
    }

    $shutdownAttempt = 1
    $shutdownExit = 125
    while ($shutdownAttempt -le 2) {
        $attemptOut = $shutdownOutLog
        $attemptErr = $shutdownErrLog
        if ($shutdownAttempt -gt 1) {
            $attemptOut = $shutdownOutLog -replace "\.out\.log$", "_attempt$shutdownAttempt.out.log"
            $attemptErr = $shutdownErrLog -replace "\.err\.log$", "_attempt$shutdownAttempt.err.log"
        }

        Write-SummaryLine "SHUTDOWN_ATTEMPT_${shutdownAttempt}_START=$(Get-Date -Format o)"
        Write-SummaryLine "SHUTDOWN_ATTEMPT_${shutdownAttempt}_STDOUT_LOG=$attemptOut"
        Write-SummaryLine "SHUTDOWN_ATTEMPT_${shutdownAttempt}_STDERR_LOG=$attemptErr"
        $shutdownExit = Invoke-LoggedProcess `
            -FilePath $VivadoPath `
            -Arguments @("-mode", "batch", "-source", $shutdownTcl) `
            -StdoutPath $attemptOut `
            -StderrPath $attemptErr `
            -TimeoutSeconds 120
        Write-SummaryLine "SHUTDOWN_ATTEMPT_${shutdownAttempt}_EXIT=$shutdownExit"
        if ($shutdownExit -eq 0) {
            break
        }
        if ($shutdownAttempt -ge 2 -or $SkipSoftRecovery -or -not (Test-Path -LiteralPath $softRecoveryScript)) {
            break
        }

        $shutdownSoftOut = Join-Path $reportsDir "p2_uart_operator_shutdown_soft_recovery_$stamp.out.log"
        $shutdownSoftErr = Join-Path $reportsDir "p2_uart_operator_shutdown_soft_recovery_$stamp.err.log"
        $shutdownSoftArgs = @(
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
            $shutdownSoftArgs += "-SkipUsbRestart"
            Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_USB_RESTART_SKIPPED_NOT_ADMIN=1"
        }
        $shutdownSoftExit = Invoke-LoggedProcess `
            -FilePath "powershell.exe" `
            -Arguments $shutdownSoftArgs `
            -StdoutPath $shutdownSoftOut `
            -StderrPath $shutdownSoftErr `
            -TimeoutSeconds 240
        Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_EXIT=$shutdownSoftExit"
        Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_OUT=$shutdownSoftOut"
        Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_ERR=$shutdownSoftErr"
        $shutdownAttempt++
    }
    Write-SummaryLine "SHUTDOWN_ATTEMPTS=$shutdownAttempt"
    Write-SummaryLine "SHUTDOWN_EXIT=$shutdownExit"
    @(
        "STDOUT:"
        if (Test-Path -LiteralPath $shutdownOutLog) { Get-Content -LiteralPath $shutdownOutLog -ErrorAction SilentlyContinue }
        "STDERR:"
        if (Test-Path -LiteralPath $shutdownErrLog) { Get-Content -LiteralPath $shutdownErrLog -ErrorAction SilentlyContinue }
    ) | Out-File -FilePath $shutdownLog -Encoding ascii

    if (Test-Path -LiteralPath $backupElf) {
        Copy-Item -LiteralPath $backupElf -Destination $workspaceElf -Force
        Write-SummaryLine "WORKSPACE_ELF_RESTORED=1"
    }
}

if (Test-Path -LiteralPath $transcript) {
    $transcriptText = Get-Content -LiteralPath $transcript -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($transcriptText -split "`r?`n") | Where-Object { $_ -match "UART_OPERATOR_CONTROL_PASS|UART_OPERATOR_CONTROL_FAILURE" })) {
        Write-SummaryLine "TRANSCRIPT_MATCH=$line"
    }
}

Write-SummaryLine "P2_UART_OPERATOR_CONTROL_SAFE_END $(Get-Date -Format o)"

if ($shutdownExit -ne 0) {
    throw "Shutdown programming failed, see $shutdownLog"
}
if (Test-Path -LiteralPath $transcript) {
    $transcriptText = Get-Content -LiteralPath $transcript -Raw -ErrorAction SilentlyContinue
    if ($transcriptText -match "UART_OPERATOR_CONTROL_PASS=1") {
        exit 0
    }
}
exit 30
