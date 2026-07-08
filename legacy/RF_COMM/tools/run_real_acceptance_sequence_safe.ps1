[CmdletBinding()]
param(
    [ValidateSet("preflight", "n03", "n04", "product_loop", "rotating_shaft", "eight_lane", "all")]
    [string]$Stage = "preflight",
    [string]$TargetHost = "192.168.10.2",
    [string]$TargetHostA = "192.168.10.2",
    [string]$TargetHostB = "192.168.10.3",
    [int]$Port = 5001,
    [int]$PortA = 5001,
    [int]$PortB = 5001,
    [int]$Repeat = 32,
    [int]$PayloadSize = 256,
    [int]$DurationSeconds = 600,
    [double]$TimeoutSeconds = 5.0,
    [int]$ReconnectCycles = 4,
    [string]$FixtureLogPath = "",
    [string]$TxLaneMaskA = "0x0f",
    [string]$RxLaneMaskA = "0xf0",
    [string]$TxLaneMaskB = "0xf0",
    [string]$RxLaneMaskB = "0x0f",
    [ValidateSet("full_8lane_stream_bidir", "a_only_external_8lane", "reduced_4lane_external", "reduced_8lane_frag16_external")]
    [string]$EightLaneProfile = "reduced_8lane_frag16_external",
    [switch]$AllowTraffic,
    [switch]$AllowUartProbe,
    [switch]$ProgramShutdownBeforeRun,
    [switch]$ProgramShutdownAfterRun,
    [switch]$PinmapReviewed,
    [switch]$ShutdownBitstreamReviewed,
    [switch]$DryRun,
    [switch]$SkipPreflightBlock
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "real_acceptance_sequence_safe_$stamp.summary.txt"
$mdReport = Join-Path $reportsDir "real_acceptance_sequence_safe_$stamp.md"
$csvReport = Join-Path $reportsDir "real_acceptance_sequence_safe_$stamp.stages.csv"
$jsonReport = Join-Path $reportsDir "real_acceptance_sequence_safe_$stamp.json"
$currentSummary = Join-Path $reportsDir "real_acceptance_sequence_safe_current.summary.txt"
$currentMd = Join-Path $reportsDir "real_acceptance_sequence_safe_current.md"
$currentCsv = Join-Path $reportsDir "real_acceptance_sequence_safe_current.stages.csv"
$currentJson = Join-Path $reportsDir "real_acceptance_sequence_safe_current.json"
$runDir = Join-Path $reportsDir "real_acceptance_sequence_safe_$stamp"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$preflightScript = Join-Path $repoRoot "tools\check_external_preconditions.py"
$runbookScript = Join-Path $repoRoot "tools\build_real_acceptance_runbook.py"
$readinessScript = Join-Path $repoRoot "tools\check_remaining_acceptance_readiness.py"
$wrapperPsPc = Join-Path $repoRoot "tools\run_ps_pc_tcp_dhcp_acceptance_safe.ps1"
$wrapperTwoAx = Join-Path $repoRoot "tools\run_two_ax7010_end_to_end_acceptance_safe.ps1"
$wrapperProduct = Join-Path $repoRoot "tools\run_product_loop_acceptance_safe.ps1"
$wrapperRotating = Join-Path $repoRoot "tools\run_rotating_shaft_acceptance_safe.ps1"
$wrapperEight = Join-Path $repoRoot "tools\run_8lane_hardware_acceptance_safe.ps1"

foreach ($path in @($preflightScript, $runbookScript, $readinessScript, $wrapperPsPc, $wrapperTwoAx, $wrapperProduct, $wrapperRotating, $wrapperEight)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

$maxContinuousRunSeconds = 600
$effectiveDurationSeconds = [Math]::Min([Math]::Max($DurationSeconds, 0), $maxContinuousRunSeconds)

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

function Add-MdLine {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Line
    )
    $Lines.Add($Line)
}

function Invoke-PythonTool {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    Write-SummaryLine "STEP_START name=$Name"
    Write-SummaryLine "STEP_COMMAND name=$Name python $($Arguments -join ' ')"
    $output = & python @Arguments 2>&1
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    foreach ($line in $output) {
        Write-SummaryLine "STEP_OUTPUT name=$Name $line"
    }
    Write-SummaryLine "STEP_RESULT name=$Name exit=$exitCode"
    return [pscustomobject]@{ ExitCode = $exitCode; Output = ($output -join "`n") }
}

function Invoke-Wrapper {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    $logPath = Join-Path $runDir "$Name.log"
    Write-SummaryLine "WRAPPER_START name=$Name log=$logPath"
    Write-SummaryLine "WRAPPER_COMMAND name=$Name powershell.exe $($Arguments -join ' ')"
    if ($DryRun) {
        Write-SummaryLine "WRAPPER_DRY_RUN name=$Name"
        return [pscustomobject]@{ ExitCode = 0; LogPath = $logPath; Ran = $false }
    }

    $output = & powershell.exe @Arguments 2>&1
    $output | Out-File -LiteralPath $logPath -Encoding utf8
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    foreach ($line in ($output | Select-Object -Last 80)) {
        Write-SummaryLine "WRAPPER_OUTPUT name=$Name $line"
    }
    Write-SummaryLine "WRAPPER_RESULT name=$Name exit=$exitCode"
    return [pscustomobject]@{ ExitCode = $exitCode; LogPath = $logPath; Ran = $true }
}

function New-StagePlan {
    param([string]$StageId)

    if ($StageId -eq "n03") {
        $args = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $wrapperPsPc,
            "-TargetHost", $TargetHost,
            "-Port", [string]$Port,
            "-ComPort", "COM3",
            "-UartProbeSeconds", "20",
            "-ReconnectCycles", [string]$ReconnectCycles,
            "-TimeoutSeconds", [string]$TimeoutSeconds,
            "-UseStaticFallback"
        )
        if (-not $AllowUartProbe) {
            $args += "-SkipUartProbe"
        }
        return [pscustomobject]@{
            Id = "N03"
            Name = "ps_pc_tcp_dhcp"
            DrivesTfdu = $false
            ProgramsHardware = $false
            RequiresTrafficSwitch = $false
            Args = $args
        }
    }

    if ($StageId -eq "n04") {
        $args = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $wrapperTwoAx,
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
            "-RxLaneMaskB", $RxLaneMaskB
        )
        if ($AllowTraffic) { $args += "-AllowTraffic" }
        if ($ProgramShutdownAfterRun) { $args += "-ProgramShutdownAfterRun" }
        return [pscustomobject]@{
            Id = "N04"
            Name = "two_ax7010"
            DrivesTfdu = $true
            ProgramsHardware = $ProgramShutdownAfterRun.IsPresent
            RequiresTrafficSwitch = $true
            Args = $args
        }
    }

    if ($StageId -eq "product_loop") {
        $args = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $wrapperProduct,
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
            "-RxLaneMaskB", $RxLaneMaskB
        )
        if ($AllowTraffic) { $args += "-AllowTraffic" }
        if ($ProgramShutdownAfterRun) { $args += "-ProgramShutdownAfterRun" }
        return [pscustomobject]@{
            Id = "A01"
            Name = "product_loop"
            DrivesTfdu = $true
            ProgramsHardware = $ProgramShutdownAfterRun.IsPresent
            RequiresTrafficSwitch = $true
            Args = $args
        }
    }

    if ($StageId -eq "rotating_shaft") {
        $args = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $wrapperRotating,
            "-TargetHostA", $TargetHostA,
            "-TargetHostB", $TargetHostB,
            "-PortA", [string]$PortA,
            "-PortB", [string]$PortB,
            "-Repeat", [string]$Repeat,
            "-PayloadSize", [string]$PayloadSize,
            "-DurationSeconds", [string]$effectiveDurationSeconds,
            "-TimeoutSeconds", [string]$TimeoutSeconds,
            "-ReconnectCycles", [string]$ReconnectCycles,
            "-ShaftDiameterMm", "200",
            "-Rpm", "600",
            "-TxLaneMaskA", $TxLaneMaskA,
            "-RxLaneMaskA", $RxLaneMaskA,
            "-TxLaneMaskB", $TxLaneMaskB,
            "-RxLaneMaskB", $RxLaneMaskB
        )
        if (-not [string]::IsNullOrWhiteSpace($FixtureLogPath)) {
            $args += @("-FixtureLogPath", $FixtureLogPath)
        }
        if ($AllowTraffic) { $args += "-AllowTraffic" }
        if ($ProgramShutdownAfterRun) { $args += "-ProgramShutdownAfterRun" }
        return [pscustomobject]@{
            Id = "S05"
            Name = "rotating_shaft"
            DrivesTfdu = $true
            ProgramsHardware = $ProgramShutdownAfterRun.IsPresent
            RequiresTrafficSwitch = $true
            Args = $args
        }
    }

    if ($StageId -eq "eight_lane") {
        $args = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $wrapperEight,
            "-Profile", $EightLaneProfile,
            "-LaneCount", "8",
            "-TargetHostA", $TargetHostA,
            "-TargetHostB", $TargetHostB,
            "-PortA", [string]$PortA,
            "-PortB", [string]$PortB,
            "-Repeat", [string]$Repeat,
            "-PayloadSize", [string]$PayloadSize,
            "-DurationSeconds", [string]$effectiveDurationSeconds,
            "-TimeoutSeconds", [string]$TimeoutSeconds,
            "-ReconnectCycles", [string]$ReconnectCycles,
            "-TxLaneMaskA", "0xff",
            "-RxLaneMaskA", "0xff",
            "-TxLaneMaskB", "0xff",
            "-RxLaneMaskB", "0xff"
        )
        if ($AllowTraffic) { $args += "-AllowTraffic" }
        if ($PinmapReviewed) { $args += "-PinmapReviewed" }
        if ($ShutdownBitstreamReviewed) { $args += "-ShutdownBitstreamReviewed" }
        if ($ProgramShutdownBeforeRun) { $args += "-ProgramShutdownBeforeRun" }
        if ($ProgramShutdownAfterRun) { $args += "-ProgramShutdownAfterRun" }
        return [pscustomobject]@{
            Id = "A02"
            Name = "eight_lane"
            DrivesTfdu = $true
            ProgramsHardware = ($ProgramShutdownBeforeRun.IsPresent -or $ProgramShutdownAfterRun.IsPresent)
            RequiresTrafficSwitch = $true
            Args = $args
        }
    }

    throw "Unknown stage id: $StageId"
}

"REAL_ACCEPTANCE_SEQUENCE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "STAGE=$Stage"
Write-SummaryLine "TARGET_HOST=$TargetHost"
Write-SummaryLine "TARGET_HOST_A=$TargetHostA"
Write-SummaryLine "TARGET_HOST_B=$TargetHostB"
Write-SummaryLine "PORT=$Port"
Write-SummaryLine "PORT_A=$PortA"
Write-SummaryLine "PORT_B=$PortB"
Write-SummaryLine "DURATION_SECONDS_REQUESTED=$DurationSeconds"
Write-SummaryLine "DURATION_SECONDS_EFFECTIVE=$effectiveDurationSeconds"
Write-SummaryLine "MAX_CONTINUOUS_RUN_SECONDS=$maxContinuousRunSeconds"
Write-SummaryLine "ALLOW_TRAFFIC=$([int]$AllowTraffic.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "SKIP_PREFLIGHT_BLOCK=$([int]$SkipPreflightBlock.IsPresent)"

$preflightResult = Invoke-PythonTool -Name "external_preconditions" -Arguments @(
    $preflightScript,
    "--target-host", $TargetHost,
    "--target-host-a", $TargetHostA,
    "--target-host-b", $TargetHostB,
    "--tcp-port", [string]$Port,
    "--timeout", "0.5"
)
$runbookResult = Invoke-PythonTool -Name "real_acceptance_runbook" -Arguments @($runbookScript)
$readinessResult = Invoke-PythonTool -Name "remaining_acceptance_readiness" -Arguments @($readinessScript)

$preflightJsonPath = Join-Path $reportsDir "external_preconditions_current.json"
$preflight = Get-Content -LiteralPath $preflightJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$preflightOverall = [string]$preflight.overall
$preflightBlockers = @($preflight.blockers)
$blockDuePreflight = ($preflightBlockers.Count -gt 0 -and -not $SkipPreflightBlock.IsPresent)

$readinessJsonPath = Join-Path $reportsDir "remaining_acceptance_readiness_current.json"
$readiness = Get-Content -LiteralPath $readinessJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$readinessOverall = [string]$readiness.overall
$readinessItems = @($readiness.items)
$readinessBlockerNotes = @(
    foreach ($item in $readinessItems) {
        $itemId = [string]$item.item_id
        $blockers = [string]$item.blockers
        if (-not [string]::IsNullOrWhiteSpace($blockers)) {
            "$itemId=$blockers"
        }
    }
)

$stageIds = if ($Stage -eq "all") {
    @("n03", "n04", "product_loop", "rotating_shaft", "eight_lane")
} elseif ($Stage -eq "preflight") {
    @()
} else {
    @($Stage)
}
$stageIds = @($stageIds)

$stageRows = [System.Collections.Generic.List[string]]::new()
Add-CsvRow $stageRows @("id", "name", "planned", "executed", "blocked", "exit_code", "log", "note", "command")

$stageResults = @()
$executedWrappers = 0
$failedWrappers = 0
$tfduDriveRequested = $false
$hardwareProgrammingRequested = $false

foreach ($stageId in $stageIds) {
    $plan = New-StagePlan -StageId $stageId
    $commandText = "powershell.exe " + ($plan.Args -join " ")
    $blockedReason = ""
    if ($blockDuePreflight) {
        $blockedReason = "preflight_blockers=" + ($preflightBlockers -join ";")
    } elseif ($plan.RequiresTrafficSwitch -and -not $AllowTraffic.IsPresent -and -not $DryRun.IsPresent) {
        $blockedReason = "traffic_switch_required"
    }

    if ($blockedReason) {
        Write-SummaryLine "STAGE_BLOCKED id=$($plan.Id) reason=$blockedReason"
        Add-CsvRow $stageRows @($plan.Id, $plan.Name, "1", "0", "1", "", "", $blockedReason, $commandText)
        $stageResults += [pscustomobject]@{
            id = $plan.Id
            name = $plan.Name
            planned = $true
            executed = $false
            blocked = $true
            exit_code = $null
            log = ""
            note = $blockedReason
            command = $commandText
        }
        continue
    }

    if ($plan.DrivesTfdu -and $AllowTraffic.IsPresent -and -not $DryRun.IsPresent) {
        $tfduDriveRequested = $true
    }
    if ($plan.ProgramsHardware -and -not $DryRun.IsPresent) {
        $hardwareProgrammingRequested = $true
    }

    $result = Invoke-Wrapper -Name $plan.Name -Arguments $plan.Args
    $executedWrappers += [int]$result.Ran
    if ($result.ExitCode -ne 0) {
        $failedWrappers += 1
    }
    Add-CsvRow $stageRows @($plan.Id, $plan.Name, "1", [string][int]$result.Ran, "0", [string]$result.ExitCode, [string]$result.LogPath, "wrapper_invoked", $commandText)
    $stageResults += [pscustomobject]@{
        id = $plan.Id
        name = $plan.Name
        planned = $true
        executed = [bool]$result.Ran
        blocked = $false
        exit_code = $result.ExitCode
        log = [string]$result.LogPath
        note = "wrapper_invoked"
        command = $commandText
    }
}

if ($stageIds.Count -eq 0) {
    Add-CsvRow $stageRows @(
        "PREFLIGHT",
        "external_preconditions_and_runbook",
        "1",
        "1",
        "0",
        "0",
        "",
        "no real wrapper selected",
        "python tools/check_external_preconditions.py; python tools/build_real_acceptance_runbook.py"
    )
}

if ($preflightResult.ExitCode -ne 0 -or $runbookResult.ExitCode -ne 0 -or $readinessResult.ExitCode -ne 0) {
    $overall = "FAIL_PREFLIGHT_TOOL"
} elseif ($blockDuePreflight) {
    if ($preflightBlockers -contains "ethernet_link") {
        $overall = "BLOCKED_NO_ETHERNET"
    } else {
        $overall = "BLOCKED_EXTERNAL_PRECONDITIONS"
    }
} elseif ($Stage -eq "preflight") {
    $overall = "PREFLIGHT_READY"
} elseif ($DryRun.IsPresent) {
    $overall = "DRY_RUN_READY_NO_HARDWARE_RUN"
} elseif ($failedWrappers -gt 0) {
    $overall = "FAIL_STAGE_WRAPPER"
} elseif ($executedWrappers -gt 0) {
    $overall = "REAL_SEQUENCE_COMPLETED_REVIEW_REQUIRED"
} else {
    $overall = "BLOCKED_NOT_EXECUTED"
}

$noHardwareProgramming = if ($hardwareProgrammingRequested) { 0 } else { 1 }
$noUartWrite = if ($AllowUartProbe.IsPresent -and -not $DryRun.IsPresent -and -not $blockDuePreflight) { 0 } else { 1 }
$noTfduDrive = if ($tfduDriveRequested) { 0 } else { 1 }

Write-SummaryLine "PREFLIGHT_OVERALL=$preflightOverall"
Write-SummaryLine "PREFLIGHT_BLOCKERS=$($preflightBlockers -join ',')"
Write-SummaryLine "REMAINING_READINESS_OVERALL=$readinessOverall"
Write-SummaryLine "REMAINING_READINESS_ITEMS=$($readinessItems.Count)"
Write-SummaryLine "REMAINING_READINESS_BLOCKERS=$($readinessBlockerNotes -join ',')"
Write-SummaryLine "EXECUTED_WRAPPERS=$executedWrappers"
Write-SummaryLine "FAILED_WRAPPERS=$failedWrappers"
Write-SummaryLine "NO_HARDWARE_PROGRAMMING=$noHardwareProgramming"
Write-SummaryLine "NO_UART_WRITE=$noUartWrite"
Write-SummaryLine "NO_TFDU_DRIVE=$noTfduDrive"
Write-SummaryLine "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=$overall stages=$($stageIds.Count)"

$stageRows | Set-Content -LiteralPath $csvReport -Encoding utf8

$md = [System.Collections.Generic.List[string]]::new()
Add-MdLine $md "# Real Acceptance Sequence Safe Entry"
Add-MdLine $md ""
Add-MdLine $md "Generated: $(Get-Date -Format o)"
Add-MdLine $md ""
Add-MdLine $md "## Verdict"
Add-MdLine $md ""
Add-MdLine $md ("- Overall: ``{0}``" -f $overall)
Add-MdLine $md ("- Requested stage: ``{0}``" -f $Stage)
Add-MdLine $md ("- External preflight: ``{0}``" -f $preflightOverall)
Add-MdLine $md ("- Preflight blockers: ``{0}``" -f ($preflightBlockers -join ', '))
Add-MdLine $md ("- Remaining readiness gate: ``{0}``" -f $readinessOverall)
Add-MdLine $md ("- Remaining readiness blockers: ``{0}``" -f ($readinessBlockerNotes -join ', '))
Add-MdLine $md ("- Duration cap: ``{0} / {1} s``" -f $effectiveDurationSeconds, $maxContinuousRunSeconds)
Add-MdLine $md ("- No hardware programming: ``{0}``" -f $noHardwareProgramming)
Add-MdLine $md ("- No UART write: ``{0}``" -f $noUartWrite)
Add-MdLine $md ("- No TFDU drive: ``{0}``" -f $noTfduDrive)
Add-MdLine $md ""
Add-MdLine $md "This wrapper is the safe top-level entry for future real acceptance. With the current no-Ethernet condition it stops after preflight/runbook/readiness generation and does not run hardware traffic wrappers."
Add-MdLine $md ""
Add-MdLine $md "## Stages"
Add-MdLine $md ""
Add-MdLine $md "| id | name | planned | executed | blocked | exit_code | note |"
Add-MdLine $md "| --- | --- | --- | --- | --- | --- | --- |"
foreach ($result in $stageResults) {
    Add-MdLine $md "| $($result.id) | $($result.name) | $([int]$result.planned) | $([int]$result.executed) | $([int]$result.blocked) | $($result.exit_code) | $($result.note) |"
}
if ($stageResults.Count -eq 0) {
    Add-MdLine $md "| PREFLIGHT | external_preconditions_and_runbook | 1 | 1 | 0 | 0 | no real wrapper selected |"
}
Add-MdLine $md ""
Add-MdLine $md '```text'
Add-MdLine $md "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=$overall stages=$($stageIds.Count)"
Add-MdLine $md "NO_HARDWARE_PROGRAMMING=$noHardwareProgramming"
Add-MdLine $md "NO_UART_WRITE=$noUartWrite"
Add-MdLine $md "NO_TFDU_DRIVE=$noTfduDrive"
Add-MdLine $md '```'
$md | Set-Content -LiteralPath $mdReport -Encoding utf8

$payload = [pscustomobject]@{
    generated = (Get-Date -Format o)
    overall = $overall
    requested_stage = $Stage
    preflight_overall = $preflightOverall
    preflight_blockers = $preflightBlockers
    remaining_readiness_overall = $readinessOverall
    remaining_readiness_blockers = $readinessBlockerNotes
    effective_duration_seconds = $effectiveDurationSeconds
    max_continuous_run_seconds = $maxContinuousRunSeconds
    allow_traffic = $AllowTraffic.IsPresent
    dry_run = $DryRun.IsPresent
    skip_preflight_block = $SkipPreflightBlock.IsPresent
    no_hardware_programming = [bool]$noHardwareProgramming
    no_uart_write = [bool]$noUartWrite
    no_tfdu_drive = [bool]$noTfduDrive
    reports = [pscustomobject]@{
        summary = $summaryLog
        markdown = $mdReport
        csv = $csvReport
        run_dir = $runDir
    }
    stages = $stageResults
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonReport -Encoding utf8

Copy-Item -LiteralPath $summaryLog -Destination $currentSummary -Force
Copy-Item -LiteralPath $mdReport -Destination $currentMd -Force
Copy-Item -LiteralPath $csvReport -Destination $currentCsv -Force
Copy-Item -LiteralPath $jsonReport -Destination $currentJson -Force

Write-Host "WROTE_SUMMARY=$summaryLog"
Write-Host "WROTE_MARKDOWN=$mdReport"
Write-Host "WROTE_CSV=$csvReport"
Write-Host "WROTE_JSON=$jsonReport"
Write-Host "WROTE_CURRENT_SUMMARY=$currentSummary"
Write-Host "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=$overall stages=$($stageIds.Count)"
Write-Host "NO_HARDWARE_PROGRAMMING=$noHardwareProgramming"
Write-Host "NO_UART_WRITE=$noUartWrite"
Write-Host "NO_TFDU_DRIVE=$noTfduDrive"

if ($overall -eq "FAIL_PREFLIGHT_TOOL" -or $overall -eq "FAIL_STAGE_WRAPPER") {
    exit 1
}
exit 0
