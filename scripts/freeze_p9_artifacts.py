#!/usr/bin/env python3
"""Freeze the P9 Z7010 candidate/shutdown/PS artifacts by SHA-256.

This is an offline-only tool.  It never imports a hardware API, starts a
server, connects to JTAG, or programs a target.  It creates a deterministic BSP
archive, copies every official artifact into a content-addressed directory,
and derives the phase-2 authorization record from the current user grant.
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
ARTIFACT_ROOT = ROOT / "artifacts/p9"
GENERATED = ROOT / "evidence/generated"
PHASE1_AUTH = ROOT / "config/p9_current_run_authorization.json"
CANDIDATE = GENERATED / "vivado/p9_z7010_candidate"
SHUTDOWN = GENERATED / "vivado/p9_z7010_shutdown"
VITIS_WORKSPACE = ROOT / "build/p9_ps_vitis_workspace"
VITIS_OUT = GENERATED / "vitis/p9_ps_runtime"
EXPECTED_PART = "xc7z010clg400-1"
EXPECTED_PROFILE = "Z7010_2LANE_DEV"
EXPECTED_SCOPE = "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION"
EXPECTED_TOP = "p9_ps_system_wrapper"
EXPECTED_GOAL_SHA256 = "543c89cb2afc1c4787f8f7b70b07ad3580018da03bad89cdfe09b84b68bad1bf"
GOAL_FILE = Path(r"C:\Users\user\Downloads\P9_Z7010_STATIONARY_2LANE_HARDWARE_VALIDATION_GOAL.md")
FINAL_P8D = GENERATED / "p9_final_source_p8d/p8d_final_summary.json"
FINAL_P8D_REGRESSION = GENERATED / "p9_final_source_p8d/p8d_p0_p8c_regression_summary.json"
P9_REGRESSION = GENERATED / "p9_candidate_regression/p9_candidate_regression_summary.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def artifact(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def deterministic_zip(source: Path, destination: Path) -> None:
    files = sorted(item for item in source.rglob("*") if item.is_file())
    if not files:
        raise RuntimeError(f"BSP directory is empty: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for item in files:
            info = zipfile.ZipInfo(item.relative_to(source).as_posix(),
                                   date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100444 << 16
            archive.writestr(info, item.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)


def deterministic_zip_files(files: list[tuple[Path, str]], destination: Path) -> None:
    if not files:
        raise RuntimeError("deterministic file archive is empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for source, archive_name in sorted(files, key=lambda item: item[1]):
            if not source.is_file():
                raise RuntimeError(f"archive input missing: {source}")
            info = zipfile.ZipInfo(archive_name.replace("\\", "/"),
                                   date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100444 << 16
            archive.writestr(info, source.read_bytes(),
                             compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)


def windows_read_only(path: Path) -> bool:
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    if attributes:
        return bool(attributes & stat.FILE_ATTRIBUTE_READONLY)
    return (path.stat().st_mode & stat.S_IWUSR) == 0


def immutable_copy(source: Path, source_commit: str) -> dict[str, Any]:
    digest = sha256(source)
    destination = ARTIFACT_ROOT / source_commit / digest / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != digest:
            raise RuntimeError(f"content-addressed destination mismatch: {destination}")
    else:
        shutil.copy2(source, destination)
    if sha256(destination) != digest:
        raise RuntimeError(f"frozen copy verification failed: {destination}")
    destination.chmod(stat.S_IREAD)
    if not windows_read_only(destination):
        raise RuntimeError(f"frozen artifact is not read-only: {destination}")
    return {
        "logical_name": source.name,
        "source_path": rel(source),
        "path": rel(destination),
        "sha256": digest,
        "bytes": destination.stat().st_size,
        "read_only": True,
    }


def timing_values(report: Path) -> dict[str, float | None]:
    text = report.read_text(encoding="utf-8", errors="replace")
    marker = "| Design Timing Summary"
    if marker not in text:
        return {key: None for key in ("wns_ns", "tns_ns", "whs_ns", "ths_ns")}
    for line in text.split(marker, 1)[1].splitlines():
        fields = line.split()
        if len(fields) < 8:
            continue
        try:
            return {"wns_ns": float(fields[0]), "tns_ns": float(fields[1]),
                    "whs_ns": float(fields[4]), "ths_ns": float(fields[5])}
        except ValueError:
            continue
    return {key: None for key in ("wns_ns", "tns_ns", "whs_ns", "ths_ns")}


def parse_key_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def rule_summary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rules: list[dict[str, Any]] = []
    for match in re.finditer(
            r"^\|\s*([A-Z][A-Z0-9-]+)\s*\|\s*([^|]+?)\s*\|.*?\|\s*(\d+)\s*\|\s*$",
            text, re.MULTILINE):
        rules.append({"rule": match.group(1), "severity": match.group(2).strip(),
                      "violations": int(match.group(3))})
    severities: dict[str, int] = {}
    for rule in rules:
        key = str(rule["severity"]).upper()
        severities[key] = severities.get(key, 0) + int(rule["violations"])
    return {"rules": rules, "severities": severities,
            "critical": sum(value for key, value in severities.items()
                            if "CRITICAL" in key),
            "error": severities.get("ERROR", 0)}


def cdc_summary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    records = []
    for match in re.finditer(
            r"^(CDC-\d+)\s+(Info|Warning|Critical|Error)\s+(\d+)\s+(.+)$",
            text, re.MULTILINE | re.IGNORECASE):
        records.append({"id": match.group(1).upper(),
                        "severity": match.group(2).upper(),
                        "count": int(match.group(3)),
                        "description": match.group(4).strip()})
    allowed = {"CDC-3", "CDC-15"}
    unclassified = [record for record in records if record["id"] not in allowed]
    unsafe_multibit = [record for record in unclassified if record["count"] != 0]
    critical = sum(record["count"] for record in records
                   if record["severity"] in {"CRITICAL", "ERROR"})
    return {"records": records, "critical_or_error": critical,
            "unclassified": unclassified,
            "unsafe_multibit": unsafe_multibit}


def p9_build_inputs() -> list[Path]:
    relative = [
        "rtl/generated/tfdu_safety_config.svh",
        "rtl/generated/ir_register_map_defs.svh",
        "rtl/ir_seq_math_pkg.sv", "rtl/ir_health_weighted_scheduler.sv",
        "rtl/ir_selective_repeat_tx.sv", "rtl/ir_selective_repeat_rx.sv",
        "rtl/ir_ack_aggregator.sv", "rtl/ir_data_plane_top.sv",
        "rtl/ir_tfdu_exact_duty_accountant.sv",
        "rtl/ir_tfdu_physical_module_safety.sv", "rtl/tfdu_lane_phy.sv",
        "rtl/ir_4ppm_codec.sv", "rtl/p9_rate_4ppm_rx.sv",
        "rtl/p9_4ppm_frame_tx.sv", "rtl/p9_4ppm_frame_rx.sv",
        "rtl/p9_optical_transport_core.sv", "rtl/p6_axi_lite_bridge.sv",
        "rtl/p9_axi_dma_peripheral.sv", "rtl/p9_axi_dma_peripheral_bd.v",
        "rtl/p9_z7010_shutdown_top.v",
        "constraints/active/PORT1.generated.xdc",
        "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
        "board_profiles/ACTIVE_PROFILE.json",
        "config/register_map/ir_axi_regs.yaml",
        "config/register_map/generated/ir_regs.h",
        "config/p9_z7010_stationary_2lane.yaml",
        "config/p9_current_run_authorization.json",
        "config/p9_current_run_authorization.txt",
        "config/project_state.json", "config/project_requirements.yaml",
        "software/ps_driver/ir_regs.h", "software/ps_driver/p9_crypto.c",
        "software/ps_driver/p9_crypto.h", "software/ps_driver/p9_runtime_main.c",
        "software/ps_driver/p9_runtime_protocol.h",
        "tests/test_p9_crypto.c", "tests/test_p9_runner.py",
        "tools/ax7010_ps7_board_contract.py",
        "scripts/build_p9_z7010_candidate.tcl",
        "scripts/audit_p9_timing_checkpoint.tcl",
        "scripts/build_p9_z7010_shutdown.tcl",
        "scripts/build_p9_ps_runtime.py", "scripts/build_p9_ps_runtime.tcl",
        "scripts/build_p9_post_synth_core.tcl",
        "scripts/run_p9_candidate_regression.py",
        "scripts/update_p9_requirements_state.py",
        "scripts/test_p9_cli_fail_closed.py",
        "scripts/freeze_p9_artifacts.py", "scripts/p9_hardware_runtime.py",
        "scripts/run_p9_z7010_stationary_2lane.py",
        "scripts/hw/p9_hw_preflight.tcl", "scripts/hw/p9_program_shutdown.tcl",
        "scripts/hw/p9_xsdb_stage.tcl",
        "sim/tb/tb_p9_4ppm_frame_link.sv",
        "sim/tb/tb_p9_tfdu_fir_frame_link.sv",
        "sim/tb/tb_p9_optical_transport_core.sv",
        "sim/tb/tb_p9_post_synth_safety.sv",
        "tools/run_p9_z7010_stationary_2lane.ps1",
    ]
    return [ROOT / item for item in relative]


def validate_build(source_commit: str) -> tuple[list[Path], dict[str, Any]]:
    candidate_files = [
        CANDIDATE / "ir_p9_z7010_2lane_candidate.bit",
        CANDIDATE / "ir_p9_z7010_2lane.xsa",
        CANDIDATE / "post_route_p9_candidate.dcp",
        CANDIDATE / "post_route_timing_summary_p9_candidate.rpt",
        CANDIDATE / "post_route_drc_p9_candidate.rpt",
        CANDIDATE / "post_route_methodology_p9_candidate.rpt",
        CANDIDATE / "post_route_cdc_p9_candidate.rpt",
        CANDIDATE / "post_route_clock_interaction_p9_candidate.rpt",
        CANDIDATE / "post_route_utilization_p9_candidate.rpt",
        CANDIDATE / "p9_candidate_build_markers.txt",
        CANDIDATE / "timing_audit/check_timing_verbose.rpt",
        CANDIDATE / "timing_audit/unconstrained_paths.rpt",
    ]
    shutdown_files = [
        SHUTDOWN / "ir_p9_shutdown_z7010.bit",
        SHUTDOWN / "post_route_p9_shutdown.dcp",
        SHUTDOWN / "post_route_timing_summary_p9_shutdown.rpt",
        SHUTDOWN / "post_route_drc_p9_shutdown.rpt",
        SHUTDOWN / "post_route_utilization_p9_shutdown.rpt",
        SHUTDOWN / "p9_shutdown_build_markers.txt",
    ]
    elf = VITIS_WORKSPACE / "p9_runtime/Debug/p9_runtime.elf"
    elf_map = VITIS_WORKSPACE / "p9_runtime/Debug/p9_runtime.map"
    ps7_init = VITIS_WORKSPACE / "p9_platform/hw/ps7_init.tcl"
    runtime_summary = VITIS_OUT / "p9_ps_runtime_build_summary.json"
    regression_files = [FINAL_P8D, FINAL_P8D_REGRESSION, P9_REGRESSION,
                        GENERATED / "p9_offline_regression_summary.json",
                        GENERATED / "p9_p8e_baseline_recheck_summary.json"]
    post_synth_files: list[Path] = []
    if P9_REGRESSION.is_file():
        early_regression = json.loads(P9_REGRESSION.read_text(encoding="utf-8"))
        entries = early_regression.get("post_synth_artifacts", [])
        expected_names = {
            "post_synth_p9_core.dcp", "post_synth_p9_core_funcsim.v",
            "post_synth_timing_summary_p9_core.rpt",
            "post_synth_utilization_p9_core.rpt", "post_synth_drc_p9_core.rpt",
            "p9_post_synth_build_markers.txt",
        }
        if not isinstance(entries, list) or {Path(str(item.get("path", ""))).name
                for item in entries if isinstance(item, dict)} != expected_names:
            raise RuntimeError("P9 post-synthesis artifact set is incomplete")
        for item in entries:
            candidate = (ROOT / str(item["path"])).resolve()
            try:
                candidate.relative_to((GENERATED / "p9_candidate_regression/raw").resolve())
            except ValueError as exc:
                raise RuntimeError("P9 post-synthesis artifact escapes regression raw root") from exc
            if not candidate.is_file() or sha256(candidate) != str(item.get("sha256", "")):
                raise RuntimeError(f"P9 post-synthesis artifact hash mismatch: {candidate}")
            post_synth_files.append(candidate)
    required = (candidate_files + shutdown_files +
                [elf, elf_map, ps7_init, runtime_summary] + regression_files +
                post_synth_files)
    missing = [rel(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("missing freeze inputs: " + ", ".join(missing))

    candidate_markers = parse_key_values(candidate_files[-3])
    shutdown_markers = parse_key_values(shutdown_files[-1])
    runtime = json.loads(runtime_summary.read_text(encoding="utf-8"))
    timing = timing_values(candidate_files[3])
    drc = rule_summary(candidate_files[4])
    methodology = rule_summary(candidate_files[5])
    cdc = cdc_summary(candidate_files[6])
    check_text = candidate_files[-2].read_text(encoding="utf-8", errors="replace")
    unconstrained_match = re.search(
        r"checking unconstrained_internal_endpoints \((\d+)\)", check_text)
    no_clock_match = re.search(r"checking no_clock \((\d+)\)", check_text)
    errors: list[str] = []
    if candidate_markers.get("P9_CANDIDATE_BUILD") != "PASS":
        errors.append("candidate build marker missing")
    if candidate_markers.get("P9_PART") != EXPECTED_PART:
        errors.append("candidate part mismatch")
    if candidate_markers.get("P9_TOP") != EXPECTED_TOP:
        errors.append("candidate top mismatch")
    if candidate_markers.get("P9_CANONICAL_XDC") != \
            "constraints/active/PORT1.generated.xdc":
        errors.append("candidate canonical XDC marker mismatch")
    if candidate_markers.get("P9_DMA_SG_STSCNTRL_STREAM") != "DISABLED":
        errors.append("candidate unused DMA SG control/status stream is not disabled")
    if candidate_markers.get("P9_STREAM_RESET_DOMAINS") != \
            "PROTOCOL64_DMA100_AXIL50":
        errors.append("candidate coordinated stream/DMA reset marker mismatch")
    for marker in ("P9_DRC_CRITICAL_COUNT", "P9_DRC_ERROR_COUNT",
                   "P9_REQP_1839_COUNT", "P9_METHODOLOGY_CRITICAL_COUNT",
                   "P9_CDC_CRITICAL_COUNT"):
        if candidate_markers.get(marker) != "0":
            errors.append(f"candidate signoff marker is not zero: {marker}")
    if shutdown_markers.get("P9_SHUTDOWN_BUILD") != "PASS":
        errors.append("shutdown build marker missing")
    if shutdown_markers.get("P9_SHUTDOWN_TXD_INTENT") != "0x0" or \
            shutdown_markers.get("P9_SHUTDOWN_SD_INTENT") != "0xF":
        errors.append("shutdown output intent mismatch")
    if runtime.get("status") != "PASS":
        errors.append("PS runtime build is not PASS")
    if any(timing[key] is None for key in timing):
        errors.append("timing values unavailable")
    elif timing["wns_ns"] < 0 or timing["whs_ns"] < 0 or \
            abs(timing["tns_ns"]) > 1e-9 or abs(timing["ths_ns"]) > 1e-9:
        errors.append("candidate timing closure failed")
    unconstrained = int(unconstrained_match.group(1)) if unconstrained_match else None
    if unconstrained != 0:
        errors.append("unconstrained internal endpoint audit failed")
    no_clock = int(no_clock_match.group(1)) if no_clock_match else None
    if no_clock != 0:
        errors.append("no-clock register/latch pin audit failed")
    if drc["critical"] != 0 or drc["error"] != 0:
        errors.append("DRC critical/error count is nonzero")
    if any(rule["rule"] == "REQP-1839" and rule["violations"] != 0
           for rule in drc["rules"]):
        errors.append("REQP-1839 count is nonzero")
    if methodology["critical"] != 0 or methodology["error"] != 0:
        errors.append("methodology critical/error count is nonzero")
    if cdc["critical_or_error"] != 0 or cdc["unclassified"] or cdc["unsafe_multibit"]:
        errors.append("CDC critical/unclassified/unsafe-multibit count is nonzero")
    if re.search(r"\b(?:unsafe|unclassified)\b", candidate_files[7].read_text(
            encoding="utf-8", errors="replace"), re.IGNORECASE):
        errors.append("clock interaction report contains unsafe/unclassified crossing")

    build_tcl = (ROOT / "scripts/build_p9_z7010_candidate.tcl").read_text(
        encoding="utf-8", errors="replace")
    # Audit commands that can actually load an XDC.  A plain text marker also
    # records the canonical XDC path, but it is evidence output rather than a
    # constraint input and must not be counted as a second loaded file.
    xdc_load_commands = [
        line.strip()
        for line in build_tcl.splitlines()
        if re.match(r"^\s*(?:read_xdc|add_files)\b", line, re.IGNORECASE)
        and re.search(r"\.xdc(?:\s|\"|$)", line, re.IGNORECASE)
    ]
    expected_xdc_command = 'read_xdc "$root_dir/constraints/active/PORT1.generated.xdc"'
    if xdc_load_commands != [expected_xdc_command]:
        errors.append(
            "candidate build XDC load commands are not canonical-only: "
            f"{xdc_load_commands}"
        )
    if build_tcl.count("CONFIG.c_sg_include_stscntrl_strm {0}") != 1 or \
            "CONFIG.c_sg_include_stscntrl_strm {1}" in build_tcl:
        errors.append("candidate DMA SG control/status stream configuration is not fail-closed")

    input_paths = p9_build_inputs()
    missing_inputs = [rel(path) for path in input_paths if not path.is_file()]
    if missing_inputs:
        errors.append("build inputs missing: " + ", ".join(missing_inputs))
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", source_commit, "--",
         *[rel(path) for path in input_paths]], cwd=ROOT, text=True).splitlines()
    if changed:
        errors.append("build inputs differ from source commit: " + ", ".join(changed))
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *[rel(path) for path in input_paths]],
        cwd=ROOT, text=True).splitlines()
    if dirty:
        errors.append("build inputs are not clean at freeze: " + ", ".join(dirty))

    regression = json.loads(P9_REGRESSION.read_text(encoding="utf-8"))
    p8d = json.loads(FINAL_P8D.read_text(encoding="utf-8"))
    p8d_regression = json.loads(FINAL_P8D_REGRESSION.read_text(encoding="utf-8"))
    for name, record in (("P9 candidate regression", regression),
                         ("P8D final regression", p8d),
                         ("P8B/P8C descendant regression", p8d_regression)):
        if record.get("status") != "PASS":
            errors.append(f"{name} is not PASS")
    if regression.get("source_commit") != source_commit or \
            p8d.get("P8D_SOURCE_COMMIT", p8d.get("source_commit")) != source_commit or \
            p8d_regression.get("source_commit") != source_commit:
        errors.append("regression source commit does not equal frozen source")
    if not GOAL_FILE.is_file() or sha256(GOAL_FILE) != EXPECTED_GOAL_SHA256:
        errors.append("P9 goal file missing or SHA-256 mismatch")
    if errors:
        raise RuntimeError("; ".join(errors))
    audit = {
        "timing": timing,
        "unconstrained_internal_endpoints": unconstrained,
        "no_clock_register_pins": no_clock,
        "drc": drc,
        "methodology": methodology,
        "cdc": cdc,
        "candidate_markers": candidate_markers,
        "shutdown_markers": shutdown_markers,
        "runtime_status": runtime.get("status"),
        "regression_status": {
            "p9_candidate": regression.get("status"),
            "p8d": p8d.get("status"),
            "p8b_p8c": p8d_regression.get("status"),
        },
        "build_input_sha256": {rel(path): sha256(path) for path in input_paths},
    }
    return required, audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", default="HEAD")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--phase1-authorization", type=Path, default=PHASE1_AUTH)
    args = parser.parse_args(argv)

    source_commit = git("rev-parse", args.source_commit)
    if source_commit != git("rev-parse", "HEAD"):
        raise SystemExit("frozen source commit must equal HEAD")
    required, build_audit = validate_build(source_commit)

    bsp = VITIS_WORKSPACE / "p9_platform/ps7_cortexa9_0/standalone_domain/bsp/ps7_cortexa9_0"
    bsp_archive = VITIS_OUT / "p9_ps7_bsp_deterministic.zip"
    deterministic_zip(bsp, bsp_archive)
    first_bsp_hash = sha256(bsp_archive)
    deterministic_zip(bsp, bsp_archive)
    if sha256(bsp_archive) != first_bsp_hash:
        raise SystemExit("deterministic BSP archive self-check failed")

    source_manifest_path = VITIS_OUT / "p9_source_input_manifest.json"
    write_json(source_manifest_path, {
        "schema_version": 1, "status": "PASS", "source_commit": source_commit,
        "goal_path": str(GOAL_FILE), "goal_sha256": sha256(GOAL_FILE),
        "inputs": [{"path": rel(path), "sha256": sha256(path),
                    "bytes": path.stat().st_size}
                   for path in p9_build_inputs()],
    })

    runner_files = [(path, rel(path)) for path in p9_build_inputs()
                    if rel(path).startswith(("scripts/", "tools/", "config/",
                                             "software/ps_driver/", "rtl/generated/"))]
    runner_files.append((GOAL_FILE, f"goal/{GOAL_FILE.name}"))
    runner_archive = VITIS_OUT / "p9_host_jtag_runner_deterministic.zip"
    deterministic_zip_files(runner_files, runner_archive)
    runner_hash = sha256(runner_archive)
    deterministic_zip_files(runner_files, runner_archive)
    if sha256(runner_archive) != runner_hash:
        raise SystemExit("deterministic host/JTAG runner archive self-check failed")

    official = list(required) + [
        bsp_archive, runner_archive, source_manifest_path,
        ROOT / "config/p9_z7010_stationary_2lane.yaml",
        ROOT / "config/p9_current_run_authorization.json",
        ROOT / "config/p9_current_run_authorization.txt",
        ROOT / "software/ps_driver/ir_regs.h",
        ROOT / "rtl/generated/ir_register_map_defs.svh",
    ]
    official = list(dict.fromkeys(path.resolve() for path in official))
    frozen = [immutable_copy(path, source_commit) for path in official]
    by_name = {item["logical_name"]: item for item in frozen}
    candidate_hash = by_name["ir_p9_z7010_2lane_candidate.bit"]["sha256"]
    run_id = args.run_id or (
        f"p9_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_"
        f"{source_commit[:12]}_{candidate_hash[:12]}")
    if not re.fullmatch(r"p9_[A-Za-z0-9_.-]+", run_id):
        raise SystemExit(f"invalid run id: {run_id}")

    report_paths = [path for path in required if path.suffix.lower() in
                    {".rpt", ".txt", ".json"}]
    manifest = {
        "schema_version": 2,
        "status": "PASS",
        "test_id": "P9-02-IMMUTABLE-ARTIFACT-FREEZE",
        "run_id": run_id,
        "generated_utc": now(),
        "source_commit": source_commit,
        "part": EXPECTED_PART,
        "top": EXPECTED_TOP,
        "profile": EXPECTED_PROFILE,
        "scope": EXPECTED_SCOPE,
        "vivado_version": "2023.1",
        "vitis_version": "2023.1",
        "register_map_sha256": sha256(ROOT / "config/register_map/ir_axi_regs.yaml"),
        "pinmap_sha256": sha256(ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"),
        "xdc_sha256": sha256(ROOT / "constraints/active/PORT1.generated.xdc"),
        "goal_sha256": sha256(GOAL_FILE),
        "source_manifest": artifact(source_manifest_path),
        "build_commands": [
            "vivado -mode batch -source scripts/build_p9_z7010_candidate.tcl",
            "vivado -mode batch -source scripts/audit_p9_timing_checkpoint.tcl",
            "vivado -mode batch -source scripts/build_p9_z7010_shutdown.tcl",
            "python scripts/build_p9_ps_runtime.py",
            "python scripts/run_p9_candidate_regression.py --source-commit <commit>",
        ],
        "build_audit": build_audit,
        "artifacts": frozen,
        "reports": [artifact(path) for path in report_paths],
    }
    run_dir = ARTIFACT_ROOT / run_id
    manifest_path = run_dir / "artifact_manifest.json"
    write_json(manifest_path, manifest)
    manifest_hash = sha256(manifest_path)

    auth = json.loads(args.phase1_authorization.read_text(encoding="utf-8"))
    errors = []
    if auth.get("authorized") is not True: errors.append("phase1 authorization false")
    if auth.get("scope") != EXPECTED_SCOPE: errors.append("phase1 scope mismatch")
    if auth.get("maximum_runtime_seconds") != 1800: errors.append("runtime must be 1800")
    if auth.get("maximum_lane_mask") != 3: errors.append("maximum lane mask must be 0x3")
    raw_auth = ROOT / str(auth.get("authorization_verbatim_utf8_path", ""))
    if not raw_auth.is_file() or sha256(raw_auth) != \
            auth.get("authorization_verbatim_utf8_sha256"):
        errors.append("verbatim UTF-8 authorization hash mismatch")
    if auth.get("user_reconfirmation_after_freeze_required") is not False:
        errors.append("phase1 record unexpectedly requires reconfirmation")
    if errors:
        raise SystemExit("; ".join(errors))
    phase2 = {**auth,
        "schema_version": 2,
        "artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND",
        "bound_utc": now(),
        "run_id": run_id,
        "stage_range": ["P9-04", "P9-26"],
        "source_commit": source_commit,
        "profile": EXPECTED_PROFILE,
        "part": EXPECTED_PART,
        "artifact_manifest_path": rel(manifest_path),
        "artifact_manifest_sha256": manifest_hash,
        "phase1_authorization_path": rel(args.phase1_authorization.resolve()),
        "phase1_authorization_sha256": sha256(args.phase1_authorization.resolve()),
        "candidate_bitstream": by_name["ir_p9_z7010_2lane_candidate.bit"],
        "shutdown_bitstream": by_name["ir_p9_shutdown_z7010.bit"],
        "ps_elf": by_name["p9_runtime.elf"],
        "ps7_init_tcl": by_name["ps7_init.tcl"],
        "bsp_archive": by_name["p9_ps7_bsp_deterministic.zip"],
        "runner_package": by_name["p9_host_jtag_runner_deterministic.zip"],
        "hardware_config": by_name["p9_z7010_stationary_2lane.yaml"],
        "generated_ps_header": by_name["ir_regs.h"],
        "generated_rtl_header": by_name["ir_register_map_defs.svh"],
        "source_manifest": by_name["p9_source_input_manifest.json"],
        "authorization_verbatim_utf8_path": rel(raw_auth),
        "authorization_verbatim_utf8_sha256": sha256(raw_auth),
        "goal_path": str(GOAL_FILE),
        "goal_sha256": sha256(GOAL_FILE),
        "project_state_sha256": sha256(ROOT / "config/project_state.json"),
        "project_requirements_sha256": sha256(ROOT / "config/project_requirements.yaml"),
        "p9_config_sha256": sha256(ROOT / "config/p9_z7010_stationary_2lane.yaml"),
        "active_xdc_sha256": sha256(ROOT / "constraints/active/PORT1.generated.xdc"),
        "pinmap_sha256": sha256(ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"),
        "register_map_sha256": sha256(ROOT / "config/register_map/ir_axi_regs.yaml"),
        "movement_allowed": False,
        "rotation_allowed": False,
        "network_allowed": False,
        "ethernet_required": False,
        "hardware_stationary_immutable": True,
        "two_lane_application_model": "PENDING_NO_CREDIBLE_FROZEN_2LANE_APPLICATION_MODEL",
        "modeled_application_goodput_bps": None,
        "application_goodput_target_bps": None,
        "maximum_single_test_seconds": 1800,
        "lane_masks": [1, 2, 3],
    }
    phase2_path = (ROOT / "evidence/hardware/p9" / run_id /
                   "authorization/phase2_immutable_artifacts.json")
    write_json(phase2_path, phase2)
    evidence_manifest = phase2_path.parents[1] / "artifacts/artifact_manifest.json"
    evidence_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, evidence_manifest)

    summary = {
        "schema_version": 1, "status": "PASS",
        "test_id": "P9-02-IMMUTABLE-ARTIFACT-FREEZE", "run_id": run_id,
        "source_commit": source_commit, "artifact_manifest": artifact(manifest_path),
        "phase2_authorization": artifact(phase2_path),
        "candidate_bitstream_sha256": candidate_hash,
        "shutdown_bitstream_sha256": by_name["ir_p9_shutdown_z7010.bit"]["sha256"],
        "xsa_sha256": by_name["ir_p9_z7010_2lane.xsa"]["sha256"],
        "bsp_sha256": by_name["p9_ps7_bsp_deterministic.zip"]["sha256"],
        "runner_package_sha256": by_name["p9_host_jtag_runner_deterministic.zip"]["sha256"],
        "elf_sha256": by_name["p9_runtime.elf"]["sha256"],
        "frozen_artifact_count": len(frozen), "generated_utc": now(),
    }
    summary_path = GENERATED / "p9_artifact_freeze_summary.json"
    write_json(summary_path, summary)
    (GENERATED / "p9_artifact_freeze_summary.md").write_text(
        "# P9 Immutable Artifact Freeze\n\n"
        f"- Status: `PASS`\n- Run ID: `{run_id}`\n"
        f"- Source commit: `{source_commit}`\n"
        f"- Candidate SHA256: `{candidate_hash}`\n"
        f"- Manifest: `{rel(manifest_path)}`\n"
        f"- Phase-2 authorization: `{rel(phase2_path)}`\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
