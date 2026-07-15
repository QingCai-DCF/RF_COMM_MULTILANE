from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import generate_p7_authorized_sequence_plan as generator  # noqa: E402
import p7_stage66_campaign as campaign  # noqa: E402
import record_p7_stage66_campaign_recovery as recovery  # noqa: E402
import run_p7_authorized_hardware_sequence as sequence  # noqa: E402


class P7Stage66CampaignTests(unittest.TestCase):
    def test_canonical_policy_binds_immutable_r41_fail_and_exact_exception(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy, errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
        self.assertEqual([], errors)
        self.assertIsNotNone(policy)
        assert policy is not None
        self.assertEqual(10, policy["maximum_actual_hardware_attempts"])
        self.assertEqual([1, 2, 3, 4, 66], policy["selected_full_stage_ordinals"])
        self.assertEqual(1800, policy["stage66_exact_runtime_seconds"])
        self.assertEqual("FAIL", policy["immutable_failed_baseline"]["status"])
        self.assertTrue(
            policy["immutable_failed_baseline"]["resume_restart_copy_reuse_forbidden"]
        )
        _policy, errors = campaign.validate_policy(campaign.POLICY_PATH, "0" * 64)
        self.assertTrue(any("SHA256 mismatch" in item for item in errors))

    def test_campaign_matrix_is_exact_and_ordinary_diagnostics_still_exclude_stationary(self) -> None:
        full = generator.build_stage_specs()
        selected = generator.select_stage_specs(
            full,
            diagnostic_suffix55=False,
            stage66_campaign_mode=True,
        )
        self.assertEqual([1, 2, 3, 4, 66], [item.index for item in selected])
        stages = [
            {"group": item.group, "risk_index": item.risk_index, "case": item.case}
            for item in selected
        ]
        self.assertEqual(
            [],
            sequence.validate_stage_matrix(
                stages,
                plan_mode=sequence.STAGE66_CAMPAIGN_PLAN_MODE,
                full_stage_ordinals=[1, 2, 3, 4, 66],
            ),
        )
        ordinary_errors = sequence.validate_stage_matrix(
            stages,
            plan_mode=sequence.DIAGNOSTIC_PLAN_MODE,
            full_stage_ordinals=[1, 2, 3, 4, 66],
        )
        self.assertTrue(ordinary_errors)
        with self.assertRaises(ValueError):
            generator.select_stage_specs(
                full,
                diagnostic_suffix55=True,
                stage66_campaign_mode=True,
            )

    def test_executor_revalidates_policy_ledger_snapshot_and_next_run_identity(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy, errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
        self.assertEqual([], errors)
        assert policy is not None
        ledger_path = campaign.campaign_ledger_path(policy)
        record = {
            "campaign_id": policy["campaign_id"],
            "run_id": "p7_20260715_stationary_app_r42_diag_stage66_c01",
            "hardware_attempt_number": 1,
            "maximum_actual_hardware_attempts": 10,
            "selected_full_stage_ordinals": [1, 2, 3, 4, 66],
            "formal_full_run_excluded_from_limit": True,
            "policy": {"path": str(campaign.POLICY_PATH), "sha256": policy_sha},
            "runtime_campaign_ledger": str(ledger_path),
            "prior_campaign_ledger_sha256": "ABSENT",
        }
        with mock.patch.object(campaign, "current_ledger_sha256", return_value="ABSENT"), mock.patch.object(
            campaign, "validate_ledger", return_value=(None, [])
        ):
            normalized, errors = sequence._validate_stage66_campaign_record(
                record,
                source_commit="a" * 40,
                selected_ordinals=[1, 2, 3, 4, 66],
            )
        self.assertEqual([], errors)
        self.assertEqual(1, normalized["hardware_attempt_number"])
        record["prior_campaign_ledger_sha256"] = "0" * 64
        with mock.patch.object(campaign, "current_ledger_sha256", return_value="ABSENT"), mock.patch.object(
            campaign, "validate_ledger", return_value=(None, [])
        ):
            _normalized, errors = sequence._validate_stage66_campaign_record(
                record,
                source_commit="a" * 40,
                selected_ordinals=[1, 2, 3, 4, 66],
            )
        self.assertTrue(any("snapshot changed" in item for item in errors))

    def test_every_campaign_stage_authorization_is_zero_coverage_and_ledger_bound(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy = json.loads(campaign.POLICY_PATH.read_text(encoding="utf-8"))
        record = {
            "campaign_id": policy["campaign_id"],
            "run_id": "p7_20260715_stationary_app_r42_diag_stage66_c01",
            "hardware_attempt_number": 1,
            "maximum_actual_hardware_attempts": 10,
            "selected_full_stage_ordinals": [1, 2, 3, 4, 66],
            "formal_full_run_excluded_from_limit": True,
            "policy": {"path": str(campaign.POLICY_PATH), "sha256": policy_sha},
            "runtime_campaign_ledger": str(campaign.campaign_ledger_path(policy)),
            "prior_campaign_ledger_sha256": "ABSENT",
        }
        artifact = generator.Artifact(Path("synthetic"), "a" * 64)
        artifacts = {
            key: artifact
            for key in (
                "goal_plan",
                "xsa",
                "elf",
                "active_xdc",
                "pinmap",
                "register_map",
                "shutdown_bitstream",
                "jtag_ltx",
            )
        }
        args = type(
            "Args",
            (),
            {
                "board_id": generator.CANONICAL_BOARD_ID,
                "expected_part": generator.CANONICAL_PART,
                "expected_target": generator.CANONICAL_TARGET,
            },
        )()
        context = {
            "source_commit": "a" * 40,
            "plan_mode": sequence.STAGE66_CAMPAIGN_PLAN_MODE,
            "stage66_diagnostic_campaign": record,
            "artifacts": artifacts,
        }
        spec = generator.build_stage_specs()[0]
        lines = generator.common_authorization_lines(
            args,
            context,
            spec,
            bitstream=artifact,
            profile=artifact,
            include_ltx=True,
        )
        fields = dict(line.split("=", 1) for line in lines if "=" in line)
        self.assertEqual("DIAGNOSTIC_ONLY", fields["P7_EXECUTION_MODE"])
        self.assertEqual("false", fields["P7_COVERAGE_CLAIMED"])
        self.assertEqual("PENDING_HW", fields["HARDWARE_ACCEPTANCE"])
        self.assertEqual("true", fields["P7_STAGE66_DIAGNOSTIC_CAMPAIGN"])
        self.assertEqual("ABSENT", fields["P7_STAGE66_CAMPAIGN_PRIOR_LEDGER_SHA256"])

    def test_next_attempt_is_contiguous_unique_bounded_and_stops_after_pass(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy, errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
        self.assertEqual([], errors)
        assert policy is not None
        ledger = campaign.new_ledger(policy, policy_sha)
        self.assertEqual(
            [],
            campaign.validate_next_attempt(
                policy,
                ledger,
                run_id="p7_20260715_stationary_app_r42_diag_stage66_c01",
                hardware_attempt_number=1,
            ),
        )
        campaign.begin_attempt(
            ledger,
            run_id="p7_20260715_stationary_app_r42_diag_stage66_c01",
            hardware_attempt_number=1,
            source_commit="a" * 40,
            sequence_plan_path="plan.json",
            sequence_plan_sha256="b" * 64,
            execution_ledger_path="ledger.json",
            prior_campaign_ledger_sha256="ABSENT",
        )
        self.assertEqual("RECOVERY_REQUIRED", ledger["status"])
        self.assertTrue(
            campaign.validate_next_attempt(
                policy,
                ledger,
                run_id="p7_20260715_stationary_app_r43_diag_stage66_c02",
                hardware_attempt_number=2,
            )
        )
        campaign.finish_attempt(
            ledger,
            passed=True,
            failed_full_stage_ordinal=None,
            stationary_launched=True,
            execution_ledger_sha256="c" * 64,
        )
        self.assertEqual("PASSED", ledger["status"])
        errors = campaign.validate_next_attempt(
            policy,
            ledger,
            run_id="p7_20260715_stationary_app_r43_diag_stage66_c02",
            hardware_attempt_number=2,
        )
        self.assertTrue(any("not ready" in item for item in errors))

    def test_ten_failures_are_a_hard_upper_bound_and_no_eleventh_suffix_is_valid(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy, errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
        self.assertEqual([], errors)
        assert policy is not None
        ledger = campaign.new_ledger(policy, policy_sha)
        for number in range(1, 11):
            run_id = f"p7_20260715_stationary_r{41 + number}_diag_stage66_c{number:02d}"
            self.assertEqual(
                [],
                campaign.validate_next_attempt(
                    policy,
                    ledger,
                    run_id=run_id,
                    hardware_attempt_number=number,
                ),
            )
            campaign.begin_attempt(
                ledger,
                run_id=run_id,
                hardware_attempt_number=number,
                source_commit=f"{number:040x}",
                sequence_plan_path=f"plan-{number}.json",
                sequence_plan_sha256=f"{number:064x}",
                execution_ledger_path=f"ledger-{number}.json",
                prior_campaign_ledger_sha256=(
                    "ABSENT" if number == 1 else f"{number + 200:064x}"
                ),
            )
            campaign.finish_attempt(
                ledger,
                passed=False,
                failed_full_stage_ordinal=66,
                stationary_launched=True,
                execution_ledger_sha256=f"{number + 100:064x}",
            )
            ledger["hardware_attempts"][-1]["status"] = "FAIL_RECOVERED"
            ledger["hardware_attempts"][-1]["independent_shutdown_recovery"] = {
                "status": "PASS",
                "shutdown_exit": 0,
                "recovery_changes_failed_stage_result": False,
            }
            ledger["status"] = "EXHAUSTED" if number == 10 else "READY"
        self.assertEqual(10, ledger["actual_hardware_attempt_count"])
        errors = campaign.validate_next_attempt(
            policy,
            ledger,
            run_id="p7_20260715_stationary_r52_diag_stage66_c11",
            hardware_attempt_number=11,
        )
        self.assertTrue(any("not ready" in item or "exhausted" in item for item in errors))
        with tempfile.TemporaryDirectory() as temp:
            ledger_path = Path(temp) / "campaign_ledger.json"
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            with mock.patch.object(
                campaign, "campaign_ledger_path", return_value=ledger_path.resolve()
            ):
                _loaded, validation_errors = campaign.validate_ledger(
                    policy, ledger_path, allow_absent=False
                )
            self.assertEqual([], validation_errors)

    def test_campaign_lock_is_exclusive_and_never_auto_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ledger_path = Path(temp) / "campaign_ledger.json"
            lock = campaign.CampaignLock.acquire(ledger_path, {"run_id": "unit"})
            try:
                with self.assertRaisesRegex(RuntimeError, "never auto-recovered"):
                    campaign.CampaignLock.acquire(ledger_path, {"run_id": "second"})
            finally:
                lock.release()
            self.assertFalse((Path(temp) / "campaign_execution.lock").exists())

    def test_child_wrapper_requires_the_one_active_campaign_attempt(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy, errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
        self.assertEqual([], errors)
        assert policy is not None
        ledger = campaign.new_ledger(policy, policy_sha)
        run_id = "p7_20260715_stationary_app_r42_diag_stage66_c01"
        campaign.begin_attempt(
            ledger,
            run_id=run_id,
            hardware_attempt_number=1,
            source_commit="a" * 40,
            sequence_plan_path="plan.json",
            sequence_plan_sha256="b" * 64,
            execution_ledger_path="ledger.json",
            prior_campaign_ledger_sha256="ABSENT",
        )
        self.assertEqual(
            [],
            campaign.validate_active_attempt(
                ledger,
                run_id=run_id,
                hardware_attempt_number=1,
                source_commit="a" * 40,
                prior_campaign_ledger_sha256="ABSENT",
            ),
        )
        self.assertTrue(
            campaign.validate_active_attempt(
                ledger,
                run_id=run_id,
                hardware_attempt_number=1,
                source_commit="a" * 40,
                prior_campaign_ledger_sha256="0" * 64,
            )
        )

    def test_jtag_prefix_preserves_campaign_zero_coverage_metadata(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy = json.loads(campaign.POLICY_PATH.read_text(encoding="utf-8"))
        fields = {
            "P7_EXECUTION_MODE": "DIAGNOSTIC_ONLY",
            "P7_COVERAGE_CLAIMED": "false",
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "P7_STAGE66_DIAGNOSTIC_CAMPAIGN": "true",
            "P7_STAGE66_CAMPAIGN_ID": policy["campaign_id"],
            "P7_STAGE66_CAMPAIGN_RUN_ID": "p7_20260715_stationary_app_r42_diag_stage66_c01",
            "P7_STAGE66_CAMPAIGN_ATTEMPT_NUMBER": "1",
            "P7_STAGE66_CAMPAIGN_MAX_HARDWARE_ATTEMPTS": "10",
            "P7_FULL_STAGE_ORDINAL": "1",
            "P7_STAGE66_CAMPAIGN_POLICY_PATH": str(campaign.POLICY_PATH),
            "P7_STAGE66_CAMPAIGN_POLICY_SHA256": policy_sha,
            "P7_STAGE66_CAMPAIGN_LEDGER_PATH": str(
                campaign.campaign_ledger_path(policy)
            ),
            "P7_STAGE66_CAMPAIGN_PRIOR_LEDGER_SHA256": "ABSENT",
        }
        safety = {"authorization_fields": fields, "source_commit_requested": "a" * 40}
        args = type("Args", (), {"execute_hardware": False, "evidence_dir": ""})()
        wrapper = generator.jtag_safe_wrapper
        self.assertEqual([], wrapper._diagnostic_authorization_errors(args, safety))
        metadata = wrapper._diagnostic_summary_metadata(safety)
        self.assertTrue(metadata["diagnostic_only"])
        self.assertFalse(metadata["coverage_claimed"])
        self.assertEqual("PENDING_HW", metadata["HARDWARE_ACCEPTANCE"])
        self.assertEqual(
            1, metadata["stage66_diagnostic_campaign"]["hardware_attempt_number"]
        )
        fields["P7_FULL_STAGE_ORDINAL"] = "66"
        self.assertTrue(wrapper._diagnostic_authorization_errors(args, safety))

    def test_independent_recovery_record_requires_exact_shutdown_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_id = "p7_20260715_stationary_app_r42_diag_stage66_c01"
            directory = (
                root
                / "evidence/hardware/p7/authorized_sequence"
                / run_id
                / "recovery_shutdown_after_failed_stage066_20260715T010000Z"
            )
            directory.mkdir(parents=True)
            (directory / "hardware_authorization.json").write_text(
                json.dumps(
                    {
                        "AUTHORIZED": True,
                        "P4_AUTHORIZATION": "AUTHORIZED",
                        "missing": [],
                    }
                ),
                encoding="utf-8",
            )
            (directory / "hash_manifest.csv").write_text("path,sha256\n", encoding="utf-8")
            (directory / "hash_manifest.json").write_text("{}\n", encoding="utf-8")
            (directory / "program_tfdu_shutdown_safe.stderr.log").write_bytes(b"")
            (directory / "program_tfdu_shutdown_safe.stdout.log").write_text(
                "TFDU_SHUTDOWN_PROGRAMMED=C:/synthetic/tfdu_shutdown.bit\n",
                encoding="utf-8",
            )
            summary_path = directory / "program_tfdu_shutdown_safe.summary.txt"
            summary_path.write_text(
                "PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN 2026-07-15T01:00:00+00:00\n"
                "HARDWARE_AUTHORIZATION_EXIT=0\n"
                "ALLOW_HARDWARE=1\n"
                "NO_HARDWARE_ACTIONS_EXECUTED=0\n"
                "TFDU_SHUTDOWN_PROGRAMMED_SEEN=1\n"
                "SHUTDOWN_EXIT=0\n"
                "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS\n"
                "PROGRAM_TFDU_SHUTDOWN_SAFE_END 2026-07-15T01:01:00+00:00\n",
                encoding="utf-8",
            )
            with mock.patch.object(recovery, "ROOT", root):
                record, errors = recovery.validate_recovery(
                    directory,
                    run_id=run_id,
                    failure_ended_at_utc="2026-07-15T00:59:00+00:00",
                )
                self.assertEqual([], errors)
                self.assertEqual("PASS", record["status"])
                summary_path.write_text(
                    summary_path.read_text(encoding="utf-8") + "SHUTDOWN_EXIT=0\n",
                    encoding="utf-8",
                )
                _record, errors = recovery.validate_recovery(
                    directory,
                    run_id=run_id,
                    failure_ended_at_utc="2026-07-15T00:59:00+00:00",
                )
                self.assertTrue(any("duplicate markers" in item for item in errors))

    def test_ps_child_summary_marks_campaign_as_diagnostic_zero_coverage(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        wrapper = generator.ps_safe_wrapper
        args = wrapper.build_parser().parse_args(
            [
                "--mode",
                "stationary",
                "--stage66-diagnostic-campaign",
                "--run-id",
                "p7_20260715_stationary_app_r42_diag_stage66_c01",
                "--stage66-campaign-id",
                "p7_stage66_stationary_diagnostic_20260715",
                "--stage66-campaign-attempt-number",
                "1",
                "--stage66-campaign-max-attempts",
                "10",
                "--stage66-campaign-policy",
                str(campaign.POLICY_PATH),
                "--stage66-campaign-policy-sha256",
                policy_sha,
                "--max-runtime-sec",
                "1800",
                "--preflight-timeout-sec",
                "60",
                "--shutdown-timeout-sec",
                "60",
            ]
        )
        summary = wrapper._base_summary(
            args,
            {"errors": [], "source_commit_requested": "a" * 40},
            [],
            {"status": "PASS", "errors": []},
        )
        self.assertTrue(summary["diagnostic_only"])
        self.assertFalse(summary["coverage_claimed"])
        self.assertEqual("PENDING_HW", summary["HARDWARE_ACCEPTANCE"])
        self.assertEqual("P7_STAGE66_DIAGNOSTIC_STAGE", summary["execution_scope"])
        self.assertEqual(1, summary["stage66_diagnostic_campaign"]["hardware_attempt_number"])

    def test_campaign_ledger_tamper_and_unresolved_recovery_fail_closed(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy, errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
        self.assertEqual([], errors)
        assert policy is not None
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "campaign_ledger.json"
            # The path itself is part of the policy, so a relocated ledger is rejected.
            ledger = campaign.new_ledger(policy, policy_sha)
            path.write_text(json.dumps(ledger), encoding="utf-8")
            _loaded, errors = campaign.validate_ledger(policy, path, allow_absent=False)
            self.assertTrue(any("path mismatch" in item for item in errors))
            ledger["actual_hardware_attempt_count"] = 1
            path.write_text(json.dumps(ledger), encoding="utf-8")
            _loaded, errors = campaign.validate_ledger(policy, path, allow_absent=False)
            self.assertTrue(any("attempt count mismatch" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
