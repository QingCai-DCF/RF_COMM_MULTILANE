#!/usr/bin/env python3
"""Build and audit the offline P9 bare-metal PS/DMA runtime.

offline-build-only: XSCT is restricted to platform/BSP/application generation
from an existing XSA; this script contains no target connection, download,
programming, or other hardware operation.
"""
from __future__ import annotations

import hashlib
import json
import re
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
HOST_GCC = Path(r"D:\Xilinx\Vivado\2023.1\tps\mingw\9.3.0\win64.o\nt\bin\gcc.exe")
WORKSPACE = ROOT / "build/p9_ps_vitis_workspace"
OUT = ROOT / "evidence/generated/vitis/p9_ps_runtime"
XSA = ROOT / "evidence/generated/vivado/p9_z7010_candidate/ir_p9_z7010_2lane.xsa"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run(command: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)


def artifact(path: Path) -> dict[str, object]:
    return {
        "path": rel(path),
        "size": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    if not XSA.is_file():
        errors.append("candidate XSA missing")
    native = OUT / "p9_crypto_protocol_test.exe"
    native_run = run([
        str(HOST_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-Isoftware/ps_driver", "tests/test_p9_crypto.c",
        "software/ps_driver/p9_crypto.c", "-o", str(native),
    ], timeout=120)
    (OUT / "p9_crypto_protocol_build.log").write_text(
        native_run.stdout + "\n" + native_run.stderr, encoding="utf-8"
    )
    native_exec = run([str(native)], timeout=30) if native_run.returncode == 0 else None
    if native_exec is None or native_exec.returncode != 0 or \
            "P9_CRYPTO_PROTOCOL_TEST=PASS" not in native_exec.stdout:
        errors.append("native crypto/protocol test failed")
    if errors:
        summary = {"status": "FAIL", "errors": errors}
        (OUT / "p9_ps_runtime_build_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary))
        return 1

    command = [str(XSCT), "scripts/build_p9_ps_runtime.tcl", str(ROOT), str(XSA)]
    proc = run(command, timeout=1800)
    build_log = OUT / "p9_ps_runtime_build.log"
    build_log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    elf = WORKSPACE / "p9_runtime/Debug/p9_runtime.elf"
    map_file = WORKSPACE / "p9_runtime/Debug/p9_runtime.map"
    bsp = WORKSPACE / "p9_platform/ps7_cortexa9_0/standalone_domain/bsp/ps7_cortexa9_0"
    xparameters = bsp / "include/xparameters.h"
    driver_header = bsp / "include/xaxidma.h"
    ps7_init = WORKSPACE / "p9_platform/hw/ps7_init.tcl"
    generated_artifacts = [elf, map_file, xparameters, driver_header, ps7_init]
    if proc.returncode != 0 or "P9_PS_RUNTIME_BUILD=PASS" not in proc.stdout:
        errors.append(f"XSCT build failed rc={proc.returncode}")
    errors.extend(f"missing {rel(path)}" for path in generated_artifacts if not path.is_file())

    inspection: dict[str, dict[str, object]] = {}
    end_address: int | None = None
    if elf.is_file():
        for name, tool, args in (
            ("size", TOOLCHAIN / "arm-none-eabi-size.exe", ["-A", str(elf)]),
            ("symbols", TOOLCHAIN / "arm-none-eabi-nm.exe", ["-n", str(elf)]),
            ("sections", TOOLCHAIN / "arm-none-eabi-objdump.exe", ["-h", str(elf)]),
        ):
            checked = run([str(tool), *args], timeout=120)
            path = OUT / f"p9_runtime_{name}.txt"
            path.write_text(checked.stdout + "\n" + checked.stderr, encoding="utf-8")
            inspection[name] = {
                "returncode": checked.returncode,
                "path": rel(path),
                "sha256": sha256(path),
            }
            if checked.returncode != 0:
                errors.append(f"{name} inspection failed")
            if name == "symbols":
                for line in checked.stdout.splitlines():
                    fields = line.split()
                    if len(fields) >= 3 and fields[-1] == "_end":
                        end_address = int(fields[0], 16)
        if end_address is None or end_address >= 0x00020000:
            errors.append(f"ELF exceeds OCM boundary: {end_address}")

    xparam_text = xparameters.read_text(encoding="utf-8", errors="replace") \
        if xparameters.is_file() else ""
    required_patterns = {
        "dma_device": r"#define\s+XPAR_AXI_DMA_0_DEVICE_ID\s+0",
        "dma_base": r"#define\s+XPAR_AXIDMA_0_BASEADDR\s+0x40400000",
        "dma_sg": r"#define\s+XPAR_AXIDMA_0_INCLUDE_SG\s+1",
        "dma_sg_width": r"#define\s+XPAR_AXI_DMA_0_SG_LENGTH_WIDTH\s+26",
        "p9_base": r"#define\s+XPAR_P9_AXI_DMA_PERIPHERAL_BD_0_BASEADDR\s+0x43C00000",
    }
    xparam_checks = {key: re.search(pattern, xparam_text) is not None
                     for key, pattern in required_patterns.items()}
    errors.extend(f"xparameters missing {key}" for key, passed in xparam_checks.items()
                  if not passed)

    hw = WORKSPACE / "p9_platform/hw"
    platform_xsas = sorted(hw.glob("*.xsa"))
    platform_xsa = platform_xsas[0] if len(platform_xsas) == 1 else \
        WORKSPACE / "__p9_platform_xsa_expected_exactly_one__"
    board_contract = validate_vitis_artifacts(
        xsa=XSA,
        platform_xsa=platform_xsa,
        ps7_parameters=WORKSPACE / "p9_platform/zynq_fsbl/ps7_parameters.xml",
        platform_ps7_init_tcl=hw / "ps7_init.tcl",
        platform_ps7_init_c=hw / "ps7_init.c",
        fsbl_ps7_init_c=WORKSPACE / "p9_platform/zynq_fsbl/ps7_init.c",
        expected_hwh_name="p9_ps_system.hwh",
    )
    board_contract_path = OUT / "p9_ps7_board_contract.json"
    board_contract_path.write_text(json.dumps(board_contract, indent=2) + "\n",
                                   encoding="utf-8")
    if board_contract["status"] != "PASS":
        errors.append("PS7/Vitis board contract failed")

    source_paths = [
        ROOT / "software/ps_driver/p9_runtime_main.c",
        ROOT / "software/ps_driver/p9_runtime_protocol.h",
        ROOT / "software/ps_driver/p9_crypto.c",
        ROOT / "software/ps_driver/p9_crypto.h",
        ROOT / "software/ps_driver/ir_regs.h",
        ROOT / "scripts/build_p9_ps_runtime.tcl",
    ]
    summary = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "test_id": "P9-02-PS-RUNTIME-BUILD",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "syntax_only": False,
        "xsct_returncode": proc.returncode,
        "xsa": artifact(XSA),
        "artifacts": {path.name: artifact(path) for path in generated_artifacts if path.is_file()},
        "source_sha256": {rel(path): sha256(path) for path in source_paths},
        "inspection": inspection,
        "elf_end_address": None if end_address is None else f"0x{end_address:08X}",
        "mailbox_base": "0x00020000",
        "tx_bd_base": "0x01000000",
        "rx_bd_base": "0x01001000",
        "tx_buffer_base": "0x02000000",
        "rx_buffer_base": "0x06000000",
        "maximum_object_bytes": 64 * 1024 * 1024,
        "xparameters_checks": xparam_checks,
        "board_contract": {"status": board_contract["status"],
                           "path": rel(board_contract_path),
                           "sha256": sha256(board_contract_path)},
        "native_crypto_protocol_test": "PASS" if native_exec and native_exec.returncode == 0 else "FAIL",
        "errors": errors,
    }
    summary_path = OUT / "p9_ps_runtime_build_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
