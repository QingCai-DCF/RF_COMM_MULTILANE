param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [ValidateSet("PL_INTERNAL", "FIXED_HW")]
    [string]$LoopbackMode = "PL_INTERNAL",
    [object]$PayloadSizes = "16,64,256",
    [int]$LaneRepeat = 8,
    [int]$TwoLaneRepeat = 16,
    [int]$StressRepeat = 100,
    [int]$StressSeconds = 60,
    [string]$SessionId = "0x2201",
    [ValidateSet("existing-path-roundtrip", "lane-ack-matrix")]
    [string]$OperatorMode = "existing-path-roundtrip",
    [switch]$EnableFaultInjection,
    [string]$LogDir = "",
    [switch]$Apply,
    [switch]$SkipPreflight,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$XsctWaitSeconds = 120,
    [int]$HostWaitSeconds = 600,
    [string]$TargetPlanPath = "C:\Users\user\Downloads\single_board_2lane_next_step_plan.md",
    [string]$OperatorElfPath = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if ([string]::IsNullOrWhiteSpace($LogDir)) {
    $LogDir = Join-Path $repoRoot "reports\single_board_2lane_existing_path_$stamp"
} elseif (-not [System.IO.Path]::IsPathRooted($LogDir)) {
    $LogDir = Join-Path $repoRoot $LogDir
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if ($PayloadSizes -is [array]) {
    $PayloadSizeList = @($PayloadSizes | ForEach-Object { [int]$_ })
} else {
    $PayloadSizeList = @(([string]$PayloadSizes -split "[,\s]+" | Where-Object { $_ -ne "" } | ForEach-Object { [int]$_ }))
}
if ($PayloadSizeList.Count -eq 0) {
    $PayloadSizeList = @(16, 64, 256)
}

$flagsPath = Join-Path $LogDir "10_result_flags.txt"
$summaryJsonPath = Join-Path $LogDir "summary.json"
$reportPath = Join-Path $LogDir "next_step_report.md"
$envPath = Join-Path $LogDir "00_environment.json"
$safeGateLog = Join-Path $LogDir "01_safe_gate.log"
$safeGateErr = Join-Path $LogDir "01_safe_gate.err.log"
$operatorTranscript = Join-Path $LogDir "single_board_existing_path_operator.transcript.log"
$operatorOutLog = Join-Path $LogDir "single_board_existing_path_operator.out.log"
$operatorErrLog = Join-Path $LogDir "single_board_existing_path_operator.err.log"
$operatorSummaryJson = Join-Path $LogDir "operator_summary.json"
$xsctOutLog = Join-Path $LogDir "program_existing_path_operator.xsct.out.log"
$xsctErrLog = Join-Path $LogDir "program_existing_path_operator.xsct.err.log"
$initialShutdownLog = Join-Path $LogDir "00_initial_shutdown.log"
$initialShutdownErr = Join-Path $LogDir "00_initial_shutdown.err.log"
$finalShutdownLog = Join-Path $LogDir "09_final_shutdown.log"
$finalShutdownErr = Join-Path $LogDir "09_final_shutdown.err.log"
$capabilityLog = Join-Path $LogDir "15_capability_scan.txt"
$gateLog = Join-Path $LogDir "15_gate_check.txt"

$constraintFile = Get-ChildItem -LiteralPath $repoRoot -Filter "*.txt" -File |
    Where-Object { $_.Length -gt 1000 -and $_.Name -match "\(" } |
    Sort-Object Length -Descending |
    Select-Object -First 1
if ($null -ne $constraintFile) {
    $constraintPath = $constraintFile.FullName
} else {
    $constraintPath = Join-Path $repoRoot "project_constraints_file_not_found.txt"
}
$workspaceBit = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$workspaceElf = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$runTcl = Join-Path $repoRoot "software\ps_ps_loopback\run_on_hw.tcl"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$operatorTool = Join-Path $repoRoot "tools\uart_operator_single_board_loopback.py"
$checkerTool = Join-Path $repoRoot "tools\check_single_board_2lane_loopback_gate.py"
$backupElf = Join-Path $LogDir "workspace_elf_before_single_board_existing_path_$stamp.elf"

if ([string]::IsNullOrWhiteSpace($OperatorElfPath)) {
    $operatorElf = Get-ChildItem -LiteralPath (Join-Path $repoRoot "deliverables\p2_uart_operator") -Filter "rf_comm_ps_ps_loopback_uart_operator_*.elf" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -ne $operatorElf) {
        $OperatorElfPath = $operatorElf.FullName
    }
}

function Write-TextFile {
    param([string]$Path, [string[]]$Lines)
    $Lines | Out-File -LiteralPath $Path -Encoding utf8
}

function Add-Flag {
    param([string]$Line)
    Add-Content -LiteralPath $flagsPath -Value $Line -Encoding ascii
}

function Get-HashOrMissing {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    }
    return "MISSING"
}

function Copy-IfExists {
    param([string]$Source, [string]$Destination)
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        return 1
    }
    "MISSING_SOURCE=$Source" | Out-File -LiteralPath $Destination -Encoding utf8
    return 0
}

function ConvertTo-CmdArg {
    param([string]$Value)
    if ($Value -match '[\s&()^|<>"]') {
        return '"' + ($Value -replace '"', '""') + '"'
    }
    return $Value
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$StdoutPath,
        [string]$StderrPath,
        [int]$TimeoutSeconds
    )

    $argLine = ($Arguments | ForEach-Object { ConvertTo-CmdArg $_ }) -join " "
    $cmdLine = '"' + $FilePath + '" ' + $argLine + ' > "' + $StdoutPath + '" 2> "' + $StderrPath + '"'
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

function Get-JsonValue {
    param($Obj, [string]$Name, $Default)
    if ($null -ne $Obj -and ($Obj.PSObject.Properties.Name -contains $Name)) {
        return $Obj.$Name
    }
    return $Default
}

function To-StatusValue {
    param($Value)
    if ($Value -is [int]) {
        return [string]$Value
    }
    if ($Value -is [long]) {
        return [string]$Value
    }
    if ($Value -is [string]) {
        return $Value
    }
    if ($null -eq $Value) {
        return "0"
    }
    return [string]$Value
}

function Write-PlaceholderIfMissing {
    param([string]$Path, [string]$Line)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-TextFile -Path $Path -Lines @($Line)
    }
}

"" | Out-File -LiteralPath $flagsPath -Encoding ascii

$targetCopied = Copy-IfExists -Source $TargetPlanPath -Destination (Join-Path $LogDir "target_plan.md")
$constraintCopied = Copy-IfExists -Source $constraintPath -Destination (Join-Path $LogDir "project_constraints_snapshot.txt")
cmd.exe /d /c "git status --short 2>&1" | Out-File -LiteralPath (Join-Path $LogDir "git_status_before_run.txt") -Encoding utf8
cmd.exe /d /c "git diff 2>&1" | Out-File -LiteralPath (Join-Path $LogDir "worktree_before_run.diff") -Encoding utf8

$scanFiles = @(
    (Join-Path $repoRoot "IPs\ip_ir_array\src\ir_array_top_axi.sv"),
    (Join-Path $repoRoot "IPs\ip_ir_array\src\ir_stream_array_top.sv"),
    (Join-Path $repoRoot "software\ps_ps_loopback\src\main.c")
)
$scanText = ""
foreach ($path in $scanFiles) {
    if (Test-Path -LiteralPath $path) {
        $scanText += "`n" + (Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue)
    }
}
$loopbackInterfacePresent = [bool]($scanText -match "REG_LOOPBACK_MODE|loopback_mode")
$faultInterfacePresent = [bool]($scanText -match "fault_drop_|fault_crc_|fault_disable_|fault_force_retry|REG_FAULT|fault_injection")

Write-TextFile -Path $capabilityLog -Lines @(
    "SINGLE_BOARD_CAPABILITY_SCAN_BEGIN",
    "LOOPBACK_MODE_REGISTER_PRESENT=$([int]$loopbackInterfacePresent)",
    "FAULT_INJECTION_REGISTER_PRESENT=$([int]$faultInterfacePresent)",
    "SCAN_FILES=$($scanFiles -join ';')",
    "BOUNDARY=static_source_scan_only_no_hardware",
    "SINGLE_BOARD_CAPABILITY_SCAN_END"
)

$envObj = [ordered]@{
    timestamp = (Get-Date -Format o)
    repo_root = $repoRoot
    report_dir = $LogDir
    apply = [bool]$Apply.IsPresent
    com_port = $ComPort
    baud_rate = $BaudRate
    loopback_mode = $LoopbackMode
    payload_sizes = $PayloadSizeList
    lane_repeat = $LaneRepeat
    two_lane_repeat = $TwoLaneRepeat
    stress_repeat = $StressRepeat
    stress_seconds = $StressSeconds
    session_id = $SessionId
    operator_mode = $OperatorMode
    enable_fault_injection = [bool]$EnableFaultInjection.IsPresent
    target_plan_copied = [bool]$targetCopied
    project_constraints_copied = [bool]$constraintCopied
    workspace_bit = $workspaceBit
    workspace_bit_sha256 = (Get-HashOrMissing -Path $workspaceBit)
    workspace_elf = $workspaceElf
    workspace_elf_sha256_before = (Get-HashOrMissing -Path $workspaceElf)
    operator_elf = $OperatorElfPath
    operator_elf_sha256 = (Get-HashOrMissing -Path $OperatorElfPath)
}
$envObj | ConvertTo-Json -Depth 5 | Out-File -LiteralPath $envPath -Encoding utf8

$mode = if ($Apply.IsPresent) { "APPLY" } else { "DRY_RUN" }
$autoGate = "DRY_RUN_READY"
$finalShutdownExit = "NOT_REQUIRED_DRY_RUN"
$hostExit = "NOT_RUN"
$xsctExit = "NOT_RUN"
$operatorObj = $null
$runFailure = ""

try {
    if (-not $Apply.IsPresent) {
        Write-TextFile -Path $safeGateLog -Lines @(
            "DRY_RUN_NO_PREFLIGHT=1",
            "DRY_RUN_NO_FPGA_PROGRAMMING=1",
            "DRY_RUN_NO_PS_ELF_STARTED=1",
            "DRY_RUN_NO_TFDU_DRIVE=1"
        )
        $dryExit = Invoke-LoggedProcess `
            -FilePath "python.exe" `
            -Arguments @(
                $operatorTool,
                "--dry-run",
                "--mode", $OperatorMode,
                "--port", $ComPort,
                "--baud", [string]$BaudRate,
                "--payload-sizes", ($PayloadSizeList -join ","),
                "--lane-repeat", [string]$LaneRepeat,
                "--two-lane-repeat", [string]$TwoLaneRepeat,
                "--stress-repeat", [string]$StressRepeat,
                "--stress-seconds", [string]$StressSeconds,
                "--session", $SessionId,
                "--transcript", $operatorTranscript,
                "--log-dir", $LogDir,
                "--summary-json", $operatorSummaryJson
            ) `
            -StdoutPath $operatorOutLog `
            -StderrPath $operatorErrLog `
            -TimeoutSeconds 60
        $hostExit = [string]$dryExit
    } else {
        $requiredPaths = @(
            $VivadoPath,
            $XsctPath,
            $preflightScript,
            $shutdownTcl,
            $runTcl,
            $operatorTool,
            $checkerTool,
            $workspaceBit,
            $workspaceElf,
            $OperatorElfPath
        )
        foreach ($path in $requiredPaths) {
            if (-not (Test-Path -LiteralPath $path)) {
                throw "Required path is missing: $path"
            }
        }

        if (-not $SkipPreflight.IsPresent) {
            $preflightExit = Invoke-LoggedProcess `
                -FilePath "powershell.exe" `
                -Arguments @(
                    "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", $preflightScript,
                    "-ComPort", $ComPort,
                    "-VivadoPath", $VivadoPath,
                    "-HwServerUrl", $HwServerUrl,
                    "-JtagFrequencyHz", [string]$JtagFrequencyHz
                ) `
                -StdoutPath $safeGateLog `
                -StderrPath $safeGateErr `
                -TimeoutSeconds 180
            $preflightText = Get-Content -LiteralPath $safeGateLog -Raw -ErrorAction SilentlyContinue
            if ($preflightExit -eq 0 -and
                $preflightText -match "COM_PORT_PRESENT=1" -and
                $preflightText -match "VIVADO_PREFLIGHT_EXIT=0" -and
                $preflightText -match "HW_PREFLIGHT_ZYNQ" -and
                $preflightText -match "HW_PREFLIGHT_RESULT PASS") {
                $autoGate = "1"
            } else {
                $autoGate = "0"
                throw "preflight failed; no test hardware programming attempted"
            }
        } else {
            Write-TextFile -Path $safeGateLog -Lines @("PREFLIGHT_SKIPPED=1")
            $autoGate = "SKIPPED"
        }

        $initialShutdownExit = Invoke-LoggedProcess `
            -FilePath $VivadoPath `
            -Arguments @("-mode", "batch", "-notrace", "-source", $shutdownTcl) `
            -StdoutPath $initialShutdownLog `
            -StderrPath $initialShutdownErr `
            -TimeoutSeconds 180
        if ($initialShutdownExit -ne 0) {
            $finalShutdownExit = [string]$initialShutdownExit
            throw "initial TFDU shutdown failed; no test bitstream programmed"
        }

        $hostProc = $null
        try {
            Copy-Item -LiteralPath $workspaceElf -Destination $backupElf -Force
            Copy-Item -LiteralPath $OperatorElfPath -Destination $workspaceElf -Force

            $hostProc = Start-Process -FilePath "python.exe" `
                -ArgumentList @(
                    $operatorTool,
                    "--apply",
                    "--mode", $OperatorMode,
                    "--port", $ComPort,
                    "--baud", [string]$BaudRate,
                    "--payload-sizes", ($PayloadSizeList -join ","),
                    "--lane-repeat", [string]$LaneRepeat,
                    "--two-lane-repeat", [string]$TwoLaneRepeat,
                    "--stress-repeat", [string]$StressRepeat,
                    "--stress-seconds", [string]$StressSeconds,
                    "--session", $SessionId,
                    "--transcript", $operatorTranscript,
                    "--log-dir", $LogDir,
                    "--summary-json", $operatorSummaryJson
                ) `
                -WorkingDirectory $repoRoot `
                -RedirectStandardOutput $operatorOutLog `
                -RedirectStandardError $operatorErrLog `
                -WindowStyle Hidden `
                -PassThru
            Start-Sleep -Seconds 1

            $xsctExit = Invoke-LoggedProcess `
                -FilePath $XsctPath `
                -Arguments @($runTcl) `
                -StdoutPath $xsctOutLog `
                -StderrPath $xsctErrLog `
                -TimeoutSeconds $XsctWaitSeconds

            $hostDone = $hostProc.WaitForExit($HostWaitSeconds * 1000)
            if (-not $hostDone) {
                Stop-Process -Id $hostProc.Id -Force -ErrorAction SilentlyContinue
                $hostExit = "124"
            } else {
                $hostProc.Refresh()
                if ($null -eq $hostProc.ExitCode) {
                    $hostExit = "UNKNOWN"
                } else {
                    $hostExit = [string]$hostProc.ExitCode
                }
            }
        } finally {
            if ($hostProc -and -not $hostProc.HasExited) {
                Stop-Process -Id $hostProc.Id -Force -ErrorAction SilentlyContinue
            }
            $shutdownExit = Invoke-LoggedProcess `
                -FilePath $VivadoPath `
                -Arguments @("-mode", "batch", "-notrace", "-source", $shutdownTcl) `
                -StdoutPath $finalShutdownLog `
                -StderrPath $finalShutdownErr `
                -TimeoutSeconds 180
            $finalShutdownExit = [string]$shutdownExit
            if (Test-Path -LiteralPath $backupElf) {
                Copy-Item -LiteralPath $backupElf -Destination $workspaceElf -Force
            }
        }
    }
} catch {
    $runFailure = $_.Exception.Message
    if (-not (Test-Path -LiteralPath $finalShutdownLog)) {
        Write-TextFile -Path $finalShutdownLog -Lines @("FINAL_SHUTDOWN_NOT_RUN_OR_NOT_REQUIRED=1", "RUN_FAILURE=$runFailure")
    }
}

if (Test-Path -LiteralPath $operatorSummaryJson) {
    try {
        $operatorObj = Get-Content -LiteralPath $operatorSummaryJson -Raw | ConvertFrom-Json
    } catch {
        $operatorObj = $null
        $runFailure = "operator summary JSON parse failed: $($_.Exception.Message)"
    }
}

$registerGate = To-StatusValue (Get-JsonValue $operatorObj "PS_PL_REGISTER_STATUS_AUTO_PASS" "0")
$lane0Pass = To-StatusValue (Get-JsonValue $operatorObj "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS" "0")
$lane1Pass = To-StatusValue (Get-JsonValue $operatorObj "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS" "0")
$twoLanePass = To-StatusValue (Get-JsonValue $operatorObj "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS" "0")
$stressPass = To-StatusValue (Get-JsonValue $operatorObj "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS" "0")
$shortStressPass = To-StatusValue (Get-JsonValue $operatorObj "SINGLE_BOARD_2LANE_SHORT_STRESS_PASS" $stressPass)
$noTxPass = To-StatusValue (Get-JsonValue $operatorObj "NO_TX_DATA_SENT_DURING_REGISTER_PHASE" "0")
$clearCountersPass = To-StatusValue (Get-JsonValue $operatorObj "CLEAR_COUNTERS_PASS" "0")
$clearErrorPass = To-StatusValue (Get-JsonValue $operatorObj "CLEAR_ERROR_PASS" "0")
$idleAfterClear = To-StatusValue (Get-JsonValue $operatorObj "STATUS_IDLE_AFTER_CLEAR" "0")
$operatorShutdownPass = To-StatusValue (Get-JsonValue $operatorObj "OPERATOR_SHUTDOWN_PASS" "0")

if (-not $Apply.IsPresent) {
    $registerGate = "DRY_RUN_READY"
    $lane0Pass = "DRY_RUN_READY"
    $lane1Pass = "DRY_RUN_READY"
    $twoLanePass = "DRY_RUN_READY"
    $stressPass = "DRY_RUN_READY"
    $shortStressPass = "DRY_RUN_READY"
    $noTxPass = "DRY_RUN_READY"
    $clearCountersPass = "DRY_RUN_READY"
    $clearErrorPass = "DRY_RUN_READY"
    $idleAfterClear = "DRY_RUN_READY"
    $operatorShutdownPass = "NOT_REQUIRED_DRY_RUN"
}

$plInternalStatus = if ($loopbackInterfacePresent) { "NOT_RUN_EXISTING_PATH_SCOPE" } else { "BLOCKED_MISSING_PL_INTERNAL_INTERFACE" }
$faultStatus = if ($faultInterfacePresent) { "NOT_RUN_EXISTING_PATH_SCOPE" } else { "BLOCKED_MISSING_FAULT_INJECTION_INTERFACE" }
$dryRunNoHardware = if ($Apply.IsPresent) { 0 } else { 1 }

Add-Flag "SINGLE_BOARD_ACCEPTANCE_MODE=$mode"
Add-Flag "SINGLE_BOARD_ACCEPTANCE_REPORT_DIR=$LogDir"
Add-Flag "NO_MANUAL_GATE_USED=1"
Add-Flag "MANUAL_OBSERVATION_NOT_REQUIRED=1"
Add-Flag "DRY_RUN_NO_HARDWARE_ACTION=$dryRunNoHardware"
Add-Flag "SINGLE_BOARD_AUTO_SAFE_GATE_PASS=$autoGate"
Add-Flag "PS_PL_REGISTER_STATUS_AUTO_PASS=$registerGate"
Add-Flag "NO_TX_DATA_SENT_DURING_REGISTER_PHASE=$noTxPass"
Add-Flag "CLEAR_COUNTERS_PASS=$clearCountersPass"
Add-Flag "CLEAR_ERROR_PASS=$clearErrorPass"
Add-Flag "STATUS_IDLE_AFTER_CLEAR=$idleAfterClear"
Add-Flag "LOOPBACK_MODE_REGISTER_PRESENT=$([int]$loopbackInterfacePresent)"
Add-Flag "FAULT_INJECTION_REGISTER_PRESENT=$([int]$faultInterfacePresent)"
Add-Flag "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS=$lane0Pass"
Add-Flag "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS=$lane1Pass"
Add-Flag "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS=$twoLanePass"
Add-Flag "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS=$stressPass"
Add-Flag "SINGLE_BOARD_2LANE_SHORT_STRESS_PASS=$shortStressPass"
Add-Flag "SINGLE_BOARD_2LANE_PL_INTERNAL_LOOPBACK_PASS=$plInternalStatus"
Add-Flag "SINGLE_BOARD_FAULT_INJECTION_PASS=$faultStatus"
Add-Flag "OPERATOR_SHUTDOWN_PASS=$operatorShutdownPass"
Add-Flag "XSCT_EXIT=$xsctExit"
Add-Flag "HOST_EXIT=$hostExit"
Add-Flag "FINAL_SHUTDOWN_EXIT=$finalShutdownExit"
Add-Flag "REAL_EXTERNAL_TFDU_OPTICAL_LINK_PASS=NOT_CLAIMED"
Add-Flag "REAL_BOARD_TCP_DHCP_PASS=BLOCKED_NO_ETHERNET"
Add-Flag "REAL_TWO_BOARD_END_TO_END_PASS=NOT_APPLICABLE_SINGLE_BOARD"
Add-Flag "ROTATION_600RPM_2H_PASS=BLOCKED_NO_ROTATION_TEST"
Add-Flag "8LANE_RATE_ACCEPTANCE_PASS=NOT_CLAIMED_2LANE_ONLY"
Add-Flag "FINAL_TARGET_PASS=0"
if (-not [string]::IsNullOrWhiteSpace($runFailure)) {
    Add-Flag "RUN_FAILURE=$runFailure"
}

Write-PlaceholderIfMissing -Path (Join-Path $LogDir "02_register_status_no_tx.log") -Line "PS_PL_REGISTER_STATUS_AUTO_PASS=$registerGate"
Write-PlaceholderIfMissing -Path (Join-Path $LogDir "03_lane0_existing_path_roundtrip.log") -Line "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS=$lane0Pass"
Write-PlaceholderIfMissing -Path (Join-Path $LogDir "04_lane1_existing_path_roundtrip.log") -Line "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS=$lane1Pass"
Write-PlaceholderIfMissing -Path (Join-Path $LogDir "05_2lane_existing_path_roundtrip.log") -Line "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS=$twoLanePass"
Write-PlaceholderIfMissing -Path (Join-Path $LogDir "06_2lane_existing_path_short_stress.log") -Line "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS=$stressPass"
Write-PlaceholderIfMissing -Path $finalShutdownLog -Line "SHUTDOWN_NOT_REQUIRED_FOR_DRY_RUN=1"
Write-TextFile -Path (Join-Path $LogDir "07_fault_injection.log") -Lines @("SINGLE_BOARD_FAULT_INJECTION_PASS=$faultStatus")
Write-TextFile -Path (Join-Path $LogDir "08_scope_boundary.log") -Lines @(
    "SINGLE_BOARD_2LANE_PL_INTERNAL_LOOPBACK_PASS=$plInternalStatus",
    "REAL_EXTERNAL_TFDU_OPTICAL_LINK_PASS=NOT_CLAIMED",
    "REAL_BOARD_TCP_DHCP_PASS=BLOCKED_NO_ETHERNET",
    "ROTATION_600RPM_2H_PASS=BLOCKED_NO_ROTATION_TEST",
    "FINAL_TARGET_PASS=0"
)

$summaryObj = [ordered]@{
    SINGLE_BOARD_AUTO_SAFE_GATE_PASS = $autoGate
    PS_PL_REGISTER_STATUS_AUTO_PASS = $registerGate
    NO_TX_DATA_SENT_DURING_REGISTER_PHASE = $noTxPass
    CLEAR_COUNTERS_PASS = $clearCountersPass
    CLEAR_ERROR_PASS = $clearErrorPass
    STATUS_IDLE_AFTER_CLEAR = $idleAfterClear
    SINGLE_BOARD_LANE0_EXISTING_PATH_PASS = $lane0Pass
    SINGLE_BOARD_LANE1_EXISTING_PATH_PASS = $lane1Pass
    SINGLE_BOARD_2LANE_EXISTING_PATH_PASS = $twoLanePass
    SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS = $stressPass
    SINGLE_BOARD_2LANE_SHORT_STRESS_PASS = $shortStressPass
    SINGLE_BOARD_2LANE_PL_INTERNAL_LOOPBACK_PASS = $plInternalStatus
    SINGLE_BOARD_FAULT_INJECTION_PASS = $faultStatus
    REAL_BOARD_TCP_DHCP_PASS = "BLOCKED_NO_ETHERNET"
    ROTATION_600RPM_2H_PASS = "BLOCKED_NO_ROTATION_TEST"
    REAL_EXTERNAL_TFDU_OPTICAL_LINK_PASS = "NOT_CLAIMED"
    FINAL_TARGET_PASS = 0
    FINAL_SHUTDOWN_EXIT = $finalShutdownExit
    report_dir = $LogDir
    operator_summary_json = $operatorSummaryJson
    operator_elf = $OperatorElfPath
    operator_elf_sha256 = (Get-HashOrMissing -Path $OperatorElfPath)
    workspace_bit_sha256 = (Get-HashOrMissing -Path $workspaceBit)
    xsct_exit = $xsctExit
    host_exit = $hostExit
    run_failure = $runFailure
}
$summaryObj | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $summaryJsonPath -Encoding utf8

Write-TextFile -Path (Join-Path $LogDir "12_counters.csv") -Lines @(
    "phase,status,evidence",
    "register_status,$registerGate,02_register_status_no_tx.log",
    "lane0_existing_path,$lane0Pass,03_lane0_existing_path_roundtrip.log",
    "lane1_existing_path,$lane1Pass,04_lane1_existing_path_roundtrip.log",
    "2lane_existing_path,$twoLanePass,05_2lane_existing_path_roundtrip.log",
    "2lane_short_stress,$stressPass,06_2lane_existing_path_short_stress.log"
)
Write-TextFile -Path (Join-Path $LogDir "13_payload_matrix.csv") -Lines @(
    "phase,payload_bytes,repeat_or_seconds,status",
    ($PayloadSizeList | ForEach-Object {
        $repeat = if ([int]$_ -ge 256) { 50 } else { $StressRepeat }
        "2lane_short_stress,$_,count=$repeat,$stressPass"
    }),
    "2lane_short_stress,16,seconds=$StressSeconds,$stressPass"
)
Write-TextFile -Path (Join-Path $LogDir "14_fault_matrix.csv") -Lines @(
    "case,injection,status",
    "fault_injection_interface,register_scan,$faultStatus",
    "rx_dma_synth_optional,not_run_existing_path_scope,NOT_CLAIMED"
)

Write-TextFile -Path $reportPath -Lines @(
    "# Single-board 2-lane existing-path next-step report",
    "",
    "Report dir: $LogDir",
    "",
    "## Status",
    "",
    '```text',
    "SINGLE_BOARD_AUTO_SAFE_GATE_PASS=$autoGate",
    "PS_PL_REGISTER_STATUS_AUTO_PASS=$registerGate",
    "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS=$lane0Pass",
    "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS=$lane1Pass",
    "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS=$twoLanePass",
    "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS=$stressPass",
    "SINGLE_BOARD_2LANE_SHORT_STRESS_PASS=$shortStressPass",
    "SINGLE_BOARD_2LANE_PL_INTERNAL_LOOPBACK_PASS=$plInternalStatus",
    "SINGLE_BOARD_FAULT_INJECTION_PASS=$faultStatus",
    "REAL_BOARD_TCP_DHCP_PASS=BLOCKED_NO_ETHERNET",
    "ROTATION_600RPM_2H_PASS=BLOCKED_NO_ROTATION_TEST",
    "REAL_EXTERNAL_TFDU_OPTICAL_LINK_PASS=NOT_CLAIMED",
    "FINAL_TARGET_PASS=0",
    "FINAL_SHUTDOWN_EXIT=$finalShutdownExit",
    '```',
    "",
    "## Boundary",
    "",
    "Under the current no-Ethernet and no-rotation constraints, this run targets reproducible UART/JTAG evidence for lane0, lane1, and 2-lane existing-path roundtrip. It does not claim final system acceptance, real Ethernet operation, real external TFDU optical link, or 600 rpm rotation qualification.",
    "",
    "## Evidence Files",
    "",
    '- `01_safe_gate.log`',
    '- `02_register_status_no_tx.log`',
    '- `03_lane0_existing_path_roundtrip.log`',
    '- `04_lane1_existing_path_roundtrip.log`',
    '- `05_2lane_existing_path_roundtrip.log`',
    '- `06_2lane_existing_path_short_stress.log`',
    '- `summary.json`'
)

$shaLines = @()
foreach ($file in (Get-ChildItem -LiteralPath $LogDir -File | Where-Object { $_.Name -ne "SHA256SUMS.txt" } | Sort-Object Name)) {
    try {
        $hashValue = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
        $shaLines += "$hashValue  $($file.Name)"
    } catch {
        $shaLines += "HASH_ERROR  $($file.Name)"
    }
}
$shaLines | Out-File -LiteralPath (Join-Path $LogDir "SHA256SUMS.txt") -Encoding ascii

$gateErr = Join-Path $LogDir "15_gate_check.err.log"
$gateExit = Invoke-LoggedProcess `
    -FilePath "python.exe" `
    -Arguments @($checkerTool, $LogDir, "--out", $gateLog) `
    -StdoutPath (Join-Path $LogDir "15_gate_check.stdout.log") `
    -StderrPath $gateErr `
    -TimeoutSeconds 60

Write-Output "SINGLE_BOARD_ACCEPTANCE_REPORT_DIR=$LogDir"
Write-Output "SINGLE_BOARD_ACCEPTANCE_MODE=$mode"
Write-Output "PS_PL_REGISTER_STATUS_AUTO_PASS=$registerGate"
Write-Output "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS=$lane0Pass"
Write-Output "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS=$lane1Pass"
Write-Output "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS=$twoLanePass"
Write-Output "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS=$stressPass"
Write-Output "FINAL_SHUTDOWN_EXIT=$finalShutdownExit"
Write-Output "GATE_CHECK_EXIT=$gateExit"

exit $gateExit
