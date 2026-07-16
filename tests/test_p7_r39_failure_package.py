from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "evidence" / "generated" / "p7_r39_diagnostic_failure.json"
PACKAGE = ROOT / "evidence" / "generated" / "p7_r39_failure_package"
REPLAY = ROOT / "evidence" / "generated" / "p7_r39_summarizer_replay"
REPLAY_RESULT = ROOT / "evidence" / "generated" / "p7_r39_summarizer_replay_result.json"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
EXPECTED_ORDINALS = [1, 2, 3, 4, *range(55, 66)]
EXPECTED_ATTEMPTS = [1, 2, 3, 4, *range(55, 65)]
R39_REPAIR_BLOB_COMMITS = {
    "software/ps_driver/p7_app_service.c": "6d56b312b35da539ca38d848455b8cbc2adb2014",
    "tools/run_p7_ps_core_offline.py": "1eb2ff82da57aa13dc2d0f3aa88fd75de35109e9",
    "tests/test_p7_ps_application_stage_safe.py": "6d56b312b35da539ca38d848455b8cbc2adb2014",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha256(commit: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"historical Git blob unavailable: {commit}:{path}: "
            + completed.stderr.decode("utf-8", errors="replace")
        )
    return hashlib.sha256(completed.stdout).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON root is not an object: {path}")
    return value


def package_tree(package_root: Path = PACKAGE) -> tuple[int, int, int, str]:
    records: list[str] = []
    total_bytes = 0
    files = sorted(path for path in package_root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(package_root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        records.append(f"{relative}\t{size}\t{sha256(path)}\n")
    digest = hashlib.sha256("".join(records).encode("utf-8")).hexdigest()
    partial_count = sum(path.name.endswith(".partial") for path in files)
    return len(files), total_bytes, partial_count, digest


def between(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    return text[start_index : text.index(end, start_index)]


class P7R39FailurePackageTests(unittest.TestCase):
    def test_portable_package_and_primary_records_are_hash_exact(self) -> None:
        summary = load_json(SUMMARY)
        portable = summary["portable_package"]
        self.assertIsInstance(portable, dict)
        count, byte_count, partial_count, digest = package_tree()
        self.assertEqual(portable["file_count"], count)
        self.assertEqual(portable["byte_count"], byte_count)
        self.assertEqual(portable["partial_file_count"], partial_count)
        self.assertEqual(portable["tree_sha256"], digest)

        records = (
            (summary["ledger"], "path", "sha256"),
            (summary["stage64"], "summary_path", "summary_sha256"),
            (summary["stage64"], "raw_result_path", "raw_result_sha256"),
            (summary["stage64"], "raw_manifest_path", "raw_manifest_sha256"),
            (
                summary["historical_preflight_freeze"],
                "manifest_path",
                "manifest_sha256",
            ),
            (
                summary["authorization_gate_recovery_attempt"],
                "summary_path",
                "summary_sha256",
            ),
            (summary["independent_recovery"], "summary_path", "summary_sha256"),
        )
        for record, path_key, hash_key in records:
            self.assertIsInstance(record, dict)
            path = ROOT / str(record[path_key])
            self.assertTrue(path.is_file(), path)
            self.assertEqual(record[hash_key], sha256(path))

    def test_ledger_has_exact_diagnostic_prefix_then_stage64_fail(self) -> None:
        summary = load_json(SUMMARY)
        ledger = load_json(PACKAGE / "sequence_execution_ledger.json")
        self.assertEqual("FAIL", ledger["status"])
        self.assertEqual("DIAGNOSTIC_SUFFIX_55", ledger["plan_mode"])
        self.assertEqual(summary["source_commit"], ledger["source_commit"])
        self.assertEqual(EXPECTED_ORDINALS, ledger["full_stage_ordinals"])
        self.assertEqual(14, ledger["attempt_count"])
        self.assertEqual(13, ledger["completed_stage_count"])
        self.assertEqual(13, ledger["failed_stage_index"])
        self.assertFalse(ledger["coverage_claimed"])
        self.assertEqual("PENDING_HW", ledger["HARDWARE_ACCEPTANCE"])

        attempts = ledger["attempts"]
        self.assertIsInstance(attempts, list)
        self.assertEqual(EXPECTED_ATTEMPTS, [item["full_stage_ordinal"] for item in attempts])
        for attempt_number, attempt in enumerate(attempts[:13], 1):
            self.assertEqual(attempt_number, attempt["attempt"])
            self.assertEqual("TERMINAL", attempt["state"])
            self.assertEqual("PASS", attempt["result"])
            self.assertTrue(attempt["shutdown_after"]["passed"])
            self.assertTrue(SHA256_RE.fullmatch(attempt["summary_file"]["sha256"]))

        failed = attempts[13]
        self.assertEqual(64, failed["full_stage_ordinal"])
        self.assertEqual("p7_ps_abort_restart", failed["stage_id"])
        self.assertEqual("TERMINAL", failed["state"])
        self.assertEqual("FAIL", failed["result"])
        self.assertEqual(1, failed["process"]["returncode"])
        self.assertTrue(failed["process"]["process_tree_reaped"])
        self.assertTrue(failed["shutdown_after"]["passed"])
        self.assertEqual(summary["stage64"]["summary_sha256"], failed["summary_file"]["sha256"])
        self.assertFalse(any(item["full_stage_ordinal"] in {65, 66} for item in attempts))

        contract = summary["diagnostic_contract"]
        self.assertTrue(contract["diagnostic_only"])
        self.assertFalse(contract["coverage_claimed"])
        self.assertFalse(contract["formal_acceptance_coverage_contributed"])
        self.assertFalse(contract["stationary_allowed"])
        self.assertEqual("PENDING_HW", contract["HARDWARE_ACCEPTANCE"])
        self.assertEqual("PASS", summary["stage62"]["terminal_result"])
        self.assertFalse(summary["stage62"]["acceptance_coverage_contributed"])
        self.assertFalse(summary["stage65"]["attempted"])
        self.assertEqual(0, summary["stationary"]["attempt_count"])
        self.assertFalse(summary["stationary"]["started"])

    def test_stage64_raw_pass_is_rejected_by_outer_atomic_wipe_check(self) -> None:
        summary = load_json(SUMMARY)
        stage = load_json(PACKAGE / "stage64" / "p7_ps_application_stage_summary.json")
        self.assertEqual("FAIL_STAGE", stage["P7_PS_APPLICATION_SAFE_STAGE"])
        self.assertEqual("PENDING_HW", stage["HARDWARE_ACCEPTANCE"])
        self.assertTrue(stage["shutdown_before"]["passed"])
        self.assertTrue(stage["shutdown_after"]["passed"])
        self.assertTrue(stage["child_reaped_before_shutdown_after"])
        self.assertEqual(0, stage["ps_process"]["returncode"])
        self.assertTrue(stage["ps_process"]["passed"])
        self.assertTrue(stage["ps_process"]["process_tree_reaped"])

        postprocess = stage["postprocess"]
        self.assertFalse(postprocess["passed"])
        self.assertEqual(
            ["slot 2: failed/aborted output was not atomically wiped"],
            postprocess["failures"],
        )
        duplicate = postprocess["cases"][2]
        self.assertEqual("duplicate_replay_rejected", duplicate["name"])
        self.assertEqual(2, duplicate["slot"])
        self.assertFalse(duplicate["passed"])
        self.assertEqual(6, duplicate["descriptor"]["status"])
        self.assertEqual(19, duplicate["descriptor"]["error_code"])
        self.assertEqual(0, duplicate["descriptor"]["bytes_completed"])
        self.assertEqual(1048576, duplicate["output_bytes"])
        self.assertEqual(
            "16c7f1d8a38b4b84560e558ab03b13c82e2ff374d87eaacb4df22f03604e7a4f",
            duplicate["output_sha256"],
        )
        self.assertNotEqual(
            "30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58",
            duplicate["output_sha256"],
        )

        raw = (PACKAGE / "stage64" / "p7_ps_application_raw_result.log").read_text(
            encoding="utf-8", errors="strict"
        )
        for marker in (
            "P7_ABORT_PHASE_ABORT_COUNT=1",
            "P7_ABORT_PHASE_SHUTDOWN_RESULT=0",
            "P7_ABORT_INTERPHASE_SHUTDOWN_PROGRAMMED=1",
            "P7_ABORT_RESTART_CANDIDATE_REPROGRAMMED=1",
            "P7_ABORT_RESTART_NEW_EPOCH=1",
            "P7_ABORT_RESTART_REPLAY_REJECTED=1",
            "P7_REQUEUE_AFTER_CUTOFF=0",
            "P7_PS_STAGE_RESULT=PASS",
        ):
            self.assertIn(marker, raw)
        self.assertTrue(summary["stage64"]["raw_ps_pass_is_not_stage_pass"])
        self.assertEqual("IMMUTABLE_FAIL_NEVER_RESUME", summary["run_status"])

    def test_historical_source_confirms_the_validation_reject_wipe_gap(self) -> None:
        summary = load_json(SUMMARY)
        history = load_json(PACKAGE / "historical_preflight_inputs" / "manifest.json")
        self.assertEqual(summary["source_commit"], history["source_commit"])
        self.assertEqual("FAIL_STAGE", history["result"])
        self.assertFalse(history["coverage_claimed"])
        self.assertEqual(44, len(history["files"]))

        roles: list[str] = []
        authorization_ordinals: list[int] = []
        for record in history["files"]:
            frozen = PACKAGE / "historical_preflight_inputs" / Path(record["frozen_path"]).name
            self.assertTrue(frozen.is_file(), frozen)
            self.assertEqual(record["bytes"], frozen.stat().st_size)
            self.assertEqual(record["sha256"], sha256(frozen))
            roles.append(record["role"])
            if record["role"] == "stage_authorization":
                authorization_ordinals.append(record["full_stage_ordinal"])
        self.assertEqual(EXPECTED_ORDINALS, authorization_ordinals)
        self.assertEqual(15, roles.count("stage_authorization"))
        self.assertEqual(1, roles.count("sequence_plan"))
        self.assertEqual(1, roles.count("offline_checkpoint"))

        historical_record = next(
            record for record in history["files"] if record["role"] == "historical_app_service_source"
        )
        historical = (
            PACKAGE / "historical_preflight_inputs" / Path(historical_record["frozen_path"]).name
        ).read_text(encoding="utf-8", errors="strict")
        validate = between(
            historical, "static int p7_validate_descriptor(", "static void p7_record_trace"
        )
        self.assertLess(validate.index("request->output_address"), validate.index("P7_ERROR_STALE_SESSION"))
        self.assertLess(validate.index("P7_ERROR_TRACE_RANGE"), validate.index("P7_ERROR_STALE_SESSION"))
        process = between(
            historical, "static int p7_process_descriptor(", "static uint32_t p7_queue_occupancy"
        )
        reject = between(process, "error = p7_validate_descriptor", "service->shutdown_attempted = 0U")
        self.assertIn("p7_stop_and_shutdown(service)", reject)
        self.assertNotIn("p7_wipe_partial", reject)
        self.assertLess(reject.index("p7_stop_and_shutdown(service)"), reject.index("p7_publish_descriptor("))

        current = (ROOT / "software" / "ps_driver" / "p7_app_service.c").read_text(
            encoding="utf-8", errors="strict"
        )
        current_process = between(
            current, "static int p7_process_descriptor(", "static uint32_t p7_queue_occupancy"
        )
        current_reject = between(
            current_process, "error = p7_validate_descriptor", "service->shutdown_attempted = 0U"
        )
        self.assertIn("if (private_output_validated != 0U)", current_reject)
        self.assertLess(
            current_reject.index("p7_stop_and_shutdown(service)"),
            current_reject.index("p7_wipe_partial(&request, 0U, descriptor)"),
        )
        self.assertLess(
            current_reject.index("p7_wipe_partial(&request, 0U, descriptor)"),
            current_reject.index("p7_publish_descriptor("),
        )
        self.assertEqual(
            "CONFIRMED_VALIDATION_REJECT_OUTPUT_WIPE_GAP",
            summary["failure_classification"]["status"],
        )
        self.assertFalse(summary["failure_classification"]["payload_or_ddr_corruption_claimed"])
        repair = summary["source_repair"]
        self.assertEqual(
            repair["service_sha256"],
            git_blob_sha256(
                R39_REPAIR_BLOB_COMMITS[repair["service_path"]],
                repair["service_path"],
            ),
        )
        self.assertEqual(
            repair["offline_checker_sha256"],
            git_blob_sha256(
                R39_REPAIR_BLOB_COMMITS[repair["offline_checker_path"]],
                repair["offline_checker_path"],
            ),
        )
        self.assertEqual(
            repair["focused_static_test_sha256"],
            git_blob_sha256(
                R39_REPAIR_BLOB_COMMITS[repair["focused_static_test_path"]],
                repair["focused_static_test_path"],
            ),
        )
        self.assertEqual("NOT_RUN", repair["complete_checkpoint_suites"])
        self.assertEqual("NOT_RUN", repair["hardware_validation"])

    def test_independent_recovery_is_separate_and_gate_failure_did_no_hardware(self) -> None:
        summary = load_json(SUMMARY)
        gate_auth = load_json(
            PACKAGE / "recovery_authorization_gate_failure" / "hardware_authorization.json"
        )
        self.assertFalse(gate_auth["AUTHORIZED"])
        self.assertFalse(gate_auth["RF_COMM_HW_AUTH_PRESENT"])
        self.assertEqual(
            ["RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"],
            gate_auth["missing"],
        )
        gate = (
            PACKAGE
            / "recovery_authorization_gate_failure"
            / "program_tfdu_shutdown_safe.summary.txt"
        ).read_text(encoding="utf-8", errors="strict")
        self.assertIn("HARDWARE_AUTHORIZATION_EXIT=2", gate)
        self.assertIn("NO_HARDWARE_ACTIONS_EXECUTED=1", gate)
        self.assertIn("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=AUTHORIZATION_MISSING", gate)

        recovery_auth = load_json(PACKAGE / "recovery" / "hardware_authorization.json")
        self.assertTrue(recovery_auth["AUTHORIZED"])
        self.assertTrue(recovery_auth["RF_COMM_HW_AUTH_PRESENT"])
        recovery = (PACKAGE / "recovery" / "program_tfdu_shutdown_safe.summary.txt").read_text(
            encoding="utf-8", errors="strict"
        )
        self.assertIn("NO_HARDWARE_ACTIONS_EXECUTED=0", recovery)
        self.assertIn("TFDU_SHUTDOWN_PROGRAMMED_SEEN=1", recovery)
        self.assertIn("SHUTDOWN_EXIT=0", recovery)
        self.assertIn("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS", recovery)
        self.assertTrue(summary["independent_recovery"]["separate_from_stage_result"])
        self.assertTrue(summary["authorization_gate_recovery_attempt"]["separate_from_stage_result"])
        self.assertFalse(summary["failure_classification"]["recovery_promotes_failed_stage"])

    def test_portable_tree_and_direct_records_reject_tampering(self) -> None:
        summary = load_json(SUMMARY)
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "package"
            shutil.copytree(PACKAGE, copied)
            raw = copied / "stage64" / "p7_ps_application_raw_result.log"
            raw.write_bytes(raw.read_bytes() + b"tamper\n")
            _, _, _, digest = package_tree(copied)
            self.assertNotEqual(summary["portable_package"]["tree_sha256"], digest)
            self.assertNotEqual(summary["stage64"]["raw_result_sha256"], sha256(raw))

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "package"
            shutil.copytree(PACKAGE, copied)
            ledger = copied / "sequence_execution_ledger.json"
            ledger.write_bytes(ledger.read_bytes() + b" ")
            _, _, _, digest = package_tree(copied)
            self.assertNotEqual(summary["portable_package"]["tree_sha256"], digest)
            self.assertNotEqual(summary["ledger"]["sha256"], sha256(ledger))

    def test_summarizer_replay_fails_closed_without_claiming_an_exit_code(self) -> None:
        replay = load_json(REPLAY_RESULT)
        tree = replay["output_tree"]
        count, byte_count, partial_count, digest = package_tree(REPLAY)
        self.assertEqual(tree["file_count"], count)
        self.assertEqual(tree["byte_count"], byte_count)
        self.assertEqual(tree["partial_file_count"], partial_count)
        self.assertEqual(tree["tree_sha256"], digest)
        self.assertEqual(1, replay["invocation_count"])
        self.assertTrue(replay["outer_wait_timed_out"])
        self.assertFalse(replay["summarizer_exit_code_observed"])
        self.assertTrue(replay["summarizer_child_completion_observed"])
        self.assertFalse(replay["summarizer_child_remaining_after_completion"])
        self.assertFalse(replay["hardware_actions_executed_by_summarizer"])

        for key in (
            "final_summary",
            "evidence_consistency",
            "shutdown_evidence",
            "authorization_summary",
            "stationary_summary",
        ):
            record = replay[key]
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(record["sha256"], sha256(path))

        final = load_json(ROOT / replay["final_summary"]["path"])
        self.assertEqual("FAIL", final["result"])
        self.assertEqual("FAIL", final["hardware_acceptance"])
        self.assertEqual(85, len(final["errors"]))
        consistency = load_json(ROOT / replay["evidence_consistency"]["path"])
        self.assertEqual("FAIL", consistency["result"])
        self.assertEqual(39, len(consistency["errors"]))
        shutdown = load_json(ROOT / replay["shutdown_evidence"]["path"])
        self.assertEqual("PASS", shutdown["result"])
        authorization = load_json(ROOT / replay["authorization_summary"]["path"])
        self.assertEqual("FAIL", authorization["result"])
        self.assertFalse(authorization["hardware_actions_executed_by_summarizer"])
        stationary = load_json(ROOT / replay["stationary_summary"]["path"])
        self.assertEqual("PENDING_HW", stationary["result"])
        self.assertFalse(stationary["hardware_actions_executed"])
        self.assertFalse(replay["r39_interpretation"]["coverage_claimed"])
        self.assertEqual("PENDING_HW", replay["r39_interpretation"]["HARDWARE_ACCEPTANCE"])
        self.assertEqual(0, replay["r39_interpretation"]["stage66_attempt_count"])


if __name__ == "__main__":
    unittest.main()
