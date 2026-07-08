param(
    [int]$RequestedPhysicalLane = 1,
    [int]$LogicalProbeLane = 0,
    [string]$LaneMask = "0x1",
    [string]$SessionId = "0x2201",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [int]$JtagFrequencyHz = 1000000,
    [int]$StageSeconds = 20,
    [int]$RepeatCount = 3,
    [int]$PreCaptureDelaySeconds = 2,
    [int]$CaptureTimeoutSeconds = 90,
    [int]$ShutdownTimeoutSeconds = 90,
    [switch]$SkipBuild,
    [switch]$SkipPreflight,
    [switch]$GuardOnly
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$prefix = "P7A_rx_only_lane${RequestedPhysicalLane}_logical${LogicalProbeLane}_$stamp"
$summaryLog = Join-Path $reportsDir "$prefix.summary.txt"
$reportMd = Join-Path $reportsDir "P7A_03_txd_disable_rx_only_report_lane${RequestedPhysicalLane}_$stamp.md"
$preflightLog = Join-Path $reportsDir "$prefix.preflight.log"
$preflightErrLog = Join-Path $reportsDir "$prefix.preflight.log.err"
$buildLog = Join-Path $reportsDir "$prefix.build_rx_only.log"
$initOutLog = Join-Path $reportsDir "$prefix.xsct_init.out.log"
$initErrLog = Join-Path $reportsDir "$prefix.xsct_init.err.log"
$elfOutLog = Join-Path $reportsDir "$prefix.xsct_elf.out.log"
$elfErrLog = Join-Path $reportsDir "$prefix.xsct_elf.err.log"
$uartLog = Join-Path $reportsDir "$prefix.uart.log"
$analysisMd = Join-Path $reportsDir "$prefix.ila_analysis.md"
$analysisJson = Join-Path $reportsDir "$prefix.ila_analysis.json"
$analysisLog = Join-Path $reportsDir "$prefix.ila_analysis.log"
$analysisJsonLog = Join-Path $reportsDir "$prefix.ila_analysis_json.log"
$shutdownLog = Join-Path $reportsDir "$prefix.shutdown.log"
$shutdownOutLog = Join-Path $reportsDir "$prefix.shutdown.out.log"
$shutdownErrLog = Join-Path $reportsDir "$prefix.shutdown.err.log"

$buildScript = Join-Path $repoRoot "tools\build_psps_rx_only_elf.ps1"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$initTcl = Join-Path $repoRoot "software\ps_ps_loopback\program_fpga_init_ps7.tcl"
$elfTcl = Join-Path $repoRoot "software\ps_ps_loopback\run_elf_only.tcl"
$ilaTcl = Join-Path $repoRoot "tools\capture_2lane_ila_once.tcl"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$analyzerScript = Join-Path $repoRoot "tools\analyze_2lane_ila_csv.py"
$bitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"

foreach ($path in @($XsctPath, $VivadoPath, $initTcl, $elfTcl, $ilaTcl, $shutdownTcl, $analyzerScript, $bitPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}
if (-not $SkipBuild -and -not (Test-Path -LiteralPath $buildScript)) {
    throw "Required path is missing: $buildScript"
}
if (-not $SkipPreflight -and -not (Test-Path -LiteralPath $preflightScript)) {
    throw "Required path is missing: $preflightScript"
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
        [string]$LogPath,
        [string]$ErrPath,
        [int]$TimeoutSeconds
    )

    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError $ErrPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 0
    }
    return $proc.ExitCode
}

function Wait-FileContains {
    param(
        [string]$Path,
        [string]$Pattern,
        [int]$TimeoutSeconds
    )

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (Test-Path -LiteralPath $Path) {
            $text = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
            if ($text -match $Pattern) {
                return $true
            }
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Get-SignalMetric {
    param(
        [object]$Analysis,
        [string]$Name
    )
    if ($Analysis -and $Analysis.signals -and ($Analysis.signals.PSObject.Properties.Name -contains $Name)) {
        return $Analysis.signals.$Name
    }
    return $null
}

function Metric-Pulses {
    param([object]$Metric)
    if ($null -eq $Metric) { return -1 }
    return [int]$Metric.pulse_count
}

function New-ReportFromAnalysis {
    param(
        [string]$Path,
        [object[]]$Analyses,
        [string[]]$Csvs,
        [string]$JsonPath,
        [string]$MdPath,
        [string]$ShutdownExit,
        [string]$BitHash,
        [string]$ElfHash
    )

    $aTxKey = "a_tx$LogicalProbeLane"
    $aRxKey = "a_rx$LogicalProbeLane"
    $bTxKey = "b_tx$LogicalProbeLane"
    $bRxKey = "b_rx$LogicalProbeLane"

    $rows = @()
    $txPulsesTotal = 0
    $rxPulsesTotal = 0
    foreach ($analysis in @($Analyses)) {
        $aTx = Get-SignalMetric -Analysis $analysis -Name $aTxKey
        $aRx = Get-SignalMetric -Analysis $analysis -Name $aRxKey
        $bTx = Get-SignalMetric -Analysis $analysis -Name $bTxKey
        $bRx = Get-SignalMetric -Analysis $analysis -Name $bRxKey
        $aTxP = Metric-Pulses -Metric $aTx
        $aRxP = Metric-Pulses -Metric $aRx
        $bTxP = Metric-Pulses -Metric $bTx
        $bRxP = Metric-Pulses -Metric $bRx
        if ($aTxP -gt 0) { $txPulsesTotal += $aTxP }
        if ($bTxP -gt 0) { $txPulsesTotal += $bTxP }
        if ($aRxP -gt 0) { $rxPulsesTotal += $aRxP }
        if ($bRxP -gt 0) { $rxPulsesTotal += $bRxP }
        $rows += "| $([IO.Path]::GetFileName($analysis.csv_path)) | $aTxP | $aRxP | $bTxP | $bRxP | $($analysis.verdict) | $($analysis.verdict_reason) |"
    }

    $txIdle = ($txPulsesTotal -eq 0)
    $rxQuiet = ($rxPulsesTotal -eq 0)
    $idleResult = if ($txIdle -and $rxQuiet) { "PASS_RX_QUIET" } elseif ($txIdle) { "FAIL_RX_ACTIVITY_WITH_TXD_IDLE" } else { "INVALID_TXD_NOT_IDLE" }
    $echoPresent = if ($txIdle -and -not $rxQuiet) { 1 } else { 0 }

    $lines = @(
        "# P7A-02/P7A-03 Lane $RequestedPhysicalLane RX-only ILA Report",
        "",
        "REQUESTED_PHYSICAL_LANE=$RequestedPhysicalLane",
        "LOGICAL_PROBE_LANE=$LogicalProbeLane",
        "LANE_MASK=$LaneMask",
        "SESSION_ID=$SessionId",
        "EVIDENCE_LEVEL=RAW_ILA_RX_ONLY",
        "BIT_SHA256=$BitHash",
        "ELF_SHA256=$ElfHash",
        "ANALYSIS_JSON=$JsonPath",
        "ANALYSIS_MD=$MdPath",
        "SHUTDOWN_EXIT=$ShutdownExit",
        "",
        "P7A_02_IDLE_BASELINE_RESULT=$idleResult",
        "P7A_03_TXD_DISABLE_ECHO_PRESENT=$echoPresent",
        "P7A_03_TXD_IDLE_VERIFIED=$([int]$txIdle)",
        "P7A_03_RX_QUIET_WHEN_TXD_IDLE=$([int]$rxQuiet)",
        "",
        "| csv | ${aTxKey}_pulses | ${aRxKey}_pulses | ${bTxKey}_pulses | ${bRxKey}_pulses | analyzer_verdict | reason |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |"
    )
    $lines += $rows
    $lines += @(
        "",
        "Boundary: this run checks raw ILA activity with RX enabled and no PS TX traffic queued. It does not prove DATA/protocol connectivity.",
        "P7A_04_NOT_COVERED_BY_THIS_RUN=1"
    )

    $lines | Out-File -FilePath $Path -Encoding utf8
}

"P7A_RX_ONLY_ILA_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "REQUESTED_PHYSICAL_LANE=$RequestedPhysicalLane"
Write-SummaryLine "LOGICAL_PROBE_LANE=$LogicalProbeLane"
Write-SummaryLine "LANE_MASK=$LaneMask"
Write-SummaryLine "SESSION_ID=$SessionId"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"
Write-SummaryLine "REPEAT_COUNT=$RepeatCount"
Write-SummaryLine "PRE_CAPTURE_DELAY_SECONDS=$PreCaptureDelaySeconds"
Write-SummaryLine "SKIP_BUILD=$([int]$SkipBuild.IsPresent)"
Write-SummaryLine "SKIP_PREFLIGHT=$([int]$SkipPreflight.IsPresent)"
Write-SummaryLine "GUARD_ONLY=$([int]$GuardOnly.IsPresent)"
Write-SummaryLine "REPORT_MD=$reportMd"

$bitHash = Get-FileHash -Algorithm SHA256 -LiteralPath $bitPath
Write-SummaryLine "PRE_BIT=$bitPath"
Write-SummaryLine "PRE_BIT_SHA256=$($bitHash.Hash)"
Write-SummaryLine "PRE_BIT_SIZE=$((Get-Item -LiteralPath $bitPath).Length)"
if (Test-Path -LiteralPath $elfPath) {
    $preElfHash = Get-FileHash -Algorithm SHA256 -LiteralPath $elfPath
    Write-SummaryLine "PRE_ELF=$elfPath"
    Write-SummaryLine "PRE_ELF_SHA256=$($preElfHash.Hash)"
    Write-SummaryLine "PRE_ELF_SIZE=$((Get-Item -LiteralPath $elfPath).Length)"
} else {
    Write-SummaryLine "PRE_ELF=MISSING"
}

if ($GuardOnly) {
    Write-SummaryLine "GUARD_ONLY_NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "GUARD_ONLY_NO_UART_WRITE=1"
    Write-SummaryLine "GUARD_ONLY_NO_TFDU_DRIVE=1"
    Write-SummaryLine "P7A_RX_ONLY_ILA_SAFE_END $(Get-Date -Format o)"
    Write-SummaryLine "RUN_RESULT_STATUS=PASS_GUARD_ONLY"
    Write-SummaryLine "RUN_EXIT_CODE=0"
    exit 0
}

if (-not $SkipBuild) {
    Write-SummaryLine "BUILD_RX_ONLY_START=$(Get-Date -Format o)"
    $buildExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $buildScript,
        "-XsctPath",
        $XsctPath,
        "-LaneMask",
        $LaneMask,
        "-SessionId",
        $SessionId,
        "-StageSeconds",
        [string]$StageSeconds
    ) -LogPath $buildLog -ErrPath ($buildLog + ".err") -TimeoutSeconds 300
    Write-SummaryLine "BUILD_RX_ONLY_EXIT=$buildExit"
    if (Test-Path -LiteralPath $buildLog) {
        $buildText = Get-Content -LiteralPath $buildLog -Raw -ErrorAction SilentlyContinue
        foreach ($line in (($buildText -split "`r?`n") | Where-Object { $_ -match "BUILD_RESULT|ELF_SHA256|LANE_MASK|SESSION_ID|PSPS_RX_ONLY|NO_TFDU_DRIVE" })) {
            Write-SummaryLine "BUILD_MATCH=$line"
        }
    }
    if ($buildExit -ne 0) {
        Write-SummaryLine "P7A_RX_ONLY_ILA_SAFE_END $(Get-Date -Format o)"
        Write-SummaryLine "RUN_RESULT_STATUS=FAIL_BUILD_RX_ONLY"
        Write-SummaryLine "RUN_EXIT_CODE=$buildExit"
        exit $buildExit
    }
}

if (-not (Test-Path -LiteralPath $elfPath)) {
    throw "RX-only ELF missing after build: $elfPath"
}
$runElfHash = Get-FileHash -Algorithm SHA256 -LiteralPath $elfPath
Write-SummaryLine "RUN_ELF=$elfPath"
Write-SummaryLine "RUN_ELF_SHA256=$($runElfHash.Hash)"
Write-SummaryLine "RUN_ELF_SIZE=$((Get-Item -LiteralPath $elfPath).Length)"

if (-not $SkipPreflight) {
    Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
    $preflightExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $preflightScript,
        "-ComPort",
        $ComPort,
        "-BaudRate",
        [string]$BaudRate,
        "-VivadoPath",
        $VivadoPath,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz
    ) -LogPath $preflightLog -ErrPath $preflightErrLog -TimeoutSeconds 120
    Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
    $preflightText = ""
    if (Test-Path -LiteralPath $preflightLog) {
        $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
        foreach ($line in (($preflightText -split "`r?`n") | Where-Object { $_ -match "COM_PORT_PRESENT|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT" })) {
            Write-SummaryLine "PREFLIGHT_MATCH=$line"
        }
    }
    $preflightPassed = ($preflightText -match "HW_PREFLIGHT_RESULT PASS" -and $preflightText -match "HW_PREFLIGHT_ZYNQ")
    Write-SummaryLine "PREFLIGHT_PASS_PARSED=$([int]$preflightPassed)"
    if (-not $preflightPassed) {
        Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
        Write-SummaryLine "P7A_RX_ONLY_ILA_SAFE_END $(Get-Date -Format o)"
        Write-SummaryLine "RUN_RESULT_STATUS=FAIL_PREFLIGHT"
        Write-SummaryLine "RUN_EXIT_CODE=20"
        exit 20
    }
}

$uartJob = $null
$shutdownExit = $null
$runError = $null
$csvs = @()
$summaries = @()
$runStart = Get-Date

try {
    $uartSeconds = [Math]::Max(60, ($StageSeconds + ($RepeatCount * 20) + 30))
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
    } -ArgumentList $ComPort, $BaudRate, $uartLog, $uartSeconds

    Write-SummaryLine "INIT_START=$(Get-Date -Format o)"
    $initExit = Invoke-LoggedProcess -FilePath $XsctPath -Arguments @($initTcl) -LogPath $initOutLog -ErrPath $initErrLog -TimeoutSeconds 60
    Write-SummaryLine "INIT_EXIT=$initExit"
    if ($initExit -ne 0) {
        throw "FPGA/PS7 init failed"
    }

    Write-SummaryLine "ELF_START=$(Get-Date -Format o)"
    $elfExit = Invoke-LoggedProcess -FilePath $XsctPath -Arguments @($elfTcl) -LogPath $elfOutLog -ErrPath $elfErrLog -TimeoutSeconds 30
    Write-SummaryLine "ELF_EXIT=$elfExit"
    if ($elfExit -ne 0) {
        throw "ELF start failed"
    }

    $stageSeen = Wait-FileContains -Path $uartLog -Pattern "PSPS_STAGE_BEGIN|mode=rx_only_b2a_probe" -TimeoutSeconds 20
    Write-SummaryLine "UART_RX_ONLY_STAGE_SEEN=$([int]$stageSeen)"
    if (-not $stageSeen) {
        Write-SummaryLine "UART_RX_ONLY_STAGE_WARN=stage marker not seen before ILA captures"
    }

    Start-Sleep -Seconds $PreCaptureDelaySeconds
    for ($idx = 1; $idx -le $RepeatCount; $idx++) {
        $csv = Join-Path $reportsDir ("P7A_03_txd_disable_rx_only_lane{0}_r{1}_{2}.csv" -f $RequestedPhysicalLane, $idx, $stamp)
        $ilaSummary = $csv -replace "\.csv$", ".summary.txt"
        $ilaOutLog = $csv -replace "\.csv$", ".out.log"
        $ilaErrLog = $csv -replace "\.csv$", ".err.log"
        Write-SummaryLine "ILA_CAPTURE_START repeat=$idx csv=$csv"
        $ilaExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @(
            "-mode",
            "batch",
            "-source",
            $ilaTcl,
            "-tclargs",
            $csv,
            $ilaSummary,
            "now",
            [string]$JtagFrequencyHz
        ) -LogPath $ilaOutLog -ErrPath $ilaErrLog -TimeoutSeconds $CaptureTimeoutSeconds
        Write-SummaryLine "ILA_CAPTURE_EXIT repeat=$idx exit=$ilaExit"
        if (Test-Path -LiteralPath $csv) {
            Write-SummaryLine "ILA_CAPTURE_CSV repeat=$idx path=$csv size=$((Get-Item -LiteralPath $csv).Length)"
            $csvs += $csv
            $summaries += $ilaSummary
        } else {
            Write-SummaryLine "ILA_CAPTURE_CSV_MISSING repeat=$idx path=$csv"
        }
        Start-Sleep -Seconds 1
    }
} catch {
    $runError = $_
    Write-SummaryLine "RUN_ERROR=$($_.Exception.Message)"
} finally {
    Write-SummaryLine "SHUTDOWN_START=$(Get-Date -Format o)"
    $shutdownExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @(
        "-mode",
        "batch",
        "-source",
        $shutdownTcl
    ) -LogPath $shutdownOutLog -ErrPath $shutdownErrLog -TimeoutSeconds $ShutdownTimeoutSeconds
    @(
        "STDOUT:"
        if (Test-Path -LiteralPath $shutdownOutLog) { Get-Content -LiteralPath $shutdownOutLog -ErrorAction SilentlyContinue }
        "STDERR:"
        if (Test-Path -LiteralPath $shutdownErrLog) { Get-Content -LiteralPath $shutdownErrLog -ErrorAction SilentlyContinue }
    ) | Out-File -FilePath $shutdownLog -Encoding ascii
    Write-SummaryLine "SHUTDOWN_EXIT=$shutdownExit"
    $shutdownText = ""
    if (Test-Path -LiteralPath $shutdownLog) {
        $shutdownText = Get-Content -LiteralPath $shutdownLog -Raw -ErrorAction SilentlyContinue
    }
    Write-SummaryLine "SHUTDOWN_PROGRAMMED=$([int]($shutdownText -match 'TFDU_SHUTDOWN_PROGRAMMED'))"
    Write-SummaryLine ("HW_WINDOW_TO_SHUTDOWN_END_SECONDS={0:N1}" -f (((Get-Date) - $runStart).TotalSeconds))

    if ($uartJob) {
        Wait-Job -Job $uartJob -Timeout 5 | Out-Null
        if ($uartJob.State -eq "Running") {
            Stop-Job -Job $uartJob -ErrorAction SilentlyContinue
        }
        Receive-Job -Job $uartJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $uartJob -Force -ErrorAction SilentlyContinue
    }
}

if ($csvs.Count -gt 0) {
    Write-SummaryLine "ANALYSIS_START=$(Get-Date -Format o)"
    $analysisExit = Invoke-LoggedProcess -FilePath "python.exe" -Arguments (@($analyzerScript) + $csvs + @("--out", $analysisMd)) -LogPath $analysisLog -ErrPath ($analysisLog + ".err") -TimeoutSeconds 60
    Write-SummaryLine "ANALYSIS_MD_EXIT=$analysisExit"
    $analysisJsonExit = Invoke-LoggedProcess -FilePath "python.exe" -Arguments (@($analyzerScript) + $csvs + @("--json", "--out", $analysisJson)) -LogPath $analysisJsonLog -ErrPath ($analysisJsonLog + ".err") -TimeoutSeconds 60
    Write-SummaryLine "ANALYSIS_JSON_EXIT=$analysisJsonExit"
    if ($analysisJsonExit -eq 0 -and (Test-Path -LiteralPath $analysisJson)) {
        $jsonText = Get-Content -LiteralPath $analysisJson -Raw -Encoding UTF8
        $parsedAnalysis = ConvertFrom-Json -InputObject $jsonText
        if ($parsedAnalysis -is [System.Array]) {
            $analyses = $parsedAnalysis
        } else {
            $analyses = @($parsedAnalysis)
        }
        New-ReportFromAnalysis -Path $reportMd -Analyses $analyses -Csvs $csvs -JsonPath $analysisJson -MdPath $analysisMd -ShutdownExit ([string]$shutdownExit) -BitHash $bitHash.Hash -ElfHash $runElfHash.Hash
        Write-SummaryLine "P7A_REPORT_WRITTEN=$reportMd"
    }
} else {
    Write-SummaryLine "ANALYSIS_SKIPPED_NO_CSV=1"
}

if (Test-Path -LiteralPath $uartLog) {
    $uartText = Get-Content -LiteralPath $uartLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($uartText -split "`r?`n") | Where-Object { $_ -match "RF_COMM|mode=|PSPS_INIT_OK|PSPS_STAGE_BEGIN|PSPS_RX_ONLY_(STATS|SUMMARY)|PSPS_RUN_ONCE_DONE" } | Select-Object -Last 60)) {
        Write-SummaryLine "UART_MATCH=$line"
    }
}

Write-SummaryLine "P7A_RX_ONLY_ILA_SAFE_END $(Get-Date -Format o)"
if ($shutdownExit -ne 0) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_SHUTDOWN"
    Write-SummaryLine "RUN_EXIT_CODE=31"
    exit 31
}
if ($null -ne $runError) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_RUN"
    Write-SummaryLine "RUN_EXIT_CODE=30"
    exit 30
}
if ($csvs.Count -eq 0) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_NO_ILA_CSV"
    Write-SummaryLine "RUN_EXIT_CODE=32"
    exit 32
}

Write-SummaryLine "RUN_RESULT_STATUS=PASS"
Write-SummaryLine "RUN_EXIT_CODE=0"
exit 0
