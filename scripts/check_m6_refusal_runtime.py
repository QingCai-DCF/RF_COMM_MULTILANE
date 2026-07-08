#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "evidence" / "generated" / "hw_preflight" / "refusal_gate"
SUMMARY_MD = ROOT / "evidence" / "generated" / "m6_refusal_runtime.md"
SUMMARY_JSON = ROOT / "evidence" / "generated" / "m6_refusal_runtime.json"

SCRIPTS = [
    {
        "name": "RUN_LANE0_RAW_MATRIX",
        "path": "scripts/hw/run_lane0_raw_matrix_safe.ps1",
        "status_marker": "RUN_LANE0_RAW_MATRIX_SAFE_STATUS=REFUSED_NO_ALLOW_HARDWARE",
        "summary": "run_lane0_raw_matrix_safe.summary.txt",
    },
    {
        "name": "RUN_G1_LANE0_REPLAY",
        "path": "scripts/hw/run_g1_lane0_replay_safe.ps1",
        "status_marker": "RUN_G1_LANE0_REPLAY_SAFE_STATUS=REFUSED_NO_ALLOW_HARDWARE",
        "summary": "run_g1_lane0_replay_safe.summary.txt",
    },
    {
        "name": "PROGRAM_TFDU_SHUTDOWN",
        "path": "scripts/hw/program_tfdu_shutdown_safe.ps1",
        "status_marker": "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=REFUSED_NO_ALLOW_HARDWARE",
        "summary": "program_tfdu_shutdown_safe.summary.txt",
    },
]


def powershell_exe() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def run_wrapper(shell: str, spec: dict) -> dict:
    script_path = ROOT / spec["path"]
    evidence_dir = OUTDIR / spec["name"].lower()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        shell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-EvidenceDir",
        str(evidence_dir),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=60)
    summary_path = evidence_dir / spec["summary"]
    summary = summary_path.read_text(encoding="utf-8", errors="ignore") if summary_path.exists() else ""
    manifest_path = evidence_dir / "hash_manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = {
        "exit_zero": proc.returncode == 0,
        "refused_marker": "REFUSED_NO_ALLOW_HARDWARE=1" in summary,
        "no_hardware_marker": "NO_HARDWARE_ACTIONS_EXECUTED=1" in summary,
        "status_marker": spec["status_marker"] in summary,
        "manifest_exists": manifest_path.exists(),
        "manifest_no_hardware": manifest.get("no_hardware_actions_executed") is True,
        "manifest_allow_false": manifest.get("allow_hardware") is False,
    }
    return {
        "name": spec["name"],
        "returncode": proc.returncode,
        "summary_path": str(summary_path.relative_to(ROOT)).replace("\\", "/"),
        "manifest_path": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "checks": checks,
    }


def main() -> int:
    shell = powershell_exe()
    if not shell:
        print("M6_REFUSAL_RUNTIME=PENDING_TOOL")
        print("POWERSHELL_TOOL_MISSING=1")
        return 0

    OUTDIR.mkdir(parents=True, exist_ok=True)
    results = [run_wrapper(shell, spec) for spec in SCRIPTS]
    all_pass = all(all(item["checks"].values()) for item in results)

    SUMMARY_JSON.write_text(
        json.dumps(
            {
                "status": "PASS" if all_pass else "FAIL",
                "shell": Path(shell).name,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# M6 Runtime Refusal Gate",
        "",
        "M6_REFUSAL_RUNTIME_REPORT=1",
    ]
    for item in results:
        prefix = "M6_" + item["name"]
        for key, ok in item["checks"].items():
            lines.append(f"{prefix}_{key.upper()}={1 if ok else 0}")
    lines.append(f"M6_REFUSAL_RUNTIME={'PASS' if all_pass else 'FAIL'}")
    lines += [
        "",
        "| Wrapper | Summary | Manifest |",
        "|---|---|---|",
    ]
    for item in results:
        lines.append(f"| {item['name']} | `{item['summary_path']}` | `{item['manifest_path']}` |")
    lines += [
        "",
        "This gate executes only the default no-authorization path. It does not pass `-AllowHardware`, and the wrappers must refuse before any hardware action.",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")

    print("M6_REFUSAL_RUNTIME_REPORT=1")
    for item in results:
        prefix = "M6_" + item["name"]
        for key, ok in item["checks"].items():
            print(f"{prefix}_{key.upper()}={1 if ok else 0}")
    print(f"M6_REFUSAL_RUNTIME={'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
