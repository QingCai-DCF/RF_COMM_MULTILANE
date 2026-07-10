param(
  [switch]$ExecuteHardware,
  [switch]$NoEthernet,
  [switch]$NoMotion,
  [int]$LaneCount = 2,
  [string]$MaxLaneMask = "0x3",
  [switch]$Include2hSoak,
  [switch]$JsonSummary
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
$arguments = @(
  "$scriptDir\run_p6_authorized_hardware_sequence.py",
  "--lane-count", "$LaneCount",
  "--max-lane-mask", "$MaxLaneMask"
)
if ($ExecuteHardware) { $arguments += "--execute-hardware" }
if ($NoEthernet) { $arguments += "--no-ethernet" }
if ($NoMotion) { $arguments += "--no-motion" }
if ($Include2hSoak) { $arguments += "--include-2h-soak" }
if ($JsonSummary) { $arguments += "--json-summary" }

Push-Location $root
try {
  & python @arguments
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
