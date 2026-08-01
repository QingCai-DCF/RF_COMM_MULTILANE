from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/finalize_p10_1_hardware_acceptance.py"


def load_module():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "finalize_p10_1_hardware_acceptance", MODULE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FinalizeP101HardwareAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_required_stage_order_matches_authorized_campaign(self) -> None:
        self.assertEqual(
            self.module.REQUIRED_STAGES,
            (
                "preflight",
                "smoke",
                "baseline",
                "tuning",
                "pipeline",
                "streaming",
                "faults",
                "crosstalk",
                "half_duplex",
                "oneplusone",
                "formal",
            ),
        )

    def test_crosstalk_classification_uses_all_four_rx_observations(self) -> None:
        stage = {
            "raw_matrix": [
                {
                    "label": "xtalk_tx_f0_raw64",
                    "fixed_rx": [0, 0, 0, 0],
                    "rotating_rx": [0, 0, 64, 0],
                },
                {
                    "label": "xtalk_tx_f1_raw1024",
                    "fixed_rx": [0, 0, 0, 0],
                    "rotating_rx": [0, 0, 0, 1024],
                },
                {
                    "label": "xtalk_tx_r0_raw64",
                    "fixed_rx": [64, 0, 0, 0],
                    "rotating_rx": [0, 0, 0, 0],
                },
                {
                    "label": "xtalk_tx_r1_raw1024",
                    "fixed_rx": [0, 1024, 0, 0],
                    "rotating_rx": [0, 0, 0, 0],
                },
            ],
            "semantics": {
                "frame_matrix": [
                    {
                        "target_valid_frames": 1,
                        "non_target_crc_valid_frames": 0,
                    }
                ]
            },
        }
        result = self.module.crosstalk_classification(stage)
        self.assertEqual(result["near_end_echo_class"], "LOW")
        self.assertEqual(result["cross_lane_crosstalk_class"], "LOW")
        self.assertEqual(result["all_rx_ready_risk"], "ACCEPTABLE")
        self.assertEqual(result["non_target_crc_valid_false_frames"], 0)

    def test_non_target_crc_valid_frame_blocks_classification(self) -> None:
        result = self.module.crosstalk_classification(
            {
                "raw_matrix": [],
                "semantics": {
                    "frame_matrix": [
                        {
                            "target_valid_frames": 1,
                            "non_target_crc_valid_frames": 1,
                        }
                    ]
                },
            }
        )
        self.assertEqual(result["all_rx_ready_risk"], "BLOCKED")

    def test_empty_crosstalk_matrix_is_not_measured(self) -> None:
        result = self.module.crosstalk_classification(
            {"raw_matrix": [], "semantics": {"frame_matrix": []}}
        )
        self.assertEqual(result["near_end_echo_class"], "NOT_MEASURED")
        self.assertEqual(result["cross_lane_crosstalk_class"], "NOT_MEASURED")
        self.assertEqual(result["all_rx_ready_risk"], "NOT_MEASURED")

    def test_timer_gate_is_local_ps_vs_pl_not_cross_endpoint(self) -> None:
        rows = self.module.timer_crosscheck_rows(
            [
                {
                    "label": "asymmetric-local-work",
                    "recovery_case": False,
                    "fixed": {
                        "ps_elapsed_ticks": 100_000_000,
                        "ps_timer_frequency_hz": 100_000_000,
                        "pl_elapsed_ticks": 64_000_000,
                        "pl_timer_frequency_hz": 64_000_000,
                        "timer_crosscheck_pass": 1,
                    },
                    "rotating": {
                        "ps_elapsed_ticks": 105_000_000,
                        "ps_timer_frequency_hz": 100_000_000,
                        "pl_elapsed_ticks": 67_200_000,
                        "pl_timer_frequency_hz": 64_000_000,
                        "timer_crosscheck_pass": 1,
                    },
                }
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["fixed_local_ps_pl_error_percent"], 0.0)
        self.assertEqual(rows[0]["rotating_local_ps_pl_error_percent"], 0.0)
        self.assertGreater(rows[0]["ps_cross_endpoint_skew_percent"], 1.0)
        self.assertFalse(rows[0]["cross_endpoint_skew_is_gating"])

    def test_unlimited_retry_authorization_supersedes_stale_audit(self) -> None:
        result = self.module.retry_campaign_fields(
            {
                "run_id": "run-4",
                "retry_limit_policy": (
                    self.module.UNLIMITED_RETRY_OVERRIDE_POLICY
                ),
                "diagnostic_stage_retry_budget": {
                    "preflight": {"run_ids": ["run-1", "run-2"]},
                    "baseline": {"run_ids": ["run-2", "run-3"]},
                },
            },
            "FAIL",
            {
                "campaign_disposition": "STOPPED_AT_GOAL_RETRY_LIMIT",
                "next_required_user_action": "request another override",
                "preflight_retry_ledger": {"new_run_id_count": 2},
                "goal": {"diagnostic_stage_new_run_id_limit": 2},
            },
        )
        self.assertEqual(
            result["campaign_disposition"],
            "AUTOMATIC_REMEDIATION_AND_RETRY_AUTHORIZED",
        )
        self.assertIsNone(result["retry_run_id_limit"])
        self.assertEqual(result["retry_run_id_count"], 4)
        self.assertTrue(result["bounded_retry_audit_superseded"])
        self.assertIn("none", result["next_required_user_action"])

    def test_common_context_uses_run_authorization_artifacts(self) -> None:
        authorization = {
            "source_commit": "authorized-source",
            "artifacts": [
                {
                    "role": "fixed",
                    "kind": "functional_bitstream",
                    "path": "authorized-fixed.bit",
                    "sha256": "a" * 64,
                    "bytes": 123,
                },
                {
                    "role": "fixed",
                    "kind": "elf",
                    "path": "authorized-fixed.elf",
                    "sha256": "b" * 64,
                    "bytes": 456,
                },
            ],
            "input_hashes": {},
        }
        latest = {
            "artifacts": [
                {
                    "role": "fixed",
                    "kind": "performance_bitstream",
                    "path": "newer-fixed.bit",
                    "sha256": "c" * 64,
                    "bytes": 789,
                }
            ]
        }
        context = self.module.common_context("run-1", authorization, latest)
        self.assertEqual(
            context["artifact_hashes"]["fixed:performance_bitstream"]["path"],
            "authorized-fixed.bit",
        )
        self.assertEqual(
            context["artifact_hashes"]["fixed:elf"]["path"],
            "authorized-fixed.elf",
        )
        self.assertNotIn(
            "newer-fixed.bit",
            {
                item["path"]
                for item in context["artifact_hashes"].values()
            },
        )
        self.assertTrue(context["captured_run_hardware_authorization"])
        self.assertFalse(context["current_run_hardware_authorization"])
        self.assertEqual(context["authorization_lifecycle"], "CONSUMED_AFTER_RUN")

    def test_missing_stage_is_fail_with_not_run_disposition(self) -> None:
        run_root = ROOT / "does-not-exist"
        orchestrator_path = ROOT / "PROJECT_STATUS.md"
        payload, source = self.module.stage_record(
            run_root,
            "formal",
            orchestrator={"stages": {"formal": "NOT_RUN"}},
            orchestrator_path=orchestrator_path,
        )
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["execution_status"], "NOT_RUN")
        self.assertEqual(payload["disposition"], "NOT_RUN_DUE_PRIOR_STAGE_FAILURE")
        self.assertEqual(source["stage"], "formal")

    def test_p10_goodput_runtime_change_is_identity_only(self) -> None:
        result = self.module.audit_p10_runtime_source_binding()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            result["audited_change_class"],
            "REGISTER_MAP_IDENTITY_BINDING_ONLY",
        )
        self.assertFalse(result["goodput_formula_changed"])
        self.assertFalse(result["campaign_minimum_aggregation_changed"])
        self.assertTrue(
            all(
                item["identical"]
                for item in result["function_source_sha256"].values()
            )
        )

    def test_failed_run_consumes_current_authorization(self) -> None:
        active = {
            "run_id": "run-2",
            "status": "AUTHORIZED",
            "current_run_hardware_authorization": True,
        }
        result = self.module.consumed_authorization_payload(
            active,
            run_id="run-2",
            campaign_status="FAIL",
            consumed_at_utc="2026-07-31T22:30:00+00:00",
            final_evidence_sha256="d" * 64,
            campaign_disposition="STOPPED_AT_GOAL_RETRY_LIMIT",
            next_required_user_action="explicit retry-limit override",
            shutdown_fixed="PASS",
            shutdown_rotating="PASS",
        )
        self.assertEqual(
            result["status"], "CONSUMED_AFTER_P10_1_HARDWARE_FAIL"
        )
        self.assertFalse(result["current_run_hardware_authorization"])
        self.assertTrue(result["consumed"])
        self.assertEqual(result["consumed_by_run_id"], "run-2")
        self.assertFalse(result["reusable_for_future_run"])
        repeated = self.module.consumed_authorization_payload(
            result,
            run_id="run-2",
            campaign_status="FAIL",
            consumed_at_utc="2026-07-31T22:31:00+00:00",
            final_evidence_sha256="e" * 64,
            campaign_disposition="STOPPED_AT_GOAL_RETRY_LIMIT",
            next_required_user_action="explicit retry-limit override",
            shutdown_fixed="PASS",
            shutdown_rotating="PASS",
        )
        self.assertEqual(
            repeated["consumed_at_utc"], "2026-07-31T22:30:00+00:00"
        )
        self.assertEqual(repeated["final_evidence_sha256"], "e" * 64)


if __name__ == "__main__":
    unittest.main()
