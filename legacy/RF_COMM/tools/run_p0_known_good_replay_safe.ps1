param(
    [ValidateSet("lane0", "two_lane", "all")]
    [string]$Mode = "all",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [string[]]$TwoLaneTriggerModes = @("b_tx_nonzero"),
    [int]$Lane0XsctWaitSeconds = 70,
    [int]$Lane0PostStartSeconds = 12,
    [int]$Lane0CaptureSeconds = 80,
    [int]$TwoLaneMatrixTimeoutSeconds = 1200,
    [switch]$DryRun,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "p0_known_good_replay_safe_$stamp.summary.txt"
$preflightLog = Join-Path $reportsDir "p0_known_good_replay_safe_$stamp.preflight.log"
$lane0Log = Join-Path $reportsDir "p0_known_good_replay_safe_$stamp.lane0.log"
$twoLaneLog = Join-Path $reportsDir "p0_known_good_replay_safe_$stamp.two_lane.log"

$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$lane0Script = Join-Path $repoRoot "tools\run_lane0_hw_once_safe.ps1"
$twoLaneScript = Join-Path $repoRoot "tools\run_2lane_matrix_safe.ps1"

foreach ($path in @($preflightScript, $lane0Script, $twoLaneScript, $VivadoPath, $XsctPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
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

function Get-LastSummaryValue {
    param(
        [string]$Text,
        [string]$Key
    )
    $matches = [regex]::Matches($Text, "(?m)\b" + [regex]::Escape($Key) + "=([^\s]+)")
    if ($matches.Count -eq 0) {
        return ""
    }
    return $matches[$matches.Count - 1].Groups[1].Value.Trim()
}

function Classify-Lane0Replay {
    param([string]$Text)

    $summaryLines = @($Text -split "`r?`n" | Where-Object { $_ -match "PSPS_STAGE_SUMMARY" })
    if ($summaryLines.Count -eq 0) {
        return "INCONCLUSIVE_NO_STAGE_SUMMARY"
    }
    $lastLine = $summaryLines[$summaryLines.Count - 1]
    $sent = Get-LastSummaryValue -Text $lastLine -Key "sent"
    $rxOk = Get-LastSummaryValue -Text $lastLine -Key "rx_ok"
    $txFail = Get-LastSummaryValue -Text $lastLine -Key "tx_fail"
    $loss = Get-LastSummaryValue -Text $lastLine -Key "loss"
    $error = Get-LastSummaryValue -Text $lastLine -Key "last_error"
    Write-SummaryLine "LANE0_LAST_SUMMARY=$lastLine"
    Write-SummaryLine "LANE0_LAST_SENT=$sent"
    Write-SummaryLine "LANE0_LAST_RX_OK=$rxOk"
    Write-SummaryLine "LANE0_LAST_TX_FAIL=$txFail"
    Write-SummaryLine "LANE0_LAST_LOSS=$loss"
    Write-SummaryLine "LANE0_LAST_ERROR=$error"

    $sentOk = $false
    $sentValue = 0
    if ([int]::TryParse($sent, [ref]$sentValue)) {
        $sentOk = ($sentValue -ge 1000)
    }
    if ($sentOk -and $sent -eq $rxOk -and $txFail -eq "0" -and $loss -eq "0.0%" -and $error -eq "none") {
        return "PASS_LANE0_KNOWN_GOOD_REPLAY"
    }
    return "FAIL_LANE0_KNOWN_GOOD_REPLAY"
}

function Get-Lane0EffectiveExit {
    param(
        [int]$ProcessExit,
        [string]$Verdict
    )
    if ($ProcessExit -ne 0) {
        return $ProcessExit
    }
    if ($Verdict -eq "PASS_LANE0_KNOWN_GOOD_REPLAY") {
        return 0
    }
    if ($Verdict -like "FAIL_*") {
        return 40
    }
    if ($Verdict -like "INCONCLUSIVE_*") {
        return 41
    }
    return 42
}

$modes = Normalize-List -Items $TwoLaneTriggerModes
$modeArg = $modes -join ","

"P0_KNOWN_GOOD_REPLAY_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "MODE=$Mode"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "TWO_LANE_TRIGGER_MODES=$($modes -join ',')"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "LANE0_LOG=$lane0Log"
Write-SummaryLine "TWO_LANE_LOG=$twoLaneLog"
Write-SummaryLine "LANE0_RECIPE=IR_LANE_COUNT=1,CNT_CHIP_MAX=7,lane_mask=0x1,session=0x2201,payload_bytes=247"
Write-SummaryLine "TWO_LANE_RECIPE=IR_LANE_COUNT=2,B_SESSION_ID=0x2203,lane_mask=0x3,trigger=$($modes -join ',')"
Write-SummaryLine "NO_FPGA_PROGRAMMING_BEFORE_PREFLIGHT_PASS=1"
Write-SummaryLine "NO_TFDU_DRIVE_BEFORE_PREFLIGHT_PASS=1"

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

$lane0Args = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $lane0Script,
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
    [string]$Lane0XsctWaitSeconds,
    "-PostStartSeconds",
    [string]$Lane0PostStartSeconds,
    "-CaptureSeconds",
    [string]$Lane0CaptureSeconds
)

$twoLaneArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $twoLaneScript,
    "-ComPort",
    $ComPort,
    "-BaudRate",
    [string]$BaudRate,
    "-XsctPath",
    $XsctPath,
    "-VivadoPath",
    $VivadoPath,
    "-TriggerModes"
) + @(
    $modeArg,
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz,
    "-PerRunTimeoutSeconds",
    [string]$TwoLaneMatrixTimeoutSeconds
)
if ($StopOnFail) {
    $twoLaneArgs += "-StopOnFail"
}

Write-SummaryLine "PREFLIGHT_COMMAND=powershell $((@($preflightArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "LANE0_COMMAND=powershell $((@($lane0Args) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "TWO_LANE_COMMAND=powershell $((@($twoLaneArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"

if ($DryRun) {
    Write-SummaryLine "DRY_RUN_NO_PREFLIGHT_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_DONE=1"
    Write-SummaryLine "P0_KNOWN_GOOD_REPLAY_SAFE_END $(Get-Date -Format o)"
    exit 0
}

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
    Write-SummaryLine "P0_REPLAY_BLOCKED_NO_PROGRAMMING=1"
    Write-SummaryLine "P0_KNOWN_GOOD_REPLAY_SAFE_END $(Get-Date -Format o)"
    exit 20
}

$overallExit = 0

if ($Mode -eq "lane0" -or $Mode -eq "all") {
    Write-SummaryLine "LANE0_START=$(Get-Date -Format o)"
    $lane0Exit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $lane0Args -LogPath $lane0Log -TimeoutSeconds 300
    Write-SummaryLine "LANE0_EXIT=$lane0Exit"
    $lane0Verdict = "INCONCLUSIVE_NO_LANE0_LOG"
    if (Test-Path -LiteralPath $lane0Log) {
        $lane0Text = Get-Content -LiteralPath $lane0Log -Raw -ErrorAction SilentlyContinue
        foreach ($line in (($lane0Text -split "`r?`n") | Where-Object {
            $_ -match "PREFLIGHT_BLOCKED|SHUTDOWN_EXIT|HW_WINDOW|UART_MATCH=PSPS_STAGE_SUMMARY|LANE0_HW_SAFE_RUN_END"
        })) {
            Write-SummaryLine "LANE0_MATCH=$line"
        }
        $lane0Verdict = Classify-Lane0Replay -Text $lane0Text
    }
    Write-SummaryLine "LANE0_VERDICT=$lane0Verdict"
    $lane0EffectiveExit = Get-Lane0EffectiveExit -ProcessExit $lane0Exit -Verdict $lane0Verdict
    Write-SummaryLine "LANE0_EFFECTIVE_EXIT=$lane0EffectiveExit"
    if ($lane0EffectiveExit -ne 0 -and $overallExit -eq 0) {
        $overallExit = $lane0EffectiveExit
    }
    if ($StopOnFail -and $lane0EffectiveExit -ne 0) {
        Write-SummaryLine "STOP_ON_FAIL_AFTER_LANE0=1"
        Write-SummaryLine "P0_KNOWN_GOOD_REPLAY_SAFE_END $(Get-Date -Format o)"
        exit $overallExit
    }
}

if ($Mode -eq "two_lane" -or $Mode -eq "all") {
    Write-SummaryLine "TWO_LANE_START=$(Get-Date -Format o)"
    $twoLaneExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $twoLaneArgs -LogPath $twoLaneLog -TimeoutSeconds ($TwoLaneMatrixTimeoutSeconds + 180)
    Write-SummaryLine "TWO_LANE_EXIT=$twoLaneExit"
    if (Test-Path -LiteralPath $twoLaneLog) {
        foreach ($line in (Get-Content -LiteralPath $twoLaneLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "MATRIX_PREFLIGHT|MATRIX_ANALYSIS|RUN_RESULT|RUN_SAFETY|LANE2_MATRIX_SAFE_END"
        })) {
            Write-SummaryLine "TWO_LANE_MATCH=$line"
        }
    }
    if ($twoLaneExit -ne 0 -and $overallExit -eq 0) {
        $overallExit = $twoLaneExit
    }
}

Write-SummaryLine "P0_KNOWN_GOOD_REPLAY_SAFE_END $(Get-Date -Format o)"
exit $overallExit
