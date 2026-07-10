[CmdletBinding()]
param(
    [switch]$JsonSummary,
    [switch]$AllowSkips,
    [switch]$SkipPsBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$arguments = @("tools/run_p7_gate.py")
if ($JsonSummary) { $arguments += "--json-summary" }
if ($AllowSkips) { $arguments += "--allow-skips" }
if ($SkipPsBuild) { $arguments += "--skip-ps-build" }
Push-Location $repoRoot
try {
    & python @arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
