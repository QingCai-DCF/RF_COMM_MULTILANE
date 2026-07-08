# Migration Notes

Legacy RF_COMM files were imported under `legacy/RF_COMM/`, `rtl/legacy_reference/`,
`software/legacy_*`, and `evidence/imported/`. These files are traceability
references only.

Canonical rebuild inputs are the generated pinmap/XDC, JSON profiles, new RTL
skeletons under `rtl/`, and the register map at
`config/register_map/ir_axi_regs.yaml`.

Start replay from `G1_LANE0_BASELINE` with lane1 disabled and AB_L1 treated as a
known-bad raw direction until fresh hardware evidence clears it.
