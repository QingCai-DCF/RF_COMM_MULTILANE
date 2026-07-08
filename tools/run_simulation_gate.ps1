param(
  [switch]$NoHardware = $true,
  [switch]$JsonSummary,
  [switch]$AllowSkips,
  [string]$OutputDir = "evidence/generated",
  [string]$P1RecheckStatus = "NOT_RUN_STANDALONE"
)

$ErrorActionPreference = "Stop"
if (-not $NoHardware) {
  throw "P2 simulation gate refuses hardware mode."
}

$argsList = @("tools/run_simulation_gate.py", "--output-dir", $OutputDir, "--p1-recheck-status", $P1RecheckStatus)
if ($JsonSummary) { $argsList += "--json-summary" }
if ($AllowSkips) { $argsList += "--allow-skips" }
python @argsList
