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

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$argsList = @(
  "-File", "$scriptDir\run_p6_local_transport_no_ethernet.ps1",
  "-LaneCount", "$LaneCount",
  "-MaxLaneMask", "$MaxLaneMask",
  "-MaxRuntimeSec", "$MaxRuntimeSec",
  "-BoardId", "$BoardId",
  "-StageFilter", "$StageFilter"
)
if ($AuthorizeHardware) { $argsList += "-AuthorizeHardware" }
if ($NoEthernet) { $argsList += "-NoEthernet" }
if ($NoMotion) { $argsList += "-NoMotion" }
if ($UserConfirmedSupplyOk) { $argsList += "-UserConfirmedSupplyOk" }
if ($ShutdownOnExit) { $argsList += "-ShutdownOnExit" }
if ($JsonSummary) { $argsList += "-JsonSummary" }

powershell -NoProfile -ExecutionPolicy Bypass @argsList
exit $LASTEXITCODE
