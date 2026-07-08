param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$RouteDir = "",
    [int]$Jobs = 16,
    [UInt64]$AffinityMask = 0xFFFF
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

if (-not (Test-Path -LiteralPath $VivadoPath -PathType Leaf)) {
    throw "Vivado not found: $VivadoPath"
}

if ([string]::IsNullOrWhiteSpace($RouteDir)) {
    $latestRoute = Get-ChildItem -LiteralPath $reportsDir -Directory -Filter "build_external_reduced_4lane_route_*" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $latestRoute) {
        throw "No build_external_reduced_4lane_route_* directory found"
    }
    $RouteDir = $latestRoute.FullName
} else {
    $RouteDir = (Resolve-Path -LiteralPath $RouteDir).Path
}

$routeDcp = Join-Path $RouteDir "design_shiboqi_wrapper_post_route.dcp"
if (-not (Test-Path -LiteralPath $routeDcp -PathType Leaf)) {
    throw "Missing reduced 4-lane post-route checkpoint: $routeDcp"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$prefix = "external_reduced_4lane_bitstream_$stamp"
$outDir = Join-Path $reportsDir $prefix
$vivadoLog = Join-Path $reportsDir "$prefix.vivado.log"
$journal = Join-Path $reportsDir "$prefix.vivado.jou"
$stdout = Join-Path $reportsDir "$prefix.out.log"
$stderr = Join-Path $reportsDir "$prefix.err.log"
$meta = Join-Path $reportsDir "$prefix.meta.txt"
$tclScript = Join-Path $scriptDir "write_external_reduced_4lane_bitstream.tcl"

if (-not (Test-Path -LiteralPath $tclScript -PathType Leaf)) {
    throw "Tcl script not found: $tclScript"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$env:VIVADO_MAX_THREADS = [string]$Jobs
$env:EXT4_BIT_ROUTE_DIR = $RouteDir
$env:EXT4_BIT_OUT_DIR = $outDir
$env:EXT4_BIT_NO_HARDWARE_PROGRAMMING = "1"
$env:EXT4_BIT_NO_UART_WRITE = "1"
$env:EXT4_BIT_NO_TFDU_DRIVE = "1"
$env:EXT4_BIT_ETHERNET_DEFERRED = "1"

$metaLines = @(
    "timestamp=$stamp",
    "route_dir=$($RouteDir.Replace($repoRoot + '\', ''))",
    "route_dcp=$($routeDcp.Replace($repoRoot + '\', ''))",
    "out_dir=$($outDir.Replace($repoRoot + '\', ''))",
    "bitstream=$((Join-Path $outDir 'external_reduced_4lane_candidate.bit').Replace($repoRoot + '\', ''))",
    "vivado_max_threads=$Jobs",
    "affinity_mask=0x$($AffinityMask.ToString('X'))",
    "no_hardware_programming=1",
    "no_uart_write=1",
    "no_tfdu_drive=1",
    "ethernet_real_test_deferred=1",
    "vivado_log=$($vivadoLog.Replace($repoRoot + '\', ''))",
    "journal=$($journal.Replace($repoRoot + '\', ''))",
    "stdout=$($stdout.Replace($repoRoot + '\', ''))",
    "stderr=$($stderr.Replace($repoRoot + '\', ''))"
)
$metaLines | Set-Content -LiteralPath $meta -Encoding ascii

$arguments = @(
    "-mode", "batch",
    "-source", $tclScript,
    "-notrace",
    "-log", $vivadoLog,
    "-journal", $journal
)

Write-Host "EXTERNAL_REDUCED_4LANE_BITSTREAM_START meta=$meta"
Write-Host "EXTERNAL_REDUCED_4LANE_BITSTREAM_COMMAND $VivadoPath $($arguments -join ' ')"

$proc = Start-Process -FilePath $VivadoPath `
    -ArgumentList $arguments `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

try {
    $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
    $proc.ProcessorAffinity = [IntPtr]([Int64]$AffinityMask)
    Add-Content -LiteralPath $meta -Value "priority_set=High" -Encoding ascii
    Add-Content -LiteralPath $meta -Value "affinity_set=0x$($AffinityMask.ToString('X'))" -Encoding ascii
    Write-Host "EXTERNAL_REDUCED_4LANE_BITSTREAM_AFFINITY_SET mask=0x$($AffinityMask.ToString('X'))"
} catch {
    Add-Content -LiteralPath $meta -Value "affinity_set_failed=$($_.Exception.Message)" -Encoding ascii
    Write-Host "EXTERNAL_REDUCED_4LANE_BITSTREAM_AFFINITY_SET_FAILED $($_.Exception.Message)"
}

$proc.WaitForExit()
$proc.Refresh()
$exitCode = if ($null -eq $proc.ExitCode) { 0 } else { [int]$proc.ExitCode }
Add-Content -LiteralPath $meta -Value "exit_code=$exitCode" -Encoding ascii
Write-Host "EXTERNAL_REDUCED_4LANE_BITSTREAM_EXIT_CODE=$exitCode"
exit $exitCode
