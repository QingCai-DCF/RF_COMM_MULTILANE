param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$PayloadBytes = 256,
    [int]$StageSeconds = 300,
    [int]$RunsPerBuild = 5,
    [int]$RequalRuns = 10,
    [int]$Jobs = 16,
    [switch]$SkipBuilds,
    [switch]$SkipSoftRecovery,
    [switch]$SkipPreflightAfterFirst,
    [switch]$ContinueOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "P4A_txack_requal_sequence_$stamp.summary.txt"
$abCsv = Join-Path $reportsDir "P4A_02_rx_tuning_ab_results.csv"
$requalCsv = Join-Path $reportsDir "P4A_03_lane0_10x300_requal.csv"
$smokeRunner = Join-Path $scriptDir "run_p4a_failure_counter_smoke_safe.ps1"
$profileBuilder = Join-Path $scriptDir "build_p4_profile.ps1"
$reportBuilder = Join-Path $scriptDir "build_p4_constrained_execution_reports.py"

foreach ($path in @($smokeRunner, $profileBuilder, $reportBuilder, $XsctPath, $VivadoPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}
if ($StageSeconds -lt 1 -or $StageSeconds -gt 600) {
    throw "StageSeconds must be between 1 and 600."
}
if ($RunsPerBuild -lt 1 -or $RequalRuns -lt 1) {
    throw "Run counts must be positive."
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
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
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -WindowStyle Hidden `
        -PassThru
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

function Get-LastRegexLine {
    param([string]$Text, [string]$Pattern)
    $matches = [regex]::Matches($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if ($matches.Count -eq 0) {
        return ""
    }
    return $matches[$matches.Count - 1].Value
}

function Get-Kv {
    param([string]$Line, [string]$Key, [string]$Default = "")
    $match = [regex]::Match($Line, "(^|\s)" + [regex]::Escape($Key) + "=([^\s]+)")
    if ($match.Success) {
        return $match.Groups[2].Value
    }
    return $Default
}

function To-Int {
    param([string]$Value, [int]$Default = 0)
    $out = 0
    if ([int]::TryParse($Value, [ref]$out)) {
        return $out
    }
    return $Default
}

function Find-NewestFile {
    param([string]$Filter, [datetime]$Since)
    $files = @(Get-ChildItem -LiteralPath $reportsDir -Filter $Filter -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $Since.AddSeconds(-5) } |
        Sort-Object LastWriteTime -Descending)
    if ($files.Count -eq 0) {
        return $null
    }
    return $files[0].FullName
}

function Get-BuildConfig {
    param([string]$Build)
    if ($Build -eq "BuildA") {
        return [pscustomobject]@{ DetectStart = 3; DetectEnd = 7; Realign = 1 }
    }
    return [pscustomobject]@{ DetectStart = 0; DetectEnd = 5; Realign = 0 }
}

function Write-AbHeader {
    "build,run,detect_start,detect_end,realign,stage_seconds,payload_bytes,lane_mask,ack_mask,sent,rx_ok,tx_fail,exact_loss,loss_ppm,rx_timeout,rx_bad,rx_mismatch,last_error,shutdown_exit,tx_start_count,tx_done_count,tx_retry_count_total,max_retry_seen,tx_retry_exhausted_count,ack_timeout_count,recovery_count,status,evidence" |
        Out-File -LiteralPath $abCsv -Encoding ascii
}

function Write-RequalHeader {
    "run,selected_tuning,stage_seconds,payload_bytes,lane_mask,ack_mask,sent,rx_ok,tx_fail,loss_ppm,rx_timeout,rx_bad,rx_mismatch,last_error,shutdown_exit,tx_retry_count_total,max_retry_seen,ack_timeout_count,ack_late_count,recovery_count,status,evidence" |
        Out-File -LiteralPath $requalCsv -Encoding ascii
}

function ConvertTo-CsvValue {
    param([string]$Value)
    if ($Value -match '[,"\r\n]') {
        return '"' + ($Value -replace '"', '""') + '"'
    }
    return $Value
}

function Add-AbRow {
    param([pscustomobject]$Row)
    $values = @(
        $Row.Build, $Row.Run, $Row.DetectStart, $Row.DetectEnd, $Row.Realign,
        $Row.StageSeconds, $Row.PayloadBytes, "0x1", "0x1",
        $Row.Sent, $Row.RxOk, $Row.TxFail, $Row.ExactLoss, $Row.LossPpm,
        $Row.RxTimeout, $Row.RxBad, $Row.RxMismatch, $Row.LastError,
        $Row.ShutdownExit, $Row.TxStartCount, $Row.TxDoneCount,
        $Row.TxRetryCountTotal, $Row.MaxRetrySeen, $Row.TxRetryExhaustedCount,
        $Row.AckTimeoutCount, $Row.RecoveryCount, $Row.Status, $Row.Evidence
    )
    ($values | ForEach-Object { ConvertTo-CsvValue ([string]$_) }) -join "," |
        Add-Content -LiteralPath $abCsv -Encoding ascii
}

function Add-RequalRow {
    param([pscustomobject]$Row)
    $values = @(
        $Row.Run, $Row.SelectedTuning, $Row.StageSeconds, $Row.PayloadBytes, "0x1", "0x1",
        $Row.Sent, $Row.RxOk, $Row.TxFail, $Row.LossPpm, $Row.RxTimeout,
        $Row.RxBad, $Row.RxMismatch, $Row.LastError, $Row.ShutdownExit,
        $Row.TxRetryCountTotal, $Row.MaxRetrySeen, $Row.AckTimeoutCount,
        $Row.AckLateCount, $Row.RecoveryCount, $Row.Status, $Row.Evidence
    )
    ($values | ForEach-Object { ConvertTo-CsvValue ([string]$_) }) -join "," |
        Add-Content -LiteralPath $requalCsv -Encoding ascii
}

function Invoke-ProfileBuild {
    param([string]$Build)
    if ($SkipBuilds) {
        Write-SummaryLine "BUILD_${Build}_SKIPPED=1"
        return 0
    }
    $started = Get-Date
    $outLog = Join-Path $reportsDir ("P4A_txack_requal_sequence_{0}_{1}.build.out.log" -f $stamp, $Build)
    $errLog = Join-Path $reportsDir ("P4A_txack_requal_sequence_{0}_{1}.build.err.log" -f $stamp, $Build)
    Write-SummaryLine "BUILD_${Build}_START=$($started.ToString('o'))"
    $exit = Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $profileBuilder,
            "-Profile",
            "P4A_TXACK_DIAG",
            "-RxTuning",
            $Build,
            "-VivadoPath",
            $VivadoPath,
            "-XsctPath",
            $XsctPath,
            "-Jobs",
            [string]$Jobs,
            "-StageSeconds",
            [string]$StageSeconds,
            "-PayloadBytes",
            [string]$PayloadBytes
        ) `
        -StdoutPath $outLog `
        -StderrPath $errLog `
        -TimeoutSeconds 14400
    $buildSummary = Find-NewestFile -Filter ("build_P4A_TXACK_DIAG_{0}_*.summary.txt" -f $Build) -Since $started
    Write-SummaryLine "BUILD_${Build}_EXIT=$exit"
    Write-SummaryLine "BUILD_${Build}_OUT=$outLog"
    Write-SummaryLine "BUILD_${Build}_ERR=$errLog"
    Write-SummaryLine "BUILD_${Build}_SUMMARY=$buildSummary"
    if ($buildSummary) {
        $text = Get-Content -LiteralPath $buildSummary -Raw -ErrorAction SilentlyContinue
        foreach ($line in (($text -split "`r?`n") | Where-Object { $_ -match "BUILD_RESULT|P4_BUILD_ENV IR_RX_DETECT|P4_BUILD_ENV IR_B_RX_DETECT|P4_BUILD_ENV PSPS_TX_ONLY|P4_PROFILE_ARTIFACT" })) {
            Write-SummaryLine "BUILD_${Build}_MATCH=$line"
        }
        if ($exit -ne 0 -and $text -match "BUILD_RESULT=PASS") {
            Write-SummaryLine "BUILD_${Build}_EXIT_OVERRIDDEN_BY_PASS_MARKER=1"
            $exit = 0
        }
    }
    return $exit
}

function Invoke-P4aRun {
    param(
        [string]$Label,
        [string]$Build,
        [int]$RunIndex,
        [switch]$SkipPreflight
    )
    $started = Get-Date
    $outLog = Join-Path $reportsDir ("P4A_txack_requal_sequence_{0}_{1}_{2:D2}.out.log" -f $stamp, $Label, $RunIndex)
    $errLog = Join-Path $reportsDir ("P4A_txack_requal_sequence_{0}_{1}_{2:D2}.err.log" -f $stamp, $Label, $RunIndex)
    Write-SummaryLine "RUN_${Label}_${RunIndex}_START=$($started.ToString('o'))"
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $smokeRunner,
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
        "-PayloadBytes",
        [string]$PayloadBytes,
        "-StageSeconds",
        [string]$StageSeconds
    )
    if ($SkipSoftRecovery) {
        $args += "-SkipSoftRecovery"
    }
    if ($SkipPreflight) {
        $args += "-SkipPreflight"
    }
    $exit = Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments $args `
        -StdoutPath $outLog `
        -StderrPath $errLog `
        -TimeoutSeconds ($StageSeconds + 420)
    $runSummary = Find-NewestFile -Filter "P4A_01_failure_counter_smoke_*.summary.txt" -Since $started
    $transcript = Join-Path $reportsDir "P4A_01_failure_counter_smoke.log"
    $shutdownExit = "125"
    $smokePassMarker = $false
    if ($runSummary) {
        $summaryText = Get-Content -LiteralPath $runSummary -Raw -ErrorAction SilentlyContinue
        $shutdownExit = Get-Kv -Line (Get-LastRegexLine -Text $summaryText -Pattern "SHUTDOWN_EXIT=[^\r\n]+") -Key "SHUTDOWN_EXIT" -Default "125"
        if ($summaryText -match "P4A_FAILURE_COUNTER_SMOKE_PASS=1" -or $summaryText -match "UART_OPERATOR_P4_FAILURE_SMOKE_PASS=1") {
            $smokePassMarker = $true
        }
    }
    if ($exit -ne 0 -and $smokePassMarker) {
        Write-SummaryLine "RUN_${Label}_${RunIndex}_EXIT_OVERRIDDEN_BY_PASS_MARKER=1"
        $exit = 0
    }

    $text = ""
    if (Test-Path -LiteralPath $transcript) {
        $text = Get-Content -LiteralPath $transcript -Raw -ErrorAction SilentlyContinue
    }
    $startLine = Get-LastRegexLine -Text $text -Pattern ".*UARTOP_RESULT command=START[^\r\n]*"
    $failureLine = Get-LastRegexLine -Text $text -Pattern ".*item=failure_counters[^\r\n]*"

    $sent = To-Int (Get-Kv -Line $startLine -Key "sent" -Default "0")
    $rxOk = To-Int (Get-Kv -Line $startLine -Key "rx_ok" -Default "0")
    $txFail = To-Int (Get-Kv -Line $startLine -Key "tx_fail" -Default "0")
    $rxTimeout = To-Int (Get-Kv -Line $startLine -Key "rx_timeout" -Default "0")
    $rxBad = To-Int (Get-Kv -Line $startLine -Key "rx_bad" -Default "0")
    $rxMismatch = To-Int (Get-Kv -Line $startLine -Key "rx_mismatch" -Default "0")
    $lastError = Get-Kv -Line $startLine -Key "last_error" -Default (Get-Kv -Line $failureLine -Key "last_error" -Default "missing")
    $exactLoss = 0.0
    if ($sent -gt 0) {
        $exactLoss = [double]$txFail / [double]$sent
    }
    $lossPpm = $exactLoss * 1000000.0

    $txStartCount = To-Int (Get-Kv -Line $failureLine -Key "tx_start_count" -Default "0")
    $txDoneCount = To-Int (Get-Kv -Line $failureLine -Key "tx_done_count" -Default "0")
    $txRetryCountTotal = To-Int (Get-Kv -Line $failureLine -Key "tx_retry_count_total" -Default "0")
    $maxRetrySeen = To-Int (Get-Kv -Line $failureLine -Key "max_retry_seen" -Default "0")
    $txRetryExhaustedCount = To-Int (Get-Kv -Line $failureLine -Key "tx_retry_exhausted_count" -Default "0")
    $ackTimeoutCount = To-Int (Get-Kv -Line $failureLine -Key "ack_timeout_count" -Default "0")
    $ackLateCount = To-Int (Get-Kv -Line $failureLine -Key "ack_late_count" -Default "0")
    $recoveryCount = To-Int (Get-Kv -Line $failureLine -Key "recovery_count" -Default "0")

    $clean = (
        $exit -eq 0 -and
        $sent -gt 0 -and
        $rxOk -eq $sent -and
        $txFail -eq 0 -and
        $rxTimeout -eq 0 -and
        $rxBad -eq 0 -and
        $rxMismatch -eq 0 -and
        $lastError -eq "none" -and
        (To-Int $shutdownExit 125) -eq 0 -and
        $txStartCount -gt 0 -and
        $txDoneCount -gt 0 -and
        $txRetryExhaustedCount -eq 0
    )
    $status = if ($clean) { "PASS" } else { "FAIL" }
    $evidence = if ($runSummary) { $runSummary } else { $transcript }
    Write-SummaryLine "RUN_${Label}_${RunIndex}_EXIT=$exit"
    Write-SummaryLine "RUN_${Label}_${RunIndex}_STATUS=$status"
    Write-SummaryLine "RUN_${Label}_${RunIndex}_SUMMARY=$runSummary"
    Write-SummaryLine "RUN_${Label}_${RunIndex}_TRANSCRIPT=$transcript"
    Write-SummaryLine "RUN_${Label}_${RunIndex}_METRICS sent=$sent rx_ok=$rxOk tx_fail=$txFail loss_ppm=$lossPpm last_error=$lastError shutdown_exit=$shutdownExit tx_retry_count_total=$txRetryCountTotal ack_timeout_count=$ackTimeoutCount"

    return [pscustomobject]@{
        Build = $Build
        Run = $RunIndex
        Sent = $sent
        RxOk = $rxOk
        TxFail = $txFail
        ExactLoss = ("{0:F12}" -f $exactLoss)
        LossPpm = ("{0:F6}" -f $lossPpm)
        RxTimeout = $rxTimeout
        RxBad = $rxBad
        RxMismatch = $rxMismatch
        LastError = $lastError
        ShutdownExit = $shutdownExit
        TxStartCount = $txStartCount
        TxDoneCount = $txDoneCount
        TxRetryCountTotal = $txRetryCountTotal
        MaxRetrySeen = $maxRetrySeen
        TxRetryExhaustedCount = $txRetryExhaustedCount
        AckTimeoutCount = $ackTimeoutCount
        AckLateCount = $ackLateCount
        RecoveryCount = $recoveryCount
        Status = $status
        Evidence = $evidence
        StageSeconds = $StageSeconds
        PayloadBytes = $PayloadBytes
    }
}

function Test-CleanRows {
    param([object[]]$Rows)
    if ($Rows.Count -lt $RunsPerBuild) {
        return $false
    }
    foreach ($row in $Rows[0..($RunsPerBuild - 1)]) {
        if ($row.Status -ne "PASS") {
            return $false
        }
    }
    return $true
}

function Select-Tuning {
    param([object[]]$BuildARows, [object[]]$BuildBRows)
    $aClean = Test-CleanRows -Rows $BuildARows
    $bClean = Test-CleanRows -Rows $BuildBRows
    if ($bClean -and -not $aClean) {
        return "BuildB"
    }
    if ($aClean -and -not $bClean) {
        return "BuildA"
    }
    if ($aClean -and $bClean) {
        $aTuple = @(
            ($BuildARows | Measure-Object -Property TxRetryCountTotal -Sum).Sum,
            ($BuildARows | Measure-Object -Property MaxRetrySeen -Maximum).Maximum,
            ($BuildARows | Measure-Object -Property AckTimeoutCount -Sum).Sum
        )
        $bTuple = @(
            ($BuildBRows | Measure-Object -Property TxRetryCountTotal -Sum).Sum,
            ($BuildBRows | Measure-Object -Property MaxRetrySeen -Maximum).Maximum,
            ($BuildBRows | Measure-Object -Property AckTimeoutCount -Sum).Sum
        )
        for ($i = 0; $i -lt 3; $i++) {
            if ([double]$aTuple[$i] -lt [double]$bTuple[$i]) {
                return "BuildA"
            }
            if ([double]$bTuple[$i] -lt [double]$aTuple[$i]) {
                return "BuildB"
            }
        }
        return "BuildB"
    }
    return ""
}

"P4A_TXACK_REQUAL_SEQUENCE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "PAYLOAD_BYTES=$PayloadBytes"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"
Write-SummaryLine "RUNS_PER_BUILD=$RunsPerBuild"
Write-SummaryLine "REQUAL_RUNS=$RequalRuns"
Write-SummaryLine "SKIP_BUILDS=$([int]$SkipBuilds.IsPresent)"
Write-SummaryLine "SKIP_SOFT_RECOVERY=$([int]$SkipSoftRecovery.IsPresent)"
Write-SummaryLine "SKIP_PREFLIGHT_AFTER_FIRST=$([int]$SkipPreflightAfterFirst.IsPresent)"
Write-SummaryLine "CONTINUE_ON_FAIL=$([int]$ContinueOnFail.IsPresent)"
Write-SummaryLine "AB_CSV=$abCsv"
Write-SummaryLine "REQUAL_CSV=$requalCsv"
Write-SummaryLine "SINGLE_TFDU_TRAFFIC_RUN_SECONDS=$StageSeconds"

Write-AbHeader
Write-RequalHeader

$allRows = @()
$buildRows = @{}
$runCounter = 0
foreach ($build in @("BuildA", "BuildB")) {
    $cfg = Get-BuildConfig -Build $build
    $buildExit = Invoke-ProfileBuild -Build $build
    if ($buildExit -ne 0) {
        Write-SummaryLine "P4A_SEQUENCE_BUILD_BLOCKED build=$build exit=$buildExit"
        if (-not $ContinueOnFail) {
            break
        }
    }
    $buildRows[$build] = @()
    for ($run = 1; $run -le $RunsPerBuild; $run++) {
        $runCounter += 1
        $skipPreflightThisRun = $SkipPreflightAfterFirst -and $runCounter -gt 1
        $row = Invoke-P4aRun -Label $build -Build $build -RunIndex $run -SkipPreflight:$skipPreflightThisRun
        $row | Add-Member -NotePropertyName DetectStart -NotePropertyValue $cfg.DetectStart
        $row | Add-Member -NotePropertyName DetectEnd -NotePropertyValue $cfg.DetectEnd
        $row | Add-Member -NotePropertyName Realign -NotePropertyValue $cfg.Realign
        Add-AbRow -Row $row
        $buildRows[$build] += $row
        $allRows += $row
        if ($row.Status -ne "PASS") {
            Write-SummaryLine "P4A_AB_RUN_FAIL_RECORDED build=$build run=$run"
        }
    }
}

$selected = Select-Tuning -BuildARows @($buildRows["BuildA"]) -BuildBRows @($buildRows["BuildB"])
Write-SummaryLine "P4A_SELECTED_TUNING=$selected"

if ($selected -eq "") {
    Write-SummaryLine "P4A_REQUAL_SKIPPED_NO_CLEAN_TUNING=1"
    $reportOut = Join-Path $reportsDir "P4A_txack_requal_sequence_$stamp.report.out.log"
    $reportErr = Join-Path $reportsDir "P4A_txack_requal_sequence_$stamp.report.err.log"
    $reportExit = Invoke-LoggedProcess `
        -FilePath "python" `
        -Arguments @($reportBuilder) `
        -StdoutPath $reportOut `
        -StderrPath $reportErr `
        -TimeoutSeconds 300
    if ($reportExit -ne 0 -and (Test-Path -LiteralPath $reportOut) -and ((Get-Content -LiteralPath $reportOut -Raw -ErrorAction SilentlyContinue) -match "P4_CONSTRAINED_EXECUTION_REPORTS_BUILT=1")) {
        Write-SummaryLine "REPORT_REBUILD_EXIT_OVERRIDDEN_BY_DONE_MARKER=1"
        $reportExit = 0
    }
    Write-SummaryLine "REPORT_REBUILD_EXIT=$reportExit"
    Write-SummaryLine "P4A_TXACK_REQUAL_SEQUENCE_END $(Get-Date -Format o)"
    exit 40
}

$lastBuild = ""
if ($allRows.Count -gt 0) {
    $lastBuild = $allRows[$allRows.Count - 1].Build
}
if ($selected -ne $lastBuild -and -not $SkipBuilds) {
    $selectedBuildExit = Invoke-ProfileBuild -Build $selected
    if ($selectedBuildExit -ne 0) {
        Write-SummaryLine "P4A_SELECTED_REBUILD_FAIL selected=$selected exit=$selectedBuildExit"
        Write-SummaryLine "P4A_TXACK_REQUAL_SEQUENCE_END $(Get-Date -Format o)"
        exit $selectedBuildExit
    }
}

$requalPass = $true
for ($run = 1; $run -le $RequalRuns; $run++) {
    $runCounter += 1
    $skipPreflightThisRun = $SkipPreflightAfterFirst -and $runCounter -gt 1
    $row = Invoke-P4aRun -Label ("REQUAL_{0}" -f $selected) -Build $selected -RunIndex $run -SkipPreflight:$skipPreflightThisRun
    $row | Add-Member -NotePropertyName SelectedTuning -NotePropertyValue $selected
    Add-RequalRow -Row $row
    if ($row.Status -ne "PASS") {
        $requalPass = $false
        Write-SummaryLine "P4A_REQUAL_FAIL run=$run"
        if (-not $ContinueOnFail) {
            break
        }
    }
}

$reportOut = Join-Path $reportsDir "P4A_txack_requal_sequence_$stamp.report.out.log"
$reportErr = Join-Path $reportsDir "P4A_txack_requal_sequence_$stamp.report.err.log"
$reportExit = Invoke-LoggedProcess `
    -FilePath "python" `
    -Arguments @($reportBuilder) `
    -StdoutPath $reportOut `
    -StderrPath $reportErr `
    -TimeoutSeconds 300
if ($reportExit -ne 0 -and (Test-Path -LiteralPath $reportOut) -and ((Get-Content -LiteralPath $reportOut -Raw -ErrorAction SilentlyContinue) -match "P4_CONSTRAINED_EXECUTION_REPORTS_BUILT=1")) {
    Write-SummaryLine "REPORT_REBUILD_EXIT_OVERRIDDEN_BY_DONE_MARKER=1"
    $reportExit = 0
}
Write-SummaryLine "REPORT_REBUILD_EXIT=$reportExit"
Write-SummaryLine "REPORT_REBUILD_OUT=$reportOut"
Write-SummaryLine "REPORT_REBUILD_ERR=$reportErr"
Write-SummaryLine "P4A_REQUAL_PASS=$([int]$requalPass)"
Write-SummaryLine "P4A_TXACK_REQUAL_SEQUENCE_END $(Get-Date -Format o)"

if ($requalPass -and $reportExit -eq 0) {
    exit 0
}
exit 50
