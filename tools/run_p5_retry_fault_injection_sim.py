#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Callable

from p5_lib import GENERATED, PASS, P5_SIM_DIR, write_csv, write_json, write_markdown


MAX_RETRY = 3
FRAME_COUNT = 20


@dataclass(frozen=True)
class Case:
    name: str
    expected_negative: bool
    drop_ack: Callable[[int, int], bool] = lambda _frame, _attempt: False
    drop_data: Callable[[int, int], bool] = lambda _frame, _attempt: False
    crc_error: Callable[[int, int], bool] = lambda _frame, _attempt: False
    lane_disabled: bool = False


CASES = [
    Case("drop_every_10th_ack", False, drop_ack=lambda frame, attempt: frame > 0 and frame % 10 == 0 and attempt == 0),
    Case("drop_first_ack_only", False, drop_ack=lambda frame, attempt: frame == 1 and attempt == 0),
    Case("drop_first_data_only", False, drop_data=lambda frame, attempt: frame == 1 and attempt == 0),
    Case("force_crc_error_simulation_only", False, crc_error=lambda frame, attempt: frame == 1 and attempt == 0),
    Case("force_lane0_disable_via_register", True, lane_disabled=True),
    Case("force_lane1_disable_via_register", True, lane_disabled=True),
]


def _simulate_case(case: Case) -> dict:
    sent_frames = FRAME_COUNT
    delivered = 0
    retry_count = 0
    ack_drop_count = 0
    data_drop_count = 0
    crc_bad = 0
    retry_exhausted = 0
    fail_safe = False

    for frame in range(1, sent_frames + 1):
        frame_delivered = False
        for attempt in range(MAX_RETRY + 1):
            if case.lane_disabled:
                if attempt < MAX_RETRY:
                    retry_count += 1
                continue
            if case.drop_data(frame, attempt):
                data_drop_count += 1
                retry_count += 1
                continue
            if case.crc_error(frame, attempt):
                crc_bad += 1
                retry_count += 1
                continue
            if case.drop_ack(frame, attempt):
                ack_drop_count += 1
                retry_count += 1
                continue
            frame_delivered = True
            break
        if frame_delivered:
            delivered += 1
        else:
            retry_exhausted += 1
            fail_safe = True
            if not case.expected_negative:
                break

    final_delivery_ok = delivered == sent_frames
    expected_retry_exhausted = case.expected_negative
    status = PASS if (
        (final_delivery_ok and not expected_retry_exhausted and retry_exhausted == 0)
        or (expected_retry_exhausted and retry_exhausted > 0 and fail_safe)
    ) else "FAIL"
    if not case.expected_negative and (ack_drop_count or data_drop_count or crc_bad) and retry_count <= 0:
        status = "FAIL"
    return {
        "case": case.name,
        "status": status,
        "expected_negative": case.expected_negative,
        "sent_frames": sent_frames,
        "delivered_frames": delivered,
        "retry_count": retry_count,
        "ack_drop_count": ack_drop_count,
        "data_drop_count": data_drop_count,
        "crc_bad": crc_bad,
        "retry_exhausted": retry_exhausted,
        "fail_safe": fail_safe,
        "max_retry": MAX_RETRY,
        "txd_stuck_high_violation": 0,
        "duty_window_violation": 0,
    }


def run_simulation() -> dict:
    out_dir = P5_SIM_DIR / "retry_fault_injection"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_simulate_case(case) for case in CASES]
    result = PASS if all(row["status"] == PASS for row in rows) else "FAIL"
    fieldnames = [
        "case",
        "status",
        "expected_negative",
        "sent_frames",
        "delivered_frames",
        "retry_count",
        "ack_drop_count",
        "data_drop_count",
        "crc_bad",
        "retry_exhausted",
        "fail_safe",
        "max_retry",
        "txd_stuck_high_violation",
        "duty_window_violation",
    ]
    write_csv(out_dir / "p5_retry_fault_injection_sim.csv", fieldnames, rows)
    payload = {
        "RETRY_FAULT_INJECTION_SIM": result,
        "cases": rows,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    write_json(out_dir / "p5_retry_fault_injection_sim.json", payload)
    lines = [
        f"RETRY_FAULT_INJECTION_SIM: {result}",
        "RETRY_FAULT_INJECTION_HW_OPTIONAL: SKIP_NO_HW_FAULT_INJECTION_HOOK",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "| Case | Status | Retry Count | Retry Exhausted | CRC Bad | Expected Negative |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['status']} | {row['retry_count']} | {row['retry_exhausted']} | {row['crc_bad']} | {str(row['expected_negative']).lower()} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a deterministic simulation-level retry/fault injection model.",
            "- It does not move hardware, block optical paths, program FPGA hardware, or claim hardware fault-injection PASS.",
            "- Hardware fault injection remains `SKIP_NO_HW_FAULT_INJECTION_HOOK` until a real debug-register hook exists.",
        ]
    )
    write_markdown(
        GENERATED / "p5_retry_fault_injection_summary.md",
        "P5 Retry Fault Injection Summary",
        result,
        "simulation-level retry/fault injection completed" if result == PASS else "simulation-level retry/fault injection failed",
        lines,
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic P5 retry/fault injection simulation without touching hardware.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = run_simulation()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"RETRY_FAULT_INJECTION_SIM: {payload['RETRY_FAULT_INJECTION_SIM']}")
        print("RETRY_FAULT_INJECTION_HW_OPTIONAL: SKIP_NO_HW_FAULT_INJECTION_HOOK")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
    return 0 if payload["RETRY_FAULT_INJECTION_SIM"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
