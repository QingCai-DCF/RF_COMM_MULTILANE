param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$ComPort = "COM3",
    [string]$HwServerUrl = "localhost:3121",
    [string[]]$JtagFrequenciesHz = @("1000000", "500000"),
    [Alias("SkipVivadoSelfCheck")]
    [switch]$SkipVivadoPreflight
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summary = Join-Path $reportsDir "jtag_usb_diag_$stamp.summary.txt"
$driversLog = Join-Path $reportsDir "jtag_usb_diag_$stamp.drivers.log"
$devicesLog = Join-Path $reportsDir "jtag_usb_diag_$stamp.devices.log"
$pnpLog = Join-Path $reportsDir "jtag_usb_diag_$stamp.pnp.log"

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -Path $summary -Value $Line -Encoding ascii
}

function Write-Section {
    param([string]$Name)
    Write-SummaryLine ""
    Write-SummaryLine "[$Name]"
}

function Run-External {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath
    )
    & $FilePath @Arguments *> $LogPath
    return $LASTEXITCODE
}

"JTAG_USB_DIAG_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summary -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "VIVADO_PATH=$VivadoPath"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "SUMMARY_LOG=$summary"
Write-SummaryLine "DEVICES_LOG=$devicesLog"
Write-SummaryLine "DRIVERS_LOG=$driversLog"
Write-SummaryLine "PNP_LOG=$pnpLog"

$parsedFrequencies = @()
foreach ($freqRaw in $JtagFrequenciesHz) {
    foreach ($part in ($freqRaw -split ",")) {
        $trimmed = $part.Trim()
        if ($trimmed -eq "") {
            continue
        }
        $value = 0
        if (-not [int]::TryParse($trimmed, [ref]$value)) {
            throw "Invalid JTAG frequency: $trimmed"
        }
        $parsedFrequencies += $value
    }
}
Write-SummaryLine "JTAG_FREQUENCIES_HZ=$($parsedFrequencies -join ',')"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-SummaryLine "IS_ADMIN=$([int]$isAdmin)"

Write-Section "Serial"
$ports = [System.IO.Ports.SerialPort]::GetPortNames()
Write-SummaryLine "SERIAL_PORTS=$($ports -join ',')"
Write-SummaryLine "COM_PORT_PRESENT=$([int]($ports -contains $ComPort))"

Write-Section "KnownPaths"
$driverRoot = "D:\Xilinx\Vivado\2023.1\data\xicom\cable_drivers\nt64"
$digilentInstaller = Join-Path $driverRoot "digilent\install_digilent.exe"
$installDrivers = Join-Path $driverRoot "install_drivers.cmd"
Write-SummaryLine "XILINX_DRIVER_ROOT_PRESENT=$([int](Test-Path -LiteralPath $driverRoot))"
Write-SummaryLine "DIGILENT_INSTALLER_PRESENT=$([int](Test-Path -LiteralPath $digilentInstaller))"
Write-SummaryLine "INSTALL_DRIVERS_CMD_PRESENT=$([int](Test-Path -LiteralPath $installDrivers))"
foreach ($dll in @("C:\Windows\System32\ftd2xx.dll", "C:\Windows\SysWOW64\ftd2xx.dll")) {
    if (Test-Path -LiteralPath $dll) {
        $item = Get-Item -LiteralPath $dll
        Write-SummaryLine ("DLL path={0} length={1} mtime={2}" -f $item.FullName, $item.Length, $item.LastWriteTime.ToString("s"))
    } else {
        Write-SummaryLine "DLL_MISSING=$dll"
    }
}

Write-Section "PnP"
try {
    $pnps = Get-PnpDevice -ErrorAction Stop | Where-Object {
        $_.FriendlyName -match "Digilent|Xilinx|JTAG|USB Serial|CP210|Silicon Labs|UART|FTDI" -or
        $_.InstanceId -match "VID_0403|VID_10C4|VID_03FD|DIGILENT|XILINX"
    } | Sort-Object Present,Class,FriendlyName,InstanceId
    $pnps | Format-Table -AutoSize Status,Class,FriendlyName,InstanceId | Out-File -FilePath $pnpLog -Encoding utf8
    foreach ($pnp in $pnps) {
        Write-SummaryLine ("PNP status={0} class={1} name={2} id={3}" -f $pnp.Status, $pnp.Class, $pnp.FriendlyName, $pnp.InstanceId)
    }
} catch {
    Write-SummaryLine "PNP_QUERY_ERROR=$($_.Exception.Message)"
}

Write-Section "PnPUtilDevices"
$devCode = Run-External -FilePath "pnputil.exe" -Arguments @("/enum-devices", "/connected") -LogPath $devicesLog
Write-SummaryLine "PNPUTIL_CONNECTED_EXIT=$devCode"
if (Test-Path -LiteralPath $devicesLog) {
    $deviceText = Get-Content -LiteralPath $devicesLog -Raw -ErrorAction SilentlyContinue
    foreach ($pattern in @("VID_0403", "VID_03FD", "VID_10C4", "Digilent", "Xilinx", "USB Serial Converter", "CP210")) {
        $count = ([regex]::Matches($deviceText, [regex]::Escape($pattern), "IgnoreCase")).Count
        Write-SummaryLine "PNPUTIL_CONNECTED_MATCH pattern=$pattern count=$count"
    }
}

Write-Section "DriverPackages"
$drvCode = Run-External -FilePath "pnputil.exe" -Arguments @("/enum-drivers") -LogPath $driversLog
Write-SummaryLine "PNPUTIL_DRIVERS_EXIT=$drvCode"
if (Test-Path -LiteralPath $driversLog) {
    $driverLines = Get-Content -LiteralPath $driversLog -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt $driverLines.Count; $i++) {
        if ($driverLines[$i] -match "Provider Name:\s+(Digilent|Xilinx|Xilinx, Inc\.|FTDI)") {
            $start = [Math]::Max(0, $i - 2)
            $end = [Math]::Min($driverLines.Count - 1, $i + 5)
            $block = ($driverLines[$start..$end] -join " | ").Trim()
            Write-SummaryLine "DRIVER_BLOCK=$block"
        }
    }
}

Write-Section "FTDI6014Binding"
$ftdiInstances = @()
try {
    $ftdiInstances = @(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.DeviceID -like "USB\VID_0403&PID_6014*"
    })
} catch {
    Write-SummaryLine "FTDI_CIM_ERROR=$($_.Exception.Message)"
}
if ($ftdiInstances.Count -eq 0) {
    Write-SummaryLine "FTDI6014_PRESENT=0"
} else {
    Write-SummaryLine "FTDI6014_PRESENT=1"
    foreach ($dev in $ftdiInstances) {
        Write-SummaryLine ("FTDI6014 name={0} status={1} service={2} pnpclass={3} id={4}" -f $dev.Name, $dev.Status, $dev.Service, $dev.PNPClass, $dev.DeviceID)
        Write-SummaryLine "FTDI6014_BOUND_SERVICE=$($dev.Service)"
        Write-SummaryLine "FTDI6014_BOUND_TO_FTDIBUS=$([int]($dev.Service -match '^FTDIBUS$'))"
        $instanceLog = Join-Path $reportsDir ("jtag_usb_diag_{0}.ftdi6014_{1}.drivers.log" -f $stamp, ($dev.DeviceID -replace '[\\/:*?""<>|&]', '_'))
        $code = Run-External -FilePath "pnputil.exe" -Arguments @("/enum-devices", "/instanceid", $dev.DeviceID, "/drivers") -LogPath $instanceLog
        Write-SummaryLine "FTDI6014_DRIVER_QUERY_EXIT=$code log=$instanceLog"
        if (Test-Path -LiteralPath $instanceLog) {
            $instanceText = Get-Content -LiteralPath $instanceLog -Raw -ErrorAction SilentlyContinue
            foreach ($line in (($instanceText -split "`r?`n") | Where-Object { $_.Trim() -ne "" } | Select-Object -First 80)) {
                Write-SummaryLine "FTDI6014_DRIVER=$($line.Trim())"
            }
            Write-SummaryLine "FTDI6014_DRIVER_PROVIDER_FTDI=$([int]($instanceText -match 'FTDI'))"
            Write-SummaryLine "FTDI6014_DRIVER_ORIGINAL_FTDIBUS=$([int]($instanceText -match 'ftdibus\.inf'))"
            Write-SummaryLine "FTDI6014_DRIVER_ORIGINAL_WINUSB=$([int]($instanceText -match 'winusb|xusb|xilinx|digilent'))"
        }
    }
}

Write-Section "VivadoPreflight"
if ($SkipVivadoPreflight) {
    Write-SummaryLine "VIVADO_PREFLIGHT_SKIPPED=1"
} else {
    $preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
    if (-not (Test-Path -LiteralPath $preflightScript)) {
        Write-SummaryLine "VIVADO_PREFLIGHT_ERROR=missing_check_hw_target"
    } elseif (-not (Test-Path -LiteralPath $VivadoPath)) {
        Write-SummaryLine "VIVADO_PREFLIGHT_ERROR=missing_vivado"
    } else {
        foreach ($freq in $parsedFrequencies) {
            $preflightLog = Join-Path $reportsDir "jtag_usb_diag_${stamp}.preflight_${freq}.log"
            $code = Run-External -FilePath "powershell.exe" -Arguments @(
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
                [string]$freq
            ) -LogPath $preflightLog
            Write-SummaryLine "VIVADO_PREFLIGHT_FREQ=$freq EXIT=$code LOG=$preflightLog"
            if (Test-Path -LiteralPath $preflightLog) {
                foreach ($line in (Get-Content -LiteralPath $preflightLog -ErrorAction SilentlyContinue | Where-Object {
                    $_ -match "HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_DEVICE_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT|COM_PORT_PRESENT|PNP_DEVICE"
                })) {
                    Write-SummaryLine "VIVADO_PREFLIGHT_MATCH freq=$freq $line"
                }
            }
        }
    }
}

Write-Section "Decision"
Write-SummaryLine "PASS_GATE=Need VIVADO_PREFLIGHT_MATCH with HW_PREFLIGHT_RESULT PASS and HW_PREFLIGHT_ZYNQ before any hardware run."
if (-not $isAdmin) {
    Write-SummaryLine "ADMIN_NOTE=Current shell is not elevated; driver re-scan or re-bind operations may require an elevated PowerShell."
}
if ($ftdiInstances.Count -gt 0) {
    Write-SummaryLine "FTDI6014_NOTE=Connected VID_0403&PID_6014 is currently an FTDI USB device; Vivado still must enumerate a hw target before any programming."
    Write-SummaryLine "JTAG_BINDING_NOTE=If Vivado reports zero hw targets while FTDI6014 is bound to FTDIBUS, check whether this USB connector is the board JTAG connector and whether Xilinx/Digilent cable drivers are bound to the actual JTAG interface."
}
Write-SummaryLine "NO_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "JTAG_USB_DIAG_END $(Get-Date -Format o)"
