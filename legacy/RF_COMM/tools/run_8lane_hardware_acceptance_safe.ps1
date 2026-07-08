[CmdletBinding()]
param(
    [ValidateSet("full_8lane_stream_bidir", "a_only_external_8lane", "reduced_4lane_external", "reduced_8lane_frag16_external")]
    [string]$Profile = "full_8lane_stream_bidir",
    [ValidateRange(1, 8)]
    [int]$LaneCount = 8,
    [string]$TargetHostA = "",
    [string]$TargetHostB = "",
    [int]$PortA = 5001,
    [int]$PortB = 5001,
    [int]$Repeat = 32,
    [int]$PayloadSize = 256,
    [int]$DurationSeconds = 600,
    [double]$TimeoutSeconds = 5.0,
    [int]$ReconnectCycles = 4,
    [string]$TxLaneMaskA = "0xff",
    [string]$RxLaneMaskA = "0xff",
    [string]$TxLaneMaskB = "0xff",
    [string]$RxLaneMaskB = "0xff",
    [switch]$PinmapReviewed,
    [switch]$ShutdownBitstreamReviewed,
    [switch]$AllowTraffic,
    [switch]$ProgramShutdownBeforeRun,
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
$summaryLog = Join-Path $reportsDir "8lane_hardware_acceptance_safe_$stamp.summary.txt"
$mdReport = Join-Path $reportsDir "8lane_hardware_acceptance_safe_$stamp.md"
$criteriaCsv = Join-Path $reportsDir "8lane_hardware_acceptance_safe_$stamp.criteria.csv"
$runDir = Join-Path $reportsDir "8lane_hardware_acceptance_safe_$stamp"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$maxContinuousRunSeconds = 600
$readinessJson = Join-Path $repoRoot "reports\8lane_hardware_readiness_current.json"
$productLoopSafe = Join-Path $repoRoot "tools\run_product_loop_acceptance_safe.ps1"
$physicalGateScript = Join-Path $repoRoot "tools\check_physical_matrix_gate.ps1"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown_8lane_candidate.tcl"

foreach ($path in @($readinessJson, $productLoopSafe, $physicalGateScript, $shutdownTcl)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding UTF8
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

function Get-JsonValue {
    param(
        [object]$Object,
        [string]$Name
    )
    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) {
        return $null
    }
    return $prop.Value
}

function Get-JsonArrayCount {
    param(
        [object]$Object,
        [string]$Name
    )
    $value = Get-JsonValue -Object $Object -Name $Name
    if ($null -eq $value) {
        return 0
    }
    return @($value).Count
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

"EIGHT_LANE_HARDWARE_ACCEPTANCE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding UTF8
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "PROFILE=$Profile"
Write-SummaryLine "LANE_COUNT_REQUESTED=$LaneCount"
Write-SummaryLine "TARGET_HOST_A=$TargetHostA"
Write-SummaryLine "TARGET_HOST_B=$TargetHostB"
Write-SummaryLine "PORT_A=$PortA"
Write-SummaryLine "PORT_B=$PortB"
Write-SummaryLine "REPEAT=$Repeat"
Write-SummaryLine "PAYLOAD_SIZE=$PayloadSize"
Write-SummaryLine "DURATION_SECONDS_REQUESTED=$DurationSeconds"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "RECONNECT_CYCLES=$ReconnectCycles"
Write-SummaryLine "TX_LANE_MASK_A=$TxLaneMaskA"
Write-SummaryLine "RX_LANE_MASK_A=$RxLaneMaskA"
Write-SummaryLine "TX_LANE_MASK_B=$TxLaneMaskB"
Write-SummaryLine "RX_LANE_MASK_B=$RxLaneMaskB"
Write-SummaryLine "PINMAP_REVIEWED=$([int]$PinmapReviewed.IsPresent)"
Write-SummaryLine "SHUTDOWN_BITSTREAM_REVIEWED=$([int]$ShutdownBitstreamReviewed.IsPresent)"
Write-SummaryLine "ALLOW_TRAFFIC=$([int]$AllowTraffic.IsPresent)"
Write-SummaryLine "PROGRAM_SHUTDOWN_BEFORE_RUN=$([int]$ProgramShutdownBeforeRun.IsPresent)"
Write-SummaryLine "PROGRAM_SHUTDOWN_AFTER_RUN=$([int]$ProgramShutdownAfterRun.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "MAX_CONTINUOUS_RUN_SECONDS=$maxContinuousRunSeconds"
Write-SummaryLine "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1"

$willUseRealTraffic = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent)
if ($willUseRealTraffic) {
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS=0"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0"
    Write-SummaryLine "SHUTDOWN_REQUIRED_BEFORE_THIS_RUN=1"
    Write-SummaryLine "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=1"
} else {
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "SHUTDOWN_REQUIRED_BEFORE_THIS_RUN=0"
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

$readiness = Get-Content -LiteralPath $readinessJson -Raw | ConvertFrom-Json
$activeALanes = Get-JsonArrayCount -Object $readiness -Name "a_endpoint_complete_lanes"
$activeBLanes = Get-JsonArrayCount -Object $readiness -Name "b_internal_complete_lanes"
$candidateALanes = Get-JsonArrayCount -Object $readiness -Name "candidate_a_endpoint_complete_lanes"
$candidateBLanes = Get-JsonArrayCount -Object $readiness -Name "candidate_b_internal_complete_lanes"
$aOnlyCandidateALanes = Get-JsonArrayCount -Object $readiness -Name "a_only_candidate_a_endpoint_complete_lanes"
$candidateResourceBlocked = [bool](Get-JsonValue -Object $readiness -Name "candidate_project_synth_pass_resource_blocked")
$externalResourceBlocked = [bool](Get-JsonValue -Object $readiness -Name "external_project_synth_pass_resource_blocked")
$candidateShutdownReady = [bool](Get-JsonValue -Object $readiness -Name "candidate_shutdown_bitstream_ready_for_review")
$reduced4BitstreamOk = [bool](Get-JsonValue -Object $readiness -Name "external_reduced_4lane_bitstream_ok")
$reduced8Frag16BitstreamOk = [bool](Get-JsonValue -Object $readiness -Name "external_reduced_8lane_frag16_bitstream_ok")
$reduced8Frag16RawHalf = Get-JsonValue -Object $readiness -Name "external_reduced_8lane_frag16_bitstream_raw_half_mbps"
$reduced8Frag16RawFdx = Get-JsonValue -Object $readiness -Name "external_reduced_8lane_frag16_bitstream_raw_fdx_per_dir_mbps"
$reduced8Frag16Sha = Get-JsonValue -Object $readiness -Name "external_reduced_8lane_frag16_bitstream_sha256"

Write-SummaryLine "ACTIVE_A_LANE_COUNT=$activeALanes"
Write-SummaryLine "ACTIVE_B_LANE_COUNT=$activeBLanes"
Write-SummaryLine "CANDIDATE_A_LANE_COUNT=$candidateALanes"
Write-SummaryLine "CANDIDATE_B_LANE_COUNT=$candidateBLanes"
Write-SummaryLine "A_ONLY_CANDIDATE_A_LANE_COUNT=$aOnlyCandidateALanes"
Write-SummaryLine "CANDIDATE_PROJECT_RESOURCE_BLOCKED=$([int]$candidateResourceBlocked)"
Write-SummaryLine "A_ONLY_EXTERNAL_PROJECT_RESOURCE_BLOCKED=$([int]$externalResourceBlocked)"
Write-SummaryLine "CANDIDATE_SHUTDOWN_BITSTREAM_READY_FOR_REVIEW=$([int]$candidateShutdownReady)"
Write-SummaryLine "REDUCED_4LANE_BITSTREAM_READY_FOR_REVIEW=$([int]$reduced4BitstreamOk)"
Write-SummaryLine "REDUCED_8LANE_FRAG16_BITSTREAM_READY_FOR_REVIEW=$([int]$reduced8Frag16BitstreamOk)"
Write-SummaryLine "REDUCED_8LANE_FRAG16_RAW_HALF_MBPS=$reduced8Frag16RawHalf"
Write-SummaryLine "REDUCED_8LANE_FRAG16_RAW_FDX_PER_DIR_MBPS=$reduced8Frag16RawFdx"
Write-SummaryLine "REDUCED_8LANE_FRAG16_BITSTREAM_SHA256=$reduced8Frag16Sha"

$blockedReasons = [System.Collections.Generic.List[string]]::new()
if (-not $AllowTraffic) {
    $blockedReasons.Add("allow_traffic_not_set")
}
if (-not $PinmapReviewed) {
    $blockedReasons.Add("pinmap_not_reviewed")
}
if (-not $ShutdownBitstreamReviewed) {
    $blockedReasons.Add("shutdown_bitstream_not_reviewed")
}
if ($AllowTraffic -and -not $ProgramShutdownBeforeRun) {
    $blockedReasons.Add("program_shutdown_before_run_not_set")
}
if ($AllowTraffic -and -not $ProgramShutdownAfterRun) {
    $blockedReasons.Add("program_shutdown_after_run_not_set")
}
if ($LaneCount -lt 8) {
    $blockedReasons.Add("lane_count_less_than_8_for_a02")
}
if ($Profile -eq "full_8lane_stream_bidir" -and $candidateResourceBlocked) {
    $blockedReasons.Add("full_8lane_stream_bidir_resource_blocked")
}
if ($Profile -eq "a_only_external_8lane" -and $externalResourceBlocked) {
    $blockedReasons.Add("a_only_external_8lane_resource_blocked")
}
if ($Profile -eq "reduced_4lane_external") {
    $blockedReasons.Add("reduced_4lane_profile_not_full_8lane_hardware_acceptance")
    if (-not $reduced4BitstreamOk) {
        $blockedReasons.Add("reduced_4lane_bitstream_not_ready")
    }
}
if ($Profile -eq "reduced_8lane_frag16_external") {
    if (-not $reduced8Frag16BitstreamOk) {
        $blockedReasons.Add("reduced_8lane_frag16_bitstream_not_ready")
    }
    if ($aOnlyCandidateALanes -lt 8) {
        $blockedReasons.Add("a_only_candidate_8lane_pinmap_incomplete")
    }
}
if (-not $candidateShutdownReady) {
    $blockedReasons.Add("candidate_shutdown_bitstream_not_ready")
}
if ($Profile -eq "full_8lane_stream_bidir" -and ($candidateALanes -lt 8 -or $candidateBLanes -lt 8)) {
    $blockedReasons.Add("candidate_8lane_pinmap_incomplete")
}
if ($Profile -eq "a_only_external_8lane" -and $aOnlyCandidateALanes -lt 8) {
    $blockedReasons.Add("a_only_candidate_8lane_pinmap_incomplete")
}
if ($TargetHostA -eq "") {
    $blockedReasons.Add("target_host_a_missing")
}
if ($TargetHostB -eq "") {
    $blockedReasons.Add("target_host_b_missing")
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
    foreach ($reason in $blockedReasons) {
        Write-SummaryLine "EIGHT_LANE_HARDWARE_DRY_RUN_BLOCKED_REASON_PREVIEW=$reason"
    }
    Write-SummaryLine "EIGHT_LANE_HARDWARE_DRY_RUN=1"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=0"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_EXIT=0"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

    $csvLines = [System.Collections.Generic.List[string]]::new()
    $csvLines.Add("criterion,status,value,note")
    Add-CsvRow $csvLines @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
    Add-CsvRow $csvLines @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
    Add-CsvRow $csvLines @("dry_run", "PASS", "1", "no 8-lane hardware traffic was sent")
    Add-CsvRow $csvLines @("candidate_pinmap", $(if ($candidateALanes -eq 8 -and $candidateBLanes -eq 8) { "PASS_REVIEW_REQUIRED" } else { "BLOCKED" }), "$candidateALanes/$candidateBLanes", "candidate A/B lane coverage")
    Add-CsvRow $csvLines @("resource_fit", $(if ($candidateResourceBlocked -or $externalResourceBlocked) { "BLOCKED" } else { "PASS" }), "full=$candidateResourceBlocked,a_only=$externalResourceBlocked", "XC7Z010 build feasibility")
    Add-CsvRow $csvLines @("reduced_8lane_frag16_raw_profile", $(if ($reduced8Frag16BitstreamOk) { "PASS_REVIEW_REQUIRED" } else { "MISSING" }), "raw_half=$reduced8Frag16RawHalf,raw_fdx_per_dir=$reduced8Frag16RawFdx", "offline bitstream candidate for final raw 32/16 lane capacity")
    [System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLines, [System.Text.Encoding]::ASCII)

    $md = [System.Collections.Generic.List[string]]::new()
    Add-MdLine $md "# 8-Lane Hardware Acceptance"
    Add-MdLine $md ""
    Add-MdLine $md "Generated: $(Get-Date -Format o)"
    Add-MdLine $md ""
    Add-MdLine $md "Verdict: DRY_RUN_READY_NO_HARDWARE_RUN"
    Add-MdLine $md ""
    Add-MdLine $md "This run did not program hardware, did not write UART, did not send TX_DATA to real boards, and did not drive TFDU boards."
    Add-MdLine $md ""
    Add-MdLine $md "- Profile: $Profile"
    Add-MdLine $md "- Requested lane count: $LaneCount"
    Add-MdLine $md "- Requested duration: $DurationSeconds s"
    Add-MdLine $md "- Effective duration: $effectiveDurationSeconds s"
    Add-MdLine $md "- Candidate A/B coverage: $candidateALanes/8, $candidateBLanes/8"
    Add-MdLine $md "- Full 8-lane resource blocked: $candidateResourceBlocked"
    Add-MdLine $md "- A-only external 8-lane resource blocked: $externalResourceBlocked"
    Add-MdLine $md "- Reduced 8-lane fragment=16 bitstream ready: $reduced8Frag16BitstreamOk"
    Add-MdLine $md "- Reduced 8-lane fragment=16 raw capacity: half=$reduced8Frag16RawHalf Mbit/s, fdx/dir=$reduced8Frag16RawFdx Mbit/s"
    Add-MdLine $md "- Reduced 8-lane fragment=16 SHA256: $reduced8Frag16Sha"
    Add-MdLine $md "- Summary log: $summaryLog"
    Add-MdLine $md "- Criteria CSV: $criteriaCsv"
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)
    exit 0
}

if ($blockedReasons.Count -gt 0) {
    foreach ($reason in $blockedReasons) {
        Write-SummaryLine "EIGHT_LANE_HARDWARE_BLOCKED_REASON=$reason"
    }
    Write-SummaryLine "NO_TX_DATA_TO_REAL_BOARDS_FINAL=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT_FINAL=1"
    Write-SummaryLine "NO_HARDWARE_PROGRAMMING_DONE_BY_THIS_SCRIPT_FINAL=1"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=1"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_EXIT=20"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

    $csvLinesBlocked = [System.Collections.Generic.List[string]]::new()
    $csvLinesBlocked.Add("criterion,status,value,note")
    Add-CsvRow $csvLinesBlocked @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
    Add-CsvRow $csvLinesBlocked @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
    Add-CsvRow $csvLinesBlocked @("real_acceptance", "BLOCKED", ($blockedReasons -join ";"), "preconditions were not met")
    [System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLinesBlocked, [System.Text.Encoding]::ASCII)

    $mdBlocked = [System.Collections.Generic.List[string]]::new()
    Add-MdLine $mdBlocked "# 8-Lane Hardware Acceptance"
    Add-MdLine $mdBlocked ""
    Add-MdLine $mdBlocked "Generated: $(Get-Date -Format o)"
    Add-MdLine $mdBlocked ""
    Add-MdLine $mdBlocked "Verdict: BLOCKED"
    Add-MdLine $mdBlocked ""
    Add-MdLine $mdBlocked "This run did not program hardware, did not write UART, did not send TX_DATA to real boards, and did not drive TFDU boards."
    Add-MdLine $mdBlocked ""
    Add-MdLine $mdBlocked ("Blocked reasons: " + ($blockedReasons -join ","))
    Add-MdLine $mdBlocked ("Summary log: " + $summaryLog)
    Add-MdLine $mdBlocked ("Criteria CSV: " + $criteriaCsv)
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$mdBlocked, [System.Text.Encoding]::UTF8)
    exit 20
}

$shutdownBefore = Invoke-LoggedProcess -Name "shutdown_before_8lane_run" -FilePath "vivado" -Arguments @(
    "-mode", "batch",
    "-source", $shutdownTcl
) -TimeoutSecondsForStep 180
$shutdownBeforePass = ($shutdownBefore.ExitCode -eq 0)
if (-not $shutdownBeforePass) {
    Write-SummaryLine "EIGHT_LANE_HARDWARE_SHUTDOWN_BEFORE_RUN_PASS=0"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=0"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=0"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_EXIT=1"
    Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"
    exit 1
}

$trafficResult = Invoke-LoggedProcess -Name "eight_lane_product_loop_traffic" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $productLoopSafe,
    "-Topology", "two_ax7010",
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
) -TimeoutSecondsForStep ($effectiveDurationSeconds + 240)
$combined = "$($trafficResult.Stdout)`n$($trafficResult.Stderr)"
$trafficPass = ($trafficResult.ExitCode -eq 0 -and $combined -match "PRODUCT_LOOP_REAL_ACCEPTANCE_PASS=1")
$shutdownAfterPass = ($combined -match "PRODUCT_LOOP_SHUTDOWN_AFTER_RUN_PASS=1")
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
$pass = ($shutdownBeforePass -and $trafficPass -and $shutdownAfterPass)

Write-SummaryLine "EIGHT_LANE_HARDWARE_SHUTDOWN_BEFORE_RUN_PASS=$([int]$shutdownBeforePass)"
Write-SummaryLine "EIGHT_LANE_HARDWARE_TRAFFIC_PASS=$([int]$trafficPass)"
Write-SummaryLine "EIGHT_LANE_HARDWARE_SHUTDOWN_AFTER_RUN_PASS=$([int]$shutdownAfterPass)"
Write-RateClaim -PayloadHalfMbps $payloadHalfMbps -PayloadFdxPerDirMbps $payloadFdxPerDirMbps
Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=$([int]$pass)"
Write-SummaryLine "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=0"
$exitCode = if ($pass) { 0 } else { 1 }
Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_EXIT=$exitCode"
Write-SummaryLine "EIGHT_LANE_HARDWARE_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

$csvLinesReal = [System.Collections.Generic.List[string]]::new()
$csvLinesReal.Add("criterion,status,value,note")
Add-CsvRow $csvLinesReal @("constraint", $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }), $constraintHash, "hard target file unchanged")
Add-CsvRow $csvLinesReal @("duration_cap", "PASS", [string]$effectiveDurationSeconds, "continuous runtime capped to 600 s")
Add-CsvRow $csvLinesReal @("shutdown_before_run", $(if ($shutdownBeforePass) { "PASS" } else { "FAIL" }), [string]$shutdownBefore.ExitCode, "shutdown bitstream programmed before TFDU/TX run")
Add-CsvRow $csvLinesReal @("product_loop_traffic", $(if ($trafficPass) { "PASS" } else { "FAIL" }), [string]$trafficResult.ExitCode, "real 8-lane traffic wrapper result")
Add-CsvRow $csvLinesReal @("raw_payload_rate_separation", "PASS", "raw_half=32.0,raw_fdx_per_dir=16.0,rate_claim=raw_phy_only", "raw PHY target and effective payload throughput are reported separately")
Add-CsvRow $csvLinesReal @("payload_throughput_reported", $(if ($trafficPass) { "PASS" } else { "FAIL" }), ("payload_half={0},payload_fdx_per_dir={1}" -f (Format-Rate $payloadHalfMbps), (Format-Rate $payloadFdxPerDirMbps)), "payload throughput is reported from the nested product-loop traffic wrapper")
Add-CsvRow $csvLinesReal @("shutdown_after_run", $(if ($shutdownAfterPass) { "PASS" } else { "FAIL" }), [string]$trafficResult.ExitCode, "nested product-loop wrapper shutdown result")
[System.IO.File]::WriteAllLines($criteriaCsv, [string[]]$csvLinesReal, [System.Text.Encoding]::ASCII)

$mdOut = [System.Collections.Generic.List[string]]::new()
Add-MdLine $mdOut "# 8-Lane Hardware Acceptance"
Add-MdLine $mdOut ""
Add-MdLine $mdOut "Generated: $(Get-Date -Format o)"
Add-MdLine $mdOut ""
if ($pass) {
    Add-MdLine $mdOut "Verdict: PASS_REAL_8LANE_HARDWARE_ACCEPTANCE"
} else {
    Add-MdLine $mdOut "Verdict: FAIL_REAL_8LANE_HARDWARE_ACCEPTANCE"
}
Add-MdLine $mdOut ""
Add-MdLine $mdOut "- Profile: $Profile"
Add-MdLine $mdOut "- Shutdown before run pass: $shutdownBeforePass"
Add-MdLine $mdOut "- Traffic pass: $trafficPass"
Add-MdLine $mdOut "- Shutdown after run pass: $shutdownAfterPass"
Add-MdLine $mdOut "- Summary log: $summaryLog"
Add-MdLine $mdOut "- Criteria CSV: $criteriaCsv"
Add-MdLine $mdOut "- Run directory: $runDir"
[System.IO.File]::WriteAllLines($mdReport, [string[]]$mdOut, [System.Text.Encoding]::UTF8)

exit $exitCode
