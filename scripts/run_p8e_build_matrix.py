#!/usr/bin/env python3
"""Run exact-part P8E implementation profiles without any hardware access."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
MATRIX = ROOT / "config/p8e_build_matrix.yaml"
VIVADO = pathlib.Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")

CAPACITY = {
    "xc7z010clg400-1": {"LUT": 17600, "FF": 35200, "BRAM36": 60, "DSP": 80},
    "xc7z020clg400-2": {"LUT": 53200, "FF": 106400, "BRAM36": 140, "DSP": 220},
}


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: pathlib.Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def parse_markers(path: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
    return result


def report_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def parse_timing_audit(out_dir: pathlib.Path) -> dict[str, int | float | None]:
    timing = report_text(out_dir / "post_route_timing_summary.rpt")
    check = report_text(out_dir / "post_route_check_timing.rpt")
    unconstrained = re.search(r"checking unconstrained_internal_endpoints \((\d+)\)", check)
    pulse_fail: int | None = None
    wpws: float | None = None
    if "| Design Timing Summary" in timing:
        section = timing.split("| Design Timing Summary", 1)[1]
        for line in section.splitlines():
            fields = line.split()
            if len(fields) < 12:
                continue
            try:
                float(fields[0]); float(fields[1]); float(fields[4]); float(fields[8])
                wpws = float(fields[8])
                pulse_fail = int(fields[10])
                break
            except ValueError:
                continue
    return {
        "unconstrained_internal_endpoints": int(unconstrained.group(1)) if unconstrained else None,
        "pulse_width_violations": pulse_fail,
        "worst_pulse_width_slack_ns": wpws,
    }


def parse_cdc_audit(out_dir: pathlib.Path) -> dict[str, int]:
    cdc = report_text(out_dir / "post_route_cdc.rpt")
    clock_interaction = report_text(out_dir / "post_route_clock_interaction.rpt")
    non_info_rows = re.findall(
        r"^\s*CDC-\d+\s+(Critical Warning|Critical|Warning|Unknown)\s+\d+\s+(.+)$",
        cdc, flags=re.MULTILINE)
    unsafe_multibit = sum(
        1 for _severity, description in non_info_rows
        if re.search(r"multi.?bit|combinational|unknown", description, flags=re.IGNORECASE)
    )
    unclassified = sum(1 for severity, description in non_info_rows
                       if severity == "Unknown" or "unknown" in description.lower())
    unexplained_clock = len(re.findall(
        r"Unsafe|Unconstrained|No Common Clock|Partial False Path",
        clock_interaction, flags=re.IGNORECASE))
    return {
        "cdc_non_info": len(non_info_rows),
        "cdc_unclassified": unclassified,
        "unsafe_multibit": unsafe_multibit,
        "unexplained_clock_interactions": unexplained_clock,
    }


def parse_exception_audit(out_dir: pathlib.Path) -> dict[str, object]:
    exceptions = report_text(out_dir / "post_route_exceptions.rpt")
    rows = [line.strip() for line in exceptions.splitlines()
            if re.match(r"^\s*\d+\s+\[get_clocks", line)]
    reviewed = [line for line in rows if line.count("clock_group") >= 2]
    unreviewed = [line for line in rows if line not in reviewed]
    broad_or_delay = [line for line in rows if re.search(
        r"false_path|max_delay|min_delay|multicycle", line, flags=re.IGNORECASE)]
    return {
        "exception_rows": len(rows),
        "reviewed_named_clock_group_rows": len(reviewed),
        "expected_named_clock_group_rows": 6,
        "unreviewed_exception_rows": len(unreviewed),
        "unreviewed_false_path_or_max_min_delay_rows": len(broad_or_delay),
        "unreviewed_rows": unreviewed,
    }


def parse_methodology_audit(out_dir: pathlib.Path) -> dict[str, object]:
    methodology = report_text(out_dir / "post_route_methodology.rpt")
    critical = len(re.findall(
        r"^\|\s*[^|]+\|\s*(?:Critical Warning|Error)\s*\|",
        methodology, flags=re.MULTILINE))
    warning_rows = re.findall(
        r"^\|\s*([A-Z0-9-]+)\s*\|\s*Warning\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|",
        methodology, flags=re.MULTILINE)
    classifications = {
        "LUTAR-1": (
            "INTENTIONAL_FAIL_LOW_ASYNC_ASSERTION: raw GLOBAL_PERMIT/reset may only "
            "clear permit filter and arm state; raw permit low also directly gates final Txd."
        ),
        "TIMING-18": (
            "EXTERNAL_IO_CONTRACT_PENDING: no zero-nanosecond I/O delay is fabricated; "
            "Z7020 remains PENDING_D12 and Z7010 external timing remains platform follow-up."
        ),
    }
    classified = [
        {"rule": rule, "description": description.strip(), "violation_count": int(count),
         "classification": classifications.get(rule)}
        for rule, description, count in warning_rows
    ]
    unclassified = [item["rule"] for item in classified if item["classification"] is None]
    return {"critical_methodology": critical,
            "methodology_warning_rules": len(warning_rows),
            "classified_warning_rules": classified,
            "unclassified_methodology_warning_rules": len(unclassified),
            "unclassified_warning_rule_ids": unclassified}


def float_marker(markers: dict[str, str], key: str) -> float | None:
    try:
        return float(markers[key])
    except (KeyError, ValueError):
        return None


def int_marker(markers: dict[str, str], key: str) -> int | None:
    try:
        return int(markers[key])
    except (KeyError, ValueError):
        return None


def tcl_quote(value: pathlib.Path | str) -> str:
    return "{" + str(value).replace("\\", "/") + "}"


def make_tcl_config(profile: dict, strategy: dict, manifest: dict,
                    out_dir: pathlib.Path) -> pathlib.Path:
    lines = [
        f"set p8e_profile_id {tcl_quote(profile['profile_id'])}",
        f"set p8e_strategy_id {tcl_quote(strategy['id'])}",
        f"set p8e_part {tcl_quote(profile['part'])}",
        f"set p8e_top {tcl_quote(profile['top_module'])}",
        f"set p8e_out_dir {tcl_quote(out_dir.resolve())}",
        f"set p8e_synth_directive {tcl_quote(strategy['synth_directive'])}",
        f"set p8e_place_directive {tcl_quote(strategy['place_directive'])}",
        f"set p8e_phys_opt_directive {tcl_quote(strategy['phys_opt_directive'])}",
        f"set p8e_route_directive {tcl_quote(strategy['route_directive'])}",
        f"set p8e_seed {int(strategy['seed'])}",
        "set p8e_include_dirs [list " + " ".join(
            tcl_quote((ROOT / item).resolve()) for item in manifest["include_directories"]) + "]",
        "set p8e_sources [list " + " ".join(
            tcl_quote((ROOT / item).resolve()) for item in manifest["source_order"]) + "]",
        "set p8e_constraints [list " + " ".join(
            tcl_quote((ROOT / item).resolve()) for item in manifest["constraints"]) + "]",
    ]
    path = out_dir / "build_config.tcl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def audit_outputs(profile: dict, strategy: dict, out_dir: pathlib.Path,
                  returncode: int, log_path: pathlib.Path) -> dict:
    markers = parse_markers(out_dir / "build_markers.txt")
    wns = float_marker(markers, "P8E_SETUP_WNS_NS")
    whs = float_marker(markers, "P8E_HOLD_WHS_NS")
    tns = float_marker(markers, "P8E_TNS_NS")
    timing_audit = parse_timing_audit(out_dir)
    cdc_audit = parse_cdc_audit(out_dir)
    exception_audit = parse_exception_audit(out_dir)
    methodology_audit = parse_methodology_audit(out_dir)
    resources = {name: int_marker(markers, f"P8E_{name}") for name in
                 ("LUT", "FF", "BRAM36", "BRAM18", "DSP")}
    capacity = CAPACITY[profile["part"]]
    bram_equivalent = (resources["BRAM36"] or 0) + (resources["BRAM18"] or 0) / 2.0
    percentages = {
        "LUT": 100.0 * (resources["LUT"] or 0) / capacity["LUT"],
        "FF": 100.0 * (resources["FF"] or 0) / capacity["FF"],
        "BRAM36": 100.0 * bram_equivalent / capacity["BRAM36"],
        "DSP": 100.0 * (resources["DSP"] or 0) / capacity["DSP"],
    }
    limits = (85, 70, 75, 75) if profile["part"].startswith("xc7z010") else (70, 70, 75, 75)
    resource_pass = all(value <= limit for value, limit in zip(
        (percentages["LUT"], percentages["FF"], percentages["BRAM36"], percentages["DSP"]), limits))
    required_reports = [
        "post_synth.dcp", "post_synth_funcsim.v", "post_route.dcp",
        "post_route_utilization.rpt", "post_route_timing_summary.rpt",
        "post_route_setup_paths.rpt", "post_route_hold_paths.rpt", "post_route_cdc.rpt",
        "post_route_clock_interaction.rpt", "post_route_check_timing.rpt",
        "post_route_exceptions.rpt", "post_route_drc.rpt", "post_route_methodology.rpt",
        "post_route_power.rpt", "post_route_pulse_width.rpt",
    ]
    reports_present = all((out_dir / name).is_file() for name in required_reports)
    status = "PASS" if all((returncode == 0, reports_present, wns is not None and wns >= 0,
                            whs is not None and whs >= 0, tns is not None and abs(tns) < 1e-6,
                            timing_audit["unconstrained_internal_endpoints"] == 0,
                            timing_audit["pulse_width_violations"] == 0,
                            int_marker(markers, "P8E_REQP_1839") == 0,
                            int_marker(markers, "P8E_DRC_CRITICAL") == 0,
                            int_marker(markers, "P8E_DRC_ERROR") == 0,
                            int_marker(markers, "P8E_CDC_CRITICAL") == 0,
                            cdc_audit["cdc_unclassified"] == 0,
                            cdc_audit["unsafe_multibit"] == 0,
                            cdc_audit["unexplained_clock_interactions"] == 0,
                            exception_audit["exception_rows"] == 6,
                            exception_audit["reviewed_named_clock_group_rows"] == 6,
                            exception_audit["unreviewed_exception_rows"] == 0,
                            exception_audit["unreviewed_false_path_or_max_min_delay_rows"] == 0,
                            methodology_audit["critical_methodology"] == 0,
                            methodology_audit["unclassified_methodology_warning_rules"] == 0,
                            resource_pass)) else "FAIL"
    artifacts = []
    if out_dir.is_dir():
        for item in sorted(out_dir.iterdir()):
            if item.is_file():
                artifacts.append({"path": rel(item), "sha256": sha256(item), "bytes": item.stat().st_size})
    return {
        "status": status, "profile_id": profile["profile_id"], "strategy": strategy["id"],
        "strategy_seed": int(strategy["seed"]), "part": profile["part"],
        "top_module": profile["top_module"], "returncode": returncode,
        "setup_wns_ns": wns, "hold_whs_ns": whs, "tns_ns": tns,
        "timing_audit": timing_audit, "cdc_audit": cdc_audit,
        "exception_audit": exception_audit,
        "methodology_audit": methodology_audit,
        "resources": resources, "utilization_percent": percentages,
        "resource_limits_pass": resource_pass, "markers": markers,
        "required_reports_present": reports_present, "vivado_log": rel(log_path),
        "artifacts": artifacts,
    }


def audit_run(profile: dict, strategy: dict, manifest: dict,
              out_dir: pathlib.Path, timeout: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = make_tcl_config(profile, strategy, manifest, out_dir)
    log_path = out_dir / "vivado_stdout_stderr.log"
    command = [str(VIVADO), "-mode", "batch", "-nolog", "-nojournal",
               "-source", str(ROOT / "scripts/vivado/run_p8e_build.tcl"),
               "-tclargs", str(cfg)]
    started = datetime.now(timezone.utc).isoformat()
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                   timeout=timeout, env=os.environ.copy())
        returncode = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTIMEOUT_SECONDS={timeout}\n"
    log_path.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"STARTED_UTC={started}\nRETURN_CODE={returncode}\n" +
        "STDOUT_BEGIN\n" + stdout + "\nSTDOUT_END\nSTDERR_BEGIN\n" + stderr +
        "\nSTDERR_END\n", encoding="utf-8", errors="replace")
    return audit_outputs(profile, strategy, out_dir, returncode, log_path)


def validate_manifest(profile: dict, manifest: dict) -> list[str]:
    errors = []
    if manifest.get("profile_id") != profile["profile_id"]:
        errors.append("profile_id mismatch")
    if manifest.get("part") != profile["part"] or manifest.get("top_module") != profile["top_module"]:
        errors.append("part/top mismatch")
    for source in manifest.get("source_order", []):
        if not (ROOT / source).is_file(): errors.append(f"missing source {source}")
        if source.startswith(("legacy/", "rtl/legacy_reference/", "docs/legacy/")):
            errors.append(f"legacy source active {source}")
    for constraint in manifest.get("constraints", []):
        if not (ROOT / constraint).is_file(): errors.append(f"missing constraint {constraint}")
    if profile["part"].startswith("xc7z020"):
        if any("PORT1.generated.xdc" in item for item in manifest.get("constraints", [])):
            errors.append("Z7010 XDC contamination")
        if profile.get("board_xdc") != "PENDING_D12": errors.append("invented Z7020 board XDC")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="all")
    parser.add_argument("--strategy", default="all")
    parser.add_argument("--output-root", type=pathlib.Path,
                        default=ROOT / "evidence/generated/p8e_raw/build_matrix")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    args = parser.parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1" or \
       os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P8E_BUILD_REFUSED: NO_HARDWARE=1 and authorization=false are required", file=sys.stderr)
        return 2
    if not VIVADO.is_file():
        print(f"Vivado not found: {VIVADO}", file=sys.stderr); return 2
    matrix = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    profiles = matrix["profiles"]
    strategies = matrix["strategies"]
    if args.profile != "all":
        profiles = [item for item in profiles if item["profile_id"] == args.profile]
    if args.strategy != "all":
        strategies = [item for item in strategies if item["id"] == args.strategy]
    if not profiles or not strategies:
        print("No matching profile/strategy", file=sys.stderr); return 2
    args.output_root.mkdir(parents=True, exist_ok=True)
    results = []
    manifest_errors = {}
    for profile in profiles:
        manifest_path = ROOT / profile["source_manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        errors = validate_manifest(profile, manifest)
        manifest_errors[profile["profile_id"]] = errors
        if errors:
            continue
        for strategy in strategies:
            out_dir = args.output_root / profile["profile_id"] / strategy["id"]
            if args.verify_existing:
                result = audit_outputs(profile, strategy, out_dir, 0,
                                       out_dir / "vivado_stdout_stderr.log")
            else:
                result = audit_run(profile, strategy, manifest, out_dir, args.timeout_seconds)
            results.append(result)
    per_profile = {}
    for profile in profiles:
        runs = [r for r in results if r["profile_id"] == profile["profile_id"]]
        passing = [r for r in runs if r["status"] == "PASS"]
        per_profile[profile["profile_id"]] = {
            "status": "PASS" if len(passing) == len(strategies) and not manifest_errors[profile["profile_id"]] else "FAIL",
            "passing_run_count": len(passing), "required_run_count": len(strategies),
            "best_setup_wns_ns": max((r.get("setup_wns_ns") for r in passing), default=None),
        }
    status = "PASS" if results and all(r["status"] == "PASS" for r in results) and \
        not any(manifest_errors.values()) else "FAIL"
    summary = {
        "schema_version": 1, "status": status,
        "test_id": "P8E-DUAL-TARGET-BUILD-MATRIX",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "matrix_sha256": sha256(MATRIX), "manifest_errors": manifest_errors,
        "profiles": per_profile, "runs": results,
    }
    summary_path = args.output_root / "build_matrix_run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"P8E_BUILD_MATRIX_STATUS={status}")
    print(f"P8E_BUILD_MATRIX_SUMMARY={rel(summary_path)}")
    if args.json_summary: print(json.dumps(summary, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
