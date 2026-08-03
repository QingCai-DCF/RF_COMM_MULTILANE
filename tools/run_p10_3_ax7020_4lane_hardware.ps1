param(
  [switch]$SelfTest,
  [string]$Request = ""
)
$ErrorActionPreference = "Stop"
$env:NO_HARDWARE = "1"
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = "false"
$arguments = @("scripts/run_p10_3_ax7020_4lane_hardware.py")
if ($SelfTest) { $arguments += "--self-test" }
if ($Request -ne "") { $arguments += @("--request", $Request) }
& python @arguments
exit $LASTEXITCODE
