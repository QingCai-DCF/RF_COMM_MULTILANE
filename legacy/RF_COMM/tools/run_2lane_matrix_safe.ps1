param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string[]]$TriggerModes = @("a_tx_lane0", "a_tx_lane1", "b_tx_nonzero"),
    [int]$JtagFrequencyHz = 1000000,
    [int]$InitWaitSeconds = 45,
    [int]$ArmWaitSeconds = 35,
    [int]$ElfWaitSeconds = 20,
    [int]$IlaWaitSeconds = 85,
    [int]$CaptureSeconds = 120,
    [int]$PerRunTimeoutSeconds = 260,
    [int]$MaxTfduWindowSeconds = 300,
    [int]$WaitPollSeconds = 15,
    [int]$MaxWaitMinutes = 0,
    [switch]$AutoBuildPsElfPerTrigger,
    [switch]$DryRun,
    [switch]$GuardOnly,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "2lane_matrix_safe_$stamp.summary.txt"
$preflightLog = Join-Path $reportsDir "2lane_matrix_safe_$stamp.preflight.log"
$matrixAnalysisMd = Join-Path $reportsDir "2lane_matrix_safe_$stamp.ila_matrix.md"
$matrixAnalysisJson = Join-Path $reportsDir "2lane_matrix_safe_$stamp.ila_matrix.json"

$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$singleRunScript = Join-Path $repoRoot "tools\run_2lane_hw_prearmed_ila_safe.ps1"
$buildPsElfScript = Join-Path $repoRoot "tools\build_psps_trigger_elf.ps1"
$analyzerScript = Join-Path $repoRoot "tools\analyze_2lane_ila_csv.py"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$autoBuildElfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"

foreach ($path in @($preflightScript, $singleRunScript, $buildPsElfScript, $analyzerScript, $shutdownTcl, $VivadoPath, $XsctPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Test-TransientFileWriteBlock {
    param([System.Exception]$Exception)
    $nativeCode = ($Exception.HResult -band 0xFFFF)
    return (
        ($Exception -is [System.UnauthorizedAccessException]) -or
        ($Exception -is [System.IO.IOException] -and ($nativeCode -eq 32 -or $nativeCode -eq 33))
    )
}

function Write-TextFileWithRetry {
    param(
        [string]$Path,
        [string]$Value,
        [ValidateSet("Append", "Set")][string]$Mode,
        [int]$MaxWaitSeconds = 120
    )

    $start = Get-Date
    $announced = $false
    while ($true) {
        try {
            if ($Mode -eq "Append") {
                Add-Content -LiteralPath $Path -Value $Value -Encoding ascii
            } else {
                Set-Content -LiteralPath $Path -Value $Value -Encoding ascii
            }
            if ($announced) {
                Write-Output "WAIT_FILE_CLEAR path=$Path elapsed_s=$([int]((Get-Date) - $start).TotalSeconds)"
            }
            return
        } catch {
            if (-not (Test-TransientFileWriteBlock -Exception $_.Exception)) {
                throw
            }
            $elapsed = [int]((Get-Date) - $start).TotalSeconds
            if ($elapsed -ge $MaxWaitSeconds) {
                Write-Output "WAIT_FILE_TIMEOUT path=$Path elapsed_s=$elapsed error=$($_.Exception.Message)"
                throw
            }
            if (-not $announced) {
                Write-Output "WAIT_FILE_LOCK path=$Path error=$($_.Exception.Message)"
                $announced = $true
            }
            Start-Sleep -Seconds 1
        }
    }
}

function Add-ContentWithRetry {
    param([string]$Path, [string]$Value)
    Write-TextFileWithRetry -Path $Path -Value $Value -Mode "Append"
}

function Set-ContentWithRetry {
    param([string]$Path, [string]$Value)
    Write-TextFileWithRetry -Path $Path -Value $Value -Mode "Set"
}

function Copy-ItemWithRetry {
    param(
        [string]$Source,
        [string]$Destination,
        [int]$MaxWaitSeconds = 120
    )

    $start = Get-Date
    $announced = $false
    while ($true) {
        try {
            Copy-Item -LiteralPath $Source -Destination $Destination -Force
            if ($announced) {
                Write-Output "WAIT_FILE_COPY_CLEAR source=$Source destination=$Destination elapsed_s=$([int]((Get-Date) - $start).TotalSeconds)"
            }
            return
        } catch {
            if (-not (Test-TransientFileWriteBlock -Exception $_.Exception)) {
                throw
            }
            $elapsed = [int]((Get-Date) - $start).TotalSeconds
            if ($elapsed -ge $MaxWaitSeconds) {
                Write-Output "WAIT_FILE_COPY_TIMEOUT source=$Source destination=$Destination elapsed_s=$elapsed error=$($_.Exception.Message)"
                throw
            }
            if (-not $announced) {
                Write-Output "WAIT_FILE_COPY_LOCK source=$Source destination=$Destination error=$($_.Exception.Message)"
                $announced = $true
            }
            Start-Sleep -Seconds 1
        }
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-ContentWithRetry -Path $summaryLog -Value $Line
}

function Test-ComPortAvailable {
    param(
        [string]$Port,
        [int]$Rate,
        [ref]$Reason
    )
    try {
        $serial = New-Object System.IO.Ports.SerialPort $Port, $Rate, "None", 8, "One"
        $serial.ReadTimeout = 200
        $serial.WriteTimeout = 200
        $serial.DtrEnable = $false
        $serial.RtsEnable = $false
        $serial.Open()
        $serial.Close()
        $Reason.Value = ""
        return $true
    } catch {
        $Reason.Value = $_.Exception.Message
        return $false
    } finally {
        if ($null -ne $serial -and $serial.IsOpen) {
            $serial.Close()
        }
    }
}

function Get-RepoVivadoXsctProcesses {
    $escapedRoot = [regex]::Escape($repoRoot)
    $currentPid = $PID
    return @(Get-CimInstance Win32_Process | Where-Object {
        $command = [string]$_.CommandLine
        $_.ProcessId -ne $currentPid -and
        $command -and
        $command -match $escapedRoot -and
        $command -notmatch "hw_server(\.bat|\.exe)?" -and
        ($_.Name -match "^(vivado|vivado\.bat|xsct|xsct\.bat|cmd)\.exe$" -or $command -match "(vivado|xsct)")
    } | Select-Object ProcessId, Name, CommandLine)
}

function Wait-ExternalBlockers {
    param(
        [string]$Phase,
        [bool]$NeedComPort
    )

    $start = Get-Date
    while ($true) {
        $blockers = @()
        foreach ($proc in (Get-RepoVivadoXsctProcesses)) {
            $shortCommand = [string]$proc.CommandLine
            if ($shortCommand.Length -gt 180) {
                $shortCommand = $shortCommand.Substring(0, 180) + "..."
            }
            $blockers += "process pid=$($proc.ProcessId) name=$($proc.Name) command=$shortCommand"
        }

        if ($NeedComPort) {
            $reason = ""
            if (-not (Test-ComPortAvailable -Port $ComPort -Rate $BaudRate -Reason ([ref]$reason))) {
                $blockers += "com_port $ComPort unavailable: $reason"
            }
        }

        if ($blockers.Count -eq 0) {
            Write-SummaryLine "WAIT_CLEAR phase=$Phase elapsed_s=$([int]((Get-Date) - $start).TotalSeconds)"
            return
        }

        $elapsedMinutes = ((Get-Date) - $start).TotalMinutes
        foreach ($blocker in $blockers) {
            Write-SummaryLine "WAIT_BLOCKED phase=$Phase elapsed_min=$([math]::Round($elapsedMinutes, 1)) blocker=$blocker"
        }
        if ($MaxWaitMinutes -gt 0 -and $elapsedMinutes -ge $MaxWaitMinutes) {
            Write-SummaryLine "WAIT_TIMEOUT phase=$Phase max_wait_min=$MaxWaitMinutes"
            exit 40
        }
        Start-Sleep -Seconds $WaitPollSeconds
    }
}

function Invoke-EmergencyShutdown {
    param(
        [string]$Trigger,
        [string]$Reason
    )

    $safeTrigger = $Trigger -replace "[^A-Za-z0-9_.-]", "_"
    $safeReason = $Reason -replace "[^A-Za-z0-9_.-]", "_"
    $emergencyStamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
    $outLog = Join-Path $reportsDir "emergency_shutdown_${safeTrigger}_${safeReason}_$emergencyStamp.out.log"
    $errLog = Join-Path $reportsDir "emergency_shutdown_${safeTrigger}_${safeReason}_$emergencyStamp.err.log"
    $combinedLog = Join-Path $reportsDir "emergency_shutdown_${safeTrigger}_${safeReason}_$emergencyStamp.log"

    [void](Write-SummaryLine "EMERGENCY_SHUTDOWN_START trigger=$Trigger reason=$Reason out=$outLog")
    $proc = Start-Process -FilePath $VivadoPath `
        -ArgumentList @("-mode", "batch", "-source", $shutdownTcl) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -WindowStyle Hidden `
        -PassThru
    $done = $proc.WaitForExit(90000)
    if (-not $done) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        [void](Write-SummaryLine "EMERGENCY_SHUTDOWN_TIMEOUT trigger=$Trigger reason=$Reason")
        $exitCode = 124
    } else {
        $proc.Refresh()
        $exitCode = $proc.ExitCode
    }

    @(
        "STDOUT:"
        if (Test-Path -LiteralPath $outLog) { Get-Content -LiteralPath $outLog -ErrorAction SilentlyContinue }
        "STDERR:"
        if (Test-Path -LiteralPath $errLog) { Get-Content -LiteralPath $errLog -ErrorAction SilentlyContinue }
    ) | Out-File -FilePath $combinedLog -Encoding ascii

    $shutdownText = ""
    if (Test-Path -LiteralPath $combinedLog) {
        $shutdownText = Get-Content -LiteralPath $combinedLog -Raw -ErrorAction SilentlyContinue
        if ($null -eq $shutdownText) {
            $shutdownText = ""
        }
    }
    $programmed = [int]($shutdownText -match "TFDU_SHUTDOWN_PROGRAMMED")
    [void](Write-SummaryLine "EMERGENCY_SHUTDOWN_RESULT trigger=$Trigger reason=$Reason exit=$exitCode programmed=$programmed log=$combinedLog")
    return $exitCode
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

function Get-LogValue {
    param(
        [string]$Text,
        [string]$Key
    )
    $match = [regex]::Match($Text, "(?m)^" + [regex]::Escape($Key) + "=(.+)$")
    if ($match.Success) {
        return $match.Groups[1].Value.Trim()
    }
    return ""
}

function Test-MatrixAnalysisPass {
    param([string]$JsonPath)

    if (-not (Test-Path -LiteralPath $JsonPath)) {
        [void](Write-SummaryLine "MATRIX_ANALYSIS_JSON_MISSING=$JsonPath")
        return $false
    }

    try {
        $items = Get-Content -LiteralPath $JsonPath -Raw | ConvertFrom-Json
    } catch {
        [void](Write-SummaryLine "MATRIX_ANALYSIS_JSON_PARSE_FAIL=$($_.Exception.Message)")
        return $false
    }

    $failures = @()
    foreach ($item in @($items)) {
        $verdict = [string]$item.verdict
        if ($verdict -match "^FAIL_") {
            $failures += ("{0}:{1}:{2}" -f $item.trigger_mode, $item.expected, $verdict)
        }
    }

    if ($failures.Count -gt 0) {
        [void](Write-SummaryLine "MATRIX_ANALYSIS_FAIL_VERDICTS=$($failures -join ',')")
        return $false
    }

    [void](Write-SummaryLine "MATRIX_ANALYSIS_PASS_VERDICTS=1")
    return $true
}

function Get-OptionalSha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return "MISSING"
    }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Backup-AutoBuildElf {
    if (-not $AutoBuildPsElfPerTrigger.IsPresent) {
        return
    }
    $script:AutoBuildElfBackupPath = Join-Path $reportsDir ("2lane_matrix_safe_{0}.original_psps.elf.bak" -f $stamp)
    $script:AutoBuildElfOriginalHash = Get-OptionalSha256 -Path $autoBuildElfPath
    $script:AutoBuildElfHadOriginal = (Test-Path -LiteralPath $autoBuildElfPath)
    Write-SummaryLine "AUTOBUILD_ELF_RESTORE_REQUIRED=1"
    Write-SummaryLine "AUTOBUILD_ELF_PATH=$autoBuildElfPath"
    Write-SummaryLine "AUTOBUILD_ELF_ORIGINAL_SHA256=$script:AutoBuildElfOriginalHash"
    if ($script:AutoBuildElfHadOriginal) {
        Copy-ItemWithRetry -Source $autoBuildElfPath -Destination $script:AutoBuildElfBackupPath
        Write-SummaryLine "AUTOBUILD_ELF_BACKUP_PATH=$script:AutoBuildElfBackupPath"
        Write-SummaryLine "AUTOBUILD_ELF_BACKUP_SHA256=$(Get-OptionalSha256 -Path $script:AutoBuildElfBackupPath)"
    } else {
        Write-SummaryLine "AUTOBUILD_ELF_BACKUP_SKIPPED_REASON=original_missing"
    }
}

function Restore-AutoBuildElf {
    if (-not $AutoBuildPsElfPerTrigger.IsPresent) {
        return $true
    }
    if (-not $script:AutoBuildElfHadOriginal) {
        Write-SummaryLine "AUTOBUILD_ELF_RESTORE_SKIPPED_REASON=original_missing"
        return $true
    }
    if (-not (Test-Path -LiteralPath $script:AutoBuildElfBackupPath)) {
        Write-SummaryLine "AUTOBUILD_ELF_RESTORE_FAIL_REASON=backup_missing"
        return $false
    }
    Copy-ItemWithRetry -Source $script:AutoBuildElfBackupPath -Destination $autoBuildElfPath
    $restoredHash = Get-OptionalSha256 -Path $autoBuildElfPath
    Write-SummaryLine "AUTOBUILD_ELF_RESTORED_SHA256=$restoredHash"
    $restoreOk = ($restoredHash -eq $script:AutoBuildElfOriginalHash)
    Write-SummaryLine "AUTOBUILD_ELF_RESTORE_OK=$([int]$restoreOk)"
    return $restoreOk
}

function Normalize-TriggerModes {
    param([string[]]$RawModes)
    $modes = @()
    foreach ($raw in $RawModes) {
        foreach ($part in ($raw -split ",")) {
            $trimmed = $part.Trim()
            if ($trimmed -ne "") {
                $modes += $trimmed
            }
        }
    }
    return $modes
}

function Test-AutoBuildSupportedTrigger {
    param([string]$Mode)
    return ($Mode -eq "a_tx_lane0" -or
            $Mode -eq "a_tx_lane1" -or
            $Mode -eq "b_tx_nonzero" -or
            $Mode -eq "b_tx_lane0" -or
            $Mode -eq "b_tx_lane1")
}

$modes = Normalize-TriggerModes -RawModes $TriggerModes

Set-ContentWithRetry -Path $summaryLog -Value "LANE2_MATRIX_SAFE_BEGIN $(Get-Date -Format o)"
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "TRIGGER_MODES=$($modes -join ',')"
Write-SummaryLine "PER_RUN_TIMEOUT_SECONDS=$PerRunTimeoutSeconds"
Write-SummaryLine "MAX_TFDU_WINDOW_SECONDS=$MaxTfduWindowSeconds"
Write-SummaryLine "WAIT_POLL_SECONDS=$WaitPollSeconds"
Write-SummaryLine "MAX_WAIT_MINUTES=$MaxWaitMinutes"
Write-SummaryLine "AUTO_BUILD_PS_ELF_PER_TRIGGER=$([int]$AutoBuildPsElfPerTrigger.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "GUARD_ONLY=$([int]$GuardOnly.IsPresent)"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "MATRIX_ANALYSIS_MD=$matrixAnalysisMd"
Write-SummaryLine "MATRIX_ANALYSIS_JSON=$matrixAnalysisJson"

if ($DryRun) {
    Write-SummaryLine "WAIT_SKIPPED_DRY_RUN=1"
    Write-SummaryLine "DRY_RUN_NO_PREFLIGHT_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_DONE=1"
    Write-SummaryLine "LANE2_MATRIX_SAFE_END $(Get-Date -Format o)"
    exit 0
}

if ($GuardOnly) {
    Wait-ExternalBlockers -Phase "before_guard_only" -NeedComPort $false
    Write-SummaryLine "WAIT_NO_COM_PORT_REQUIRED_GUARD_ONLY=1"
    Write-SummaryLine "GUARD_ONLY_NO_PREFLIGHT_DONE=1"
    Write-SummaryLine "GUARD_ONLY_NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "GUARD_ONLY_NO_UART_WRITE=1"
    Write-SummaryLine "GUARD_ONLY_NO_TFDU_DRIVE=1"
} else {
    Wait-ExternalBlockers -Phase "before_matrix_preflight" -NeedComPort $true
    Write-SummaryLine "MATRIX_PREFLIGHT_START=$(Get-Date -Format o)"
    $preflightProcessExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $preflightScript,
        "-VivadoPath",
        $VivadoPath,
        "-ComPort",
        $ComPort,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz
    ) -LogPath $preflightLog -TimeoutSeconds 120
    Write-SummaryLine "MATRIX_PREFLIGHT_PROCESS_EXIT=$preflightProcessExit"
    $preflightText = ""
    if (Test-Path -LiteralPath $preflightLog) {
        $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
        foreach ($line in (($preflightText -split "`r?`n") | Where-Object {
            $_ -match "COM_PORT_PRESENT|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT|PNP_DEVICE"
        })) {
            Write-SummaryLine "MATRIX_PREFLIGHT_MATCH=$line"
        }
    }

    $preflightPassed = ($preflightText -match "HW_PREFLIGHT_RESULT PASS" -and $preflightText -match "HW_PREFLIGHT_ZYNQ")
    Write-SummaryLine "MATRIX_PREFLIGHT_PASS_PARSED=$([int]$preflightPassed)"

    if (-not $preflightPassed) {
        Write-SummaryLine "MATRIX_PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
        Write-SummaryLine "LANE2_MATRIX_SAFE_END $(Get-Date -Format o)"
        exit 20
    }
}

$runCsvs = @()
$runSummaries = @()
$overallExit = 0
$script:AutoBuildElfBackupPath = ""
$script:AutoBuildElfOriginalHash = ""
$script:AutoBuildElfHadOriginal = $false
Backup-AutoBuildElf

foreach ($mode in $modes) {
    $runStart = Get-Date
    $runLog = Join-Path $reportsDir ("2lane_matrix_safe_{0}.{1}.run.log" -f $stamp, $mode)
    Write-SummaryLine "RUN_START trigger=$mode time=$($runStart.ToString('o')) log=$runLog"

    if ($AutoBuildPsElfPerTrigger) {
        if (Test-AutoBuildSupportedTrigger -Mode $mode) {
            Wait-ExternalBlockers -Phase "before_autobuild_$mode" -NeedComPort $false
            $buildLog = Join-Path $reportsDir ("2lane_matrix_safe_{0}.{1}.build_psps.log" -f $stamp, $mode)
            Write-SummaryLine "RUN_AUTOBUILD_PS_ELF_START trigger=$mode log=$buildLog"
            $buildExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                $buildPsElfScript,
                "-TriggerMode",
                $mode,
                "-XsctPath",
                $XsctPath
            ) -LogPath $buildLog -TimeoutSeconds 240
            Write-SummaryLine "RUN_AUTOBUILD_PS_ELF_EXIT trigger=$mode exit=$buildExit"
            if (Test-Path -LiteralPath $buildLog) {
                $buildText = Get-Content -LiteralPath $buildLog -Raw -ErrorAction SilentlyContinue
                foreach ($line in (($buildText -split "`r?`n") | Where-Object {
                    $_ -match "BUILD_RESULT|BUILD_EXIT_CODE|TRIGGER_MODE|LANE_MASK|SESSION_ID|ELF_SHA256|NO_HARDWARE_PROGRAMMING|NO_TFDU_DRIVE"
                })) {
                    Write-SummaryLine "RUN_AUTOBUILD_MATCH trigger=$mode $line"
                }
            }
            if ($buildExit -ne 0) {
                if ($overallExit -eq 0) {
                    $overallExit = $buildExit
                }
                if ($StopOnFail) {
                    Write-SummaryLine "RUN_STOP_ON_AUTOBUILD_FAIL trigger=$mode"
                    break
                }
            }
        } else {
            Write-SummaryLine "RUN_AUTOBUILD_PS_ELF_SKIPPED trigger=$mode reason=unsupported_trigger"
        }
    }

    $singleRunArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $singleRunScript,
        "-ComPort",
        $ComPort,
        "-BaudRate",
        [string]$BaudRate,
        "-XsctPath",
        $XsctPath,
        "-VivadoPath",
        $VivadoPath,
        "-TriggerMode",
        $mode,
        "-InitWaitSeconds",
        [string]$InitWaitSeconds,
        "-ArmWaitSeconds",
        [string]$ArmWaitSeconds,
        "-ElfWaitSeconds",
        [string]$ElfWaitSeconds,
        "-IlaWaitSeconds",
        [string]$IlaWaitSeconds,
        "-CaptureSeconds",
        [string]$CaptureSeconds,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz
    )
    if ($GuardOnly) {
        $singleRunArgs += "-GuardOnly"
    }
    if (-not $GuardOnly) {
        Wait-ExternalBlockers -Phase "before_single_run_$mode" -NeedComPort $true
    }
    $singleRunTimeout = $PerRunTimeoutSeconds
    if ($GuardOnly -and $singleRunTimeout -gt 60) {
        $singleRunTimeout = 60
    }
    $processExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $singleRunArgs -LogPath $runLog -TimeoutSeconds $singleRunTimeout

    $emergencyShutdownExit = ""
    if ($processExit -eq 124) {
        $emergencyShutdownExit = Invoke-EmergencyShutdown -Trigger $mode -Reason "single_run_process_timeout"
    }

    $runText = ""
    if (Test-Path -LiteralPath $runLog) {
        $runText = Get-Content -LiteralPath $runLog -Raw -ErrorAction SilentlyContinue
    }

    $ilaCsv = Get-LogValue -Text $runText -Key "ILA_CSV"
    $ilaTimedOut = [int]($runText -match "(?m)^ILA_TIMEOUT_KILLED=1")
    $runStatus = Get-LogValue -Text $runText -Key "RUN_RESULT_STATUS"
    $runExitReported = Get-LogValue -Text $runText -Key "RUN_EXIT_CODE"
    $summaryPath = ""
    $match = [regex]::Match($runText, "(?m)^LANE2_PREARMED_SAFE_RUN_BEGIN.*")
    $ilaCsvMissing = [int]($ilaCsv -eq "" -or -not (Test-Path -LiteralPath $ilaCsv))
    if ($ilaCsvMissing -eq 0) {
        $runCsvs += $ilaCsv
        $summaryPath = $ilaCsv -replace "^(.+\\)ila_(.+)\.csv$", '$1$2.summary.txt'
    }
    if ($summaryPath -ne "" -and (Test-Path -LiteralPath $summaryPath)) {
        $runSummaries += $summaryPath
    }

    $shutdownExit = Get-LogValue -Text $runText -Key "SHUTDOWN_EXIT"
    $shutdownInferred = Get-LogValue -Text $runText -Key "SHUTDOWN_EXIT_INFERRED"
    $tfduWindow = Get-LogValue -Text $runText -Key "HW_WINDOW_TO_SHUTDOWN_END_SECONDS"
    $blocked = [int]($runText -match "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1")
    $effectiveExit = $processExit
    if ($runExitReported -match "^\d+$") {
        $effectiveExit = [int]$runExitReported
    }
    if ($effectiveExit -eq 0 -and $ilaTimedOut -eq 1) {
        $effectiveExit = 3
    }
    if ($effectiveExit -eq 0 -and $ilaCsvMissing -eq 1 -and -not $GuardOnly) {
        $effectiveExit = 4
    }
    if ($effectiveExit -eq 0 -and $runStatus -match "^FAIL_") {
        $effectiveExit = 10
    }

    Write-SummaryLine "RUN_RESULT trigger=$mode process_exit=$processExit blocked_no_programming=$blocked shutdown_exit=$shutdownExit shutdown_inferred=$shutdownInferred tfdu_window_s=$tfduWindow ila_csv=$ilaCsv"
    if ($emergencyShutdownExit -ne "") {
        Write-SummaryLine "RUN_EMERGENCY_SHUTDOWN trigger=$mode exit=$emergencyShutdownExit"
    }
    Write-SummaryLine "RUN_DIAGNOSTIC trigger=$mode effective_exit=$effectiveExit run_status=$runStatus run_exit_reported=$runExitReported ila_timeout=$ilaTimedOut ila_csv_missing=$ilaCsvMissing"
    if ($ilaTimedOut -eq 1) {
        Write-SummaryLine "RUN_ILA_TIMEOUT trigger=$mode"
    }
    if ($ilaCsvMissing -eq 1 -and -not $GuardOnly) {
        Write-SummaryLine "RUN_MISSING_ILA_CSV trigger=$mode ila_csv=$ilaCsv"
    }

    if ($blocked -eq 1) {
        if ($overallExit -eq 0) {
            $overallExit = 20
        }
        if ($StopOnFail) {
            Write-SummaryLine "RUN_STOP_ON_PREFLIGHT_BLOCK trigger=$mode"
            break
        }
    }

    if ($blocked -eq 0 -and -not $GuardOnly) {
        $shutdownOk = (($shutdownExit -eq "0") -or ($shutdownInferred -eq "0") -or ($emergencyShutdownExit -eq 0))
        if (-not $shutdownOk) {
            Write-SummaryLine "RUN_SAFETY_VIOLATION trigger=$mode shutdown_after_run_missing_or_failed=1 shutdown_exit=$shutdownExit shutdown_inferred=$shutdownInferred emergency_shutdown_exit=$emergencyShutdownExit"
            if ($overallExit -eq 0) {
                $overallExit = 31
            }
            if ($StopOnFail) {
                Write-SummaryLine "RUN_STOP_ON_SHUTDOWN_FAIL trigger=$mode"
                break
            }
        }
    }

    if ($tfduWindow -ne "") {
        $windowValue = 0.0
        if ([double]::TryParse(($tfduWindow -replace ",", ""), [ref]$windowValue)) {
            if ($windowValue -gt $MaxTfduWindowSeconds) {
                Write-SummaryLine "RUN_SAFETY_VIOLATION trigger=$mode tfdu_window_s=$tfduWindow limit_s=$MaxTfduWindowSeconds"
                $overallExit = 30
            }
        }
    }

    if ($effectiveExit -ne 0 -and $overallExit -eq 0) {
        $overallExit = $effectiveExit
    }
    if ($StopOnFail -and $effectiveExit -ne 0) {
        Write-SummaryLine "RUN_STOP_ON_FAIL trigger=$mode"
        break
    }
}

if ($runCsvs.Count -gt 0) {
    Write-SummaryLine "MATRIX_ANALYSIS_START=$(Get-Date -Format o)"
    $analysisLog = Join-Path $reportsDir "2lane_matrix_safe_$stamp.analysis.log"
    $analysisArgs = @($analyzerScript) + $runCsvs + @("--out", $matrixAnalysisMd)
    $analysisExit = Invoke-LoggedProcess -FilePath "python.exe" -Arguments $analysisArgs -LogPath $analysisLog -TimeoutSeconds 60
    Write-SummaryLine "MATRIX_ANALYSIS_MD_EXIT=$analysisExit"
    $analysisJsonLog = Join-Path $reportsDir "2lane_matrix_safe_$stamp.analysis_json.log"
    $analysisJsonArgs = @($analyzerScript) + $runCsvs + @("--json", "--out", $matrixAnalysisJson)
    $analysisJsonExit = Invoke-LoggedProcess -FilePath "python.exe" -Arguments $analysisJsonArgs -LogPath $analysisJsonLog -TimeoutSeconds 60
    Write-SummaryLine "MATRIX_ANALYSIS_JSON_EXIT=$analysisJsonExit"
    if (Test-Path -LiteralPath $matrixAnalysisMd) {
        foreach ($line in (Get-Content -LiteralPath $matrixAnalysisMd -Encoding UTF8 -ErrorAction SilentlyContinue | Select-String -Pattern "PASS_|FAIL_|WARN_" | Select-Object -First 40)) {
            Write-SummaryLine "MATRIX_ANALYSIS_MATCH=$($line.Line)"
        }
    }
    if ($analysisExit -ne 0 -and $overallExit -eq 0) {
        $overallExit = $analysisExit
    }
    if ($analysisJsonExit -ne 0 -and $overallExit -eq 0) {
        $overallExit = $analysisJsonExit
    }
    if ($analysisJsonExit -eq 0) {
        $analysisPassResult = @(Test-MatrixAnalysisPass -JsonPath $matrixAnalysisJson)
        $analysisPassed = $false
        if ($analysisPassResult.Count -gt 0) {
            $lastAnalysisResult = $analysisPassResult[$analysisPassResult.Count - 1]
            $analysisPassed = ($lastAnalysisResult -is [bool] -and $lastAnalysisResult)
        }
        Write-SummaryLine "MATRIX_ANALYSIS_PASS_PARSED=$([int]$analysisPassed)"
        if ((-not $analysisPassed) -and ($overallExit -eq 0)) {
            $overallExit = 10
        }
    }
} else {
    Write-SummaryLine "MATRIX_ANALYSIS_SKIPPED_NO_CSV=1"
}

$autoBuildRestoreOk = @(Restore-AutoBuildElf)
if ($autoBuildRestoreOk.Count -gt 0 -and -not [bool]$autoBuildRestoreOk[-1] -and $overallExit -eq 0) {
    $overallExit = 32
}

Write-SummaryLine "MATRIX_OVERALL_EXIT=$overallExit"
Write-SummaryLine "LANE2_MATRIX_SAFE_END $(Get-Date -Format o)"
exit $overallExit
