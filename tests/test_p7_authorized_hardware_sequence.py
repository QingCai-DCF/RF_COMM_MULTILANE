from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import p7_hardware_safety as safety  # noqa: E402
import run_p7_authorized_hardware_sequence as subject  # noqa: E402


def write_bytes(path: Path, value: bytes) -> dict[str, object]:
    path.write_bytes(value)
    return subject._file_record(path)


class P7AuthorizedHardwareSequenceTests(unittest.TestCase):
    def test_diagnostic_suffix_matrix_is_exact_and_excludes_stationary(self) -> None:
        full = subject.expected_stage_contracts()
        ordinals = list(subject.DIAGNOSTIC_FULL_STAGE_ORDINALS)
        stages = [dict(full[ordinal - 1]) for ordinal in ordinals]
        self.assertEqual(
            [],
            subject.validate_stage_matrix(
                stages,
                plan_mode=subject.DIAGNOSTIC_PLAN_MODE,
                full_stage_ordinals=ordinals,
            ),
        )
        self.assertEqual(15, len(stages))
        self.assertNotIn("ps_stationary", [stage["group"] for stage in stages])
        bad_ordinals = list(ordinals)
        bad_ordinals[-1] = 66
        errors = subject.validate_stage_matrix(
            stages,
            plan_mode=subject.DIAGNOSTIC_PLAN_MODE,
            full_stage_ordinals=bad_ordinals,
        )
        self.assertTrue(any("full_stage_ordinals" in item for item in errors))

    def test_canonical_matrix_is_exact_and_stationary_is_once_last(self) -> None:
        stages = subject.expected_stage_contracts()
        self.assertEqual(66, len(stages))
        self.assertEqual([], subject.validate_stage_matrix(stages))
        groups = [stage["group"] for stage in stages]
        self.assertEqual(1, groups.count("safe_idle"))
        self.assertEqual(3, groups.count("p6_frame_regression"))
        self.assertEqual(48, groups.count("fragment_boundary"))
        self.assertEqual(9, groups.count("large_object_jtag"))
        self.assertLess(groups.index("ps_abort"), groups.index("ps_queue"))
        self.assertEqual("ps_stationary", groups[-1])
        self.assertEqual(1, groups.count("ps_stationary"))
        p6_masks = [
            stage["case"]["lane_mask"]
            for stage in stages
            if stage["group"] == "p6_frame_regression"
        ]
        self.assertEqual([1, 2, 3], p6_masks)
        self.assertTrue(
            all(
                stage["case"]["minimum_fragments"] >= 10
                for stage in stages
                if stage["group"] == "p6_frame_regression"
            )
        )

    def test_matrix_rejects_missing_boundary_and_duplicate_stationary(self) -> None:
        stages = subject.expected_stage_contracts()
        del stages[10]
        stages.append({"group": "ps_stationary", "risk_index": 80, "case": {}})
        errors = subject.validate_stage_matrix(stages)
        self.assertTrue(any("contract mismatch" in item for item in errors))
        self.assertTrue(any("exactly one stationary" in item for item in errors))

    def test_exact_command_parser_rejects_shell_and_unknown_arguments(self) -> None:
        unsafe = ["powershell", "-Command", "anything"]
        _wrapper, _options, errors = subject._parse_exact_wrapper_command(unsafe)
        self.assertTrue(any("exact Python" in item or "approved" in item for item in errors))
        command = [
            sys.executable,
            str(subject.JTAG_WRAPPER),
            "--execute-hardware",
            "--unknown-shell-hook",
            "value",
        ]
        _wrapper, _options, errors = subject._parse_exact_wrapper_command(command)
        self.assertTrue(any("unknown or positional" in item for item in errors))
        self.assertTrue(subject.is_exact_vivado_batch_launcher(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat"))
        self.assertFalse(subject.is_exact_vivado_batch_launcher(r"D:\Xilinx\Vivado\2023.1\bin\vivado.exe"))

    def test_wrapper_summary_rejects_any_inner_forced_cleanup_evidence(self) -> None:
        identity_patcher = mock.patch.object(
            subject.helper_identity,
            "validate_identity_validation_report",
            return_value=[],
        )
        identity_patcher.start()
        self.addCleanup(identity_patcher.stop)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutdown_bit = root / "shutdown.bit"
            shutdown_bit.write_bytes(b"authorized shutdown fixture")
            shutdown_before_result = root / "shutdown_before.txt"
            shutdown_after_result = root / "shutdown_after.txt"

            def write_shutdown_result(path: Path, programmed: Path = shutdown_bit) -> None:
                path.write_text(
                    "\n".join(
                        [
                            "P7_TCL_PROGRAMMING_ATTEMPTED=1",
                            f"TFDU_SHUTDOWN_PROGRAMMED={programmed}",
                            "P7_SHUTDOWN_RESULT=PASS",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

            write_shutdown_result(shutdown_before_result)
            write_shutdown_result(shutdown_after_result)
            summary_path = root / "summary.json"
            process = {
                "returncode": 0,
                "passed": True,
                "process_tree_reaped": True,
                "process_tree_terminated": False,
                "containment_cleanup_attempted": False,
                "containment_cleanup_terminated": False,
            }
            summary = {
                "P7_JTAG_AXI_SAFE_STAGE": "PASS",
                "stage_name": "safe_idle",
                "hardware_actions_executed": True,
                "network_used": False,
                "ethernet_used": False,
                "motion_used": False,
                "safety_validation": {"source_commit_requested": "b" * 40},
                "programmed_shutdown_before": True,
                "programmed_shutdown_after": True,
                "shutdown_before": {
                    **process,
                    "attempted": True,
                    "programming_attempted": True,
                    "result_file": str(shutdown_before_result),
                },
                "shutdown_after": {
                    **process,
                    "attempted": True,
                    "programming_attempted": True,
                    "result_file": str(shutdown_after_result),
                },
                "stage_process": dict(process),
                "backend_parse": {
                    "passed": True,
                    "raw_log_bound_to_this_hardware_process": True,
                },
            }
            stage_record = {
                "id": "safe_idle",
                "wrapper": str(subject.JTAG_WRAPPER),
                "options": {
                    "--source-commit": "b" * 40,
                    "--shutdown-bitstream": str(shutdown_bit),
                },
                "group": "safe_idle",
            }
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertEqual([], errors)
            summary["stage_process"]["containment_cleanup_attempted"] = True
            summary["stage_process"]["process_tree_terminated"] = True
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("candidate used" in item for item in errors))
            summary["stage_process"] = dict(process)
            summary["shutdown_after"]["containment_cleanup_attempted"] = True
            summary["shutdown_after"]["process_tree_terminated"] = True
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("shutdown-after used" in item for item in errors))
            summary["shutdown_after"] = {
                **process,
                "attempted": True,
                "programming_attempted": False,
                "result_file": str(shutdown_after_result),
            }
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("shutdown-after does not prove programming_attempted" in item for item in errors))

            summary["shutdown_after"]["programming_attempted"] = True
            echoed_stdout = root / "shutdown_after.stdout.log"
            echoed_stdout.write_text(
                '# puts "TFDU_SHUTDOWN_PROGRAMMED=' + str(shutdown_bit) + '"\n',
                encoding="utf-8",
            )
            summary["shutdown_after"]["stdout_path"] = str(echoed_stdout)
            shutdown_after_result.write_text(
                "P7_TCL_PROGRAMMING_ATTEMPTED=1\nSHUTDOWN_EXIT=0\nP7_SHUTDOWN_RESULT=PASS\n",
                encoding="utf-8",
            )
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("lacks exact TFDU_SHUTDOWN_PROGRAMMED" in item for item in errors))

            write_shutdown_result(shutdown_after_result, root / "wrong_shutdown.bit")
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("other than the authorized shutdown bit" in item for item in errors))

            write_shutdown_result(shutdown_after_result)
            summary["shutdown_before"]["programming_attempted"] = True
            shutdown_before_result.write_text(
                f"TFDU_SHUTDOWN_PROGRAMMED={shutdown_bit}\nP7_SHUTDOWN_RESULT=PASS\n",
                encoding="utf-8",
            )
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("shutdown-before fresh result lacks P7_TCL_PROGRAMMING_ATTEMPTED=1" in item for item in errors))

            write_shutdown_result(shutdown_before_result)
            summary["shutdown_before"]["attempted"] = False
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("shutdown-before does not prove attempted=true" in item for item in errors))
            summary["shutdown_before"]["attempted"] = True

            for duplicate_line in (
                "P7_TCL_PROGRAMMING_ATTEMPTED=1",
                f"TFDU_SHUTDOWN_PROGRAMMED={shutdown_bit}",
                "P7_SHUTDOWN_RESULT=PASS",
            ):
                write_shutdown_result(shutdown_after_result)
                with shutdown_after_result.open("a", encoding="utf-8") as handle:
                    handle.write(duplicate_line + "\n")
                summary_path.write_text(json.dumps(summary), encoding="utf-8")
                _summary, errors, _shutdown = subject.validate_wrapper_summary(
                    stage_record, summary_path, require_pass=True
                )
                self.assertTrue(any("shutdown-after fresh result contains duplicate markers" in item for item in errors))

    def test_sequence_dry_run_launches_no_stage_process(self) -> None:
        plan = {
            "errors": [],
            "path": str(ROOT / "fake-sequence-plan.json"),
            "sha256": "a" * 64,
            "source_commit": "b" * 40,
            "stage_count": 66,
            "stages": [],
            "offline_checkpoint": {"path": "checkpoint.json", "sha256": "c" * 64},
        }
        output = io.StringIO()
        with mock.patch.object(subject, "validate_sequence_plan", return_value=plan):
            with mock.patch.object(subject, "_run_stage_process") as run_mock:
                with contextlib.redirect_stdout(output):
                    returncode = subject.main(
                        [
                            "--sequence-plan",
                            "fake-sequence-plan.json",
                            "--sequence-plan-sha256",
                            "a" * 64,
                            "--json-summary",
                        ]
                    )
        self.assertEqual(0, returncode)
        run_mock.assert_not_called()
        self.assertIn('"P7_AUTHORIZED_HARDWARE_SEQUENCE": "DRY_RUN_VALIDATED"', output.getvalue())
        self.assertIn('"hardware_actions_executed": false', output.getvalue())

    def test_ps_wrapper_summary_binds_frozen_shutdown_path_hash_and_fresh_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = b"authorized frozen shutdown fixture"
            authorized_shutdown = root / "authorized_shutdown.bit"
            frozen_shutdown = root / "p7_frozen_shutdown.bit"
            authorized_shutdown.write_bytes(payload)
            frozen_shutdown.write_bytes(payload)
            expected_sha = subject.sha256_file(authorized_shutdown)
            before_result = root / "shutdown_before_result.txt"
            after_result = root / "shutdown_after_result.txt"
            marker_text = "\n".join(
                [
                    "P7_TCL_PROGRAMMING_ATTEMPTED=1",
                    f"TFDU_SHUTDOWN_PROGRAMMED={frozen_shutdown}",
                    "P7_SHUTDOWN_RESULT=PASS",
                    "",
                ]
            )
            before_result.write_text(marker_text, encoding="utf-8")
            after_result.write_text(marker_text, encoding="utf-8")
            process = {
                "returncode": 0,
                "passed": True,
                "process_tree_reaped": True,
                "process_tree_terminated": False,
                "containment_cleanup_attempted": False,
                "containment_cleanup_terminated": False,
            }
            summary = {
                "P7_PS_APPLICATION_SAFE_STAGE": "PASS",
                "stage_name": "ps_functional",
                "mode": "functional",
                "hardware_actions_executed": True,
                "network_used": False,
                "ethernet_used": False,
                "motion_used": False,
                "safety_validation": {"source_commit_requested": "b" * 40},
                "frozen_shutdown": subject._file_record(frozen_shutdown),
                "programmed_shutdown_before": True,
                "programmed_shutdown_after": True,
                "shutdown_before": {
                    **process,
                    "attempted": True,
                    "programming_attempted": True,
                    "result_file": str(before_result),
                },
                "shutdown_after": {
                    **process,
                    "attempted": True,
                    "programming_attempted": True,
                    "result_file": str(after_result),
                },
                "ps_process": dict(process),
                "postprocess": {"passed": True},
            }
            summary_path = root / "summary.json"
            stage_record = {
                "id": "ps_functional",
                "wrapper": str(subject.PS_WRAPPER),
                "options": {
                    "--source-commit": "b" * 40,
                    "--shutdown-bitstream": str(authorized_shutdown),
                    "--shutdown-bitstream-sha256": expected_sha,
                },
                "group": "ps_functional",
            }
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertEqual([], errors)
            self.assertEqual(str(frozen_shutdown), shutdown["tfdu_shutdown_programmed"])
            self.assertTrue(shutdown["tfdu_shutdown_programmed_exact"])

            frozen_shutdown.write_bytes(b"tampered")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("actual SHA256 mismatches authorization" in item for item in errors))
            frozen_shutdown.write_bytes(payload)

            summary["frozen_shutdown"]["sha256"] = "0" * 64
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            _summary, errors, _shutdown = subject.validate_wrapper_summary(
                stage_record, summary_path, require_pass=True
            )
            self.assertTrue(any("SHA256 mismatches authorized" in item for item in errors))

    def test_resume_skips_only_hash_verified_pass_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stdout = write_bytes(root / "stdout.log", b"ok\n")
            stderr = write_bytes(root / "stderr.log", b"")
            summary = write_bytes(root / "summary.json", b"{}\n")
            stage = {
                "id": "safe_idle",
                "group": "safe_idle",
                "risk_index": 10,
                "case": {},
                "command": [sys.executable, str(subject.JTAG_WRAPPER)],
                "wrapper": str(subject.JTAG_WRAPPER),
                "options": {"--source-commit": "b" * 40},
                "summary_path": str(root / "summary.json"),
            }
            plan = {
                "path": str(root / "plan.json"),
                "sha256": "a" * 64,
                "source_commit": "b" * 40,
                "offline_checkpoint": {"path": str(root / "checkpoint.json"), "sha256": "c" * 64},
                "stages": [stage],
            }
            attempt = {
                "stage_index": 0,
                "stage_id": "safe_idle",
                "group": "safe_idle",
                "command": stage["command"],
                "started_at_utc": "2026-07-10T00:00:00+00:00",
                "ended_at_utc": "2026-07-10T00:00:01+00:00",
                "state": "TERMINAL",
                "result": "PASS",
                "process": {
                    "returncode": 0,
                    "process_tree_reaped": True,
                    "process_tree_terminated": False,
                    "containment_closed": True,
                    "descendant_count_after": 0,
                    "containment_cleanup_attempted": False,
                    "containment_cleanup_terminated": False,
                    "stdout_file": stdout,
                    "stderr_file": stderr,
                },
                "summary_file": summary,
            }
            ledger = {
                "schema": subject.LEDGER_SCHEMA,
                "source_commit": plan["source_commit"],
                "sequence_plan": {"path": plan["path"], "sha256": plan["sha256"]},
                "offline_checkpoint": {
                    "path": plan["offline_checkpoint"]["path"],
                    "sha256": plan["offline_checkpoint"]["sha256"],
                    "result": "PASS",
                },
                "attempt_count": 1,
                "completed_stage_count": 1,
                "next_stage_index": 1,
                "attempts": [attempt],
            }
            with mock.patch.object(subject, "validate_wrapper_summary", return_value=({}, [], {})):
                prefix, errors = subject.validate_resume_ledger(ledger, plan)
                self.assertEqual((1, []), (prefix, errors))
                attempt["process"]["containment_cleanup_attempted"] = True
                attempt["process"]["process_tree_terminated"] = True
                prefix, errors = subject.validate_resume_ledger(ledger, plan)
                self.assertEqual(0, prefix)
                self.assertTrue(any("forced-cleanup" in item for item in errors))
                attempt["process"]["containment_cleanup_attempted"] = False
                attempt["process"]["process_tree_terminated"] = False
                attempt["result"] = "FAIL"
                prefix, errors = subject.validate_resume_ledger(ledger, plan)
        self.assertEqual(0, prefix)
        self.assertTrue(any("only verified PASS" in item for item in errors))

    def test_unresolved_stationary_launch_intent_permanently_blocks_resume(self) -> None:
        stage = {
            "id": "stationary_final",
            "group": "ps_stationary",
            "risk_index": 80,
            "case": {},
            "command": [sys.executable, str(subject.PS_WRAPPER)],
            "wrapper": str(subject.PS_WRAPPER),
            "options": {"--source-commit": "b" * 40},
            "summary_path": "missing-summary.json",
        }
        plan = {
            "path": "plan.json",
            "sha256": "a" * 64,
            "source_commit": "b" * 40,
            "offline_checkpoint": {"path": "checkpoint.json", "sha256": "c" * 64},
            "stages": [stage],
        }
        intent = {
            "attempt": 1,
            "stage_index": 0,
            "stage_id": "stationary_final",
            "group": "ps_stationary",
            "risk_index": 80,
            "case": {},
            "command": stage["command"],
            "state": "LAUNCH_INTENT",
            "result": "IN_PROGRESS",
            "launch_intent_at_utc": "2026-07-10T00:00:00+00:00",
            "started_at_utc": None,
            "ended_at_utc": None,
            "process": {},
            "summary_file": {"path": "missing-summary.json", "missing": True},
        }
        ledger = {
            "schema": subject.LEDGER_SCHEMA,
            "source_commit": plan["source_commit"],
            "sequence_plan": {"path": plan["path"], "sha256": plan["sha256"]},
            "offline_checkpoint": {
                "path": plan["offline_checkpoint"]["path"],
                "sha256": plan["offline_checkpoint"]["sha256"],
                "result": "PASS",
            },
            "attempt_count": 1,
            "completed_stage_count": 0,
            "next_stage_index": 0,
            "attempts": [intent],
        }
        prefix, errors = subject.validate_resume_ledger(ledger, plan)
        self.assertEqual(0, prefix)
        joined = "\n".join(errors)
        self.assertIn("unresolved launch intent", joined)
        self.assertIn("stationary attempt exists without a verified final sequence PASS", joined)

    def test_executor_stops_after_first_failed_wrapper_without_second_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            hardware_root = Path(temp)
            stages = []
            for index in range(2):
                evidence = hardware_root / f"stage{index}"
                stages.append(
                    {
                        "id": f"stage_{index}",
                        "group": "safe_idle" if index == 0 else "p6_frame_regression",
                        "risk_index": 10 + index * 10,
                        "case": {},
                        "command": [sys.executable, str(subject.JTAG_WRAPPER)],
                        "wrapper": str(subject.JTAG_WRAPPER),
                        "options": {"--abort-file": str(hardware_root / "ABORT_NOW.txt")},
                        "evidence_dir": str(evidence),
                        "summary_path": str(evidence / "p7_jtag_axi_stage_summary.json"),
                        "wrapper_timeout_sec": 60,
                    }
                )
            plan = {
                "path": str(hardware_root / "plan.json"),
                "sha256": "a" * 64,
                "source_commit": "b" * 40,
                "stage_count": 2,
                "stages": stages,
                "offline_checkpoint": {
                    "path": str(hardware_root / "checkpoint.json"),
                    "sha256": "c" * 64,
                },
                "errors": [],
            }
            args = argparse.Namespace(
                source_commit="b" * 40,
                max_runtime_sec=1800,
                shutdown_on_exit=True,
                no_ethernet=True,
                no_motion=True,
                lane_count=2,
                max_lane_mask="0x3",
                execution_ledger=str(hardware_root / "ledger.json"),
                resume=False,
            )
            failed_process = {
                "returncode": 1,
                "process_tree_reaped": True,
                "containment_closed": True,
                "descendant_count_after": 0,
                "started_at_utc": "2026-07-10T00:00:00+00:00",
                "ended_at_utc": "2026-07-10T00:00:01+00:00",
            }
            observed_intent: dict[str, object] = {}

            def fail_after_observing_intent(**_kwargs: object) -> dict[str, object]:
                snapshot = json.loads((hardware_root / "ledger.json").read_text(encoding="utf-8"))
                observed_intent.update(snapshot["attempts"][-1])
                return failed_process

            with mock.patch.object(subject, "HARDWARE_ROOT", hardware_root):
                with mock.patch.dict(os.environ, {safety.AUTH_ENV: safety.AUTH_ENV_VALUE}, clear=False):
                    with mock.patch.object(
                        subject,
                        "validate_plan_vivado_helper_identity",
                        return_value={"status": "PASS", "errors": []},
                    ), mock.patch.object(
                        subject, "_run_stage_process", side_effect=fail_after_observing_intent
                    ) as run_mock:
                        with mock.patch.object(
                            subject,
                            "validate_wrapper_summary",
                            return_value=(None, ["synthetic offline failure"], {"present": False}),
                        ):
                            returncode, manifest = subject._execute_sequence(args, plan)
            self.assertEqual(1, returncode)
            self.assertEqual("FAIL", manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"])
            self.assertEqual(1, run_mock.call_count)
            self.assertEqual("LAUNCH_INTENT", observed_intent["state"])
            self.assertEqual("IN_PROGRESS", observed_intent["result"])
            ledger = json.loads((hardware_root / "ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(1, ledger["attempt_count"])
            self.assertEqual(0, ledger["next_stage_index"])

    def test_helper_prelaunch_failure_creates_no_execution_ledger_or_stage_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = root / "sequence_execution_ledger.json"
            plan = {
                "path": str(root / "plan.json"),
                "sha256": "a" * 64,
                "source_commit": "b" * 40,
                "stage_count": 1,
                "stages": [
                    {
                        "id": "p7_safe_idle",
                        "group": "safe_idle",
                        "options": {"--vivado-path": r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat"},
                        "summary_path": str(root / "stage" / "p7_jtag_axi_stage_summary.json"),
                    }
                ],
                "offline_checkpoint": {"path": "checkpoint.json", "sha256": "c" * 64},
                "errors": [],
            }
            args = argparse.Namespace(
                source_commit="b" * 40,
                max_runtime_sec=1800,
                shutdown_on_exit=True,
                no_ethernet=True,
                no_motion=True,
                lane_count=2,
                max_lane_mask="0x3",
                execution_ledger=str(ledger),
                resume=False,
            )
            failure = {
                "status": "FAIL",
                "error_code": "VIVADO_HELPER_RUNTIME_HASH_PROFILE_MISMATCH",
                "errors": [{"error_code": "VIVADO_HELPER_RUNTIME_HASH_PROFILE_MISMATCH"}],
                "hardware_actions_executed": False,
                "campaign_attempt_created": False,
            }
            with mock.patch.dict(
                os.environ, {safety.AUTH_ENV: safety.AUTH_ENV_VALUE}, clear=False
            ), mock.patch.object(
                subject, "HARDWARE_ROOT", root
            ), mock.patch.object(
                subject, "validate_plan_vivado_helper_identity", return_value=failure
            ), mock.patch.object(subject, "_run_stage_process") as run_mock:
                returncode, manifest = subject._execute_sequence(args, plan)
            self.assertEqual(2, returncode)
            self.assertEqual("BLOCKED_PRELAUNCH", manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"])
            self.assertFalse(ledger.exists())
            self.assertFalse(manifest["hardware_actions_executed"])
            run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
