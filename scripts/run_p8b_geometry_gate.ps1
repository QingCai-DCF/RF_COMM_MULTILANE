param(
    [switch]$JsonSummary,
    [switch]$ParentOfflinePass
)

$env:NO_HARDWARE = '1'
$arguments = @('scripts/run_p8b_geometry_gate.py')
if ($JsonSummary) { $arguments += '--json-summary' }
if ($ParentOfflinePass) { $arguments += '--parent-offline-pass' }
& python @arguments
exit $LASTEXITCODE
