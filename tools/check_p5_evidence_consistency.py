#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from p5_lib import FAIL, GENERATED, P5_DIR, PASS, PASS_WITH_NOTES, load_json, parse_markers, write_markdown


HARDWARE_PASS_MARKERS = [
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

PASSISH = {PASS, PASS_WITH_NOTES, "PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED"}


def _pending_marker_is_active(path):
    parent = path.parent
    for candidate in [
        parent / "p5_stage_result.json",
        parent / "readback.json",
        parent / "p5_payload_sweep.json",
        parent / "p5_mask_regression.json",
    ]:
        data = load_json(candidate)
        if not isinstance(data, dict):
            continue
        if data.get("NO_HARDWARE_ACTIONS_EXECUTED") is False and (
            data.get("hardware_actions_executed") is True
            or data.get("source_hardware_actions_executed") is True
            or data.get("HARDWARE_ACTIONS_EXECUTED") is True
        ):
            for marker in HARDWARE_PASS_MARKERS:
                if data.get(marker) in PASSISH:
                    return False
    return True


def check() -> dict:
    failures = []
    notes = []
    summaries = sorted(GENERATED.glob("p5_*summary.md"))
    for summary in summaries:
        markers = parse_markers(summary)
        for marker in HARDWARE_PASS_MARKERS:
            if markers.get(marker) == PASS:
                text = summary.read_text(encoding="utf-8", errors="ignore")
                if "hardware_actions_executed: true" not in text and "HARDWARE_ACTIONS_EXECUTED: true" not in text:
                    failures.append(f"{summary}: {marker} is PASS without hardware_actions_executed=true")
                if "SHUTDOWN_ON_EXIT: PASS" not in text and marker not in {"PAYLOAD_SWEEP", "MASK_REGRESSION"}:
                    failures.append(f"{summary}: {marker} is PASS without shutdown evidence")
        if markers.get("ETHERNET_ACCEPTANCE") == PASS:
            failures.append(f"{summary}: Ethernet deferred item is PASS")
        if markers.get("ROTATION_ACCEPTANCE") == PASS:
            failures.append(f"{summary}: rotation deferred item is PASS")
        if markers.get("EIGHT_LANE_ACCEPTANCE") == PASS:
            failures.append(f"{summary}: 8-lane deferred item is PASS")

    pending_hw = [path for path in sorted(P5_DIR.rglob("p5_pending_hw.json")) if _pending_marker_is_active(path)]
    if pending_hw:
        notes.append(f"fresh P5 hardware stages pending: {len(pending_hw)} placeholder records")

    result = FAIL if failures else PASS_WITH_NOTES if notes else PASS
    lines = [
        f"EVIDENCE_CONSISTENCY: {result}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Checked Summaries",
        "",
        *(f"- `{summary.as_posix()}`" for summary in summaries),
    ]
    if notes:
        lines.extend(["", "## Notes", "", *(f"- {note}" for note in notes)])
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(
        GENERATED / "p5_evidence_consistency_summary.md",
        "P5 Evidence Consistency Summary",
        result,
        "P5 evidence schema is internally consistent" if not failures else "P5 evidence consistency failures found",
        lines,
    )
    return {
        "EVIDENCE_CONSISTENCY": result,
        "failures": failures,
        "notes": notes,
        "summary": "evidence/generated/p5_evidence_consistency_summary.md",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check P5 generated and hardware evidence consistency.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = check()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"EVIDENCE_CONSISTENCY: {payload['EVIDENCE_CONSISTENCY']}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    return 0 if payload["EVIDENCE_CONSISTENCY"] in {PASS, PASS_WITH_NOTES} else 1


if __name__ == "__main__":
    raise SystemExit(main())
