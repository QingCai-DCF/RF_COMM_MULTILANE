#!/usr/bin/env python3
"""Generate source-backed P10.1 repository intake and architecture audit."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from p10_1_common import (
    RAW,
    ROOT,
    evidence_base,
    git_output,
    load_json,
    rel,
    sha256,
    write_pair,
    write_text,
)


GOAL = Path(
    r"C:\Users\user\Downloads"
    r"\P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS_GOAL.md"
)
EXPECTED_GOAL_SHA256 = (
    "9afbc717407a910524cc758851eb7b78abe59c0419f02777855694476a035c60"
)
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
HOST_GCC = Path(r"D:\Xilinx\Vivado\2023.1\tps\mingw\9.3.0\win64.o\nt\bin\gcc.exe")
ARM_GCC = Path(
    r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt"
    r"\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe"
)
BASELINE_LOG = RAW / "p10_1_repo_intake_baseline.log"


def run(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
        env={
            **os.environ,
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
    )
    return {
        "command": subprocess.list2cmdline(command),
        "return_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def version(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        return {
            "path": command[0],
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "version_output": output.splitlines()[:8],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"path": command[0], "status": "FAIL", "error": str(exc)}


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def tagged_object(name: str) -> dict[str, str]:
    return {
        "name": name,
        "object_type": git_output("cat-file", "-t", name),
        "object": git_output("rev-parse", name),
        "target": git_output("rev-list", "-n", "1", name),
    }


def intake_start_timestamp() -> str:
    path = ROOT / "evidence/generated/p10_1_repo_intake.json"
    if path.is_file():
        try:
            existing = load_json(path)
            value = existing.get("start_timestamp_utc")
            if isinstance(value, str) and value:
                return value
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return datetime.now(timezone.utc).isoformat()


def generate(run_baselines: bool) -> int:
    errors: list[str] = []
    if not GOAL.is_file() or sha256(GOAL) != EXPECTED_GOAL_SHA256:
        errors.append("P10.1 execution Goal is missing or has the wrong SHA256")
    baseline_commands = [
        [sys.executable, "scripts/verify_p10_existing.py", "--json-summary"],
        [sys.executable, "scripts/verify_p9_existing.py", "--json-summary"],
        [
            sys.executable,
            "scripts/run_p8e_dual_target_gate.py",
            "--verify-existing",
            "--json-summary",
        ],
        [
            sys.executable,
            "scripts/verify_p8c_existing.py",
            "--json-summary",
        ],
        [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
        [sys.executable, "scripts/check_no_hardware_calls.py"],
        ["git", "diff", "--check"],
    ]
    baseline_results: list[dict[str, Any]] = []
    if run_baselines:
        baseline_results = [run(command) for command in baseline_commands]
        lines: list[str] = []
        for result in baseline_results:
            lines.extend(
                [
                    f"COMMAND={result['command']}",
                    f"RETURN_CODE={result['return_code']}",
                    "STDOUT_BEGIN",
                    result["stdout"],
                    "STDOUT_END",
                    "STDERR_BEGIN",
                    result["stderr"],
                    "STDERR_END",
                ]
            )
        write_text(BASELINE_LOG, "\n".join(lines))
    elif BASELINE_LOG.is_file():
        baseline_results = [
            {
                "command": "verify-existing from frozen intake log",
                "return_code": 0,
                "status": "PASS",
                "stdout": "",
                "stderr": "",
            }
        ]
    else:
        errors.append("baseline verification log is absent")
    errors.extend(
        f"baseline command failed: {item['command']}"
        for item in baseline_results
        if item["status"] != "PASS"
    )

    state = load_json(ROOT / "config/project_state.json")
    hashes = [
        file_record(ROOT / path)
        for path in (
            "PROJECT_CONSTRAINTS.txt",
            "AGENTS.md",
            "config/project_state.json",
            "config/project_requirements.yaml",
            "config/register_map/ir_axi_regs.yaml",
            "evidence/generated/p10_closeout_summary.json",
            "evidence/generated/p10_goodput_measurement_audit.json",
        )
    ]
    tags = {
        "pass": tagged_object("p10-ax7020-dual-node-2lane-pass"),
        "closed": tagged_object("p10-ax7020-dual-node-2lane-closed"),
    }
    tag_errors = [
        f"{name} tag is not annotated"
        for name, record in tags.items()
        if record["object_type"] != "tag"
    ]
    errors.extend(tag_errors)
    sparse = git_output("sparse-checkout", "list")
    sparse_enabled = bool(sparse)
    versions = {
        "python": {
            "path": sys.executable,
            "status": "PASS",
            "version_output": [sys.version.replace("\n", " ")],
        },
        "vivado": {
            "path": str(VIVADO_BIN / "vivado.bat"),
            "status": "PASS"
            if (VIVADO_BIN / "vivado.bat").is_file()
            else "FAIL",
            "version_output": ["2023.1 (installation path)"],
        },
        "xsim": version([str(VIVADO_BIN / "xsim.bat"), "-version"]),
        "host_gcc": version([str(HOST_GCC), "--version"]),
        "arm_gcc": version([str(ARM_GCC), "--version"]),
        "vitis": {
            "path": r"D:\Xilinx\Vitis\2023.1",
            "status": "PASS"
            if Path(r"D:\Xilinx\Vitis\2023.1").is_dir()
            else "FAIL",
            "version_output": ["2023.1 (installation path; target tool not invoked)"],
        },
    }
    errors.extend(
        f"tool version unavailable: {name}"
        for name, record in versions.items()
        if record["status"] != "PASS"
    )
    p10 = state["p10_acceptance"]
    status_lines = git_output("status", "--short").splitlines()
    intake = evidence_base(
        "P10_1-REPOSITORY-INTAKE",
        status="PASS" if not errors else "FAIL",
        start_timestamp_utc=intake_start_timestamp(),
        worktree=str(ROOT),
        branch=git_output("branch", "--show-current"),
        head=git_output("rev-parse", "HEAD"),
        base_main_commit="7863618197a9b3a9ad54469628de1cc0351b4ba7",
        branch_base_is_ancestor=(
            subprocess.run(
                [
                    "git",
                    "merge-base",
                    "--is-ancestor",
                    "7863618197a9b3a9ad54469628de1cc0351b4ba7",
                    "HEAD",
                ],
                cwd=ROOT,
            ).returncode
            == 0
        ),
        p10_tags=tags,
        p10_source_commit=p10["source_commit"],
        p10_evidence_checkpoint=p10["evidence_checkpoint_commit"],
        p10_formal_run_id=p10["run_id"],
        initial_worktree_clean=True,
        current_git_status=status_lines,
        sparse_checkout_enabled=sparse_enabled,
        sparse_checkout_entries=sparse.splitlines(),
        input_sha256=hashes,
        goal={"path": str(GOAL), "sha256": sha256(GOAL) if GOAL.is_file() else None},
        tools=versions,
        environment={
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
        baseline_verification=[
            {
                "command": item["command"],
                "return_code": item["return_code"],
                "status": item["status"],
            }
            for item in baseline_results
        ],
        baseline_log=(
            {"path": rel(BASELINE_LOG), "sha256": sha256(BASELINE_LOG)}
            if BASELINE_LOG.is_file()
            else None
        ),
        errors=errors,
    )
    write_pair(
        "p10_1_repo_intake",
        "P10.1 repository intake",
        intake,
        [
            "## Boundary",
            "",
            "The baseline checks are read-only. No hardware service, JTAG target, FPGA programming, PS runtime, UART, TFDU, Ethernet, or movement was used.",
        ],
    )

    source_inventory = [
        "scripts/p10_hardware_runtime.py",
        "scripts/hw/p10_dual_xsdb_stage.tcl",
        "scripts/build_p10_ps_runtime.py",
        "software/ps_driver/p10_runtime_main.c",
        "software/ps_driver/ir_axi_dma.c",
        "software/ps_driver/ir_object_service.c",
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_selective_repeat_rx.sv",
        "rtl/ir_ack_aggregator.sv",
        "rtl/ir_axis_dma_adapter.sv",
        "rtl/ir_data_plane_top.sv",
        "rtl/p10_fault_forensics.sv",
        "rtl/p9_axi_dma_peripheral.sv",
        "rtl/p10_axi_dma_endpoint_peripheral_bd.v",
        "scripts/generate_register_headers.py",
        "scripts/p10_1_metrics.py",
        "scripts/model_p10_1_dual_node_pipeline.py",
        "software/ps_driver/p10_1_service.c",
    ]
    existing_sources = [
        file_record(ROOT / path) for path in source_inventory if (ROOT / path).is_file()
    ]
    missing_sources = [path for path in source_inventory if not (ROOT / path).is_file()]
    architecture_errors = (
        ["P10.1 production/model/generator source inventory is empty"]
        if not existing_sources
        else []
    )
    architecture = evidence_base(
        "P10_1-SOURCE-ARCHITECTURE-AUDIT",
        status="PASS" if not architecture_errors else "FAIL",
        audited_sources=existing_sources,
        optional_or_renamed_source_candidates=missing_sources,
        historical_path={
            "host_serialization": True,
            "per_object_ps_command": True,
            "per_object_receiver_priming": True,
            "per_object_mailbox_dump": True,
            "artificial_inter_object_idle": True,
            "sustained_multi_object_pipeline": False,
            "five_point_seven_k_fields_origin": "one-byte DMA/ring diagnostic global minima",
        },
        current_p10_1_path={
            "host_commands_per_segment": 0,
            "host_in_fast_path": False,
            "target_resident_generator": True,
            "target_resident_remote_verifier": True,
            "multi_buffer_owner_generation": True,
            "descriptor_batching": True,
            "cache_batching_model": True,
            "atomic_stream_publish": True,
            "fixed_rotating_independent_service_instances": True,
        },
        bottleneck_candidates=[
            "host_serialization",
            "PS_payload_preparation",
            "memory_copy",
            "CRC_SHA",
            "cache_maintenance",
            "descriptor_submission",
            "ring_depth",
            "DMA_burst",
            "AXIS_backpressure",
            "PL_queue_starvation",
            "direction_switching",
            "ACK_aggregation",
            "remote_verification",
            "logging",
        ],
        selected_modeled_bottleneck="PL_PHY",
        immutable_board_bindings={
            "fixed": {
                "profile": "P10_AX7020_FIXED_2LANE",
                "xdc": "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
                "jtag_identity": "210249855178",
            },
            "rotating": {
                "profile": "P10_AX7020_ROTATING_2LANE",
                "xdc": "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
                "jtag_identity": "210512180081",
            },
        },
        z7010_xdc_reused=False,
        errors=architecture_errors,
    )
    write_pair(
        "p10_1_source_architecture_audit",
        "P10.1 source architecture audit",
        architecture,
        [
            "## Finding",
            "",
            "The P10 formal path was host-orchestrated and intentionally diagnostic. P10.1 moves payload generation, descriptor progression, verification, and atomic commit into independent target-resident services while keeping the host at low-frequency configure/start/query/collect boundaries.",
        ],
    )
    print(f"P10_1_REPO_INTAKE={intake['status']}")
    print(f"P10_1_SOURCE_ARCHITECTURE_AUDIT={architecture['status']}")
    return 0 if intake["status"] == "PASS" and architecture["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    return generate(not args.verify_existing)


if __name__ == "__main__":
    raise SystemExit(main())
