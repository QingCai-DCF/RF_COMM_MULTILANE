#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
import hashlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evidence/generated/vivado"
SUMMARY_JSON = OUT_DIR / "nonhardware_build_summary.json"
SUMMARY_MD = OUT_DIR / "nonhardware_build_summary.md"
XILINX_VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
STAGES = ["safe_idle", "tfdu_control_idle", "raw_pulse", "raw_lane_matrix", "protocol_lane0", "protocol_lane0_ack", "protocol_lane1", "protocol_lane1_ack", "protocol_two_lane_minimal", "protocol_lane0_soak", "protocol_two_lane_soak"]


def trim_trailing_space(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def sanitize_generated_reports() -> None:
    for pattern in ("*.rpt", "*.txt"):
        for path in OUT_DIR.glob(pattern):
            trim_trailing_space(path)


def clean_log_tail(stdout: str, stderr: str) -> str:
    tail = (stdout + "\n" + stderr)[-4000:].strip()
    return "\n".join(line.rstrip() for line in tail.splitlines())


def sha256_or_missing(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_key_value_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    markers: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        markers[key.strip()] = value.strip()
    return markers


def resolve_vivado_executable() -> tuple[str | None, dict[str, str | bool]]:
    vivado_on_path = shutil.which("vivado") or shutil.which("vivado.bat")
    fallback = XILINX_VIVADO_BIN / "vivado.bat"
    fallback_exists = fallback.exists()
    vivado = vivado_on_path or (str(fallback) if fallback_exists else None)
    discovery: dict[str, str | bool] = {
        "vivado_on_path": bool(vivado_on_path),
        "vivado_bat_fallback": str(fallback) if fallback_exists else "",
        "xilinx_vivado_2023_1_bin": str(XILINX_VIVADO_BIN),
    }
    return vivado, discovery


def write_summary(
    status: str,
    vivado: str | None,
    returncode: int | None = None,
    stdout: str = "",
    stderr: str = "",
    discovery: dict[str, str | bool] | None = None,
    stage_results: list[dict] | None = None,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    discovery = discovery or {}
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "vivado": vivado,
        "vivado_on_path": discovery.get("vivado_on_path", False),
        "vivado_bat_fallback": discovery.get("vivado_bat_fallback", ""),
        "xilinx_vivado_2023_1_bin": discovery.get("xilinx_vivado_2023_1_bin", str(XILINX_VIVADO_BIN)),
        "returncode": returncode,
        "no_hardware": True,
        "tcl": "scripts/vivado_nonhardware_build.tcl",
        "report_dir": "evidence/generated/vivado",
        "stdout": stdout,
        "stderr": stderr,
        "stage_results": stage_results or [],
    }
    stage_bitstreams = {}
    for stage in STAGES:
        stage_bitstream = OUT_DIR / f"ir_top_new_{stage}.bit"
        stage_debug_log = OUT_DIR / f"p4_auto_{stage}_debug_instrumentation.txt"
        stage_debug_ltx = OUT_DIR / f"p4_auto_{stage}_debug.ltx"
        if stage_bitstream.exists():
            stage_bitstreams[stage] = {
                "bitstream_path": f"evidence/generated/vivado/ir_top_new_{stage}.bit",
                "bitstream_sha256": sha256_or_missing(stage_bitstream),
                "p4_auto_debug_instrumentation_log": f"evidence/generated/vivado/p4_auto_{stage}_debug_instrumentation.txt" if stage_debug_log.exists() else "MISSING",
                "p4_auto_debug_instrumentation": parse_key_value_file(stage_debug_log),
                "p4_auto_debug_probes": f"evidence/generated/vivado/p4_auto_{stage}_debug.ltx" if stage_debug_ltx.exists() else "MISSING",
                "p4_auto_debug_probes_sha256": sha256_or_missing(stage_debug_ltx),
            }
    data["stage_bitstreams"] = stage_bitstreams
    bitstream_path = OUT_DIR / "ir_top_new_safe_idle.bit"
    if bitstream_path.exists():
        data["bitstream_path"] = "evidence/generated/vivado/ir_top_new_safe_idle.bit"
        data["bitstream_sha256"] = sha256_or_missing(bitstream_path)
    debug_log = OUT_DIR / "p4_auto_debug_instrumentation.txt"
    debug_ltx = OUT_DIR / "p4_auto_safe_idle_debug.ltx"
    debug_markers = parse_key_value_file(debug_log)
    if debug_log.exists():
        data["p4_auto_debug_instrumentation_log"] = "evidence/generated/vivado/p4_auto_debug_instrumentation.txt"
        data["p4_auto_debug_instrumentation"] = debug_markers
    if debug_ltx.exists():
        data["p4_auto_debug_probes"] = "evidence/generated/vivado/p4_auto_safe_idle_debug.ltx"
        data["p4_auto_debug_probes_sha256"] = sha256_or_missing(debug_ltx)
    SUMMARY_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Vivado Non-Hardware Build Summary",
        "",
        f"M5_VIVADO_NONHARDWARE_BUILD={status}",
        "NO_HARDWARE_ACTIONS_EXECUTED=1",
        "VIVADO_BATCH_TCL=scripts/vivado_nonhardware_build.tcl",
        "VIVADO_REPORT_DIR=evidence/generated/vivado",
        f"VIVADO_PATH_ON_PATH={1 if discovery.get('vivado_on_path') else 0}",
        f"XILINX_VIVADO_2023_1_BIN={discovery.get('xilinx_vivado_2023_1_bin', XILINX_VIVADO_BIN)}",
        f"XILINX_VIVADO_2023_1_BAT_AVAILABLE={1 if discovery.get('vivado_bat_fallback') else 0}",
    ]
    if vivado:
        lines.append(f"VIVADO_EXECUTABLE={vivado}")
    if returncode is not None:
        lines.append(f"VIVADO_EXIT_CODE={returncode}")
    bitstream_path = OUT_DIR / "ir_top_new_safe_idle.bit"
    if bitstream_path.exists():
        lines.append("BITSTREAM_GENERATED_NO_HW=1")
        lines.append("BITSTREAM_PATH=evidence/generated/vivado/ir_top_new_safe_idle.bit")
        lines.append(f"BITSTREAM_SHA256={sha256_or_missing(bitstream_path)}")
    if debug_log.exists():
        lines.append("P4_AUTO_DEBUG_INSTRUMENTATION_LOG=evidence/generated/vivado/p4_auto_debug_instrumentation.txt")
        for key in [
            "P4_AUTO_DEBUG_CLOCK_NET_COUNT",
            "P4_AUTO_DEBUG_STATUS_NET_COUNT",
            "P4_AUTO_ILA_CORE_INSERTION",
            "P4_AUTO_ILA_CORE_NAME",
            "P4_AUTO_ILA_PROBE0_WIDTH",
        ]:
            if key in debug_markers:
                lines.append(f"{key}={debug_markers[key]}")
    if debug_ltx.exists():
        lines.append("P4_AUTO_DEBUG_PROBES=evidence/generated/vivado/p4_auto_safe_idle_debug.ltx")
        lines.append(f"P4_AUTO_DEBUG_PROBES_SHA256={sha256_or_missing(debug_ltx)}")
    if stage_bitstreams:
        lines += [
            "",
            "## P4_AUTO Stage Bitstreams",
            "",
            "| Stage | Bitstream | SHA256 | ILA Core | Probe Width |",
            "| --- | --- | --- | --- | --- |",
        ]
        for stage, item in stage_bitstreams.items():
            markers = item.get("p4_auto_debug_instrumentation", {})
            lines.append(
                f"| {stage} | `{item['bitstream_path']}` | `{item['bitstream_sha256']}` | "
                f"{markers.get('P4_AUTO_ILA_CORE_NAME', 'MISSING')} | {markers.get('P4_AUTO_ILA_PROBE0_WIDTH', 'MISSING')} |"
            )
    if stage_results:
        lines += ["", "## Stage Commands", ""]
        for result in stage_results:
            lines.append(f"- `{result.get('stage')}` rc={result.get('returncode')}")
    if stdout or stderr:
        lines += ["", "## Log Tail", "", "```text", clean_log_tail(stdout, stderr), "```"]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Vivado non-hardware builds for generated RF_COMM stages.")
    parser.add_argument("--stage", action="append", choices=STAGES, help="Build only this stage. May be repeated.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected_stages = args.stage or STAGES
    vivado, discovery = resolve_vivado_executable()
    if not vivado:
        write_summary("PENDING_TOOL", None, discovery=discovery)
        print("M5_VIVADO_NONHARDWARE_BUILD=PENDING_TOOL")
        print("VIVADO_TOOL_MISSING=1")
        print("VIVADO_PATH_ON_PATH=0")
        print("XILINX_VIVADO_2023_1_BAT_AVAILABLE=0")
        print("NO_HARDWARE_ACTIONS_EXECUTED=1")
        return 0

    stage_results = []
    stdout_parts = []
    stderr_parts = []
    status = "PASS"
    returncode = 0
    for stage in selected_stages:
        cmd = [vivado, "-mode", "batch", "-source", "scripts/vivado_nonhardware_build.tcl", "-tclargs", str(ROOT), stage]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        stage_results.append(
            {
                "stage": stage,
                "cmd": " ".join(cmd),
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-4000:],
                "stderr_tail": proc.stderr[-4000:],
            }
        )
        stdout_parts.append(f"===== {stage} stdout =====\n{proc.stdout}")
        stderr_parts.append(f"===== {stage} stderr =====\n{proc.stderr}")
        if proc.returncode != 0:
            status = "FAIL"
            returncode = proc.returncode
            break
    sanitize_generated_reports()
    stdout = "\n".join(stdout_parts)
    stderr = "\n".join(stderr_parts)
    write_summary(status, vivado, returncode, stdout, stderr, discovery=discovery, stage_results=stage_results)
    print(f"M5_VIVADO_NONHARDWARE_BUILD={status}")
    print(f"VIVADO_PATH_ON_PATH={1 if discovery.get('vivado_on_path') else 0}")
    print(f"XILINX_VIVADO_2023_1_BAT_AVAILABLE={1 if discovery.get('vivado_bat_fallback') else 0}")
    print(f"VIVADO_EXECUTABLE={vivado}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=1")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
