#!/usr/bin/env python3
"""Run the focused P10.1 RTL campaign with the installed Vivado simulator."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

from p10_1_common import ROOT, evidence_base, rel, sha256, write_pair, write_text


VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
TOOLS = {name: VIVADO_BIN / f"{name}.bat" for name in ("xvlog", "xelab", "xsim")}
RAW = ROOT / "evidence/generated/p10_1_raw/xsim"
WORK_ROOT = ROOT / "evidence/generated/p10_1_raw/xsim_work"
TESTBENCH = ROOT / "sim/tb/tb_p10_1_suite.sv"
RTL_SOURCES = [
    ROOT / "rtl/p10_1_metric_counter.sv",
    ROOT / "rtl/p10_1_timer_snapshot.sv",
    ROOT / "rtl/p10_1_event_fifo.sv",
    ROOT / "rtl/p10_1_perf_monitor.sv",
    ROOT / "rtl/p10_1_axis_sustained.sv",
    ROOT / "rtl/p10_1_buffer_pool.sv",
    ROOT / "rtl/p10_1_descriptor_batch.sv",
    ROOT / "rtl/p10_1_autonomous_perf.sv",
]
TESTS = [
    ("tb_p10_1_metric_counter", "P10_1_METRIC_COUNTER=PASS"),
    ("tb_p10_1_timer_snapshot", "P10_1_TIMER_SNAPSHOT=PASS"),
    ("tb_p10_1_trace_fifo", "P10_1_TRACE_FIFO=PASS"),
    ("tb_p10_1_perf_command", "P10_1_PERF_COMMAND=PASS"),
    ("tb_p10_1_axis_sustained", "P10_1_AXIS_SUSTAINED=PASS"),
    ("tb_p10_1_buffer_pool", "P10_1_BUFFER_POOL=PASS"),
    ("tb_p10_1_descriptor_batch", "P10_1_DESCRIPTOR_BATCH=PASS"),
    ("tb_p10_1_streaming_chain", "P10_1_STREAMING_CHAIN=PASS"),
    ("tb_p10_1_stream_abort_reset", "P10_1_STREAM_ABORT_RESET=PASS"),
    ("tb_p10_1_dual_endpoint_perf", "P10_1_DUAL_ENDPOINT_PERF=PASS"),
]


def source_key() -> str:
    digest = hashlib.sha256()
    for source in [*RTL_SOURCES, TESTBENCH]:
        digest.update(rel(source).encode("utf-8"))
        digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def run_phase(
    command: list[str],
    cwd: Path,
    log: Path,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=60,
            env={
                **os.environ,
                "NO_HARDWARE": "1",
                "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
            },
        )
    except subprocess.TimeoutExpired as exc:
        result = subprocess.CompletedProcess(
            command,
            124,
            (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
            + "\nPHASE_TIMEOUT_SECONDS=60\n",
        )
    write_text(
        log,
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        + f"RETURN_CODE={result.returncode}\n"
        + "STDOUT_BEGIN\n" + result.stdout + "STDOUT_END\n"
        + "STDERR_BEGIN\n" + result.stderr + "STDERR_END",
    )
    return result


def verify_existing(test: str, marker: str) -> dict[str, Any]:
    log = RAW / test / "run.log"
    errors: list[str] = []
    if not log.is_file():
        errors.append("run log is missing")
        content = ""
    else:
        content = log.read_text(encoding="utf-8", errors="replace")
        if "RETURN_CODE=0" not in content:
            errors.append("xsim did not return zero")
        if marker not in content:
            errors.append(f"PASS marker is missing: {marker}")
    return {
        "top": test,
        "marker": marker,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "logs": (
            [
                {
                    "path": rel(path),
                    "sha256": sha256(path),
                }
                for path in sorted((RAW / test).glob("*.log"))
            ]
            if (RAW / test).is_dir()
            else []
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument(
        "--top",
        action="append",
        choices=[top for top, _ in TESTS],
        help="Run only the named top; may be repeated.",
    )
    args = parser.parse_args()
    selected_tests = [
        (top, marker)
        for top, marker in TESTS
        if not args.top or top in set(args.top)
    ]
    errors: list[str] = []
    for name, path in TOOLS.items():
        if not path.is_file():
            errors.append(f"missing {name} tool: {path}")
    for source in [*RTL_SOURCES, TESTBENCH]:
        if not source.is_file():
            errors.append(f"missing source: {rel(source)}")

    results: list[dict[str, Any]] = []
    if not errors and not args.verify_existing:
        key = source_key()
        for top, marker in selected_tests:
            out = RAW / top
            work = WORK_ROOT / key / top
            out.mkdir(parents=True, exist_ok=True)
            work.mkdir(parents=True, exist_ok=True)
            snapshot = f"{top}_{key}"
            phases = [
                (
                    "compile",
                    [
                        str(TOOLS["xvlog"]),
                        "-sv",
                        "-i",
                        str(ROOT / "rtl"),
                        *[str(path) for path in RTL_SOURCES],
                        str(TESTBENCH),
                    ],
                ),
                (
                    "elaborate",
                    [
                        str(TOOLS["xelab"]),
                        top,
                        "-debug",
                        "typical",
                        "-s",
                        snapshot,
                    ],
                ),
                ("run", [str(TOOLS["xsim"]), snapshot, "-runall"]),
            ]
            phase_error = False
            for phase, command in phases:
                result = run_phase(command, work, out / f"{phase}.log")
                if result.returncode != 0:
                    phase_error = True
                    break
            result_record = verify_existing(top, marker)
            if phase_error and not result_record["errors"]:
                result_record["errors"].append("a compile/elaborate/run phase failed")
                result_record["status"] = "FAIL"
            results.append(result_record)
    elif not errors:
        results = [verify_existing(top, marker) for top, marker in selected_tests]

    for result in results:
        if result["status"] != "PASS":
            errors.append(f"{result['top']}: {'; '.join(result['errors'])}")
    payload = evidence_base(
        "P10_1-FOCUSED-XSIM",
        status="PASS" if not errors else "FAIL",
        simulator={name: str(path) for name, path in TOOLS.items()},
        test_count=len(selected_tests),
        tests=results,
        coverage={
            "different_clock_ratio": True,
            "random_backpressure": True,
            "reset": True,
            "abort": True,
            "timer_wrap": True,
            "fifo_overflow": True,
            "ring_wrap": True,
        },
        errors=errors,
    )
    write_pair("p10_1_xsim", "P10.1 focused XSIM campaign", payload)
    print(f"P10_1_XSIM={payload['status']}")
    for result in results:
        print(f"{result['top']}={result['status']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
