[CmdletBinding()]
param(
    [string]$TargetHostA = "",
    [string]$TargetHostB = "",
    [int]$PortA = 5001,
    [int]$PortB = 5001,
    [int]$Repeat = 32,
    [int]$PayloadSize = 256,
    [int]$DurationSeconds = 600,
    [double]$TimeoutSeconds = 5.0,
    [int]$ReconnectCycles = 4,
    [double]$ShaftDiameterMm = 200.0,
    [double]$ShaftDiameterToleranceMm = 20.0,
    [double]$Rpm = 600.0,
    [double]$RpmTolerance = 30.0,
    [string]$FixtureLogPath = "",
    [string]$TxLaneMaskA = "0x0f",
    [string]$RxLaneMaskA = "0xf0",
    [string]$TxLaneMaskB = "0xf0",
    [string]$RxLaneMaskB = "0x0f",
    [switch]$AllowTraffic,
    [switch]$ProgramShutdownAfterRun,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "rotating_shaft_acceptance_safe_$stamp.summary.txt"
$mdReport = Join-Path $reportsDir "rotating_shaft_acceptance_safe_$stamp.md"
$criteriaCsv = Join-Path $reportsDir "rotating_shaft_acceptance_safe_$stamp.criteria.csv"
$runDir = Join-Path $reportsDir "rotating_shaft_acceptance_safe_$stamp"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$maxContinuousRunSeconds = 600
$twoAxSafe = Join-Path $repoRoot "tools\run_two_ax7010_end_to_end_acceptance_safe.ps1"
$physicalGateScript = Join-Path $repoRoot "tools\check_physical_matrix_gate.ps1"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown_8lane_candidate.tcl"

foreach ($path in @($twoAxSafe, $physicalGateScript, $shutdownTcl)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
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

function Add-MdLine {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Line
    )
    $Lines.Add($Line)
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
        [int]$TimeoutSecondsForStep
    )

    $outPath = Join-Path $runDir "$Name.out.log"
    $errPath = Join-Path $runDir "$Name.err.log"
    Write-SummaryLine "STEP_START name=$Name out=$outPath err=$errPath"
    Write-SummaryLine "STEP_COMMAND name=$Name $FilePath $($Arguments -join ' ')"
    if ($DryRun) {
        Write-SummaryLine "STEP_DRY_RUN name=$Name"
        return [pscustomobject]@{
            ExitCode = 0
            TimedOut = $false
            Stdout = ""
            Stderr = ""
            OutPath = $outPath
            ErrPath = $errPath
        }
    }

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
        Write-SummaryLine "STEP_RESULT name=$Name exit=124 timeout=1"
        return [pscustomobject]@{
            ExitCode = 124
            TimedOut = $true
            Stdout = if (Test-Path -LiteralPath $outPath) { Get-Content -LiteralPath $outPath -Raw -ErrorAction SilentlyContinue } else { "" }
            Stderr = if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue } else { "" }
            OutPath = $outPath
            ErrPath = $errPath
        }
    }
    $proc.Refresh()
    $exit = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
    Write-SummaryLine "STEP_RESULT name=$Name exit=$exit timeout=0"
    return [pscustomobject]@{
        ExitCode = $exit
        TimedOut = $false
        Stdout = if (Test-Path -LiteralPath $outPath) { Get-Content -LiteralPath $outPath -Raw -ErrorAction SilentlyContinue } else { "" }
        Stderr = if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue } else { "" }
        OutPath = $outPath
        ErrPath = $errPath
    }
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

function Get-FirstNumber {
    param(
        [string]$Text,
        [string[]]$Patterns
    )
    foreach ($pattern in $Patterns) {
        $match = [regex]::Match($Text, $pattern, "IgnoreCase,Multiline")
        if ($match.Success) {
            return [double]$match.Groups[1].Value
        }
    }
    return $null
}

function Test-FixtureLog {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return [pscustomobject]@{
            Provided = $false
            Exists = $false
            DiameterOk = $false
            RpmOk = $false
            DiameterSeen = $null
            RpmSeen = $null
            Note = "fixture_log_not_provided"
        }
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]@{
            Provided = $true
            Exists = $false
            DiameterOk = $false
            RpmOk = $false
            DiameterSeen = $null
            RpmSeen = $null
            Note = "fixture_log_missing"
        }
    }

    $text = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    $diameterSeen = Get-FirstNumber -Text $text -Patterns @(
        "shaft[_ -]?diameter[_ -]?mm\s*[:=,]\s*([0-9]+(?:\.[0-9]+)?)",
        "diameter[_ -]?mm\s*[:=,]\s*([0-9]+(?:\.[0-9]+)?)",
        "diameter\s*[:=,]\s*([0-9]+(?:\.[0-9]+)?)\s*mm"
    )
    $rpmSeen = Get-FirstNumber -Text $text -Patterns @(
        "\brpm\s*[:=,]\s*([0-9]+(?:\.[0-9]+)?)",
        "speed[_ -]?rpm\s*[:=,]\s*([0-9]+(?:\.[0-9]+)?)",
        "rotation[_ -]?rpm\s*[:=,]\s*([0-9]+(?:\.[0-9]+)?)"
    )

    $diameterOk = ($null -ne $diameterSeen -and [Math]::Abs($diameterSeen - $ShaftDiameterMm) -le $ShaftDiameterToleranceMm)
    $rpmOk = ($null -ne $rpmSeen -and [Math]::Abs($rpmSeen - $Rpm) -le $RpmTolerance)
    return [pscustomobject]@{
        Provided = $true
        Exists = $true
        DiameterOk = $diameterOk
        RpmOk = $rpmOk
        DiameterSeen = $diameterSeen
        RpmSeen = $rpmSeen
        Note = if ($diameterOk -and $rpmOk) { "fixture_log_ok" } else { "fixture_log_out_of_range_or_incomplete" }
    }
}

"ROTATING_SHAFT_ACCEPTANCE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "TARGET_HOST_A=$TargetHostA"
Write-SummaryLine "TARGET_HOST_B=$TargetHostB"
Write-SummaryLine "PORT_A=$PortA"
Write-SummaryLine "PORT_B=$PortB"
Write-SummaryLine "REPEAT=$Repeat"
Write-SummaryLine "PAYLOAD_SIZE=$PayloadSize"
Write-SummaryLine "DURATION_SECONDS_REQUESTED=$DurationSeconds"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "RECONNECT_CYCLES=$ReconnectCycles"
Write-SummaryLine "SHAFT_DIAMETER_MM=$ShaftDiameterMm"
Write-SummaryLine "SHAFT_DIAMETER_TOLERANCE_MM=$ShaftDiameterToleranceMm"
Write-SummaryLine "RPM=$Rpm"
Write-SummaryLine "RPM_TOLERANCE=$RpmTolerance"
Write-SummaryLine "FIXTURE_LOG_PATH=$FixtureLogPath"
Write-SummaryLine "ALLOW_TRAFFIC=$([int]$AllowTraffic.IsPresent)"
Write-SummaryLine "PROGRAM_SHUTDOWN_AFTER_RUN=$([int]$ProgramShutdownAfterRun.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "MAX_CONTINUOUS_RUN_SECONDS=$maxContinuousRunSeconds"
Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1"

$willUseRealTraffic = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent)
if ($willUseRealTraffic) {
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS=0"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0"
    Write-SummaryLine "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=1"
} else {
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=0"
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

$diameterTargetOk = ([Math]::Abs($ShaftDiameterMm - 200.0) -le $ShaftDiameterToleranceMm)
$rpmTargetOk = ([Math]::Abs($Rpm - 600.0) -le $RpmTolerance)
Write-SummaryLine "TARGET_DIAMETER_OK=$([int]$diameterTargetOk)"
Write-SummaryLine "TARGET_RPM_OK=$([int]$rpmTargetOk)"

$fixture = Test-FixtureLog -Path $FixtureLogPath
Write-SummaryLine "FIXTURE_LOG_PROVIDED=$([int]$fixture.Provided)"
Write-SummaryLine "FIXTURE_LOG_EXISTS=$([int]$fixture.Exists)"
Write-SummaryLine "FIXTURE_LOG_DIAMETER_SEEN=$($fixture.DiameterSeen)"
Write-SummaryLine "FIXTURE_LOG_RPM_SEEN=$($fixture.RpmSeen)"
Write-SummaryLine "FIXTURE_LOG_DIAMETER_OK=$([int]$fixture.DiameterOk)"
Write-SummaryLine "FIXTURE_LOG_RPM_OK=$([int]$fixture.RpmOk)"
Write-SummaryLine "FIXTURE_LOG_NOTE=$($fixture.Note)"

$blockedReasons = [System.Collections.Generic.List[string]]::new()
if (-not $AllowTraffic) {
    $blockedReasons.Add("allow_traffic_not_set")
}
if ($TargetHostA -eq "") {
    $blockedReasons.Add("target_host_a_missing")
}
if ($TargetHostB -eq "") {
    $blockedReasons.Add("target_host_b_missing")
}
if (-not $diameterTargetOk) {
    $blockedReasons.Add("shaft_diameter_target_out_of_range")
}
if (-not $rpmTargetOk) {
    $blockedReasons.Add("rpm_target_out_of_range")
}
if ($AllowTraffic -and -not $ProgramShutdownAfterRun) {
    $blockedReasons.Add("program_shutdown_after_run_not_set")
}
if ($AllowTraffic -and -not $fixture.Provided) {
    $blockedReasons.Add("fixture_log_required_for_real_acceptance")
}
if ($AllowTraffic -and $fixture.Provided -and -not ($fixture.Exists -and $fixture.DiameterOk -and $fixture.RpmOk)) {
    $blockedReasons.Add("fixture_log_invalid")
}
if ($willUseRealTraffic) {
    $physicalGateExit = Invoke-PhysicalMatrixGate -RequiredLinks @(
        "A_TO_B_LANE0",
        "A_TO_B_LANE1",
        "B_TO_A_LANE0",
        "B_TO_A_LANE1"
    )
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
    Write-SummaryLine "ROTATING_SHAFT_DRY_RUN=1"
    Write-SummaryLine "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=0"
    Write-SummaryLine "ROTATING_SHAFT_ACCEPTANCE_EXIT=0"
    Write-SummaryLine "ROTATING_SHAFT_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

    $csvLines = [System.Collections.Generic.List[string]]::new()
    $csvLines.Add("criterion,status,value,note")
    Add-CsvRow $csvLines @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
    Add-CsvRow $csvLines @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
    Add-CsvRow $csvLines @("dry_run", "PASS", "1", "no hardware traffic was sent")
    [System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLines, [System.Text.Encoding]::ASCII)

    $md = [System.Collections.Generic.List[string]]::new()
    Add-MdLine $md "# Rotating Shaft Acceptance"
    Add-MdLine $md ""
    Add-MdLine $md "Generated: $(Get-Date -Format o)"
    Add-MdLine $md ""
    Add-MdLine $md "Verdict: DRY_RUN_READY_NO_HARDWARE_RUN"
    Add-MdLine $md ""
    Add-MdLine $md "This run did not program hardware, did not write UART, did not send TX_DATA to real boards, and did not drive TFDU boards."
    Add-MdLine $md ""
    Add-MdLine $md "- Requested duration: $DurationSeconds s"
    Add-MdLine $md "- Effective duration: $effectiveDurationSeconds s"
    Add-MdLine $md "- Shaft diameter target: $ShaftDiameterMm mm"
    Add-MdLine $md "- RPM target: $Rpm"
    Add-MdLine $md "- Summary log: $summaryLog"
    Add-MdLine $md "- Criteria CSV: $criteriaCsv"
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)
    exit 0
}

if ($blockedReasons.Count -gt 0) {
    foreach ($reason in $blockedReasons) {
        Write-SummaryLine "ROTATING_SHAFT_BLOCKED_REASON=$reason"
    }
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS_FINAL=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT_FINAL=1"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING_DONE_BY_THIS_SCRIPT_FINAL=1"
    Write-SummaryLine "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=1"
    Write-SummaryLine "ROTATING_SHAFT_ACCEPTANCE_EXIT=20"
    Write-SummaryLine "ROTATING_SHAFT_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

    $csvLines = [System.Collections.Generic.List[string]]::new()
    $csvLines.Add("criterion,status,value,note")
    Add-CsvRow $csvLines @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
    Add-CsvRow $csvLines @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
    Add-CsvRow $csvLines @("real_acceptance", "BLOCKED", ($blockedReasons -join ";"), "preconditions were not met")
    [System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLines, [System.Text.Encoding]::ASCII)

    $md = [System.Collections.Generic.List[string]]::new()
    Add-MdLine $md "# Rotating Shaft Acceptance"
    Add-MdLine $md ""
    Add-MdLine $md "Generated: $(Get-Date -Format o)"
    Add-MdLine $md ""
    Add-MdLine $md "Verdict: BLOCKED"
    Add-MdLine $md ""
    Add-MdLine $md "This run did not program hardware, did not write UART, did not send TX_DATA to real boards, and did not drive TFDU boards."
    Add-MdLine $md ""
    Add-MdLine $md ("Blocked reasons: " + ($blockedReasons -join ","))
    Add-MdLine $md ("Summary log: " + $summaryLog)
    Add-MdLine $md ("Criteria CSV: " + $criteriaCsv)
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)
    exit 20
}

$trafficArgs = @(
    "-TargetHostA", $TargetHostA,
    "-TargetHostB", $TargetHostB,
    "-PortA", [string]$PortA,
    "-PortB", [string]$PortB,
    "-Repeat", [string]$Repeat,
    "-PayloadSize", [string]$PayloadSize,
    "-DurationSeconds", [string]$effectiveDurationSeconds,
    "-TimeoutSeconds", [string]$TimeoutSeconds,
    "-ReconnectCycles", [string]$ReconnectCycles,
    "-TxLaneMaskA", $TxLaneMaskA,
    "-RxLaneMaskA", $RxLaneMaskA,
    "-TxLaneMaskB", $TxLaneMaskB,
    "-RxLaneMaskB", $RxLaneMaskB,
    "-AllowTraffic",
    "-ProgramShutdownAfterRun"
)
$trafficResult = Invoke-LoggedProcess -Name "two_ax7010_real_traffic" -FilePath "powershell.exe" -Arguments (@(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $twoAxSafe
) + $trafficArgs) -TimeoutSecondsForStep ($effectiveDurationSeconds + 180)

$combined = "$($trafficResult.Stdout)`n$($trafficResult.Stderr)"
$trafficPass = ($trafficResult.ExitCode -eq 0 -and $combined -match "TWO_AX7010_REAL_ACCEPTANCE_PASS=1")
$payloadHalfMbps = Get-MaxMetric -Text $combined -MetricName "PAYLOAD_HALF_MBPS"
if ($payloadHalfMbps -le 0.0) {
    $payloadHalfMbps = [Math]::Max(
        (Get-MaxMetric -Text $combined -MetricName "tx_mbps"),
        (Get-MaxMetric -Text $combined -MetricName "rx_mbps")
    )
}
$payloadFdxPerDirMbps = Get-MaxMetric -Text $combined -MetricName "PAYLOAD_FDX_PER_DIR_MBPS"
if ($payloadFdxPerDirMbps -le 0.0) {
    $payloadFdxPerDirMbps = Get-MinPositiveOrZero @(
        (Get-MaxMetric -Text $combined -MetricName "tx_mbps"),
        (Get-MaxMetric -Text $combined -MetricName "rx_mbps")
    )
}

$shutdownResult = Invoke-LoggedProcess -Name "shutdown_after_rotating_run" -FilePath "vivado" -Arguments @(
    "-mode", "batch",
    "-source", $shutdownTcl
) -TimeoutSecondsForStep 180
$shutdownPass = ($shutdownResult.ExitCode -eq 0)
$pass = ($trafficPass -and $shutdownPass -and $fixture.DiameterOk -and $fixture.RpmOk)

Write-SummaryLine "ROTATING_SHAFT_TRAFFIC_PASS=$([int]$trafficPass)"
Write-SummaryLine "ROTATING_SHAFT_SHUTDOWN_AFTER_RUN_PASS=$([int]$shutdownPass)"
Write-RateClaim -PayloadHalfMbps $payloadHalfMbps -PayloadFdxPerDirMbps $payloadFdxPerDirMbps
Write-SummaryLine "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=$([int]$pass)"
Write-SummaryLine "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=0"
$exitCode = if ($pass) { 0 } else { 1 }
Write-SummaryLine "ROTATING_SHAFT_ACCEPTANCE_EXIT=$exitCode"
Write-SummaryLine "ROTATING_SHAFT_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

$csvLinesReal = [System.Collections.Generic.List[string]]::new()
$csvLinesReal.Add("criterion,status,value,note")
Add-CsvRow $csvLinesReal @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
Add-CsvRow $csvLinesReal @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
Add-CsvRow $csvLinesReal @("fixture_log", $(if ($fixture.DiameterOk -and $fixture.RpmOk) { "PASS" } else { "FAIL" }), "$($fixture.DiameterSeen)mm,$($fixture.RpmSeen)rpm", $fixture.Note)
Add-CsvRow $csvLinesReal @("two_ax7010_traffic", $(if ($trafficPass) { "PASS" } else { "FAIL" }), [string]$trafficResult.ExitCode, "real traffic wrapper result")
Add-CsvRow $csvLinesReal @("raw_payload_rate_separation", "PASS", "raw_half=32.0,raw_fdx_per_dir=16.0,rate_claim=raw_phy_only", "raw PHY target and effective payload throughput are reported separately")
Add-CsvRow $csvLinesReal @("payload_throughput_reported", $(if ($trafficPass) { "PASS" } else { "FAIL" }), ("payload_half={0},payload_fdx_per_dir={1}" -f (Format-Rate $payloadHalfMbps), (Format-Rate $payloadFdxPerDirMbps)), "payload throughput is reported from the nested two-AX7010 traffic wrapper")
Add-CsvRow $csvLinesReal @("shutdown_after_run", $(if ($shutdownPass) { "PASS" } else { "FAIL" }), [string]$shutdownResult.ExitCode, "shutdown bitstream programmed after TFDU/TX run")
[System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLinesReal, [System.Text.Encoding]::ASCII)

$mdOut = [System.Collections.Generic.List[string]]::new()
Add-MdLine $mdOut "# Rotating Shaft Acceptance"
Add-MdLine $mdOut ""
Add-MdLine $mdOut "Generated: $(Get-Date -Format o)"
Add-MdLine $mdOut ""
if ($pass) {
    Add-MdLine $mdOut "Verdict: PASS_REAL_ROTATING_SHAFT_ACCEPTANCE"
} else {
    Add-MdLine $mdOut "Verdict: FAIL_REAL_ROTATING_SHAFT_ACCEPTANCE"
}
Add-MdLine $mdOut ""
Add-MdLine $mdOut "- Traffic pass: $trafficPass"
Add-MdLine $mdOut "- Fixture log pass: $($fixture.DiameterOk -and $fixture.RpmOk)"
Add-MdLine $mdOut "- Shutdown after run pass: $shutdownPass"
Add-MdLine $mdOut "- Summary log: $summaryLog"
Add-MdLine $mdOut "- Criteria CSV: $criteriaCsv"
Add-MdLine $mdOut "- Run directory: $runDir"
[System.IO.File]::WriteAllLines($mdReport, [string[]]$mdOut, [System.Text.Encoding]::UTF8)

exit $exitCode
