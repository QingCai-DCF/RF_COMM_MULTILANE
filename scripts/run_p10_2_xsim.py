#!/usr/bin/env python3
"""Run the required bounded P10.2 four-lane XSIM suite offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P10_3_GOAL = "goals/P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_GOAL.md"
P10_3_GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
P10_4_GOAL = "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md"
P10_4_GOAL_SHA256 = "0098acc827d22ad8f72876f5551e70d8051452e0c81eb2bfe8986e142f47254f"
P10_5_GOAL = "goals/P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE_GOAL.md"
P10_5_GOAL_SHA256 = "5c08e89917ffc18150e37f65ff29cf7c48f749d81033fe02a0d1bce772c23a36"
BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
TOOLS = {name: BIN / f"{name}.bat" for name in ("xvlog", "xelab", "xsim")}
SUITE = "sim/tb/tb_p10_2_4lane_suite.sv"
ELAB = "sim/tb/tb_p10_2_lane_count_elaboration.sv"
CORE = [
    "rtl/ir_seq_math_pkg.sv", "rtl/ir_health_weighted_scheduler.sv",
    "rtl/ir_selective_repeat_tx.sv", "rtl/ir_selective_repeat_rx.sv",
    "rtl/ir_ack_aggregator.sv", "rtl/ir_data_plane_top.sv",
    "rtl/ir_tfdu_exact_duty_accountant.sv",
    "rtl/ir_tfdu_physical_module_safety.sv", "rtl/tfdu_lane_phy.sv",
    "rtl/ir_4ppm_codec.sv", "rtl/p9_rate_4ppm_rx.sv",
    "rtl/p9_4ppm_frame_tx.sv", "rtl/p9_4ppm_frame_rx.sv",
    "rtl/p10_1r_rx_admission.sv",
    "rtl/p10_4_connector_ack_rx_quarantine.sv",
    "rtl/p9_optical_transport_core.sv",
]
TESTS = (
    ("tb_ax7020_4lane_profile", "TB_AX7020_4LANE_PROFILE=PASS",
     ["rtl/p10_2_lane_activity_leds.sv", SUITE]),
    ("tb_4lane_lane_mask_matrix", "TB_4LANE_LANE_MASK_MATRIX=PASS",
     ["rtl/ir_health_weighted_scheduler.sv", SUITE]),
    ("tb_4lane_scheduler_fairness", "TB_4LANE_SCHEDULER_FAIRNESS=PASS", [SUITE]),
    ("tb_4lane_retry_migration", "TB_4LANE_RETRY_MIGRATION=PASS",
     ["rtl/ir_retry_migration.sv", SUITE]),
    ("tb_4lane_echo_admission", "TB_4LANE_ECHO_ADMISSION=PASS",
     ["rtl/p10_1r_rx_admission.sv", SUITE]),
    ("tb_4lane_streaming", "TB_4LANE_STREAMING=PASS",
     ["rtl/ir_seq_math_pkg.sv", "rtl/ir_selective_repeat_rx.sv", SUITE]),
    ("tb_4lane_dual_endpoint", "TB_4LANE_DUAL_ENDPOINT=PASS", [*CORE, SUITE]),
    ("tb_2lane_4lane_regression", "TB_2LANE_4LANE_REGRESSION=PASS",
     [*CORE, ELAB, SUITE]),
    ("tb_p10_2_lane_count_elaboration", "TB_P10_2_LANE_COUNT_ELABORATION=PASS",
     [*CORE, ELAB]),
)
P10_3_TESTS = (
    ("tb_p10_3_single_lane_ack_progress",
     "TB_P10_3_SINGLE_LANE_ACK_PROGRESS=PASS", [*CORE, SUITE]),
    ("tb_p10_3_atomic_lane_migration",
     "TB_P10_3_ATOMIC_LANE_MIGRATION=PASS", [*CORE, SUITE]),
    ("tb_p10_fault_forensics", "P10_FAULT_FORENSICS_XSIM=PASS",
     ["rtl/p10_fault_forensics.sv", "sim/tb/tb_p10_fault_forensics.sv"]),
    ("tb_p10_forensic_safety_integration",
     "P10_FORENSIC_SAFETY_INTEGRATION_XSIM=PASS",
     [*CORE, "sim/tb/tb_p10_forensic_safety_integration.sv"]),
)
P10_4_TESTS = (
    ("tb_p10_4_connector_ack_quarantine",
     "TB_P10_4_CONNECTOR_ACK_QUARANTINE=PASS", [
        "rtl/p10_1r_rx_admission.sv",
        "rtl/p10_4_connector_ack_rx_quarantine.sv",
        SUITE,
    ]),
    ("tb_p10_4_perf_command", "P10_4_PERF_COUNTER_SPLIT_XSIM=PASS", [
        "rtl/generated/ir_register_map_defs.svh",
        "rtl/p10_1_metric_counter.sv",
        "rtl/p10_1_timer_snapshot.sv",
        "rtl/p10_1_event_fifo.sv",
        "rtl/p10_1_perf_monitor.sv",
        "sim/tb/tb_p10_4_perf_command.sv",
    ]),
    ("tb_p10_4_forensic_safety_integration",
     "P10_4_FORENSIC_SAFETY_INTEGRATION_XSIM=PASS",
     [*CORE, "sim/tb/tb_p10_4_forensic_safety_integration.sv"]),
)
PERIPHERAL_CORE = [
    *CORE,
    "rtl/p6_axi_lite_bridge.sv",
    "rtl/p10_1_metric_counter.sv",
    "rtl/p10_1_timer_snapshot.sv",
    "rtl/p10_1_event_fifo.sv",
    "rtl/p10_1_perf_monitor.sv",
    "rtl/p10_fault_forensics.sv",
    "rtl/p9_axi_dma_peripheral.sv",
]
P10_5_TESTS = (
    ("tb_p10_5_role_mask_commit", "TB_P10_5_ROLE_MASK_COMMIT=PASS",
     [*PERIPHERAL_CORE, "sim/tb/tb_p10_5_role_mask_commit.sv"]),
    ("tb_p10_5_half_duplex_compatibility",
     "TB_2LANE_4LANE_REGRESSION=PASS",
     [*CORE, ELAB, SUITE], "tb_2lane_4lane_regression"),
    ("tb_p10_5_dual_direction_l2", "TB_P10_5_DUAL_DIRECTION_L2=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
    ("tb_p10_5_ack_piggyback", "TB_P10_5_ACK_PIGGYBACK=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
    ("tb_p10_5_control_only_ack", "TB_P10_5_CONTROL_ONLY_ACK=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
    ("tb_p10_5_bidirectional_dma", "TB_P10_5_BIDIRECTIONAL_DMA=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
    ("tb_p10_5_1plus1_mask_matrix", "TB_P10_5_1PLUS1_MASK_MATRIX=PASS",
     [*PERIPHERAL_CORE, "sim/tb/tb_p10_5_role_mask_commit.sv"],
     "tb_p10_5_role_mask_commit"),
    ("tb_p10_5_2plus1_mask_matrix", "TB_P10_5_2PLUS1_MASK_MATRIX=PASS",
     [*PERIPHERAL_CORE, "sim/tb/tb_p10_5_role_mask_commit.sv"],
     "tb_p10_5_role_mask_commit"),
    ("tb_p10_5_1plus2_mask_matrix", "TB_P10_5_1PLUS2_MASK_MATRIX=PASS",
     [*PERIPHERAL_CORE, "sim/tb/tb_p10_5_role_mask_commit.sv"],
     "tb_p10_5_role_mask_commit"),
    ("tb_p10_5_2plus2_partitions", "TB_P10_5_2PLUS2_PARTITIONS=PASS",
     [*PERIPHERAL_CORE, "sim/tb/tb_p10_5_role_mask_commit.sv"],
     "tb_p10_5_role_mask_commit"),
    ("tb_p10_5_role_epoch_stale", "TB_P10_5_ROLE_EPOCH_STALE=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
    ("tb_p10_5_direction_abort_isolation",
     "TB_P10_5_DIRECTION_ABORT_ISOLATION=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
    ("tb_p10_5_dual_direction_faults", "TB_P10_5_DUAL_DIRECTION_FAULTS=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
    ("tb_p10_5_dual_endpoint_integration",
     "TB_P10_5_DUAL_ENDPOINT_INTEGRATION=PASS",
     [*CORE, "sim/tb/tb_p10_5_dual_direction.sv"],
     "tb_p10_5_dual_direction"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run_one(test_id: str, marker: str, sources: list[str], raw: Path,
            actual_top: str | None = None) -> dict[str, object]:
    top = actual_top or test_id
    work = raw / f"{test_id}_work"
    work.mkdir()
    log = raw / f"{test_id}.log"
    commands = (
        [str(TOOLS["xvlog"]), "-sv", "-i", str(ROOT / "rtl"),
         "-i", str(ROOT / "sim/tb"), *[str(ROOT / item) for item in sources]],
        [str(TOOLS["xelab"]), top, "-debug", "typical", "-s", f"{test_id}_snapshot"],
        [str(TOOLS["xsim"]), f"{test_id}_snapshot", "-runall"],
    )
    chunks: list[str] = []
    returncode = 0
    for command in commands:
        chunks.append("COMMAND=" + subprocess.list2cmdline(command) + "\n")
        result = subprocess.run(command, cwd=work, text=True, capture_output=True,
                                timeout=600, env={**os.environ, "NO_HARDWARE": "1",
                                "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
                                "NO_2H_QUALIFICATION": "true"})
        chunks.extend(("STDOUT_BEGIN\n", result.stdout, "\nSTDOUT_END\n",
                       "STDERR_BEGIN\n", result.stderr, "\nSTDERR_END\n"))
        returncode = result.returncode
        if returncode != 0:
            break
    text = "".join(chunks) + f"RETURN_CODE={returncode}\n"
    log.write_text(text, encoding="utf-8", errors="replace", newline="\n")
    fatal = bool(re.search(r"(^|\n)(Fatal:|FATAL_ERROR|ERROR:.*\$fatal)", text))
    status = "PASS" if returncode == 0 and marker in text and not fatal else "FAIL"
    return {"test_id": test_id, "elaboration_top": top,
            "status": status, "required_marker": marker,
            "marker_present": marker in text, "fatal_detected": fatal,
            "returncode": returncode, "log": rel(log), "log_sha256": sha(log)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir")
    parser.add_argument("--campaign", choices=("p10_2", "p10_3", "p10_3f", "p10_4", "p10_5"),
                        default="p10_2")
    parser.add_argument(
        "--only", choices=[
            test[0] for test in (*TESTS, *P10_3_TESTS, *P10_4_TESTS, *P10_5_TESTS)
        ])
    args = parser.parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_2_XSIM_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED", file=sys.stderr)
        return 2
    if any(not tool.is_file() for tool in TOOLS.values()):
        print("P10_2_XSIM_REFUSED=MISSING_VIVADO_SIMULATOR", file=sys.stderr)
        return 2
    if args.campaign in {"p10_3", "p10_3f", "p10_4", "p10_5"} and (
            not (ROOT / P10_3_GOAL).is_file() or
            sha(ROOT / P10_3_GOAL) != P10_3_GOAL_SHA256):
        print("P10_3_XSIM_REFUSED=GOAL_HASH_MISMATCH", file=sys.stderr)
        return 2
    if args.campaign in {"p10_4", "p10_5"} and (
            not (ROOT / P10_4_GOAL).is_file() or
            sha(ROOT / P10_4_GOAL) != P10_4_GOAL_SHA256):
        print("P10_4_XSIM_REFUSED=GOAL_HASH_MISMATCH", file=sys.stderr)
        return 2
    if args.campaign == "p10_5" and (
            not (ROOT / P10_5_GOAL).is_file() or
            sha(ROOT / P10_5_GOAL) != P10_5_GOAL_SHA256):
        print("P10_5_XSIM_REFUSED=GOAL_HASH_MISMATCH", file=sys.stderr)
        return 2
    output_name = args.output_dir or {
        "p10_2": "evidence/generated/p10_2_raw/xsim",
        "p10_3": "evidence/generated/p10_3_xsim",
        "p10_3f": "evidence/generated/p10_3_fault_forensics_xsim",
        "p10_4": "evidence/generated/p10_4_xsim",
        "p10_5": "evidence/generated/p10_5_xsim",
    }[args.campaign]
    output = (ROOT / output_name).resolve()
    output.relative_to(ROOT.resolve())
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    raw = output / "raw" / run_id
    raw.mkdir(parents=True)
    available = (
        (*TESTS, *P10_3_TESTS, *P10_4_TESTS, *P10_5_TESTS)
        if args.campaign == "p10_5"
        else (*TESTS, *P10_3_TESTS, *P10_4_TESTS)
        if args.campaign == "p10_4"
        else (*TESTS, *P10_3_TESTS)
        if args.campaign in {"p10_3", "p10_3f"}
        else TESTS
    )
    selected = [test for test in available
                if args.only is None or args.only == test[0]]
    if not selected:
        print("P10_2_XSIM_REFUSED=TEST_NOT_IN_CAMPAIGN", file=sys.stderr)
        return 2
    results = [run_one(test[0], test[1], list(test[2]), raw,
                       test[3] if len(test) == 4 else None)
               for test in selected]
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    source_files = sorted({item for test in selected for item in test[2]} |
                          {rel(Path(__file__).resolve())})
    if args.campaign in {"p10_3", "p10_3f", "p10_4", "p10_5"}:
        source_files.extend([
            P10_3_GOAL,
            "config/hardware/p10_3_actual_wiring.yaml",
            "config/hardware/tfdu_module_inventory.yaml",
            "config/hardware/p10_3_ax7020_activity_leds.yaml",
            "docs/hardware/P10_3_AX7020_ACTIVITY_LED_DESIGN.md",
        ])
        if args.campaign in {"p10_3f", "p10_4", "p10_5"}:
            source_files.extend([
                "config/safety/p10_3_fault_forensics.yaml",
                "config/performance/p10_3f_staircase.yaml",
                "docs/design/P10_3_FIRST_FAULT_FORENSICS.md",
                "scripts/archive_p10_fault_forensics.py",
                "scripts/hw/p10_3f_fault_forensics.tcl",
                "scripts/run_p10_3f_staircase_hardware.py",
                "scripts/run_p10_3f_fault_forensics_offline.py",
                "scripts/freeze_p10_3f_artifacts.py",
                "scripts/finalize_p10_3f_offline.py",
            ])
        if args.campaign in {"p10_4", "p10_5"}:
            source_files.extend([
                P10_4_GOAL,
                "config/p10_4_connector_ack_rx_quarantine.yaml",
                "docs/design/P10_4_CONNECTOR_ACK_RX_QUARANTINE.md",
                "evidence/generated/p10_4_crc_bad_root_cause_diagnosis.json",
            ])
        if args.campaign == "p10_5":
            source_files.extend([
                P10_5_GOAL,
                "config/p10_5_dual_direction.yaml",
                "config/generated/p10_5_dual_direction.py",
                "config/generated/p10_5_capability_table.json",
                "rtl/generated/p10_5_dual_direction_pkg.sv",
                "software/ps_driver/p10_5_dual_direction_config.h",
                "scripts/generate_p10_5_config.py",
                "scripts/model_p10_5_dual_direction.py",
                "docs/design/P10_5_DUAL_DIRECTION_CAPABILITY.md",
            ])
        source_files = sorted(set(source_files))
    summary = {
        "schema_version": 1,
        "test_id": {
            "p10_2": "P10_2_4LANE_XSIM",
            "p10_3": "P10_3_4LANE_XSIM",
            "p10_3f": "P10_3F_FIRST_FAULT_4LANE_XSIM",
            "p10_4": "P10_4_HARDENED_4LANE_XSIM",
            "p10_5": "P10_5_DUAL_DIRECTION_XSIM",
        }[args.campaign],
        "campaign": args.campaign,
        "status": status, "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--", *source_files], cwd=ROOT, text=True)),
        "no_hardware": True, "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "source_sha256": {item: sha(ROOT / item) for item in source_files},
        "results": results,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8", newline="\n")
    lines = [f"# {args.campaign.replace('_', '.')} four-lane XSIM", "",
             f"- Status: `{status}`",
             "- Hardware actions executed: `false`", "",
             "| Test | Status | Log |", "|---|---|---|"]
    lines.extend(f"| {item['test_id']} | {item['status']} | `{item['log']}` |"
                 for item in results)
    (output / "summary.md").write_text("\n".join(lines) + "\n",
                                       encoding="utf-8", newline="\n")
    print(f"{args.campaign.upper()}_4LANE_XSIM={status}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
