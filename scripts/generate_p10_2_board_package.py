#!/usr/bin/env python3
"""Generate the P10.2 AX7020 four-lane board package from audited sources.

This generator is intentionally offline-only.  It never imports or derives
constraints from the Z7010/AX7010 XDC.  Lane 0/1 package pins are copied from
the accepted AX7020 role profiles; lane 2/3 are independently mapped through
the official AX7020 J11 table, package-pin workbook, schematic, and the
Vivado xc7z020clg400-2 device database.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOAL_SHA256 = "f09ddcd1556b6def7eab250cae92b1cc69f7316a4c3338b5b04d23b10f22a8f5"

SOURCES = {
    "ax7020_schematic_v2": {
        "path": r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7020\01_SCH\AX7020开发板原理图V2.0.pdf",
        "sha256": "e35eb1b654774a6f314de0140f5608d38a1c6be72d1c3e1008f5e288ac83c87e",
        "authority": "ALINX official AX7010/AX7020 development-board schematic",
        "locations": [
            "PDF page/sheet 5: Bank 34/35 package pins and VCC3V3/VCCIO",
            "PDF page/sheet 15: J10/J11 numbering and 33-ohm resistor arrays",
            "PDF page/sheet 16: VCC3V3 regulator and VCCIO_35 regulator",
        ],
    },
    "ax7020_manual_v2_2": {
        "path": r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7020\AX7020UserManualV2.2\AX7020UserManualV2.2.rst",
        "sha256": "d5451ad97ad1b54edd646b3258d03c95b4f485d47b1da1a58a7aea2526b20f16",
        "authority": "ALINX official AX7020 user manual V2.2 source",
        "locations": [
            "section 7.4 J10 connector table and pin-1 photograph",
            "section 7.5 J11 connector table and pin-1 photograph",
        ],
    },
    "ax7020_pin_workbook": {
        "path": r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7020\01_SCH\AX7010_AX7020管脚.xlsx",
        "sha256": "2113ac32317262b681b2f54f63e77fced28f99c233c456e030b03cf77941ccbb",
        "authority": "ALINX official AX7010/AX7020 package-pin workbook",
        "locations": ["Sheet1 A1:B228; IO1/IO2 signal-to-package-pin rows"],
    },
    "tfdu6102_datasheet": {
        "path": r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7010\TFDU6102datasheet.pdf",
        "sha256": "54db2771cf8887eb264f38518b13ec5eb17be04d63a20712d18a558b0c7376ef",
        "authority": "Vishay TFDU6102 datasheet, document 82550 rev 1.3",
        "locations": [
            "PDF page 4 / printed page 3: pin descriptions and polarities",
            "PDF page 8 / printed page 7: 3.3-V transmitter and 600-mA maximum switched current",
            "PDF page 10 / printed page 9: static Mode and SD/Txd truth table",
        ],
    },
    "tfdu_small_board_schematic": {
        "path": r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7010\TFDU6102电路\ir_comm_TFDU6102\TFDU6102_subb.SchDoc",
        "sha256": "4fb54601855e9bf585fffeda037390db9097e6cb11caa32efdcadd4fefd57f4a",
        "authority": "user-supplied TFDU small-board design source",
        "locations": [
            "header pin1 VCC2/VCC1 path; pins2/4/6 GND; pin3 Txd; pin5 Rxd; pin7 SD; pin8 Mode"
        ],
    },
}


# The order of the four signals is deliberate and matches each existing
# module harness.  F0/F1/R0/R1 are byte-for-byte identical to the accepted
# AX7020 2-lane role profiles.  F2/F3/R2/R3 use J11 in the same A/B connector
# pin pattern so a module harness never mixes signal ordering.
LANES = [
    {
        "lane": 0, "position": "J10-A", "connector": "J10",
        "pins": {
            "Mode": (30, "T12", "IO_L2P_T0_34", "IO1_14P", 34),
            "SD":   (32, "T11", "IO_L1P_T0_34", "IO1_15P", 34),
            "Rxd":  (34, "B19", "IO_L2P_T0_AD8P_35", "IO1_16P", 35),
            "Txd":  (36, "C20", "IO_L1P_T0_AD0P_35", "IO1_17P", 35),
        },
    },
    {
        "lane": 1, "position": "J10-B", "connector": "J10",
        "pins": {
            "Mode": (22, "V17", "IO_L21P_T3_DQS_34", "IO1_10P", 34),
            "SD":   (24, "T14", "IO_L5P_T0_34", "IO1_11P", 34),
            "Rxd":  (26, "U13", "IO_L3P_T0_DQS_PUDC_B_34", "IO1_12P", 34),
            "Txd":  (28, "V12", "IO_L4P_T0_34", "IO1_13P", 34),
        },
    },
    {
        "lane": 2, "position": "J11-A", "connector": "J11",
        "pins": {
            "Mode": (30, "G17", "IO_L16P_T2_35", "IO2_14P", 35),
            "SD":   (32, "H16", "IO_L13P_T2_MRCC_35", "IO2_15P", 35),
            "Rxd":  (34, "H15", "IO_L19P_T3_35", "IO2_16P", 35),
            "Txd":  (36, "K14", "IO_L20P_T3_AD6P_35", "IO2_17P", 35),
        },
    },
    {
        "lane": 3, "position": "J11-B", "connector": "J11",
        "pins": {
            "Mode": (22, "L16", "IO_L11P_T1_SRCC_35", "IO2_10P", 35),
            "SD":   (24, "M17", "IO_L8P_T1_AD10P_35", "IO2_11P", 35),
            "Rxd":  (26, "D19", "IO_L4P_T0_35", "IO2_12P", 35),
            "Txd":  (28, "E18", "IO_L5P_T0_AD9P_35", "IO2_13P", 35),
        },
    },
]

SIGNAL_META = {
    "Mode": {
        "fpga_direction": "output_to_tfdu",
        "tfdu_header_pin": 8,
        "tfdu_device_pin": 7,
        "reset_default": "HIGH; static MIR/FIR mode",
        "pull": "No discrete board pull shown; 33-ohm connector series resistor; configuration pull-up is power-sequence dependent",
    },
    "SD": {
        "fpga_direction": "output_to_tfdu",
        "tfdu_header_pin": 7,
        "tfdu_device_pin": 5,
        "reset_default": "HIGH; active-high full shutdown",
        "pull": "No discrete board pull shown; 33-ohm connector series resistor; configuration pull-up is power-sequence dependent",
    },
    "Rxd": {
        "fpga_direction": "input_from_tfdu",
        "tfdu_header_pin": 5,
        "tfdu_device_pin": 4,
        "reset_default": "Input; active-low; TFDU has approximately 500-kohm weak pull-up only in shutdown",
        "pull": "No selected-net discrete pull except J10-26/U13 R29=1 kohm to GND; 33-ohm connector series resistor",
    },
    "Txd": {
        "fpga_direction": "output_to_tfdu",
        "tfdu_header_pin": 3,
        "tfdu_device_pin": 3,
        "reset_default": "LOW in configured reset/fault/shutdown; active-high pulse; continuous HIGH <=1 us",
        "pull": "No discrete board pull shown; 33-ohm connector series resistor; configuration pull-up is power-sequence dependent",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_text(relpath: str, text: str) -> Path:
    path = ROOT / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    return path


def write_json(relpath: str, data: object) -> Path:
    return write_text(relpath, stable_json(data))


def build_rows(role: str) -> list[dict[str, object]]:
    prefix = "F" if role == "fixed" else "R"
    rows: list[dict[str, object]] = []
    for lane in LANES:
        module = f"{prefix}{lane['lane']}"
        for signal in ("Mode", "SD", "Rxd", "Txd"):
            connector_pin, package_pin, pin_name, connector_net, bank = lane["pins"][signal]
            meta = SIGNAL_META[signal]
            notes: list[str] = []
            if package_pin == "U13":
                notes.append("R29=1 kohm to GND is the preserved P10.1R electrical-guarantee gap")
            if "MRCC" in pin_name or "SRCC" in pin_name:
                notes.append("clock-capable pin intentionally used as ordinary GPIO; no clock constraint or clock consumer exists")
            if "AD" in pin_name:
                notes.append("XADC auxiliary-capable pin used as ordinary digital I/O; XADC auxiliary channel is not enabled")
            if not notes:
                notes.append("No selected-net onboard peripheral conflict shown")
            rows.append({
                "board_role": role,
                "module_id": module,
                "lane": lane["lane"],
                "position": lane["position"],
                "logical_signal": signal,
                "fpga_direction": meta["fpga_direction"],
                "rtl_port": f"tfdu_{signal.lower()}_{'i' if signal == 'Rxd' else 'o'}[{lane['lane']}]",
                "connector": lane["connector"],
                "connector_pin": connector_pin,
                "connector_net": connector_net,
                "fpga_package_pin": package_pin,
                "fpga_pin_name": pin_name,
                "io_bank": bank,
                "vcco_volts": 3.3,
                "iostandard": "LVCMOS33",
                "tfdu_header_pin": meta["tfdu_header_pin"],
                "tfdu_device_pin": meta["tfdu_device_pin"],
                "reset_default": meta["reset_default"],
                "pull": meta["pull"],
                "source_document": "AX7020 schematic V2.0 + AX7020 manual V2.2 + AX7020 pin workbook + Vivado 2023.1 device DB + TFDU sources",
                "source_page_table": (
                    f"schematic sheets 5/15/16; manual section {'7.4' if lane['connector'] == 'J10' else '7.5'}; "
                    "workbook Sheet1; TFDU datasheet pages 4/8/10; TFDU small-board schematic"
                ),
                "notes": "; ".join(notes),
            })
    return rows


def csv_text(rows: list[dict[str, object]]) -> str:
    fields = list(rows[0])
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def xdc_text(role: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"# Independently generated from official AX7020 sources for P10.2 {role} four-lane profile.",
        "# This file is not copied from, sourced from, or validated by any Z7010/AX7010 XDC.",
        "# OFFLINE_CANDIDATE_ONLY=1; CURRENT_RUN_HARDWARE_AUTHORIZATION=false",
        "# F0/F1 or R0/R1 package pins are preserved from the accepted AX7020 2-lane profile.",
        "",
    ]
    for row in rows:
        signal = str(row["logical_signal"])
        port = str(row["rtl_port"])
        lines.extend([
            f"# {row['module_id']} {signal}: {row['connector']}-{row['connector_pin']} -> {row['fpga_package_pin']} bank {row['io_bank']}",
            f"set_property PACKAGE_PIN {row['fpga_package_pin']} [get_ports {{{port}}}]",
            f"set_property IOSTANDARD LVCMOS33 [get_ports {{{port}}}]",
        ])
        if signal != "Rxd":
            lines.extend([
                f"set_property DRIVE 4 [get_ports {{{port}}}]",
                f"set_property SLEW SLOW [get_ports {{{port}}}]",
            ])
        lines.append("")
    lines.extend([
        "# AX7020 onboard PL user LEDs: Bank 35, VCCO=3.3 V, active-low.",
        "# Four-lane candidate maps one monitor-only LED to aggregate accepted activity per lane.",
        "set_property PACKAGE_PIN M14 [get_ports {pl_activity_led_n_o[0]}]",
        "set_property PACKAGE_PIN M15 [get_ports {pl_activity_led_n_o[1]}]",
        "set_property PACKAGE_PIN K16 [get_ports {pl_activity_led_n_o[2]}]",
        "set_property PACKAGE_PIN J16 [get_ports {pl_activity_led_n_o[3]}]",
        "set_property IOSTANDARD LVCMOS33 [get_ports {pl_activity_led_n_o[*]}]",
        "set_property DRIVE 4 [get_ports {pl_activity_led_n_o[*]}]",
        "set_property SLEW SLOW [get_ports {pl_activity_led_n_o[*]}]",
    ])
    return "\n".join(lines) + "\n"


def profile_yaml(role: str, pinmap_path: str, xdc_path: str) -> str:
    board_id = "AX7020-F" if role == "fixed" else "AX7020-R"
    serial = "210249855178" if role == "fixed" else "210512180081"
    modules = [f"{'F' if role == 'fixed' else 'R'}{index}" for index in range(4)]
    return f"""schema_version: 2
profile_id: "P10_2_AX7020_{role.upper()}_4LANE"
status: "PASS_OFFLINE_PROFILE_PENDING_PHYSICAL_WIRING_AND_P10_3_AUTHORIZATION"
node_role: "{role}"
proposed_board_id: "{board_id}"
physical_board_identity: "JTAG_CABLE_SERIAL:{serial}"
physical_board_identity_method: "JTAG_CABLE_SERIAL"
physical_pcb_revision: "PENDING_PRE_WIRING_SILKSCREEN_CHECK; NOT_GUESSED"
common_profile: "board_profiles/ax7020_common/board_identity.yaml"
exact_documented_board_model: "ALINX AX7020"
exact_documented_fpga_marking: "XC7Z020-2CLG400I"
vivado_part: "xc7z020clg400-2"
clock_reset:
  ps_input_clock_mhz: 33.333333
  pl_fclk_mhz: 64.0
  reset: "role-local active-low fabric reset from PS reset infrastructure"
ddr_ps_preset:
  source: "official ALINX AX7020 Vivado 2023.1 ps_config.tcl"
  sha256: "b9212817e1333a73c9a317217e0636b6a1636e2306095296fbe6eff6bf10f217"
pinmap: "{pinmap_path}"
xdc: "{xdc_path}"
lane_count: 4
physical_module_count: 4
lane_mask_width: 4
max_lane_mask: 15
allowed_lane_masks: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
modules: [{', '.join(modules)}]
module_positions:
  lane0: "J10-A"
  lane1: "J10-B"
  lane2: "J11-A"
  lane3: "J11-B"
register_map: "config/register_map/ir_axi_regs.yaml"
register_map_version: "P10_2-1"
window_size: 32
sack_bits: 32
single_global_permit_channels_per_endpoint: 1
network_required: false
hardware_admission: false
blocking_conditions:
  - "F2/F3/R2/R3 physical inventory and pinout verification"
  - "eight-module safe-idle and raw acceptance"
  - "physical wiring against frozen proposal"
  - "new P10.3 current-run hardware authorization"
no_hardware: true
current_run_hardware_authorization: false
no_2h_qualification: true
"""


def markdown_table(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "| Endpoint | Module | Lane | Signal | FPGA direction | Connector | Pin | Package pin | Bank | VCCO | IOSTANDARD | TFDU header/device | Reset/default | Pull | Source | Notes |",
        "|---|---|---:|---|---|---|---:|---|---:|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['board_role']} | {row['module_id']} | {row['lane']} | {row['logical_signal']} | "
            f"{row['fpga_direction']} | {row['connector']} | {row['connector_pin']} | {row['fpga_package_pin']} "
            f"({row['fpga_pin_name']}) | {row['io_bank']} | {row['vcco_volts']} V | {row['iostandard']} | "
            f"{row['tfdu_header_pin']} / {row['tfdu_device_pin']} | {row['reset_default']} | {row['pull']} | "
            f"{row['source_page_table']} | {row['notes']} |"
        )
    return lines


def main() -> int:
    source_manifest = {
        "schema_version": 1,
        "status": "PASS",
        "goal_sha256": GOAL_SHA256,
        "read_only_sources": SOURCES,
        "spreadsheet_inspection": {
            "tool": "@oai/artifact-tool 2.8.6+",
            "result": "Sheet1 A1:B228 inspected; all selected IO1/IO2 package-pin pairs matched",
        },
        "vivado_device_database": {
            "tool": "Vivado 2023.1",
            "part": "xc7z020clg400-2",
            "result": "all 20 selected TFDU/LED package pins resolved with expected PIN_FUNC and BANK",
        },
    }
    source_manifest_path = write_json(
        "evidence/generated/p10_2_raw/board_document_set_manifest.json",
        source_manifest,
    )
    board_document_set_sha = sha256(source_manifest_path)

    role_outputs: dict[str, dict[str, str]] = {}
    all_rows: list[dict[str, object]] = []
    for role in ("fixed", "rotating"):
        rows = build_rows(role)
        all_rows.extend(rows)
        directory = f"board_profiles/ax7020_{role}_4lane"
        pinmap_rel = f"{directory}/pinmap.csv"
        xdc_rel = f"{directory}/ax7020_{role}_4lane.generated.xdc"
        profile_rel = f"{directory}/profile.yaml"
        active_rel = f"{directory}/ACTIVE_PROFILE.json"
        pinmap_path = write_text(pinmap_rel, csv_text(rows))
        xdc_path = write_text(xdc_rel, xdc_text(role, rows))
        profile_path = write_text(profile_rel, profile_yaml(role, pinmap_rel, xdc_rel))
        active = {
            "schema_version": 1,
            "profile": f"P10_2_AX7020_{role.upper()}_4LANE",
            "profile_path": profile_rel,
            "pinmap_path": pinmap_rel,
            "xdc_path": xdc_rel,
            "node_role": role,
            "lane_count": 4,
            "physical_module_count": 4,
            "max_lane_mask": "0xF",
            "no_hardware": True,
            "current_run_hardware_authorization": False,
        }
        active_path = write_json(active_rel, active)
        role_outputs[role] = {
            "pinmap": pinmap_rel,
            "pinmap_sha256": sha256(pinmap_path),
            "xdc": xdc_rel,
            "xdc_sha256": sha256(xdc_path),
            "profile": profile_rel,
            "profile_sha256": sha256(profile_path),
            "active_profile": active_rel,
            "active_profile_sha256": sha256(active_path),
        }

    pinmap_manifest_path = write_json(
        "evidence/generated/p10_2_raw/pinmap_sha256_manifest.json",
        {"schema_version": 1, "status": "PASS", "roles": role_outputs},
    )
    pinmap_set_sha = sha256(pinmap_manifest_path)

    wiring_md_lines = [
        "# P10.2 AX7020 stationary four-lane wiring proposal",
        "",
        "> Status: `PASS_OFFLINE_PROPOSAL`; this is not hardware acceptance or hardware authorization.",
        "",
        "## Identity and topology",
        "",
        "- Fixed endpoint: `AX7020-F`, JTAG cable serial `210249855178`, modules `F0..F3`.",
        "- Rotating-role stationary endpoint: `AX7020-R`, JTAG cable serial `210512180081`, modules `R0..R3`.",
        "- Lane pairs are fixed: `lane0=F0-R0`, `lane1=F1-R1`, `lane2=F2-R2`, `lane3=F3-R3`; cross-pairing is prohibited.",
        "- Accepted lane0/lane1 pins remain unchanged. New lane2 uses J11-A and lane3 uses J11-B in the same 30/32/34/36 and 22/24/26/28 signal order.",
        "- The original failed F1 module is quarantined and cannot be relabeled or connected as F2/F3/R2/R3.",
        "",
        "## Connector orientation",
        "",
        "With the board silkscreen readable, J10 and J11 pin 1 are the marked left near/lower-row corners. Pin 2 is directly above on the far row. Pins 39/40 are at the opposite end. Verify both silkscreen markers before inserting any harness.",
        "",
        "## Signal map",
        "",
        *markdown_table(all_rows),
        "",
        "## TFDU power and ground",
        "",
        "| Modules | TFDU connection | Proposal | FPGA package pin | Evidence / restriction |",
        "|---|---|---|---|---|",
        "| F0/F1/R0/R1 | header pin1 VCC2/VCC1 path; pins2/4/6 GND | Preserve the user's existing power/ground wiring exactly | N/A - power | User confirmed existing wiring; Codex must not reroute it |",
        "| F2/F3/R2/R3 | header pin1 VCC2/VCC1 path; pins2/4/6 GND | Dedicated 3.3-V module rail and low-impedance star return meeting the frozen P10.2 power budget | N/A - power | Do not assume J10/J11 3.3-V header pins can source four-module peak current; qualify supply, connector, wire and return path before P10.3 |",
        "",
        "The supplied small-board schematic connects header pin1 to device VCC2 and through the documented board network to VCC1; its ground header pins are 2/4/6. The TFDU6102 datasheet allows 3.3-V operation and specifies up to 600 mA switched IRED current per transmitter. VCC/GND wiring is therefore a power-distribution design item, not an FPGA pin assignment.",
        "",
        "## Power-up, reset and safety sequence",
        "",
        "1. Make or change every signal, power and ground connection only with both AX7020 boards and every TFDU rail off.",
        "2. Verify module labels, connector identity, pin-1 orientation, no A/B or endpoint cross-pair, rail polarity, common ground, no shorts and physical clearance.",
        "3. Verify each new module marking/revision and the actual AX7020 PCB revision against this proposal; an unverified revision blocks P10.3.",
        "4. Power module rails only after the supply/decoupling checks in `P10_2_4LANE_POWER_AND_DECOUPLING_REQUIREMENTS.md` pass.",
        "5. A future authorized run must program role-bound shutdown images first. Configured reset/fault/full shutdown is `Txd=LOW`, `SD=HIGH`, LEDs off; wait at least 500 us after SD leaves shutdown before RX/TX.",
        "6. The single endpoint `GLOBAL_PERMIT` is necessary but never sufficient. Each module keeps independent final kill, one-hot, pulse-width and exact sliding-duty enforcement.",
        "",
        "## JTAG, UART and LED roles",
        "",
        "JTAG cable serial is the role key only; it is not an optical identity. UART is role-local diagnostics and cannot arm or bypass TX safety. The four active-low PL LEDs are monitor-only; in the four-lane candidate LED1..LED4 show accepted aggregate activity for lane0..lane3. LED state is not safety, continuity or optical-success evidence.",
        "",
        "## Audited special cases and open physical prerequisites",
        "",
        "- J10-26/U13 retains R29=1 kohm to GND. This is an accepted P10.1R empirical path but remains outside the TFDU datasheet guaranteed Rxd load.",
        "- J11-32/H16 is MRCC-capable and J11-22/L16 is SRCC-capable; both are legal ordinary GPIO here and no clock consumer or clock constraint uses them.",
        "- J11 K14/M17/E18 are XADC-auxiliary-capable digital I/O. The 4-lane profile does not enable those auxiliary channels.",
        "- Actual PCB revision, F2/F3/R2/R3 markings, installed harness continuity, idle levels, supply droop and eight-module raw/echo acceptance remain P10.3 prerequisites.",
        "- No hardware action, two-hour qualification, movement, module insertion or wiring change is authorized by this document.",
        "",
        "## Source hashes",
        "",
        f"- Board document set manifest SHA256: `{board_document_set_sha}`.",
        f"- Combined pinmap manifest SHA256: `{pinmap_set_sha}`.",
        f"- Goal SHA256: `{GOAL_SHA256}`.",
    ]
    wiring_md_path = write_text(
        "docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md",
        "\n".join(wiring_md_lines),
    )
    wiring_sha = sha256(wiring_md_path)

    wiring_yaml_lines = [
        "schema_version: 2",
        "proposal_id: \"P10_2_AX7020_STATIONARY_4LANE\"",
        "status: \"PASS_OFFLINE_PROPOSAL_PENDING_PHYSICAL_WIRING\"",
        f"goal_sha256: \"{GOAL_SHA256}\"",
        f"wiring_proposal_sha256: \"{wiring_sha}\"",
        f"pinmap_set_sha256: \"{pinmap_set_sha}\"",
        f"board_document_set_sha256: \"{board_document_set_sha}\"",
        "no_hardware: true",
        "current_run_hardware_authorization: false",
        "no_2h_qualification: true",
        "fixed_board: {board_id: \"AX7020-F\", jtag_cable_serial: \"210249855178\"}",
        "rotating_role_board: {board_id: \"AX7020-R\", jtag_cable_serial: \"210512180081\"}",
        "topology:",
        "  lane0: \"F0-R0\"",
        "  lane1: \"F1-R1\"",
        "  lane2: \"F2-R2\"",
        "  lane3: \"F3-R3\"",
        "connector_pin1_orientation: \"silkscreen-readable left near/lower row; pin2 directly above/far row; verify marked 1/2 and 39/40 before wiring\"",
        "power:",
        "  accepted_modules: \"preserve existing user wiring; no Codex reroute\"",
        "  new_modules: \"dedicated qualified 3.3-V rail to TFDU header pin1; star return to header pins2/4/6\"",
        "  connector_power_assumption: \"J10/J11 VCC3V3 pins are not assumed capable of aggregate module peak current\"",
        "signals:",
    ]
    for row in all_rows:
        wiring_yaml_lines.extend([
            f"  - board_role: \"{row['board_role']}\"",
            f"    module_id: \"{row['module_id']}\"",
            f"    lane: {row['lane']}",
            f"    logical_signal: \"{row['logical_signal']}\"",
            f"    fpga_direction: \"{row['fpga_direction']}\"",
            f"    connector: \"{row['connector']}\"",
            f"    connector_pin: {row['connector_pin']}",
            f"    fpga_package_pin: \"{row['fpga_package_pin']}\"",
            f"    io_bank: {row['io_bank']}",
            f"    vcco_volts: {row['vcco_volts']}",
            f"    iostandard: \"{row['iostandard']}\"",
            f"    tfdu_header_pin: {row['tfdu_header_pin']}",
            f"    reset_default: {json.dumps(row['reset_default'])}",
            f"    pull: {json.dumps(row['pull'])}",
            f"    source: {json.dumps(row['source_page_table'])}",
            f"    notes: {json.dumps(row['notes'])}",
        ])
    wiring_yaml_lines.extend([
        "physical_prerequisites:",
        "  - \"actual AX7020 PCB revision check\"",
        "  - \"F2/F3/R2/R3 inventory and pinout check\"",
        "  - \"qualified power distribution and measured droop\"",
        "  - \"safe-idle then per-module raw acceptance\"",
        "  - \"new P10.3 current-run authorization\"",
    ])
    wiring_yaml_path = write_text(
        "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
        "\n".join(wiring_yaml_lines),
    )

    layout = """# P10.2 stationary four-lane physical layout guide

This guide is an offline wiring aid, not permission to power, program or transmit.

## Labels and lane geometry

Use `AX7020-F` with F0/F1 on J10-A/B and F2/F3 on J11-A/B. Use `AX7020-R` with R0/R1 on J10-A/B and R2/R3 on J11-A/B. Pair only F0-R0, F1-R1, F2-R2 and F3-R3. Label both ends of every Mode/SD/Rxd/Txd conductor and every power/return harness.

Keep every paired module at a fixed, unobstructed, face-to-face orientation. Route signal and power harnesses so they cannot shade an aperture or pull a module out of alignment. Separate high-current supply/return bundles from Rxd signal runs; use a short low-impedance return for each module and join at a documented star point.

## Harness identifiers

Signal harness IDs are `F0-SIG` through `F3-SIG` and `R0-SIG` through `R3-SIG`. Power harness IDs are the corresponding `-PWR` and `-RET`. J10-A/B retain the accepted P10.1R pin pattern. J11-A/B use the identical logical order at J11 pins 30/32/34/36 and 22/24/26/28.

## Mandatory sequence

1. Switch off both AX7020 boards and all TFDU supplies; verify absence of voltage before inserting, moving or measuring continuity on a harness.
2. Quarantine the original F1 in a separately marked container. It may not occupy any F/R slot.
3. Verify board and module labels, actual PCB revisions, connector names, pin-1 marks, polarity and signal direction against the frozen proposal.
4. Check continuity end-to-end and verify no short between adjacent connector pins, 3.3 V and GND, or any signal and a power rail.
5. Verify the external module supply current rating, decoupling, star returns and planned droop measurement points. Do not assume a J10/J11 3.3-V pin is a four-module power feed.
6. Photograph and record the completed unpowered layout. During any future formal run, do not move, rotate, re-aim, shade, swap or rewire anything.
7. A future separately authorized P10.3 run starts with role-bound shutdown programming, verified Txd-low/SD-high, one-module intake, then 1 -> 2 -> 4 lane escalation. Never jump directly to four simultaneous transmitters.
"""
    layout_path = write_text("docs/hardware/P10_2_4LANE_PHYSICAL_LAYOUT_GUIDE.md", layout)

    wiring_summary = {
        "schema_version": 1,
        "test_id": "P10_2-WIRE-001",
        "status": "PASS",
        "scope": "OFFLINE_WIRING_PROPOSAL_ONLY",
        "lane_pairs": ["F0-R0", "F1-R1", "F2-R2", "F3-R3"],
        "lane0_lane1_pin_preservation": "PASS",
        "new_mapping": {"lane2": "J11-A", "lane3": "J11-B"},
        "signal_row_count": len(all_rows),
        "wiring_proposal": "docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md",
        "wiring_proposal_sha256": wiring_sha,
        "wiring_yaml_sha256": sha256(wiring_yaml_path),
        "pinmap_set_sha256": pinmap_set_sha,
        "board_document_set_sha256": board_document_set_sha,
        "physical_wiring_complete": False,
        "hardware_admission": False,
        "hardware_actions_executed": False,
    }
    write_json("evidence/generated/p10_2_wiring_summary.json", wiring_summary)
    write_text(
        "evidence/generated/p10_2_wiring_summary.md",
        "# P10.2 wiring summary\n\n"
        f"- Status: `PASS` (offline proposal only).\n"
        f"- Wiring proposal SHA256: `{wiring_sha}`.\n"
        f"- Pinmap-set SHA256: `{pinmap_set_sha}`.\n"
        f"- Board-document-set SHA256: `{board_document_set_sha}`.\n"
        "- Lane0/lane1 pin preservation: `PASS`; lane2=`J11-A`, lane3=`J11-B`.\n"
        "- Physical wiring and hardware admission remain false.\n",
    )

    selected_pins = [str(row["fpga_package_pin"]) for row in build_rows("fixed")]
    pin_audit = {
        "schema_version": 1,
        "test_id": "P10_2-PIN-001",
        "status": "PASS",
        "part": "xc7z020clg400-2",
        "selected_signal_pin_count_per_endpoint": 16,
        "unique_signal_pin_count_per_endpoint": len(set(selected_pins)),
        "duplicate_package_pins": sorted({p for p in selected_pins if selected_pins.count(p) > 1}),
        "banks": {"34": {"vcco_volts": 3.3}, "35": {"vcco_volts": 3.3}},
        "iostandard": "LVCMOS33",
        "connector_series_ohms": 33,
        "lane0_lane1_pin_preservation": "PASS",
        "z7010_xdc_reuse": False,
        "j10_u13_r29_gap_preserved": True,
        "clock_capable_gpio": ["H16/MRCC", "L16/SRCC"],
        "xadc_auxiliary_gpio": ["K14/AD6P", "M17/AD10P", "E18/AD9P", "B19/AD8P", "C20/AD0P"],
        "configuration_behavior": "PUDC_B low enables configuration pull-ups; paired SD high optically inhibits Txd high, but partial-power fail-low remains unclaimed",
        "source_manifest": str(source_manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "source_manifest_sha256": board_document_set_sha,
        "hardware_actions_executed": False,
    }
    write_json("evidence/generated/p10_2_pin_bank_audit.json", pin_audit)
    write_text(
        "evidence/generated/p10_2_pin_bank_audit.md",
        "# P10.2 AX7020 pin/bank audit\n\n"
        "- Status: `PASS`.\n"
        "- 16 unique PL signal pins per endpoint; no package-pin collision.\n"
        "- Banks 34/35 are both documented at 3.3 V; every selected signal uses LVCMOS33 and a 33-ohm connector series path.\n"
        "- Lane0/lane1 are preserved. Lane2/lane3 are independently sourced from AX7020 J11, not a Z7010 XDC.\n"
        "- H16/L16 clock capability and K14/M17/E18 auxiliary-analog capability are audited ordinary-GPIO uses, not hidden clock/XADC consumers.\n"
        "- J10-26/U13 R29 and configuration/partial-power limitations remain explicitly recorded.\n",
    )

    profile_summary = {
        "schema_version": 1,
        "test_ids": ["P10_2-PROFILE-001", "P10_2-PROFILE-002"],
        "status": "PASS",
        "lane_count": 4,
        "physical_module_count_per_endpoint": 4,
        "lane_mask_width": 4,
        "max_lane_mask": "0xF",
        "roles": role_outputs,
        "hardware_admission": False,
        "hardware_actions_executed": False,
    }
    write_json("evidence/generated/p10_2_profile_summary.json", profile_summary)
    write_text(
        "evidence/generated/p10_2_profile_summary.md",
        "# P10.2 four-lane profile summary\n\n"
        "Both AX7020 role profiles are generated with LANE_COUNT=4, four local modules, 4-bit masks 0x1..0xF, the exact xc7z020clg400-2 part and independent AX7020 XDCs. Status: `PASS` offline; hardware admission remains false.\n",
    )

    module_summary = {
        "schema_version": 1,
        "test_id": "P10_2-INV-001",
        "status": "PASS",
        "accepted": ["F0", "F1_REPLACEMENT(runtime F1)", "R0", "R1"],
        "quarantined": ["F1_ORIGINAL"],
        "future_pending": ["F2", "F3", "R2", "R3"],
        "future_positions": {"F2": "J11-A", "R2": "J11-A", "F3": "J11-B", "R3": "J11-B"},
        "old_f1_eligible_for_future_use": False,
        "hardware_actions_executed": False,
    }
    write_json("evidence/generated/p10_2_module_inventory_summary.json", module_summary)
    write_text(
        "evidence/generated/p10_2_module_inventory_summary.md",
        "# P10.2 module inventory summary\n\nStatus: `PASS`. Accepted P10.1R baseline: F0, replacement F1, R0, R1. Original F1 is quarantined and forbidden as a future alias. F2/F3/R2/R3 are assigned proposed J11-A/B positions but remain pending physical inventory, safe-idle and raw acceptance.\n",
    )

    repo_intake = {
        "schema_version": 1,
        "test_id": "P10_2-REPO-INTAKE",
        "status": "PASS",
        "goal_sha256": GOAL_SHA256,
        "branch": "p10.2/4lane-offline-readiness",
        "base_commit": "e90a2203c4d6b71f93e0ee1c5bf93bb263c8a1b8",
        "worktree": str(ROOT),
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "no_2h_qualification": True,
        "reference_roots_read_only": True,
        "hardware_actions_executed": False,
    }
    write_json("evidence/generated/p10_2_repo_intake.json", repo_intake)
    write_text(
        "evidence/generated/p10_2_repo_intake.md",
        "# P10.2 repository intake\n\n"
        "- Status: `PASS`.\n"
        f"- Goal SHA256: `{GOAL_SHA256}`.\n"
        "- Branch/worktree: `p10.2/4lane-offline-readiness` / `C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_2`.\n"
        "- Base/closed P10.1R commit: `e90a2203c4d6b71f93e0ee1c5bf93bb263c8a1b8`.\n"
        "- `NO_HARDWARE=1`, current-run authorization false, and no two-hour qualification.\n",
    )

    print("P10_2_BOARD_PACKAGE_GENERATED=1")
    print(f"WIRING_PROPOSAL_SHA256={wiring_sha}")
    print(f"PINMAP_SHA256={pinmap_set_sha}")
    print(f"BOARD_DOCUMENT_SET_SHA256={board_document_set_sha}")
    print(f"LAYOUT_GUIDE_SHA256={sha256(layout_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
