param(
  [ValidateSet('quick','full','verify-existing')]
  [string]$Mode = 'full',
  [string]$Profile = 'all',
  [string]$Strategy = 'all'
)
$ErrorActionPreference = 'Stop'
$env:NO_HARDWARE = '1'
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = 'false'
$root = Split-Path -Parent $PSScriptRoot
$arguments = @('scripts/run_p8e_dual_target_gate.py', "--$Mode", '--profile', $Profile,
               '--strategy', $Strategy, '--json-summary')
& python @arguments
exit $LASTEXITCODE
