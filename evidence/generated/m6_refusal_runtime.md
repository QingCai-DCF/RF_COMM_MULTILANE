# M6 Runtime Refusal Gate

M6_REFUSAL_RUNTIME_REPORT=1
M6_RUN_LANE0_RAW_MATRIX_EXIT_ZERO=1
M6_RUN_LANE0_RAW_MATRIX_REFUSED_MARKER=1
M6_RUN_LANE0_RAW_MATRIX_NO_HARDWARE_MARKER=1
M6_RUN_LANE0_RAW_MATRIX_STATUS_MARKER=1
M6_RUN_LANE0_RAW_MATRIX_MANIFEST_EXISTS=1
M6_RUN_LANE0_RAW_MATRIX_MANIFEST_NO_HARDWARE=1
M6_RUN_LANE0_RAW_MATRIX_MANIFEST_ALLOW_FALSE=1
M6_RUN_G1_LANE0_REPLAY_EXIT_ZERO=1
M6_RUN_G1_LANE0_REPLAY_REFUSED_MARKER=1
M6_RUN_G1_LANE0_REPLAY_NO_HARDWARE_MARKER=1
M6_RUN_G1_LANE0_REPLAY_STATUS_MARKER=1
M6_RUN_G1_LANE0_REPLAY_MANIFEST_EXISTS=1
M6_RUN_G1_LANE0_REPLAY_MANIFEST_NO_HARDWARE=1
M6_RUN_G1_LANE0_REPLAY_MANIFEST_ALLOW_FALSE=1
M6_PROGRAM_TFDU_SHUTDOWN_EXIT_ZERO=1
M6_PROGRAM_TFDU_SHUTDOWN_REFUSED_MARKER=1
M6_PROGRAM_TFDU_SHUTDOWN_NO_HARDWARE_MARKER=1
M6_PROGRAM_TFDU_SHUTDOWN_STATUS_MARKER=1
M6_PROGRAM_TFDU_SHUTDOWN_MANIFEST_EXISTS=1
M6_PROGRAM_TFDU_SHUTDOWN_MANIFEST_NO_HARDWARE=1
M6_PROGRAM_TFDU_SHUTDOWN_MANIFEST_ALLOW_FALSE=1
M6_REFUSAL_RUNTIME=PASS

| Wrapper | Summary | Manifest |
|---|---|---|
| RUN_LANE0_RAW_MATRIX | `evidence/generated/hw_preflight/refusal_gate/run_lane0_raw_matrix/run_lane0_raw_matrix_safe.summary.txt` | `evidence/generated/hw_preflight/refusal_gate/run_lane0_raw_matrix/hash_manifest.json` |
| RUN_G1_LANE0_REPLAY | `evidence/generated/hw_preflight/refusal_gate/run_g1_lane0_replay/run_g1_lane0_replay_safe.summary.txt` | `evidence/generated/hw_preflight/refusal_gate/run_g1_lane0_replay/hash_manifest.json` |
| PROGRAM_TFDU_SHUTDOWN | `evidence/generated/hw_preflight/refusal_gate/program_tfdu_shutdown/program_tfdu_shutdown_safe.summary.txt` | `evidence/generated/hw_preflight/refusal_gate/program_tfdu_shutdown/hash_manifest.json` |

This gate executes only the default no-authorization path. It does not pass `-AllowHardware`, and the wrappers must refuse before any hardware action.
