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
HARDWARE_COMPARISON = Path(r"C:\Users\user\Desktop\AX7010_AX7020_HARDWARE_COMPARISON.md")

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
    "ax7010_ax7020_hardware_comparison": {
        "path": HARDWARE_COMPARISON,
        "sha256": "a8c47064d725b28f7679aa208a1195b4075b3a0ba3a8bbe335c3c0fbea98cb13",
        "authority": "user-supplied cross-board comparison with per-file hashes",
    },
}

USER_CLARIFICATION = {
    "date": "2026-07-30",
    "tfdu_modules_previously_operational_on_ax7010": True,
    "tfdu_module_identity_reconfirmation_required_for_p10": False,
    "ax7020_role_binding_method": "JTAG_CABLE_SERIAL",
    "evidence_boundary": (
        "Prior operation on AX7010 and byte-identical AX7010/AX7020 base-board J10 "
        "references establish empirical module/circuit compatibility. They do not constitute "
        "a fresh AX7020 hardware PASS or prove the canonical reset/fault, "
        "FPGA-unconfigured, or partial-power TX-disabled requirement."
    ),
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
                        "outside the TFDU6102 guaranteed VOH test currents of 250/500 uA. The user "
                        "confirms prior operation on the byte-identical AX7010 base/J10 circuit."
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
    jtag_inventory_path = ROOT / "config/hardware/p10_jtag_identity_inventory.json"
    jtag_inventory = {
        "schema_version": 1,
        "inventory_id": "P10_DUAL_AX7020_JTAG_IDENTITY",
        "status": "PENDING_LIVE_READ_ONLY_ENUMERATION",
        "role_binding_method": "JTAG_CABLE_SERIAL",
        "observed_cable_serials": [],
        "fixed_board_serial": "PENDING_LIVE_READ_ONLY_ENUMERATION_AND_ROLE_BINDING",
        "rotating_board_serial": "PENDING_LIVE_READ_ONLY_ENUMERATION_AND_ROLE_BINDING",
        "target_order_used_for_role_binding": False,
    }
    if jtag_inventory_path.is_file():
        existing_jtag_inventory = json.loads(jtag_inventory_path.read_text(encoding="utf-8"))
        if (
            existing_jtag_inventory.get("inventory_id") == "P10_DUAL_AX7020_JTAG_IDENTITY"
            and existing_jtag_inventory.get("role_binding_method") == "JTAG_CABLE_SERIAL"
            and str(existing_jtag_inventory.get("status", "")).startswith("ENUMERATED")
        ):
            jtag_inventory = existing_jtag_inventory
    jtag_enumerated = str(jtag_inventory["status"]).startswith("ENUMERATED")
    observed_jtag_serials = list(jtag_inventory.get("observed_cable_serials", []))
    jtag_role_status = (
        "ENUMERATED_UNASSIGNED: " + ", ".join(observed_jtag_serials)
        if jtag_enumerated
        else "PENDING_LIVE_READ_ONLY_ENUMERATION"
    )
    board_document_status = (
        "REFERENCE_PASS_PHYSICAL_REVISION_GAPS_NONBLOCKING_JTAG_SERIALS_ENUMERATED_ROLE_ASSIGNMENT_PENDING"
        if jtag_enumerated
        else "REFERENCE_PASS_PHYSICAL_REVISION_GAPS_NONBLOCKING_JTAG_ROLE_BINDING_PENDING"
    )

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
            "physical_board_identity": "PENDING_JTAG_CABLE_SERIAL_ROLE_BINDING",
            "physical_board_identity_method": "JTAG_CABLE_SERIAL",
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
        "status": (
            "USER_WIRING_INTENT_CONFIRMED_JTAG_SERIALS_ENUMERATED_ROLE_ASSIGNMENT_PENDING_HARDWARE_ADMISSION_BLOCKED"
            if jtag_enumerated
            else "USER_WIRING_INTENT_CONFIRMED_HARDWARE_ADMISSION_BLOCKED"
        ),
        "generated_at_utc": generated_at,
        "goal": "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md",
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": jtag_enumerated,
        "hardware_action_scope": (
            "READ_ONLY_JTAG_CABLE_SERIAL_ENUMERATION_ONLY" if jtag_enumerated else "NONE"
        ),
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "network_used": False,
        "movement_allowed": False,
        "rewiring_allowed": False,
        "user_clarification": USER_CLARIFICATION,
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
        "jtag_role": (
            "JTAG cable serial is the authoritative P10 F/R role key. Observed serials are "
            + ", ".join(observed_jtag_serials)
            + "; each must be explicitly bound to AX7020-F or AX7020-R before programming."
            if jtag_enumerated
            else "JTAG cable serial is the authoritative P10 F/R role key. Read-only enumeration is allowed; each observed serial must be explicitly bound to AX7020-F or AX7020-R before programming."
        ),
        "uart_role": "Role-local PS diagnostic log only; UART cannot arm or bypass the physical TX kill.",
        "signal_lines": rows,
        "profiles": profile_paths,
        "sources": sources,
    }
    write_yaml("config/hardware/p10_active_wiring.yaml", wiring)

    board_inventory = {
        "schema_version": 1,
        "inventory_id": "P10_AX7020_DUAL_BOARD_INVENTORY",
        "document_set_status": board_document_status,
        "documented_model": "ALINX AX7020",
        "documented_fpga": "XC7Z020-2CLG400I",
        "vivado_part": "xc7z020clg400-2",
        "role_binding_method": "JTAG_CABLE_SERIAL",
        "live_jtag_identity_inventory": "config/hardware/p10_jtag_identity_inventory.json",
        "live_jtag_role_status": jtag_role_status,
        "user_clarification": USER_CLARIFICATION,
        "boards": [
            {
                "proposed_id": "AX7020-F",
                "role": "fixed",
                "full_model_from_physical_board": "DOCUMENTATION_GAP_NONBLOCKING",
                "pcb_revision": "DOCUMENTATION_GAP_NONBLOCKING",
                "fpga_marking_from_physical_board": "DOCUMENTATION_GAP_NONBLOCKING",
                "front_photo": "NOT_REQUIRED_FOR_P10_ROLE_BINDING",
                "back_photo": "NOT_REQUIRED_FOR_P10_ROLE_BINDING",
                "jtag_cable_identity": jtag_inventory["fixed_board_serial"],
            },
            {
                "proposed_id": "AX7020-R",
                "role": "rotating_role_stationary_for_p10",
                "full_model_from_physical_board": "DOCUMENTATION_GAP_NONBLOCKING",
                "pcb_revision": "DOCUMENTATION_GAP_NONBLOCKING",
                "fpga_marking_from_physical_board": "DOCUMENTATION_GAP_NONBLOCKING",
                "front_photo": "NOT_REQUIRED_FOR_P10_ROLE_BINDING",
                "back_photo": "NOT_REQUIRED_FOR_P10_ROLE_BINDING",
                "jtag_cable_identity": jtag_inventory["rotating_board_serial"],
            },
        ],
        "reference_file_inventory": "evidence/generated/p10_board_reference_file_inventory.json",
        "sources": sources,
    }
    write_yaml("config/hardware/p10_board_inventory.yaml", board_inventory)
    write_json("config/hardware/p10_jtag_identity_inventory.json", jtag_inventory)

    tfdu_inventory = {
        "schema_version": 1,
        "inventory_id": "P10_TFDU_FOUR_MODULE_INVENTORY",
        "document_set_status": "USER_ACCEPTED_HISTORICAL_FUNCTIONAL_IDENTITY_SAFETY_GAP_SEPARATE",
        "functional_identity_status": "USER_CONFIRMED_PREVIOUSLY_OPERATIONAL_ON_AX7010",
        "identity_reconfirmation_required_for_p10": False,
        "user_clarification": USER_CLARIFICATION,
        "intended_device": "TFDU6102",
        "schematic_symbol_identity": "TFDU6108-TT3 symbol/footprint used in supplied SchDoc; user accepts the four historically operational modules without renewed marking/revision inspection",
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
            {"module_id": "F0", "board": "AX7020-F", "position": "J10-A", "actual_marking": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "pcb_revision": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "functional_history": "USER_CONFIRMED_OPERATIONAL_ON_AX7010"},
            {"module_id": "F1", "board": "AX7020-F", "position": "J10-B", "actual_marking": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "pcb_revision": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "functional_history": "USER_CONFIRMED_OPERATIONAL_ON_AX7010"},
            {"module_id": "R0", "board": "AX7020-R", "position": "J10-A", "actual_marking": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "pcb_revision": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "functional_history": "USER_CONFIRMED_OPERATIONAL_ON_AX7010"},
            {"module_id": "R1", "board": "AX7020-R", "position": "J10-B", "actual_marking": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "pcb_revision": "NOT_RECONFIRMED_PER_USER_NOT_REQUIRED_FOR_P10", "functional_history": "USER_CONFIRMED_OPERATIONAL_ON_AX7010"},
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
        "hardware_actions_executed": jtag_enumerated,
        "hardware_action_scope": (
            "READ_ONLY_JTAG_CABLE_SERIAL_ENUMERATION_ONLY" if jtag_enumerated else "NONE"
        ),
        "finding": "Passive fail-safe levels for all four TFDU Txd and SD inputs are not established.",
        "user_clarification": USER_CLARIFICATION,
        "direct_evidence": [
            "The supplied TFDU small-board schematic contains R2-R5 as 22-ohm series resistors, R1=0 ohm and R6=47 ohm; it contains no Txd pull-down and no SD pull-up.",
            "The selected AX7020 J10 Txd and SD nets have 33-ohm series resistor arrays but no discrete fail-safe pulls in the official schematic.",
            "AX7020 U13/IO1_12P/PUDC_B is held low by R29=1 kohm, which enables 7-series SelectIO internal pull-ups during configuration; activation is power-sequence dependent and cannot prove the required Txd-low/SD-high state.",
            "A configured shutdown bitstream can drive Txd low and SD high only after PL configuration; it cannot prove FPGA-unconfigured, reset/fault, or partial-power behavior.",
            "The user confirms that all four TFDU small boards previously operated on AX7010. The supplied comparison shows byte-identical AX7010/AX7020 base-PCB J10 references. This closes renewed module identity inspection for P10 but does not prove the passive power-up safety state.",
        ],
        "requirements": [
            "AGENTS.md: physical Txd must default low on reset/fault.",
            "AGENTS.md: full shutdown requires SD high and Txd low.",
            "PROJECT_CONSTRAINTS.txt: TX output default is LOW, partial-power behavior is FAIL_LOW, and FPGA-unconfigured behavior is TX_DISABLED.",
            "Fast-track section 2: autonomous TX or final-TX-kill violations are severe blockers.",
        ],
        "additional_electrical_risk": {
            "id": "P10-RX-B-R29-001",
            "classification": "DATASHEET_GUARANTEE_GAP_EMPIRICALLY_OPERABLE_ON_IDENTICAL_AX7010_BASE_CIRCUIT",
            "signal": "F1/R1 Rxd at J10-26 / U13",
            "finding": "AX7020 R29 is a 1-kohm pull-down on this receiver input.",
            "datasheet_gap": "TFDU6102 VOH is guaranteed only at 250/500-uA test currents; a 1-kohm load at 3.3 V demands approximately 3.3 mA.",
            "damage_risk": "No output-to-output connection found; functional high-level compliance is not guaranteed.",
            "empirical_context": "User-confirmed prior operation at the same J10 positions on AX7010; the supplied comparison records byte-identical AX7010/AX7020 base-board schematic and connector circuitry.",
            "blocking_scope": "Not treated as an independent severe damage-risk blocker; retain as a formal datasheet-guarantee gap for live RX evidence.",
        },
        "required_user_resolution": [
            "Provide existing circuit or measurement evidence proving a fail-low physical Txd state for every module during reset/fault, FPGA-unconfigured, and partial-power conditions; renewed TFDU module identity/photos are not requested.",
            "Alternatively issue a new explicit authorization permitting a documented fail-safe hardware revision/rewire; the current fast-track explicitly sets REWIRING_ALLOWED=false.",
            "Provide or authorize safe external measurement evidence for Txd and SD during FPGA-unconfigured and partial-power states before JTAG programming is attempted.",
        ],
        "sources": sources,
    }
    write_json("evidence/generated/p10_severe_hardware_blocker.json", blocker)

    board_doc = {
        "schema_version": 1,
        "test_id": "P10-BOARD-DOCUMENT-INTAKE",
        "status": "PASS_WITH_DOCUMENTATION_GAPS_NONBLOCKING_AND_SEPARATE_SAFETY_BLOCKER",
        "board_document_set": "PASS_FOR_J10_MAPPING_PHYSICAL_REVISION_GAPS_NONBLOCKING",
        "tfdu_document_set": "PASS_FOR_USER_ACCEPTED_FUNCTIONAL_IDENTITY_SAFETY_SEPARATELY_OPEN",
        "official_board_sources_sufficient_for_j10_pin_mapping": True,
        "official_board_sources_sufficient_for_physical_board_revision": False,
        "official_tfdu_datasheet_available": True,
        "supplied_tfdu_small_board_schematic_available": True,
        "supplied_tfdu_small_board_schematic_exact_part_mismatch": "symbol is TFDU6108-TT3 while intended mounted part is TFDU6102",
        "tfdu_module_identity_reconfirmation_required_for_p10": False,
        "tfdu_historical_functionality": "USER_CONFIRMED_PREVIOUSLY_OPERATIONAL_ON_AX7010",
        "user_clarification": USER_CLARIFICATION,
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
        "r29_b_rxd_loading": "ELECTRICAL_GUARANTEE_GAP_WITH_USER_CONFIRMED_PRIOR_OPERATION_ON_IDENTICAL_BASE_CIRCUIT",
        "powerup_reset_default": "FAIL: passive Txd-low and SD-high are not established",
        "physical_board_role_binding": jtag_role_status,
        "tfdu_module_identity": "USER_ACCEPTED_HISTORICAL_FUNCTIONAL_IDENTITY_NO_RECONFIRMATION_REQUIRED",
        "hardware_admission": False,
        "hardware_actions_executed": jtag_enumerated,
        "hardware_action_scope": (
            "READ_ONLY_JTAG_CABLE_SERIAL_ENUMERATION_ONLY" if jtag_enumerated else "NONE"
        ),
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
            (
                f"- JTAG cable serial is the authoritative F/R role key. Read-only enumeration observed {', '.join(observed_jtag_serials)}; explicitly bind each to AX7020-F or AX7020-R before programming."
                if jtag_enumerated
                else "- Use JTAG cable serial as the authoritative F/R role key. A bounded read-only enumeration may run now; bind each serial to AX7020-F or AX7020-R before programming."
            ),
            "- UART is role-local diagnostic output only; it cannot arm TX or bypass the final TX kill.",
            "- A shutdown bitstream must drive both Txd outputs low and both SD outputs high, but it does not cure an unconfigured/partial-power electrical gap.",
            "",
            "## Open items",
            "",
            "- Severe blocker: no documented passive Txd pull-down or SD pull-up on any supplied TFDU small-board schematic.",
            "- J10-26/U13 (F1/R1 Rxd) has AX7020 R29=1 kohm to ground. This remains a datasheet-guarantee gap, while user-confirmed AX7010 operation on the byte-identical base/J10 circuit supplies empirical compatibility context.",
            f"- AX7020-F/AX7020-R JTAG cable serial role binding remains pending (`{jtag_role_status}`); physical PCB revision/marking photos are nonblocking documentation gaps for this fast-track.",
            "- Per user direction, the four historically operational TFDU modules do not require renewed marking/revision/photo confirmation for P10.",
            "",
            "## Hardware admission decision",
            "",
            "`FAIL_CLOSED_FOR_ACTIVE_HARDWARE`: bounded read-only JTAG serial enumeration is admitted. Programming, ELF execution, UART writes, TFDU drive, and any configuration-changing action remain blocked by `P10-SAFETY-POWERUP-001`.",
        ]
    )
    proposal_path = ROOT / "docs/hardware/P10_AX7020_DUAL_BOARD_WIRING_PROPOSAL.md"
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text("\n".join(proposal_lines) + "\n", encoding="utf-8")

    required_docs = """# P10 remaining board and safety evidence

The official AX7020 reference set is sufficient to derive the J10 package pins, banks, documented VCCO, connector orientation, and independent AX7020 XDCs. The user confirms that all four TFDU small boards previously operated on AX7010 and does not require renewed small-board identity inspection. The supplied comparison records byte-identical AX7010/AX7020 base-PCB J10 design files.

Required before any programming or TFDU-driving hardware action:

- explicit F/R role assignment for the two read-only-enumerated JTAG cable serials recorded in `config/hardware/p10_jtag_identity_inventory.json`;
- existing circuit or measurement evidence that every physical Txd remains LOW during reset/fault, FPGA-unconfigured, and partial-power conditions;
- safe external measurement evidence for the Txd/SD states above, or a separately authorized documented fail-safe hardware revision (the current goal prohibits rewiring).

Nonblocking documentation gaps retained for provenance:

- physical AX7020 PCB revision/silkscreen and FPGA top marking;
- front/back photographs of the two AX7020 boards;
- direct physical confirmation of bank 34/35 VCCO and VCC1/VCC2 rail values.

Not requested again for P10 per the user's 2026-07-30 clarification:

- TFDU module front/back photographs;
- renewed TFDU module marking or PCB-revision confirmation;
- renewed proof that the modules functioned on AX7010.

Do not substitute zero, `unknown`, target order, a similar board revision, or the AX7010 XDC for a missing identity or electrical value.
"""
    required_path = ROOT / "docs/hardware/P10_REQUIRED_BOARD_DOCUMENTS.md"
    required_path.write_text(required_docs, encoding="utf-8")

    clarification_md = """# P10 user hardware clarifications

Recorded from the current user instructions on 2026-07-30:

- all four TFDU small boards previously operated on AX7010;
- renewed TFDU module hardware identity, marking, PCB-revision, and photo confirmation is not required for P10;
- the two AX7020 boards are to be distinguished and role-bound by JTAG cable serial;
- this clarification does not authorize target-order role assignment;
- this clarification does not convert historical AX7010 operation into fresh AX7020 hardware acceptance;
- this clarification does not waive the canonical TX-disabled requirements for reset/fault, FPGA-unconfigured, or partial-power states.

Supporting comparison input: `C:\\Users\\user\\Desktop\\AX7010_AX7020_HARDWARE_COMPARISON.md`, SHA256 `a8c47064d725b28f7679aa208a1195b4075b3a0ba3a8bbe335c3c0fbea98cb13`. It records byte-identical AX7010/AX7020 base-PCB schematic, connector, and pin-workbook design files. It is compatibility context, not fresh hardware evidence.
"""
    clarification_path = ROOT / "docs/hardware/P10_USER_HARDWARE_CLARIFICATIONS.md"
    clarification_path.write_text(clarification_md, encoding="utf-8")

    blocker_md = """# P10 severe hardware blocker: TFDU power-up fail-safe is not established

`P10-SAFETY-POWERUP-001` is an open severe blocker. The current fast-track authorizes hardware actions, but it also requires Codex to stop for autonomous-TX/final-TX-kill safety violations.

Direct evidence:

- The supplied TFDU small-board `SchDoc` contains four 22-ohm signal series resistors, a 0-ohm VCC2 path, and a 47-ohm VCC1 filter. It contains no Txd pull-down and no SD pull-up.
- The official AX7020 schematic shows only 33-ohm series arrays on the selected J10 Txd/SD nets; it shows no discrete fail-safe bias on those nets.
- AX7020 R29 holds U13/`PUDC_B` low with 1 kohm. The 7-series configuration contract therefore enables internal SelectIO pull-ups during configuration, subject to power sequencing. That cannot establish the required physical Txd-low/SD-high state in every power/reset/fault/partial-power condition.
- A shutdown image controls pins only after PL configuration and cannot prove FPGA-unconfigured or partial-power behavior.

The user confirms that all four TFDU small boards previously operated on AX7010. The supplied comparison records byte-identical AX7010/AX7020 base-PCB schematic and J10 circuitry. That is accepted as empirical module/circuit compatibility and removes any P10 request to re-inspect the four module markings, revisions, or photos. It does not establish the passive unconfigured/reset/partial-power safety state required by the canonical project constraints.

The same schematic also places R29=1 kohm to ground on the requested B-position Rxd (`J10-26/U13`). This is not an output-to-output connection, but its approximately 3.3 mA high-state load exceeds the TFDU6102 datasheet's 250/500-uA VOH guarantee points. User-confirmed prior operation on the identical AX7010 base/J10 circuit makes this an empirical-operability-backed datasheet gap, not an independent damage-risk blocker.

At artifact-generation time no hardware action was performed. A bounded read-only JTAG cable-serial enumeration is allowed because it neither configures the FPGA nor drives TFDU pins. FPGA programming, ELF execution, UART writes, TFDU drive, reset, and configuration-changing actions remain blocked. Resolution requires existing fail-low circuit/measurement evidence, or a new authorization that permits a documented fail-safe hardware revision because the current goal prohibits rewiring.
"""
    blocker_path = ROOT / "docs/hardware/P10_SEVERE_HARDWARE_BLOCKER.md"
    blocker_path.write_text(blocker_md, encoding="utf-8")

    board_md = """# P10 board-document intake

- Board reference file inventory: `PASS` (71 files, every file SHA256-hashed).
- Official AX7020 J10 pin mapping source set: `PASS` for the documented AX7020 reference design.
- Physical board revision/marking: retained as a nonblocking documentation gap; P10 role identity uses JTAG cable serial.
- TFDU6102 manufacturer datasheet: `PASS`.
- Supplied TFDU small-board schematic: `PRESENT`; its library symbol/footprint says TFDU6108-TT3.
- TFDU functional identity: `USER_ACCEPTED`; the user confirms all four modules previously operated on AX7010 and requires no renewed module marking/revision/photo check.
- AX7010/AX7020 base/J10 comparison: `PASS`; the supplied comparison reports byte-identical reference design files.
- As-built passive Txd-low/SD-high safety network: `INCOMPLETE` and safety-blocking.

See `evidence/generated/p10_board_document_intake.json` and `docs/hardware/P10_REQUIRED_BOARD_DOCUMENTS.md`.
"""
    (ROOT / "evidence/generated/p10_board_document_intake.md").write_text(board_md, encoding="utf-8")

    audit_md = f"""# P10 wiring design audit

The confirmed J10 A/B mapping is independently supported by the AX7020 manual, schematic, and pin workbook. Both role-specific pinmaps/XDC files use `xc7z020clg400-2`, LVCMOS33, bank 34/35 at documented 3.3 V, and do not source the AX7010 XDC.

Mapping is complete, but hardware admission fails closed:

- `P10-SAFETY-POWERUP-001`: no passive Txd-low/SD-high guarantee in reset/fault, unconfigured, or partial-power states.
- `P10-RX-B-R29-001`: J10-26/U13 Rxd is loaded by R29=1 kohm to ground, outside the TFDU6102 guaranteed VOH test load; user-confirmed prior AX7010 operation on the byte-identical base/J10 circuit supplies empirical compatibility context.
- physical F/R role binding by JTAG cable serial is pending: `{jtag_role_status}`.
- TFDU small-board identity is accepted from user-confirmed prior operation; renewed marking/revision/photo checks are not required.

Result: `FAIL_CLOSED_SEVERE_BLOCKER` for programming and active hardware; bounded read-only JTAG identity enumeration is allowed. Artifact-generation hardware actions executed: `false`.
"""
    (ROOT / "evidence/generated/p10_wiring_design_audit.md").write_text(audit_md, encoding="utf-8")

    outputs = [
        "config/hardware/p10_active_wiring.yaml",
        "config/hardware/p10_board_inventory.yaml",
        "config/hardware/p10_jtag_identity_inventory.json",
        "config/hardware/p10_tfdu_module_inventory.yaml",
        "board_profiles/ax7020_common/board_identity.yaml",
        *[item for value in profile_paths.values() for item in value.values()],
        "docs/hardware/P10_AX7020_DUAL_BOARD_WIRING_PROPOSAL.md",
        "docs/hardware/P10_REQUIRED_BOARD_DOCUMENTS.md",
        "docs/hardware/P10_USER_HARDWARE_CLARIFICATIONS.md",
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
