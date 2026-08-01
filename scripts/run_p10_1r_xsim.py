#!/usr/bin/env python3
"""Run the bounded P10.1R RX-admission, ACK, pipeline, and endpoint XSIM suite."""

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
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
TOOLS = {name: VIVADO_BIN / f"{name}.bat" for name in ("xvlog", "xelab", "xsim")}
FOCUSED_TB = "sim/tb/tb_p10_1r_focused.sv"

COMMON_RTL = [
    "rtl/ir_seq_math_pkg.sv",
    "rtl/ir_health_weighted_scheduler.sv",
    "rtl/ir_selective_repeat_tx.sv",
    "rtl/ir_selective_repeat_rx.sv",
    "rtl/ir_ack_aggregator.sv",
    "rtl/ir_data_plane_top.sv",
    "rtl/ir_tfdu_exact_duty_accountant.sv",
    "rtl/ir_tfdu_physical_module_safety.sv",
    "rtl/tfdu_lane_phy.sv",
    "rtl/ir_4ppm_codec.sv",
    "rtl/p9_rate_4ppm_rx.sv",
    "rtl/p9_4ppm_frame_tx.sv",
    "rtl/p9_4ppm_frame_rx.sv",
    "rtl/p10_1r_rx_admission.sv",
    "rtl/p9_optical_transport_core.sv",
]

ADMISSION_RTL = [
    "rtl/ir_4ppm_codec.sv",
    "rtl/p9_rate_4ppm_rx.sv",
    "rtl/p9_4ppm_frame_tx.sv",
    "rtl/p9_4ppm_frame_rx.sv",
    "rtl/p10_1r_rx_admission.sv",
    FOCUSED_TB,
]

TESTS: list[dict[str, Any]] = [
    {"top": "tb_tfdu_rx_admission_same_module_echo",
     "marker": "TB_TFDU_RX_ADMISSION_SAME_MODULE_ECHO=PASS",
     "sources": ADMISSION_RTL},
    {"top": "tb_tfdu_rx_admission_remote_ack",
     "marker": "TB_TFDU_RX_ADMISSION_REMOTE_ACK=PASS",
     "sources": ADMISSION_RTL},
    {"top": "tb_tfdu_rx_admission_other_lane",
     "marker": "TB_TFDU_RX_ADMISSION_OTHER_LANE=PASS",
     "sources": ADMISSION_RTL},
    {"top": "tb_tfdu_echo_guard_sweep",
     "marker": "TB_TFDU_ECHO_GUARD_SWEEP=PASS",
     "sources": ADMISSION_RTL},
    {"top": "tb_bundle_ack_window_2lane",
     "marker": "TB_BUNDLE_ACK_WINDOW_2LANE=PASS",
     "sources": ["rtl/ir_ack_aggregator.sv", FOCUSED_TB]},
    {"top": "tb_multi_object_continuous_pipeline",
     "marker": "TB_MULTI_OBJECT_CONTINUOUS_PIPELINE=PASS",
     "sources": ["rtl/ir_ack_aggregator.sv", FOCUSED_TB]},
    {"top": "tb_p10_1r_dual_endpoint",
     "marker": "TB_P10_1R_DUAL_ENDPOINT=PASS",
     "sources": [*COMMON_RTL, "sim/tb/tb_p10_1r_dual_endpoint.sv"]},
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run_one(spec: dict[str, Any], raw: Path) -> dict[str, Any]:
    top = spec["top"]
    work = raw / f"{top}_work"
    work.mkdir(parents=True, exist_ok=False)
    log = raw / f"{top}.log"
    commands = [
        [str(TOOLS["xvlog"]), "-sv", "-i", str(ROOT / "rtl"),
         "-i", str(ROOT / "sim/tb"),
         *[str(ROOT / item) for item in spec["sources"]]],
        [str(TOOLS["xelab"]), top, "-debug", "typical", "-s", f"{top}_snapshot"],
        [str(TOOLS["xsim"]), f"{top}_snapshot", "-runall"],
    ]
    chunks = [f"STARTED_UTC={now()}\n"]
    returncode = 0
    timed_out = False
    for command in commands:
        chunks.append("COMMAND=" + subprocess.list2cmdline(command) + "\n")
        try:
            result = subprocess.run(
                command, cwd=work, text=True, capture_output=True, timeout=600,
                env={**os.environ, "NO_HARDWARE": "1",
                     "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
            )
            chunks.extend(["STDOUT_BEGIN\n", result.stdout, "\nSTDOUT_END\n",
                           "STDERR_BEGIN\n", result.stderr, "\nSTDERR_END\n"])
            returncode = result.returncode
        except subprocess.TimeoutExpired as exc:
            chunks.extend([str(exc.stdout or ""), str(exc.stderr or ""),
                           "\nTIMEOUT_AFTER_SECONDS=600\n"])
            returncode = 124
            timed_out = True
        if returncode != 0:
            break
    combined = "".join(chunks) + f"FINISHED_UTC={now()}\nRETURN_CODE={returncode}\n"
    log.write_text(combined, encoding="utf-8", errors="replace", newline="\n")
    fatal = bool(re.search(r"(^|\n)(Fatal:|FATAL_ERROR|ERROR:.*\$fatal)", combined))
    marker_present = spec["marker"] in combined
    status = "PASS" if returncode == 0 and not timed_out and not fatal and marker_present else "FAIL"
    return {
        "test_id": top,
        "status": status,
        "required_marker": spec["marker"],
        "marker_present": marker_present,
        "returncode": returncode,
        "timed_out": timed_out,
        "fatal_detected": fatal,
        "log": relative(log),
        "log_sha256": digest(log),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="evidence/generated/p10_1r_xsim")
    args = parser.parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_1R_XSIM_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED", file=sys.stderr)
        return 2
    missing = [str(path) for path in TOOLS.values() if not path.is_file()]
    if missing:
        print("P10_1R_XSIM_REFUSED=MISSING_TOOLS:" + ",".join(missing), file=sys.stderr)
        return 2
    output = (ROOT / args.output_dir).resolve()
    try:
        output.relative_to(ROOT.resolve())
    except ValueError:
        print("P10_1R_XSIM_REFUSED=OUTPUT_OUTSIDE_REPOSITORY", file=sys.stderr)
        return 2
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    raw = output / "raw" / run_id
    raw.mkdir(parents=True, exist_ok=False)
    results = [run_one(spec, raw) for spec in TESTS]
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    source_files = sorted({item for spec in TESTS for item in spec["sources"]})
    summary = {
        "schema_version": 1,
        "test_id": "P10_1R_FOCUSED_XSIM",
        "status": status,
        "generated_at_utc": now(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--", *source_files],
            cwd=ROOT, text=True)),
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "source_sha256": {item: digest(ROOT / item) for item in source_files},
        "results": results,
    }
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    lines = ["# P10.1R focused XSIM", "", f"- Status: `{status}`",
             "- Hardware actions executed: `false`", "",
             "| Test | Status | Raw log |", "|---|---|---|"]
    lines.extend(f"| {item['test_id']} | {item['status']} | `{item['log']}` |"
                 for item in results)
    lines.extend(["", f"Raw run: `{relative(raw)}`", ""])
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"P10_1R_FOCUSED_XSIM={status}")
    print(f"P10_1R_FOCUSED_XSIM_SUMMARY={relative(json_path)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
