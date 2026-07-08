[CmdletBinding()]
param(
    [string]$BootgenBat = "D:\Xilinx\Vitis\2023.1\bin\bootgen.bat",
    [string]$XsctBat = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$OutputDir = "",
    [int]$Jobs = 16,
    [switch]$RebuildVitis,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path

if ($OutputDir -eq "") {
    $OutputDir = Join-Path $repoRoot "software\_boot"
}

$buildScript = Join-Path $repoRoot "software\ps_lwip_bridge\build_vitis.tcl"
$fsblCandidates = @(
    (Join-Path $repoRoot "software\_vitis_ws\design_shiboqi_wrapper\export\design_shiboqi_wrapper\sw\design_shiboqi_wrapper\boot\fsbl.elf"),
    (Join-Path $repoRoot "software\_vitis_ws\design_shiboqi_wrapper\zynq_fsbl\fsbl.elf")
)
$bitCandidates = @(
    (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"),
    (Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.bit")
)
$appElf = Join-Path $repoRoot "software\_vitis_ws\rf_comm_ps_bridge\Debug\rf_comm_ps_bridge.elf"
$bifFile = Join-Path $OutputDir "rf_comm_boot.bif"
$bootBin = Join-Path $OutputDir "BOOT.BIN"

function Get-FirstExisting {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    return $null
}

function Require-File {
    param([string]$Name, [string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Name is missing: $Path"
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -le 0) {
        throw "$Name is empty: $Path"
    }
    return $item
}

try {
    $proc = [System.Diagnostics.Process]::GetCurrentProcess()
    $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
    $proc.ProcessorAffinity = [IntPtr]65535
    Write-Host "BOOT_IMAGE priority=$($proc.PriorityClass) affinity=$($proc.ProcessorAffinity)"
} catch {
    Write-Host "BOOT_IMAGE affinity_priority_set_failed: $($_.Exception.Message)"
}

if ($RebuildVitis) {
    if (-not (Test-Path -LiteralPath $XsctBat)) {
        throw "XSCT is missing: $XsctBat"
    }
    $env:MAKEFLAGS = "-j$Jobs"
    Write-Host "Rebuilding Vitis software: $buildScript"
    & $XsctBat $buildScript
    if ($LASTEXITCODE -ne 0) {
        throw "Vitis build failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $BootgenBat)) {
    throw "bootgen is missing: $BootgenBat"
}

$fsblElf = Get-FirstExisting $fsblCandidates
if ($null -eq $fsblElf) {
    throw "FSBL ELF is missing. Run tools\build_boot_image.ps1 -RebuildVitis or software\ps_lwip_bridge\build_vitis.tcl first."
}
$bitFile = Get-FirstExisting $bitCandidates
if ($null -eq $bitFile) {
    throw "bitstream is missing. Expected one of: $($bitCandidates -join ', ')"
}

$fsblItem = Require-File "FSBL ELF" $fsblElf
$bitItem = Require-File "bitstream" $bitFile
$appItem = Require-File "PS bridge ELF" $appElf

if ((Test-Path -LiteralPath $bootBin) -and -not $Force) {
    $bootItem = Get-Item -LiteralPath $bootBin
    $inputs = @($fsblItem, $bitItem, $appItem)
    $newerInput = $inputs | Where-Object { $_.LastWriteTime -gt $bootItem.LastWriteTime } | Select-Object -First 1
    if ($null -eq $newerInput) {
        Write-Host "BOOT.BIN is already up to date: $bootBin"
        Write-Host "BOOT_BIN $bootBin"
        exit 0
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$bifText = @"
the_ROM_image:
{
  [bootloader] $fsblElf
  $bitFile
  $appElf
}
"@

Set-Content -LiteralPath $bifFile -Value $bifText -Encoding ASCII

Write-Host "Generating BOOT.BIN"
Write-Host "  bif:  $bifFile"
Write-Host "  fsbl: $fsblElf"
Write-Host "  bit:  $bitFile"
Write-Host "  elf:  $appElf"
Write-Host "  out:  $bootBin"

$bootgenOutput = & $BootgenBat -image $bifFile -arch zynq -o $bootBin -w on 2>&1
$bootgenOutput | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0 -or ($bootgenOutput -match "^\[ERROR\]")) {
    throw "bootgen failed"
}

$bootItem = Require-File "BOOT.BIN" $bootBin
Write-Host ("BOOT_BIN {0} bytes={1} mtime={2}" -f $bootItem.FullName, $bootItem.Length, $bootItem.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
