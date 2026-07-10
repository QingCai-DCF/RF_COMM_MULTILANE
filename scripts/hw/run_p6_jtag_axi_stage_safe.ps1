[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Stage,
    [Parameter(Mandatory = $true)][string]$Bitstream,
    [Parameter(Mandatory = $true)][string]$BitstreamSha256,
    [Parameter(Mandatory = $true)][string]$Ltx,
    [Parameter(Mandatory = $true)][string]$LtxSha256,
    [Parameter(Mandatory = $true)][string]$Profile,
    [Parameter(Mandatory = $true)][string]$ProfileSha256,
    [Parameter(Mandatory = $true)][string]$ActiveXdcSha256,
    [Parameter(Mandatory = $true)][string]$PinmapSha256,
    [Parameter(Mandatory = $true)][string]$ShutdownBitstreamSha256,
    [Parameter(Mandatory = $true)][string]$TransactionFile,
    [Parameter(Mandatory = $true)][string]$ResultFile,
    [Parameter(Mandatory = $true)][string]$EvidenceDir,
    [int]$LaneCount = 2,
    [string]$MaxLaneMask = "0x3",
    [int]$MaxRuntimeSec = 1200,
    [switch]$NoEthernet,
    [switch]$NoMotion,
    [switch]$ShutdownOnExit,
    [string]$AuthorizationFile = ".hardware_authorization\P6_LOCAL_TRANSPORT_APPROVED.txt",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..\..")).Path

function Resolve-RepoPath([string]$Path) {
    if ([IO.Path]::IsPathRooted($Path)) { return $Path }
    return Join-Path $repoRoot $Path
}
function Get-Sha([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return "MISSING" }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}
function Require-Hash([string]$Label, [string]$Path, [string]$Expected) {
    $actual = Get-Sha $Path
    if ($actual -ne $Expected.ToLowerInvariant()) { throw "$Label SHA256 mismatch expected=$Expected actual=$actual path=$Path" }
}
function Quote-Arg([string]$Value) {
    if ($Value -match '[\s&()^|<>"]') { return '"' + ($Value -replace '"', '\"') + '"' }
    return $Value
}
function Invoke-Logged([string]$FilePath, [string[]]$Arguments, [string]$Stdout, [string]$Stderr, [int]$TimeoutSec) {
    $argLine = ($Arguments | ForEach-Object { Quote-Arg $_ }) -join " "
    $proc = Start-Process -FilePath $FilePath -ArgumentList $argLine -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -WindowStyle Hidden -PassThru
    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    $proc.WaitForExit()
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) { return 125 }
    return [int]$proc.ExitCode
}
function Invoke-Shutdown([string]$Name) {
    $stdout = Join-Path $evidenceFull "$Name.stdout.log"
    $stderr = Join-Path $evidenceFull "$Name.stderr.log"
    $rc = Invoke-Logged $VivadoPath @("-mode", "batch", "-source", $shutdownTcl) $stdout $stderr 240
    $text = ""
    if (Test-Path -LiteralPath $stdout) { $text += Get-Content -Raw -LiteralPath $stdout }
    if (Test-Path -LiteralPath $stderr) { $text += "`n" + (Get-Content -Raw -LiteralPath $stderr) }
    $ok = ($rc -eq 0) -or ($text -match "TFDU_SHUTDOWN_PROGRAMMED")
    Add-Content -LiteralPath $summary -Encoding ascii -Value "$($Name.ToUpperInvariant())_RAW_EXIT=$rc"
    Add-Content -LiteralPath $summary -Encoding ascii -Value "$($Name.ToUpperInvariant())_TFDU_SHUTDOWN_PROGRAMMED=$([int]($text -match 'TFDU_SHUTDOWN_PROGRAMMED'))"
    Add-Content -LiteralPath $summary -Encoding ascii -Value "$($Name.ToUpperInvariant())_SHUTDOWN_EXIT=$(if($ok){0}else{$rc})"
    return $ok
}

$evidenceFull = Resolve-RepoPath $EvidenceDir
New-Item -ItemType Directory -Force -Path $evidenceFull | Out-Null
$summary = Join-Path $evidenceFull "p6_safe_stage_summary.log"
"P6_SAFE_STAGE_BEGIN=$(Get-Date -Format o)" | Set-Content -LiteralPath $summary -Encoding ascii

$bitFull = Resolve-RepoPath $Bitstream
$ltxFull = Resolve-RepoPath $Ltx
$profileFull = Resolve-RepoPath $Profile
$txnFull = Resolve-RepoPath $TransactionFile
$resultFull = Resolve-RepoPath $ResultFile
$authFull = Resolve-RepoPath $AuthorizationFile
$activeXdc = Join-Path $repoRoot "constraints\active\PORT1.generated.xdc"
$pinmap = Join-Path $repoRoot "board_profiles\ax7010_tfdu_j10_j11_pinmap.csv"
$shutdownBit = Join-Path $repoRoot "shutdown_bitstream\tfdu_shutdown_j10_j11.bit"
$shutdownTcl = Join-Path $repoRoot "scripts\legacy_safe_tools\program_tfdu_shutdown.tcl"
$stageTcl = Join-Path $repoRoot "scripts\hw\p6_jtag_axi_transactions.tcl"

if ($env:RF_COMM_HW_AUTH -ne "P6_LOCAL_TRANSPORT_APPROVED") { throw "RF_COMM_HW_AUTH=P6_LOCAL_TRANSPORT_APPROVED is required" }
if (-not $NoEthernet) { throw "-NoEthernet is required" }
if (-not $NoMotion) { throw "-NoMotion is required" }
if (-not $ShutdownOnExit) { throw "-ShutdownOnExit is required" }
if ($LaneCount -ne 2) { throw "LaneCount must be exactly 2" }
if ([Convert]::ToInt32($MaxLaneMask, 16) -ne 3) { throw "MaxLaneMask must be 0x3" }
if ($MaxRuntimeSec -le 0 -or $MaxRuntimeSec -gt 7560) { throw "MaxRuntimeSec must be in 1..7560" }
if (Test-Path -LiteralPath (Join-Path $repoRoot ".hardware_authorization\ABORT_NOW.txt")) { throw "P6 abort file is present" }
foreach ($required in @($bitFull,$ltxFull,$profileFull,$txnFull,$authFull,$activeXdc,$pinmap,$shutdownBit,$shutdownTcl,$stageTcl,$VivadoPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Required P6 file missing: $required" }
}
$authText = Get-Content -Raw -LiteralPath $authFull
foreach ($phrase in @(
    "P6_LOCAL_TRANSPORT_APPROVED",
    "AUTHORIZED_STAGE=P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET",
    "NETWORK_CABLE_CONNECTED=false",
    "HARDWARE_MOVEMENT_ALLOWED=false",
    "AVAILABLE_LANES=2",
    "MAX_LANE_MASK=0x3",
    "SHUTDOWN_ON_EXIT=required"
)) { if ($authText -notmatch [regex]::Escape($phrase)) { throw "Authorization phrase missing: $phrase" } }
$authRuntime = [regex]::Match($authText, '(?m)^MAX_RUNTIME_SEC=(\d+)\s*$')
if (-not $authRuntime.Success -or [int]$authRuntime.Groups[1].Value -lt $MaxRuntimeSec) { throw "Authorization runtime is lower than requested" }

$profileJson = Get-Content -Raw -LiteralPath $profileFull | ConvertFrom-Json
if ($profileJson.network_required -ne $false -or $profileJson.motion_required -ne $false) { throw "Profile violates no-Ethernet/no-motion boundary" }
if ($profileJson.lane_count -ne 2 -or [Convert]::ToInt32([string]$profileJson.max_lane_mask,16) -ne 3) { throw "Profile violates 2-lane scope" }
if ($profileJson.shutdown_on_exit -ne $true -or [int]$profileJson.startup_wait_us -lt 500) { throw "Profile violates TFDU startup/shutdown contract" }
if ([int]$profileJson.max_runtime_sec -lt $MaxRuntimeSec) { throw "Profile runtime is lower than requested" }

Require-Hash "candidate bitstream" $bitFull $BitstreamSha256
Require-Hash "candidate ltx" $ltxFull $LtxSha256
Require-Hash "profile" $profileFull $ProfileSha256
Require-Hash "active XDC" $activeXdc $ActiveXdcSha256
Require-Hash "pinmap" $pinmap $PinmapSha256
Require-Hash "shutdown bitstream" $shutdownBit $ShutdownBitstreamSha256

Add-Content -LiteralPath $summary -Encoding ascii -Value "STAGE=$Stage"
Add-Content -LiteralPath $summary -Encoding ascii -Value "BITSTREAM=$bitFull"
Add-Content -LiteralPath $summary -Encoding ascii -Value "BITSTREAM_SHA256=$((Get-Sha $bitFull))"
Add-Content -LiteralPath $summary -Encoding ascii -Value "LTX_SHA256=$((Get-Sha $ltxFull))"
Add-Content -LiteralPath $summary -Encoding ascii -Value "PROFILE_SHA256=$((Get-Sha $profileFull))"
Add-Content -LiteralPath $summary -Encoding ascii -Value "NETWORK_CABLE_CONNECTED=false"
Add-Content -LiteralPath $summary -Encoding ascii -Value "HARDWARE_MOVEMENT_ALLOWED=false"
Add-Content -LiteralPath $summary -Encoding ascii -Value "MAX_LANE_MASK=0x3"

$beforeOk = Invoke-Shutdown "before_stage"
if (-not $beforeOk) {
    Add-Content -LiteralPath $summary -Encoding ascii -Value "P6_SAFE_STAGE_STATUS=FAIL_SHUTDOWN_BEFORE"
    exit 31
}

$stageStdout = Join-Path $evidenceFull "p6_stage.stdout.log"
$stageStderr = Join-Path $evidenceFull "p6_stage.stderr.log"
$stageRc = 125
$afterOk = $false
try {
    $stageRc = Invoke-Logged $VivadoPath @(
        "-mode", "batch", "-source", $stageTcl, "-tclargs",
        $repoRoot, $bitFull, $ltxFull, $txnFull, $resultFull, $HwServerUrl, [string]$JtagFrequencyHz
    ) $stageStdout $stageStderr $MaxRuntimeSec
} finally {
    $afterOk = Invoke-Shutdown "after_stage"
}
Add-Content -LiteralPath $summary -Encoding ascii -Value "P6_STAGE_RAW_EXIT=$stageRc"
Add-Content -LiteralPath $summary -Encoding ascii -Value "SHUTDOWN_EXIT=$(if($afterOk){0}else{1})"
if (-not $afterOk) {
    Add-Content -LiteralPath $summary -Encoding ascii -Value "P6_SAFE_STAGE_STATUS=FAIL_SHUTDOWN_AFTER"
    exit 32
}
$stageText = Get-Content -Raw -LiteralPath $stageStdout
if ($stageText -notmatch "P6_CANDIDATE_PROGRAMMED=1" -or $stageText -notmatch "P6_JTAG_AXI_TRANSACTIONS=PASS") {
    Add-Content -LiteralPath $summary -Encoding ascii -Value "P6_SAFE_STAGE_STATUS=FAIL_MISSING_MARKER"
    exit $(if($stageRc -ne 0 -and $stageRc -ne 125){$stageRc}else{33})
}
Add-Content -LiteralPath $summary -Encoding ascii -Value "P6_SAFE_STAGE_STATUS=PASS"
Add-Content -LiteralPath $summary -Encoding ascii -Value "P6_SAFE_STAGE_END=$(Get-Date -Format o)"
exit 0
