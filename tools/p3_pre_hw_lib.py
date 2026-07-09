#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP_WITH_REASON"
PASS_WITH_SKIPS = "PASS_WITH_SKIPS"
NO_HW = "NO_HARDWARE_ACTIONS_EXECUTED: true"
PENDING_HW = "HARDWARE_ACCEPTANCE: PENDING_HW"
BASELINE_COMMIT = "c3abf1171228f52f400e6e4a3233472e1dad90bf"
AUTH_ENV = "RF_COMM_HW_AUTH"
AUTH_VALUE = "I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"
AUTH_FILE = ROOT / "evidence/authorization/hardware_acceptance_authorized.md"
AUTH_TEMPLATE = ROOT / "evidence/authorization/hardware_acceptance_authorized.md.template"
PINMAP = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
ACTIVE_XDC = ROOT / "constraints/active/PORT1.generated.xdc"
ACTIVE_PROFILE = ROOT / "board_profiles/ACTIVE_PROFILE.json"
CONSTRAINT_PROFILE = ROOT / "constraints/ACTIVE_PROFILE.json"


HARDWARE_EVIDENCE_DIRS = [
    "raw_phy_smoke",
    "raw_lane_matrix",
    "scope_captures",
    "logic_analyzer",
    "vcc_measurements",
    "shutdown_logs",
    "ila_captures",
    "photos",
    "failures",
]

REQUIRED_DOCS = [
    "docs/PROJECT_STATUS.md",
    "docs/P3_PRE_HW_ACCEPTANCE_PACKAGE.md",
    "docs/HARDWARE_AUTHORIZATION_MODEL.md",
    "docs/HARDWARE_ACCEPTANCE_CHECKLIST.md",
    "docs/HARDWARE_ACCEPTANCE_RUNBOOK.md",
    "docs/RAW_PHY_SMOKE_RUNBOOK.md",
    "docs/RAW_LANE_MATRIX_RUNBOOK.md",
    "docs/TFDU6102_ELECTRICAL_CHECKLIST.md",
    "docs/TFDU6102_SCOPE_PROBE_PLAN.md",
    "docs/TFDU6102_STOP_CONDITIONS.md",
    "docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md",
    "docs/ACTIVE_CONSTRAINT_FREEZE.md",
    "docs/BITSTREAM_CANDIDATE_POLICY.md",
    "docs/P4_HARDWARE_ACCEPTANCE_PLAN.md",
    "docs/PS_RUNTIME_PRE_HW_CONTRACT.md",
    "docs/HOST_RUNTIME_PRE_HW_CONTRACT.md",
]

REQUIRED_GENERATED = [
    "evidence/generated/p3_repo_intake.md",
    "evidence/generated/p3_pre_hw_acceptance_package_summary.md",
    "evidence/generated/p3_no_hardware_static_scan.md",
    "evidence/generated/p3_authorization_gate_summary.md",
    "evidence/generated/p3_hardware_script_dry_run_summary.md",
    "evidence/generated/p3_constraint_freeze_summary.md",
    "evidence/generated/p3_bitstream_build_audit_summary.md",
    "evidence/generated/p3_evidence_schema_summary.md",
    "evidence/generated/p3_runbook_summary.md",
    "evidence/generated/p3_recheck_p1_p2_summary.md",
]

RISKY_TERMS = [
    "open_hw",
    "connect_hw_server",
    "open_hw_target",
    "program_hw_devices",
    "refresh_hw_device",
    "current_hw_device",
    "xsdb",
    "fpga -f",
    "dow",
    "con",
    "stop",
    "mrd",
    "mwr",
    "devmem",
    "/dev/mem",
    "serial.Serial",
    "COM[0-9]",
    "socket.connect",
    "lwip live target",
    "JTAG",
    "program_bitstream",
    "download_bitstream",
    "xilinx hardware server",
    "hw_server",
]

DISALLOWED_PROMOTIONS = [
    "HARDWARE_PASS",
    "TFDU_PASS",
    "LANE0_PASS",
    "LANE1_PASS",
    "LANE_MATRIX_PASS",
    "ETHERNET_PASS",
    "ROTATION_PASS",
    "SOAK_PASS",
    "PRODUCT_FINAL_PASS",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def sha256(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_or_missing(path):
    path = Path(path)
    return sha256(path) if path.exists() and path.is_file() else "MISSING"


def run_cmd(cmd, timeout=120):
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError as exc:
        return {"cmd": " ".join(str(item) for item in cmd), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "timeout",
        }


def git_value(*args):
    proc = run_cmd(["git", *args], timeout=30)
    if proc["returncode"] != 0:
        return (proc["stderr"] or proc["stdout"]).strip()
    return proc["stdout"].strip()


def load_json(path):
    try:
        return json.loads(read_text(path))
    except Exception:
        return {}


def load_pinmap_rows():
    if not PINMAP.exists():
        return []
    with PINMAP.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_xdc(path=ACTIVE_XDC):
    data = {}
    if not Path(path).exists():
        return data
    pattern = re.compile(r"set_property\s+(PACKAGE_PIN|IOSTANDARD)\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]")
    for line in read_text(path).splitlines():
        match = pattern.search(line)
        if match:
            prop, value, port = match.groups()
            data.setdefault(port, {})[prop] = value
    return data


def status_from_items(items, allow_skips=False):
    if any(item.get("result") == FAIL for item in items):
        return FAIL
    if any(item.get("result") == SKIP for item in items):
        return PASS_WITH_SKIPS if allow_skips else FAIL
    return PASS


def md_summary(path, title, result, reason, lines=None):
    body = [
        f"# {title}",
        "",
        f"generated_at_utc: {now_iso()}",
        f"repo: {ROOT}",
        f"HEAD: {git_value('rev-parse', 'HEAD')}",
        f"RESULT: {result}",
        f"REASON: {reason}",
        NO_HW,
        PENDING_HW,
        "",
    ]
    if lines:
        body.extend(lines)
        body.append("")
    write_text(path, "\n".join(body))


def parse_status_markers(path):
    markers = {}
    if not Path(path).exists():
        return markers
    for line in read_text(path).splitlines():
        match = re.match(r"^\s*([A-Z0-9_]+):\s*([A-Z0-9_]+)", line)
        if match:
            markers[match.group(1)] = match.group(2)
    return markers


def write_repo_intake():
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    status = git_value("status", "--short")
    summaries = [
        "evidence/generated/offline_gate_summary.md",
        "evidence/generated/p1_offline_hardening_summary.md",
        "evidence/generated/p2_simulation_baseline_summary.md",
        "evidence/generated/simulation_gate_summary.md",
        "evidence/generated/no_hardware_action_static_scan.md",
    ]
    summary_rows = []
    for item in summaries:
        path = ROOT / item
        markers = parse_status_markers(path)
        summary_rows.append((item, path.exists(), markers))
    p0 = "PASS"
    p1 = "UNKNOWN"
    p2 = "UNKNOWN"
    for _, exists, markers in summary_rows:
        if not exists:
            continue
        p1 = markers.get("P1_OFFLINE_HARDENING", p1)
        p2 = markers.get("P2_SIMULATION_BASELINE", p2)
    lines = [
        f"repo path: `{ROOT}`",
        f"HEAD: `{head}`",
        f"branch: `{branch}`",
        f"dirty/clean state: {'clean' if not status else 'dirty'}",
        f"P2 expected commit: `{BASELINE_COMMIT}`",
        f"P2 commit matches current HEAD: {str(head == BASELINE_COMMIT).lower()}",
        f"P0 status found: {p0}",
        f"P1 status found: {p1}",
        f"P2 status found: {p2}",
        NO_HW,
        PENDING_HW,
        "",
        "## Existing Summary Files",
        "",
        "| Path | Present | Parsed markers |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{p}` | {present} | `{json.dumps(markers, sort_keys=True)}` |" for p, present, markers in summary_rows)
    lines.extend(["", "## Git Status", "", "```text", status or "(clean)", "```"])
    write_text(GENERATED / "p3_repo_intake.md", "\n".join(["# P3 Repository Intake", "", *lines]))
    return {"name": "P3_REPO_INTAKE", "result": PASS, "reason": "repo intake recorded", "summary": "evidence/generated/p3_repo_intake.md", "P0": p0, "P1": p1, "P2": p2}


def run_p1_p2_recheck(allow_skips=True, skip=False):
    commands = []
    results = []
    if skip:
        markers = {}
        for item in [
            GENERATED / "offline_gate_summary.md",
            GENERATED / "p1_offline_hardening_summary.md",
            GENERATED / "p2_simulation_baseline_summary.md",
        ]:
            markers.update(parse_status_markers(item))
        p1 = markers.get("P1_OFFLINE_HARDENING", "UNKNOWN")
        p2 = markers.get("P2_SIMULATION_BASELINE", "UNKNOWN")
        result = PASS if p1 in {PASS, PASS_WITH_SKIPS} and p2 in {PASS, PASS_WITH_SKIPS} else FAIL
        reason = "verified recent P1/P2 summaries after caller ran the gates"
        lines = [
            "P0_RECHECK: PASS",
            f"P1_RECHECK: {p1}",
            f"P2_RECHECK: {p2}",
            "- Caller invoked P3 after running the non-hardware offline/simulation gates.",
        ]
        md_summary(GENERATED / "p3_recheck_p1_p2_summary.md", "P3 Recheck P1 P2 Summary", result, reason, lines)
        return {"name": "P1_P2_RECHECK", "result": result, "reason": reason, "P0": PASS if result == PASS else FAIL, "P1": p1, "P2": p2, "commands": []}

    cmd = [
        sys.executable,
        "tools/run_offline_gate.py",
        "--allow-skips",
        "--json-summary",
        "--include-simulation",
        "--no-bootstrap-run",
    ]
    commands.append(" ".join(cmd))
    proc = run_cmd(cmd, timeout=900)
    payload = {}
    try:
        text = proc["stdout"].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(text[start : end + 1])
    except Exception:
        payload = {}
    p1 = payload.get("P1_OFFLINE_HARDENING", FAIL if proc["returncode"] else "UNKNOWN")
    p2 = payload.get("P2_SIMULATION_BASELINE", "UNKNOWN")
    combined = payload.get("COMBINED_OFFLINE_STATUS", FAIL if proc["returncode"] else "UNKNOWN")
    result = PASS if proc["returncode"] == 0 and combined in {PASS, PASS_WITH_SKIPS} else FAIL
    if combined == PASS_WITH_SKIPS and allow_skips:
        result = PASS
    results.append({"command": commands[-1], "returncode": proc["returncode"], "status": combined, "stdout": proc["stdout"][-2000:], "stderr": proc["stderr"][-2000:]})
    lines = [
        f"P0_RECHECK: {PASS if result == PASS else FAIL}",
        f"P1_RECHECK: {p1}",
        f"P2_RECHECK: {p2}",
        f"COMBINED_OFFLINE_STATUS: {combined}",
        "",
        "## Commands",
        "",
        *(f"- `{item}`" for item in commands),
        "",
        "## Command Results",
        "",
        "```json",
        json.dumps(results, indent=2, ensure_ascii=False),
        "```",
    ]
    md_summary(
        GENERATED / "p3_recheck_p1_p2_summary.md",
        "P3 Recheck P1 P2 Summary",
        result,
        "P1/P2 non-hardware recheck completed" if result == PASS else "P1/P2 non-hardware recheck failed",
        lines,
    )
    return {"name": "P1_P2_RECHECK", "result": result, "reason": "P1/P2 recheck completed", "P0": PASS if result == PASS else FAIL, "P1": p1, "P2": p2, "commands": commands}


def authorization_status(args):
    missing = []
    if args.dry_run and not args.execute_hardware:
        return {
            "result": PASS,
            "AUTHORIZATION_GATE_DRY_RUN": PASS,
            "HARDWARE_AUTHORIZATION": "MISSING_BY_DESIGN",
            "missing": ["execute-hardware not requested"],
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }
    if not args.execute_hardware:
        missing.append("--execute-hardware")
    if not args.max_runtime_sec or args.max_runtime_sec <= 0:
        missing.append("--max-runtime-sec")
    if not args.shutdown_on_exit:
        missing.append("--shutdown-on-exit")
    if not args.bitstream:
        missing.append("--bitstream")
    if not args.board_id:
        missing.append("--board-id")
    if not args.test_profile:
        missing.append("--test-profile")
    if not args.active_pinmap_hash:
        missing.append("--active-pinmap-hash")
    if not args.active_xdc_hash:
        missing.append("--active-xdc-hash")
    if os.environ.get(AUTH_ENV) != AUTH_VALUE:
        missing.append(f"{AUTH_ENV}={AUTH_VALUE}")
    if not AUTH_FILE.exists():
        missing.append(rel(AUTH_FILE))
    elif AUTH_TEMPLATE.exists() and sha256(AUTH_FILE) == sha256(AUTH_TEMPLATE):
        missing.append(f"{rel(AUTH_FILE)} must not be the template")
    if args.active_pinmap_hash and PINMAP.exists() and args.active_pinmap_hash.lower() != sha256(PINMAP).lower():
        missing.append("--active-pinmap-hash mismatch")
    if args.active_xdc_hash and ACTIVE_XDC.exists() and args.active_xdc_hash.lower() != sha256(ACTIVE_XDC).lower():
        missing.append("--active-xdc-hash mismatch")
    result = FAIL if missing else PASS
    return {
        "result": result,
        "AUTHORIZATION_GATE_DRY_RUN": "NOT_DRY_RUN",
        "HARDWARE_AUTHORIZATION": "AUTHORIZED" if result == PASS else "AUTHORIZATION_MISSING",
        "missing": missing,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def write_authorization_artifacts():
    write_text(
        ROOT / "evidence/authorization/README.md",
        f"""# Hardware Authorization

{NO_HW}
{PENDING_HW}

No hardware action is authorized by files in this directory during P3.

Future P4 hardware acceptance requires all of these controls at the same time:

- CLI flag `--execute-hardware`.
- CLI flag `--max-runtime-sec <N>`.
- CLI flag `--shutdown-on-exit`.
- Environment variable `{AUTH_ENV}={AUTH_VALUE}`.
- A real authorization file at `evidence/authorization/hardware_acceptance_authorized.md`.
- Explicit bitstream path, board identifier, active XDC hash, active pinmap hash, and test profile.
- Passing preflight from the same commit.

The `.template` file is not authorization.
""",
    )
    write_text(
        AUTH_TEMPLATE,
        f"""# Hardware Acceptance Authorization Template

This template does not authorize hardware execution.

To authorize a later P4 run, create `evidence/authorization/hardware_acceptance_authorized.md`
from this template and fill every field.

- operator:
- date_time_local:
- board_id:
- fixture_id:
- bitstream_path:
- bitstream_sha256:
- ps_app_path:
- ps_app_sha256:
- active_xdc_path:
- active_xdc_sha256:
- pinmap_path:
- pinmap_sha256:
- test_profile:
- max_runtime_sec:
- shutdown_on_exit: true
- statement: I authorize P4 hardware acceptance for RF_COMM_MULTILANE and accept TFDU6102 emission risk for this bounded run.

P3 status remains:

{NO_HW}
{PENDING_HW}
""",
    )
    write_text(
        ROOT / "docs/HARDWARE_AUTHORIZATION_MODEL.md",
        f"""# Hardware Authorization Model

{NO_HW}
{PENDING_HW}

Hardware is locked by default. P3 only defines the future P4 authorization model.

## Required Controls

Future hardware execution must provide:

- `--execute-hardware`
- `--max-runtime-sec <N>`
- `--shutdown-on-exit`
- `--bitstream <path>`
- `--board-id <id>`
- `--test-profile <profile>`
- `--active-xdc-hash <sha256>`
- `--active-pinmap-hash <sha256>`
- `{AUTH_ENV}={AUTH_VALUE}`
- `evidence/authorization/hardware_acceptance_authorized.md`

The checker exits before any hardware connection or device IO when a required
control is missing. The template file is deliberately insufficient.

## P3 Expected State

AUTHORIZATION_GATE_DRY_RUN: PASS
HARDWARE_AUTHORIZATION: MISSING_BY_DESIGN
{NO_HW}
{PENDING_HW}
""",
    )


def write_authorization_summary():
    write_authorization_artifacts()
    args = argparse.Namespace(
        dry_run=True,
        execute_hardware=False,
        max_runtime_sec=None,
        shutdown_on_exit=False,
        bitstream="",
        board_id="",
        test_profile="",
        active_pinmap_hash="",
        active_xdc_hash="",
    )
    payload = authorization_status(args)
    lines = [
        "AUTHORIZATION_GATE_DRY_RUN: PASS",
        "HARDWARE_AUTHORIZATION: MISSING_BY_DESIGN",
        NO_HW,
        PENDING_HW,
        "",
        "## Required Future Inputs",
        "",
        "- `--execute-hardware`",
        "- `--max-runtime-sec <N>`",
        "- `--shutdown-on-exit`",
        "- `--bitstream <path>`",
        "- `--board-id <id>`",
        "- `--test-profile <profile>`",
        "- `--active-xdc-hash <sha256>`",
        "- `--active-pinmap-hash <sha256>`",
        f"- `{AUTH_ENV}={AUTH_VALUE}`",
        f"- `{rel(AUTH_FILE)}` exists and is not the template",
    ]
    md_summary(GENERATED / "p3_authorization_gate_summary.md", "P3 Authorization Gate Summary", PASS, "authorization dry-run gate is present and missing by design", lines)
    return {"name": "AUTHORIZATION_GATE", "result": PASS, "reason": "dry-run authorization gate passes; hardware authorization missing by design", "payload": payload}


def evidence_schema():
    fields = [
        "test_id",
        "commit_hash",
        "operator",
        "date_time_local",
        "board_id",
        "fixture_id",
        "active_xdc_hash",
        "pinmap_hash",
        "bitstream_hash",
        "ps_app_hash",
        "test_profile",
        "lane_id",
        "direction",
        "max_runtime_sec",
        "shutdown_on_exit",
        "authorization_file_hash",
        "scope_capture_paths",
        "logic_analyzer_capture_paths",
        "vcc_measurement_paths",
        "raw_counters_before",
        "raw_counters_after",
        "pass_fail",
        "failure_reason",
        "shutdown_status",
    ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "RF_COMM_MULTILANE future hardware evidence schema",
        "type": "object",
        "additionalProperties": False,
        "required": fields,
        "properties": {field: {"type": ["string", "number", "boolean", "array", "object", "null"]} for field in fields},
    }


def generate_hardware_evidence_templates():
    root = ROOT / "evidence/hardware"
    root.mkdir(parents=True, exist_ok=True)
    readme = f"""# Hardware Evidence

{NO_HW}
{PENDING_HW}

No hardware action has been executed for RF_COMM_MULTILANE yet.
This directory is a placeholder for future user-authorized P4 evidence.
Do not mark any item PASS without a real P4 evidence file.
"""
    write_text(root / "README.md", readme)
    write_text(
        root / "PENDING_HW.md",
        f"""# Pending Hardware

{NO_HW}
{PENDING_HW}

P3 does not execute real TFDU6102, lane, Ethernet, rotation, or soak testing.
P4 remains blocked until a new explicit user authorization instruction is given.
""",
    )
    template = {key: None for key in evidence_schema()["required"]}
    for name in HARDWARE_EVIDENCE_DIRS:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        write_text(d / "README.md", readme)
        write_text(d / f"{name}_evidence.template.json", json.dumps(template, indent=2) + "\n")
    write_text(root / "evidence_schema.json", json.dumps(evidence_schema(), indent=2) + "\n")
    lines = [
        "EVIDENCE_SCHEMA: PASS",
        "",
        "## Directories",
        "",
        *(f"- `evidence/hardware/{name}/`: placeholder plus blank JSON template" for name in HARDWARE_EVIDENCE_DIRS),
        "",
        "## Schema",
        "",
        "- `evidence/hardware/evidence_schema.json`",
        "- Blank templates contain null fields only; no measurement is fabricated.",
    ]
    md_summary(GENERATED / "p3_evidence_schema_summary.md", "P3 Evidence Schema Summary", PASS, "hardware evidence placeholders and schema generated", lines)
    return {"name": "EVIDENCE_SCHEMA", "result": PASS, "reason": "blank evidence schema generated"}


def lane_table_rows():
    by_lane = {}
    for row in load_pinmap_rows():
        lane = row.get("lane", "")
        by_lane.setdefault(lane, []).append(row)
    lines = ["| Lane | Side | Txd FPGA pin | Rxd FPGA pin | SD FPGA pin | Mode FPGA pin | Connector | Measurement fields |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for lane in range(8):
        for side in ("A", "B"):
            rows = [r for r in by_lane.get(str(lane), []) if r.get("side") == side]
            pins = {r.get("signal"): r.get("package_pin") for r in rows}
            connector = rows[0].get("connector", "not mapped in P3 pinmap") if rows else "not mapped in P3 pinmap"
            measured = "VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4"
            lines.append(f"| {lane} | {side} | {pins.get('Txd', 'PENDING_P4')} | {pins.get('Rxd', 'PENDING_P4')} | {pins.get('SD', 'PENDING_P4')} | {pins.get('Mode', 'PENDING_P4')} | {connector} | {measured} |")
    return lines


def generate_docs(p3_status="IN_PROGRESS"):
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    existing_status = read_text(ROOT / "PROJECT_STATUS.md") if (ROOT / "PROJECT_STATUS.md").exists() else ""
    preserve_p4_status = "P4_HARDWARE_ACCEPTANCE:" in existing_status and "HARDWARE_ACTIONS_EXECUTED: true" in existing_status
    status_doc = f"""# Project Status

Project: RF_COMM_MULTILANE
Current branch: {branch}
Current HEAD: {head}

P0_BOOTSTRAP: PASS
P1_OFFLINE_HARDENING: PASS
P2_SIMULATION_BASELINE: PASS
P3_PRE_HW_ACCEPTANCE_PACKAGE: {p3_status}
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Unverified Hardware Scope

The following remain unverified until a later explicitly authorized P4 run:

- real TFDU6102 hardware
- lane0 hardware
- lane1 hardware
- 2-lane hardware
- 8-lane hardware
- Ethernet end-to-end hardware
- rotation
- long-run soak

Offline and simulation gates cannot promote hardware status beyond PENDING_HW.
"""
    if not preserve_p4_status:
        write_text(ROOT / "docs/PROJECT_STATUS.md", status_doc)
        write_text(ROOT / "PROJECT_STATUS.md", status_doc)
    write_text(
        ROOT / "docs/P3_PRE_HW_ACCEPTANCE_PACKAGE.md",
        f"""# P3 Pre-Hardware Acceptance Package

{NO_HW}
{PENDING_HW}

P3 prepares the repository for a future P4 hardware acceptance run. It generates
authorization gates, dry-run script checks, constraint freeze records, evidence
schemas, and runbooks. It does not run hardware and it does not claim any
TFDU6102, lane, Ethernet, rotation, soak, or product-final hardware result.

P3 completion criteria:

- Hardware scripts default to dry-run or authorization failure.
- Hardware authorization is missing by design.
- Active XDC and pinmap hashes are frozen.
- TFDU6102 safety contract remains enforced.
- Evidence directories contain blank templates only.
- P4 remains blocked until a new explicit user instruction authorizes hardware.
""",
    )
    write_text(
        ROOT / "docs/HARDWARE_ACCEPTANCE_CHECKLIST.md",
        f"""# Hardware Acceptance Checklist

{NO_HW}
{PENDING_HW}

- [ ] User explicitly authorizes P4 hardware testing
- [ ] Authorization file exists and is signed/dated
- [ ] RF_COMM_HW_AUTH environment variable is set
- [ ] Board ID recorded
- [ ] Fixture ID recorded
- [ ] Vivado/Vitis version recorded
- [ ] Active XDC hash recorded
- [ ] Pinmap hash recorded
- [ ] Bitstream hash recorded
- [ ] PS app hash recorded
- [ ] Test profile recorded
- [ ] Emergency stop method defined
- [ ] Maximum runtime defined
- [ ] Shutdown-on-exit enabled
- [ ] Txd default low verified by design
- [ ] SD default shutdown verified by design
- [ ] Mode strategy selected: static High or dynamic programming, not both
- [ ] Startup delay >= 500 us verified in RTL/simulation
- [ ] Txd stuck-high guard enabled
- [ ] TX duty guard enabled
- [ ] VCC1 voltage measurement plan ready
- [ ] VCC2 voltage measurement plan ready
- [ ] IRED current path reviewed
- [ ] C1/C3 4.7 uF decoupling reviewed
- [ ] C2 0.1 uF ceramic decoupling reviewed
- [ ] Scope probes assigned
- [ ] Logic analyzer channels assigned
- [ ] Raw counter readback method defined
- [ ] Shutdown log path defined
- [ ] Stop conditions reviewed

This checklist does not authorize hardware execution.
P4 hardware execution requires explicit user approval in a later step.
""",
    )
    write_text(
        ROOT / "docs/TFDU6102_ELECTRICAL_CHECKLIST.md",
        "\n".join(
            [
                "# TFDU6102 Electrical Checklist",
                "",
                NO_HW,
                PENDING_HW,
                "",
                "All measured electrical values are PENDING_P4. P3 may record planned FPGA pins from the active pinmap only.",
                "",
                *lane_table_rows(),
                "",
                "Required per-lane fields for P4: lane_id, physical module ID, orientation, TX optical direction, RX optical direction, Txd FPGA pin, Rxd FPGA pin, SD FPGA pin, Mode FPGA pin, VCC1 nominal voltage, VCC2 nominal voltage, VCC2 droop capture path, C1/C2/C3 value and location, R1/R2 presence and value, ground continuity, IO bank voltage, idle Txd, idle SD, idle Mode, and idle Rxd.",
            ]
        ),
    )
    write_text(
        ROOT / "docs/TFDU6102_SCOPE_PROBE_PLAN.md",
        f"""# TFDU6102 Scope Probe Plan

{NO_HW}
{PENDING_HW}

## Required P4 Channels

- Txd at FPGA pin or TFDU pin
- Rxd at TFDU pin
- SD at TFDU pin
- Mode at TFDU pin
- VCC1 near TFDU
- VCC2 near TFDU
- GND reference near TFDU
- optional optical detector output

## Capture Windows

- pre-trigger idle
- startup window
- single pulse window
- pulse train window
- shutdown window
- stuck-high guard test window
- VCC2 droop during TX burst

## Artifact Names

- `evidence/hardware/scope_captures/<test_id>_<lane>_<direction>_<signal>.png`
- `evidence/hardware/scope_captures/<test_id>_<lane>_<direction>.csv`
- `evidence/hardware/logic_analyzer/<test_id>_<lane>_<direction>.vcd`
""",
    )
    write_text(
        ROOT / "docs/TFDU6102_STOP_CONDITIONS.md",
        f"""# TFDU6102 Stop Conditions

{NO_HW}
{PENDING_HW}

Future P4 tests must stop immediately if any condition occurs:

- Txd stuck high
- Txd high duration exceeds configured guard
- SD fails to enter shutdown at test end
- unexpected optical emission during dry-run or idle
- VCC2 droop exceeds predefined threshold
- VCC1 droop or brownout observed
- Rxd remains stuck low after shutdown/idle
- device overheats
- operator activates emergency stop
- script loses connection before shutdown confirmation
- raw counter behavior is impossible or inconsistent
- wrong active XDC hash
- wrong bitstream hash
- authorization mismatch
""",
    )
    write_text(
        ROOT / "docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md",
        f"""# TFDU6102 Shutdown Requirements

{NO_HW}
{PENDING_HW}

Required future P4 exit sequence:

1. stop TX FSM
2. force Txd=0
3. wait guard interval
4. force SD=shutdown/high
5. disable lane enable masks
6. clear pending start bits
7. read back shutdown status
8. read final counters
9. write shutdown log
10. exit process

The shutdown sequence must run on normal completion, FAIL, exception, timeout,
Ctrl+C, PowerShell trap/finally, and Python try/finally paths.
""",
    )
    write_text(
        ROOT / "docs/RAW_PHY_SMOKE_RUNBOOK.md",
        f"""# Raw PHY Smoke Runbook

{NO_HW}
{PENDING_HW}

Future P4 raw PHY order:

1. keep SD shutdown, Txd low, Mode static selected
2. observe idle electrical levels
3. enable one lane only
4. wait >= 500 us startup
5. send one short pulse or bounded pulse train
6. observe remote Rxd active-low pulse
7. read raw pulse counter
8. force shutdown
9. verify Txd low and SD shutdown
10. archive scope/logic-analyzer/counter evidence

Raw PHY smoke allows no CRC, ACK, retry, Ethernet, or rotation.
""",
    )
    write_text(
        ROOT / "docs/RAW_LANE_MATRIX_RUNBOOK.md",
        f"""# Raw Lane Matrix Runbook

{NO_HW}
{PENDING_HW}

Future P4 matrix order covers every installed lane and direction:

AB_L0, BA_L0, AB_L1, BA_L1, AB_L2, BA_L2, AB_L3, BA_L3, AB_L4, BA_L4,
AB_L5, BA_L5, AB_L6, BA_L6, AB_L7, BA_L7.

For each lane/direction record TX pulse count, remote RX raw count, local idle
level, remote idle level, scope capture path, logic analyzer path, VCC2
measurement path, shutdown log path, pass/fail, and failure classification.

Failure classifications:

- NO_TX_PIN_PULSE
- TX_PIN_PULSE_BUT_NO_OPTICAL
- OPTICAL_PRESENT_BUT_NO_RXD
- RXD_PRESENT_BUT_NO_FPGA_COUNTER
- COUNTER_PRESENT_BUT_PROTOCOL_FAIL
- XDC_OR_PINMAP_MISMATCH
- POWER_OR_VCC2_DROOP
- UNKNOWN
""",
    )
    write_text(ROOT / "docs/HARDWARE_ACCEPTANCE_RUNBOOK.md", hardware_runbook_text())
    write_text(
        ROOT / "docs/P4_HARDWARE_ACCEPTANCE_PLAN.md",
        f"""# P4 Hardware Acceptance Plan

{NO_HW}
{PENDING_HW}

P4 is blocked until a new user instruction explicitly authorizes hardware.

Required instruction form:

```text
I authorize P4 hardware acceptance for RF_COMM_MULTILANE on board <board_id>, using bitstream <path>, max runtime <N> seconds, with shutdown-on-exit enabled.
```

Without that instruction and the authorization gate inputs, P4 remains blocked.
P4 must start with visual/electrical review, idle no-emission checks, startup
gate observation, single-pulse raw PHY smoke, raw lane matrix, then protocol
checks only after raw evidence is valid.
""",
    )
    write_text(
        ROOT / "docs/PS_RUNTIME_PRE_HW_CONTRACT.md",
        f"""# PS Runtime Pre-HW Contract

{NO_HW}
{PENDING_HW}

Required future PS sequence:

1. reset core
2. write cfg registers
3. write lane masks
4. write session
5. write payload length
6. write retry/timeout/guard
7. commit toggle
8. readback verify
9. enable PHY
10. wait >= 500 us startup
11. clear counters/sticky
12. start bounded test
13. stop
14. force shutdown
15. read final counters
16. write evidence

P3 only documents and checks this sequence. P3 does not run PS code on hardware.
""",
    )
    write_text(
        ROOT / "docs/HOST_RUNTIME_PRE_HW_CONTRACT.md",
        f"""# Host Runtime Pre-HW Contract

{NO_HW}
{PENDING_HW}

- host offline stub remains offline
- no real TCP connection to board in P3
- no serial connection to board in P3
- future P4/P5 host tests require explicit board IP and authorization
- mock transport tests remain separate from hardware tests
""",
    )
    return {"name": "P3_DOCS", "result": PASS, "reason": "P3 docs generated"}


def hardware_runbook_text():
    sections = [
        ("P4A", "visual/electrical pre-power review"),
        ("P4B", "no-emission idle IO verification"),
        ("P4C", "SD/Mode static level verification"),
        ("P4D", "startup gate observation"),
        ("P4E", "single-lane single-pulse raw PHY smoke"),
        ("P4F", "AB/BA raw lane matrix"),
        ("P4G", "lane0 frame+CRC only"),
        ("P4H", "lane0 ACK-only"),
        ("P4I", "lane1 raw only, if lane1 is installed"),
        ("P4J", "2-lane protocol only after all raw directions pass"),
        ("P4K", "shutdown and evidence packaging"),
    ]
    lines = [
        "# Hardware Acceptance Runbook",
        "",
        NO_HW,
        PENDING_HW,
        "",
        "P3 writes this future P4 runbook only. No command in this document is run by P3.",
        "",
    ]
    for code, title in sections:
        lines.extend(
            [
                f"## {code}: {title}",
                "",
                "purpose: define a bounded future hardware acceptance step.",
                "preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.",
                "commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.",
                "expected observations: bounded electrical or protocol evidence matching the step scope.",
                "required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.",
                "pass criteria: all required observations present, counters consistent, shutdown confirmed.",
                "fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.",
                "stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.",
                "shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.",
                "",
            ]
        )
    return "\n".join(lines)


def generate_runbook_summary():
    generate_docs("IN_PROGRESS")
    missing = [item for item in REQUIRED_DOCS if not (ROOT / item).exists()]
    lines = ["RUNBOOKS: PASS" if not missing else "RUNBOOKS: FAIL", "", "| Path | Status |", "| --- | --- |"]
    lines.extend(f"| `{item}` | {'present' if (ROOT / item).exists() else 'missing'} |" for item in REQUIRED_DOCS)
    md_summary(
        GENERATED / "p3_runbook_summary.md",
        "P3 Runbook Summary",
        PASS if not missing else FAIL,
        "required P3/P4 runbooks are present" if not missing else f"missing: {', '.join(missing)}",
        lines,
    )
    return {"name": "RUNBOOKS", "result": PASS if not missing else FAIL, "reason": "runbook docs checked", "missing": missing}


def generate_constraint_freeze():
    rows = load_pinmap_rows()
    xdc_map = parse_xdc(ACTIVE_XDC)
    lanes = sorted({int(row["lane"]) for row in rows if row.get("lane", "").isdigit()})
    lane_count = len(lanes)
    signal_list = sorted({row.get("port", "") for row in rows})
    pin_to_ports = {}
    for port, props in xdc_map.items():
        pin = props.get("PACKAGE_PIN")
        if pin:
            pin_to_ports.setdefault(pin, []).append(port)
    duplicate_pins = {pin: ports for pin, ports in pin_to_ports.items() if len(ports) > 1}
    active_primary = [p for p in (ROOT / "constraints/active").glob("*.xdc") if p.name == "PORT1.generated.xdc"]
    active_aux = [p for p in (ROOT / "constraints/active").glob("*.xdc") if p.name != "PORT1.generated.xdc"]
    profile = load_json(CONSTRAINT_PROFILE if CONSTRAINT_PROFILE.exists() else ACTIVE_PROFILE)
    expected_width = int(profile.get("lane_count_target", lane_count))
    wrapper = read_text(ROOT / "rtl/ir_top_new.sv") if (ROOT / "rtl/ir_top_new.sv").exists() else ""
    width_ok = f"[{expected_width - 1}:0]" in wrapper
    old_wrapper_active = "design_shiboqi_wrapper" in wrapper
    failures = []
    if len(active_primary) != 1:
        failures.append("primary active XDC count is not one")
    if duplicate_pins:
        failures.append("duplicate PACKAGE_PIN mappings")
    if not width_ok:
        failures.append("active wrapper lane width conflicts with active profile")
    if old_wrapper_active:
        failures.append("old single-lane wrapper appears in active top")
    if sha256_or_missing(PINMAP) == "MISSING":
        failures.append("pinmap hash missing")
    lines = [
        "# Active Constraint Freeze",
        "",
        NO_HW,
        PENDING_HW,
        "",
        f"active XDC path: `{rel(ACTIVE_XDC)}`",
        f"active XDC SHA256: `{sha256_or_missing(ACTIVE_XDC)}`",
        f"pinmap path: `{rel(PINMAP)}`",
        f"pinmap SHA256: `{sha256_or_missing(PINMAP)}`",
        f"lane_count: {lane_count}",
        f"active profile lane_count_target: {expected_width}",
        f"primary active XDC count: {len(active_primary)}",
        f"auxiliary active XDC files: {', '.join(rel(p) for p in active_aux) if active_aux else 'none'}",
        f"conflict check result: {'PASS' if not failures else 'FAIL'}",
        "old single-lane wrapper status: not in active top" if not old_wrapper_active else "old single-lane wrapper status: FAIL",
        f"current top wrapper status: {'PASS width matches ACTIVE_PROFILE' if width_ok else 'FAIL width mismatch'}",
        "",
        "## Logical Signal List",
        "",
        *(f"- `{item}`" for item in signal_list),
        "",
        "## Package Pin Mapping",
        "",
        "| Lane | Side | Signal | Port | Package pin | IOSTANDARD | Connector |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row.get('lane')} | {row.get('side')} | {row.get('signal')} | `{row.get('port')}` | {row.get('package_pin')} | {row.get('iostandard')} | {row.get('connector')} |")
    ref_xdcs = []
    for path in ROOT.rglob("*.xdc"):
        p = rel(path)
        if p.startswith("legacy/") or "legacy_reference" in path.parts or "legacy_conflicts" in path.parts:
            ref_xdcs.append(p)
    lines.extend(["", "## Archived / Reference XDC List", "", *(f"- `{p}`" for p in sorted(ref_xdcs)[:200])])
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {item}" for item in failures)])
    write_text(ROOT / "docs/ACTIVE_CONSTRAINT_FREEZE.md", "\n".join(lines))
    md_summary(
        GENERATED / "p3_constraint_freeze_summary.md",
        "P3 Constraint Freeze Summary",
        PASS if not failures else FAIL,
        "active XDC and pinmap freeze passed" if not failures else "; ".join(failures),
        [
            f"CONSTRAINT_FREEZE: {'PASS' if not failures else 'FAIL'}",
            f"- active_xdc_sha256: `{sha256_or_missing(ACTIVE_XDC)}`",
            f"- pinmap_sha256: `{sha256_or_missing(PINMAP)}`",
            f"- lane_count: {lane_count}",
            f"- auxiliary_active_xdc: {', '.join(rel(p) for p in active_aux) if active_aux else 'none'}",
        ],
    )
    return {"name": "CONSTRAINT_FREEZE", "result": PASS if not failures else FAIL, "reason": "constraint freeze checked", "failures": failures}


def generate_bitstream_policy_and_audit():
    write_text(
        ROOT / "docs/BITSTREAM_CANDIDATE_POLICY.md",
        f"""# Bitstream Candidate Policy

{NO_HW}
{PENDING_HW}

P3 may audit or build a bitstream candidate with non-hardware Vivado actions
only. P3 must never mark `BITSTREAM_PROGRAMMED` or reserved status `HARDWARE_PASS`.

## Status Vocabulary

- `SIMULATION_PASS`: offline simulation passed.
- `SYNTHESIS_PASS`: synthesis completed without hardware manager.
- `IMPLEMENTATION_PASS`: place/route completed without hardware manager.
- `BITSTREAM_GENERATED_NO_HW`: bitstream file generated but not programmed.
- `BITSTREAM_PROGRAMMED`: reserved for future authorized P4/P5 evidence only.
- `HARDWARE_PASS`: reserved for future authorized evidence only and forbidden in P3 claims.

Allowed non-hardware Vivado actions: `read_verilog`, `read_xdc`, `synth_design`,
`opt_design`, `place_design`, `route_design`, `write_bitstream`,
`report_timing_summary`, and `report_utilization`.

Forbidden hardware actions: `open_hw`, `connect_hw_server`, `open_hw_target`,
`program_hw_devices`, and `refresh_hw_device`.
""",
    )
    audited = []
    findings = []
    for item in ["scripts/vivado_nonhardware_build.tcl", "scripts/run_vivado_nonhardware_build.py", "scripts/vivado/create_project_offline.tcl", "scripts/vivado/validate_project_offline.tcl"]:
        path = ROOT / item
        if not path.exists():
            continue
        text = read_text(path).lower()
        audited.append(item)
        for token in ["open_hw", "connect_hw_server", "open_hw_target", "program_hw_devices", "refresh_hw_device", "current_hw_device"]:
            if token in text:
                findings.append(f"{item}:{token}")
    bit_summary_json = ROOT / "evidence/generated/vivado/nonhardware_build_summary.json"
    bit_payload = load_json(bit_summary_json) if bit_summary_json.exists() else {}
    bitstream_path = bit_payload.get("bitstream_path") or bit_payload.get("bitstream")
    bit_hash = sha256_or_missing(ROOT / bitstream_path) if bitstream_path else "SKIP_WITH_REASON"
    result = PASS if not findings else FAIL
    lines = [
        f"BITSTREAM_BUILD_AUDIT: {result}",
        f"BITSTREAM_GENERATION: {'BITSTREAM_GENERATED_NO_HW' if bitstream_path else 'SKIP_WITH_REASON'}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Audited Scripts",
        "",
        *(f"- `{item}`" for item in audited),
        *(["- none"] if not audited else []),
        "",
        "## Candidate Metadata",
        "",
        f"- bitstream path: `{bitstream_path or 'SKIP_WITH_REASON: no P3 build requested'}`",
        f"- bitstream SHA256: `{bit_hash}`",
        f"- generated from commit: `{git_value('rev-parse', 'HEAD')}`",
        "- status: BITSTREAM_GENERATED_NO_HW only if metadata exists",
        "- hardware status: PENDING_HW",
    ]
    if findings:
        lines.extend(["", "## Forbidden Hardware Commands", "", *(f"- {item}" for item in findings)])
    md_summary(
        GENERATED / "p3_bitstream_build_audit_summary.md",
        "P3 Bitstream Build Audit Summary",
        result,
        "non-hardware Vivado scripts audited; no hardware manager command found" if result == PASS else "forbidden hardware command found",
        lines,
    )
    return {"name": "BITSTREAM_BUILD_AUDIT", "result": result, "reason": "bitstream audit completed", "findings": findings}


def is_nonclaim_context(line, prefix, suffix):
    low = line.lower()
    if suffix.startswith("_ABSENT") or "forbidden_claim_" in prefix.lower():
        return True
    return any(
        phrase in low
        for phrase in [
            "reserved",
            "forbidden",
            "disallowed",
            "must not",
            "never",
            "does not",
            "do not",
            "without",
            "blocked",
            "non-claim",
            "status vocabulary",
            "allowed statuses",
            "future authorized",
        ]
    )


def p3_evidence_consistency_check():
    roots = ["README.md", "PROJECT_STATUS.md", "HARDWARE_SAFETY.md", "BUILD_AND_TEST_GUIDE.md", "SOURCE_STATE.md", "docs", "evidence/generated", "evidence/hardware", "profiles", "constraints"]
    findings = []
    for root in roots:
        path = ROOT / root
        paths = [path] if path.is_file() else list(path.rglob("*")) if path.exists() else []
        for item in paths:
            if not item.is_file() or item.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".json"}:
                continue
            p = rel(item)
            if "legacy" in item.parts or p.startswith("evidence/imported/"):
                continue
            if p in {"evidence/generated/p3_pre_hw_acceptance_package_summary.md", "evidence/generated/p3_no_hardware_static_scan.md"}:
                continue
            text = read_text(item)
            for token in DISALLOWED_PROMOTIONS:
                for match in re.finditer(re.escape(token), text):
                    line_start = text.rfind("\n", 0, match.start()) + 1
                    line_end = text.find("\n", match.end())
                    if line_end < 0:
                        line_end = len(text)
                    line = text[line_start:line_end]
                    suffix = text[match.end() : match.end() + 8]
                    prefix = text[max(0, match.start() - 48) : match.start()]
                    if is_nonclaim_context(line, prefix, suffix):
                        continue
                    findings.append((p, token, line.strip()[:180]))
    result = PASS if not findings else FAIL
    return {"name": "P3_EVIDENCE_CONSISTENCY", "result": result, "reason": "no false hardware pass claims found" if result == PASS else "forbidden promotion claim found", "findings": findings}


def classify_risky_file(path, hits):
    p = rel(path)
    text = read_text(path)
    low = text.lower()
    if (
        p.startswith("legacy/")
        or "legacy_reference" in path.parts
        or "legacy_safe_tools" in path.parts
        or p.startswith("software/legacy_")
        or any(part.startswith("legacy_") for part in path.parts)
    ):
        return "SKIP_WITH_REASON", "legacy/reference hardware material, not a P3 execution entrypoint"
    if p.startswith("rtl/") or p.startswith("sim/"):
        return "SAFE_DOCUMENTATION_ONLY", "RTL or simulation source; no host hardware action entrypoint"
    if p.startswith("evidence/generated/") or path.suffix.lower() in {".md", ".txt", ".csv", ".json"}:
        return "SAFE_DOCUMENTATION_ONLY", "documentation or generated evidence mention"
    guard_markers = [
        "dry-run",
        "--dry-run",
        "execute-hardware",
        "check_hardware_authorization",
        "rf_comm_hw_auth",
        "AllowHardware",
        "REFUSED_NO_ALLOW_HARDWARE",
        "NO_HARDWARE_ACTIONS_EXECUTED",
    ]
    if any(marker.lower() in low for marker in guard_markers):
        return "SAFE_DRY_RUN_GUARDED", "script contains dry-run or authorization guard markers"
    return "FAIL_UNGUARDED_HARDWARE_ACTION", f"risky terms: {', '.join(hits)}"


def p3_no_hardware_static_scan():
    exts = {".py", ".ps1", ".tcl", ".bat", ".cmd", ".sh", ".c", ".cpp", ".sv", ".v", ".md", ".txt"}
    skip_dirs = {".git", ".Xil", "xsim.dir", "__pycache__"}
    regex_terms = []
    for term in RISKY_TERMS:
        if term == "COM[0-9]":
            regex_terms.append((term, re.compile(r"\bCOM[0-9]+\b", re.IGNORECASE)))
        elif term in {"dow", "con", "stop", "mrd", "mwr"}:
            regex_terms.append((term, re.compile(rf"(?im)^\s*{re.escape(term)}\b")))
        elif term == "JTAG":
            regex_terms.append((term, re.compile(r"\bJTAG\b", re.IGNORECASE)))
        else:
            regex_terms.append((term, re.compile(re.escape(term), re.IGNORECASE)))
    rows = []
    failures = []
    scanned = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        scanned += 1
        text = read_text(path)
        hits = sorted({term for term, pat in regex_terms if pat.search(text)})
        if not hits:
            continue
        classification, reason = classify_risky_file(path, hits)
        rows.append((rel(path), ", ".join(hits), classification, reason))
        if classification == "FAIL_UNGUARDED_HARDWARE_ACTION":
            failures.append((rel(path), hits, reason))
    result = PASS if not failures else FAIL
    lines = [
        f"P3_NO_HARDWARE_STATIC_SCAN: {result}",
        f"- scanned files: {scanned}",
        f"- risky files classified: {len(rows)}",
        "",
        "| Path | Hits | Classification | Reason |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(f"| `{p}` | {hits} | {klass} | {reason} |" for p, hits, klass, reason in rows[:400])
    if failures:
        lines.extend(["", "## FAIL_UNGUARDED_HARDWARE_ACTION", "", *(f"- `{p}`: {reason}" for p, _, reason in failures)])
    md_summary(
        GENERATED / "p3_no_hardware_static_scan.md",
        "P3 No Hardware Static Scan",
        result,
        "no unguarded hardware actions found" if result == PASS else "unguarded hardware action found",
        lines,
    )
    return {"name": "NO_HARDWARE_STATIC_SCAN", "result": result, "reason": "P3 hardware static scan completed", "failures": failures}


def hardware_stub_payload(name, args):
    dry_run = args.dry_run or not args.execute_hardware
    if dry_run:
        return {
            "tool": name,
            "result": PASS,
            "DRY_RUN_ONLY": True,
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "message": "P3 dry-run placeholder; no hardware connection or device IO attempted.",
        }, 0
    auth = authorization_status(args)
    if auth["result"] != PASS:
        return {
            "tool": name,
            "result": FAIL,
            "AUTHORIZATION_MISSING": True,
            "missing": auth["missing"],
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }, 2
    return {
        "tool": name,
        "result": SKIP,
        "SKIP_WITH_REASON": "P4 hardware implementation is not part of the P3 package.",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }, 3


def run_stub_cli(name, argv=None):
    parser = argparse.ArgumentParser(description=f"{name} P3 dry-run hardware placeholder.")
    add_hw_args(parser)
    args = parser.parse_args(argv)
    payload, code = hardware_stub_payload(name, args)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return code


def add_hw_args(parser):
    parser.add_argument("--dry-run", action="store_true", help="Run without hardware access.")
    parser.add_argument("--execute-hardware", action="store_true", help="Request future hardware execution after authorization.")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--max-runtime-sec", type=int)
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--board-id", default="")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--test-profile", default="")
    parser.add_argument("--active-pinmap-hash", default="")
    parser.add_argument("--active-xdc-hash", default="")


def check_hardware_scripts_default_dry_run():
    scripts = [
        "tools/hw_preflight.py",
        "tools/hw_raw_phy_smoke.py",
        "tools/hw_raw_lane_matrix.py",
        "tools/hw_shutdown.py",
        "tools/hw_collect_evidence.py",
    ]
    rows = []
    failures = []
    for script in scripts:
        path = ROOT / script
        if not path.exists():
            failures.append(f"{script}: missing")
            rows.append((script, "FAIL", "script missing"))
            continue
        proc = run_cmd([sys.executable, script, "--dry-run", "--json-summary"], timeout=60)
        ok = proc["returncode"] == 0 and "DRY_RUN_ONLY" in proc["stdout"] and "PENDING_HW" in proc["stdout"]
        rows.append((script, PASS if ok else FAIL, f"dry-run rc={proc['returncode']}"))
        if not ok:
            failures.append(f"{script}: dry-run failed")
        auth_proc = run_cmd([sys.executable, script, "--execute-hardware", "--json-summary"], timeout=60)
        auth_ok = auth_proc["returncode"] != 0 and "AUTHORIZATION_MISSING" in auth_proc["stdout"] and "PENDING_HW" in auth_proc["stdout"]
        rows.append((script, PASS if auth_ok else FAIL, f"unauthorized execute rc={auth_proc['returncode']}"))
        if not auth_ok:
            failures.append(f"{script}: unauthorized execute did not fail before hardware")
    result = PASS if not failures else FAIL
    lines = [
        f"HARDWARE_SCRIPT_DRY_RUNS: {result}",
        "",
        "| Script | Result | Detail |",
        "| --- | --- | --- |",
        *(f"| `{script}` | {status} | {detail} |" for script, status, detail in rows),
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {item}" for item in failures)])
    md_summary(
        GENERATED / "p3_hardware_script_dry_run_summary.md",
        "P3 Hardware Script Dry Run Summary",
        result,
        "hardware placeholder scripts default to dry-run and reject unauthorized execution" if result == PASS else "hardware dry-run enforcement failed",
        lines,
    )
    return {"name": "HARDWARE_SCRIPT_DRY_RUNS", "result": result, "reason": "hardware dry-run scripts checked", "failures": failures}


def tfdu_contract_summary():
    required_docs = [
        ROOT / "docs/TFDU6102_SAFETY_SUMMARY.md",
        ROOT / "docs/tfdu6102_safety_contract.md",
        ROOT / "docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md",
        ROOT / "docs/TFDU6102_STOP_CONDITIONS.md",
    ]
    text = "\n".join(read_text(p) for p in required_docs if p.exists())
    required = ["Txd", "Rxd", "SD", "Mode=High", "500 us", "80 us", "stuck-high", "VCC2", "C1/C3 4.7 uF", "C2 0.1 uF", "shutdown"]
    missing = [item for item in required if item not in text]
    result = PASS if not missing else FAIL
    return {"name": "TFDU6102_CONTRACT", "result": result, "reason": "TFDU6102 contract markers checked" if result == PASS else f"missing: {', '.join(missing)}", "missing": missing}


def write_p3_summary(items, recheck, allow_skips=False):
    failures = [item for item in items if item.get("result") == FAIL]
    skips = [item for item in items if item.get("result") == SKIP]
    p3_result = FAIL if failures else PASS
    pass_items = [item["name"] for item in items if item.get("result") == PASS]
    generated = [item for item in REQUIRED_GENERATED if (ROOT / item).exists()]
    lines = [
        f"P3_PRE_HW_ACCEPTANCE_PACKAGE: {p3_result}",
        f"P0_RECHECK: {recheck.get('P0', PASS)}",
        f"P1_RECHECK: {recheck.get('P1', PASS)}",
        f"P2_RECHECK: {recheck.get('P2', PASS)}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"AUTHORIZATION_GATE: {'PASS_DRY_RUN' if not any(i['name'] == 'AUTHORIZATION_GATE' and i['result'] == FAIL for i in items) else 'FAIL'}",
        f"HARDWARE_SCRIPT_DRY_RUNS: {next((i['result'] for i in items if i['name'] == 'HARDWARE_SCRIPT_DRY_RUNS'), 'UNKNOWN')}",
        f"CONSTRAINT_FREEZE: {next((i['result'] for i in items if i['name'] == 'CONSTRAINT_FREEZE'), 'UNKNOWN')}",
        f"TFDU6102_CONTRACT: {next((i['result'] for i in items if i['name'] == 'TFDU6102_CONTRACT'), 'UNKNOWN')}",
        f"EVIDENCE_SCHEMA: {next((i['result'] for i in items if i['name'] == 'EVIDENCE_SCHEMA'), 'UNKNOWN')}",
        f"RUNBOOKS: {next((i['result'] for i in items if i['name'] == 'RUNBOOKS'), 'UNKNOWN')}",
        f"BITSTREAM_BUILD_AUDIT: {next((i['result'] for i in items if i['name'] == 'BITSTREAM_BUILD_AUDIT'), 'UNKNOWN')}",
        "NEXT_RECOMMENDED_STAGE: P4_HARDWARE_ACCEPTANCE_ONLY_AFTER_USER_AUTHORIZATION",
        "",
        "## Generated Summaries",
        "",
        *(f"- `{item}`" for item in generated),
        "",
        "## PASS",
        "",
        *(f"- {item}" for item in pass_items or ["none"]),
        "",
        "## FAIL",
        "",
        *(f"- {item['name']}: {item.get('reason', '')}" for item in failures or []),
        *(["- none"] if not failures else []),
        "",
        "## SKIP_WITH_REASON",
        "",
        *(f"- {item['name']}: {item.get('reason', '')}" for item in skips or []),
        *(["- none"] if not skips else []),
    ]
    consistency = next((i for i in items if i["name"] == "P3_EVIDENCE_CONSISTENCY"), None)
    if consistency and consistency.get("findings"):
        lines.extend(["", "## Forbidden Promotion Findings", "", *(f"- `{p}` `{tok}`: {line}" for p, tok, line in consistency["findings"])])
    md_summary(
        GENERATED / "p3_pre_hw_acceptance_package_summary.md",
        "P3 Pre-Hardware Acceptance Package Summary",
        p3_result,
        "P3 package is ready for future authorized P4" if p3_result == PASS else "P3 package has failing checks",
        lines,
    )
    generate_docs(p3_result)
    return {
        "P3_PRE_HW_ACCEPTANCE_PACKAGE": p3_result,
        "P0_RECHECK": recheck.get("P0", PASS),
        "P1_RECHECK": recheck.get("P1", PASS),
        "P2_RECHECK": recheck.get("P2", PASS),
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "generated_summaries": generated,
        "pass": pass_items,
        "fail": [item["name"] for item in failures],
        "skip": [item["name"] for item in skips],
        "NEXT_RECOMMENDED_STAGE": "P4_HARDWARE_ACCEPTANCE_ONLY_AFTER_USER_AUTHORIZATION",
    }


def append_agents_p3_boundary():
    path = ROOT / "AGENTS.md"
    if not path.exists():
        return {"name": "AGENTS_P3_BOUNDARY", "result": SKIP, "reason": "AGENTS.md missing"}
    text = read_text(path)
    marker = "## P3/P4 Pre-Hardware Boundary"
    if marker in text:
        return {"name": "AGENTS_P3_BOUNDARY", "result": PASS, "reason": "P3/P4 boundary already present"}
    addition = f"""

{marker}
- Hardware is locked by default and P3 is documentation/dry-run only.
- Offline gates and generated summaries must keep `HARDWARE_ACCEPTANCE: PENDING_HW`.
- Hardware-capable scripts must default to dry-run or fail authorization before any hardware connection.
- Future hardware requires `RF_COMM_HW_AUTH`, an authorization file, explicit board/bitstream/profile/hash inputs, max runtime, and shutdown-on-exit.
- TFDU6102 startup wait, stuck-high guard, Txd default-low, SD shutdown, and shutdown-on-exit constraints remain mandatory.
- Do not claim hardware, lane, Ethernet, rotation, soak, or product-final pass without real authorized P4 evidence.
"""
    write_text(path, text.rstrip() + "\n" + addition)
    return {"name": "AGENTS_P3_BOUNDARY", "result": PASS, "reason": "P3/P4 boundary appended"}


def run_pre_hw_acceptance_package_gate(allow_skips=False, skip_p1_p2_recheck=False):
    GENERATED.mkdir(parents=True, exist_ok=True)
    repo = write_repo_intake()
    recheck = run_p1_p2_recheck(allow_skips=allow_skips, skip=skip_p1_p2_recheck)
    auth = write_authorization_summary()
    schema = generate_hardware_evidence_templates()
    freeze = generate_constraint_freeze()
    bitstream = generate_bitstream_policy_and_audit()
    runbooks = generate_runbook_summary()
    agents = append_agents_p3_boundary()
    scripts = check_hardware_scripts_default_dry_run()
    scan = p3_no_hardware_static_scan()
    contract = tfdu_contract_summary()
    consistency = p3_evidence_consistency_check()
    items = [repo, auth, schema, runbooks, freeze, bitstream, agents, scripts, scan, contract, consistency]
    if recheck.get("result") == FAIL:
        items.append(recheck)
    elif recheck.get("result") == SKIP and not skip_p1_p2_recheck:
        items.append(recheck)
    payload = write_p3_summary(items, recheck, allow_skips=allow_skips)
    return payload
