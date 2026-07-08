param(
  [switch]$NoHardware = $true,
  [switch]$Strict,
  [switch]$AllowSkips,
  [string]$OutputDir = "evidence/generated",
  [switch]$JsonSummary,
  [switch]$IncludeSimulation,
  [switch]$IncludePreHwPackage,
  [switch]$SimulationRequired,
  [switch]$AllowSimulationSkip
)

$ErrorActionPreference = "Stop"
if (-not $NoHardware) {
  throw "P1 offline gate refuses hardware mode. Use future safe wrappers only after explicit authorization."
}

Write-Host "RF_COMM_MULTILANE P1 offline gate"
Write-Host "PWD=$(Get-Location)"
$head = git rev-parse HEAD
Write-Host "GIT_HEAD=$head"
Write-Host "NO_HARDWARE_ACTIONS_EXECUTED: true"
Write-Host "HARDWARE_ACCEPTANCE: PENDING_HW"

$argsList = @("tools/run_offline_gate.py", "--output-dir", $OutputDir)
if ($Strict) { $argsList += "--strict" }
if ($AllowSkips) { $argsList += "--allow-skips" }
if ($JsonSummary) { $argsList += "--json-summary" }
if ($IncludeSimulation) { $argsList += "--include-simulation" }
if ($IncludePreHwPackage) { $argsList += "--include-pre-hw-package" }
if ($SimulationRequired) { $argsList += "--simulation-required" }
if ($AllowSimulationSkip) { $argsList += "--allow-simulation-skip" }
python @argsList
