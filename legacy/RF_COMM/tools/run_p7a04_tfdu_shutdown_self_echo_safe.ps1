param(
    [ValidateRange(0, 7)]
    [int]$Lane = 1,
    [ValidateRange(0, 1)]
    [int]$LogicalProbeLane = 0,
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$Jobs = 16,
    [int]$RepeatCount = 3,
    [int]$PerRunTimeoutSeconds = 300,
    [int]$MaxTfduWindowSeconds = 300,
    [switch]$SkipRepackage,
    [switch]$SkipBuild,
    [switch]$BuildOnly,
    [switch]$NoRestoreElf
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "P7A_04_tfdu_shutdown_self_echo_lane${Lane}_${stamp}.summary.txt"
$reportPath = Join-Path $reportsDir "P7A_04_tfdu_shutdown_self_echo_report_lane${Lane}_${stamp}.md"
$repackageLog = Join-Path $reportsDir "P7A_04_tfdu_shutdown_self_echo_lane${Lane}_${stamp}.repackage.log"
$buildLog = Join-Path $reportsDir "P7A_04_tfdu_shutdown_self_echo_lane${Lane}_${stamp}.lane_remap_build.log"

$repackageTcl = Join-Path $repoRoot "IPs\ip_ir_array\repackage_ip.tcl"
$laneRemapScript = Join-Path $repoRoot "tools\run_lane_remap_probe_safe.ps1"
$matrixScript = Join-Path $repoRoot "tools\run_2lane_matrix_safe.ps1"
$bitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$ltxPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx"
$xsaPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"

foreach ($path in @($VivadoPath, $XsctPath, $repackageTcl, $laneRemapScript, $matrixScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

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

    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError ($LogPath + ".err") `
        -WindowStyle Hidden `
        -PassThru
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

function Get-LogValue {
    param(
        [string]$Text,
        [string]$Key
    )
    $match = [regex]::Match($Text, "(?m)^" + [regex]::Escape($Key) + "=(.+)$")
    if ($match.Success) {
        return $match.Groups[1].Value.Trim()
    }
    return ""
}

function Get-SignalMetric {
    param(
        $Analysis,
        [string]$Name
    )
    if ($null -eq $Analysis.signals) {
        return $null
    }
    $property = $Analysis.signals.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Test-ActiveShutdown {
    param($Metric)
    if ($null -eq $Metric) {
        return $false
    }
    return ([double]$Metric.active_fraction -ge 0.95 -and [bool]$Metric.stuck_active)
}

function Test-PulseActivity {
    param($Metric)
    if ($null -eq $Metric) {
        return $false
    }
    return ([int]$Metric.pulse_count -gt 0 -and [bool]$Metric.has_pulse_activity)
}

function New-AnalysisRow {
    param($Analysis)

    $trigger = [string]$Analysis.trigger_mode
    if ($trigger -eq "a_tx_lane$LogicalProbeLane") {
        $tx = Get-SignalMetric -Analysis $Analysis -Name "a_tx$LogicalProbeLane"
        $localRx = Get-SignalMetric -Analysis $Analysis -Name "a_rx$LogicalProbeLane"
        $remoteRx = Get-SignalMetric -Analysis $Analysis -Name "b_rx$LogicalProbeLane"
        $aSd = Get-SignalMetric -Analysis $Analysis -Name "a_sd$LogicalProbeLane"
        $bSd = Get-SignalMetric -Analysis $Analysis -Name "b_sd$LogicalProbeLane"
    } elseif ($trigger -eq "b_tx_lane$LogicalProbeLane") {
        $tx = Get-SignalMetric -Analysis $Analysis -Name "b_tx$LogicalProbeLane"
        $localRx = Get-SignalMetric -Analysis $Analysis -Name "b_rx$LogicalProbeLane"
        $remoteRx = Get-SignalMetric -Analysis $Analysis -Name "a_rx$LogicalProbeLane"
        $aSd = Get-SignalMetric -Analysis $Analysis -Name "a_sd$LogicalProbeLane"
        $bSd = Get-SignalMetric -Analysis $Analysis -Name "b_sd$LogicalProbeLane"
    } else {
        $tx = $null
        $localRx = $null
        $remoteRx = $null
        $aSd = Get-SignalMetric -Analysis $Analysis -Name "a_sd$LogicalProbeLane"
        $bSd = Get-SignalMetric -Analysis $Analysis -Name "b_sd$LogicalProbeLane"
    }

    $txToggled = Test-PulseActivity -Metric $tx
    $localEcho = Test-PulseActivity -Metric $localRx
    $remotePresent = Test-PulseActivity -Metric $remoteRx
    $sdVerified = ((Test-ActiveShutdown -Metric $aSd) -and (Test-ActiveShutdown -Metric $bSd))

    return [ordered]@{
        trigger = $trigger
        csv = [string]$Analysis.csv_path
        verdict = [string]$Analysis.verdict
        reason = [string]$Analysis.verdict_reason
        tx_pulses = if ($tx) { [int]$tx.pulse_count } else { -1 }
        local_rx_pulses = if ($localRx) { [int]$localRx.pulse_count } else { -1 }
        remote_rx_pulses = if ($remoteRx) { [int]$remoteRx.pulse_count } else { -1 }
        a_sd_active_fraction = if ($aSd) { [double]$aSd.active_fraction } else { -1.0 }
        b_sd_active_fraction = if ($bSd) { [double]$bSd.active_fraction } else { -1.0 }
        tx_toggled = $txToggled
        local_echo = $localEcho
        remote_present = $remotePresent
        sd_shutdown_verified = $sdVerified
    }
}

function ConvertTo-MdTable {
    param([array]$Rows)
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("| trigger | tx_pulses | local_rx_pulses | remote_rx_pulses | a_sd_frac | b_sd_frac | tx_toggled | local_echo | remote_present | sd_verified |")
    $lines.Add("| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |")
    foreach ($row in $Rows) {
        $lines.Add((
            "| {0} | {1} | {2} | {3} | {4:N3} | {5:N3} | {6} | {7} | {8} | {9} |" -f
            $row.trigger,
            $row.tx_pulses,
            $row.local_rx_pulses,
            $row.remote_rx_pulses,
            $row.a_sd_active_fraction,
            $row.b_sd_active_fraction,
            [int]$row.tx_toggled,
            [int]$row.local_echo,
            [int]$row.remote_present,
            [int]$row.sd_shutdown_verified
        ))
    }
    return ($lines -join "`n")
}

"P7A_04_TFDU_SHUTDOWN_SELF_ECHO_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "REQUESTED_PHYSICAL_LANE=$Lane"
Write-SummaryLine "LOGICAL_PROBE_LANE=$LogicalProbeLane"
Write-SummaryLine "REPEAT_COUNT=$RepeatCount"
Write-SummaryLine "JOBS=$Jobs"
Write-SummaryLine "SUMMARY_LOG=$summaryLog"
Write-SummaryLine "REPORT=$reportPath"
Write-SummaryLine "FORCE_SD_SHUTDOWN=1"
Write-SummaryLine "BIT_BEFORE_SHA256=$(Get-FileHashOrEmpty -Path $bitPath)"
Write-SummaryLine "LTX_BEFORE_SHA256=$(Get-FileHashOrEmpty -Path $ltxPath)"
Write-SummaryLine "ELF_BEFORE_SHA256=$(Get-FileHashOrEmpty -Path $elfPath)"

$oldForce = [Environment]::GetEnvironmentVariable("IR_FORCE_SD_SHUTDOWN", "Process")
$elfBackup = ""
$restoreElfPerformed = $false
$allRows = @()
$matrixReports = @()
$overallExit = 0

try {
    [Environment]::SetEnvironmentVariable("IR_FORCE_SD_SHUTDOWN", "1", "Process")

    if (-not $SkipRepackage) {
        Write-SummaryLine "REPACKAGE_START=$(Get-Date -Format o)"
        $repackageExit = Invoke-LoggedProcess -FilePath $VivadoPath -Arguments @(
            "-mode",
            "batch",
            "-source",
            $repackageTcl
        ) -LogPath $repackageLog -TimeoutSeconds 1200
        if ($repackageExit -eq 125 -and (Test-Path -LiteralPath $repackageLog)) {
            $repackageText = Get-Content -LiteralPath $repackageLog -Raw -ErrorAction SilentlyContinue
            if ($repackageText -match "Repackaged .* revision") {
                $repackageExit = 0
                Write-SummaryLine "REPACKAGE_EXIT_INFERRED=0"
            }
        }
        Write-SummaryLine "REPACKAGE_LOG=$repackageLog"
        Write-SummaryLine "REPACKAGE_EXIT=$repackageExit"
        if ($repackageExit -ne 0) {
            $overallExit = $repackageExit
            throw "IP repackage failed"
        }
    } else {
        Write-SummaryLine "REPACKAGE_SKIPPED=1"
    }

    if (-not $SkipBuild) {
        Write-SummaryLine "LANE_REMAP_FORCE_SD_BUILD_START=$(Get-Date -Format o)"
        $buildExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $laneRemapScript,
            "-Lane",
            [string]$Lane,
            "-Variant",
            "b2a_rx",
            "-ComPort",
            $ComPort,
            "-BaudRate",
            [string]$BaudRate,
            "-VivadoPath",
            $VivadoPath,
            "-XsctPath",
            $XsctPath,
            "-HwServerUrl",
            $HwServerUrl,
            "-JtagFrequencyHz",
            [string]$JtagFrequencyHz,
            "-Jobs",
            [string]$Jobs,
            "-Apply",
            "-BuildOnly",
            "-SkipPreflight"
        ) -LogPath $buildLog -TimeoutSeconds 10000
        if ($buildExit -eq 125 -and (Test-Path -LiteralPath $buildLog)) {
            $buildTextForExit = Get-Content -LiteralPath $buildLog -Raw -ErrorAction SilentlyContinue
            $remapExitText = Get-LogValue -Text $buildTextForExit -Key "LANE_REMAP_PROBE_OVERALL_EXIT"
            if ($remapExitText -eq "0") {
                $buildExit = 0
                Write-SummaryLine "LANE_REMAP_FORCE_SD_BUILD_EXIT_INFERRED=0"
            }
        }
        Write-SummaryLine "LANE_REMAP_FORCE_SD_BUILD_LOG=$buildLog"
        Write-SummaryLine "LANE_REMAP_FORCE_SD_BUILD_EXIT=$buildExit"
        if (Test-Path -LiteralPath $buildLog) {
            $buildText = Get-Content -LiteralPath $buildLog -Raw -ErrorAction SilentlyContinue
            foreach ($line in (($buildText -split "`r?`n") | Where-Object {
                $_ -match "MANIFEST=|MAPPING |BUILD_ENV IR_FORCE_SD_SHUTDOWN|BUILD_ENV IR_B2A|ARTIFACT |LANE_REMAP_PROBE_RESULT|ACTIVE_XDC_RESTORE_MATCH"
            })) {
                Write-SummaryLine "BUILD_MATCH=$line"
            }
        }
        if ($buildExit -ne 0) {
            $overallExit = $buildExit
            throw "Lane remap force-SD build failed"
        }
    } else {
        Write-SummaryLine "BUILD_SKIPPED=1"
    }

    Write-SummaryLine "BIT_FORCE_SD_SHA256=$(Get-FileHashOrEmpty -Path $bitPath)"
    Write-SummaryLine "LTX_FORCE_SD_SHA256=$(Get-FileHashOrEmpty -Path $ltxPath)"
    Write-SummaryLine "XSA_FORCE_SD_SHA256=$(Get-FileHashOrEmpty -Path $xsaPath)"
    Write-SummaryLine "ELF_AFTER_BUILD_SHA256=$(Get-FileHashOrEmpty -Path $elfPath)"

    if ($BuildOnly) {
        Write-SummaryLine "P7A_04_BUILD_ONLY_NO_HARDWARE_RUN=1"
    } elseif ((Test-Path -LiteralPath $elfPath) -and (-not $NoRestoreElf)) {
        $elfBackup = Join-Path $reportsDir "P7A_04_tfdu_shutdown_self_echo_lane${Lane}_${stamp}.elf_before_matrix.bak"
        Copy-Item -LiteralPath $elfPath -Destination $elfBackup -Force
        Write-SummaryLine "ELF_BACKUP_BEFORE_MATRIX=$elfBackup"
    }

    $triggerModes = "a_tx_lane$LogicalProbeLane,b_tx_lane$LogicalProbeLane"
    for ($repeat = 1; (-not $BuildOnly) -and $repeat -le $RepeatCount; $repeat++) {
        $matrixLog = Join-Path $reportsDir "P7A_04_tfdu_shutdown_self_echo_lane${Lane}_${stamp}.matrix_r${repeat}.log"
        Write-SummaryLine "MATRIX_REPEAT_START repeat=$repeat trigger_modes=$triggerModes time=$(Get-Date -Format o)"
        $matrixExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $matrixScript,
            "-ComPort",
            $ComPort,
            "-BaudRate",
            [string]$BaudRate,
            "-XsctPath",
            $XsctPath,
            "-VivadoPath",
            $VivadoPath,
            "-TriggerModes",
            $triggerModes,
            "-JtagFrequencyHz",
            [string]$JtagFrequencyHz,
            "-PerRunTimeoutSeconds",
            [string]$PerRunTimeoutSeconds,
            "-MaxTfduWindowSeconds",
            [string]$MaxTfduWindowSeconds,
            "-AutoBuildPsElfPerTrigger"
        ) -LogPath $matrixLog -TimeoutSeconds (($PerRunTimeoutSeconds * 2) + 420)
        $matrixTextForExit = ""
        if (Test-Path -LiteralPath $matrixLog) {
            $matrixTextForExit = Get-Content -LiteralPath $matrixLog -Raw -ErrorAction SilentlyContinue
        }
        if ($matrixExit -eq 125 -and $matrixTextForExit -ne "") {
            $matrixExitText = Get-LogValue -Text $matrixTextForExit -Key "MATRIX_OVERALL_EXIT"
            if ($matrixExitText -match "^\d+$") {
                $matrixExit = [int]$matrixExitText
                Write-SummaryLine "MATRIX_REPEAT_EXIT_INFERRED repeat=$repeat exit=$matrixExit"
            }
        }
        Write-SummaryLine "MATRIX_REPEAT_LOG repeat=$repeat log=$matrixLog"
        Write-SummaryLine "MATRIX_REPEAT_EXIT repeat=$repeat exit=$matrixExit"
        if ($matrixExit -ne 0 -and $overallExit -eq 0) {
            $overallExit = $matrixExit
        }

        $matrixText = $matrixTextForExit
        if ($matrixText -ne "") {
            foreach ($line in (($matrixText -split "`r?`n") | Where-Object {
                $_ -match "MATRIX_ANALYSIS_JSON=|MATRIX_ANALYSIS_MD=|RUN_RESULT trigger=|MATRIX_OVERALL_EXIT|MATRIX_ANALYSIS_MATCH="
            })) {
                Write-SummaryLine "MATRIX_MATCH repeat=$repeat $line"
            }
        }

        $matrixJson = Get-LogValue -Text $matrixText -Key "MATRIX_ANALYSIS_JSON"
        $matrixMd = Get-LogValue -Text $matrixText -Key "MATRIX_ANALYSIS_MD"
        if ($matrixJson -ne "") {
            $matrixReports += $matrixJson
            $analyses = Get-Content -LiteralPath $matrixJson -Raw | ConvertFrom-Json
            foreach ($analysis in $analyses) {
                $allRows += New-AnalysisRow -Analysis $analysis
            }
        }
        if ($matrixMd -ne "") {
            $matrixReports += $matrixMd
        }
    }
} finally {
    [Environment]::SetEnvironmentVariable("IR_FORCE_SD_SHUTDOWN", $oldForce, "Process")
    if ($elfBackup -ne "" -and (Test-Path -LiteralPath $elfBackup) -and (-not $NoRestoreElf)) {
        Copy-Item -LiteralPath $elfBackup -Destination $elfPath -Force
        $restoreElfPerformed = $true
        Write-SummaryLine "ELF_RESTORED_AFTER_MATRIX=1"
        Write-SummaryLine "ELF_RESTORED_SHA256=$(Get-FileHashOrEmpty -Path $elfPath)"
    }
}

$expectedRows = $RepeatCount * 2
$rowsPresent = $allRows.Count
$txValid = @($allRows | Where-Object { $_.tx_toggled }).Count
$sdVerified = @($allRows | Where-Object { $_.sd_shutdown_verified }).Count
$localEcho = @($allRows | Where-Object { $_.local_echo }).Count
$remotePresent = @($allRows | Where-Object { $_.remote_present }).Count

$p7aResult = "INDETERMINATE"
$classificationNote = "P7A-04 did not produce enough valid shutdown-plus-TXD-toggle captures."
$diagnosticComplete = ($rowsPresent -eq $expectedRows -and $txValid -eq $expectedRows -and $sdVerified -eq $expectedRows)
if ($diagnosticComplete) {
    if ($localEcho -eq $expectedRows -and $remotePresent -eq 0) {
        $p7aResult = "SELF_ECHO_PERSISTS_WITH_SD_SHUTDOWN"
        $classificationNote = "TXD toggled while A/B SD stayed shutdown-high, yet the same-side RX pulse train remained and the far-end RX stayed quiet."
    } elseif ($localEcho -eq 0 -and $remotePresent -eq 0) {
        $p7aResult = "SELF_ECHO_SUPPRESSED_BY_SD_SHUTDOWN"
        $classificationNote = "TXD toggled while A/B SD stayed shutdown-high, and the previous same-side RX echo disappeared."
    } elseif ($remotePresent -gt 0) {
        $p7aResult = "REMOTE_RAW_PRESENT_UNDER_SD_SHUTDOWN"
        $classificationNote = "At least one far-end RX pulse train appeared while SD was high; inspect mapping and electrical state before using this as connectivity evidence."
    } else {
        $p7aResult = "MIXED_SHUTDOWN_ECHO_RESULT"
        $classificationNote = "Valid captures were produced but local echo behavior was not consistent across repeats."
    }
}
if ($diagnosticComplete) {
    $overallExit = 0
}

Write-SummaryLine "P7A_04_EXPECTED_ROWS=$expectedRows"
Write-SummaryLine "P7A_04_ROWS_PRESENT=$rowsPresent"
Write-SummaryLine "P7A_04_TXD_TOGGLED_COUNT=$txValid"
Write-SummaryLine "P7A_04_SD_SHUTDOWN_VERIFIED_COUNT=$sdVerified"
Write-SummaryLine "P7A_04_LOCAL_ECHO_COUNT=$localEcho"
Write-SummaryLine "P7A_04_REMOTE_PRESENT_COUNT=$remotePresent"
Write-SummaryLine "P7A_04_DIAGNOSTIC_COMPLETE=$([int]$diagnosticComplete)"
Write-SummaryLine "P7A_04_RESULT=$p7aResult"
Write-SummaryLine "P7A_04_OVERALL_EXIT=$overallExit"
Write-SummaryLine "P7A_04_TFDU_SHUTDOWN_SELF_ECHO_END $(Get-Date -Format o)"

$reportLines = @(
    "# P7A-04 TFDU Shutdown Self-Echo Report",
    "",
    "P7A_04_RESULT = $p7aResult",
    "P7A_04_REQUESTED_PHYSICAL_LANE = $Lane",
    "P7A_04_LOGICAL_PROBE_LANE = $LogicalProbeLane",
    "P7A_04_FORCE_SD_SHUTDOWN = 1",
    "P7A_04_EXPECTED_CAPTURES = $expectedRows",
    "P7A_04_VALID_ANALYSIS_ROWS = $rowsPresent",
    "P7A_04_TXD_TOGGLED_COUNT = $txValid",
    "P7A_04_SD_SHUTDOWN_VERIFIED_COUNT = $sdVerified",
    "P7A_04_LOCAL_SELF_ECHO_COUNT = $localEcho",
    "P7A_04_REMOTE_RAW_PRESENT_COUNT = $remotePresent",
    "P7A_04_ELF_RESTORED_AFTER_MATRIX = $([int]$restoreElfPerformed)",
    "",
    "## Interpretation",
    "",
    $classificationNote,
    "",
    "This is a raw ILA diagnostic. It is not a DATA/protocol connectivity PASS claim.",
    "",
    "## Artifact Hashes",
    "",
    ("- Bit: ``{0}`` SHA256 ``{1}``" -f $bitPath, (Get-FileHashOrEmpty -Path $bitPath)),
    ("- LTX: ``{0}`` SHA256 ``{1}``" -f $ltxPath, (Get-FileHashOrEmpty -Path $ltxPath)),
    ("- XSA: ``{0}`` SHA256 ``{1}``" -f $xsaPath, (Get-FileHashOrEmpty -Path $xsaPath)),
    ("- ELF: ``{0}`` SHA256 ``{1}``" -f $elfPath, (Get-FileHashOrEmpty -Path $elfPath)),
    "",
    "## Logs",
    "",
    ("- Summary: ``{0}``" -f $summaryLog),
    ("- Repackage log: ``{0}``" -f $repackageLog),
    ("- Lane remap force-SD build log: ``{0}``" -f $buildLog),
    "",
    "## Matrix Outputs",
    "",
    (($matrixReports | Sort-Object -Unique | ForEach-Object { "- ``{0}``" -f $_ }) -join "`n"),
    "",
    "## Capture Metrics",
    "",
    (ConvertTo-MdTable -Rows $allRows)
)
$reportLines | Out-File -LiteralPath $reportPath -Encoding utf8

if ($overallExit -ne 0) {
    exit $overallExit
}
exit 0
