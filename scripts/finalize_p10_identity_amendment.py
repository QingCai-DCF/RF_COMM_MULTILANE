#!/usr/bin/env python3
"""Reconcile the read-only P10 JTAG inventory into the current summary."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "evidence/generated/p10_jtag_identity_latest.json"
FINAL_JSON = ROOT / "evidence/generated/p10_fasttrack_final_summary.json"
FINAL_MD = ROOT / "evidence/generated/p10_fasttrack_final_summary.md"
AMENDMENT_JSON = ROOT / "evidence/generated/p10_fasttrack_identity_amendment.json"
AMENDMENT_MD = ROOT / "evidence/generated/p10_fasttrack_identity_amendment.md"
IDENTITY_CONFIG = ROOT / "config/hardware/p10_jtag_identity_inventory.json"
REASSESSMENT = ROOT / "evidence/generated/p10_hardware_admission_reassessment.json"

POWER_STATE_FINDING_ID = "P10-SAFETY-POWERUP-001"
ROLE_BINDING_BLOCKER_ID = "P10-ROLE-BINDING-001"
POWER_STATE_SCOPE_STATUS = "PENDING_D17_NONBLOCKING_FOR_P10_SCOPED_NO_POWER_CYCLE_RUN"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE=1 is required for summary reconciliation")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION=false is required for summary reconciliation")
    for path in (LATEST, FINAL_JSON, REASSESSMENT):
        if not path.is_file():
            errors.append(f"missing input: {path}")
    if errors:
        for error in errors:
            print(f"P10_IDENTITY_AMENDMENT_ERROR: {error}", file=sys.stderr)
        return 2

    identity = load(LATEST)
    summary = load(FINAL_JSON)
    if identity.get("test_id") != "P10-JTAG-IDENTITY-READONLY":
        errors.append("unexpected JTAG identity test id")
    if identity.get("status") != "PASS_ENUMERATED_UNASSIGNED":
        errors.append(f"JTAG inventory is not complete: {identity.get('status')}")
    if identity.get("programming_executed") is not False:
        errors.append("identity evidence reports programming")
    if identity.get("tfdu_drive_executed") is not False:
        errors.append("identity evidence reports TFDU drive")
    serials = identity.get("distinct_cable_serials", [])
    if not isinstance(serials, list) or len(serials) != 2 or len(set(serials)) != 2:
        errors.append("identity evidence does not contain exactly two distinct serials")
    if errors:
        for error in errors:
            print(f"P10_IDENTITY_AMENDMENT_ERROR: {error}", file=sys.stderr)
        return 1

    current_inventory = load(IDENTITY_CONFIG) if IDENTITY_CONFIG.is_file() else {}
    current_status = str(current_inventory.get("status", ""))
    fixed_serial = str(current_inventory.get("fixed_board_serial", ""))
    rotating_serial = str(current_inventory.get("rotating_board_serial", ""))
    roles_bound = (
        current_status.startswith("BOUND")
        and fixed_serial in serials
        and rotating_serial in serials
        and fixed_serial != rotating_serial
        and current_inventory.get("target_order_used_for_role_binding") is False
    )
    if current_status.startswith("BOUND") and not roles_bound:
        print("P10_IDENTITY_AMENDMENT_ERROR: invalid bound role inventory", file=sys.stderr)
        return 1
    role_binding_status = (
        f"BOUND_EXPLICIT_SERIAL_TO_ROLE: AX7020-F={fixed_serial}, AX7020-R={rotating_serial}"
        if roles_bound
        else "ENUMERATED_UNASSIGNED"
    )
    blocking_condition = None if roles_bound else ROLE_BINDING_BLOCKER_ID

    generated_at = datetime.now(timezone.utc).isoformat()
    action = {
        "test_id": identity["test_id"],
        "status": identity["status"],
        "run_id": identity["run_id"],
        "source_commit": identity["source_commit"],
        "summary_path": str(Path(identity.get("raw_result", "")).parent / "summary.json").replace("\\", "/"),
        "latest_summary": "evidence/generated/p10_jtag_identity_latest.json",
        "latest_summary_sha256": sha256(LATEST),
        "observed_cable_serials": serials,
        "role_binding_status": role_binding_status,
        "read_only": True,
        "programming_executed": False,
        "reset_executed": False,
        "memory_access_executed": False,
        "elf_executed": False,
        "uart_write_executed": False,
        "tfdu_drive_executed": False,
        "shutdown_required": False,
    }
    amendment = {
        "schema_version": 1,
        "test_id": "P10-FASTTRACK-IDENTITY-AMENDMENT",
        "status": "READY_FOR_SCOPED_P10_HARDWARE" if roles_bound else "PARTIAL_ROLE_ASSIGNMENT_REQUIRED",
        "generated_at_utc": generated_at,
        "user_clarification": {
            "tfdu_module_identity_reconfirmation_required_for_p10": False,
            "tfdu_modules_previously_operational_on_ax7010": True,
            "ax7020_role_binding_method": "JTAG_CABLE_SERIAL",
        },
        "hardware_action": action,
        "blocking_condition_for_programming": blocking_condition,
        "power_state_scope": POWER_STATE_SCOPE_STATUS,
        "hardware_admission_reassessment": {
            "path": "evidence/generated/p10_hardware_admission_reassessment.json",
            "sha256": sha256(REASSESSMENT),
        },
        "next_required_user_action": (
            None
            if roles_bound
            else f"State which of serial {serials[0]} and serial {serials[1]} is AX7020-F; the other will be AX7020-R."
        ),
    }
    write_json(AMENDMENT_JSON, amendment)
    if not roles_bound:
        write_json(IDENTITY_CONFIG, {
            "schema_version": 1,
            "inventory_id": "P10_DUAL_AX7020_JTAG_IDENTITY",
            "status": "ENUMERATED_UNASSIGNED",
            "role_binding_method": "JTAG_CABLE_SERIAL",
            "observed_cable_serials": serials,
            "fixed_board_serial": "PENDING_EXPLICIT_SERIAL_TO_ROLE_BINDING",
            "rotating_board_serial": "PENDING_EXPLICIT_SERIAL_TO_ROLE_BINDING",
            "target_order_used_for_role_binding": False,
            "evidence": "evidence/generated/p10_jtag_identity_latest.json",
            "evidence_sha256": sha256(LATEST),
        })
    AMENDMENT_MD.write_text(
        "# P10 fast-track identity amendment\n\n"
        "- TFDU module identity reinspection: `NOT_REQUIRED_PER_USER`.\n"
        f"- Read-only JTAG run: `{identity['run_id']}`.\n"
        f"- Distinct AX7020 cable serials: `{serials[0]}`, `{serials[1]}`.\n"
        f"- Serial-to-role assignment: `{role_binding_status}`; target order is prohibited.\n"
        "- Programming/reset/memory/ELF/UART/TFDU drive: `false`.\n"
        "- Shutdown: `NOT_REQUIRED_READ_ONLY_ENUMERATION`.\n"
        f"- `{POWER_STATE_FINDING_ID}`: `{POWER_STATE_SCOPE_STATUS}`; D17 remains pending.\n"
        f"- Active-hardware admission: `{'READY_FOR_SCOPED_P10_HARDWARE' if roles_bound else 'FAIL_CLOSED_PENDING_ROLE_BINDING'}` (`{blocking_condition or 'NONE'}`).\n",
        encoding="utf-8",
    )

    summary["generated_at_utc"] = generated_at
    summary["evidence_checkpoint"] = "COMMIT_CONTAINING_THIS_SUMMARY"
    summary["hardware_actions_executed"] = True
    summary["hardware_action_scope"] = "READ_ONLY_JTAG_CABLE_SERIAL_ENUMERATION_ONLY"
    summary["programming_executed"] = False
    summary["tfdu_drive_executed"] = False
    summary["jtag_identity"] = action
    summary["fixed_board_id"] = f"AX7020-F/JTAG:{fixed_serial}" if roles_bound else "PENDING_EXPLICIT_JTAG_SERIAL_ROLE_ASSIGNMENT"
    summary["rotating_board_id"] = f"AX7020-R/JTAG:{rotating_serial}" if roles_bound else "PENDING_EXPLICIT_JTAG_SERIAL_ROLE_ASSIGNMENT"
    summary["user_clarification"] = amendment["user_clarification"]
    summary["hardware_admission"] = roles_bound
    summary["blocking_condition"] = blocking_condition
    summary["power_state_scope"] = POWER_STATE_SCOPE_STATUS
    summary["hardware_admission_reassessment"] = amendment["hardware_admission_reassessment"]
    summary["fail"] = []
    if not roles_bound:
        summary["fail"].append(
            f"{ROLE_BINDING_BLOCKER_ID}: two JTAG serials were enumerated ({serials[0]}, {serials[1]}) but are not explicitly assigned to F/R roles"
        )
    summary["fail"].append("All mandatory active-hardware acceptance stages are not run")
    summary["nonblocking_findings"] = [
        f"{POWER_STATE_FINDING_ID}: {POWER_STATE_SCOPE_STATUS}; FPGA-unconfigured/partial-power fail-low remains PENDING_D17 and is not claimed by P10",
        "P10-RX-B-R29-001: formal VOH guarantee gap retained; user-confirmed prior operation on the byte-identical AX7010 base/J10 circuit provides empirical compatibility context",
    ]
    summary["required_user_resolution"] = (
        [f"State which of {serials[0]} and {serials[1]} is AX7020-F; the other will be bound as AX7020-R."]
        if not roles_bound
        else []
    )
    mandatory_results = summary.get("mandatory_results", {})
    for key, value in list(mandatory_results.items()):
        if isinstance(value, str):
            mandatory_results[key] = value.replace("SEVERE_BLOCKER", "ROLE_BINDING_REQUIRED")
    summary["mandatory_results"] = mandatory_results
    summary["nonblocking_extensions"] = (
        "NOT_RUN_BECAUSE_MANDATORY_ROLE_BINDING_PENDING"
        if not roles_bound
        else "READY_AFTER_SCOPED_HARDWARE_PREFLIGHT"
    )
    summary["next_recommended_stage"] = (
        "P10_EXPLICIT_JTAG_ROLE_BINDING"
        if not roles_bound
        else "P10_SCOPED_HARDWARE_RUN"
    )
    generated = list(summary.get("generated_evidence", []))
    generated.extend([
        "evidence/generated/p10_jtag_identity_latest.json",
        "evidence/generated/p10_jtag_identity_latest.md",
        "evidence/generated/p10_fasttrack_identity_amendment.json",
        "evidence/generated/p10_fasttrack_identity_amendment.md",
        "evidence/generated/p10_hardware_admission_reassessment.json",
        "evidence/generated/p10_hardware_admission_reassessment.md",
    ])
    summary["generated_evidence"] = unique(generated)
    write_json(FINAL_JSON, summary)

    mandatory = summary["mandatory_results"]
    FINAL_MD.write_text(
        "# P10 fast-track final summary\n\n"
        "```text\n"
        "P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET:\nPARTIAL\n\n"
        f"P10_SOURCE_COMMIT:\n{summary['source_commit']}\n\n"
        "P10_EVIDENCE_CHECKPOINT:\nCOMMIT_CONTAINING_THIS_SUMMARY\n\n"
        "P10_TAG:\nNONE\n\nWORKTREE_CLEAN:\nEXPECTED_AFTER_EVIDENCE_COMMIT\n\n"
        "WIRING_ALREADY_CONFIRMED: true\nCURRENT_RUN_HARDWARE_AUTHORIZATION: true\n"
        "HARDWARE_ACTIONS_EXECUTED: true\n"
        "HARDWARE_ACTION_SCOPE: READ_ONLY_JTAG_CABLE_SERIAL_ENUMERATION_ONLY\n"
        "PROGRAMMING_EXECUTED: false\nTFDU_DRIVE_EXECUTED: false\n"
        "NETWORK_USED: false\nNO_HARDWARE_MOVEMENT: true\nMAX_LANE_MASK_USED: NONE_NO_ACTIVE_HARDWARE_RUN\n\n"
        f"ENUMERATED_JTAG_SERIALS:\n{serials[0]}, {serials[1]}\n\n"
        f"FIXED_BOARD_ID:\n{summary['fixed_board_id']}\n\n"
        f"ROTATING_BOARD_ID:\n{summary['rotating_board_id']}\n\n"
        f"FOUR_DIRECTION_RAW:\n{mandatory['four_direction_raw']}\n"
        f"LANE0_4MBPS:\n{mandatory['lane0_4mbps']}\n"
        f"LANE1_4MBPS:\n{mandatory['lane1_4mbps']}\n"
        f"TWO_LANE_8MBPS_RAW:\n{mandatory['two_lane_8mbps_raw']}\n\n"
        f"SELECTIVE_REPEAT_SACK:\n{mandatory['selective_repeat_sack']}\n"
        f"DMA_DDR_CACHE_FIXED:\n{mandatory['dma_ddr_cache_fixed']}\n"
        f"DMA_DDR_CACHE_ROTATING:\n{mandatory['dma_ddr_cache_rotating']}\n"
        f"DUAL_INDEPENDENT_PS:\n{mandatory['dual_independent_ps']}\n"
        f"NO_SHARED_RAM:\n{mandatory['no_shared_ram']}\n"
        f"F_TO_R_OBJECT:\n{mandatory['f_to_r_object']}\n"
        f"R_TO_F_OBJECT:\n{mandatory['r_to_f_object']}\n"
        f"OBJECT_SHA256:\n{mandatory['object_sha256']}\n"
        f"ENDPOINT_REBOOT_RECOVERY:\n{mandatory['endpoint_reboot_recovery']}\n"
        f"STATIONARY_30MIN:\n{mandatory['stationary_30min']}\n\n"
        f"APPLICATION_GOODPUT_F_TO_R_BPS:\n{mandatory['application_goodput_f_to_r_bps']}\n"
        f"APPLICATION_GOODPUT_R_TO_F_BPS:\n{mandatory['application_goodput_r_to_f_bps']}\n\n"
        f"SHUTDOWN_FIXED:\n{mandatory['shutdown_fixed']}\n"
        f"SHUTDOWN_ROTATING:\n{mandatory['shutdown_rotating']}\n\n"
        "PASS:\nOFFLINE_BUILD_SIMULATION_ARCHITECTURE_AND_READ_ONLY_IDENTITY_ENUMERATION\n"
        f"FAIL:\n{('P10-ROLE-BINDING-001; ' if not roles_bound else '')}MANDATORY_ACTIVE_HARDWARE_NOT_RUN\n"
        f"NONBLOCKING_EXTENSIONS:\n{summary['nonblocking_extensions']}\n"
        "GENERATED_EVIDENCE:\nevidence/generated/p10_fasttrack_final_summary.json\n"
        "UNCHANGED_PENDING_SCOPES:\nETHERNET; SPI; PHYSICAL_GLOBAL_PERMIT; EXTERNAL_TFDU_DUTY; HANDOVER; 8X32; 600RPM; PRODUCT_FINAL\n\n"
        f"NEXT_RECOMMENDED_STAGE:\n{summary['next_recommended_stage']}\n"
        "```\n\n"
        f"The four TFDU modules are accepted without renewed identity inspection. Two AX7020 JTAG cable serials were enumerated read-only; role state is `{role_binding_status}`. Configured reset/fault and shutdown builds drive Txd low and SD high. The ordinary configuration interval is optically inhibited by SD high; FPGA-unconfigured/partial-power fail-low remains `PENDING_D17` and is not claimed by P10. No FPGA programming, reset, memory access, ELF execution, UART write, TFDU drive, Ethernet use, movement, or optical test occurred. Current active-hardware blocker: `{blocking_condition or 'NONE'}`.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": amendment["status"], "serials": serials}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
