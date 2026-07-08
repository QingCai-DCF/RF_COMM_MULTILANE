#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "evidence/generated"
XILINX_VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
PASS = "PASS"
SKIP = "SKIP_WITH_REASON"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_version(cmd, timeout=20):
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def resolve_tool(exe, fallback: Path | None = None):
    found = shutil.which(exe)
    if found:
        return found
    if fallback and fallback.exists():
        return str(fallback)
    return None


def tool_entry(name, executables, version_cmd, kind, fallbacks=None):
    fallbacks = fallbacks or {}
    paths = {exe: resolve_tool(exe, fallbacks.get(exe)) for exe in executables}
    missing = [exe for exe, path in paths.items() if not path]
    if missing:
        return {
            "name": name,
            "kind": kind,
            "result": SKIP,
            "reason": f"missing executables: {', '.join(missing)}",
            "paths": paths,
            "version": "",
        }
    resolved_version_cmd = [paths.get(version_cmd[0], version_cmd[0]), *version_cmd[1:]]
    version = run_version(resolved_version_cmd)
    text = (version["stdout"] + "\n" + version["stderr"]).strip()
    return {
        "name": name,
        "kind": kind,
        "result": PASS if version["returncode"] == 0 else SKIP,
        "reason": "detected" if version["returncode"] == 0 else "version command failed",
        "paths": paths,
        "version": first_line(text),
        "version_returncode": version["returncode"],
    }


def detect_simulators():
    entries = [
        tool_entry("iverilog_vvp", ["iverilog", "vvp"], ["iverilog", "-V"], "icarus"),
        tool_entry("verilator", ["verilator"], ["verilator", "--version"], "verilator"),
        tool_entry(
            "xsim",
            ["xvlog", "xelab", "xsim"],
            ["xvlog", "-version"],
            "xsim",
            {
                "xvlog": XILINX_VIVADO_BIN / "xvlog.bat",
                "xelab": XILINX_VIVADO_BIN / "xelab.bat",
                "xsim": XILINX_VIVADO_BIN / "xsim.bat",
            },
        ),
        tool_entry("vivado_batch_compile", ["vivado"], ["vivado", "-version"], "vivado_batch", {"vivado": XILINX_VIVADO_BIN / "vivado.bat"}),
    ]
    selected = None
    for entry in entries:
        if entry["result"] == PASS and entry["kind"] in {"icarus", "xsim"}:
            selected = entry
            break
    fallback = selected is None
    return {
        "generated_at_utc": now_iso(),
        "entries": entries,
        "selected": selected,
        "python_reference_fallback": fallback,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def write_detection_summary(payload, path=GENERATED / "simulator_detection_summary.md"):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Simulator Detection Summary",
        "",
        f"generated_at_utc: {payload['generated_at_utc']}",
        "command: python tools/sim/detect_simulator.py",
        f"RESULT: {'PASS' if payload['selected'] else 'SKIP_WITH_REASON'}",
        f"REASON: {'HDL simulator selected' if payload['selected'] else 'no executable HDL simulator found; Python reference model fallback is required'}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "| Tool | Result | Version | Path / Reason |",
        "| --- | --- | --- | --- |",
    ]
    for entry in payload["entries"]:
        path_text = "; ".join(f"{name}={value or 'missing'}" for name, value in entry["paths"].items())
        lines.append(f"| {entry['name']} | {entry['result']} | `{entry.get('version', '')}` | {path_text}; {entry['reason']} |")
    lines.extend(
        [
            "",
            f"SELECTED: {payload['selected']['name'] if payload['selected'] else 'none'}",
            f"PYTHON_REFERENCE_FALLBACK: {str(payload['python_reference_fallback']).lower()}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect offline HDL simulation tools.")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout.")
    parser.add_argument("--summary", default=str(GENERATED / "simulator_detection_summary.md"))
    args = parser.parse_args()
    payload = detect_simulators()
    write_detection_summary(payload, Path(args.summary))
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"SIMULATOR_DETECTION: {'PASS' if payload['selected'] else 'SKIP_WITH_REASON'}")
        print(f"SELECTED: {payload['selected']['name'] if payload['selected'] else 'none'}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
