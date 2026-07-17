param([switch]$JsonSummary, [switch]$VerifyExisting, [switch]$NoFullRegression)
$ErrorActionPreference = 'Stop'
$env:NO_HARDWARE = '1'
$arguments = @('scripts/run_p8c_safety_gate.py')
if ($JsonSummary) { $arguments += '--json-summary' }
if ($VerifyExisting) { $arguments += '--verify-existing' }
if ($NoFullRegression) { $arguments += '--no-full-regression' }
& python @arguments
exit $LASTEXITCODE
