param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$XsctWaitSeconds = 45,
    [int]$PostStartSeconds = 25,
    [int]$CaptureSeconds = 100,
    [switch]$SkipSoftRecovery,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$uartLog = Join-Path $reportsDir "uart_lane0_hw_loopback_safe_$stamp.log"
$xsctOutLog = Join-Path $reportsDir "xsct_lane0_hw_loopback_safe_$stamp.out.log"
$xsctErrLog = Join-Path $reportsDir "xsct_lane0_hw_loopback_safe_$stamp.err.log"
$shutdownLog = Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_loopback_$stamp.log"
$shutdownOutLog = Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_loopback_$stamp.out.log"
$shutdownErrLog = Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_loopback_$stamp.err.log"
$preflightLog = Join-Path $reportsDir "lane0_hw_loopback_safe_$stamp.preflight.log"
$summaryLog = Join-Path $reportsDir "lane0_hw_loopback_safe_$stamp.summary.txt"

$runTcl = Join-Path $repoRoot "software\ps_ps_loopback\run_on_hw.tcl"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$softRecoveryScript = Join-Path $repoRoot "tools\recover_jtag_usb_soft.ps1"

foreach ($path in @($XsctPath, $VivadoPath, $runTcl, $shutdownTcl, $preflightScript)) {
    if (-not (Test-Path $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -Path $summaryLog -Value $Line -Encoding ascii
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-CmdLoggedProcess {
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

"LANE0_HW_SAFE_RUN_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "UART_LOG=$uartLog"
Write-SummaryLine "XSCT_STDOUT_LOG=$xsctOutLog"
Write-SummaryLine "XSCT_STDERR_LOG=$xsctErrLog"
Write-SummaryLine "SHUTDOWN_LOG=$shutdownLog"
Write-SummaryLine "SHUTDOWN_STDOUT_LOG=$shutdownOutLog"
Write-SummaryLine "SHUTDOWN_STDERR_LOG=$shutdownErrLog"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "XSCT_WAIT_SECONDS=$XsctWaitSeconds"
Write-SummaryLine "POST_START_SECONDS=$PostStartSeconds"
Write-SummaryLine "SKIP_SOFT_RECOVERY=$([int]$SkipSoftRecovery.IsPresent)"
Write-SummaryLine "SKIP_PREFLIGHT=$([int]$SkipPreflight.IsPresent)"

if (-not $SkipSoftRecovery -and -not $SkipPreflight -and (Test-Path -LiteralPath $softRecoveryScript)) {
    $softOutLog = Join-Path $reportsDir "lane0_hw_loopback_soft_recovery_$stamp.out.log"
    $softErrLog = Join-Path $reportsDir "lane0_hw_loopback_soft_recovery_$stamp.err.log"
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
    $softExit = Invoke-CmdLoggedProcess `
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
} elseif (-not $SkipSoftRecovery -and -not $SkipPreflight) {
    Write-SummaryLine "SOFT_RECOVERY_SCRIPT_MISSING=1"
}

if (-not $SkipPreflight) {
    Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
    $preflightProc = Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
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
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $preflightLog `
        -RedirectStandardError ($preflightLog + ".err") `
        -WindowStyle Hidden `
        -PassThru
    $preflightProc.WaitForExit()
    $preflightProc.Refresh()
    $preflightExit = if ($null -eq $preflightProc.ExitCode) { 0 } else { $preflightProc.ExitCode }
    Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
    $preflightText = ""
    if (Test-Path -LiteralPath $preflightLog) {
        $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
        foreach ($line in (Get-Content -LiteralPath $preflightLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "COM_PORT_PRESENT|PNP_DEVICE|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT"
        })) {
            Write-SummaryLine "PREFLIGHT_MATCH=$line"
        }
    }
    $preflightEffectiveExit = $preflightExit
    $vivadoExitMatch = [regex]::Match($preflightText, "VIVADO_PREFLIGHT_EXIT\s*=\s*(\d+)")
    if ($vivadoExitMatch.Success) {
        $preflightEffectiveExit = [int]$vivadoExitMatch.Groups[1].Value
    }
    $preflightPassed = ($preflightText -match "HW_PREFLIGHT_RESULT PASS" -and $preflightText -match "HW_PREFLIGHT_ZYNQ")
    Write-SummaryLine "PREFLIGHT_EFFECTIVE_EXIT=$preflightEffectiveExit"
    Write-SummaryLine "PREFLIGHT_PASS_PARSED=$([int]$preflightPassed)"
    if (-not $preflightPassed) {
        Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
        Write-SummaryLine "LANE0_HW_SAFE_RUN_END $(Get-Date -Format o)"
        exit 20
    }
}

$uartJob = Start-Job -ScriptBlock {
    param($Port, $Rate, $LogPath, $Seconds)

    "UART_CAPTURE_BEGIN $(Get-Date -Format o) port=$Port baud=$Rate" | Out-File -FilePath $LogPath -Encoding ascii

    try {
        $serial = New-Object System.IO.Ports.SerialPort $Port, $Rate, "None", 8, "One"
        $serial.ReadTimeout = 200
        $serial.DtrEnable = $false
        $serial.RtsEnable = $false

        $opened = $false
        for ($attempt = 1; $attempt -le 30 -and -not $opened; $attempt++) {
            try {
                $serial.Open()
                $opened = $true
            } catch {
                Add-Content -Path $LogPath -Value "`r`nUART_OPEN_RETRY attempt=$attempt error=$($_.Exception.Message)" -Encoding ascii
                Start-Sleep -Milliseconds 250
            }
        }
        if (-not $opened) {
            throw "Unable to open $Port after retries"
        }

        $timer = [System.Diagnostics.Stopwatch]::StartNew()
        while ($timer.Elapsed.TotalSeconds -lt $Seconds) {
            $chunk = $serial.ReadExisting()
            if ($chunk.Length -gt 0) {
                Add-Content -Path $LogPath -Value $chunk -NoNewline -Encoding ascii
            }
            Start-Sleep -Milliseconds 50
        }
    } catch {
        Add-Content -Path $LogPath -Value "`r`nUART_CAPTURE_ERROR $($_.Exception.Message)" -Encoding ascii
    } finally {
        if ($serial -and $serial.IsOpen) {
            $serial.Close()
        }
        Add-Content -Path $LogPath -Value "`r`nUART_CAPTURE_END $(Get-Date -Format o)" -Encoding ascii
    }
} -ArgumentList $ComPort, $BaudRate, $uartLog, $CaptureSeconds

$runStart = Get-Date
$shutdownExit = $null
$xsctExit = $null
$xsctTimedOut = $false

try {
    Write-SummaryLine "HW_RUN_START=$($runStart.ToString('o'))"

    $xsctProc = Start-Process -FilePath $XsctPath `
        -ArgumentList @($runTcl) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $xsctOutLog `
        -RedirectStandardError $xsctErrLog `
        -WindowStyle Hidden `
        -PassThru

    $xsctDone = $xsctProc.WaitForExit($XsctWaitSeconds * 1000)
    if ($xsctDone) {
        $xsctProc.Refresh()
        $xsctExit = $xsctProc.ExitCode
        Write-SummaryLine "XSCT_EXIT=$xsctExit"
    } else {
        $xsctTimedOut = $true
        Write-SummaryLine "XSCT_TIMEOUT_KILLED=1"
        Stop-Process -Id $xsctProc.Id -Force -ErrorAction SilentlyContinue
    }

    if ($PostStartSeconds -gt 0) {
        Start-Sleep -Seconds $PostStartSeconds
    }
} finally {
    $shutdownStart = Get-Date
    Write-SummaryLine "SHUTDOWN_START=$($shutdownStart.ToString('o'))"

    $shutdownAttemptCount = 0
    $shutdownExit = 1
    $shutdownMaxAttempts = 2

    for ($attempt = 1; $attempt -le $shutdownMaxAttempts; $attempt++) {
        $shutdownAttemptCount = $attempt
        $attemptSuffix = if ($attempt -eq 1) { "" } else { "_retry$($attempt - 1)" }
        $attemptOutLog = if ($attempt -eq 1) { $shutdownOutLog } else { Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_loopback_${stamp}${attemptSuffix}.out.log" }
        $attemptErrLog = if ($attempt -eq 1) { $shutdownErrLog } else { Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_loopback_${stamp}${attemptSuffix}.err.log" }
        $attemptLog = if ($attempt -eq 1) { $shutdownLog } else { Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_loopback_${stamp}${attemptSuffix}.log" }

        Write-SummaryLine "SHUTDOWN_ATTEMPT_$($attempt)_START=$(Get-Date -Format o)"
        Write-SummaryLine "SHUTDOWN_ATTEMPT_$($attempt)_LOG=$attemptLog"
        Write-SummaryLine "SHUTDOWN_ATTEMPT_$($attempt)_STDOUT_LOG=$attemptOutLog"
        Write-SummaryLine "SHUTDOWN_ATTEMPT_$($attempt)_STDERR_LOG=$attemptErrLog"

        $attemptExit = Invoke-CmdLoggedProcess `
            -FilePath $VivadoPath `
            -Arguments @("-mode", "batch", "-source", $shutdownTcl) `
            -StdoutPath $attemptOutLog `
            -StderrPath $attemptErrLog `
            -TimeoutSeconds 120

        @(
            "STDOUT_ATTEMPT_$($attempt):"
            if (Test-Path $attemptOutLog) { Get-Content -Path $attemptOutLog -ErrorAction SilentlyContinue }
            "STDERR_ATTEMPT_$($attempt):"
            if (Test-Path $attemptErrLog) { Get-Content -Path $attemptErrLog -ErrorAction SilentlyContinue }
        ) | Out-File -FilePath $attemptLog -Encoding ascii

        Write-SummaryLine "SHUTDOWN_ATTEMPT_$($attempt)_END=$(Get-Date -Format o)"
        Write-SummaryLine "SHUTDOWN_ATTEMPT_$($attempt)_EXIT=$attemptExit"

        $attemptText = ""
        if (Test-Path -LiteralPath $attemptLog) {
            $attemptText = Get-Content -LiteralPath $attemptLog -Raw -ErrorAction SilentlyContinue
        }
        if ($attemptExit -eq 0 -or $attemptText -match "TFDU_SHUTDOWN_PROGRAMMED") {
            $shutdownExit = 0
            break
        }

        $shutdownExit = $attemptExit
        if ($attempt -ge $shutdownMaxAttempts) {
            break
        }

        if (-not $SkipSoftRecovery -and (Test-Path -LiteralPath $softRecoveryScript)) {
            $shutdownSoftOutLog = Join-Path $reportsDir "shutdown_soft_recovery_${stamp}_attempt$($attempt + 1).out.log"
            $shutdownSoftErrLog = Join-Path $reportsDir "shutdown_soft_recovery_${stamp}_attempt$($attempt + 1).err.log"
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
            Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_BEFORE_ATTEMPT=$($attempt + 1)"
            $shutdownSoftExit = Invoke-CmdLoggedProcess `
                -FilePath "powershell.exe" `
                -Arguments $shutdownSoftArgs `
                -StdoutPath $shutdownSoftOutLog `
                -StderrPath $shutdownSoftErrLog `
                -TimeoutSeconds 240
            Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_EXIT=$shutdownSoftExit"
            Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_OUT=$shutdownSoftOutLog"
            Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_ERR=$shutdownSoftErrLog"
            if (Test-Path -LiteralPath $shutdownSoftOutLog) {
                foreach ($line in (Get-Content -LiteralPath $shutdownSoftOutLog -ErrorAction SilentlyContinue | Where-Object {
                    $_ -match "POWER_PLAN_|USB_RESTART_|PREFLIGHT_MATCH|PREFLIGHT_EXIT|HW_PREFLIGHT_RESULT|HW_PREFLIGHT_TARGET_COUNT|NO_FPGA|NO_TFDU|JTAG_USB_SOFT_RECOVER_END"
                })) {
                    Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_MATCH=$line"
                }
            }
        } else {
            Write-SummaryLine "SHUTDOWN_SOFT_RECOVERY_SKIPPED_BEFORE_RETRY=1"
        }
    }

    $shutdownEnd = Get-Date
    Write-SummaryLine "SHUTDOWN_END=$($shutdownEnd.ToString('o'))"
    Write-SummaryLine "SHUTDOWN_ATTEMPTS=$shutdownAttemptCount"
    Write-SummaryLine "SHUTDOWN_EXIT=$shutdownExit"
    Write-SummaryLine ("HW_WINDOW_TO_SHUTDOWN_START_SECONDS={0:N1}" -f (($shutdownStart - $runStart).TotalSeconds))
    Write-SummaryLine ("HW_WINDOW_TO_SHUTDOWN_END_SECONDS={0:N1}" -f (($shutdownEnd - $runStart).TotalSeconds))

    Wait-Job -Job $uartJob -Timeout 5 | Out-Null
    if ($uartJob.State -eq "Running") {
        Stop-Job -Job $uartJob -ErrorAction SilentlyContinue
    }
    Receive-Job -Job $uartJob -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $uartJob -Force -ErrorAction SilentlyContinue
}

if (Test-Path $uartLog) {
    $uartText = Get-Content -Path $uartLog -Raw -ErrorAction SilentlyContinue
    $interesting = $uartText -split "`r?`n" | Where-Object {
        $_ -match "PSPS_(INIT_OK|STAGE_BEGIN|STATS|STAGE_SUMMARY|TDM_STATS|TDM_STAGE_SUMMARY|RX_ONLY_STATS|RX_ONLY_SUMMARY|B_RX_ONLY_STATS|B_RX_ONLY_SUMMARY)|RF_COMM PS-PS loopback"
    }
    foreach ($line in ($interesting | Select-Object -Last 20)) {
        Write-SummaryLine "UART_MATCH=$line"
    }
}

if ($null -eq $xsctExit -and (Test-Path $xsctOutLog)) {
    $xsctText = Get-Content -Path $xsctOutLog -Raw -ErrorAction SilentlyContinue
    if ($xsctText -match "PS-PS loopback started") {
        $xsctExit = 0
        Write-SummaryLine "XSCT_EXIT_INFERRED=0"
    }
}

if ($null -eq $shutdownExit -and (Test-Path $shutdownLog)) {
    $shutdownText = Get-Content -Path $shutdownLog -Raw -ErrorAction SilentlyContinue
    if ($shutdownText -match "TFDU_SHUTDOWN_PROGRAMMED") {
        $shutdownExit = 0
        Write-SummaryLine "SHUTDOWN_EXIT_INFERRED=0"
    }
}

Write-SummaryLine "LANE0_HW_SAFE_RUN_END $(Get-Date -Format o)"

if ($shutdownExit -ne 0) {
    throw "Shutdown programming failed, see $shutdownLog"
}

if ($xsctTimedOut) {
    exit 2
}

if ($null -ne $xsctExit -and $xsctExit -ne 0) {
    exit $xsctExit
}

exit 0
