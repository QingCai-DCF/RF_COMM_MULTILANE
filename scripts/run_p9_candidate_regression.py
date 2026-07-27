#!/usr/bin/env python3
"""Run the source-bound P9 RTL and post-synthesis candidate regression."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated/p9_candidate_regression"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
TOOLS = {name: VIVADO_BIN / f"{name}.bat"
         for name in ("vivado", "xvlog", "xelab", "xsim")}
RTL_SOURCES = [
    "rtl/ir_seq_math_pkg.sv", "rtl/ir_health_weighted_scheduler.sv",
    "rtl/ir_selective_repeat_tx.sv", "rtl/ir_selective_repeat_rx.sv",
    "rtl/ir_ack_aggregator.sv", "rtl/ir_data_plane_top.sv",
    "rtl/ir_tfdu_exact_duty_accountant.sv",
    "rtl/ir_tfdu_physical_module_safety.sv", "rtl/tfdu_lane_phy.sv",
    "rtl/ir_4ppm_codec.sv", "rtl/p9_rate_4ppm_rx.sv",
    "rtl/p9_4ppm_frame_tx.sv", "rtl/p9_4ppm_frame_rx.sv",
    "rtl/p9_optical_transport_core.sv", "sim/tb/tb_p9_optical_transport_core.sv",
]
FRAME_LINK_SOURCES = [
    "rtl/ir_4ppm_codec.sv", "rtl/p9_rate_4ppm_rx.sv",
    "rtl/p9_4ppm_frame_tx.sv", "rtl/p9_4ppm_frame_rx.sv",
    "sim/tb/tb_p9_4ppm_frame_link.sv",
]
POST_MARKERS = [
    "P9_POST_SYNTH_SAFE_RESET_PASS=1",
    "P9_POST_SYNTH_DISARM_KILL_PASS=1",
    "P9_POST_SYNTH_NO_PARTIAL_RESUME_PASS=1",
    "P9_POST_SYNTH_FINAL_SHUTDOWN_PASS=1",
    "TB_P9_POST_SYNTH_SAFETY=PASS",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def run_steps(name: str, commands: list[list[str]], work: Path,
              markers: list[str], timeout: int = 1800) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=False)
    log = work.parent / f"{name}.log"
    started = utc_now()
    chunks: list[str] = []
    returncode = 0
    for command in commands:
        chunks.append("COMMAND=" + subprocess.list2cmdline(command) + "\n")
        try:
            result = subprocess.run(command, cwd=work, text=True, capture_output=True,
                                    timeout=timeout, shell=False, env=os.environ.copy())
            chunks.extend(["STDOUT_BEGIN\n", result.stdout, "\nSTDOUT_END\n",
                           "STDERR_BEGIN\n", result.stderr, "\nSTDERR_END\n"])
            returncode = result.returncode
        except subprocess.TimeoutExpired as exc:
            chunks.extend([str(exc.stdout or ""), str(exc.stderr or ""),
                           f"\nTIMEOUT_AFTER_SECONDS={timeout}\n"])
            returncode = 124
        if returncode != 0:
            break
    combined = "".join(chunks)
    log.write_text(f"STARTED_UTC={started}\nFINISHED_UTC={utc_now()}\n"
                   f"RETURN_CODE={returncode}\n{combined}",
                   encoding="utf-8", errors="replace", newline="\n")
    fatal = re.search(r"(^|\n)(Fatal:|FATAL_ERROR|ERROR:.*\$fatal|.*EXPECT_FAIL:)",
                      combined)
    status = "PASS" if returncode == 0 and not fatal and all(
        marker in combined for marker in markers) else "FAIL"
    return {"status": status, "test_id": name, "returncode": returncode,
            "markers": markers, "log": rel(log), "log_sha256": sha256(log)}


def parse_markers(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", default="HEAD")
    args = parser.parse_args(argv)
    missing_tools = [str(path) for path in TOOLS.values() if not path.is_file()]
    if missing_tools:
        print("missing mandatory P9 regression tools: " + ", ".join(missing_tools),
              file=sys.stderr)
        return 2
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    requested_commit = subprocess.check_output(
        ["git", "rev-parse", args.source_commit], cwd=ROOT, text=True).strip()
    if requested_commit != source_commit:
        print("P9 candidate regression source commit must equal HEAD", file=sys.stderr)
        return 2
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "_" + source_commit[:12]
    raw = OUT / "raw" / run_id
    raw.mkdir(parents=True, exist_ok=False)

    rtl_commands = [
        [str(TOOLS["xvlog"]), "-sv", "-i", str(ROOT / "rtl"),
         *[str(ROOT / source) for source in RTL_SOURCES]],
        [str(TOOLS["xelab"]), "tb_p9_optical_transport_core", "-debug", "typical",
         "-s", "tb_p9_optical_transport_core_snapshot"],
        [str(TOOLS["xsim"]), "tb_p9_optical_transport_core_snapshot", "-runall"],
    ]
    rtl = run_steps("p9_rtl_full", rtl_commands, raw / "rtl_work",
                    ["TB_P9_OPTICAL_TRANSPORT_CORE=PASS"])

    frame_link_commands = [
        [str(TOOLS["xvlog"]), "-sv", "-i", str(ROOT / "rtl"),
         *[str(ROOT / source) for source in FRAME_LINK_SOURCES]],
        [str(TOOLS["xelab"]), "tb_p9_4ppm_frame_link", "-debug", "typical",
         "-s", "tb_p9_4ppm_frame_link_delayed_snapshot"],
        [str(TOOLS["xsim"]), "tb_p9_4ppm_frame_link_delayed_snapshot", "-runall"],
    ]
    frame_link = run_steps(
        "p9_frame_link_delayed", frame_link_commands, raw / "frame_link_work",
        ["TB_P9_4PPM_FRAME_LINK_DELAYED=PASS"],
    )

    post_dir = raw / "post_synth"
    build = run_steps("p9_post_synth_build", [[str(TOOLS["vivado"]), "-mode", "batch",
        "-source", str(ROOT / "scripts/build_p9_post_synth_core.tcl"), "-tclargs",
        str(ROOT), str(post_dir)]], raw / "vivado_work", ["P9_POST_SYNTH_BUILD=PASS"])
    build_markers = parse_markers(post_dir / "p9_post_synth_build_markers.txt")
    if any(build_markers.get(key) != expected for key, expected in {
        "P9_POST_SYNTH_BUILD": "PASS", "P9_POST_SYNTH_PART": "xc7z010clg400-1",
        "P9_POST_SYNTH_TOP": "p9_optical_transport_core",
        "P9_POST_SYNTH_DRC_CRITICAL_COUNT": "0",
        "P9_POST_SYNTH_DRC_ERROR_COUNT": "0",
        "P9_POST_SYNTH_REQP_1839_COUNT": "0",
    }.items()):
        build["status"] = "FAIL"
        build["marker_error"] = "post-synthesis identity/signoff marker mismatch"

    post = {"status": "FAIL", "test_id": "p9_post_synth_safety",
            "reason": "post-synthesis build failed"}
    netlist = post_dir / "post_synth_p9_core_funcsim.v"
    if build["status"] == "PASS" and netlist.is_file():
        post_commands = [
            [str(TOOLS["xvlog"]), str(netlist)],
            [str(TOOLS["xvlog"]), "-sv", str(ROOT / "sim/tb/tb_p9_post_synth_safety.sv")],
            [str(TOOLS["xelab"]), "tb_p9_post_synth_safety", "glbl", "-L",
             "unisims_ver", "-s", "tb_p9_post_synth_safety_snapshot"],
            [str(TOOLS["xsim"]), "tb_p9_post_synth_safety_snapshot", "-runall"],
        ]
        post = run_steps("p9_post_synth_safety", post_commands,
                         raw / "post_synth_work", POST_MARKERS)

    artifact_paths = [post_dir / name for name in (
        "post_synth_p9_core.dcp", "post_synth_p9_core_funcsim.v",
        "post_synth_timing_summary_p9_core.rpt",
        "post_synth_utilization_p9_core.rpt", "post_synth_drc_p9_core.rpt",
        "p9_post_synth_build_markers.txt")]
    artifacts = [{"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}
                 for path in artifact_paths if path.is_file()]
    status = "PASS" if (rtl["status"] == frame_link["status"] ==
                         build["status"] == post["status"] == "PASS") else "FAIL"
    summary = {
        "schema_version": 1, "status": status,
        "test_id": "P9-CANDIDATE-SOURCE-POST-SYNTH-REGRESSION",
        "generated_utc": utc_now(), "source_commit": source_commit,
        "profile": "Z7010_2LANE_DEV", "part": "xc7z010clg400-1",
        "rtl_full_regression": rtl, "delayed_frame_link_regression": frame_link,
        "post_synth_build": build,
        "post_synth_safety": post, "post_synth_markers": build_markers,
        "post_synth_artifacts": artifacts,
    }
    write_json(OUT / "p9_candidate_regression_summary.json", summary)
    print(f"P9_CANDIDATE_REGRESSION={status}")
    print(f"P9_CANDIDATE_REGRESSION_RUN_ID={run_id}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
