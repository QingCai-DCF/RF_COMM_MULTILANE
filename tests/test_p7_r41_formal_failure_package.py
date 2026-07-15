from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "evidence/generated/p7_r41_formal_failure.json"
PACKAGE = ROOT / "evidence/generated/p7_r41_formal_failure_package"
REPLAY_RESULT = ROOT / "evidence/generated/p7_r41_summarizer_replay_result.json"
EXPECTED_SOURCE = "946ccbad66d64d715ad6745449b95f6c261ddf76"
EXPECTED_LEDGER = "a86ec2a8e326a5354e9e79abed71ca938a3aa7a54b6936bc961beaf668ddba64"
EXPECTED_RAW_TREE = "3501544a5fcd13458cbeb280e3e0a617430e8d8671ef8be5d90f5b6e7ebefa91"
EXPECTED_PACKAGE_TREE = "bf710e4207146ceb27476ab86b91d9e31bc61ef63716bc48ce41ea96f1095cb7"
EXPECTED_SHUTDOWN = "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810"
EXPECTED_FAILING_TCL = "9c0251d30b723c015b87e7fc399212d719c75f70a7f6fb57da2d2888868fd5ec"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON root is not an object: {path}")
    return value


def tree_record(root: Path, *, exclude: set[str] | None = None) -> dict[str, object]:
    excluded = exclude or set()
    files = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.relative_to(root).as_posix() not in excluded
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files
    ]
    canonical = "".join(
        f"{record['path']}\t{record['bytes']}\t{record['sha256']}\n"
        for record in records
    )
    return {
        "file_count": len(records),
        "byte_count": sum(int(record["bytes"]) for record in records),
        "partial_file_count": sum(
            str(record["path"]).endswith(".partial") for record in records
        ),
        "tree_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "files": records,
    }


def assert_file_record(
    test: unittest.TestCase, record: dict[str, object], *, root: Path = PACKAGE
) -> Path:
    path = root / str(record["path"])
    test.assertTrue(path.is_file(), path)
    test.assertFalse(path.is_symlink(), path)
    test.assertEqual(record["bytes"], path.stat().st_size)
    test.assertEqual(record["sha256"], sha256(path))
    return path


class P7R41FormalFailurePackageTests(unittest.TestCase):
    def test_portable_package_manifest_is_hash_exact(self) -> None:
        summary = load_json(SUMMARY)
        full_tree = tree_record(PACKAGE)
        portable = summary["portable_package"]
        self.assertIsInstance(portable, dict)
        for key in ("file_count", "byte_count", "partial_file_count", "tree_sha256"):
            self.assertEqual(portable[key], full_tree[key])
        self.assertEqual(220, full_tree["file_count"])
        self.assertEqual(76_154_254, full_tree["byte_count"])
        self.assertEqual(0, full_tree["partial_file_count"])
        self.assertEqual(EXPECTED_PACKAGE_TREE, full_tree["tree_sha256"])

        manifest = load_json(PACKAGE / "package_manifest.json")
        payload_tree = tree_record(PACKAGE, exclude={"package_manifest.json"})
        self.assertTrue(manifest["manifest_excludes_itself"])
        for key in ("file_count", "byte_count", "partial_file_count", "tree_sha256", "files"):
            self.assertEqual(manifest[key], payload_tree[key])

    def test_ledger_freezes_stages_1_to_65_pass_and_stage66_fail(self) -> None:
        ledger_path = PACKAGE / "sequence_execution_ledger.json"
        self.assertEqual(EXPECTED_LEDGER, sha256(ledger_path))
        ledger = load_json(ledger_path)
        self.assertEqual("FAIL", ledger["status"])
        self.assertEqual("FULL_ACCEPTANCE", ledger["plan_mode"])
        self.assertEqual(EXPECTED_SOURCE, ledger["source_commit"])
        self.assertEqual(list(range(1, 67)), ledger["full_stage_ordinals"])
        self.assertEqual(66, ledger["attempt_count"])
        self.assertEqual(65, ledger["completed_stage_count"])
        self.assertEqual(65, ledger["next_stage_index"])
        self.assertFalse(ledger["network_used"])
        self.assertFalse(ledger["motion_used"])

        attempts = ledger["attempts"]
        self.assertEqual(list(range(1, 67)), [item["full_stage_ordinal"] for item in attempts])
        self.assertEqual(["PASS"] * 65, [item["result"] for item in attempts[:65]])
        failed = attempts[65]
        self.assertEqual("FAIL", failed["result"])
        self.assertEqual("p7_ps_stationary", failed["stage_id"])
        self.assertEqual(1, failed["process"]["returncode"])
        self.assertFalse(failed["process"]["timed_out"])
        self.assertTrue(failed["process"]["process_tree_reaped"])
        self.assertTrue(failed["process"]["containment_closed"])
        self.assertEqual(0, failed["process"]["descendant_count_after"])
        self.assertTrue(failed["shutdown_after"]["passed"])
        self.assertEqual(0, failed["shutdown_after"]["returncode"])

    def test_all_stage_summaries_and_raw_results_are_exactly_archived(self) -> None:
        manifest = load_json(PACKAGE / "stage_evidence_manifest.json")
        self.assertEqual(66, manifest["stage_count"])
        self.assertEqual(65, manifest["pass_count"])
        self.assertEqual(1, manifest["fail_count"])
        self.assertEqual(66, manifest["failed_ordinal"])
        rows = manifest["stage_rows"]
        self.assertEqual(list(range(1, 67)), [row["ordinal"] for row in rows])

        summary_archive = manifest["summary_archive"]
        summary_zip = assert_file_record(self, summary_archive)
        summary_entries = {entry["archive_path"]: entry for entry in summary_archive["entries"]}
        self.assertEqual(66, len(summary_entries))
        with zipfile.ZipFile(summary_zip) as archive:
            self.assertEqual(sorted(summary_entries), sorted(archive.namelist()))
            for row in rows:
                data = archive.read(row["summary_archive_path"])
                self.assertEqual(row["summary_bytes"], len(data))
                self.assertEqual(row["summary_sha256"], sha256_bytes(data))
                summary = json.loads(data.decode("utf-8", errors="strict"))
                ordinal = row["ordinal"]
                key = "P7_JTAG_AXI_SAFE_STAGE" if ordinal <= 61 else "P7_PS_APPLICATION_SAFE_STAGE"
                expected = "PASS" if ordinal <= 65 else "FAIL_STAGE"
                self.assertEqual(expected, summary[key])
                acceptance = summary.get("HARDWARE_ACCEPTANCE", summary.get("hardware_acceptance"))
                self.assertEqual("PENDING_HW", acceptance)
                self.assertTrue(summary["shutdown_before"]["passed"])
                self.assertTrue(summary["shutdown_after"]["passed"])

        raw_archive = manifest["raw_archive"]
        raw_zip = assert_file_record(self, raw_archive)
        raw_entries = {entry["archive_path"]: entry for entry in raw_archive["entries"]}
        self.assertEqual(66, len(raw_entries))
        with zipfile.ZipFile(raw_zip) as archive:
            self.assertEqual(sorted(raw_entries), sorted(archive.namelist()))
            for row in rows:
                data = archive.read(row["raw_archive_path"])
                self.assertEqual(row["raw_bytes"], len(data))
                self.assertEqual(row["raw_sha256"], sha256_bytes(data))
                text = data.decode("utf-8", errors="strict")
                if row["ordinal"] <= 65:
                    self.assertIn("PASS", text)
                else:
                    self.assertIn("P7_PS_STAGE_RESULT=FAIL", text)
                    self.assertIn("P7_PS_STAGE_ERROR=integer value too large to represent", text)

    def test_stage66_is_one_incomplete_stationary_attempt_with_safe_shutdown(self) -> None:
        summary = load_json(PACKAGE / "stage66/p7_ps_application_stage_summary.json")
        raw = (PACKAGE / "stage66/p7_ps_application_raw_result.log").read_text(
            encoding="utf-8", errors="strict"
        )
        self.assertEqual("FAIL_STAGE", summary["P7_PS_APPLICATION_SAFE_STAGE"])
        self.assertEqual("PENDING_HW", summary["HARDWARE_ACCEPTANCE"])
        self.assertTrue(summary["shutdown_before"]["passed"])
        self.assertTrue(summary["shutdown_after"]["passed"])
        self.assertEqual(1, raw.count("P7_SAMPLE_"))
        self.assertEqual(4, raw.count("P7_STATIONARY_OBJECT_"))
        self.assertIn("P7_PS_STAGE_RESULT=FAIL", raw)
        self.assertIn("P7_PS_STAGE_ERROR=integer value too large to represent", raw)
        self.assertNotIn("P7_PS_STAGE_RESULT=PASS", raw)
        self.assertNotIn("P7_SAMPLE_00060=", raw)

        classification = load_json(SUMMARY)
        stationary = classification["stationary"]
        self.assertEqual(1, stationary["authorized_attempt_count"])
        self.assertTrue(stationary["attempt_consumed"])
        self.assertFalse(stationary["future_attempt_permitted_under_current_constraint"])
        self.assertFalse(stationary["completed_1800_seconds"])
        self.assertFalse(stationary["pass"])
        self.assertEqual("PENDING_HW", classification["HARDWARE_ACCEPTANCE"])
        self.assertEqual("FAIL_INCOMPLETE", classification["STATIONARY_30MIN"])

    def test_independent_recovery_pass_is_separate_from_stage66_fail(self) -> None:
        recovery = (PACKAGE / "recovery/program_tfdu_shutdown_safe.summary.txt").read_text(
            encoding="utf-8", errors="strict"
        )
        stdout = (PACKAGE / "recovery/program_tfdu_shutdown_safe.stdout.log").read_text(
            encoding="utf-8", errors="strict"
        )
        self.assertIn("HARDWARE_AUTHORIZATION_EXIT=0", recovery)
        self.assertIn("SHUTDOWN_RAW_EXIT=125", recovery)
        self.assertIn("SHUTDOWN_EXIT=0", recovery)
        self.assertIn("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS", recovery)
        emitted = [line for line in stdout.splitlines() if line.startswith("TFDU_SHUTDOWN_PROGRAMMED ")]
        self.assertEqual(1, len(emitted))
        self.assertEqual(
            EXPECTED_SHUTDOWN,
            sha256(
                PACKAGE
                / "historical_preflight_inputs"
                / next(
                    path.name
                    for path in (PACKAGE / "historical_preflight_inputs").iterdir()
                    if path.name.startswith("shutdown_bitstream_")
                )
            ),
        )
        classification = load_json(SUMMARY)
        self.assertFalse(classification["shutdown"]["recovery_changes_failed_stage_result"])
        self.assertEqual("PASS", classification["shutdown"]["independent_recovery_status"])

    def test_original_834mb_tree_has_complete_content_addressed_inventory(self) -> None:
        raw = load_json(PACKAGE / "original_raw_tree_manifest.json")
        self.assertEqual(1808, raw["file_count"])
        self.assertEqual(834_613_170, raw["byte_count"])
        self.assertEqual(0, raw["partial_file_count"])
        self.assertEqual(EXPECTED_RAW_TREE, raw["tree_sha256"])
        records = raw["files"]
        self.assertEqual(1808, len(records))
        self.assertEqual(sorted(record["path"] for record in records), [record["path"] for record in records])
        canonical = "".join(
            f"{record['path']}\t{record['bytes']}\t{record['sha256']}\n"
            for record in records
        )
        self.assertEqual(EXPECTED_RAW_TREE, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        by_path = {record["path"]: record for record in records}
        self.assertEqual(EXPECTED_LEDGER, by_path["sequence_execution_ledger.json"]["sha256"])
        self.assertIn("066_p7_ps_stationary/p7_ps_application_stage_summary.json", by_path)
        self.assertIn(
            "recovery_shutdown_after_failed_stage066_20260715T114509Z/program_tfdu_shutdown_safe.summary.txt",
            by_path,
        )

    def test_historical_inputs_freeze_all_authorizations_and_runtime_artifacts(self) -> None:
        history = load_json(PACKAGE / "historical_preflight_inputs/manifest.json")
        self.assertEqual(EXPECTED_SOURCE, history["source_commit"])
        self.assertEqual("FORMAL_FAIL", history["result"])
        self.assertFalse(history["coverage_claimed"])
        self.assertEqual("PENDING_HW", history["HARDWARE_ACCEPTANCE"])
        self.assertEqual(126, history["file_count"])
        roles = []
        role_hashes = {}
        for record in history["files"]:
            frozen = ROOT / record["frozen_path"]
            self.assertTrue(frozen.is_file(), frozen)
            self.assertEqual(record["bytes"], frozen.stat().st_size)
            self.assertEqual(record["sha256"], sha256(frozen))
            roles.append(record["role"])
            role_hashes[record["role"]] = record["sha256"]
        self.assertEqual(66, sum(role.startswith("stage_authorization_") for role in roles))
        for required in (
            "sequence_plan",
            "historical_sequence_executor",
            "historical_summarizer",
            "historical_ps_execute_tcl",
            "jtag_bitstream",
            "jtag_ltx",
            "ps_bitstream",
            "xsa",
            "elf",
            "linker_map",
            "ps7_init",
            "shutdown_bitstream",
            "recovery_p4_authorization",
        ):
            self.assertIn(required, roles)
        self.assertEqual(EXPECTED_FAILING_TCL, role_hashes["historical_ps_execute_tcl"])
        self.assertEqual(EXPECTED_SHUTDOWN, role_hashes["shutdown_bitstream"])

    def test_xsct_reproduction_confirms_the_host_tcl_root_cause_and_fix(self) -> None:
        root_cause = load_json(PACKAGE / "root_cause/root_cause.json")
        self.assertEqual(
            "CONFIRMED_HOST_TCL_SIGNED_32_BIT_LATENCY_SORT_OVERFLOW",
            root_cause["status"],
        )
        self.assertEqual(2, root_cause["first_failing_sample_sequence"])
        latencies = [row["latency_ticks"] for row in root_cause["terminal_tick_pairs"]]
        self.assertEqual(
            [17_875_676_347, 26_957_722_756, 51_321_168_692, 45_147_234_789],
            latencies,
        )
        self.assertTrue(all(value > root_cause["signed_32_bit_max"] for value in latencies))
        self.assertTrue(root_cause["xsct_2023_1_old_path_reproduced_exact_error"])
        self.assertTrue(root_cause["xsct_2023_1_fixed_comparator_passed"])
        self.assertFalse(root_cause["hardware_rerun_performed"])
        self.assertFalse(root_cause["acceptance_claimed"])

        old_source = assert_file_record(self, root_cause["files"]["failing_tcl"]).read_text(encoding="utf-8")
        fixed_source = assert_file_record(self, root_cause["files"]["fixed_tcl"]).read_text(encoding="utf-8")
        xsct = assert_file_record(self, root_cause["files"]["xsct_stdout"]).read_text(encoding="utf-8")
        self.assertIn("set sorted [lsort -integer $values]", old_source)
        self.assertIn("set sorted [lsort -command p7_compare_wide_integer $values]", fixed_source)
        self.assertIn("P7_R41_OLD_SORT_ERROR=integer value too large to represent", xsct)
        self.assertIn("P7_R41_FIXED_SORT_RC=0", xsct)
        self.assertIn("P7_R41_WIDE_LATENCY_REPRODUCER=PASS", xsct)

    def test_unique_summarizer_replay_fails_formal_and_passes_shutdown(self) -> None:
        replay = load_json(REPLAY_RESULT)
        self.assertEqual(1, replay["invocation_count"])
        self.assertTrue(replay["summarizer_exit_code_observed"])
        self.assertEqual(1, replay["summarizer_exit_code"])
        self.assertFalse(replay["hardware_actions_executed_by_summarizer"])
        self.assertEqual("FAIL", replay["final_summary"]["result"])
        self.assertEqual("FAIL", replay["stationary_summary"]["result"])
        self.assertEqual("PASS", replay["shutdown_evidence"]["result"])

    def test_content_hashes_reject_ledger_raw_and_recovery_tampering(self) -> None:
        package_manifest = load_json(PACKAGE / "package_manifest.json")
        records = {record["path"]: record for record in package_manifest["files"]}
        targets = (
            "sequence_execution_ledger.json",
            "stage66/p7_ps_application_raw_result.log",
            "recovery/program_tfdu_shutdown_safe.summary.txt",
        )
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            for relative in targets:
                record = records[relative]
                source = PACKAGE / relative
                data = bytearray(source.read_bytes())
                self.assertTrue(data)
                data[len(data) // 2] ^= 1
                destination = temp_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                with self.assertRaises(AssertionError):
                    assert_file_record(self, record, root=temp_root)


if __name__ == "__main__":
    unittest.main()
