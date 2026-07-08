param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$ComPort = "COM3",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [string[]]$UsbInstanceIdPatterns = @("USB\VID_0403&PID_6014\*"),
    [switch]$Apply,
    [switch]$LaunchElevated,
    [switch]$SkipPowerPlan,
    [switch]$SkipUsbRestart,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "jtag_usb_soft_recover_$stamp.summary.txt"
$powerLog = Join-Path $reportsDir "jtag_usb_soft_recover_$stamp.power.log"
$restartLog = Join-Path $reportsDir "jtag_usb_soft_recover_$stamp.restart.log"
$preflightLog = Join-Path $reportsDir "jtag_usb_soft_recover_$stamp.preflight.log"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"

$usbSettingsGuid = "2a737441-1930-4402-8d77-b2bebba308a3"
$usbSelectiveSuspendGuid = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-Logged {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath
    )
    & $FilePath @Arguments *> $LogPath
    return $LASTEXITCODE
}

function Quote-Arg {
    param([string]$Text)
    if ($Text -match "[\s`"&|<>]") {
        return '"' + ($Text -replace '"', '\"') + '"'
    }
    return $Text
}

function Get-MatchingUsbInstances {
    $instances = @()
    $present = @(Get-PnpDevice -PresentOnly -ErrorAction Stop)
    foreach ($pattern in $UsbInstanceIdPatterns) {
        foreach ($dev in ($present | Where-Object { $_.InstanceId -like $pattern })) {
            $instances += $dev.InstanceId
        }
    }
    return @($instances | Sort-Object -Unique)
}

"JTAG_USB_SOFT_RECOVER_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "VIVADO_PATH=$VivadoPath"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "APPLY=$([int]$Apply.IsPresent)"
Write-SummaryLine "LAUNCH_ELEVATED=$([int]$LaunchElevated.IsPresent)"
Write-SummaryLine "SKIP_POWER_PLAN=$([int]$SkipPowerPlan.IsPresent)"
Write-SummaryLine "SKIP_USB_RESTART=$([int]$SkipUsbRestart.IsPresent)"
Write-SummaryLine "SKIP_PREFLIGHT=$([int]$SkipPreflight.IsPresent)"
Write-SummaryLine "USB_INSTANCE_ID_PATTERNS=$($UsbInstanceIdPatterns -join ',')"
Write-SummaryLine "SUMMARY_LOG=$summaryLog"
Write-SummaryLine "POWER_LOG=$powerLog"
Write-SummaryLine "RESTART_LOG=$restartLog"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"

$isAdmin = Test-IsAdmin
Write-SummaryLine "IS_ADMIN=$([int]$isAdmin)"

if ($LaunchElevated) {
    $elevatedArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $PSCommandPath,
        "-VivadoPath",
        $VivadoPath,
        "-ComPort",
        $ComPort,
        "-HwServerUrl",
        $HwServerUrl,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz,
        "-Apply",
        "-UsbInstanceIdPatterns"
    ) + $UsbInstanceIdPatterns
    if ($SkipPowerPlan) { $elevatedArgs += "-SkipPowerPlan" }
    if ($SkipUsbRestart) { $elevatedArgs += "-SkipUsbRestart" }
    if ($SkipPreflight) { $elevatedArgs += "-SkipPreflight" }

    $elevatedArgLine = (@($elevatedArgs) | ForEach-Object { Quote-Arg $_ }) -join ' '
    Write-SummaryLine "ELEVATED_COMMAND=powershell $elevatedArgLine"
    Start-Process -FilePath "powershell.exe" -ArgumentList $elevatedArgLine -WorkingDirectory $repoRoot -Verb RunAs -Wait
    Write-SummaryLine "ELEVATED_PROCESS_RETURNED=1"
    Write-SummaryLine "JTAG_USB_SOFT_RECOVER_END $(Get-Date -Format o)"
    exit 0
}

if (-not $Apply) {
    Write-SummaryLine "DRY_RUN=1"
    Write-SummaryLine "NO_SYSTEM_CHANGE_DONE=1"
    Write-SummaryLine "TO_LAUNCH_ELEVATED=powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\recover_jtag_usb_soft.ps1 -LaunchElevated"
    Write-SummaryLine "JTAG_USB_SOFT_RECOVER_END $(Get-Date -Format o)"
    exit 0
}

if (-not $SkipPowerPlan) {
    Write-SummaryLine "POWER_PLAN_FIX_START=$(Get-Date -Format o)"
    "POWER_PLAN_FIX_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $powerLog -Encoding utf8
    & powercfg /SETACVALUEINDEX SCHEME_CURRENT $usbSettingsGuid $usbSelectiveSuspendGuid 0 *>> $powerLog
    $acExit = $LASTEXITCODE
    & powercfg /SETDCVALUEINDEX SCHEME_CURRENT $usbSettingsGuid $usbSelectiveSuspendGuid 0 *>> $powerLog
    $dcExit = $LASTEXITCODE
    & powercfg /SETACTIVE SCHEME_CURRENT *>> $powerLog
    $activeExit = $LASTEXITCODE
    & powercfg /QUERY SCHEME_CURRENT $usbSettingsGuid $usbSelectiveSuspendGuid *>> $powerLog
    $queryExit = $LASTEXITCODE
    Write-SummaryLine "POWER_PLAN_SET_AC_EXIT=$acExit"
    Write-SummaryLine "POWER_PLAN_SET_DC_EXIT=$dcExit"
    Write-SummaryLine "POWER_PLAN_SETACTIVE_EXIT=$activeExit"
    Write-SummaryLine "POWER_PLAN_QUERY_EXIT=$queryExit"
}

if (-not $SkipUsbRestart) {
    if (-not $isAdmin) {
        Write-SummaryLine "USB_RESTART_BLOCKED_NOT_ADMIN=1"
        Write-SummaryLine "JTAG_USB_SOFT_RECOVER_END $(Get-Date -Format o)"
        exit 10
    }

    Write-SummaryLine "USB_RESTART_START=$(Get-Date -Format o)"
    "USB_RESTART_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $restartLog -Encoding utf8
    $instances = @(Get-MatchingUsbInstances)
    Write-SummaryLine "USB_RESTART_INSTANCE_COUNT=$($instances.Count)"
    foreach ($id in $instances) {
        Write-SummaryLine "USB_RESTART_INSTANCE=$id"
        $code = Invoke-Logged -FilePath "pnputil.exe" -Arguments @("/restart-device", $id) -LogPath ($restartLog + ".$(($id -replace '[\\/:*?""<>|&]', '_')).log")
        Write-SummaryLine "USB_RESTART_EXIT instance=$id exit=$code"
        Add-Content -LiteralPath $restartLog -Value "USB_RESTART_EXIT instance=$id exit=$code" -Encoding utf8
    }
}

if (-not $SkipPreflight -and (Test-Path -LiteralPath $preflightScript)) {
    Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
    $preflightExit = Invoke-Logged -FilePath "powershell.exe" -Arguments @(
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
    ) -LogPath $preflightLog
    Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
    if (Test-Path -LiteralPath $preflightLog) {
        foreach ($line in (Get-Content -LiteralPath $preflightLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_DEVICE_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT|COM_PORT_PRESENT|PNP_DEVICE"
        })) {
            Write-SummaryLine "PREFLIGHT_MATCH=$line"
        }
    }
}

Write-SummaryLine "JTAG_USB_SOFT_RECOVER_END $(Get-Date -Format o)"
