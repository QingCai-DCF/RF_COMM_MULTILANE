param(
  [switch]$NoHardware = $true,
  [switch]$Json
)

$ErrorActionPreference = "Stop"
if (-not $NoHardware) {
  throw "Simulator detection is offline-only and refuses hardware mode."
}

$argsList = @("tools/sim/detect_simulator.py")
if ($Json) {
  $argsList += "--json"
}
python @argsList
