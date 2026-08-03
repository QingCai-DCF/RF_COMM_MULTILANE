[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$GateArguments
)

$ErrorActionPreference = 'Stop'
$env:NO_HARDWARE = '1'
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = 'false'
$env:NO_2H_QUALIFICATION = 'true'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot
try {
    & python 'scripts/run_p10_2_4lane_offline_gate.py' @GateArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
