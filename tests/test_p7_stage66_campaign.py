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
import record_p7_stage66_campaign_prelaunch_retirement as prelaunch_retirement  # noqa: E402
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

    def test_prehardware_retirement_is_hash_bound_unique_and_consumes_zero_quota(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        policy, errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
        self.assertEqual([], errors)
        assert policy is not None
        evidence = (
            ROOT
            / "evidence"
            / "generated"
            / "p7_r42_stage66_campaign_c01_prelaunch_failure.json"
        )
        evidence_sha = hashlib.sha256(evidence.read_bytes()).hexdigest()
        run_id = "p7_20260715_stationary_app_r42_diag_stage66_c01"
        next_run_id = "p7_20260715_stationary_app_r43_diag_stage66_c01"
        payload, evidence_errors = prelaunch_retirement.validate_retirement_evidence(
            evidence,
            evidence_sha,
            run_id=run_id,
            source_commit="5ead7d1d1bdd0ecb8b41a2980a545f3e7bced9c4",
            requested_hardware_attempt_number=1,
        )
        self.assertEqual([], evidence_errors)
        self.assertIsNotNone(payload)
        ledger = campaign.new_ledger(policy, policy_sha)
        campaign.retire_pre_hardware_run_id(
            ledger,
            run_id=run_id,
            requested_hardware_attempt_number=1,
            source_commit="5ead7d1d1bdd0ecb8b41a2980a545f3e7bced9c4",
            reason="PLAN_GENERATOR_CHILD_WRAPPER_DRY_VALIDATION_FAIL",
            evidence_path=str(evidence.relative_to(ROOT)).replace("\\", "/"),
            evidence_sha256=evidence_sha,
        )
        self.assertEqual(0, ledger["actual_hardware_attempt_count"])
        self.assertEqual("READY", ledger["status"])
        self.assertFalse(
            ledger["retired_pre_hardware_run_ids"][0]["hardware_attempt_consumed"]
        )
        self.assertTrue(
            campaign.validate_next_attempt(
                policy,
                ledger,
                run_id=run_id,
                hardware_attempt_number=1,
            )
        )
        self.assertEqual(
            [],
            campaign.validate_next_attempt(
                policy,
                ledger,
                run_id=next_run_id,
                hardware_attempt_number=1,
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "already launched or retired"):
            campaign.retire_pre_hardware_run_id(
                ledger,
                run_id=run_id,
                requested_hardware_attempt_number=1,
                source_commit="5ead7d1d1bdd0ecb8b41a2980a545f3e7bced9c4",
                reason="DUPLICATE",
                evidence_path=str(evidence.relative_to(ROOT)).replace("\\", "/"),
                evidence_sha256=evidence_sha,
            )
        campaign.begin_attempt(
            ledger,
            run_id=next_run_id,
            hardware_attempt_number=1,
            source_commit="a" * 40,
            sequence_plan_path="plan.json",
            sequence_plan_sha256="b" * 64,
            execution_ledger_path="execution-ledger.json",
            prior_campaign_ledger_sha256="c" * 64,
        )
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
            shutdown_bit = root / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"
            shutdown_bit.parent.mkdir(parents=True)
            shutdown_bit.write_bytes(b"canonical shutdown bitstream\n")
            shutdown_sha = hashlib.sha256(shutdown_bit.read_bytes()).hexdigest()
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
            (directory / "hash_manifest.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": str(shutdown_bit),
                                "exists": True,
                                "sha256": shutdown_sha,
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (directory / "program_tfdu_shutdown_safe.stderr.log").write_bytes(b"")
            (directory / "program_tfdu_shutdown_safe.stdout.log").write_text(
                f"TFDU_SHUTDOWN_PROGRAMMED={shutdown_bit}\n",
                encoding="utf-8",
            )
            summary_path = directory / "program_tfdu_shutdown_safe.summary.txt"
            summary_path.write_text(
                "PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN 2026-07-15T01:00:00+00:00\n"
                f"SHUTDOWN_BITSTREAM={shutdown_bit}\n"
                f"SHUTDOWN_BITSTREAM_SHA256={shutdown_sha}\n"
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
                (directory / "program_tfdu_shutdown_safe.stdout.log").write_text(
                    "# puts \"TFDU_SHUTDOWN_PROGRAMMED $bit_file\"\n"
                    f"TFDU_SHUTDOWN_PROGRAMMED {shutdown_bit}\n",
                    encoding="utf-8",
                )
                _record, errors = recovery.validate_recovery(
                    directory,
                    run_id=run_id,
                    failure_ended_at_utc="2026-07-15T00:59:00+00:00",
                )
                self.assertEqual([], errors)
                wrong_bit = root / "shutdown_bitstream" / "wrong.bit"
                (directory / "program_tfdu_shutdown_safe.stdout.log").write_text(
                    f"TFDU_SHUTDOWN_PROGRAMMED {wrong_bit}\n",
                    encoding="utf-8",
                )
                _record, errors = recovery.validate_recovery(
                    directory,
                    run_id=run_id,
                    failure_ended_at_utc="2026-07-15T00:59:00+00:00",
                )
                self.assertTrue(any("path is not canonical" in item for item in errors))
                (directory / "program_tfdu_shutdown_safe.stdout.log").write_text(
                    f"TFDU_SHUTDOWN_PROGRAMMED {shutdown_bit}\n"
                    f"TFDU_SHUTDOWN_PROGRAMMED={shutdown_bit}\n",
                    encoding="utf-8",
                )
                _record, errors = recovery.validate_recovery(
                    directory,
                    run_id=run_id,
                    failure_ended_at_utc="2026-07-15T00:59:00+00:00",
                )
                self.assertTrue(any("exactly one" in item for item in errors))
                (directory / "program_tfdu_shutdown_safe.stdout.log").write_text(
                    f"TFDU_SHUTDOWN_PROGRAMMED {shutdown_bit}\n",
                    encoding="utf-8",
                )
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

    def test_stage66_campaign_scope_reaches_the_xsdb_executor_exactly(self) -> None:
        policy_sha = hashlib.sha256(campaign.POLICY_PATH.read_bytes()).hexdigest()
        run_id = "p7_20260715_stationary_app_r48_diag_stage66_c02"
        campaign_record = {
            "campaign_id": "p7_stage66_stationary_diagnostic_20260715",
            "run_id": run_id,
            "hardware_attempt_number": 2,
            "maximum_actual_hardware_attempts": 10,
            "policy": {"path": str(campaign.POLICY_PATH), "sha256": policy_sha},
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
                "ps_stationary_profile",
                "ps_bitstream",
                "ps7_init",
                "p6_build_summary",
                "p7_build_summary",
                "core_readiness_attestation",
                "active_profile",
                "lane1_promotion_summary",
            )
        }
        args = type(
            "Args",
            (),
            {
                "board_id": generator.CANONICAL_BOARD_ID,
                "expected_part": generator.CANONICAL_PART,
                "expected_target": generator.CANONICAL_TARGET,
                "hw_server_url": generator.CANONICAL_HW_SERVER_URL,
                "jtag_frequency_hz": generator.CANONICAL_JTAG_FREQUENCY_HZ,
            },
        )()
        context = {
            "source_commit": "a" * 40,
            "artifacts": artifacts,
            "abort_file": Path("abort.txt"),
            "vivado": Path("vivado.bat"),
            "xsdb": Path("xsdb.bat"),
            "stage66_diagnostic_campaign": campaign_record,
        }
        spec = generator.build_stage_specs()[-1]
        command = generator.build_ps_command(
            args,
            context,
            spec,
            artifact,
            artifact,
            Path("evidence"),
        )
        self.assertIn("--stage66-diagnostic-campaign", command)
        wrapper = generator.ps_safe_wrapper
        parsed = wrapper.build_parser().parse_args(command[2:])
        self.assertTrue(parsed.stage66_diagnostic_campaign)
        self.assertEqual(run_id, parsed.run_id)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "input.bin"
            input_path.write_bytes(b"campaign-scope")
            bundle = wrapper.build_stage_bundle(
                bundle_dir=root / "bundle",
                mode="stationary",
                input_path=input_path,
                max_runtime_sec=1800,
                calibration_sec=300,
                acceptance_sec=1500,
                sample_interval_sec=30,
                idle_margin_sec=60,
                stationary_object_bytes=64 * 1024,
                run_id=run_id,
                execution_scope="P7_STAGE66_DIAGNOSTIC_STAGE",
                diagnostic_only=True,
            )
            xsdb_command = wrapper.build_ps_command(
                parsed, bundle, root / "preflight.txt", root / "raw.log"
            )
        self.assertEqual("P7_STAGE66_DIAGNOSTIC_STAGE", xsdb_command[-2])
        self.assertEqual(run_id, xsdb_command[-1])
        tcl = (generator.ROOT / "scripts/hw/p7_ps_application_execute.tcl").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "{P7_PS_APPLICATION_STAGE STAGE62_ONLY P7_STAGE66_DIAGNOSTIC_STAGE}",
            tcl,
        )
        self.assertIn(
            'if {$execution_scope in {STAGE62_ONLY P7_STAGE66_DIAGNOSTIC_STAGE}}',
            tcl,
        )
        self.assertIn(
            "p7_require_value $auth_text P7_STAGE66_CAMPAIGN_RUN_ID $run_id", tcl
        )

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
