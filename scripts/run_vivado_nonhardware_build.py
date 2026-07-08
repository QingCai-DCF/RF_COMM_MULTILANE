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
XILINX_VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")


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
    }
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
    if stdout or stderr:
        lines += ["", "## Log Tail", "", "```text", (stdout + "\n" + stderr)[-4000:].strip(), "```"]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    vivado, discovery = resolve_vivado_executable()
    if not vivado:
        write_summary("PENDING_TOOL", None, discovery=discovery)
        print("M5_VIVADO_NONHARDWARE_BUILD=PENDING_TOOL")
        print("VIVADO_TOOL_MISSING=1")
        print("VIVADO_PATH_ON_PATH=0")
        print("XILINX_VIVADO_2023_1_BAT_AVAILABLE=0")
        print("NO_HARDWARE_ACTIONS_EXECUTED=1")
        return 0

    cmd = [vivado, "-mode", "batch", "-source", "scripts/vivado_nonhardware_build.tcl", "-tclargs", str(ROOT)]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    status = "PASS" if proc.returncode == 0 else "FAIL"
    write_summary(status, vivado, proc.returncode, proc.stdout, proc.stderr, discovery=discovery)
    print(f"M5_VIVADO_NONHARDWARE_BUILD={status}")
    print(f"VIVADO_PATH_ON_PATH={1 if discovery.get('vivado_on_path') else 0}")
    print(f"XILINX_VIVADO_2023_1_BAT_AVAILABLE={1 if discovery.get('vivado_bat_fallback') else 0}")
    print(f"VIVADO_EXECUTABLE={vivado}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=1")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
