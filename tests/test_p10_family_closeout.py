#!/usr/bin/env python3
"""Executable contracts for the offline P10-family closeout tooling."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts/verify_p10_family_closeout.py"
GENERATE = ROOT / "scripts/generate_p10_family_closeout.py"
sys.path.insert(0, str(ROOT / "scripts"))

from p8a_common import validate_state  # noqa: E402


def offline_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "NO_HARDWARE": "1",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
    })
    return env


class P10FamilyCloseoutTests(unittest.TestCase):
    def test_canonical_state_allows_final_p10_family_closeout_before_p11(self) -> None:
        state = json.loads(
            (ROOT / "config/project_state.json").read_text(encoding="utf-8")
        )
        errors = validate_state(state, ROOT)
        self.assertEqual([], errors)
        self.assertEqual("P10_FAMILY_FINAL_CLOSEOUT", state["current_program_stage"])
        self.assertEqual("NOT_STARTED", state["p11_status"])
        self.assertFalse(state["current_run_hardware_authorization"])
        self.assertFalse(state["current_run_hardware_authorization_reusable"])

    def test_canonical_state_rejects_a_changed_closeout_report_hash(self) -> None:
        state = json.loads(
            (ROOT / "config/project_state.json").read_text(encoding="utf-8")
        )
        state["p10_family_closeout"]["family_summary_sha256"] = "0" * 64
        errors = validate_state(state, ROOT)
        self.assertTrue(
            any("p10_family_closeout family_summary SHA256 mismatch" in item for item in errors),
            errors,
        )

    def test_frozen_baseline_verifier_passes_without_mutating_worktree(self) -> None:
        before = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
        )
        result = subprocess.run(
            [sys.executable, str(VERIFY), "--json-summary"],
            cwd=ROOT,
            env=offline_env(),
            text=True,
            capture_output=True,
        )
        after = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(
            "0a79ee8be21a199e7ba14bd65fcd72638f7160e0",
            payload["p10_5"]["pass_tag_target"],
        )
        self.assertEqual(1107, payload["p10_5"]["manifest_verified_files"])
        self.assertEqual("PASS", payload["p10_5"]["mandatory_result"])
        self.assertEqual(
            "PASS_WITH_NONBLOCKING_LIMITS", payload["p10_5"]["status"]
        )
        self.assertEqual(
            "FAIL_NONBLOCKING",
            payload["p10_5"]["stretch_4p8mbps"]["F_TO_R"],
        )
        self.assertEqual(
            "FAIL_NONBLOCKING",
            payload["p10_5"]["stretch_4p8mbps"]["R_TO_F"],
        )
        self.assertEqual("PASS", payload["p10_4"]["archive_provenance"]["status"])
        self.assertEqual(
            "4fdb7b1db433e213bd0ab5bd49e07df3f9d87517f933406b0f29ae5e7c57f42c",
            payload["p10_4"]["archive_provenance"]["archive_sha256"],
        )
        self.assertEqual(
            486, payload["p10_4"]["archive_provenance"]["verified_files"]
        )
        self.assertEqual(
            [5285, 3147],
            [item["verified_files"] for item in payload["p10_4"]["manifests"]],
        )
        self.assertFalse(payload["current_run_hardware_authorization"])
        self.assertFalse(payload["hardware_actions_executed"])
        self.assertEqual("NOT_STARTED", payload["p11_status"])
        self.assertEqual(before, after)

    def test_committed_closeout_reports_match_canonical_renderer(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATE), "--check"],
            cwd=ROOT,
            env=offline_env(),
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(14, payload["verified_report_files"])
        self.assertEqual("PASS", payload["p10_5_mandatory_result"])
        self.assertEqual(
            "PASS_WITH_NONBLOCKING_LIMITS", payload["p10_5_status"]
        )
        self.assertFalse(payload["current_run_hardware_authorization"])
        self.assertTrue(payload["no_hardware_actions_executed"])
        self.assertEqual("NOT_STARTED", payload["p11_status"])


if __name__ == "__main__":
    unittest.main()
