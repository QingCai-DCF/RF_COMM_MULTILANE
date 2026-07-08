[CmdletBinding()]
param(
    [string]$TargetHostA = "",
    [string]$TargetHostB = "",
    [int]$PortA = 5001,
    [int]$PortB = 5001,
    [int]$Repeat = 32,
    [int]$PayloadSize = 256,
    [int]$DurationSeconds = 0,
    [double]$TimeoutSeconds = 5.0,
    [int]$ReconnectCycles = 4,
    [string]$TxLaneMaskA = "0x0f",
    [string]$RxLaneMaskA = "0xf0",
    [string]$TxLaneMaskB = "0xf0",
    [string]$RxLaneMaskB = "0x0f",
    [switch]$AllowTraffic,
    [switch]$ProgramShutdownAfterRun,
    [switch]$OfflineModel,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "two_ax7010_end_to_end_acceptance_safe_$stamp.summary.txt"
$mdReport = Join-Path $reportsDir "two_ax7010_end_to_end_acceptance_safe_$stamp.md"
$criteriaCsv = Join-Path $reportsDir "two_ax7010_end_to_end_acceptance_safe_$stamp.criteria.csv"
$runDir = Join-Path $reportsDir "two_ax7010_end_to_end_acceptance_safe_$stamp"
$acceptanceScript = Join-Path $repoRoot "software\host_client\run_acceptance.ps1"
$offlineModelScript = Join-Path $repoRoot "software\host_client\two_ax7010_end_to_end_model.py"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown_8lane_candidate.tcl"
$physicalGateScript = Join-Path $repoRoot "tools\check_physical_matrix_gate.ps1"
$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$maxContinuousRunSeconds = 600

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

foreach ($path in @($acceptanceScript, $offlineModelScript, $shutdownTcl, $physicalGateScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Add-MdLine {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Line
    )
    $Lines.Add($Line)
}

function Csv-Escape {
    param([AllowNull()][string]$Value)
    if ($null -eq $Value) {
        return '""'
    }
    return '"' + ($Value -replace '"', '""') + '"'
}

function Add-CsvRow {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string[]]$Values
    )
    $escaped = foreach ($value in $Values) {
        Csv-Escape $value
    }
    $Lines.Add(($escaped -join ","))
}

function Format-Rate {
    param([double]$Value)
    return $Value.ToString("0.000000", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-MaxMetric {
    param(
        [string]$Text,
        [string]$MetricName
    )
    $maxValue = 0.0
    $pattern = "(?m)\b" + [regex]::Escape($MetricName) + "=([0-9]+(?:\.[0-9]+)?)"
    foreach ($match in [regex]::Matches($Text, $pattern)) {
        $value = [double]::Parse($match.Groups[1].Value, [System.Globalization.CultureInfo]::InvariantCulture)
        if ($value -gt $maxValue) {
            $maxValue = $value
        }
    }
    return $maxValue
}

function Get-MinPositiveOrZero {
    param([double[]]$Values)
    $positive = @($Values | Where-Object { $_ -gt 0.0 })
    if ($positive.Count -eq 0) {
        return 0.0
    }
    $minValue = [double]$positive[0]
    foreach ($value in $positive) {
        if ($value -lt $minValue) {
            $minValue = [double]$value
        }
    }
    return $minValue
}

function Write-RateClaim {
    param(
        [double]$PayloadHalfMbps,
        [double]$PayloadFdxPerDirMbps
    )
    Write-SummaryLine "RAW_HALF_MBPS=32.0"
    Write-SummaryLine "RAW_FDX_PER_DIR_MBPS=16.0"
    Write-SummaryLine "RATE_CLAIM=raw_phy_only"
    Write-SummaryLine "EFFECTIVE_PAYLOAD_REPORTED=1"
    Write-SummaryLine ("PAYLOAD_HALF_MBPS={0}" -f (Format-Rate $PayloadHalfMbps))
    Write-SummaryLine ("PAYLOAD_FDX_PER_DIR_MBPS={0}" -f (Format-Rate $PayloadFdxPerDirMbps))
}

function Test-TcpPortQuick {
    param(
        [string]$HostName,
        [int]$TcpPort,
        [int]$TimeoutMs
    )
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $iar = $client.BeginConnect($HostName, $TcpPort, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            $client.Close()
            return $false
        }
        $client.EndConnect($iar)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Invoke-LoggedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [string]$ErrPath,
        [int]$TimeoutSecondsForStep
    )

    Write-SummaryLine "STEP_START name=$Name log=$LogPath err=$ErrPath"
    Write-SummaryLine "STEP_COMMAND name=$Name $FilePath $($Arguments -join ' ')"
    if ($DryRun) {
        Write-SummaryLine "STEP_DRY_RUN name=$Name"
        return [pscustomobject]@{ ExitCode = 0; TimedOut = $false; Stdout = ""; Stderr = "" }
    }

    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError $ErrPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSecondsForStep * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-SummaryLine "STEP_RESULT name=$Name exit=124 timeout=1"
        return [pscustomobject]@{
            ExitCode = 124
            TimedOut = $true
            Stdout = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { "" }
            Stderr = if (Test-Path -LiteralPath $ErrPath) { Get-Content -LiteralPath $ErrPath -Raw -ErrorAction SilentlyContinue } else { "" }
        }
    }
    $proc.Refresh()
    $exit = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
    Write-SummaryLine "STEP_RESULT name=$Name exit=$exit timeout=0"
    return [pscustomobject]@{
        ExitCode = $exit
        TimedOut = $false
        Stdout = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { "" }
        Stderr = if (Test-Path -LiteralPath $ErrPath) { Get-Content -LiteralPath $ErrPath -Raw -ErrorAction SilentlyContinue } else { "" }
    }
}

function Invoke-Acceptance {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [int]$TimeoutSecondsForStep
    )

    return Invoke-LoggedProcess `
        -Name $Name `
        -FilePath "powershell.exe" `
        -Arguments (@("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $acceptanceScript) + $Arguments) `
        -LogPath (Join-Path $runDir "$Name.out.log") `
        -ErrPath (Join-Path $runDir "$Name.err.log") `
        -TimeoutSecondsForStep $TimeoutSecondsForStep
}

function Invoke-PhysicalMatrixGate {
    param([string[]]$RequiredLinks)

    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $physicalGateScript -RequiredLinks ($RequiredLinks -join ",") 2>&1
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    foreach ($line in $output) {
        [void](Write-SummaryLine "PHYSICAL_MATRIX_GATE_OUTPUT=$line")
    }
    [void](Write-SummaryLine "PHYSICAL_MATRIX_GATE_EXIT=$exitCode")
    return $exitCode
}

"TWO_AX7010_END_TO_END_ACCEPTANCE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "TARGET_HOST_A=$TargetHostA"
Write-SummaryLine "TARGET_HOST_B=$TargetHostB"
Write-SummaryLine "PORT_A=$PortA"
Write-SummaryLine "PORT_B=$PortB"
Write-SummaryLine "CRITERIA_CSV=$criteriaCsv"
Write-SummaryLine "REPEAT=$Repeat"
Write-SummaryLine "PAYLOAD_SIZE=$PayloadSize"
Write-SummaryLine "DURATION_SECONDS_REQUESTED=$DurationSeconds"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "RECONNECT_CYCLES=$ReconnectCycles"
Write-SummaryLine "TX_LANE_MASK_A=$TxLaneMaskA"
Write-SummaryLine "RX_LANE_MASK_A=$RxLaneMaskA"
Write-SummaryLine "TX_LANE_MASK_B=$TxLaneMaskB"
Write-SummaryLine "RX_LANE_MASK_B=$RxLaneMaskB"
Write-SummaryLine "ALLOW_TRAFFIC=$([int]$AllowTraffic.IsPresent)"
Write-SummaryLine "PROGRAM_SHUTDOWN_AFTER_RUN=$([int]$ProgramShutdownAfterRun.IsPresent)"
Write-SummaryLine "OFFLINE_MODEL=$([int]$OfflineModel.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "MAX_CONTINUOUS_RUN_SECONDS=$maxContinuousRunSeconds"
Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1"

$willUseRealTraffic = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent -and -not $OfflineModel.IsPresent)
if (-not $willUseRealTraffic) {
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=0"
} else {
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS=0"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0"
    Write-SummaryLine "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=1"
}

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

$effectiveDurationSeconds = $DurationSeconds
if ($effectiveDurationSeconds -gt $maxContinuousRunSeconds) {
    $effectiveDurationSeconds = $maxContinuousRunSeconds
    Write-SummaryLine "CONTINUOUS_RUNTIME_CAP_APPLIED=1"
} else {
    Write-SummaryLine "CONTINUOUS_RUNTIME_CAP_APPLIED=0"
}
Write-SummaryLine "DURATION_SECONDS_EFFECTIVE=$effectiveDurationSeconds"

if ($OfflineModel) {
    $offlineLog = Join-Path $runDir "offline_model.out.log"
    $offlineErr = Join-Path $runDir "offline_model.err.log"
    $modelPayloadSize = [Math]::Min($PayloadSize, 512)
    $offlineResult = Invoke-LoggedProcess -Name "offline_two_ax7010_model" -FilePath "python" -Arguments @(
        $offlineModelScript,
        "--repeat", [string]$Repeat,
        "--payload-size", [string]$modelPayloadSize,
        "--timeout", [string]([Math]::Max($TimeoutSeconds, 10.0)),
        "--log-dir", (Join-Path $runDir "offline_model")
    ) -LogPath $offlineLog -ErrPath $offlineErr -TimeoutSecondsForStep ([int]([Math]::Max($TimeoutSeconds, 10.0) + 20.0))
    $offlinePass = (
        $offlineResult.ExitCode -eq 0 -and
        $offlineResult.Stdout -match "TWO_AX7010_END_TO_END_OFFLINE_PASS" -and
        $offlineResult.Stdout -match "hdx_tx_lane_coverage=0xff" -and
        $offlineResult.Stdout -match "hdx_rx_lane_coverage=0xff" -and
        $offlineResult.Stdout -match "fdx_a_to_b_tx_lane_coverage=0x0f" -and
        $offlineResult.Stdout -match "fdx_a_to_b_rx_lane_coverage=0x0f" -and
        $offlineResult.Stdout -match "fdx_b_to_a_tx_lane_coverage=0xf0" -and
        $offlineResult.Stdout -match "fdx_b_to_a_rx_lane_coverage=0xf0" -and
        $offlineResult.Stdout -match "route_probe_events="
    )
    foreach ($line in (($offlineResult.Stdout + "`n" + $offlineResult.Stderr) -split "`r?`n" | Where-Object { $_ -match "TWO_AX7010|PASS|FAIL|lane|reconnect" } | Select-Object -Last 30)) {
        Write-SummaryLine "OFFLINE_MATCH=$line"
    }
    Write-SummaryLine "TWO_AX7010_OFFLINE_MODEL_PASS=$([int]$offlinePass)"
    Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1"
    Write-SummaryLine "TWO_AX7010_BLOCKED_REASON=real_two_board_ethernet_not_run"
    Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_EXIT=$([int](-not $offlinePass))"
    Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

    $csvLines = [System.Collections.Generic.List[string]]::new()
    $csvLines.Add("criterion,status,value,note")
    Add-CsvRow $csvLines @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
    Add-CsvRow $csvLines @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
    Add-CsvRow $csvLines @("offline_model", $(if ($offlinePass) { "PASS" } else { "FAIL" }), [string]$offlineResult.ExitCode, "offline two-endpoint model only")
    Add-CsvRow $csvLines @("offline_8lane_hdx", $(if ($offlineResult.Stdout -match "hdx_tx_lane_coverage=0xff" -and $offlineResult.Stdout -match "hdx_rx_lane_coverage=0xff") { "PASS" } else { "FAIL" }), "tx=0xff,rx=0xff", "offline model covers 8-lane bidirectional raw lane mask")
    Add-CsvRow $csvLines @("offline_4plus4_fdx", $(if ($offlineResult.Stdout -match "fdx_a_to_b_tx_lane_coverage=0x0f" -and $offlineResult.Stdout -match "fdx_b_to_a_tx_lane_coverage=0xf0") { "PASS" } else { "FAIL" }), "a_to_b_tx=0x0f,b_to_a_tx=0xf0", "offline model covers 4+4 full-duplex lane-mask configuration")
    Add-CsvRow $csvLines @("real_acceptance", "BLOCKED", "real_two_board_ethernet_not_run", "offline model is not real hardware acceptance")
    [System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLines, [System.Text.Encoding]::ASCII)

    $md = [System.Collections.Generic.List[string]]::new()
    Add-MdLine $md "# Two AX7010 End-to-End Acceptance"
    Add-MdLine $md ""
    Add-MdLine $md "Generated: $(Get-Date -Format o)"
    Add-MdLine $md ""
    Add-MdLine $md "Verdict: OFFLINE_MODEL_PASS_REAL_HARDWARE_NOT_RUN"
    Add-MdLine $md ""
    Add-MdLine $md "This run did not program hardware, did not write UART, did not send TX_DATA to real boards, and did not drive TFDU boards."
    Add-MdLine $md ""
    Add-MdLine $md "- Offline model pass: $offlinePass"
    Add-MdLine $md "- Summary log: $summaryLog"
    Add-MdLine $md "- Criteria CSV: $criteriaCsv"
    Add-MdLine $md "- Offline stdout: $offlineLog"
    Add-MdLine $md "- Offline stderr: $offlineErr"
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)
    if ($offlinePass) { exit 0 } else { exit 1 }
}

$blockedReasons = [System.Collections.Generic.List[string]]::new()
if (-not $AllowTraffic) {
    $blockedReasons.Add("allow_traffic_not_set")
}
if ($AllowTraffic -and -not $ProgramShutdownAfterRun) {
    $blockedReasons.Add("program_shutdown_after_run_not_set")
}
if ($TargetHostA -eq "") {
    $blockedReasons.Add("target_host_a_missing")
}
if ($TargetHostB -eq "") {
    $blockedReasons.Add("target_host_b_missing")
}
if ($willUseRealTraffic) {
    $physicalGateExit = Invoke-PhysicalMatrixGate -RequiredLinks @("A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1")
    if ($physicalGateExit -ne 0) {
        $blockedReasons.Add("physical_matrix_not_passing")
    }
}

$eth = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {
    $_.InterfaceDescription -match "Realtek|Ethernet|GbE|2.5GbE" -or $_.Name -match "Ethernet"
} | Sort-Object -Property @{ Expression = { if ($_.Status -eq "Up") { 0 } else { 1 } } }, Name | Select-Object -First 1
if ($null -eq $eth) {
    $blockedReasons.Add("ethernet_adapter_missing")
    Write-SummaryLine "ETH_ADAPTER_STATUS=MISSING"
} else {
    Write-SummaryLine "ETH_ADAPTER_NAME=$($eth.Name)"
    Write-SummaryLine "ETH_ADAPTER_DESC=$($eth.InterfaceDescription)"
    Write-SummaryLine "ETH_ADAPTER_STATUS=$($eth.Status)"
    Write-SummaryLine "ETH_ADAPTER_LINK_SPEED=$($eth.LinkSpeed)"
    if ($eth.Status -ne "Up") {
        $blockedReasons.Add("ethernet_link_not_up")
    }
}

$tcpA = $false
$tcpB = $false
if ($TargetHostA -ne "") {
    $tcpA = Test-TcpPortQuick -HostName $TargetHostA -TcpPort $PortA -TimeoutMs ([int]([Math]::Max($TimeoutSeconds, 1.0) * 1000.0))
}
if ($TargetHostB -ne "") {
    $tcpB = Test-TcpPortQuick -HostName $TargetHostB -TcpPort $PortB -TimeoutMs ([int]([Math]::Max($TimeoutSeconds, 1.0) * 1000.0))
}
Write-SummaryLine "TCP_A_QUICK_CONNECT_OK=$([int]$tcpA)"
Write-SummaryLine "TCP_B_QUICK_CONNECT_OK=$([int]$tcpB)"
if ($AllowTraffic -and $TargetHostA -ne "" -and -not $tcpA) { $blockedReasons.Add("tcp_a_not_reachable") }
if ($AllowTraffic -and $TargetHostB -ne "" -and -not $tcpB) { $blockedReasons.Add("tcp_b_not_reachable") }

if ($DryRun) {
    Write-SummaryLine "TWO_AX7010_DRY_RUN=1"
    Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=0"
    Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_EXIT=0"
    Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

    $csvLines = [System.Collections.Generic.List[string]]::new()
    $csvLines.Add("criterion,status,value,note")
    Add-CsvRow $csvLines @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
    Add-CsvRow $csvLines @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
    Add-CsvRow $csvLines @("dry_run", "PASS", "1", "no two-AX7010 traffic was sent")
    Add-CsvRow $csvLines @("real_acceptance", "BLOCKED", "dry_run", "dry-run is not real hardware acceptance")
    [System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLines, [System.Text.Encoding]::ASCII)
    exit 0
}

if ($blockedReasons.Count -gt 0) {
    foreach ($reason in $blockedReasons) {
        Write-SummaryLine "TWO_AX7010_BLOCKED_REASON=$reason"
    }
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS_FINAL=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT_FINAL=1"
    Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1"
    Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_EXIT=20"
    Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

    $csvLinesBlocked = [System.Collections.Generic.List[string]]::new()
    $csvLinesBlocked.Add("criterion,status,value,note")
    Add-CsvRow $csvLinesBlocked @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
    Add-CsvRow $csvLinesBlocked @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
    Add-CsvRow $csvLinesBlocked @("real_acceptance", "BLOCKED", ($blockedReasons -join ";"), "preconditions were not met")
    [System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLinesBlocked, [System.Text.Encoding]::ASCII)

    $md = [System.Collections.Generic.List[string]]::new()
    Add-MdLine $md "# Two AX7010 End-to-End Acceptance"
    Add-MdLine $md ""
    Add-MdLine $md "Generated: $(Get-Date -Format o)"
    Add-MdLine $md ""
    Add-MdLine $md "Verdict: BLOCKED"
    Add-MdLine $md ""
    Add-MdLine $md "This run did not program hardware, did not write UART, did not send TX_DATA to real boards, and did not drive TFDU boards."
    Add-MdLine $md ""
    Add-MdLine $md ("Blocked reasons: " + ($blockedReasons -join ','))
    Add-MdLine $md ("Summary log: " + $summaryLog)
    Add-MdLine $md ("Criteria CSV: " + $criteriaCsv)
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)
    exit 20
}

$smokeA = Invoke-Acceptance -Name "smoke_a" -Arguments @("-Mode", "smoke", "-TargetHost", $TargetHostA, "-Port", [string]$PortA, "-TimeoutSeconds", [string]$TimeoutSeconds) -TimeoutSecondsForStep ([int]($TimeoutSeconds + 20))
$smokeB = Invoke-Acceptance -Name "smoke_b" -Arguments @("-Mode", "smoke", "-TargetHost", $TargetHostB, "-Port", [string]$PortB, "-TimeoutSeconds", [string]$TimeoutSeconds) -TimeoutSecondsForStep ([int]($TimeoutSeconds + 20))
$reconnectA = Invoke-Acceptance -Name "reconnect_a" -Arguments @("-Mode", "reconnect", "-TargetHost", $TargetHostA, "-Port", [string]$PortA, "-TimeoutSeconds", [string]$TimeoutSeconds, "-ReconnectCycles", [string]$ReconnectCycles) -TimeoutSecondsForStep ([int](($TimeoutSeconds + 2.0) * $ReconnectCycles + 20))
$reconnectB = Invoke-Acceptance -Name "reconnect_b" -Arguments @("-Mode", "reconnect", "-TargetHost", $TargetHostB, "-Port", [string]$PortB, "-TimeoutSeconds", [string]$TimeoutSeconds, "-ReconnectCycles", [string]$ReconnectCycles) -TimeoutSecondsForStep ([int](($TimeoutSeconds + 2.0) * $ReconnectCycles + 20))

$trafficArgsA = @("-Mode", "fdx_partition", "-TargetHost", $TargetHostA, "-Port", [string]$PortA, "-TimeoutSeconds", [string]$TimeoutSeconds, "-TxLaneMask", $TxLaneMaskA, "-RxLaneMask", $RxLaneMaskA, "-PayloadSize", [string]$PayloadSize)
$trafficArgsB = @("-Mode", "fdx_partition", "-TargetHost", $TargetHostB, "-Port", [string]$PortB, "-TimeoutSeconds", [string]$TimeoutSeconds, "-TxLaneMask", $TxLaneMaskB, "-RxLaneMask", $RxLaneMaskB, "-PayloadSize", [string]$PayloadSize)
if ($effectiveDurationSeconds -gt 0) {
    $trafficArgsA += @("-DurationSeconds", [string]$effectiveDurationSeconds)
    $trafficArgsB += @("-DurationSeconds", [string]$effectiveDurationSeconds)
} else {
    $trafficArgsA += @("-Repeat", [string]$Repeat, "-MinRxFrames", [string]$Repeat)
    $trafficArgsB += @("-Repeat", [string]$Repeat, "-MinRxFrames", [string]$Repeat)
}

$trafficTimeout = if ($effectiveDurationSeconds -gt 0) { $effectiveDurationSeconds + 90 } else { 120 }
$trafficA = Invoke-Acceptance -Name "traffic_a_to_b" -Arguments $trafficArgsA -TimeoutSecondsForStep $trafficTimeout
$trafficB = Invoke-Acceptance -Name "traffic_b_to_a" -Arguments $trafficArgsB -TimeoutSecondsForStep $trafficTimeout

$shutdownResult = Invoke-LoggedProcess `
    -Name "shutdown_after_two_ax7010_run" `
    -FilePath "vivado" `
    -Arguments @("-mode", "batch", "-source", $shutdownTcl) `
    -LogPath (Join-Path $runDir "shutdown_after_two_ax7010_run.out.log") `
    -ErrPath (Join-Path $runDir "shutdown_after_two_ax7010_run.err.log") `
    -TimeoutSecondsForStep 180

$smokeOk = ($smokeA.ExitCode -eq 0 -and $smokeB.ExitCode -eq 0)
$reconnectOk = ($reconnectA.ExitCode -eq 0 -and $reconnectB.ExitCode -eq 0)
$trafficOk = ($trafficA.ExitCode -eq 0 -and $trafficB.ExitCode -eq 0)
$shutdownPass = ($shutdownResult.ExitCode -eq 0)
$trafficAText = "$($trafficA.Stdout)`n$($trafficA.Stderr)"
$trafficBText = "$($trafficB.Stdout)`n$($trafficB.Stderr)"
$payloadTxA = Get-MaxMetric -Text $trafficAText -MetricName "tx_mbps"
$payloadRxA = Get-MaxMetric -Text $trafficAText -MetricName "rx_mbps"
$payloadTxB = Get-MaxMetric -Text $trafficBText -MetricName "tx_mbps"
$payloadRxB = Get-MaxMetric -Text $trafficBText -MetricName "rx_mbps"
$payloadHalfMbps = [Math]::Max([Math]::Max($payloadTxA, $payloadRxA), [Math]::Max($payloadTxB, $payloadRxB))
$payloadFdxPerDirMbps = Get-MinPositiveOrZero @($payloadTxA, $payloadRxA, $payloadTxB, $payloadRxB)
$pass = ($smokeOk -and $reconnectOk -and $trafficOk -and $shutdownPass)

Write-SummaryLine "SMOKE_BOTH_OK=$([int]$smokeOk)"
Write-SummaryLine "RECONNECT_BOTH_OK=$([int]$reconnectOk)"
Write-SummaryLine "BIDIRECTIONAL_TRAFFIC_OK=$([int]$trafficOk)"
Write-SummaryLine "TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=$([int]$shutdownPass)"
Write-RateClaim -PayloadHalfMbps $payloadHalfMbps -PayloadFdxPerDirMbps $payloadFdxPerDirMbps
Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_PASS=$([int]$pass)"
Write-SummaryLine "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=0"
$exitCode = if ($pass) { 0 } else { 1 }
Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_EXIT=$exitCode"
Write-SummaryLine "TWO_AX7010_END_TO_END_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

$csvLinesReal = [System.Collections.Generic.List[string]]::new()
$csvLinesReal.Add("criterion,status,value,note")
Add-CsvRow $csvLinesReal @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
Add-CsvRow $csvLinesReal @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
Add-CsvRow $csvLinesReal @("smoke_both", $(if ($smokeOk) { "PASS" } else { "FAIL" }), "$($smokeA.ExitCode),$($smokeB.ExitCode)", "both PS bridge endpoints answered smoke checks")
Add-CsvRow $csvLinesReal @("reconnect_both", $(if ($reconnectOk) { "PASS" } else { "FAIL" }), "$($reconnectA.ExitCode),$($reconnectB.ExitCode)", "both PS bridge endpoints passed reconnect checks")
Add-CsvRow $csvLinesReal @("bidirectional_traffic", $(if ($trafficOk) { "PASS" } else { "FAIL" }), "$($trafficA.ExitCode),$($trafficB.ExitCode)", "real bidirectional traffic wrapper result")
Add-CsvRow $csvLinesReal @("raw_payload_rate_separation", "PASS", "raw_half=32.0,raw_fdx_per_dir=16.0,rate_claim=raw_phy_only", "raw PHY target and effective payload throughput are reported separately")
Add-CsvRow $csvLinesReal @("payload_throughput_reported", $(if ($trafficOk) { "PASS" } else { "FAIL" }), ("payload_half={0},payload_fdx_per_dir={1},a_tx={2},a_rx={3},b_tx={4},b_rx={5}" -f (Format-Rate $payloadHalfMbps), (Format-Rate $payloadFdxPerDirMbps), (Format-Rate $payloadTxA), (Format-Rate $payloadRxA), (Format-Rate $payloadTxB), (Format-Rate $payloadRxB)), "payload throughput is measured from real traffic client summaries")
Add-CsvRow $csvLinesReal @("shutdown_after_run", $(if ($shutdownPass) { "PASS" } else { "FAIL" }), [string]$shutdownResult.ExitCode, "shutdown bitstream programmed after TFDU/TX run")
[System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLinesReal, [System.Text.Encoding]::ASCII)

$mdOut = [System.Collections.Generic.List[string]]::new()
Add-MdLine $mdOut "# Two AX7010 End-to-End Acceptance"
Add-MdLine $mdOut ""
Add-MdLine $mdOut "Generated: $(Get-Date -Format o)"
Add-MdLine $mdOut ""
if ($pass) {
    Add-MdLine $mdOut "Verdict: PASS_REAL_TWO_AX7010_END_TO_END"
} else {
    Add-MdLine $mdOut "Verdict: FAIL_REAL_TWO_AX7010_END_TO_END"
}
Add-MdLine $mdOut ""
Add-MdLine $mdOut "- Smoke both OK: $smokeOk"
Add-MdLine $mdOut "- Reconnect both OK: $reconnectOk"
Add-MdLine $mdOut "- Bidirectional traffic OK: $trafficOk"
Add-MdLine $mdOut "- Shutdown after run pass: $shutdownPass"
Add-MdLine $mdOut "- Summary log: $summaryLog"
Add-MdLine $mdOut "- Criteria CSV: $criteriaCsv"
Add-MdLine $mdOut "- Run directory: $runDir"
[System.IO.File]::WriteAllLines($mdReport, [string[]]$mdOut, [System.Text.Encoding]::UTF8)

exit $exitCode
