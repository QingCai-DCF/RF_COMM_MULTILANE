param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [int]$Jobs = 16,
    [int]$LaneCount = 5,
    [int]$FragmentBytes = 32,
    [int]$MaxPacketBytes = 128,
    [int]$TxAsyncFifoDepth = 128,
    [int]$RxAsyncFifoDepth = 128,
    [int]$StreamPhyDbgSelect = 6,
    [UInt64]$AffinityMask = 0xFFFF
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$prefix = "build_external_reduced_5lane_frag32_route_$stamp"
$outDir = Join-Path $reportsDir $prefix
$vivadoLog = Join-Path $reportsDir "$prefix.vivado.log"
$journal = Join-Path $reportsDir "$prefix.vivado.jou"
$stdout = Join-Path $reportsDir "$prefix.out.log"
$stderr = Join-Path $reportsDir "$prefix.err.log"
$meta = Join-Path $reportsDir "$prefix.meta.txt"
$tclScript = Join-Path $scriptDir "build_external_reduced_2lane_route.tcl"

if (-not (Test-Path -LiteralPath $VivadoPath -PathType Leaf)) {
    throw "Vivado not found: $VivadoPath"
}
if (-not (Test-Path -LiteralPath $tclScript -PathType Leaf)) {
    throw "Tcl script not found: $tclScript"
}
if ($LaneCount -ne 5) {
    throw "This wrapper is for the reduced 5-lane fragment=32 route build; got LaneCount=$LaneCount"
}
if ($FragmentBytes -ne 32 -or $MaxPacketBytes -ne 128) {
    throw "This wrapper is locked to fragment=32 and max_packet=128; got fragment=$FragmentBytes max_packet=$MaxPacketBytes"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$env:VIVADO_MAX_THREADS = [string]$Jobs
$env:REDUCED_ROUTE_OUT_DIR = $outDir
$env:REDUCED_ROUTE_LANE_COUNT = [string]$LaneCount
$env:REDUCED_ROUTE_FRAGMENT_BYTES = [string]$FragmentBytes
$env:REDUCED_ROUTE_MAX_PACKET_BYTES = [string]$MaxPacketBytes
$env:REDUCED_ROUTE_TX_ASYNC_FIFO_DEPTH = [string]$TxAsyncFifoDepth
$env:REDUCED_ROUTE_RX_ASYNC_FIFO_DEPTH = [string]$RxAsyncFifoDepth
$env:REDUCED_ROUTE_STREAM_PHY_DBG_SELECT = [string]$StreamPhyDbgSelect
$env:REDUCED_ROUTE_NO_HARDWARE_PROGRAMMING = "1"
$env:REDUCED_ROUTE_NO_UART_WRITE = "1"
$env:REDUCED_ROUTE_NO_TFDU_DRIVE = "1"
$env:REDUCED_ROUTE_ETHERNET_DEFERRED = "1"

$metaLines = @(
    "timestamp=$stamp",
    "out_dir=$($outDir.Replace($repoRoot + '\', ''))",
    "lane_count=$LaneCount",
    "fragment_bytes=$FragmentBytes",
    "max_packet_bytes=$MaxPacketBytes",
    "tx_async_fifo_depth=$TxAsyncFifoDepth",
    "rx_async_fifo_depth=$RxAsyncFifoDepth",
    "stream_phy_dbg_select=$StreamPhyDbgSelect",
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

Write-Host "EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_START meta=$meta"
Write-Host "EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_COMMAND $VivadoPath $($arguments -join ' ')"

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
    Write-Host "EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_AFFINITY_SET mask=0x$($AffinityMask.ToString('X'))"
} catch {
    Add-Content -LiteralPath $meta -Value "affinity_set_failed=$($_.Exception.Message)" -Encoding ascii
    Write-Host "EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_AFFINITY_SET_FAILED $($_.Exception.Message)"
}

$proc.WaitForExit()
$proc.Refresh()
$exitCode = if ($null -eq $proc.ExitCode) { 0 } else { [int]$proc.ExitCode }
Add-Content -LiteralPath $meta -Value "exit_code=$exitCode" -Encoding ascii
Write-Host "EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_EXIT_CODE=$exitCode"
exit $exitCode
