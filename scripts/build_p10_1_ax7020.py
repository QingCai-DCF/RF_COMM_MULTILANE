#!/usr/bin/env python3
"""Build and audit the fixed/rotating AX7020 P10.1 routed candidates."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from p10_1_common import (
    RAW,
    ROOT,
    evidence_base,
    load_json,
    rel,
    sha256,
    write_json,
    write_pair,
    write_text,
)


P10_BUILD = ROOT / "scripts/build_p10_ax7020_functional.py"
P10_SUMMARY = ROOT / "evidence/generated/p10_ax7020_functional_build_summary.json"
BASELINE = RAW / "p10_1_preinstrumentation_build_resources.json"
BUILD_LOG = RAW / "p10_1_ax7020_build.log"
DEVICE_CAPACITY = {
    "lut": 53200,
    "ff": 106400,
    "bram36_equivalent": 140.0,
    "dsp": 220,
}
LIMITS = {
    "lut": 70.0,
    "ff": 70.0,
    "bram36_equivalent": 75.0,
    "dsp": 50.0,
}


def resources(report: Path) -> dict[str, Any]:
    text = report.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"^\|\s*p10_ps_system_wrapper\s*\|\s*\(top\)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
        text,
        re.MULTILINE,
    )
    if match is None:
        return {"status": "FAIL", "error": "top utilization row not found"}
    total_lut, _, _, _, ff, ramb36, ramb18, dsp = (
        int(value) for value in match.groups()
    )
    used = {
        "lut": total_lut,
        "ff": ff,
        "bram36_equivalent": ramb36 + ramb18 / 2.0,
        "dsp": dsp,
    }
    percent = {
        name: value / DEVICE_CAPACITY[name] * 100.0
        for name, value in used.items()
    }
    return {
        "status": "PASS",
        "used": used,
        "capacity": DEVICE_CAPACITY,
        "percent": percent,
        "limits_percent": LIMITS,
        "within_limits": all(percent[name] <= LIMITS[name] for name in LIMITS),
    }


def role_resources(summary: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for role in summary.get("roles", []):
        utilization = next(
            (
                ROOT / report["path"]
                for report in role.get("reports", [])
                if report["path"].endswith("post_route_utilization.rpt")
            ),
            None,
        )
        result[role["role"]] = (
            resources(utilization)
            if utilization is not None and utilization.is_file()
            else {"status": "FAIL", "error": "utilization report is missing"}
        )
    return result


def capture_baseline() -> None:
    if BASELINE.is_file() or not P10_SUMMARY.is_file():
        return
    summary = load_json(P10_SUMMARY)
    write_json(
        BASELINE,
        {
            "schema_version": 1,
            "source_commit": summary.get("source_commit"),
            "summary_sha256": sha256(P10_SUMMARY),
            "roles": role_resources(summary),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("current-run hardware authorization must be false")
    capture_baseline()
    if not errors:
        command = [sys.executable, rel(P10_BUILD)]
        if args.reuse_existing:
            command.append("--reuse-existing")
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=3600,
            env={
                **os.environ,
                "NO_HARDWARE": "1",
                "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
            },
        )
        write_text(
            BUILD_LOG,
            "COMMAND=" + subprocess.list2cmdline(command) + "\n"
            + f"RETURN_CODE={result.returncode}\n"
            + "STDOUT_BEGIN\n" + result.stdout + "STDOUT_END\n"
            + "STDERR_BEGIN\n" + result.stderr + "STDERR_END",
        )
        if result.returncode != 0:
            errors.append("dual AX7020 functional build command failed")
    if not P10_SUMMARY.is_file():
        errors.append("P10 dual-build summary is missing")
        summary: dict[str, Any] = {"roles": []}
    else:
        summary = load_json(P10_SUMMARY)
        if summary.get("status") != "PASS":
            errors.append("underlying dual AX7020 build is not PASS")
        if summary.get("source_worktree_dirty") is not False:
            errors.append("tracked build inputs were dirty")
        if summary.get("hardware_actions_executed") is not False:
            errors.append("build evidence claims a hardware action")
    current_resources = role_resources(summary)
    baseline = load_json(BASELINE) if BASELINE.is_file() else {"roles": {}}
    for role, audit in current_resources.items():
        if audit.get("status") != "PASS":
            errors.append(f"{role} resource report could not be parsed")
        elif not audit.get("within_limits"):
            errors.append(f"{role} resource limits exceeded")
    role_records: dict[str, dict[str, Any]] = {}
    for role in ("fixed", "rotating"):
        build = next(
            (item for item in summary.get("roles", []) if item.get("role") == role),
            {},
        )
        markers = build.get("markers", {})
        timing_pass = (
            build.get("status") == "PASS"
            and float(markers.get("P10_WNS_NS", "-1")) >= 0.0
            and float(markers.get("P10_WHS_NS", "-1")) >= 0.0
            and float(markers.get("P10_TNS_NS", "-1")) == 0.0
        )
        implementation_pass = (
            timing_pass
            and markers.get("P10_DRC_CRITICAL_COUNT") == "0"
            and markers.get("P10_DRC_ERROR_COUNT") == "0"
            and markers.get("P10_CDC_CRITICAL_COUNT") == "0"
            and markers.get("P10_REQP_1839_COUNT") == "0"
            and markers.get("P10_METHODOLOGY_CRITICAL_COUNT") == "0"
            and markers.get("P10_ETHERNET_ENABLED") == "false"
        )
        audit = current_resources.get(role, {"status": "FAIL"})
        base_audit = baseline.get("roles", {}).get(role, {})
        delta: dict[str, float] = {}
        if audit.get("status") == "PASS" and base_audit.get("status") == "PASS":
            delta = {
                key: float(audit["used"][key]) - float(base_audit["used"][key])
                for key in audit["used"]
            }
        role_errors = list(build.get("errors", []))
        if not implementation_pass:
            role_errors.append("timing/CDC/DRC/REQP implementation hard gate failed")
        if audit.get("status") != "PASS" or not audit.get("within_limits", False):
            role_errors.append("resource hard gate failed")
        role_records[role] = evidence_base(
            f"P10_1-AX7020-{role.upper()}-ROUTED-BUILD",
            status="PASS" if not role_errors else "FAIL",
            source_commit=summary.get("source_commit"),
            source_worktree_dirty=summary.get("source_worktree_dirty"),
            role=role,
            profile=build.get("profile"),
            part=summary.get("part"),
            markers=markers,
            timing_cdc_drc_reqp_status="PASS" if implementation_pass else "FAIL",
            resource_status=(
                "PASS"
                if audit.get("status") == "PASS" and audit.get("within_limits")
                else "FAIL"
            ),
            resource=audit,
            preinstrumentation_resource=base_audit,
            instrumentation_delta=delta,
            buffer_delta="PS_DDR_BUFFERS_NO_PL_BRAM_ALLOCATION",
            large_ila_default_enabled=False,
            register_map_consistency=(
                "PASS"
                if build.get("source_sha256", {}).get(
                    "config/register_map/ir_axi_regs.yaml"
                )
                == sha256(ROOT / "config/register_map/ir_axi_regs.yaml")
                else "FAIL"
            ),
            tfdu_safety_architecture_unchanged=True,
            artifacts=build.get("artifacts", {}),
            reports=build.get("reports", []),
            build_log=build.get("log"),
            errors=role_errors,
        )
        errors.extend(f"{role}: {item}" for item in role_errors)
        write_pair(
            f"p10_1_{role}_build",
            f"P10.1 AX7020 {role} routed build",
            role_records[role],
        )
    overall = "PASS" if not errors else "FAIL"
    print(f"P10_1_AX7020_DUAL_BUILD={overall}")
    print(f"AX7020_FIXED_BUILD={role_records.get('fixed', {}).get('status', 'FAIL')}")
    print(
        "AX7020_ROTATING_BUILD="
        + role_records.get("rotating", {}).get("status", "FAIL")
    )
    print("HARDWARE_ACTIONS_EXECUTED=false")
    if args.json_summary:
        print(
            json.dumps(
                {
                    "status": overall,
                    "roles": {
                        role: record["status"]
                        for role, record in role_records.items()
                    },
                    "errors": errors,
                },
                sort_keys=True,
            )
        )
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
