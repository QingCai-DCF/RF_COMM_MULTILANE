param(
  [switch]$DryRun,
  [switch]$ExecuteHardware,
  [switch]$RequireUserHwAuthorization,
  [string]$AuthorizationFile = ".hardware_authorization\P4_APPROVED.txt",
  [string]$Profile = "",
  [string]$BoardId = "",
  [string]$Bitstream = "",
  [string]$BitstreamSha256 = "",
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

$argsList = @("tools/run_p4_hardware_acceptance.py")
if ($DryRun -or -not $ExecuteHardware) { $argsList += "--dry-run" }
if ($ExecuteHardware) { $argsList += "--execute-hardware" }
if ($RequireUserHwAuthorization) { $argsList += "--require-user-hw-authorization" }
if ($AuthorizationFile) { $argsList += @("--authorization-file", $AuthorizationFile) }
if ($Profile) { $argsList += @("--profile", $Profile) }
if ($BoardId) { $argsList += @("--board-id", $BoardId) }
if ($Bitstream) { $argsList += @("--bitstream", $Bitstream) }
if ($BitstreamSha256) { $argsList += @("--bitstream-sha256", $BitstreamSha256) }
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
