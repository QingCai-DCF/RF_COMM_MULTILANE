[CmdletBinding()]
param(
    [switch]$ExecuteHardware,
    [string]$AuthorizationFile = "",
    [string]$AuthorizationSha256 = "",
    [string]$BoardId = "",
    [string]$ExpectedPart = "",
    [string]$ExpectedTarget = "",
    [string]$SourceCommit = "",
    [string]$PlanFile = "",
    [string]$PlanSha256 = "",
    [string]$Bitstream = "",
    [string]$BitstreamSha256 = "",
    [string]$Xsa = "",
    [string]$XsaSha256 = "",
    [string]$Elf = "",
    [string]$ElfSha256 = "",
    [string]$Profile = "",
    [string]$ProfileSha256 = "",
    [string]$ActiveXdc = "",
    [string]$ActiveXdcSha256 = "",
    [string]$Pinmap = "",
    [string]$PinmapSha256 = "",
    [string]$RegisterMap = "",
    [string]$RegisterMapSha256 = "",
    [string]$ShutdownBitstream = "",
    [string]$ShutdownBitstreamSha256 = "",
    [string]$Ltx = "",
    [string]$LtxSha256 = "",
    [int]$MaxRuntimeSec = 0,
    [switch]$ShutdownOnExit,
    [switch]$NoEthernet,
    [switch]$NoMotion,
    [int]$LaneCount = 0,
    [string]$MaxLaneMask = "",
    [string]$AbortFile = "",
    [string]$VivadoPath = "",
    [string]$HwServerUrl = "localhost:3121",
    [string]$EvidenceDir = "",
    [int]$PreflightTimeoutSec = 180,
    [switch]$JsonSummary,
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$pythonScript = Join-Path $scriptDir "run_p7_authorized_hardware_sequence.py"

$arguments = @($pythonScript)
function Add-StringArgument([string]$Name, [string]$Value) {
    if ($Value) {
        $script:arguments += @($Name, $Value)
    }
}

if ($ExecuteHardware) { $arguments += "--execute-hardware" }
Add-StringArgument "--authorization-file" $AuthorizationFile
Add-StringArgument "--authorization-sha256" $AuthorizationSha256
Add-StringArgument "--board-id" $BoardId
Add-StringArgument "--expected-part" $ExpectedPart
Add-StringArgument "--expected-target" $ExpectedTarget
Add-StringArgument "--source-commit" $SourceCommit
Add-StringArgument "--plan-file" $PlanFile
Add-StringArgument "--plan-sha256" $PlanSha256
Add-StringArgument "--bitstream" $Bitstream
Add-StringArgument "--bitstream-sha256" $BitstreamSha256
Add-StringArgument "--xsa" $Xsa
Add-StringArgument "--xsa-sha256" $XsaSha256
Add-StringArgument "--elf" $Elf
Add-StringArgument "--elf-sha256" $ElfSha256
Add-StringArgument "--profile" $Profile
Add-StringArgument "--profile-sha256" $ProfileSha256
Add-StringArgument "--active-xdc" $ActiveXdc
Add-StringArgument "--active-xdc-sha256" $ActiveXdcSha256
Add-StringArgument "--pinmap" $Pinmap
Add-StringArgument "--pinmap-sha256" $PinmapSha256
Add-StringArgument "--register-map" $RegisterMap
Add-StringArgument "--register-map-sha256" $RegisterMapSha256
Add-StringArgument "--shutdown-bitstream" $ShutdownBitstream
Add-StringArgument "--shutdown-bitstream-sha256" $ShutdownBitstreamSha256
Add-StringArgument "--ltx" $Ltx
Add-StringArgument "--ltx-sha256" $LtxSha256
if ($MaxRuntimeSec -ne 0) { $arguments += @("--max-runtime-sec", [string]$MaxRuntimeSec) }
if ($ShutdownOnExit) { $arguments += "--shutdown-on-exit" }
if ($NoEthernet) { $arguments += "--no-ethernet" }
if ($NoMotion) { $arguments += "--no-motion" }
if ($LaneCount -ne 0) { $arguments += @("--lane-count", [string]$LaneCount) }
Add-StringArgument "--max-lane-mask" $MaxLaneMask
Add-StringArgument "--abort-file" $AbortFile
Add-StringArgument "--vivado-path" $VivadoPath
Add-StringArgument "--hw-server-url" $HwServerUrl
Add-StringArgument "--evidence-dir" $EvidenceDir
$arguments += @("--preflight-timeout-sec", [string]$PreflightTimeoutSec)
if ($JsonSummary) { $arguments += "--json-summary" }

Push-Location $repoRoot
try {
    & $PythonPath @arguments
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $exitCode
