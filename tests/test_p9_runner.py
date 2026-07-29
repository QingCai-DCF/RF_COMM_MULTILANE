from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "p9_runner", ROOT / "scripts/run_p9_z7010_stationary_2lane.py"
)
assert SPEC and SPEC.loader
P9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P9)

HW_SPEC = importlib.util.spec_from_file_location(
    "p9_hardware_runtime", ROOT / "scripts/p9_hardware_runtime.py"
)
assert HW_SPEC and HW_SPEC.loader
P9_HW = importlib.util.module_from_spec(HW_SPEC)
sys.modules[HW_SPEC.name] = P9_HW
HW_SPEC.loader.exec_module(P9_HW)


class P9AuthorizationTests(unittest.TestCase):
    def write_record(self, updates: dict | None = None) -> Path:
        source = json.loads((ROOT / "config/p9_current_run_authorization.json").read_text())
        source.update(updates or {})
        temporary = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(source, temporary)
        temporary.close()
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return Path(temporary.name)

    def validate(self, path: Path, **updates):
        values = {"stage": "P9-04", "max_runtime": 1800, "lane_mask": 1,
                  "require_bound_artifacts": True}
        values.update(updates)
        return P9.validate_authorization(path, **values)

    def test_no_authorization_fails(self):
        result = self.validate(Path("missing-authorization.json"))
        self.assertEqual(result["status"], "FAIL")

    def test_unbound_hardware_authorization_fails(self):
        result = self.validate(ROOT / "config/p9_current_run_authorization.json")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("phase-2" in error for error in result["errors"]))

    def test_lane_mask_0x4_fails(self):
        path = self.write_record({"artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path, lane_mask=4)["status"], "FAIL")

    def test_runtime_above_1800_fails(self):
        path = self.write_record({"artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path, max_runtime=1801)["status"], "FAIL")

    def test_wrong_scope_fails(self):
        path = self.write_record({"scope": "WRONG_SCOPE", "artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path)["status"], "FAIL")


class P9HardwareDutyEvaluatorTests(unittest.TestCase):
    @staticmethod
    def safe_idle_observation() -> tuple[dict, list[int]]:
        row = {
            "label": "duty_boundary", "command": 1, "expected_status": 0,
            "sequence": 1001, "lane": 0, "direction": 0, "rate": 0,
            "size": 0, "window": "NA",
        }
        words = [0] * 256
        words[0] = 0x424D3950
        words[1] = P9_HW.P9_MAILBOX_SCHEMA
        words[2] = P9_HW.P9_FIRMWARE_BUILD_ID
        words[3] = 4
        words[6] = row["sequence"]
        words[7] = row["sequence"]
        words[8] = 0
        words[32] = 0x50395A10
        words[33] = P9_HW.P9_PL_BUILD_ID
        words[34] = 0x00701022
        words[35] = P9_HW.EXPECTED_REGISTER_MAP_VERSION
        words[36] = P9_HW.EXPECTED_REGISTER_MAP_HASH_LOW
        words[37] = 0xF7204221
        words[39] = 0x40400000
        words[40] = 1
        words[49] = 64
        words[50] = 32

        def set_pl(index: int, value: int) -> None:
            words[P9_HW.PL_SNAPSHOT_START + index] = value

        set_pl(0, 0x50395A10)
        set_pl(7, 0x2)
        set_pl(85, 64_000)
        set_pl(86, 12_799)
        set_pl(87, 11_520)
        return row, words

    def test_canonical_strict_duty_telemetry_passes(self):
        row, words = self.safe_idle_observation()
        errors, detail = P9_HW.evaluate_observation(row, words)
        self.assertEqual([], errors)
        self.assertEqual(64_000, detail["duty_window_cycles"])
        self.assertEqual(12_799, detail["duty_hard_max_high_cycles"])
        self.assertEqual(11_520, detail["duty_target_max_high_cycles"])

    def test_12799_is_below_strict_20_percent_but_12800_is_not(self):
        row, words = self.safe_idle_observation()
        words[P9_HW.PL_SNAPSHOT_START + 65] = 12_799
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertFalse(any("strict 20%" in error for error in errors))
        words[P9_HW.PL_SNAPSHOT_START + 65] = 12_800
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("strict 20%" in error for error in errors))

    def test_noncanonical_hard_limit_telemetry_fails(self):
        row, words = self.safe_idle_observation()
        words[P9_HW.PL_SNAPSHOT_START + 86] = 12_800
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("64000/12799/11520" in error for error in errors))

    def test_p9_counter_clear_cannot_invalidate_physical_duty_history(self):
        lane_phy = (ROOT / "rtl/tfdu_lane_phy.sv").read_text(encoding="utf-8")
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(encoding="utf-8")
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertIn("parameter integer CLEAR_STICKY_INVALIDATES_HISTORY = 1", lane_phy)
        self.assertIn(".safety_fault_clear_i(safety_fault_clear)", lane_phy)
        self.assertIn(".telemetry_clear_i(clear_sticky)", lane_phy)
        self.assertEqual(2, core.count(".CLEAR_STICKY_INVALIDATES_HISTORY(0)"))
        self.assertIn("P9 telemetry clear invalidated safety/startup state", testbench)

    def raw_observation(self, *, direction: int) -> tuple[dict, list[int]]:
        row, words = self.safe_idle_observation()
        row.update({
            "label": f"raw_direction_{direction}", "command": 2,
            "lane": 1, "direction": direction, "rawtarget": 64,
        })

        def set_pl(index: int, value: int) -> None:
            words[P9_HW.PL_SNAPSHOT_START + index] = value

        set_pl(16, 1 | (direction << 8))
        set_pl(19, 64)
        # Current stationary Z7010 policy: both same-lane receivers see the
        # exact train, while the other lane sees no pulses.
        set_pl(53, 64)
        set_pl(55, 64)
        set_pl(57 + (2 if direction else 0), 64)
        return row, words

    def test_raw_selected_lane_exact_at_both_endpoint_receivers(self):
        for direction in (0, 1):
            with self.subTest(direction=direction):
                row, words = self.raw_observation(direction=direction)
                errors, detail = P9_HW.evaluate_observation(row, words)
                self.assertEqual([], errors)
                self.assertEqual(
                    "BOTH_ENDPOINTS_EXACT_SELECTED_LANE",
                    detail["raw_rx_observation_policy"],
                )
                self.assertEqual([64, 0, 64, 0], detail["expected_raw_rx"])

    def test_raw_off_lane_pulse_still_fails_closed(self):
        row, words = self.raw_observation(direction=0)
        words[P9_HW.PL_SNAPSHOT_START + 54] = 1
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("physical RX raw vector mismatch" in error for error in errors))

    def test_p9_rearm_plan_covers_both_directions_and_profile_policy_is_bound(self):
        plans = P9_HW.build_plans()
        rearm = [case for case in plans["P9-07"] if getattr(case, "label", "").startswith("p9_07_rearm_")]
        self.assertEqual([0, 1], [case.direction for case in rearm])
        config = (ROOT / "config/p9_z7010_stationary_2lane.yaml").read_text(
            encoding="utf-8"
        )
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertIn("policy: BOTH_ENDPOINTS_EXACT_SELECTED_LANE", config)
        self.assertIn("wire [1:0] combined_txd = a_txd | b_txd;", testbench)
        self.assertEqual(2, testbench.count("= ~(combined_txd & {"))
        self.assertIn("a_rx_recovery_cycles[1] == 0", testbench)
        self.assertIn("b_rx_recovery_cycles[1] == 0", testbench)

    def test_command3_observation_schema_preserves_flags_and_failure_dump(self):
        tcl = (ROOT / "scripts/hw/p9_xsdb_stage.tcl").read_text(
            encoding="utf-8"
        )
        self.assertIn("expected_status|flags|lane|direction", tcl)
        self.assertIn("[dict get $d flags] [dict get $d lane]", tcl)
        terminal = tcl.index("set observed_status [p9_read32 0x00020020]")
        dump = tcl.index("set dump_path [p9_dump_mailbox [dict get $d label]]", terminal)
        mismatch = tcl.index("P9 command status mismatch", terminal)
        self.assertLess(dump, mismatch)

    def test_xsdb_mailbox_polling_uses_running_context_safe_reads(self):
        tcl = (ROOT / "scripts/hw/p9_xsdb_stage.tcl").read_text(
            encoding="utf-8"
        )
        read32 = tcl[tcl.index("proc p9_read32 {address}"):
                     tcl.index("proc p9_read32_force {address}")]
        self.assertIn(
            "mrd -address-space AP0 -force -value $address", read32
        )
        self.assertIn("p9_select_memory_target", read32)
        self.assertNotIn("mrd -value $address", read32)

        live_reads = [
            line.strip() for line in tcl.splitlines()
            if "mrd " in line and not line.lstrip().startswith("#")
        ]
        live_writes = [
            line.strip() for line in tcl.splitlines()
            if "mwr " in line and not line.lstrip().startswith("#")
        ]
        self.assertTrue(live_reads)
        self.assertTrue(live_writes)
        for command in live_reads:
            self.assertIn("-address-space AP0", command)
        for command in live_writes:
            self.assertIn("-address-space AP0", command)
            self.assertIn("-bypass-cache-sync", command)
        self.assertIn("proc p9_select_cpu_target", tcl)
        self.assertIn("proc p9_select_memory_target", tcl)
        self.assertIn("P9_XSDB_APU_TARGET_COUNT", tcl)
        self.assertIn("P9_XSDB_DEBUG_RECOVERY_SYSTEM_RESET=1", tcl)
        self.assertIn("configparams force-mem-accesses 1", tcl)
        self.assertIn("configparams force-mem-accesses 0", tcl)
        self.assertIn("P9_XSDB_FORCE_MEM_ACCESSES_WINDOW=PS7_INIT_ONLY", tcl)
        self.assertIn("P9_READY_TIMEOUT_SNAPSHOT", tcl)
        self.assertIn("P9_XSDB_PL_PREFLIGHT", tcl)
        self.assertIn("P9_XSDB_STREAM_RESET_PREFLIGHT", tcl)
        self.assertIn("p9_write32 0x43C00718 0x0000001A", tcl)
        self.assertIn("p9_write32 0x43C00718 0x00000200", tcl)

    def test_stationary_ack_turnaround_guard_is_4096_cycles(self):
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        config = (ROOT / "config/p9_z7010_stationary_2lane.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("ACK_TURNAROUND_GUARD_CYCLES = 4_096", core)
        self.assertEqual(
            2, core.count("phase_guard_q <= ACK_TURNAROUND_GUARD_CYCLES;")
        )
        self.assertIn("PH_DATA_GUARD", core)
        self.assertIn("both DATA-to-ACK and ACK-to-DATA directions", core)
        self.assertIn("ack_turnaround_guard_cycles: 4096", config)
        self.assertIn("ack_turnaround_guard_us_at_64mhz: 64", config)

    def test_p9_receiver_acquires_phase_from_delayed_preamble(self):
        codec = (ROOT / "rtl/ir_4ppm_codec.sv").read_text(encoding="utf-8")
        wrapper = (ROOT / "rtl/p9_rate_4ppm_rx.sv").read_text(encoding="utf-8")
        testbench = (ROOT / "sim/tb/tb_p9_4ppm_frame_link.sv").read_text(
            encoding="utf-8"
        )
        regression = (ROOT / "scripts/run_p9_candidate_regression.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("RX_ACQUIRE_ON_FIRST_PULSE = 1'b0", codec)
        self.assertIn("rx_phase_acquired", codec)
        self.assertEqual(3, wrapper.count(".RX_ACQUIRE_ON_FIRST_PULSE(1'b1)"))
        self.assertIn("RX_PATH_DELAY_CYCLES = 12", testbench)
        self.assertIn("TB_P9_4PPM_FRAME_LINK_DELAYED=PASS", testbench)
        self.assertIn('"p9_frame_link_delayed"', regression)

    def test_p9_4mbps_uses_tfdu_fir_pulse_and_bounded_duty_admission(self):
        tx = (ROOT / "rtl/p9_4ppm_frame_tx.sv").read_text(encoding="utf-8")
        wrapper = (ROOT / "rtl/p9_rate_4ppm_rx.sv").read_text(encoding="utf-8")
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        config = (ROOT / "config/p9_z7010_stationary_2lane.yaml").read_text(
            encoding="utf-8"
        )
        fir_bench = (ROOT / "sim/tb/tb_p9_tfdu_fir_frame_link.sv").read_text(
            encoding="utf-8"
        )
        regression = (ROOT / "scripts/run_p9_candidate_regression.py").read_text(
            encoding="utf-8"
        )
        peripheral = (ROOT / "rtl/p9_axi_dma_peripheral.sv").read_text(
            encoding="utf-8"
        )
        firmware = (ROOT / "software/ps_driver/p9_runtime_main.c").read_text(
            encoding="utf-8"
        )
        protocol = (ROOT / "software/ps_driver/p9_runtime_protocol.h").read_text(
            encoding="utf-8"
        )
        self.assertIn("active_pulse_cycles <= 8'd8", tx)
        self.assertIn(".TX_PULSE_CYCLES(8)", wrapper)
        self.assertIn(".DETECT_START_CYCLES(3), .DETECT_END_CYCLES(4)", wrapper)
        self.assertIn("FRAME_DUTY_GUARD_CYCLES = 20_480", core)
        self.assertIn("frame_duty_guard_q[0] == 0", core)
        self.assertIn("frame_duty_guard_q[1] == 0", core)
        self.assertIn(
            "frame_duty_guard_q[copy_lane] <= FRAME_DUTY_GUARD_CYCLES", core
        )
        self.assertIn("frame_admission_duty_guard_cycles: 20480", config)
        self.assertIn("frame_admission_duty_guard_us_at_64mhz: 320", config)
        self.assertIn("raw_bps: 4000000, chip_cycles: 8, tx_pulse_cycles: 8", config)
        self.assertIn("model_rxd_sync", fir_bench)
        self.assertIn("TB_P9_TFDU_FIR_FRAME_LINK=PASS", fir_bench)
        self.assertIn('"p9_tfdu_fir_frame_link"', regression)
        self.assertIn("P9_BUILD_ID = 32'h5009_0009", peripheral)
        self.assertIn("m->pl_build_id != UINT32_C(0x50090009)", firmware)
        self.assertIn("P9_RUNTIME_BUILD_ID UINT32_C(0x5009000a)", protocol)
        self.assertIn("P9_MAILBOX_SCHEMA_VERSION UINT32_C(5)", protocol)
        self.assertIn("terminal_window_command_sequence", protocol)
        self.assertIn("p9_capture_terminal_window(m);", firmware)
        self.assertIn("if (object_fail && !object_fail_d_q)", peripheral)
        self.assertIn("clear_counters_i && !object_active_q", core)
        self.assertEqual(0x50090009, P9_HW.P9_PL_BUILD_ID)
        self.assertEqual(0x5009000A, P9_HW.P9_FIRMWARE_BUILD_ID)

    def test_scheduler_plan_forces_real_retry_migration_and_explicit_all_down_fault(self):
        plan = {case.label: case for case in P9_HW.build_plans()["P9-20"]}
        migration = plan["retry_migration"]
        self.assertEqual(
            (1, 1, 10),
            (migration.dropdata, migration.injectmask, migration.injectdelay),
        )
        all_down = plan["all_lanes_unavailable"]
        self.assertEqual(12, all_down.expected_status)
        self.assertEqual(0, all_down.flags & 1)

    def test_pl_soft_reset_flushes_all_stream_domains_and_rebuilds_dma(self):
        peripheral = (ROOT / "rtl/p9_axi_dma_peripheral.sv").read_text(
            encoding="utf-8"
        )
        wrapper = (ROOT / "rtl/p9_axi_dma_peripheral_bd.v").read_text(
            encoding="utf-8"
        )
        build = (ROOT / "scripts/build_p9_z7010_candidate.tcl").read_text(
            encoding="utf-8"
        )
        firmware = (ROOT / "software/ps_driver/p9_runtime_main.c").read_text(
            encoding="utf-8"
        )
        freeze = (ROOT / "scripts/freeze_p9_artifacts.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("stream_reset_hold_q <= 6'd32", peripheral)
        self.assertIn("stream_reset_request_o <= 1", peripheral)
        self.assertIn("!stream_reset_request_o", peripheral)
        self.assertIn(".stream_reset_request_o(stream_reset_request_o)", wrapper)
        for domain in ("rst_stream_protocol_64", "rst_stream_dma_100",
                       "rst_stream_dma_50"):
            self.assertIn(domain, build)
        self.assertIn("p9_peripheral_0/stream_reset_request_o", build)
        self.assertIn(
            "foreach stream_reset [list $stream_rst64 $stream_rst100 $stream_rst50]",
            build,
        )
        self.assertIn(
            "set_property CONFIG.C_AUX_RESET_HIGH {1} $stream_reset", build
        )
        self.assertIn("P9_STREAM_AUX_RESET_ACTIVE_HIGH=1", build)
        self.assertIn("return p9_dma_initialize(depth, count_dma_reset);",
                      firmware)
        self.assertIn("p9_reset_stream_path(8U, 0U, 0U)", firmware)
        self.assertIn("P9_STREAM_RESET_DOMAINS", freeze)
        self.assertIn("P9_STREAM_AUX_RESET_ACTIVE_HIGH", freeze)

    def test_terminal_window_capture_precedes_shutdown_and_is_command_bound(self):
        firmware = (ROOT / "software/ps_driver/p9_runtime_main.c").read_text(
            encoding="utf-8"
        )
        capture = firmware.index("p9_capture_terminal_window(m);")
        object_exit = firmware.index("object_exit:", capture)
        shutdown = firmware.index("int shutdown_status = p9_shutdown();", object_exit)
        self.assertLess(capture, object_exit)
        self.assertLess(object_exit, shutdown)
        self.assertIn(
            "terminal_window_command_sequence = mailbox->command_sequence", firmware
        )
        self.assertLess(
            firmware.index("terminal_window_status = p9_pl_read", 0),
            firmware.index("terminal_window_valid = P9_TERMINAL_WINDOW_VALID", 0),
        )

    def test_object_evaluator_uses_bound_pre_shutdown_window_snapshot(self):
        row, words = self.safe_idle_observation()
        size = 247 * 96
        final_sequence = (0xFFFE + 96) & 0xFFFF
        row.update({
            "label": "sr_wrap_d0", "command": 3, "flags": 0,
            "lane": 3, "direction": 0, "rate": 2, "weights": 0x0101,
            "size": size, "dropdata": 0, "dropack": 0,
            "faultflags": 0, "unavailable": 0, "injectmask": 0,
        })

        def set_pl(index: int, value: int) -> None:
            words[P9_HW.PL_SNAPSHOT_START + index] = value

        words[60] = size
        words[79] = 0xFFFFFFFF
        set_pl(10, 3 | (2 << 8))
        set_pl(11, 0x0101)
        set_pl(20, size)
        set_pl(21, size)
        set_pl(22, 0)  # Mandatory shutdown has cleared the live TX window.
        set_pl(23, (32 << 22) | final_sequence)
        set_pl(39, 96)
        set_pl(94, 96)
        words[P9_HW.TERMINAL_WINDOW_START] = P9_HW.P9_TERMINAL_WINDOW_VALID
        words[P9_HW.TERMINAL_WINDOW_START + 1] = row["sequence"]
        words[P9_HW.TERMINAL_WINDOW_START + 2] = (
            final_sequence | (final_sequence << 16)
        )
        words[P9_HW.TERMINAL_WINDOW_START + 3] = (
            (32 << 22) | final_sequence
        )

        errors, detail = P9_HW.evaluate_observation(row, words)
        self.assertEqual([], errors)
        self.assertTrue(detail["terminal_window_valid"])
        self.assertEqual(final_sequence, detail["tx_next_sequence"])
        self.assertEqual(final_sequence, detail["tx_ack_base"])
        self.assertEqual(0, detail["outstanding_count"])
        self.assertEqual(0, detail["post_shutdown_tx_sequence_base"])

        words[P9_HW.TERMINAL_WINDOW_START + 1] += 1
        errors, detail = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("terminal window snapshot" in error for error in errors))
        self.assertFalse(detail["terminal_window_valid"])

    def test_ingress_rechecks_window_admission_at_an_axi_beat_fragment_boundary(self):
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertIn("wire ingress_byte_can_advance", core)
        self.assertIn(
            "beat_valid_q && !allocate_pending_q && ingress_byte_can_advance", core
        )
        self.assertIn("run_object(247*100", testbench)
        self.assertIn("TX slot generation mismatch", testbench)
        self.assertIn("TX final metadata mismatch", testbench)

    def test_back_to_back_frames_realign_codec_without_truncating_parser_tail(self):
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(".align_i(!serializer_busy[tx_lane])", core)
        self.assertIn("reg serializer_busy_d [0:1]", core)
        self.assertIn("wire serializer_busy_rise", core)
        self.assertIn("!receive_window || serializer_busy_rise ||", core)
        self.assertIn("rx_frame_valid[tx_lane]", core)
        self.assertEqual(1, core.count(".align_i(!receive_window)"))
        self.assertIn("run_object(247*20", testbench)

    def test_s2mm_stream_packs_fragment_tails_into_one_contiguous_packet(self):
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertIn("reg [2:0] out_pack_count_q", core)
        self.assertIn("out_pack_data_q[8*out_pack_count_q +: 8]", core)
        self.assertIn("out_pack_last_q <= out_final_q", core)
        self.assertNotIn("output_remaining == 3 ? 4'h7", core)
        self.assertIn("non-final AXI DMA beat contains a TKEEP hole", testbench)

    def test_dma_diagnostic_reads_only_bounded_live_descriptors(self):
        tcl = (ROOT / "scripts/hw/p9_xsdb_stage.tcl").read_text(
            encoding="utf-8"
        )
        self.assertIn("{rx_current 0x40400038 0x01001000 0x01001800}", tcl)
        self.assertIn("($pointer & 0x3F) != 0", tcl)
        self.assertIn("%s_pointer_invalid", tcl)

    def test_xsdb_waits_for_missing_debug_descendants_but_rejects_ambiguity(self):
        tcl = (ROOT / "scripts/hw/p9_xsdb_stage.tcl").read_text(
            encoding="utf-8"
        )
        self.assertIn("proc p9_wait_debug_targets", tcl)
        self.assertIn("P9 XSDB ambiguous debug-target topology", tcl)
        self.assertIn("P9 XSDB debug-target discovery timeout", tcl)
        self.assertIn("P9_XSDB_DEBUG_DISCOVERY_ATTEMPTS=", tcl)
        self.assertIn("P9_XSDB_DEBUG_DISCOVERY_ELAPSED_MS=", tcl)

    def test_unused_dma_sg_control_status_stream_is_disabled(self):
        build_tcl = (ROOT / "scripts/build_p9_z7010_candidate.tcl").read_text(
            encoding="utf-8"
        )
        freeze = (ROOT / "scripts/freeze_p9_artifacts.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            1, build_tcl.count("CONFIG.c_sg_include_stscntrl_strm {0}")
        )
        self.assertNotIn("CONFIG.c_sg_include_stscntrl_strm {1}", build_tcl)
        self.assertIn("P9_DMA_SG_STSCNTRL_STREAM=DISABLED", build_tcl)
        self.assertIn(
            "candidate unused DMA SG control/status stream is not disabled", freeze
        )

    def test_cumulative_ack_idempotence_and_sack_reorder_retry_policy(self):
        self.assertEqual(
            {"fault_drop_ack", "fault_duplicate_ack", "fault_reorder"},
            set(P9_HW.P9_FAULTS_WITHOUT_REQUIRED_RETRY),
        )
        self.assertTrue(P9_HW.p9_fault_requires_retry_evidence(
            "fault_drop_one_data"))
        self.assertFalse(P9_HW.p9_fault_requires_retry_evidence(
            "fault_recovery_soft_reset"))
        self.assertFalse(P9_HW.p9_fault_requires_retry_evidence(
            "fault_post_recovery_clean"))
        plans = {case.label: case for case in P9_HW.build_plans()["P9-18"]}
        self.assertEqual(247 * 96, plans["fault_drop_ack"].size)
        self.assertEqual(247, plans["fault_duplicate_data_by_ack_loss"].size)
        self.assertEqual(1 << 5, plans["fault_duplicate_ack"].faultflags)
        self.assertEqual(1 << 6, plans["fault_reorder"].faultflags)
        self.assertEqual(8, plans["fault_recovery_soft_reset"].command)
        labels = [case.label for case in P9_HW.build_plans()["P9-18"]]
        self.assertLess(labels.index("fault_reorder"),
                        labels.index("fault_crc_corruption"))
        self.assertLess(labels.index("fault_crc_corruption"),
                        labels.index("fault_retry_exhausted"))
        self.assertLess(labels.index("fault_retry_exhausted"),
                        labels.index("fault_recovery_soft_reset"))
        self.assertLess(labels.index("fault_recovery_soft_reset"),
                        labels.index("fault_post_recovery_clean"))

    def test_intentional_crc_fault_allows_only_expected_parser_counters(self):
        row, words = self.safe_idle_observation()
        row.update({
            "label": "fault_crc_corruption", "command": 3,
            "flags": 0, "lane": 3, "direction": 0, "rate": 2,
            "weights": 0x0101, "size": 247, "dropdata": 0,
            "dropack": 0, "faultflags": 1 << 4, "unavailable": 0,
            "injectmask": 0,
        })

        def set_pl(index: int, value: int) -> None:
            words[P9_HW.PL_SNAPSHOT_START + index] = value

        words[60] = 247
        words[79] = 0xFFFFFFFF
        set_pl(10, 3 | (2 << 8))
        set_pl(11, 0x0101)
        set_pl(20, 247)
        set_pl(21, 247)
        set_pl(41, 3)
        set_pl(96, 3)
        words[P9_HW.TERMINAL_WINDOW_START] = P9_HW.P9_TERMINAL_WINDOW_VALID
        words[P9_HW.TERMINAL_WINDOW_START + 1] = row["sequence"]
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertFalse(any("physical frame/CRC/symbol error" in error
                             for error in errors))
        row["faultflags"] = 0
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("physical frame/CRC/symbol error" in error
                            for error in errors))

    def test_ack_loss_recovery_accepts_cumulative_drain_without_retry(self):
        detail = {
            "label": "sack_ack_loss_recovery",
            "dropped_ack": 1,
            "ack_aggregation": 256,
            "ack_frames": 145,
            "physical_ack_good": 144,
            "tx_attempts": 256,
            "tx_retries": 0,
            "rx_delivery": 256,
            "outstanding_count": 0,
            "tx_next_sequence": 256,
            "tx_ack_base": 256,
            "rx_base_sequence": 256,
            "retry_exhausted": 0,
        }
        self.assertEqual([], P9_HW.ack_loss_recovery_errors(detail, 256))

    def test_ack_loss_recovery_fails_without_terminal_drain(self):
        detail = {
            "label": "sack_ack_loss_recovery",
            "dropped_ack": 1,
            "ack_aggregation": 256,
            "ack_frames": 145,
            "physical_ack_good": 144,
            "tx_attempts": 256,
            "tx_retries": 0,
            "rx_delivery": 256,
            "outstanding_count": 1,
            "tx_next_sequence": 256,
            "tx_ack_base": 255,
            "rx_base_sequence": 256,
            "retry_exhausted": 0,
        }
        errors = P9_HW.ack_loss_recovery_errors(detail, 256)
        self.assertTrue(any("did not drain" in error for error in errors))

    def test_old_sequence_fault_is_bound_to_object_start_base(self):
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertIn("object_initial_sequence_q - 1'b1", core)
        self.assertNotIn("dp_attempt_sequence - 1'b1", core)
        self.assertIn("run_object(247*2, 8'ha4", testbench)


if __name__ == "__main__":
    unittest.main()
