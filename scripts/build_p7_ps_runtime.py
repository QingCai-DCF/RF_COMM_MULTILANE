#!/usr/bin/env python3
# offline-build-only: XSCT creates the Vitis workspace and ELF here; this
# script never connects to a target, programs an FPGA, starts an ELF, or drives
# a TFDU pin.
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ax7010_ps7_board_contract import validate_vitis_artifacts  # noqa: E402

XSCT = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsct.bat")
TOOLCHAIN = Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin")
OUT = ROOT / "evidence/generated/vitis/p7_ps_runtime"
WORKSPACE = ROOT / "build/p7_ps_vitis_workspace"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run(command: list[str], *, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)


def _remove_cache_directory(path: Path, required_parent: Path) -> None:
    resolved = path.resolve()
    parent = required_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise RuntimeError(f"refusing unsafe cache removal: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-bypass",
        action="store_true",
        help="delete only the declared Vitis workspace before a real rebuild",
    )
    parsed_args = parser.parse_args(argv)
    if parsed_args.cache_bypass:
        _remove_cache_directory(WORKSPACE, ROOT / "build")
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("p7_runtime_*"):
        if stale.is_file():
            stale.unlink()
    (OUT / "p7_ps7_board_contract.json").unlink(missing_ok=True)
    ps_summary_path = ROOT / "evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate_build_summary.json"
    ps_summary = json.loads(ps_summary_path.read_text(encoding="utf-8"))
    xsa = ROOT / ps_summary["artifacts"]["xsa"]["immutable"]
    command = [str(XSCT), "scripts/build_p7_ps_runtime.tcl", str(ROOT), str(xsa)]
    proc = run(command)
    build_log = OUT / "p7_ps_runtime_build.log"
    build_log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    built = WORKSPACE / "p7_runtime/Debug/p7_runtime.elf"
    built_map = WORKSPACE / "p7_runtime/Debug/p7_runtime.map"
    bsp_parameters = ROOT / (
        "build/p7_ps_vitis_workspace/p7_platform/ps7_cortexa9_0/standalone_domain/"
        "bsp/ps7_cortexa9_0/include/xparameters.h"
    )
    size_tool = TOOLCHAIN / "arm-none-eabi-size.exe"
    nm_tool = TOOLCHAIN / "arm-none-eabi-nm.exe"
    objdump_tool = TOOLCHAIN / "arm-none-eabi-objdump.exe"
    inspection: dict[str, object] = {}
    end_address = None
    linker_ocm_hard_boundary = False
    stage62_diagnostic_section_verified = False
    critical_payload_byte_copy_verified = False
    first_error_diagnostic_disassembly_verified = False
    stage62_copy_diagnostic_disassembly_verified = False
    stage62_microtest_disassembly_verified = False
    stack_usage_verified = False
    stage62_microtest_stack_verified = False
    process_descriptor_stack_bytes = None
    stage62_microtest_stack_bytes = None
    user_stack_bytes = None
    diagnostic_chain_stack_bytes = None
    diagnostic_chain_stack_margin_bytes = None
    stack_usage_by_function: dict[str, int] = {}
    copy_ldrb_count = 0
    copy_strb_count = 0
    copy_dsb_count = 0
    equal_ldrb_count = 0
    critical_payload_copy_call_count = 0
    critical_payload_equal_call_count = 0
    first_error_publish_call_count = 0
    microtest_copy_ldrb_count = 0
    microtest_copy_strb_count = 0
    microtest_copy_dsb_count = 0
    microtest_copy_forbidden_reference = False
    diagnostic_section_address = None
    diagnostic_section_size = None
    cpu_clock_hz = None
    counts_per_second = None
    if built.exists():
        for name, tool, args in (
            ("size", size_tool, ["-A", str(built)]),
            ("symbols", nm_tool, ["-n", str(built)]),
            ("sections", objdump_tool, ["-h", str(built)]),
            ("disassembly", objdump_tool, ["-d", str(built)]),
        ):
            checked = run([str(tool), *args], timeout=120)
            path = OUT / f"p7_runtime_{name}.txt"
            path.write_text(checked.stdout + "\n" + checked.stderr, encoding="utf-8")
            inspection[name] = {
                "returncode": checked.returncode,
                "path": rel(path),
                "sha256": sha(path),
            }
            if name == "symbols" and checked.returncode == 0:
                for line in checked.stdout.splitlines():
                    fields = line.split()
                    if len(fields) >= 3 and fields[-1] == "_end":
                        end_address = int(fields[0], 16)
                    if (
                        len(fields) >= 3
                        and fields[-1] == "g_p7_first_error_diagnostic"
                    ):
                        diagnostic_section_address = int(fields[0], 16)
            if name == "sections" and checked.returncode == 0:
                diagnostic_section_match = re.search(
                    r"^\s*\d+\s+\.p7_stage62_diagnostic\s+"
                    r"([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+",
                    checked.stdout,
                    re.MULTILINE,
                )
                if diagnostic_section_match is not None:
                    diagnostic_section_size = int(
                        diagnostic_section_match.group(1), 16
                    )
                    section_vma = int(diagnostic_section_match.group(2), 16)
                    stage62_diagnostic_section_verified = (
                        diagnostic_section_size == 1536
                        and section_vma == 0x00021000
                    )
            if name == "disassembly" and checked.returncode == 0:
                copy_match = re.search(
                    r"<p7_copy_bytes_verified>:(.*?)(?=\n[0-9a-f]+ <)",
                    checked.stdout,
                    re.DOTALL,
                )
                equal_match = re.search(
                    r"<p7_bytes_equal_volatile>:(.*?)(?=\n[0-9a-f]+ <)",
                    checked.stdout,
                    re.DOTALL,
                )
                copy_calls = len(
                    re.findall(
                        r"\bbl\s+[0-9a-f]+\s+<p7_copy_bytes_verified>",
                        checked.stdout,
                    )
                )
                equal_calls = len(
                    re.findall(
                        r"\bbl\s+[0-9a-f]+\s+<p7_bytes_equal_volatile>",
                        checked.stdout,
                    )
                )
                copy_body = "" if copy_match is None else copy_match.group(1)
                equal_body = "" if equal_match is None else equal_match.group(1)
                copy_ldrb_count = len(re.findall(r"\bldrb\b", copy_body))
                copy_strb_count = len(re.findall(r"\bstrb\b", copy_body))
                copy_dsb_count = len(re.findall(r"\bdsb\b", copy_body))
                equal_ldrb_count = len(re.findall(r"\bldrb\b", equal_body))
                critical_payload_copy_call_count = copy_calls
                critical_payload_equal_call_count = equal_calls
                critical_payload_byte_copy_verified = (
                    copy_ldrb_count >= 2
                    and copy_strb_count >= 1
                    and copy_dsb_count >= 1
                    and "memcpy" not in copy_body
                    and equal_ldrb_count >= 2
                    and "memcmp" not in equal_body
                    and copy_calls >= 4
                    and equal_calls >= 1
                )
                first_error_match = re.search(
                    r"<p7_publish_first_error_diagnostic>:(.*?)(?=\n[0-9a-f]+ <)",
                    checked.stdout,
                    re.DOTALL,
                )
                first_error_calls = len(
                    re.findall(
                        r"\bbl\s+[0-9a-f]+\s+<p7_publish_first_error_diagnostic>",
                        checked.stdout,
                    )
                )
                first_error_publish_call_count = first_error_calls
                first_error_body = (
                    "" if first_error_match is None else first_error_match.group(1)
                )
                first_error_diagnostic_disassembly_verified = (
                    first_error_match is not None
                    and "p7_hash_volatile_bytes" in first_error_body
                    and "p7_publish_prepared_diagnostic" in first_error_body
                    and first_error_calls >= 7
                )
                copy_diagnostic_match = re.search(
                    r"<p7_copy_output_with_diagnostic>:(.*?)(?=\n[0-9a-f]+ <)",
                    checked.stdout,
                    re.DOTALL,
                )
                publish_diagnostic_match = re.search(
                    r"<p7_publish_prepared_diagnostic>:(.*?)(?=\n[0-9a-f]+ <)",
                    checked.stdout,
                    re.DOTALL,
                )
                copy_diagnostic_body = (
                    ""
                    if copy_diagnostic_match is None
                    else copy_diagnostic_match.group(1)
                )
                publish_diagnostic_body = (
                    ""
                    if publish_diagnostic_match is None
                    else publish_diagnostic_match.group(1)
                )
                stage62_copy_diagnostic_disassembly_verified = (
                    copy_diagnostic_match is not None
                    and len(re.findall(r"\bldrb\b", copy_diagnostic_body)) >= 1
                    and len(re.findall(r"\bstrb\b", copy_diagnostic_body)) >= 1
                    and len(re.findall(r"\bdsb\b", copy_diagnostic_body)) >= 1
                    and "p7_capture_window" in copy_diagnostic_body
                    and "p7_stage62_classify_copy_observation"
                    in copy_diagnostic_body
                    and "p7_publish_prepared_diagnostic" in copy_diagnostic_body
                    and publish_diagnostic_match is not None
                    and "p7_stage62_record_crc32" in publish_diagnostic_body
                    and "p7_publish_failure_snapshot_diagnostic"
                    in publish_diagnostic_body
                )
                microtest_copy_match = re.search(
                    r"<p7_stage62_microtest_copy_bytes>:(.*?)(?=\n[0-9a-f]+ <|\Z)",
                    checked.stdout,
                    re.DOTALL,
                )
                microtest_copy_body = (
                    "" if microtest_copy_match is None else microtest_copy_match.group(1)
                )
                microtest_copy_ldrb_count = len(
                    re.findall(r"\bldrb\b", microtest_copy_body)
                )
                microtest_copy_strb_count = len(
                    re.findall(r"\bstrb\b", microtest_copy_body)
                )
                microtest_copy_dsb_count = len(
                    re.findall(r"\bdsb\b", microtest_copy_body)
                )
                microtest_copy_forbidden_reference = bool(
                    "memcpy" in microtest_copy_body
                    or "memmove" in microtest_copy_body
                )
                stage62_microtest_disassembly_verified = (
                    microtest_copy_match is not None
                    and microtest_copy_ldrb_count >= 1
                    and microtest_copy_strb_count >= 1
                    and microtest_copy_dsb_count >= 1
                    and not microtest_copy_forbidden_reference
                )
    platform_hw = WORKSPACE / "p7_platform/hw"
    platform_xsa_candidates = sorted(platform_hw.glob("*.xsa"))
    platform_xsa = (
        platform_xsa_candidates[0]
        if len(platform_xsa_candidates) == 1
        else WORKSPACE / "__vitis_platform_xsa_expected_exactly_one__"
    )
    board_contract = validate_vitis_artifacts(
        xsa=xsa,
        platform_xsa=platform_xsa,
        ps7_parameters=WORKSPACE / "p7_platform/zynq_fsbl/ps7_parameters.xml",
        platform_ps7_init_tcl=platform_hw / "ps7_init.tcl",
        platform_ps7_init_c=platform_hw / "ps7_init.c",
        fsbl_ps7_init_c=WORKSPACE / "p7_platform/zynq_fsbl/ps7_init.c",
    )
    board_contract_path = OUT / "p7_ps7_board_contract.json"
    board_contract_path.write_text(
        json.dumps(board_contract, indent=2) + "\n", encoding="utf-8"
    )
    board_contract_verified = board_contract["status"] == "PASS"
    passed = (
        proc.returncode == 0
        and built.exists()
        and built_map.exists()
        and "P7_PS_RUNTIME_BUILD=PASS" in proc.stdout
        and all(value["returncode"] == 0 for value in inspection.values())
        and end_address is not None
        and end_address < 0x00020000
        and board_contract_verified
    )
    if built_map.exists():
        map_text = built_map.read_text(encoding="utf-8", errors="replace")
        linker_ocm_hard_boundary = re.search(
            r"^ps7_ram_0\s+0x0+\s+0x0*20000\s*$", map_text, re.MULTILINE
        ) is not None
        stage62_diagnostic_section_verified = bool(
            stage62_diagnostic_section_verified
            and diagnostic_section_address == 0x00021000
            and re.search(
                r"^p7_stage62_diag\s+0x0*21000\s+0x0*1000\s*$",
                map_text,
                re.MULTILINE,
            )
            is not None
            and re.search(
                r"^\.p7_stage62_diagnostic\s+0x0*21000\s+0x0*600\s*$",
                map_text,
                re.MULTILINE,
            )
            is not None
        )
        stack_match = re.search(
            r"^\s*(0x[0-9a-fA-F]+)\s+_STACK_SIZE\s+=",
            map_text,
            re.MULTILINE,
        )
        if stack_match is not None:
            user_stack_bytes = int(stack_match.group(1), 16)
    stack_usage_sources = sorted(
        (ROOT / "build/p7_ps_vitis_workspace/p7_runtime/Debug/src").glob("*.su")
    )
    if stack_usage_sources:
        stack_text = "\n".join(
            source.read_text(encoding="utf-8", errors="strict")
            for source in stack_usage_sources
        )
        stack_copy = OUT / "p7_runtime_stack_usage.txt"
        stack_copy.write_text(stack_text, encoding="utf-8")
        inspection["stack_usage"] = {
            "returncode": 0,
            "path": rel(stack_copy),
            "sha256": sha(stack_copy),
            "source_count": len(stack_usage_sources),
        }
        for line in stack_text.splitlines():
            fields = line.rsplit("\t", 2)
            if len(fields) == 3 and fields[-2].isdigit():
                function_name = fields[0].rsplit(":", 1)[-1]
                stack_usage_by_function[function_name] = max(
                    int(fields[-2]), stack_usage_by_function.get(function_name, 0)
                )
        process_descriptor_stack_bytes = stack_usage_by_function.get(
            "p7_process_descriptor"
        )
        stage62_microtest_stack_bytes = stack_usage_by_function.get(
            "p7_stage62_microtest_try_run"
        )
        stage62_microtest_stack_verified = (
            stage62_microtest_stack_bytes is not None
            and stage62_microtest_stack_bytes <= 1024
        )
        diagnostic_chain_functions = (
            "p7_process_descriptor",
            "rf_transport_submit_fragment",
            "p7_p6_submit",
            "p7_publish_first_error_diagnostic",
            "p7_hash_volatile_bytes",
            "p7_sha256_update",
            "p7_sha256_transform",
        )
        if all(name in stack_usage_by_function for name in diagnostic_chain_functions):
            diagnostic_chain_stack_bytes = sum(
                stack_usage_by_function[name] for name in diagnostic_chain_functions
            )
        if user_stack_bytes is not None and diagnostic_chain_stack_bytes is not None:
            diagnostic_chain_stack_margin_bytes = (
                user_stack_bytes - diagnostic_chain_stack_bytes
            )
        stack_usage_verified = (
            process_descriptor_stack_bytes is not None
            and process_descriptor_stack_bytes <= 4096
            and user_stack_bytes is not None
            and diagnostic_chain_stack_bytes is not None
            and diagnostic_chain_stack_margin_bytes is not None
            and diagnostic_chain_stack_margin_bytes >= 2048
        )
    else:
        inspection["stack_usage"] = {
            "returncode": 127,
            "path": None,
            "reason": "p7_app_service.su missing",
        }
    if bsp_parameters.is_file():
        parameters_text = bsp_parameters.read_text(encoding="utf-8", errors="strict")
        clock_match = re.search(
            r"^#define\s+XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ\s+([0-9]+)\s*$",
            parameters_text,
            re.MULTILINE,
        )
        if clock_match:
            cpu_clock_hz = int(clock_match.group(1))
            counts_per_second = cpu_clock_hz // 2
    passed = (
        passed
        and linker_ocm_hard_boundary
        and stage62_diagnostic_section_verified
        and critical_payload_byte_copy_verified
        and first_error_diagnostic_disassembly_verified
        and stage62_copy_diagnostic_disassembly_verified
        and stage62_microtest_disassembly_verified
        and stack_usage_verified
        and stage62_microtest_stack_verified
        and counts_per_second is not None
    )
    artifacts: dict[str, object] = {}
    if built.exists():
        digest = sha(built)
        record = {"source": rel(built), "sha256": digest, "immutable": None}
        if passed:
            immutable = ROOT / f"evidence/hardware/p7/artifacts/p7_runtime_{digest}.elf"
            immutable.parent.mkdir(parents=True, exist_ok=True)
            if immutable.exists() and sha(immutable) != digest:
                raise RuntimeError(f"immutable P7 ELF path collision: {immutable}")
            shutil.copy2(built, immutable)
            record["immutable"] = rel(immutable)
        artifacts["elf"] = record
    if built_map.exists():
        map_digest = sha(built_map)
        immutable_map = ROOT / f"evidence/hardware/p7/artifacts/p7_runtime_{map_digest}.map"
        immutable_map_value = None
        if passed:
            if immutable_map.exists() and sha(immutable_map) != map_digest:
                raise RuntimeError(f"immutable P7 map path collision: {immutable_map}")
            shutil.copy2(built_map, immutable_map)
            immutable_map_value = rel(immutable_map)
        map_copy = OUT / "p7_runtime.map"
        shutil.copy2(built_map, map_copy)
        artifacts["linker_map"] = {
            "source": rel(built_map),
            "sha256": map_digest,
            "immutable": immutable_map_value,
            "generated_copy": rel(map_copy),
        }
    if bsp_parameters.is_file():
        parameters_digest = sha(bsp_parameters)
        immutable_parameters = ROOT / f"evidence/hardware/p7/artifacts/p7_bsp_xparameters_{parameters_digest}.h"
        immutable_parameters_value = None
        if passed:
            if immutable_parameters.exists() and sha(immutable_parameters) != parameters_digest:
                raise RuntimeError(f"immutable P7 BSP xparameters path collision: {immutable_parameters}")
            shutil.copy2(bsp_parameters, immutable_parameters)
            immutable_parameters_value = rel(immutable_parameters)
        artifacts["bsp_xparameters"] = {
            "source": rel(bsp_parameters),
            "sha256": parameters_digest,
            "immutable": immutable_parameters_value,
        }
    sources = {}
    for path_text in (
        "software/ps_driver/p7_runtime_main.c", "software/ps_driver/p7_app_service.c",
        "software/ps_driver/p7_app_service.h", "software/ps_driver/p7_stage62_diagnostic.c",
        "software/ps_driver/p7_stage62_diagnostic.h", "software/ps_driver/p7_stage62_microtest.c",
        "software/ps_driver/p7_stage62_microtest.h", "software/ps_driver/p7_admission_contract.h",
        "software/ps_driver/ir_driver.c",
        "software/ps_driver/ir_driver.h", "software/ps_driver/ir_regs.h",
        "software/common/rf_app_protocol.c",
        "software/common/rf_app_protocol.h", "software/common/rf_transport_backend.c",
        "software/common/rf_transport_backend.h",
        "scripts/build_p7_ps_runtime.tcl", "scripts/build_p7_ps_runtime.py",
    ):
        path = ROOT / path_text
        sources[path_text] = sha(path)
    summary = {
        "P7_PS_RUNTIME_BUILD": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "returncode": proc.returncode,
        "cache_bypass": parsed_args.cache_bypass,
        "command": subprocess.list2cmdline(command),
        "xsct": str(XSCT),
        "xsa": rel(xsa),
        "xsa_sha256": sha(xsa),
        "mailbox_base": "0x00020000",
        "ocm_image_end": None if end_address is None else f"0x{end_address:08x}",
        "mailbox_overlap": end_address is None or end_address >= 0x00020000,
        "linker_ocm_hard_boundary_0x20000": linker_ocm_hard_boundary,
        "stage62_diagnostic_section_verified": stage62_diagnostic_section_verified,
        "stage62_diagnostic_section_address": (
            None
            if diagnostic_section_address is None
            else f"0x{diagnostic_section_address:08x}"
        ),
        "stage62_diagnostic_section_size": diagnostic_section_size,
        "critical_payload_byte_copy_verified": critical_payload_byte_copy_verified,
        "critical_payload_copy_disassembly": {
            "copy_ldrb_count": copy_ldrb_count,
            "copy_strb_count": copy_strb_count,
            "copy_dsb_count": copy_dsb_count,
            "equal_ldrb_count": equal_ldrb_count,
            "copy_call_count": critical_payload_copy_call_count,
            "equal_call_count": critical_payload_equal_call_count,
        },
        "first_error_diagnostic_disassembly_verified": first_error_diagnostic_disassembly_verified,
        "stage62_copy_diagnostic_disassembly_verified": stage62_copy_diagnostic_disassembly_verified,
        "stage62_microtest_disassembly_verified": stage62_microtest_disassembly_verified,
        "stage62_microtest_copy_disassembly": {
            "ldrb_count": microtest_copy_ldrb_count,
            "strb_count": microtest_copy_strb_count,
            "dsb_count": microtest_copy_dsb_count,
            "forbidden_memcpy_or_memmove": microtest_copy_forbidden_reference,
        },
        "first_error_publish_call_count": first_error_publish_call_count,
        "stack_usage_verified": stack_usage_verified,
        "stage62_microtest_stack_verified": stage62_microtest_stack_verified,
        "stage62_microtest_stack_bytes": stage62_microtest_stack_bytes,
        "stage62_microtest_stack_limit_bytes": 1024,
        "p7_process_descriptor_stack_bytes": process_descriptor_stack_bytes,
        "p7_process_descriptor_stack_limit_bytes": 4096,
        "user_stack_bytes": user_stack_bytes,
        "diagnostic_chain_stack_bytes": diagnostic_chain_stack_bytes,
        "diagnostic_chain_stack_margin_bytes": diagnostic_chain_stack_margin_bytes,
        "diagnostic_chain_minimum_margin_bytes": 2048,
        "stack_usage_by_function": stack_usage_by_function,
        "max_object_bytes": 8388608,
        "queue_depth": 8,
        "cpu_clock_hz": cpu_clock_hz,
        "counts_per_second": counts_per_second,
        "counts_per_second_definition": "XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ/2",
        "ps7_board_contract_verified": board_contract_verified,
        "ps7_board_contract_report": {
            "path": rel(board_contract_path),
            "sha256": sha(board_contract_path),
            "status": board_contract["status"],
        },
        "syntax_only": False,
        "artifacts": artifacts,
        "inspection": inspection,
        "sources": sources,
        "network_used": False,
        "hardware_actions_executed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    summary_text = json.dumps(summary, indent=2) + "\n"
    summary_path = OUT / "p7_ps_runtime_build_summary.json"
    summary_path.write_text(summary_text, encoding="utf-8")
    (ROOT / "evidence/generated/p7_ps_runtime_build_summary.json").write_text(
        summary_text, encoding="utf-8"
    )
    md = [
        "# P7 PS Runtime Build", "", f"P7_PS_RUNTIME_BUILD: {summary['P7_PS_RUNTIME_BUILD']}",
        "SYNTAX_ONLY: false", "NO_HARDWARE_ACTIONS_EXECUTED: true", "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"XSA_SHA256: {summary['xsa_sha256']}", f"OCM_IMAGE_END: {summary['ocm_image_end']}",
        f"MAILBOX_OVERLAP: {str(summary['mailbox_overlap']).lower()}",
        f"LINKER_OCM_HARD_BOUNDARY_0X20000: {str(summary['linker_ocm_hard_boundary_0x20000']).lower()}",
        f"STAGE62_DIAGNOSTIC_SECTION_VERIFIED: {str(summary['stage62_diagnostic_section_verified']).lower()}",
        f"CRITICAL_PAYLOAD_BYTE_COPY_VERIFIED: {str(summary['critical_payload_byte_copy_verified']).lower()}",
        f"FIRST_ERROR_DIAGNOSTIC_DISASSEMBLY_VERIFIED: {str(summary['first_error_diagnostic_disassembly_verified']).lower()}",
        f"STAGE62_COPY_DIAGNOSTIC_DISASSEMBLY_VERIFIED: {str(summary['stage62_copy_diagnostic_disassembly_verified']).lower()}",
        f"STAGE62_MICROTEST_DISASSEMBLY_VERIFIED: {str(summary['stage62_microtest_disassembly_verified']).lower()}",
        f"STACK_USAGE_VERIFIED: {str(summary['stack_usage_verified']).lower()}",
        f"STAGE62_MICROTEST_STACK_VERIFIED: {str(summary['stage62_microtest_stack_verified']).lower()}",
        f"STAGE62_MICROTEST_STACK_BYTES: {summary['stage62_microtest_stack_bytes']}",
        f"P7_PROCESS_DESCRIPTOR_STACK_BYTES: {summary['p7_process_descriptor_stack_bytes']}",
        f"USER_STACK_BYTES: {summary['user_stack_bytes']}",
        f"DIAGNOSTIC_CHAIN_STACK_BYTES: {summary['diagnostic_chain_stack_bytes']}",
        f"DIAGNOSTIC_CHAIN_STACK_MARGIN_BYTES: {summary['diagnostic_chain_stack_margin_bytes']}",
        f"COUNTS_PER_SECOND: {summary['counts_per_second']}",
    ]
    if "elf" in artifacts and "linker_map" in artifacts:
        md.append(f"ELF_SHA256: {artifacts['elf']['sha256']}")
        md.append(f"IMMUTABLE_ELF: {artifacts['elf']['immutable']}")
        md.append(f"LINKER_MAP_SHA256: {artifacts['linker_map']['sha256']}")
        md.append(f"IMMUTABLE_LINKER_MAP: {artifacts['linker_map']['immutable']}")
    markdown_text = "\n".join(md) + "\n"
    (OUT / "p7_ps_runtime_build_summary.md").write_text(markdown_text, encoding="utf-8")
    (ROOT / "evidence/generated/p7_ps_runtime_build_summary.md").write_text(
        markdown_text, encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
