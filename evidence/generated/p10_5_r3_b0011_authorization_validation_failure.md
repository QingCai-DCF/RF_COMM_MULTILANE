# P10.5 R3 B0011 authorization validation failure

- Status: `FAIL_PRE_HARDWARE`
- Run ID: `p10_5_20260827T101906Z_e1f8c01a_4015142e_79607d01`
- R3 binding: `B0011`
- Hardware actions executed: `false`
- Shutdown required: `false` (validation stopped before any hardware connection or action)

The authorization copied stale offline-input hashes for the previous module identity records and host harness. The rejected authorization and its commit remain immutable. The remediation refreezes the unchanged target artifacts against the current committed records while allowing only semantically verified module-identity metadata changes; electrical wiring, topology, RTL, firmware, XDC, register-map, and protocol configuration remain fail-closed.
