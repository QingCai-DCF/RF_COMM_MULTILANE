param(
    [string]$SnapshotPath = "",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$PerRunTimeoutSeconds = 480,
    [int]$MaxTfduWindowSeconds = 300,
    [int]$WaitPollSeconds = 15,
    [int]$MaxWaitMinutes = 0,
    [string]$PythonPath = "python",
    [switch]$AllowTraffic,
    [switch]$PhysicalAdjusted,
    [string]$PhysicalAdjustmentNote = "",
    [switch]$OverrideRepeatFailureGuard,
    [switch]$DryRun,
    [switch]$WaitOnly,
    [switch]$SkipArtifactGuard,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

if ($SnapshotPath -eq "") {
    $SnapshotPath = Join-Path $reportsDir "2lane_physical_failure_snapshot_current.json"
}

$matrixWrapper = Join-Path $repoRoot "tools\run_p1_lane_mapping_matrix_safe.ps1"
$repeatFailureGuard = Join-Path $repoRoot "tools\check_repeat_physical_failure_guard.py"
foreach ($path in @($SnapshotPath, $matrixWrapper, $repeatFailureGuard)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

$stamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "failed_2lane_links_safe_$stamp.summary.txt"

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

function Get-LinkMode {
    param([string]$Link)
    switch ($Link) {
        "A_TO_B_LANE0" { return "a_tx_lane0" }
        "A_TO_B_LANE1" { return "a_tx_lane1" }
        "B_TO_A_LANE0" { return "b_tx_lane0" }
        "B_TO_A_LANE1" { return "b_tx_lane1" }
        default { return "" }
    }
}

$payload = Get-Content -LiteralPath $SnapshotPath -Raw -Encoding UTF8 | ConvertFrom-Json
$orderedLinks = @("A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1")
$rowsByLink = @{}
foreach ($row in @($payload.rows)) {
    $link = [string]$row.link
    if ($link -ne "") {
        $rowsByLink[$link] = $row
    }
}

$failedLinks = @()
$failedReasons = @()
foreach ($link in $orderedLinks) {
    if (-not $rowsByLink.ContainsKey($link)) {
        continue
    }
    $row = $rowsByLink[$link]
    $status = [string]$row.status
    $classification = [string]$row.classification
    if ($status -ne "PASS" -or $classification -ne "PASS_PHYSICAL_RAW_PULSE") {
        $failedLinks += $link
        $failedReasons += ("{0}:status={1}:class={2}:tx={3}:far_rx={4}:near_rx={5}" -f `
            $link, $status, $classification, $row.tx_pulses, $row.far_rx_pulses, $row.near_rx_pulses)
    }
}

$selectedModes = @()
foreach ($link in $failedLinks) {
    $mode = Get-LinkMode -Link $link
    if ($mode -ne "" -and -not ($selectedModes -contains $mode)) {
        $selectedModes += $mode
    }
}

$realRunRequested = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent)
$effectiveDryRun = -not $realRunRequested

Set-ContentWithRetry -Path $summaryLog -Value "FAILED_2LANE_LINKS_SAFE_BEGIN $(Get-Date -Format o)"
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "SNAPSHOT_PATH=$SnapshotPath"
Write-SummaryLine "SNAPSHOT_OVERALL=$($payload.overall)"
Write-SummaryLine "SNAPSHOT_FAILURES=$($payload.failures)"
Write-SummaryLine "SELECTED_FAILED_LINKS=$($failedLinks -join ',')"
Write-SummaryLine "SELECTED_FAILURE_REASONS=$($failedReasons -join ';')"
Write-SummaryLine "SELECTED_TRIGGER_MODES=$($selectedModes -join ',')"
Write-SummaryLine "ALLOW_TRAFFIC=$([int]$AllowTraffic.IsPresent)"
Write-SummaryLine "PHYSICAL_ADJUSTED=$([int]$PhysicalAdjusted.IsPresent)"
Write-SummaryLine "PHYSICAL_ADJUSTMENT_NOTE=$PhysicalAdjustmentNote"
Write-SummaryLine "OVERRIDE_REPEAT_FAILURE_GUARD=$([int]$OverrideRepeatFailureGuard.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "WAIT_ONLY=$([int]$WaitOnly.IsPresent)"
Write-SummaryLine "EFFECTIVE_DRY_RUN=$([int]$effectiveDryRun)"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "PER_RUN_TIMEOUT_SECONDS=$PerRunTimeoutSeconds"
Write-SummaryLine "MAX_TFDU_WINDOW_SECONDS=$MaxTfduWindowSeconds"
Write-SummaryLine "WAIT_POLL_SECONDS=$WaitPollSeconds"
Write-SummaryLine "MAX_WAIT_MINUTES=$MaxWaitMinutes"
Write-SummaryLine "NO_HARDWARE_PROGRAMMING_UNLESS_ALLOW_TRAFFIC=1"
Write-SummaryLine "NO_UART_WRITE_UNLESS_ALLOW_TRAFFIC=1"
Write-SummaryLine "NO_TFDU_DRIVE_UNLESS_ALLOW_TRAFFIC=1"

if ($WaitOnly) {
    Write-SummaryLine "WAIT_ONLY_TRANSIENT_BLOCKER_CHECK=1"
    Write-SummaryLine "WAIT_ONLY_NEED_COM_PORT=1"
    Write-SummaryLine "WAIT_ONLY_NO_REPEAT_FAILURE_GUARD=1"
    Write-SummaryLine "WAIT_ONLY_NO_CHILD_RETEST=1"
    Wait-ExternalBlockers -Phase "wait_only_transient_blockers" -NeedComPort $true
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "FAILED_2LANE_LINKS_SAFE_END $(Get-Date -Format o)"
    exit 0
}

if ($selectedModes.Count -eq 0) {
    Write-SummaryLine "NO_FAILED_LINKS_TO_RETEST=1"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "FAILED_2LANE_LINKS_SAFE_END $(Get-Date -Format o)"
    exit 0
}

if ($realRunRequested -and $PhysicalAdjusted.IsPresent -and $PhysicalAdjustmentNote.Trim() -eq "") {
    Write-SummaryLine "PHYSICAL_ADJUSTMENT_NOTE_REQUIRED=1"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "FAILED_2LANE_LINKS_SAFE_END $(Get-Date -Format o)"
    exit 26
}

if ($realRunRequested -and -not $PhysicalAdjusted.IsPresent -and -not $OverrideRepeatFailureGuard.IsPresent) {
    $guardStamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
    $guardPrefix = Join-Path $reportsDir "repeat_physical_failure_guard_$guardStamp"
    $guardLog = Join-Path $reportsDir "repeat_physical_failure_guard_$guardStamp.log"
    $guardArgs = @(
        $repeatFailureGuard,
        "--snapshot",
        $SnapshotPath,
        "--links",
        ($failedLinks -join ","),
        "--threshold",
        "3",
        "--out-prefix",
        $guardPrefix
    )
    Write-SummaryLine "REPEAT_FAILURE_GUARD_COMMAND=$PythonPath $((@($guardArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
    $guardProc = Start-Process -FilePath $PythonPath `
        -ArgumentList $guardArgs `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $guardLog `
        -RedirectStandardError ($guardLog + ".err") `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    $guardExit = $guardProc.ExitCode
    if ($null -eq $guardExit) {
        $guardExit = 0
    }
    Write-SummaryLine "REPEAT_FAILURE_GUARD_EXIT=$guardExit"
    if (Test-Path -LiteralPath $guardLog) {
        foreach ($line in (Get-Content -LiteralPath $guardLog -ErrorAction SilentlyContinue | Select-String -Pattern "RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD|NO_HARDWARE|NO_UART|NO_TFDU|WROTE_")) {
            Write-SummaryLine "REPEAT_FAILURE_GUARD_MATCH=$($line.Line)"
        }
    }
    if ($guardExit -ne 0) {
        Write-SummaryLine "REPEAT_FAILURE_GUARD_BLOCKED=1"
        Write-SummaryLine "PHYSICAL_ADJUSTMENT_REQUIRED_BEFORE_REAL_RETEST=1"
        Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
        Write-SummaryLine "NO_UART_WRITE=1"
        Write-SummaryLine "NO_TFDU_DRIVE=1"
        Write-SummaryLine "FAILED_2LANE_LINKS_SAFE_END $(Get-Date -Format o)"
        exit 25
    }
} elseif ($realRunRequested -and $PhysicalAdjusted.IsPresent) {
    Write-SummaryLine "REPEAT_FAILURE_GUARD_BYPASSED_REASON=physical_adjusted"
    Write-SummaryLine "PHYSICAL_ADJUSTMENT_DECLARED_FOR_LINKS=$($failedLinks -join ',')"
} elseif ($realRunRequested -and $OverrideRepeatFailureGuard.IsPresent) {
    Write-SummaryLine "REPEAT_FAILURE_GUARD_BYPASSED_REASON=override"
}

$matrixArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $matrixWrapper,
    "-ComPort",
    $ComPort,
    "-BaudRate",
    [string]$BaudRate,
    "-VivadoPath",
    $VivadoPath,
    "-XsctPath",
    $XsctPath,
    "-HwServerUrl",
    $HwServerUrl,
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz,
    "-TriggerModes",
    ($selectedModes -join ","),
    "-PerRunTimeoutSeconds",
    [string]$PerRunTimeoutSeconds,
    "-MaxTfduWindowSeconds",
    [string]$MaxTfduWindowSeconds,
    "-WaitPollSeconds",
    [string]$WaitPollSeconds,
    "-MaxWaitMinutes",
    [string]$MaxWaitMinutes,
    "-PythonPath",
    $PythonPath,
    "-AutoBuildPsElfPerTrigger",
    "-StopOnFail"
)
if ($SkipArtifactGuard) {
    $matrixArgs += "-SkipArtifactGuard"
}
if ($effectiveDryRun) {
    $matrixArgs += "-DryRun"
}

Write-SummaryLine "RETEST_COMMAND=powershell $((@($matrixArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"

if ($effectiveDryRun) {
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "DRY_RUN_NO_UART_WRITE=1"
    Write-SummaryLine "DRY_RUN_NO_TFDU_DRIVE=1"
    Write-SummaryLine "DRY_RUN_NO_RETEST_EXECUTION=0"
}

if ($realRunRequested) {
    Wait-ExternalBlockers -Phase "before_failed_link_retest" -NeedComPort $true
} else {
    Write-SummaryLine "WAIT_SKIPPED_DRY_RUN=1"
}

$process = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $matrixArgs `
    -WorkingDirectory $repoRoot `
    -NoNewWindow `
    -Wait `
    -PassThru
$exitCode = $process.ExitCode
if ($null -eq $exitCode) {
    $exitCode = 0
}

Write-SummaryLine "RETEST_EXIT=$exitCode"
if ($effectiveDryRun) {
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
} else {
    Write-SummaryLine "REAL_RETEST_REQUESTED=1"
    Write-SummaryLine "CHILD_WRAPPER_ENFORCES_PREFLIGHT_AND_SHUTDOWN=1"
}
Write-SummaryLine "FAILED_2LANE_LINKS_SAFE_END $(Get-Date -Format o)"
exit $exitCode
