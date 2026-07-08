param([switch]$NoHardware)
$ErrorActionPreference = 'Stop'
if (-not $NoHardware) { Write-Host 'NO_HARDWARE defaults to enabled for this project.' }
python scripts/run_offline_gates.py
