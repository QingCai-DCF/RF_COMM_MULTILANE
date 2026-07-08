param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [string[]]$TriggerModes = @("a_tx_lane0", "a_tx_lane1", "b_tx_lane0", "b_tx_lane1"),
    [int]$PerRunTimeoutSeconds = 480,
    [int]$MaxTfduWindowSeconds = 300,
    [int]$WaitPollSeconds = 15,
    [int]$MaxWaitMinutes = 0,
    [string]$PythonPath = "python",
    [switch]$DryRun,
    [switch]$SkipArtifactGuard,
    [switch]$AutoBuildPsElfPerTrigger,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "p1_lane_mapping_matrix_safe_$stamp.summary.txt"
$artifactGuardLog = Join-Path $reportsDir "p1_lane_mapping_matrix_safe_$stamp.artifact_guard.log"
$preflightLog = Join-Path $reportsDir "p1_lane_mapping_matrix_safe_$stamp.preflight.log"
$matrixLog = Join-Path $reportsDir "p1_lane_mapping_matrix_safe_$stamp.matrix.log"

$artifactGuardScript = Join-Path $repoRoot "tools\check_active_artifact_stage.py"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$matrixScript = Join-Path $repoRoot "tools\run_2lane_matrix_safe.ps1"
$captureTcl = Join-Path $repoRoot "tools\capture_2lane_ila_once.tcl"
$analyzerScript = Join-Path $repoRoot "tools\analyze_2lane_ila_csv.py"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"

foreach ($path in @($artifactGuardScript, $preflightScript, $matrixScript, $captureTcl, $analyzerScript, $shutdownTcl, $VivadoPath, $XsctPath)) {
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

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-ContentWithRetry -Path $summaryLog -Value $Line
}

function Invoke-EmergencyShutdown {
    param([string]$Reason)

    $safeReason = $Reason -replace "[^A-Za-z0-9_.-]", "_"
    $emergencyStamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
    $outLog = Join-Path $reportsDir "emergency_shutdown_p1_${safeReason}_$emergencyStamp.out.log"
    $errLog = Join-Path $reportsDir "emergency_shutdown_p1_${safeReason}_$emergencyStamp.err.log"
    $combinedLog = Join-Path $reportsDir "emergency_shutdown_p1_${safeReason}_$emergencyStamp.log"

    [void](Write-SummaryLine "EMERGENCY_SHUTDOWN_START reason=$Reason out=$outLog")
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
        [void](Write-SummaryLine "EMERGENCY_SHUTDOWN_TIMEOUT reason=$Reason")
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
    [void](Write-SummaryLine "EMERGENCY_SHUTDOWN_RESULT reason=$Reason exit=$exitCode programmed=$programmed log=$combinedLog")
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

function Normalize-List {
    param([string[]]$Items)
    $out = @()
    foreach ($item in $Items) {
        foreach ($part in ($item -split ",")) {
            $trimmed = $part.Trim()
            if ($trimmed -ne "") {
                $out += $trimmed
            }
        }
    }
    return $out
}

function Quote-Arg {
    param([string]$Text)
    if ($Text -match "[\s`"]") {
        return '"' + ($Text -replace '"', '\"') + '"'
    }
    return $Text
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

$modes = Normalize-List -Items $TriggerModes

Set-ContentWithRetry -Path $summaryLog -Value "P1_LANE_MAPPING_MATRIX_SAFE_BEGIN $(Get-Date -Format o)"
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "TRIGGER_MODES=$($modes -join ',')"
Write-SummaryLine "WAIT_POLL_SECONDS=$WaitPollSeconds"
Write-SummaryLine "MAX_WAIT_MINUTES=$MaxWaitMinutes"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "SKIP_ARTIFACT_GUARD=$([int]$SkipArtifactGuard.IsPresent)"
Write-SummaryLine "AUTO_BUILD_PS_ELF_PER_TRIGGER=$([int]$AutoBuildPsElfPerTrigger.IsPresent)"
Write-SummaryLine "ARTIFACT_GUARD_LOG=$artifactGuardLog"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "MATRIX_LOG=$matrixLog"
Write-SummaryLine "P1_SCOPE=P1-1 lane mapping raw-pulse matrix"
Write-SummaryLine "P1_EXPECTED_LINKS=A_TO_B_LANE0,A_TO_B_LANE1,B_TO_A_LANE0,B_TO_A_LANE1 plus cross-lane absence checks in analyzer"
Write-SummaryLine "NO_FPGA_PROGRAMMING_BEFORE_ARTIFACT_GUARD_PASS=1"
Write-SummaryLine "NO_FPGA_PROGRAMMING_BEFORE_PREFLIGHT_PASS=1"
Write-SummaryLine "NO_TFDU_DRIVE_BEFORE_PREFLIGHT_PASS=1"

$artifactGuardArgs = @(
    $artifactGuardScript,
    "--expect",
    "P1_2LANE_ILA_BASELINE"
)

$preflightArgs = @(
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
)

$matrixArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $matrixScript,
    "-ComPort",
    $ComPort,
    "-BaudRate",
    [string]$BaudRate,
    "-XsctPath",
    $XsctPath,
    "-VivadoPath",
    $VivadoPath,
    "-TriggerModes"
    ($modes -join ",")
) + @(
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz,
    "-PerRunTimeoutSeconds",
    [string]$PerRunTimeoutSeconds,
    "-MaxTfduWindowSeconds",
    [string]$MaxTfduWindowSeconds,
    "-WaitPollSeconds",
    [string]$WaitPollSeconds,
    "-MaxWaitMinutes",
    [string]$MaxWaitMinutes
)
if ($AutoBuildPsElfPerTrigger) {
    $matrixArgs += "-AutoBuildPsElfPerTrigger"
}
if ($StopOnFail) {
    $matrixArgs += "-StopOnFail"
}

Write-SummaryLine "ARTIFACT_GUARD_COMMAND=$PythonPath $((@($artifactGuardArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "PREFLIGHT_COMMAND=powershell $((@($preflightArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "MATRIX_COMMAND=powershell $((@($matrixArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"

if ($DryRun) {
    Write-SummaryLine "WAIT_SKIPPED_DRY_RUN=1"
    Write-SummaryLine "DRY_RUN_NO_ARTIFACT_GUARD_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_PREFLIGHT_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_DONE=1"
    Write-SummaryLine "P1_LANE_MAPPING_MATRIX_SAFE_END $(Get-Date -Format o)"
    exit 0
}

if ($SkipArtifactGuard) {
    Write-SummaryLine "ARTIFACT_GUARD_SKIPPED=1"
} else {
    Wait-ExternalBlockers -Phase "before_artifact_guard" -NeedComPort $false
    Write-SummaryLine "ARTIFACT_GUARD_START=$(Get-Date -Format o)"
    $artifactGuardExit = Invoke-LoggedProcess -FilePath $PythonPath -Arguments $artifactGuardArgs -LogPath $artifactGuardLog -TimeoutSeconds 120
    Write-SummaryLine "ARTIFACT_GUARD_EXIT=$artifactGuardExit"
    $artifactGuardText = ""
    if (Test-Path -LiteralPath $artifactGuardLog) {
        $artifactGuardText = Get-Content -LiteralPath $artifactGuardLog -Raw -ErrorAction SilentlyContinue
        if ($null -eq $artifactGuardText) {
            $artifactGuardText = ""
        }
        foreach ($line in (($artifactGuardText -split "`r?`n") | Where-Object {
            $_ -match "ACTIVE_ARTIFACT_STAGE|ACTIVE_ARTIFACT_GUARD_EXPECT|ACTIVE_ARTIFACT_GUARD_RESULT|ACTIVE_ARTIFACT_GUARD_REASON"
        })) {
            Write-SummaryLine "ARTIFACT_GUARD_MATCH=$line"
        }
    }

    $artifactGuardPassed = ($artifactGuardText -match "(?m)^ACTIVE_ARTIFACT_GUARD_RESULT=PASS\b")
    Write-SummaryLine "ARTIFACT_GUARD_PASS_PARSED=$([int]$artifactGuardPassed)"
    if (-not $artifactGuardPassed) {
        Write-SummaryLine "P1_LANE_MAPPING_BLOCKED_ARTIFACT_GUARD=1"
        Write-SummaryLine "P1_LANE_MAPPING_MATRIX_SAFE_END $(Get-Date -Format o)"
        exit 19
    }
}

Wait-ExternalBlockers -Phase "before_p1_preflight" -NeedComPort $true
Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
$preflightExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $preflightArgs -LogPath $preflightLog -TimeoutSeconds 150
Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
$preflightText = ""
if (Test-Path -LiteralPath $preflightLog) {
    $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
    if ($null -eq $preflightText) {
        $preflightText = ""
    }
    foreach ($line in (($preflightText -split "`r?`n") | Where-Object {
        $_ -match "COM_PORT_PRESENT|PNP_DEVICE|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT"
    })) {
        Write-SummaryLine "PREFLIGHT_MATCH=$line"
    }
}

$preflightPassed = ($preflightText -match "HW_PREFLIGHT_RESULT PASS" -and $preflightText -match "HW_PREFLIGHT_ZYNQ")
$preflightEffectiveExit = $preflightExit
$vivadoExitMatch = [regex]::Match($preflightText, "VIVADO_PREFLIGHT_EXIT\s*=\s*(\d+)")
if ($vivadoExitMatch.Success) {
    $preflightEffectiveExit = [int]$vivadoExitMatch.Groups[1].Value
}
Write-SummaryLine "PREFLIGHT_EFFECTIVE_EXIT=$preflightEffectiveExit"
Write-SummaryLine "PREFLIGHT_PASS_PARSED=$([int]$preflightPassed)"
if (-not $preflightPassed) {
    Write-SummaryLine "P1_LANE_MAPPING_BLOCKED_NO_PROGRAMMING=1"
    Write-SummaryLine "P1_LANE_MAPPING_MATRIX_SAFE_END $(Get-Date -Format o)"
    exit 20
}

Wait-ExternalBlockers -Phase "before_p1_matrix" -NeedComPort $true
Write-SummaryLine "MATRIX_START=$(Get-Date -Format o)"
$matrixTimeout = ($PerRunTimeoutSeconds * [Math]::Max(1, $modes.Count)) + 300
$matrixExitRaw = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $matrixArgs -LogPath $matrixLog -TimeoutSeconds $matrixTimeout
$matrixExit = $matrixExitRaw
Write-SummaryLine "MATRIX_EXIT=$matrixExitRaw"
if ($matrixExitRaw -eq 124) {
    $emergencyShutdownExit = Invoke-EmergencyShutdown -Reason "matrix_process_timeout"
    Write-SummaryLine "MATRIX_EMERGENCY_SHUTDOWN_EXIT=$emergencyShutdownExit"
    if ($emergencyShutdownExit -ne 0 -and $matrixExit -eq 0) {
        $matrixExit = 31
    }
}
if ((Test-Path -LiteralPath ($matrixLog + ".err")) -and (Get-Item -LiteralPath ($matrixLog + ".err")).Length -gt 0) {
    foreach ($line in (Get-Content -LiteralPath ($matrixLog + ".err") -ErrorAction SilentlyContinue | Select-Object -First 30)) {
        Write-SummaryLine "MATRIX_STDERR=$line"
    }
    if ($matrixExit -eq 0) {
        Write-SummaryLine "MATRIX_STDERR_NONEMPTY_TREATED_AS_FAIL=1"
        $matrixExit = 98
    }
}
$matrixText = ""
if (Test-Path -LiteralPath $matrixLog) {
    $matrixText = Get-Content -LiteralPath $matrixLog -Raw -ErrorAction SilentlyContinue
    if ($null -eq $matrixText) {
        $matrixText = ""
    }
    foreach ($line in (($matrixText -split "`r?`n") | Where-Object {
        $_ -match "MATRIX_PREFLIGHT|MATRIX_ANALYSIS|MATRIX_OVERALL_EXIT|RUN_RESULT|RUN_DIAGNOSTIC|RUN_ILA_TIMEOUT|RUN_MISSING_ILA_CSV|RUN_SAFETY|LANE2_MATRIX_SAFE_END"
    })) {
        Write-SummaryLine "MATRIX_MATCH=$line"
    }
}
$matrixOverallExitMatch = [regex]::Match($matrixText, "(?m)^MATRIX_OVERALL_EXIT=(\d+)\b")
if ($matrixOverallExitMatch.Success) {
    $matrixReportedOverallExit = [int]$matrixOverallExitMatch.Groups[1].Value
    Write-SummaryLine "MATRIX_REPORTED_OVERALL_EXIT=$matrixReportedOverallExit"
    if ($matrixExit -eq 0 -and $matrixReportedOverallExit -ne 0) {
        Write-SummaryLine "MATRIX_EXIT_OVERRIDDEN_BY_REPORTED_OVERALL_EXIT=1"
        $matrixExit = $matrixReportedOverallExit
    }
}
$diagnosticExits = [regex]::Matches($matrixText, "(?m)^RUN_DIAGNOSTIC .*\beffective_exit=(\d+)\b")
foreach ($diag in $diagnosticExits) {
    $diagExit = [int]$diag.Groups[1].Value
    if ($diagExit -ne 0 -and $matrixExit -eq 0) {
        $matrixExit = $diagExit
    }
}
if ($matrixExit -eq 0 -and $matrixText -match "(?m)^RUN_ILA_TIMEOUT\b") {
    $matrixExit = 3
}
if ($matrixExit -eq 0 -and $matrixText -match "(?m)^RUN_MISSING_ILA_CSV\b") {
    $matrixExit = 4
}
Write-SummaryLine "MATRIX_EFFECTIVE_EXIT=$matrixExit"

Write-SummaryLine "P1_LANE_MAPPING_MATRIX_SAFE_END $(Get-Date -Format o)"
exit $matrixExit
