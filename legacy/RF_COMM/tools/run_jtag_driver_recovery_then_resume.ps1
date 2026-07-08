param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [string[]]$TriggerModes = @("a_tx_lane0", "a_tx_lane1", "b_tx_lane0", "b_tx_lane1"),
    [int]$JtagFrequencyHz = 1000000,
    [int]$MatrixTimeoutSeconds = 1200,
    [int]$PerRunTimeoutSeconds = 480,
    [int]$MaxTfduWindowSeconds = 300,
    [switch]$Apply,
    [switch]$InstallPcUsb,
    [switch]$InstallDigilent,
    [switch]$UseFullXilinxInstaller,
    [switch]$LaunchElevated,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "jtag_recovery_then_resume_$stamp.summary.txt"
$repairLog = Join-Path $reportsDir "jtag_recovery_then_resume_$stamp.repair.log"
$resumeLog = Join-Path $reportsDir "jtag_recovery_then_resume_$stamp.resume.log"

$repairScript = Join-Path $repoRoot "tools\repair_jtag_drivers_admin.ps1"
$resumeScript = Join-Path $repoRoot "tools\run_p1_lane_mapping_matrix_safe.ps1"

foreach ($path in @($repairScript, $resumeScript, $VivadoPath, $XsctPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
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
        return 0
    }
    return $proc.ExitCode
}

function Normalize-List {
    param([string[]]$Items)
    $out = @()
    foreach ($item in $Items) {
        foreach ($part in ($item -split ",")) {
            $trimmed = $part.Trim()
            if ($trimmed -ne "") {
                $out += $trimmed
            }
        }
    }
    return $out
}

function Quote-Arg {
    param([string]$Text)
    if ($Text -match "[\s`"]") {
        return '"' + ($Text -replace '"', '\"') + '"'
    }
    return $Text
}

$modes = Normalize-List -Items $TriggerModes
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

"JTAG_RECOVERY_THEN_RESUME_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "PER_RUN_TIMEOUT_SECONDS=$PerRunTimeoutSeconds"
Write-SummaryLine "MAX_TFDU_WINDOW_SECONDS=$MaxTfduWindowSeconds"
Write-SummaryLine "TRIGGER_MODES=$($modes -join ',')"
Write-SummaryLine "APPLY=$([int]$Apply.IsPresent)"
Write-SummaryLine "LAUNCH_ELEVATED=$([int]$LaunchElevated.IsPresent)"
Write-SummaryLine "IS_ADMIN=$([int]$isAdmin)"
Write-SummaryLine "REPAIR_LOG=$repairLog"
Write-SummaryLine "RESUME_LOG=$resumeLog"
Write-SummaryLine "NO_FPGA_PROGRAMMING_BEFORE_RESUME_PREFLIGHT=1"
Write-SummaryLine "NO_TFDU_DRIVE_BEFORE_RESUME_PREFLIGHT=1"

if (-not $InstallPcUsb -and -not $InstallDigilent -and -not $UseFullXilinxInstaller) {
    $InstallPcUsb = $true
    $InstallDigilent = $true
    Write-SummaryLine "DEFAULT_DRIVER_ACTION=InstallPcUsb,InstallDigilent"
}

$repairArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $repairScript,
    "-VivadoPath",
    $VivadoPath,
    "-ComPort",
    $ComPort,
    "-HwServerUrl",
    $HwServerUrl,
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz
)
if ($Apply) { $repairArgs += "-Apply" }
if ($InstallPcUsb) { $repairArgs += "-InstallPcUsb" }
if ($InstallDigilent) { $repairArgs += "-InstallDigilent" }
if ($UseFullXilinxInstaller) { $repairArgs += "-UseFullXilinxInstaller" }

$resumeArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $resumeScript,
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
    "-PerRunTimeoutSeconds",
    [string]$PerRunTimeoutSeconds,
    "-MaxTfduWindowSeconds",
    [string]$MaxTfduWindowSeconds,
    "-TriggerModes"
    ($modes -join ",")
)
if ($StopOnFail) { $resumeArgs += "-StopOnFail" }

Write-SummaryLine "REPAIR_COMMAND=powershell $((@($repairArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "RESUME_COMMAND=powershell $((@($resumeArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"

if ($LaunchElevated) {
    $elevatedArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $PSCommandPath,
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
        "-MatrixTimeoutSeconds",
        [string]$MatrixTimeoutSeconds,
        "-PerRunTimeoutSeconds",
        [string]$PerRunTimeoutSeconds,
        "-MaxTfduWindowSeconds",
        [string]$MaxTfduWindowSeconds,
        "-Apply",
        "-StopOnFail"
    )
    if ($InstallPcUsb) { $elevatedArgs += "-InstallPcUsb" }
    if ($InstallDigilent) { $elevatedArgs += "-InstallDigilent" }
    if ($UseFullXilinxInstaller) { $elevatedArgs += "-UseFullXilinxInstaller" }
    $elevatedArgs += "-TriggerModes"
    $elevatedArgs += ($modes -join ",")

    Write-SummaryLine "ELEVATED_LAUNCH_REQUESTED=1"
    Write-SummaryLine "ELEVATED_COMMAND=powershell $((@($elevatedArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
    Start-Process -FilePath "powershell.exe" -ArgumentList $elevatedArgs -Verb RunAs
    Write-SummaryLine "ELEVATED_LAUNCH_SENT=1"
    Write-SummaryLine "JTAG_RECOVERY_THEN_RESUME_END $(Get-Date -Format o)"
    exit 0
}

if (-not $Apply) {
    Write-SummaryLine "DRY_RUN=1"
    Write-SummaryLine "NO_SYSTEM_DRIVER_CHANGE_DONE=1"
    Write-SummaryLine "NO_RESUME_RUN_DONE=1"
    Write-SummaryLine "TO_RUN_ELEVATED=powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_jtag_driver_recovery_then_resume.ps1 -Apply -InstallPcUsb -InstallDigilent -StopOnFail -TriggerModes a_tx_lane0,a_tx_lane1,b_tx_lane0,b_tx_lane1"
    Write-SummaryLine "TO_LAUNCH_ELEVATED=powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_jtag_driver_recovery_then_resume.ps1 -LaunchElevated -InstallPcUsb -InstallDigilent -TriggerModes a_tx_lane0,a_tx_lane1,b_tx_lane0,b_tx_lane1"
    Write-SummaryLine "JTAG_RECOVERY_THEN_RESUME_END $(Get-Date -Format o)"
    exit 0
}

if (-not $isAdmin) {
    Write-SummaryLine "APPLY_BLOCKED_NOT_ADMIN=1"
    Write-SummaryLine "NO_SYSTEM_DRIVER_CHANGE_DONE=1"
    Write-SummaryLine "NO_RESUME_RUN_DONE=1"
    Write-SummaryLine "JTAG_RECOVERY_THEN_RESUME_END $(Get-Date -Format o)"
    exit 10
}

Write-SummaryLine "REPAIR_START=$(Get-Date -Format o)"
$repairExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $repairArgs -LogPath $repairLog -TimeoutSeconds 240
Write-SummaryLine "REPAIR_EXIT=$repairExit"
if (Test-Path -LiteralPath $repairLog) {
    foreach ($line in (Get-Content -LiteralPath $repairLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "APPLY|INSTALL_|EXIT|FAIL|PREFLIGHT|NO_SYSTEM|NO_FPGA|NO_TFDU|JTAG_DRIVER_REPAIR_END"
    })) {
        Write-SummaryLine "REPAIR_MATCH=$line"
    }
}
if ($repairExit -ne 0) {
    Write-SummaryLine "RESUME_SKIPPED_REPAIR_FAILED=1"
    Write-SummaryLine "JTAG_RECOVERY_THEN_RESUME_END $(Get-Date -Format o)"
    exit $repairExit
}

Write-SummaryLine "RESUME_START=$(Get-Date -Format o)"
$resumeExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $resumeArgs -LogPath $resumeLog -TimeoutSeconds ($MatrixTimeoutSeconds + 300)
Write-SummaryLine "RESUME_EXIT=$resumeExit"
$resumeText = ""
if (Test-Path -LiteralPath $resumeLog) {
    $resumeText = Get-Content -LiteralPath $resumeLog -Raw -ErrorAction SilentlyContinue
    if ($null -eq $resumeText) {
        $resumeText = ""
    }
    foreach ($line in (($resumeText -split "`r?`n") | Where-Object {
        $_ -match "ARTIFACT_GUARD|PREFLIGHT_|MATRIX_|RUN_RESULT|RUN_DIAGNOSTIC|RUN_ILA_TIMEOUT|RUN_MISSING_ILA_CSV|P1_LANE_MAPPING|LANE2_MATRIX_SAFE_END"
    })) {
        Write-SummaryLine "RESUME_MATCH=$line"
    }
}
$resumeEffectiveMatch = [regex]::Match($resumeText, "(?m)^MATRIX_EFFECTIVE_EXIT=(\d+)\b")
if ($resumeExit -eq 0 -and $resumeEffectiveMatch.Success) {
    $resumeEffective = [int]$resumeEffectiveMatch.Groups[1].Value
    if ($resumeEffective -ne 0) {
        $resumeExit = $resumeEffective
    }
}
Write-SummaryLine "RESUME_EFFECTIVE_EXIT=$resumeExit"

Write-SummaryLine "JTAG_RECOVERY_THEN_RESUME_END $(Get-Date -Format o)"
exit $resumeExit
