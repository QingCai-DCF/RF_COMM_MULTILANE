[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 3,
    [switch]$RunOfflineGates
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.summary.txt"
$mdReport = Join-Path $reportsDir "n03_current_state_gate_$stamp.md"
$jsonReport = Join-Path $reportsDir "n03_current_state_gate_$stamp.json"
$currentSummary = Join-Path $reportsDir "n03_current_state_gate_current.summary.txt"
$currentMd = Join-Path $reportsDir "n03_current_state_gate_current.md"
$currentJson = Join-Path $reportsDir "n03_current_state_gate_current.json"

$staticLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.static_direct.log"
$dhcpLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.pc_dhcp.log"
$externalLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.external_preconditions.log"
$runbookLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.real_acceptance_runbook.log"
$offlineLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.offline_gates.log"
$readinessLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.readiness.log"
$packageLog = Join-Path $reportsDir "n03_current_state_gate_$stamp.package.log"

$staticScript = Join-Path $repoRoot "tools\setup_n03_static_direct_network_safe.ps1"
$dhcpScript = Join-Path $repoRoot "tools\check_n03_pc_hosted_dhcp_preflight.ps1"
$externalScript = Join-Path $repoRoot "tools\check_external_preconditions.py"
$runbookScript = Join-Path $repoRoot "tools\build_real_acceptance_runbook.py"
$offlineScript = Join-Path $repoRoot "tools\run_ps_pc_offline_gates.ps1"
$readinessScript = Join-Path $repoRoot "tools\audit_n03_network_first_readiness.py"
$packageScript = Join-Path $repoRoot "tools\build_n03_network_first_package.py"

foreach ($path in @($staticScript, $dhcpScript, $externalScript, $runbookScript, $readinessScript, $packageScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}
if ($RunOfflineGates -and -not (Test-Path -LiteralPath $offlineScript)) {
    throw "Required path is missing: $offlineScript"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding utf8
}

function Invoke-Step {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [int]$TimeoutSecondsForStep,
        [int[]]$AllowedExitCodes = @(0)
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
        Write-SummaryLine "STEP_RESULT name=$Name exit=124 timeout=1 allowed=0"
        return 124
    }
    $proc.Refresh()
    $exit = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
    $allowed = $AllowedExitCodes -contains $exit
    Write-SummaryLine "STEP_RESULT name=$Name exit=$exit timeout=0 allowed=$([int]$allowed)"
    if (Test-Path -LiteralPath $LogPath) {
        foreach ($line in (Get-Content -LiteralPath $LogPath -ErrorAction SilentlyContinue | Select-Object -Last 40)) {
            if ($line -match "PASS|FAIL|BLOCK|READY|WAITING|RUNBOOK|N03_|NO_|WROTE_|STEP_|PREFLIGHT|STATIC|DHCP") {
                Write-SummaryLine "STEP_STDOUT name=$Name $line"
            }
        }
    }
    if ((Test-Path -LiteralPath $errPath) -and (Get-Item -LiteralPath $errPath).Length -gt 0) {
        foreach ($line in (Get-Content -LiteralPath $errPath -ErrorAction SilentlyContinue | Select-Object -Last 40)) {
            if ($line -match "PASS|FAIL|BLOCK|ERROR|Traceback|Exception") {
                Write-SummaryLine "STEP_STDERR name=$Name $line"
            }
        }
    }
    return $exit
}

function Test-LogMarker {
    param(
        [string]$Path,
        [string]$Pattern
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    return [bool](Select-String -LiteralPath $Path -Pattern $Pattern -SimpleMatch -Quiet)
}

function Get-LogValue {
    param(
        [string]$Path,
        [string]$Key
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }
    $prefix = "$Key="
    foreach ($line in (Get-Content -LiteralPath $Path -ErrorAction SilentlyContinue)) {
        if ($line.StartsWith($prefix)) {
            return $line.Substring($prefix.Length).Trim()
        }
    }
    return ""
}

"N03_CURRENT_STATE_GATE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding utf8
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "RUN_OFFLINE_GATES=$([int]$RunOfflineGates.IsPresent)"
Write-SummaryLine "READ_ONLY=1"
Write-SummaryLine "NO_NETWORK_CONFIG_CHANGE=1"
Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
Write-SummaryLine "NO_UART_WRITE=1"
Write-SummaryLine "NO_TFDU_DRIVE=1"
Write-SummaryLine "NO_FINAL_PASS_CLAIM=1"
Write-SummaryLine "STATIC_DIRECT_LOG=$staticLog"
Write-SummaryLine "PC_DHCP_LOG=$dhcpLog"
Write-SummaryLine "EXTERNAL_PRECONDITIONS_LOG=$externalLog"
Write-SummaryLine "REAL_ACCEPTANCE_RUNBOOK_LOG=$runbookLog"
Write-SummaryLine "OFFLINE_GATES_LOG=$offlineLog"
Write-SummaryLine "READINESS_LOG=$readinessLog"
Write-SummaryLine "PACKAGE_LOG=$packageLog"

Copy-Item -LiteralPath $summaryLog -Destination $currentSummary -Force

$overall = 0

$staticExit = Invoke-Step -Name "n03_static_direct_preflight" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $staticScript,
    "-TimeoutMs",
    [string]([Math]::Max(1, $TimeoutSeconds) * 1000)
) -LogPath $staticLog -TimeoutSecondsForStep 45 -AllowedExitCodes @(0, 20)
if (($staticExit -notin @(0, 20)) -and $overall -eq 0) { $overall = $staticExit }

$dhcpExit = Invoke-Step -Name "n03_pc_hosted_dhcp_preflight" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $dhcpScript
) -LogPath $dhcpLog -TimeoutSecondsForStep 45 -AllowedExitCodes @(0)
if ($dhcpExit -ne 0 -and $overall -eq 0) { $overall = $dhcpExit }

$externalExit = Invoke-Step -Name "n03_external_preconditions" -FilePath "python.exe" -Arguments @(
    $externalScript,
    "--target-host",
    "192.168.10.2",
    "--target-host-a",
    "192.168.10.2",
    "--target-host-b",
    "192.168.10.3",
    "--tcp-port",
    "5001",
    "--require-pc-ip",
    "--expected-pc-ip",
    "192.168.10.1",
    "--expected-pc-prefix",
    "24",
    "--discover-local-tcp",
    "--discover-timeout",
    "0.2",
    "--discover-max-hosts",
    "512",
    "--timeout",
    [string]([Math]::Max(0.5, [Math]::Min(5.0, [double]$TimeoutSeconds)))
) -LogPath $externalLog -TimeoutSecondsForStep 45 -AllowedExitCodes @(0)
if ($externalExit -ne 0 -and $overall -eq 0) { $overall = $externalExit }

$runbookExit = Invoke-Step -Name "n03_real_acceptance_runbook" -FilePath "python.exe" -Arguments @(
    $runbookScript
) -LogPath $runbookLog -TimeoutSecondsForStep 45 -AllowedExitCodes @(0)
if ($runbookExit -ne 0 -and $overall -eq 0) { $overall = $runbookExit }

if ($RunOfflineGates) {
    $offlineExit = Invoke-Step -Name "n03_offline_gates" -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $offlineScript,
        "-TimeoutSeconds",
        [string]$TimeoutSeconds
    ) -LogPath $offlineLog -TimeoutSecondsForStep 180 -AllowedExitCodes @(0)
    if ($offlineExit -ne 0 -and $overall -eq 0) { $overall = $offlineExit }
} else {
    Write-SummaryLine "STEP_SKIPPED name=n03_offline_gates reason=RunOfflineGates_not_set"
}

$readinessExit = Invoke-Step -Name "n03_readiness_audit" -FilePath "python.exe" -Arguments @(
    $readinessScript
) -LogPath $readinessLog -TimeoutSecondsForStep 90 -AllowedExitCodes @(0)
if ($readinessExit -ne 0 -and $overall -eq 0) { $overall = $readinessExit }

Copy-Item -LiteralPath $summaryLog -Destination $currentSummary -Force

$packageExit = Invoke-Step -Name "n03_package_rebuild" -FilePath "python.exe" -Arguments @(
    $packageScript
) -LogPath $packageLog -TimeoutSecondsForStep 90 -AllowedExitCodes @(0)
if ($packageExit -ne 0 -and $overall -eq 0) { $overall = $packageExit }

$staticPass = Test-LogMarker -Path $staticLog -Pattern "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_PASS=1"
$staticBlocked = Test-LogMarker -Path $staticLog -Pattern "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_PASS=0"
$dhcpReady = Test-LogMarker -Path $dhcpLog -Pattern "N03_PC_HOSTED_DHCP_SERVER_READY=1"
$dhcpLease = Test-LogMarker -Path $dhcpLog -Pattern ("N03_PC_HOSTED_DHCP_LEASE_PASS" + "=1")
$externalOverall = Get-LogValue -Path $externalLog -Key "RF_COMM_EXTERNAL_PRECONDITIONS overall"
$runbookOverall = Get-LogValue -Path $runbookLog -Key "RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall"
$readinessPass = Test-LogMarker -Path $readinessLog -Pattern "N03_NETWORK_FIRST_READINESS_PASS=1"
$forbiddenCount = Get-LogValue -Path $readinessLog -Key "N03_FORBIDDEN_PASS_CLAIM_COUNT"
$blockerCount = Get-LogValue -Path $readinessLog -Key "N03_NETWORK_FIRST_REAL_BOARD_BLOCKER_COUNT"

Write-SummaryLine "N03_CURRENT_STATE_STATIC_PREFLIGHT_PASS=$([int]$staticPass)"
Write-SummaryLine "N03_CURRENT_STATE_STATIC_PREFLIGHT_BLOCKED=$([int]$staticBlocked)"
Write-SummaryLine "N03_CURRENT_STATE_PC_DHCP_SERVER_READY=$([int]$dhcpReady)"
Write-SummaryLine "N03_CURRENT_STATE_PC_DHCP_LEASE_PASS=$([int]$dhcpLease)"
Write-SummaryLine "N03_CURRENT_STATE_EXTERNAL_PRECONDITIONS=$externalOverall"
Write-SummaryLine "N03_CURRENT_STATE_REAL_ACCEPTANCE_RUNBOOK=$runbookOverall"
Write-SummaryLine "N03_CURRENT_STATE_READINESS_PASS=$([int]$readinessPass)"
Write-SummaryLine "N03_CURRENT_STATE_FORBIDDEN_PASS_CLAIM_COUNT=$forbiddenCount"
Write-SummaryLine "N03_CURRENT_STATE_REAL_BOARD_BLOCKER_COUNT=$blockerCount"
Write-SummaryLine "N03_CURRENT_STATE_GATE_EXIT=$overall"

if ($overall -eq 0 -and $readinessPass) {
    Write-SummaryLine "N03_CURRENT_STATE_GATE_STATUS=PASS_READY_TO_CLAIM_FINAL"
} elseif ($overall -eq 0) {
    Write-SummaryLine "N03_CURRENT_STATE_GATE_STATUS=BLOCKED_REAL_BOARD_EVIDENCE"
} else {
    Write-SummaryLine "N03_CURRENT_STATE_GATE_STATUS=TOOL_FAILURE"
}
Write-SummaryLine "N03_CURRENT_STATE_GATE_COMPLETE=1"
Write-SummaryLine "N03_CURRENT_STATE_GATE_END $(Get-Date -Format o)"

$payload = [ordered]@{
    generated = (Get-Date -Format o)
    status = if ($overall -eq 0 -and $readinessPass) { "PASS_READY_TO_CLAIM_FINAL" } elseif ($overall -eq 0) { "BLOCKED_REAL_BOARD_EVIDENCE" } else { "TOOL_FAILURE" }
    exit_code = $overall
    run_offline_gates = [bool]$RunOfflineGates.IsPresent
    markers = [ordered]@{
        read_only = $true
        no_network_config_change = $true
        no_hardware_programming = $true
        no_uart_write = $true
        no_tfdu_drive = $true
        no_final_pass_claim = $true
        static_preflight_pass = [bool]$staticPass
        static_preflight_blocked = [bool]$staticBlocked
        pc_dhcp_server_ready = [bool]$dhcpReady
        pc_dhcp_lease_pass = [bool]$dhcpLease
        external_preconditions = $externalOverall
        real_acceptance_runbook = $runbookOverall
        readiness_pass = [bool]$readinessPass
    }
    logs = [ordered]@{
        summary = $summaryLog
        static_direct = $staticLog
        pc_dhcp = $dhcpLog
        external_preconditions = $externalLog
        real_acceptance_runbook = $runbookLog
        offline_gates = $offlineLog
        readiness = $readinessLog
        package = $packageLog
    }
    counts = [ordered]@{
        forbidden_pass_claims = $forbiddenCount
        real_board_blockers = $blockerCount
    }
}
$payload | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $jsonReport -Encoding utf8

$md = @(
    "# N03 Current State Gate",
    "",
    "Generated: $(Get-Date -Format o)",
    "",
    "Verdict: $(if ($overall -eq 0 -and $readinessPass) { 'PASS_READY_TO_CLAIM_FINAL' } elseif ($overall -eq 0) { 'BLOCKED_REAL_BOARD_EVIDENCE' } else { 'TOOL_FAILURE' })",
    "",
    "This wrapper is read-only. It does not configure networking, program FPGA, write UART, drive TFDU, or claim final N03 pass.",
    "",
    "- Static preflight pass: $staticPass",
    "- Static preflight blocked: $staticBlocked",
    "- PC DHCP server ready: $dhcpReady",
    "- PC DHCP lease pass: $dhcpLease",
    "- External preconditions: $externalOverall",
    "- Real acceptance runbook: $runbookOverall",
    "- Readiness pass: $readinessPass",
    "- Forbidden pass claim count: $forbiddenCount",
    "- Real-board blocker count: $blockerCount",
    "- Summary log: $summaryLog",
    "- Static preflight log: $staticLog",
    "- PC DHCP preflight log: $dhcpLog",
    "- External preconditions log: $externalLog",
    "- Real acceptance runbook log: $runbookLog",
    "- Readiness log: $readinessLog",
    "- Package rebuild log: $packageLog"
)
[System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)

Copy-Item -LiteralPath $summaryLog -Destination $currentSummary -Force
Copy-Item -LiteralPath $mdReport -Destination $currentMd -Force
Copy-Item -LiteralPath $jsonReport -Destination $currentJson -Force

if ($overall -ne 0) {
    exit $overall
}
if ($readinessPass) {
    exit 0
}
exit 20
