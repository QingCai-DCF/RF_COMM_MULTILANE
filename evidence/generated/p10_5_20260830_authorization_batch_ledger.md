# P10.5 Ten-run Authorization Ledger

- Maximum distinct current-run authorizations: `10`
- Used: `2`
- Remaining: `8`
- Next ordinal: `3`

Run 1 (`p10_5_20260830T095106Z_e1f8c01a_4015142e_79607d01`) failed closed in `one_plus_one`; both fixed and rotating shutdown verification passed. The immutable failure evidence is preserved and will not be overwritten.

Run 2 (`p10_5_20260830T101446Z_e1f8c01a_4015142e_79607d01`) passed the complete `1+1`, `2+1`, `1+2`, `2+2`, role-commit, performance, and five simultaneous bidirectional 64 MiB stages. It failed closed in `faults` at `fault_abort_r2f`; both fixed and rotating shutdown verification passed, and the required half-runtime cooldown completed. The immutable failure evidence is preserved and will not be overwritten.
