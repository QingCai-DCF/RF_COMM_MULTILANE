param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactDir,
    [ValidateSet("a2b_ack", "b2a_rx", "any")]
    [string]$ExpectedMode = "any",
    [string]$Label = "",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$XsctWaitSeconds = 60,
    [int]$PostStartSeconds = 85,
    [int]$CaptureSeconds = 150,
    [switch]$SkipPreflight,
    [switch]$RequirePass
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$artifactPath = (Resolve-Path -LiteralPath $ArtifactDir).Path
if (-not $Label) {
    $Label = Split-Path -Leaf $artifactPath
}
$safeLabel = ($Label -replace "[^A-Za-z0-9_.-]", "_")
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$summaryLog = Join-Path $reportsDir "lane0_artifact_${safeLabel}_${stamp}.summary.txt"
$uartLog = Join-Path $reportsDir "uart_lane0_artifact_${safeLabel}_${stamp}.log"
$xsctOutLog = Join-Path $reportsDir "xsct_lane0_artifact_${safeLabel}_${stamp}.out.log"
$xsctErrLog = Join-Path $reportsDir "xsct_lane0_artifact_${safeLabel}_${stamp}.err.log"
$preflightLog = Join-Path $reportsDir "lane0_artifact_${safeLabel}_${stamp}.preflight.log"
$shutdownLog = Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_artifact_${safeLabel}_${stamp}.log"
$shutdownOutLog = Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_artifact_${safeLabel}_${stamp}.out.log"
$shutdownErrLog = Join-Path $reportsDir "program_tfdu_shutdown_after_lane0_artifact_${safeLabel}_${stamp}.err.log"

$programTcl = Join-Path $artifactPath "program_this_artifact.tcl"
$bitPath = Join-Path $artifactPath "design_shiboqi_wrapper.bit"
$elfPath = Join-Path $artifactPath "rf_comm_ps_ps_loopback.elf"
$xsaPath = Join-Path $artifactPath "design_shiboqi_wrapper.xsa"
$ltxPath = Join-Path $artifactPath "design_shiboqi_wrapper.ltx"
$ps7InitPath = Join-Path $artifactPath "ps7_init.tcl"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"

foreach ($path in @($XsctPath, $VivadoPath, $programTcl, $bitPath, $elfPath, $ps7InitPath, $shutdownTcl, $preflightScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Get-FileHashOrEmpty {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    }
    return ""
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

function Get-StageFieldInt {
    param(
        $Fields,
        [string]$Name
    )
    if ($Fields.ContainsKey($Name)) {
        $value = $Fields[$Name] -replace "%$", ""
        $parsed = 0
        if ([int]::TryParse($value, [ref]$parsed)) {
            return $parsed
        }
    }
    return 0
}

function Convert-LineToFields {
    param([string]$Line)
    $fields = @{}
    foreach ($match in [regex]::Matches($Line, "([A-Za-z0-9_]+)=([^\s]+)")) {
        $fields[$match.Groups[1].Value] = $match.Groups[2].Value
    }
    return $fields
}

function Test-CleanA2B {
    param($Fields)
    $sent = Get-StageFieldInt -Fields $Fields -Name "sent"
    $rxOk = Get-StageFieldInt -Fields $Fields -Name "rx_ok"
    $txFail = Get-StageFieldInt -Fields $Fields -Name "tx_fail"
    $rxTimeout = Get-StageFieldInt -Fields $Fields -Name "rx_timeout"
    $rxBad = Get-StageFieldInt -Fields $Fields -Name "rx_bad"
    $rxMismatch = Get-StageFieldInt -Fields $Fields -Name "rx_mismatch"
    $lastError = if ($Fields.ContainsKey("last_error")) { $Fields["last_error"] } else { "none" }
    return ($sent -gt 0 -and $rxOk -eq $sent -and $txFail -eq 0 -and $rxTimeout -eq 0 -and $rxBad -eq 0 -and $rxMismatch -eq 0 -and $lastError -eq "none")
}

function Test-CleanB2A {
    param($Fields)
    $rxOk = Get-StageFieldInt -Fields $Fields -Name "rx_ok"
    $txFail = Get-StageFieldInt -Fields $Fields -Name "tx_fail"
    $rxTimeout = Get-StageFieldInt -Fields $Fields -Name "rx_timeout"
    $rxBad = Get-StageFieldInt -Fields $Fields -Name "rx_bad"
    $rxMismatch = Get-StageFieldInt -Fields $Fields -Name "rx_mismatch"
    $lastError = if ($Fields.ContainsKey("last_error")) { $Fields["last_error"] } else { "none" }
    return ($rxOk -gt 0 -and $txFail -eq 0 -and $rxTimeout -eq 0 -and $rxBad -eq 0 -and $rxMismatch -eq 0 -and $lastError -eq "none")
}

function Get-UartVerdict {
    param(
        [string]$Text,
        [string]$Mode
    )

    $lines = @($Text -split "`r?`n" | Where-Object { $_ -match "PSPS_STAGE_SUMMARY|PSPS_RX_ONLY_SUMMARY" })
    if ($lines.Count -eq 0) {
        return [ordered]@{
            verdict = "INDETERMINATE_NO_STAGE_SUMMARY"
            evidence = ""
        }
    }

    foreach ($line in ($lines | Select-Object -Last 20)) {
        $fields = Convert-LineToFields -Line $line
        if (($Mode -eq "a2b_ack" -or $Mode -eq "any") -and $line -match "PSPS_STAGE_SUMMARY" -and (Test-CleanA2B -Fields $fields)) {
            return [ordered]@{
                verdict = "PASS_A2B_CLEAN_COUNTERS"
                evidence = $line
            }
        }
        if (($Mode -eq "b2a_rx" -or $Mode -eq "any") -and $line -match "PSPS_RX_ONLY_SUMMARY" -and (Test-CleanB2A -Fields $fields)) {
            return [ordered]@{
                verdict = "PASS_B2A_CLEAN_COUNTERS"
                evidence = $line
            }
        }
    }

    return [ordered]@{
        verdict = "FAIL_OR_INDETERMINATE_COUNTERS"
        evidence = [string]($lines | Select-Object -Last 1)
    }
}

"LANE0_ARTIFACT_SAFE_RUN_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "ARTIFACT_DIR=$artifactPath"
Write-SummaryLine "EXPECTED_MODE=$ExpectedMode"
Write-SummaryLine "UART_LOG=$uartLog"
Write-SummaryLine "XSCT_STDOUT_LOG=$xsctOutLog"
Write-SummaryLine "XSCT_STDERR_LOG=$xsctErrLog"
Write-SummaryLine "SHUTDOWN_LOG=$shutdownLog"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "XSCT_WAIT_SECONDS=$XsctWaitSeconds"
Write-SummaryLine "POST_START_SECONDS=$PostStartSeconds"
Write-SummaryLine "CAPTURE_SECONDS=$CaptureSeconds"
Write-SummaryLine "BIT_SHA256=$(Get-FileHashOrEmpty -Path $bitPath)"
Write-SummaryLine "ELF_SHA256=$(Get-FileHashOrEmpty -Path $elfPath)"
Write-SummaryLine "XSA_SHA256=$(Get-FileHashOrEmpty -Path $xsaPath)"
Write-SummaryLine "LTX_SHA256=$(Get-FileHashOrEmpty -Path $ltxPath)"

$xsctHwServerUrl = if ($HwServerUrl -match "^[Tt][Cc][Pp]:") { $HwServerUrl } else { "TCP:$HwServerUrl" }
Write-SummaryLine "XSCT_HW_SERVER_URL=$xsctHwServerUrl"

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
    $preflightText = ""
    if (Test-Path -LiteralPath $preflightLog) {
        $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
        foreach ($line in (($preflightText -split "`r?`n") | Where-Object { $_ -match "COM_PORT_PRESENT|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT" })) {
            Write-SummaryLine "PREFLIGHT_MATCH=$line"
        }
    }
    if ($preflightText -notmatch "HW_PREFLIGHT_RESULT PASS" -or $preflightText -notmatch "HW_PREFLIGHT_ZYNQ") {
        Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
        Write-SummaryLine "LANE0_ARTIFACT_SAFE_RUN_END $(Get-Date -Format o)"
        exit 20
    }
}

$uartJob = Start-Job -ScriptBlock {
    param($Port, $Rate, $LogPath, $Seconds)

    "UART_CAPTURE_BEGIN $(Get-Date -Format o) port=$Port baud=$Rate" | Out-File -LiteralPath $LogPath -Encoding ascii
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
                Add-Content -LiteralPath $LogPath -Value "`r`nUART_OPEN_RETRY attempt=$attempt error=$($_.Exception.Message)" -Encoding ascii
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
                Add-Content -LiteralPath $LogPath -Value $chunk -NoNewline -Encoding ascii
            }
            Start-Sleep -Milliseconds 50
        }
    } catch {
        Add-Content -LiteralPath $LogPath -Value "`r`nUART_CAPTURE_ERROR $($_.Exception.Message)" -Encoding ascii
    } finally {
        if ($serial -and $serial.IsOpen) {
            $serial.Close()
        }
        Add-Content -LiteralPath $LogPath -Value "`r`nUART_CAPTURE_END $(Get-Date -Format o)" -Encoding ascii
    }
} -ArgumentList $ComPort, $BaudRate, $uartLog, $CaptureSeconds

$shutdownExit = $null
$xsctExit = $null
try {
    Write-SummaryLine "XSCT_START=$(Get-Date -Format o)"
    $xsctExit = Invoke-LoggedProcess `
        -FilePath $XsctPath `
        -Arguments @($programTcl, $xsctHwServerUrl) `
        -StdoutPath $xsctOutLog `
        -StderrPath $xsctErrLog `
        -TimeoutSeconds $XsctWaitSeconds
    Write-SummaryLine "XSCT_EXIT=$xsctExit"
    $programMarkerPresent = $false
    if (Test-Path -LiteralPath $xsctOutLog) {
        $xsctOutText = Get-Content -LiteralPath $xsctOutLog -Raw -ErrorAction SilentlyContinue
        $programMarkerPresent = ($xsctOutText -match "RF_COMM_ARTIFACT_PROGRAMMED_AND_ELF_STARTED")
        foreach ($line in (($xsctOutText -split "`r?`n") | Where-Object {
            $_ -match "RF_COMM_ARTIFACT_PROGRAMMED_AND_ELF_STARTED|RF_COMM lane0 artifact programming|bit:|elf:|init:"
        })) {
            Write-SummaryLine "XSCT_MATCH=$line"
        }
    }
    Write-SummaryLine "XSCT_PROGRAM_MARKER_PRESENT=$([int]$programMarkerPresent)"
    if (-not $programMarkerPresent -and $xsctExit -eq 0) {
        $xsctExit = 30
        Write-SummaryLine "XSCT_EXIT_OVERRIDDEN_NO_PROGRAM_MARKER=30"
    }

    if ($PostStartSeconds -gt 0) {
        Start-Sleep -Seconds $PostStartSeconds
    }
} finally {
    Write-SummaryLine "SHUTDOWN_START=$(Get-Date -Format o)"
    $shutdownExit = Invoke-LoggedProcess `
        -FilePath $VivadoPath `
        -Arguments @("-mode", "batch", "-source", $shutdownTcl) `
        -StdoutPath $shutdownOutLog `
        -StderrPath $shutdownErrLog `
        -TimeoutSeconds 120
    @(
        "STDOUT:"
        if (Test-Path -LiteralPath $shutdownOutLog) { Get-Content -LiteralPath $shutdownOutLog -ErrorAction SilentlyContinue }
        "STDERR:"
        if (Test-Path -LiteralPath $shutdownErrLog) { Get-Content -LiteralPath $shutdownErrLog -ErrorAction SilentlyContinue }
    ) | Out-File -LiteralPath $shutdownLog -Encoding ascii
    $shutdownText = ""
    if (Test-Path -LiteralPath $shutdownLog) {
        $shutdownText = Get-Content -LiteralPath $shutdownLog -Raw -ErrorAction SilentlyContinue
    }
    if ($shutdownExit -ne 0 -and $shutdownText -match "TFDU_SHUTDOWN_PROGRAMMED") {
        $shutdownExit = 0
        Write-SummaryLine "SHUTDOWN_EXIT_INFERRED=0"
    }
    Write-SummaryLine "SHUTDOWN_EXIT=$shutdownExit"

    Wait-Job -Job $uartJob -Timeout 5 | Out-Null
    if ($uartJob.State -eq "Running") {
        Stop-Job -Job $uartJob -ErrorAction SilentlyContinue
    }
    Receive-Job -Job $uartJob -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $uartJob -Force -ErrorAction SilentlyContinue
}

$verdict = [ordered]@{
    verdict = "INDETERMINATE_UART_LOG_MISSING"
    evidence = ""
}
if (Test-Path -LiteralPath $uartLog) {
    $uartText = Get-Content -LiteralPath $uartLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($uartText -split "`r?`n") | Where-Object {
        $_ -match "PSPS_(INIT_OK|STAGE_BEGIN|STATS|STAGE_SUMMARY|RX_ONLY_STATS|RX_ONLY_SUMMARY)|RF_COMM PS-PS loopback"
    } | Select-Object -Last 30)) {
        Write-SummaryLine "UART_MATCH=$line"
    }
    $verdict = Get-UartVerdict -Text $uartText -Mode $ExpectedMode
}

Write-SummaryLine "ARTIFACT_LOG_VERDICT=$($verdict.verdict)"
if ($verdict.evidence) {
    Write-SummaryLine "ARTIFACT_LOG_EVIDENCE=$($verdict.evidence)"
}

Write-SummaryLine "LANE0_ARTIFACT_SAFE_RUN_END $(Get-Date -Format o)"

if ($shutdownExit -ne 0) {
    throw "Shutdown programming failed, see $shutdownLog"
}
if ($xsctExit -ne 0) {
    exit $xsctExit
}
if ($RequirePass -and $verdict.verdict -notlike "PASS_*") {
    exit 40
}
exit 0
