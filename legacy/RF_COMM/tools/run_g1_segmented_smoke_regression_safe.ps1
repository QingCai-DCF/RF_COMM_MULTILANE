param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$Cycles = 3,
    [int]$PostStartSeconds = 35,
    [int]$CaptureSeconds = 75,
    [int]$CooldownSeconds = 60,
    [int]$MaxTfduWindowSeconds = 600,
    [int]$ShutdownBudgetSeconds = 30,
    [int]$XsctWaitSeconds = 45,
    [switch]$SkipPreflight,
    [switch]$ContinueOnFail,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "g1_segmented_smoke_regression_$stamp.summary.txt"
$cyclesCsv = Join-Path $reportsDir "g1_segmented_smoke_regression_$stamp.cycles.csv"
$runner = Join-Path $scriptDir "run_g1_lane0_hw_smoke_safe.ps1"

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Missing G1 safe smoke runner: $runner"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Get-MatchValue {
    param([string]$Text, [string]$Pattern, [string]$Default = "")
    $match = [regex]::Match($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if ($match.Success) {
        return $match.Groups[1].Value
    }
    return $Default
}

function Get-LastMatchValue {
    param([string]$Text, [string]$Pattern, [string]$Default = "")
    $matches = [regex]::Matches($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if ($matches.Count -gt 0) {
        return $matches[$matches.Count - 1].Groups[1].Value
    }
    return $Default
}

function Get-NewestCycleSummary {
    param([datetime]$Since)
    $candidates = @(Get-ChildItem -LiteralPath $reportsDir -Filter "g1_lane0_hw_smoke_safe_*.summary.txt" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $Since.AddSeconds(-2) } |
        Sort-Object LastWriteTime -Descending)
    if ($candidates.Count -eq 0) {
        return $null
    }
    return $candidates[0].FullName
}

function Parse-CycleEvidence {
    param([string]$Text)

    $stageLine = Get-LastMatchValue -Text $Text -Pattern "(PSPS_STAGE_SUMMARY[^\r\n]*)"
    $window = Get-LastMatchValue -Text $Text -Pattern "HW_WINDOW_TO_SHUTDOWN_END_SECONDS=([0-9]+(?:\.[0-9]+)?)" -Default "0"
    $payloadSeen = Get-LastMatchValue -Text $Text -Pattern "G1_HW_SMOKE_PAYLOAD_256_SEEN=(\d+)" -Default "0"
    $summaryPass = Get-LastMatchValue -Text $Text -Pattern "G1_HW_SMOKE_SUMMARY_PASS=(\d+)" -Default "0"
    $shutdownOk = Get-LastMatchValue -Text $Text -Pattern "G1_HW_SMOKE_SHUTDOWN_OK=(\d+)" -Default "0"
    $windowOk = Get-LastMatchValue -Text $Text -Pattern "G1_HW_SMOKE_WINDOW_OK=(\d+)" -Default "0"

    return [pscustomobject]@{
        StageLine = $stageLine
        Sent = Get-MatchValue -Text $stageLine -Pattern "\bsent=(\d+)" -Default "0"
        RxOk = Get-MatchValue -Text $stageLine -Pattern "\brx_ok=(\d+)" -Default "0"
        TxFail = Get-MatchValue -Text $stageLine -Pattern "\btx_fail=(\d+)" -Default "0"
        RxTimeout = Get-MatchValue -Text $stageLine -Pattern "\brx_timeout=(\d+)" -Default "0"
        RxBad = Get-MatchValue -Text $stageLine -Pattern "\brx_bad=(\d+)" -Default "0"
        RxMismatch = Get-MatchValue -Text $stageLine -Pattern "\brx_mismatch=(\d+)" -Default "0"
        LossPercent = Get-MatchValue -Text $stageLine -Pattern "\bloss=([0-9.]+)%" -Default "100.0"
        WinRxMbps = Get-MatchValue -Text $stageLine -Pattern "\bwin_rx_mbps=([0-9.]+)" -Default "0"
        RecoveryCount = Get-MatchValue -Text $stageLine -Pattern "\brec=(\d+)" -Default "0"
        LastError = Get-MatchValue -Text $stageLine -Pattern "\blast_error=([^\s]+)" -Default "missing"
        PayloadSeen = $payloadSeen
        SummaryPass = $summaryPass
        ShutdownOk = $shutdownOk
        WindowOk = $windowOk
        TfduWindowSeconds = $window
    }
}

function Add-CsvRow {
    param(
        [int]$Cycle,
        [string]$Status,
        [int]$ExitCode,
        [string]$SummaryPath,
        [pscustomobject]$Evidence
    )

    $row = [pscustomobject]@{
        cycle = $Cycle
        status = $Status
        exit_code = $ExitCode
        summary = $SummaryPath
        sent = $Evidence.Sent
        rx_ok = $Evidence.RxOk
        tx_fail = $Evidence.TxFail
        rx_timeout = $Evidence.RxTimeout
        rx_bad = $Evidence.RxBad
        rx_mismatch = $Evidence.RxMismatch
        loss_percent = $Evidence.LossPercent
        win_rx_mbps = $Evidence.WinRxMbps
        recovery_count = $Evidence.RecoveryCount
        last_error = $Evidence.LastError
        payload_seen = $Evidence.PayloadSeen
        summary_pass = $Evidence.SummaryPass
        shutdown_ok = $Evidence.ShutdownOk
        window_ok = $Evidence.WindowOk
        tfdu_window_seconds = $Evidence.TfduWindowSeconds
    }
    $row | Export-Csv -LiteralPath $cyclesCsv -NoTypeInformation -Append -Encoding ascii
}

"G1_SEGMENTED_SMOKE_REGRESSION_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "RUNNER=$runner"
Write-SummaryLine "CYCLES_CSV=$cyclesCsv"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "CYCLES_REQUESTED=$Cycles"
Write-SummaryLine "POST_START_SECONDS=$PostStartSeconds"
Write-SummaryLine "CAPTURE_SECONDS=$CaptureSeconds"
Write-SummaryLine "COOLDOWN_SECONDS=$CooldownSeconds"
Write-SummaryLine "MAX_TFDU_WINDOW_SECONDS=$MaxTfduWindowSeconds"
Write-SummaryLine "SHUTDOWN_BUDGET_SECONDS=$ShutdownBudgetSeconds"
Write-SummaryLine "SKIP_PREFLIGHT=$([int]$SkipPreflight.IsPresent)"
Write-SummaryLine "CONTINUE_ON_FAIL=$([int]$ContinueOnFail.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "NOTE_SEGMENTED_REGRESSION_NOT_CONTINUOUS_SOAK=1"

if ($Cycles -lt 1) {
    Write-SummaryLine "G1_SEGMENTED_BLOCKED_INVALID_CYCLES=1"
    Write-SummaryLine "G1_SEGMENTED_SMOKE_REGRESSION_END $(Get-Date -Format o)"
    exit 10
}

if (($XsctWaitSeconds + $PostStartSeconds + $ShutdownBudgetSeconds) -ge $MaxTfduWindowSeconds) {
    Write-SummaryLine "G1_SEGMENTED_BLOCKED_RUNTIME_LIMIT=1"
    Write-SummaryLine "G1_SEGMENTED_SMOKE_REGRESSION_END $(Get-Date -Format o)"
    exit 11
}

if (-not $DryRun -and $CooldownSeconds -lt 30 -and $Cycles -gt 1) {
    Write-SummaryLine "G1_SEGMENTED_BLOCKED_COOLDOWN_TOO_SHORT=1"
    Write-SummaryLine "G1_SEGMENTED_SMOKE_REGRESSION_END $(Get-Date -Format o)"
    exit 12
}

if ($DryRun) {
    Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    $dryEvidence = [pscustomobject]@{
        Sent = "0"
        RxOk = "0"
        TxFail = "0"
        RxTimeout = "0"
        RxBad = "0"
        RxMismatch = "0"
        LossPercent = "0.0"
        WinRxMbps = "0"
        RecoveryCount = "0"
        LastError = "dry_run"
        PayloadSeen = "0"
        SummaryPass = "0"
        ShutdownOk = "0"
        WindowOk = "0"
        TfduWindowSeconds = "0"
    }
    for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
        Write-SummaryLine "DRY_RUN_CYCLE_$cycle=planned"
        Add-CsvRow -Cycle $cycle -Status "DRY_RUN_PLANNED" -ExitCode 0 -SummaryPath "" -Evidence $dryEvidence
    }
    Write-SummaryLine "G1_SEGMENTED_SMOKE_REGRESSION_PASS=DRY_RUN_ONLY"
    Write-SummaryLine "CYCLES_RUN=0"
    Write-SummaryLine "CYCLES_PASS=0"
    Write-SummaryLine "CYCLES_FAIL=0"
    Write-SummaryLine "G1_SEGMENTED_SMOKE_REGRESSION_END $(Get-Date -Format o)"
    exit 0
}

$totalSent = 0
$totalRxOk = 0
$totalTxFail = 0
$totalRxTimeout = 0
$totalRxBad = 0
$totalRxMismatch = 0
$totalRecovery = 0
$sumMbps = 0.0
$mbpsCount = 0
$maxWindow = 0.0
$worstLoss = 0.0
$cyclesRun = 0
$cyclesPass = 0
$cyclesFail = 0

for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
    $cycleStart = Get-Date
    $cycleOut = Join-Path $reportsDir ("g1_segmented_smoke_regression_{0}_cycle{1:D2}.out.log" -f $stamp, $cycle)
    $cycleErr = Join-Path $reportsDir ("g1_segmented_smoke_regression_{0}_cycle{1:D2}.err.log" -f $stamp, $cycle)
    Write-SummaryLine "CYCLE_$cycle`_START=$($cycleStart.ToString('o'))"
    Write-SummaryLine "CYCLE_$cycle`_STDOUT=$cycleOut"
    Write-SummaryLine "CYCLE_$cycle`_STDERR=$cycleErr"

    $args = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $runner,
        "-ComPort",
        $ComPort,
        "-BaudRate",
        [string]$BaudRate,
        "-XsctPath",
        $XsctPath,
        "-VivadoPath",
        $VivadoPath,
        "-HwServerUrl",
        $HwServerUrl,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz,
        "-XsctWaitSeconds",
        [string]$XsctWaitSeconds,
        "-PostStartSeconds",
        [string]$PostStartSeconds,
        "-CaptureSeconds",
        [string]$CaptureSeconds,
        "-MaxTfduWindowSeconds",
        [string]$MaxTfduWindowSeconds,
        "-ShutdownBudgetSeconds",
        [string]$ShutdownBudgetSeconds
    )
    if ($SkipPreflight) {
        $args += "-SkipPreflight"
    }

    $proc = Start-Process -FilePath "powershell.exe" `
        -ArgumentList $args `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $cycleOut `
        -RedirectStandardError $cycleErr `
        -WindowStyle Hidden `
        -PassThru
    $proc.WaitForExit()
    $proc.Refresh()
    $exitCode = if ($null -eq $proc.ExitCode) { 125 } else { $proc.ExitCode }

    $cycleText = ""
    if (Test-Path -LiteralPath $cycleOut) {
        $cycleText = Get-Content -LiteralPath $cycleOut -Raw -ErrorAction SilentlyContinue
    }
    $cycleSummary = Get-NewestCycleSummary -Since $cycleStart
    $cycleSummaryPath = ""
    if ($cycleSummary) {
        $cycleSummaryPath = $cycleSummary
        $cycleText = $cycleText + "`n" + (Get-Content -LiteralPath $cycleSummary -Raw -ErrorAction SilentlyContinue)
    }

    $evidence = Parse-CycleEvidence -Text $cycleText
    if ($exitCode -eq 125 -and $cycleText -match "(?m)^INNER_EXIT_INFERRED=0\b") {
        Write-SummaryLine "CYCLE_$cycle`_EXIT_INFERRED=0"
        $exitCode = 0
    }
    $tfduWindow = [double]$evidence.TfduWindowSeconds
    $cyclePassed = (
        $exitCode -eq 0 -and
        $evidence.PayloadSeen -eq "1" -and
        $evidence.SummaryPass -eq "1" -and
        $evidence.ShutdownOk -eq "1" -and
        $evidence.WindowOk -eq "1" -and
        $tfduWindow -lt [double]$MaxTfduWindowSeconds
    )

    $cyclesRun++
    if ($cyclePassed) {
        $cyclesPass++
        $status = "PASS"
    } else {
        $cyclesFail++
        $status = "FAIL"
    }

    $totalSent += [int]$evidence.Sent
    $totalRxOk += [int]$evidence.RxOk
    $totalTxFail += [int]$evidence.TxFail
    $totalRxTimeout += [int]$evidence.RxTimeout
    $totalRxBad += [int]$evidence.RxBad
    $totalRxMismatch += [int]$evidence.RxMismatch
    $totalRecovery += [int]$evidence.RecoveryCount
    $lossValue = [double]$evidence.LossPercent
    if ($lossValue -gt $worstLoss) {
        $worstLoss = $lossValue
    }
    $mbpsValue = [double]$evidence.WinRxMbps
    if ($mbpsValue -gt 0.0) {
        $sumMbps += $mbpsValue
        $mbpsCount++
    }
    if ($tfduWindow -gt $maxWindow) {
        $maxWindow = $tfduWindow
    }

    Add-CsvRow -Cycle $cycle -Status $status -ExitCode $exitCode -SummaryPath $cycleSummaryPath -Evidence $evidence
    Write-SummaryLine ("CYCLE_{0}_RESULT status={1} exit={2} summary={3} sent={4} rx_ok={5} tx_fail={6} loss={7}% mbps={8} shutdown_ok={9} window_ok={10} tfdu_window_s={11} last_error={12}" -f
        $cycle,
        $status,
        $exitCode,
        $cycleSummaryPath,
        $evidence.Sent,
        $evidence.RxOk,
        $evidence.TxFail,
        $evidence.LossPercent,
        $evidence.WinRxMbps,
        $evidence.ShutdownOk,
        $evidence.WindowOk,
        $evidence.TfduWindowSeconds,
        $evidence.LastError)

    if (-not $cyclePassed -and -not $ContinueOnFail) {
        Write-SummaryLine "STOP_ON_FIRST_FAILURE=1"
        break
    }

    if ($cycle -lt $Cycles) {
        Write-SummaryLine "CYCLE_$cycle`_COOLDOWN_START=$(Get-Date -Format o)"
        Start-Sleep -Seconds $CooldownSeconds
        Write-SummaryLine "CYCLE_$cycle`_COOLDOWN_END=$(Get-Date -Format o)"
    }
}

$avgMbps = 0.0
if ($mbpsCount -gt 0) {
    $avgMbps = $sumMbps / $mbpsCount
}
$overallPass = ($cyclesRun -eq $Cycles -and $cyclesFail -eq 0)

Write-SummaryLine "CYCLES_RUN=$cyclesRun"
Write-SummaryLine "CYCLES_PASS=$cyclesPass"
Write-SummaryLine "CYCLES_FAIL=$cyclesFail"
Write-SummaryLine "TOTAL_SENT=$totalSent"
Write-SummaryLine "TOTAL_RX_OK=$totalRxOk"
Write-SummaryLine "TOTAL_TX_FAIL=$totalTxFail"
Write-SummaryLine "TOTAL_RX_TIMEOUT=$totalRxTimeout"
Write-SummaryLine "TOTAL_RX_BAD=$totalRxBad"
Write-SummaryLine "TOTAL_RX_MISMATCH=$totalRxMismatch"
Write-SummaryLine "TOTAL_RECOVERY_COUNT=$totalRecovery"
Write-SummaryLine ("WORST_LOSS_PERCENT={0:N3}" -f $worstLoss)
Write-SummaryLine ("AVG_WIN_RX_MBPS={0:N3}" -f $avgMbps)
Write-SummaryLine ("MAX_TFDU_WINDOW_SECONDS={0:N1}" -f $maxWindow)
Write-SummaryLine "G1_SEGMENTED_SMOKE_REGRESSION_PASS=$([int]$overallPass)"
Write-SummaryLine "NOTE_FULL_G1_ONE_HOUR_SOAK_STILL_NOT_CLAIMED=1"
Write-SummaryLine "G1_SEGMENTED_SMOKE_REGRESSION_END $(Get-Date -Format o)"

if ($overallPass) {
    exit 0
}
exit 20
