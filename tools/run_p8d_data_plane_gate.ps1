[CmdletBinding()]
param(
    [switch]$JsonSummary,
    [switch]$VerifyExisting,
    [switch]$AllowSkips,
    [ValidateSet('all', 'Z7010_2LANE_DEV', 'Z7020_ROTATING_8LANE_MODEL',
        'Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE')]
    [string]$Profile = 'all',
    [switch]$Quick,
    [switch]$Full
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:NO_HARDWARE = '1'
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = 'false'
$arguments = @('scripts/run_p8d_data_plane_gate.py', '--profile', $Profile)
if ($JsonSummary) { $arguments += '--json-summary' }
if ($VerifyExisting) { $arguments += '--verify-existing' }
if ($AllowSkips) { $arguments += '--allow-skips' }
if ($Quick) { $arguments += '--quick' }
if ($Full) { $arguments += '--full' }

Push-Location $repoRoot
try {
    & python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
