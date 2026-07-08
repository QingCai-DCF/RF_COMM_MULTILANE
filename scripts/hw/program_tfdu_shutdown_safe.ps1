[CmdletBinding()]
param(
    [switch]$AllowHardware,
    [string]$ProfilePath = "config/profiles/G1_LANE0_BASELINE.json",
    [string]$EvidenceDir = "",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$ShutdownTcl = "scripts/legacy_safe_tools/program_tfdu_shutdown.tcl",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..\..")).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $EvidenceDir) {
    $EvidenceDir = Join-Path $repoRoot "evidence\generated\hw_preflight\program_tfdu_shutdown_safe_$stamp"
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
    $EvidenceDir = Join-Path $repoRoot $EvidenceDir
}
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$summaryLog = Join-Path $EvidenceDir "program_tfdu_shutdown_safe.summary.txt"
$manifestJson = Join-Path $EvidenceDir "hash_manifest.json"
$manifestCsv = Join-Path $EvidenceDir "hash_manifest.csv"
$stdoutLog = Join-Path $EvidenceDir "program_tfdu_shutdown_safe.stdout.log"
$stderrLog = Join-Path $EvidenceDir "program_tfdu_shutdown_safe.stderr.log"

function Resolve-RepoPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $repoRoot $Path
}

function Get-FileSha256OrMissing {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    }
    return "MISSING"
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Write-HashManifest {
    param([string[]]$Paths)
    $entries = @()
    foreach ($path in $Paths) {
        if (-not $path) {
            continue
        }
        $full = Resolve-RepoPath $path
        $exists = Test-Path -LiteralPath $full -PathType Leaf
        $entries += [ordered]@{
            path = $full
            exists = [bool]$exists
            sha256 = Get-FileSha256OrMissing -Path $full
        }
    }
    $profileFull = Resolve-RepoPath $ProfilePath
    $manifest = [ordered]@{
        script = $MyInvocation.MyCommand.Path
        generated_at = (Get-Date).ToString("o")
        allow_hardware = [bool]$AllowHardware.IsPresent
        no_hardware_actions_executed = -not $AllowHardware.IsPresent
        profile_path = $profileFull
        profile_sha256 = Get-FileSha256OrMissing -Path $profileFull
        files = $entries
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestJson -Encoding ascii
    $csvLines = @("path,exists,sha256")
    foreach ($entry in $entries) {
        $csvLines += ('"{0}",{1},{2}' -f ($entry.path -replace '"', '""'), $entry.exists, $entry.sha256)
    }
    $csvLines | Set-Content -LiteralPath $manifestCsv -Encoding ascii
}

function ConvertTo-Argument {
    param([string]$Value)
    if ($Value -match '[\s&()^|<>"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$StdoutPath,
        [string]$StderrPath,
        [int]$Timeout
    )
    $argLine = ($Arguments | ForEach-Object { ConvertTo-Argument $_ }) -join " "
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $argLine `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($Timeout * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 125
    }
    return $proc.ExitCode
}

$profileFullPath = Resolve-RepoPath $ProfilePath
$shutdownTclFullPath = Resolve-RepoPath $ShutdownTcl
$shutdownBitPath = Resolve-RepoPath "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
Write-HashManifest -Paths @(
    $ProfilePath,
    $ShutdownTcl,
    "scripts/legacy_safe_tools/build_tfdu_shutdown.tcl",
    "scripts/legacy_safe_tools/tfdu_shutdown_top.v",
    "scripts/legacy_safe_tools/tfdu_shutdown_j10_j11.xdc",
    "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
)

"PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN $(Get-Date -Format o)" | Set-Content -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "PROFILE_PATH=$profileFullPath"
Write-SummaryLine "PROFILE_SHA256=$(Get-FileSha256OrMissing -Path $profileFullPath)"
Write-SummaryLine "HASH_MANIFEST_JSON=$manifestJson"
Write-SummaryLine "HASH_MANIFEST_CSV=$manifestCsv"
Write-SummaryLine "SHUTDOWN_TCL=$shutdownTclFullPath"
Write-SummaryLine "SHUTDOWN_TCL_SHA256=$(Get-FileSha256OrMissing -Path $shutdownTclFullPath)"
Write-SummaryLine "SHUTDOWN_BITSTREAM=$shutdownBitPath"
Write-SummaryLine "SHUTDOWN_BITSTREAM_SHA256=$(Get-FileSha256OrMissing -Path $shutdownBitPath)"

if (-not $AllowHardware.IsPresent) {
    Write-SummaryLine "REFUSED_NO_ALLOW_HARDWARE=1"
    Write-SummaryLine "NO_HARDWARE_ACTIONS_EXECUTED=1"
    Write-SummaryLine "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=REFUSED_NO_ALLOW_HARDWARE"
    Write-SummaryLine "PROGRAM_TFDU_SHUTDOWN_SAFE_END $(Get-Date -Format o)"
    exit 0
}

if (-not (Test-Path -LiteralPath $VivadoPath -PathType Leaf)) {
    Write-SummaryLine "VIVADO_PATH_MISSING=$VivadoPath"
    throw "Vivado path is missing: $VivadoPath"
}
if (-not (Test-Path -LiteralPath $shutdownTclFullPath -PathType Leaf)) {
    Write-SummaryLine "SHUTDOWN_TCL_MISSING=$shutdownTclFullPath"
    throw "Shutdown Tcl is missing: $shutdownTclFullPath"
}

Write-SummaryLine "ALLOW_HARDWARE=1"
Write-SummaryLine "NO_HARDWARE_ACTIONS_EXECUTED=0"
Write-SummaryLine "SHUTDOWN_START=$(Get-Date -Format o)"
$shutdownExit = Invoke-LoggedProcess `
    -FilePath $VivadoPath `
    -Arguments @("-mode", "batch", "-source", $shutdownTclFullPath) `
    -StdoutPath $stdoutLog `
    -StderrPath $stderrLog `
    -Timeout $TimeoutSeconds
Write-SummaryLine "SHUTDOWN_STDOUT_LOG=$stdoutLog"
Write-SummaryLine "SHUTDOWN_STDERR_LOG=$stderrLog"
Write-SummaryLine "SHUTDOWN_RAW_EXIT=$shutdownExit"

$shutdownText = ""
if (Test-Path -LiteralPath $stdoutLog) {
    $shutdownText += Get-Content -LiteralPath $stdoutLog -Raw -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $stderrLog) {
    $shutdownText += "`n" + (Get-Content -LiteralPath $stderrLog -Raw -ErrorAction SilentlyContinue)
}
$shutdownOk = ($shutdownExit -eq 0 -or $shutdownText -match "TFDU_SHUTDOWN_PROGRAMMED")
Write-SummaryLine "TFDU_SHUTDOWN_PROGRAMMED_SEEN=$([int]($shutdownText -match 'TFDU_SHUTDOWN_PROGRAMMED'))"
Write-SummaryLine "SHUTDOWN_EXIT=$(if ($shutdownOk) { 0 } else { $shutdownExit })"
Write-SummaryLine "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=$(if ($shutdownOk) { 'PASS' } else { 'FAIL' })"
Write-SummaryLine "PROGRAM_TFDU_SHUTDOWN_SAFE_END $(Get-Date -Format o)"

if (-not $shutdownOk) {
    exit $(if ($shutdownExit -ne 0) { $shutdownExit } else { 30 })
}
exit 0
