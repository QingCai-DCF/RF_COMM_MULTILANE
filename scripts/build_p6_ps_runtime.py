#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XSCT = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsct.bat")
OUT = ROOT / "evidence/generated/vitis/p6_ps_runtime"

# --allow-hardware scanner marker: XSCT is used here only as an offline
# compiler/platform generator.  This script has no connect/program/run target
# operation; actual hardware execution is isolated in the authorized wrapper.


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ps_summary = json.loads((ROOT / "evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate_build_summary.json").read_text(encoding="utf-8"))
    xsa = ROOT / ps_summary["artifacts"]["xsa"]["immutable"]
    proc = subprocess.run(
        [str(XSCT), "scripts/build_p6_ps_runtime.tcl", str(ROOT), str(xsa)],
        cwd=ROOT, text=True, capture_output=True, timeout=1800,
    )
    (OUT / "p6_ps_runtime_build.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    built = ROOT / "build/p6_ps_vitis_workspace/p6_runtime/Debug/p6_runtime.elf"
    passed = proc.returncode == 0 and built.exists() and "P6_PS_RUNTIME_BUILD=PASS" in proc.stdout
    artifacts = {}
    if built.exists():
        digest = sha(built)
        immutable = ROOT / f"evidence/hardware/p6/elf/p6_runtime_mailbox_{digest}.elf"
        immutable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, immutable)
        artifacts["elf"] = {"source": rel(built), "sha256": digest, "immutable": rel(immutable)}
    summary = {
        "P6_PS_RUNTIME_BUILD": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "returncode": proc.returncode,
        "xsa": rel(xsa),
        "xsa_sha256": sha(xsa),
        "mailbox_base": "0x00020000",
        "artifacts": artifacts,
        "syntax_only": False,
    }
    (OUT / "p6_ps_runtime_build_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
