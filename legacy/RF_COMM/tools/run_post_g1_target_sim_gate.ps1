param(
    [string]$VivadoBin = "D:\Xilinx\Vivado\2023.1\bin",
    [int]$Jobs = 16,
    [int]$SimTimeoutSeconds = 900,
    [int]$PcRepeat = 64,
    [int]$PcPayloadSize = 256,
    [int]$PcReconnectCycles = 4,
    [double]$PcTimeoutSeconds = 5.0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryPath = Join-Path $reportsDir "post_g1_target_sim_gate_$stamp.summary.txt"
$csvPath = Join-Path $reportsDir "post_g1_target_sim_gate_$stamp.cases.csv"
$mdPath = Join-Path $reportsDir "post_g1_target_sim_gate_$stamp.md"
$logDir = Join-Path $reportsDir "post_g1_target_sim_gate_$stamp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$simRunner = Join-Path $repoRoot "IPs\ip_ir_array\run_loopback_single_lane.ps1"
$pcGate = Join-Path $repoRoot "tools\run_ps_pc_offline_gates.ps1"
$targetConsistency = Join-Path $repoRoot "tools\check_target_consistency.py"
$rateBoundaryProof = Join-Path $repoRoot "tools\prove_rate_boundary.py"
$twoAx7010Offline = Join-Path $repoRoot "software\host_client\two_ax7010_end_to_end_model.py"
$fullSystemCappedModel = Join-Path $repoRoot "tools\model_full_system_capped_soak.py"

$constraintPath = Get-ChildItem -LiteralPath $repoRoot -File -Filter "*.txt" |
    Where-Object {
        try {
            (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash -eq $expectedConstraintSha256
        } catch {
            $false
        }
    } |
    Select-Object -First 1 -ExpandProperty FullName

if ([string]::IsNullOrWhiteSpace($constraintPath)) {
    throw "Required hard constraint file with expected SHA256 was not found under repo root."
}

foreach ($path in @($simRunner, $pcGate, $targetConsistency, $rateBoundaryProof, $twoAx7010Offline, $fullSystemCappedModel)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

function Add-Line {
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
        [string]$LogPath,
        [int]$TimeoutSeconds
    )

    $errPath = "$LogPath.err"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError $errPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $sw.Stop()
        return [pscustomobject]@{
            ExitCode = 124
            TimedOut = $true
            Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
            Stdout = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { "" }
            Stderr = if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue } else { "" }
        }
    }
    $proc.Refresh()
    $sw.Stop()
    return [pscustomobject]@{
        ExitCode = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
        TimedOut = $false
        Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
        Stdout = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { "" }
        Stderr = if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue } else { "" }
    }
}

$constraintHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $constraintPath).Hash
$constraintOk = ($constraintHash -eq $expectedConstraintSha256)

"POST_G1_TARGET_SIM_GATE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryPath -Encoding ascii
Add-Line "REPO_ROOT=$repoRoot"
Add-Line "NO_HARDWARE_PROGRAMMING=1"
Add-Line "NO_TFDU_DRIVE=1"
Add-Line "VIVADO_BIN=$VivadoBin"
Add-Line "JOBS=$Jobs"
Add-Line "CONSTRAINT_PATH=$constraintPath"
Add-Line "CONSTRAINT_SHA256=$constraintHash"
Add-Line "CONSTRAINT_UNCHANGED=$([int]$constraintOk)"
Add-Line "LOG_DIR=$logDir"
Add-Line "CSV=$csvPath"
Add-Line "MARKDOWN=$mdPath"

$cases = @(
    [pscustomobject]@{ Kind = "python"; Name = "target_consistency"; Pass = "RF_COMM_TARGET_CONSISTENCY_CHECK overall=BOUNDARY_RAW_ONLY"; Coverage = "Target consistency guard: 8 lanes, raw PHY 32/16 target, payload boundary, TCP/DHCP, rotating-shaft wording, and active 10-minute runtime cap." },
    [pscustomobject]@{ Kind = "python_model"; Name = "rate_boundary_proof"; Pass = "RATE_BOUNDARY_PROOF_PASS"; Coverage = "Arithmetic proof that 32/16 Mbit/s is reachable only as raw PHY capacity under the current 8 x 4 Mbit/s physical budget."; Script = $rateBoundaryProof },
    [pscustomobject]@{ Kind = "xsim"; Name = "phy_rate"; Pass = "IR_PHY_RATE_MODEL_PASS"; Coverage = "Raw PHY capacity basis: 4 Mbit/s per lane, 32 Mbit/s 8-lane half-duplex, 16 Mbit/s per direction 4+4 full-duplex." },
    [pscustomobject]@{ Kind = "xsim"; Name = "payload_budget"; Pass = "IR_PAYLOAD_THROUGHPUT_BUDGET_PASS"; Coverage = "Payload-throughput boundary: proves current frame format is below final payload-rate target and must not be overclaimed." },
    [pscustomobject]@{ Kind = "xsim"; Name = "fdx"; Pass = "LOOPBACK_FULL_DUPLEX_LANE_PARTITION_PASS"; Coverage = "Digital full-duplex lane partition with concurrent bidirectional packets." },
    [pscustomobject]@{ Kind = "xsim"; Name = "fdx_4plus4"; Pass = "LOOPBACK_FULL_DUPLEX_4PLUS4_LANE_PASS"; Coverage = "8-lane full-duplex 4+4 lane partition with four concurrent lanes per direction." },
    [pscustomobject]@{ Kind = "xsim"; Name = "stream_bidir_b0_2lane_perf"; Pass = "IR_STREAM_BIDIR_B0_2LANE_PERF_PASS"; Coverage = "2-lane B0 bidirectional stream performance evidence." },
    [pscustomobject]@{ Kind = "xsim"; Name = "stream_parallel_asym_2lane_perf"; Pass = "IR_STREAM_PARALLEL_ASYM_2LANE_PERF_PASS"; Coverage = "2-lane asymmetric parallel stream performance evidence." },
    [pscustomobject]@{ Kind = "xsim"; Name = "stream_4lane"; Pass = "IR_STREAM_FIXED_4LANE_PASS"; Coverage = "4-lane stream closed-loop evidence for expansion beyond the G1 single lane." },
    [pscustomobject]@{ Kind = "xsim"; Name = "multi"; Pass = "LOOPBACK_MULTI_LANE_PASS"; Coverage = "4-lane packet loopback with concurrent lane use." },
    [pscustomobject]@{ Kind = "xsim"; Name = "multi_8lane"; Pass = "LOOPBACK_8LANE_PASS"; Coverage = "8-lane packet loopback with all lanes concurrently busy and 8 in-flight fragments." },
    [pscustomobject]@{ Kind = "xsim"; Name = "max_fragment_8lane"; Pass = "LOOPBACK_8LANE_MAX_FRAGMENT_PASS"; Coverage = "8-lane packet loopback at the current 255-byte protocol fragment limit and 2040-byte packet payload." },
    [pscustomobject]@{ Kind = "xsim"; Name = "multi_impair"; Pass = "LOOPBACK_MULTI_LANE_IMPAIR_PASS"; Coverage = "4-lane unstable-link recovery with lost lane data, lost ACK, and RX backpressure." },
    [pscustomobject]@{ Kind = "xsim"; Name = "degrade"; Pass = "LOOPBACK_MULTI_LANE_DEGRADE_PASS"; Coverage = "Lane-mask fallback and restoration across 4/3/2/1/4-lane operation." },
    [pscustomobject]@{ Kind = "xsim"; Name = "route"; Pass = "LOOPBACK_MULTI_LANE_ROUTE_PASS"; Coverage = "Changing TX/RX lane correspondence between packets." },
    [pscustomobject]@{ Kind = "xsim"; Name = "autoroute"; Pass = "LOOPBACK_MULTI_LANE_AUTOROUTE_PASS"; Coverage = "Automatic route finding when only one optical source lane is reachable per packet." },
    [pscustomobject]@{ Kind = "xsim"; Name = "autoroute_8lane"; Pass = "LOOPBACK_8LANE_AUTOROUTE_PASS"; Coverage = "8-lane automatic route finding across changing TX/RX correspondence with all source lanes covered." },
    [pscustomobject]@{ Kind = "xsim"; Name = "rotating_autoroute"; Pass = "LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS"; Coverage = "600 rpm / 20 cm metadata stress with rotating-style route changes." },
    [pscustomobject]@{ Kind = "xsim"; Name = "rotating_soak_model"; Pass = "ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS"; Coverage = "2-hour equivalent rotating autoroute model: 72000 rotations and 288000 sector changes." },
    [pscustomobject]@{ Kind = "xsim"; Name = "rotating_8lane_soak_model"; Pass = "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS"; Coverage = "8-lane rotating autoroute model under the active 10-minute cap: 6000 rotations and 48000 sector changes." },
    [pscustomobject]@{ Kind = "python_script"; Name = "two_ax7010_end_to_end_offline"; Pass = "TWO_AX7010_END_TO_END_OFFLINE_PASS"; Coverage = "Two independent AX7010 PS bridge endpoints with PC-A/PC-B RFCM clients exchanging bidirectional traffic through an offline IR link model and reconnect queue."; Script = $twoAx7010Offline },
    [pscustomobject]@{ Kind = "python_model"; Name = "full_system_capped_digital_twin"; Pass = "FULL_SYSTEM_CAPPED_DIGITAL_TWIN_PASS"; Coverage = "Two AX7010 endpoints, PC/PS TCP-DHCP behavior, 8-lane rotating autoroute, short impairments, and the active 10-minute cap in one offline model."; Script = $fullSystemCappedModel },
    [pscustomobject]@{ Kind = "pc"; Name = "ps_pc_offline"; Pass = "PS_PC_OFFLINE_GATES_PASS"; Coverage = "PC/PS protocol offline gate with TCP/DHCP/reconnect static checks, host tests, and offline mock traffic." }
)

$rows = [System.Collections.Generic.List[object]]::new()
$overallPass = $constraintOk

foreach ($case in $cases) {
    $safeName = $case.Name -replace '[^A-Za-z0-9_.-]', '_'
    $caseLog = Join-Path $logDir "$safeName.log"
    Add-Line "CASE_START kind=$($case.Kind) name=$($case.Name) log=$caseLog"

    if ($case.Kind -eq "xsim") {
        $result = Invoke-LoggedProcess -Name $case.Name -FilePath "powershell.exe" -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $simRunner,
            "-VivadoBin",
            $VivadoBin,
            "-Jobs",
            [string]$Jobs,
            "-Test",
            $case.Name
        ) -LogPath $caseLog -TimeoutSeconds $SimTimeoutSeconds
    } elseif ($case.Kind -eq "pc") {
        $result = Invoke-LoggedProcess -Name $case.Name -FilePath "powershell.exe" -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $pcGate,
            "-Repeat",
            [string]$PcRepeat,
            "-PayloadSize",
            [string]$PcPayloadSize,
            "-ReconnectCycles",
            [string]$PcReconnectCycles,
            "-TimeoutSeconds",
            [string]$PcTimeoutSeconds
        ) -LogPath $caseLog -TimeoutSeconds 240
    } elseif ($case.Kind -eq "python") {
        $result = Invoke-LoggedProcess -Name $case.Name -FilePath "python" -Arguments @(
            $targetConsistency
        ) -LogPath $caseLog -TimeoutSeconds 60
    } elseif ($case.Kind -eq "python_script") {
        $modelLogDir = Join-Path $logDir $safeName
        $modelTimeout = [math]::Max($PcTimeoutSeconds, 10.0)
        $result = Invoke-LoggedProcess -Name $case.Name -FilePath "python" -Arguments @(
            $case.Script,
            "--repeat",
            [string]$PcRepeat,
            "--payload-size",
            [string]$PcPayloadSize,
            "--timeout",
            [string]$modelTimeout,
            "--log-dir",
            $modelLogDir
        ) -LogPath $caseLog -TimeoutSeconds 120
    } elseif ($case.Kind -eq "python_model") {
        $jsonOutput = Join-Path $logDir "$safeName.json"
        $result = Invoke-LoggedProcess -Name $case.Name -FilePath "python" -Arguments @(
            $case.Script,
            "--json-output",
            $jsonOutput
        ) -LogPath $caseLog -TimeoutSeconds 120
    } else {
        throw "Unsupported case kind: $($case.Kind)"
    }

    $combined = "$($result.Stdout)`n$($result.Stderr)"
    $passSeen = $result.Stdout -match [regex]::Escape($case.Pass)
    $casePass = (($result.ExitCode -eq 0) -and $passSeen -and (-not $result.TimedOut))
    if (-not $casePass) {
        $overallPass = $false
    }
    Add-Line "CASE_RESULT name=$($case.Name) pass=$([int]$casePass) exit=$($result.ExitCode) timeout=$([int]$result.TimedOut) seconds=$($result.Seconds) pass_pattern=$($case.Pass) pass_seen=$([int]$passSeen)"
    foreach ($line in (($combined -split "`r?`n") | Where-Object { $_ -match "PASS|FAIL|Mbit|rpm|rotations|sectors|summary|PS_PC|acceptance|RF_COMM|BOUNDARY" } | Select-Object -Last 12)) {
        Add-Line "CASE_NOTE name=$($case.Name) $line"
    }
    $rows.Add([pscustomobject]@{
        kind = $case.Kind
        name = $case.Name
        status = if ($casePass) { "PASS" } else { "FAIL" }
        exit_code = $result.ExitCode
        timed_out = [int]$result.TimedOut
        seconds = $result.Seconds
        pass_pattern = $case.Pass
        pass_seen = [int]$passSeen
        log = $caseLog
        coverage = $case.Coverage
    })
}

$csvLines = [System.Collections.Generic.List[string]]::new()
$csvLines.Add("kind,name,status,exit_code,timed_out,seconds,pass_pattern,pass_seen,log,coverage")
foreach ($row in $rows) {
    $csvLines.Add((
        (Csv-Escape $row.kind),
        (Csv-Escape $row.name),
        (Csv-Escape $row.status),
        $row.exit_code,
        $row.timed_out,
        $row.seconds,
        (Csv-Escape $row.pass_pattern),
        $row.pass_seen,
        (Csv-Escape $row.log),
        (Csv-Escape $row.coverage)
    ) -join ",")
}
[System.IO.File]::WriteAllLines($csvPath, [string[]]$csvLines, [System.Text.Encoding]::ASCII)

$passCount = @($rows | Where-Object { $_.status -eq "PASS" }).Count
$failCount = @($rows | Where-Object { $_.status -ne "PASS" }).Count
Add-Line "POST_G1_TARGET_SIM_GATE_PASS_COUNT=$passCount"
Add-Line "POST_G1_TARGET_SIM_GATE_FAIL_COUNT=$failCount"
Add-Line "POST_G1_TARGET_SIM_GATE_PASS=$([int]($overallPass -and ($failCount -eq 0)))"

$mdLines = [System.Collections.Generic.List[string]]::new()
$mdLines.Add("# Post-G1 Target Simulation Gate")
$mdLines.Add("")
$mdLines.Add("Generated: $(Get-Date -Format o)")
$mdLines.Add("")
$mdLines.Add("This gate uses simulation and offline software tests only. It does not program hardware or drive TFDU boards.")
$mdLines.Add("")
$mdLines.Add("- Overall: ``$(if ($overallPass -and ($failCount -eq 0)) { "PASS" } else { "FAIL" })``")
$mdLines.Add("- Constraint SHA256: ``$constraintHash``")
$mdLines.Add("- Constraint unchanged: ``$constraintOk``")
$mdLines.Add("- Summary: ``$summaryPath``")
$mdLines.Add("- CSV: ``$csvPath``")
$mdLines.Add("- Logs: ``$logDir``")
$mdLines.Add("")
$mdLines.Add("| Case | Status | Seconds | Coverage |")
$mdLines.Add("| --- | --- | ---: | --- |")
foreach ($row in $rows) {
    $mdLines.Add("| ``$($row.name)`` | ``$($row.status)`` | $($row.seconds) | $($row.coverage) |")
}
$mdLines.Add("")
$mdLines.Add("Remaining non-simulation gates: physical 8-lane wiring, real rotating shaft validation, capped hardware soak repetitions under the active runtime rule, and real PS-to-PC TCP/DHCP board tests.")
[System.IO.File]::WriteAllLines($mdPath, [string[]]$mdLines, [System.Text.Encoding]::UTF8)

Add-Line "POST_G1_TARGET_SIM_GATE_MARKDOWN=$mdPath"
Add-Line "POST_G1_TARGET_SIM_GATE_END $(Get-Date -Format o)"

if (-not ($overallPass -and ($failCount -eq 0))) {
    exit 1
}
exit 0
