#!/usr/bin/env python3
"""Generate P10 AX7020 wiring, profile, and electrical-audit artifacts.

The source facts in this generator are independently derived from the AX7020
reference set and the supplied TFDU small-board schematic.  No AX7010 XDC is
read or copied.  Generation is intentionally fail-closed on source hashes.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AX7020_ROOT = Path(r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7020")
AX7010_ROOT = Path(r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7010")

SOURCES = {
    "ax7020_schematic": {
        "path": AX7020_ROOT / "01_SCH" / "AX7020开发板原理图V2.0.pdf",
        "sha256": "e35eb1b654774a6f314de0140f5608d38a1c6be72d1c3e1008f5e288ac83c87e",
        "authority": "ALINX official board schematic",
    },
    "ax7020_manual": {
        "path": AX7020_ROOT / "AX7020UserManualV2.2" / "AX7020UserManualV2.2.rst",
        "sha256": "d5451ad97ad1b54edd646b3258d03c95b4f485d47b1da1a58a7aea2526b20f16",
        "authority": "ALINX official AX7020 user-manual source",
    },
    "ax7020_pin_workbook": {
        "path": AX7020_ROOT / "01_SCH" / "AX7010_AX7020管脚.xlsx",
        "sha256": "2113ac32317262b681b2f54f63e77fced28f99c233c456e030b03cf77941ccbb",
        "authority": "ALINX official package-pin workbook",
    },
    "tfdu_datasheet": {
        "path": AX7010_ROOT / "TFDU6102datasheet.pdf",
        "sha256": "54db2771cf8887eb264f38518b13ec5eb17be04d63a20712d18a558b0c7376ef",
        "authority": "Vishay TFDU6102 datasheet",
    },
    "tfdu_small_board_schematic": {
        "path": AX7010_ROOT / "TFDU6102电路" / "ir_comm_TFDU6102" / "TFDU6102_subb.SchDoc",
        "sha256": "4fb54601855e9bf585fffeda037390db9097e6cb11caa32efdcadd4fefd57f4a",
        "authority": "user-supplied TFDU small-board design source",
    },
}

OFFICIAL_ALINX_REPO = {
    "url": "https://github.com/alinxalinx/AX7020_2023.1",
    "commit": "fcf1e4a239b0f47e8ee95dfde7c2eedc5685c327",
    "path": "course_s2_vitis/01_ps_hello/Vivado/auto_create_project/ps_config.tcl",
    "git_blob": "8cd9d3600f65af43afe1ade8b8b63b24a31a090c",
    "sha256": "b9212817e1333a73c9a317217e0636b6a1636e2306095296fbe6eff6bf10f217",
    "bytes": 24915,
}

AMD_UG470 = {
    "url": "https://docs.amd.com/api/khub/documents/FOs3lXmlcWxBhTIFxVKyGA/content",
    "document": "UG470 7 Series FPGAs Configuration User Guide",
    "version": "1.17",
    "date": "2023-12-05",
    "location": "page 22, PUDC_B configuration-pin definition",
    "claim": "Active-low PUDC_B enables internal pull-ups on SelectIO pins after power-up and during configuration; low enables and high disables them.",
}

POSITION = {
    "A": {
        "lane": 0,
        "vector_index": 0,
        "connector_pins": {"Mode": 30, "SD": 32, "Rxd": 34, "Txd": 36},
        "package_pins": {"Mode": "T12", "SD": "T11", "Rxd": "B19", "Txd": "C20"},
        "banks": {"Mode": 34, "SD": 34, "Rxd": 35, "Txd": 35},
        "fpga_pin_names": {
            "Mode": "IO_L2P_T0_34",
            "SD": "IO_L1P_T0_34",
            "Rxd": "IO_L2P_T0_35",
            "Txd": "IO_L1P_T0_35",
        },
    },
    "B": {
        "lane": 1,
        "vector_index": 1,
        "connector_pins": {"Mode": 22, "SD": 24, "Rxd": 26, "Txd": 28},
        "package_pins": {"Mode": "V17", "SD": "T14", "Rxd": "U13", "Txd": "V12"},
        "banks": {"Mode": 34, "SD": 34, "Rxd": 34, "Txd": 34},
        "fpga_pin_names": {
            "Mode": "IO_L21P_T3_DQS_34",
            "SD": "IO_L5P_T0_34",
            "Rxd": "IO_L3P_T0_DQS_PUDC_B_34",
            "Txd": "IO_L4P_T0_34",
        },
    },
}

SIGNAL_META = {
    "Mode": {
        "fpga_direction": "output_to_tfdu",
        "port": "tfdu_mode_o",
        "tfdu_board_pin": 8,
        "tfdu_device_pin": 7,
        "small_board_series": "R5 22 ohm",
        "configured_shutdown_value": "HIGH (static MIR/FIR)",
    },
    "SD": {
        "fpga_direction": "output_to_tfdu",
        "port": "tfdu_sd_o",
        "tfdu_board_pin": 7,
        "tfdu_device_pin": 5,
        "small_board_series": "R4 22 ohm",
        "configured_shutdown_value": "HIGH (shutdown)",
    },
    "Rxd": {
        "fpga_direction": "input_from_tfdu",
        "port": "tfdu_rxd_i",
        "tfdu_board_pin": 5,
        "tfdu_device_pin": 4,
        "small_board_series": "R3 22 ohm",
        "configured_shutdown_value": "input; active-low; TFDU internal weak pull-up in shutdown",
    },
    "Txd": {
        "fpga_direction": "output_to_tfdu",
        "port": "tfdu_txd_o",
        "tfdu_board_pin": 3,
        "tfdu_device_pin": 3,
        "small_board_series": "R2 22 ohm",
        "configured_shutdown_value": "LOW",
    },
}

ROLES = {
    "fixed": {"board_proposed_id": "AX7020-F", "modules": {"A": "F0", "B": "F1"}},
    "rotating_role": {"board_proposed_id": "AX7020-R", "modules": {"A": "R0", "B": "R1"}},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def yaml_lines(value: object, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(yaml_lines(child, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(child)}")
        return lines
    if isinstance(value, list):
        lines = []
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(child, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(child)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def write_yaml(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(yaml_lines(value)) + "\n", encoding="utf-8")


def write_json(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def source_manifest() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for key, item in SOURCES.items():
        actual = sha256_file(item["path"])
        if actual != item["sha256"]:
            raise RuntimeError(f"source hash mismatch for {key}: {actual}")
        result[key] = {
            "path": str(item["path"]),
            "sha256": actual,
            "authority": item["authority"],
            "read_only": True,
        }
    result["official_alinx_ax7020_2023_1_ps_config"] = dict(OFFICIAL_ALINX_REPO)
    result["amd_ug470_pudc_b"] = dict(AMD_UG470)
    return result


def signal_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for role, role_data in ROLES.items():
        for position_name, module_id in role_data["modules"].items():
            position = POSITION[position_name]
            for signal in ("Mode", "SD", "Rxd", "Txd"):
                meta = SIGNAL_META[signal]
                connector_pin = position["connector_pins"][signal]
                package_pin = position["package_pins"][signal]
                bank = position["banks"][signal]
                pull = "no selected-signal pull shown; 33 ohm connector series resistor only"
                reset_default = meta["configured_shutdown_value"]
                notes = "No PL peripheral conflict shown on the selected J10 net."
                if signal == "Rxd":
                    pull = "TFDU shutdown weak pull-up approximately 500 kohm; no AX7020 pull shown"
                if position_name == "B" and signal == "Rxd":
                    pull = "AX7020 R29 1 kohm pull-down to GND on IO1_12P, plus TFDU shutdown weak pull-up"
                    notes = (
                        "Electrical guarantee gap: a 1 kohm pull-down requires about 3.3 mA at 3.3 V, "
                        "outside the TFDU6102 guaranteed VOH test currents of 250/500 uA."
                    )
                if signal in {"Txd", "SD", "Mode"}:
                    reset_default += "; FPGA-unconfigured/partial-power level not guaranteed by supplied schematics"
                rows.append(
                    {
                        "board_role": role,
                        "board_proposed_id": role_data["board_proposed_id"],
                        "module_id": module_id,
                        "lane": position["lane"],
                        "j10_position": position_name,
                        "logical_signal": signal,
                        "fpga_direction": meta["fpga_direction"],
                        "rtl_port": f"{meta['port']}[{position['vector_index']}]",
                        "connector": "J10",
                        "connector_pin": connector_pin,
                        "connector_net": f"EX_IO1_{({22: '10P', 24: '11P', 26: '12P', 28: '13P', 30: '14P', 32: '15P', 34: '16P', 36: '17P'})[connector_pin]}",
                        "fpga_package_pin": package_pin,
                        "fpga_pin_name": position["fpga_pin_names"][signal],
                        "io_bank": bank,
                        "vcco_volts": 3.3,
                        "iostandard": "LVCMOS33",
                        "ax7020_series_path": "33 ohm resistor array between FPGA net and J10",
                        "tfdu_board_pin": meta["tfdu_board_pin"],
                        "tfdu_device_pin": meta["tfdu_device_pin"],
                        "tfdu_small_board_series_path": meta["small_board_series"],
                        "reset_default": reset_default,
                        "pull": pull,
                        "source_document": "AX7020 schematic + AX7020 manual/table 7.4 + AX7020 pin workbook + TFDU small-board schematic + TFDU6102 datasheet",
                        "source_page_table": "AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records",
                        "notes": notes,
                    }
                )
    return rows


def write_pinmap_and_xdc(role: str, rows: list[dict[str, object]]) -> tuple[str, str]:
    role_dir = "ax7020_fixed_2lane" if role == "fixed" else "ax7020_rotating_2lane"
    role_rows = [row for row in rows if row["board_role"] == role]
    csv_rel = f"board_profiles/{role_dir}/pinmap.csv"
    csv_path = ROOT / csv_rel
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "module_id", "lane", "j10_position", "logical_signal", "rtl_port", "connector",
        "connector_pin", "fpga_package_pin", "fpga_pin_name", "io_bank", "vcco_volts",
        "iostandard", "reset_default", "pull", "source_document", "source_page_table", "notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(role_rows)

    xdc_rel = f"board_profiles/{role_dir}/{role_dir}.generated.xdc"
    xdc_path = ROOT / xdc_rel
    profile_id = "P10_AX7020_FIXED_2LANE" if role == "fixed" else "P10_AX7020_ROTATING_2LANE"
    lines = [
        f"# Independently generated from AX7020 official references for {profile_id}.",
        "# This is not copied from, sourced from, or validated by the AX7010 XDC.",
        "# HARDWARE_ADMISSION=BLOCKED_PENDING_EXTERNAL_TXD_SD_FAILSAFE",
    ]
    order = {"Mode": 0, "SD": 1, "Rxd": 2, "Txd": 3}
    for row in sorted(role_rows, key=lambda item: (int(item["lane"]), order[str(item["logical_signal"])])):
        port = row["rtl_port"]
        lines.append("")
        lines.append(
            f"# {row['module_id']} {row['logical_signal']}: J10-{row['connector_pin']} -> "
            f"{row['fpga_package_pin']} bank {row['io_bank']}"
        )
        lines.append(f"set_property PACKAGE_PIN {row['fpga_package_pin']} [get_ports {{{port}}}]")
        lines.append(f"set_property IOSTANDARD LVCMOS33 [get_ports {{{port}}}]")
        if row["fpga_direction"] == "output_to_tfdu":
            lines.append(f"set_property DRIVE 4 [get_ports {{{port}}}]")
            lines.append(f"set_property SLEW SLOW [get_ports {{{port}}}]")
    xdc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_rel, xdc_rel


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    sources = source_manifest()
    rows = signal_rows()

    common_profile = {
        "schema_version": 1,
        "profile_family": "P10_AX7020_COMMON",
        "status": "DRAFT_HARDWARE_ADMISSION_BLOCKED",
        "exact_documented_board_model": "ALINX AX7020",
        "exact_documented_fpga_marking": "XC7Z020-2CLG400I",
        "vivado_part": "xc7z020clg400-2",
        "physical_board_pcb_revision": "PENDING_PHYSICAL_SILKSCREEN_OR_PHOTO",
        "ps_clock_mhz": 33.333333,
        "pl_oscillator_mhz": 50.0,
        "ddr": {
            "documented_population": "two H5TQ4G63AFR-PBC (MT41J256M16RE-125 compatible)",
            "capacity_bits_total": 8_589_934_592,
            "capacity_bytes": 1_073_741_824,
            "bus_width_bits": 32,
            "frequency_mhz": 533.333333,
            "official_2023_1_ps_preset_part": "MT41J256M16 RE-125",
            "official_ps_preset": OFFICIAL_ALINX_REPO,
        },
        "j10": {
            "connector": "keyed 2x20 2.54 mm header",
            "pin1_orientation": "With J10 board silkscreen readable and the keyed shroud as photographed, pin 1 is the left near/lower-row corner marked '1'; pin 2 is directly above/far-row and marked '2'.",
            "signal_series_ohms": 33,
            "bank34_vcco_volts": 3.3,
            "bank35_vcco_volts": 3.3,
        },
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "sources": sources,
    }
    write_yaml("board_profiles/ax7020_common/board_identity.yaml", common_profile)

    profile_paths: dict[str, dict[str, str]] = {}
    for role in ROLES:
        csv_rel, xdc_rel = write_pinmap_and_xdc(role, rows)
        role_dir = "ax7020_fixed_2lane" if role == "fixed" else "ax7020_rotating_2lane"
        profile_id = "P10_AX7020_FIXED_2LANE" if role == "fixed" else "P10_AX7020_ROTATING_2LANE"
        profile = {
            "schema_version": 1,
            "profile_id": profile_id,
            "node_role": role,
            "proposed_board_id": ROLES[role]["board_proposed_id"],
            "physical_board_identity": "PENDING_UNIQUE_JTAG_CABLE_AND_PHYSICAL_MARKING_BINDING",
            "common_profile": "board_profiles/ax7020_common/board_identity.yaml",
            "vivado_part": "xc7z020clg400-2",
            "pinmap": csv_rel,
            "xdc": xdc_rel,
            "lane_count": 2,
            "allowed_lane_masks": [1, 2, 3],
            "modules": ROLES[role]["modules"],
            "register_map": "config/register_map/ir_axi_regs.yaml",
            "dma": "AXI DMA scatter-gather; role-local DDR only",
            "network_required": False,
            "movement_allowed": False,
            "hardware_admission": False,
            "blocking_condition": "P10-SAFETY-POWERUP-001",
        }
        write_yaml(f"board_profiles/{role_dir}/profile.yaml", profile)
        profile_paths[role] = {"profile": f"board_profiles/{role_dir}/profile.yaml", "pinmap": csv_rel, "xdc": xdc_rel}

    wiring = {
        "schema_version": 1,
        "configuration_id": "P10_AX7020_DUAL_NODE_2LANE_J10_CONFIRMED",
        "status": "USER_WIRING_INTENT_CONFIRMED_HARDWARE_ADMISSION_BLOCKED",
        "generated_at_utc": generated_at,
        "goal": "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md",
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": False,
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "network_used": False,
        "movement_allowed": False,
        "rewiring_allowed": False,
        "roles": ROLES,
        "lanes": {
            "lane0": {"fixed": "F0", "rotating_role": "R0", "physical_pair": "A-to-A", "cross_pairing": False},
            "lane1": {"fixed": "F1", "rotating_role": "R1", "physical_pair": "B-to-B", "cross_pairing": False},
        },
        "connector_pin1_orientation": common_profile["j10"]["pin1_orientation"],
        "existing_power_and_ground": {
            "owner": "user",
            "change_authorized": False,
            "documented_small_board_header": {
                "pin1": "VCC2 direct through R1=0 ohm; VCC1 through R6=47 ohm",
                "pins2_4_6": "GND",
            },
            "measured_voltage": "PENDING_DIRECT_MEASUREMENT",
        },
        "power_sequence": [
            "Do not alter any existing VCC/GND wiring under this authorization.",
            "Any future connector work requires all boards and TFDU supplies powered off.",
            "Before power-up verify ground continuity, rail voltage, rail polarity, and absence of shorts.",
            "Hardware admission additionally requires passive Txd-low and SD-high evidence in FPGA-unconfigured and partial-power states.",
        ],
        "jtag_role": "Two independent JTAG cable identities must be bound to AX7020-F and AX7020-R before any programming.",
        "uart_role": "Role-local PS diagnostic log only; UART cannot arm or bypass the physical TX kill.",
        "signal_lines": rows,
        "profiles": profile_paths,
        "sources": sources,
    }
    write_yaml("config/hardware/p10_active_wiring.yaml", wiring)

    board_inventory = {
        "schema_version": 1,
        "inventory_id": "P10_AX7020_DUAL_BOARD_INVENTORY",
        "document_set_status": "INCOMPLETE_PHYSICAL_IDENTITY",
        "documented_model": "ALINX AX7020",
        "documented_fpga": "XC7Z020-2CLG400I",
        "vivado_part": "xc7z020clg400-2",
        "boards": [
            {
                "proposed_id": "AX7020-F",
                "role": "fixed",
                "full_model_from_physical_board": "PENDING_PHYSICAL_PHOTO",
                "pcb_revision": "PENDING_PHYSICAL_SILKSCREEN_OR_PHOTO",
                "fpga_marking_from_physical_board": "PENDING_PHYSICAL_PHOTO",
                "front_photo": "PENDING_USER_DOCUMENT",
                "back_photo": "PENDING_USER_DOCUMENT",
                "jtag_cable_identity": "PENDING_ROLE_BINDING",
            },
            {
                "proposed_id": "AX7020-R",
                "role": "rotating_role_stationary_for_p10",
                "full_model_from_physical_board": "PENDING_PHYSICAL_PHOTO",
                "pcb_revision": "PENDING_PHYSICAL_SILKSCREEN_OR_PHOTO",
                "fpga_marking_from_physical_board": "PENDING_PHYSICAL_PHOTO",
                "front_photo": "PENDING_USER_DOCUMENT",
                "back_photo": "PENDING_USER_DOCUMENT",
                "jtag_cable_identity": "PENDING_ROLE_BINDING",
            },
        ],
        "reference_file_inventory": "evidence/generated/p10_board_reference_file_inventory.json",
        "sources": sources,
    }
    write_yaml("config/hardware/p10_board_inventory.yaml", board_inventory)

    tfdu_inventory = {
        "schema_version": 1,
        "inventory_id": "P10_TFDU_FOUR_MODULE_INVENTORY",
        "document_set_status": "INCOMPLETE_AS_BUILT_IDENTITY_AND_FAILSAFE",
        "intended_device": "TFDU6102",
        "schematic_symbol_identity": "TFDU6108-TT3 symbol/footprint used in supplied SchDoc; actual mounted marking not photographed",
        "small_board_header": {
            "pin1": "VCC2; R1=0 ohm to device pin1; R6=47 ohm onward to VCC1/device pin6",
            "pin2": "GND",
            "pin3": "Txd through R2=22 ohm to device pin3",
            "pin4": "GND",
            "pin5": "Rxd through R3=22 ohm to device pin4",
            "pin6": "GND",
            "pin7": "SD through R4=22 ohm to device pin5",
            "pin8": "Mode through R5=22 ohm to device pin7",
        },
        "on_board_bias": {
            "Txd_pull_down": "NOT_PRESENT_IN_SUPPLIED_SCHEMATIC",
            "SD_pull_up": "NOT_PRESENT_IN_SUPPLIED_SCHEMATIC",
            "Mode_pull": "NOT_PRESENT_IN_SUPPLIED_SCHEMATIC",
        },
        "modules": [
            {"module_id": "F0", "board": "AX7020-F", "position": "J10-A", "actual_marking": "PENDING_PHOTO", "pcb_revision": "PENDING_PHOTO"},
            {"module_id": "F1", "board": "AX7020-F", "position": "J10-B", "actual_marking": "PENDING_PHOTO", "pcb_revision": "PENDING_PHOTO"},
            {"module_id": "R0", "board": "AX7020-R", "position": "J10-A", "actual_marking": "PENDING_PHOTO", "pcb_revision": "PENDING_PHOTO"},
            {"module_id": "R1", "board": "AX7020-R", "position": "J10-B", "actual_marking": "PENDING_PHOTO", "pcb_revision": "PENDING_PHOTO"},
        ],
        "sources": sources,
    }
    write_yaml("config/hardware/p10_tfdu_module_inventory.yaml", tfdu_inventory)

    blocker = {
        "schema_version": 1,
        "blocker_id": "P10-SAFETY-POWERUP-001",
        "severity": "SEVERE_BLOCKER",
        "status": "OPEN",
        "hardware_campaign_admitted": False,
        "hardware_actions_executed": False,
        "finding": "Passive fail-safe levels for all four TFDU Txd and SD inputs are not established.",
        "direct_evidence": [
            "The supplied TFDU small-board schematic contains R2-R5 as 22-ohm series resistors, R1=0 ohm and R6=47 ohm; it contains no Txd pull-down and no SD pull-up.",
            "The selected AX7020 J10 Txd and SD nets have 33-ohm series resistor arrays but no discrete fail-safe pulls in the official schematic.",
            "AX7020 U13/IO1_12P/PUDC_B is held low by R29=1 kohm, which enables 7-series SelectIO internal pull-ups during configuration; activation is power-sequence dependent and cannot prove the required Txd-low/SD-high state.",
            "A configured shutdown bitstream can drive Txd low and SD high only after PL configuration; it cannot prove FPGA-unconfigured, open-circuit or partial-power behavior.",
        ],
        "requirements": [
            "AGENTS.md: physical Txd must default low on reset/fault.",
            "AGENTS.md: full shutdown requires SD high and Txd low.",
            "AGENTS.md: fail-low behavior is required at power-up, open circuit, undriven input, FPGA-unconfigured and partial-power states.",
            "Fast-track section 2: autonomous TX or final-TX-kill violations are severe blockers.",
        ],
        "additional_electrical_risk": {
            "id": "P10-RX-B-R29-001",
            "signal": "F1/R1 Rxd at J10-26 / U13",
            "finding": "AX7020 R29 is a 1-kohm pull-down on this receiver input.",
            "datasheet_gap": "TFDU6102 VOH is guaranteed only at 250/500-uA test currents; a 1-kohm load at 3.3 V demands approximately 3.3 mA.",
            "damage_risk": "No output-to-output connection found; functional high-level compliance is not guaranteed.",
        },
        "required_user_resolution": [
            "Provide the as-built schematic/photo and resistor values proving a passive pull-down on every Txd and passive pull-up on every SD, including the actual external harness if the bias is not on the small board.",
            "Alternatively issue a new explicit authorization permitting a documented fail-safe hardware revision/rewire; the current fast-track explicitly sets REWIRING_ALLOWED=false.",
            "Provide or authorize safe external measurement evidence for Txd and SD during FPGA-unconfigured and partial-power states before JTAG programming is attempted.",
        ],
        "sources": sources,
    }
    write_json("evidence/generated/p10_severe_hardware_blocker.json", blocker)

    board_doc = {
        "schema_version": 1,
        "test_id": "P10-BOARD-DOCUMENT-INTAKE",
        "status": "INCOMPLETE",
        "board_document_set": "INCOMPLETE_PHYSICAL_REVISION_IDENTITY",
        "tfdu_document_set": "INCOMPLETE_AS_BUILT_IDENTITY_AND_FAILSAFE",
        "official_board_sources_sufficient_for_j10_pin_mapping": True,
        "official_board_sources_sufficient_for_physical_board_revision": False,
        "official_tfdu_datasheet_available": True,
        "supplied_tfdu_small_board_schematic_available": True,
        "supplied_tfdu_small_board_schematic_exact_part_mismatch": "symbol is TFDU6108-TT3 while intended mounted part is TFDU6102",
        "reference_file_inventory": "evidence/generated/p10_board_reference_file_inventory.json",
        "sources": sources,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
    }
    write_json("evidence/generated/p10_board_document_intake.json", board_doc)

    audit = {
        "schema_version": 1,
        "test_id": "P10-WIRING-DESIGN-AUDIT",
        "status": "FAIL_CLOSED_SEVERE_BLOCKER",
        "mapping_complete": True,
        "signal_line_count": len(rows),
        "pinmap_independently_derived_for_ax7020": True,
        "ax7010_xdc_reused": False,
        "j10_pin1_orientation_documented": True,
        "bank_vcco_iostandard": "PASS_FOR_DOCUMENTED_AX7020_REFERENCE: bank34/bank35 3.3 V, LVCMOS33",
        "connector_series_resistors": "PASS: 33 ohm on all selected J10 signal nets",
        "board_peripheral_conflict": "PASS_FOR_SELECTED_NETS_EXCEPT_R29_B_RXD",
        "r29_b_rxd_loading": "ELECTRICAL_GUARANTEE_GAP",
        "powerup_reset_default": "FAIL: passive Txd-low and SD-high are not established",
        "physical_board_role_binding": "PENDING",
        "hardware_admission": False,
        "hardware_actions_executed": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "signal_lines": rows,
        "sources": sources,
    }
    write_json("evidence/generated/p10_wiring_design_audit.json", audit)

    proposal_lines = [
        "# P10 AX7020 dual-board J10 wiring proposal and audit",
        "",
        "> Mapping status: user-confirmed. Hardware admission: **blocked** by `P10-SAFETY-POWERUP-001`.",
        "",
        "The fixed-role board is proposed as `AX7020-F` with `F0/F1`; the stationary rotating-role board is proposed as `AX7020-R` with `R0/R1`. Lane 0 is `F0 ↔ R0` (A-to-A) and lane 1 is `F1 ↔ R1` (B-to-B). A/B cross-pairing is prohibited.",
        "",
        "## Connector orientation",
        "",
        common_profile["j10"]["pin1_orientation"],
        "",
        "## Signal wiring",
        "",
        "| Board role | Module | Lane | Signal | FPGA direction | Connector pin | Package pin | Bank | VCCO | IOSTANDARD | TFDU header/device pin | Reset/default | Pull | Source location | Notes |",
        "|---|---|---:|---|---|---|---|---:|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        proposal_lines.append(
            f"| {row['board_role']} | {row['module_id']} | {row['lane']} | {row['logical_signal']} | "
            f"{row['fpga_direction']} | J10-{row['connector_pin']} | {row['fpga_package_pin']} | "
            f"{row['io_bank']} | {row['vcco_volts']} V | {row['iostandard']} | "
            f"{row['tfdu_board_pin']} / {row['tfdu_device_pin']} | {row['reset_default']} | "
            f"{row['pull']} | {row['source_page_table']} | {row['notes']} |"
        )
    proposal_lines.extend(
        [
            "",
            "## Power, JTAG, UART, and pre-power checks",
            "",
            "- Existing TFDU VCC/GND wiring remains user-owned and must not be altered under the current authorization.",
            "- Any future connector change requires both AX7020 boards and all TFDU rails to be powered off.",
            "- Before power-up: verify ground continuity, supply polarity, actual VCC1/VCC2 voltage/topology, no shorts, and all four passive Txd-low/SD-high states.",
            "- Bind two distinct JTAG cable identities to AX7020-F and AX7020-R before programming either board.",
            "- UART is role-local diagnostic output only; it cannot arm TX or bypass the final TX kill.",
            "- A shutdown bitstream must drive both Txd outputs low and both SD outputs high, but it does not cure an unconfigured/partial-power electrical gap.",
            "",
            "## Open items",
            "",
            "- Severe blocker: no documented passive Txd pull-down or SD pull-up on any supplied TFDU small-board schematic.",
            "- J10-26/U13 (F1/R1 Rxd) has AX7020 R29=1 kohm to ground; TFDU6102 high-level compliance is not guaranteed at that load.",
            "- Actual AX7020-F/AX7020-R PCB revisions, FPGA markings, and unique JTAG identities remain unbound.",
            "- Actual four-module markings/revisions and as-built VCC1/VCC2/harness bias remain undocumented.",
            "",
            "## Hardware admission decision",
            "",
            "`FAIL_CLOSED`: no hw_server/JTAG/program/ELF/UART/TFDU action is admitted until `P10-SAFETY-POWERUP-001` is resolved.",
        ]
    )
    proposal_path = ROOT / "docs/hardware/P10_AX7020_DUAL_BOARD_WIRING_PROPOSAL.md"
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text("\n".join(proposal_lines) + "\n", encoding="utf-8")

    required_docs = """# P10 required physical board/module evidence

The official AX7020 reference set is sufficient to derive the J10 package pins, banks, documented VCCO, and connector orientation. It does not identify the two physical boards or prove the as-built TFDU fail-safe network.

Required from the user before hardware admission:

- full model marking for both physical AX7020 boards;
- PCB revision/silkscreen for both boards;
- full FPGA top marking for both boards;
- clear front/back photographs of both boards, including J10 pin-1 markings;
- the official user manual and schematic revision that matches each physical PCB (the current local copies remain reference candidates);
- physical confirmation that J10 bank 34 and bank 35 VCCO are 3.3 V on both boards;
- clear front/back photographs and revision markings for F0, F1, R0, and R1;
- an as-built TFDU small-board schematic/pinout that identifies the mounted device as TFDU6102 rather than only a TFDU6108 library symbol;
- exact VCC1/VCC2 rail voltage and the actual R1/R6/decoupling population;
- exact Mode and SD structure;
- passive fail-safe component values and locations proving Txd LOW and SD HIGH for every module at reset, FPGA-unconfigured, open-circuit, and partial-power states;
- unique JTAG cable/target identifiers that bind the physical fixed and rotating-role boards.

Do not substitute zero, `unknown`, a similar board revision, or the AX7010 XDC for any missing item.
"""
    required_path = ROOT / "docs/hardware/P10_REQUIRED_BOARD_DOCUMENTS.md"
    required_path.write_text(required_docs, encoding="utf-8")

    blocker_md = """# P10 severe hardware blocker: TFDU power-up fail-safe is not established

`P10-SAFETY-POWERUP-001` is an open severe blocker. The current fast-track authorizes hardware actions, but it also requires Codex to stop for autonomous-TX/final-TX-kill safety violations.

Direct evidence:

- The supplied TFDU small-board `SchDoc` contains four 22-ohm signal series resistors, a 0-ohm VCC2 path, and a 47-ohm VCC1 filter. It contains no Txd pull-down and no SD pull-up.
- The official AX7020 schematic shows only 33-ohm series arrays on the selected J10 Txd/SD nets; it shows no discrete fail-safe bias on those nets.
- AX7020 R29 holds U13/`PUDC_B` low with 1 kohm. The 7-series configuration contract therefore enables internal SelectIO pull-ups during configuration, subject to power sequencing. That cannot establish the required physical Txd-low/SD-high state in every power/reset/open-circuit condition.
- A shutdown image controls pins only after PL configuration and cannot prove FPGA-unconfigured or partial-power behavior.

The same schematic also places R29=1 kohm to ground on the requested B-position Rxd (`J10-26/U13`). This is not an output-to-output connection, but its approximately 3.3 mA high-state load exceeds the TFDU6102 datasheet's 250/500-uA VOH guarantee points.

No hw_server connection, JTAG enumeration, FPGA programming, ELF execution, UART write, or TFDU drive was performed. Resolution requires as-built passive-bias evidence, or a new authorization that permits a documented fail-safe hardware revision because the current goal prohibits rewiring.
"""
    blocker_path = ROOT / "docs/hardware/P10_SEVERE_HARDWARE_BLOCKER.md"
    blocker_path.write_text(blocker_md, encoding="utf-8")

    board_md = """# P10 board-document intake

- Board reference file inventory: `PASS` (71 files, every file SHA256-hashed).
- Official AX7020 J10 pin mapping source set: `PASS` for the documented AX7020 reference design.
- Physical board revision/marking identity: `INCOMPLETE` for both boards.
- TFDU6102 manufacturer datasheet: `PASS`.
- Supplied TFDU small-board schematic: `PRESENT`, but its library symbol/footprint says TFDU6108-TT3 and the four actual module markings/revisions are not photographed.
- As-built passive Txd-low/SD-high safety network: `INCOMPLETE` and safety-blocking.

See `evidence/generated/p10_board_document_intake.json` and `docs/hardware/P10_REQUIRED_BOARD_DOCUMENTS.md`.
"""
    (ROOT / "evidence/generated/p10_board_document_intake.md").write_text(board_md, encoding="utf-8")

    audit_md = """# P10 wiring design audit

The confirmed J10 A/B mapping is independently supported by the AX7020 manual, schematic, and pin workbook. Both role-specific pinmaps/XDC files use `xc7z020clg400-2`, LVCMOS33, bank 34/35 at documented 3.3 V, and do not source the AX7010 XDC.

Mapping is complete, but hardware admission fails closed:

- `P10-SAFETY-POWERUP-001`: no passive Txd-low/SD-high guarantee in unconfigured/open-circuit/partial-power states.
- `P10-RX-B-R29-001`: J10-26/U13 Rxd is loaded by R29=1 kohm to ground, outside the TFDU6102 guaranteed VOH test load.
- physical F/R board identity and JTAG cable binding are pending.

Result: `FAIL_CLOSED_SEVERE_BLOCKER`; hardware actions executed: `false`.
"""
    (ROOT / "evidence/generated/p10_wiring_design_audit.md").write_text(audit_md, encoding="utf-8")

    outputs = [
        "config/hardware/p10_active_wiring.yaml",
        "config/hardware/p10_board_inventory.yaml",
        "config/hardware/p10_tfdu_module_inventory.yaml",
        "board_profiles/ax7020_common/board_identity.yaml",
        *[item for value in profile_paths.values() for item in value.values()],
        "docs/hardware/P10_AX7020_DUAL_BOARD_WIRING_PROPOSAL.md",
        "docs/hardware/P10_REQUIRED_BOARD_DOCUMENTS.md",
        "docs/hardware/P10_SEVERE_HARDWARE_BLOCKER.md",
        "evidence/generated/p10_severe_hardware_blocker.json",
        "evidence/generated/p10_board_document_intake.json",
        "evidence/generated/p10_board_document_intake.md",
        "evidence/generated/p10_wiring_design_audit.json",
        "evidence/generated/p10_wiring_design_audit.md",
    ]
    manifest = {
        "schema_version": 1,
        "test_id": "P10-WIRING-ARTIFACT-GENERATION",
        "status": "PASS_OFFLINE_GENERATION_HARDWARE_BLOCKED",
        "generated_at_utc": generated_at,
        "outputs": [
            {"path": item, "bytes": (ROOT / item).stat().st_size, "sha256": sha256_file(ROOT / item)}
            for item in sorted(set(outputs))
        ],
        "hardware_actions_executed": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
    }
    write_json("evidence/generated/p10_wiring_artifact_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "outputs": len(manifest["outputs"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
