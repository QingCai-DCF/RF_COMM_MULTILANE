param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$ComPort = "COM3",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$tcl = Join-Path $repoRoot "tools\check_hw_target.tcl"
$out = Join-Path $reportsDir "hw_target_preflight_$stamp.out.log"
$err = Join-Path $reportsDir "hw_target_preflight_$stamp.err.log"
$summary = Join-Path $reportsDir "hw_target_preflight_$stamp.summary.txt"

if (-not (Test-Path -LiteralPath $VivadoPath)) {
    throw "Vivado path missing: $VivadoPath"
}
if (-not (Test-Path -LiteralPath $tcl)) {
    throw "Preflight Tcl missing: $tcl"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -Path $summary -Value $Line -Encoding ascii
}

"HW_TARGET_PREFLIGHT_WRAPPER_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summary -Encoding ascii
Write-SummaryLine "VIVADO_PATH=$VivadoPath"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "STDOUT_LOG=$out"
Write-SummaryLine "STDERR_LOG=$err"

$ports = [System.IO.Ports.SerialPort]::GetPortNames() -join ","
Write-SummaryLine "SERIAL_PORTS=$ports"
Write-SummaryLine "COM_PORT_PRESENT=$([int](([System.IO.Ports.SerialPort]::GetPortNames()) -contains $ComPort))"

try {
    $pnps = Get-PnpDevice -PresentOnly -ErrorAction Stop | Where-Object {
        $_.FriendlyName -match "Digilent|Xilinx|JTAG|USB Serial|CP210|Silicon Labs|UART" -or
        $_.InstanceId -match "VID_0403|VID_10C4|VID_03FD|DIGILENT|XILINX"
    }
    foreach ($pnp in $pnps) {
        Write-SummaryLine ("PNP_DEVICE status={0} class={1} name={2} id={3}" -f $pnp.Status, $pnp.Class, $pnp.FriendlyName, $pnp.InstanceId)
    }
} catch {
    Write-SummaryLine "PNP_QUERY_WARN=$($_.Exception.Message)"
}

$oldErrorActionPreference = $ErrorActionPreference
$hasNativePreference = Test-Path -LiteralPath "Variable:\PSNativeCommandUseErrorActionPreference"
if ($hasNativePreference) {
    $oldNativePreference = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
}
$ErrorActionPreference = "Continue"
try {
    & $VivadoPath -mode batch -notrace -source $tcl -tclargs $HwServerUrl $JtagFrequencyHz *> $out 2> $err
    $code = $LASTEXITCODE
} catch {
    $code = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 1 }
    Add-Content -Path $err -Value $_.Exception.Message -Encoding ascii
} finally {
    $ErrorActionPreference = $oldErrorActionPreference
    if ($hasNativePreference) {
        $PSNativeCommandUseErrorActionPreference = $oldNativePreference
    }
}
Write-SummaryLine "VIVADO_PREFLIGHT_EXIT=$code"

if (Test-Path -LiteralPath $out) {
    $lines = Get-Content -LiteralPath $out -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "HW_PREFLIGHT|Labtools|ERROR|WARNING"
    }
    foreach ($line in ($lines | Select-Object -Last 80)) {
        Write-SummaryLine "VIVADO_MATCH=$line"
    }
}
if ((Test-Path -LiteralPath $err) -and (Get-Item -LiteralPath $err).Length -gt 0) {
    foreach ($line in (Get-Content -LiteralPath $err -ErrorAction SilentlyContinue | Select-Object -Last 30)) {
        Write-SummaryLine "VIVADO_STDERR=$line"
    }
}

Write-SummaryLine "HW_TARGET_PREFLIGHT_WRAPPER_END $(Get-Date -Format o)"
exit $code
