# P8D canonical data-plane configuration

- Status: `PASS`
- Test ID: `P8D-CANONICAL-CONFIG`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `19bdeced49b01804611c2ce56a114b3fc164745c`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "evidence/generated/p9_final_source_p8d_19bdeced/p8d_raw/formal_19bdeced49b0/canonical_config.log",
  "config_path": "config/p8d_data_plane.yaml",
  "config_sha256": "2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02",
  "generated_utc": "2026-07-28T18:37:52.344587Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "schema_validation": {
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
    "NO_HARDWARE_ACTIONS_EXECUTED": true,
    "profile": "P8D_MULTI_PROFILE_OFFLINE",
    "schema_version": 1,
    "source_path": "config/p8d_data_plane.yaml",
    "source_sha256": "2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02",
    "status": "PASS",
    "test_id": "P8D-CANONICAL-CONFIG-SCHEMA",
    "validation": {
      "active_window_less_than_half_space": true,
      "descriptor_layout_bytes_covered": 64,
      "minimum_outstanding": 32,
      "minimum_sack_bits": 32,
      "profile_count": 3,
      "profiles": [
        "Z7010_2LANE_DEV",
        "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE",
        "Z7020_ROTATING_8LANE_MODEL"
      ],
      "sequence_space": 65536,
      "status": "PASS"
    }
  },
  "schema_version": 1,
  "source_commit": "19bdeced49b01804611c2ce56a114b3fc164745c",
  "status": "PASS",
  "test_id": "P8D-CANONICAL-CONFIG"
}
```
