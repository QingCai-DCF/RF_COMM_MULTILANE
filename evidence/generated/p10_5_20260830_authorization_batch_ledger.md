# P10.5 Ten-run Authorization Ledger

- Maximum distinct current-run authorizations: `10`
- Used: `3`
- Remaining: `7`
- Next ordinal: `4`

Run 1 (`p10_5_20260830T095106Z_e1f8c01a_4015142e_79607d01`) failed closed in `one_plus_one`; both fixed and rotating shutdown verification passed. The immutable failure evidence is preserved and will not be overwritten.

Run 2 (`p10_5_20260830T101446Z_e1f8c01a_4015142e_79607d01`) passed the complete `1+1`, `2+1`, `1+2`, `2+2`, role-commit, performance, and five simultaneous bidirectional 64 MiB stages. It failed closed in `faults` at `fault_abort_r2f`; both fixed and rotating shutdown verification passed, and the required half-runtime cooldown completed. The immutable failure evidence is preserved and will not be overwritten.

Run 3 (`p10_5_20260830T123451Z_e1f8c01a_4015142e_79607d01`) passed every pre-formal stage, including the complete fault matrix and `fault_abort_r2f`. Its direct 1800-second hardware formal case also reported PASS with zero formal transport timeouts and zero integrity, protocol, DMA, and safety hard counters. The overall run remains immutable FAIL because the old host guard compared the 1800.336-second conservative observation/shutdown envelope with the 1800-second TX-capable limit. Both shutdowns passed. A separate no-TX rest observation confirmed 900.955 seconds after shutdown, exceeding the required 900.168 seconds, before any later hardware action. The remediation and exact evidence hashes are in `p10_5_20260830_run3_formal_runtime_guard_diagnosis.json`.
