param(
  [switch]$NoHardware = $true,
  [switch]$AllowSkips,
  [switch]$JsonSummary,
  [switch]$SkipP1P2Recheck
)

$ErrorActionPreference = "Stop"
if (-not $NoHardware) {
  throw "P3 pre-hardware gate refuses hardware mode."
}

$argsList = @("tools/run_pre_hw_acceptance_package_gate.py", "--no-hardware")
if ($AllowSkips) { $argsList += "--allow-skips" }
if ($JsonSummary) { $argsList += "--json-summary" }
if ($SkipP1P2Recheck) { $argsList += "--skip-p1-p2-recheck" }
python @argsList
