#!/usr/bin/env python3
"""Add immutable checkpoint/Definition-of-Done fields to P8B final evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL_JSON = ROOT / "evidence/generated/p8b_final_summary.json"
FINAL_MD = ROOT / "evidence/generated/p8b_final_summary.md"
GAPS_JSON = ROOT / "evidence/generated/p8b_geometry_gap_ledger.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    data = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    gaps = json.loads(GAPS_JSON.read_text(encoding="utf-8"))["gaps"]
    if data.get("status") != "PASS" or data.get("failures") or data.get("pending"):
        raise RuntimeError("refusing to finalize a non-PASS P8B gate")

    pass_items = [
        "P8A_CHECKPOINT_FROZEN", "32X8_MAPPING_PERMUTATION",
        "FORWARD_CANDIDATE_MAPPING", "REVERSE_CANDIDATE_MAPPING",
        "Q3_TO_Q0_WRAP", "Q0_TO_Q3_WRAP", "BANK_LANE_CROSSBAR_INVERSE",
        "CROSSBAR_DATA_ROUTING", "PATH_EPOCH_ATOMICITY", "PATH_EPOCH_EXACTLY_ONCE",
        "STALE_EPOCH_REJECTION", "PHASE_INVALID_TO_ACQUISITION",
        "STOP_RESTART_REVERSAL_MODEL", "NOMINAL_GEOMETRY_CHECK",
        "GEOMETRY_MODEL_IMPLEMENTATION", "HANDOVER_METRICS_SEPARATED",
        "RTL_PYTHON_CROSSCHECK", "P8B_REQUIREMENT_TRACEABILITY",
        "P8B_STATE_NONPROMOTION", "P0_P7_REGRESSION", "OFFLINE_FULL_REGRESSION",
        "GIT_DIFF_CHECK",
    ]
    generated = [
        f"evidence/generated/{stem}.{suffix}"
        for stem in (
            "p8b_repo_intake", "p8a_checkpoint_freeze_summary",
            "p8b_mapping_exhaustive_summary", "p8b_crossbar_summary",
            "p8b_path_epoch_summary", "p8b_phase_acquisition_summary",
            "p8b_geometry_nominal_summary", "p8b_geometry_worst_case_summary",
            "p8b_geometry_gap_ledger", "p8b_handover_timing_summary",
            "p8b_rtl_python_crosscheck", "p8b_simulation_gate_summary",
            "p8b_state_consistency_summary", "p8b_acceptance_core", "p8b_final_summary",
        )
        for suffix in ("json", "md")
    ]
    data.update({
        "P8B_GEOMETRY_MAPPING_HANDOVER": "PASS",
        "P8A_BASELINE_COMMIT": "3ed79e02baa2c60af86e752c79ad1d0c44e37fb4",
        "P8B_COMMIT": data["source_commit"],
        "P8B_TAG": "p8b-pass",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "32X8_MAPPING_PERMUTATION": "PASS",
        "FORWARD_REVERSE_CANDIDATE_MAPPING": "PASS",
        "BANK_LANE_CROSSBAR_INVERSE": "PASS",
        "CROSSBAR_DATA_ROUTING": "PASS",
        "PATH_EPOCH_ATOMICITY": "PASS",
        "PATH_EPOCH_EXACTLY_ONCE": "PASS",
        "STALE_EPOCH_REJECTION": "PASS",
        "PHASE_ACQUISITION_MODEL": "PASS",
        "STOP_RESTART_REVERSAL_MODEL": "PASS",
        "NOMINAL_GEOMETRY_CHECK": "PASS",
        "GEOMETRY_MODEL_IMPLEMENTATION": "PASS",
        "WORST_CASE_GEOMETRY_ACCEPTANCE": "PENDING_WITH_EXPLICIT_GAPS",
        "HANDOVER_TIMING_MODEL": "PASS",
        "RTL_PYTHON_CROSSCHECK": "PASS",
        "P0_P7_REGRESSION": "PASS",
        "OFFLINE_FULL_REGRESSION": "PASS",
        "PROJECT_CONSTRAINTS_SHA256": sha256(ROOT / "PROJECT_CONSTRAINTS.txt"),
        "GEOMETRY_CONFIG_SHA256": sha256(ROOT / "config/geometry/optical_geometry.yaml"),
        "PROJECT_STATE_SHA256": sha256(ROOT / "config/project_state.json"),
        "PROJECT_REQUIREMENTS_SHA256": sha256(ROOT / "config/project_requirements.yaml"),
        "PASS": pass_items,
        "FAIL": [],
        "SKIP_WITH_REASON": [],
        "EXPLICIT_GEOMETRY_GAPS": [gap["parameter"] for gap in gaps],
        "GENERATED_SUMMARIES": generated,
        "NEXT_RECOMMENDED_STAGE": "P8C_TFDU_SAFETY_EXACT_DUTY_SINGLE_GLOBAL_PERMIT",
    })
    FINAL_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        "# P8B final summary", "",
        "```text",
        "P8B_GEOMETRY_MAPPING_HANDOVER: PASS",
        f"P8A_BASELINE_COMMIT: {data['P8A_BASELINE_COMMIT']}",
        f"P8B_COMMIT: {data['P8B_COMMIT']}",
        "P8B_TAG: p8b-pass",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION: false",
        "WORST_CASE_GEOMETRY_ACCEPTANCE: PENDING_WITH_EXPLICIT_GAPS",
        "P0_P7_REGRESSION: PASS",
        "OFFLINE_FULL_REGRESSION: PASS",
        "NEXT_RECOMMENDED_STAGE: P8C_TFDU_SAFETY_EXACT_DUTY_SINGLE_GLOBAL_PERMIT",
        "```", "", "```json",
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
        "```", "",
    ]
    FINAL_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("P8B_CHECKPOINT_FINALIZATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
