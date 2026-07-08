param(
    [string]$MdPlanPath = "C:\Users\user\Downloads\P7_P11_2lane_direct_ethernet_only_plan.md",
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
    [switch]$WaitForPhysicalAdjustmentMarker,
    [switch]$WaitForPhysicalAdjustmentMarkerOnly,
    [string]$PhysicalAdjustmentMarkerPath = "",
    [switch]$AllowExistingPhysicalAdjustmentMarker,
    [switch]$OverrideRepeatFailureGuard,
    [switch]$DryRun,
    [switch]$RefreshP7ArtifactsOnly,
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
if ($PhysicalAdjustmentMarkerPath -eq "") {
    $PhysicalAdjustmentMarkerPath = Join-Path $reportsDir "p7_physical_adjustment_ready.txt"
}

$failedLinkWrapper = Join-Path $repoRoot "tools\run_failed_2lane_links_safe.ps1"
$snapshotBuilder = Join-Path $repoRoot "tools\build_2lane_physical_failure_snapshot.py"
$p7RawDeliverablesBuilder = Join-Path $repoRoot "tools\build_p7_2_raw_matrix_deliverables.py"

foreach ($path in @($MdPlanPath, $SnapshotPath, $failedLinkWrapper, $snapshotBuilder, $p7RawDeliverablesBuilder)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

$stamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "md_p7_resume_safe_$stamp.summary.txt"

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

function Invoke-LoggedProcess {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$OutLog,
        [string]$ErrLog
    )

    [void](Write-SummaryLine "${Label}_COMMAND=$FilePath $((@($Arguments) | ForEach-Object { Quote-Arg $_ }) -join ' ')")
    [void](Write-SummaryLine "${Label}_OUT_LOG=$OutLog")
    [void](Write-SummaryLine "${Label}_ERR_LOG=$ErrLog")
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru
    $proc.WaitForExit()
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 0
    }
    return [int]$proc.ExitCode
}

function Invoke-P7PostRetestRefresh {
    param([int]$RetestExit)

    $script:LastP7PostRetestRefreshExit = 0
    Write-SummaryLine "POST_RETEST_REFRESH_ATTEMPTED=1"
    Write-SummaryLine "POST_RETEST_REFRESH_REASON=real_child_retest_completed"
    Write-SummaryLine "POST_RETEST_REFRESH_CHILD_EXIT=$RetestExit"
    $refreshOut = Join-Path $reportsDir "md_p7_resume_safe_$stamp.snapshot_refresh.out.log"
    $refreshErr = Join-Path $reportsDir "md_p7_resume_safe_$stamp.snapshot_refresh.err.log"
    $refreshExit = Invoke-LoggedProcess -Label "SNAPSHOT_REFRESH" -FilePath $PythonPath -Arguments @($snapshotBuilder) -OutLog $refreshOut -ErrLog $refreshErr
    Write-SummaryLine "SNAPSHOT_REFRESH_EXIT=$refreshExit"
    if (Test-Path -LiteralPath $refreshOut) {
        foreach ($line in (Get-Content -LiteralPath $refreshOut -ErrorAction SilentlyContinue | Select-String -Pattern "RF_COMM_2LANE_PHYSICAL_FAILURE_SNAPSHOT|NO_HARDWARE|NO_UART|NO_TFDU|WROTE_")) {
            Write-SummaryLine "SNAPSHOT_REFRESH_MATCH=$($line.Line)"
        }
    }

    if ($refreshExit -ne 0) {
        Write-SummaryLine "P7_01_DELIVERABLE_REFRESH_SKIPPED_REASON=snapshot_refresh_failed"
        $script:LastP7PostRetestRefreshExit = $refreshExit
        return
    }

    $updatedPayload = Read-SnapshotPayload
    $updatedP7Pass = ([string]$updatedPayload.overall -eq 'PASS_ALL_REQUIRED_LINKS')
    Write-SummaryLine "UPDATED_SNAPSHOT_OVERALL=$($updatedPayload.overall)"
    Write-SummaryLine "UPDATED_SNAPSHOT_FAILURES=$($updatedPayload.failures)"
    Write-SummaryLine "UPDATED_P7_2LANE_REMOTE_RAW_MATRIX_PASS=$([int]$updatedP7Pass)"

    $deliverableOut = Join-Path $reportsDir "md_p7_resume_safe_$stamp.p7_01_deliverables.out.log"
    $deliverableErr = Join-Path $reportsDir "md_p7_resume_safe_$stamp.p7_01_deliverables.err.log"
    $deliverableExit = Invoke-LoggedProcess -Label "P7_01_DELIVERABLE_REFRESH" -FilePath $PythonPath -Arguments @($p7RawDeliverablesBuilder, "--snapshot", $SnapshotPath) -OutLog $deliverableOut -ErrLog $deliverableErr
    Write-SummaryLine "P7_01_DELIVERABLE_REFRESH_EXIT=$deliverableExit"
    if (Test-Path -LiteralPath $deliverableOut) {
        foreach ($line in (Get-Content -LiteralPath $deliverableOut -ErrorAction SilentlyContinue | Select-String -Pattern "RF_COMM_P7_2_RAW_MATRIX_DELIVERABLE|NO_HARDWARE|NO_UART|NO_TFDU|P7_3_AUTO_RUN")) {
            Write-SummaryLine "P7_01_DELIVERABLE_REFRESH_MATCH=$($line.Line)"
        }
    }
    if ($updatedP7Pass) {
        Write-SummaryLine "NEXT_MD_STAGE_AFTER_REFRESH=P7.3"
    } else {
        Write-SummaryLine "NEXT_MD_STAGE_AFTER_REFRESH=P7.2"
    }
    Write-SummaryLine "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0"
    $script:LastP7PostRetestRefreshExit = $deliverableExit
}

function Read-PhysicalAdjustmentMarkerNote {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }
    $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 -ErrorAction Stop
    $note = ($text -replace "`r", " " -replace "`n", " ").Trim()
    return $note
}

function Wait-PhysicalAdjustmentMarker {
    param([string]$Path)
    $start = Get-Date
    while ($true) {
        $markerExists = Test-Path -LiteralPath $Path
        $note = ""
        $markerLastWrite = $null
        if ($markerExists) {
            $markerItem = Get-Item -LiteralPath $Path -ErrorAction Stop
            $markerLastWrite = $markerItem.LastWriteTime
            $note = Read-PhysicalAdjustmentMarkerNote -Path $Path
        }
        if ($note.Trim() -ne "") {
            $freshEnough = ($AllowExistingPhysicalAdjustmentMarker.IsPresent -or $markerLastWrite -ge $start)
            if ($freshEnough) {
                [void](Write-SummaryLine "WAIT_PHYSICAL_ADJUSTMENT_MARKER_CLEAR path=$Path elapsed_s=$([int]((Get-Date) - $start).TotalSeconds)")
                [void](Write-SummaryLine "PHYSICAL_ADJUSTMENT_MARKER_LAST_WRITE=$($markerLastWrite.ToString('o'))")
                [void](Write-SummaryLine "PHYSICAL_ADJUSTMENT_MARKER_ACCEPTED_EXISTING=$([int]($markerLastWrite -lt $start))")
                return $note
            }
            [void](Write-SummaryLine "WAIT_PHYSICAL_ADJUSTMENT_MARKER_STALE path=$Path last_write=$($markerLastWrite.ToString('o')) wait_start=$($start.ToString('o'))")
        }

        $elapsedMinutes = ((Get-Date) - $start).TotalMinutes
        $blockReason = if ($note.Trim() -ne "") { "marker_older_than_wait_start" } else { "marker_missing_or_empty" }
        [void](Write-SummaryLine "WAIT_PHYSICAL_ADJUSTMENT_MARKER_BLOCKED path=$Path elapsed_min=$([math]::Round($elapsedMinutes, 1)) reason=$blockReason")
        if ($MaxWaitMinutes -gt 0 -and $elapsedMinutes -ge $MaxWaitMinutes) {
            [void](Write-SummaryLine "WAIT_PHYSICAL_ADJUSTMENT_MARKER_TIMEOUT path=$Path max_wait_min=$MaxWaitMinutes")
            [void](Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1")
            [void](Write-SummaryLine "NO_UART_WRITE=1")
            [void](Write-SummaryLine "NO_TFDU_DRIVE=1")
            [void](Write-SummaryLine "MD_P7_RESUME_SAFE_END $(Get-Date -Format o)")
            exit 27
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

function Read-SnapshotPayload {
    return (Get-Content -LiteralPath $SnapshotPath -Raw -Encoding UTF8 | ConvertFrom-Json)
}

$payload = Read-SnapshotPayload
$requiredLinks = @("A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1")
$failedLinks = @()
$physicalFailureLinks = @()
$missingEvidenceLinks = @()
$selectedModes = @()

foreach ($link in $requiredLinks) {
    $row = @($payload.rows | Where-Object { [string]$_.link -eq $link } | Select-Object -First 1)
    if ($row.Count -eq 0) {
        $failedLinks += $link
        $missingEvidenceLinks += $link
    } else {
        $item = $row[0]
        $status = [string]$item.status
        $classification = [string]$item.classification
        if ($status -ne "PASS" -or $classification -ne "PASS_PHYSICAL_RAW_PULSE") {
            $failedLinks += $link
            if ($classification -eq "FAIL_PHYSICAL_RX_MISSING") {
                $physicalFailureLinks += $link
            }
            if ($classification -eq "EVIDENCE_MISSING_REQUIRED_LINK") {
                $missingEvidenceLinks += $link
            }
        }
    }
}
foreach ($link in $failedLinks) {
    $mode = Get-LinkMode -Link $link
    if ($mode -ne "" -and -not ($selectedModes -contains $mode)) {
        $selectedModes += $mode
    }
}

$p7RawPass = ($failedLinks.Count -eq 0 -and [string]$payload.overall -eq "PASS_ALL_REQUIRED_LINKS")
$effectiveDryRun = ($DryRun.IsPresent -or -not $AllowTraffic.IsPresent)
$realRunRequested = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent)
$physicalAdjustedEffective = $PhysicalAdjusted.IsPresent
$physicalAdjustmentNoteEffective = $PhysicalAdjustmentNote

Set-ContentWithRetry -Path $summaryLog -Value "MD_P7_RESUME_SAFE_BEGIN $(Get-Date -Format o)"
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "MD_PLAN_PATH=$MdPlanPath"
Write-SummaryLine "SNAPSHOT_PATH=$SnapshotPath"
Write-SummaryLine "SNAPSHOT_OVERALL=$($payload.overall)"
Write-SummaryLine "SNAPSHOT_FAILURES=$($payload.failures)"
Write-SummaryLine "CURRENT_MD_STAGE=P7.2"
Write-SummaryLine "P7_2LANE_REMOTE_RAW_MATRIX_PASS=$([int]$p7RawPass)"
Write-SummaryLine "FAILED_LINKS=$($failedLinks -join ',')"
Write-SummaryLine "PHYSICAL_FAILURE_LINKS=$($physicalFailureLinks -join ',')"
Write-SummaryLine "MISSING_EVIDENCE_LINKS=$($missingEvidenceLinks -join ',')"
Write-SummaryLine "SELECTED_TRIGGER_MODES=$($selectedModes -join ',')"
Write-SummaryLine "ALLOW_TRAFFIC=$([int]$AllowTraffic.IsPresent)"
Write-SummaryLine "PHYSICAL_ADJUSTED=$([int]$PhysicalAdjusted.IsPresent)"
Write-SummaryLine "PHYSICAL_ADJUSTMENT_NOTE=$PhysicalAdjustmentNote"
Write-SummaryLine "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER=$([int]$WaitForPhysicalAdjustmentMarker.IsPresent)"
Write-SummaryLine "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER_ONLY=$([int]$WaitForPhysicalAdjustmentMarkerOnly.IsPresent)"
Write-SummaryLine "PHYSICAL_ADJUSTMENT_MARKER_PATH=$PhysicalAdjustmentMarkerPath"
Write-SummaryLine "ALLOW_EXISTING_PHYSICAL_ADJUSTMENT_MARKER=$([int]$AllowExistingPhysicalAdjustmentMarker.IsPresent)"
Write-SummaryLine "OVERRIDE_REPEAT_FAILURE_GUARD=$([int]$OverrideRepeatFailureGuard.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "REFRESH_P7_ARTIFACTS_ONLY=$([int]$RefreshP7ArtifactsOnly.IsPresent)"
Write-SummaryLine "EFFECTIVE_DRY_RUN=$([int]$effectiveDryRun)"
Write-SummaryLine "REAL_RUN_REQUESTED=$([int]$realRunRequested)"
Write-SummaryLine "WAIT_POLL_SECONDS=$WaitPollSeconds"
Write-SummaryLine "MAX_WAIT_MINUTES=$MaxWaitMinutes"
Write-SummaryLine "NO_P7_3_BEFORE_P7_2_RAW_PASS=1"
Write-SummaryLine "TRANSIENT_BLOCKER_WAIT_DELEGATED_TO_CHILD_WRAPPERS=1"

if ($WaitForPhysicalAdjustmentMarkerOnly.IsPresent) {
    Write-SummaryLine "MARKER_ONLY_NO_CHILD_RETEST=1"
    Write-SummaryLine "MARKER_ONLY_NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "MARKER_ONLY_NO_UART_WRITE=1"
    Write-SummaryLine "MARKER_ONLY_NO_TFDU_DRIVE=1"
    Write-SummaryLine "WAIT_PHYSICAL_ADJUSTMENT_MARKER_ONLY_IMPLIES_WAIT=1"
    $markerNote = Wait-PhysicalAdjustmentMarker -Path $PhysicalAdjustmentMarkerPath
    Write-SummaryLine "PHYSICAL_ADJUSTMENT_DECLARED_SOURCE=marker_only"
    Write-SummaryLine "PHYSICAL_ADJUSTMENT_NOTE_EFFECTIVE=$markerNote"
    Write-SummaryLine "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0"
    Write-SummaryLine "MARKER_ONLY_EXIT=0"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "MD_P7_RESUME_SAFE_END $(Get-Date -Format o)"
    exit 0
}

if ($RefreshP7ArtifactsOnly.IsPresent) {
    Write-SummaryLine "REFRESH_ONLY_NO_CHILD_RETEST=1"
    Write-SummaryLine "REFRESH_ONLY_NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "REFRESH_ONLY_NO_UART_WRITE=1"
    Write-SummaryLine "REFRESH_ONLY_NO_TFDU_DRIVE=1"
    Invoke-P7PostRetestRefresh -RetestExit 0
    $refreshOnlyExit = $script:LastP7PostRetestRefreshExit
    Write-SummaryLine "REFRESH_ONLY_EXIT=$refreshOnlyExit"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "MD_P7_RESUME_SAFE_END $(Get-Date -Format o)"
    exit $refreshOnlyExit
}

if ($p7RawPass) {
    Write-SummaryLine "P7_2_GATE_RESULT=PASS"
    Write-SummaryLine "NEXT_MD_STAGE=P7.3"
    Write-SummaryLine "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0"
    Write-SummaryLine "P7_3_AUTO_RUN_REASON=no dedicated P7.3 protocol wrapper is proven in this stage-level launcher"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "MD_P7_RESUME_SAFE_END $(Get-Date -Format o)"
    exit 0
}

Write-SummaryLine "P7_2_GATE_RESULT=BLOCK"
if ($realRunRequested -and $physicalFailureLinks.Count -gt 0 -and -not $physicalAdjustedEffective -and $WaitForPhysicalAdjustmentMarker.IsPresent) {
    Write-SummaryLine "WAIT_PHYSICAL_ADJUSTMENT_MARKER_ENABLED=1"
    $markerNote = Wait-PhysicalAdjustmentMarker -Path $PhysicalAdjustmentMarkerPath
    $physicalAdjustedEffective = $true
    $physicalAdjustmentNoteEffective = $markerNote
    Write-SummaryLine "PHYSICAL_ADJUSTMENT_DECLARED_SOURCE=marker"
}
if ($physicalFailureLinks.Count -gt 0 -and -not $physicalAdjustedEffective) {
    Write-SummaryLine "PHYSICAL_ADJUSTMENT_REQUIRED_BEFORE_REAL_RETEST=1"
}
Write-SummaryLine "PHYSICAL_ADJUSTED_EFFECTIVE=$([int]$physicalAdjustedEffective)"
Write-SummaryLine "PHYSICAL_ADJUSTMENT_NOTE_EFFECTIVE=$physicalAdjustmentNoteEffective"
if ($realRunRequested -and $physicalAdjustedEffective -and $physicalAdjustmentNoteEffective.Trim() -eq "") {
    Write-SummaryLine "PHYSICAL_ADJUSTMENT_NOTE_REQUIRED=1"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "MD_P7_RESUME_SAFE_END $(Get-Date -Format o)"
    exit 26
}

$childArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $failedLinkWrapper,
    "-SnapshotPath",
    $SnapshotPath,
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
    "-PerRunTimeoutSeconds",
    [string]$PerRunTimeoutSeconds,
    "-MaxTfduWindowSeconds",
    [string]$MaxTfduWindowSeconds,
    "-WaitPollSeconds",
    [string]$WaitPollSeconds,
    "-MaxWaitMinutes",
    [string]$MaxWaitMinutes,
    "-PythonPath",
    $PythonPath
)
if ($AllowTraffic) { $childArgs += "-AllowTraffic" }
if ($physicalAdjustedEffective) { $childArgs += "-PhysicalAdjusted" }
if ($physicalAdjustmentNoteEffective.Trim() -ne "") {
    $childArgs += @("-PhysicalAdjustmentNote", $physicalAdjustmentNoteEffective)
}
if ($OverrideRepeatFailureGuard) { $childArgs += "-OverrideRepeatFailureGuard" }
if ($effectiveDryRun) { $childArgs += "-DryRun" }
if ($SkipArtifactGuard) { $childArgs += "-SkipArtifactGuard" }
if ($StopOnFail) { $childArgs += "-StopOnFail" }

$childOut = Join-Path $reportsDir "md_p7_resume_safe_$stamp.failed_links.out.log"
$childErr = Join-Path $reportsDir "md_p7_resume_safe_$stamp.failed_links.err.log"
$childExitRaw = Invoke-LoggedProcess -Label "FAILED_LINK_RETEST" -FilePath "powershell.exe" -Arguments $childArgs -OutLog $childOut -ErrLog $childErr
$childExit = $childExitRaw
Write-SummaryLine "FAILED_LINK_RETEST_RAW_EXIT=$childExitRaw"
if (Test-Path -LiteralPath $childOut) {
    $childText = Get-Content -LiteralPath $childOut -Raw -ErrorAction SilentlyContinue
    if ($childText -match "(?m)^REPEAT_FAILURE_GUARD_BLOCKED=1") {
        $childExit = 25
        Write-SummaryLine "FAILED_LINK_RETEST_EXIT_NORMALIZED_REASON=repeat_failure_guard_blocked"
    } elseif ($childText -match "(?m)^PHYSICAL_ADJUSTMENT_NOTE_REQUIRED=1") {
        $childExit = 26
        Write-SummaryLine "FAILED_LINK_RETEST_EXIT_NORMALIZED_REASON=physical_adjustment_note_required"
    } elseif ($childText -match "(?m)^RETEST_EXIT=(\d+)") {
        $reportedRetestExit = [int]$Matches[1]
        if ($childExit -eq 0 -and $reportedRetestExit -ne 0) {
            $childExit = $reportedRetestExit
            Write-SummaryLine "FAILED_LINK_RETEST_EXIT_NORMALIZED_REASON=reported_retest_exit"
        }
    }
    foreach ($line in (($childText -split "`r?`n") | Where-Object {
        $_ -match "REPEAT_FAILURE_GUARD|PHYSICAL_ADJUSTMENT|WAIT_|SELECTED_FAILED_LINKS|SELECTED_TRIGGER_MODES|NO_HARDWARE|NO_UART|NO_TFDU|RETEST_EXIT"
    })) {
        Write-SummaryLine "FAILED_LINK_RETEST_MATCH=$line"
    }
}
if ((Test-Path -LiteralPath $childErr) -and (Get-Item -LiteralPath $childErr).Length -gt 0) {
    foreach ($line in (Get-Content -LiteralPath $childErr -ErrorAction SilentlyContinue | Select-Object -First 30)) {
        Write-SummaryLine "FAILED_LINK_RETEST_STDERR=$line"
    }
}
Write-SummaryLine "FAILED_LINK_RETEST_EXIT=$childExit"

if ($effectiveDryRun) {
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "NO_UART_WRITE=1"
    Write-SummaryLine "NO_TFDU_DRIVE=1"
    Write-SummaryLine "MD_P7_RESUME_SAFE_END $(Get-Date -Format o)"
    exit $childExit
}

$script:LastP7PostRetestRefreshExit = 0
Invoke-P7PostRetestRefresh -RetestExit $childExit
$postRetestRefreshExit = $script:LastP7PostRetestRefreshExit
Write-SummaryLine "POST_RETEST_REFRESH_EXIT=$postRetestRefreshExit"

Write-SummaryLine "MD_P7_RESUME_SAFE_END $(Get-Date -Format o)"
exit $childExit
