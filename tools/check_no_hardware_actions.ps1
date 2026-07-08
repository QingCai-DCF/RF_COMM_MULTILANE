param([switch]$NoHardware = $true)
$ErrorActionPreference = "Stop"
if (-not $NoHardware) { throw "Hardware mode is not allowed for this static scan." }
python tools/check_no_hardware_actions.py
