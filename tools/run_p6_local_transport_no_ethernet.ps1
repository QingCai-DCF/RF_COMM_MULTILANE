param(
  [switch]$AuthorizeHardware,
  [switch]$NoEthernet,
  [switch]$NoMotion,
  [int]$LaneCount = 2,
  [string]$MaxLaneMask = "0x3",
  [switch]$UserConfirmedSupplyOk,
  [switch]$ShutdownOnExit,
  [int]$MaxRuntimeSec = 7560,
  [string]$BoardId = "AX7010",
  [switch]$JsonSummary,
  [string]$StageFilter = "all"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
$python = "python"
$argsList = @(
  "$scriptDir\run_p6_local_transport_no_ethernet.py",
  "--lane-count", "$LaneCount",
  "--max-lane-mask", "$MaxLaneMask",
  "--max-runtime-sec", "$MaxRuntimeSec",
  "--board-id", "$BoardId",
  "--stage-filter", "$StageFilter"
)
if ($AuthorizeHardware) { $argsList += "--authorize-hardware" }
if ($NoEthernet) { $argsList += "--no-ethernet" }
if ($NoMotion) { $argsList += "--no-motion" }
if ($UserConfirmedSupplyOk) { $argsList += "--user-confirmed-supply-ok" }
if ($ShutdownOnExit) { $argsList += "--shutdown-on-exit" }
if ($JsonSummary) { $argsList += "--json-summary" }

Push-Location $root
try {
  & $python @argsList
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
