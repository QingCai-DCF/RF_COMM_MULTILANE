# P10.3 actual wiring freeze

- Status: `PASS`
- Test ID: `P10_3-WIRE-001`
- Hardware actions executed: `false`

- Source commit: `ed1656a05e6f814b18f8a94090c5c4c322ded07d`
- Canonical SHA256: `51e65e9f993068a25ed113b9be0648319875eb8b02b8e7b524bba76249346603`

```json
{
  "board_binding": {
    "fixed": {
      "active_modules": [
        "F0",
        "F1",
        "F2",
        "F3"
      ],
      "board_id": "AX7020-F",
      "jtag_cable_serial": "210249855178"
    },
    "rotating": {
      "active_modules": [
        "R0",
        "R1",
        "R2",
        "R3"
      ],
      "board_id": "AX7020-R",
      "jtag_cable_serial": "210512180081"
    }
  },
  "bytes": 4765,
  "canonical_path": "config/hardware/p10_3_actual_wiring.yaml",
  "electrical_contract": {
    "Mode": "FPGA output to TFDU; static HIGH for MIR/FIR",
    "Rxd": "TFDU output to FPGA; active low",
    "SD": "FPGA output to TFDU; active-high shutdown",
    "Txd": "FPGA output to TFDU; active high; configured reset/fault/shutdown LOW; continuous HIGH <=1 us",
    "iostandard": "LVCMOS33",
    "signal_details_source": "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
    "vcco_volts": 3.3
  },
  "errors": [],
  "hardware_actions_executed": false,
  "historical_power_off_during_wiring": "NOT_STATED_BY_USER; NOT_CLAIMED",
  "lane_pairs": {
    "lane0": "F0-R0",
    "lane1": "F1-R1",
    "lane2": "F2-R2",
    "lane3": "F3-R3"
  },
  "module_positions": {
    "F0": {
      "connector": "J10",
      "endpoint": "fixed",
      "lane": 0,
      "position": "A",
      "small_board_id": "A0019"
    },
    "F1": {
      "connector": "J10",
      "endpoint": "fixed",
      "lane": 1,
      "position": "B",
      "small_board_id": "B0012"
    },
    "F2": {
      "connector": "J11",
      "endpoint": "fixed",
      "lane": 2,
      "position": "A",
      "small_board_id": "B0001"
    },
    "F3": {
      "connector": "J11",
      "endpoint": "fixed",
      "lane": 3,
      "position": "B",
      "small_board_id": "B0004"
    },
    "R0": {
      "connector": "J10",
      "endpoint": "rotating",
      "lane": 0,
      "position": "A",
      "small_board_id": "A0010"
    },
    "R1": {
      "connector": "J10",
      "endpoint": "rotating",
      "lane": 1,
      "position": "B",
      "small_board_id": "A0017"
    },
    "R2": {
      "connector": "J11",
      "endpoint": "rotating",
      "lane": 2,
      "position": "A",
      "small_board_id": "B0015"
    },
    "R3": {
      "connector": "J11",
      "endpoint": "rotating",
      "lane": 3,
      "position": "B",
      "small_board_id": "B0017"
    }
  },
  "no_hardware": true,
  "package_pins": {
    "lane0": {
      "Mode": "T12",
      "Rxd": "B19",
      "SD": "T11",
      "Txd": "C20"
    },
    "lane1": {
      "Mode": "V17",
      "Rxd": "U13",
      "SD": "T14",
      "Txd": "V12"
    },
    "lane2": {
      "Mode": "G17",
      "Rxd": "H15",
      "SD": "H16",
      "Txd": "K14"
    },
    "lane3": {
      "Mode": "L16",
      "Rxd": "D19",
      "SD": "M17",
      "Txd": "E18"
    }
  },
  "physical_wiring_completed": true,
  "power_and_ground": {
    "attestation_is_not_independent_external_measurement": true,
    "codex_rewiring_authorized": false,
    "external_four_lane_power_acceptance": "PENDING_EXTERNAL_MEASUREMENT",
    "internal_no_brownout_observation_is_not_external_power_acceptance": true,
    "j11_gauge_source_and_decoupling_match_j10": "USER_ATTESTED",
    "user_attested_adequate_for_current_use": true,
    "user_existing_connections_preserved": true
  },
  "schema_version": 1,
  "scope": "P10_3_ACTUAL_WIRING_FREEZE",
  "sha256": "51e65e9f993068a25ed113b9be0648319875eb8b02b8e7b524bba76249346603",
  "signal_positions": {
    "A": {
      "Mode": 30,
      "Rxd": 34,
      "SD": 32,
      "Txd": 36
    },
    "B": {
      "Mode": 22,
      "Rxd": 26,
      "SD": 24,
      "Txd": 28
    }
  },
  "source_commit": "ed1656a05e6f814b18f8a94090c5c4c322ded07d",
  "status": "PASS",
  "test_id": "P10_3-WIRE-001"
}
```
