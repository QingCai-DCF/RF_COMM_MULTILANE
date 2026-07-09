param(
  [switch]$DryRun,
  [switch]$AllowHardware,
  [switch]$ExecuteHardware,
  [string]$AuthorizationFile = ".hardware_authorization\P5_2LANE_APPROVED.txt",
  [string]$BoardId = "AX7010",
  [int]$MaxRuntimeSec = 0,
  [string]$Profile = "",
  [string]$ProfileSha256 = "",
  [string]$Bitstream = "",
  [string]$BitstreamSha256 = "",
  [string]$ActivePinmapHash = "",
  [string]$ActiveXdcHash = "",
  [string]$ShutdownBitstream = "shutdown_bitstream\tfdu_shutdown_j10_j11.bit",
  [string]$ShutdownBitstreamSha256 = "",
  [switch]$ShutdownOnExit,
  [switch]$JsonSummary,
  [string]$StageFilter = "all",
  [switch]$StopOnFirstFail,
  [switch]$SkipEthernet = $true,
  [switch]$SkipMotion = $true,
  [int]$LaneCount = 2,
  [switch]$ReuseExistingRecheck
)

$ErrorActionPreference = "Stop"

$argsList = @("tools/run_p5_2lane_protocol_stabilization.py")
if ($DryRun -or -not $ExecuteHardware) { $argsList += "--dry-run" }
if ($AllowHardware) { $argsList += "--allow-hardware" }
if ($ExecuteHardware) { $argsList += "--execute-hardware" }
if ($AuthorizationFile) { $argsList += @("--authorization-file", $AuthorizationFile) }
if ($BoardId) { $argsList += @("--board-id", $BoardId) }
if ($MaxRuntimeSec -gt 0) { $argsList += @("--max-runtime-sec", "$MaxRuntimeSec") }
if ($Profile) { $argsList += @("--profile", $Profile) }
if ($ProfileSha256) { $argsList += @("--profile-sha256", $ProfileSha256) }
if ($Bitstream) { $argsList += @("--bitstream", $Bitstream) }
if ($BitstreamSha256) { $argsList += @("--bitstream-sha256", $BitstreamSha256) }
if ($ActivePinmapHash) { $argsList += @("--active-pinmap-hash", $ActivePinmapHash) }
if ($ActiveXdcHash) { $argsList += @("--active-xdc-hash", $ActiveXdcHash) }
if ($ShutdownBitstream) { $argsList += @("--shutdown-bitstream", $ShutdownBitstream) }
if ($ShutdownBitstreamSha256) { $argsList += @("--shutdown-bitstream-sha256", $ShutdownBitstreamSha256) }
if ($ShutdownOnExit) { $argsList += "--shutdown-on-exit" }
if ($JsonSummary) { $argsList += "--json-summary" }
if ($StageFilter) { $argsList += @("--stage-filter", $StageFilter) }
if ($StopOnFirstFail) { $argsList += "--stop-on-first-fail" }
if ($SkipEthernet) { $argsList += "--skip-ethernet" }
if ($SkipMotion) { $argsList += "--skip-motion" }
if ($LaneCount -ne 0) { $argsList += @("--lane-count", "$LaneCount") }
if ($ReuseExistingRecheck) { $argsList += "--reuse-existing-recheck" }

python @argsList
