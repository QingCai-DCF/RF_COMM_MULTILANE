from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / "ddr_debug" / "campaign_d" / "CAMPAIGN_D_CLOSURE.json"
RUN_IDS = [
    "p7_20260714_ddr_external_campaign_d_01",
    "p7_20260714_ddr_external_campaign_d_02",
    "p7_20260714_ddr_external_campaign_d_03",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CampaignDEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = json.loads(CLOSURE.read_text(encoding="utf-8"))

    def test_closure_scope_and_result_are_exact(self) -> None:
        closure = self.closure
        self.assertEqual(
            "COMPLETE_DIAGNOSTIC_STAGE62_THREE_RUN_STREAK_PASS",
            closure["status"],
        )
        self.assertEqual("PENDING_HW", closure["HARDWARE_ACCEPTANCE"])
        self.assertFalse(closure["acceptance_valid"])
        self.assertTrue(closure["diagnostic_only"])
        self.assertFalse(closure["coverage_claimed"])
        self.assertEqual(3, closure["hardware_runs_attempted"])
        self.assertEqual(3, closure["hardware_runs_passed"])
        self.assertFalse(closure["fourth_authorization_created"])
        self.assertFalse(closure["fourth_run_started"])
        self.assertEqual(RUN_IDS, [run["run_id"] for run in closure["runs"]])

        scope = closure["execution_scope"]
        self.assertTrue(scope["stage62_only"])
        self.assertFalse(scope["stages_1_61_executed"])
        self.assertFalse(scope["full_stages_1_66_executed"])
        self.assertFalse(scope["stationary_executed"])
        self.assertFalse(scope["ethernet_used"])
        self.assertFalse(scope["motion_used"])

    def test_each_run_summary_and_shutdown_are_complete(self) -> None:
        for run in self.closure["runs"]:
            summary_path = ROOT / run["summary_path"]
            manifest_path = ROOT / run["raw_manifest_path"]
            shutdown_path = ROOT / run["shutdown_after_path"]
            for path, size_key, sha_key in (
                (summary_path, "summary_size_bytes", "summary_sha256"),
                (manifest_path, "raw_manifest_size_bytes", "raw_manifest_sha256"),
                (shutdown_path, "shutdown_after_size_bytes", "shutdown_after_sha256"),
            ):
                self.assertTrue(path.is_file(), path)
                self.assertEqual(run[size_key], path.stat().st_size)
                self.assertEqual(run[sha_key], sha256(path))

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(run["run_id"], summary["run_id"])
            self.assertEqual("PASS", summary["P7_PS_APPLICATION_SAFE_STAGE"])
            self.assertTrue(summary["stage62_attempted"])
            self.assertTrue(summary["stage62_executed"])
            self.assertTrue(summary["stage62_completed"])
            self.assertFalse(summary["functional_stages_1_61_executed"])
            self.assertTrue(summary["postprocess"]["passed"])
            self.assertEqual([], summary["postprocess"]["failures"])
            self.assertEqual(48, len(summary["postprocess"]["boundary_cases"]))
            self.assertTrue(
                all(case["passed"] for case in summary["postprocess"]["boundary_cases"])
            )
            self.assertEqual(8, len(summary["postprocess"]["cases"]))
            self.assertTrue(all(case["passed"] for case in summary["postprocess"]["cases"]))
            self.assertEqual([], summary["postprocess"]["stationary_objects"])
            self.assertEqual([], summary["postprocess"]["stationary_samples"])
            self.assertEqual(0, summary["ps_process"]["returncode"])
            self.assertFalse(summary["ps_process"]["timed_out"])
            self.assertEqual(0, summary["shutdown_before"]["returncode"])
            self.assertEqual(0, summary["shutdown_after"]["returncode"])
            self.assertTrue(summary["programmed_shutdown_before"])
            self.assertTrue(summary["programmed_shutdown_after"])
            self.assertEqual("PENDING_HW", summary["HARDWARE_ACCEPTANCE"])
            self.assertFalse(summary["coverage_claimed"])
            self.assertTrue(summary["diagnostic_only"])

            shutdown = shutdown_path.read_text(encoding="utf-8")
            self.assertIn("P7_SHUTDOWN_RESULT=PASS", shutdown)
            self.assertIn(
                "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810.bit",
                shutdown,
            )

    def test_all_raw_evidence_records_rehash_exactly(self) -> None:
        total_records = 0
        for run in self.closure["runs"]:
            manifest_path = ROOT / run["raw_manifest_path"]
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(0, manifest["partial_file_count"])
            self.assertEqual([], manifest["partial_files"])
            self.assertEqual(run["raw_record_count"], manifest["record_count"])
            self.assertEqual(run["raw_record_count"], len(manifest["records"]))
            run_root = manifest_path.parent
            for record in manifest["records"]:
                self.assertTrue(record["committed"], record["path"])
                path = run_root / record["path"]
                self.assertTrue(path.is_file(), path)
                self.assertEqual(record["size_bytes"], path.stat().st_size)
                self.assertEqual(record["sha256"], sha256(path))
                total_records += 1
        self.assertEqual(1275, total_records)

    def test_final_safety_and_conclusion_remain_bounded(self) -> None:
        safety = self.closure["final_safety"]
        self.assertFalse(safety["active_runner"])
        self.assertFalse(safety["active_xsdb_transaction"])
        self.assertFalse(safety["active_vivado_transaction"])
        self.assertTrue(safety["runner_lock_free"])
        self.assertTrue(safety["safe_shutdown_complete"])
        self.assertEqual(0, safety["established_hw_server_connections"])

        conclusion = self.closure["conclusion"]
        self.assertTrue(conclusion["evidence_harvest_fix_confirmed_on_hardware"])
        self.assertEqual(3, conclusion["original_stage62_consecutive_passes"])
        self.assertTrue(conclusion["ready_for_main_integration"])
        self.assertIn(
            "formal full-project hardware acceptance",
            conclusion["not_proven"],
        )


if __name__ == "__main__":
    unittest.main()
