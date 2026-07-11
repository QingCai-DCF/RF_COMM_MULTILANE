#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
OUT = ROOT / "evidence/generated/vivado/p6_jtag_candidate"
IMMUTABLE = ROOT / "evidence/hardware/p6/bitstreams"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    IMMUTABLE.mkdir(parents=True, exist_ok=True)
    cmd = [str(VIVADO), "-mode", "batch", "-source", "scripts/build_p6_jtag_candidate.tcl", "-tclargs", str(ROOT)]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    (OUT / "build_stdout.log").write_text(proc.stdout, encoding="utf-8", errors="ignore")
    (OUT / "build_stderr.log").write_text(proc.stderr, encoding="utf-8", errors="ignore")
    bit = OUT / "p6_jtag_candidate.bit"
    ltx = OUT / "p6_jtag_candidate.ltx"
    timing_report = OUT / "post_route_timing_summary_p6_jtag_candidate.rpt"
    drc_report = OUT / "post_route_drc_p6_jtag_candidate.rpt"
    timing_text = timing_report.read_text(encoding="utf-8", errors="ignore") if timing_report.exists() else ""
    drc_text = drc_report.read_text(encoding="utf-8", errors="ignore") if drc_report.exists() else ""
    timing_met = "All user specified timing constraints are met." in timing_text
    drc_clean = drc_report.exists() and "| Error" not in drc_text
    result = "PASS" if proc.returncode == 0 and bit.exists() and ltx.exists() and timing_met and drc_clean else "FAIL"
    artifacts: dict[str, dict[str, str]] = {}
    for kind, path in (("bit", bit), ("ltx", ltx)):
        if path.exists():
            digest = sha256(path)
            immutable = IMMUTABLE / f"p6_jtag_dynamic_transport_{digest}.{kind}"
            shutil.copy2(path, immutable)
            artifacts[kind] = {
                "source": path.relative_to(ROOT).as_posix(),
                "sha256": digest,
                "immutable": immutable.relative_to(ROOT).as_posix(),
            }
    inputs = {}
    for name, relpath in {
        "active_xdc": "constraints/active/PORT1.generated.xdc",
        "pinmap": "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
        "active_profile": "board_profiles/ACTIVE_PROFILE.json",
        "register_map": "config/register_map/ir_axi_regs.yaml",
        "build_python": "scripts/build_p6_jtag_candidate.py",
        "build_tcl": "scripts/build_p6_jtag_candidate.tcl",
    }.items():
        path = ROOT / relpath
        inputs[name] = {"path": relpath, "sha256": sha256(path)}
    summary = {
        "P6_JTAG_CANDIDATE_BUILD": result,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vivado": str(VIVADO),
        "returncode": proc.returncode,
        "timing_met": timing_met,
        "drc_clean": drc_clean,
        "artifacts": artifacts,
        "inputs": inputs,
        "live_jtag_axi_ingress": True,
        "dynamic_payload_physical_engine": True,
        "ethernet_used": False,
        "motion_used": False,
        "max_lane_mask": "0x3",
        "jtag_axi_config": {
            "protocol": "AXI4",
            "read_transaction_queue_length": 16,
            "write_transaction_queue_length": 16,
            "maximum_incr_burst_words": 64,
            "downstream_protocol": "AXI4-Lite",
            "protocol_converter": "xilinx.com:ip:axi_protocol_converter",
        },
    }
    (OUT / "p6_jtag_candidate_build_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
