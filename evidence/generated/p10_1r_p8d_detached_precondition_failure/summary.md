# P10.1R P8D detached-worktree precondition failure

- Status: `RECORDED_PRECONDITION_FAILURE`
- Source commit: `493955d5788942ac448a9cfd99c97f0c526281fe`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`
- Network used: `false`

The first exact-source P8D invocation ran from a detached replay worktree. Its
`git branch --show-current` result was empty, so the mandatory
`P8C_BASELINE_RECHECK` rejected the run even though no mandatory functional
data-plane test failed. The raw failure summaries are preserved under `raw/`;
this record does not rewrite that run as PASS.

The replay worktree was then attached to the exact
`p10.1r/2lane-speed-stability-remediation` branch and P8D was rerun into a new
output directory. That corrected rerun passed all mandatory gates. Its final
summary is frozen at
`evidence/generated/p10_1r_full_offline_regression/p8d/p8d_final_summary.json`
with SHA256
`7470973f4edf8134ca884bba40833c2b1c48ba76e9c70b26f642ea79311f6be9`.

`19P2MBPS_STRETCH_FEASIBILITY=FAIL` remains visible as the gate's declared
non-blocking model outcome; it is not reported as a hardware result.
