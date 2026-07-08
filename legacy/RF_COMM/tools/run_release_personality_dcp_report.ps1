param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$DcpPath = "",
    [int]$Jobs = 16,
    [UInt64]$AffinityMask = 0xFFFF
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

if ([string]::IsNullOrWhiteSpace($DcpPath)) {
    $DcpPath = Get-ChildItem -LiteralPath $reportsDir -Directory -Filter "build_external_reduced_8lane_frag16_route_20260627_*" |
        ForEach-Object {
            $candidate = Join-Path $_.FullName "design_shiboqi_wrapper_post_route.dcp"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                Get-Item -LiteralPath $candidate
            }
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    if ([string]::IsNullOrWhiteSpace($DcpPath)) {
        throw "No reduced 8-lane fragment=16 post-route DCP was found under reports."
    }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$prefix = "release_personality_dcp_report_$stamp"
$outDir = Join-Path $reportsDir $prefix
$vivadoLog = Join-Path $reportsDir "$prefix.vivado.log"
$journal = Join-Path $reportsDir "$prefix.vivado.jou"
$stdout = Join-Path $reportsDir "$prefix.out.log"
$stderr = Join-Path $reportsDir "$prefix.err.log"
$meta = Join-Path $reportsDir "$prefix.meta.txt"
$tclScript = Join-Path $scriptDir "report_release_personality_from_dcp.tcl"

if (-not (Test-Path -LiteralPath $VivadoPath -PathType Leaf)) {
    throw "Vivado not found: $VivadoPath"
}
if (-not (Test-Path -LiteralPath $DcpPath -PathType Leaf)) {
    throw "DCP not found: $DcpPath"
}
if (-not (Test-Path -LiteralPath $tclScript -PathType Leaf)) {
    throw "Tcl script not found: $tclScript"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$env:VIVADO_MAX_THREADS = [string]$Jobs
$env:RELEASE_PERSONALITY_OUT_DIR = $outDir
$env:RELEASE_PERSONALITY_DCP = $DcpPath
$env:RELEASE_PERSONALITY_NO_HARDWARE_PROGRAMMING = "1"
$env:RELEASE_PERSONALITY_NO_UART_WRITE = "1"
$env:RELEASE_PERSONALITY_NO_TFDU_DRIVE = "1"
$env:RELEASE_PERSONALITY_NO_SYNTHESIS = "1"
$env:RELEASE_PERSONALITY_NO_IMPLEMENTATION = "1"
$env:RELEASE_PERSONALITY_NO_BITSTREAM = "1"

$relOut = $outDir.Replace($repoRoot + '\', '')
$relDcp = $DcpPath.Replace($repoRoot + '\', '')
$metaLines = @(
    "timestamp=$stamp",
    "out_dir=$relOut",
    "dcp=$relDcp",
    "vivado_max_threads=$Jobs",
    "affinity_mask=0x$($AffinityMask.ToString('X'))",
    "no_hardware_programming=1",
    "no_uart_write=1",
    "no_tfdu_drive=1",
    "no_synthesis=1",
    "no_implementation=1",
    "no_bitstream=1",
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

Write-Host "RELEASE_PERSONALITY_DCP_REPORT_START meta=$meta"
Write-Host "RELEASE_PERSONALITY_DCP_REPORT_COMMAND $VivadoPath $($arguments -join ' ')"

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
    Write-Host "RELEASE_PERSONALITY_DCP_REPORT_AFFINITY_SET mask=0x$($AffinityMask.ToString('X'))"
} catch {
    Add-Content -LiteralPath $meta -Value "affinity_set_failed=$($_.Exception.Message)" -Encoding ascii
    Write-Host "RELEASE_PERSONALITY_DCP_REPORT_AFFINITY_SET_FAILED $($_.Exception.Message)"
}

$proc.WaitForExit()
$proc.Refresh()
$exitCode = if ($null -eq $proc.ExitCode) { 0 } else { [int]$proc.ExitCode }
Add-Content -LiteralPath $meta -Value "exit_code=$exitCode" -Encoding ascii
Write-Host "RELEASE_PERSONALITY_DCP_REPORT_EXIT_CODE=$exitCode"
exit $exitCode
