# Bitstream Candidate Policy

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P3 may audit or build a bitstream candidate with non-hardware Vivado actions
only. P3 must never mark `BITSTREAM_PROGRAMMED` or reserved status `HARDWARE_PASS`.

## Status Vocabulary

- `SIMULATION_PASS`: offline simulation passed.
- `SYNTHESIS_PASS`: synthesis completed without hardware manager.
- `IMPLEMENTATION_PASS`: place/route completed without hardware manager.
- `BITSTREAM_GENERATED_NO_HW`: bitstream file generated but not programmed.
- `BITSTREAM_PROGRAMMED`: reserved for future authorized P4/P5 evidence only.
- `HARDWARE_PASS`: reserved for future authorized evidence only and forbidden in P3 claims.

Allowed non-hardware Vivado actions: `read_verilog`, `read_xdc`, `synth_design`,
`opt_design`, `place_design`, `route_design`, `write_bitstream`,
`report_timing_summary`, and `report_utilization`.

Forbidden hardware actions: `open_hw`, `connect_hw_server`, `open_hw_target`,
`program_hw_devices`, and `refresh_hw_device`.
