#!/usr/bin/env python3
"""Generate deterministic, empty P10.3 evidence schemas (no hardware)."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = (
    "authorization", "wiring", "module_inventory", "board_identity",
    "artifact_manifest", "safe_boot", "power_baseline", "raw_8x8_matrix",
    "per_lane_phy", "four_lane_raw", "protocol_scheduler", "degraded_masks",
    "streaming", "performance", "stationary_30min", "shutdown", "final",
)


def main() -> int:
    root = ROOT / "evidence/templates/p10_3_4lane"
    root.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        payload = {
            "schema_version": 1,
            "campaign": "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE",
            "category": category,
            "status": "PENDING_NOT_EXECUTED",
            "run_id": None,
            "source_commit": None,
            "goal_sha256": None,
            "wiring_sha256": None,
            "artifact_sha256": {},
            "board_identities": {
                "fixed": "AX7020-F/JTAG:210249855178",
                "rotating": "AX7020-R/JTAG:210512180081",
            },
            "lane_count": 4,
            "lane_mask": None,
            "lanes": {f"lane{lane}": None for lane in range(4)},
            "modules": {module: None for module in
                        ("F0", "F1", "F2", "F3", "R0", "R1", "R2", "R3")},
            "shutdown_before": None,
            "shutdown_after": None,
            "hardware_actions_executed": False,
        }
        path = root / f"{category}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    matrix_root = ROOT / "evidence/templates/p10_3_crosstalk_8x8"
    matrix_root.mkdir(parents=True, exist_ok=True)
    matrix = {
        "schema_version": 1, "status": "PENDING_NOT_EXECUTED",
        "tx_sources": [f"{side}{lane}" for side in "FR" for lane in range(4)],
        "rx_observations": [f"{side}{lane}" for side in "FR" for lane in range(4)],
        "cells": [], "non_target_accepted_crc_valid_frames": None,
        "shutdown_before": None, "shutdown_after": None,
    }
    (matrix_root / "matrix.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    print("P10_3_EVIDENCE_TEMPLATES=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
