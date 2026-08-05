# P10 P8D source-binding re-verification

- Status: `PASS`
- Verified source commit: `99c83fc58488eba1a86751b6259ac7ed9b3d2999`
- Hardware actions executed: `false`
- Scope: refresh only current-source P8D bindings affected by the P10.3 retry path-diversity change; no hardware scope is promoted.
- Raw run: `evidence/generated/p10_3_retry_path_diversity_source_reverification/raw/20260805T004912.446359Z`

| Simulation | Result |
|---|---|
| `tb_ir_scheduler_migration` | `PASS` |
| `tb_ir_selective_repeat_tx` | `PASS` |
| `tb_ir_sack_ack_aggregation` | `PASS` |
| `tb_ir_data_plane_integration_2lane` | `PASS` |
| `tb_ir_data_plane_integration_8lane` | `PASS` |
