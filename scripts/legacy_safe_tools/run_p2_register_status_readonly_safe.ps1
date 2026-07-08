param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$XsctWaitSeconds = 90,
    [int]$HostWaitSeconds = 90,
    [switch]$Apply,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.summary.txt"
$preflightLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.preflight.log"
$hostOutLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.host.out.log"
$hostErrLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.host.err.log"
$xsctOutLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.xsct.out.log"
$xsctErrLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.xsct.err.log"
$shutdownOutLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.shutdown.out.log"
$shutdownErrLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.shutdown.err.log"
$shutdownLog = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.shutdown.log"
$transcript = Join-Path $reportsDir "p2_register_status_readonly_safe_$stamp.transcript.log"

$runTcl = Join-Path $repoRoot "software\ps_ps_loopback\run_on_hw.tcl"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$hostTool = Join-Path $repoRoot "tools\uart_operator_readonly_no_tx.py"
$workspaceBit = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$workspaceElf = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$operatorElf = Get-ChildItem -LiteralPath (Join-Path $repoRoot "deliverables\p2_uart_operator") -Filter "rf_comm_ps_ps_loopback_uart_operator_*.elf" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$backupElf = Join-Path $reportsDir "workspace_elf_before_p2_register_status_readonly_$stamp.elf"

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$StdoutPath,
        [string]$StderrPath,
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

function Get-HashOrMissing {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    }
    return "MISSING"
}

"P2_REGISTER_STATUS_READONLY_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "APPLY=$([int]$Apply.IsPresent)"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "HOST_TOOL=$hostTool"
Write-SummaryLine "TRANSCRIPT=$transcript"
Write-SummaryLine "NO_START_COMMAND_IN_HOST_PLAN=1"
Write-SummaryLine "NO_TEST_COMMAND_IN_HOST_PLAN=1"

foreach ($path in @($XsctPath, $VivadoPath, $runTcl, $shutdownTcl, $preflightScript, $hostTool, $workspaceBit, $workspaceElf)) {
    if (-not (Test-Path -LiteralPath $path)) {
        Write-SummaryLine "REQUIRED_PATH_MISSING=$path"
        Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=FAIL_REQUIRED_PATH_MISSING"
        Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
        exit 22
    }
}
if ($null -eq $operatorElf) {
    Write-SummaryLine "REQUIRED_PATH_MISSING=deliverables\\p2_uart_operator\\rf_comm_ps_ps_loopback_uart_operator_*.elf"
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=FAIL_OPERATOR_ELF_MISSING"
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
    exit 22
}

Write-SummaryLine "WORKSPACE_BIT=$workspaceBit"
Write-SummaryLine "WORKSPACE_BIT_SHA256=$(Get-HashOrMissing -Path $workspaceBit)"
Write-SummaryLine "WORKSPACE_ELF=$workspaceElf"
Write-SummaryLine "WORKSPACE_ELF_BEFORE_SHA256=$(Get-HashOrMissing -Path $workspaceElf)"
Write-SummaryLine "OPERATOR_ELF=$($operatorElf.FullName)"
Write-SummaryLine "OPERATOR_ELF_SHA256=$(Get-HashOrMissing -Path $operatorElf.FullName)"

if (-not $Apply.IsPresent) {
    $dryExit = Invoke-LoggedProcess `
        -FilePath "python.exe" `
        -Arguments @($hostTool, "--port", $ComPort, "--baud", [string]$BaudRate, "--transcript", $transcript, "--dry-run") `
        -StdoutPath $hostOutLog `
        -StderrPath $hostErrLog `
        -TimeoutSeconds 30
    Write-SummaryLine "DRY_RUN_HOST_EXIT=$dryExit"
    Write-SummaryLine "DRY_RUN_NO_FPGA_PROGRAMMING=1"
    Write-SummaryLine "DRY_RUN_NO_PS_ELF_STARTED=1"
    Write-SummaryLine "DRY_RUN_NO_TFDU_DRIVE=1"
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=DRY_RUN_READY"
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
    exit $dryExit
}

if (-not $SkipPreflight.IsPresent) {
    $preflightExit = Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments @(
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
        ) `
        -StdoutPath $preflightLog `
        -StderrPath ($preflightLog + ".err") `
        -TimeoutSeconds 180
    Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
    $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($preflightText -split "`r?`n") | Where-Object { $_ -match "COM_PORT_PRESENT|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT" })) {
        Write-SummaryLine "PREFLIGHT_MATCH=$line"
    }
    if ($preflightText -notmatch "HW_PREFLIGHT_RESULT PASS" -or $preflightText -notmatch "HW_PREFLIGHT_ZYNQ") {
        Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
        Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=FAIL_PREFLIGHT"
        Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
        exit 20
    }
}

$hostProc = $null
$shutdownExit = 125
try {
    Copy-Item -LiteralPath $workspaceElf -Destination $backupElf -Force
    Copy-Item -LiteralPath $operatorElf.FullName -Destination $workspaceElf -Force
    Write-SummaryLine "WORKSPACE_ELF_REPLACED_WITH_OPERATOR=1"
    Write-SummaryLine "WORKSPACE_ELF_OPERATOR_SHA256=$(Get-HashOrMissing -Path $workspaceElf)"

    $hostProc = Start-Process -FilePath "python.exe" `
        -ArgumentList @($hostTool, "--port", $ComPort, "--baud", [string]$BaudRate, "--transcript", $transcript) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $hostOutLog `
        -RedirectStandardError $hostErrLog `
        -WindowStyle Hidden `
        -PassThru
    Write-SummaryLine "HOST_STARTED_PID=$($hostProc.Id)"
    Start-Sleep -Seconds 1

    $xsctExit = Invoke-LoggedProcess `
        -FilePath $XsctPath `
        -Arguments @($runTcl) `
        -StdoutPath $xsctOutLog `
        -StderrPath $xsctErrLog `
        -TimeoutSeconds $XsctWaitSeconds
    Write-SummaryLine "XSCT_EXIT=$xsctExit"

    $hostDone = $hostProc.WaitForExit($HostWaitSeconds * 1000)
    if (-not $hostDone) {
        Stop-Process -Id $hostProc.Id -Force -ErrorAction SilentlyContinue
        Write-SummaryLine "HOST_TIMEOUT_KILLED=1"
        $hostExit = 124
    } else {
        $hostProc.Refresh()
        $hostExit = $hostProc.ExitCode
    }
    Write-SummaryLine "HOST_EXIT=$hostExit"
} finally {
    if ($hostProc -and -not $hostProc.HasExited) {
        Stop-Process -Id $hostProc.Id -Force -ErrorAction SilentlyContinue
    }

    $shutdownExit = Invoke-LoggedProcess `
        -FilePath $VivadoPath `
        -Arguments @("-mode", "batch", "-notrace", "-source", $shutdownTcl) `
        -StdoutPath $shutdownOutLog `
        -StderrPath $shutdownErrLog `
        -TimeoutSeconds 180
    Write-SummaryLine "SHUTDOWN_EXIT=$shutdownExit"
    @(
        "STDOUT:"
        if (Test-Path -LiteralPath $shutdownOutLog) { Get-Content -LiteralPath $shutdownOutLog -ErrorAction SilentlyContinue }
        "STDERR:"
        if (Test-Path -LiteralPath $shutdownErrLog) { Get-Content -LiteralPath $shutdownErrLog -ErrorAction SilentlyContinue }
    ) | Out-File -LiteralPath $shutdownLog -Encoding ascii

    if (Test-Path -LiteralPath $backupElf) {
        Copy-Item -LiteralPath $backupElf -Destination $workspaceElf -Force
        Write-SummaryLine "WORKSPACE_ELF_RESTORED=1"
        Write-SummaryLine "WORKSPACE_ELF_AFTER_RESTORE_SHA256=$(Get-HashOrMissing -Path $workspaceElf)"
    }
}

if (Test-Path -LiteralPath $transcript) {
    $transcriptText = Get-Content -LiteralPath $transcript -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($transcriptText -split "`r?`n") | Where-Object { $_ -match "UART_OPERATOR_READONLY_NO_TX|CHECK |UARTOP_RESULT command=(STATUS|READ|DUMP|CLEAR|SHUTDOWN)" })) {
        Write-SummaryLine "TRANSCRIPT_MATCH=$line"
    }
}
if ($shutdownExit -ne 0) {
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=FAIL_SHUTDOWN"
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
    exit 50
}
if ($xsctExit -ne 0) {
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=FAIL_XSCT"
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
    exit $xsctExit
}
if ($hostExit -ne 0) {
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=FAIL_HOST"
    Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
    exit $hostExit
}

Write-SummaryLine "P2_REGISTER_STATUS_READONLY_RESULT=PASS_NO_TX"
Write-SummaryLine "P2_REGISTER_STATUS_READONLY_SAFE_END $(Get-Date -Format o)"
exit 0
