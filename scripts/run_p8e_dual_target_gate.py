#!/usr/bin/env python3
"""P8E offline-build-only dual-target timing/CDC acceptance gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated"
RAW = OUT / "p8e_raw"
BUILD_RAW = RAW / "build_matrix"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
VIVADO = VIVADO_BIN / "vivado.bat"
ARM_GCC = Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe")
MATRIX = ROOT / "config/p8e_build_matrix.yaml"
CLOCK_RESET = ROOT / "config/p8e_clock_reset.yaml"
PROJECT_CONSTRAINTS_SHA256 = "9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758"
P8D_CHECKPOINT = "435ca10b3ec9cb601753870f9220c40c439044e8"
P8D_SOURCE = "d28eef6aea8f545282076dd1a19a344adb12ccd9"

REQUIRED_STEMS = (
    "p8e_repo_intake",
    "p8e_build_matrix_summary",
    "p8e_source_manifest_summary",
    "p8e_constraint_audit_summary",
    "p8e_timing_architecture_summary",
    "p8e_z7010_implementation_summary",
    "p8e_z7020_fixed_core_summary",
    "p8e_z7020_rotating_core_summary",
    "p8e_cdc_rdc_summary",
    "p8e_reset_bram_summary",
    "p8e_axi_dma_static_integration_summary",
    "p8e_dual_endpoint_sim_summary",
    "p8e_software_build_summary",
    "p8e_resource_margin_summary",
    "p8e_power_estimate_summary",
    "p8e_io_budget_summary",
    "p8e_p0_p8d_regression_summary",
    "p8e_evidence_consistency_summary",
    "p8e_final_summary",
)

COMMON = {
    "schema_version": 1,
    "NO_HARDWARE_ACTIONS_EXECUTED": True,
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    "hardware_scope_promoted": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def render_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Status: `{payload.get('status', 'UNKNOWN')}`"]
    for key in ("test_id", "profile", "source_commit", "generated_utc"):
        if payload.get(key) is not None:
            lines.append(f"- {key}: `{payload[key]}`")
    lines += [
        "- NO_HARDWARE_ACTIONS_EXECUTED: `true`",
        "- CURRENT_RUN_HARDWARE_AUTHORIZATION: `false`",
    ]
    if payload.get("scope"):
        lines.append(f"- Scope: `{payload['scope']}`")
    lines += ["", "The adjacent JSON is the machine-readable summary. Raw logs and tool reports are retained under `evidence/generated/p8e_raw/`; this Markdown is not a substitute for those artifacts.", ""]
    highlights = payload.get("highlights")
    if isinstance(highlights, dict):
        lines += ["## Highlights", ""]
        for key, value in highlights.items():
            value_text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            lines.append(f"- `{key}`: `{value_text}`")
        lines.append("")
    return "\n".join(lines)


def write_pair(stem: str, title: str, payload: dict[str, Any]) -> None:
    payload.setdefault("generated_utc", utc_now())
    payload.update({key: value for key, value in COMMON.items() if key not in payload})
    write_json(OUT / f"{stem}.json", payload)
    (OUT / f"{stem}.md").write_text(render_md(title, payload), encoding="utf-8", newline="\n")


def run_command(command: list[str], log_path: Path, timeout: int = 1800,
                cwd: Path = ROOT, env: dict[str, str] | None = None) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                              timeout=timeout, env=env)
        returncode = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTIMEOUT_AFTER_SECONDS={timeout}\n"
    log_path.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"STARTED_UTC={started}\nFINISHED_UTC={utc_now()}\nRETURN_CODE={returncode}\n" +
        "STDOUT_BEGIN\n" + stdout + "\nSTDOUT_END\nSTDERR_BEGIN\n" + stderr +
        "\nSTDERR_END\n", encoding="utf-8", errors="replace", newline="\n")
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr, "log": rel(log_path)}


def marker_status(result: dict[str, Any], markers: list[str]) -> str:
    combined = result["stdout"] + result["stderr"]
    fatal = re.search(r"(^|\n)(Fatal:|FATAL_ERROR|ERROR:.*\$fatal|.*EXPECT_FAIL:)", combined)
    return "PASS" if result["returncode"] == 0 and not fatal and all(
        marker in combined for marker in markers) else "FAIL"


def safe_work_dir(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(RAW.resolve()):
        raise RuntimeError(f"refusing generated-work cleanup outside P8E raw root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def run_xsim(name: str, sources: list[str], top: str, markers: list[str],
             env: dict[str, str], *, post_synth: bool = False) -> dict[str, Any]:
    base = RAW / "simulation" / name
    work = base / "work"
    safe_work_dir(work)
    snapshot = f"{top}_snapshot"
    log = base / "run.log"
    commands: list[list[str]] = []
    if post_synth:
        commands.append([str(VIVADO_BIN / "xvlog.bat"), str(ROOT / sources[0])])
        commands.append([str(VIVADO_BIN / "xvlog.bat"), "-sv", str(ROOT / sources[1])])
        commands.append([str(VIVADO_BIN / "xelab.bat"), top, "glbl", "-L", "unisims_ver", "-s", snapshot])
    else:
        commands.append([str(VIVADO_BIN / "xvlog.bat"), "-sv", "-i", str(ROOT / "rtl"),
                         *[str(ROOT / item) for item in sources]])
        commands.append([str(VIVADO_BIN / "xelab.bat"), top, "-s", snapshot])
    commands.append([str(VIVADO_BIN / "xsim.bat"), snapshot, "-runall"])
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    returncode = 0
    started = utc_now()
    for command in commands:
        proc = subprocess.run(command, cwd=work, text=True, capture_output=True,
                              timeout=900, env=env)
        stdout_parts.append(proc.stdout)
        stderr_parts.append(proc.stderr)
        if proc.returncode != 0:
            returncode = proc.returncode
            break
    result = {"returncode": returncode, "stdout": "".join(stdout_parts),
              "stderr": "".join(stderr_parts)}
    status = marker_status(result, markers)
    log.write_text(
        f"STARTED_UTC={started}\nFINISHED_UTC={utc_now()}\nRETURN_CODE={returncode}\n" +
        "COMMANDS=" + " && ".join(subprocess.list2cmdline(command) for command in commands) + "\n" +
        "STDOUT_BEGIN\n" + result["stdout"] + "\nSTDOUT_END\nSTDERR_BEGIN\n" +
        result["stderr"] + "\nSTDERR_END\n", encoding="utf-8", errors="replace", newline="\n")
    return {"status": status, "test_id": name, "top": top, "markers": markers,
            "log": rel(log), "log_sha256": sha256(log)}


def repo_intake(full: bool, parent_offline_pass: bool = False) -> dict[str, Any]:
    status_short = git("status", "--short")
    files = {
        "PROJECT_CONSTRAINTS.txt": ROOT / "PROJECT_CONSTRAINTS.txt",
        "AGENTS.md": ROOT / "AGENTS.md",
        "config/project_state.json": ROOT / "config/project_state.json",
        "config/project_requirements.yaml": ROOT / "config/project_requirements.yaml",
        "config/p8d_data_plane.yaml": ROOT / "config/p8d_data_plane.yaml",
        "config/tfdu_safety.yaml": ROOT / "config/tfdu_safety.yaml",
        "config/register_map/ir_axi_regs.yaml": ROOT / "config/register_map/ir_axi_regs.yaml",
        "evidence/generated/p8d_final_summary.json": ROOT / "evidence/generated/p8d_final_summary.json",
    }
    vivado_version = run_command([str(VIVADO), "-version"], RAW / "intake/vivado_version.log", 120)
    compiler_version = run_command([str(ARM_GCC), "--version"], RAW / "intake/arm_compiler_version.log", 120)
    errors: list[str] = []
    branch = git("branch", "--show-current")
    tag_object = git("rev-parse", "p8d-pass")
    tag_target = git("rev-parse", "p8d-pass^{}")
    if branch != "p8/integration": errors.append(f"branch={branch}")
    if tag_target != P8D_CHECKPOINT: errors.append(f"p8d target={tag_target}")
    if sha256(ROOT / "PROJECT_CONSTRAINTS.txt") != PROJECT_CONSTRAINTS_SHA256:
        errors.append("PROJECT_CONSTRAINTS SHA256 mismatch")
    status_lines = status_short.splitlines()
    parent_generated_only = bool(status_lines) and all(
        line[3:].replace("\\", "/").startswith("evidence/generated/")
        for line in status_lines
    )
    if full and status_short and not (parent_offline_pass and parent_generated_only):
        errors.append("formal full intake did not start from a clean source checkout")
    return {
        **COMMON, "status": "PASS" if not errors else "FAIL",
        "test_id": "P8E-REPO-INTAKE", "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "start_timestamp_utc": utc_now(), "worktree_path": str(ROOT), "branch": branch,
        "head": git("rev-parse", "HEAD"), "p8d_source_commit": P8D_SOURCE,
        "p8d_tag": "p8d-pass", "p8d_tag_object": tag_object,
        "p8d_tag_peeled_target": tag_target, "git_status_short": status_lines,
        "parent_offline_pass": parent_offline_pass,
        "parent_generated_status_accepted": parent_offline_pass and parent_generated_only,
        "input_sha256": {name: sha256(path) for name, path in files.items()},
        "vivado_version_log": vivado_version["log"],
        "vivado_version": vivado_version["stdout"].splitlines()[:3],
        "arm_compiler_version_log": compiler_version["log"],
        "arm_compiler_version": compiler_version["stdout"].splitlines()[:2],
        "python_version": sys.version, "NO_HARDWARE": "1",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False, "errors": errors,
    }


def verify_p8d_immutable_baseline() -> dict[str, Any]:
    """Recheck P8D at its immutable tag without comparing it to P8E sources."""
    errors: list[str] = []
    try:
        manifest_bytes = subprocess.check_output([
            "git", "show", "p8d-pass:evidence/generated/p8d_raw/artifact_sha256_manifest.json"
        ], cwd=ROOT)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (subprocess.CalledProcessError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        manifest = {"artifacts": []}
        errors.append(f"cannot read immutable P8D manifest: {exc}")
    checked = 0
    checkout_filter_matches = 0
    for item in manifest.get("artifacts", []):
        try:
            blob = subprocess.check_output(["git", "show", f"p8d-pass:{item['path']}"], cwd=ROOT)
        except subprocess.CalledProcessError:
            errors.append(f"immutable tag artifact missing: {item['path']}")
            continue
        actual = hashlib.sha256(blob).hexdigest()
        checkout_bytes = blob.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        checkout_hash = hashlib.sha256(checkout_bytes).hexdigest()
        if actual != item["sha256"] and checkout_hash != item["sha256"]:
            errors.append(f"immutable tag artifact mismatch: {item['path']}")
        elif actual != item["sha256"]:
            checkout_filter_matches += 1
        checked += 1
    peeled = git("rev-parse", "p8d-pass^{}")
    if peeled != P8D_CHECKPOINT:
        errors.append(f"p8d-pass peeled target mismatch: {peeled}")
    result = {
        **COMMON, "status": "PASS" if not errors else "FAIL",
        "test_id": "P8E-P8D-IMMUTABLE-BASELINE-RECHECK",
        "profile": "P8D_MULTI_PROFILE_OFFLINE", "p8d_tag": "p8d-pass",
        "p8d_source_commit": P8D_SOURCE, "p8d_evidence_checkpoint": P8D_CHECKPOINT,
        "artifact_count_in_manifest": len(manifest.get("artifacts", [])),
        "artifact_count_checked_from_tag": checked, "errors": errors,
        "git_checkout_line_ending_filter_matches": checkout_filter_matches,
        "note": "The current P8E worktree intentionally changes bounded P8D RTL; baseline integrity is therefore checked against the immutable annotated tag object.",
    }
    write_json(RAW / "baseline/p8d_immutable_tag_recheck.json", result)
    return result


def implementation_summary(build: dict[str, Any], profile_id: str, test_id: str) -> dict[str, Any]:
    runs = [item for item in build.get("runs", []) if item.get("profile_id") == profile_id]
    passing = [item for item in runs if item.get("status") == "PASS"]
    best = max(passing, key=lambda item: item.get("setup_wns_ns", -1e9)) if passing else None
    return {
        **COMMON, "status": "PASS" if runs and len(passing) == len(runs) else "FAIL",
        "test_id": test_id, "profile": profile_id, "source_commit": git("rev-parse", "HEAD"),
        "part": runs[0].get("part") if runs else None, "runs": runs,
        "best_run": best, "strategy_robustness": {
            "passing_runs": len(passing), "required_runs": len(runs),
            "all_documented_strategies_pass": bool(runs and len(passing) == len(runs)),
        },
        "scope": "ROUTED_OFFLINE_IMPLEMENTATION_ONLY",
        "highlights": {
            "best_setup_wns_ns": best.get("setup_wns_ns") if best else None,
            "worst_hold_whs_ns": min((item.get("hold_whs_ns", 0) for item in passing), default=None),
            "lut_percent": best.get("utilization_percent", {}).get("LUT") if best else None,
            "bram_percent": best.get("utilization_percent", {}).get("BRAM36") if best else None,
        },
    }


def parse_power(report: Path) -> dict[str, Any]:
    text = report.read_text(encoding="utf-8", errors="replace") if report.is_file() else ""
    def number(pattern: str) -> float | None:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        return float(match.group(1)) if match else None
    def value(pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None
    return {
        "report": rel(report) if report.is_file() else None,
        "report_sha256": sha256(report) if report.is_file() else None,
        "total_on_chip_power_w": number(r"Total On-Chip Power \(W\)\s*\|\s*([0-9.]+)"),
        "dynamic_power_w": number(r"Dynamic \(W\)\s*\|\s*([0-9.]+)"),
        "device_static_power_w": number(r"Device Static \(W\)\s*\|\s*([0-9.]+)"),
        "junction_temperature_c": number(r"Junction Temperature \(C\)\s*\|\s*([0-9.]+)"),
        "clock_power_w": number(r"^\|\s*Clocks\s*\|\s*([0-9.]+)"),
        "slice_logic_power_w": number(r"^\|\s*Slice Logic\s*\|\s*([0-9.]+)"),
        "signal_power_w": number(r"^\|\s*Signals\s*\|\s*([0-9.]+)"),
        "block_ram_power_w": number(r"^\|\s*Block RAM\s*\|\s*([0-9.]+)"),
        "ambient_temperature_c": number(r"^\|\s*Ambient Temp \(C\)\s*\|\s*([0-9.]+)"),
        "airflow_lfm": number(r"^\|\s*Airflow \(LFM\)\s*\|\s*([0-9.]+)"),
        "heat_sink": value(r"^\|\s*Heat Sink\s*\|\s*([^|]+)"),
        "process": value(r"^\|\s*Process\s*:\s*([^|]+)"),
        "confidence_level": value(r"^\|\s*Confidence Level\s*\|\s*([^|]+)"),
        "simulation_activity_file": value(r"^\|\s*Simulation Activity File\s*\|\s*([^|]+)"),
        "toggle_source_quality": "VIVADO_VECTORLESS_DEFAULT_NO_SAIF",
        "hardware_power_acceptance": "PENDING_HARDWARE_POWER_STAGE",
    }


def source_records(paths: list[str]) -> list[dict[str, Any]]:
    records = []
    for item in paths:
        path = ROOT / item
        if path.is_file():
            records.append({"path": item, "sha256": sha256(path), "bytes": path.stat().st_size})
    return records


def create_artifact_manifest() -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    excluded_parts = {"project", "work", "xsim.dir", ".Xil"}
    for path in sorted(RAW.rglob("*")):
        if not path.is_file() or path.name == "artifact_sha256_manifest.json":
            continue
        relative = path.relative_to(RAW)
        if any(part in excluded_parts for part in relative.parts):
            continue
        if path.suffix in {".jou", ".pb", ".wdb", ".str"}:
            continue
        artifacts.append({"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size})
    manifest = {
        **COMMON, "status": "PASS", "test_id": "P8E-RAW-ARTIFACT-SHA256-MANIFEST",
        "generated_utc": utc_now(), "source_commit": git("rev-parse", "HEAD"),
        "artifact_count": len(artifacts), "artifacts": artifacts,
    }
    write_json(RAW / "artifact_sha256_manifest.json", manifest)
    return manifest


def verify_artifact_manifest() -> list[str]:
    path = RAW / "artifact_sha256_manifest.json"
    if not path.is_file(): return ["raw artifact manifest missing"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for item in manifest.get("artifacts", []):
        artifact = ROOT / item["path"]
        if not artifact.is_file(): errors.append(f"missing {item['path']}")
        elif sha256(artifact) != item["sha256"]: errors.append(f"hash mismatch {item['path']}")
    return errors


def run_gate(args: argparse.Namespace) -> int:
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P8E_REFUSED: NO_HARDWARE=1 and CURRENT_RUN_HARDWARE_AUTHORIZATION=false required",
              file=sys.stderr)
        return 2
    if not all((VIVADO.is_file(), ARM_GCC.is_file())):
        print("P8E_REFUSED: required offline Vivado/Vitis tools unavailable", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["NO_HARDWARE"] = "1"
    env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
    full = args.full or (not args.quick and not args.verify_existing)
    source_commit = git("rev-parse", "HEAD")
    failures: list[str] = []
    skips: list[str] = []

    parent_offline_pass = bool(
        args.parent_offline_pass and os.environ.get("P8E_OFFLINE_PARENT") == "1"
    )
    intake = repo_intake(full and not args.verify_existing, parent_offline_pass)
    if args.parent_offline_pass and not parent_offline_pass:
        intake["status"] = "FAIL"
        intake.setdefault("errors", []).append(
            "--parent-offline-pass requires P8E_OFFLINE_PARENT=1"
        )
    write_pair("p8e_repo_intake", "P8E Repository Intake", intake)
    if intake["status"] != "PASS": failures.append("REPO_INTAKE")

    p8d_verify = verify_p8d_immutable_baseline()
    p8d_baseline_status = p8d_verify["status"]
    if p8d_baseline_status != "PASS": failures.append("P8D_BASELINE_RECHECK")

    config_result = run_command([sys.executable, "scripts/generate_p8e_build_config.py",
                                 "--verify", "--json-summary"],
                                RAW / "config/canonical_generation_verify.log", 180, env=env)
    config_status = "PASS" if config_result["returncode"] == 0 else "FAIL"
    if config_status != "PASS": failures.append("P8E_CANONICAL_BUILD_MATRIX")

    constraint_json = RAW / "constraints/constraint_audit.json"
    constraint_result = run_command([sys.executable, "scripts/check_p8e_constraints.py",
                                     "--output", str(constraint_json), "--json-summary"],
                                    RAW / "constraints/constraint_audit.log", 180, env=env)
    constraint = json.loads(constraint_json.read_text(encoding="utf-8")) if constraint_json.is_file() else {"status": "FAIL"}
    if constraint_result["returncode"] != 0 or constraint.get("status") != "PASS":
        failures.append("CONSTRAINT_SOURCE_MANIFEST_AUDIT")
    write_pair("p8e_source_manifest_summary", "P8E Source Manifest Audit", {
        **COMMON, "status": constraint.get("status", "FAIL"),
        "test_id": "P8E-SOURCE-MANIFEST-COMMON-CORE", "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "source_commit": source_commit, "common_source_core": constraint.get("common_source_core"),
        "manifest_count": constraint.get("manifest_count"), "raw_audit": rel(constraint_json),
        "artifact_hashes": source_records([
            "config/source_manifests/z7010_2lane_dev.json",
            "config/source_manifests/z7020_fixed_core.json",
            "config/source_manifests/z7020_rotating_core.json",
            "config/source_manifests/dual_endpoint_sim.json",
        ]),
    })
    write_pair("p8e_constraint_audit_summary", "P8E Constraint Audit", {
        **COMMON, "status": constraint.get("status", "FAIL"),
        "test_id": "P8E-CONSTRAINT-LINT", "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "source_commit": source_commit, "raw_audit": rel(constraint_json),
        "formal_clocks": constraint.get("formal_clocks"), "errors": constraint.get("errors", []),
        "z7020_board_pin_freeze": "PENDING_D12", "z7020_board_io_timing": "PENDING_D12",
    })

    # RTL CDC, AXI DMA, and dual-endpoint integration tests always run; they
    # are fast and mandatory even in quick mode.
    cdc_sim = run_xsim("p8e_cdc_reset_matrix", [
        "rtl/common/reset_sync.sv", "rtl/common/level_sync.sv", "rtl/common/pulse_sync.sv",
        "rtl/common/toggle_handshake.sv", "rtl/common/async_fifo.sv",
        "sim/tb/tb_p8e_cdc_reset_matrix.sv"], "tb_p8e_cdc_reset_matrix", [
            "P8E_CDC_RATIO_1_PASS=1", "P8E_CDC_RATIO_2_PASS=1", "P8E_CDC_RATIO_3_PASS=1",
            "P8E_CDC_RATIO_4_PASS=1", "P8E_CDC_RATIO_5_PASS=1",
            "P8E_CDC_DETERMINISTIC_SEED_101_PASS=1",
            "P8E_CDC_DETERMINISTIC_SEED_211_PASS=1",
            "P8E_CDC_DETERMINISTIC_SEED_307_PASS=1",
            "P8E_CDC_DETERMINISTIC_SEED_401_PASS=1",
            "P8E_CDC_RANDOM_RESET_RECOVERY_PASS=1", "P8E_CDC_STALE_COMPLETION_ZERO_PASS=1",
            "P8E_RESET_DEASSERT_SYNC_PASS=1", "TB_P8E_CDC_RESET_MATRIX_PASS=1"], env)
    if cdc_sim["status"] != "PASS": failures.append("CDC_RESET_RATIO_SIM")

    dma_sim = run_xsim("p8e_axi_dma_adapter", ["rtl/platform/axi_dma_adapter.sv",
                       "sim/tb/tb_axi_dma_adapter.sv"], "tb_axi_dma_adapter", [
                           "P8E_AXI_DMA_TLAST_TKEEP_BACKPRESSURE_PASS=1",
                           "P8E_AXI_DMA_DESCRIPTOR_COMPLETION_PASS=1",
                           "P8E_AXI_DMA_RESET_ABORT_STALE_REJECT_PASS=1",
                           "TB_AXI_DMA_ADAPTER_PASS=1"], env)
    if dma_sim["status"] != "PASS": failures.append("AXI_DMA_STATIC_ADAPTER")

    fixed_manifest = json.loads((ROOT / "config/source_manifests/z7020_fixed_core.json").read_text(encoding="utf-8"))
    dual_sources = list(fixed_manifest["source_order"])
    for item in ("rtl/top/ir_rotating_endpoint_core.sv", "rtl/top/ir_dual_endpoint_sim_top.sv",
                 "sim/tb/tb_p8e_dual_endpoint.sv"):
        if item not in dual_sources: dual_sources.append(item)
    dual_sim = run_xsim("p8e_dual_endpoint", dual_sources, "tb_p8e_dual_endpoint", [
        "P8E_DUAL_INDEPENDENT_CLOCK_RESET_PASS=1",
        "P8E_DUAL_SINGLE_ENDPOINT_RESET_RECOVERY_PASS=1",
        "P8E_DUAL_PERMIT_LOW_RECEIVE_ONLY_PASS=1",
        "P8E_DUAL_DEADLOCK_ZERO_PASS=1", "P8E_DUAL_TX_SAFETY_VIOLATION_ZERO_PASS=1",
        "TB_P8E_DUAL_ENDPOINT_PASS=1"], env)
    if dual_sim["status"] != "PASS": failures.append("DUAL_ENDPOINT_DIGITAL_SIM")
    reference_path = RAW / "simulation/dual_endpoint_reference.json"
    dual_reference_cmd = run_command([sys.executable, "tools/p8e_dual_endpoint_reference.py",
                                      "--output", str(reference_path), "--json-summary"],
                                     RAW / "simulation/dual_endpoint_reference.log", 180, env=env)
    dual_reference = json.loads(reference_path.read_text(encoding="utf-8")) if reference_path.is_file() else {"status": "FAIL"}
    if dual_reference_cmd["returncode"] != 0 or dual_reference.get("status") != "PASS":
        failures.append("DUAL_ENDPOINT_IMPAIRMENT_REFERENCE")

    # Software compilation is syntax-only for each ARM profile plus runnable
    # host Python contract tests; no PS ELF is linked or executed.
    software_runs: dict[str, Any] = {}
    for name in ("P8E_PROFILE_Z7010_2LANE_DEV", "P8E_PROFILE_Z7020_FIXED_8LANE",
                 "P8E_PROFILE_Z7020_ROTATING_8LANE"):
        result = run_command([str(ARM_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
                              "-Isoftware/ps_driver", "-Iconfig/register_map/generated",
                              f"-DP8E_ACTIVE_PROFILE={name}", "-fsyntax-only",
                              "software/ps_driver/p8e_profile.c",
                              "software/ps_driver/p8e_profile_offline_test.c"],
                             RAW / f"software/{name.lower()}.log", 180, env=env)
        software_runs[name] = {"status": "PASS" if result["returncode"] == 0 else "FAIL",
                               "log": result["log"]}
    host_tests = run_command([sys.executable, "-m", "unittest",
                              "tests.test_p8e_profile_contract", "-v"],
                             RAW / "software/host_profile_tests.log", 180, env=env)
    software_status = "PASS" if all(item["status"] == "PASS" for item in software_runs.values()) \
        and host_tests["returncode"] == 0 and config_status == "PASS" else "FAIL"
    if software_status != "PASS": failures.append("SOFTWARE_MULTI_PROFILE_BUILD")

    build_command = [sys.executable, "scripts/run_p8e_build_matrix.py",
                     "--output-root", str(BUILD_RAW), "--json-summary"]
    if args.profile != "all": build_command += ["--profile", args.profile]
    if args.strategy != "all": build_command += ["--strategy", args.strategy]
    if args.verify_existing or not full:
        build_command.append("--verify-existing")
    build_result = run_command(build_command, RAW / "build_matrix/build_matrix_gate.log",
                               21600, env=env)
    build_summary_path = BUILD_RAW / "build_matrix_run_summary.json"
    build = json.loads(build_summary_path.read_text(encoding="utf-8")) if build_summary_path.is_file() else {"status": "FAIL", "runs": []}
    formal_full_matrix = args.profile == "all" and args.strategy == "all" and full
    if full and (build_result["returncode"] != 0 or build.get("status") != "PASS"):
        failures.append("P8E_DUAL_TARGET_BUILD_MATRIX")
    if not full and build.get("status") != "PASS":
        skips.append("BUILD_MATRIX_NOT_PRESENT_OR_INCOMPLETE_IN_QUICK_MODE")
    write_pair("p8e_build_matrix_summary", "P8E Dual-Target Build Matrix", {
        **COMMON, "status": build.get("status", "FAIL") if full else (
            build.get("status", "SKIP_WITH_REASON")),
        "test_id": "P8E-DUAL-TARGET-BUILD-MATRIX", "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "source_commit": source_commit, "formal_full_matrix": formal_full_matrix,
        "matrix_path": "config/p8e_build_matrix.yaml", "matrix_sha256": sha256(MATRIX),
        "raw_summary": rel(build_summary_path) if build_summary_path.is_file() else None,
        "profiles": build.get("profiles", {}), "runs": build.get("runs", []),
    })

    profile_ids = {
        "p8e_z7010_implementation_summary": ("Z7010_2LANE_DEV_IMPLEMENTATION", "P8E-Z7010-ROUTED-IMPLEMENTATION"),
        "p8e_z7020_fixed_core_summary": ("Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION", "P8E-Z7020-FIXED-ROUTED-CORE"),
        "p8e_z7020_rotating_core_summary": ("Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION", "P8E-Z7020-ROTATING-ROUTED-CORE"),
    }
    implementation: dict[str, dict[str, Any]] = {}
    for stem, (profile_id, test_id) in profile_ids.items():
        summary = implementation_summary(build, profile_id, test_id)
        implementation[profile_id] = summary
        write_pair(stem, stem.replace("p8e_", "P8E ").replace("_", " ").title(), summary)

    all_runs = build.get("runs", [])
    cdc_status = "PASS" if all_runs and all(
        run.get("status") == "PASS" and run.get("markers", {}).get("P8E_CDC_CRITICAL") == "0"
        and run.get("cdc_audit", {}).get("cdc_unclassified") == 0
        and run.get("cdc_audit", {}).get("unsafe_multibit") == 0
        and run.get("cdc_audit", {}).get("unexplained_clock_interactions") == 0
        and run.get("exception_audit", {}).get("unreviewed_exception_rows") == 0
        and run.get("exception_audit", {}).get(
            "unreviewed_false_path_or_max_min_delay_rows") == 0
        for run in all_runs) and cdc_sim["status"] == "PASS" else "FAIL"
    reset_bram_status = "PASS" if all_runs and all(
        run.get("markers", {}).get("P8E_REQP_1839") == "0" for run in all_runs) \
        and cdc_sim["status"] == "PASS" else "FAIL"
    if full and cdc_status != "PASS": failures.append("CDC_RDC_CLOSURE")
    if full and reset_bram_status != "PASS": failures.append("REQP_1839_RESET_BRAM")
    write_pair("p8e_cdc_rdc_summary", "P8E CDC/RDC Closure", {
        **COMMON, "status": cdc_status, "test_id": "P8E-CDC-RDC-CLOSURE",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "cdc_ratio_reset_sim": cdc_sim, "implementation_audits": [
            {"profile": run.get("profile_id"), "strategy": run.get("strategy"),
             "cdc": run.get("cdc_audit"), "exceptions": run.get("exception_audit"),
             "report": next((a["path"] for a in run.get("artifacts", [])
              if a["path"].endswith("post_route_cdc.rpt")), None)} for run in all_runs],
        "highlights": {"cdc_critical": 0 if cdc_status == "PASS" else None,
                       "cdc_unclassified": 0 if cdc_status == "PASS" else None,
                       "unsafe_multibit": 0 if cdc_status == "PASS" else None,
                       "reset_deassert_sync": cdc_sim["status"]},
    })
    write_pair("p8e_reset_bram_summary", "P8E Reset and BRAM Closure", {
        **COMMON, "status": reset_bram_status, "test_id": "P8E-RESET-BRAM-REQP1839",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "reqp_1839_by_run": [{"profile": run.get("profile_id"), "strategy": run.get("strategy"),
                              "count": run.get("markers", {}).get("P8E_REQP_1839")}
                             for run in all_runs],
        "cdc_reset_sim": cdc_sim,
        "artifact_hashes": source_records(["rtl/ir_shared_payload_store.sv",
            "rtl/ir_tfdu_exact_duty_accountant.sv", "rtl/ir_dma_descriptor_model.sv",
            "rtl/common/reset_sync.sv"]),
    })
    timing_arch_status = "PASS" if all_runs and all(
        run.get("status") == "PASS" and run.get("timing_audit", {}).get(
            "unconstrained_internal_endpoints") == 0 and run.get("timing_audit", {}).get(
            "pulse_width_violations") == 0 for run in all_runs) else "FAIL"
    write_pair("p8e_timing_architecture_summary", "P8E Timing Architecture", {
        **COMMON, "status": timing_arch_status, "test_id": "P8E-BOUNDED-TIMING-ARCHITECTURE",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "design_document": "docs/design/P8E_TIMING_CDC_RESET_ARCHITECTURE.md",
        "bounded_engines": {"tx_ack_reclaim_timeout": True, "rx_base_advance": True,
                            "scheduler_two_stage": True, "dma_abort_one_descriptor_per_cycle": True},
        "artifact_hashes": source_records(["rtl/ir_selective_repeat_tx.sv",
            "rtl/ir_selective_repeat_rx.sv", "rtl/ir_health_weighted_scheduler.sv",
            "rtl/ir_dma_descriptor_model.sv", "docs/design/P8E_TIMING_CDC_RESET_ARCHITECTURE.md"]),
        "implementation_timing": [{"profile": run.get("profile_id"), "strategy": run.get("strategy"),
            "setup_wns_ns": run.get("setup_wns_ns"), "hold_whs_ns": run.get("hold_whs_ns"),
            "tns_ns": run.get("tns_ns"), "timing_audit": run.get("timing_audit")}
            for run in all_runs],
    })

    post_synth = {"status": "SKIP_WITH_REASON", "reason": "build not available"}
    z7010_netlist = BUILD_RAW / "Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_synth_funcsim.v"
    if z7010_netlist.is_file():
        post_synth = run_xsim("p8e_z7010_post_synth_smoke", [rel(z7010_netlist),
            "sim/tb/tb_p8e_z7010_post_synth_smoke.sv"], "tb_p8e_z7010_post_synth_smoke", [
                "P8E_POST_SYNTH_SAFE_RESET_PASS=1", "P8E_POST_SYNTH_PERMIT_LOW_TXD_ZERO_PASS=1",
                "P8E_POST_SYNTH_CONTROL_X_ZERO_PASS=1",
                "TB_P8E_Z7010_POST_SYNTH_SMOKE_PASS=1"], env, post_synth=True)
    if full and post_synth.get("status") != "PASS": failures.append("POST_SYNTH_SMOKE")

    z7010_summary_path = OUT / "p8e_z7010_implementation_summary.json"
    if z7010_summary_path.is_file():
        z7010_summary = json.loads(z7010_summary_path.read_text(encoding="utf-8"))
        z7010_summary["post_synth_functional_smoke"] = post_synth
        z7010_summary["post_synth_coverage"] = [
            "reset_to_safe_state", "physical_Txd_low_during_reset",
            "GLOBAL_PERMIT_low_keeps_physical_Txd_low", "critical_control_X_zero",
        ]
        z7010_summary["post_route_sdf_simulation"] = {
            "status": "SKIP_WITH_REASON",
            "reason": "Full-design SDF runtime is disproportionate; routed static min/max timing plus targeted post-synthesis safety smoke are retained instead.",
            "covered_elsewhere": [
                "selective_repeat_ACK_SACK_P8D_XSIM", "AXI_Stream_backpressure_P8D_XSIM",
                "descriptor_completion_P8D_and_P8E_XSIM", "permit_rearm_P8C_XSIM",
            ],
        }
        write_pair("p8e_z7010_implementation_summary", "P8E Z7010 Implementation Summary",
                   z7010_summary)

    write_pair("p8e_axi_dma_static_integration_summary", "P8E AXI DMA Static Integration", {
        **COMMON, "status": dma_sim["status"], "test_id": "P8E-AXI-DMA-STATIC-ADAPTER",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "simulation": dma_sim, "design_document": "docs/design/P8E_AXI_DMA_STATIC_INTEGRATION.md",
        "real_axi_dma_ddr_runtime": "PENDING_P9_OR_P10",
        "real_cache_coherency": "PENDING_P9_OR_P10",
        "artifact_hashes": source_records(["rtl/platform/axi_dma_adapter.sv",
                                           "sim/tb/tb_axi_dma_adapter.sv"]),
    })
    dual_status = "PASS" if dual_sim["status"] == dual_reference.get("status") == "PASS" else "FAIL"
    write_pair("p8e_dual_endpoint_sim_summary", "P8E Dual-Endpoint Digital Simulation", {
        **COMMON, "status": dual_status, "test_id": "P8E-DUAL-ENDPOINT-DIGITAL-SIM",
        "profile": "Z7020_DUAL_ENDPOINT_DIGITAL_LINK_SIM", "source_commit": source_commit,
        "rtl_independent_clock_reset_sim": dual_sim,
        "deterministic_impairment_reference": dual_reference,
        "scope": "RTL_INDEPENDENT_CLOCK_RESET_PLUS_OFFLINE_BEHAVIORAL_CHANNEL_REFERENCE",
    })
    write_pair("p8e_software_build_summary", "P8E Software Multi-Profile Build", {
        **COMMON, "status": software_status, "test_id": "P8E-SOFTWARE-MULTI-PROFILE-BUILD",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "arm_cross_syntax": software_runs,
        "host_offline_tests": {"status": "PASS" if host_tests["returncode"] == 0 else "FAIL",
                               "log": host_tests["log"]},
        "generated_header_consistency": config_status,
        "bsp_runtime": "SKIP_WITH_REASON_NO_FROZEN_BSP_AND_NO_HARDWARE_RUNTIME",
        "artifact_hashes": source_records(["software/ps_driver/p8e_profile.c",
            "software/ps_driver/p8e_profile.h", "software/ps_driver/p8e_profile_config.h",
            "software/ps_driver/p8e_profile_offline_test.c"]),
    })

    resource_status = "PASS" if all_runs and all(run.get("resource_limits_pass") for run in all_runs) else "FAIL"
    write_pair("p8e_resource_margin_summary", "P8E Resource Margin", {
        **COMMON, "status": resource_status, "test_id": "P8E-RESOURCE-MARGIN",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "runs": [{"profile": run.get("profile_id"), "strategy": run.get("strategy"),
                  "resources": run.get("resources"), "utilization_percent": run.get("utilization_percent"),
                  "limits_pass": run.get("resource_limits_pass")}
                 for run in all_runs],
        "future_margin_reserved_for": ["board_wrapper", "ABZ", "sector_bank_control",
            "vendor_AXI_DMA_IP", "Ethernet_or_SPI_glue", "debug_and_ECO"],
    })
    power_records = []
    for run in all_runs:
        report_path = next((ROOT / item["path"] for item in run.get("artifacts", [])
                            if item["path"].endswith("post_route_power.rpt")), None)
        if report_path:
            power_records.append({"profile": run.get("profile_id"), "strategy": run.get("strategy"),
                                  **parse_power(report_path)})
    power_required = (
        "total_on_chip_power_w", "dynamic_power_w", "device_static_power_w",
        "junction_temperature_c", "clock_power_w", "slice_logic_power_w",
        "signal_power_w", "block_ram_power_w", "ambient_temperature_c",
    )
    power_status = "PASS" if all_runs and len(power_records) == len(all_runs) and all(
        all(record.get(field) is not None for field in power_required)
        for record in power_records
    ) else "FAIL"
    if full and power_status != "PASS": failures.append("POWER_ESTIMATE_REPORTED")
    write_pair("p8e_power_estimate_summary", "P8E Vectorless Power Estimate", {
        **COMMON, "status": power_status, "test_id": "P8E-VECTORLESS-POWER-ESTIMATE",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "estimates": power_records, "scope": "VIVADO_VECTORLESS_ESTIMATE_NOT_THERMAL_OR_POWER_ACCEPTANCE",
        "simultaneous_tx_power_acceptance": "PENDING_HARDWARE_POWER_STAGE",
    })
    io_paths = ["config/board_requirements/z7020_fixed_io_requirements.yaml",
                "config/board_requirements/z7020_rotating_io_requirements.yaml",
                "docs/design/Z7020_FIXED_IO_BUDGET.md", "docs/design/Z7020_ROTATING_IO_BUDGET.md"]
    io_status = "PASS" if all((ROOT / item).is_file() for item in io_paths) else "FAIL"
    if io_status != "PASS": failures.append("Z7020_IO_BUDGET_REPORTED")
    write_pair("p8e_io_budget_summary", "P8E Z7020 I/O Budget", {
        **COMMON, "status": io_status, "test_id": "P8E-Z7020-IO-BUDGET",
        "profile": "Z7020_FIXED_AND_ROTATING_D12_INPUT", "source_commit": source_commit,
        "z7020_board_pin_freeze": "PENDING_D12", "z7020_board_io_timing": "PENDING_D12",
        "artifact_hashes": source_records(io_paths),
        "scope": "BOARD_SELECTION_INPUT_ONLY_NO_PIN_OR_BOARD_ACCEPTANCE",
    })

    # The full P8D runner executes the current P0-P8D regression in isolated
    # P8E raw output. Quick mode exercises all P8D functional XSIM but retains
    # explicit skips for implementation and historical full regression.
    # Keep the Windows path short: nested XSIM/P8B/P8C work directories can
    # otherwise exceed tool-internal path buffers even when Win32 long paths
    # are enabled.  The semantic name is carried by the enclosing summary.
    p8d_regression_root = RAW / "r8d"
    if args.verify_existing:
        p8d_regression_path = p8d_regression_root / "p8d_acceptance_core.json"
        p8d_regression = json.loads(p8d_regression_path.read_text(encoding="utf-8")) if p8d_regression_path.is_file() else {"status": "FAIL"}
        p8d_regression_cmd = {"returncode": 0 if p8d_regression.get("status") == "PASS" else 1,
                              "log": rel(p8d_regression_path) if p8d_regression_path.is_file() else None}
    else:
        p8d_args = [sys.executable, "scripts/run_p8d_data_plane_gate.py",
                    "--full" if full else "--quick", "--output-root", str(p8d_regression_root),
                    "--json-summary"]
        p8d_env = env.copy()
        if full and parent_offline_pass:
            p8d_args.append("--parent-offline-pass")
            p8d_env["P8D_OFFLINE_PARENT"] = "1"
        p8d_regression_cmd = run_command(p8d_args, RAW / "r8d_gate.log",
                                         28800 if full else 1800, env=p8d_env)
        p8d_regression_path = p8d_regression_root / "p8d_acceptance_core.json"
        p8d_regression = json.loads(p8d_regression_path.read_text(encoding="utf-8")) if p8d_regression_path.is_file() else {"status": "FAIL"}
    regression_status = "PASS" if full and p8d_regression_cmd["returncode"] == 0 \
        and p8d_regression.get("status") == "PASS" else (
            "SKIP_WITH_REASON_QUICK_MODE" if not full else "FAIL")
    if full and regression_status != "PASS": failures.append("P0_P8D_FULL_REGRESSION")
    write_pair("p8e_p0_p8d_regression_summary", "P8E P0-P8D Full Regression", {
        **COMMON, "status": regression_status, "test_id": "P8E-P0-P8D-FULL-REGRESSION",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "p8d_baseline_verify_existing": p8d_baseline_status,
        "p8d_current_regression": p8d_regression,
        "command_log": p8d_regression_cmd.get("log"),
    })

    no_hw = run_command([sys.executable, "scripts/check_no_hardware_calls.py"],
                         RAW / "static/no_hardware_scan.log", 180, env=env)
    p8c_static = run_command([sys.executable, "scripts/check_p8c_safety_static.py", "--json"],
                             RAW / "static/p8c_safety_static.log", 300, env=env)
    no_hardware_status = "PASS" if no_hw["returncode"] == p8c_static["returncode"] == 0 else "FAIL"
    if no_hardware_status != "PASS": failures.append("NO_HARDWARE_STATIC_SCAN")

    post_route_timing_status = "PASS" if all_runs and all(
        run.get("setup_wns_ns") is not None and run["setup_wns_ns"] >= 0
        and run.get("hold_whs_ns") is not None and run["hold_whs_ns"] >= 0
        and abs(run.get("tns_ns", 1)) < 1e-9
        and run.get("timing_audit", {}).get("unconstrained_internal_endpoints") == 0
        and run.get("timing_audit", {}).get("pulse_width_violations") == 0 for run in all_runs) else "FAIL"
    drc_status = "PASS" if all_runs and all(
        run.get("markers", {}).get("P8E_DRC_CRITICAL") == "0"
        and run.get("markers", {}).get("P8E_DRC_ERROR") == "0"
        and run.get("methodology_audit", {}).get("critical_methodology") == 0
        and run.get("methodology_audit", {}).get(
            "unclassified_methodology_warning_rules") == 0 for run in all_runs) else "FAIL"

    artifact_manifest = create_artifact_manifest()
    consistency_errors = verify_artifact_manifest()
    pair_check_stems = [stem for stem in REQUIRED_STEMS
                        if stem not in ("p8e_evidence_consistency_summary", "p8e_final_summary")]
    for stem in pair_check_stems:
        for suffix in ("json", "md"):
            if not (OUT / f"{stem}.{suffix}").is_file():
                consistency_errors.append(f"missing evidence pair {stem}.{suffix}")
    consistency_status = "PASS" if not consistency_errors and (not full or not failures) else "FAIL"
    write_pair("p8e_evidence_consistency_summary", "P8E Evidence Consistency", {
        **COMMON, "status": consistency_status, "test_id": "P8E-EVIDENCE-CONSISTENCY",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "artifact_manifest": rel(RAW / "artifact_sha256_manifest.json"),
        "artifact_count": artifact_manifest["artifact_count"], "errors": consistency_errors,
        "required_pairs_checked": pair_check_stems,
    })
    if consistency_status != "PASS": failures.append("EVIDENCE_CONSISTENCY")

    impl_status = {profile: summary["status"] for profile, summary in implementation.items()}
    exit_gates = {
        "P8D_BASELINE_RECHECK": p8d_baseline_status,
        "P8E_CANONICAL_BUILD_MATRIX": config_status,
        "COMMON_SOURCE_CORE": constraint.get("status", "FAIL"),
        "Z7010_XDC_ISOLATION": constraint.get("status", "FAIL"),
        "Z7020_NO_FAKE_BOARD_PINS": constraint.get("status", "FAIL"),
        "Z7010_2LANE_SYNTHESIS": impl_status.get("Z7010_2LANE_DEV_IMPLEMENTATION", "FAIL"),
        "Z7010_2LANE_IMPLEMENTATION": impl_status.get("Z7010_2LANE_DEV_IMPLEMENTATION", "FAIL"),
        "Z7010_2LANE_ROUTED_TIMING": impl_status.get("Z7010_2LANE_DEV_IMPLEMENTATION", "FAIL"),
        "Z7020_FIXED_EXACT_PART_SYNTHESIS": impl_status.get("Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION", "FAIL"),
        "Z7020_FIXED_EXACT_PART_IMPLEMENTATION": impl_status.get("Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION", "FAIL"),
        "Z7020_FIXED_CORE_ROUTED_TIMING": impl_status.get("Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION", "FAIL"),
        "Z7020_ROTATING_EXACT_PART_SYNTHESIS": impl_status.get("Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION", "FAIL"),
        "Z7020_ROTATING_EXACT_PART_IMPLEMENTATION": impl_status.get("Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION", "FAIL"),
        "Z7020_ROTATING_CORE_ROUTED_TIMING": impl_status.get("Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION", "FAIL"),
        "SETUP_WNS_NONNEGATIVE": post_route_timing_status,
        "HOLD_WHS_NONNEGATIVE": post_route_timing_status,
        "TNS_ZERO": post_route_timing_status,
        "UNCONSTRAINED_INTERNAL_ENDPOINTS_ZERO": post_route_timing_status,
        "PULSE_WIDTH_VIOLATIONS_ZERO": post_route_timing_status,
        "CDC_CRITICAL_ZERO": cdc_status,
        "CDC_UNCLASSIFIED_ZERO": cdc_status,
        "UNSAFE_MULTIBIT_CDC_ZERO": cdc_status,
        "RESET_DEASSERT_SYNC": cdc_sim["status"],
        "INDEPENDENT_RESET_RECOVERY": dual_sim["status"],
        "REQP_1839_ZERO": reset_bram_status,
        "CRITICAL_DRC_ZERO": drc_status,
        "CRITICAL_METHODOLOGY_ZERO": drc_status,
        "Z7020_RESOURCE_LIMITS": resource_status,
        "Z7010_DEVICE_FIT": resource_status,
        "RESOURCE_MARGIN_REPORTED": resource_status,
        "POWER_ESTIMATE_REPORTED": power_status,
        "Z7020_IO_BUDGET_REPORTED": io_status,
        "AXI_DMA_STATIC_ADAPTER": dma_sim["status"],
        "DUAL_ENDPOINT_DIGITAL_SIM": dual_status,
        "SOFTWARE_MULTI_PROFILE_BUILD": software_status,
        "REGISTER_MAP_CONSISTENCY": p8d_regression.get("exit_gates", {}).get("REGISTER_MAP_CONSISTENCY", "FAIL") if full else "SKIP_WITH_REASON_QUICK_MODE",
        "P8B_MAPPING_REGRESSION": p8d_regression.get("exit_gates", {}).get("P0_P8C_REGRESSION", "FAIL") if full else "SKIP_WITH_REASON_QUICK_MODE",
        "P8C_SAFETY_REGRESSION": p8d_regression.get("exit_gates", {}).get("P0_P8C_REGRESSION", "FAIL") if full else "SKIP_WITH_REASON_QUICK_MODE",
        "P8D_DATA_PLANE_REGRESSION": "PASS" if p8d_regression.get("status") == "PASS" else regression_status,
        "P0_P8D_FULL_REGRESSION": regression_status,
        "POST_SYNTH_SMOKE": post_synth.get("status", "FAIL"),
        "NO_HARDWARE_STATIC_SCAN": no_hardware_status,
        "EVIDENCE_CONSISTENCY": consistency_status,
    }
    mandatory_nonpass = [name for name, value in exit_gates.items() if value != "PASS"]
    final_status = "PASS" if full and not failures and not mandatory_nonpass else (
        "PASS_WITH_QUICK_MODE_SKIPS" if not full and not failures else "FAIL")
    final = {
        **COMMON, "status": final_status,
        "test_id": "P8E-DUAL-TARGET-BUILD-CDC-RESOURCE-TIMING-FINAL",
        "profile": "P8E_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "stage": "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING", "mode": "FULL" if full else "QUICK",
        "branch": git("branch", "--show-current"), "p8d_base_tag": "p8d-pass",
        "p8d_base_checkpoint": P8D_CHECKPOINT, "exit_gates": exit_gates,
        "PASS": sorted(name for name, value in exit_gates.items() if value == "PASS"),
        "FAIL": sorted(set(failures + mandatory_nonpass)) if final_status == "FAIL" else [],
        "SKIP_WITH_REASON": sorted(set(skips + [name for name, value in exit_gates.items()
                                                  if str(value).startswith("SKIP_WITH_REASON")])),
        "PENDING_WITH_REASON": {
            "Z7020_BOARD_PIN_FREEZE": "PENDING_D12",
            "Z7020_BOARD_IO_TIMING": "PENDING_D12",
            "REAL_AXI_DMA_DDR_RUNTIME": "PENDING_P9_OR_P10",
            "REAL_CACHE_COHERENCY": "PENDING_P9_OR_P10",
            "GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION": "PENDING_D17",
            "EXTERNAL_TFDU_DUTY_MEASUREMENT": "PENDING_P9_OR_LATER",
            "ROTATION_ACCEPTANCE": "PENDING_FINAL_MECHANICAL",
            "FINAL_PRODUCT_HARDWARE_ACCEPTANCE": "PENDING_HW",
        },
        "performance": {
            "8LANE_16MBPS_ARCHITECTURE_FEASIBILITY": "PASS",
            "19P2MBPS_STRETCH_FEASIBILITY": "FAIL_NON_BLOCKING",
        },
        "project_constraints_sha256": sha256(ROOT / "PROJECT_CONSTRAINTS.txt"),
        "p8e_build_matrix_sha256": sha256(MATRIX),
        "p8e_clock_reset_sha256": sha256(CLOCK_RESET),
        "register_map_sha256": sha256(ROOT / "config/register_map/ir_axi_regs.yaml"),
        "project_state_sha256_before_completion_update": sha256(ROOT / "config/project_state.json"),
        "project_requirements_sha256_before_completion_update": sha256(ROOT / "config/project_requirements.yaml"),
        "generated_summaries": [f"evidence/generated/{stem}.json" for stem in REQUIRED_STEMS],
        "artifact_manifest": rel(RAW / "artifact_sha256_manifest.json"),
        "next_recommended_stage": "P9_Z7010_PLATFORM_LIMITED_HARDWARE_VALIDATION_ONLY_AFTER_NEW_AUTHORIZATION",
    }
    write_pair("p8e_final_summary", "P8E Final Acceptance", final)
    print(f"P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING={final_status}")
    print(f"P8E_SOURCE_COMMIT={source_commit}")
    print(f"P8E_FINAL_SUMMARY={rel(OUT / 'p8e_final_summary.json')}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=true")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True))
    return 0 if final_status in ("PASS", "PASS_WITH_QUICK_MODE_SKIPS") else 1


def verify_existing() -> int:
    errors: list[str] = []
    errors.extend(verify_artifact_manifest())
    final_path = OUT / "p8e_final_summary.json"
    for stem in REQUIRED_STEMS:
        json_path, md_path = OUT / f"{stem}.json", OUT / f"{stem}.md"
        if not json_path.is_file() or not md_path.is_file():
            errors.append(f"missing pair {stem}")
    final = json.loads(final_path.read_text(encoding="utf-8")) if final_path.is_file() else {}
    if final.get("status") != "PASS": errors.append("final status is not PASS")
    if final.get("NO_HARDWARE_ACTIONS_EXECUTED") is not True: errors.append("hardware flag mismatch")
    if final.get("CURRENT_RUN_HARDWARE_AUTHORIZATION") is not False: errors.append("authorization flag mismatch")
    result = {**COMMON, "status": "PASS" if not errors else "FAIL",
              "test_id": "P8E-VERIFY-EXISTING", "errors": errors,
              "source_commit": final.get("source_commit"),
              "artifact_count": json.loads((RAW / "artifact_sha256_manifest.json").read_text(
                  encoding="utf-8")).get("artifact_count") if (RAW / "artifact_sha256_manifest.json").is_file() else 0}
    print(f"P8E_VERIFY_EXISTING={result['status']}")
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--parent-offline-pass", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--profile", default="all", choices=["all",
        "Z7010_2LANE_DEV_IMPLEMENTATION", "Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION",
        "Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION"])
    parser.add_argument("--strategy", default="all", choices=["all", "Default", "Performance_Explore"])
    args = parser.parse_args(argv)
    if args.verify_existing:
        return verify_existing()
    return run_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
