#!/usr/bin/env python3
"""Fail-closed P8E source-manifest and layered-XDC lint."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "config/p8e_build_matrix.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    matrix = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    manifests: list[dict] = []
    common_core = matrix.get("common_source_core")
    if common_core != "rtl/top/ir_endpoint_core.sv":
        errors.append("common_source_core changed or missing")

    clock_definitions: dict[str, list[str]] = {}
    artifact_hashes: list[dict[str, str]] = []
    implementation_profiles = matrix.get("profiles", [])
    for profile in implementation_profiles:
        manifest_path = ROOT / profile["source_manifest"]
        if not manifest_path.is_file():
            errors.append(f"missing manifest {profile['source_manifest']}")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests.append(manifest)
        if manifest.get("profile_id") != profile["profile_id"]:
            errors.append(f"{profile['profile_id']}: manifest profile mismatch")
        if manifest.get("part") != profile["part"] or manifest.get("top_module") != profile["top_module"]:
            errors.append(f"{profile['profile_id']}: part/top mismatch")
        sources = manifest.get("source_order", [])
        if common_core not in sources:
            errors.append(f"{profile['profile_id']}: common core absent")
        if len(sources) != len(set(sources)):
            errors.append(f"{profile['profile_id']}: duplicate source entry")
        for source in sources:
            source_path = ROOT / source
            if not source_path.is_file():
                errors.append(f"{profile['profile_id']}: missing source {source}")
            if source.startswith(("legacy/", "rtl/legacy_reference/", "docs/legacy/")):
                errors.append(f"{profile['profile_id']}: legacy source active {source}")
        constraints = manifest.get("constraints", [])
        for constraint in constraints:
            path = ROOT / constraint
            if not path.is_file():
                errors.append(f"{profile['profile_id']}: missing XDC {constraint}")
                continue
            text = path.read_text(encoding="utf-8", errors="strict")
            active_text = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
            artifact_hashes.append({"path": constraint, "sha256": sha256(path)})
            for match in re.finditer(r"create_clock\s+-name\s+(\S+)", text):
                clock_definitions.setdefault(match.group(1), []).append(constraint)
            if constraint.startswith("constraints/core/") and re.search(
                    r"\b(?:PACKAGE_PIN|LOC|IOSTANDARD)\b", active_text):
                errors.append(f"core XDC contains board property: {constraint}")
            if constraint.startswith("constraints/profile/") and re.search(
                    r"\b(?:PACKAGE_PIN|LOC|IOSTANDARD)\b", active_text):
                errors.append(f"profile XDC contains board property: {constraint}")
            if re.search(r"set_false_path[^\n]*(?:all_clocks|all_registers)", active_text, re.I):
                errors.append(f"broad false path in {constraint}")
            if re.search(r"set_(?:max|min)_delay[^\n]*(?:all_clocks|all_registers)", active_text, re.I):
                errors.append(f"broad max/min delay in {constraint}")
        is_z7020 = profile["part"].startswith("xc7z020")
        if is_z7020:
            if any("PORT1.generated.xdc" in item or item.startswith("constraints/board/")
                   for item in constraints):
                errors.append(f"{profile['profile_id']}: Z7010 board XDC contamination")
            if profile.get("board_pinmap") != "PENDING_D12" or profile.get("board_xdc") != "PENDING_D12":
                errors.append(f"{profile['profile_id']}: invented Z7020 board input")
            if any(re.search(r"\b(?:set_input_delay|set_output_delay)\b",
                             (ROOT / item).read_text(encoding="utf-8")) for item in constraints):
                errors.append(f"{profile['profile_id']}: invented Z7020 I/O delay")
        else:
            if "constraints/active/PORT1.generated.xdc" not in constraints:
                errors.append("Z7010 canonical board XDC absent")

    expected_clocks = {"protocol_clk", "axis_dma_clk", "axi_lite_clk"}
    if set(clock_definitions) != expected_clocks:
        errors.append(f"formal clock names mismatch: {sorted(clock_definitions)}")
    for name, paths in clock_definitions.items():
        unique = sorted(set(paths))
        if unique != ["constraints/core/common_clocks.xdc"]:
            errors.append(f"clock {name} duplicated outside common_clocks.xdc: {unique}")
    common_clock_text = (ROOT / "constraints/core/common_clocks.xdc").read_text(encoding="utf-8")
    for port, period in (("protocol_clk_i", "15.625"), ("axis_dma_clk_i", "10.000"),
                         ("axi_lite_clk_i", "20.000")):
        if not re.search(rf"create_clock[^\n]*-period\s+{re.escape(period)}[^\n]*{port}", common_clock_text):
            errors.append(f"missing exact clock constraint for {port}")
    if re.search(r"^\s*if\s+\{", common_clock_text, re.MULTILINE):
        errors.append("Tcl flow control embedded in common XDC")
    cdc_text = (ROOT / "constraints/core/cdc_exceptions.xdc").read_text(encoding="utf-8")
    if "set_clock_groups -asynchronous" not in cdc_text:
        errors.append("exact asynchronous clock groups absent")
    if cdc_text.count("get_clocks") != 3:
        errors.append("asynchronous group must name exactly the three formal clocks")

    # The same ordered core source set, up to role/board wrappers, proves that
    # the fixed/rotating profiles do not maintain divergent core forks.
    common_required = {
        "rtl/top/ir_endpoint_core.sv", "rtl/ir_data_plane_top.sv",
        "rtl/ir_tfdu_safety_endpoint.sv", "rtl/platform/axi_dma_adapter.sv",
    }
    for manifest in manifests:
        if not common_required.issubset(set(manifest.get("source_order", []))):
            errors.append(f"{manifest.get('profile_id')}: common-source set incomplete")

    status = "PASS" if not errors else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": "P8E-CONSTRAINT-SOURCE-MANIFEST-LINT",
        "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "status": status,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "matrix_sha256": sha256(MATRIX),
        "formal_clocks": clock_definitions,
        "manifest_count": len(manifests),
        "common_source_core": common_core,
        "z7010_xdc_isolated": not any("contamination" in error for error in errors),
        "z7020_board_pin_freeze": "PENDING_D12",
        "z7020_board_io_timing": "PENDING_D12",
        "errors": errors,
        "warnings": warnings,
        "artifact_hashes": sorted(artifact_hashes, key=lambda item: item["path"]),
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"P8E_CONSTRAINT_AUDIT={status}")
    for error in errors:
        print(f"ERROR: {error}")
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
