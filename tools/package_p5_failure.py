#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_p5_plan_requirements import audit as audit_plan_requirements
from check_p5_evidence_consistency import check as check_consistency
from p5_hw_execution import P5_STAGE_RUNS
from p5_lib import (
    FAIL,
    GENERATED,
    P5_DIR,
    PASS,
    PENDING_HW_NOT_EXECUTED,
    ROOT,
    load_json,
    rel,
    write_json,
    write_text,
)
from run_p5_2lane_protocol_stabilization import update_status_docs, write_final_summary


BLOCKING_MARKERS = [
    "SAFE_IDLE_RECHECK",
    "TFDU_CONTROL_IDLE_RECHECK",
    "RAW_LANE_MATRIX_FRESH",
    "LANE0_FRAME_CRC_100",
    "LANE1_FRAME_CRC_100",
    "LANE0_ACK_RETRY_100",
    "LANE1_ACK_RETRY_100",
    "TWO_LANE_MINIMAL_100",
    "PAYLOAD_SWEEP",
    "MASK_REGRESSION",
    "TWO_LANE_30MIN_SOAK",
]


def _stage_result(stage: str) -> dict[str, Any]:
    cfg = P5_STAGE_RUNS[stage]
    return load_json(ROOT / cfg["evidence_dir"] / "p5_stage_result.json")


def _write_hardware_execution_summary(status_by_marker: dict[str, str], shutdown_status: str, failures: list[str], attempted: list[str]) -> dict[str, Any]:
    payload = {
        "P5_HARDWARE_EXECUTION": FAIL if failures else PASS,
        "HARDWARE_ACTIONS_EXECUTED": bool(attempted),
        "NO_HARDWARE_ACTIONS_EXECUTED": not bool(attempted),
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "SHUTDOWN_ON_EXIT": shutdown_status,
        "STOP_CONDITIONS_TRIGGERED": "hardware_stage_failure:" + ",".join(failures) if failures else "none",
        "executed_stages": attempted,
        "failures": failures,
        "shutdown_failures": [] if shutdown_status == PASS else attempted,
        **status_by_marker,
    }
    write_json(P5_DIR / "p5_hardware_execution_summary.json", payload)
    lines = [
        "# P5 Hardware Execution Summary",
        "",
        "P5_HARDWARE_EXECUTION: " + payload["P5_HARDWARE_EXECUTION"],
        f"HARDWARE_ACTIONS_EXECUTED: {str(payload['HARDWARE_ACTIONS_EXECUTED']).lower()}",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(payload['NO_HARDWARE_ACTIONS_EXECUTED']).lower()}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"SHUTDOWN_ON_EXIT: {shutdown_status}",
        f"STOP_CONDITIONS_TRIGGERED: {payload['STOP_CONDITIONS_TRIGGERED']}",
        "",
        "## Stages",
        "",
    ]
    for marker, status in status_by_marker.items():
        lines.append(f"- `{marker}` -> {status}")
    write_text(GENERATED / "p5_hardware_execution_summary.md", "\n".join(lines))
    return payload


def package_failure() -> dict[str, Any]:
    status_by_marker: dict[str, str] = {}
    attempted: list[str] = []
    failures: list[str] = []
    shutdown_failures: list[str] = []
    for stage, cfg in P5_STAGE_RUNS.items():
        result = _stage_result(stage)
        marker = cfg["marker"]
        if not result:
            continue
        attempted.append(stage)
        status = result.get(marker, "UNKNOWN")
        status_by_marker[marker] = status
        if status == FAIL:
            failures.append(marker)
        if result.get("SHUTDOWN_ON_EXIT") != PASS:
            shutdown_failures.append(marker)

    for marker in BLOCKING_MARKERS:
        status_by_marker.setdefault(marker, PENDING_HW_NOT_EXECUTED)

    shutdown_status = FAIL if shutdown_failures else PASS if attempted else "SKIP_NO_HARDWARE_ACTIONS"
    hw_summary = _write_hardware_execution_summary(status_by_marker, shutdown_status, failures, attempted)

    raw = _stage_result("raw_lane_matrix_fresh")
    directions = raw.get("direction_results", []) if isinstance(raw, dict) else []
    failing_directions = [item for item in directions if item.get("status") != PASS]
    failure_dir = P5_DIR / "failures"
    failure_dir.mkdir(parents=True, exist_ok=True)
    package = {
        "P5_FAILURE_PACKAGE": "GENERATED",
        "failure_stage": "RAW_LANE_MATRIX_FRESH" if raw else "UNKNOWN",
        "failure_class": "RAW_LANE_MATRIX_DIRECTION_FAILURE" if failing_directions else "UNKNOWN",
        "failing_directions": failing_directions,
        "source_summary": "evidence/generated/p5_raw_lane_matrix_summary.md",
        "source_json": "evidence/hardware/p5/raw_lane_matrix/p5_stage_result.json",
        "shutdown_on_exit": shutdown_status,
        "stop_condition": hw_summary["STOP_CONDITIONS_TRIGGERED"],
        "boundary": "P5 hardware progression stopped before protocol expansion; no Ethernet, rotation, lane_mask > 0x3, 8-lane, or product-final claim.",
    }
    write_json(failure_dir / "raw_lane_matrix_fresh_failure_package.json", package)
    failure_lines = [
        "# P5 Raw Lane Matrix Failure Package",
        "",
        "P5_FAILURE_PACKAGE: GENERATED",
        "FAILURE_STAGE: RAW_LANE_MATRIX_FRESH",
        "FAILURE_CLASS: RAW_LANE_MATRIX_DIRECTION_FAILURE",
        f"SHUTDOWN_ON_EXIT: {shutdown_status}",
        f"STOP_CONDITIONS_TRIGGERED: {package['stop_condition']}",
        "HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Failing Directions",
        "",
    ]
    if failing_directions:
        for item in failing_directions:
            failure_lines.append(
                f"- {item.get('direction')}: status={item.get('status')} "
                f"tx_observed={item.get('tx_observed_count')} expected={item.get('tx_requested_count')} "
                f"rx_active_low_pulse_count={item.get('rx_active_low_pulse_count')}"
            )
    else:
        failure_lines.append("- none parsed")
    failure_lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Hardware progression is stopped before frame/CRC, ACK/retry, payload sweep, mask regression, and soak expansion.",
            "- Shutdown was attempted after the failed stage and must be PASS to consider this failure package complete.",
        ]
    )
    write_text(failure_dir / "raw_lane_matrix_fresh_failure_package.md", "\n".join(failure_lines))
    write_text(GENERATED / "p5_failure_package_summary.md", "\n".join(failure_lines))

    payload = load_json(GENERATED / "p5_2lane_protocol_stabilization_summary.json")
    if not isinstance(payload, dict):
        payload = {}
    payload.update(status_by_marker)
    payload.update(hw_summary)
    payload.update(
        {
            "P5_FAILURE_PACKAGE": rel(failure_dir / "raw_lane_matrix_fresh_failure_package.md"),
            "SHUTDOWN_ON_EXIT": shutdown_status,
            "STOP_CONDITIONS_TRIGGERED": hw_summary["STOP_CONDITIONS_TRIGGERED"],
            "HARDWARE_ACTIONS_EXECUTED": bool(attempted),
            "NO_HARDWARE_ACTIONS_EXECUTED": not bool(attempted),
        }
    )
    final_payload = write_final_summary(payload)
    update_status_docs(final_payload["P5_2LANE_PROTOCOL_STABILIZATION"])
    final_payload = write_final_summary(final_payload)
    consistency = check_consistency()
    final_payload.update(consistency)
    plan = audit_plan_requirements()
    final_payload.update(plan)
    final_payload = write_final_summary(final_payload)
    update_status_docs(final_payload["P5_2LANE_PROTOCOL_STABILIZATION"])
    final_payload = write_final_summary(final_payload)
    return {**package, "P5_2LANE_PROTOCOL_STABILIZATION": final_payload["P5_2LANE_PROTOCOL_STABILIZATION"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package current P5 hardware failure evidence without touching hardware.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = package_failure()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P5_FAILURE_PACKAGE: {payload['P5_FAILURE_PACKAGE']}")
        print(f"P5_2LANE_PROTOCOL_STABILIZATION: {payload['P5_2LANE_PROTOCOL_STABILIZATION']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
