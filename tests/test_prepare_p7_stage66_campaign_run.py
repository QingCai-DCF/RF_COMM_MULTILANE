import sys
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import prepare_p7_stage66_campaign_run as subject  # noqa: E402


class PrepareP7Stage66CampaignRunTests(unittest.TestCase):
    def test_only_exact_stage66_ephemeral_evidence_paths_are_ignored(self) -> None:
        ignored = (
            "evidence/generated/p7_stage66_campaign_next_preparation/probe.json",
            "evidence/hardware/p7/stage66_diagnostic_campaign/"
            "p7_stage66_stationary_diagnostic_20260715/campaign_ledger.json",
        )
        visible = (
            "evidence/hardware/p7/stage66_diagnostic_campaign/"
            "p7_stage66_stationary_diagnostic_20260715/campaign_execution.lock",
            "evidence/generated/p7_r59_stage66_campaign_c03_complete_suite_dirty_source_block.json",
        )
        for path in ignored:
            with self.subTest(path=path):
                result = subprocess.run(
                    ["git", "check-ignore", "-q", "--", path],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(0, result.returncode)
        for path in visible:
            with self.subTest(path=path):
                result = subprocess.run(
                    ["git", "check-ignore", "-q", "--", path],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(1, result.returncode)

    def fixture(self, root: Path):
        plan = root / "plan.json"
        ledger = root / "run" / "sequence_execution_ledger.json"
        commit = "a" * 40
        digest = "b" * 64
        argv = subject.build_outer_execution_argv(
            sequence_plan=plan,
            sequence_plan_sha256=digest,
            execution_ledger=ledger,
            source_commit=commit,
        )
        return plan, ledger, commit, digest, argv

    def validate(self, argv, plan, ledger, commit, digest):
        return subject.validate_outer_execution_argv(
            argv,
            sequence_plan=plan,
            sequence_plan_sha256=digest,
            execution_ledger=ledger,
            source_commit=commit,
        )[1]

    def test_exact_outer_argv_has_all_controls_once_and_no_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan, ledger, commit, digest, argv = self.fixture(Path(temp))
            self.assertEqual([], self.validate(argv, plan, ledger, commit, digest))
            self.assertEqual(str(Path(sys.executable).resolve()), argv[0])
            self.assertEqual(str(subject.OUTER_EXECUTOR), argv[1])
            self.assertNotIn("--resume", argv)
            for flag in (
                "--execute-hardware",
                "--shutdown-on-exit",
                "--no-ethernet",
                "--no-motion",
                "--json-summary",
            ):
                self.assertEqual(1, argv.count(flag))

    def test_tree_hash_matches_established_case_insensitive_windows_sort(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Z.txt").write_bytes(b"z")
            (root / "a.txt").write_bytes(b"a")
            record = subject.canonical_tree_record(root)
        self.assertEqual([], record["errors"])
        self.assertEqual(
            "be0a26ae6f2ad503f0e2c1fa77d5a81ed6476166f183f9570bcb4388ef6c275b",
            record["tree_sha256"],
        )

    def test_r54_r57_regression_mutations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan, ledger, commit, digest, argv = self.fixture(Path(temp))
            mutations = []
            omitted = list(argv)
            omitted.remove("--no-ethernet")
            mutations.append(omitted)
            resume = [*argv, "--resume"]
            mutations.append(resume)
            join_path = list(argv)
            join_path[join_path.index("--sequence-plan") + 1] = "Join-Path $root plan.json"
            mutations.append(join_path)
            test_path = list(argv)
            test_path[test_path.index("--execution-ledger") + 1] = "Test-Path ledger.json"
            mutations.append(test_path)
            alias = list(argv)
            alias[0] = "python"
            mutations.append(alias)
            wrong_executor = list(argv)
            wrong_executor[1] = str(ROOT / "tools" / "run_p6_authorized_hardware_sequence.py")
            mutations.append(wrong_executor)
            for mutated in mutations:
                with self.subTest(argv=mutated):
                    self.assertTrue(self.validate(mutated, plan, ledger, commit, digest))

    def test_placeholder_rehearsal_is_zero_auth_zero_attempt_and_regression_complete(self) -> None:
        snapshot = {
            "status": "PASS",
            "errors": [],
            "ledger_sha256": "c" * 64,
            "actual_hardware_attempt_count": 2,
            "campaign_status": "READY",
            "campaign_lock_exists": False,
        }
        identity = {
            "status": "PASS",
            "error_code": "NONE",
            "observed_sha256_by_role": dict(
                subject.helper_identity.EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE
            ),
            "hardware_actions_executed": False,
            "campaign_attempt_created": False,
        }
        environment = {
            "status": "PASS",
            "error_code": "NONE",
            "errors": [],
        }
        build_preflight = {
            "status": "PASS",
            "copy_started": False,
            "destination_paths_absent": True,
            "errors": [],
        }
        with mock.patch.object(subject, "_campaign_snapshot", return_value=snapshot), mock.patch.object(
            subject.helper_identity, "validate_vivado_helper_identity", return_value=identity
        ), mock.patch.object(subject, "_environment_validation", return_value=environment), mock.patch.object(
            subject, "_git_head", return_value="d" * 40
        ), mock.patch.object(
            subject, "inspect_build_materialization", return_value=build_preflight
        ):
            report = subject.placeholder_rehearsal(
                Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat"),
                build_source_root=Path(r"D:\CodexWorktrees\source\RF_COMM_MULTILANE"),
                build_source_commit="e" * 40,
                expected_build_tree_sha256_by_name={
                    "p6_ps_candidate": "1" * 64,
                    "p7_ps_vitis_workspace": "2" * 64,
                },
            )
        self.assertEqual("PASS", report["P7_STAGE66_PREPARATION_DRIVER"])
        self.assertTrue(all(report["fixed_regression_matrix"].values()))
        self.assertFalse(report["hardware_actions_executed"])
        self.assertFalse(report["campaign_attempt_created"])
        self.assertEqual(snapshot, report["campaign_before"])
        self.assertEqual(snapshot, report["campaign_after"])

    def test_build_tree_materialization_is_atomic_hash_exact_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source_root = temp_root / "source"
            destination_root = temp_root / "destination"
            for name, content in (
                ("p6_ps_candidate", b"p6\n"),
                ("p7_ps_vitis_workspace", b"p7\n"),
            ):
                tree = source_root / "build" / name
                (tree / "nested").mkdir(parents=True)
                (tree / "root.bin").write_bytes(content)
                (tree / "nested" / "empty.bin").write_bytes(b"")
            expected = {
                name: subject.canonical_tree_record(source_root / "build" / name)[
                    "tree_sha256"
                ]
                for name in subject.BUILD_MATERIALIZATION_NAMES
            }
            source_commit = "a" * 40
            snapshot = {
                "status": "PASS",
                "errors": [],
                "ledger_sha256": "b" * 64,
                "actual_hardware_attempt_count": 2,
                "campaign_status": "READY",
                "campaign_lock_exists": False,
            }
            environment = {"status": "PASS", "error_code": "NONE", "errors": []}

            def identity(path: Path):
                return {
                    "status": "PASS",
                    "path": str(path),
                    "head": source_commit if Path(path).resolve() == source_root.resolve() else "c" * 40,
                    "tracked_clean": True,
                    "tracked_status": [],
                    "errors": [],
                }

            candidate = {"status": "PASS", "errors": []}
            collisions = {"status": "PASS", "errors": [], "collisions": []}
            with mock.patch.object(subject, "ROOT", destination_root), mock.patch.object(
                subject, "_git_worktree_identity", side_effect=identity
            ), mock.patch.object(
                subject, "_environment_validation", return_value=environment
            ), mock.patch.object(
                subject, "_campaign_snapshot", return_value=snapshot
            ), mock.patch.object(
                subject, "_campaign_candidate_validation", return_value=candidate
            ), mock.patch.object(
                subject, "run_id_filename_collision_report", return_value=collisions
            ):
                report = subject.materialize_build_trees(
                    source_root=source_root,
                    source_commit=source_commit,
                    expected_tree_sha256_by_name=expected,
                    run_id="p7_20260716_stationary_app_r59_diag_stage66_c03",
                    attempt_number=3,
                )
                collision = subject.materialize_build_trees(
                    source_root=source_root,
                    source_commit=source_commit,
                    expected_tree_sha256_by_name=expected,
                    run_id="p7_20260716_stationary_app_r60_diag_stage66_c03",
                    attempt_number=3,
                )
            self.assertEqual("PASS", report["P7_STAGE66_PREPARATION_DRIVER"])
            self.assertTrue(report["build_materialization_completed"])
            self.assertFalse(report["hardware_actions_executed"])
            for name in subject.BUILD_MATERIALIZATION_NAMES:
                destination = destination_root / "build" / name
                self.assertEqual(expected[name], subject.canonical_tree_record(destination)["tree_sha256"])
            self.assertEqual("FAIL", collision["P7_STAGE66_PREPARATION_DRIVER"])
            self.assertIn(
                "BUILD_DESTINATION_COLLISION",
                {item["error_code"] for item in collision["errors"]},
            )

    def test_build_preflight_rejects_commit_hash_and_destination_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source_root = temp_root / "source"
            destination_root = temp_root / "destination"
            for name in subject.BUILD_MATERIALIZATION_NAMES:
                tree = source_root / "build" / name
                tree.mkdir(parents=True)
                (tree / "payload.bin").write_bytes(name.encode("ascii"))
            (destination_root / "build" / "p6_ps_candidate").mkdir(parents=True)
            identity = {
                "status": "PASS",
                "path": str(source_root),
                "head": "b" * 40,
                "tracked_clean": True,
                "tracked_status": [],
                "errors": [],
            }
            with mock.patch.object(subject, "ROOT", destination_root), mock.patch.object(
                subject, "_git_worktree_identity", return_value=identity
            ):
                report = subject.inspect_build_materialization(
                    source_root=source_root,
                    source_commit="a" * 40,
                    expected_tree_sha256_by_name={
                        "p6_ps_candidate": "0" * 64,
                        "p7_ps_vitis_workspace": "1" * 64,
                    },
                )
            codes = {item["error_code"] for item in report["errors"]}
            self.assertEqual("FAIL", report["status"])
            self.assertIn("BUILD_SOURCE_COMMIT_MISMATCH", codes)
            self.assertIn("BUILD_SOURCE_TREE_SHA256_MISMATCH", codes)
            self.assertIn("BUILD_DESTINATION_COLLISION", codes)
            self.assertFalse(report["copy_started"])

    def test_build_preflight_rejects_relative_source_root(self) -> None:
        identity = {
            "status": "PASS",
            "path": "relative-source",
            "head": "a" * 40,
            "tracked_clean": True,
            "tracked_status": [],
            "errors": [],
        }
        with mock.patch.object(subject, "_git_worktree_identity", return_value=identity):
            report = subject.inspect_build_materialization(
                source_root=Path("relative-source"),
                source_commit="a" * 40,
                expected_tree_sha256_by_name={
                    "p6_ps_candidate": "0" * 64,
                    "p7_ps_vitis_workspace": "1" * 64,
                },
            )
        self.assertIn(
            "BUILD_SOURCE_ROOT_NOT_ABSOLUTE",
            {item["error_code"] for item in report["errors"]},
        )

    def test_run_id_collision_scan_covers_registered_worktree_evidence_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_id = "p7_20260716_stationary_app_r59_diag_stage66_c03"
            collision = root / "evidence" / "generated" / f"{run_id}_prior.json"
            collision.parent.mkdir(parents=True)
            collision.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(
                subject, "_registered_worktree_roots", return_value=([root], [])
            ):
                report = subject.run_id_filename_collision_report(run_id)
            self.assertEqual("FAIL", report["status"])
            self.assertEqual([str(collision.resolve())], report["collisions"])

    def test_run_id_collision_scan_covers_unregistered_sibling_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pool = Path(temp) / "CodexWorktrees"
            registered = pool / "registered" / "RF_COMM_MULTILANE"
            orphan = pool / "orphan" / "RF_COMM_MULTILANE"
            registered.mkdir(parents=True)
            run_id = "p7_20260716_stationary_app_r59_diag_stage66_c03"
            collision = orphan / "evidence" / "generated" / f"{run_id}_orphan.json"
            collision.parent.mkdir(parents=True)
            collision.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(
                subject,
                "_registered_worktree_roots",
                return_value=([registered], []),
            ):
                report = subject.run_id_filename_collision_report(run_id)
            self.assertEqual("FAIL", report["status"])
            self.assertEqual([str(collision.resolve())], report["collisions"])

    def test_driver_source_has_no_campaign_or_hardware_lock_acquire(self) -> None:
        source = Path(subject.__file__).read_text(encoding="utf-8")
        self.assertNotIn("CampaignLock.acquire", source)
        self.assertNotIn("HardwareExecutionLock.acquire", source)
        self.assertNotIn("shell=True", source)

    def test_ledger_materialization_is_hash_exact_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "evidence" / "generated" / "package" / "ledger.json"
            source.parent.mkdir(parents=True)
            payload = b'{"exact":"ledger-bytes"}\n'
            source.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            policy_path = root / "config" / "policy.json"
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text("{}\n", encoding="utf-8")
            target = root / "runtime" / "campaign_ledger.json"
            environment = {"status": "PASS", "error_code": "NONE", "errors": []}
            ledger = {"actual_hardware_attempt_count": 2, "status": "READY"}
            with mock.patch.object(subject, "ROOT", root), mock.patch.object(
                subject.campaign, "POLICY_PATH", policy_path
            ), mock.patch.object(
                subject.campaign, "validate_policy", return_value=({}, [])
            ), mock.patch.object(
                subject.campaign, "campaign_ledger_path", return_value=target
            ), mock.patch.object(
                subject.campaign, "validate_ledger", return_value=(ledger, [])
            ), mock.patch.object(
                subject, "_environment_validation", return_value=environment
            ):
                report = subject.materialize_campaign_ledger(source, digest, 2)
                self.assertEqual("PASS", report["P7_STAGE66_PREPARATION_DRIVER"])
                self.assertTrue(report["campaign_ledger_materialized"])
                self.assertEqual(payload, target.read_bytes())
                source.write_bytes(b"different\n")
                collision = subject.materialize_campaign_ledger(
                    source, hashlib.sha256(source.read_bytes()).hexdigest(), 2
                )
            self.assertEqual("FAIL", collision["P7_STAGE66_PREPARATION_DRIVER"])
            self.assertEqual(payload, target.read_bytes())
            self.assertIn(
                "CAMPAIGN_LEDGER_TARGET_COLLISION",
                {item["error_code"] for item in collision["errors"]},
            )

    def test_outer_helper_gate_precedes_execution_ledger_and_campaign_attempt(self) -> None:
        source = (ROOT / "tools" / "run_p7_authorized_hardware_sequence.py").read_text(
            encoding="utf-8"
        )
        execute = source[
            source.index("def _execute_sequence(") : source.index("def _sequence_main(")
        ]
        self.assertLess(
            execute.index("validate_plan_vivado_helper_identity(plan)"),
            execute.index("ledger_path = resolve_path(args.execution_ledger)"),
        )
        self.assertLess(
            execute.index("ledger_path = resolve_path(args.execution_ledger)"),
            execute.index("def begin_campaign_attempt()"),
        )


if __name__ == "__main__":
    unittest.main()
