# P10.5 R3=B0011 initial offline-gate failure

- Status: `FAIL_WITH_ROOT_CAUSE_IDENTIFIED`
- Hardware actions executed: `false`
- Root cause: `config/project_state.json` changed for the current R3=`B0011` binding, while `P8A-STATE-001`, `P8A-TRACE-001`, and `P8A-SCOPE-001` still bound the prior state hash and byte count.
- Remediation: bind those three requirements to SHA256 `68bc2217a656087479ea2e7f26d1dc93951ac19cfa9c22a5bdf0f4d15c6f86f6`, bytes `59054`, then rerun focused P8A checks and the complete offline gate.
- Scope: offline traceability only; no hardware action occurred.
