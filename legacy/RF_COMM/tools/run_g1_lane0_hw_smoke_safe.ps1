param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$XsctWaitSeconds = 45,
    [int]$PostStartSeconds = 35,
    [int]$CaptureSeconds = 75,
    [int]$MaxTfduWindowSeconds = 600,
    [int]$ShutdownBudgetSeconds = 30,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "g1_lane0_hw_smoke_safe_$stamp.summary.txt"
$innerOutLog = Join-Path $reportsDir "g1_lane0_hw_smoke_safe_$stamp.inner.out.log"
$innerErrLog = Join-Path $reportsDir "g1_lane0_hw_smoke_safe_$stamp.inner.err.log"
$runScript = Join-Path $scriptDir "run_lane0_hw_once_safe.ps1"

if (-not (Test-Path -LiteralPath $runScript)) {
    throw "Missing safe run script: $runScript"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

"G1_LANE0_HW_SMOKE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "INNER_STDOUT_LOG=$innerOutLog"
Write-SummaryLine "INNER_STDERR_LOG=$innerErrLog"
Write-SummaryLine "POST_START_SECONDS=$PostStartSeconds"
Write-SummaryLine "CAPTURE_SECONDS=$CaptureSeconds"
Write-SummaryLine "MAX_TFDU_WINDOW_SECONDS=$MaxTfduWindowSeconds"
Write-SummaryLine "SHUTDOWN_BUDGET_SECONDS=$ShutdownBudgetSeconds"

if ($PostStartSeconds -lt 0 -or $CaptureSeconds -lt 1 -or $XsctWaitSeconds -lt 1 -or $MaxTfduWindowSeconds -lt 60) {
    Write-SummaryLine "G1_HW_SMOKE_BLOCKED_INVALID_RUNTIME_ARGS=1"
    Write-SummaryLine "G1_LANE0_HW_SMOKE_SAFE_END $(Get-Date -Format o)"
    exit 10
}

if (($XsctWaitSeconds + $PostStartSeconds + $ShutdownBudgetSeconds) -ge $MaxTfduWindowSeconds) {
    Write-SummaryLine "G1_HW_SMOKE_BLOCKED_RUNTIME_LIMIT=1"
    Write-SummaryLine "G1_LANE0_HW_SMOKE_SAFE_END $(Get-Date -Format o)"
    exit 10
}

$innerArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $runScript,
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
    [string]$CaptureSeconds
)
if ($SkipPreflight) {
    $innerArgs += "-SkipPreflight"
}

$procInfo = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $innerArgs `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $innerOutLog `
    -RedirectStandardError $innerErrLog `
    -WindowStyle Hidden `
    -PassThru
$procInfo.WaitForExit()
$procInfo.Refresh()
$innerExit = if ($null -eq $procInfo.ExitCode) { 125 } else { $procInfo.ExitCode }
Write-SummaryLine "INNER_EXIT=$innerExit"

$innerText = ""
if (Test-Path -LiteralPath $innerOutLog) {
    $innerText = Get-Content -LiteralPath $innerOutLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in ($innerText -split "`r?`n" | Where-Object {
        $_ -match "UART_LOG=|SHUTDOWN_EXIT|SHUTDOWN_EXIT_INFERRED|HW_WINDOW_TO_SHUTDOWN_END_SECONDS|UART_MATCH=PSPS_(STAGE_SUMMARY|RUN_ONCE_DONE)"
    })) {
        Write-SummaryLine "INNER_MATCH=$line"
    }
}

$shutdownOk = ($innerText -match "SHUTDOWN_EXIT(?:_INFERRED)?=0")
$windowOk = $false
$windowMatch = [regex]::Match($innerText, "HW_WINDOW_TO_SHUTDOWN_END_SECONDS=([0-9]+(?:\.[0-9]+)?)")
if ($windowMatch.Success) {
    $windowOk = ([double]$windowMatch.Groups[1].Value -lt [double]$MaxTfduWindowSeconds)
}

$uartText = ""
$uartMatch = [regex]::Match($innerText, "(?m)^UART_LOG=(.+)$")
if ($uartMatch.Success) {
    $uartPath = $uartMatch.Groups[1].Value.Trim()
    Write-SummaryLine "G1_HW_SMOKE_UART_LOG=$uartPath"
    if (Test-Path -LiteralPath $uartPath) {
        $uartText = Get-Content -LiteralPath $uartPath -Raw -ErrorAction SilentlyContinue
    }
}

$summaryLine = [regex]::Match($innerText, "UART_MATCH=PSPS_STAGE_SUMMARY .*")
$payloadOk = ($innerText -match "payload_bytes=256" -or $uartText -match "payload_bytes=256")
$summaryOk = $false
if ($summaryLine.Success) {
    $line = $summaryLine.Value
    $sent = [regex]::Match($line, "\bsent=(\d+)")
    $rxOk = [regex]::Match($line, "\brx_ok=(\d+)")
    $txFail = [regex]::Match($line, "\btx_fail=(\d+)")
    $loss = [regex]::Match($line, "\bloss=([0-9.]+)%")
    $lastError = [regex]::Match($line, "\blast_error=([^\s]+)")
    if ($sent.Success -and $rxOk.Success -and $txFail.Success -and $loss.Success -and $lastError.Success) {
        $summaryOk = (
            [int]$sent.Groups[1].Value -gt 0 -and
            [int]$sent.Groups[1].Value -eq [int]$rxOk.Groups[1].Value -and
            [int]$txFail.Groups[1].Value -eq 0 -and
            [double]$loss.Groups[1].Value -eq 0.0 -and
            $lastError.Groups[1].Value -eq "none"
        )
    }
}

Write-SummaryLine "G1_HW_SMOKE_PAYLOAD_256_SEEN=$([int]$payloadOk)"
Write-SummaryLine "G1_HW_SMOKE_SUMMARY_PASS=$([int]$summaryOk)"
Write-SummaryLine "G1_HW_SMOKE_SHUTDOWN_OK=$([int]$shutdownOk)"
Write-SummaryLine "G1_HW_SMOKE_WINDOW_OK=$([int]$windowOk)"
Write-SummaryLine "G1_LANE0_HW_SMOKE_SAFE_END $(Get-Date -Format o)"

if ($innerExit -eq 125 -and $innerText -match "LANE0_HW_SAFE_RUN_END" -and $shutdownOk) {
    Write-SummaryLine "INNER_EXIT_INFERRED=0"
    $innerExit = 0
}

if ($innerExit -ne 0) {
    exit $innerExit
}
if (-not ($payloadOk -and $summaryOk -and $shutdownOk -and $windowOk)) {
    exit 20
}
exit 0
