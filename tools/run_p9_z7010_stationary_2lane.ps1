[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$BuildOnly,
    [switch]$Formal,
    [string]$AuthorizeFrom = "config/p9_current_run_authorization.json",
    [string]$RunId = "",
    [string]$Stage = "P9-00",
    [int]$MaxRuntime = 0,
    [string]$LaneMask = "0x1",
    [switch]$JsonSummary
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$arguments = @(
    "scripts/run_p9_z7010_stationary_2lane.py",
    "--authorize-from", $AuthorizeFrom,
    "--stage", $Stage,
    "--max-runtime", $MaxRuntime,
    "--lane-mask", $LaneMask
)
if ($DryRun) { $arguments += "--dry-run" }
if ($BuildOnly) { $arguments += "--build-only" }
if ($Formal) { $arguments += "--formal" }
if ($RunId) { $arguments += @("--run-id", $RunId) }
if ($JsonSummary) { $arguments += "--json-summary" }

Push-Location $repoRoot
try {
    & python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
