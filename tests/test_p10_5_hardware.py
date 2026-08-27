import hashlib
import subprocess
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_p10_5_hardware as campaign
import freeze_p10_5_artifacts as freezer
from p10_tfdu_runtime_guard import RuntimeRestGuard, load_policy


class FakeTime:
    def __init__(self) -> None:
        self.value = 100.0
        self.utc = datetime(2026, 8, 9, tzinfo=timezone.utc)

    def clock(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds
        self.utc += timedelta(seconds=seconds)

    def utc_clock(self) -> datetime:
        return self.utc


class P10_5HardwareTests(unittest.TestCase):
    def test_goal_and_fixed_hardware_identity(self) -> None:
        self.assertEqual(campaign.sha256(campaign.GOAL), campaign.GOAL_SHA256)
        self.assertEqual(campaign.EXPECTED_FIXED_SERIAL, "210249855178")
        self.assertEqual(campaign.EXPECTED_ROTATING_SERIAL, "210512180081")
        self.assertEqual(campaign.PRIMARY_F2R, 0x3)
        self.assertEqual(campaign.PRIMARY_R2F, 0xC)
        self.assertEqual(len(set(campaign.MODULE_BINDING.values())), 8)
        self.assertEqual(campaign.MODULE_BINDING["F2"], "B0019")
        self.assertEqual(campaign.MODULE_BINDING["R3"], "B0011")

    def test_complete_disjoint_mask_matrices(self) -> None:
        plans = campaign.build_plans()
        one = [x for x in plans["one_plus_one"]
               if isinstance(x, campaign.P105Case)]
        mixed = [x for x in plans["two_plus_one"]
                 if isinstance(x, campaign.P105Case)]
        two = [x for x in plans["two_plus_two"]
               if isinstance(x, campaign.P105Case)]
        self.assertEqual(len(one), 12)
        self.assertEqual(len(mixed), 24)
        self.assertEqual(len(two), 6)
        for case in one + mixed + two:
            case.validate()
            self.assertEqual(case.f2r & case.r2f, 0)
            self.assertEqual(case.f2r | case.r2f, case.active)
            self.assertEqual(len(case.plan_line().split()), 29)
        self.assertEqual(campaign.validate_plans(), [])

    def test_required_streaming_and_formal_plan(self) -> None:
        plans = campaign.build_plans()
        capability = [x for x in plans["capability"]
                      if isinstance(x, campaign.P105Case)]
        self.assertEqual(len(capability), 1)
        self.assertEqual(capability[0].duration_ms, 0)
        self.assertEqual(capability[0].size,
                         4 * campaign.INTERNAL_OBJECT_BYTES)
        self.assertEqual(campaign.stage_runtime_limit("capability"), 10)
        for index in range(1, 6):
            case = plans[f"streaming_64m_{index}"][0]
            self.assertIsInstance(case, campaign.P105Case)
            self.assertEqual(case.size, 64 << 20)
            self.assertEqual((case.f2r, case.r2f), (0x3, 0xC))
        formal = plans["formal_30min"][0]
        self.assertEqual(formal.duration_ms, 1_800_000)
        self.assertEqual(campaign.stage_runtime_limit("faults"), 900)
        self.assertEqual(campaign.stage_runtime_limit("formal_30min"), 1800)
        self.assertLessEqual(max(campaign.stage_runtime_limit(x)
                                 for x in campaign.STAGES), 1800)

    def test_plan_hashes_cover_exact_stage_order(self) -> None:
        hashes = campaign.plan_hashes()
        self.assertEqual(tuple(hashes), campaign.STAGES)
        for stage, value in hashes.items():
            self.assertEqual(
                value,
                hashlib.sha256(campaign.plan_text(
                    campaign.build_plans()[stage]).encode("ascii")).hexdigest(),
            )

    def test_post_artifact_harness_allowlist_is_fail_closed(self) -> None:
        for path in (
                "config/project_state.json",
                "docs/hardware/P10_3_AS_WIRED_RECORD.md",
                "reports/lane3_connectivity_probe_20260810T114211Z.md",
                "scripts/create_p10_5_authorization.py",
                "scripts/run_p10_5_hardware.py",
                "tests/test_p10_5_hardware.py",
                "evidence/hardware/p10_5/run/final.json",
                "artifacts/p10_5/source/hash/candidate.bit"):
            self.assertTrue(freezer.post_artifact_path_allowed(path), path)
        for path in (
                "rtl/ir_data_plane_top.sv",
                "software/ps_driver/p9_runtime_main.c",
                "constraints/active/p10_ax7020_fixed.xdc",
                "config/p10_5_dual_direction.yaml",
                "scripts/build_p10_5_functional.py"):
            self.assertFalse(freezer.post_artifact_path_allowed(path), path)

    def test_post_artifact_module_identity_only_change_is_admissible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wiring = root / "config/hardware/p10_3_actual_wiring.yaml"
            inventory = root / "config/hardware/tfdu_module_inventory.yaml"
            wiring.parent.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"],
                           cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "P10.5 test"],
                           cwd=root, check=True)
            wiring.write_text(
                "schema_version: 1\n"
                "status: OLD\n"
                "module_positions:\n"
                "  R3: {endpoint: rotating, connector: J11, position: B, lane: 3, small_board_id: B0025}\n"
                "signal_positions:\n"
                "  B: {Mode: 22, SD: 24, Rxd: 26, Txd: 28}\n",
                encoding="utf-8")
            inventory.write_text(
                "schema_version: 2\n"
                "status: OLD\n"
                "p10_3_current_installation:\n"
                "  active_modules: [R3]\n"
                "  lane_pairs: {lane3: F3-R3}\n"
                "  old_f1_active: false\n"
                "  old_f1_status: QUARANTINED_NOT_ACCEPTED\n"
                "  modules:\n"
                "    R3: {small_board_id: B0025, endpoint: 'AX7020-R/JTAG:210512180081', position: J11-B, inventory_status: OLD}\n",
                encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "before"],
                           cwd=root, check=True)
            before = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            wiring.write_text(wiring.read_text(encoding="utf-8")
                              .replace("status: OLD", "status: PENDING")
                              .replace("B0025", "B0011"), encoding="utf-8")
            inventory.write_text(inventory.read_text(encoding="utf-8")
                                 .replace("status: OLD", "status: PENDING")
                                 .replace("B0025", "B0011")
                                 .replace("inventory_status: OLD",
                                          "inventory_status: PENDING"),
                                 encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "after"],
                           cwd=root, check=True)
            after = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            original_root = freezer.ROOT
            freezer.ROOT = root
            try:
                changed, disallowed = freezer.post_artifact_changes(before, after)
            finally:
                freezer.ROOT = original_root
        self.assertEqual(changed, [
            "config/hardware/p10_3_actual_wiring.yaml",
            "config/hardware/tfdu_module_inventory.yaml",
        ])
        self.assertEqual(disallowed, [])

    def test_post_artifact_module_record_rejects_wiring_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wiring = root / "config/hardware/p10_3_actual_wiring.yaml"
            wiring.parent.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"],
                           cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "P10.5 test"],
                           cwd=root, check=True)
            wiring.write_text(
                "schema_version: 1\n"
                "module_positions:\n"
                "  R3: {endpoint: rotating, connector: J11, position: B, lane: 3, small_board_id: B0025}\n"
                "signal_positions:\n"
                "  B: {Mode: 22, SD: 24, Rxd: 26, Txd: 28}\n",
                encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "before"],
                           cwd=root, check=True)
            before = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            wiring.write_text(wiring.read_text(encoding="utf-8")
                              .replace("Mode: 22", "Mode: 23"), encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "after"],
                           cwd=root, check=True)
            after = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            original_root = freezer.ROOT
            freezer.ROOT = root
            try:
                _, disallowed = freezer.post_artifact_changes(before, after)
            finally:
                freezer.ROOT = original_root
        self.assertEqual(disallowed,
                         ["config/hardware/p10_3_actual_wiring.yaml"])

    def test_result_parser_tail_and_capability_aggregation(self) -> None:
        words = [0] * 512
        words[0:7] = [0x31303150, 1, campaign.EXPECTED_BUILD["fixed"],
                      1, 6, 0, 7]
        words[176:216] = list(range(40))
        words[216:220] = [1, 1, 0x89ABCDEF, 0x01234567]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.bin"
            path.write_bytes(struct.pack("<512I", *words))
            parsed = campaign.parse_p105_result(path, "fixed")
        self.assertEqual(parsed["dual_mode"], 0)
        self.assertEqual(parsed["diagnostic_stall_delta"], 39)
        self.assertEqual(parsed["launch_barrier_waited"], 1)
        self.assertEqual(parsed["launch_release_seen"], 1)
        self.assertEqual(parsed["launch_wait_ticks"], 0x0123456789ABCDEF)
        pair = {
            "fixed": {"piggyback_tx": 2, "piggyback_rx": 3,
                      "control_only_ack": 0, "tx_bytes": 4, "rx_bytes": 5},
            "rotating": {"piggyback_tx": 1, "piggyback_rx": 1,
                         "control_only_ack": 7, "tx_bytes": 8,
                         "rx_bytes": 9},
        }
        evidence = campaign.aggregate_capability_evidence([
            {"stage": "capability", "details": [pair]},
            {"stage": "two_plus_two", "details": [pair] * 6},
        ])
        self.assertTrue(evidence["ack_piggyback_tx_observed"])
        self.assertTrue(evidence["ack_piggyback_rx_observed"])
        self.assertTrue(evidence["control_only_ack_fallback_observed"])
        self.assertTrue(evidence["two_plus_two_tx_executed"])
        pre_two_plus_two = campaign.aggregate_capability_evidence([
            {"stage": "capability", "details": [pair]}])
        self.assertFalse(pre_two_plus_two["two_plus_two_tx_executed"])

    def test_transport_timeout_policy_is_formal_only(self) -> None:
        for stage in campaign.STAGES:
            self.assertEqual(
                campaign.transport_timeout_is_hard_failure(stage),
                stage == "formal_30min",
            )
        nonformal = [{
            "stage": "one_plus_one",
            "details": [{
                "fixed": {"tx_timeouts": 1},
                "rotating": {"tx_timeouts": 0},
            }],
        }]
        self.assertFalse(campaign.formal_transport_timeout_zero(nonformal))
        formal = nonformal + [{
            "stage": "formal_30min",
            "details": [{
                "fixed": {"tx_timeouts": 0},
                "rotating": {"tx_timeouts": 0},
            }],
        }]
        self.assertTrue(campaign.formal_transport_timeout_zero(formal))
        formal[-1]["details"][0]["rotating"]["tx_timeouts"] = 1
        self.assertFalse(campaign.formal_transport_timeout_zero(formal))

    def test_dma_backpressure_evidence_is_direction_scoped(self) -> None:
        faults = [x for x in campaign.build_plans()["faults"]
                  if isinstance(x, campaign.P105Case)]
        f2r = next(x for x in faults
                   if x.label == "fault_backpressure_f2r")
        r2f = next(x for x in faults
                   if x.label == "fault_backpressure_r2f")

        def evidence(role: str, stall: int = 0, before: int = 0,
                     after: int = 0) -> dict[str, int | str]:
            return {
                "role": role,
                "diagnostic_before": before,
                "diagnostic_after": after,
                "diagnostic_stall_delta": stall,
            }

        # Direct run evidence: F_TO_R injection executes on fixed, while the
        # rotating peer remains unarmed and reports no injected stall delta.
        self.assertEqual(campaign.dma_backpressure_evidence_errors(
            f2r.label, f2r,
            evidence("fixed", 3_196_992, 2, 0x00020002)), [])
        self.assertEqual(campaign.dma_backpressure_evidence_errors(
            f2r.label, f2r, evidence("rotating")), [])

        # R_TO_F is symmetric: rotating executes the injection and fixed is
        # the unaffected peer.
        self.assertEqual(campaign.dma_backpressure_evidence_errors(
            r2f.label, r2f,
            evidence("rotating", 3_196_994, 2, 0x00020002)), [])
        self.assertEqual(campaign.dma_backpressure_evidence_errors(
            r2f.label, r2f, evidence("fixed")), [])

        missing = campaign.dma_backpressure_evidence_errors(
            f2r.label, f2r, evidence("fixed"))
        self.assertEqual(missing,
                         ["fault_backpressure_f2r:fixed: "
                          "DMA backpressure evidence"])
        leaked = campaign.dma_backpressure_evidence_errors(
            f2r.label, f2r, evidence("rotating", 1))
        self.assertEqual(leaked,
                         ["fault_backpressure_f2r:rotating: "
                          "unexpected DMA backpressure evidence"])
        stale_arm = campaign.dma_backpressure_evidence_errors(
            r2f.label, r2f, evidence("rotating", 1, before=1))
        self.assertEqual(stale_arm,
                         ["fault_backpressure_r2f:rotating: "
                          "DMA backpressure evidence"])

    def test_runner_has_no_runtime_cap_or_network_path(self) -> None:
        source = (ROOT / "scripts/run_p10_5_hardware.py").read_text(
            encoding="utf-8")
        self.assertIn('measured = float(result["active_runtime_seconds"])', source)
        self.assertIn(
            "active_runtime = max(active_runtime, observation_runtime)", source
        )
        self.assertNotIn('measured = min(', source)
        self.assertIn('"network_used": False', source)
        self.assertIn('"spi_used": False', source)
        self.assertNotIn("socket.", source)

    def test_failed_case_observation_runtime_drives_rest_accounting(self) -> None:
        rows = [
            {
                "label": "clean_before_failure",
                "command": 15,
                "started_ms": 1_000,
                "finished_ms": 13_000,
            },
            {
                "label": "fault_abort_r2f",
                "command": 15,
                "started_ms": 20_000,
                "finished_ms": 620_403,
            },
            {
                "label": "shutdown",
                "command": 10,
                "started_ms": 621_000,
                "finished_ms": 622_000,
            },
        ]
        self.assertAlmostEqual(
            campaign.observation_active_runtime_seconds(rows),
            612.403,
            places=3,
        )

    def test_tcl_has_read_only_capability_and_exact_plan_parser(self) -> None:
        source = campaign.STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("proc p105_capability", source)
        self.assertIn('elseif {$kind eq "P105_CAPABILITY"}', source)
        self.assertIn("P10 CASE requires exactly 29 fields", source)
        self.assertIn("if {[llength $argv] ni {16 18 20}}", source)
        self.assertIn("($role_status & 0x07) != 0x07", source)
        self.assertNotIn("($role_status & 0x13) != 0x13", source)
        stage_fixed = source.index("p10_stage_case fixed $d $sequence")
        stage_rotating = source.index("p10_stage_case rotating $d $sequence",
                                      stage_fixed)
        submit_rotating = source.index(
            "p10_submit_staged_case rotating $sequence", stage_rotating)
        submit_fixed = source.index(
            "p10_submit_staged_case fixed $sequence", submit_rotating)
        wait_pair = source.index(
            "p10_wait_p10_5_pair_primed $d $sequence", submit_fixed)
        release_pair = source.index(
            "p10_release_p10_5_pair $d $sequence", wait_pair)
        self.assertLess(stage_fixed, stage_rotating)
        self.assertLess(stage_rotating, submit_rotating)
        self.assertLess(submit_rotating, submit_fixed)
        self.assertLess(submit_fixed, wait_pair)
        self.assertLess(wait_pair, release_pair)
        self.assertIn("P10_5_PAIR_PRIMED", source)
        self.assertIn("P10_5_PAIRED_RELEASE_SKEW_US", source)
        self.assertIn("($pl_status & 0x207) == 0x205", source)
        self.assertIn("($role_status & 0x1F) == 0x1B", source)
        self.assertNotIn("($role_status & 0x0F) == 0x07", source)
        self.assertIn("($context_status & 0x8F) == 0x09", source)
        self.assertIn("set tx_held_total [p10_read32 $role 0x00020780]", source)
        self.assertIn("$submitted_low == $tx_held_total", source)
        self.assertIn("$tx_held == $expected_first_held", source)
        self.assertNotIn("P10_5_PAIRED_LAUNCH_SKEW_US", source)

    def test_all_hardware_tcl_guards_admit_p10_5_marker(self) -> None:
        paths = (
            campaign.STAGE_TCL,
            campaign.FORENSIC_TCL,
            ROOT / "scripts/hw/p10_program_dual_shutdown.tcl",
        )
        for path in paths:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("P10_5_IMMUTABLE_AUTHORIZED", source)
        forensic = campaign.FORENSIC_TCL.read_text(encoding="utf-8")
        self.assertIn(r"^p10_(3f|4|5)_", forensic)

    def test_measured_runtime_drives_cooldown_without_hiding_overrun(self) -> None:
        policy = load_policy(campaign.RUNTIME_REST_POLICY)
        fake = FakeTime()
        with tempfile.TemporaryDirectory() as temporary:
            guard = RuntimeRestGuard(
                policy, Path(temporary) / "ledger.json", campaign.ALL_MODULES,
                clock=fake.clock, sleeper=fake.sleep, utc_clock=fake.utc_clock)
            guard.begin_stage("bounded", 1800)
            fake.sleep(1800.5)
            with self.assertRaisesRegex(RuntimeError, "exceeded"):
                guard.finish_stage(shutdown_verified=True,
                                   measured_runtime_seconds=1800.001)
            ledger = guard.public_ledger()
        self.assertEqual(ledger["status"], "FAIL")
        self.assertEqual(ledger["stages"][0]["runtime_limit_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
