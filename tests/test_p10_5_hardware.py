import hashlib
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_p10_5_hardware as campaign
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
        for index in range(1, 6):
            case = plans[f"streaming_64m_{index}"][0]
            self.assertIsInstance(case, campaign.P105Case)
            self.assertEqual(case.size, 64 << 20)
            self.assertEqual((case.f2r, case.r2f), (0x3, 0xC))
        formal = plans["formal_30min"][0]
        self.assertEqual(formal.duration_ms, 1_800_000)
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

    def test_result_parser_tail_and_capability_aggregation(self) -> None:
        words = [0] * 512
        words[0:7] = [0x31303150, 1, campaign.EXPECTED_BUILD["fixed"],
                      1, 6, 0, 7]
        words[176:216] = list(range(40))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.bin"
            path.write_bytes(struct.pack("<512I", *words))
            parsed = campaign.parse_p105_result(path, "fixed")
        self.assertEqual(parsed["dual_mode"], 0)
        self.assertEqual(parsed["diagnostic_stall_delta"], 39)
        evidence = campaign.aggregate_capability_evidence([{
            "details": [{
                "fixed": {"piggyback_tx": 2, "piggyback_rx": 3,
                          "control_only_ack": 0, "tx_bytes": 4, "rx_bytes": 5},
                "rotating": {"piggyback_tx": 1, "piggyback_rx": 1,
                             "control_only_ack": 7, "tx_bytes": 8,
                             "rx_bytes": 9},
            }]
        }])
        self.assertTrue(evidence["ack_piggyback_tx_observed"])
        self.assertTrue(evidence["ack_piggyback_rx_observed"])
        self.assertTrue(evidence["control_only_ack_fallback_observed"])
        self.assertTrue(evidence["two_plus_two_tx_executed"])

    def test_runner_has_no_runtime_cap_or_network_path(self) -> None:
        source = (ROOT / "scripts/run_p10_5_hardware.py").read_text(
            encoding="utf-8")
        self.assertIn('measured = float(result["active_runtime_seconds"])', source)
        self.assertNotIn('measured = min(', source)
        self.assertIn('"network_used": False', source)
        self.assertIn('"spi_used": False', source)
        self.assertNotIn("socket.", source)

    def test_tcl_has_read_only_capability_and_exact_plan_parser(self) -> None:
        source = campaign.STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("proc p105_capability", source)
        self.assertIn('elseif {$kind eq "P105_CAPABILITY"}', source)
        self.assertIn("P10 CASE requires exactly 29 fields", source)
        self.assertIn("if {[llength $argv] ni {16 18 20}}", source)

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
