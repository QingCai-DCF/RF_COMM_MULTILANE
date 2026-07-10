#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def execute(stage: str, profile_name: str, evidence_name: str, lines: list[str]) -> bool:
    evidence = ROOT / f"evidence/hardware/p6/{evidence_name}"
    evidence.mkdir(parents=True, exist_ok=True)
    txn = evidence / "p6_idle_transactions.txt"
    raw = evidence / "p6_idle_raw_result.log"
    txn.write_text("\n".join(lines) + "\n", encoding="utf-8")
    candidate = json.loads((ROOT / "evidence/generated/vivado/p6_jtag_candidate/p6_jtag_candidate_build_summary.json").read_text(encoding="utf-8"))
    bit = ROOT / candidate["artifacts"]["bit"]["immutable"]
    ltx = ROOT / candidate["artifacts"]["ltx"]["immutable"]
    profile = ROOT / f"profiles/p6/{profile_name}"
    xdc = ROOT / "constraints/active/PORT1.generated.xdc"
    pinmap = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
    shutdown = ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/hw/run_p6_jtag_axi_stage_safe.ps1",
        "-Stage", stage, "-Bitstream", str(bit), "-BitstreamSha256", sha(bit), "-Ltx", str(ltx), "-LtxSha256", sha(ltx),
        "-Profile", str(profile), "-ProfileSha256", sha(profile), "-ActiveXdcSha256", sha(xdc), "-PinmapSha256", sha(pinmap),
        "-ShutdownBitstreamSha256", sha(shutdown), "-TransactionFile", str(txn), "-ResultFile", str(raw),
        "-EvidenceDir", str(evidence), "-LaneCount", "2", "-MaxLaneMask", "0x3", "-MaxRuntimeSec", "120",
        "-JtagFrequencyHz", "10000000", "-NoEthernet", "-NoMotion", "-ShutdownOnExit",
    ]
    env = os.environ.copy()
    env["RF_COMM_HW_AUTH"] = "P6_LOCAL_TRANSPORT_APPROVED"
    proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    (evidence / "idle_wrapper.stdout.log").write_text(proc.stdout, encoding="utf-8")
    (evidence / "idle_wrapper.stderr.log").write_text(proc.stderr, encoding="utf-8")
    safe = (evidence / "p6_safe_stage_summary.log").read_text(encoding="utf-8", errors="ignore") if (evidence / "p6_safe_stage_summary.log").exists() else ""
    raw_text = raw.read_text(encoding="utf-8", errors="ignore") if raw.exists() else ""
    passed = proc.returncode == 0 and "P6_JTAG_AXI_TRANSACTIONS=PASS" in raw_text and "P6_SAFE_STAGE_STATUS=PASS" in safe
    marker = "P6_SAFE_IDLE_RECHECK" if stage == "safe_idle_recheck" else "P6_TFDU_CONTROL_IDLE_RECHECK"
    summary = {
        marker: "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bitstream": rel(bit), "bitstream_sha256": sha(bit), "profile": rel(profile), "profile_sha256": sha(profile),
        "hardware_actions_executed": True, "shutdown_before": "BEFORE_STAGE_SHUTDOWN_EXIT=0" in safe,
        "shutdown_after": "AFTER_STAGE_SHUTDOWN_EXIT=0" in safe, "ethernet_used": False, "motion_used": False,
        "raw_result": rel(raw),
    }
    (evidence / "p6_stage_result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (evidence / "summary.md").write_text("\n".join([
        f"# {marker}", "", f"{marker}: {summary[marker]}", f"BITSTREAM_SHA256: {sha(bit)}",
        f"SHUTDOWN_BEFORE: {summary['shutdown_before']}", f"SHUTDOWN_AFTER: {summary['shutdown_after']}",
        "ETHERNET_USED: false", "MOTION_USED: false", "",
    ]), encoding="utf-8")
    return passed


def main() -> int:
    base = 0x43C00000
    a = lambda offset: f"0x{base + offset:08x}"
    safe_lines = [
        "# P6 candidate reset-safe observation; no PHY enable and no TX.",
        f"ASSERT {a(0x104)} 0x000000ff 0x00000000 SAFE_STATUS_RESET",
        f"ASSERT {a(0x12c)} 0xffffffff 0x00000000 SAFE_TX_COUNT",
        f"ASSERT {a(0x14c)} 0xffffffff 0x00000000 SAFE_TXD_HIGH",
        f"ASSERT {a(0x150)} 0xffffffff 0x00000000 SAFE_DUTY",
        "WAIT 100",
        f"ASSERT {a(0x104)} 0x000000ff 0x00000000 SAFE_STATUS_STABLE",
    ]
    active_lines = [
        "# Enable both TFDU receivers through a valid commit, but never start TX.",
        f"W {a(0x100)} 0x00000001", f"W {a(0x200)} 0x000000a5",
        f"W {a(0x108)} 0x00002201", f"W {a(0x10c)} 0x00000003", f"W {a(0x110)} 0x00000003",
        f"W {a(0x114)} 0x00000001", f"W {a(0x15c)} 0x0061a800", f"W {a(0x100)} 0x00000004",
        f"POLL {a(0x104)} 0x00000004 0x00000004 2000 ACTIVE_COMMITTED", "WAIT 10",
        f"ASSERT {a(0x104)} 0x000000ff 0x00000007 ACTIVE_READY_IDLE",
        f"ASSERT {a(0x12c)} 0xffffffff 0x00000000 ACTIVE_TX_COUNT",
        f"ASSERT {a(0x080)} 0xffffffff 0x00000000 ACTIVE_TX_PULSES",
        f"ASSERT {a(0x14c)} 0xffffffff 0x00000000 ACTIVE_TXD_HIGH",
        f"ASSERT {a(0x150)} 0xffffffff 0x00000000 ACTIVE_DUTY",
        f"W {a(0x100)} 0x00000030",
    ]
    safe_pass = execute("safe_idle_recheck", "p6_safe_idle_recheck.json", "safe_idle_recheck", safe_lines)
    active_pass = execute("tfdu_control_idle_recheck", "p6_tfdu_control_idle_recheck.json", "tfdu_control_idle_recheck", active_lines)
    print(json.dumps({"P6_SAFE_IDLE_RECHECK": "PASS" if safe_pass else "FAIL", "P6_TFDU_CONTROL_IDLE_RECHECK": "PASS" if active_pass else "FAIL"}))
    return 0 if safe_pass and active_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
