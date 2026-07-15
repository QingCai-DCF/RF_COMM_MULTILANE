from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import generate_p7_authorized_sequence_plan as subject  # noqa: E402
import run_p7_authorized_hardware_sequence as sequence  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload: bytes) -> tuple[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return str(path), sha(path)


def write_json(path: Path, payload: dict[str, object]) -> tuple[str, str]:
    return write(path, (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))


def option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]


class GenerateP7AuthorizedSequencePlanTests(unittest.TestCase):
    def test_diagnostic_suffix_selection_is_exact_zero_stationary_matrix(self) -> None:
        full = subject.build_stage_specs()
        selected = subject.select_stage_specs(full, diagnostic_suffix55=True)
        self.assertEqual(list(sequence.DIAGNOSTIC_FULL_STAGE_ORDINALS), [spec.index for spec in selected])
        self.assertEqual(15, len(selected))
        self.assertEqual(["safe_idle", "p6_frame_regression", "p6_frame_regression", "p6_frame_regression"], [spec.group for spec in selected[:4]])
        self.assertEqual(7, sum(spec.group == "large_object_jtag" for spec in selected))
        self.assertEqual(4, sum(spec.group.startswith("ps_") for spec in selected))
        self.assertFalse(any(spec.group == "ps_stationary" for spec in selected))
        stages = [
            {"group": spec.group, "risk_index": spec.risk_index, "case": spec.case}
            for spec in selected
        ]
        self.assertEqual(
            [],
            sequence.validate_stage_matrix(
                stages,
                plan_mode=sequence.DIAGNOSTIC_PLAN_MODE,
                full_stage_ordinals=list(sequence.DIAGNOSTIC_FULL_STAGE_ORDINALS),
            ),
        )
        tampered = list(stages)
        tampered[-1] = {"group": "ps_stationary", "risk_index": 80, "case": {}}
        errors = sequence.validate_stage_matrix(
            tampered,
            plan_mode=sequence.DIAGNOSTIC_PLAN_MODE,
            full_stage_ordinals=list(sequence.DIAGNOSTIC_FULL_STAGE_ORDINALS),
        )
        self.assertTrue(any("stationary" in item for item in errors))

    def test_adaptive_diagnostic_selection_is_prefix_plus_exact_unresolved_suffix(self) -> None:
        full = subject.build_stage_specs()
        selected = subject.select_stage_specs(
            full,
            diagnostic_suffix55=False,
            diagnostic_first_ordinal=62,
        )
        ordinals = [spec.index for spec in selected]
        self.assertEqual([1, 2, 3, 4, 62, 63, 64, 65], ordinals)
        stages = [
            {"group": spec.group, "risk_index": spec.risk_index, "case": spec.case}
            for spec in selected
        ]
        self.assertEqual(
            [],
            sequence.validate_stage_matrix(
                stages,
                plan_mode=sequence.ADAPTIVE_DIAGNOSTIC_PLAN_MODE,
                full_stage_ordinals=ordinals,
            ),
        )
        self.assertFalse(any(spec.group == "ps_stationary" for spec in selected))
        generation_source = inspect.getsource(subject.generate_sequence)
        self.assertIn('"plan_mode": plan_mode', generation_source)
        self.assertNotIn('"plan_mode": sequence.DIAGNOSTIC_PLAN_MODE', generation_source)
        with self.assertRaises(ValueError):
            subject.select_stage_specs(
                full,
                diagnostic_suffix55=False,
                diagnostic_first_ordinal=66,
            )

    def test_stage_specs_are_exact_and_1m_budget_is_separately_1800_capable(self) -> None:
        specs = subject.build_stage_specs()
        self.assertEqual(66, len(specs))
        groups = [spec.group for spec in specs]
        self.assertEqual(1, groups.count("safe_idle"))
        self.assertEqual(3, groups.count("p6_frame_regression"))
        self.assertEqual(48, groups.count("fragment_boundary"))
        self.assertEqual(9, groups.count("large_object_jtag"))
        self.assertEqual(1, groups.count("ps_stationary"))
        self.assertEqual("ps_stationary", groups[-1])
        self.assertLess(groups.index("ps_abort"), groups.index("ps_queue"))
        one_mib = [
            spec
            for spec in specs
            if spec.group == "large_object_jtag" and spec.case["object_size"] == 1_048_576
        ]
        self.assertEqual(4, len(one_mib))
        for spec in one_mib:
            self.assertEqual(1800, spec.max_runtime_sec)
            self.assertEqual(60, spec.preflight_timeout_sec)
            self.assertEqual(60, spec.shutdown_timeout_sec)
            self.assertEqual(1400, spec.stage_timeout_sec)
            feasibility = subject.jtag_backend.runtime_feasibility(
                subject.jtag_backend.transaction_shape(1_048_576)["operation_count"],
                jtag_frequency_hz=subject.CANONICAL_JTAG_FREQUENCY_HZ,
                authorized_runtime_sec=spec.max_runtime_sec,
                preflight_timeout_sec=spec.preflight_timeout_sec,
                shutdown_timeout_sec=spec.shutdown_timeout_sec,
                configured_stage_timeout_sec=spec.stage_timeout_sec,
            )
            budget = feasibility["global_runtime_budget"]
            self.assertTrue(budget["feasible"])
            self.assertEqual(120, budget["containment_allowance_seconds"])
            self.assertEqual(65, budget["other_guard_seconds"])
            self.assertEqual(45, budget["bookkeeping_guard_seconds"])
            self.assertEqual(1765, budget["configured_global_timeout_ceiling_sec"])
            self.assertEqual(35, budget["configured_unallocated_margin_seconds"])
            self.assertEqual(1372, feasibility["minimum_stage_runtime_sec"])
            self.assertEqual(1920, spec.wrapper_timeout_sec)
        stationary = specs[-1]
        self.assertEqual(1800, stationary.max_runtime_sec)
        self.assertEqual("stationary", stationary.mode)
        self.assertTrue(
            all(
                spec.wrapper_timeout_sec >= 1440
                for spec in specs
                if spec.kind == "ps" and spec.group != "ps_stationary"
            )
        )
        self.assertEqual(2640, stationary.wrapper_timeout_sec)
        safe_idle = specs[0]
        self.assertEqual(600, safe_idle.max_runtime_sec)
        self.assertEqual(60, safe_idle.shutdown_timeout_sec)
        self.assertEqual(90, safe_idle.stage_timeout_sec)
        self.assertEqual(425, 30 + 2 * 60 + 90 + 120 + 65)
        ordinary_jtag = next(spec for spec in specs if spec.group == "fragment_boundary")
        self.assertEqual(960, ordinary_jtag.max_runtime_sec)
        self.assertEqual(60, ordinary_jtag.shutdown_timeout_sec)
        self.assertEqual(550, ordinary_jtag.stage_timeout_sec)
        self.assertEqual(915, 60 + 2 * 60 + 550 + 120 + 65)
        self.assertEqual(66, len({spec.stage_id for spec in specs}))
        self.assertTrue(all(len(spec.stage_id) <= 64 for spec in specs))
        subject.validate_stage_specs(specs)

    def test_safe_idle_transaction_cannot_start_commit_or_write_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "safe_idle.transactions.txt"
            subject.write_safe_idle_transaction(path)
            text = path.read_text(encoding="utf-8")
        self.assertIn("META EVIDENCE_KIND safe_idle", text)
        operation_names = [
            line.split()[0]
            for line in text.splitlines()
            if line and not line.startswith("META ") and not line.startswith("P7_JTAG_")
        ]
        self.assertFalse({"START", "COMMIT", "PAYLOAD", "PAYLOAD_WRITE"} & set(operation_names))
        writes = [line for line in text.splitlines() if line.startswith("W32 ")]
        self.assertEqual(["W32 0x43c00100 0x00000030"], writes)
        self.assertEqual(12, sum(line.startswith("ASSERT32 ") for line in text.splitlines()))

    def test_dirty_worktree_is_rejected_before_any_output(self) -> None:
        args = argparse.Namespace(
            run_id="test_run",
            source_commit="a" * 40,
            board_id=subject.CANONICAL_BOARD_ID,
            expected_part=subject.CANONICAL_PART,
            expected_target=subject.CANONICAL_TARGET,
            hw_server_url=subject.CANONICAL_HW_SERVER_URL,
            jtag_frequency_hz=subject.CANONICAL_JTAG_FREQUENCY_HZ,
            axi_base_address=subject.CANONICAL_AXI_BASE,
            p6_session=subject.DEFAULT_P6_SESSION,
        )
        with mock.patch.object(subject, "git_state", return_value=("a" * 40, [" M source.c"], None)):
            with self.assertRaisesRegex(ValueError, "permits only post-gate"):
                subject.validate_preconditions(args)

    def test_only_generated_gate_dirt_is_allowlisted(self) -> None:
        allowed, rejected = subject.classify_dirty_entries(
            [
                " M evidence/generated/p7_offline_gate_summary.json",
                "?? evidence/generated/new_gate_output.md",
                " M evidence/hardware/p7/p7_run_sequence_ledger.json",
                " M tools/run_p7_gate.py",
                "?? evidence/hardware/p7/fake.json",
                "R  software/a.c -> evidence/generated/a.c",
            ]
        )
        self.assertEqual(3, len(allowed))
        self.assertEqual(3, len(rejected))

    def test_campaign_runtime_ledger_allowance_is_exact_validated_and_untracked_only(self) -> None:
        ledger = (
            "evidence/hardware/p7/stage66_diagnostic_campaign/"
            "p7_stage66_stationary_diagnostic_20260715/campaign_ledger.json"
        )
        entries = [
            f"?? {ledger}",
            f"A  {ledger}",
            "?? evidence/hardware/p7/stage66_diagnostic_campaign/"
            "p7_stage66_stationary_diagnostic_20260715/campaign_execution.lock",
            "?? evidence/hardware/p7/stage66_diagnostic_campaign/arbitrary.json",
        ]
        allowed, rejected = subject.classify_dirty_entries(
            entries,
            additional_exact_untracked=frozenset({ledger}),
        )
        self.assertEqual([f"?? {ledger}"], allowed)
        self.assertEqual(entries[1:], rejected)
        ordinary_allowed, ordinary_rejected = subject.classify_dirty_entries(entries)
        self.assertEqual([], ordinary_allowed)
        self.assertEqual(entries, ordinary_rejected)

    def test_post_gate_p7_content_addressed_allowance_is_exact_untracked_only(self) -> None:
        digest = "a" * 64
        exact_map = f"evidence/hardware/p7/artifacts/p7_runtime_{digest}.map"
        entries = [
            f"?? {exact_map}",
            f"A  {exact_map}",
            "?? evidence/hardware/p7/artifacts/arbitrary.map",
            f"?? evidence/hardware/p7/artifacts/p7_runtime_{'b' * 64}.map",
        ]
        allowed, rejected = subject.classify_dirty_entries(
            entries,
            additional_exact_untracked=frozenset({exact_map}),
        )
        self.assertEqual([f"?? {exact_map}"], allowed)
        self.assertEqual(entries[1:], rejected)

    def test_post_gate_p7_outputs_are_summary_hash_and_checkpoint_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            artifact_root = root / "evidence" / "hardware" / "p7" / "artifacts"
            artifact_records: dict[str, dict[str, str]] = {}
            for kind, prefix, suffix, payload in (
                ("elf", "p7_runtime_", ".elf", b"elf\n"),
                ("linker_map", "p7_runtime_", ".map", b"map\n"),
                ("bsp_xparameters", "p7_bsp_xparameters_", ".h", b"header\n"),
            ):
                digest = hashlib.sha256(payload).hexdigest()
                relative = f"evidence/hardware/p7/artifacts/{prefix}{digest}{suffix}"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                artifact_records[kind] = {"sha256": digest, "immutable": relative}
            summary_path = (
                root
                / "evidence"
                / "generated"
                / "vitis"
                / "p7_ps_runtime"
                / "p7_ps_runtime_build_summary.json"
            )
            _summary_name, summary_digest = write_json(
                summary_path,
                {
                    "P7_PS_RUNTIME_BUILD": "PASS",
                    "hardware_actions_executed": False,
                    "artifacts": artifact_records,
                },
            )
            args = argparse.Namespace(
                p7_build_summary=str(summary_path),
                p7_build_summary_sha256=summary_digest,
            )
            with mock.patch.object(subject, "ROOT", root):
                outputs = subject.validate_post_gate_p7_content_addressed_outputs(args)
                expected = {
                    record["immutable"]: record["sha256"]
                    for record in artifact_records.values()
                }
                self.assertEqual(expected, outputs)
                subject.validate_post_gate_p7_checkpoint_bindings(
                    outputs, {"checkpoint_input_hashes": dict(outputs)}
                )
                missing_map = dict(outputs)
                missing_map.pop(artifact_records["linker_map"]["immutable"])
                with self.assertRaisesRegex(ValueError, "not exactly bound"):
                    subject.validate_post_gate_p7_checkpoint_bindings(
                        outputs, {"checkpoint_input_hashes": missing_map}
                    )
                map_path = root / artifact_records["linker_map"]["immutable"]
                map_path.write_bytes(b"tampered\n")
                with self.assertRaisesRegex(ValueError, "immutable output SHA256 mismatch"):
                    subject.validate_post_gate_p7_content_addressed_outputs(args)

    def test_post_gate_p7_output_rejects_noncanonical_summary_path(self) -> None:
        args = argparse.Namespace(
            p7_build_summary="evidence/generated/not_canonical.json",
            p7_build_summary_sha256="a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "canonical P7 build summary"):
            subject.validate_post_gate_p7_content_addressed_outputs(args)

    def test_noncanonical_live_identity_is_rejected_before_git_or_outputs(self) -> None:
        args = argparse.Namespace(
            board_id="wrong-board",
            expected_part=subject.CANONICAL_PART,
            expected_target=subject.CANONICAL_TARGET,
            hw_server_url=subject.CANONICAL_HW_SERVER_URL,
            jtag_frequency_hz=subject.CANONICAL_JTAG_FREQUENCY_HZ,
            axi_base_address=subject.CANONICAL_AXI_BASE,
            p6_session=subject.DEFAULT_P6_SESSION,
        )
        with self.assertRaisesRegex(ValueError, "canonical live board"):
            subject.validate_canonical_identity(args)

    def test_canonical_xdc_pinmap_register_goal_and_profiles_are_hard_locked(self) -> None:
        hashes = {name: f"{index:064x}"[-64:] for index, name in enumerate(subject.ARTIFACT_ARGUMENTS, 1)}
        p6 = ROOT / "evidence" / "hardware" / "p6" / "bitstreams"
        p7 = ROOT / "evidence" / "hardware" / "p7" / "artifacts"
        artifacts = {
            "jtag_bitstream": subject.Artifact(
                (p6 / f"p6_jtag_dynamic_transport_{hashes['jtag_bitstream']}.bit").resolve(),
                hashes["jtag_bitstream"],
            ),
            "jtag_ltx": subject.Artifact(
                (p6 / f"p6_jtag_dynamic_transport_{hashes['jtag_ltx']}.ltx").resolve(),
                hashes["jtag_ltx"],
            ),
            "ps_bitstream": subject.Artifact(
                (p6 / f"p6_ps_dynamic_transport_{hashes['ps_bitstream']}.bit").resolve(),
                hashes["ps_bitstream"],
            ),
            "xsa": subject.Artifact(
                (p6 / f"p6_ps_dynamic_transport_{hashes['xsa']}.xsa").resolve(), hashes["xsa"]
            ),
            "elf": subject.Artifact(
                (p7 / f"p7_runtime_{hashes['elf']}.elf").resolve(), hashes["elf"]
            ),
            "goal_plan": subject.Artifact(
                (p7 / f"p7_plan_{hashes['goal_plan']}.md").resolve(), hashes["goal_plan"]
            ),
            "active_xdc": subject.Artifact(
                (ROOT / "constraints/active/PORT1.generated.xdc").resolve(), hashes["active_xdc"]
            ),
            "pinmap": subject.Artifact(
                (ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv").resolve(),
                hashes["pinmap"],
            ),
            "register_map": subject.Artifact(
                (ROOT / "config/register_map/ir_axi_regs.yaml").resolve(), hashes["register_map"]
            ),
            "jtag_profile": subject.Artifact(
                (ROOT / "profiles/p7/p7_stationary_app_30min.json").resolve(),
                hashes["jtag_profile"],
            ),
            "ps_functional_profile": subject.Artifact(
                (ROOT / "profiles/p7/p7_ps_application_functional.json").resolve(),
                hashes["ps_functional_profile"],
            ),
            "ps_stationary_profile": subject.Artifact(
                (ROOT / "profiles/p7/p7_stationary_app_30min.json").resolve(),
                hashes["ps_stationary_profile"],
            ),
            "shutdown_bitstream": subject.Artifact(
                (ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit").resolve(),
                hashes["shutdown_bitstream"],
            ),
            "active_profile": subject.Artifact(
                (ROOT / "board_profiles/ACTIVE_PROFILE.json").resolve(), hashes["active_profile"]
            ),
            "lane1_promotion_summary": subject.Artifact(
                (ROOT / "evidence/generated/p7_lane1_promotion_summary.json").resolve(),
                hashes["lane1_promotion_summary"],
            ),
        }
        subject.validate_canonical_artifact_paths(
            artifacts, subject.safety.DEFAULT_ABORT_FILE.resolve()
        )
        artifacts["active_xdc"] = subject.Artifact(
            (ROOT / "legacy/PORT1.xdc").resolve(), hashes["active_xdc"]
        )
        with self.assertRaisesRegex(ValueError, "active_xdc must be canonical"):
            subject.validate_canonical_artifact_paths(
                artifacts, subject.safety.DEFAULT_ABORT_FILE.resolve()
            )

    def test_source_has_no_authorization_environment_mutation_or_hardware_launcher(self) -> None:
        source = Path(subject.__file__).read_text(encoding="utf-8")
        self.assertNotIn("os.environ[", source)
        self.assertNotIn("os.putenv", source)
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("jtag_safe_wrapper.main(", source)
        self.assertNotIn("ps_safe_wrapper.main(", source)
        self.assertIn("sequence.is_exact_vivado_batch_launcher(vivado)", source)

    def test_campaign_child_dry_validation_defers_only_runtime_ledger_state(self) -> None:
        spec = subject.build_stage_specs()[-1]
        parsed = argparse.Namespace(
            stage66_diagnostic_campaign=True,
            execute_hardware=True,
            mode="stationary",
        )
        parser = mock.Mock()
        parser.parse_args.return_value = parsed
        external_auth_error = (
            f"external environment authorization required: "
            f"{subject.safety.AUTH_ENV}={subject.safety.AUTH_ENV_VALUE}"
        )

        def validate_offline_view(
            args: argparse.Namespace, _readiness: dict[str, object]
        ) -> list[str]:
            self.assertIsNot(args, parsed)
            self.assertFalse(args.execute_hardware)
            self.assertTrue(args.stage66_diagnostic_campaign)
            return []

        with mock.patch.object(
            subject.ps_safe_wrapper, "build_parser", return_value=parser
        ), mock.patch.object(
            subject.ps_safe_wrapper,
            "validate_core_readiness",
            return_value={"status": "PASS", "errors": []},
        ), mock.patch.object(
            subject.ps_safe_wrapper,
            "_stage_validation",
            side_effect=validate_offline_view,
        ), mock.patch.object(
            subject.safety,
            "validate_request",
            side_effect=lambda args: (
                self.assertIs(args, parsed) or {"errors": [external_auth_error]}
            ),
        ):
            report = subject.validate_child_wrapper_dry(
                spec,
                ["python", "wrapper.py", "--execute-hardware"],
            )

        self.assertTrue(parsed.execute_hardware)
        self.assertTrue(report["emitted_execute_hardware"])
        self.assertEqual(
            "DEFERRED_TO_OUTER_EXECUTOR_LOCKED_LAUNCH",
            report["campaign_runtime_ledger_validation"],
        )
        self.assertEqual(
            "PASS_OFFLINE_WITH_EXTERNAL_EXECUTION_ENVIRONMENT_INTENTIONALLY_ABSENT",
            report["common_safety_validation"],
        )

    def test_full_offline_generation_has_unique_auth_hashes_and_valid_exact_plan(self) -> None:
        source_commit = "a" * 40
        tree_sha = "b" * 64
        run_id = "ut_" + uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(dir=subject.BUILD_ROOT) as bundle_temp:
            with tempfile.TemporaryDirectory(dir=subject.AUTH_ROOT) as auth_temp:
                base = Path(auth_temp)
                artifacts: dict[str, tuple[str, str]] = {}
                for name in (
                    "goal_plan",
                    "jtag_bitstream",
                    "jtag_ltx",
                    "ps_bitstream",
                    "xsa",
                    "elf",
                    "active_xdc",
                    "pinmap",
                    "register_map",
                    "shutdown_bitstream",
                    "ps7_init",
                ):
                    artifacts[name] = write(base / f"{name}.bin", (name + "\n").encode())
                functional_profile = {
                    "stage": "P7_PS_APPLICATION_FUNCTIONAL",
                    "network_required": False,
                    "motion_required": False,
                    "lane_count": 2,
                    "allowed_lane_masks": ["0x1", "0x2", "0x3"],
                    "max_lane_mask": "0x3",
                    "max_runtime_sec": 900,
                    "startup_wait_us": 500,
                    "stuck_high_trip_us": 10,
                    "continuous_txd_high_hard_limit_us": 80,
                    "duty_guard_required": True,
                    "shutdown_on_exit": True,
                }
                stationary_profile = {
                    **functional_profile,
                    "stage": "P7_STATIONARY_APP_30MIN",
                    "max_runtime_sec": 1800,
                    "calibration_window_sec": 300,
                    "acceptance_window_sec": 1500,
                    "sample_interval_sec": 30,
                    "calibration_is_part_of_final_30min_run": True,
                }
                artifacts["ps_functional_profile"] = write_json(
                    base / "functional_profile.json", functional_profile
                )
                artifacts["ps_stationary_profile"] = write_json(
                    base / "stationary_profile.json", stationary_profile
                )
                artifacts["jtag_profile"] = artifacts["ps_stationary_profile"]
                p6_summary = {
                    "P6_PS_CANDIDATE_BUILD": "PASS",
                    "artifacts": {
                        "bit": {"sha256": artifacts["ps_bitstream"][1]},
                        "xsa": {"sha256": artifacts["xsa"][1]},
                    },
                }
                artifacts["p6_build_summary"] = write_json(base / "p6_build.json", p6_summary)
                p7_summary = {
                    "P7_PS_RUNTIME_BUILD": "PASS",
                    "counts_per_second": subject.COUNTS_PER_SECOND,
                    "xsa_sha256": artifacts["xsa"][1],
                    "artifacts": {"elf": {"sha256": artifacts["elf"][1]}},
                }
                artifacts["p7_build_summary"] = write_json(base / "p7_build.json", p7_summary)
                artifacts["core_readiness_attestation"] = write_json(
                    base / "readiness.json", {"P7_PS_CORE_HARDWARE_READINESS": "PASS"}
                )
                artifacts["active_profile"] = write_json(
                    base / "active_profile.json", {"lane1_reliable_enabled": True}
                )
                artifacts["lane1_promotion_summary"] = write_json(
                    base / "promotion.json", {"P7_LANE1_RELIABILITY_PROMOTION_GATE": "PASS"}
                )
                checkpoint_input = ROOT / "tools" / "run_p7_authorized_hardware_sequence.py"
                checkpoint = {
                    "P7_OFFLINE_GATE": "PASS",
                    "hardware_actions_executed": False,
                    "NO_HARDWARE_ACTIONS_EXECUTED": True,
                    "HARDWARE_ACCEPTANCE": "PENDING_HW",
                    "checks": {
                        "P7_CLEAN_SOURCE_CHECKPOINT": True,
                        "P7_CHECKPOINT_INPUT_HASHES": True,
                    },
                    "source_commit": source_commit,
                    "dirty_worktree": False,
                    "source_tree_listing_sha256": tree_sha,
                    "checkpoint_input_count": 1,
                    "checkpoint_input_hashes": {
                        "tools/run_p7_authorized_hardware_sequence.py": sha(checkpoint_input)
                    },
                }
                checkpoint_path, checkpoint_hash = write_json(base / "checkpoint.json", checkpoint)
                vivado, _ = write(base / "vivado.bat", b"offline placeholder\n")
                xsdb, _ = write(base / "xsdb.bat", b"offline placeholder\n")
                output_plan = base / "sequence_plan.txt"
                evidence_root = subject.HARDWARE_ROOT / "unit_test_plans" / run_id
                argv = [
                    "--run-id",
                    run_id,
                    "--source-commit",
                    source_commit,
                    "--offline-checkpoint",
                    checkpoint_path,
                    "--offline-checkpoint-sha256",
                    checkpoint_hash,
                ]
                for name in subject.ARTIFACT_ARGUMENTS:
                    path, digest = artifacts[name]
                    argv.extend(
                        [
                            f"--{name.replace('_', '-')}",
                            path,
                            f"--{name.replace('_', '-')}-sha256",
                            digest,
                        ]
                    )
                argv.extend(
                    [
                        "--board-id",
                        "210512180081",
                        "--expected-part",
                        "xc7z010clg400-1",
                        "--expected-target",
                        "localhost:3121/xilinx_tcf/Digilent/210512180081",
                        "--vivado-path",
                        vivado,
                        "--xsdb-path",
                        xsdb,
                        "--bundle-dir",
                        bundle_temp,
                        "--authorization-dir",
                        auth_temp,
                        "--output-plan",
                        str(output_plan),
                        "--evidence-root",
                        str(evidence_root),
                    ]
                )
                args = subject.build_parser().parse_args(argv)

                def fake_bundle(
                    data: bytes,
                    *,
                    transaction_path: Path,
                    manifest_path: Path,
                    lane_policy: str,
                    **_kwargs: object,
                ) -> dict[str, object]:
                    transaction_path.write_text(
                        "P7_JTAG_AXI_TRANSACTIONS_V1\nW32 0x43c00100 0x00000030\nEND\n",
                        encoding="utf-8",
                    )
                    count = 20 if len(data) == 4096 else 1
                    mask = {
                        "LANE0_ONLY": 1,
                        "LANE1_ONLY": 2,
                        "REPLICATE_0X3": 3,
                        "STRIPE_ROUND_ROBIN": 1,
                    }[lane_policy]
                    manifest: dict[str, object] = {
                        "schema": "rf-comm-p7-jtag-backend-manifest-v1",
                        "network_used": False,
                        "hardware_actions_executed_by_module": False,
                        "input_length": len(data),
                        "input_sha256": hashlib.sha256(data).hexdigest(),
                        "lane_policy": lane_policy,
                        "fragment_count": count,
                        "fragments": [{"lane_mask": mask} for _ in range(count)],
                        "transaction_file": transaction_path.name,
                        "transaction_sha256": sha(transaction_path),
                    }
                    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
                    return manifest

                with mock.patch.object(subject, "git_state", return_value=(source_commit, [], None)):
                    with mock.patch.object(sequence, "_current_git_head", return_value=(source_commit, None)):
                        with mock.patch.object(
                            sequence, "_git_tree_listing_sha256", return_value=(tree_sha, None)
                        ):
                            with mock.patch.object(subject, "validate_canonical_artifact_paths"):
                                with mock.patch.object(
                                    subject.jtag_backend, "generate_bundle", side_effect=fake_bundle
                                ):
                                    with mock.patch.object(
                                        subject,
                                        "validate_child_wrapper_dry",
                                        return_value={"errors": [], "kind": "offline-test"},
                                    ) as child_validate:
                                        with mock.patch.object(
                                            subject.subprocess,
                                            "run",
                                            side_effect=AssertionError(
                                                "no subprocess is permitted in this generation path"
                                            ),
                                        ):
                                            result = subject.generate_sequence(args)

                self.assertEqual("PASS", result["P7_AUTHORIZED_SEQUENCE_GENERATOR"])
                self.assertFalse(result["hardware_actions_executed"])
                self.assertFalse(result["safe_wrapper_processes_launched"])
                self.assertEqual(66, child_validate.call_count)
                self.assertEqual(66, result["authorization_count"])
                auth_paths = [item["path"] for item in result["authorization_records"]]
                auth_hashes = [item["sha256"] for item in result["authorization_records"]]
                self.assertEqual(66, len(set(auth_paths)))
                self.assertEqual(66, len(set(auth_hashes)))
                plan = json.loads(output_plan.read_text(encoding="utf-8"))
                self.assertEqual(66, len(plan["stages"]))
                self.assertEqual("ps_stationary", plan["stages"][-1]["group"])
                self.assertEqual(1, sum(stage["group"] == "ps_stationary" for stage in plan["stages"]))
                ps_stages = [
                    stage for stage in plan["stages"] if stage["group"].startswith("ps_")
                ]
                self.assertEqual(5, len(ps_stages))
                for stage in ps_stages:
                    authorization = Path(
                        option(stage["command"], "--authorization-file")
                    ).read_text(encoding="utf-8")
                    self.assertEqual(
                        1,
                        authorization.splitlines().count(
                            "P7_EXECUTION_SCOPE=P7_PS_APPLICATION_STAGE"
                        ),
                    )
                    self.assertEqual(
                        1, authorization.splitlines().count("P7_RUN_ID=NONE")
                    )
                goal_plan_path = str(Path(artifacts["goal_plan"][0]).resolve())
                for stage in plan["stages"]:
                    self.assertEqual(goal_plan_path, option(stage["command"], "--plan-file"))
                    self.assertNotEqual(str(output_plan), option(stage["command"], "--plan-file"))
                    self.assertFalse(Path(option(stage["command"], "--evidence-dir")).exists())
                stationary = plan["stages"][-1]["command"]
                self.assertEqual("1800", option(stationary, "--max-runtime-sec"))
                self.assertEqual("300", option(stationary, "--calibration-sec"))
                self.assertEqual("1500", option(stationary, "--acceptance-sec"))
                one_mib = [
                    stage
                    for stage in plan["stages"]
                    if stage["group"] == "large_object_jtag"
                    and stage["case"]["object_size"] == 1_048_576
                ]
                self.assertEqual(4, len(one_mib))
                for stage in one_mib:
                    command = stage["command"]
                    self.assertEqual("1800", option(command, "--max-runtime-sec"))
                    self.assertEqual("60", option(command, "--preflight-timeout-sec"))
                    self.assertEqual("60", option(command, "--shutdown-timeout-sec"))
                    self.assertEqual("1400", option(command, "--stage-timeout-sec"))
                safe_command = plan["stages"][0]["command"]
                safe_transaction = Path(option(safe_command, "--transaction-file"))
                safe_text = safe_transaction.read_text(encoding="utf-8")
                safe_operations = [
                    line.split()[0]
                    for line in safe_text.splitlines()
                    if line and not line.startswith("META ") and not line.startswith("P7_JTAG_")
                ]
                self.assertFalse(
                    {"START", "COMMIT", "PAYLOAD", "PAYLOAD_WRITE"} & set(safe_operations)
                )
                self.assertEqual(
                    ["W32 0x43c00100 0x00000030"],
                    [line for line in safe_text.splitlines() if line.startswith("W32 ")],
                )
                self.assertEqual(sha(output_plan), result["sequence_plan"]["sha256"])


if __name__ == "__main__":
    unittest.main()
