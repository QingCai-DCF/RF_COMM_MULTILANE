# P8E Build Profiles

> Generated from `config/p8e_build_matrix.yaml`; do not edit by hand.

- Source SHA256: `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- Common-source core: `rtl/top/ir_endpoint_core.sv`
- Hardware scope: `NONE`

| Profile | Part | Role | Lanes | Modules | TX/RX/SACK | Board input |
|---|---|---|---:|---:|---|---|
| `Z7010_2LANE_DEV_IMPLEMENTATION` | `xc7z010clg400-1` | `DEVELOPMENT` | 2 | 2 | 32/32/32 | `constraints/active/PORT1.generated.xdc` |
| `Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION` | `xc7z020clg400-2` | `FIXED` | 8 | 32 | 64/64/64 | `PENDING_D12` |
| `Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION` | `xc7z020clg400-2` | `ROTATING` | 8 | 8 | 64/64/64 | `PENDING_D12` |

The two exact-part Z7020 profiles intentionally retain board pins and board I/O timing as `PENDING_D12`.
