# P8D canonical data-plane configuration

- Status: `PASS`
- Test ID: `P8D-CANONICAL-CONFIG`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `36e7ecd07b67b385d433f69ec754af6db473a3a6`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/canonical_config.log",
  "config_path": "config/p8d_data_plane.yaml",
  "config_sha256": "2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02",
  "generated_utc": "2026-07-26T13:43:03.686896Z",
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
  "source_commit": "36e7ecd07b67b385d433f69ec754af6db473a3a6",
  "status": "PASS",
  "test_id": "P8D-CANONICAL-CONFIG"
}
```
