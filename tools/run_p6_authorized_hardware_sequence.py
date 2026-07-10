#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES = ROOT / "evidence/hardware/p6/failures"


def failure_package(stage: str, command: list[str], proc: subprocess.CompletedProcess[str]) -> None:
    FAILURES.mkdir(parents=True, exist_ok=True)
    stem = FAILURES / f"{stage}_runtime_failure_package"
    payload = {
        "P6_HARDWARE_SEQUENCE_STAGE": "FAIL",
        "stage": stage,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-8000:],
        "shutdown_contract": "child stage is required to complete shutdown-before/after in its safe wrapper",
        "next_suggested_fix": f"inspect evidence/hardware/p6/{stage} safe-stage logs and repair the first failing assertion",
    }
    stem.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text("\n".join([
        "# P6 Hardware Sequence Failure Package", "", "P6_HARDWARE_SEQUENCE_STAGE: FAIL",
        f"stage: {stage}", f"returncode: {proc.returncode}",
        "shutdown contract: child safe wrapper must contain shutdown-before/after evidence", "",
    ]), encoding="utf-8")
    with zipfile.ZipFile(stem.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(stem.with_suffix(".json"), stem.with_suffix(".json").name)
        archive.write(stem.with_suffix(".md"), stem.with_suffix(".md").name)


def main() -> int:
    parser = argparse.ArgumentParser(description="P6 shutdown-bounded no-Ethernet/no-motion hardware sequence.")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--no-ethernet", action="store_true")
    parser.add_argument("--no-motion", action="store_true")
    parser.add_argument("--lane-count", type=int, default=2)
    parser.add_argument("--max-lane-mask", default="0x3")
    parser.add_argument("--include-2h-soak", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    if args.execute_hardware:
        if not args.no_ethernet or not args.no_motion or args.lane_count != 2 or int(args.max_lane_mask, 0) != 3:
            raise SystemExit("hardware execution requires --no-ethernet --no-motion --lane-count 2 --max-lane-mask 0x3")
        if os.environ.get("RF_COMM_HW_AUTH") != "P6_LOCAL_TRANSPORT_APPROVED":
            raise SystemExit("RF_COMM_HW_AUTH=P6_LOCAL_TRANSPORT_APPROVED required")
        if not args.include_2h_soak:
            raise SystemExit("full P6 execution requires --include-2h-soak; a short soak cannot be promoted")

    py = sys.executable
    commands: list[tuple[str, list[str]]] = [
        ("idle_rechecks", [py, "tools/run_p6_jtag_axi_idle_stages.py"]),
        ("jtag_axi_payload_ram_smoke", [py, "tools/p6_jtag_axi_transport.py", "--backend", "jtag-axi", "--allow-live-jtag", "--no-start", "--input-file", "evidence/hardware/p6/host_file_transport_jtag/input_payloads/counter_247.bin", "--output-file", "evidence/hardware/p6/jtag_axi_payload_ram_smoke/smoke_output.bin", "--lane-mask", "0x3", "--ack-lane-mask", "0x3", "--profile", "profiles/p6/p6_jtag_axi_payload_ram_smoke.json", "--evidence-dir", "evidence/hardware/p6/jtag_axi_payload_ram_smoke", "--max-runtime-sec", "300"]),
        ("lane0_dynamic_payload", [py, "tools/run_p6_jtag_axi_matrix.py", "--lane-mask", "0x1", "--profile", "profiles/p6/p6_lane0_dynamic_payload_256.json", "--evidence-dir", "evidence/hardware/p6/protocol/lane0_dynamic_payload", "--stage-name", "lane0_dynamic_payload", "--max-runtime-sec", "900"]),
        ("lane1_dynamic_payload", [py, "tools/run_p6_jtag_axi_matrix.py", "--lane-mask", "0x2", "--profile", "profiles/p6/p6_lane1_dynamic_payload_256.json", "--evidence-dir", "evidence/hardware/p6/protocol/lane1_dynamic_payload", "--stage-name", "lane1_dynamic_payload", "--max-runtime-sec", "900"]),
        ("two_lane_dynamic_payload", [py, "tools/run_p6_jtag_axi_matrix.py", "--lane-mask", "0x3", "--profile", "profiles/p6/p6_two_lane_dynamic_payload_256.json", "--evidence-dir", "evidence/hardware/p6/protocol/two_lane_dynamic_payload", "--stage-name", "two_lane_dynamic_payload", "--max-runtime-sec", "1200"]),
        ("ps_driver_runtime", [py, "tools/run_p6_ps_runtime_safe.py"]),
        ("host_file_transport_jtag", [py, "tools/run_p6_host_file_transport_matrix.py"]),
        ("lane_fallback_regression", [py, "tools/run_p6_jtag_axi_matrix.py", "--lane-mask", "0x3", "--profile", "profiles/p6/p6_lane_fallback_regression.json", "--evidence-dir", "evidence/hardware/p6/lane_fallback_regression", "--stage-name", "lane_fallback_regression", "--include-negative", "--max-runtime-sec", "900"]),
        ("two_lane_2h_stationary_soak", [py, "tools/run_p6_two_lane_soak.py", "--runtime-sec", "7200", "--sample-interval-sec", "60", "--min-frames-per-lane", "7200", "--max-runtime-sec", "7560"]),
    ]
    if not args.execute_hardware:
        summary = {
            "P6_AUTHORIZED_HARDWARE_SEQUENCE": "DRY_RUN_PASS",
            "hardware_actions_executed": False,
            "no_ethernet": True,
            "no_motion": True,
            "lane_count": 2,
            "max_lane_mask": "0x3",
            "stages": [{"stage": stage, "command": command} for stage, command in commands],
        }
        summary_path = ROOT / "evidence/generated/p6_authorized_hardware_sequence_dry_run_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False) if args.json_summary else "P6_AUTHORIZED_HARDWARE_SEQUENCE: DRY_RUN_PASS")
        return 0

    env = os.environ.copy()
    for stage, command in commands:
        proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        if proc.returncode != 0:
            failure_package(stage, command, proc)
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            return proc.returncode or 1
    summary = {"P6_AUTHORIZED_HARDWARE_SEQUENCE": "PASS", "hardware_actions_executed": True, "stages": [stage for stage, _ in commands]}
    print(json.dumps(summary) if args.json_summary else "P6_AUTHORIZED_HARDWARE_SEQUENCE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
