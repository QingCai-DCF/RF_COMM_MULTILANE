param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$ComPort = "COM3",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [switch]$Apply,
    [switch]$InstallPcUsb,
    [switch]$InstallDigilent,
    [switch]$UseFullXilinxInstaller,
    [switch]$SkipScanDevices,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "jtag_driver_repair_$stamp.summary.txt"
$deviceLogBefore = Join-Path $reportsDir "jtag_driver_repair_$stamp.devices_before.log"
$driverLogBefore = Join-Path $reportsDir "jtag_driver_repair_$stamp.drivers_before.log"
$deviceLogAfter = Join-Path $reportsDir "jtag_driver_repair_$stamp.devices_after.log"
$driverLogAfter = Join-Path $reportsDir "jtag_driver_repair_$stamp.drivers_after.log"
$diagLog = Join-Path $reportsDir "jtag_driver_repair_$stamp.diag_after.log"
$preflightLog = Join-Path $reportsDir "jtag_driver_repair_$stamp.preflight_after.log"

$driverRoot = "D:\Xilinx\Vivado\2023.1\data\xicom\cable_drivers\nt64"
$installDriversCmd = Join-Path $driverRoot "install_drivers.cmd"
$xpcInstallCmd = Join-Path $driverRoot "dlc10_win10\install_xpcwinusb.cmd"
$digilentInstaller = Join-Path $driverRoot "digilent\install_digilent.exe"
$xilinxInstallLog = Join-Path $reportsDir "jtag_driver_repair_$stamp.xilinx_install.log"
$pcusbInstallLog = Join-Path $reportsDir "jtag_driver_repair_$stamp.pcusb_install.log"
$digilentInstallLog = Join-Path $reportsDir "jtag_driver_repair_$stamp.digilent_install.log"
$scanLog = Join-Path $reportsDir "jtag_driver_repair_$stamp.scan_devices.log"

$diagScript = Join-Path $repoRoot "tools\diagnose_jtag_usb.ps1"
$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
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

function Write-DriverSnapshot {
    param(
        [string]$DevicesPath,
        [string]$DriversPath,
        [string]$Prefix
    )
    $devExit = Invoke-Logged -FilePath "pnputil.exe" -Arguments @("/enum-devices", "/connected") -LogPath $DevicesPath
    Write-SummaryLine "${Prefix}_DEVICES_EXIT=$devExit"
    if (Test-Path -LiteralPath $DevicesPath) {
        $deviceText = Get-Content -LiteralPath $DevicesPath -Raw -ErrorAction SilentlyContinue
        foreach ($pattern in @("VID_0403", "VID_03FD", "VID_10C4", "Digilent", "Xilinx", "USB Serial Converter", "CP210")) {
            $count = ([regex]::Matches($deviceText, [regex]::Escape($pattern), "IgnoreCase")).Count
            Write-SummaryLine "${Prefix}_DEVICE_MATCH pattern=$pattern count=$count"
        }
    }

    $drvExit = Invoke-Logged -FilePath "pnputil.exe" -Arguments @("/enum-drivers") -LogPath $DriversPath
    Write-SummaryLine "${Prefix}_DRIVERS_EXIT=$drvExit"
    if (Test-Path -LiteralPath $DriversPath) {
        $driverLines = Get-Content -LiteralPath $DriversPath -ErrorAction SilentlyContinue
        for ($i = 0; $i -lt $driverLines.Count; $i++) {
            if ($driverLines[$i] -match "Provider Name:\s+(Digilent|Xilinx|Xilinx, Inc\.|FTDI)") {
                $start = [Math]::Max(0, $i - 2)
                $end = [Math]::Min($driverLines.Count - 1, $i + 5)
                $block = ($driverLines[$start..$end] -join " | ").Trim()
                Write-SummaryLine "${Prefix}_DRIVER_BLOCK=$block"
            }
        }
    }
}

"JTAG_DRIVER_REPAIR_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "VIVADO_PATH=$VivadoPath"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "APPLY=$([int]$Apply.IsPresent)"
Write-SummaryLine "INSTALL_PCUSB=$([int]$InstallPcUsb.IsPresent)"
Write-SummaryLine "INSTALL_DIGILENT=$([int]$InstallDigilent.IsPresent)"
Write-SummaryLine "USE_FULL_XILINX_INSTALLER=$([int]$UseFullXilinxInstaller.IsPresent)"
Write-SummaryLine "SKIP_SCAN_DEVICES=$([int]$SkipScanDevices.IsPresent)"
Write-SummaryLine "SKIP_PREFLIGHT=$([int]$SkipPreflight.IsPresent)"
Write-SummaryLine "SUMMARY_LOG=$summaryLog"
Write-SummaryLine "DEVICE_LOG_BEFORE=$deviceLogBefore"
Write-SummaryLine "DRIVER_LOG_BEFORE=$driverLogBefore"
Write-SummaryLine "DEVICE_LOG_AFTER=$deviceLogAfter"
Write-SummaryLine "DRIVER_LOG_AFTER=$driverLogAfter"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-SummaryLine "IS_ADMIN=$([int]$isAdmin)"

Write-SummaryLine "XILINX_DRIVER_ROOT_PRESENT=$([int](Test-Path -LiteralPath $driverRoot))"
Write-SummaryLine "XILINX_INSTALL_DRIVERS_CMD_PRESENT=$([int](Test-Path -LiteralPath $installDriversCmd))"
Write-SummaryLine "XILINX_PCUSB_INSTALL_CMD_PRESENT=$([int](Test-Path -LiteralPath $xpcInstallCmd))"
Write-SummaryLine "DIGILENT_INSTALLER_PRESENT=$([int](Test-Path -LiteralPath $digilentInstaller))"

Write-SummaryLine "SNAPSHOT_BEFORE_START=$(Get-Date -Format o)"
Write-DriverSnapshot -DevicesPath $deviceLogBefore -DriversPath $driverLogBefore -Prefix "BEFORE"

if (-not $Apply) {
    Write-SummaryLine "DRY_RUN=1"
    Write-SummaryLine "NO_SYSTEM_DRIVER_CHANGE_DONE=1"
    Write-SummaryLine "TO_APPLY_PCUSB=powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\repair_jtag_drivers_admin.ps1 -Apply -InstallPcUsb"
    Write-SummaryLine "TO_APPLY_DIGILENT=powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\repair_jtag_drivers_admin.ps1 -Apply -InstallDigilent"
    Write-SummaryLine "TO_APPLY_BOTH=powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\repair_jtag_drivers_admin.ps1 -Apply -InstallPcUsb -InstallDigilent"
    Write-SummaryLine "JTAG_DRIVER_REPAIR_END $(Get-Date -Format o)"
    exit 0
}

if (-not $isAdmin) {
    Write-SummaryLine "APPLY_BLOCKED_NOT_ADMIN=1"
    Write-SummaryLine "NO_SYSTEM_DRIVER_CHANGE_DONE=1"
    Write-SummaryLine "JTAG_DRIVER_REPAIR_END $(Get-Date -Format o)"
    exit 10
}

if ($UseFullXilinxInstaller) {
    if (-not (Test-Path -LiteralPath $installDriversCmd)) {
        throw "Missing Xilinx install_drivers.cmd: $installDriversCmd"
    }
    Write-SummaryLine "FULL_XILINX_INSTALL_START=$(Get-Date -Format o)"
    $fullExit = Invoke-Logged -FilePath $installDriversCmd -Arguments @("-disable_smartlynq", "-log_filename", $xilinxInstallLog) -LogPath ($xilinxInstallLog + ".wrapper.log")
    Write-SummaryLine "FULL_XILINX_INSTALL_EXIT=$fullExit"
    if ($fullExit -ne 0) {
        Write-SummaryLine "FULL_XILINX_INSTALL_FAILED=1"
    }
}

if ($InstallPcUsb -and -not $UseFullXilinxInstaller) {
    if (-not (Test-Path -LiteralPath $xpcInstallCmd)) {
        throw "Missing Xilinx xpcwinusb installer: $xpcInstallCmd"
    }
    Write-SummaryLine "PCUSB_INSTALL_START=$(Get-Date -Format o)"
    $pcusbExit = Invoke-Logged -FilePath $xpcInstallCmd -Arguments @() -LogPath $pcusbInstallLog
    Write-SummaryLine "PCUSB_INSTALL_EXIT=$pcusbExit"
    if ($pcusbExit -ne 0) {
        Write-SummaryLine "PCUSB_INSTALL_FAILED=1"
    }
}

if ($InstallDigilent -and -not $UseFullXilinxInstaller) {
    if (-not (Test-Path -LiteralPath $digilentInstaller)) {
        throw "Missing Digilent installer: $digilentInstaller"
    }
    Write-SummaryLine "DIGILENT_INSTALL_START=$(Get-Date -Format o)"
    $digilentExit = Invoke-Logged -FilePath $digilentInstaller -Arguments @("/S", "/LogFile=`"$digilentInstallLog`"") -LogPath ($digilentInstallLog + ".wrapper.log")
    Write-SummaryLine "DIGILENT_INSTALL_EXIT=$digilentExit"
    if ($digilentExit -ne 0) {
        Write-SummaryLine "DIGILENT_INSTALL_FAILED=1"
    }
}

if (-not $SkipScanDevices) {
    Write-SummaryLine "SCAN_DEVICES_START=$(Get-Date -Format o)"
    $scanExit = Invoke-Logged -FilePath "pnputil.exe" -Arguments @("/scan-devices") -LogPath $scanLog
    Write-SummaryLine "SCAN_DEVICES_EXIT=$scanExit"
}

Write-SummaryLine "SNAPSHOT_AFTER_START=$(Get-Date -Format o)"
Write-DriverSnapshot -DevicesPath $deviceLogAfter -DriversPath $driverLogAfter -Prefix "AFTER"

if (Test-Path -LiteralPath $diagScript) {
    Write-SummaryLine "DIAG_AFTER_START=$(Get-Date -Format o)"
    $diagExit = Invoke-Logged -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $diagScript,
        "-VivadoPath",
        $VivadoPath,
        "-ComPort",
        $ComPort,
        "-HwServerUrl",
        $HwServerUrl,
        "-SkipVivadoSelfCheck"
    ) -LogPath $diagLog
    Write-SummaryLine "DIAG_AFTER_EXIT=$diagExit"
}

if (-not $SkipPreflight -and (Test-Path -LiteralPath $preflightScript)) {
    Write-SummaryLine "PREFLIGHT_AFTER_START=$(Get-Date -Format o)"
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
    Write-SummaryLine "PREFLIGHT_AFTER_EXIT=$preflightExit"
    if (Test-Path -LiteralPath $preflightLog) {
        foreach ($line in (Get-Content -LiteralPath $preflightLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_DEVICE_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT|COM_PORT_PRESENT|PNP_DEVICE"
        })) {
            Write-SummaryLine "PREFLIGHT_AFTER_MATCH=$line"
        }
    }
}

Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "JTAG_DRIVER_REPAIR_END $(Get-Date -Format o)"
