param(
    [string]$Manifest = "",
    [switch]$ExecuteHardware,
    [switch]$JsonSummary
)

$env:NO_HARDWARE = "1"
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = "false"
$arguments = @("scripts/run_p10_1_hardware_performance.py")
if ($Manifest) {
    $arguments += @("--manifest", $Manifest)
}
if ($ExecuteHardware) {
    $arguments += "--execute-hardware"
}
if ($JsonSummary) {
    $arguments += "--json-summary"
}
python @arguments
exit $LASTEXITCODE
