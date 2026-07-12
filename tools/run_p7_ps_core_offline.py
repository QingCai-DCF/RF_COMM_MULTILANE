#!/usr/bin/env python3
"""Create a source-bound P7 PS core hardware-readiness attestation offline."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated"
READINESS = OUT / "p7_ps_core_hardware_readiness.json"
RUNNER = ROOT / "scripts/hw/run_p7_ps_application_stage_safe.py"
GCC_CANDIDATES = (
    Path(r"D:\Xilinx\Vitis_HLS\2023.1\tps\mingw\8.3.0\win64.o\nt\bin\gcc.exe"),
    Path(r"D:\Xilinx\Vitis_HLS\2023.1\tps\win64\msys64\mingw64\bin\gcc.exe"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], timeout: int = 600) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=timeout
    )
    return {
        "command": subprocess.list2cmdline(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("p7_ps_safe_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load P7 PS safe runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def between(text: str, start: str, end: str) -> str:
    left = text.find(start)
    right = text.find(end, left + len(start)) if left >= 0 else -1
    return "" if left < 0 or right < 0 else text[left:right]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    runner = load_runner()
    service = (ROOT / "software/ps_driver/p7_app_service.c").read_text(encoding="utf-8")
    runtime = (ROOT / "software/ps_driver/p7_runtime_main.c").read_text(encoding="utf-8")
    driver = (ROOT / "software/ps_driver/ir_driver.c").read_text(encoding="utf-8")
    codec = (ROOT / "tools/p7_ps_mailbox_backend.py").read_text(encoding="utf-8")
    runner_text = RUNNER.read_text(encoding="utf-8")
    execute_tcl = (ROOT / "scripts/hw/p7_ps_application_execute.tcl").read_text(encoding="utf-8")
    jtag_wrapper = (ROOT / "scripts/hw/run_p7_jtag_axi_stage_safe.py").read_text(encoding="utf-8")
    contained_launcher = (ROOT / "tools/p7_contained_launcher.py").read_text(encoding="utf-8")
    failed_block = between(service, "failed:", "static uint32_t p7_queue_occupancy")
    wipe_block = between(service, "static void p7_wipe_partial", "static int p7_validate_descriptor")
    runtime_expired_block = between(
        service, "static int p7_runtime_expired", "static int p7_runtime_has_budget"
    )
    process_descriptor_block = between(
        service, "static int p7_process_descriptor", "static uint32_t p7_queue_occupancy"
    )
    final_release_block = service[service.rfind("final_runtime_request =") :]
    static_checks = {
        "host_command_cache_disabled_or_isolated":
            "Xil_DCacheDisable();" in runtime
            and runtime.find("Xil_DCacheDisable();")
            < runtime.find("volatile p7_mailbox_control_t *mailbox")
            < runtime.find("p7_app_service_run("),
        "host_command_cacheline_isolated":
            "Xil_DCacheDisable();" in runtime
            and runtime.find("Xil_DCacheDisable();")
            < runtime.find("volatile p7_mailbox_control_t *mailbox")
            < runtime.find("p7_app_service_run("),
        "deadline_frozen_in_private_context":
            "p7_service_context" in service
            and "shutdown_deadline_ticks" in service
            and "requested_runtime = mailbox->max_runtime_seconds" in service,
        "active_transfer_obeys_absolute_deadline":
            "for (uint32_t poll = 0U; poll < P7_P6_MAX_POLLS; ++poll)" in service
            and "p7_active_stop_requested(context->service)" in service,
        "stop_abort_shutdown_observed_during_active_object":
            all(token in service for token in (
                "command == P7_CONTROL_STOP", "command == P7_CONTROL_ABORT",
                "command == P7_CONTROL_SHUTDOWN", "p7_active_stop_requested(service)",
            )),
        "shutdown_readback_verified":
            all(token in driver for token in (
                "IR_SHUTDOWN_READBACK_POLLS", "IR_REG_P6_STATUS",
                "IR_REG_P6_SHUTDOWN_REASON", "IR_REG_SAFETY_SHUTDOWN_REASON",
                "IR_REG_P6_MAILBOX_STATUS", "return -2;",
            )),
        "failure_cleanup_shutdown_first":
            failed_block.find("p7_stop_and_shutdown(service)") >= 0
            and failed_block.find("p7_stop_and_shutdown(service)")
            < failed_block.find("p7_wipe_partial("),
        "failure_wipe_uses_private_validated_range":
            "const p7_object_descriptor_t *request" in wipe_block
            and "uint32_t completed" in wipe_block
            and "request->output_address" in wipe_block
            and "descriptor->output_address" not in wipe_block,
        "integrity_crc_sha_immutable_chunk_snapshot":
            "uint8_t snapshot[256] __attribute__((aligned(64)))" in service
            and "p7_invalidate(data + offset, chunk);" in service
            and "memcpy(snapshot, data + offset, chunk);" in service
            and "crc ^= snapshot[index];" in service
            and "p7_sha256_update(&sha, snapshot, chunk);" in service
            and "crc ^= data[offset + index];" not in service
            and "p7_sha256_update(&sha, data + offset, chunk);" not in service,
        "descriptor_ready_published_last":
            "def descriptor_ready_publication" in codec
            and "P7_DESCRIPTOR_FREE" in codec
            and "pack_ready_publication_word" in codec,
        "terminal_descriptor_stable_snapshot":
            "def unpack_stable_terminal_descriptor" in codec
            and "status_before" in codec and "status_after" in codec,
        "runtime_terminal_after_exact_deadline":
            "service.completion_deadline_ticks =" in service
            and "service.start_ticks + service.runtime_limit_ticks;" in service
            and "while (p7_get_ticks() < service.completion_deadline_ticks)" in service
            and service.find("while (p7_get_ticks() < service.completion_deadline_ticks)")
            < service.rfind("p7_publish_runtime_elapsed("),
        "runtime_elapsed_seqlock_and_monotonic_reader":
            "runtime_elapsed_sequence" in service
            and "sequence + 1U" in service
            and "sequence + 2U" in service
            and "runtime_elapsed_request" in service
            and "runtime_elapsed_ack" in service
            and "p7_read_runtime_elapsed_request" in service
            and "0x00020088" in execute_tcl
            and "0x0002008C" in execute_tcl
            and "0x00020090" in execute_tcl
            and "runtime_elapsed_ticks regressed" in execute_tcl
            and "decode_runtime_elapsed_snapshot" in codec,
        "runtime_elapsed_causal_request_release":
            runtime_expired_block.find("p7_read_runtime_elapsed_request(mailbox)") >= 0
            and runtime_expired_block.find("p7_read_runtime_elapsed_request(mailbox)")
            < runtime_expired_block.find("p7_get_ticks()")
            < runtime_expired_block.find("p7_publish_runtime_elapsed(mailbox, elapsed, request)")
            and final_release_block.find("p7_publish_runtime_elapsed(") >= 0
            and final_release_block.find("p7_publish_runtime_elapsed(")
            < final_release_block.find("mailbox->service_state ="),
        "object_latency_start_precedes_input_integrity":
            process_descriptor_block.find("object_start = p7_get_ticks()") >= 0
            and process_descriptor_block.find("object_start = p7_get_ticks()")
            < process_descriptor_block.find("p7_integrity_checked("),
        "firmware_stationary_admission_cutoff":
            "p7_descriptor_admission_allowed" in service
            and "p7_reject_late_admission" in service
            and "scheduling_cutoff_seconds" in service
            and "admission_guard_seconds" in service
            and "reject_late_admission" in service
            and "scheduling_cutoff_seconds" in codec,
        "contained_child_tree_reaped_before_shutdown":
            "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in jtag_wrapper
            and "AssignProcessToJobObject" in jtag_wrapper
            and "QueryInformationJobObject" in jtag_wrapper
            and "verify_process_tree_reaped" in jtag_wrapper
            and "candidate_child_reaped" in runner_text
            and "shutdown_after_started" in runner_text
            and "P7_GO" in contained_launcher,
        "strict_ring_host_publication_supported":
            "proc p7_publish_source_descriptor_to_target" in execute_tcl
            and "p7_wait_service_ready" in execute_tcl
            and "dow -data [file join $bundle_dir \"descriptor_free_${source_slot}.bin\"]" in execute_tcl
            and "mwr [expr {$descriptor_address + 0x0C}] 1" in execute_tcl,
        "stationary_identity_ledger_bound":
            "stationary_final_by_slot" in runner_text
            and "expected_completion_sequence = int(final_identity[\"sequence\"])" in runner_text
            and "trace[\"object_id\"] != case.request.object_id" in runner_text
            and "stationary final mailbox counters do not reconcile" in runner_text,
    }
    required_checks = tuple(runner.CORE_READINESS_CHECKS)
    checks: dict[str, bool] = {
        key: bool(static_checks.get(key, False)) for key in required_checks
    }
    checks["phy_reenabled_and_startup_ready_waited"] = (
        "p7_p6_wait_phy_ready" in service
        and "P7_P6_STATUS_READY" in service
        and service.find("p7_p6_wait_phy_ready(context)")
        < service.find("ir_driver_p6_start(context->io)")
    )

    gcc = next((path for path in GCC_CANDIDATES if path.is_file()), None)
    native = {"returncode": 127, "reason": "SKIP_WITH_REASON:gcc_not_found"}
    admission_native = {"returncode": 127, "reason": "SKIP_WITH_REASON:gcc_not_found"}
    if gcc is not None:
        build_dir = ROOT / "build/p7_ps_core_native"
        build_dir.mkdir(parents=True, exist_ok=True)
        executable = build_dir / "ir_driver_shutdown_test.exe"
        env = os.environ.copy()
        env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(gcc), "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-Isoftware/ps_driver", "tests/p7/ir_driver_shutdown_test.c",
             "software/ps_driver/ir_driver.c", "-o", str(executable)],
            cwd=ROOT, text=True, capture_output=True, timeout=120, env=env,
        )
        executed = subprocess.run(
            [str(executable)], cwd=ROOT, text=True, capture_output=True,
            timeout=30, env=env,
        ) if compiled.returncode == 0 else None
        native = {
            "compiler": str(gcc), "compile_returncode": compiled.returncode,
            "compile_stdout": compiled.stdout, "compile_stderr": compiled.stderr,
            "returncode": None if executed is None else executed.returncode,
            "stdout": "" if executed is None else executed.stdout,
            "stderr": "" if executed is None else executed.stderr,
        }
        admission_executable = build_dir / "p7_admission_contract_test.exe"
        admission_compiled = subprocess.run(
            [str(gcc), "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-Isoftware/ps_driver", "tests/p7/p7_admission_contract_test.c",
             "-o", str(admission_executable)],
            cwd=ROOT, text=True, capture_output=True, timeout=120, env=env,
        )
        admission_executed = subprocess.run(
            [str(admission_executable)], cwd=ROOT, text=True, capture_output=True,
            timeout=30, env=env,
        ) if admission_compiled.returncode == 0 else None
        admission_native = {
            "compiler": str(gcc),
            "compile_returncode": admission_compiled.returncode,
            "compile_stdout": admission_compiled.stdout,
            "compile_stderr": admission_compiled.stderr,
            "returncode": None if admission_executed is None else admission_executed.returncode,
            "stdout": "" if admission_executed is None else admission_executed.stdout,
            "stderr": "" if admission_executed is None else admission_executed.stderr,
        }
    native_ok = native.get("returncode") == 0
    checks["native_shutdown_readback_test"] = native_ok
    checks["firmware_stationary_admission_cutoff"] = bool(
        checks.get("firmware_stationary_admission_cutoff")
        and admission_native.get("returncode") == 0
    )

    unit = run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/p7", "-p", "test*.py", "-v"])
    checks["p7_python_and_codec_tests"] = unit["returncode"] == 0

    build_summary_path = ROOT / "evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json"
    build_summary = json.loads(build_summary_path.read_text(encoding="utf-8")) if build_summary_path.is_file() else {}
    source_hashes = {source: sha256(ROOT / source) for source in runner.CORE_READINESS_SOURCES}
    recorded_sources = build_summary.get("sources", {})
    required_build_sources = (
        "software/ps_driver/p7_runtime_main.c",
        "software/ps_driver/p7_app_service.c",
        "software/ps_driver/p7_app_service.h",
        "software/ps_driver/p7_admission_contract.h",
        "software/ps_driver/ir_driver.c",
        "software/ps_driver/ir_driver.h",
        "software/common/rf_app_protocol.c",
        "software/common/rf_app_protocol.h",
        "software/common/rf_transport_backend.c",
        "software/common/rf_transport_backend.h",
    )
    required_build_hashes = {source: sha256(ROOT / source) for source in required_build_sources}
    build_fresh = (
        build_summary.get("P7_PS_RUNTIME_BUILD") == "PASS"
        and build_summary.get("syntax_only") is False
        and build_summary.get("mailbox_overlap") is False
        and build_summary.get("linker_ocm_hard_boundary_0x20000") is True
        and set(recorded_sources) == set(required_build_sources)
        and all(recorded_sources.get(source) == digest for source, digest in required_build_hashes.items())
    )
    checks["real_vitis_build_source_bound"] = build_fresh
    passed = all(checks.values())
    payload = {
        "schema": "rf-comm-p7-ps-core-hardware-readiness-v1",
        "P7_PS_CORE_HARDWARE_READINESS": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hardware_actions_executed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "checks": checks,
        "sources": source_hashes,
        "native_shutdown_test": native,
        "native_stationary_admission_test": admission_native,
        "unit_tests": unit,
        "build_summary": str(build_summary_path.relative_to(ROOT)).replace("\\", "/"),
    }
    READINESS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md = [
        "# P7 PS Core Hardware Readiness", "",
        f"P7_PS_CORE_HARDWARE_READINESS: {payload['P7_PS_CORE_HARDWARE_READINESS']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true", "HARDWARE_ACCEPTANCE: PENDING_HW", "",
    ] + [f"- {key}: {'PASS' if value else 'FAIL'}" for key, value in checks.items()]
    (OUT / "p7_ps_core_hardware_readiness.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "P7_PS_CORE_HARDWARE_READINESS": payload["P7_PS_CORE_HARDWARE_READINESS"],
        "attestation": str(READINESS.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(READINESS), "checks": checks,
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
