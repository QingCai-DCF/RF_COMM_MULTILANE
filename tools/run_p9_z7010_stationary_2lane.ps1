[CmdletBinding()]
param(
    [switch]$ExecuteHardware,
    [switch]$Formal,
    [switch]$DryRun,
    [Parameter(Mandatory = $true)]
    [string]$Authorization,
    [string]$RunId = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$entry = Join-Path $repoRoot "scripts\run_p9_z7010_stationary_2lane.py"
$authorizationPath = (Resolve-Path -LiteralPath $Authorization).Path
$authorizationRecord = Get-Content -LiteralPath $authorizationPath -Raw | ConvertFrom-Json
if ($authorizationRecord.artifact_binding_phase -ne "PHASE2_IMMUTABLE_ARTIFACTS_BOUND") {
    throw "P9 hardware wrapper requires a phase-2 immutable authorization record"
}
function Resolve-BoundArtifact([object]$Artifact, [string]$Label) {
    if (-not $Artifact.path -or -not $Artifact.sha256) {
        throw "P9 phase-2 record is missing $Label"
    }
    $candidate = Join-Path $repoRoot ([string]$Artifact.path).Replace('/', '\')
    return (Resolve-Path -LiteralPath $candidate).Path
}
$candidateBitstream = Resolve-BoundArtifact $authorizationRecord.candidate_bitstream "candidate bitstream"
$shutdownBitstream = Resolve-BoundArtifact $authorizationRecord.shutdown_bitstream "shutdown bitstream"
$psElf = Resolve-BoundArtifact $authorizationRecord.ps_elf "PS ELF"

$arguments = @(
    $entry,
    "--execute-hardware",
    "--authorize-from", $authorizationPath,
    "--bitstream", $candidateBitstream,
    "--shutdown-bitstream", $shutdownBitstream,
    "--elf", $psElf,
    "--max-runtime", "1800",
    "--lane-mask", "0x3",
    "--stage", "P9-04",
    "--json-summary"
)
if ($RunId) { $arguments += @("--run-id", $RunId) }

if ($ExecuteHardware.IsPresent -and $Formal.IsPresent -and -not $DryRun.IsPresent) {
    $env:NO_HARDWARE = "0"
    $arguments += "--formal"
} else {
    $env:NO_HARDWARE = "1"
    $arguments += "--dry-run"
}

& $Python @arguments
exit $LASTEXITCODE
