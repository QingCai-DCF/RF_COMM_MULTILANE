#!/usr/bin/env python3
"""Generate immutable-source P10.1R repository, failure, and RX-design intake."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated"
GOAL = ROOT / "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md"
TERMINAL = ROOT / "evidence/generated/p10_1_hw_campaign_terminal_summary.json"
FAIL_TAG = "p10.1-hardware-performance-fail-20260801"
EXPECTED_GOAL_SHA256 = (
    "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
)
EXPECTED_BASE_SOURCE = "bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1"
EXPECTED_ARTIFACTS = {
    "fixed:performance_bitstream":
        "1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e",
    "rotating:performance_bitstream":
        "9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f",
    "fixed:elf":
        "17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728",
    "rotating:elf":
        "88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path) -> dict[str, object]:
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_pair(stem: str, title: str, payload: dict[str, object]) -> None:
    json_path = OUT / f"{stem}.json"
    md_path = OUT / f"{stem}.md"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    lines = [
        f"# {title}", "", f"- Status: `{payload['status']}`",
        f"- Source commit: `{payload['source_commit']}`",
        "- Hardware actions executed: `false`", "", "```json",
        json.dumps(payload, indent=2, sort_keys=True), "```", "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        print("P10_1R_INTAKE_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED")
        return 2

    required = [
        GOAL, TERMINAL, ROOT / "config/project_state.json",
        ROOT / "config/project_requirements.yaml",
        ROOT / "config/tfdu_rx_admission.yaml",
        ROOT / "config/performance/p10_1r_hardware_runtime.yaml",
        ROOT / "config/register_map/ir_axi_regs.yaml",
        ROOT / "rtl/p10_1r_rx_admission.sv",
        ROOT / "rtl/p9_optical_transport_core.sv",
        ROOT / "sim/tb/tb_p10_1r_focused.sv",
    ]
    missing = [rel(path) for path in required if not path.is_file()]
    if missing:
        print("P10_1R_INTAKE_REFUSED=MISSING:" + ",".join(missing))
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    source_commit = git("rev-parse", "HEAD").stdout.strip()
    branch = git("branch", "--show-current").stdout.strip()
    dirty_before = bool(git("status", "--porcelain").stdout.strip())
    tag_type = git("cat-file", "-t", FAIL_TAG).stdout.strip()
    tag_target = git("rev-parse", f"{FAIL_TAG}^{{}}").stdout.strip()
    offline_ancestor = git(
        "merge-base", "--is-ancestor", "p10.1-offline-performance-ready", "HEAD",
        check=False,
    ).returncode == 0
    p10_pass_ancestor = git(
        "merge-base", "--is-ancestor", "p10-ax7020-dual-node-2lane-pass", "HEAD",
        check=False,
    ).returncode == 0

    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    state = json.loads((ROOT / "config/project_state.json").read_text(encoding="utf-8"))
    admission = yaml.safe_load(
        (ROOT / "config/tfdu_rx_admission.yaml").read_text(encoding="utf-8")
    )
    runtime = yaml.safe_load(
        (ROOT / "config/performance/p10_1r_hardware_runtime.yaml").read_text(
            encoding="utf-8"
        )
    )
    frozen_artifacts = terminal.get("artifact_hashes", {})
    artifact_match = all(
        frozen_artifacts.get(name, {}).get("sha256") == digest
        for name, digest in EXPECTED_ARTIFACTS.items()
    )
    goal_match = sha256(GOAL) == EXPECTED_GOAL_SHA256
    baseline_ok = all((
        tag_type == "tag",
        terminal.get("source_commit") == EXPECTED_BASE_SOURCE,
        terminal.get("campaign_disposition") ==
            "TERMINAL_FAIL_REMEDIATION_REQUIRED",
        terminal.get("current_run_hardware_authorization") is False,
        terminal.get("SHUTDOWN_FIXED") == "PASS",
        terminal.get("SHUTDOWN_ROTATING") == "PASS",
        state.get("last_hardware_authorization_consumed") is True,
        state.get("p10_1_current_run_authorization", {}).get("consumed") is True,
        artifact_match,
    ))

    common = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "source_commit": source_commit,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "network_used": False,
    }
    repo_ok = all((
        branch == "p10.1r/2lane-speed-stability-remediation",
        Path.cwd().resolve() == ROOT.resolve(), goal_match, tag_type == "tag",
        offline_ancestor, p10_pass_ancestor,
        state.get("current_run_hardware_authorization") is False,
    ))
    repo_payload = {
        **common,
        "test_id": "P10_1R-REPOSITORY-INTAKE",
        "status": "PASS" if repo_ok else "FAIL",
        "branch": branch,
        "worktree": str(ROOT),
        "source_worktree_dirty_before_generation": dirty_before,
        "goal": record(GOAL),
        "expected_goal_sha256": EXPECTED_GOAL_SHA256,
        "goal_hash_match": goal_match,
        "failure_tag": FAIL_TAG,
        "failure_tag_type": tag_type,
        "failure_tag_target": tag_target,
        "offline_tag_is_ancestor": offline_ancestor,
        "p10_pass_tag_is_ancestor": p10_pass_ancestor,
        "board_binding": {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating_role": "AX7020-R/JTAG:210512180081",
        },
        "lane_mapping": {"lane0": "F0-R0", "lane1": "F1-R1"},
        "inputs": [record(path) for path in required],
    }

    failure_payload = {
        **common,
        "test_id": "P10_1R-FAILURE-BASELINE-FREEZE",
        "status": "PASS" if baseline_ok else "FAIL",
        "failure_tag": FAIL_TAG,
        "failure_tag_type": tag_type,
        "failure_tag_target": tag_target,
        "terminal_summary": record(TERMINAL),
        "baseline_source_commit": terminal.get("source_commit"),
        "artifact_hashes": {
            name: frozen_artifacts.get(name) for name in EXPECTED_ARTIFACTS
        },
        "artifact_hash_match": artifact_match,
        "run_ids": terminal.get("run_ids"),
        "selected_stage_runs": terminal.get("selected_stage_runs"),
        "fail_gates": terminal.get("fail_gates"),
        "failure_classification": terminal.get("failure_classification"),
        "measured_goodput_bps": {
            "fixed_to_rotating": terminal.get("f_to_r_application_goodput_bps"),
            "rotating_to_fixed": terminal.get("r_to_f_application_goodput_bps"),
        },
        "same_module_false_frames": terminal.get(
            "non_target_crc_valid_false_frames"
        ),
        "crosstalk_4x4_matrix": terminal.get("crosstalk_4x4_matrix"),
        "shutdown_fixed": terminal.get("SHUTDOWN_FIXED"),
        "shutdown_rotating": terminal.get("SHUTDOWN_ROTATING"),
        "old_authorization_consumed": state.get(
            "last_hardware_authorization_consumed"
        ) is True,
        "old_authorization_reusable": False,
    }

    xsim_path = ROOT / "evidence/generated/p10_1r_xsim/summary.json"
    xsim = (
        json.loads(xsim_path.read_text(encoding="utf-8"))
        if xsim_path.is_file() else None
    )
    design_ok = all((
        admission.get("candidate_timing", {}).get("minimum_post_tx_guard_cycles")
            == 4_096,
        admission.get("candidate_timing", {}).get("rxd_idle_qual_cycles") == 256,
        admission.get("candidate_timing", {}).get(
            "maximum_echo_quarantine_cycles"
        ) == 131_072,
        admission.get("behavior", {}).get(
            "local_tx_does_not_blank_other_lane"
        ) is True,
        admission.get("safety", {}).get("affects_global_permit") is False,
        runtime.get("protocol", {}).get("endpoint_burst_frames") == 32,
        runtime.get("protocol", {}).get("ack_threshold") == 32,
        xsim is not None and xsim.get("status") == "PASS",
    ))
    design_payload = {
        **common,
        "test_id": "P10_1R-RX-ADMISSION-DESIGN",
        "status": "PASS" if design_ok else "FAIL",
        "scope": "OFFLINE_DESIGN_AND_XSIM_ONLY",
        "hardware_measurement_status": "PASS_GUARD_SELECTION_REBUILD_PENDING",
        "candidate_guard_cycles": 4_096,
        "candidate_guard_us": 64,
        "selected_final_guard_cycles": 4_096,
        "guard_selection_evidence": record(
            ROOT / "evidence/generated/p10_1r_echo_guard_selection.json"
        ),
        "idle_qualification_cycles": 256,
        "maximum_quarantine_cycles": 131_072,
        "source_identity": admission.get("source_identity"),
        "safety_noninterference": admission.get("safety"),
        "config": record(ROOT / "config/tfdu_rx_admission.yaml"),
        "register_map": record(ROOT / "config/register_map/ir_axi_regs.yaml"),
        "rtl": [
            record(ROOT / "rtl/p10_1r_rx_admission.sv"),
            record(ROOT / "rtl/p9_optical_transport_core.sv"),
        ],
        "focused_xsim": record(xsim_path) if xsim_path.is_file() else None,
        "direct_hardware_claim": False,
    }

    write_pair("p10_1r_repo_intake", "P10.1R repository intake", repo_payload)
    write_pair(
        "p10_1r_failure_baseline_summary",
        "P10.1R immutable failure baseline",
        failure_payload,
    )
    write_pair(
        "p10_1r_failure_baseline",
        "P10.1R immutable failure baseline",
        failure_payload,
    )
    write_pair(
        "p10_1r_rx_admission_design",
        "P10.1R RX admission design evidence",
        design_payload,
    )
    status = "PASS" if repo_ok and baseline_ok and design_ok else "FAIL"
    print(f"P10_1R_INTAKE={status}")
    print(f"FAILURE_BASELINE_FROZEN={failure_payload['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
