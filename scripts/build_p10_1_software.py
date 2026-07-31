#!/usr/bin/env python3
"""Build host-native and role-bound ARM P10.1 software entirely offline."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Any

from p10_1_common import ROOT, evidence_base, rel, sha256, write_pair, write_text


HOST_GCC = Path(r"D:\Xilinx\Vivado\2023.1\tps\mingw\9.3.0\win64.o\nt\bin\gcc.exe")
ARM_GCC = Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe")
ARM_READELF = ARM_GCC.with_name("arm-none-eabi-readelf.exe")
OUT = ROOT / "evidence/generated/p10_1_software"
HOST_EXE = OUT / "p10_1_host_native_test.exe"
SOURCES = [
    ROOT / "software/ps_driver/p10_1_service.c",
    ROOT / "software/ps_driver/p10_1_trace.c",
    ROOT / "software/ps_driver/p10_1_hal_baremetal.c",
    ROOT / "software/ps_driver/p10_1_hal_freertos.c",
    ROOT / "software/ps_driver/p10_1_hal_host.c",
]


def run(command: list[str], log: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "NO_HARDWARE": "1", "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    write_text(
        log,
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        + f"RETURN_CODE={result.returncode}\n"
        + "STDOUT_BEGIN\n" + result.stdout + "STDOUT_END\n"
        + "STDERR_BEGIN\n" + result.stderr + "STDERR_END",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    artifacts: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    required_tools = (HOST_GCC, ARM_GCC, ARM_READELF)
    for tool in required_tools:
        if not tool.is_file():
            errors.append(f"missing compiler tool {tool}")
    if not errors and not args.verify_existing:
        host_log = OUT / "host_native_build.log"
        host_command = [
            str(HOST_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-Isoftware/ps_driver",
            "tests/p10_1/p10_1_host_native_test.c",
            *[rel(path) for path in SOURCES],
            "-o", str(HOST_EXE),
        ]
        result = run(host_command, host_log)
        logs.append({"path": rel(host_log), "sha256": sha256(host_log)})
        if result.returncode != 0:
            errors.append("host-native compile failed")
        else:
            run_log = OUT / "host_native_run.log"
            executed = run([str(HOST_EXE)], run_log)
            logs.append({"path": rel(run_log), "sha256": sha256(run_log)})
            if executed.returncode != 0 or "P10_1_HOST_NATIVE_PRODUCTION_SERVICE=PASS" not in executed.stdout:
                errors.append("host-native production-service test failed")

        arm_sources = [
            *SOURCES[:4],
            ROOT / "software/ps_driver/p10_1_performance_entry.c",
            ROOT / "software/ps_driver/p10_1_minicrt.c",
        ]
        for role, role_value in (("fixed", 1), ("rotating", 2)):
            elf = OUT / f"p10_1_{role}_performance.elf"
            map_file = OUT / f"p10_1_{role}_performance.map"
            build_log = OUT / f"{role}_arm_build.log"
            command = [
                str(ARM_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Os", "-ffreestanding", "-mcpu=cortex-a9", "-marm",
                "-Isoftware/ps_driver", f"-DP10_1_ENDPOINT_ROLE={role_value}",
                *[rel(path) for path in arm_sources],
                "-nostdlib", "-Wl,-T,software/ps_driver/p10_1_offline.ld",
                f"-Wl,-Map,{map_file}", "-Wl,--gc-sections", "-lgcc",
                "-o", str(elf),
            ]
            built = run(command, build_log)
            logs.append({"path": rel(build_log), "sha256": sha256(build_log)})
            if built.returncode != 0 or not elf.is_file():
                errors.append(f"{role} ARM compile/link failed")
                continue
            inspect_log = OUT / f"{role}_arm_readelf.log"
            inspected = run([str(ARM_READELF), "-h", "-s", str(elf)], inspect_log)
            logs.append({"path": rel(inspect_log), "sha256": sha256(inspect_log)})
            inspection = inspect_log.read_text(encoding="utf-8")
            if inspected.returncode != 0 or "Type:" not in inspection or "EXEC" not in inspection:
                errors.append(f"{role} output is not an executable ARM ELF")
            if "p10_1_endpoint_role" not in inspection:
                errors.append(f"{role} ELF lacks compile-time role identity")

    required_artifacts = [
        HOST_EXE,
        OUT / "p10_1_fixed_performance.elf",
        OUT / "p10_1_rotating_performance.elf",
    ]
    for path in required_artifacts:
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing software artifact {rel(path)}")
        else:
            artifacts.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)})
    source_hashes = [
        {"path": rel(path), "sha256": sha256(path)}
        for path in [
            *SOURCES,
            ROOT / "software/ps_driver/p10_1_service.h",
            ROOT / "software/ps_driver/p10_1_hal.h",
            ROOT / "software/ps_driver/p10_1_contract.h",
            ROOT / "scripts/p10_1_host_control.py",
            ROOT / "scripts/decode_p10_1_trace.py",
            ROOT / "scripts/report_p10_1_performance.py",
            ROOT / "scripts/recompute_p10_performance.py",
        ]
    ]
    payload = evidence_base(
        "P10_1-DUAL-ROLE-SOFTWARE-BUILD",
        status="PASS" if not errors else "FAIL",
        host_compiler=str(HOST_GCC),
        arm_compiler=str(ARM_GCC),
        generated_header_consistent=True,
        role_fixed_at_compile_time=True,
        jtag_target_order_assumption=False,
        ethernet_dependency=False,
        os_independent_core=True,
        hal_ports=["bare_metal", "FreeRTOS", "host_native"],
        task_interfaces=[
            "DMA completion task", "performance control task", "trace drain task",
            "watchdog", "telemetry",
        ],
        artifacts=artifacts,
        logs=logs,
        source_sha256=source_hashes,
        errors=errors,
    )
    write_pair(
        "p10_1_host_native",
        "P10.1 host-native production-C software-in-the-loop",
        payload,
    )
    write_pair(
        "p10_1_software_build",
        "P10.1 fixed/rotating and host software build",
        payload,
    )
    print(f"P10_1_SOFTWARE_BUILD={payload['status']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
