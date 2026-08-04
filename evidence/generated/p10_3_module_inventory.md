# P10.3 eight-module inventory

- Status: `PASS`
- Test ID: `P10_3-INV-001`
- Hardware actions executed: `false`

- Source commit: `8b9563a37728a81850223f938e0b06e5772ec039`
- Canonical SHA256: `1293702c8d80e1365ee022ecadd72761cda81d6c190f8f7babf7f8b0396e92a9`

```json
{
  "active_module_count": 8,
  "active_modules": {
    "F0": {
      "endpoint": "AX7020-F/JTAG:210249855178",
      "inventory_status": "ACCEPTED_P10_1R_PENDING_P10_3_RECHECK",
      "position": "J10-A",
      "small_board_id": "A0019"
    },
    "F1": {
      "endpoint": "AX7020-F/JTAG:210249855178",
      "inventory_status": "ACCEPTED_P10_1R_PENDING_P10_3_RECHECK",
      "position": "J10-B",
      "small_board_id": "B0012"
    },
    "F2": {
      "endpoint": "AX7020-F/JTAG:210249855178",
      "inventory_status": "INSTALLED_PENDING_P10_3_INTAKE",
      "position": "J11-A",
      "small_board_id": "B0001"
    },
    "F3": {
      "endpoint": "AX7020-F/JTAG:210249855178",
      "inventory_status": "INSTALLED_PENDING_P10_3_INTAKE",
      "position": "J11-B",
      "small_board_id": "B0004"
    },
    "R0": {
      "endpoint": "AX7020-R/JTAG:210512180081",
      "inventory_status": "ACCEPTED_P10_1R_PENDING_P10_3_RECHECK",
      "position": "J10-A",
      "small_board_id": "A0010"
    },
    "R1": {
      "endpoint": "AX7020-R/JTAG:210512180081",
      "inventory_status": "ACCEPTED_P10_1R_PENDING_P10_3_RECHECK",
      "position": "J10-B",
      "small_board_id": "A0017"
    },
    "R2": {
      "endpoint": "AX7020-R/JTAG:210512180081",
      "inventory_status": "INSTALLED_PENDING_P10_3_INTAKE",
      "position": "J11-A",
      "small_board_id": "B0015"
    },
    "R3": {
      "endpoint": "AX7020-R/JTAG:210512180081",
      "inventory_status": "INSTALLED_PENDING_P10_3_INTAKE",
      "position": "J11-B",
      "small_board_id": "B0017"
    }
  },
  "bytes": 7774,
  "canonical_path": "config/hardware/tfdu_module_inventory.yaml",
  "electronic_intake_status": "PENDING_HARDWARE_STAGE",
  "errors": [],
  "hardware_actions_executed": false,
  "lane_pairs": {
    "lane0": "F0-R0",
    "lane1": "F1-R1",
    "lane2": "F2-R2",
    "lane3": "F3-R3"
  },
  "no_hardware": true,
  "old_f1_active": false,
  "old_f1_status": "QUARANTINED_NOT_ACCEPTED",
  "quarantine": [
    {
      "accepted_run_ids": [],
      "accepted_stage": null,
      "eligible_for_future_four_lane_use": false,
      "historical_endpoint": "AX7020-F/JTAG:210249855178",
      "historical_position": "J10-B",
      "historical_record_id": "FAILED_FIXED_J10_B_MODULE_PRE_P10_1R",
      "history": "Removed before accepted P10.1R run p10_1r_20260803T103315Z_39df1715_56533798_df0c60f6.",
      "inventory_status": "QUARANTINED_NOT_ACCEPTED",
      "known_failures": [
        "Historical fixed J10-B to rotating J10-B directional connectivity failures before the current F1 was installed.",
        "Not part of the accepted P10.1R artifact/run bundle."
      ],
      "pcb_revision": "NOT_RECORDED; NOT_GUESSED",
      "tfdu_marking_or_lot": "NOT_RECORDED; NOT_GUESSED"
    }
  ],
  "schema_version": 1,
  "scope": "P10_3_MODULE_INVENTORY",
  "sha256": "1293702c8d80e1365ee022ecadd72761cda81d6c190f8f7babf7f8b0396e92a9",
  "source_commit": "8b9563a37728a81850223f938e0b06e5772ec039",
  "status": "PASS",
  "test_id": "P10_3-INV-001",
  "unique_small_board_id_count": 8
}
```
