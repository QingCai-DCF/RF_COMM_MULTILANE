#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from run_p6_jtag_axi_matrix import make_payload, payload_word

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run shutdown-bounded P6 stationary two-lane soak.")
    parser.add_argument("--runtime-sec", type=int, default=7200)
    parser.add_argument("--sample-interval-sec", type=int, default=60)
    parser.add_argument("--min-frames-per-lane", type=int, default=7200)
    parser.add_argument("--evidence-dir", default="evidence/hardware/p6/soak/two_lane_2h_stationary")
    parser.add_argument("--max-runtime-sec", type=int, default=7560)
    args = parser.parse_args()
    if args.runtime_sec < 1 or args.runtime_sec > 7200 or args.max_runtime_sec < args.runtime_sec or args.max_runtime_sec > 7560:
        raise SystemExit("invalid P6 soak runtime boundary")
    evidence = (ROOT / args.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    profile = ROOT / "profiles/p6/p6_two_lane_2h_stationary_soak.json"
    profile_data = json.loads(profile.read_text(encoding="utf-8"))
    lines = ["# Rotating payload set for stationary two-lane physical soak."]
    for length in profile_data["payload_length"]:
        for pattern in profile_data["payload_pattern"]:
            payload = make_payload(pattern, int(length))
            words = [f"0x{payload_word(payload, index):08x}" for index in range((len(payload) + 3) // 4)]
            import zlib
            lines.append(" ".join(["SOAK_CASE", str(len(payload)), f"0x{zlib.crc32(payload) & 0xffffffff:08x}", *words]))
    lines.append(f"SOAK 0x43c00000 {args.runtime_sec} {args.sample_interval_sec} {args.min_frames_per_lane}")
    txn = evidence / "p6_two_lane_soak_transactions.txt"
    raw = evidence / "p6_two_lane_soak_raw_result.log"
    txn.write_text("\n".join(lines) + "\n", encoding="utf-8")
    candidate = json.loads((ROOT / "evidence/generated/vivado/p6_jtag_candidate/p6_jtag_candidate_build_summary.json").read_text(encoding="utf-8"))
    bit = ROOT / candidate["artifacts"]["bit"]["immutable"]
    ltx = ROOT / candidate["artifacts"]["ltx"]["immutable"]
    xdc = ROOT / "constraints/active/PORT1.generated.xdc"
    pinmap = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
    shutdown = ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/hw/run_p6_jtag_axi_stage_safe.ps1",
        "-Stage", "two_lane_2h_stationary_soak" if args.runtime_sec == 7200 else "two_lane_stationary_soak_smoke",
        "-Bitstream", str(bit), "-BitstreamSha256", sha(bit), "-Ltx", str(ltx), "-LtxSha256", sha(ltx),
        "-Profile", str(profile), "-ProfileSha256", sha(profile), "-ActiveXdcSha256", sha(xdc), "-PinmapSha256", sha(pinmap),
        "-ShutdownBitstreamSha256", sha(shutdown), "-TransactionFile", str(txn), "-ResultFile", str(raw),
        "-EvidenceDir", str(evidence), "-LaneCount", "2", "-MaxLaneMask", "0x3", "-MaxRuntimeSec", str(args.max_runtime_sec),
        "-JtagFrequencyHz", "10000000", "-NoEthernet", "-NoMotion", "-ShutdownOnExit",
    ]
    env = os.environ.copy()
    env["RF_COMM_HW_AUTH"] = "P6_LOCAL_TRANSPORT_APPROVED"
    proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    (evidence / "soak_wrapper.stdout.log").write_text(proc.stdout, encoding="utf-8")
    (evidence / "soak_wrapper.stderr.log").write_text(proc.stderr, encoding="utf-8")
    raw_text = raw.read_text(encoding="utf-8", errors="ignore") if raw.exists() else ""
    safe_text = (evidence / "p6_safe_stage_summary.log").read_text(encoding="utf-8", errors="ignore") if (evidence / "p6_safe_stage_summary.log").exists() else ""
    expected_marker = "P6_TWO_LANE_2H_STATIONARY_SOAK=PASS"
    passed = proc.returncode == 0 and expected_marker in raw_text and "P6_SAFE_STAGE_STATUS=PASS" in safe_text
    def raw_value(key: str) -> str:
        for line in raw_text.splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1]
        return "MISSING"
    summary = {
        "P6_TWO_LANE_2H_STATIONARY_SOAK": "PASS" if passed and args.runtime_sec == 7200 else ("PASS_SMOKE" if passed else "FAIL"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requested_runtime_sec": args.runtime_sec,
        "observed_runtime_sec": raw_value("P6_SOAK_ELAPSED_SEC"),
        "sample_interval_sec": args.sample_interval_sec,
        "sample_count": raw_value("P6_SOAK_SAMPLE_COUNT"),
        "case_rotations": raw_value("P6_SOAK_CASE_ROTATIONS"),
        "tx_count": raw_value("P6_SOAK_TX_COUNT"),
        "rx_good_l0": raw_value("P6_SOAK_RX_GOOD_L0"),
        "rx_good_l1": raw_value("P6_SOAK_RX_GOOD_L1"),
        "min_frames_per_lane": args.min_frames_per_lane,
        "bitstream": rel(bit), "bitstream_sha256": sha(bit), "ltx": rel(ltx), "ltx_sha256": sha(ltx),
        "profile": rel(profile), "profile_sha256": sha(profile),
        "hardware_actions_executed": True,
        "shutdown_before": "BEFORE_STAGE_SHUTDOWN_EXIT=0" in safe_text,
        "shutdown_after": "AFTER_STAGE_SHUTDOWN_EXIT=0" in safe_text,
        "ethernet_used": False, "motion_used": False, "lane_mask": "0x3",
        "raw_result": rel(raw),
    }
    (evidence / "p6_two_lane_soak_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (evidence / "summary.md").write_text("\n".join([
        "# P6 Two-Lane Stationary Soak", "", f"P6_TWO_LANE_2H_STATIONARY_SOAK: {summary['P6_TWO_LANE_2H_STATIONARY_SOAK']}",
        f"REQUESTED_RUNTIME_SEC: {args.runtime_sec}", f"OBSERVED_RUNTIME_SEC: {summary['observed_runtime_sec']}",
        f"TX_COUNT: {summary['tx_count']}", f"RX_GOOD_L0: {summary['rx_good_l0']}", f"RX_GOOD_L1: {summary['rx_good_l1']}",
        f"SHUTDOWN_BEFORE: {summary['shutdown_before']}", f"SHUTDOWN_AFTER: {summary['shutdown_after']}",
        "ETHERNET_USED: false", "MOTION_USED: false", "LANE_MASK: 0x3", "",
    ]), encoding="utf-8")
    print(json.dumps(summary))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
