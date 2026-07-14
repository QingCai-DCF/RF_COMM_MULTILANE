#!/usr/bin/env python3
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

from tools.ax7010_ps7_board_contract import (  # noqa: E402
    EXPECTED_DEVICE,
    EXPECTED_PS7_PARAMETERS,
    validate_vivado_artifacts,
)

OUT = ROOT / "evidence/generated/vivado/p6_ps_candidate"
IMMUTABLE = ROOT / "evidence/hardware/p6/bitstreams"
BUILD = ROOT / "build/p6_ps_candidate"
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
EXPECTED_BOARD_CONFIGURATION = {
    "P6_PS7_DEVICE": EXPECTED_DEVICE,
    **{f"CONFIG.{key}": value for key, value in EXPECTED_PS7_PARAMETERS.items()},
    "P6_PS7_BOARD_CONFIGURATION": "PASS",
    "P6_PS7_DDR_CONFIGURATION": "PASS",
}
# Backward-compatible name used by earlier offline reports/tests.  It now
# represents the complete board contract rather than a four-field DDR subset.
EXPECTED_DDR_CONFIGURATION = EXPECTED_BOARD_CONFIGURATION


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_key_value_report(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or "=" not in line:
            raise ValueError(f"invalid key/value report line: {line!r}")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"invalid or duplicate key in report: {key!r}")
        values[key] = value
    return values


def _remove_cache_directory(path: Path, required_parent: Path) -> None:
    resolved = path.resolve()
    parent = required_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise RuntimeError(f"refusing unsafe cache removal: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _vivado_artifact_paths() -> dict[str, Path]:
    bd_root = BUILD / "project/p6_ps_candidate.srcs/sources_1/bd/p6_ps_system"
    generated_ip = (
        BUILD
        / "project/p6_ps_candidate.gen/sources_1/bd/p6_ps_system/ip"
        / "p6_ps_system_processing_system7_0_0"
    )
    return {
        "build_tcl": ROOT / "scripts/build_p6_ps_candidate.tcl",
        "xci": (
            bd_root
            / "ip/p6_ps_system_processing_system7_0_0"
            / "p6_ps_system_processing_system7_0_0.xci"
        ),
        "block_design": bd_root / "p6_ps_system.bd",
        "xsa": OUT / "p6_ps_candidate.xsa",
        "ps7_init_tcl": generated_ip / "ps7_init.tcl",
        "ps7_init_c": generated_ip / "ps7_init.c",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-bypass",
        action="store_true",
        help="delete only the declared P6 build cache before a real rebuild",
    )
    args = parser.parse_args(argv)
    if args.cache_bypass:
        _remove_cache_directory(BUILD, ROOT / "build")
    OUT.mkdir(parents=True, exist_ok=True)
    IMMUTABLE.mkdir(parents=True, exist_ok=True)
    log = OUT / "p6_ps_candidate_build.log"
    ddr_report = OUT / "p6_ps7_ddr_configuration.txt"
    board_contract_report = OUT / "p6_ps7_board_contract.json"
    for stale in (
        log,
        ddr_report,
        board_contract_report,
        OUT / "p6_ps_candidate.bit",
        OUT / "p6_ps_candidate.xsa",
        OUT / "p6_ps_candidate_build_markers.txt",
        OUT / "post_route_drc_p6_ps_candidate.rpt",
        OUT / "post_route_timing_summary_p6_ps_candidate.rpt",
        OUT / "post_route_utilization_p6_ps_candidate.rpt",
    ):
        stale.unlink(missing_ok=True)
    proc = subprocess.run(
        [str(VIVADO), "-mode", "batch", "-source", "scripts/build_p6_ps_candidate.tcl", "-tclargs", str(ROOT)],
        cwd=ROOT, text=True, capture_output=True, timeout=3600,
    )
    log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    bit = OUT / "p6_ps_candidate.bit"
    xsa = OUT / "p6_ps_candidate.xsa"
    timing = (OUT / "post_route_timing_summary_p6_ps_candidate.rpt").read_text(encoding="utf-8", errors="ignore") if (OUT / "post_route_timing_summary_p6_ps_candidate.rpt").exists() else ""
    drc = (OUT / "post_route_drc_p6_ps_candidate.rpt").read_text(encoding="utf-8", errors="ignore") if (OUT / "post_route_drc_p6_ps_candidate.rpt").exists() else ""
    timing_met = "All user specified timing constraints are met" in timing
    drc_clean = not bool(re.search(r"^\s*ERROR(?:\s|:)", drc, re.MULTILINE | re.IGNORECASE))
    ddr_configuration: dict[str, str] = {}
    if ddr_report.is_file():
        try:
            ddr_configuration = read_key_value_report(ddr_report)
        except ValueError:
            ddr_configuration = {}
    ddr_configuration_verified = ddr_configuration == EXPECTED_BOARD_CONFIGURATION
    contract = validate_vivado_artifacts(**_vivado_artifact_paths())
    board_contract_report.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    board_contract_verified = contract["status"] == "PASS"
    passed = (
        proc.returncode == 0
        and bit.exists()
        and xsa.exists()
        and timing_met
        and drc_clean
        and ddr_configuration_verified
        and board_contract_verified
    )
    artifacts = {}
    for kind, source in (("bit", bit), ("xsa", xsa)):
        if source.exists():
            artifact_sha = digest(source)
            record = {"source": rel(source), "sha256": artifact_sha, "immutable": None}
            if passed:
                immutable = IMMUTABLE / (
                    f"p6_ps_dynamic_transport_{artifact_sha}.{source.suffix.lstrip('.')}"
                )
                if immutable.exists() and digest(immutable) != artifact_sha:
                    raise RuntimeError(f"immutable P6 artifact path collision: {immutable}")
                shutil.copy2(source, immutable)
                record["immutable"] = rel(immutable)
            artifacts[kind] = record
    summary = {
        "P6_PS_CANDIDATE_BUILD": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "returncode": proc.returncode,
        "timing_met": timing_met,
        "drc_clean": drc_clean,
        "cache_bypass": args.cache_bypass,
        "ps7_ddr_configuration_verified": ddr_configuration_verified,
        "ps7_board_contract_verified": board_contract_verified,
        "ps7_ddr_configuration": ddr_configuration,
        "ps7_ddr_configuration_report": (
            None
            if not ddr_report.is_file()
            else {
                "path": rel(ddr_report),
                "sha256": digest(ddr_report),
            }
        ),
        "ps7_board_contract_report": {
            "path": rel(board_contract_report),
            "sha256": digest(board_contract_report),
            "status": contract["status"],
        },
        "artifacts": artifacts,
        "inputs": {
            "active_xdc": {
                "path": "constraints/active/PORT1.generated.xdc",
                "sha256": digest(ROOT / "constraints/active/PORT1.generated.xdc"),
            },
            "pinmap": {
                "path": "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
                "sha256": digest(ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"),
            },
            "active_profile": {
                "path": "board_profiles/ACTIVE_PROFILE.json",
                "sha256": digest(ROOT / "board_profiles/ACTIVE_PROFILE.json"),
            },
            "register_map": {
                "path": "config/register_map/ir_axi_regs.yaml",
                "sha256": digest(ROOT / "config/register_map/ir_axi_regs.yaml"),
            },
        },
        "axi_base": "0x43c00000",
        "ethernet_used": False,
        "motion_used": False,
    }
    (OUT / "p6_ps_candidate_build_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
