#!/usr/bin/env python3
"""Write a concise execution snapshot for the current RF_COMM plan state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CONSTRAINT = ROOT / "项目约束(目标）.txt"


ARTIFACTS = [
    ("active_bit", ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.bit"),
    ("active_ltx", ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.ltx"),
    ("active_xsa", ROOT / "TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa"),
    ("active_boot", ROOT / "software/_boot/BOOT.BIN"),
    ("shutdown_bit", ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"),
    ("constraint", CONSTRAINT),
]


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def latest(pattern: str) -> Path | None:
    paths = list(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def latest_any(*patterns: str) -> Path | None:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_json(path: Path | None) -> object:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return None


def status_counts(path: Path | None) -> dict[str, int]:
    data = load_json(path)
    counts: dict[str, int] = {}
    if not isinstance(data, list):
        return counts
    for item in data:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "UNKNOWN"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "unavailable"
    return " / ".join(f"{key} {value}" for key, value in sorted(counts.items()))


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if cell is None else str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def extract_line(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(0) if match else ""


def collect() -> dict[str, object]:
    completion = latest("reports/plan_completion_audit_current_*.md")
    completion_json = latest("reports/plan_completion_audit_current_*.json")
    item_audit = latest("reports/plan_item_audit_current_*.md")
    item_json = latest("reports/plan_item_audit_current_*.json")
    readiness = latest("reports/plan_readiness_current_*.md")
    ack_build = latest("reports/p0_ack_only_build_*.summary.txt")
    ack_safe = latest("reports/p0_ack_only_safe_*.summary.txt")
    p1_mapping = latest("reports/p1_lane_mapping_matrix_safe_*.summary.txt")
    jtag_diag = latest("reports/jtag_usb_diag_*.summary.txt")
    active_guard = latest("reports/active_artifact_guard_current_*.md")
    active_guard_json = latest("reports/active_artifact_guard_current_*.json")
    jtag_blocker = latest_any("reports/jtag_blocker_current_*.md", "reports/jtag_blocker_analysis_current_*.md")
    jtag_blocker_json = latest_any("reports/jtag_blocker_current_*.json", "reports/jtag_blocker_analysis_current_*.json")
    jtag_checklist = latest("reports/jtag_recovery_checklist_current_*.md")
    jtag_checklist_json = latest("reports/jtag_recovery_checklist_current_*.json")
    jtag_recovery = latest("reports/jtag_recovery_then_resume_*.summary.txt")

    readiness_text = read_text(readiness)
    ack_build_text = read_text(ack_build)
    ack_safe_text = read_text(ack_safe)
    completion_text = read_text(completion)
    item_text = read_text(item_audit)
    active_guard_text = read_text(active_guard)
    jtag_blocker_text = read_text(jtag_blocker)
    jtag_checklist_text = read_text(jtag_checklist)
    jtag_recovery_text = read_text(jtag_recovery)
    jtag_ready = "JTAG_BLOCKER_ANALYSIS status=JTAG_READY" in jtag_blocker_text
    p1_mapping_failed = "P1-1-HW" in completion_text and "FAIL_HARDWARE" in completion_text
    if p1_mapping_failed:
        current_stage = "P1_LANE_MAPPING_BLOCKED"
    elif jtag_ready:
        current_stage = "P1_READY_FOR_LANE_MAPPING"
    else:
        current_stage = "P1_WAITING_JTAG"

    artifact_rows = [
        [name, rel(path), sha256(path)]
        for name, path in ARTIFACTS
    ]

    ack_env_rows = []
    for line in ack_build_text.splitlines():
        if line.startswith("BUILD_ENV "):
            key_value = line[len("BUILD_ENV ") :]
            if "=" in key_value:
                key, value = key_value.split("=", 1)
                if key in {
                    "IR_B_MODE",
                    "IR_LANE_COUNT",
                    "IR_B_SESSION_ID",
                    "IR_B_RX_LANE_MASK",
                    "IR_B_EXPECTED_A_LANE_MASK",
                    "IR_B_TX_LANE_MASK",
                    "IR_B_ACK_LANE_MASK",
                    "IR_B2A_ENABLE",
                    "IR_B2A_FREE_RUN",
                    "PSPS_STAGE_LANE_MASK",
                    "PSPS_STAGE_SESSION_ID",
                    "PSPS_PAYLOAD_LANE_MASK",
                    "PSPS_RX_LANE_MASK",
                    "VIVADO_MAX_THREADS",
                    "MAKEFLAGS",
                }:
                    ack_env_rows.append([key, value])

    status_rows = [
        ["completion_counts", format_counts(status_counts(completion_json)), rel(completion_json or completion)],
        ["item_counts", format_counts(status_counts(item_json)), rel(item_json or item_audit)],
        ["readiness", extract_line(readiness_text, r"Overall: `[^`]+`"), rel(readiness)],
        ["next_blocking_gate", extract_line(readiness_text, r"Next blocking gate: `[^`]+`"), rel(readiness)],
        ["active_artifact_guard", extract_line(active_guard_text, r"ACTIVE_ARTIFACT_GUARD .+"), rel(active_guard)],
        ["jtag_blocker", extract_line(jtag_blocker_text, r"JTAG_BLOCKER_ANALYSIS .+"), rel(jtag_blocker)],
        ["jtag_recovery_checklist", extract_line(jtag_checklist_text, r"JTAG_RECOVERY_CHECKLIST .+"), rel(jtag_checklist)],
        ["jtag_recovery_chain", extract_line(jtag_recovery_text, r"RESUME_COMMAND=.+"), rel(jtag_recovery)],
        ["ack_build_recipe", "dry-run only; no ACK-only bitstream claimed", rel(ack_build)],
        ["ack_safe_latest", "blocked before programming or dry-run only", rel(ack_safe)],
    ]

    command_rows = [
        [
            "1",
            "Recover/verify JTAG, then capture physical lane matrix",
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p1_lane_mapping_matrix_safe.ps1 -StopOnFail",
        ],
        [
            "2",
            "After P1 matrix PASS, classify current RX failure",
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p0_rx_root_cause_safe.ps1 -Mode all -StopOnFail",
        ],
        [
            "3",
            "After RX PASS evidence exists, build ACK-only artifacts when ready to switch active project config",
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\build_p0_ack_only_artifacts.ps1 -Mode lane0 -RunBuild",
        ],
        [
            "4",
            "After ACK-only build and RX PASS, run ACK-only hardware verification",
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p0_ack_only_safe.ps1 -Mode lane0 -StopOnFail -RxEvidencePath <rx-pass-summary>",
        ],
    ]

    safety_rows = [
        ["project_constraint_modified", "no"],
        ["fpga_programmed_by_snapshot", "no"],
        ["tfdu_driven_by_snapshot", "no"],
        ["shutdown_needed_for_snapshot", "no"],
        ["hardware_action_by_artifact_guard", "no"],
        ["hardware_action_by_jtag_blocker_analysis", "no"],
        ["hardware_action_by_jtag_recovery_checklist", "no"],
        ["hardware_action_by_jtag_recovery_chain_dry_run", "no"],
        ["current_active_artifact_intent", "2-lane ILA baseline for P1 lane mapping, not ACK-only"],
        ["ack_only_build_risk", "RunBuild intentionally changes active Vivado project/bitstream; save/restore artifacts before switching stages"],
    ]

    return {
        "completion": completion,
        "completion_json": completion_json,
        "item_audit": item_audit,
        "item_json": item_json,
        "readiness": readiness,
        "ack_build": ack_build,
        "ack_safe": ack_safe,
        "p1_mapping": p1_mapping,
        "jtag_diag": jtag_diag,
        "active_guard": active_guard,
        "active_guard_json": active_guard_json,
        "jtag_blocker": jtag_blocker,
        "jtag_blocker_json": jtag_blocker_json,
        "jtag_checklist": jtag_checklist,
        "jtag_checklist_json": jtag_checklist_json,
        "jtag_recovery": jtag_recovery,
        "completion_text": completion_text,
        "item_text": item_text,
        "readiness_text": readiness_text,
        "ack_build_text": ack_build_text,
        "ack_safe_text": ack_safe_text,
        "active_guard_text": active_guard_text,
        "jtag_blocker_text": jtag_blocker_text,
        "jtag_checklist_text": jtag_checklist_text,
            "jtag_recovery_text": jtag_recovery_text,
        "jtag_ready": jtag_ready,
        "p1_mapping_failed": p1_mapping_failed,
        "current_stage": current_stage,
        "artifact_rows": artifact_rows,
        "status_rows": status_rows,
        "ack_env_rows": sorted(ack_env_rows),
        "command_rows": command_rows,
        "safety_rows": safety_rows,
    }


def render(snapshot: dict[str, object]) -> str:
    return "\n".join(
        [
            "# RF_COMM Active Execution Snapshot",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Current Position",
            "",
            "- The active implementation artifact is kept as the current 2-lane ILA baseline for P1 lane mapping.",
            "- ACK-only build tooling is ready, but no ACK-only bitstream is claimed until `-RunBuild` is executed and hashed artifacts are saved.",
            "- JTAG is currently ready, but P1 lane mapping is blocked by lane timeout/missing CSV."
            if snapshot["p1_mapping_failed"]
            else ("- JTAG is currently ready; the first blocking gate is the P1 physical lane mapping matrix." if snapshot["jtag_ready"] else "- The first blocking gate is still JTAG target enumeration."),
            "",
            "## Status",
            "",
            md_table(["item", "state", "evidence"], snapshot["status_rows"]),  # type: ignore[arg-type]
            "",
            "## Active Artifacts",
            "",
            md_table(["name", "path", "sha256"], snapshot["artifact_rows"]),  # type: ignore[arg-type]
            "",
            "## ACK-Only Recipe",
            "",
            md_table(["env", "value"], snapshot["ack_env_rows"]),  # type: ignore[arg-type]
            "",
            "## Next Commands",
            "",
            md_table(["order", "purpose", "command"], snapshot["command_rows"]),  # type: ignore[arg-type]
            "",
            "## Safety",
            "",
            md_table(["check", "state"], snapshot["safety_rows"]),  # type: ignore[arg-type]
            "",
            f"PLAN_EXECUTION_SNAPSHOT current_stage={snapshot['current_stage']} active_artifact=2LANE_ILA_BASELINE ack_only=DRY_RUN_RECIPE_ONLY hardware_action=NONE",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPORTS / "plan_execution_snapshot_current_20260626.md")
    parser.add_argument("--json", type=Path, default=REPORTS / "plan_execution_snapshot_current_20260626.json")
    args = parser.parse_args()

    snapshot = collect()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(snapshot), encoding="utf-8")

    json_out = args.json if args.json.is_absolute() else ROOT / args.json
    json_data = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "artifacts": [
            {"name": name, "path": path, "sha256": hash_value}
            for name, path, hash_value in snapshot["artifact_rows"]  # type: ignore[index]
        ],
        "status": snapshot["status_rows"],
        "ack_recipe": snapshot["ack_env_rows"],
        "next_commands": snapshot["command_rows"],
        "safety": snapshot["safety_rows"],
    }
    json_out.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"WROTE_MARKDOWN={out}")
    print(f"WROTE_JSON={json_out}")
    print("PLAN_EXECUTION_SNAPSHOT_WRITTEN=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
