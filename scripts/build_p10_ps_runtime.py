#!/usr/bin/env python3
"""Build, audit, and freeze role-bound P10 AX7020 BSP/ELF artifacts offline.

offline-build-only: XSCT is used strictly as a local Vitis workspace/build
driver.  This script contains no target connection, download, or run command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
XSCT = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsct.bat")
TOOLCHAIN = Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin")
HOST_GCC = Path(r"D:\Xilinx\Vivado\2023.1\tps\mingw\9.3.0\win64.o\nt\bin\gcc.exe")
TCL = ROOT / "scripts/vitis/build_p10_ax7020_runtime.tcl"
OUT = ROOT / "evidence/generated/vitis/p10_ax7020_runtime"
ARTIFACTS = ROOT / "artifacts/p10"
SUMMARY_JSON = ROOT / "evidence/generated/p10_ax7020_ps_runtime_build_summary.json"
SUMMARY_MD = ROOT / "evidence/generated/p10_ax7020_ps_runtime_build_summary.md"
FUNCTIONAL_OUT = ROOT / "evidence/generated/vivado/p10_ax7020_functional"
CAMPAIGN = "p10"
TEST_ID = "P10-AX7020-DUAL-PS-RUNTIME-BUILD"
SUMMARY_TITLE = "P10 AX7020 role-bound PS runtime build"

ROLES = {
    "fixed": {
        "role_value": 1,
        "header": ROOT / "board_profiles/ax7020_fixed_2lane/p10_runtime_role.h",
    },
    "rotating": {
        "role_value": 2,
        "header": ROOT / "board_profiles/ax7020_rotating_2lane/p10_runtime_role.h",
    },
}

SOURCES = [
    Path(__file__).resolve(),
    ROOT / "software/ps_driver/p10_runtime_main.c",
    ROOT / "software/ps_driver/p9_runtime_main.c",
    ROOT / "software/ps_driver/p9_runtime_protocol.h",
    ROOT / "software/ps_driver/p10_1_runtime_protocol.h",
    ROOT / "software/ps_driver/p10_1_runtime_extension.inc",
    ROOT / "software/ps_driver/p9_crypto.c",
    ROOT / "software/ps_driver/p9_crypto.h",
    ROOT / "software/ps_driver/ir_regs.h",
    TCL,
]
P10_1_HW_GOAL = Path(
    r"C:\Users\user\Downloads"
    r"\P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE_GOAL.md"
)
P10_1_HW_GOAL_SHA256 = (
    "b3d0ae793a89ba270ca72880fb4fa38bcb17ac7631f3fc650e2557963840f9d3"
)
P10_1_PROVENANCE = [
    ROOT / "config/performance/p10_1_measurement_contract.yaml",
    ROOT / "config/performance/p10_1_pipeline.yaml",
    ROOT / "config/performance/p10_1_streaming.yaml",
    ROOT / "config/performance/p10_1_hardware_runtime.yaml",
    ROOT / "config/hardware/p10_active_wiring.yaml",
    ROOT / "scripts/p10_1_hardware_acceptance.py",
    ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl",
]
P10_1R_GOAL = ROOT / "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md"
P10_1R_GOAL_SHA256 = (
    "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
)
P10_1R_PROVENANCE = [
    ROOT / "config/tfdu_rx_admission.yaml",
    ROOT / "config/performance/p10_1_pipeline.yaml",
    ROOT / "config/performance/p10_1r_hardware_runtime.yaml",
    ROOT / "config/register_map/ir_axi_regs.yaml",
    ROOT / "docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md",
]
P10_2_GOAL = ROOT / "goals/P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS_GOAL.md"
P10_2_GOAL_SHA256 = "f09ddcd1556b6def7eab250cae92b1cc69f7316a4c3338b5b04d23b10f22a8f5"
P10_3_GOAL = ROOT / "goals/P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_GOAL.md"
P10_3_GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
P10_3F_PROVENANCE = [
    ROOT / "config/safety/p10_3_fault_forensics.yaml",
    ROOT / "config/performance/p10_3f_staircase.yaml",
    ROOT / "docs/design/P10_3_FIRST_FAULT_FORENSICS.md",
    ROOT / "scripts/archive_p10_fault_forensics.py",
    ROOT / "scripts/hw/p10_3f_fault_forensics.tcl",
    ROOT / "scripts/run_p10_3f_staircase_hardware.py",
    ROOT / "scripts/run_p10_3f_fault_forensics_offline.py",
    ROOT / "scripts/freeze_p10_3f_artifacts.py",
    ROOT / "scripts/finalize_p10_3f_offline.py",
]


def configure_campaign(campaign: str) -> None:
    global OUT, ARTIFACTS, SUMMARY_JSON, SUMMARY_MD, FUNCTIONAL_OUT
    global CAMPAIGN, TEST_ID, SUMMARY_TITLE, ROLES
    CAMPAIGN = campaign
    if campaign == "p10":
        return
    if campaign == "p10_1":
        OUT = ROOT / "evidence/generated/vitis/p10_1_hw_performance_runtime"
        ARTIFACTS = ROOT / "artifacts/p10_1"
        SUMMARY_JSON = (
            ROOT / "evidence/generated/p10_1_hw_ps_runtime_build_summary.json"
        )
        SUMMARY_MD = (
            ROOT / "evidence/generated/p10_1_hw_ps_runtime_build_summary.md"
        )
        FUNCTIONAL_OUT = (
            ROOT / "evidence/generated/vivado/p10_1_hw_performance"
        )
        TEST_ID = "P10_1-HW-AX7020-DUAL-PS-RUNTIME-BUILD"
        SUMMARY_TITLE = "P10.1 hardware-performance AX7020 PS runtime build"
        return
    if campaign == "p10_1r":
        OUT = ROOT / "evidence/generated/vitis/p10_1r_runtime"
        ARTIFACTS = ROOT / "artifacts/p10_1r"
        SUMMARY_JSON = ROOT / "evidence/generated/p10_1r_ps_runtime_build_summary.json"
        SUMMARY_MD = ROOT / "evidence/generated/p10_1r_ps_runtime_build_summary.md"
        FUNCTIONAL_OUT = ROOT / "evidence/generated/vivado/p10_1r"
        TEST_ID = "P10_1R-AX7020-DUAL-PS-RUNTIME-BUILD"
        SUMMARY_TITLE = "P10.1R AX7020 role-bound PS runtime build"
        return
    if campaign == "p10_2":
        OUT = ROOT / "evidence/generated/vitis/p10_2_4lane_runtime"
        ARTIFACTS = ROOT / "artifacts/p10_2"
        SUMMARY_JSON = ROOT / "evidence/generated/p10_2_ps_runtime_build_summary.json"
        SUMMARY_MD = ROOT / "evidence/generated/p10_2_ps_runtime_build_summary.md"
        FUNCTIONAL_OUT = ROOT / "evidence/generated/vivado/p10_2_4lane"
        TEST_ID = "P10_2-AX7020-DUAL-4LANE-PS-RUNTIME-BUILD"
        SUMMARY_TITLE = "P10.2 AX7020 role-bound four-lane PS runtime build"
        ROLES = {
            "fixed": {
                "role_value": 1,
                "header": ROOT / "board_profiles/ax7020_fixed_4lane/p10_runtime_role.h",
            },
            "rotating": {
                "role_value": 2,
                "header": ROOT / "board_profiles/ax7020_rotating_4lane/p10_runtime_role.h",
            },
        }
        return
    if campaign == "p10_3":
        OUT = ROOT / "evidence/generated/vitis/p10_3_4lane_runtime"
        ARTIFACTS = ROOT / "artifacts/p10_3"
        SUMMARY_JSON = ROOT / "evidence/generated/p10_3_ps_runtime_build_summary.json"
        SUMMARY_MD = ROOT / "evidence/generated/p10_3_ps_runtime_build_summary.md"
        FUNCTIONAL_OUT = ROOT / "evidence/generated/vivado/p10_3_4lane"
        TEST_ID = "P10_3-AX7020-DUAL-4LANE-PS-RUNTIME-BUILD"
        SUMMARY_TITLE = "P10.3 AX7020 role-bound four-lane PS runtime build"
        ROLES = {
            "fixed": {
                "role_value": 1,
                "header": ROOT / "board_profiles/ax7020_fixed_4lane/p10_3_runtime_role.h",
            },
            "rotating": {
                "role_value": 2,
                "header": ROOT / "board_profiles/ax7020_rotating_4lane/p10_3_runtime_role.h",
            },
        }
        return
    if campaign == "p10_3f":
        OUT = ROOT / "evidence/generated/vitis/p10_3_fault_forensics_runtime"
        ARTIFACTS = ROOT / "artifacts/p10_3_fault_forensics"
        SUMMARY_JSON = ROOT / "evidence/generated/p10_3_fault_forensics_ps_runtime_build_summary.json"
        SUMMARY_MD = ROOT / "evidence/generated/p10_3_fault_forensics_ps_runtime_build_summary.md"
        FUNCTIONAL_OUT = ROOT / "evidence/generated/vivado/p10_3_fault_forensics"
        TEST_ID = "P10_3F-AX7020-DUAL-4LANE-PS-RUNTIME-BUILD"
        SUMMARY_TITLE = "P10.3F AX7020 role-bound first-fault PS runtime build"
        ROLES = {
            "fixed": {
                "role_value": 1,
                "header": ROOT / "board_profiles/ax7020_fixed_4lane/p10_3f_runtime_role.h",
            },
            "rotating": {
                "role_value": 2,
                "header": ROOT / "board_profiles/ax7020_rotating_4lane/p10_3f_runtime_role.h",
            },
        }
        return
    if campaign != "p10_1_led":
        raise ValueError(f"unsupported campaign: {campaign}")
    OUT = ROOT / "evidence/generated/vitis/p10_1_ax7020_pl_activity_led_runtime"
    ARTIFACTS = ROOT / "artifacts/p10_1_led"
    SUMMARY_JSON = ROOT / "evidence/generated/p10_1_ax7020_pl_activity_led_runtime_build_summary.json"
    SUMMARY_MD = ROOT / "evidence/generated/p10_1_ax7020_pl_activity_led_runtime_build_summary.md"
    FUNCTIONAL_OUT = ROOT / "evidence/generated/vivado/p10_1_ax7020_pl_activity_led"
    TEST_ID = "P10_1-AX7020-PL-ACTIVITY-LED-DUAL-PS-RUNTIME-BUILD"
    SUMMARY_TITLE = "P10.1 AX7020 PL activity LED role-bound PS runtime build"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def tracked_source_dirty(paths: list[Path]) -> bool:
    return bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no", "--",
         *[rel(path) for path in paths]], cwd=ROOT, text=True))


def deterministic_zip(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            name = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def freeze(path: Path, bundle: str) -> dict[str, Any]:
    digest = sha256(path)
    namespace = (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        if CAMPAIGN in {"p10_1", "p10_1r", "p10_3", "p10_3f"}
        else bundle
    )
    destination = ARTIFACTS / namespace / digest / path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) != digest:
        raise RuntimeError(f"content-address collision: {destination}")
    if not destination.exists():
        shutil.copy2(path, destination)
    if sha256(destination) != digest:
        raise RuntimeError(f"frozen artifact hash mismatch: {destination}")
    destination.chmod(stat.S_IREAD)
    return {"path": rel(destination), "sha256": digest,
            "bytes": destination.stat().st_size, "read_only": True}


def run(command: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=timeout,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )


def bundle_hash(role: str, header: Path, xsa: Path) -> tuple[str, dict[str, str]]:
    paths = [*SOURCES, header, xsa]
    if CAMPAIGN in {"p10_2", "p10_3", "p10_3f"}:
        paths.append(P10_3_GOAL if CAMPAIGN in {"p10_3", "p10_3f"} else P10_2_GOAL)
    if CAMPAIGN in {"p10_3", "p10_3f"}:
        paths.extend([
            ROOT / "config/hardware/p10_3_actual_wiring.yaml",
            ROOT / "config/hardware/tfdu_module_inventory.yaml",
            ROOT / "docs/hardware/P10_3_AS_WIRED_RECORD.md",
            ROOT / "config/hardware/p10_3_ax7020_activity_leds.yaml",
            ROOT / "docs/hardware/P10_3_AX7020_ACTIVITY_LED_DESIGN.md",
        ])
    if CAMPAIGN == "p10_3f":
        paths.extend(P10_3F_PROVENANCE)
    if CAMPAIGN == "p10_1":
        paths.extend(P10_1_PROVENANCE)
    elif CAMPAIGN == "p10_1r":
        paths.extend(P10_1R_PROVENANCE)
        paths.append(P10_1R_GOAL)
    hashes = {rel(path): sha256(path) for path in paths}
    if CAMPAIGN == "p10_1":
        hashes[str(P10_1_HW_GOAL)] = sha256(P10_1_HW_GOAL)
    payload = json.dumps({"campaign": CAMPAIGN, "role": role, "inputs": hashes},
                         sort_keys=True,
                         separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest(), hashes


def inspect_elf(role: str, elf: Path, out: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    inspection: dict[str, Any] = {}
    end_address: int | None = None
    for name, executable, arguments in (
        ("size", TOOLCHAIN / "arm-none-eabi-size.exe", ["-A", str(elf)]),
        ("symbols", TOOLCHAIN / "arm-none-eabi-nm.exe", ["-n", str(elf)]),
        ("sections", TOOLCHAIN / "arm-none-eabi-objdump.exe", ["-h", str(elf)]),
    ):
        result = run([str(executable), *arguments], 120)
        path = out / f"p10_{role}_runtime_{name}.txt"
        inspection_text = "\n".join(
            line.rstrip()
            for line in (result.stdout + "\n" + result.stderr).splitlines()
        ) + "\n"
        path.write_text(inspection_text, encoding="utf-8", errors="replace",
                        newline="\n")
        inspection[name] = {"returncode": result.returncode, "path": rel(path),
                            "sha256": sha256(path)}
        if result.returncode != 0:
            errors.append(f"{name} inspection failed")
        if name == "symbols":
            for line in result.stdout.splitlines():
                fields = line.split()
                if len(fields) >= 3 and fields[-1] == "_end":
                    end_address = int(fields[0], 16)
    inspection["elf_end_address"] = None if end_address is None else f"0x{end_address:08X}"
    inspection["ocm_boundary"] = "0x00020000"
    if end_address is None or end_address >= 0x00020000:
        errors.append(f"ELF exceeds OCM boundary: {end_address}")
    return inspection, errors


def run_role(role: str, cfg: dict[str, Any]) -> dict[str, Any]:
    role_out = OUT / role
    role_out.mkdir(parents=True, exist_ok=True)
    xsa = FUNCTIONAL_OUT / role / f"p10_ax7020_{role}_functional.xsa"
    workspace = Path(f"C:/p10_vitis/{CAMPAIGN}_{role}")
    platform = workspace / f"p10_{role}_platform"
    app = workspace / f"p10_{role}_runtime"
    elf = app / "Debug" / f"p10_{role}_runtime.elf"
    map_file = app / "Debug" / f"p10_{role}_runtime.map"
    bsp = platform / "ps7_cortexa9_0/standalone_domain/bsp"
    system_mss = bsp / "system.mss"
    xparameters = bsp / "ps7_cortexa9_0/include/xparameters.h"
    ps7_parameters = platform / "zynq_fsbl/ps7_parameters.xml"
    platform_xsa = platform / "hw" / xsa.name
    ps7_init_tcl = platform / "hw/ps7_init.tcl"
    command = [str(XSCT), str(TCL), str(ROOT), role, str(xsa), CAMPAIGN]
    result = run(command)
    log = role_out / f"p10_{role}_runtime_build.log"
    log.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"RETURN_CODE={result.returncode}\nSTDOUT_BEGIN\n{result.stdout}\nSTDOUT_END\n" +
        f"STDERR_BEGIN\n{result.stderr}\nSTDERR_END\n",
        encoding="utf-8", errors="replace", newline="\n",
    )
    required = [xsa, elf, map_file, system_mss, xparameters, ps7_parameters,
                platform_xsa, ps7_init_tcl]
    errors = [f"missing {path}" for path in required if not path.is_file()]
    if result.returncode != 0 or "P10_PS_RUNTIME_BUILD=PASS" not in result.stdout or \
            f"P10_PS_RUNTIME_ROLE={role}" not in result.stdout:
        errors.append(f"XSCT runtime build failed rc={result.returncode}")
    inspection: dict[str, Any] = {}
    if elf.is_file():
        inspection, inspect_errors = inspect_elf(role, elf, role_out)
        errors.extend(inspect_errors)
    xparam_text = xparameters.read_text(encoding="utf-8", errors="replace") \
        if xparameters.is_file() else ""
    xparam_checks = {
        "dma_device": bool(re.search(r"#define\s+XPAR_AXI_DMA_0_DEVICE_ID\s+0", xparam_text)),
        "dma_base": bool(re.search(r"#define\s+XPAR_AXIDMA_0_BASEADDR\s+0x40400000", xparam_text)),
        "dma_sg_width": bool(re.search(r"#define\s+XPAR_AXI_DMA_0_SG_LENGTH_WIDTH\s+26", xparam_text)),
        "endpoint_base": bool(re.search(r"#define\s+XPAR_P10_ENDPOINT_0_BASEADDR\s+0x43C00000", xparam_text)),
    }
    if CAMPAIGN in {"p10_3", "p10_3f"}:
        xparam_checks.update({
            "ps_gpio_device": bool(re.search(
                r"#define\s+XPAR_PS7_GPIO_0_DEVICE_ID\s+0", xparam_text)),
            "ps_gpio_canonical_alias": bool(re.search(
                r"#define\s+XPAR_XGPIOPS_0_DEVICE_ID\s+"
                r"XPAR_PS7_GPIO_0_DEVICE_ID", xparam_text)),
            "ps_gpio_base": bool(re.search(
                r"#define\s+XPAR_PS7_GPIO_0_BASEADDR\s+0xE000A000", xparam_text)),
        })
    errors.extend(f"xparameters check failed: {key}" for key, ok in xparam_checks.items() if not ok)
    mss_text = system_mss.read_text(encoding="utf-8", errors="replace") \
        if system_mss.is_file() else ""
    mss_checks = {}
    if CAMPAIGN in {"p10_3", "p10_3f"}:
        mss_checks = {
            "gpiops_driver": bool(re.search(
                r"DRIVER_NAME\s*=\s*gpiops[\s\S]*?HW_INSTANCE\s*=\s*ps7_gpio_0",
                mss_text,
            )),
        }
        errors.extend(f"system.mss check failed: {key}"
                      for key, ok in mss_checks.items() if not ok)
    parameters_text = ps7_parameters.read_text(encoding="utf-8", errors="replace") \
        if ps7_parameters.is_file() else ""
    ps_checks = {
        "ddr_part": "MT41J256M16 RE-125" in parameters_text,
        "ddr_frequency": "533.333333" in parameters_text,
        "ddr_width": "32 Bit" in parameters_text,
        "crystal": "33.333333" in parameters_text,
    }
    errors.extend(f"PS7 parameter check failed: {key}" for key, ok in ps_checks.items() if not ok)
    if platform_xsa.is_file() and xsa.is_file() and sha256(platform_xsa) != sha256(xsa):
        errors.append("Vitis platform XSA differs from source XSA")
    bsp_zip = role_out / f"p10_ax7020_{role}_bsp.zip"
    if bsp.is_dir():
        deterministic_zip(bsp, bsp_zip)
        first = sha256(bsp_zip)
        deterministic_zip(bsp, bsp_zip)
        if sha256(bsp_zip) != first:
            errors.append("BSP archive is not deterministic")
    else:
        errors.append("BSP directory missing")
    bundle, input_hashes = bundle_hash(role, cfg["header"], xsa) if xsa.is_file() else ("NONE", {})
    frozen = {}
    if not errors:
        frozen = {"elf": freeze(elf, bundle), "bsp": freeze(bsp_zip, bundle)}
    return {
        "role": role, "role_value": cfg["role_value"],
        "status": "PASS" if not errors else "FAIL",
        "source_bundle_sha256": bundle, "source_sha256": input_hashes,
        "xsa": {"path": rel(xsa), "sha256": sha256(xsa)} if xsa.is_file() else None,
        "xparameters_checks": xparam_checks, "system_mss_checks": mss_checks,
        "ps7_parameter_checks": ps_checks,
        "inspection": inspection, "artifacts": frozen,
        "build_log": rel(log), "build_log_sha256": sha256(log), "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign",
        choices=("p10", "p10_1_led", "p10_1", "p10_1r", "p10_2", "p10_3", "p10_3f"),
        default="p10",
        help="Use a separate source-XSA, artifact, and evidence namespace.",
    )
    args = parser.parse_args()
    configure_campaign(args.campaign)
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_RUNTIME_BUILD_REFUSED: offline environment required", file=sys.stderr)
        return 2
    if not XSCT.is_file():
        print(f"XSCT not found: {XSCT}", file=sys.stderr)
        return 2
    if CAMPAIGN == "p10_1" and (
        not P10_1_HW_GOAL.is_file()
        or sha256(P10_1_HW_GOAL) != P10_1_HW_GOAL_SHA256
    ):
        print(
            "P10_RUNTIME_BUILD_REFUSED: P10.1 hardware goal hash mismatch",
            file=sys.stderr,
        )
        return 2
    if CAMPAIGN == "p10_1r" and (
        not P10_1R_GOAL.is_file()
        or sha256(P10_1R_GOAL) != P10_1R_GOAL_SHA256
    ):
        print(
            "P10_RUNTIME_BUILD_REFUSED: P10.1R goal hash mismatch",
            file=sys.stderr,
        )
        return 2
    if CAMPAIGN == "p10_2" and (
        not P10_2_GOAL.is_file() or sha256(P10_2_GOAL) != P10_2_GOAL_SHA256
    ):
        print("P10_RUNTIME_BUILD_REFUSED: P10.2 goal hash mismatch", file=sys.stderr)
        return 2
    if CAMPAIGN in {"p10_3", "p10_3f"} and (
        not P10_3_GOAL.is_file() or sha256(P10_3_GOAL) != P10_3_GOAL_SHA256
    ):
        print("P10_RUNTIME_BUILD_REFUSED: P10.3 goal hash mismatch", file=sys.stderr)
        return 2
    source_worktree_dirty = tracked_source_dirty([
        *SOURCES,
        *(
            P10_1_PROVENANCE if CAMPAIGN == "p10_1"
            else [*P10_1R_PROVENANCE, P10_1R_GOAL]
            if CAMPAIGN == "p10_1r"
            else [P10_2_GOAL] if CAMPAIGN == "p10_2"
            else [
                P10_3_GOAL,
                ROOT / "config/hardware/p10_3_actual_wiring.yaml",
                ROOT / "config/hardware/tfdu_module_inventory.yaml",
                ROOT / "docs/hardware/P10_3_AS_WIRED_RECORD.md",
                ROOT / "config/hardware/p10_3_ax7020_activity_leds.yaml",
                ROOT / "docs/hardware/P10_3_AX7020_ACTIVITY_LED_DESIGN.md",
                *(P10_3F_PROVENANCE if CAMPAIGN == "p10_3f" else []),
            ] if CAMPAIGN in {"p10_3", "p10_3f"}
            else []
        ),
        *(cfg["header"] for cfg in ROLES.values()),
    ])
    OUT.mkdir(parents=True, exist_ok=True)
    native = run([
        str(HOST_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-Wl,--no-insert-timestamp",
        "-Isoftware/ps_driver", "tests/test_p9_crypto.c",
        "software/ps_driver/p9_crypto.c", "-o", str(OUT / "p10_crypto_test.exe")], 120)
    native_run = run([str(OUT / "p10_crypto_test.exe")], 30) if native.returncode == 0 else None
    native_pass = native_run is not None and native_run.returncode == 0 and \
        "P9_CRYPTO_PROTOCOL_TEST=PASS" in native_run.stdout
    results = [run_role(role, cfg) for role, cfg in ROLES.items()]
    status = "PASS" if native_pass and all(item["status"] == "PASS" for item in results) else "FAIL"
    summary = {
        "schema_version": 1, "test_id": TEST_ID, "campaign": CAMPAIGN,
        "status": status, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": source_worktree_dirty,
        "no_hardware": True, "current_run_hardware_authorization": False,
        "hardware_actions_executed": False, "network_used": False,
        "native_crypto_protocol_test": "PASS" if native_pass else "FAIL",
        "hardware_admission": False, "blocking_condition": "P10-SAFETY-POWERUP-001",
        "artifact_provenance": {
            "hardware_goal": {
                "path": (
                    str(P10_1_HW_GOAL) if CAMPAIGN == "p10_1"
                    else str(P10_1R_GOAL) if CAMPAIGN == "p10_1r"
                    else None
                ),
                "sha256": (
                    sha256(P10_1_HW_GOAL) if CAMPAIGN == "p10_1"
                    else sha256(P10_1R_GOAL) if CAMPAIGN == "p10_1r"
                    else None
                ),
            },
            "required_inputs": {
                rel(path): sha256(path)
                for path in (
                    P10_1_PROVENANCE if CAMPAIGN == "p10_1"
                    else P10_1R_PROVENANCE if CAMPAIGN == "p10_1r"
                    else []
                )
            }
            if CAMPAIGN in {"p10_1", "p10_1r"}
            else {},
        },
        "roles": results,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8", newline="\n")
    lines = [f"# {SUMMARY_TITLE}", "",
             f"- Status: `{status}`", "- Hardware actions executed: `false`",
             "- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.",
             "- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.", "",
             "| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |",
             "|---|---|---|---|---|"]
    for item in results:
        artifacts = item.get("artifacts", {})
        lines.append(
            f"| {item['role']} | {item['status']} | {item.get('inspection', {}).get('elf_end_address', 'NONE')} | "
            f"`{artifacts.get('elf', {}).get('sha256', 'NONE')}` | "
            f"`{artifacts.get('bsp', {}).get('sha256', 'NONE')}` |")
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_AX7020_DUAL_PS_RUNTIME_BUILD={status}")
    print(f"P10_PS_RUNTIME_BUILD_SUMMARY={rel(SUMMARY_JSON)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
