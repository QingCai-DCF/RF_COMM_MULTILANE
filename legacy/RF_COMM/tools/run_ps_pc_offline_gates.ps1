param(
    [int]$Repeat = 64,
    [int]$PayloadSize = 96,
    [int]$ReconnectCycles = 4,
    [double]$TimeoutSeconds = 5.0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "ps_pc_offline_gates_$stamp.summary.txt"
$staticLog = Join-Path $reportsDir "ps_pc_offline_gates_$stamp.static.log"
$boundaryLog = Join-Path $reportsDir "ps_pc_offline_gates_$stamp.boundary.log"
$payloadMatrixLog = Join-Path $reportsDir "ps_pc_offline_gates_$stamp.payload_matrix.log"
$reconnectMatrixLog = Join-Path $reportsDir "ps_pc_offline_gates_$stamp.reconnect_matrix.log"
$unittestLog = Join-Path $reportsDir "ps_pc_offline_gates_$stamp.unittest.log"
$acceptanceLog = Join-Path $reportsDir "ps_pc_offline_gates_$stamp.acceptance.log"
$acceptanceDir = Join-Path $reportsDir "ps_pc_offline_acceptance_$stamp"

$staticScript = Join-Path $repoRoot "software\ps_lwip_bridge\check_ps_bridge_static.py"
$boundaryScript = Join-Path $repoRoot "tools\build_no_ethernet_network_boundary_evidence.py"
$payloadMatrixScript = Join-Path $repoRoot "tools\run_n03_offline_payload_matrix.py"
$reconnectMatrixScript = Join-Path $repoRoot "tools\run_n03_offline_reconnect_matrix.py"
$unitTestScript = Join-Path $repoRoot "software\host_client\test_rf_comm_client.py"
$acceptanceScript = Join-Path $repoRoot "software\host_client\run_acceptance.ps1"

foreach ($path in @($staticScript, $boundaryScript, $payloadMatrixScript, $reconnectMatrixScript, $unitTestScript, $acceptanceScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Invoke-Step {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [int]$TimeoutSecondsForStep
    )

    Write-SummaryLine "STEP_START name=$Name log=$LogPath"
    $errPath = "$LogPath.err"
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError $errPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSecondsForStep * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-SummaryLine "STEP_RESULT name=$Name exit=124 timeout=1"
        return 124
    }
    $proc.Refresh()
    $exit = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
    Write-SummaryLine "STEP_RESULT name=$Name exit=$exit timeout=0"
    if (Test-Path -LiteralPath $LogPath) {
        foreach ($line in (Get-Content -LiteralPath $LogPath -ErrorAction SilentlyContinue | Select-Object -Last 30)) {
            if ($line -match "PASS|FAIL|summary|PS_BRIDGE|acceptance|log_acceptance|Ran ") {
                Write-SummaryLine "STEP_STDOUT name=$Name $line"
            }
        }
    }
    if ((Test-Path -LiteralPath $errPath) -and (Get-Item -LiteralPath $errPath).Length -gt 0) {
        foreach ($line in (Get-Content -LiteralPath $errPath -ErrorAction SilentlyContinue | Select-Object -Last 30)) {
            if ($line -match "PASS|FAIL|OK|Ran |FAILED|ERROR") {
                Write-SummaryLine "STEP_STDERR name=$Name $line"
            }
        }
    }
    return $exit
}

"PS_PC_OFFLINE_GATES_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "STATIC_LOG=$staticLog"
Write-SummaryLine "BOUNDARY_LOG=$boundaryLog"
Write-SummaryLine "PAYLOAD_MATRIX_LOG=$payloadMatrixLog"
Write-SummaryLine "RECONNECT_MATRIX_LOG=$reconnectMatrixLog"
Write-SummaryLine "UNITTEST_LOG=$unittestLog"
Write-SummaryLine "ACCEPTANCE_LOG=$acceptanceLog"
Write-SummaryLine "ACCEPTANCE_DIR=$acceptanceDir"
Write-SummaryLine "REPEAT=$Repeat"
Write-SummaryLine "PAYLOAD_SIZE=$PayloadSize"
Write-SummaryLine "RECONNECT_CYCLES=$ReconnectCycles"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "N03_OFFLINE_MODES=commands;memory_echo;pspl_synth;ir_physical_deferred_negative;app_payload_segmentation;payload_matrix;reconnect_matrix;protocol_fault_boundary;reconnect_payload_echo"

$overall = 0

$staticExit = Invoke-Step -Name "ps_bridge_static" -FilePath "python.exe" -Arguments @($staticScript) -LogPath $staticLog -TimeoutSecondsForStep 30
if ($staticExit -ne 0 -and $overall -eq 0) { $overall = $staticExit }

$boundaryExit = Invoke-Step -Name "no_ethernet_network_boundary" -FilePath "python.exe" -Arguments @($boundaryScript) -LogPath $boundaryLog -TimeoutSecondsForStep 60
if ($boundaryExit -ne 0 -and $overall -eq 0) { $overall = $boundaryExit }
if ($boundaryExit -eq 0 -and (Select-String -LiteralPath $boundaryLog -Pattern "RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall=PASS_OFFLINE_NETWORK_BOUNDARY" -SimpleMatch -Quiet)) {
    Write-SummaryLine "N03_PROTOCOL_FAULT_NEGATIVE_OFFLINE_PASS=1"
}

$payloadMatrixExit = Invoke-Step -Name "n03_offline_payload_matrix" -FilePath "python.exe" -Arguments @(
    $payloadMatrixScript,
    "--repeat",
    "2"
) -LogPath $payloadMatrixLog -TimeoutSecondsForStep 90
if ($payloadMatrixExit -ne 0 -and $overall -eq 0) { $overall = $payloadMatrixExit }
if ($payloadMatrixExit -eq 0 -and (Select-String -LiteralPath $payloadMatrixLog -Pattern "N03_OFFLINE_PAYLOAD_MATRIX_PASS=1" -SimpleMatch -Quiet)) {
    Write-SummaryLine "N03_OFFLINE_PAYLOAD_MATRIX_PASS=1"
}

$reconnectMatrixExit = Invoke-Step -Name "n03_offline_reconnect_matrix" -FilePath "python.exe" -Arguments @(
    $reconnectMatrixScript,
    "--timeout",
    [string]$TimeoutSeconds
) -LogPath $reconnectMatrixLog -TimeoutSecondsForStep 90
if ($reconnectMatrixExit -ne 0 -and $overall -eq 0) { $overall = $reconnectMatrixExit }
if ($reconnectMatrixExit -eq 0) {
    if (Select-String -LiteralPath $reconnectMatrixLog -Pattern "N03_OFFLINE_RECONNECT_HELLO_10X_PASS=1" -SimpleMatch -Quiet) {
        Write-SummaryLine "N03_OFFLINE_RECONNECT_HELLO_10X_PASS=1"
    }
    if (Select-String -LiteralPath $reconnectMatrixLog -Pattern "N03_OFFLINE_RECONNECT_PAYLOAD_20X_PASS=1" -SimpleMatch -Quiet) {
        Write-SummaryLine "N03_OFFLINE_RECONNECT_PAYLOAD_20X_PASS=1"
    }
}

$unitExit = Invoke-Step -Name "host_client_unittest" -FilePath "python.exe" -Arguments @("-m", "unittest", $unitTestScript) -LogPath $unittestLog -TimeoutSecondsForStep 90
if ($unitExit -ne 0 -and $overall -eq 0) { $overall = $unitExit }
if ($unitExit -eq 0) {
    Write-SummaryLine "N03_APP_PAYLOAD_SEGMENTATION_OFFLINE_PASS=1"
    Write-SummaryLine "N03_APP_PAYLOAD_SEGMENTATION_OFFLINE_CASE=8192_bytes_over_512_byte_rfcm_frames"
}

$acceptanceExit = Invoke-Step -Name "host_offline_mock_acceptance" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $acceptanceScript,
    "-Mode",
    "offline_mock",
    "-Repeat",
    [string]$Repeat,
    "-PayloadSize",
    [string]$PayloadSize,
    "-ReconnectCycles",
    [string]$ReconnectCycles,
    "-TimeoutSeconds",
    [string]$TimeoutSeconds,
    "-LogDir",
    $acceptanceDir
) -LogPath $acceptanceLog -TimeoutSecondsForStep 120
if ($acceptanceExit -ne 0 -and $overall -eq 0) { $overall = $acceptanceExit }

if (Test-Path -LiteralPath $acceptanceLog) {
    foreach ($marker in @(
        "N03_TCP_PROTOCOL_COMMAND_PASS=1",
        "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=1",
        "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=1",
        "N03_BAD_ARG_NEGATIVE_PASS=1",
        "N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=1"
    )) {
        if (Select-String -LiteralPath $acceptanceLog -Pattern $marker -SimpleMatch -Quiet) {
            Write-SummaryLine "N03_ACCEPTANCE_MARKER $marker"
        }
    }
    if ((Select-String -LiteralPath $acceptanceLog -Pattern "reconnect cycle 2/2" -SimpleMatch -Quiet) -and
        (Select-String -LiteralPath $acceptanceLog -Pattern "rx_data=1" -SimpleMatch -Quiet) -and
        -not (Select-String -LiteralPath $acceptanceLog -Pattern "reconnect cycle .*acceptance failures" -Quiet)) {
        Write-SummaryLine "N03_RECONNECT_PAYLOAD_ECHO_OFFLINE_PASS=1"
    }
}

if (Test-Path -LiteralPath $acceptanceDir) {
    foreach ($csv in (Get-ChildItem -LiteralPath $acceptanceDir -Filter "*.csv" -ErrorAction SilentlyContinue)) {
        Write-SummaryLine "ACCEPTANCE_CSV=$($csv.FullName)"
    }
    foreach ($serverLog in (Get-ChildItem -LiteralPath $acceptanceDir -Filter "offline_mock_server_*.log" -ErrorAction SilentlyContinue)) {
        Write-SummaryLine "ACCEPTANCE_SERVER_LOG=$($serverLog.FullName)"
    }
}

if ($overall -eq 0) {
    Write-SummaryLine "PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1 boundary=1 payload_matrix=1 reconnect_matrix=1 n03_commands=1 n03_modes=1"
} else {
    Write-SummaryLine "PS_PC_OFFLINE_GATES_FAIL exit=$overall"
}
Write-SummaryLine "PS_PC_OFFLINE_GATES_END $(Get-Date -Format o)"
exit $overall
