param(
    [ValidateSet("quick", "full", "verify-existing")]
    [string]$Mode = "full",
    [switch]$JsonSummary,
    [switch]$AllowSkips,
    [switch]$NoCache
)

$env:NO_HARDWARE = "1"
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = "false"
$arguments = @("scripts/run_p10_1_offline_gate.py", "--$Mode")
if ($JsonSummary) {
    $arguments += "--json-summary"
}
if ($AllowSkips) {
    $arguments += "--allow-skips"
}
if ($NoCache) {
    $arguments += "--no-cache"
}
python @arguments
exit $LASTEXITCODE
