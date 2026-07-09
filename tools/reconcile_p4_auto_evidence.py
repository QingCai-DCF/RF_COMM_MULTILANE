#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from p5_lib import (
    FAIL,
    GENERATED,
    PASS,
    PASS_WITH_NOTES,
    ROOT,
    load_json,
    parse_markers,
    rel,
    status_is_passish,
    write_json,
    write_markdown,
)


P4_ITEMS = [
    {
        "name": "P4_AUTO_HARDWARE_ACCEPTANCE",
        "marker": "P4_AUTO_HARDWARE_ACCEPTANCE",
        "generated": ["evidence/generated/p4_auto_hardware_acceptance_summary.md"],
        "hardware": ["evidence/generated/p4_auto_hardware_acceptance_summary.json"],
    },
    {
        "name": "SAFE_IDLE_DIRECT_PROXY",
        "marker": "SAFE_IDLE_DIRECT_PROXY",
        "generated": ["evidence/generated/p4_auto_safe_idle_direct_proxy_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/safe_idle_direct_proxy/readback.json",
            "evidence/hardware/p4_auto/safe_idle_direct_proxy/p4_auto_safe_idle_program_result.json",
            "evidence/hardware/p4_auto/safe_idle_direct_proxy/p4_auto_safe_idle_direct_proxy_summary.md",
        ],
    },
    {
        "name": "TFDU_CONTROL_IDLE",
        "marker": "TFDU_CONTROL_IDLE",
        "generated": ["evidence/generated/p4_auto_tfdu_control_idle_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/tfdu_control_idle/p4_auto_tfdu_control_idle_program_result.json",
            "evidence/hardware/p4_auto/tfdu_control_idle/p4_auto_tfdu_control_idle_summary.md",
        ],
    },
    {
        "name": "RAW_PULSE_SMOKE_L0",
        "marker": "RAW_PULSE_SMOKE_L0",
        "generated": ["evidence/generated/p4_auto_raw_pulse_smoke_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/raw_pulse_smoke/raw_pulse_smoke.json",
            "evidence/hardware/p4_auto/raw_pulse_smoke/p4_auto_raw_pulse_smoke_program_result.json",
            "evidence/hardware/p4_auto/ila/raw_pulse_smoke/raw_pulse_parse_result.json",
        ],
    },
    {
        "name": "RAW_LANE_MATRIX",
        "marker": "RAW_LANE_MATRIX",
        "generated": ["evidence/generated/p4_auto_raw_lane_matrix_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/raw_lane_matrix/p4_auto_raw_lane_matrix_program_result.json",
            "evidence/hardware/p4_auto/ila/raw_lane_matrix/raw_lane_matrix_parse_result.json",
            "evidence/hardware/p4_auto/raw_lane_matrix/ila_or_axi_summary.md",
        ],
    },
    {
        "name": "LANE0_FRAME_CRC",
        "marker": "LANE0_FRAME_CRC",
        "generated": ["evidence/generated/p4_auto_lane0_frame_crc_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/protocol_smoke/lane0_frame_crc_readback.json",
            "evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane0_frame_crc_program_result.json",
            "evidence/hardware/p4_auto/protocol_smoke/lane0_frame_crc_summary.md",
        ],
    },
    {
        "name": "LANE0_ACK_RETRY",
        "marker": "LANE0_ACK_RETRY",
        "generated": ["evidence/generated/p4_auto_lane0_ack_retry_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/protocol_smoke/lane0_ack_retry_readback.json",
            "evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane0_ack_retry_program_result.json",
            "evidence/hardware/p4_auto/protocol_smoke/lane0_ack_retry_summary.md",
        ],
    },
    {
        "name": "LANE1_FRAME_CRC",
        "marker": "LANE1_FRAME_CRC",
        "generated": ["evidence/generated/p4_auto_lane1_frame_crc_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/protocol_smoke/lane1_frame_crc_readback.json",
            "evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane1_frame_crc_program_result.json",
            "evidence/hardware/p4_auto/protocol_smoke/lane1_frame_crc_summary.md",
        ],
    },
    {
        "name": "LANE1_ACK_RETRY",
        "marker": "LANE1_ACK_RETRY",
        "generated": ["evidence/generated/p4_auto_lane1_ack_retry_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/protocol_smoke/lane1_ack_retry_readback.json",
            "evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane1_ack_retry_program_result.json",
            "evidence/hardware/p4_auto/protocol_smoke/lane1_ack_retry_summary.md",
        ],
    },
    {
        "name": "TWO_LANE_MINIMAL",
        "marker": "TWO_LANE_MINIMAL",
        "generated": ["evidence/generated/p4_auto_two_lane_minimal_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/protocol_smoke/two_lane_minimal_readback.json",
            "evidence/hardware/p4_auto/protocol_smoke/p4_auto_two_lane_minimal_program_result.json",
            "evidence/hardware/p4_auto/protocol_smoke/two_lane_minimal_summary.md",
        ],
    },
    {
        "name": "LANE0_300S_SOAK",
        "marker": "LANE0_300S_SOAK",
        "generated": ["evidence/generated/p4_auto_lane0_300s_soak_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/soak/lane0_300s_soak_readback.json",
            "evidence/hardware/p4_auto/soak/p4_auto_lane0_300s_soak_program_result.json",
            "evidence/hardware/p4_auto/soak/lane0_300s_soak_summary.md",
        ],
    },
    {
        "name": "TWO_LANE_300S_SOAK",
        "marker": "TWO_LANE_300S_SOAK",
        "generated": ["evidence/generated/p4_auto_two_lane_300s_soak_summary.md"],
        "hardware": [
            "evidence/hardware/p4_auto/soak/two_lane_300s_soak_readback.json",
            "evidence/hardware/p4_auto/soak/p4_auto_two_lane_300s_soak_program_result.json",
            "evidence/hardware/p4_auto/soak/two_lane_300s_soak_summary.md",
        ],
    },
]


def _flatten_statuses(obj: Any, marker: str) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            normalized_key = str(key).upper()
            if normalized_key == marker and not isinstance(value, (dict, list)):
                found.append(str(value))
            found.extend(_flatten_statuses(value, marker))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_flatten_statuses(item, marker))
    return found


def _status_from_path(path: Path, marker: str) -> tuple[str, str]:
    if not path.exists():
        return "MISSING", ""
    if path.suffix.lower() == ".json":
        data = load_json(path)
        statuses = _flatten_statuses(data, marker)
        if statuses:
            return statuses[0], rel(path)
        parse_marker = f"{marker}_ILA_PARSE"
        parse_statuses = _flatten_statuses(data, parse_marker)
        if parse_statuses:
            return parse_statuses[0], rel(path)
        return "UNKNOWN", rel(path)
    markers = parse_markers(path)
    if marker in markers:
        return markers[marker], rel(path)
    result = markers.get("RESULT") or markers.get("STATUS")
    return result or "UNKNOWN", rel(path)


def _is_stale(value: str) -> bool:
    return value in {"BLOCKED_BY_AUTOMATION_GAP", "SKIP_WITH_REASON", "PENDING_HW", "UNKNOWN", "MISSING"}


def reconcile() -> dict[str, Any]:
    final_json = load_json(GENERATED / "p4_auto_hardware_acceptance_summary.json")
    rows = []
    any_notes = False
    any_fail = False

    for item in P4_ITEMS:
        marker = item["marker"]
        generated_statuses = []
        hardware_statuses = []
        for relpath in item["generated"]:
            status, source = _status_from_path(ROOT / relpath, marker)
            generated_statuses.append({"path": relpath, "status": status, "source": source})
        for relpath in item["hardware"]:
            status, source = _status_from_path(ROOT / relpath, marker)
            hardware_statuses.append({"path": relpath, "status": status, "source": source})

        final_status = str(final_json.get(marker, "MISSING")) if isinstance(final_json, dict) else "MISSING"
        generated_pass = any(status_is_passish(entry["status"]) for entry in generated_statuses)
        generated_stale = any(_is_stale(entry["status"]) for entry in generated_statuses)
        hardware_pass = any(status_is_passish(entry["status"]) for entry in hardware_statuses)
        hardware_fail = any(entry["status"] == FAIL for entry in hardware_statuses)

        if generated_pass and not hardware_fail:
            normalized = "PASS_WITH_DIRECT_SUMMARY"
        elif generated_stale and hardware_pass:
            normalized = "PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY"
            any_notes = True
        elif hardware_pass:
            normalized = "PASS_WITH_HARDWARE_SUBDIR_EVIDENCE"
            any_notes = True
        elif final_status == PASS and generated_stale and not hardware_pass:
            normalized = "CONFLICTING_SUMMARY"
            any_fail = True
        elif generated_stale:
            normalized = "BLOCKED_OR_STALE_SUMMARY"
            any_fail = True
        elif all(entry["status"] == "MISSING" for entry in generated_statuses + hardware_statuses):
            normalized = "MISSING_EVIDENCE"
            any_fail = True
        else:
            normalized = "CONFLICTING_SUMMARY"
            any_fail = True

        rows.append(
            {
                "item": item["name"],
                "marker": marker,
                "final_json_status": final_status,
                "generated_statuses": generated_statuses,
                "hardware_statuses": hardware_statuses,
                "normalized_status": normalized,
            }
        )

    result = FAIL if any_fail else PASS_WITH_NOTES if any_notes else PASS
    payload = {
        "P4_EVIDENCE_RECONCILIATION": result,
        "P4_FINAL_JSON": rel(GENERATED / "p4_auto_hardware_acceptance_summary.json"),
        "P4_RESULT_PACKAGE": "p4_auto_acceptance_results_20260709_181930.zip",
        "rows": rows,
        "note": "P4 had stale/generated summary inconsistencies; P5 uses normalized evidence and fresh P5 reruns.",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    write_json(GENERATED / "p5_p4_evidence_reconciliation.json", payload)

    lines = [
        f"P4_EVIDENCE_RECONCILIATION: {result}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "P4 had stale/generated summary inconsistencies; P5 uses normalized evidence and fresh P5 reruns.",
        "",
        "| Item | Final JSON | Generated | Hardware evidence | Normalized status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        generated_text = "<br>".join(f"{entry['status']} `{entry['path']}`" for entry in row["generated_statuses"])
        hardware_text = "<br>".join(f"{entry['status']} `{entry['path']}`" for entry in row["hardware_statuses"])
        lines.append(
            f"| {row['item']} | {row['final_json_status']} | {generated_text} | {hardware_text} | {row['normalized_status']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This reconciliation is historical P4 intake only.",
            "- It does not promote P5 hardware stages to PASS.",
            "- Fresh P5 hardware stages remain pending until an explicitly authorized P5 run creates P5 evidence.",
        ]
    )
    write_markdown(
        GENERATED / "p5_p4_evidence_reconciliation.md",
        "P5 P4 Evidence Reconciliation",
        result,
        "P4 normalized evidence table generated" if result != FAIL else "P4 evidence reconciliation found conflicts",
        lines,
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize P4_AUTO evidence for P5 intake without touching hardware.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = reconcile()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P4_EVIDENCE_RECONCILIATION: {payload['P4_EVIDENCE_RECONCILIATION']}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
    return 0 if payload["P4_EVIDENCE_RECONCILIATION"] in {PASS, PASS_WITH_NOTES} else 1


if __name__ == "__main__":
    raise SystemExit(main())
