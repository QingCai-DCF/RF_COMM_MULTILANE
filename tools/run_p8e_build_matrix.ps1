param(
  [string]$Profile = "all",
  [string]$Strategy = "all",
  [string]$OutputRoot = "evidence/generated/p8e_raw/build_matrix"
)
$env:NO_HARDWARE = "1"
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = "false"
python scripts/run_p8e_build_matrix.py --profile $Profile --strategy $Strategy `
  --output-root $OutputRoot --json-summary
exit $LASTEXITCODE
