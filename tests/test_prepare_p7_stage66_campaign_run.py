import sys
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import prepare_p7_stage66_campaign_run as subject  # noqa: E402


class PrepareP7Stage66CampaignRunTests(unittest.TestCase):
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
        with mock.patch.object(subject, "_campaign_snapshot", return_value=snapshot), mock.patch.object(
            subject.helper_identity, "validate_vivado_helper_identity", return_value=identity
        ), mock.patch.object(subject, "_environment_validation", return_value=environment), mock.patch.object(
            subject, "_git_head", return_value="d" * 40
        ):
            report = subject.placeholder_rehearsal(
                Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
            )
        self.assertEqual("PASS", report["P7_STAGE66_PREPARATION_DRIVER"])
        self.assertTrue(all(report["fixed_regression_matrix"].values()))
        self.assertFalse(report["hardware_actions_executed"])
        self.assertFalse(report["campaign_attempt_created"])
        self.assertEqual(snapshot, report["campaign_before"])
        self.assertEqual(snapshot, report["campaign_after"])

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
