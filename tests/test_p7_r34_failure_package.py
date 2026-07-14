from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "evidence" / "generated" / "p7_r34_formal_failure.json"
PACKAGE = ROOT / "evidence" / "generated" / "p7_r34_failure_package"
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON root is not an object: {path}")
    return value


def package_tree(package_root: Path = PACKAGE) -> tuple[int, int, str]:
    records: list[str] = []
    total_bytes = 0
    files = sorted(path for path in package_root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(package_root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        records.append(f"{relative}\t{size}\t{sha256(path)}\n")
    digest = hashlib.sha256("".join(records).encode("utf-8")).hexdigest()
    return len(files), total_bytes, digest


class P7R34FailurePackageTests(unittest.TestCase):
    def test_portable_package_is_hash_exact(self) -> None:
        summary = load_json(SUMMARY)
        package = summary["portable_package"]
        self.assertIsInstance(package, dict)
        count, byte_count, digest = package_tree()
        self.assertEqual(package["file_count"], count)
        self.assertEqual(package["byte_count"], byte_count)
        self.assertEqual(package["tree_sha256"], digest)

        for section, key in (
            ("ledger", "path"),
            ("stage62", "summary_path"),
            ("independent_recovery", "summary_path"),
            ("historical_preflight_freeze", "manifest_path"),
        ):
            record = summary[section]
            self.assertIsInstance(record, dict)
            path = ROOT / str(record[key])
            self.assertTrue(path.is_file(), path)
            self.assertEqual(record["sha256" if section == "ledger" else "summary_sha256" if section in {"stage62", "independent_recovery"} else "manifest_sha256"], sha256(path))

    def test_ledger_is_contiguous_pass_1_to_61_then_fail_62(self) -> None:
        summary = load_json(SUMMARY)
        ledger = load_json(PACKAGE / "sequence_execution_ledger.json")
        self.assertEqual("FAIL", ledger["status"])
        self.assertEqual("FULL_ACCEPTANCE", ledger["plan_mode"])
        self.assertEqual(summary["source_commit"], ledger["source_commit"])
        self.assertEqual(62, ledger["attempt_count"])
        self.assertEqual(61, ledger["completed_stage_count"])
        self.assertEqual(61, ledger["failed_stage_index"])
        self.assertEqual(list(range(1, 67)), ledger["full_stage_ordinals"])
        attempts = ledger["attempts"]
        self.assertIsInstance(attempts, list)
        self.assertEqual(62, len(attempts))
        self.assertEqual(list(range(1, 63)), [item["full_stage_ordinal"] for item in attempts])
        for index, attempt in enumerate(attempts[:61], 1):
            self.assertEqual(index, attempt["attempt"])
            self.assertEqual("TERMINAL", attempt["state"])
            self.assertEqual("PASS", attempt["result"])
            self.assertTrue(attempt["shutdown_after"]["passed"])
            self.assertTrue(SHA256_RE.fullmatch(attempt["summary_file"]["sha256"]))
        failed = attempts[61]
        self.assertEqual("p7_ps_functional", failed["stage_id"])
        self.assertEqual("FAIL", failed["result"])
        self.assertTrue(failed["shutdown_after"]["passed"])
        self.assertEqual(summary["stage62"]["summary_sha256"], failed["summary_file"]["sha256"])
        self.assertFalse(any(item["full_stage_ordinal"] == 66 for item in attempts))
        self.assertEqual(0, summary["stationary"]["attempt_count"])
        self.assertFalse(summary["stationary"]["started"])

    def test_stage62_failed_before_candidate_and_recovery_is_separate(self) -> None:
        summary = load_json(SUMMARY)
        stage = load_json(PACKAGE / "stage62" / "p7_ps_application_stage_summary.json")
        self.assertEqual("FAIL_STAGE", stage["P7_PS_APPLICATION_SAFE_STAGE"])
        self.assertEqual("PENDING_HW", stage["HARDWARE_ACCEPTANCE"])
        self.assertEqual("P7_PS_APPLICATION_STAGE", stage["execution_scope"])
        self.assertFalse(stage["stage62_attempted"])
        self.assertFalse(stage["stage62_executed"])
        self.assertFalse(stage["stage62_completed"])
        self.assertFalse(stage["programmed_candidate"])
        self.assertFalse(stage["started_ps_elf"])
        self.assertTrue(stage["shutdown_before"]["passed"])
        self.assertTrue(stage["shutdown_after"]["passed"])

        raw = (PACKAGE / "stage62" / "p7_ps_application_raw_result.log").read_text(
            encoding="utf-8", errors="strict"
        )
        self.assertEqual(
            "P7_PS_STAGE_RESULT=FAIL\n"
            "P7_PS_STAGE_ERROR=P7 authorization mismatch for P7_EXECUTION_SCOPE "
            "expected=P7_PS_APPLICATION_STAGE observed=\n",
            raw,
        )
        self.assertEqual(summary["stage62"]["raw_result_sha256"], sha256(PACKAGE / "stage62" / "p7_ps_application_raw_result.log"))

        recovery = (PACKAGE / "recovery" / "program_tfdu_shutdown_safe.summary.txt").read_text(
            encoding="utf-8", errors="strict"
        )
        self.assertIn("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS", recovery)
        self.assertIn("SHUTDOWN_EXIT=0", recovery)
        self.assertIn("TFDU_SHUTDOWN_PROGRAMMED_SEEN=1", recovery)
        self.assertTrue(summary["independent_recovery"]["separate_from_stage_result"])
        self.assertEqual("IMMUTABLE_FAIL_NEVER_RESUME", summary["run_status"])

    def test_historical_authorization_proves_both_missing_contract_fields(self) -> None:
        summary = load_json(SUMMARY)
        history = load_json(PACKAGE / "historical_preflight_inputs" / "manifest.json")
        self.assertEqual(summary["source_commit"], history["source_commit"])
        self.assertEqual("FAIL_STAGE", history["result"])
        self.assertFalse(history["coverage_claimed"])
        self.assertEqual(12, len(history["files"]))
        for record in history["files"]:
            frozen = PACKAGE / "historical_preflight_inputs" / Path(record["frozen_path"]).name
            self.assertTrue(frozen.is_file(), frozen)
            self.assertEqual(record["bytes"], frozen.stat().st_size)
            self.assertEqual(record["sha256"], sha256(frozen))

        authorization = next(
            PACKAGE.glob("historical_preflight_inputs/p7_stage_001_authorization_*.txt")
        ).read_text(encoding="utf-8", errors="strict")
        lines = authorization.splitlines()
        self.assertEqual(1, lines.count("P7_PS_MODE=functional"))
        self.assertFalse(any(line.startswith("P7_EXECUTION_SCOPE=") for line in lines))
        self.assertFalse(any(line.startswith("P7_RUN_ID=") for line in lines))
        contract = summary["authorization_contract"]
        self.assertEqual(0, contract["observed_execution_scope_field_count"])
        self.assertEqual(0, contract["observed_run_id_field_count"])
        self.assertEqual(
            "CONFIRMED_GENERATOR_AND_OFFLINE_VALIDATOR_AUTHORIZATION_CONTRACT_GAP",
            contract["failure_root_cause"],
        )

    def test_portable_tree_and_raw_hashes_reject_tampering(self) -> None:
        summary = load_json(SUMMARY)
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "package"
            shutil.copytree(PACKAGE, copied)
            raw = copied / "stage62" / "p7_ps_application_raw_result.log"
            raw.write_bytes(raw.read_bytes() + b"tamper\n")
            _count, _bytes, digest = package_tree(copied)
            self.assertNotEqual(summary["portable_package"]["tree_sha256"], digest)
            self.assertNotEqual(summary["stage62"]["raw_result_sha256"], sha256(raw))


if __name__ == "__main__":
    unittest.main()
