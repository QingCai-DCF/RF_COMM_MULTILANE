param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$PayloadBytes = 256,
    [int]$StageSeconds = 60,
    [int]$XsctWaitSeconds = 90,
    [int]$HostTimeoutPaddingSeconds = 90,
    [string]$ProfileElf = "",
    [switch]$SkipSoftRecovery,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.summary.txt"
$canonicalLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke.log"
$xsctOutLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.xsct.out.log"
$xsctErrLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.xsct.err.log"
$hostOutLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.host.out.log"
$hostErrLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.host.err.log"
$preflightLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.preflight.log"
$shutdownOutLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.shutdown.out.log"
$shutdownErrLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.shutdown.err.log"
$transcript = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.transcript.log"

$runTcl = Join-Path $repoRoot "software\ps_ps_loopback\run_on_hw.tcl"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$softRecoveryScript = Join-Path $repoRoot "tools\recover_jtag_usb_soft.ps1"
$hostTool = Join-Path $repoRoot "software\host_uart_operator\rf_comm_uart_operator.py"
$workspaceElf = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$backupElf = Join-Path $reportsDir "workspace_elf_before_P4A_01_$stamp.elf"

foreach ($path in @($XsctPath, $VivadoPath, $runTcl, $shutdownTcl, $preflightScript, $hostTool, $workspaceElf)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}
if ($ProfileElf -ne "" -and -not (Test-Path -LiteralPath $ProfileElf)) {
    throw "ProfileElf is missing: $ProfileElf"
}
if ($StageSeconds -lt 1 -or $StageSeconds -gt 600) {
    throw "StageSeconds must be between 1 and 600."
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

"P4A_FAILURE_COUNTER_SMOKE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "PAYLOAD_BYTES=$PayloadBytes"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"
Write-SummaryLine "WORKSPACE_ELF=$workspaceElf"
Write-SummaryLine "PROFILE_ELF=$ProfileElf"
Write-SummaryLine "TRANSCRIPT=$transcript"
Write-SummaryLine "CANONICAL_LOG=$canonicalLog"

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
    $softOutLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.soft_recovery.out.log"
    $softErrLog = Join-Path $reportsDir "P4A_01_failure_counter_smoke_$stamp.soft_recovery.err.log"
    $softExit = Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments $softArgs `
        -StdoutPath $softOutLog `
        -StderrPath $softErrLog `
        -TimeoutSeconds 240
    Write-SummaryLine "SOFT_RECOVERY_EXIT=$softExit"
    Write-SummaryLine "SOFT_RECOVERY_OUT=$softOutLog"
    Write-SummaryLine "SOFT_RECOVERY_ERR=$softErrLog"
}

if (-not $SkipPreflight) {
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
        Write-SummaryLine "P4A_FAILURE_COUNTER_SMOKE_END $(Get-Date -Format o)"
        exit 20
    }
}

$hostProc = $null
$restoreElf = $false
try {
    if ($ProfileElf -ne "") {
        Copy-Item -LiteralPath $workspaceElf -Destination $backupElf -Force
        Copy-Item -LiteralPath $ProfileElf -Destination $workspaceElf -Force
        $restoreElf = $true
        Write-SummaryLine "WORKSPACE_ELF_REPLACED_WITH_PROFILE=1"
        Write-SummaryLine "WORKSPACE_ELF_BACKUP=$backupElf"
    }

    $hostProc = Start-Process -FilePath "python" `
        -ArgumentList @(
            $hostTool,
            "--mode", "p4-failure-smoke",
            "--port", $ComPort,
            "--baud", [string]$BaudRate,
            "--payload-bytes", [string]$PayloadBytes,
            "--stage-seconds", [string]$StageSeconds,
            "--lane-mask", "0x1",
            "--ack-mask", "0x1",
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

    $shutdownExit = Invoke-LoggedProcess `
        -FilePath $VivadoPath `
        -Arguments @("-mode", "batch", "-source", $shutdownTcl) `
        -StdoutPath $shutdownOutLog `
        -StderrPath $shutdownErrLog `
        -TimeoutSeconds 120
    Write-SummaryLine "SHUTDOWN_EXIT=$shutdownExit"

    if ($restoreElf -and (Test-Path -LiteralPath $backupElf)) {
        Copy-Item -LiteralPath $backupElf -Destination $workspaceElf -Force
        Write-SummaryLine "WORKSPACE_ELF_RESTORED=1"
    }
}

if (Test-Path -LiteralPath $transcript) {
    Copy-Item -LiteralPath $transcript -Destination $canonicalLog -Force
    $transcriptText = Get-Content -LiteralPath $transcript -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($transcriptText -split "`r?`n") | Where-Object {
        $_ -match "UARTOP_RESULT command=(START|READ|SHUTDOWN)|UART_OPERATOR_P4_FAILURE_SMOKE_PASS|ERROR"
    })) {
        Write-SummaryLine "TRANSCRIPT_MATCH=$line"
    }
}

Write-SummaryLine "P4A_FAILURE_COUNTER_SMOKE_END $(Get-Date -Format o)"
if (Test-Path -LiteralPath $hostOutLog) {
    $hostOut = Get-Content -LiteralPath $hostOutLog -Raw -ErrorAction SilentlyContinue
    if ($hostOut -match "UART_OPERATOR_P4_FAILURE_SMOKE_PASS=1") {
        Write-SummaryLine "P4A_FAILURE_COUNTER_SMOKE_PASS=1"
        exit 0
    }
}
Write-SummaryLine "P4A_FAILURE_COUNTER_SMOKE_PASS=0"
exit 30
