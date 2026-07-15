from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "evidence/generated/p7_r40_diagnostic_pass.json"
PACKAGE = ROOT / "evidence/generated/p7_r40_diagnostic_pass_package"
REPLAY = ROOT / "evidence/generated/p7_r40_summarizer_replay"
REPLAY_RESULT = ROOT / "evidence/generated/p7_r40_summarizer_replay_result.json"
EXPECTED_ORDINALS = [1, 2, 3, 4, *range(55, 66)]
EXPECTED_RAW_TREE = "2702bb0019ddb5899a82c6aa8d6eea775612168a8e0d4d962f0c5fee0db270a2"
EXPECTED_LEDGER = "756c83030a6224b0381b7a90f0bf9085e3fe59eebe09957a9b68008ae9ca77a5"
EXPECTED_SHUTDOWN = "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810"


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
    test: unittest.TestCase, record: dict[str, object], *, root: Path = ROOT
) -> Path:
    path = root / str(record["path"])
    test.assertTrue(path.is_file(), path)
    test.assertFalse(path.is_symlink(), path)
    test.assertEqual(record["bytes"], path.stat().st_size)
    test.assertEqual(record["sha256"], sha256(path))
    return path


class P7R40DiagnosticPassPackageTests(unittest.TestCase):
    def test_portable_package_and_payload_manifest_are_hash_exact(self) -> None:
        summary = load_json(SUMMARY)
        portable = summary["portable_package"]
        self.assertIsInstance(portable, dict)
        full_tree = tree_record(PACKAGE)
        for key in ("file_count", "byte_count", "partial_file_count", "tree_sha256"):
            self.assertEqual(portable[key], full_tree[key])
        self.assertEqual(129, full_tree["file_count"])
        self.assertEqual(0, full_tree["partial_file_count"])

        manifest = load_json(PACKAGE / "package_manifest.json")
        payload_tree = tree_record(PACKAGE, exclude={"package_manifest.json"})
        self.assertTrue(manifest["manifest_excludes_itself"])
        for key in ("file_count", "byte_count", "partial_file_count", "tree_sha256"):
            self.assertEqual(manifest[key], payload_tree[key])
        self.assertEqual(manifest["files"], payload_tree["files"])

        direct_records = (
            summary["ledger"],
            {
                "path": summary["stages"]["manifest_path"],
                "sha256": summary["stages"]["manifest_sha256"],
                "bytes": (ROOT / summary["stages"]["manifest_path"]).stat().st_size,
            },
            {
                "path": summary["raw_evidence"]["manifest_path"],
                "sha256": summary["raw_evidence"]["manifest_sha256"],
                "bytes": (ROOT / summary["raw_evidence"]["manifest_path"]).stat().st_size,
            },
            {
                "path": summary["historical_preflight_freeze"]["manifest_path"],
                "sha256": summary["historical_preflight_freeze"]["manifest_sha256"],
                "bytes": (
                    ROOT / summary["historical_preflight_freeze"]["manifest_path"]
                ).stat().st_size,
            },
            {
                "path": summary["summarizer_replay"]["result_path"],
                "sha256": summary["summarizer_replay"]["result_sha256"],
                "bytes": (ROOT / summary["summarizer_replay"]["result_path"]).stat().st_size,
            },
        )
        for record in direct_records:
            self.assertIsInstance(record, dict)
            assert_file_record(self, record)

    def test_ledger_is_exact_completed_zero_coverage_diagnostic(self) -> None:
        summary = load_json(SUMMARY)
        ledger = load_json(PACKAGE / "sequence_execution_ledger.json")
        self.assertEqual(EXPECTED_LEDGER, sha256(PACKAGE / "sequence_execution_ledger.json"))
        self.assertEqual("DIAGNOSTIC_PASS", ledger["status"])
        self.assertEqual("DIAGNOSTIC_SUFFIX_55", ledger["plan_mode"])
        self.assertEqual(summary["source_commit"], ledger["source_commit"])
        self.assertEqual(EXPECTED_ORDINALS, ledger["full_stage_ordinals"])
        self.assertEqual(15, ledger["attempt_count"])
        self.assertEqual(15, ledger["completed_stage_count"])
        self.assertEqual(15, ledger["next_stage_index"])
        self.assertFalse(ledger["coverage_claimed"])
        self.assertEqual("PENDING_HW", ledger["HARDWARE_ACCEPTANCE"])
        self.assertFalse(ledger["network_used"])
        self.assertFalse(ledger["motion_used"])
        self.assertNotIn(66, ledger["full_stage_ordinals"])

        attempts = ledger["attempts"]
        self.assertEqual(EXPECTED_ORDINALS, [item["full_stage_ordinal"] for item in attempts])
        for attempt_number, attempt in enumerate(attempts, 1):
            self.assertEqual(attempt_number, attempt["attempt"])
            self.assertEqual("TERMINAL", attempt["state"])
            self.assertEqual("PASS", attempt["result"])
            self.assertEqual([], attempt["failures"])
            process = attempt["process"]
            self.assertEqual(0, process["returncode"])
            self.assertFalse(process["timed_out"])
            self.assertTrue(process["process_tree_reaped"])
            self.assertTrue(process["containment_closed"])
            self.assertEqual(0, process["descendant_count_after"])
            shutdown = attempt["shutdown_after"]
            self.assertTrue(shutdown["present"])
            self.assertTrue(shutdown["passed"])
            self.assertEqual(0, shutdown["returncode"])
            self.assertTrue(shutdown["tfdu_shutdown_programmed_exact"])
            self.assertEqual("1", shutdown["p7_tcl_programming_attempted"])
            self.assertEqual("PASS", shutdown["p7_shutdown_result"])

        contract = summary["diagnostic_contract"]
        self.assertTrue(contract["diagnostic_only"])
        self.assertFalse(contract["coverage_claimed"])
        self.assertFalse(contract["formal_acceptance_coverage_contributed"])
        self.assertFalse(contract["stationary_allowed"])
        self.assertEqual(0, contract["stage66_attempt_count"])
        self.assertFalse(contract["stationary_started"])
        self.assertEqual("PENDING_HW", contract["HARDWARE_ACCEPTANCE"])
        self.assertEqual("NOT_RUN", summary["STATIONARY_30MIN"])

    def test_exact_stage_summaries_and_raw_results_are_losslessly_archived(self) -> None:
        manifest = load_json(PACKAGE / "stage_evidence_manifest.json")
        self.assertEqual(15, manifest["stage_count"])
        self.assertEqual(EXPECTED_ORDINALS, manifest["stage_ordinals"])
        rows = manifest["stage_rows"]
        self.assertEqual(EXPECTED_ORDINALS, [row["ordinal"] for row in rows])

        summary_archive = manifest["summary_archive"]
        summary_zip = PACKAGE / str(summary_archive["path"])
        self.assertEqual(summary_archive["bytes"], summary_zip.stat().st_size)
        self.assertEqual(summary_archive["sha256"], sha256(summary_zip))
        summary_entries = {entry["archive_path"]: entry for entry in summary_archive["entries"]}
        self.assertEqual(15, len(summary_entries))
        with zipfile.ZipFile(summary_zip) as archive:
            self.assertEqual(sorted(summary_entries), sorted(archive.namelist()))
            for row in rows:
                name = row["summary_archive_path"]
                data = archive.read(name)
                self.assertEqual(row["summary_bytes"], len(data))
                self.assertEqual(row["summary_sha256"], sha256_bytes(data))
                self.assertEqual(summary_entries[name]["bytes"], len(data))
                self.assertEqual(summary_entries[name]["sha256"], sha256_bytes(data))
                stage = json.loads(data.decode("utf-8", errors="strict"))
                ordinal = row["ordinal"]
                key = "P7_JTAG_AXI_SAFE_STAGE" if ordinal <= 61 else "P7_PS_APPLICATION_SAFE_STAGE"
                self.assertEqual("PASS", stage[key])
                self.assertEqual([], stage["stage_validation_errors"])
                if ordinal >= 62:
                    self.assertEqual([], stage["ps_failures"])
                acceptance = stage.get("HARDWARE_ACCEPTANCE", stage.get("hardware_acceptance"))
                self.assertEqual("PENDING_HW", acceptance)
                for shutdown_name in ("shutdown_before", "shutdown_after"):
                    shutdown = stage[shutdown_name]
                    self.assertTrue(shutdown["attempted"])
                    self.assertTrue(shutdown["programming_attempted"])
                    self.assertTrue(shutdown["passed"])
                    self.assertEqual(0, shutdown["returncode"])
                    self.assertFalse(shutdown["timed_out"])
                    self.assertTrue(shutdown["process_tree_reaped"])
                    self.assertTrue(shutdown["containment_closed"])
                    self.assertEqual(0, shutdown["descendant_count_after"])

        raw_archive = manifest["raw_result_archive"]
        raw_zip = PACKAGE / str(raw_archive["path"])
        self.assertEqual(raw_archive["bytes"], raw_zip.stat().st_size)
        self.assertEqual(raw_archive["sha256"], sha256(raw_zip))
        raw_entries = {entry["archive_path"]: entry for entry in raw_archive["entries"]}
        self.assertEqual(15, len(raw_entries))
        with zipfile.ZipFile(raw_zip) as archive:
            self.assertEqual(sorted(raw_entries), sorted(archive.namelist()))
            for name, entry in raw_entries.items():
                data = archive.read(name)
                self.assertEqual(entry["bytes"], len(data))
                self.assertEqual(entry["sha256"], sha256_bytes(data))
                self.assertIn("PASS", data.decode("utf-8", errors="strict"))

    def test_shutdown_and_support_records_are_directly_hash_exact(self) -> None:
        summary = load_json(SUMMARY)
        manifest = load_json(PACKAGE / "stage_evidence_manifest.json")
        support = manifest["support_records"]
        self.assertEqual(49, len(support))
        before = [record for record in support if record["kind"] == "shutdown_before"]
        after = [record for record in support if record["kind"] == "shutdown_after"]
        preflight = [record for record in support if record["kind"] == "preflight_result"]
        raw_manifests = [record for record in support if record["kind"] == "raw_evidence_manifest"]
        self.assertEqual(15, len(before))
        self.assertEqual(15, len(after))
        self.assertEqual(15, len(preflight))
        self.assertEqual(4, len(raw_manifests))
        for record in support:
            path = assert_file_record(self, record, root=PACKAGE)
            if record["kind"] in {"shutdown_before", "shutdown_after"}:
                text = path.read_text(encoding="utf-8", errors="strict")
                self.assertIn("P7_TCL_PROGRAMMING_ATTEMPTED=1", text)
                self.assertIn("P7_SHUTDOWN_RESULT=PASS", text)
                self.assertIn("TFDU_SHUTDOWN_PROGRAMMED=", text)
        shutdown = summary["shutdown"]
        self.assertEqual(15, shutdown["shutdown_before_pass_count"])
        self.assertEqual(15, shutdown["shutdown_after_pass_count"])
        self.assertEqual(EXPECTED_SHUTDOWN, shutdown["shutdown_artifact_sha256"])
        self.assertFalse(shutdown["independent_recovery_required"])
        self.assertFalse(shutdown["independent_recovery_run"])
        self.assertTrue(shutdown["safe_shutdown_complete"])

    def test_original_797mb_tree_has_complete_content_addressed_inventory(self) -> None:
        summary = load_json(SUMMARY)
        raw = load_json(PACKAGE / "original_raw_tree_manifest.json")
        self.assertEqual(836, raw["file_count"])
        self.assertEqual(797132623, raw["byte_count"])
        self.assertEqual(0, raw["partial_file_count"])
        self.assertEqual(EXPECTED_RAW_TREE, raw["tree_sha256"])
        self.assertFalse(summary["raw_evidence"]["portable_package_embeds_entire_raw_tree"])
        self.assertEqual(raw["file_count"], summary["raw_evidence"]["file_count"])
        self.assertEqual(raw["byte_count"], summary["raw_evidence"]["byte_count"])
        self.assertEqual(raw["tree_sha256"], summary["raw_evidence"]["tree_sha256"])

        records = raw["files"]
        self.assertEqual(raw["file_count"], len(records))
        self.assertEqual(
            sorted(record["path"] for record in records),
            [record["path"] for record in records],
        )
        self.assertEqual(raw["byte_count"], sum(record["bytes"] for record in records))
        canonical = "".join(
            f"{record['path']}\t{record['bytes']}\t{record['sha256']}\n"
            for record in records
        )
        self.assertEqual(raw["tree_sha256"], hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        by_path = {record["path"]: record for record in records}
        self.assertEqual(EXPECTED_LEDGER, by_path["sequence_execution_ledger.json"]["sha256"])
        self.assertIn("062_p7_ps_functional/p7_ps_application_stage_summary.json", by_path)
        self.assertIn("065_p7_ps_queue/p7_ps_application_stage_summary.json", by_path)
        self.assertFalse(any(path.endswith(".partial") for path in by_path))

    def test_historical_inputs_and_immutable_artifacts_are_frozen(self) -> None:
        summary = load_json(SUMMARY)
        history = load_json(PACKAGE / "historical_preflight_inputs/manifest.json")
        self.assertEqual(summary["source_commit"], history["source_commit"])
        self.assertEqual("DIAGNOSTIC_PASS", history["result"])
        self.assertFalse(history["coverage_claimed"])
        self.assertEqual("PENDING_HW", history["HARDWARE_ACCEPTANCE"])
        self.assertEqual(69, history["file_count"])
        self.assertEqual(69, len(history["files"]))

        roles: list[str] = []
        for record in history["files"]:
            frozen = ROOT / str(record["frozen_path"])
            self.assertTrue(frozen.is_file(), frozen)
            self.assertFalse(frozen.is_symlink(), frozen)
            self.assertEqual(record["bytes"], frozen.stat().st_size)
            self.assertEqual(record["sha256"], sha256(frozen))
            roles.append(record["role"])
        self.assertEqual(15, sum(role.startswith("stage_authorization_") for role in roles))
        self.assertEqual(1, roles.count("sequence_plan"))
        for required in (
            "historical_sequence_executor",
            "historical_jtag_stage_wrapper",
            "historical_ps_stage_wrapper",
            "historical_shutdown_wrapper",
            "historical_shutdown_tcl",
            "historical_summarizer",
            "jtag_bitstream",
            "jtag_ltx",
            "ps_bitstream",
            "xsa",
            "elf",
            "linker_map",
            "ps7_init",
            "shutdown_bitstream",
        ):
            self.assertIn(required, roles)

        artifacts = summary["immutable_artifacts"]
        role_hashes = {record["role"]: record["sha256"] for record in history["files"]}
        self.assertEqual(artifacts["jtag_bitstream_sha256"], role_hashes["jtag_bitstream"])
        self.assertEqual(artifacts["jtag_ltx_sha256"], role_hashes["jtag_ltx"])
        self.assertEqual(artifacts["ps_bitstream_sha256"], role_hashes["ps_bitstream"])
        self.assertEqual(artifacts["xsa_sha256"], role_hashes["xsa"])
        self.assertEqual(artifacts["elf_sha256"], role_hashes["elf"])
        self.assertEqual(artifacts["linker_map_sha256"], role_hashes["linker_map"])
        self.assertEqual(artifacts["ps7_init_sha256"], role_hashes["ps7_init"])
        self.assertEqual(EXPECTED_SHUTDOWN, role_hashes["shutdown_bitstream"])

    def test_outer_exit_code_observation_is_not_fabricated(self) -> None:
        summary = load_json(SUMMARY)
        observation = load_json(PACKAGE / "executor/outer_monitor_observation.json")
        stdout = load_json(PACKAGE / "executor/sequence_executor.stdout.log")
        stderr = PACKAGE / "executor/sequence_executor.stderr.log"
        self.assertTrue(observation["tool_cell_exit_code_observed"])
        self.assertEqual(0, observation["tool_cell_exit_code"])
        self.assertFalse(observation["executor_process_exit_code_observed"])
        self.assertIsNone(observation["executor_process_exit_code"])
        self.assertIn("no process exit code is inferred", observation["missing_reason"])
        self.assertEqual("DIAGNOSTIC_PASS", observation["semantic_result"])
        self.assertTrue(observation["ledger_child_returncodes_all_zero"])
        self.assertEqual(0, stderr.stat().st_size)
        self.assertEqual("DIAGNOSTIC_PASS", stdout["P7_AUTHORIZED_HARDWARE_SEQUENCE"])
        self.assertFalse(stdout["coverage_claimed"])
        self.assertEqual("PENDING_HW", stdout["HARDWARE_ACCEPTANCE"])
        self.assertEqual([], stdout["validation_errors"])
        self.assertEqual(EXPECTED_LEDGER, stdout["execution_ledger"]["sha256"])
        self.assertFalse(summary["execution"]["executor_process_exit_code_observed"])
        self.assertIsNone(summary["execution"]["executor_process_exit_code"])

    def test_summarizer_replay_fails_closed_without_reclassifying_r40(self) -> None:
        replay = load_json(REPLAY_RESULT)
        tree = tree_record(REPLAY)
        for key in ("file_count", "byte_count", "partial_file_count", "tree_sha256"):
            self.assertEqual(replay["output_tree"][key], tree[key])
        self.assertEqual(1, replay["invocation_count"])
        self.assertTrue(replay["summarizer_exit_code_observed"])
        self.assertEqual(1, replay["summarizer_exit_code"])
        self.assertFalse(replay["hardware_actions_executed_by_summarizer"])
        self.assertEqual(
            "EXPECTED_FAIL_CLOSED_FORMAL_ACCEPTANCE_SUMMARY_OVER_DIAGNOSTIC_ONLY_SUFFIX",
            replay["interpretation"],
        )

        expected = {
            "final_summary": ("FAIL", 160),
            "evidence_consistency": ("FAIL", 5),
            "shutdown_evidence": ("PASS", 0),
            "authorization_summary": ("FAIL", 0),
            "stationary_summary": ("PENDING_HW", 0),
        }
        for key, (result, error_count) in expected.items():
            record = replay[key]
            path = assert_file_record(self, record)
            payload = load_json(path)
            self.assertEqual(result, record["result"])
            self.assertEqual(error_count, record["error_count"])
            self.assertEqual(result, payload["result"])
        interpretation = replay["r40_interpretation"]
        self.assertEqual("DIAGNOSTIC_PASS", interpretation["diagnostic_status"])
        self.assertFalse(interpretation["coverage_claimed"])
        self.assertFalse(interpretation["formal_acceptance_coverage_contributed"])
        self.assertEqual(0, interpretation["stage66_attempt_count"])
        self.assertFalse(interpretation["stationary_started"])
        self.assertEqual("PENDING_HW", interpretation["HARDWARE_ACCEPTANCE"])

    def test_package_and_archives_reject_tampering(self) -> None:
        summary = load_json(SUMMARY)
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "package"
            shutil.copytree(PACKAGE, copied)
            ledger = copied / "sequence_execution_ledger.json"
            ledger.write_bytes(ledger.read_bytes() + b" ")
            tampered_tree = tree_record(copied)
            self.assertNotEqual(summary["portable_package"]["tree_sha256"], tampered_tree["tree_sha256"])
            self.assertNotEqual(summary["ledger"]["sha256"], sha256(ledger))

        manifest = load_json(PACKAGE / "stage_evidence_manifest.json")
        first = manifest["summary_archive"]["entries"][0]
        with zipfile.ZipFile(PACKAGE / "stage_summaries.zip") as archive:
            tampered = archive.read(first["archive_path"]) + b"tamper"
        self.assertNotEqual(first["bytes"], len(tampered))
        self.assertNotEqual(first["sha256"], sha256_bytes(tampered))


if __name__ == "__main__":
    unittest.main()
