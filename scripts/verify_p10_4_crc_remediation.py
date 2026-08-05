#!/usr/bin/env python3
"""Verify the P10.4 connector-local ACK RX-quarantine remediation offline."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
OUTPUT_JSON = GENERATED / "p10_4_crc_bad_remediation.json"
OUTPUT_MD = GENERATED / "p10_4_crc_bad_remediation.md"
CONFIG = ROOT / "config/p10_4_connector_ack_rx_quarantine.yaml"
DIAGNOSIS = GENERATED / "p10_4_crc_bad_root_cause_diagnosis.json"
XSIM = GENERATED / "p10_4_xsim/summary.json"
HELPER = ROOT / "rtl/p10_4_connector_ack_rx_quarantine.sv"
CORE = ROOT / "rtl/p9_optical_transport_core.sv"
TESTBENCH = ROOT / "sim/tb/tb_p10_2_4lane_suite.sv"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
DESIGN = ROOT / "docs/design/P10_4_CONNECTOR_ACK_RX_QUARANTINE.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"non-object JSON: {path}")
    return value


def main() -> int:
    errors: list[str] = []
    checks: dict[str, bool] = {}
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        errors.append("offline environment is not fail-closed")

    paths = (CONFIG, DIAGNOSIS, XSIM, HELPER, CORE, TESTBENCH,
             REQUIREMENTS, DESIGN)
    missing = [rel(path) for path in paths if not path.is_file()]
    if missing:
        errors.append("missing inputs: " + ",".join(missing))

    config: dict[str, Any] = {}
    diagnosis: dict[str, Any] = {}
    xsim: dict[str, Any] = {}
    helper_text = core_text = testbench_text = requirements_text = ""
    if not missing:
        try:
            parsed_config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
            if not isinstance(parsed_config, dict):
                raise ValueError(f"non-object YAML: {CONFIG}")
            config = parsed_config
            diagnosis = load_json(DIAGNOSIS)
            xsim = load_json(XSIM)
            helper_text = HELPER.read_text(encoding="utf-8")
            core_text = CORE.read_text(encoding="utf-8")
            testbench_text = TESTBENCH.read_text(encoding="utf-8")
            requirements_text = REQUIREMENTS.read_text(encoding="utf-8")
        except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
            errors.append(f"input parse failed: {exc}")

    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    xsim_result = next((item for item in xsim.get("results", [])
                        if isinstance(item, dict) and item.get("test_id") ==
                        "tb_p10_4_connector_ack_quarantine"), None)
    noninterference = config.get("noninterference", {}) if config else {}
    pairs = config.get("physical_topology", {}).get("pairs", []) if config else []
    pair_lanes = [item.get("lanes") for item in pairs
                  if isinstance(item, dict)]
    checks.update({
        "diagnosis_is_exact_failed_run": (
            diagnosis.get("run_id") ==
            "p10_4_20260805T173745Z_6c7418e6_b20f137e_795f3f34" and
            diagnosis.get("observed_failure", {}).get(
                "maximum_physical_crc_bad") == 929
        ),
        "connector_pairs_are_j10_and_j11": pair_lanes == [[0, 1], [2, 3]],
        "helper_pairs_adjacent_lanes": "PEER_LANE = lane ^ 1" in helper_text,
        "helper_requires_actual_peer_ack_txd": bool(re.search(
            r"final_local_txd_i\[PEER_LANE\]\s*&&\s*"
            r"local_tx_is_ack_i\[PEER_LANE\]", helper_text)),
        "helper_preserves_same_module_source": bool(re.search(
            r"final_local_txd_i\[lane\]\s*\|\|\s*"
            r"paired_ack_txd_o\[lane\]", helper_text)),
        "core_uses_actual_final_txd": (
            "local_final_txd = local_is_a ? a_txd_o : b_txd_o" in core_text
        ),
        "core_routes_quarantine_to_admission": (
            ".final_physical_txd_i(selected_rx_quarantine_source)" in core_text
        ),
        "focused_test_present": (
            "module tb_p10_4_connector_ack_quarantine" in testbench_text and
            "TB_P10_4_CONNECTOR_ACK_QUARANTINE=PASS" in testbench_text
        ),
        "focused_test_passed": (
            isinstance(xsim_result, dict) and xsim_result.get("status") == "PASS"
        ),
        "complete_p10_4_xsim_passed": xsim.get("status") == "PASS",
        "xsim_bound_to_current_commit": xsim.get("source_commit") == head,
        "xsim_source_clean": xsim.get("source_worktree_dirty") is False,
        "requirement_id_present": (
            "requirement_id: P10_4-XTALK-002" in requirements_text
        ),
        "no_control_or_safety_feedback": (
            bool(noninterference) and
            all(value == 0 for value in noninterference.values())
        ),
        "ordinary_data_peer_independence_frozen": (
            config.get("quarantine_source", {}).get(
                "ordinary_peer_lane_data_tx_is_not_a_trigger") is True
        ),
        "old_results_not_inherited": (
            config.get("artifact_policy", {}).get(
                "old_hardware_results_inherited") is False
        ),
    })
    errors.extend(name for name, passed in checks.items() if not passed)
    status = "PASS" if not errors else "FAIL"
    inputs = {
        rel(path): {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in paths if path.is_file()
    }
    payload = {
        "schema_version": 1,
        "test_id": "P10_4-XTALK-002",
        "status": status,
        "source_commit": head,
        "scope": "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT",
        "strategy": "ACK_ONLY_CONNECTOR_PAIR_RX_QUARANTINE",
        "checks": checks,
        "inputs": inputs,
        "old_hardware_results_inherited": False,
        "fresh_hardware_acceptance_required": True,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "errors": errors,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    GENERATED.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n"
    )
    lines = [
        "# P10.4 connector ACK RX-quarantine verification", "",
        f"- Status: `{status}`", f"- Source commit: `{head}`",
        "- Hardware actions executed: `false`",
        "- Fresh hardware acceptance required: `true`", "",
        "| Check | Result |", "|---|---|",
    ]
    lines.extend(f"| {name} | {'PASS' if passed else 'FAIL'} |"
                 for name, passed in checks.items())
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {item}" for item in errors])
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_4_CRC_BAD_REMEDIATION={status}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
