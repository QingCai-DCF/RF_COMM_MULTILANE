param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(0, 7)]
    [int]$Lane,
    [ValidateSet("both", "a2b_rx", "b2a_rx", "a2b_ack")]
    [string]$Variant = "both",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$Jobs = 16,
    [switch]$Apply,
    [switch]$BuildOnly,
    [switch]$SkipFullBdGenerate,
    [switch]$SkipRun,
    [switch]$SkipVitisBuild,
    [switch]$SkipPreflight,
    [switch]$NoRestore,
    [switch]$KeepGeneratedXdc
)

$ErrorActionPreference = "Stop"

$effectiveVariant = if ($Variant -eq "a2b_ack") { "a2b_rx" } else { $Variant }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.summary.txt"
$manifestPath = Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.manifest.json"
$generatedXdc = Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.PORT1.xdc"
$backupDir = Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.backup"
$backupXdc = Join-Path $backupDir "PORT1.xdc"

$port1Xdc = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.srcs\constrs_1\new\PORT1.xdc"
$buildScript = Join-Path $repoRoot "tools\build_g0_lane0_artifacts.ps1"
$runScript = Join-Path $repoRoot "tools\run_lane0_hw_once_safe.ps1"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$bitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$bdPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.srcs\sources_1\bd\design_shiboqi\design_shiboqi.bd"

$probePorts = @(
    "ir_mode_out_0",
    "ir_rx_in_0",
    "ir_sd_0",
    "ir_tx_out_0",
    "loop_mode_b0",
    "loop_rx_b0",
    "loop_sd_b0",
    "loop_tx_b0"
)

$endpointSwapPortPairs = @(
    @("ir_mode_out_0", "loop_mode_b0"),
    @("ir_rx_in_0", "loop_rx_b0"),
    @("ir_sd_0", "loop_sd_b0"),
    @("ir_tx_out_0", "loop_tx_b0")
)

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Get-FileHashOrEmpty {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    }
    return ""
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [int]$TimeoutSeconds
    )

    function ConvertTo-CmdArg {
        param([string]$Value)
        if ($Value -match '[\s&()^|<>"]') {
            return '"' + ($Value -replace '"', '""') + '"'
        }
        return $Value
    }

    $argLine = ($Arguments | ForEach-Object { ConvertTo-CmdArg $_ }) -join " "
    $cmdLine = '"' + $FilePath + '" ' + $argLine + ' > "' + $LogPath + '" 2> "' + $LogPath + '.err"'
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "cmd.exe"
    $psi.Arguments = '/d /s /c "' + $cmdLine + '"'
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    try {
        $proc.WaitForExit()
    } catch {
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 125
    }
    return $proc.ExitCode
}

function Parse-XdcPinMap {
    param([string[]]$Lines)
    $map = @{}
    foreach ($line in $Lines) {
        $match = [regex]::Match($line, "^\s*set_property\s+PACKAGE_PIN\s+(\S+)\s+\[get_ports\s+\{([A-Za-z0-9_]+)\[(\d+)\]\}\]")
        if (-not $match.Success) {
            continue
        }
        $port = $match.Groups[2].Value
        $idx = [int]$match.Groups[3].Value
        if (-not $map.ContainsKey($port)) {
            $map[$port] = @{}
        }
        $map[$port][$idx] = $match.Groups[1].Value
    }
    return $map
}

function Convert-PinMapForJson {
    param($Map)
    $outer = [ordered]@{}
    foreach ($port in ($Map.Keys | Sort-Object)) {
        $inner = [ordered]@{}
        foreach ($idx in ($Map[$port].Keys | Sort-Object)) {
            $inner[[string]$idx] = $Map[$port][$idx]
        }
        $outer[$port] = $inner
    }
    return $outer
}

function New-RemappedLines {
    param(
        [string[]]$Lines,
        $PinMap,
        [int]$RequestedLane,
        [ValidateSet("normal", "endpoint_swap")]
        [string]$MappingMode = "normal"
    )

    $remapped = @{}
    foreach ($port in $probePorts) {
        if (-not $PinMap.ContainsKey($port)) {
            throw "Missing probe port in XDC: $port"
        }
        if (-not $PinMap[$port].ContainsKey(0)) {
            throw "Missing logical lane0 pin for port $port"
        }
        if (-not $PinMap[$port].ContainsKey($RequestedLane)) {
            throw "Requested lane $RequestedLane is not mapped for port $port"
        }
        $remapped[$port] = @{}
        foreach ($idx in $PinMap[$port].Keys) {
            $remapped[$port][$idx] = $PinMap[$port][$idx]
        }
    }

    if ($MappingMode -eq "endpoint_swap") {
        foreach ($pair in $endpointSwapPortPairs) {
            $aPort = $pair[0]
            $bPort = $pair[1]
            foreach ($port in @($aPort, $bPort)) {
                if (-not $PinMap[$port].ContainsKey(0)) {
                    throw "Missing logical lane0 pin for port $port"
                }
                if (-not $PinMap[$port].ContainsKey($RequestedLane)) {
                    throw "Requested lane $RequestedLane is not mapped for port $port"
                }
            }

            $oldA0 = $PinMap[$aPort][0]
            $oldALane = $PinMap[$aPort][$RequestedLane]
            $oldB0 = $PinMap[$bPort][0]
            $oldBLane = $PinMap[$bPort][$RequestedLane]

            if ($RequestedLane -eq 0) {
                $remapped[$aPort][0] = $oldB0
                $remapped[$bPort][0] = $oldA0
            } else {
                $remapped[$aPort][0] = $oldBLane
                $remapped[$bPort][0] = $oldALane
                $remapped[$aPort][$RequestedLane] = $oldB0
                $remapped[$bPort][$RequestedLane] = $oldA0
            }
        }
    } else {
        foreach ($port in $probePorts) {
            $oldLane0 = $PinMap[$port][0]
            $oldRequested = $PinMap[$port][$RequestedLane]
            $remapped[$port][0] = $oldRequested
            $remapped[$port][$RequestedLane] = $oldLane0
        }
    }

    $newLines = foreach ($line in $Lines) {
        $match = [regex]::Match($line, "^(\s*set_property\s+PACKAGE_PIN\s+)(\S+)(\s+\[get_ports\s+\{([A-Za-z0-9_]+)\[(\d+)\]\}\].*)$")
        if ($match.Success) {
            $port = $match.Groups[4].Value
            $idx = [int]$match.Groups[5].Value
            if ($remapped.ContainsKey($port) -and $remapped[$port].ContainsKey($idx)) {
                "{0}{1}{2}" -f $match.Groups[1].Value, $remapped[$port][$idx], $match.Groups[3].Value
                continue
            }
        }
        $line
    }

    return @{
        Lines = @($newLines)
        Remapped = $remapped
    }
}

function Get-PhaseProfileVariant {
    param([string]$Phase)
    if ($Phase -eq "a2b_rx") {
        return "b2a_rx"
    }
    return $Phase
}

function Get-PhaseMappingMode {
    param([string]$Phase)
    if ($Phase -eq "a2b_rx") {
        return "endpoint_swap"
    }
    return "normal"
}

function Get-StageFieldInt {
    param(
        $Fields,
        [string]$Name
    )
    if ($Fields.ContainsKey($Name)) {
        $value = $Fields[$Name] -replace "%$", ""
        $parsed = 0
        if ([int]::TryParse($value, [ref]$parsed)) {
            return $parsed
        }
    }
    return 0
}

function Get-RunLogVerdict {
    param(
        [string]$RunLog,
        [string]$Phase
    )

    if (-not (Test-Path -LiteralPath $RunLog)) {
        return [ordered]@{
            verdict = "INDETERMINATE_LOG_MISSING"
            reason = "run_log_missing"
            evidence = ""
        }
    }

    $runText = [string](Get-Content -LiteralPath $RunLog -Raw -ErrorAction SilentlyContinue)
    $shutdownOk = ($runText -match "(?m)^SHUTDOWN_EXIT=0\b" -or $runText -match "TFDU_SHUTDOWN_PROGRAMMED")
    $summaryLines = ($runText -split "`r?`n") | Where-Object {
        $_ -match "PSPS_B_RX_ONLY_SUMMARY|PSPS_RX_ONLY_SUMMARY|PSPS_STAGE_SUMMARY"
    }
    if (-not $summaryLines -or $summaryLines.Count -eq 0) {
        return [ordered]@{
            verdict = "INDETERMINATE_NO_STAGE_SUMMARY"
            reason = "no_receiver_summary"
            evidence = ""
        }
    }

    $failReasons = New-Object System.Collections.Generic.List[string]
    $passEvidence = ""
    $lastEvidence = [string]($summaryLines | Select-Object -Last 1)
    $sawRequiredSummary = $false

    foreach ($line in $summaryLines) {
        if ($Phase -eq "a2b_rx") {
            if ($line -notmatch "PSPS_B_RX_ONLY_SUMMARY") {
                continue
            }
            $sawRequiredSummary = $true
        } elseif ($Phase -eq "b2a_rx") {
            if ($line -notmatch "PSPS_RX_ONLY_SUMMARY") {
                continue
            }
            $sawRequiredSummary = $true
        }

        $fields = @{}
        foreach ($match in [regex]::Matches($line, "([A-Za-z0-9_]+)=([^\s]+)")) {
            $fields[$match.Groups[1].Value] = $match.Groups[2].Value
        }

        $sent = Get-StageFieldInt -Fields $fields -Name "sent"
        $rxOk = Get-StageFieldInt -Fields $fields -Name "rx_ok"
        $txFail = Get-StageFieldInt -Fields $fields -Name "tx_fail"
        $rxTimeout = Get-StageFieldInt -Fields $fields -Name "rx_timeout"
        $rxBad = Get-StageFieldInt -Fields $fields -Name "rx_bad"
        $rxMismatch = Get-StageFieldInt -Fields $fields -Name "rx_mismatch"
        $lastError = if ($fields.ContainsKey("last_error")) { $fields["last_error"] } else { "none" }
        $loss = if ($fields.ContainsKey("loss")) { $fields["loss"] } else { "" }

        if ($Phase -eq "a2b_rx") {
            $summaryValid = if ($fields.ContainsKey("b_summary_valid")) { $fields["b_summary_valid"] } else { "0" }
            if ($summaryValid -ne "1") {
                $failReasons.Add("b_summary_valid=$summaryValid") | Out-Null
            }
            if (-not $fields.ContainsKey("b_rx_good_count")) {
                $failReasons.Add("b_rx_good_count_missing") | Out-Null
            } else {
                $bRxGoodCount = Get-StageFieldInt -Fields $fields -Name "b_rx_good_count"
                if ($bRxGoodCount -le 0) {
                    $failReasons.Add("b_rx_good_count=$bRxGoodCount") | Out-Null
                }
            }
            if (-not $fields.ContainsKey("b_rx_bad_seen")) {
                $failReasons.Add("b_rx_bad_seen_missing") | Out-Null
            } else {
                $bRxBadSeen = Get-StageFieldInt -Fields $fields -Name "b_rx_bad_seen"
                if ($bRxBadSeen -ne 0) {
                    $failReasons.Add("b_rx_bad_seen=$bRxBadSeen") | Out-Null
                }
            }
            if (-not $fields.ContainsKey("b_rx_error")) {
                $failReasons.Add("b_rx_error_missing") | Out-Null
            } else {
                $bRxError = Get-StageFieldInt -Fields $fields -Name "b_rx_error"
                if ($bRxError -ne 0) {
                    $failReasons.Add("b_rx_error=$bRxError") | Out-Null
                }
            }
            if (-not $fields.ContainsKey("b_tx_start")) {
                $failReasons.Add("b_tx_start_missing") | Out-Null
            } else {
                $bTxStart = Get-StageFieldInt -Fields $fields -Name "b_tx_start"
                if ($bTxStart -gt 0) {
                    $failReasons.Add("b_tx_start=$bTxStart") | Out-Null
                }
            }
            if (-not $fields.ContainsKey("b_tx_activity")) {
                $failReasons.Add("b_tx_activity_missing") | Out-Null
            } else {
                $bTxActivity = Get-StageFieldInt -Fields $fields -Name "b_tx_activity"
                if ($bTxActivity -gt 0) {
                    $failReasons.Add("b_tx_activity=$bTxActivity") | Out-Null
                }
            }
            $payloadMatch = if ($fields.ContainsKey("payload_match")) { $fields["payload_match"] } else { "" }
            if ($payloadMatch -ne "fixed_a_pattern") {
                $failReasons.Add("payload_match=$payloadMatch") | Out-Null
            }
        }

        if ($sent -le 0 -and $Phase -eq "a2b_rx") {
            $failReasons.Add("sent=0") | Out-Null
        }
        if ($txFail -gt 0) {
            $failReasons.Add("tx_fail=$txFail") | Out-Null
        }
        if ($rxTimeout -gt 0) {
            $failReasons.Add("rx_timeout=$rxTimeout") | Out-Null
        }
        if ($rxBad -gt 0) {
            $failReasons.Add("rx_bad=$rxBad") | Out-Null
        }
        if ($rxMismatch -gt 0) {
            $failReasons.Add("rx_mismatch=$rxMismatch") | Out-Null
        }
        if ($lastError -and $lastError -ne "none") {
            $failReasons.Add("last_error=$lastError") | Out-Null
        }
        if ($loss -match "^100(\.0+)?%$") {
            $failReasons.Add("loss=$loss") | Out-Null
        }

        if ($rxOk -gt 0 -and $txFail -eq 0 -and $rxTimeout -eq 0 -and $rxBad -eq 0 -and $rxMismatch -eq 0 -and $lastError -eq "none") {
            $passEvidence = [string]$line
        }
    }

    if (-not $sawRequiredSummary) {
        $missingReason = if ($Phase -eq "a2b_rx") { "missing_psps_b_rx_only_summary" } else { "missing_psps_rx_only_summary" }
        return [ordered]@{
            verdict = "INDETERMINATE_NO_REQUIRED_RX_ONLY_SUMMARY"
            reason = $missingReason
            evidence = $lastEvidence
        }
    }

    if (-not $passEvidence -and $failReasons.Count -eq 0) {
        $failReasons.Add("rx_only_summary_without_pass_condition") | Out-Null
    }

    if ($passEvidence -and $failReasons.Count -eq 0 -and -not $shutdownOk) {
        return [ordered]@{
            verdict = "INDETERMINATE_SHUTDOWN_NOT_CONFIRMED"
            reason = "shutdown_exit_zero_missing"
            evidence = $passEvidence
        }
    }
    if ($passEvidence -and $failReasons.Count -eq 0) {
        return [ordered]@{
            verdict = "PASS_LOG_COUNTERS"
            reason = "clean_receiver_rx_only_summary"
            evidence = $passEvidence
        }
    }
    if ($failReasons.Count -gt 0) {
        return [ordered]@{
            verdict = "FAIL_LOG_COUNTERS"
            reason = (($failReasons | Select-Object -Unique) -join ";")
            evidence = $lastEvidence
        }
    }
    return [ordered]@{
        verdict = "INDETERMINATE_NO_PASS_COUNTERS"
        reason = "stage_summary_without_pass_condition"
        evidence = $lastEvidence
    }
}

function Write-Manifest {
    param(
        [string]$Path,
        [string]$Status,
        $OriginalPinMap,
        $RemappedPinMap,
        [array]$PhaseResults
    )

    $manifest = [ordered]@{
        schema = "rf_comm_lane_remap_probe_manifest_v1"
        status = $Status
        generated_at = (Get-Date).ToString("o")
        repo_root = $repoRoot
        requested_physical_lane = $Lane
        logical_probe_lane = 0
        requested_variant = $Variant
        variant = $effectiveVariant
        active_xdc = $port1Xdc
        generated_xdc = $generatedXdc
        backup_xdc = $backupXdc
        apply = [bool]$Apply.IsPresent
        build_only = [bool]$BuildOnly.IsPresent
        skip_full_bd_generate = [bool]$SkipFullBdGenerate.IsPresent
        skip_run = [bool]$SkipRun.IsPresent
        no_restore = [bool]$NoRestore.IsPresent
        original_pin_map = Convert-PinMapForJson -Map $OriginalPinMap
        remapped_pin_map = if ($null -ne $RemappedPinMap) { Convert-PinMapForJson -Map $RemappedPinMap } else { $null }
        bit_before_sha256 = $script:bitBeforeHash
        elf_before_sha256 = $script:elfBeforeHash
        bd_before_sha256 = $script:bdBeforeHash
        bit_after_sha256 = Get-FileHashOrEmpty -Path $bitPath
        elf_after_sha256 = Get-FileHashOrEmpty -Path $elfPath
        bd_after_sha256 = Get-FileHashOrEmpty -Path $bdPath
        xdc_before_sha256 = $script:xdcBeforeHash
        xdc_after_sha256 = Get-FileHashOrEmpty -Path $port1Xdc
        restore_performed = $script:restorePerformed
        restore_xdc_match = $script:restoreXdcMatch
        phase_results = $PhaseResults
    }
    $manifest | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $Path -Encoding ascii
}

"LANE_REMAP_PROBE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "REQUESTED_PHYSICAL_LANE=$Lane"
Write-SummaryLine "LOGICAL_PROBE_LANE=0"
Write-SummaryLine "REQUESTED_VARIANT=$Variant"
Write-SummaryLine "VARIANT=$effectiveVariant"
if ($Variant -ne $effectiveVariant) {
    Write-SummaryLine "VARIANT_ALIAS_MAPPED=$Variant->$effectiveVariant"
}
Write-SummaryLine "APPLY=$([int]$Apply.IsPresent)"
Write-SummaryLine "BUILD_ONLY=$([int]$BuildOnly.IsPresent)"
Write-SummaryLine "SKIP_FULL_BD_GENERATE=$([int]$SkipFullBdGenerate.IsPresent)"
Write-SummaryLine "SKIP_RUN=$([int]$SkipRun.IsPresent)"
Write-SummaryLine "SKIP_VITIS_BUILD=$([int]$SkipVitisBuild.IsPresent)"
Write-SummaryLine "SKIP_PREFLIGHT=$([int]$SkipPreflight.IsPresent)"
Write-SummaryLine "NO_RESTORE=$([int]$NoRestore.IsPresent)"
Write-SummaryLine "ACTIVE_XDC=$port1Xdc"
Write-SummaryLine "GENERATED_XDC=$generatedXdc"
Write-SummaryLine "MANIFEST=$manifestPath"
Write-SummaryLine "BD_PATH=$bdPath"

foreach ($path in @($port1Xdc, $buildScript, $runScript, $preflightScript, $VivadoPath, $XsctPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        Write-SummaryLine "REQUIRED_PATH_MISSING=$path"
        Write-SummaryLine "LANE_REMAP_PROBE_RESULT=INDETERMINATE_CONFIG_MISSING"
        Write-SummaryLine "LANE_REMAP_PROBE_END $(Get-Date -Format o)"
        exit 22
    }
}

$script:bitBeforeHash = Get-FileHashOrEmpty -Path $bitPath
$script:elfBeforeHash = Get-FileHashOrEmpty -Path $elfPath
$script:bdBeforeHash = Get-FileHashOrEmpty -Path $bdPath
$script:xdcBeforeHash = Get-FileHashOrEmpty -Path $port1Xdc
Write-SummaryLine "BIT_BEFORE_SHA256=$script:bitBeforeHash"
Write-SummaryLine "ELF_BEFORE_SHA256=$script:elfBeforeHash"
Write-SummaryLine "BD_BEFORE_SHA256=$script:bdBeforeHash"
Write-SummaryLine "XDC_BEFORE_SHA256=$script:xdcBeforeHash"
$script:restorePerformed = $false
$script:restoreXdcMatch = $false
$phaseResults = @()
$variantsToRun = @()
if ($effectiveVariant -eq "both") {
    $variantsToRun += "a2b_rx"
    $variantsToRun += "b2a_rx"
} else {
    $variantsToRun += $effectiveVariant
}
Write-SummaryLine "PLANNED_PHASES=$(($variantsToRun) -join ',')"

$lines = Get-Content -LiteralPath $port1Xdc -Encoding UTF8
$pinMap = Parse-XdcPinMap -Lines $lines

$phaseRemaps = @{}
try {
    for ($i = 0; $i -lt $variantsToRun.Count; $i++) {
        $phase = $variantsToRun[$i]
        $mappingMode = Get-PhaseMappingMode -Phase $phase
        $profileVariant = Get-PhaseProfileVariant -Phase $phase
        $phaseGeneratedXdc = if ($variantsToRun.Count -eq 1) {
            $generatedXdc
        } else {
            Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.${phase}.PORT1.xdc"
        }
        $remapResult = New-RemappedLines -Lines $lines -PinMap $pinMap -RequestedLane $Lane -MappingMode $mappingMode
        $remapResult.Lines | Out-File -LiteralPath $phaseGeneratedXdc -Encoding ascii
        $phaseRemaps[$phase] = [ordered]@{
            mapping_mode = $mappingMode
            profile_variant = $profileVariant
            generated_xdc = $phaseGeneratedXdc
            remapped = $remapResult.Remapped
        }
        Write-SummaryLine "PHASE_MAPPING_MODE variant=$phase mode=$mappingMode"
        Write-SummaryLine "PHASE_PROFILE_VARIANT variant=$phase profile=$profileVariant"
        Write-SummaryLine "PHASE_GENERATED_XDC variant=$phase path=$phaseGeneratedXdc"
        foreach ($port in $probePorts) {
            Write-SummaryLine ("PHASE_MAPPING variant={0} {1}[0] <= physical_lane_{2} pin={3}" -f $phase, $port, $Lane, $remapResult.Remapped[$port][0])
        }
    }
} catch {
    Write-SummaryLine "LANE_REMAP_CONFIG_ERROR=$($_.Exception.Message)"
    Write-SummaryLine "LANE_REMAP_PROBE_RESULT=INDETERMINATE_CONFIG_MISSING"
    Write-Manifest -Path $manifestPath -Status "INDETERMINATE_CONFIG_MISSING" -OriginalPinMap $pinMap -RemappedPinMap $null -PhaseResults $phaseResults
    Write-SummaryLine "LANE_REMAP_PROBE_END $(Get-Date -Format o)"
    exit 22
}

$remappedPinMap = $phaseRemaps[$variantsToRun[0]]["remapped"]

Write-Manifest -Path $manifestPath -Status "PLANNED" -OriginalPinMap $pinMap -RemappedPinMap $remappedPinMap -PhaseResults $phaseResults

if (-not $Apply.IsPresent) {
    Write-SummaryLine "DRY_RUN_NO_XDC_REPLACED=1"
    Write-SummaryLine "DRY_RUN_NO_BUILD_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "LANE_REMAP_PROBE_RESULT=DRY_RUN_READY"
    Write-Manifest -Path $manifestPath -Status "DRY_RUN_READY" -OriginalPinMap $pinMap -RemappedPinMap $remappedPinMap -PhaseResults $phaseResults
    Write-SummaryLine "LANE_REMAP_PROBE_END $(Get-Date -Format o)"
    exit 0
}

if (-not $SkipPreflight.IsPresent) {
    $preflightLog = Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.preflight.log"
    $preflightExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $preflightScript,
        "-VivadoPath",
        $VivadoPath,
        "-ComPort",
        $ComPort,
        "-HwServerUrl",
        $HwServerUrl,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz
    ) -LogPath $preflightLog -TimeoutSeconds 180
    Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
    Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
    $preflightText = ""
    if (Test-Path -LiteralPath $preflightLog) {
        $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
        foreach ($line in (($preflightText -split "`r?`n") | Where-Object { $_ -match "COM_PORT_PRESENT|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT" })) {
            Write-SummaryLine "PREFLIGHT_MATCH=$line"
        }
    }
    $preflightPass = ($preflightText -match "HW_PREFLIGHT_RESULT PASS" -and $preflightText -match "HW_PREFLIGHT_ZYNQ")
    Write-SummaryLine "PREFLIGHT_PASS_PARSED=$([int]$preflightPass)"
    if (-not $preflightPass) {
        Write-SummaryLine "PREFLIGHT_BLOCKED_NO_BUILD_OR_PROGRAMMING=1"
        Write-SummaryLine "LANE_REMAP_PROBE_RESULT=INDETERMINATE_PREFLIGHT_FAIL"
        Write-Manifest -Path $manifestPath -Status "INDETERMINATE_PREFLIGHT_FAIL" -OriginalPinMap $pinMap -RemappedPinMap $remappedPinMap -PhaseResults $phaseResults
        Write-SummaryLine "LANE_REMAP_PROBE_END $(Get-Date -Format o)"
        exit 20
    }
}

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
Copy-Item -LiteralPath $port1Xdc -Destination $backupXdc -Force

$overallExit = 0
try {
    foreach ($phase in $variantsToRun) {
        $phaseProfileVariant = $phaseRemaps[$phase]["profile_variant"]
        $phaseMappingMode = $phaseRemaps[$phase]["mapping_mode"]
        $phaseGeneratedXdc = $phaseRemaps[$phase]["generated_xdc"]
        Copy-Item -LiteralPath $phaseGeneratedXdc -Destination $port1Xdc -Force
        Write-SummaryLine "PHASE_ACTIVE_XDC_REPLACED variant=$phase path=$phaseGeneratedXdc"
        Write-SummaryLine "PHASE_ACTIVE_XDC_SHA256 variant=$phase sha256=$((Get-FileHash -Algorithm SHA256 -LiteralPath $port1Xdc).Hash)"
        $phaseResult = [ordered]@{
            variant = $phase
            profile_variant = $phaseProfileVariant
            mapping_mode = $phaseMappingMode
            generated_xdc = $phaseGeneratedXdc
            remapped_pin_map = Convert-PinMapForJson -Map $phaseRemaps[$phase]["remapped"]
            build_log = $null
            build_exit = $null
            run_log = $null
            run_exit = $null
            log_verdict = $null
            log_reason = $null
            log_evidence = $null
            status = "PENDING"
        }
        Write-SummaryLine "PHASE_START variant=$phase time=$(Get-Date -Format o)"
        Write-SummaryLine "PHASE_PROFILE_VARIANT_ACTIVE variant=$phase profile=$phaseProfileVariant"
        Write-SummaryLine "PHASE_MAPPING_MODE_ACTIVE variant=$phase mode=$phaseMappingMode"
        $buildLog = Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.${phase}.build.log"
        $buildArgs = @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $buildScript,
            "-VivadoPath",
            $VivadoPath,
            "-XsctPath",
            $XsctPath,
            "-Variant",
            $phaseProfileVariant,
            "-Jobs",
            [string]$Jobs
        )
        if (-not $SkipFullBdGenerate.IsPresent) {
            $buildArgs += "-FullBdGenerate"
        }
        if ($SkipVitisBuild.IsPresent) {
            $buildArgs += "-SkipVitisBuild"
        }
        $buildExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $buildArgs -LogPath $buildLog -TimeoutSeconds 9000
        $phaseResult.build_log = $buildLog
        $phaseResult.build_exit = $buildExit
        Write-SummaryLine "PHASE_BUILD_LOG variant=$phase log=$buildLog"
        Write-SummaryLine "PHASE_BUILD_EXIT variant=$phase exit=$buildExit"
        if (Test-Path -LiteralPath $buildLog) {
            foreach ($line in (Get-Content -LiteralPath $buildLog -ErrorAction SilentlyContinue | Where-Object {
                $_ -match "G0_LANE0_BUILD_DONE|BITSTREAM_EXIT|VITIS_EXIT|ARTIFACT .*sha256|ARTIFACT_SKIPPED|ARTIFACT_OPTIONAL|ILA_|BUILD_ENV PSPS_|BUILD_ENV IR_CNT_CHIP_MAX|BUILD_ENV IR_CNT_PREAMBLE|BUILD_ENV IR_STREAM_TX_REQUIRE_ACK|BUILD_ENV IR_B_|BUILD_ENV IR_MAX_RETRY|BUILD_ENV IR_FRAG_TIMEOUT_CYCLES"
            } | Select-Object -Last 60)) {
                Write-SummaryLine "PHASE_BUILD_MATCH variant=$phase $line"
            }
        }
        if ($buildExit -ne 0) {
            $phaseResult.status = "FAIL_BUILD"
            if ($overallExit -eq 0) { $overallExit = $buildExit }
            $phaseResults += $phaseResult
            break
        }

        if ($BuildOnly.IsPresent -or $SkipRun.IsPresent) {
            $phaseResult.status = "BUILD_ONLY"
            $phaseResults += $phaseResult
            Write-SummaryLine "PHASE_RUN_SKIPPED variant=$phase reason=BuildOnly_or_SkipRun"
            continue
        }

        $runLog = Join-Path $reportsDir "lane_remap_probe_lane${Lane}_${stamp}.${phase}.run.log"
        $runArgs = @(
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
            "-SkipPreflight"
        )
        if ($phaseProfileVariant -eq "b2a_rx") {
            $runArgs += @(
                "-XsctWaitSeconds",
                "60",
                "-PostStartSeconds",
                "90",
                "-CaptureSeconds",
                "140"
            )
        }
        $runExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $runArgs -LogPath $runLog -TimeoutSeconds 1200
        $phaseResult.run_log = $runLog
        $phaseResult.run_exit = $runExit
        Write-SummaryLine "PHASE_RUN_LOG variant=$phase log=$runLog"
        Write-SummaryLine "PHASE_RUN_EXIT variant=$phase exit=$runExit"
        if (Test-Path -LiteralPath $runLog) {
            foreach ($line in (Get-Content -LiteralPath $runLog -ErrorAction SilentlyContinue | Where-Object {
                $_ -match "UART_MATCH=|PSPS_B_RX_ONLY_SUMMARY|PSPS_RX_ONLY_SUMMARY|SHUTDOWN_EXIT=|XSCT_EXIT=|RUN_RESULT_STATUS|LANE0_HW_SAFE_RUN_END"
            } | Select-Object -Last 80)) {
                Write-SummaryLine "PHASE_RUN_MATCH variant=$phase $line"
            }
        }
        $logVerdict = Get-RunLogVerdict -RunLog $runLog -Phase $phaseProfileVariant
        $phaseResult.log_verdict = $logVerdict.verdict
        $phaseResult.log_reason = $logVerdict.reason
        $phaseResult.log_evidence = [string]$logVerdict.evidence
        Write-SummaryLine "PHASE_LOG_VERDICT variant=$phase profile=$phaseProfileVariant verdict=$($logVerdict.verdict)"
        Write-SummaryLine "PHASE_LOG_REASON variant=$phase profile=$phaseProfileVariant reason=$($logVerdict.reason)"
        if ($logVerdict.evidence) {
            Write-SummaryLine "PHASE_LOG_EVIDENCE variant=$phase profile=$phaseProfileVariant $($logVerdict.evidence)"
        }
        if ($runExit -ne 0) {
            $phaseResult.status = "FAIL_RUN"
            if ($overallExit -eq 0) { $overallExit = $runExit }
        } elseif ($logVerdict.verdict -eq "PASS_LOG_COUNTERS") {
            $phaseResult.status = "PASS"
        } elseif ($logVerdict.verdict -like "FAIL*") {
            $phaseResult.status = $logVerdict.verdict
            if ($overallExit -eq 0) { $overallExit = 40 }
        } else {
            $phaseResult.status = $logVerdict.verdict
            if ($overallExit -eq 0) { $overallExit = 41 }
        }
        $phaseResults += $phaseResult
    }
} finally {
    if (-not $NoRestore.IsPresent) {
        Copy-Item -LiteralPath $backupXdc -Destination $port1Xdc -Force
        $script:restorePerformed = $true
        $script:restoreXdcMatch = ((Get-FileHash -Algorithm SHA256 -LiteralPath $port1Xdc).Hash -eq $script:xdcBeforeHash)
        Write-SummaryLine "ACTIVE_XDC_RESTORED=1"
        Write-SummaryLine "ACTIVE_XDC_RESTORE_MATCH=$script:restoreXdcMatch"
    } else {
        Write-SummaryLine "ACTIVE_XDC_RESTORED=0"
        Write-SummaryLine "ACTIVE_XDC_LEFT_REMAP=1"
    }
}

if (-not $KeepGeneratedXdc.IsPresent -and $script:restorePerformed) {
    # Keep the manifest and backup; the generated XDC remains useful evidence and is intentionally not deleted.
    Write-SummaryLine "GENERATED_XDC_RETAINED_FOR_EVIDENCE=1"
}

$status = if ($overallExit -eq 0) {
    if ($BuildOnly.IsPresent -or $SkipRun.IsPresent) { "BUILD_READY" } else { "RUN_COMPLETE" }
} else {
    "FAIL"
}
Write-Manifest -Path $manifestPath -Status $status -OriginalPinMap $pinMap -RemappedPinMap $remappedPinMap -PhaseResults $phaseResults
Write-SummaryLine "LANE_REMAP_PROBE_RESULT=$status"
Write-SummaryLine "LANE_REMAP_PROBE_OVERALL_EXIT=$overallExit"
Write-SummaryLine "LANE_REMAP_PROBE_END $(Get-Date -Format o)"
exit $overallExit
