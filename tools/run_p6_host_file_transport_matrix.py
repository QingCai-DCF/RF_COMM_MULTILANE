#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from p6_jtag_axi_transport import parse_key_values, unpack_word
from run_p6_jtag_axi_matrix import build_case

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/hardware/p6/host_file_transport_jtag"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    inputs = sorted((EVIDENCE / "input_payloads").glob("*.bin"))
    if {path.name for path in inputs} != {"small_text.bin", "counter_247.bin", "prbs_247.bin", "random_seeded_247.bin"}:
        raise SystemExit("P6 host input payload set is incomplete")
    lines = ["# P6 file-to-file local JTAG/AXI transport; no Ethernet."]
    cases: list[tuple[str, Path, bytes]] = []
    for index, input_path in enumerate(inputs):
        payload = input_path.read_bytes()
        prefix = f"FILE{index}_{input_path.stem.upper()}"
        build_case(lines, prefix, payload, 3, 0x43C00000)
        cases.append((prefix, input_path, payload))
    txn = EVIDENCE / "p6_host_file_matrix_transactions.txt"
    raw = EVIDENCE / "p6_host_file_matrix_raw_result.log"
    txn.write_text("\n".join(lines) + "\n", encoding="utf-8")
    candidate = json.loads((ROOT / "evidence/generated/vivado/p6_jtag_candidate/p6_jtag_candidate_build_summary.json").read_text(encoding="utf-8"))
    bit = ROOT / candidate["artifacts"]["bit"]["immutable"]
    ltx = ROOT / candidate["artifacts"]["ltx"]["immutable"]
    profile = ROOT / "profiles/p6/p6_host_file_transport_jtag.json"
    xdc = ROOT / "constraints/active/PORT1.generated.xdc"
    pinmap = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
    shutdown = ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/hw/run_p6_jtag_axi_stage_safe.ps1",
        "-Stage", "host_file_transport_jtag", "-Bitstream", str(bit), "-BitstreamSha256", sha(bit),
        "-Ltx", str(ltx), "-LtxSha256", sha(ltx), "-Profile", str(profile), "-ProfileSha256", sha(profile),
        "-ActiveXdcSha256", sha(xdc), "-PinmapSha256", sha(pinmap), "-ShutdownBitstreamSha256", sha(shutdown),
        "-TransactionFile", str(txn), "-ResultFile", str(raw), "-EvidenceDir", str(EVIDENCE),
        "-LaneCount", "2", "-MaxLaneMask", "0x3", "-MaxRuntimeSec", "1200", "-JtagFrequencyHz", "10000000",
        "-NoEthernet", "-NoMotion", "-ShutdownOnExit",
    ]
    env = os.environ.copy()
    env["RF_COMM_HW_AUTH"] = "P6_LOCAL_TRANSPORT_APPROVED"
    proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    (EVIDENCE / "host_matrix_wrapper.stdout.log").write_text(proc.stdout, encoding="utf-8")
    (EVIDENCE / "host_matrix_wrapper.stderr.log").write_text(proc.stderr, encoding="utf-8")
    raw_values = parse_key_values(raw) if raw.exists() else {}
    safe = (EVIDENCE / "p6_safe_stage_summary.log").read_text(encoding="utf-8", errors="ignore") if (EVIDENCE / "p6_safe_stage_summary.log").exists() else ""
    stage_pass = proc.returncode == 0 and raw_values.get("P6_JTAG_AXI_TRANSACTIONS") == "PASS" and "P6_SAFE_STAGE_STATUS=PASS" in safe
    rows = []
    all_match = stage_pass
    outputs = EVIDENCE / "output_payloads"
    outputs.mkdir(exist_ok=True)
    for prefix, input_path, expected in cases:
        observed = bytearray(len(expected))
        for word_index in range((len(expected) + 3) // 4):
            value = int(raw_values.get(f"{prefix}_RXW{word_index}", 0))
            unpack_word(value, len(expected), word_index, observed)
        output_path = outputs / input_path.name
        output_path.write_bytes(observed)
        match = bytes(observed) == expected
        all_match = all_match and match
        rows.append({
            "input_file": rel(input_path), "output_file": rel(output_path), "bytes": len(expected),
            "input_sha256": sha(input_path), "output_sha256": sha(output_path), "match": match,
        })
    csv_path = EVIDENCE / "p6_host_file_transport_jtag.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "P6_HOST_FILE_TRANSPORT_JTAG": "PASS" if all_match else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_tested": len(rows), "all_input_output_files_match": all_match, "files": rows,
        "bitstream": rel(bit), "bitstream_sha256": sha(bit), "ltx": rel(ltx), "ltx_sha256": sha(ltx),
        "profile": rel(profile), "profile_sha256": sha(profile), "csv": rel(csv_path),
        "hardware_actions_executed": True, "script_hardware_actions_executed": True,
        "shutdown_before": "BEFORE_STAGE_SHUTDOWN_EXIT=0" in safe,
        "shutdown_after": "AFTER_STAGE_SHUTDOWN_EXIT=0" in safe,
        "shutdown_on_exit": "AFTER_STAGE_SHUTDOWN_EXIT=0" in safe,
        "ethernet_used": False, "motion_used": False, "lane_mask": "0x3",
    }
    (EVIDENCE / "p6_jtag_axi_transport_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
