param(
    [ValidateSet("rx_microscope", "session_mask_probe", "all")]
    [string]$Mode = "all",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$PerRunTimeoutSeconds = 300,
    [int]$MaxTfduWindowSeconds = 300,
    [string[]]$ExtraTriggerModes = @(),
    [switch]$DryRun,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "p0_rx_root_cause_safe_$stamp.summary.txt"
$preflightLog = Join-Path $reportsDir "p0_rx_root_cause_safe_$stamp.preflight.log"
$matrixLog = Join-Path $reportsDir "p0_rx_root_cause_safe_$stamp.matrix.log"

$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$matrixScript = Join-Path $repoRoot "tools\run_2lane_matrix_safe.ps1"
$analyzerScript = Join-Path $repoRoot "tools\analyze_2lane_ila_csv.py"

foreach ($path in @($preflightScript, $matrixScript, $analyzerScript, $VivadoPath, $XsctPath)) {
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

$rxTriggers = @("b_rx_data_state", "b_rx_check_state", "b_rx_flush_state")
$sessionProbeTriggers = @("a_tx_lane0", "a_tx_lane1", "b_tx_lane0", "b_tx_lane1")
if ($Mode -eq "rx_microscope") {
    $triggerModes = $rxTriggers
} elseif ($Mode -eq "session_mask_probe") {
    $triggerModes = $sessionProbeTriggers
} else {
    $triggerModes = $sessionProbeTriggers + $rxTriggers
}
$triggerModes = Normalize-List -Items ($triggerModes + $ExtraTriggerModes)
$triggerModeArg = $triggerModes -join ","

"P0_RX_ROOT_CAUSE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "MODE=$Mode"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "TRIGGER_MODES=$($triggerModes -join ',')"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "MATRIX_LOG=$matrixLog"
Write-SummaryLine "P0_SCOPE=P0-4/P0-5 current-build capture orchestration"
Write-SummaryLine "P0_LIMITATION=This wrapper captures current configured sessions/masks; true session/mask variant cases still require matching rebuild/config recipes."
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
) + @(
    $triggerModeArg,
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz,
    "-PerRunTimeoutSeconds",
    [string]$PerRunTimeoutSeconds,
    "-MaxTfduWindowSeconds",
    [string]$MaxTfduWindowSeconds
)
if ($StopOnFail) {
    $matrixArgs += "-StopOnFail"
}

Write-SummaryLine "PREFLIGHT_COMMAND=powershell $((@($preflightArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "MATRIX_COMMAND=powershell $((@($matrixArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"

if ($DryRun) {
    Write-SummaryLine "DRY_RUN_NO_PREFLIGHT_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_DONE=1"
    Write-SummaryLine "P0_RX_ROOT_CAUSE_SAFE_END $(Get-Date -Format o)"
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
    Write-SummaryLine "P0_RX_ROOT_CAUSE_BLOCKED_NO_PROGRAMMING=1"
    Write-SummaryLine "P0_RX_ROOT_CAUSE_SAFE_END $(Get-Date -Format o)"
    exit 20
}

Write-SummaryLine "MATRIX_START=$(Get-Date -Format o)"
$matrixExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $matrixArgs -LogPath $matrixLog -TimeoutSeconds (($PerRunTimeoutSeconds * [Math]::Max(1, $triggerModes.Count)) + 300)
Write-SummaryLine "MATRIX_EXIT=$matrixExit"
$matrixEffectiveExit = $matrixExit
if (Test-Path -LiteralPath $matrixLog) {
    $matrixText = Get-Content -LiteralPath $matrixLog -Raw -ErrorAction SilentlyContinue
    if ($matrixText -match "(?m)^RUN_DIAGNOSTIC .*effective_exit=([1-9][0-9]*)") {
        $matrixEffectiveExit = [int]$Matches[1]
    }
    foreach ($line in (Get-Content -LiteralPath $matrixLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "MATRIX_PREFLIGHT|MATRIX_ANALYSIS|RUN_RESULT|RUN_SAFETY|LANE2_MATRIX_SAFE_END"
    })) {
        Write-SummaryLine "MATRIX_MATCH=$line"
    }
}
Write-SummaryLine "MATRIX_EFFECTIVE_EXIT=$matrixEffectiveExit"

Write-SummaryLine "P0_RX_ROOT_CAUSE_SAFE_END $(Get-Date -Format o)"
exit $matrixEffectiveExit
