# P10 P8D source-binding re-verification

- Status: `PASS`
- Verified source commit: `63ff1d08eeb60822c6ad350a32f56c5b30f45641`
- Hardware actions executed: `false`
- Scope: refresh only `L2-ARQ-002` and `L2-SACK-002`; no hardware scope is promoted.
- Raw run: `evidence/generated/p10_p8d_source_reverification/raw/20260730T133857.092818Z`

| Simulation | Result |
|---|---|
| `tb_ir_selective_repeat_tx` | `PASS` |
| `tb_ir_sack_ack_aggregation` | `PASS` |
| `tb_ir_data_plane_integration_2lane` | `PASS` |
| `tb_ir_data_plane_integration_8lane` | `PASS` |
