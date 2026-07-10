#!/usr/bin/env python3
"""Verify that the legacy AB_L1 block has the required fresh P5/P6 gates."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "evidence/generated/p7_lane1_promotion_summary.json"
OUT_MD = ROOT / "evidence/generated/p7_lane1_promotion_summary.md"
PROMOTION_SOURCE_COMMIT = "ca041d4877b831de84fe7829788ac835b0b46acd"


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sources = {
        "raw": "evidence/hardware/p5/raw_lane_matrix/p5_stage_result.json",
        "frame": "evidence/hardware/p5/protocol/lane1_frame_crc_100/p5_stage_result.json",
        "ack": "evidence/hardware/p5/protocol/lane1_ack_retry_100/p5_stage_result.json",
        "p6": "evidence/hardware/p6/protocol/lane1_dynamic_payload/p6_jtag_axi_matrix_summary.json",
    }
    raw, frame, ack, p6 = (load(sources[key]) for key in ("raw", "frame", "ack", "p6"))
    raw_dirs = {item["direction"]: item for item in raw.get("direction_results", [])}
    frame_best = frame.get("parse", {}).get("best_result", {})
    ack_best = ack.get("parse", {}).get("best_result", {})
    checks = {
        "raw_stage_pass": raw.get("RAW_LANE_MATRIX_FRESH") == "PASS",
        "raw_ab_l1": raw_dirs.get("AB_L1", {}).get("status") == "PASS"
        and raw_dirs.get("AB_L1", {}).get("tx_observed_count") == 64
        and raw_dirs.get("AB_L1", {}).get("rx_active_low_pulse_count") == 64,
        "raw_ba_l1": raw_dirs.get("BA_L1", {}).get("status") == "PASS"
        and raw_dirs.get("BA_L1", {}).get("tx_observed_count") == 64
        and raw_dirs.get("BA_L1", {}).get("rx_active_low_pulse_count") == 64,
        "raw_safety": raw.get("TXD_STUCK_HIGH_VIOLATION") == 0
        and raw.get("DUTY_WINDOW_VIOLATION") == 0
        and raw.get("SHUTDOWN_ON_EXIT") == "PASS",
        "frame_crc_100": frame.get("LANE1_FRAME_CRC_100") == "PASS"
        and frame_best.get("SENT_FRAMES") == 100
        and frame_best.get("RX_GOOD") == 100
        and all(frame_best.get(key) == 0 for key in ("FRAME_BAD", "CRC_BAD", "PAYLOAD_MISMATCH", "RX_SYMBOL_ERRORS")),
        "frame_session_mask_readback": frame_best.get("SESSION_READBACK") == "0x2201"
        and frame_best.get("LANE_MASK_READBACK") == "0x2",
        "frame_safety_shutdown": frame.get("SHUTDOWN_ON_EXIT") == "PASS"
        and frame_best.get("TXD_STUCK_HIGH_VIOLATION") == 0
        and frame_best.get("DUTY_WINDOW_VIOLATION") == 0,
        "ack_100": ack.get("LANE1_ACK_RETRY_100") == "PASS"
        and ack_best.get("A_SENT_FRAMES") == 100
        and ack_best.get("B_RX_GOOD") == 100
        and ack_best.get("B_ACK_SENT") == 100
        and ack_best.get("A_ACK_SEEN") == 100,
        "ack_session_masks_readback": ack_best.get("SESSION_READBACK") == "0x2201"
        and ack_best.get("LANE_MASK_READBACK") == "0x2"
        and ack_best.get("ACK_LANE_MASK_READBACK") == "0x2",
        "ack_errors_safety_shutdown": all(ack_best.get(key) == 0 for key in (
            "B_FRAME_BAD", "CRC_BAD", "PAYLOAD_MISMATCH", "TX_RETRY_EXHAUSTED", "TX_FAIL",
            "TXD_STUCK_HIGH_VIOLATION", "DUTY_WINDOW_VIOLATION",
        )) and ack.get("SHUTDOWN_ON_EXIT") == "PASS",
        "p6_lane1_160": p6.get("P6_JTAG_AXI_HARDWARE_MATRIX") == "PASS"
        and p6.get("positive_cases") == 160
        and p6.get("lane_mask") == "0x2"
        and p6.get("ack_lane_mask") == "0x2",
        "p6_shutdown": p6.get("safe_wrapper_returncode") == 0
        and p6.get("shutdown_before") is True
        and p6.get("shutdown_after") is True,
        "p6_immutable_hash": p6.get("bitstream_sha256")
        == "0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d",
    }
    passed = all(checks.values())
    result = {
        "P7_LANE1_RELIABILITY_PROMOTION_GATE": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_commit": PROMOTION_SOURCE_COMMIT,
        "reason": "fresh raw-pulse, frame CRC, ACK-only, session/lane/ACK-mask readback and P6 lane1 physical-frame gates verified"
        if passed else "one or more mandatory lane1 promotion checks failed",
        "checks": checks,
        "sources": {key: {"path": path, "sha256": sha(ROOT / path)} for key, path in sources.items()},
        "hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": True,
        "network_used": False,
        "motion_used": False,
        "boundary": "promotion eligibility from existing matching evidence; P7 still requires fresh staged regression before acceptance",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P7 Lane1 Reliability Promotion Gate", "",
        f"P7_LANE1_RELIABILITY_PROMOTION_GATE: {result['P7_LANE1_RELIABILITY_PROMOTION_GATE']}",
        "HARDWARE_ACTIONS_EXECUTED: false", "SOURCE_EVIDENCE_CONTAINS_HARDWARE_ACTIONS: true", "",
        "## Checks", "",
    ] + [f"- {name}: {'PASS' if value else 'FAIL'}" for name, value in checks.items()] + [
        "", "## Boundary", "", f"- {result['boundary']}", "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
