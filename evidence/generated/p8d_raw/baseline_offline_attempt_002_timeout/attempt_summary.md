# P8D-00 baseline offline regression attempt 2

- Result: `ABORTED_AFTER_OUTER_TIMEOUT_AND_CHILD_TERMINATION`
- Command: `python scripts/run_offline_gates.py --include-p8c --json-summary`
- Runner bound: `904 seconds`
- Failure classification: `OUTER_RUNNER_BOUND_TOO_SHORT_AND_TIMEOUT_DID_NOT_TERMINATE_PROCESS_TREE`
- Hardware actions executed: `false`

The canonical offline runner reached the fifth sequential Vivado stage,
`protocol_lane0`, after completing `safe_idle`, `tfdu_control_idle`,
`raw_pulse`, and `raw_lane_matrix`. The outer shell runner timed out before the
twelve-stage non-hardware build could complete, but its Python process tree
continued detached.

The timeout left a Vivado process tree rooted at PID `31484`. Its command line
was verified to reference this worktree, batch mode,
`scripts/vivado_nonhardware_build.tcl`, and `protocol_lane0`. Descendants
`24692` and `37332` and root `31484` were stopped and confirmed absent.

Twenty partial generated Vivado reports and ten corresponding logs/journals
were copied into this directory before any generated tracked output was
restored. Because terminating `protocol_lane0` made the aggregate result
irrecoverably failing, the subsequently observed detached nested P8C/P8B tree
was also stopped. The stopped PIDs were `30744`, `34300`, `26972`, `36668`,
`34328`, `35128`, `3440`, and `21908`; all were confirmed absent.

Thirty-nine later tracked outputs were preserved byte-for-byte under
`post_timeout_tracked_outputs`. Deletions of the P8C artifact and source
manifests were recorded before restoration. The next attempt uses a bounded
5,400-second runner limit.
