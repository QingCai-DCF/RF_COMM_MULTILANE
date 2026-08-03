#!/usr/bin/env python3
"""Compile the P10.2 four-lane production service for host and ARM offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOST_GCC = Path(r"D:\Xilinx\Vivado\2023.1\tps\mingw\9.3.0\win64.o\nt\bin\gcc.exe")
ARM_GCC = Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe")
ARM_READELF = ARM_GCC.with_name("arm-none-eabi-readelf.exe")
OUT = ROOT / "evidence/generated/p10_2_software"
SUMMARY_JSON = ROOT / "evidence/generated/p10_2_host_software_build.json"
SUMMARY_MD = ROOT / "evidence/generated/p10_2_host_software_build.md"
HOST_EXE = OUT / "p10_2_4lane_host_native_test.exe"
SERVICE_SOURCES = [
    ROOT / "software/ps_driver/p10_1_service.c",
    ROOT / "software/ps_driver/p10_1_trace.c",
    ROOT / "software/ps_driver/p10_1_hal_baremetal.c",
    ROOT / "software/ps_driver/p10_1_hal_freertos.c",
]
HOST_SOURCES = [*SERVICE_SOURCES, ROOT / "software/ps_driver/p10_1_hal_host.c"]
ARM_SOURCES = [
    *SERVICE_SOURCES,
    ROOT / "software/ps_driver/p10_1_performance_entry.c",
    ROOT / "software/ps_driver/p10_1_minicrt.c",
]
PROVENANCE = [
    Path(__file__).resolve(),
    ROOT / "tests/p10_1/p10_1_host_native_test.c",
    *HOST_SOURCES,
    ROOT / "software/ps_driver/p10_1_service.h",
    ROOT / "software/ps_driver/p10_1_contract.h",
    ROOT / "software/ps_driver/ir_regs.h",
    ROOT / "config/register_map/ir_axi_regs.yaml",
    ROOT / "config/performance/p10_2_4lane.yaml",
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], log: Path) -> subprocess.CompletedProcess[str]:
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
            "NO_2H_QUALIFICATION": "true",
        },
    )
    log.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        + f"RETURN_CODE={result.returncode}\n"
        + "STDOUT_BEGIN\n" + result.stdout + "\nSTDOUT_END\n"
        + "STDERR_BEGIN\n" + result.stderr + "\nSTDERR_END\n",
        encoding="utf-8",
        errors="replace",
        newline="\n",
    )
    return result


def artifact(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    for tool in (HOST_GCC, ARM_GCC, ARM_READELF):
        if not tool.is_file():
            errors.append(f"missing compiler tool {tool}")
    OUT.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    if not errors and not args.verify_existing:
        host_log = OUT / "host_build.log"
        host = run(
            [
                str(HOST_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wl,--no-insert-timestamp", "-DP10_1_SERVICE_LANE_COUNT=4",
                "-Isoftware/ps_driver", "tests/p10_1/p10_1_host_native_test.c",
                *[rel(path) for path in HOST_SOURCES], "-o", str(HOST_EXE),
            ],
            host_log,
        )
        logs.append(artifact(host_log))
        if host.returncode != 0:
            errors.append("four-lane host production-service compile failed")
        else:
            host_run_log = OUT / "host_run.log"
            host_run = run([str(HOST_EXE)], host_run_log)
            logs.append(artifact(host_run_log))
            if host_run.returncode != 0 or \
                    "P10_1_HOST_NATIVE_PRODUCTION_SERVICE=PASS" not in host_run.stdout:
                errors.append("four-lane host production-service execution failed")

        for role, role_value in (("fixed", 1), ("rotating", 2)):
            elf = OUT / f"p10_2_{role}_service.elf"
            map_path = OUT / f"p10_2_{role}_service.map"
            build_log = OUT / f"{role}_arm_build.log"
            built = run(
                [
                    str(ARM_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-Os", "-ffreestanding", "-mcpu=cortex-a9", "-marm",
                    "-Isoftware/ps_driver", "-DP10_1_SERVICE_LANE_COUNT=4",
                    f"-DP10_1_ENDPOINT_ROLE={role_value}",
                    *[rel(path) for path in ARM_SOURCES], "-nostdlib",
                    "-Wl,-T,software/ps_driver/p10_1_offline.ld",
                    f"-Wl,-Map,{map_path}", "-Wl,--gc-sections", "-lgcc",
                    "-o", str(elf),
                ],
                build_log,
            )
            logs.append(artifact(build_log))
            if built.returncode != 0 or not elf.is_file():
                errors.append(f"{role} four-lane ARM service compile/link failed")
                continue
            inspect_log = OUT / f"{role}_arm_readelf.log"
            inspected = run([str(ARM_READELF), "-h", "-s", str(elf)], inspect_log)
            logs.append(artifact(inspect_log))
            inspection = inspect_log.read_text(encoding="utf-8", errors="replace")
            if inspected.returncode != 0 or "EXEC" not in inspection or \
                    "p10_1_endpoint_role" not in inspection:
                errors.append(f"{role} four-lane ARM service identity inspection failed")

    required = [
        HOST_EXE,
        OUT / "p10_2_fixed_service.elf",
        OUT / "p10_2_rotating_service.elf",
    ]
    artifacts: list[dict[str, Any]] = []
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing software artifact {rel(path)}")
        else:
            artifacts.append(artifact(path))
    summary = {
        "schema_version": 1,
        "test_id": "P10_2-FOUR-LANE-SOFTWARE-COMPILE",
        "status": "PASS" if not errors else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "lane_count": 4,
        "lane_mask_max": "0xF",
        "role_fixed_at_compile_time": True,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "network_used": False,
        "artifacts": artifacts,
        "logs": logs,
        "source_sha256": {rel(path): sha256(path) for path in PROVENANCE},
        "errors": errors,
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    lines = [
        "# P10.2 four-lane software compile", "",
        f"- Status: `{summary['status']}`",
        "- Lane count: `4`; maximum lane mask: `0xF`.",
        "- Hardware actions executed: `false`.", "",
        "| Artifact | SHA256 |", "|---|---|",
    ]
    lines.extend(f"| `{item['path']}` | `{item['sha256']}` |" for item in artifacts)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_2_FOUR_LANE_SOFTWARE_COMPILE={summary['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
