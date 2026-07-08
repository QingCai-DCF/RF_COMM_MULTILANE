param(
    [int]$Repeat = 32,
    [int]$PayloadSize = 256,
    [double]$TimeoutSeconds = 5.0,
    [int]$ReconnectCycles = 3
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryPath = Join-Path $reportsDir "no_ethernet_network_offline_acceptance_$stamp.summary.txt"
$csvPath = Join-Path $reportsDir "no_ethernet_network_offline_acceptance_$stamp.cases.csv"
$mdPath = Join-Path $reportsDir "no_ethernet_network_offline_acceptance_$stamp.md"
$logDir = Join-Path $reportsDir "no_ethernet_network_offline_acceptance_$stamp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$psBridgeStatic = Join-Path $repoRoot "software\ps_lwip_bridge\check_ps_bridge_static.py"
$hostAcceptance = Join-Path $repoRoot "software\host_client\run_acceptance.ps1"
$twoAxModel = Join-Path $repoRoot "software\host_client\two_ax7010_end_to_end_model.py"
$networkFaultModel = Join-Path $repoRoot "software\host_client\network_fault_recovery_model.py"
$boardTcpSafe = Join-Path $repoRoot "tools\run_ps_pc_tcp_dhcp_acceptance_safe.ps1"
$twoAxSafe = Join-Path $repoRoot "tools\run_two_ax7010_end_to_end_acceptance_safe.ps1"
$rotatingSafe = Join-Path $repoRoot "tools\run_rotating_shaft_acceptance_safe.ps1"
$productLoopSafe = Join-Path $repoRoot "tools\run_product_loop_acceptance_safe.ps1"
$eightLaneSafe = Join-Path $repoRoot "tools\run_8lane_hardware_acceptance_safe.ps1"

foreach ($path in @($psBridgeStatic, $hostAcceptance, $twoAxModel, $networkFaultModel, $boardTcpSafe, $twoAxSafe, $rotatingSafe, $productLoopSafe, $eightLaneSafe)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryPath -Value $Line -Encoding ascii
}

function Csv-Escape {
    param([AllowNull()][string]$Value)
    if ($null -eq $Value) {
        return '""'
    }
    return '"' + ($Value -replace '"', '""') + '"'
}

function Invoke-LoggedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [int]$TimeoutSecondsForStep
    )

    $outPath = Join-Path $logDir "$Name.out.log"
    $errPath = Join-Path $logDir "$Name.err.log"
    Write-SummaryLine "STEP_START name=$Name out=$outPath err=$errPath"
    Write-SummaryLine "STEP_COMMAND name=$Name $FilePath $($Arguments -join ' ')"

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $outPath `
        -RedirectStandardError $errPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSecondsForStep * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $sw.Stop()
        Write-SummaryLine "STEP_RESULT name=$Name exit=124 timeout=1 seconds=$([math]::Round($sw.Elapsed.TotalSeconds, 3))"
        return [pscustomobject]@{
            ExitCode = 124
            TimedOut = $true
            Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
            Stdout = if (Test-Path -LiteralPath $outPath) { Get-Content -LiteralPath $outPath -Raw -ErrorAction SilentlyContinue } else { "" }
            Stderr = if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue } else { "" }
            OutPath = $outPath
            ErrPath = $errPath
        }
    }
    $proc.Refresh()
    $sw.Stop()
    $exit = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
    Write-SummaryLine "STEP_RESULT name=$Name exit=$exit timeout=0 seconds=$([math]::Round($sw.Elapsed.TotalSeconds, 3))"
    return [pscustomobject]@{
        ExitCode = $exit
        TimedOut = $false
        Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
        Stdout = if (Test-Path -LiteralPath $outPath) { Get-Content -LiteralPath $outPath -Raw -ErrorAction SilentlyContinue } else { "" }
        Stderr = if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue } else { "" }
        OutPath = $outPath
        ErrPath = $errPath
    }
}

function Test-Patterns {
    param(
        [string]$Text,
        [string[]]$Patterns
    )
    foreach ($pattern in $Patterns) {
        if ($Text -notmatch [regex]::Escape($pattern)) {
            return $false
        }
    }
    return $true
}

"NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryPath -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "NO_HARDWARE_PROGRAMMING=1"
Write-SummaryLine "NO_UART_WRITE=1"
Write-SummaryLine "NO_TFDU_DRIVE=1"
Write-SummaryLine "NO_REAL_BOARD_TCP_DHCP=1"
Write-SummaryLine "NO_REAL_TWO_AX7010_TRAFFIC=1"
Write-SummaryLine "REPEAT=$Repeat"
Write-SummaryLine "PAYLOAD_SIZE=$PayloadSize"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "RECONNECT_CYCLES=$ReconnectCycles"

$constraintPath = Get-ChildItem -LiteralPath $repoRoot -File -Filter "*.txt" |
    Where-Object {
        try {
            (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash -eq $expectedConstraintSha256
        } catch {
            $false
        }
    } |
    Select-Object -First 1 -ExpandProperty FullName
$constraintHash = if ([string]::IsNullOrWhiteSpace($constraintPath)) { "MISSING" } else { (Get-FileHash -Algorithm SHA256 -LiteralPath $constraintPath).Hash }
Write-SummaryLine "CONSTRAINT_SHA256=$constraintHash"
Write-SummaryLine "CONSTRAINT_UNCHANGED=$([int]($constraintHash -eq $expectedConstraintSha256))"

$rows = [System.Collections.Generic.List[object]]::new()

function Add-CaseResult {
    param(
        [string]$Name,
        [string]$Coverage,
        [object]$Result,
        [string[]]$RequiredPatterns
    )

    $combined = "$($Result.Stdout)`n$($Result.Stderr)"
    $patternsOk = Test-Patterns -Text $combined -Patterns $RequiredPatterns
    $casePass = ($Result.ExitCode -eq 0 -and -not $Result.TimedOut -and $patternsOk)
    Write-SummaryLine "CASE_RESULT name=$Name pass=$([int]$casePass) exit=$($Result.ExitCode) timeout=$([int]$Result.TimedOut) seconds=$($Result.Seconds) patterns_ok=$([int]$patternsOk)"
    foreach ($line in (($combined -split "`r?`n") | Where-Object { $_ -match "PASS|FAIL|OK|RF_COMM|PS_BRIDGE|TWO_AX7010|BOARD_TCP|NO_|DURATION|summary" } | Select-Object -Last 16)) {
        Write-SummaryLine "CASE_NOTE name=$Name $line"
    }
    $rows.Add([pscustomobject]@{
        name = $Name
        status = if ($casePass) { "PASS" } else { "FAIL" }
        exit_code = $Result.ExitCode
        timed_out = [int]$Result.TimedOut
        seconds = $Result.Seconds
        patterns = ($RequiredPatterns -join ";")
        log = $Result.OutPath
        err = $Result.ErrPath
        coverage = $Coverage
    })
}

$psStatic = Invoke-LoggedProcess -Name "ps_bridge_static" -FilePath "python" -Arguments @($psBridgeStatic) -TimeoutSecondsForStep 30
Add-CaseResult -Name "ps_bridge_static" -Coverage "PS lwIP bridge source includes DHCP, static fallback, TCP listen/reconnect handling, RFCM frame handling, status/error forwarding, and PC protocol compatibility." -Result $psStatic -RequiredPatterns @("PS_BRIDGE_STATIC_CHECKS_PASS")

$hostUnit = Invoke-LoggedProcess -Name "host_client_unittest" -FilePath "python" -Arguments @("-m", "unittest", "software/host_client/test_rf_comm_client.py", "-v") -TimeoutSecondsForStep 60
Add-CaseResult -Name "host_client_unittest" -Coverage "PC RFCM client unit tests cover framing, parsing, ACK/error/status handling, config masks, and client behavior." -Result $hostUnit -RequiredPatterns @("OK")

$offlineMock = Invoke-LoggedProcess -Name "host_offline_mock_acceptance" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $hostAcceptance,
    "-Mode",
    "offline_mock",
    "-Repeat",
    [string]$Repeat,
    "-PayloadSize",
    [string]$PayloadSize,
    "-ReconnectCycles",
    [string]$ReconnectCycles,
    "-TimeoutSeconds",
    [string]$TimeoutSeconds
) -TimeoutSecondsForStep 120
Add-CaseResult -Name "host_offline_mock_acceptance" -Coverage "Loopback-only PC/PS protocol acceptance with local TCP mock, traffic, clean log analysis, and reconnect cycles." -Result $offlineMock -RequiredPatterns @("RF_COMM acceptance mode finished: offline_mock", "log_acceptance PASS")

$twoAxModelResult = Invoke-LoggedProcess -Name "two_ax7010_direct_offline_model" -FilePath "python" -Arguments @(
    $twoAxModel,
    "--repeat",
    [string]$Repeat,
    "--payload-size",
    [string]$PayloadSize,
    "--timeout",
    [string]([Math]::Max($TimeoutSeconds, 10.0)),
    "--log-dir",
    (Join-Path $logDir "two_ax7010_direct_model")
) -TimeoutSecondsForStep 120
Add-CaseResult -Name "two_ax7010_direct_offline_model" -Coverage "Two AX7010-style RFCM endpoints exchange bidirectional PC traffic through an 8-lane offline IR link, then reconfigure over RFCM into a 4+4 full-duplex lane partition with route probing, ACK loss, and reconnect queued RX." -Result $twoAxModelResult -RequiredPatterns @("TWO_AX7010_END_TO_END_OFFLINE_PASS", "tx_lane_coverage=0xff", "rx_lane_coverage=0xff", "hdx_tx_lane_coverage=0xff", "hdx_rx_lane_coverage=0xff", "fdx_a_to_b_tx_lane_coverage=0x0f", "fdx_a_to_b_rx_lane_coverage=0x0f", "fdx_b_to_a_tx_lane_coverage=0xf0", "fdx_b_to_a_rx_lane_coverage=0xf0", "route_probe_events=", "reconnect_queued_rx=1")

$networkFaultResult = Invoke-LoggedProcess -Name "network_fault_recovery_model" -FilePath "python" -Arguments @(
    $networkFaultModel
) -TimeoutSecondsForStep 60
Add-CaseResult -Name "network_fault_recovery_model" -Coverage "Offline PS/PC network fault recovery model covers TCP reset reconnect, host restart, cable replug style reconnect, DHCP address change, DHCP timeout static fallback, and queued RX delivery after reconnect without real Ethernet." -Result $networkFaultResult -RequiredPatterns @("RF_COMM_NETWORK_FAULT_RECOVERY_MODEL overall=PASS scenarios=7", "NO_HARDWARE_PROGRAMMING=1", "NO_UART_WRITE=1", "NO_TFDU_DRIVE=1", "SCENARIO name=tcp_reset_reconnect status=PASS", "SCENARIO name=host_restart status=PASS", "SCENARIO name=cable_replug_reconnect status=PASS", "SCENARIO name=dhcp_address_change status=PASS", "SCENARIO name=dhcp_timeout_static_fallback status=PASS", "SCENARIO name=queued_rx_after_reconnect status=PASS")

$boardDryRun = Invoke-LoggedProcess -Name "board_tcp_safe_dry_run" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $boardTcpSafe,
    "-UseStaticFallback",
    "-SkipUartProbe",
    "-TargetHost",
    "192.168.10.2",
    "-ReconnectCycles",
    [string]$ReconnectCycles,
    "-TimeoutSeconds",
    "1.0",
    "-DryRun"
) -TimeoutSecondsForStep 30
Add-CaseResult -Name "board_tcp_safe_dry_run" -Coverage "Real board PS/PC TCP-DHCP acceptance wrapper is safe under the current no-Ethernet/no-target-TCP condition: it records target TCP unreachable, no programming, no TX_DATA, no TFDU drive, and no real TCP/DHCP pass claim." -Result $boardDryRun -RequiredPatterns @("BOARD_TCP_DHCP_ACCEPTANCE_PASS=0", "TCP_QUICK_CONNECT_OK=0", "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1")

$twoAxWrapperOffline = Invoke-LoggedProcess -Name "two_ax7010_safe_wrapper_offline_model" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $twoAxSafe,
    "-OfflineModel",
    "-Repeat",
    [string]$Repeat,
    "-PayloadSize",
    [string]$PayloadSize,
    "-TimeoutSeconds",
    [string]([Math]::Max($TimeoutSeconds, 10.0))
) -TimeoutSecondsForStep 120
Add-CaseResult -Name "two_ax7010_safe_wrapper_offline_model" -Coverage "Two-AX7010 safe wrapper can run the strengthened offline endpoint model, including 8-lane and 4+4 lane-mask coverage, without programming hardware, writing UART, sending TX data to real boards, or driving TFDU boards." -Result $twoAxWrapperOffline -RequiredPatterns @("TWO_AX7010_OFFLINE_MODEL_PASS=1", "fdx_a_to_b_tx_lane_coverage=0x0f", "fdx_b_to_a_tx_lane_coverage=0xf0", "NO_TX_DATA_TO_REAL_BOARDS=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1")

$twoAxDryRun = Invoke-LoggedProcess -Name "two_ax7010_safe_wrapper_dry_run_cap" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $twoAxSafe,
    "-TargetHostA",
    "192.168.10.2",
    "-TargetHostB",
    "192.168.10.3",
    "-AllowTraffic",
    "-DurationSeconds",
    "7200",
    "-TimeoutSeconds",
    "1.0",
    "-DryRun"
) -TimeoutSecondsForStep 40
Add-CaseResult -Name "two_ax7010_safe_wrapper_dry_run_cap" -Coverage "Two-AX7010 real acceptance wrapper caps any requested continuous traffic above 600 s and stays dry-run/no-TFDU under no-Ethernet conditions." -Result $twoAxDryRun -RequiredPatterns @("TWO_AX7010_DRY_RUN=1", "CONTINUOUS_RUNTIME_CAP_APPLIED=1", "DURATION_SECONDS_EFFECTIVE=600", "NO_TX_DATA_TO_REAL_BOARDS=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1")

$rotatingDryRun = Invoke-LoggedProcess -Name "rotating_shaft_safe_wrapper_dry_run_cap" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $rotatingSafe,
    "-TargetHostA",
    "192.168.10.2",
    "-TargetHostB",
    "192.168.10.3",
    "-AllowTraffic",
    "-ProgramShutdownAfterRun",
    "-ShaftDiameterMm",
    "200",
    "-Rpm",
    "600",
    "-DurationSeconds",
    "7200",
    "-TimeoutSeconds",
    "1.0",
    "-DryRun"
) -TimeoutSecondsForStep 40
Add-CaseResult -Name "rotating_shaft_safe_wrapper_dry_run_cap" -Coverage "Rotating-shaft real acceptance wrapper records 20 cm / 600 rpm target metadata, caps requests above 600 s, and stays dry-run/no-TFDU while Ethernet and fixture hardware are unavailable." -Result $rotatingDryRun -RequiredPatterns @("ROTATING_SHAFT_DRY_RUN=1", "CONTINUOUS_RUNTIME_CAP_APPLIED=1", "DURATION_SECONDS_EFFECTIVE=600", "SHAFT_DIAMETER_MM=200", "RPM=600", "NO_TX_DATA_TO_REAL_BOARDS=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1")

$productLoopDryRun = Invoke-LoggedProcess -Name "product_loop_safe_wrapper_dry_run_cap" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $productLoopSafe,
    "-Topology",
    "two_ax7010",
    "-TargetHostA",
    "192.168.10.2",
    "-TargetHostB",
    "192.168.10.3",
    "-AllowTraffic",
    "-ProgramShutdownAfterRun",
    "-DurationSeconds",
    "7200",
    "-TimeoutSeconds",
    "1.0",
    "-DryRun"
) -TimeoutSecondsForStep 40
Add-CaseResult -Name "product_loop_safe_wrapper_dry_run_cap" -Coverage "Product-loop real acceptance wrapper covers the two-AX7010 product topology, caps requests above 600 s, and stays dry-run/no-TFDU while Ethernet is unavailable." -Result $productLoopDryRun -RequiredPatterns @("PRODUCT_LOOP_DRY_RUN=1", "TOPOLOGY=two_ax7010", "CONTINUOUS_RUNTIME_CAP_APPLIED=1", "DURATION_SECONDS_EFFECTIVE=600", "NO_TX_DATA_TO_REAL_BOARDS=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1")

$eightLaneDryRun = Invoke-LoggedProcess -Name "eight_lane_hardware_safe_wrapper_dry_run_cap" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $eightLaneSafe,
    "-Profile",
    "reduced_8lane_frag16_external",
    "-LaneCount",
    "8",
    "-TargetHostA",
    "192.168.10.2",
    "-TargetHostB",
    "192.168.10.3",
    "-AllowTraffic",
    "-PinmapReviewed",
    "-ShutdownBitstreamReviewed",
    "-ProgramShutdownBeforeRun",
    "-ProgramShutdownAfterRun",
    "-DurationSeconds",
    "7200",
    "-TimeoutSeconds",
    "1.0",
    "-DryRun"
) -TimeoutSecondsForStep 40
Add-CaseResult -Name "eight_lane_hardware_safe_wrapper_dry_run_cap" -Coverage "8-lane hardware acceptance wrapper checks the reduced fragment=16 raw 32/16 Mbit/s bitstream precondition, candidate 8-lane coverage, the current no-Ethernet/no-target-TCP blocker, caps requests above 600 s, and stays dry-run/no-TFDU." -Result $eightLaneDryRun -RequiredPatterns @("EIGHT_LANE_HARDWARE_DRY_RUN=1", "PROFILE=reduced_8lane_frag16_external", "LANE_COUNT_REQUESTED=8", "CONTINUOUS_RUNTIME_CAP_APPLIED=1", "DURATION_SECONDS_EFFECTIVE=600", "CANDIDATE_A_LANE_COUNT=8", "CANDIDATE_B_LANE_COUNT=8", "REDUCED_8LANE_FRAG16_BITSTREAM_READY_FOR_REVIEW=1", "REDUCED_8LANE_FRAG16_RAW_HALF_MBPS=32.0", "REDUCED_8LANE_FRAG16_RAW_FDX_PER_DIR_MBPS=16.0", "TCP_A_QUICK_CONNECT_OK=0", "TCP_B_QUICK_CONNECT_OK=0", "NO_TX_DATA_TO_REAL_BOARDS=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1")

$csvLines = [System.Collections.Generic.List[string]]::new()
$csvLines.Add("name,status,exit_code,timed_out,seconds,patterns,log,err,coverage")
foreach ($row in $rows) {
    $csvLines.Add((@(
        (Csv-Escape $row.name),
        (Csv-Escape $row.status),
        $row.exit_code,
        $row.timed_out,
        $row.seconds,
        (Csv-Escape $row.patterns),
        (Csv-Escape $row.log),
        (Csv-Escape $row.err),
        (Csv-Escape $row.coverage)
    ) -join ","))
}
[System.IO.File]::WriteAllLines($csvPath, [string[]]$csvLines, [System.Text.Encoding]::ASCII)

$passCount = @($rows | Where-Object { $_.status -eq "PASS" }).Count
$failCount = @($rows | Where-Object { $_.status -ne "PASS" }).Count
$overallPass = (($constraintHash -eq $expectedConstraintSha256) -and $failCount -eq 0)

Write-SummaryLine "NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT=$passCount"
Write-SummaryLine "NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT=$failCount"
Write-SummaryLine "NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=$([int]$overallPass)"
Write-SummaryLine "SUMMARY=$summaryPath"
Write-SummaryLine "CSV=$csvPath"
Write-SummaryLine "MARKDOWN=$mdPath"
Write-SummaryLine "LOG_DIR=$logDir"
Write-SummaryLine "NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_END $(Get-Date -Format o)"

$md = [System.Collections.Generic.List[string]]::new()
$md.Add("# No-Ethernet Network Offline Acceptance")
$md.Add("")
$md.Add("Generated: $(Get-Date -Format o)")
$md.Add("")
$md.Add("## Verdict")
$md.Add("")
$md.Add("- Overall: $(if ($overallPass) { 'PASS' } else { 'FAIL' })")
$md.Add("- Pass count: $passCount")
$md.Add("- Fail count: $failCount")
$md.Add("- Real board TCP/DHCP: NOT_RUN_NO_ETHERNET")
$md.Add("- Real two-AX7010 traffic: NOT_RUN_NO_ETHERNET")
$md.Add("- Real rotating/product/8-lane traffic: NOT_RUN_NO_ETHERNET")
$md.Add("")
$md.Add("This gate intentionally does not program FPGA hardware, does not write UART, does not send TX_DATA to real boards, and does not drive TFDU boards.")
$md.Add("")
$md.Add("## Cases")
$md.Add("")
$md.Add("| case | status | seconds | coverage |")
$md.Add("| --- | --- | --- | --- |")
foreach ($row in $rows) {
    $coverage = ($row.coverage -replace "\|", "/")
    $md.Add("| $($row.name) | $($row.status) | $($row.seconds) | $coverage |")
}
$md.Add("")
$md.Add("## Evidence")
$md.Add("")
$md.Add("~~~text")
$md.Add("NO_HARDWARE_PROGRAMMING=1")
$md.Add("NO_UART_WRITE=1")
$md.Add("NO_TFDU_DRIVE=1")
$md.Add("NO_REAL_BOARD_TCP_DHCP=1")
$md.Add("NO_REAL_TWO_AX7010_TRAFFIC=1")
$md.Add("CONSTRAINT_SHA256=$constraintHash")
$md.Add("CONSTRAINT_UNCHANGED=$([int]($constraintHash -eq $expectedConstraintSha256))")
$md.Add("NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT=$passCount")
$md.Add("NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT=$failCount")
$md.Add("NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=$([int]$overallPass)")
$md.Add("SUMMARY=$summaryPath")
$md.Add("CSV=$csvPath")
$md.Add("LOG_DIR=$logDir")
$md.Add("~~~")
[System.IO.File]::WriteAllLines($mdPath, [string[]]$md, [System.Text.Encoding]::UTF8)

if ($overallPass) {
    exit 0
}
exit 1
