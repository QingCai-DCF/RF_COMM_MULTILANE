#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated/vivado/p6_ps_candidate"
IMMUTABLE = ROOT / "evidence/hardware/p6/bitstreams"
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    IMMUTABLE.mkdir(parents=True, exist_ok=True)
    log = OUT / "p6_ps_candidate_build.log"
    proc = subprocess.run(
        [str(VIVADO), "-mode", "batch", "-source", "scripts/build_p6_ps_candidate.tcl", "-tclargs", str(ROOT)],
        cwd=ROOT, text=True, capture_output=True, timeout=3600,
    )
    log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    bit = OUT / "p6_ps_candidate.bit"
    xsa = OUT / "p6_ps_candidate.xsa"
    timing = (OUT / "post_route_timing_summary_p6_ps_candidate.rpt").read_text(encoding="utf-8", errors="ignore") if (OUT / "post_route_timing_summary_p6_ps_candidate.rpt").exists() else ""
    drc = (OUT / "post_route_drc_p6_ps_candidate.rpt").read_text(encoding="utf-8", errors="ignore") if (OUT / "post_route_drc_p6_ps_candidate.rpt").exists() else ""
    timing_met = "All user specified timing constraints are met" in timing
    drc_clean = not bool(re.search(r"^\s*ERROR(?:\s|:)", drc, re.MULTILINE | re.IGNORECASE))
    passed = proc.returncode == 0 and bit.exists() and xsa.exists() and timing_met and drc_clean
    artifacts = {}
    for kind, source in (("bit", bit), ("xsa", xsa)):
        if source.exists():
            sha = digest(source)
            immutable = IMMUTABLE / f"p6_ps_dynamic_transport_{sha}.{source.suffix.lstrip('.')}"
            shutil.copy2(source, immutable)
            artifacts[kind] = {"source": rel(source), "sha256": sha, "immutable": rel(immutable)}
    summary = {
        "P6_PS_CANDIDATE_BUILD": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "returncode": proc.returncode,
        "timing_met": timing_met,
        "drc_clean": drc_clean,
        "artifacts": artifacts,
        "inputs": {
            "active_xdc": {
                "path": "constraints/active/PORT1.generated.xdc",
                "sha256": digest(ROOT / "constraints/active/PORT1.generated.xdc"),
            },
            "pinmap": {
                "path": "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
                "sha256": digest(ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"),
            },
            "active_profile": {
                "path": "board_profiles/ACTIVE_PROFILE.json",
                "sha256": digest(ROOT / "board_profiles/ACTIVE_PROFILE.json"),
            },
            "register_map": {
                "path": "config/register_map/ir_axi_regs.yaml",
                "sha256": digest(ROOT / "config/register_map/ir_axi_regs.yaml"),
            },
        },
        "axi_base": "0x43c00000",
        "ethernet_used": False,
        "motion_used": False,
    }
    (OUT / "p6_ps_candidate_build_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
