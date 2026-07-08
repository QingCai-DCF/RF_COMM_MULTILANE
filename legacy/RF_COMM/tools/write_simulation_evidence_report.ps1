[CmdletBinding()]
param(
    [string]$OutputPath = "",
    [string]$ExpectedConstraintHash = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$ipDir = Join-Path $repoRoot "IPs\ip_ir_array"
if ($OutputPath -eq "") {
    $OutputPath = Join-Path $repoRoot "reports\simulation_evidence_report.txt"
}

$constraintFileName = (-join @(
    [char]0x9879,
    [char]0x76EE,
    [char]0x7EA6,
    [char]0x675F,
    [char]0x0028,
    [char]0x76EE,
    [char]0x6807,
    [char]0xFF09
)) + ".txt"

$cases = @(
    [pscustomobject]@{ Test = "phy_rate";      Suffix = "single_lane";    Pass = "IR_PHY_RATE_MODEL_PASS";                   Scope = "64 MHz 4PPM PHY raw-rate model for 4 Mbit/s single-lane and 32/16 Mbit/s 8-lane targets" },
    [pscustomobject]@{ Test = "payload_budget"; Suffix = "model";         Pass = "IR_PAYLOAD_THROUGHPUT_BUDGET_PASS";        Scope = "Raw PHY versus effective payload throughput budget for current 16-byte fragments and 32/16 Mbit/s targets" },
    [pscustomobject]@{ Test = "loopback";      Suffix = "single_lane";    Pass = "LOOPBACK_SINGLE_LANE_PASS";                 Scope = "Single-lane nominal payload delivery" },
    [pscustomobject]@{ Test = "impair";        Suffix = "single_lane";    Pass = "LOOPBACK_IMPAIR_SINGLE_LANE_PASS";          Scope = "Dropped data frame and dropped final ACK recovery" },
    [pscustomobject]@{ Test = "crc";           Suffix = "single_lane";    Pass = "LOOPBACK_CRC_SINGLE_LANE_PASS";             Scope = "CRC rejection and retransmission recovery" },
    [pscustomobject]@{ Test = "exhaust";       Suffix = "single_lane";    Pass = "LOOPBACK_RETRY_EXHAUST_SINGLE_LANE_PASS";   Scope = "Permanent outage retry-exhaustion reporting" },
    [pscustomobject]@{ Test = "recover_after_exhaust"; Suffix = "single_lane"; Pass = "LOOPBACK_RECOVER_AFTER_EXHAUST_SINGLE_LANE_PASS"; Scope = "New packet transfer after retry exhaustion and link restoration" },
    [pscustomobject]@{ Test = "burst";         Suffix = "single_lane";    Pass = "LOOPBACK_BURST_SINGLE_LANE_PASS";           Scope = "Consecutive packets with RX backpressure" },
    [pscustomobject]@{ Test = "bidir";         Suffix = "single_lane";    Pass = "LOOPBACK_BIDIR_SINGLE_LANE_PASS";           Scope = "Single-lane bidirectional packet exchange" },
    [pscustomobject]@{ Test = "fdx";           Suffix = "lane_partition"; Pass = "LOOPBACK_FULL_DUPLEX_LANE_PARTITION_PASS";  Scope = "Continuous 2+2 lane full-duplex stress with eight bidirectional packet pairs" },
    [pscustomobject]@{ Test = "long_packet";   Suffix = "single_lane";    Pass = "LOOPBACK_SINGLE_LANE_256B_LATENCY_PASS";   Scope = "256-byte single-lane packet fragmentation and millisecond-level latency" },
    [pscustomobject]@{ Test = "multi";         Suffix = "multi_lane";     Pass = "LOOPBACK_MULTI_LANE_PASS";                 Scope = "Continuous four-lane half-duplex stress with eight 64-byte packets" },
    [pscustomobject]@{ Test = "multi_impair";  Suffix = "multi_lane";     Pass = "LOOPBACK_MULTI_LANE_IMPAIR_PASS";          Scope = "Multi-lane lost lane, lost ACK, and backpressure recovery" },
    [pscustomobject]@{ Test = "degrade";       Suffix = "multi_lane";     Pass = "LOOPBACK_MULTI_LANE_DEGRADE_PASS";         Scope = "Lane mask degradation and restoration" },
    [pscustomobject]@{ Test = "route";         Suffix = "multi_lane";     Pass = "LOOPBACK_MULTI_LANE_ROUTE_PASS";           Scope = "Changing rotating-side TX/RX lane mapping" },
    [pscustomobject]@{ Test = "autoroute";     Suffix = "multi_lane";     Pass = "LOOPBACK_MULTI_LANE_AUTOROUTE_PASS";       Scope = "Automatic route finding through retry plus lane round-robin" },
    [pscustomobject]@{ Test = "rotating_autoroute"; Suffix = "multi_lane"; Pass = "LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS"; Scope = "600 rpm / 20 cm metadata, 10-rotation scaled rotating-sector autoroute stress" },
    [pscustomobject]@{ Test = "rotating_soak_model"; Suffix = "model";    Pass = "ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS";   Scope = "72000-rotation / 288000-sector autoroute search model for the 2-hour rotating target" },
    [pscustomobject]@{ Test = "defensive";     Suffix = "protocol";       Pass = "IR_PROTOCOL_DEFENSIVE_CASES_PASS";        Scope = "Duplicate DATA, mismatched DATA, wrong-session ACK, and stale ACK rejection" },
    [pscustomobject]@{ Test = "regs";          Suffix = "axi_regs";       Pass = "AXI_REGS_CONFIG_MASKS_PASS";               Scope = "AXI-Lite config masks and static lane counter readback" },
    [pscustomobject]@{ Test = "axi_counters";  Suffix = "axi_top";        Pass = "AXI_TOP_LANE_COUNTERS_PASS";               Scope = "AXI wrapper payload, lane counter readback, and clear behavior" },
    [pscustomobject]@{ Test = "axi_rx_microscope"; Suffix = "axi_top";    Pass = "AXI_RX_MICROSCOPE_SESSION_MISMATCH_PASS";  Scope = "AXI-readable RX microscope classification for frame-valid but session-mismatched traffic" }
)

function Get-SimLogPath {
    param([string]$Test, [string]$Suffix)
    return (Join-Path $ipDir ".sim_${Test}_${Suffix}\${Test}_${Suffix}.sim\sim_1\behav\xsim\simulate.log")
}

$lines = New-Object System.Collections.Generic.List[string]
$failures = New-Object System.Collections.Generic.List[string]

$lines.Add("RF_COMM Simulation Evidence Report") | Out-Null
$lines.Add(("Generated: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"))) | Out-Null
$lines.Add(("Repository: {0}" -f $repoRoot)) | Out-Null
$lines.Add("") | Out-Null
$lines.Add("Current acceptance scope") | Out-Null
$lines.Add("- Simulation-only scope per current user direction.") | Out-Null
$lines.Add("- Hardware/JTAG, TFDU optical physics, TCP/DHCP on board, physical rotating shaft operation, real-time 2-hour soak, and measured final throughput are intentionally not required for this phase.") | Out-Null
$lines.Add("- Re-run command: .\tools\run_simulation_gates.ps1 -Jobs 16") | Out-Null
$lines.Add("") | Out-Null

$lines.Add("Constraint file hash") | Out-Null
foreach ($path in @(
    (Join-Path (Join-Path $env:USERPROFILE "Desktop") $constraintFileName),
    (Join-Path $repoRoot $constraintFileName)
)) {
    if (-not (Test-Path -LiteralPath $path)) {
        $msg = "missing $path"
        $failures.Add("constraint_hash: $msg") | Out-Null
        $lines.Add(("- FAIL {0}" -f $msg)) | Out-Null
        continue
    }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($hash -eq $ExpectedConstraintHash) {
        $lines.Add(("- PASS {0} hash={1}" -f $path, $hash)) | Out-Null
    } else {
        $msg = "$path hash=$hash expected=$ExpectedConstraintHash"
        $failures.Add("constraint_hash: $msg") | Out-Null
        $lines.Add(("- FAIL {0}" -f $msg)) | Out-Null
    }
}
$lines.Add("") | Out-Null

$lines.Add("RTL/XSim evidence") | Out-Null
foreach ($case in $cases) {
    $logPath = Get-SimLogPath -Test $case.Test -Suffix $case.Suffix
    if (-not (Test-Path -LiteralPath $logPath)) {
        $msg = "missing log for $($case.Test): $logPath"
        $failures.Add($msg) | Out-Null
        $lines.Add(("- FAIL {0} | {1}" -f $case.Test, $case.Scope)) | Out-Null
        $lines.Add(("  missing: {0}" -f $logPath)) | Out-Null
        continue
    }

    $match = Select-String -LiteralPath $logPath -SimpleMatch -Pattern $case.Pass | Select-Object -First 1
    if ($null -eq $match) {
        $msg = "pass signature not found for $($case.Test): $($case.Pass)"
        $failures.Add($msg) | Out-Null
        $lines.Add(("- FAIL {0} | {1}" -f $case.Test, $case.Scope)) | Out-Null
        $lines.Add(("  expected: {0}" -f $case.Pass)) | Out-Null
        $lines.Add(("  log: {0}" -f $logPath)) | Out-Null
        continue
    }

    $lines.Add(("- PASS {0} | {1}" -f $case.Test, $case.Scope)) | Out-Null
    $lines.Add(("  evidence: {0}" -f $match.Line.Trim())) | Out-Null
    $lines.Add(("  log: {0}" -f $logPath)) | Out-Null
}
$lines.Add("") | Out-Null

$lines.Add("Software/offline evidence") | Out-Null
$psBridgeCheck = Join-Path $repoRoot "software\ps_lwip_bridge\check_ps_bridge_static.py"
$psBridgeOutput = & python $psBridgeCheck 2>&1
$psBridgeExit = $LASTEXITCODE
$psBridgePass = $psBridgeOutput | Select-String -SimpleMatch -Pattern "PS_BRIDGE_STATIC_CHECKS_PASS" | Select-Object -First 1
if ($psBridgeExit -eq 0 -and $null -ne $psBridgePass) {
    $lines.Add("- PASS ps_bridge_static_checks | DHCP/static fallback, TCP reconnectability, and PS/PC protocol compatibility") | Out-Null
    $lines.Add(("  evidence: {0}" -f $psBridgePass.Line.Trim())) | Out-Null
    $lines.Add(("  command: python {0}" -f $psBridgeCheck)) | Out-Null
} else {
    $failures.Add("ps_bridge_static_checks: failed") | Out-Null
    $lines.Add("- FAIL ps_bridge_static_checks | DHCP/static fallback, TCP reconnectability, and PS/PC protocol compatibility") | Out-Null
    foreach ($line in $psBridgeOutput) {
        $lines.Add(("  output: {0}" -f $line)) | Out-Null
    }
}

$hostDir = Join-Path $repoRoot "software\host_client"
Push-Location $hostDir
try {
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $hostCompileOutput = & python -m py_compile "rf_comm_client.py" "analyze_acceptance_log.py" "test_rf_comm_client.py" 2>&1
    $hostCompileExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $oldErrorActionPreference
    Pop-Location
}
if ($hostCompileExit -eq 0) {
    $lines.Add("- PASS host_py_compile | PC-side client, acceptance-log analyzer, and mock protocol tests compile") | Out-Null
    $lines.Add(("  command: python -m py_compile {0}" -f (Join-Path $hostDir "rf_comm_client.py"))) | Out-Null
} else {
    $failures.Add("host_py_compile: failed") | Out-Null
    $lines.Add("- FAIL host_py_compile | PC-side client, acceptance-log analyzer, and mock protocol tests compile") | Out-Null
    foreach ($line in $hostCompileOutput) {
        $lines.Add(("  output: {0}" -f $line)) | Out-Null
    }
}

Push-Location $hostDir
try {
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $hostTestOutput = & python -m unittest "test_rf_comm_client.py" -v 2>&1
    $hostTestExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $oldErrorActionPreference
    Pop-Location
}
$hostRanLine = $hostTestOutput | Select-String -Pattern "^Ran [0-9]+ tests?" | Select-Object -First 1
$hostOkLine = $hostTestOutput | Select-String -Pattern "^OK$" | Select-Object -Last 1
if ($hostTestExit -eq 0) {
    $lines.Add("- PASS host_mock_protocol_tests | PC-side TCP client reconnect, parser, ACK/ERROR accounting, and CONFIG behavior") | Out-Null
    if ($null -ne $hostRanLine) {
        $lines.Add(("  evidence: {0}" -f $hostRanLine.Line.Trim())) | Out-Null
    }
    if ($null -ne $hostOkLine) {
        $lines.Add(("  result: {0}" -f $hostOkLine.Line.Trim())) | Out-Null
    }
    $lines.Add(("  command: python -m unittest {0} -v" -f (Join-Path $hostDir "test_rf_comm_client.py"))) | Out-Null
} else {
    $failures.Add("host_mock_protocol_tests: failed") | Out-Null
    $lines.Add("- FAIL host_mock_protocol_tests | PC-side TCP client reconnect, parser, ACK/ERROR accounting, and CONFIG behavior") | Out-Null
    foreach ($line in $hostTestOutput) {
        $lines.Add(("  output: {0}" -f $line)) | Out-Null
    }
}
$lines.Add("") | Out-Null

if ($failures.Count -eq 0) {
    $lines.Add("Overall result: PASS") | Out-Null
    $lines.Add("Simulation-stage objective status: all listed simulation evidence is present.") | Out-Null
} else {
    $lines.Add("Overall result: FAIL") | Out-Null
    foreach ($failure in $failures) {
        $lines.Add(("- {0}" -f $failure)) | Out-Null
    }
}

$outDir = Split-Path -Parent $OutputPath
if ($outDir -ne "" -and -not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}
$utf8WithBom = New-Object System.Text.UTF8Encoding -ArgumentList $true
[System.IO.File]::WriteAllLines($OutputPath, [string[]]$lines, $utf8WithBom)

Write-Host "SIM_EVIDENCE_REPORT $OutputPath"
if ($failures.Count -gt 0) {
    Write-Host "SIM_EVIDENCE_REPORT_FAIL"
    exit 1
}
Write-Host "SIM_EVIDENCE_REPORT_PASS"
