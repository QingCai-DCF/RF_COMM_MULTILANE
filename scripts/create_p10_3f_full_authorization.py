#!/usr/bin/env python3
"""Create one immutable, exact P10.3F full-campaign authorization record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "evidence/generated/p10_3f_full_campaign_freeze.json"
OUTPUT = ROOT / "config/p10_3f_full_current_run_hardware_authorization.json"
SCOPE = (
    "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_"
    "WITH_FIRST_FAULT_FORENSICS"
)
AUTHORIZATION_ID = "P10_3F-FULL-CURRENT-RUN-IMMUTABLE"
GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
FIXED_SERIAL = "210249855178"
ROTATING_SERIAL = "210512180081"
MODULE_BINDING = {
    "F0": "A0019",
    "F1": "B0012",
    "F2": "B0001",
    "F3": "B0020",
    "R0": "A0010",
    "R1": "A0017",
    "R2": "B0023",
    "R3": "B0025",
}
SHUTDOWN_POLICY = {
    "shutdown_before_every_stage": True,
    "archive_before_independent_shutdown": True,
    "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
    "verify_both_shutdown_markers": True,
    "clear_frozen_capture_before_shutdown_program": False,
}
RUN_RE = re.compile(
    r"^p10_3f_full_(?P<utc>[0-9]{8}T[0-9]{6}Z)_"
    r"(?P<host>[0-9a-f]{8})_(?P<fixed>[0-9a-f]{8})_"
    r"(?P<rotating>[0-9a-f]{8})$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def artifact_by_key(campaign: dict[str, Any], role: str, kind: str) -> dict[str, Any]:
    matches = [
        item for item in campaign.get("artifacts", [])
        if isinstance(item, dict) and item.get("role") == role and
        item.get("kind") == kind
    ]
    if len(matches) != 1:
        raise ValueError(f"campaign artifact is not unique: {role}/{kind}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--user-statement", required=True)
    parser.add_argument("--received-at-utc")
    args = parser.parse_args()

    if os.environ.get("NO_HARDWARE") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() not in {"false", "0", "no"}:
        raise SystemExit("authorization creation requires offline environment gates")
    if git("branch", "--show-current") != "codex/p10.3-fault-forensics":
        raise SystemExit("authorization creation refused on unexpected branch")
    if git("status", "--porcelain"):
        raise SystemExit("authorization creation requires a completely clean worktree")
    if git("diff", "--exit-code", "HEAD", "--", str(CAMPAIGN.relative_to(ROOT))):
        raise SystemExit("campaign freeze differs from committed HEAD")

    campaign = load_json(CAMPAIGN)
    if campaign.get("status") != "PASS" or campaign.get("acceptance_eligible") is not True:
        raise SystemExit("campaign freeze is not an acceptance-eligible PASS")
    if campaign.get("goal_sha256") != GOAL_SHA256:
        raise SystemExit("campaign Goal hash mismatch")
    if campaign.get("module_binding") != MODULE_BINDING:
        raise SystemExit("campaign module binding mismatch")
    if campaign.get("shutdown_policy") != SHUTDOWN_POLICY:
        raise SystemExit("campaign shutdown policy mismatch")
    if len(campaign.get("artifacts", [])) != 10:
        raise SystemExit("campaign artifact set is not complete")

    fixed = artifact_by_key(campaign, "fixed", "functional_bitstream")
    rotating = artifact_by_key(campaign, "rotating", "functional_bitstream")
    match = RUN_RE.fullmatch(args.run_id)
    if match is None:
        raise SystemExit("run ID does not satisfy the exact P10.3F format")
    expected_parts = {
        "host": str(campaign.get("host_source_commit", ""))[:8],
        "fixed": str(fixed.get("sha256", ""))[:8],
        "rotating": str(rotating.get("sha256", ""))[:8],
    }
    if any(match.group(name) != value for name, value in expected_parts.items()):
        raise SystemExit("run ID digest prefixes do not bind the campaign")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    previous: dict[str, Any] | None = None
    if OUTPUT.is_file():
        previous_record = load_json(OUTPUT)
        previous = {
            "path": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(OUTPUT),
            "status": previous_record.get("status"),
            "run_id": previous_record.get("run_id"),
            "consumed": previous_record.get("consumed"),
        }
        if previous["consumed"] is not True:
            raise SystemExit("refusing to replace an unconsumed authorization")

    payload = {
        "schema_version": 1,
        "authorization_id": AUTHORIZATION_ID,
        "scope": SCOPE,
        "status": "AUTHORIZED",
        "run_id": args.run_id,
        "authorized": True,
        "consumed": False,
        "current_run_hardware_authorization": True,
        "no_hardware": False,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": campaign["artifact_source_commit"],
        "host_source_commit": campaign["host_source_commit"],
        "campaign_freeze_path": str(CAMPAIGN.relative_to(ROOT)).replace("\\", "/"),
        "campaign_freeze_sha256": sha256(CAMPAIGN),
        "fixed_jtag_serial": FIXED_SERIAL,
        "rotating_jtag_serial": ROTATING_SERIAL,
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{ROTATING_SERIAL}",
        },
        "module_binding": MODULE_BINDING,
        "allowed_stages": campaign["allowed_hardware_stages"],
        "artifacts": campaign["artifacts"],
        "host_inputs": campaign["host_inputs"],
        "maximum_lane_mask": 15,
        "internal_stream_object_bytes": 262_144,
        "maximum_staircase_level_bytes": 262_144,
        "maximum_long_test_command_bytes": 64 << 20,
        "maximum_board_autonomous_aggregate_command_bytes": 64 << 20,
        "maximum_functional_diagnostic_object_bytes": 16 << 20,
        "maximum_single_formal_run_seconds": 1800,
        "ethernet_allowed": False,
        "movement_rotation_realignment_or_rewiring_allowed": False,
        "manual_instrumentation": "OMITTED_BY_USER",
        "two_hour_test_allowed": False,
        "p11_allowed": False,
        "shutdown_policy": SHUTDOWN_POLICY,
        "authorization_boundaries": {
            "maximum_lane_mask": 15,
            "maximum_single_formal_run_seconds": 1800,
            "shutdown_before_every_stage": True,
            "archive_before_independent_shutdown": True,
            "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
            "verify_both_shutdown_markers": True,
            "ethernet_used": False,
            "no_hardware_movement": True,
            "no_rotation": True,
            "no_realignment": True,
            "no_rewiring": True,
            "no_two_hour_test": True,
            "p11_not_started": True,
        },
        "retry_policy": (
            "No retry-count upper bound inside the exact authorized Goal; each immutable "
            "run_id still requires shutdown-before and verified dual-board shutdown."
        ),
        "user_authorization_statement": args.user_statement.strip(),
        "user_authorization_received_at_utc": args.received_at_utc or now,
        "user_authorization_context": (
            "The user's current statement authorizes every operation needed to continue "
            "the exact P10.3/P10.3F Goal with this newly frozen atomic-migration artifact "
            "bundle. Existing Goal prohibitions and shutdown boundaries remain in force."
        ),
        "authorization_created_at_utc": now,
        "supersedes_consumed_authorization": previous,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"P10_3F_CURRENT_RUN_AUTHORIZATION=AUTHORIZED")
    print(f"P10_3F_RUN_ID={args.run_id}")
    print(f"P10_3F_AUTHORIZATION_SHA256={sha256(OUTPUT)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
