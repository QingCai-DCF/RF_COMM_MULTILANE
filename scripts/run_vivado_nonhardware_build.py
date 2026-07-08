#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evidence/generated/vivado"
SUMMARY_JSON = OUT_DIR / "nonhardware_build_summary.json"
SUMMARY_MD = OUT_DIR / "nonhardware_build_summary.md"


def write_summary(status: str, vivado: str | None, returncode: int | None = None, stdout: str = "", stderr: str = "") -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "vivado": vivado,
        "returncode": returncode,
        "no_hardware": True,
        "tcl": "scripts/vivado_nonhardware_build.tcl",
        "report_dir": "evidence/generated/vivado",
        "stdout": stdout,
        "stderr": stderr,
    }
    SUMMARY_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Vivado Non-Hardware Build Summary",
        "",
        f"M5_VIVADO_NONHARDWARE_BUILD={status}",
        "NO_HARDWARE_ACTIONS_EXECUTED=1",
        "VIVADO_BATCH_TCL=scripts/vivado_nonhardware_build.tcl",
        "VIVADO_REPORT_DIR=evidence/generated/vivado",
    ]
    if vivado:
        lines.append(f"VIVADO_EXECUTABLE={vivado}")
    if returncode is not None:
        lines.append(f"VIVADO_EXIT_CODE={returncode}")
    if stdout or stderr:
        lines += ["", "## Log Tail", "", "```text", (stdout + "\n" + stderr)[-4000:].strip(), "```"]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    vivado = shutil.which("vivado") or shutil.which("vivado.bat")
    if not vivado:
        write_summary("PENDING_TOOL", None)
        print("M5_VIVADO_NONHARDWARE_BUILD=PENDING_TOOL")
        print("VIVADO_TOOL_MISSING=1")
        print("NO_HARDWARE_ACTIONS_EXECUTED=1")
        return 0

    cmd = [vivado, "-mode", "batch", "-source", "scripts/vivado_nonhardware_build.tcl", "-tclargs", str(ROOT)]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    status = "PASS" if proc.returncode == 0 else "FAIL"
    write_summary(status, vivado, proc.returncode, proc.stdout, proc.stderr)
    print(f"M5_VIVADO_NONHARDWARE_BUILD={status}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=1")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
