param(
    [string]$TargetHost = "",
    [int]$Port = 5001,
    [double]$TimeoutSeconds = 5.0,
    [switch]$UseStaticFallback,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "ps_pc_board_smoke_safe_$stamp.summary.txt"
$acceptanceLog = Join-Path $reportsDir "ps_pc_board_smoke_safe_$stamp.acceptance.log"
$acceptanceErr = Join-Path $reportsDir "ps_pc_board_smoke_safe_$stamp.acceptance.err.log"

$acceptanceScript = Join-Path $repoRoot "software\host_client\run_acceptance.ps1"
if (-not (Test-Path -LiteralPath $acceptanceScript)) {
    throw "Missing acceptance wrapper: $acceptanceScript"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Get-LatestFile {
    param([string]$Pattern)
    $files = @(Get-ChildItem -Path $repoRoot -Filter $Pattern -Recurse -File -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) {
        return $null
    }
    return ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
}

"PS_PC_BOARD_SMOKE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "TARGET_HOST_ARG=$TargetHost"
Write-SummaryLine "PORT=$Port"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "USE_STATIC_FALLBACK=$([int]$UseStaticFallback.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "SUMMARY_LOG=$summaryLog"
Write-SummaryLine "ACCEPTANCE_LOG=$acceptanceLog"
Write-SummaryLine "ACCEPTANCE_ERR=$acceptanceErr"

$latestProbe = Get-LatestFile -Pattern "ps_uart_boot_probe_*.summary.txt"
if ($latestProbe) {
    Write-SummaryLine "LATEST_UART_PROBE=$($latestProbe.FullName)"
    $probeText = Get-Content -LiteralPath $latestProbe.FullName -Raw -ErrorAction SilentlyContinue
    if ($probeText -match "(?m)^UART_PROBE_VERDICT=(.+)$") {
        Write-SummaryLine "LATEST_UART_VERDICT=$($Matches[1].Trim())"
    }
    $ips = [regex]::Matches($probeText, "(?m)^BOARD_IP_SEEN=(\d+\.\d+\.\d+\.\d+)$")
    if ($TargetHost -eq "" -and $ips.Count -gt 0) {
        $TargetHost = $ips[$ips.Count - 1].Groups[1].Value
        Write-SummaryLine "TARGET_HOST_FROM_UART=$TargetHost"
    }
} else {
    Write-SummaryLine "LATEST_UART_PROBE=NONE"
}

if ($TargetHost -eq "" -and $UseStaticFallback) {
    $TargetHost = "192.168.10.2"
    Write-SummaryLine "TARGET_HOST_STATIC_FALLBACK=$TargetHost"
}

if ($TargetHost -eq "") {
    Write-SummaryLine "SMOKE_BLOCKED_NO_TARGET_HOST=1"
    Write-SummaryLine "RUN_UART_PROBE_FIRST=powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\probe_ps_uart_boot_safe.ps1 -ComPort COM3 -DurationSeconds 20"
    Write-SummaryLine "NO_TCP_CONNECT_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "SMOKE_EFFECTIVE_EXIT=20"
    Write-SummaryLine "PS_PC_BOARD_SMOKE_SAFE_END $(Get-Date -Format o)"
    exit 20
}

$cmd = @(
    "powershell",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $acceptanceScript,
    "-Mode",
    "smoke",
    "-TargetHost",
    $TargetHost,
    "-Port",
    [string]$Port,
    "-TimeoutSeconds",
    [string]$TimeoutSeconds
)
Write-SummaryLine "SMOKE_COMMAND=$($cmd -join ' ')"
Write-SummaryLine "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"

if ($DryRun) {
    Write-SummaryLine "SMOKE_DRY_RUN=1"
    Write-SummaryLine "NO_TCP_CONNECT_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "SMOKE_EFFECTIVE_EXIT=0"
    Write-SummaryLine "PS_PC_BOARD_SMOKE_SAFE_END $(Get-Date -Format o)"
    exit 0
}

$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $cmd[1..($cmd.Count - 1)] `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $acceptanceLog `
    -RedirectStandardError $acceptanceErr `
    -WindowStyle Hidden `
    -PassThru
$finished = $proc.WaitForExit([int](($TimeoutSeconds + 15.0) * 1000.0))
if (-not $finished) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Write-SummaryLine "SMOKE_TIMEOUT_KILLED=1"
    Write-SummaryLine "SMOKE_EFFECTIVE_EXIT=124"
    Write-SummaryLine "PS_PC_BOARD_SMOKE_SAFE_END $(Get-Date -Format o)"
    exit 124
}
$proc.Refresh()
$exitCode = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
Write-SummaryLine "SMOKE_EXIT=$exitCode"

$stdoutText = ""
if (Test-Path -LiteralPath $acceptanceLog) {
    $stdoutText = Get-Content -LiteralPath $acceptanceLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (Get-Content -LiteralPath $acceptanceLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "RF_COMM acceptance mode|ACK|STATUS|summary|acceptance|connected|rf_comm_ps_bridge|failed|error"
    })) {
        Write-SummaryLine "SMOKE_MATCH=$line"
    }
}
$stderrText = ""
if ((Test-Path -LiteralPath $acceptanceErr) -and (Get-Item -LiteralPath $acceptanceErr).Length -gt 0) {
    $stderrText = Get-Content -LiteralPath $acceptanceErr -Raw -ErrorAction SilentlyContinue
    foreach ($line in (Get-Content -LiteralPath $acceptanceErr -ErrorAction SilentlyContinue | Select-Object -Last 30)) {
        Write-SummaryLine "SMOKE_STDERR=$line"
    }
}

$stderrFailure = ($stderrText -match "Traceback|TimeoutError|failed with exit code|RuntimeException|ConnectionRefused|No route")
$responseOk = ($stdoutText -match "ACK" -and $stdoutText -match "STATUS_RSP")
Write-SummaryLine "SMOKE_STDERR_FAILURE_PARSED=$([int]$stderrFailure)"
Write-SummaryLine "SMOKE_RESPONSE_OK_PARSED=$([int]$responseOk)"

if ($exitCode -eq 0 -and -not $stderrFailure -and $responseOk) {
    Write-SummaryLine "SMOKE_VERDICT=PASS_REAL_BOARD_HELLO_STATUS"
    $effectiveExitCode = 0
} else {
    Write-SummaryLine "SMOKE_VERDICT=FAIL_OR_NO_BOARD_RESPONSE"
    $effectiveExitCode = $exitCode
    if ($effectiveExitCode -eq 0) {
        $effectiveExitCode = 1
    }
}
Write-SummaryLine "SMOKE_EFFECTIVE_EXIT=$effectiveExitCode"
Write-SummaryLine "PS_PC_BOARD_SMOKE_SAFE_END $(Get-Date -Format o)"
exit $effectiveExitCode
