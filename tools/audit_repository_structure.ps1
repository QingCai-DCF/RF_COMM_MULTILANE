param(
    [switch]$JsonSummary
)

$env:NO_HARDWARE = "1"
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = "false"

$arguments = @("scripts/audit_repository_structure.py")
if ($JsonSummary) {
    $arguments += "--json-summary"
}

& python @arguments
exit $LASTEXITCODE
