param(
  [switch]$DryRun,
  [switch]$AllowHardware,
  [switch]$ExecuteHardware,
  [string]$AuthorizationFile = ".hardware_authorization\P4_AUTO_APPROVED.txt",
  [switch]$UserConfirmedSupplyOk,
  [switch]$NoManualIntervention,
  [string]$BoardId = "",
  [string]$Bitstream = "",
  [string]$BitstreamSha256 = "",
  [string]$ProfilePath = "",
  [string]$ProfileSha256 = "",
  [string]$ActivePinmapHash = "",
  [string]$ActiveXdcHash = "",
  [int]$MaxRuntimeSec = 0,
  [switch]$ShutdownOnExit,
  [string]$Stage = "all",
  [switch]$JsonSummary,
  [switch]$AllowSkips,
  [switch]$SkipRecheck
)

$ErrorActionPreference = "Stop"

$argsList = @("tools/run_p4_auto_hardware_acceptance.py")
if ($DryRun -or -not $ExecuteHardware) { $argsList += "--dry-run" }
if ($AllowHardware) { $argsList += "--allow-hardware" }
if ($ExecuteHardware) { $argsList += "--execute-hardware" }
if ($AuthorizationFile) { $argsList += @("--authorization-file", $AuthorizationFile) }
if ($UserConfirmedSupplyOk) { $argsList += "--user-confirmed-supply-ok" }
if ($NoManualIntervention) { $argsList += "--no-manual-intervention" }
if ($BoardId) { $argsList += @("--board-id", $BoardId) }
if ($Bitstream) { $argsList += @("--bitstream", $Bitstream) }
if ($BitstreamSha256) { $argsList += @("--bitstream-sha256", $BitstreamSha256) }
if ($ProfilePath) { $argsList += @("--profile-path", $ProfilePath) }
if ($ProfileSha256) { $argsList += @("--profile-sha256", $ProfileSha256) }
if ($ActivePinmapHash) { $argsList += @("--active-pinmap-hash", $ActivePinmapHash) }
if ($ActiveXdcHash) { $argsList += @("--active-xdc-hash", $ActiveXdcHash) }
if ($MaxRuntimeSec -gt 0) { $argsList += @("--max-runtime-sec", "$MaxRuntimeSec") }
if ($ShutdownOnExit) { $argsList += "--shutdown-on-exit" }
if ($Stage) { $argsList += @("--stage", $Stage) }
if ($JsonSummary) { $argsList += "--json-summary" }
if ($AllowSkips) { $argsList += "--allow-skips" }
if ($SkipRecheck) { $argsList += "--skip-recheck" }

python @argsList
