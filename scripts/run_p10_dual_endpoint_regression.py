#!/usr/bin/env python3
"""Run the offline P10 dual-endpoint and legacy-P9 RTL regressions."""

from __future__ import annotations

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
OUT = ROOT / "evidence/generated/p10_dual_endpoint_regression"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
TOOLS = {name: VIVADO_BIN / f"{name}.bat" for name in ("xvlog", "xelab", "xsim")}

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
    "rtl/p9_optical_transport_core.sv",
]

TESTS = [
    {
        "test_id": "P10-RTL-DUAL-INDEPENDENT-ENDPOINT",
        "name": "p10_dual_endpoint_pair",
        "top": "tb_p10_dual_endpoint_pair",
        "sources": [*COMMON_RTL, "sim/tb/tb_p10_dual_endpoint_pair.sv"],
        "required": [
            "TB_P10_DUAL_ENDPOINT_PAIR=PASS",
            "P10_DUAL_RAW_PASS direction=0 lane=0 pulses=64",
            "P10_DUAL_RAW_PASS direction=1 lane=0 pulses=64",
            "P10_DUAL_RAW_PASS direction=0 lane=1 pulses=64",
            "P10_DUAL_RAW_PASS direction=1 lane=1 pulses=64",
            "P10_DUAL_OBJECT_PASS direction=0 lanes=3 length=9880",
            "P10_DUAL_OBJECT_PASS direction=1 lanes=3 length=9880 initial=0300 faults=00000000 drops=1/0",
            "P10_DUAL_OBJECT_PASS direction=1 lanes=3 length=600 initial=fffe",
            "P10_DUAL_OBJECT_PASS direction=0 lanes=3 length=600 initial=1000 faults=00000040",
            "P10_DUAL_OBJECT_PASS direction=1 lanes=3 length=600 initial=1800 faults=00000020",
            "P10_DUAL_OBJECT_PASS direction=1 lanes=3 length=600 initial=2000 faults=00000000 drops=1/1",
        ],
    },
    {
        "test_id": "P10-REGRESSION-P9-LEGACY-MONOLITHIC",
        "name": "p9_legacy_transport",
        "top": "tb_p9_optical_transport_core",
        "sources": [*COMMON_RTL, "sim/tb/tb_p9_optical_transport_core.sv"],
        "required": ["TB_P9_OPTICAL_TRANSPORT_CORE=PASS"],
    },
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def tracked_source_dirty(paths: list[str]) -> bool:
    return bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", *paths],
        cwd=ROOT, text=True))


def run_test(spec: dict[str, Any], raw: Path) -> dict[str, Any]:
    work = raw / f"{spec['name']}_work"
    work.mkdir(parents=True, exist_ok=False)
    log = raw / f"{spec['name']}.log"
    commands = [
        [str(TOOLS["xvlog"]), "-sv", "-i", str(ROOT / "rtl"),
         *[str(ROOT / source) for source in spec["sources"]]],
        [str(TOOLS["xelab"]), spec["top"], "-debug", "typical", "-s",
         f"{spec['name']}_snapshot"],
        [str(TOOLS["xsim"]), f"{spec['name']}_snapshot", "-runall"],
    ]
    chunks = [f"STARTED_UTC={now()}\n"]
    returncode = 0
    timed_out = False
    for command in commands:
        chunks.append("COMMAND=" + subprocess.list2cmdline(command) + "\n")
        try:
            result = subprocess.run(
                command, cwd=work, text=True, capture_output=True, timeout=1800,
                shell=False,
                env={**os.environ, "NO_HARDWARE": "1",
                     "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
            )
            chunks.extend([
                "STDOUT_BEGIN\n", result.stdout, "\nSTDOUT_END\n",
                "STDERR_BEGIN\n", result.stderr, "\nSTDERR_END\n",
            ])
            returncode = result.returncode
        except subprocess.TimeoutExpired as exc:
            chunks.extend([str(exc.stdout or ""), str(exc.stderr or ""),
                           "\nTIMEOUT_AFTER_SECONDS=1800\n"])
            returncode = 124
            timed_out = True
        if returncode != 0:
            break
    combined = "".join(chunks) + f"FINISHED_UTC={now()}\nRETURN_CODE={returncode}\n"
    log.write_text(combined, encoding="utf-8", errors="replace", newline="\n")
    fatal = bool(re.search(r"(^|\n)(Fatal:|FATAL_ERROR|ERROR:.*\$fatal)", combined))
    missing = [marker for marker in spec["required"] if marker not in combined]
    status = "PASS" if returncode == 0 and not timed_out and not fatal and not missing else "FAIL"
    metrics = {
        "raw_pass_count": combined.count("P10_DUAL_RAW_PASS"),
        "object_pass_count": combined.count("P10_DUAL_OBJECT_PASS"),
        "p10_final_marker_count": combined.count("TB_P10_DUAL_ENDPOINT_PAIR=PASS"),
        "p9_final_marker_count": combined.count("TB_P9_OPTICAL_TRANSPORT_CORE=PASS"),
    }
    return {
        "test_id": spec["test_id"],
        "status": status,
        "returncode": returncode,
        "timed_out": timed_out,
        "fatal_detected": fatal,
        "missing_markers": missing,
        "metrics": metrics,
        "log": rel(log),
        "log_sha256": sha256(log),
    }


def run_python_tests(raw: Path) -> dict[str, Any]:
    log = raw / "p9_runner_unit_tests.log"
    command = [sys.executable, "-m", "unittest", "tests.test_p9_runner", "-q"]
    result = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=600,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    content = (
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"RETURN_CODE={result.returncode}\nSTDOUT_BEGIN\n{result.stdout}\nSTDOUT_END\n" +
        f"STDERR_BEGIN\n{result.stderr}\nSTDERR_END\n"
    )
    log.write_text(content, encoding="utf-8", errors="replace", newline="\n")
    return {
        "test_id": "P10-REGRESSION-P9-RUNNER-UNIT",
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returncode": result.returncode,
        "log": rel(log),
        "log_sha256": sha256(log),
    }


def run_register_map_verify(raw: Path) -> dict[str, Any]:
    log = raw / "register_map_verify.log"
    command = [sys.executable, "scripts/generate_register_headers.py", "--verify"]
    result = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=600,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    content = (
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"RETURN_CODE={result.returncode}\nSTDOUT_BEGIN\n{result.stdout}\nSTDOUT_END\n" +
        f"STDERR_BEGIN\n{result.stderr}\nSTDERR_END\n"
    )
    log.write_text(content, encoding="utf-8", errors="replace", newline="\n")
    required = (
        "REGISTER_MAP_SINGLE_SOURCE_CREATED=1",
        "REGISTER_MAP_VERSION=P9-3",
    )
    missing = [marker for marker in required if marker not in content]
    return {
        "test_id": "P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY",
        "status": "PASS" if result.returncode == 0 and not missing else "FAIL",
        "returncode": result.returncode,
        "missing_markers": missing,
        "log": rel(log),
        "log_sha256": sha256(log),
    }


def main() -> int:
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_REGRESSION_REFUSED: offline environment required", file=sys.stderr)
        return 2
    missing_tools = [str(path) for path in TOOLS.values() if not path.is_file()]
    if missing_tools:
        print("P10_REGRESSION_REFUSED: missing tools: " + ", ".join(missing_tools),
              file=sys.stderr)
        return 2
    source_files = sorted({source for spec in TESTS for source in spec["sources"]})
    source_worktree_dirty = tracked_source_dirty([
        *source_files, rel(Path(__file__).resolve()),
        "scripts/generate_register_headers.py", "tests/test_p9_runner.py",
        "config/register_map/ir_axi_regs.yaml",
    ])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    raw = OUT / "raw" / run_id
    raw.mkdir(parents=True, exist_ok=False)
    results = [run_test(spec, raw) for spec in TESTS]
    results.append(run_python_tests(raw))
    results.append(run_register_map_verify(raw))
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": "P10-DUAL-ENDPOINT-PORTABLE-REGRESSION",
        "status": status,
        "generated_at_utc": now(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": source_worktree_dirty,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "source_sha256": {source: sha256(ROOT / source) for source in source_files},
        "results": results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    summary_json = OUT / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8", newline="\n")
    lines = [
        "# P10 dual-independent-endpoint portable regression",
        "",
        f"- Status: `{status}`",
        "- Hardware actions executed: `false`",
        "- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).",
        "- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.",
        "",
        "| Test ID | Result | Log SHA256 |",
        "|---|---|---|",
    ]
    for item in results:
        lines.append(f"| {item['test_id']} | {item['status']} | `{item['log_sha256']}` |")
    lines.extend(["", f"Raw run: `{rel(raw)}`", ""])
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"P10_DUAL_ENDPOINT_PORTABLE_REGRESSION={status}")
    print(f"P10_DUAL_ENDPOINT_REGRESSION_SUMMARY={rel(summary_json)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
