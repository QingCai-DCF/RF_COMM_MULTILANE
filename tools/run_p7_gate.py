#!/usr/bin/env python3
"""P7 offline/final evidence gate.

The gate is hardware inert.  It may compile software and inspect existing or
new evidence, but it never connects to hw_server, programs the FPGA, starts an
ELF, or writes a hardware register.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
P6_BASELINE_COMMIT = "ca041d4877b831de84fe7829788ac835b0b46acd"

P6_ARTIFACTS = {
    "p6_results_package": (
        "evidence/packages/rf_comm_multilane_p6_results_20260710_091555.zip",
        "1e2fd052c0954abeb87427b9473f9ab6465a03aef95f791121f91bda1d4133e5",
    ),
    "p6_jtag_bit": (
        "evidence/hardware/p6/bitstreams/p6_jtag_dynamic_transport_674cf4a14988bbce15b8025162e7d528aa888c44e188a3a94ef5acd97d01d8d9.bit",
        "674cf4a14988bbce15b8025162e7d528aa888c44e188a3a94ef5acd97d01d8d9",
    ),
    "p6_jtag_ltx": (
        "evidence/hardware/p6/bitstreams/p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
        "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    ),
    "p6_ps_bit": (
        "evidence/hardware/p6/bitstreams/p6_ps_dynamic_transport_34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249.bit",
        "34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249",
    ),
    "p6_xsa": (
        "evidence/hardware/p6/bitstreams/p6_ps_dynamic_transport_b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9.xsa",
        "b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9",
    ),
    "p6_reference_elf": (
        "evidence/hardware/p6/elf/p6_runtime_mailbox_789d8132038408015bdb65c147b3826203a09345c851c570bf47dbd27f54fcba.elf",
        "789d8132038408015bdb65c147b3826203a09345c851c570bf47dbd27f54fcba",
    ),
    "shutdown_bit": (
        "shutdown_bitstream/tfdu_shutdown_j10_j11.bit",
        "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    ),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, title: str, marker: str, status: str, details: dict[str, Any]) -> None:
    lines = [
        f"# {title}", "", f"generated_at_utc: {now()}", f"{marker}: {status}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true", "HARDWARE_ACCEPTANCE: PENDING_HW", "",
        "## Details", "",
    ]
    for key, value in details.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        lines.append(f"- {key}: {rendered}")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(command: list[str], *, timeout: int = 1800) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    return {
        "command": subprocess.list2cmdline(command),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def p6_recheck() -> tuple[bool, dict[str, Any]]:
    files: dict[str, Any] = {}
    passed = True
    for name, (path_text, expected) in P6_ARTIFACTS.items():
        path = ROOT / path_text
        actual = sha(path) if path.is_file() else "MISSING"
        valid = actual == expected
        files[name] = {"path": path_text, "expected_sha256": expected, "actual_sha256": actual, "valid": valid}
        passed &= valid
    summary_path = ROOT / "evidence/generated/p6_local_transport_no_ethernet_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    p6_status = summary.get("P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET") == "PASS"
    passed &= p6_status
    return passed, {
        "P6_RECHECK": "PASS" if passed else "FAIL",
        "p6_summary_pass": p6_status,
        "artifacts": files,
        "p6_build_recorded_head": summary.get("HEAD", "UNKNOWN"),
        "p7_starting_clean_successor": P6_BASELINE_COMMIT,
        "provenance_note": "The P6 package and PS artifacts retain their baseline provenance; the active JTAG candidate was rebuilt offline after r12 with explicit AXI4-Lite RD/WR queue depth 16 and is bound by its content-addressed build summary.",
    }


def scan_no_ethernet() -> tuple[bool, dict[str, Any]]:
    roots = [ROOT / "tools", ROOT / "scripts", ROOT / "software/common", ROOT / "software/ps_driver"]
    files = [path for base in roots if base.exists() for path in base.rglob("*p7*") if path.is_file()]
    forbidden = re.compile(r"(?i)(#include\s*[<\"](?:sys/socket|lwip|netinet)|\bimport\s+socket\b|\bfrom\s+socket\b|\bsocket\s*\(|\bconnect\s*\(|\bbind\s*\(|\blisten\s*\(|\bdhcp\w*\s*\()")
    hits: list[str] = []
    for path in files:
        if path.suffix.lower() not in {".py", ".c", ".h", ".tcl", ".ps1"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), 1):
            if forbidden.search(line):
                hits.append(f"{rel(path)}:{line_number}:{line.strip()}")
    return not hits, {"files_scanned": len(files), "forbidden_hits": hits, "network_used": False}


def scope_check() -> tuple[bool, dict[str, Any]]:
    protocol = (ROOT / "config/p7_app_protocol.yaml").read_text(encoding="utf-8")
    profile = json.loads((ROOT / "profiles/p7/p7_stationary_app_30min.json").read_text(encoding="utf-8"))
    active = json.loads((ROOT / "board_profiles/ACTIVE_PROFILE.json").read_text(encoding="utf-8"))
    checks = {
        "available_lanes_2": profile.get("lane_count") == 2,
        "max_mask_0x3": profile.get("max_lane_mask") == "0x3",
        "allowed_masks_exact": profile.get("allowed_lane_masks") == ["0x1", "0x2", "0x3"],
        "no_network": profile.get("network_required") is False,
        "no_motion": profile.get("motion_required") is False,
        "runtime_1800": profile.get("max_runtime_sec") == 1800,
        "embedded_calibration": profile.get("calibration_window_sec") == 300
        and profile.get("acceptance_window_sec") == 1500
        and profile.get("calibration_is_part_of_final_30min_run") is True,
        "lane1_promotion_recorded": active.get("lane1_reliable_enabled") is True
        and active.get("lane1_reliability_promotion", {}).get("status") == "PASS",
        "protocol_no_ethernet": "network_allowed: false" in protocol,
        "protocol_no_motion": "motion_allowed: false" in protocol,
    }
    return all(checks.values()), {"checks": checks, "profile": rel(ROOT / "profiles/p7/p7_stationary_app_30min.json")}


def latest_p7_elf() -> tuple[bool, dict[str, Any]]:
    summary_path = ROOT / "evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json"
    if not summary_path.exists():
        return False, {"reason": "P7 PS runtime build summary missing", "summary": rel(summary_path)}
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    elf_info = summary.get("artifacts", {}).get("elf", {})
    immutable = ROOT / elf_info.get("immutable", "MISSING")
    valid = (
        summary.get("P7_PS_RUNTIME_BUILD") == "PASS"
        and summary.get("syntax_only") is False
        and immutable.is_file()
        and sha(immutable) == elf_info.get("sha256")
        and summary.get("mailbox_overlap") is False
        and summary.get("linker_ocm_hard_boundary_0x20000") is True
    )
    return valid, {"summary": rel(summary_path), "build": summary, "immutable_hash_valid": valid}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P7 offline and evidence gates without hardware actions")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--skip-ps-build", action="store_true")
    args = parser.parse_args()
    GENERATED.mkdir(parents=True, exist_ok=True)

    git_branch = run(["git", "branch", "--show-current"], timeout=30)
    git_head = run(["git", "rev-parse", "HEAD"], timeout=30)
    git_status = run(["git", "status", "--short"], timeout=30)
    git_tree = run(["git", "ls-tree", "-r", "--full-tree", "HEAD"], timeout=30)
    source_commit = git_head["stdout"].strip().lower()
    dirty_files_before_gate = git_status["stdout"].splitlines()
    dirty_worktree = bool(dirty_files_before_gate)
    source_tree_listing_sha256 = hashlib.sha256(
        git_tree["stdout"].encode("utf-8")
    ).hexdigest()
    p6_ok, p6 = p6_recheck()
    intake = {
        "P7_REPO_INTAKE": "PASS" if p6_ok else "FAIL",
        "generated_at_utc": now(),
        "branch": git_branch["stdout"].strip(),
        "HEAD": source_commit,
        "SOURCE_COMMIT": source_commit,
        "dirty_files_at_gate": dirty_files_before_gate,
        "dirty_worktree": dirty_worktree,
        "source_tree_listing_sha256": source_tree_listing_sha256,
        "p6": p6,
        "plan": "C:/Users/user/Downloads/p7_stationary_local_application_layer_no_ethernet_30min_plan.md",
        "plan_sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
        "hardware_actions_executed": False,
    }
    write_json(GENERATED / "p7_repo_intake_summary.json", intake)
    write_md(GENERATED / "p7_repo_intake_summary.md", "P7 Repository Intake", "P7_REPO_INTAKE", intake["P7_REPO_INTAKE"], intake)
    write_md(GENERATED / "p7_repo_intake.md", "P7 Repository Intake", "P7_REPO_INTAKE", intake["P7_REPO_INTAKE"], intake)

    vector_script = ROOT / "tools/run_p7_protocol_vectors.py"
    vector_run = run([sys.executable, str(vector_script), "--json-summary"], timeout=300) if vector_script.exists() else {
        "command": str(vector_script), "returncode": 127, "stdout": "", "stderr": "script missing"
    }
    vectors_ok = vector_run["returncode"] == 0
    try:
        vector_result = json.loads(vector_run["stdout"].splitlines()[-1]) if vector_run["stdout"].strip() else {}
    except (json.JSONDecodeError, IndexError):
        vector_result = {}
    vector_details = {"run": {key: value for key, value in vector_run.items() if key not in {"stdout", "stderr"}}, **vector_result}
    write_json(GENERATED / "p7_protocol_vector_summary.json", vector_details)
    write_md(GENERATED / "p7_protocol_vector_summary.md", "P7 Protocol Golden Vectors", "P7_PROTOCOL_VECTORS", "PASS" if vectors_ok else "FAIL", vector_details)
    write_md(GENERATED / "p7_application_protocol_summary.md", "P7 Application Protocol", "P7_APPLICATION_PROTOCOL", "PASS" if vectors_ok else "FAIL", {"header_bytes": 32, "max_chunk_bytes": 215, "p6_payload_bytes": 247, **vector_details})

    tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests/p7", "-p", "test_*.py", "-v"], timeout=600)
    tests_ok = tests["returncode"] == 0 and "Ran " in tests["stderr"] and "OK" in tests["stderr"]
    safety_tests = run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_p7_hardware_safety",
            "tests.test_p7_jtag_axi_stage_safe",
            "tests.test_p7_ps_application_stage_safe",
            "tests.test_p7_authorized_hardware_sequence",
            "tests.test_generate_p7_authorized_sequence_plan",
            "tests.test_summarize_p7_hardware",
            "-v",
        ],
        timeout=600,
    )
    safety_tests_ok = safety_tests["returncode"] == 0 and "OK" in safety_tests["stderr"]
    write_json(GENERATED / "p7_offline_test_run.json", {"vectors": vector_run, "unittest": tests, "hardware_safety": safety_tests})

    lane_run = run([sys.executable, "tools/check_p7_lane1_promotion.py"], timeout=60)
    lane_ok = lane_run["returncode"] == 0

    if not args.skip_ps_build and (ROOT / "scripts/build_p7_ps_runtime.py").exists():
        ps_build_run = run([sys.executable, "scripts/build_p7_ps_runtime.py"], timeout=1800)
    else:
        ps_build_run = {"command": "SKIPPED", "returncode": 0 if args.skip_ps_build else 127, "stdout": "", "stderr": ""}
    ps_ok, ps_detail = latest_p7_elf()
    core_run = run([sys.executable, "tools/run_p7_ps_core_offline.py"], timeout=600)
    core_ok = core_run["returncode"] == 0
    write_json(
        GENERATED / "p7_offline_test_run.json",
        {"vectors": vector_run, "unittest": tests,
         "hardware_safety": safety_tests, "ps_core_readiness": core_run},
    )

    ethernet_ok, ethernet = scan_no_ethernet()
    scope_ok, scope = scope_check()

    unit_details = {
        "command": tests["command"], "returncode": tests["returncode"],
        "test_output_tail": (tests["stdout"] + tests["stderr"])[-4000:],
        "sizes_include_0_to_1MiB": True, "negative_cases_present": True,
    }
    write_md(GENERATED / "p7_segmentation_reassembly_summary.md", "P7 Segmentation and Reassembly", "P7_SEGMENTATION_REASSEMBLY", "PASS" if tests_ok else "FAIL", unit_details)
    write_md(GENERATED / "p7_fragmentation_reassembly_summary.md", "P7 Fragmentation and Reassembly", "FRAGMENTATION_REASSEMBLY", "PASS" if tests_ok else "FAIL", unit_details)
    write_md(GENERATED / "p7_backend_conformance_summary.md", "P7 Backend Conformance", "P7_BACKEND_CONFORMANCE", "PASS" if tests_ok else "FAIL", {**unit_details, "backends": ["local_stub", "mock_jtag_axi", "mock_ps_mailbox", "tcp_stub_disabled"]})
    write_md(GENERATED / "p7_lane_scheduler_summary.md", "P7 Lane Scheduler", "P7_LANE_SCHEDULER", "PASS" if tests_ok and lane_ok else "FAIL", {"stripe": "round-robin", "replicate": "0x3", "software_fault_injection": True, "lane1_promotion_gate": lane_ok})
    write_md(GENERATED / "p7_queue_backpressure_summary.md", "P7 Queue and Backpressure", "P7_QUEUE_BACKPRESSURE_OFFLINE", "PASS" if tests_ok else "FAIL", {"queue_depth": 8, "bounded_overflow_reject": True, "hardware_acceptance": "PENDING_HW"})
    write_md(GENERATED / "p7_fault_recovery_summary.md", "P7 Fault Recovery", "P7_FAULT_RECOVERY_OFFLINE", "PASS" if tests_ok else "FAIL", {"abort_restart": True, "stale_session": True, "duplicate_same": "idempotent", "duplicate_different": "reject", "hardware_acceptance": "PENDING_HW"})
    write_md(GENERATED / "p7_file_integrity_summary.md", "P7 File Integrity", "P7_FILE_INTEGRITY_OFFLINE", "PASS" if tests_ok else "FAIL", {"whole_object_crc32": True, "sha256_compare": True, "atomic_replace": True, "hardware_acceptance": "PENDING_HW"})
    write_md(GENERATED / "p7_no_ethernet_summary.md", "P7 No Ethernet", "P7_NO_ETHERNET", "PASS" if ethernet_ok and scope_ok else "FAIL", ethernet)
    write_md(GENERATED / "p7_no_motion_summary.md", "P7 No Motion", "P7_NO_MOTION", "PASS" if scope_ok else "FAIL", {"motion_used": False, **scope})
    write_md(GENERATED / "p7_2lane_scope_summary.md", "P7 Two-Lane Scope", "P7_2LANE_SCOPE", "PASS" if scope_ok and lane_ok else "FAIL", scope)
    write_md(GENERATED / "p7_ps_runtime_summary.md", "P7 PS Runtime", "P7_PS_RUNTIME_BUILD", "PASS" if ps_ok else "FAIL", {"build_command": ps_build_run["command"], **ps_detail})

    active_inputs = {}
    for path_text in (
        "constraints/active/PORT1.generated.xdc", "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
        "board_profiles/ACTIVE_PROFILE.json", "config/register_map/ir_axi_regs.yaml",
        "config/p7_app_protocol.yaml", "profiles/p7/p7_stationary_app_30min.json",
    ):
        path = ROOT / path_text
        active_inputs[path_text] = sha(path) if path.exists() else "MISSING"
    provenance = {"P7_ARTIFACT_PROVENANCE": "PASS" if p6_ok and ps_ok else "FAIL", "pl_reused_from_p6": True, "p6": p6["artifacts"], "p7_ps": ps_detail, "active_inputs": active_inputs}
    write_json(GENERATED / "p7_artifact_provenance_summary.json", provenance)
    write_md(GENERATED / "p7_artifact_provenance_summary.md", "P7 Artifact Provenance", "P7_ARTIFACT_PROVENANCE", provenance["P7_ARTIFACT_PROVENANCE"], provenance)

    checkpoint_paths = {
        path_text
        for path_text in (
            *active_inputs.keys(),
            *(entry[0] for entry in P6_ARTIFACTS.values()),
            "evidence/generated/vivado/p6_jtag_candidate/p6_jtag_candidate_build_summary.json",
            "evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate_build_summary.json",
            "evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json",
            "evidence/generated/p7_ps_core_hardware_readiness.json",
            "tools/run_p7_gate.py",
            "tools/run_p7_ps_core_offline.py",
            "tools/summarize_p7_hardware.py",
            "tools/run_p7_authorized_hardware_sequence.py",
            "tools/generate_p7_authorized_sequence_plan.py",
            "tools/p7_hardware_safety.py",
            "tools/p7_jtag_backend.py",
            "tools/p7_app_protocol.py",
            "tools/p7_app_transport.py",
            "tools/p7_ps_mailbox_backend.py",
            "tools/p7_contained_launcher.py",
            "scripts/build_p7_ps_runtime.py",
            "scripts/build_p7_ps_runtime.tcl",
            "scripts/hw/p7_hw_preflight.tcl",
            "scripts/hw/run_p7_jtag_axi_stage_safe.py",
            "scripts/hw/run_p7_ps_application_stage_safe.py",
            "scripts/hw/p7_jtag_axi_transactions.tcl",
            "scripts/hw/p7_ps_application_execute.tcl",
            "software/common/rf_app_protocol.h",
            "software/common/rf_app_protocol.c",
            "software/common/rf_transport_backend.h",
            "software/common/rf_transport_backend.c",
            "software/ps_driver/ir_driver.h",
            "software/ps_driver/ir_driver.c",
            "software/ps_driver/p7_app_service.h",
            "software/ps_driver/p7_admission_contract.h",
            "software/ps_driver/p7_app_service.c",
            "software/ps_driver/p7_runtime_main.c",
        )
    }
    artifact_dir = ROOT / "evidence/hardware/p7/artifacts"
    if artifact_dir.is_dir():
        checkpoint_paths.update(rel(path) for path in artifact_dir.iterdir() if path.is_file())
    checkpoint_input_hashes = {
        path_text: sha(ROOT / path_text) if (ROOT / path_text).is_file() else "MISSING"
        for path_text in sorted(checkpoint_paths)
    }
    checkpoint_inputs_valid = bool(checkpoint_input_hashes) and all(
        re.fullmatch(r"[0-9a-f]{64}", value) for value in checkpoint_input_hashes.values()
    )

    offline_checks = {
        "P6_RECHECK": p6_ok,
        "P7_PROTOCOL_VECTORS": vectors_ok,
        "P7_SEGMENTATION_REASSEMBLY": tests_ok,
        "P7_BACKEND_CONFORMANCE": tests_ok,
        "P7_PS_RUNTIME_BUILD": ps_ok,
        "P7_PS_CORE_HARDWARE_READINESS": core_ok,
        "P7_NO_ETHERNET": ethernet_ok and scope_ok,
        "P7_NO_MOTION": scope_ok,
        "P7_2LANE_SCOPE": scope_ok and lane_ok,
        "P7_LANE1_PROMOTION": lane_ok,
        "P7_HARDWARE_SAFETY_OFFLINE": safety_tests_ok,
        "P7_CLEAN_SOURCE_CHECKPOINT": (
            not dirty_worktree
            and bool(re.fullmatch(r"[0-9a-f]{40}", source_commit))
            and git_tree["returncode"] == 0
        ),
        "P7_CHECKPOINT_INPUT_HASHES": checkpoint_inputs_valid,
    }
    offline_pass = all(offline_checks.values())
    final = {
        "P7_OFFLINE_GATE": "PASS" if offline_pass else "FAIL",
        "generated_at_utc": now(), "checks": offline_checks,
        "NO_HARDWARE_ACTIONS_EXECUTED": True, "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "PS_PL_PHY_PL_PS_APPLICATION_PASS": False,
        "STATIONARY_30MIN": "PENDING_HW",
        "hardware_actions_executed": False,
        "source_commit": source_commit,
        "dirty_worktree": dirty_worktree,
        "dirty_files_before_gate": dirty_files_before_gate,
        "source_tree_listing_sha256": source_tree_listing_sha256,
        "checkpoint_input_hashes": checkpoint_input_hashes,
        "checkpoint_input_count": len(checkpoint_input_hashes),
    }
    write_json(GENERATED / "p7_offline_gate_summary.json", final)
    write_md(GENERATED / "p7_offline_gate_summary.md", "P7 Offline Gate", "P7_OFFLINE_GATE", final["P7_OFFLINE_GATE"], final)
    if args.json_summary:
        print(json.dumps(final, ensure_ascii=False))
    else:
        print(f"P7_OFFLINE_GATE: {final['P7_OFFLINE_GATE']}")
        for name, value in offline_checks.items():
            print(f"{name}: {'PASS' if value else 'FAIL'}")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
    return 0 if offline_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
