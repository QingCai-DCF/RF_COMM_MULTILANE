# P10.3 actual wiring freeze

- Status: `PASS`
- Test ID: `P10_3-WIRE-001`
- Hardware actions executed: `false`

- Source commit: `b1b2a268c182dff370fef02b25ed1675d7935043`
- Canonical SHA256: `fee58fc4852547bc3d8d10e140a218b918fd12c8d41cf9ee64dca05c03262179`

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
  "bytes": 5072,
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
      "small_board_id": "B0023"
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
  "sha256": "fee58fc4852547bc3d8d10e140a218b918fd12c8d41cf9ee64dca05c03262179",
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
  "source_commit": "b1b2a268c182dff370fef02b25ed1675d7935043",
  "status": "PASS",
  "test_id": "P10_3-WIRE-001"
}
```
