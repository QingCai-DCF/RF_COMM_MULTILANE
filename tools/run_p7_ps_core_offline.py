#!/usr/bin/env python3
"""Create a source-bound P7 PS core hardware-readiness attestation offline."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from p7_regression_evidence import (
    required_suite_commands,
    validate_regression_summary,
)

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


def resolve_unit_test_evidence(
    args: argparse.Namespace, source_commit: str
) -> tuple[dict[str, Any], bool, dict[str, Any] | None]:
    supplied = bool(
        args.validated_regression_summary
        or args.validated_regression_summary_sha256
    )
    if supplied:
        if not args.validated_regression_summary or not re.fullmatch(
            r"[0-9a-fA-F]{64}", args.validated_regression_summary_sha256
        ):
            validated = False
            record: dict[str, Any] = {
                "errors": [
                    "both validated regression summary path and SHA256 are required"
                ]
            }
        else:
            validated, record = validate_regression_summary(
                Path(args.validated_regression_summary),
                args.validated_regression_summary_sha256,
                source_commit,
            )
        p7_suite: dict[str, Any] | None = None
        payload = record.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("suites"), list):
            p7_suite = next(
                (
                    item
                    for item in payload["suites"]
                    if isinstance(item, dict)
                    and item.get("name") == "tests_p7_discovery"
                ),
                None,
            )
        unit = {
            "command": "VALIDATED_COMPLETE_SUITE:tests_p7_discovery",
            "returncode": 0 if validated else 1,
            "stdout": "",
            "stderr": "" if validated else "; ".join(record.get("errors", [])),
            "evidence_mode": "VALIDATED_REUSE_NO_TEST_INVOCATION",
            "invocation_count_in_core_gate": 0,
            "original_suite": p7_suite,
            "validated_complete_regression_summary": record,
        }
        return unit, validated, record

    command = required_suite_commands()["tests_p7_discovery"]
    unit = run(command)
    match = re.search(r"Ran (\d+) tests? in ", unit["stderr"])
    passed = bool(
        unit["returncode"] == 0
        and match is not None
        and int(match.group(1)) >= 1
        and re.search(r"^OK$", unit["stderr"], re.MULTILINE) is not None
    )
    unit.update(
        {
            "evidence_mode": "DIRECT_TEST_INVOCATION",
            "invocation_count_in_core_gate": 1,
            "discovered_test_count": int(match.group(1)) if match else None,
        }
    )
    return unit, passed, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validated-regression-summary", default="")
    parser.add_argument("--validated-regression-summary-sha256", default="")
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    git_head = run(["git", "rev-parse", "HEAD"], timeout=30)
    source_commit = git_head["stdout"].strip().lower()
    runner = load_runner()
    service = (ROOT / "software/ps_driver/p7_app_service.c").read_text(encoding="utf-8")
    service_header = (ROOT / "software/ps_driver/p7_app_service.h").read_text(encoding="utf-8")
    stage62_diagnostic = (
        ROOT / "software/ps_driver/p7_stage62_diagnostic.c"
    ).read_text(encoding="utf-8")
    stage62_microtest = (
        ROOT / "software/ps_driver/p7_stage62_microtest.c"
    ).read_text(encoding="utf-8")
    stage62_microtest_header = (
        ROOT / "software/ps_driver/p7_stage62_microtest.h"
    ).read_text(encoding="utf-8")
    runtime = (ROOT / "software/ps_driver/p7_runtime_main.c").read_text(encoding="utf-8")
    driver = (ROOT / "software/ps_driver/ir_driver.c").read_text(encoding="utf-8")
    codec = (ROOT / "tools/p7_ps_mailbox_backend.py").read_text(encoding="utf-8")
    runner_text = RUNNER.read_text(encoding="utf-8")
    execute_tcl = (ROOT / "scripts/hw/p7_ps_application_execute.tcl").read_text(encoding="utf-8")
    build_tcl = (ROOT / "scripts/build_p7_ps_runtime.tcl").read_text(encoding="utf-8")
    jtag_wrapper = (ROOT / "scripts/hw/run_p7_jtag_axi_stage_safe.py").read_text(encoding="utf-8")
    contained_launcher = (ROOT / "tools/p7_contained_launcher.py").read_text(encoding="utf-8")
    failed_block = between(service, "failed:", "static uint32_t p7_queue_occupancy")
    wipe_block = between(service, "static void p7_wipe_partial", "static int p7_validate_descriptor")
    validate_descriptor_block = between(
        service, "static int p7_validate_descriptor", "static void p7_record_trace"
    )
    runtime_expired_block = between(
        service, "static int p7_runtime_expired", "static int p7_runtime_has_budget"
    )
    process_descriptor_block = between(
        service, "static int p7_process_descriptor", "static uint32_t p7_queue_occupancy"
    )
    publish_prepared_block = between(
        service,
        "static uint32_t p7_publish_prepared_diagnostic(",
        "static uint32_t p7_publish_first_error_diagnostic(",
    )
    copy_diagnostic_block = between(
        service,
        "static int p7_copy_output_with_diagnostic(",
        "static int p7_p6_open(",
    )
    prepare_diagnostic_block = between(
        service,
        "static int p7_prepare_diagnostic_common(",
        "static void p7_hash_diagnostic_snapshots(",
    )
    validation_reject_block = between(
        process_descriptor_block,
        "error = p7_validate_descriptor",
        "service->shutdown_attempted = 0U",
    )
    final_release_block = service[service.rfind("final_runtime_request =") :]
    microtest_execute_block = between(
        execute_tcl[execute_tcl.find("rst -processor") :],
        'if {$mode eq "stage62-microtest"} {',
        '} else {\n  set host_input_start_ms',
    )
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
            and "descriptor->output_address" not in wipe_block
            and "memset(output, 0, request->object_length)" in wipe_block
            and "uint32_t *private_output_validated" in validate_descriptor_block
            and "*private_output_validated = 0U;" in validate_descriptor_block
            and validate_descriptor_block.rfind("return P7_ERROR_TRACE_RANGE;")
            < validate_descriptor_block.find("*private_output_validated = 1U;")
            < validate_descriptor_block.find("return P7_ERROR_STALE_SESSION;")
            and "&private_output_validated" in validation_reject_block
            and "if (private_output_validated != 0U)" in validation_reject_block
            and "p7_wipe_partial(&request, 0U, descriptor)" in validation_reject_block
            and validation_reject_block.find("p7_stop_and_shutdown(service)")
            < validation_reject_block.find("p7_wipe_partial(&request, 0U, descriptor)")
            < validation_reject_block.find("p7_publish_descriptor("),
        "integrity_crc_sha_immutable_chunk_snapshot":
            "uint8_t snapshot[256] __attribute__((aligned(64)))" in service
            and "p7_invalidate(data + offset, chunk);" in service
            and "memcpy(snapshot, data + offset, chunk);" in service
            and "crc ^= snapshot[index];" in service
            and "p7_sha256_update(&sha, snapshot, chunk);" in service
            and "crc ^= data[offset + index];" not in service
            and "p7_sha256_update(&sha, data + offset, chunk);" not in service,
        "critical_payload_copies_are_volatile_byte_verified":
            "static __attribute__((noinline)) int p7_copy_bytes_verified(" in service
            and "static __attribute__((noinline)) int p7_bytes_equal_volatile(" in service
            and "destination[index] = source[index];" in service
            and "uint32_t expected_byte = source[index];" in service
            and "uint32_t actual_byte = destination[index];" in service
            and "if (actual_byte != expected_byte)" in service
            and "p7_mismatch_observation_t" in service
            and "observation->offset = index;" in service
            and "observation->expected_byte = expected_byte;" in service
            and "uint32_t expected_byte = P7_DIAGNOSTIC_MISSING_BYTE" in service
            and "diagnostic->expected_byte = expected_byte;" in service
            and "absolute_index == observed_offset" in service
            and "P7_ERROR_FRAGMENT_ENCODE_COPY" in service
            and "P7_ERROR_FRAGMENT_TRANSFER_COPY" in service
            and "P7_ERROR_OUTPUT_COPY" in service
            and "encoded + RF_APP_HEADER_BYTES" in process_descriptor_block
            and "p7_bytes_equal_volatile(" in process_descriptor_block
            and "request.output_address +" in process_descriptor_block
            and "memcmp(received, encoded, encoded_size)" not in process_descriptor_block
            and "memcpy((void *)(uintptr_t)(request.output_address" not in process_descriptor_block,
        "first_error_diagnostic_is_atomic_and_first_only":
            "P7_FIRST_ERROR_DIAGNOSTIC_MAGIC" in service_header
            and "sizeof(p7_first_error_diagnostic_t) ==" in service
            and "P7_FIRST_ERROR_DIAGNOSTIC_TOTAL_BYTES" in service
            and "if (Xil_In32(address) != 0U)" in service
            and publish_prepared_block.find("p7_flush(diagnostic")
            < publish_prepared_block.find(
                "diagnostic->record_crc32 = p7_stage62_record_crc32("
            )
            < publish_prepared_block.find(
                "diagnostic->magic = P7_FIRST_ERROR_DIAGNOSTIC_MAGIC"
            )
            < publish_prepared_block.find("magic_readback = Xil_In32(address)")
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_FIRST_ERROR_DIAGNOSTIC_CAPTURED=1" in execute_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_FIRST_ERROR_DIAGNOSTIC_WIPED=1" in execute_tcl,
        "stage62_first_error_prepare_is_first_only":
            prepare_diagnostic_block.find(
                "if (Xil_In32(P7_FAILURE_SNAPSHOT_BASEADDR) != 0U) return 0;"
            )
            < prepare_diagnostic_block.find("p7_zero_diagnostic_record();")
            and prepare_diagnostic_block.find(
                "if (Xil_In32(P7_FAILURE_SNAPSHOT_BASEADDR) != 0U) return 0;"
            )
            >= 0,
        "first_error_capture_precedes_validation_and_is_input_bound":
            "set diagnostic_capture_bytes 1536" in execute_tcl
            and "p7_atomic_dump $failure_snapshot $failure_snapshot_address" in execute_tcl
            and "p7_zero_words_and_verify $failure_snapshot_address" in execute_tcl
            and execute_tcl.find("p7_atomic_dump $failure_snapshot $failure_snapshot_address")
            < execute_tcl.find("p7_zero_words_and_verify $failure_snapshot_address")
            < execute_tcl.find("P7 failure diagnostic firmware rejected publication")
            < execute_tcl.find("P7 first-error diagnostic identity/geometry validation failed")
            and "set diagnostic_data [p7_read_binary_exact $failure_snapshot" in execute_tcl
            and "set diagnostic_marker [p7_le32 $diagnostic_data 0]" in execute_tcl
            and "from p7_app_protocol import segment_object" in runner_text
            and "first-error diagnostic expected SHA256 is not input-reference bound" in runner_text
            and "first-error diagnostic expected snapshot is not input-reference bound" in runner_text,
        "stage62_diagnostic_fixed_ocm_section":
            'section(".p7_stage62_diagnostic")' in service
            and "offsetof(p7_first_error_diagnostic_t, source_before)" in service
            and "p7_stage62_diag : ORIGIN = 0x21000, LENGTH = 0x1000" in build_tcl
            and ".p7_stage62_diagnostic (NOLOAD)" in build_tcl
            and "SIZEOF(.p7_stage62_diagnostic) == 1536" in build_tcl,
        "stage62_copy_four_snapshot_classification":
            "p7_copy_output_with_diagnostic(" in process_descriptor_block
            and all(
                token in copy_diagnostic_block
                for token in (
                    "diagnostic->source_before",
                    "diagnostic->source_after",
                    "diagnostic->destination_before",
                    "diagnostic->destination_after",
                    "p7_stage62_classify_copy_observation(",
                    "P7_COPY_DIAGNOSTIC_CANARY_PRECHECK_FAILED",
                    "P7_ERROR_OUTPUT_CANARY_PRECHECK",
                )
            )
            and "P7_COPY_DIAGNOSTIC_DEST_PARTIAL_WRITE"
            in stage62_diagnostic
            and "P7_COPY_DIAGNOSTIC_READBACK_VISIBILITY_SUSPECT"
            in stage62_diagnostic,
        "stage62_diagnostic_crc_publish_order":
            "p7_stage62_record_crc32(" in publish_prepared_block
            and publish_prepared_block.find("p7_flush(diagnostic")
            < publish_prepared_block.find("p7_stage62_record_crc32(")
            < publish_prepared_block.find(
                "diagnostic->magic = P7_FIRST_ERROR_DIAGNOSTIC_MAGIC"
            )
            and "record CRC32 is invalid" in codec,
        "stage62_only_microtest_bypasses_pl_and_is_disassembly_bound":
            runtime.find("Xil_DCacheDisable();")
            < runtime.find("p7_stage62_microtest_try_run()")
            < runtime.find("p7_mmio_context_t context")
            < runtime.find("p7_app_service_run(")
            and "void __attribute__((noinline)) p7_stage62_microtest_copy_bytes("
            in stage62_microtest
            and "volatile uint8_t *destination" in stage62_microtest
            and "const volatile uint8_t *source" in stage62_microtest
            and "destination[index] = value;" in stage62_microtest
            and "dsb();" in stage62_microtest
            and "p7_publish_record(record)" in stage62_microtest
            and stage62_microtest.find("p7_publish_record(record)")
            < stage62_microtest.find("p7_zero_volatile(destination_target")
            and "valid_control != 0U && destination_target != NULL"
            in stage62_microtest
            and "P7_STAGE62_MICROTEST_CONTROL_ADDRESS UINT32_C(0x00022300)"
            in stage62_microtest_header
            and "P7_STAGE62_MICROTEST_DDR_DESTINATION_ADDRESS UINT32_C(0x00900000)"
            in stage62_microtest_header
            and "software/ps_driver/p7_stage62_microtest.c" in build_tcl
            and "software/ps_driver/p7_stage62_microtest.h" in build_tcl
            and "stage62_microtest_record_zero.bin" in microtest_execute_block
            and "P7_STAGE62_MICROTEST_PRESTART_READBACK=PASS"
            in microtest_execute_block
            and "stage62_microtest_record_result.bin" in microtest_execute_block
            and "P7_STAGE62_MICROTEST_STAGE62_EXECUTED=0"
            in microtest_execute_block
            and "p7_wait_service_ready" not in microtest_execute_block
            and "mwr 0x0002000C" not in microtest_execute_block
            and "0x43C00000" not in microtest_execute_block
            and "--stage62-only" in runner_text
            and '("P7_EXECUTION_SCOPE", "STAGE62_ONLY")' in runner_text,
        "pre_repair_encode_raw_compared_to_fixed_input_reference":
            "P7_INPUT_REFERENCE_BASEADDR" in service_header
            and "P7_FIRST_ERROR_STAGE_INPUT_REF" in process_descriptor_block
            and "P7_FIRST_ERROR_STAGE_ENCODE_RAW" in process_descriptor_block
            and "P7_FIRST_ERROR_STAGE_ENCODE_REPAIR" in process_descriptor_block
            and process_descriptor_block.find("P7_FIRST_ERROR_STAGE_ENCODE_RAW")
            < process_descriptor_block.find("P7_FIRST_ERROR_STAGE_ENCODE_REPAIR"),
        "p6_tx_mmio_readback_and_rx_boundaries_observed":
            "ir_driver_p6_read_tx_payload(" in driver
            and "P7_FIRST_ERROR_STAGE_P6_TX_LOCAL" in service
            and "P7_FIRST_ERROR_STAGE_P6_TX_MMIO_READBACK" in service
            and "P7_FIRST_ERROR_STAGE_P6_RX_LOCAL" in service
            and "P7_FIRST_ERROR_STAGE_RECEIVED" in service,
        "local_payload_buffers_are_64_byte_aligned":
            "uint8_t tx_payload[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)))" in service
            and "uint8_t rx_payload[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)))" in service
            and "uint8_t encoded[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)))" in service
            and "uint8_t received[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)))" in service
            and "_Alignof(p7_p6_backend_context_t) >= P7_DDR_ALIGNMENT" in service
            and "offsetof(p7_p6_backend_context_t, tx_payload)" in service
            and "offsetof(p7_p6_backend_context_t, rx_payload)" in service,
        "end_to_end_output_compare_is_independent":
            "P7_FIRST_ERROR_STAGE_DDR_OUTPUT_END_TO_END" in process_descriptor_block
            and "P7_ERROR_DDR_OUTPUT_END_TO_END" in process_descriptor_block
            and "end_to_end_status = p7_compare_object_checked(" in process_descriptor_block
            and "(const volatile uint8_t *)(uintptr_t)request.input_address" in process_descriptor_block
            and "(const volatile uint8_t *)(uintptr_t)request.output_address" in process_descriptor_block
            and process_descriptor_block.find("end_to_end_status = p7_compare_object_checked(")
            < process_descriptor_block.find("if (descriptor->fragments_completed != fragment_count")
            < process_descriptor_block.find("failed:"),
        "nonzero_output_canary_is_manifest_bound":
            "OUTPUT_PREFILL_BYTE = 0xA5" in runner_text
            and 'f"OUTPUT_PREFILL_BYTE {OUTPUT_PREFILL_BYTE}"' in runner_text
            and '"output_prefill_byte": OUTPUT_PREFILL_BYTE' in runner_text
            and "p7_require_file_fill_byte $output_file 165" in execute_tcl
            and "$plan_value(OUTPUT_PREFILL_BYTE) != 165" in execute_tcl,
        "integrity_failure_snapshot_precedes_output_wipe":
            "P7_FAILURE_SNAPSHOT_MAGIC" in service
            and "p7_publish_integrity_failure_snapshot(" in process_descriptor_block
            and process_descriptor_block.find("p7_publish_integrity_failure_snapshot(")
            < process_descriptor_block.find("failed:")
            < process_descriptor_block.find("p7_wipe_partial(")
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED=1" in execute_tcl
            and "set diagnostic_capture_bytes 320" in execute_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_WIPED=1" in execute_tcl,
        "integrity_failure_snapshot_mailbox_diagnostic":
            "failure_snapshot_address" in service
            and "failure_snapshot_bytes" in service
            and "failure_snapshot_status" in service
            and "failure_snapshot_magic_readback" in service
            and "P7_FAILURE_SNAPSHOT_STATUS_PUBLISHED" in service
            and "P7_FAILURE_SNAPSHOT_STATUS_MARKER_READBACK_FAILED" in service
            and "P7_FAILURE_SNAPSHOT_BASEADDR" in service
            and "Xil_In32(address)" in service
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_ADDRESS=" in execute_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_BYTES=" in execute_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_STATUS=" in execute_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_MAGIC_READBACK=" in execute_tcl
            and "0x0002009C" in execute_tcl
            and "0x000200A0" in execute_tcl
            and "0x000200A4" in execute_tcl
            and "0x000200A8" in execute_tcl,
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
    payload_native = {"returncode": 127, "reason": "SKIP_WITH_REASON:gcc_not_found"}
    stage62_native = {"returncode": 127, "reason": "SKIP_WITH_REASON:gcc_not_found"}
    stage62_microtest_native = {
        "returncode": 127,
        "reason": "SKIP_WITH_REASON:gcc_not_found",
    }
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
        payload_executable = build_dir / "ir_driver_payload_alignment_test.exe"
        payload_compiled = subprocess.run(
            [str(gcc), "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-Isoftware/ps_driver", "tests/p7/ir_driver_payload_alignment_test.c",
             "software/ps_driver/ir_driver.c", "-o", str(payload_executable)],
            cwd=ROOT, text=True, capture_output=True, timeout=120, env=env,
        )
        payload_executed = subprocess.run(
            [str(payload_executable)], cwd=ROOT, text=True, capture_output=True,
            timeout=30, env=env,
        ) if payload_compiled.returncode == 0 else None
        payload_native = {
            "compiler": str(gcc),
            "compile_returncode": payload_compiled.returncode,
            "compile_stdout": payload_compiled.stdout,
            "compile_stderr": payload_compiled.stderr,
            "returncode": None if payload_executed is None else payload_executed.returncode,
            "stdout": "" if payload_executed is None else payload_executed.stdout,
            "stderr": "" if payload_executed is None else payload_executed.stderr,
        }
        stage62_executable = build_dir / "p7_stage62_diagnostic_test.exe"
        stage62_compiled = subprocess.run(
            [str(gcc), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-Isoftware/ps_driver", "-Isoftware/common",
             "tests/p7/p7_stage62_diagnostic_test.c",
             "software/ps_driver/p7_stage62_diagnostic.c",
             "-o", str(stage62_executable)],
            cwd=ROOT, text=True, capture_output=True, timeout=120, env=env,
        )
        stage62_executed = subprocess.run(
            [str(stage62_executable)], cwd=ROOT, text=True, capture_output=True,
            timeout=30, env=env,
        ) if stage62_compiled.returncode == 0 else None
        stage62_native = {
            "compiler": str(gcc),
            "compile_returncode": stage62_compiled.returncode,
            "compile_stdout": stage62_compiled.stdout,
            "compile_stderr": stage62_compiled.stderr,
            "returncode": None if stage62_executed is None else stage62_executed.returncode,
            "stdout": "" if stage62_executed is None else stage62_executed.stdout,
            "stderr": "" if stage62_executed is None else stage62_executed.stderr,
        }
        stage62_microtest_executable = (
            build_dir / "p7_stage62_microtest_layout_test.exe"
        )
        stage62_microtest_compiled = subprocess.run(
            [str(gcc), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-Isoftware/ps_driver",
             "tests/p7/p7_stage62_microtest_layout_test.c",
             "-o", str(stage62_microtest_executable)],
            cwd=ROOT, text=True, capture_output=True, timeout=120, env=env,
        )
        stage62_microtest_executed = subprocess.run(
            [str(stage62_microtest_executable)], cwd=ROOT, text=True,
            capture_output=True, timeout=30, env=env,
        ) if stage62_microtest_compiled.returncode == 0 else None
        stage62_microtest_native = {
            "compiler": str(gcc),
            "compile_returncode": stage62_microtest_compiled.returncode,
            "compile_stdout": stage62_microtest_compiled.stdout,
            "compile_stderr": stage62_microtest_compiled.stderr,
            "returncode": (
                None
                if stage62_microtest_executed is None
                else stage62_microtest_executed.returncode
            ),
            "stdout": (
                ""
                if stage62_microtest_executed is None
                else stage62_microtest_executed.stdout
            ),
            "stderr": (
                ""
                if stage62_microtest_executed is None
                else stage62_microtest_executed.stderr
            ),
        }
    native_ok = native.get("returncode") == 0
    checks["native_shutdown_readback_test"] = native_ok
    checks["native_payload_alignment_matrix_test"] = bool(
        payload_native.get("returncode") == 0
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_CASES=1000" in payload_native.get("stdout", "")
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_LENGTH_RANGE=1..247" in payload_native.get("stdout", "")
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_SOURCE_MOD64_COUNT=64" in payload_native.get("stdout", "")
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_DESTINATION_MOD64_COUNT=64" in payload_native.get("stdout", "")
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_SOURCE_DESTINATION_MOD4_PAIRS=16" in payload_native.get("stdout", "")
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_ARGUMENT_LIMITS=PASS" in payload_native.get("stdout", "")
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_BUFFER_BASE_ALIGNMENT=64" in payload_native.get("stdout", "")
        and "P7_PAYLOAD_ALIGNMENT_MATRIX_CANARY=0xA5" in payload_native.get("stdout", "")
    )
    checks["native_stage62_diagnostic_matrix_test"] = bool(
        stage62_native.get("returncode") == 0
        and "P7_STAGE62_DIAGNOSTIC_LAYOUT=PASS" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_CLASSIFICATIONS=PASS" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_CANARY=PASS" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_INDEPENDENT_READBACK=PASS" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_LENGTH_RANGE=1..247" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_SOURCE_MOD64_COUNT=64" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_DESTINATION_MOD64_COUNT=64" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_SOURCE_DESTINATION_MOD4_PAIRS=16" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_MATRIX_CASES=1011712" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_RECORD_CRC32=PASS" in stage62_native.get("stdout", "")
        and "P7_STAGE62_DIAGNOSTIC_RECORD_BYTES=1536" in stage62_native.get("stdout", "")
    )
    checks["native_stage62_microtest_layout_test"] = bool(
        stage62_microtest_native.get("returncode") == 0
        and "P7_STAGE62_MICROTEST_LAYOUT=PASS"
        in stage62_microtest_native.get("stdout", "")
        and "P7_STAGE62_MICROTEST_CONTROL_BYTES=64"
        in stage62_microtest_native.get("stdout", "")
        and "P7_STAGE62_MICROTEST_RECORD_BYTES=1536"
        in stage62_microtest_native.get("stdout", "")
        and "P7_STAGE62_MICROTEST_CASES=A,B,C,D"
        in stage62_microtest_native.get("stdout", "")
        and "P7_STAGE62_MICROTEST_LENGTH_RANGE=29..32"
        in stage62_microtest_native.get("stdout", "")
        and "P7_STAGE62_MICROTEST_ALIGNMENT_RANGE=0..3"
        in stage62_microtest_native.get("stdout", "")
        and "P7_STAGE62_MICROTEST_CANARY=0xA5"
        in stage62_microtest_native.get("stdout", "")
    )
    checks["firmware_stationary_admission_cutoff"] = bool(
        checks.get("firmware_stationary_admission_cutoff")
        and admission_native.get("returncode") == 0
    )

    unit, unit_ok, regression_record = resolve_unit_test_evidence(
        args, source_commit
    )
    checks["p7_python_and_codec_tests"] = unit_ok

    build_summary_path = ROOT / "evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json"
    build_summary = json.loads(build_summary_path.read_text(encoding="utf-8")) if build_summary_path.is_file() else {}
    source_hashes = {source: sha256(ROOT / source) for source in runner.CORE_READINESS_SOURCES}
    recorded_sources = build_summary.get("sources", {})
    required_build_sources = (
        "software/ps_driver/p7_runtime_main.c",
        "software/ps_driver/p7_app_service.c",
        "software/ps_driver/p7_app_service.h",
        "software/ps_driver/p7_stage62_diagnostic.c",
        "software/ps_driver/p7_stage62_diagnostic.h",
        "software/ps_driver/p7_stage62_microtest.c",
        "software/ps_driver/p7_stage62_microtest.h",
        "software/ps_driver/p7_admission_contract.h",
        "software/ps_driver/ir_driver.c",
        "software/ps_driver/ir_driver.h",
        "software/ps_driver/ir_regs.h",
        "software/common/rf_app_protocol.c",
        "software/common/rf_app_protocol.h",
        "software/common/rf_transport_backend.c",
        "software/common/rf_transport_backend.h",
        "scripts/build_p7_ps_runtime.tcl",
        "scripts/build_p7_ps_runtime.py",
    )
    required_build_hashes = {source: sha256(ROOT / source) for source in required_build_sources}
    build_fresh = (
        build_summary.get("P7_PS_RUNTIME_BUILD") == "PASS"
        and build_summary.get("syntax_only") is False
        and build_summary.get("mailbox_overlap") is False
        and build_summary.get("linker_ocm_hard_boundary_0x20000") is True
        and build_summary.get("stage62_diagnostic_section_verified") is True
        and build_summary.get("critical_payload_byte_copy_verified") is True
        and build_summary.get("first_error_diagnostic_disassembly_verified") is True
        and build_summary.get("stage62_copy_diagnostic_disassembly_verified") is True
        and build_summary.get("stage62_microtest_disassembly_verified") is True
        and build_summary.get("stack_usage_verified") is True
        and build_summary.get("stage62_microtest_stack_verified") is True
        and isinstance(build_summary.get("stage62_microtest_stack_bytes"), int)
        and not isinstance(build_summary.get("stage62_microtest_stack_bytes"), bool)
        and build_summary["stage62_microtest_stack_bytes"]
        <= build_summary.get("stage62_microtest_stack_limit_bytes", -1)
        and isinstance(build_summary.get("p7_process_descriptor_stack_bytes"), int)
        and not isinstance(build_summary.get("p7_process_descriptor_stack_bytes"), bool)
        and build_summary["p7_process_descriptor_stack_bytes"]
        <= build_summary.get("p7_process_descriptor_stack_limit_bytes", -1)
        and isinstance(build_summary.get("diagnostic_chain_stack_margin_bytes"), int)
        and build_summary["diagnostic_chain_stack_margin_bytes"]
        >= build_summary.get("diagnostic_chain_minimum_margin_bytes", -1)
        and isinstance(build_summary.get("critical_payload_copy_disassembly"), dict)
        and build_summary.get("critical_payload_copy_disassembly", {}).get(
            "copy_ldrb_count", 0
        )
        >= 2
        and build_summary.get("critical_payload_copy_disassembly", {}).get(
            "copy_strb_count", 0
        )
        >= 1
        and isinstance(build_summary.get("stage62_microtest_copy_disassembly"), dict)
        and build_summary.get("stage62_microtest_copy_disassembly", {}).get(
            "ldrb_count", 0
        ) >= 1
        and build_summary.get("stage62_microtest_copy_disassembly", {}).get(
            "strb_count", 0
        ) >= 1
        and build_summary.get("stage62_microtest_copy_disassembly", {}).get(
            "dsb_count", 0
        ) >= 1
        and build_summary.get("stage62_microtest_copy_disassembly", {}).get(
            "forbidden_memcpy_or_memmove"
        ) is False
        and build_summary.get("critical_payload_copy_disassembly", {}).get(
            "copy_dsb_count", 0
        )
        >= 1
        and set(recorded_sources) == set(required_build_sources)
        and all(recorded_sources.get(source) == digest for source, digest in required_build_hashes.items())
    )
    checks["real_vitis_build_source_bound"] = build_fresh
    checks["stage62_only_microtest_bypasses_pl_and_is_disassembly_bound"] = bool(
        checks.get("stage62_only_microtest_bypasses_pl_and_is_disassembly_bound")
        and build_summary.get("stage62_microtest_disassembly_verified") is True
        and build_summary.get("stage62_microtest_stack_verified") is True
    )
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
        "native_payload_alignment_matrix_test": payload_native,
        "native_stage62_diagnostic_matrix_test": stage62_native,
        "native_stage62_microtest_layout_test": stage62_microtest_native,
        "unit_tests": unit,
        "validated_complete_regression_summary": regression_record,
        "source_commit": source_commit,
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
