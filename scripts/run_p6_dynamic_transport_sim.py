#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XILINX = Path(r"D:\Xilinx\Vivado\2023.1\bin")
OUT = ROOT / "evidence/simulation/p6/dynamic_payload_engine"
BUILD = ROOT / "build/p6_dynamic_transport_sim"


def run_test(name: str, sources: list[str], markers: list[str]) -> dict[str, object]:
    work = BUILD / name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    logs = OUT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    commands = [
        ([str(XILINX / "xvlog.bat"), "-sv", *[str(ROOT / source) for source in sources]], "xvlog"),
        ([str(XILINX / "xelab.bat"), name, "-s", f"{name}_sim"], "xelab"),
        ([str(XILINX / "xsim.bat"), f"{name}_sim", "-runall"], "xsim"),
    ]
    combined = ""
    returncodes: dict[str, int] = {}
    for command, phase in commands:
        proc = subprocess.run(command, cwd=work, text=True, capture_output=True, timeout=900)
        text = proc.stdout + "\n" + proc.stderr
        (logs / f"{name}.{phase}.log").write_text(text, encoding="utf-8")
        returncodes[phase] = proc.returncode
        combined += text
        if proc.returncode != 0:
            break
    passed = all(returncodes.get(phase) == 0 for phase in ("xvlog", "xelab", "xsim")) and all(marker in combined for marker in markers)
    return {"name": name, "result": "PASS" if passed else "FAIL", "returncodes": returncodes, "markers": markers}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tests = [
        run_test(
            "tb_p6_dynamic_transport_engine",
            ["rtl/tfdu_lane_phy.sv", "rtl/ir_4ppm_codec.sv", "rtl/p6_dynamic_transport_engine.sv", "sim/tb/tb_p6_dynamic_transport_engine.sv"],
            ["TB_P6_DYNAMIC_ENGINE_POSITIVE_CASES=480", "TB_P6_DYNAMIC_ENGINE_PASS=1"],
        ),
        run_test(
            "tb_p6_local_transport_regs_integration",
            ["rtl/p6_local_transport_regs.sv", "sim/tb/tb_p6_local_transport_regs_integration.sv"],
            ["TB_P6_REGS_NEGATIVE_CASES=3", "TB_P6_REGS_INTEGRATION_PASS=1"],
        ),
    ]
    passed = all(test["result"] == "PASS" for test in tests)
    pre_candidate_log = ROOT / "build/p6_dynamic_sim/xsim.log"
    pre_candidate_copy = OUT / "logs/tb_p6_dynamic_transport_engine.pre_candidate.xsim.log"
    pre_candidate_pass = False
    pre_candidate_timestamp = "MISSING"
    if pre_candidate_log.exists():
        pre_text = pre_candidate_log.read_text(encoding="utf-8", errors="ignore")
        pre_candidate_pass = "TB_P6_DYNAMIC_ENGINE_POSITIVE_CASES=480" in pre_text and "TB_P6_DYNAMIC_ENGINE_PASS=1" in pre_text
        shutil.copy2(pre_candidate_log, pre_candidate_copy)
        pre_candidate_timestamp = datetime.fromtimestamp(pre_candidate_log.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    candidate_summary = ROOT / "evidence/generated/vivado/p6_jtag_candidate/p6_jtag_candidate_build_summary.json"
    candidate_data = json.loads(candidate_summary.read_text(encoding="utf-8")) if candidate_summary.exists() else {}
    summary = {
        "P6_DYNAMIC_PAYLOAD_SIM": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "positive_cases": 480,
        "negative_cases": 3,
        "payload_lengths": [1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 191, 247],
        "patterns": ["zeros", "ones", "0xAA", "0x55", "counter", "walking_one", "walking_zero", "prbs7", "prbs15", "deterministic_random"],
        "lane_masks": ["0x1", "0x2", "0x3"],
        "negative_coverage": ["session mismatch", "ack mask mismatch", "lane mask >0x3 rejected"],
        "tests": tests,
        "pre_candidate_physical_engine_gate": {
            "result": "PASS" if pre_candidate_pass else "MISSING",
            "timestamp_utc": pre_candidate_timestamp,
            "log": "evidence/simulation/p6/dynamic_payload_engine/logs/tb_p6_dynamic_transport_engine.pre_candidate.xsim.log",
            "log_sha256": hashlib.sha256(pre_candidate_copy.read_bytes()).hexdigest() if pre_candidate_copy.exists() else "MISSING",
            "candidate_build_timestamp_utc": candidate_data.get("generated_at_utc", "MISSING"),
        },
        "hardware_acceptance": "PENDING_HW",
    }
    (OUT / "p6_dynamic_transport_sim_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT / "summary.md").write_text("\n".join([
        "# P6 Dynamic Transport Simulation", "", f"P6_DYNAMIC_PAYLOAD_SIM: {summary['P6_DYNAMIC_PAYLOAD_SIM']}",
        "POSITIVE_CASES: 480", "NEGATIVE_CASES: 3", "LANE_MASKS: 0x1,0x2,0x3",
        "HARDWARE_ACCEPTANCE: PENDING_HW", "",
    ]), encoding="utf-8")
    print(json.dumps(summary))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
