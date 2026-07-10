#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
XSDB = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsdb.bat")
EVIDENCE = ROOT / "evidence/hardware/p6/ps_driver_runtime"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run_logged(command: list[str], stdout: Path, stderr: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    stdout.write_text(proc.stdout, encoding="utf-8")
    stderr.write_text(proc.stderr, encoding="utf-8")
    return proc


def shutdown(label: str) -> bool:
    proc = run_logged(
        [str(VIVADO), "-mode", "batch", "-source", "scripts/legacy_safe_tools/program_tfdu_shutdown.tcl"],
        EVIDENCE / f"{label}.stdout.log", EVIDENCE / f"{label}.stderr.log", 240,
    )
    text = proc.stdout + proc.stderr
    return proc.returncode == 0 or "TFDU_SHUTDOWN_PROGRAMMED" in text


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if os.environ.get("RF_COMM_HW_AUTH") != "P6_LOCAL_TRANSPORT_APPROVED":
        raise SystemExit("RF_COMM_HW_AUTH=P6_LOCAL_TRANSPORT_APPROVED required")
    auth = (ROOT / ".hardware_authorization/P6_LOCAL_TRANSPORT_APPROVED.txt").read_text(encoding="utf-8")
    for phrase in ("NETWORK_CABLE_CONNECTED=false", "HARDWARE_MOVEMENT_ALLOWED=false", "AVAILABLE_LANES=2", "MAX_LANE_MASK=0x3", "SHUTDOWN_ON_EXIT=required"):
        if phrase not in auth:
            raise SystemExit(f"authorization phrase missing: {phrase}")
    profile = ROOT / "profiles/p6/p6_ps_driver_runtime_mailbox.json"
    profile_data = json.loads(profile.read_text(encoding="utf-8"))
    if profile_data["network_required"] or profile_data["motion_required"] or profile_data["lane_count"] != 2 or profile_data["max_lane_mask"] != "0x3":
        raise SystemExit("P6 PS runtime profile violates authorization boundary")
    ps_candidate = json.loads((ROOT / "evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate_build_summary.json").read_text(encoding="utf-8"))
    runtime_build = json.loads((ROOT / "evidence/generated/vitis/p6_ps_runtime/p6_ps_runtime_build_summary.json").read_text(encoding="utf-8"))
    bit = ROOT / ps_candidate["artifacts"]["bit"]["immutable"]
    xsa = ROOT / ps_candidate["artifacts"]["xsa"]["immutable"]
    elf = ROOT / runtime_build["artifacts"]["elf"]["immutable"]
    ps7_init = ROOT / "build/p6_ps_vitis_workspace/p6_platform/hw/ps7_init.tcl"
    active_xdc = ROOT / "constraints/active/PORT1.generated.xdc"
    pinmap = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
    shutdown_bit = ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
    auth_file = ROOT / ".hardware_authorization/P6_LOCAL_TRANSPORT_APPROVED.txt"
    raw_result = EVIDENCE / "p6_ps_runtime_mailbox_raw.log"
    before_ok = shutdown("before_stage")
    stage_proc: subprocess.CompletedProcess[str] | None = None
    after_ok = False
    try:
        if not before_ok:
            raise RuntimeError("shutdown before PS runtime failed")
        stage_proc = run_logged(
            [str(XSDB), "scripts/hw/p6_ps_runtime_execute.tcl", str(ROOT), str(bit), str(elf), str(ps7_init), str(raw_result), "tcp:127.0.0.1:3121"],
            EVIDENCE / "p6_ps_stage.stdout.log", EVIDENCE / "p6_ps_stage.stderr.log", 300,
        )
    finally:
        after_ok = shutdown("after_stage")
    raw = raw_result.read_text(encoding="utf-8", errors="ignore") if raw_result.exists() else ""
    passed = bool(stage_proc and stage_proc.returncode == 0 and "P6_PS_RUNTIME_MAILBOX=PASS" in raw and before_ok and after_ok)
    summary = {
        "P6_PS_DRIVER_RUNTIME": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bitstream": rel(bit), "bitstream_sha256": sha(bit),
        "xsa": rel(xsa), "xsa_sha256": sha(xsa),
        "elf": rel(elf), "elf_sha256": sha(elf),
        "profile": rel(profile), "profile_sha256": sha(profile),
        "active_xdc": rel(active_xdc), "active_xdc_sha256": sha(active_xdc),
        "pinmap": rel(pinmap), "pinmap_sha256": sha(pinmap),
        "shutdown_bitstream": rel(shutdown_bit), "shutdown_bitstream_sha256": sha(shutdown_bit),
        "authorization_file": rel(auth_file), "authorization_file_sha256": sha(auth_file),
        "mailbox_base": "0x00020000",
        "syntax_only": False,
        "hardware_actions_executed": True,
        "shutdown_before": before_ok,
        "shutdown_after": after_ok,
        "SHUTDOWN_EXIT": 0 if after_ok else 1,
        "ethernet_used": False,
        "motion_used": False,
        "lane_mask": "0x3",
        "stage_returncode": None if stage_proc is None else stage_proc.returncode,
        "raw_result": rel(raw_result),
    }
    (EVIDENCE / "p6_ps_runtime_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "summary.md").write_text("\n".join([
        "# P6 PS Driver Runtime", "", f"P6_PS_DRIVER_RUNTIME: {summary['P6_PS_DRIVER_RUNTIME']}",
        f"BITSTREAM_SHA256: {summary['bitstream_sha256']}", f"XSA_SHA256: {summary['xsa_sha256']}",
        f"ELF_SHA256: {summary['elf_sha256']}", "SYNTAX_ONLY: false", f"SHUTDOWN_BEFORE: {before_ok}",
        f"SHUTDOWN_AFTER: {after_ok}", "ETHERNET_USED: false", "MOTION_USED: false", "LANE_MASK: 0x3", "",
    ]), encoding="utf-8")
    print(json.dumps(summary))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
