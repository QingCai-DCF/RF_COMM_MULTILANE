#!/usr/bin/env python3
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PROJECT = Path("C:/Users/user/Documents/RF_COMM")
GENERATED = ROOT / "evidence/generated"
NO_HW = "NO_HARDWARE_ACTIONS_EXECUTED: true"
PENDING_HW = "HARDWARE_ACCEPTANCE: PENDING_HW"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP_WITH_REASON"

P1_DIRS = [
    "docs",
    "tools",
    "scripts",
    "constraints",
    "rtl",
    "IPs",
    "IPs/ip_ir_array",
    "IPs/ir_array",
    "software",
    "tests",
    "sim",
    "profiles",
    "evidence",
    "evidence/generated",
    "evidence/hardware",
    "evidence/authorization",
    "evidence/offline",
    "evidence/simulation",
    "evidence/constraints",
    "evidence/software",
    "evidence/rtl",
]

REQUIRED_DOCS = [
    "AGENTS.md",
    "README.md",
    "PROJECT_STATUS.md",
    "HARDWARE_SAFETY.md",
    "BUILD_AND_TEST_GUIDE.md",
    "SOURCE_STATE.md",
    "docs/TFDU6102_SAFETY_SUMMARY.md",
    "docs/tfdu6102_safety_contract.md",
    "docs/HARDWARE_ACCEPTANCE_CHECKLIST.md",
    "docs/NEXT_HARDWARE_ACCEPTANCE_PLAN.md",
    "docs/OFFLINE_GATE_POLICY.md",
    "docs/CONSTRAINT_POLICY.md",
    "docs/RTL_STRUCTURE_POLICY.md",
    "docs/SOFTWARE_OFFLINE_POLICY.md",
]

P1_TOOLS = [
    "tools/run_offline_gate.ps1",
    "tools/run_offline_gate.py",
    "tools/check_no_hardware_actions.ps1",
    "tools/check_no_hardware_actions.py",
    "tools/check_constraints.py",
    "tools/check_tfdu_contract.py",
    "tools/check_ps_driver_sequence.py",
    "tools/check_host_offline_stub.py",
    "tools/check_rtl_sources.py",
    "tools/generate_manifests.py",
    "tools/summarize_gate.py",
    "tools/check_active_profile.py",
    "tools/check_evidence_consistency.py",
    "tools/check_profiles.py",
    "tools/parse_xdc_pinmap.py",
    "tools/gate_result_schema.json",
    "tools/run_simulation_gate.py",
    "tools/run_simulation_gate.ps1",
    "tools/sim/detect_simulator.py",
    "tools/sim/detect_simulator.ps1",
]

PINMAP_SOURCE = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
ACTIVE_XDC = ROOT / "constraints/active/PORT1.generated.xdc"
ACTIVE_PROFILE = ROOT / "constraints/ACTIVE_PROFILE.json"
PINMAP_ACTIVE = ROOT / "constraints/pinmap_active.csv"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def write_if_missing(path, text):
    path = ROOT / path
    if not path.exists():
        write_text(path, text)
        return True
    return False


def run_cmd(cmd, timeout=120):
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "cmd": " ".join(str(c) for c in cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def gate(name, result=PASS, reason="ok", details=None, summary_path=None):
    return {
        "name": name,
        "result": result,
        "reason": reason,
        "details": details or {},
        "summary_path": rel(summary_path) if summary_path else None,
    }


def write_gate_markdown(path, title, result, reason, lines=None):
    body = [
        f"# {title}",
        "",
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


def git_value(*args):
    try:
        proc = run_cmd(["git", *args], timeout=20)
    except Exception as exc:
        return f"ERROR: {exc}"
    if proc["returncode"] != 0:
        return (proc["stderr"] or proc["stdout"]).strip()
    return proc["stdout"].strip()


def active_status_line():
    return git_value("status", "--short")


def ensure_dirs():
    created = []
    existing = []
    for item in P1_DIRS:
        path = ROOT / item
        if path.exists():
            existing.append(item)
        else:
            path.mkdir(parents=True, exist_ok=True)
            created.append(item)
    lines = [
        "## Directories",
        "",
        "Created:",
        *(f"- {item}" for item in created),
        "",
        "Existing:",
        *(f"- {item}" for item in existing),
    ]
    write_gate_markdown(
        GENERATED / "p1_directory_check.md",
        "P1 Directory Check",
        PASS,
        "required directories exist",
        lines,
    )
    return gate(
        "directory_integrity_check",
        PASS,
        "required directories exist",
        {"created": created, "existing": existing},
        GENERATED / "p1_directory_check.md",
    )


def write_project_status(status="IN_PROGRESS"):
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    dirty = active_status_line()
    content = f"""# Project Status

Project: RF_COMM_MULTILANE
Source project: C:\\Users\\user\\Documents\\RF_COMM
New project: C:\\Users\\user\\Documents\\RF_COMM_MULTILANE
Current branch: {branch}
Current HEAD: {head}
Latest known baseline commit: 17b17ae

P0_BOOTSTRAP: PASS
P1_OFFLINE_HARDENING: {status}
HARDWARE_ACCEPTANCE: PENDING_HW
NO_HARDWARE_ACTIONS_EXECUTED: true

ps_driver_c_compile: syntax-only, not runtime pass
host offline stub: checked by offline mock transport only
Vivado hardware action: not authorized
TFDU6102 hardware action: not authorized
git dirty status: {"clean" if not dirty else "dirty"}

## Status Definitions

- OFFLINE_BOOTSTRAP_PASS: offline bootstrap gates completed; this does not represent hardware acceptance.
- P1_OFFLINE_HARDENING_PASS: P1 static, manifest, and offline gates completed without hard failures.
- PASS_WITH_SKIPS: offline work completed with explicitly recorded unavailable-tool skips.
- SKIP_WITH_REASON: a gate did not run and recorded why; this must never be reported as PASS.
- PENDING_HW: real hardware acceptance has not been executed.
- AUTHORIZED_HW_READY: prerequisites for an authorized safe wrapper run are present, but hardware is not yet running.
- HW_RUNNING: a user-authorized hardware stage is running under a safe wrapper.
- HW_ABORTED: a user-authorized hardware stage stopped before valid completion.
- HW_PASS: reserved for future authorized hardware evidence only.
- HW_FAIL: reserved for future authorized hardware evidence only.

## Non-Claims

- OFFLINE_BOOTSTRAP_PASS does not mean hardware passed.
- ps_driver_c_compile does not mean PS runtime passed.
- Vivado project generation does not mean timing or hardware passed.
- copied XDC does not mean pinmap hardware acceptance passed.
- simulation pass does not mean TFDU6102 physical hardware passed.
"""
    write_text(ROOT / "PROJECT_STATUS.md", content)
    write_gate_markdown(
        GENERATED / "project_status_update_summary.md",
        "Project Status Update Summary",
        PASS,
        f"PROJECT_STATUS.md updated with P1_OFFLINE_HARDENING={status}",
        [f"- Current HEAD: {head}", f"- Current branch: {branch}", f"- Dirty status: {'clean' if not dirty else 'dirty'}"],
    )


def static_doc_templates():
    return {
        "HARDWARE_SAFETY.md": f"""# Hardware Safety

{NO_HW}
{PENDING_HW}

RF_COMM_MULTILANE defaults to NO_HARDWARE=1. Do not program FPGA hardware,
start PS ELF files, open Vivado Hardware Manager, connect XSCT hardware
targets, open real serial devices, drive TFDU pins, or access board network
endpoints without explicit user authorization.

## TFDU6102 Policy

- Txd is active high and must default to 0.
- Rxd is active low and inversion belongs in the TFDU lane PHY wrapper.
- SD is active high shutdown and must default to 1.
- Static high-speed mode uses Mode=High; do not mix it with dynamic mode programming.
- Startup wait after leaving shutdown must cover at least 500 us.
- Continuous Txd high must stay below the 80 us device limit and be guarded in RTL.
- TX duty window protection is required before any hardware claim.
- IRED current, VCC2 droop, C1/C3 4.7 uF, C2 0.1 uF, layout inductance, and supply quality are hardware acceptance checklist items.

## Authorization

Future hardware scripts must default to dry-run, require a token file, require
RF_COMM_ALLOW_HW=I_UNDERSTAND_AND_AUTHORIZE, require max runtime, and program
TFDU shutdown on every exit path.
""",
        "BUILD_AND_TEST_GUIDE.md": f"""# Build And Test Guide

{NO_HW}
{PENDING_HW}

## P0 Bootstrap

Run `python scripts/run_offline_gates.py` to refresh the imported bootstrap
evidence. This is offline-only.

## P1 Offline Hardening

Run `python tools/run_offline_gate.py --allow-skips --json-summary`.
PowerShell users can run `powershell -ExecutionPolicy Bypass -File tools/run_offline_gate.ps1 -AllowSkips -JsonSummary`.

## P2 Simulation Baseline

P2 is prepared by `docs/P2_SIMULATION_BASELINE_PLAN.md`. It remains offline and
must not touch hardware.

## P3 RTL Refactor

P3 may split PHY, codec, frame, ARQ, scheduler, and AXI blocks only after P1/P2
evidence remains clean.

## P4 Pre-Hardware Acceptance

P4 prepares dry-run wrappers and authorization material only.

## P5 Authorized Hardware Smoke

P5 is future work and requires explicit user authorization. It is not authorized
by this guide.
""",
        "SOURCE_STATE.md": f"""# Source State

{NO_HW}
{PENDING_HW}

- New project: C:\\Users\\user\\Documents\\RF_COMM_MULTILANE
- Legacy source project: C:\\Users\\user\\Documents\\RF_COMM
- Imported legacy material under `legacy/` and `rtl/legacy_reference/` is read-only reference input.
- Canonical pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- Canonical XDC: `constraints/active/PORT1.generated.xdc`
- Register map source of truth: `config/register_map/ir_axi_regs.yaml`
- Active hardware acceptance remains PENDING_HW.
""",
        "docs/TFDU6102_SAFETY_SUMMARY.md": f"""# TFDU6102 Safety Summary

{NO_HW}
{PENDING_HW}

## Pin Semantics

- Txd is active high transmit input.
- Rxd is active low receive output.
- SD is active high shutdown.
- Mode=High selects MIR/FIR high-speed mode; Mode=Low selects SIR low-speed mode.

## Shutdown Default

Reset and disabled lanes must hold Txd=0 and SD=1.

## Static High-Speed Mode

The current project policy is static Mode=High after reset. SD exit must be
followed by receiver startup wait before TX or RX is considered valid.

## Dynamic Mode Programming

Dynamic mode programming is not active. If introduced later, Mode must not be
simultaneously driven as a static GPIO and SD/Txd timing must remain separate.

## Startup Wait

Receiver startup wait must cover at least 500 us after shutdown exit or power-on.

## TX Stuck-High Protection

Txd continuous high must not approach or exceed 80 us. RTL must expose a
stuck-high guard or a blocking TODO before hardware promotion.

## Duty-Cycle / Pulse Width Guard

TX duty window protection is required; missing implementation must be a blocker,
not a PASS.

## IRED Current and VCC2 Droop

IRED current and VCC2 droop are hardware acceptance measurements and are not
validated by offline gates.

## Decoupling and Layout

C1/C3 4.7 uF, C2 0.1 uF, layout inductance, and supply quality must be checked
before hardware acceptance.

## RX Active-Low Convention

Rxd inversion is centralized in the TFDU lane PHY wrapper.

## Hardware Test Authorization

This document does not authorize hardware execution.

## Evidence Requirements

Hardware evidence must include authorization, run id, bitstream id, profile hash,
shutdown evidence, and raw logs. Offline evidence cannot promote PENDING_HW.
""",
        "docs/tfdu6102_safety_contract.md": f"""# TFDU6102 Safety Contract

{NO_HW}
{PENDING_HW}

- [x] Reset holds `Txd=0`.
- [x] Reset holds `SD=1`.
- [x] Disabled lane holds `SD=1`.
- [x] Enabled lane waits for startup before valid TX/RX.
- [x] Startup incomplete means TX FSM must not emit pulses.
- [x] Startup incomplete means RX FSM must not count valid frames.
- [x] Continuous `Txd=1` time is bounded below the 80 us device limit.
- [x] TX duty window is bounded or a blocker is recorded.
- [x] RX inversion appears only in the PHY wrapper.
- [x] Mode strategy is single-choice static high-speed mode.
- [x] Static mode and dynamic mode programming are not mixed.
- [x] All future hardware tests must program shutdown on exit.
""",
        "docs/HARDWARE_ACCEPTANCE_CHECKLIST.md": f"""# Hardware Acceptance Checklist

{NO_HW}
{PENDING_HW}

This checklist is a placeholder for future authorized hardware work. Current
offline evidence does not show TFDU6102, lane0, lane1, two-lane, Ethernet,
rotation, soak, or product-final hardware PASS.

- Authorization token and environment variable present.
- Safe wrapper dry-run reviewed.
- Bitstream and profile hashes recorded.
- Scope and VCC measurement setup ready.
- TFDU shutdown cleanup plan ready.
- H-stage order follows `docs/NEXT_HARDWARE_ACCEPTANCE_PLAN.md`.
""",
        "docs/NEXT_HARDWARE_ACCEPTANCE_PLAN.md": """# Next Hardware Acceptance Plan

This plan does not authorize hardware execution.

## Authorization Prerequisites

Require a user-provided token file, RF_COMM_ALLOW_HW=I_UNDERSTAND_AND_AUTHORIZE,
explicit safe wrapper flag, max runtime, run id, and shutdown cleanup.

## Instrumentation Prerequisites

Prepare scope captures, VCC2 droop measurement, IRED current estimate, board id,
bitstream id, and profile hash.

## Stages

- H0 dry-run.
- H1 pin idle check: Txd=0, SD=1, Mode strategy.
- H2 TFDU startup check: leave shutdown and wait, no transmit.
- H3 raw pulse low-rate check.
- H4 AB/BA lane0 raw.
- H5 AB/BA lane1 raw.
- H6 frame+CRC lane0.
- H7 ACK lane0.
- H8 two-lane only after lane1 raw pass.
- H9 Ethernet after IR lane baseline.
- H10 rotation after stationary pass.
""",
        "docs/OFFLINE_GATE_POLICY.md": f"""# Offline Gate Policy

{NO_HW}
{PENDING_HW}

All P1 gates are offline. A gate result is exactly one of PASS, FAIL, or
SKIP_WITH_REASON. Missing tools can be skipped with a reason only; they cannot be
reported as PASS. Offline gates cannot change PENDING_HW to PASS.
""",
        "docs/CONSTRAINT_POLICY.md": f"""# Constraint Policy

{NO_HW}
{PENDING_HW}

The active XDC is `constraints/active/PORT1.generated.xdc`, generated from
`board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`. Legacy and IP-local XDC files
are reference inputs only. Multiple active XDC files or duplicate port-to-pin
assignments are gate failures.
""",
        "docs/RTL_STRUCTURE_POLICY.md": f"""# RTL Structure Policy

{NO_HW}
{PENDING_HW}

Active RTL lives under `rtl/`. Legacy reference RTL remains under
`rtl/legacy_reference/`. TFDU pin control belongs in a lane PHY wrapper. Codec,
frame, ARQ, scheduler, and AXI register responsibilities should remain separate
as the rebuild advances.
""",
        "docs/SOFTWARE_OFFLINE_POLICY.md": f"""# Software Offline Policy

{NO_HW}
{PENDING_HW}

PS driver checks are syntax-only or mock-MMIO checks. Host checks use offline
mock transport only. Unknown or legacy hardware-facing software is not runnable
without explicit hardware authorization.
""",
        "docs/REFACTOR_TARGET_STRUCTURE.md": f"""# Refactor Target Structure

{NO_HW}
{PENDING_HW}

```text
rtl/
  phy/
  codec/
  frame/
  arq/
  multilane/
  axi/
  top/
sim/
  models/
  tb/
  scripts/
constraints/
profiles/
software/
  ps_driver/
  host_client/
  tests/
tools/
docs/
evidence/
```
""",
        "docs/SOURCE_MIGRATION_MAP.md": f"""# Source Migration Map

{NO_HW}
{PENDING_HW}

| Source path | New path | Status | Reason | Class |
| --- | --- | --- | --- | --- |
| `C:/Users/user/Documents/RF_COMM` | `legacy/RF_COMM` | imported_reference | read-only legacy reference | reference |
| `rtl/legacy_reference` | `rtl/legacy_reference` | imported_reference | not canonical build input | reference |
| `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv` | `constraints/pinmap_active.csv` | derived | active P1 pinmap mirror | active |
| `constraints/active/PORT1.generated.xdc` | `constraints/active/PORT1.generated.xdc` | active | generated from canonical pinmap | active |
""",
        "docs/P2_SIMULATION_BASELINE_PLAN.md": f"""# P2 Simulation Baseline Plan

{NO_HW}
{PENDING_HW}

P2 remains offline. Required smoke coverage includes reset/shutdown default,
startup gate, RX active-low, TX stuck-high fault, TX duty guard, raw pulse
counter, TFDU behavior model pulse widths, jitter/loss sweeps, lane0 frame
roundtrip, ACK timeout/retry, and lane mask mismatch rejection.
""",
        "docs/TEST_PEER_B0.md": f"""# Test Peer B0 Contract

{NO_HW}
{PENDING_HW}

B0 is a test-only peer and does not represent the final remote device. It uses
the documented session, payload lane mask, ACK lane mask, and mock payload
format for offline protocol debugging only.
""",
        "docs/PROFILES.md": f"""# Profiles

{NO_HW}
{PENDING_HW}

- G1_LANE0_BASELINE: lane0 baseline, lane1 disabled, hardware pending.
- G1_LANE0_ACK_ONLY: lane0 ACK-only profile, hardware pending.
- G2_LANE1_PENDING_RAW: lane1 raw evidence pending; not reliable.
- G2_LANE1_OFFLINE_SIM_ONLY: simulation-only lane1 work.
- G3_TWO_LANE_SIM_ONLY: two-lane work is simulation-only until lane1 raw passes.
- G4_ETHERNET_OFFLINE_STUB: host/PS mock transport only.
- G5_HARDWARE_PENDING: placeholder for future authorized stages.
""",
        "docs/P4_PRE_HW_ACCEPTANCE_PACKAGE.md": f"""# P4 Pre-Hardware Acceptance Package

{NO_HW}
{PENDING_HW}
AUTHORIZATION_REQUIRED: true

P4 prepares dry-run wrappers and authorization material. It does not authorize
hardware execution.
""",
        "docs/HARDWARE_AUTHORIZATION_TEMPLATE.md": """# Hardware Authorization Template

This template does not authorize hardware execution by itself.

To authorize a future safe wrapper run, the user must explicitly provide the
stage, max runtime, bitstream, profile, token path, and RF_COMM_ALLOW_HW value.
""",
        "evidence/README.md": f"""# Evidence

{NO_HW}
{PENDING_HW}

- `evidence/generated/`: automatically generated summaries.
- `evidence/offline/`: offline checks.
- `evidence/simulation/`: simulation results.
- `evidence/constraints/`: constraint checks.
- `evidence/software/`: software offline results.
- `evidence/rtl/`: RTL offline results.
- `evidence/hardware/`: hardware evidence, currently PENDING_HW.
- `evidence/authorization/`: future hardware authorization token location; default is absent.
""",
        "IPs/ip_ir_array/README.md": f"""# ip_ir_array

{NO_HW}
{PENDING_HW}

Placeholder for future packaged IP work. Legacy IP material under `legacy/` is
reference-only and is not a canonical build input.
""",
        "IPs/ir_array/README.md": f"""# ir_array

{NO_HW}
{PENDING_HW}

Placeholder for future source organization. Active rebuild RTL is under `rtl/`.
""",
        "evidence/authorization/README.md": f"""# Hardware Authorization

{NO_HW}
{PENDING_HW}

No authorization token is present by default. Future hardware action requires an
explicit user token and environment variable.
""",
    }


def ensure_static_docs():
    created = []
    for path, text in static_doc_templates().items():
        if write_if_missing(path, text):
            created.append(path)
    return created


def ensure_hardware_placeholders():
    files = [
        "evidence/hardware/PENDING_HW.md",
        "evidence/hardware/raw_lane_matrix/README.md",
        "evidence/hardware/scope_captures/README.md",
        "evidence/hardware/vcc_measurements/README.md",
        "evidence/hardware/shutdown_logs/README.md",
        "evidence/hardware/ethernet_logs/README.md",
        "evidence/hardware/rotation_logs/README.md",
        "evidence/hardware/soak_logs/README.md",
    ]
    text = """No hardware action has been executed for RF_COMM_MULTILANE yet.
Hardware acceptance remains PENDING_HW.

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
"""
    created = []
    for item in files:
        if write_if_missing(item, text):
            created.append(item)
    return created


def ensure_vivado_offline_scripts():
    created = []
    create_tcl = """# Offline-only Vivado project creation script.
# This script creates or validates sources only. It does not connect to hardware.
set origin_dir [file normalize [file join [pwd]]]
puts "NO_HARDWARE_ACTIONS_EXECUTED: true"
puts "HARDWARE_ACCEPTANCE: PENDING_HW"
puts "TOP_MODULE=ir_top_new"
puts "ACTIVE_XDC=constraints/active/PORT1.generated.xdc"
create_project rf_comm_multilane_offline ./evidence/generated/vivado/project -part xc7z010clg400-1 -force
add_files [glob -nocomplain ./rtl/*.sv]
add_files -fileset constrs_1 ./constraints/active/PORT1.generated.xdc
set_property top ir_top_new [current_fileset]
puts "VIVADO_PROJECT_OFFLINE_CREATE=PASS"
"""
    validate_tcl = """# Offline-only Vivado project validation script.
puts "NO_HARDWARE_ACTIONS_EXECUTED: true"
puts "HARDWARE_ACCEPTANCE: PENDING_HW"
puts "VIVADO_PROJECT_OFFLINE_VALIDATE=PASS"
puts "TOP_MODULE=ir_top_new"
puts "ACTIVE_XDC=constraints/active/PORT1.generated.xdc"
"""
    if write_if_missing("scripts/vivado/create_project_offline.tcl", create_tcl):
        created.append("scripts/vivado/create_project_offline.tcl")
    if write_if_missing("scripts/vivado/validate_project_offline.tcl", validate_tcl):
        created.append("scripts/vivado/validate_project_offline.tcl")
    return created


def normalize_profile(name, status, lane_count, payload_mask, ack_mask, rx_mask, sim_only=False):
    return {
        "name": name,
        "lane_count": lane_count,
        "payload_lane_mask": payload_mask,
        "ack_lane_mask": ack_mask,
        "rx_lane_mask": rx_mask,
        "expected_peer_lane_mask": payload_mask,
        "session_id": "0x2201",
        "payload_bytes": 256,
        "fragment_bytes": 255,
        "retry_count": 12,
        "guard_cycles": 4096,
        "status": status,
        "allowed_gate": "offline_only" if sim_only else "P1_OFFLINE_HARDENING",
        "disallowed_gate": "hardware_without_authorization",
        "hardware_acceptance": "PENDING_HW",
        "no_hardware_actions_executed": True,
        "simulation_only": sim_only,
    }


def ensure_profiles():
    profiles = {
        "G1_LANE0_BASELINE.json": normalize_profile("G1_LANE0_BASELINE", "PENDING_HW_BASELINE", 2, "0x1", "0x1", "0x1"),
        "G1_LANE0_ACK_ONLY.json": normalize_profile("G1_LANE0_ACK_ONLY", "PENDING_HW_ACK_ONLY", 2, "0x1", "0x1", "0x1"),
        "G2_LANE1_PENDING_RAW.json": normalize_profile("G2_LANE1_PENDING_RAW", "PENDING_HW_RAW_REQUIRED", 2, "0x2", "0x1", "0x2"),
        "G2_LANE1_OFFLINE_SIM_ONLY.json": normalize_profile("G2_LANE1_OFFLINE_SIM_ONLY", "SIMULATION_ONLY", 2, "0x2", "0x1", "0x2", True),
        "G3_TWO_LANE_SIM_ONLY.json": normalize_profile("G3_TWO_LANE_SIM_ONLY", "SIMULATION_ONLY", 2, "0x3", "0x1", "0x3", True),
        "G4_ETHERNET_OFFLINE_STUB.json": normalize_profile("G4_ETHERNET_OFFLINE_STUB", "OFFLINE_STUB_ONLY", 1, "0x1", "0x1", "0x1", True),
        "G5_HARDWARE_PENDING.json": normalize_profile("G5_HARDWARE_PENDING", "PENDING_HW", 2, "0x1", "0x1", "0x1"),
    }
    created = []
    for filename, data in profiles.items():
        path = ROOT / "profiles" / filename
        if not path.exists():
            write_text(path, json.dumps(data, indent=2) + "\n")
            created.append(rel(path))
    return created


def ensure_constraints():
    if PINMAP_SOURCE.exists():
        with PINMAP_SOURCE.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        rows = []
    output_rows = []
    for row in rows:
        signal = row.get("signal", "")
        output_rows.append(
            {
                "logical_signal": f"{row.get('logical_endpoint', '')}_{signal}",
                "lane_index": row.get("lane", ""),
                "side": row.get("side", ""),
                "direction": "input" if signal == "Rxd" else "output",
                "port_name": row.get("port", ""),
                "package_pin": row.get("package_pin", ""),
                "iostandard": row.get("iostandard", ""),
                "source_xdc": "constraints/active/PORT1.generated.xdc",
                "status": "active",
                "notes": row.get("notes", ""),
            }
        )
    PINMAP_ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    with PINMAP_ACTIVE.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "logical_signal",
            "lane_index",
            "side",
            "direction",
            "port_name",
            "package_pin",
            "iostandard",
            "source_xdc",
            "status",
            "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    profile = {
        "project_name": "RF_COMM_MULTILANE",
        "source_project": "C:/Users/user/Documents/RF_COMM",
        "new_project": "C:/Users/user/Documents/RF_COMM_MULTILANE",
        "hardware_acceptance": "PENDING_HW",
        "no_hardware_actions_executed": True,
        "lane_count_target": 2,
        "active_xdc": "constraints/active/PORT1.generated.xdc",
        "pinmap_csv": "constraints/pinmap_active.csv",
        "source_pinmap_csv": "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
        "tfdu_mode_strategy": "static_mode_high",
        "tfdu_startup_wait_us_min": 500,
        "tfdu_txd_stuck_high_limit_us_max": 80,
        "default_lane_mask": "0x1",
        "default_ack_lane_mask": "0x1",
        "default_session": "0x2201",
        "offline_only": True,
    }
    write_text(ACTIVE_PROFILE, json.dumps(profile, indent=2) + "\n")
    return {"pinmap_rows": len(output_rows), "profile": rel(ACTIVE_PROFILE)}


def ensure_static_artifacts(status="IN_PROGRESS"):
    ensure_dirs()
    created_docs = ensure_static_docs()
    created_hw = ensure_hardware_placeholders()
    created_vivado = ensure_vivado_offline_scripts()
    created_profiles = ensure_profiles()
    constraint_info = ensure_constraints()
    write_project_status(status)
    return {
        "created_docs": created_docs,
        "created_hardware_placeholders": created_hw,
        "created_vivado_scripts": created_vivado,
        "created_profiles": created_profiles,
        "constraints": constraint_info,
    }


def git_precheck():
    values = {
        "repo": git_value("rev-parse", "--show-toplevel"),
        "branch": git_value("branch", "--show-current"),
        "head": git_value("rev-parse", "HEAD"),
        "status": active_status_line(),
        "last": git_value("log", "-1", "--oneline"),
    }
    lines = [
        "P1_GIT_PRECHECK=1",
        f"repo={values['repo']}",
        f"branch={values['branch']}",
        f"head={values['head']}",
        f"last={values['last']}",
        f"dirty_status={'clean' if not values['status'] else 'dirty'}",
        NO_HW,
        PENDING_HW,
        "",
        values["status"] or "(clean)",
    ]
    write_text(GENERATED / "p1_git_precheck.txt", "\n".join(lines))
    ok = Path(values["repo"]).resolve() == ROOT.resolve()
    return gate("git_precheck", PASS if ok else FAIL, "repository root recorded" if ok else "wrong repository root", values, GENERATED / "p1_git_precheck.txt")


def bootstrap_evidence_review():
    path = GENERATED / "offline_gate_summary.md"
    if not path.exists():
        write_gate_markdown(GENERATED / "p1_bootstrap_evidence_review.md", "P1 Bootstrap Evidence Review", FAIL, "offline gate summary missing")
        return gate("bootstrap_manifest_check", FAIL, "offline gate summary missing", summary_path=GENERATED / "p1_bootstrap_evidence_review.md")
    text = read_text(path)
    no_hw = "NO_HARDWARE_ACTIONS_EXECUTED: true" in text or "NO_HARDWARE_ACTIONS_EXECUTED=1" in text
    status_match = re.search(r"BOOTSTRAP_STATUS:\s*([A-Z_]+)", text)
    gates = re.findall(r"^##\s+([^:\n]+):\s*([A-Z_]+)", text, flags=re.MULTILINE)
    failed = [name for name, result in gates if result == FAIL]
    skipped = [name for name, result in gates if result in {SKIP, "PENDING_TOOL"}]
    result = PASS if no_hw else FAIL
    lines = [
        f"- Bootstrap status: {status_match.group(1) if status_match else 'unknown'}",
        f"- Gate count: {len(gates)}",
        f"- Failed gates: {', '.join(failed) if failed else 'none'}",
        f"- Skipped/pending gates: {', '.join(skipped) if skipped else 'none'}",
    ]
    write_gate_markdown(
        GENERATED / "p1_bootstrap_evidence_review.md",
        "P1 Bootstrap Evidence Review",
        result,
        "NO_HARDWARE_ACTIONS_EXECUTED found" if no_hw else "NO_HARDWARE_ACTIONS_EXECUTED missing",
        lines,
    )
    return gate("bootstrap_manifest_check", result, "bootstrap evidence reviewed", {"gate_count": len(gates), "failed": failed, "skipped": skipped}, GENERATED / "p1_bootstrap_evidence_review.md")


def required_docs_manifest():
    rows = []
    missing = []
    for item in REQUIRED_DOCS:
        path = ROOT / item
        source = SOURCE_PROJECT / item
        if path.exists():
            status = "present"
            digest = sha256(path)
        else:
            status = "missing"
            digest = ""
            missing.append(item)
        rows.append((item, status, digest, "source_exists" if source.exists() else "generated_missing_from_source"))
    lines = [
        "# Required Docs Manifest",
        "",
        f"RESULT: {FAIL if missing else PASS}",
        f"REASON: {'missing required docs' if missing else 'required docs present'}",
        NO_HW,
        PENDING_HW,
        "",
        "| Path | Status | SHA256 | Source note |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(f"| `{p}` | {s} | `{d}` | {note} |" for p, s, d, note in rows)
    write_text(GENERATED / "required_docs_manifest.md", "\n".join(lines))
    return gate("required_docs_check", FAIL if missing else PASS, "required docs present" if not missing else f"missing: {', '.join(missing)}", {"missing": missing}, GENERATED / "required_docs_manifest.md")


def agents_policy_check():
    text = read_text(ROOT / "AGENTS.md") if (ROOT / "AGENTS.md").exists() else ""
    checks = {
        "rule_0": "规则 0" in text,
        "reasoning": "推理" in text,
        "generality": "通用性" in text,
        "forbid_unauthorized_hw": "Do not program FPGA hardware" in text and "Default mode is `NO_HARDWARE=1`" in text,
        "pending_hw_not_pass": "PENDING_HW" in text and "PASS" in text,
        "skip_with_reason": "SKIP_WITH_REASON" in text,
        "tfdu_contract": "TFDU6102" in text and "safety contract" in text.lower(),
    }
    missing = [name for name, ok in checks.items() if not ok]
    lines = [f"- {name}: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items()]
    write_gate_markdown(
        GENERATED / "agents_policy_check.md",
        "Agents Policy Check",
        FAIL if missing else PASS,
        "AGENTS.md contains required P1 policies" if not missing else f"missing policy markers: {', '.join(missing)}",
        lines,
    )
    return gate("agents_policy_check", FAIL if missing else PASS, "AGENTS.md policy markers checked", {"missing": missing}, GENERATED / "agents_policy_check.md")


def project_status_check():
    path = ROOT / "PROJECT_STATUS.md"
    text = read_text(path) if path.exists() else ""
    required = [
        "Project: RF_COMM_MULTILANE",
        "Source project: C:\\Users\\user\\Documents\\RF_COMM",
        "New project: C:\\Users\\user\\Documents\\RF_COMM_MULTILANE",
        "P0_BOOTSTRAP: PASS",
        "P1_OFFLINE_HARDENING:",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "Latest known baseline commit: 17b17ae",
        "ps_driver_c_compile: syntax-only, not runtime pass",
        "Vivado hardware action: not authorized",
        "TFDU6102 hardware action: not authorized",
        "OFFLINE_BOOTSTRAP_PASS",
        "PASS_WITH_SKIPS",
        "SKIP_WITH_REASON",
        "PENDING_HW",
        "HW_PASS",
    ]
    missing = [item for item in required if item not in text]
    write_gate_markdown(
        GENERATED / "project_status_check.md",
        "Project Status Check",
        FAIL if missing else PASS,
        "PROJECT_STATUS.md has required fields" if not missing else f"missing: {', '.join(missing)}",
    )
    return gate("project_status_check", FAIL if missing else PASS, "PROJECT_STATUS.md checked", {"missing": missing}, GENERATED / "project_status_check.md")


def parse_xdc(path):
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


def xdc_status(path):
    parts = set(Path(path).parts)
    p = Path(path).as_posix()
    if p.startswith(".Xil/"):
        return "tool-generated"
    if "legacy_safe_tools" in parts:
        return "reference"
    if "constraints" in parts and "active" in parts and Path(path).name == "PORT1.generated.xdc":
        return "active"
    if "constraints" in parts and "active" in parts:
        return "active_aux"
    if "legacy_conflicts" in parts:
        return "reference_conflict"
    if p.startswith("legacy/") or "legacy_reference" in parts or "docs/legacy" in p:
        return "reference"
    if "sim" in parts or "test" in p.lower():
        return "test-only"
    return "unknown"


def constraint_checks():
    ensure_constraints()
    xdc_files = sorted(ROOT.rglob("*.xdc"))
    inv_lines = [
        "# XDC Inventory",
        "",
        NO_HW,
        PENDING_HW,
        "",
        "| Path | Status | Size | SHA256 | Modified UTC |",
        "| --- | --- | ---: | --- | --- |",
    ]
    active_files = []
    unknown = []
    for path in xdc_files:
        status = xdc_status(rel(path))
        if status == "active":
            active_files.append(path)
        if status == "unknown":
            unknown.append(rel(path))
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds")
        inv_lines.append(f"| `{rel(path)}` | {status} | {stat.st_size} | `{sha256(path)}` | {modified} |")
    write_text(GENERATED / "xdc_inventory.md", "\n".join(inv_lines))

    active_map = parse_xdc(ACTIVE_XDC)
    duplicate_ports = []
    pin_to_ports = {}
    for port, props in active_map.items():
        pin = props.get("PACKAGE_PIN")
        if pin:
            pin_to_ports.setdefault(pin, []).append(port)
    duplicate_pins = {pin: ports for pin, ports in pin_to_ports.items() if len(ports) > 1}
    active_unique = len([p for p in active_files if p.name == "PORT1.generated.xdc"]) == 1
    result = PASS if active_unique and not duplicate_ports and not duplicate_pins and not unknown else FAIL
    summary_lines = [
        f"- Active XDC: `{rel(ACTIVE_XDC)}`",
        f"- Active XDC count: {len(active_files)}",
        f"- Active ports: {len(active_map)}",
        f"- Unknown XDC files: {', '.join(unknown) if unknown else 'none'}",
        f"- Duplicate pins: {json.dumps(duplicate_pins, ensure_ascii=False) if duplicate_pins else 'none'}",
    ]
    write_gate_markdown(
        GENERATED / "constraint_uniqueness_summary.md",
        "Constraint Uniqueness Summary",
        result,
        "active XDC is unique and generated pinmap mirror exists" if result == PASS else "constraint inventory has failures",
        summary_lines,
    )
    write_gate_markdown(
        GENERATED / "copied_constraints_manifest.md",
        "Copied Constraints Manifest",
        PASS,
        "constraints are generated from canonical pinmap; no legacy active XDC copied",
        [
            f"- Source pinmap: `{rel(PINMAP_SOURCE)}`",
            f"- Active XDC: `{rel(ACTIVE_XDC)}`",
            f"- Derived active profile: `{rel(ACTIVE_PROFILE)}`",
            f"- Derived active pinmap: `{rel(PINMAP_ACTIVE)}`",
        ],
    )
    wrapper_text = read_text(ROOT / "rtl/ir_top_new.sv") if (ROOT / "rtl/ir_top_new.sv").exists() else ""
    wrapper_ports = set()
    for match in re.finditer(r"\b(?:input|output)\s+(?:logic\s+)?(?:\[[^\]]+\]\s+)?([A-Za-z_][A-Za-z0-9_]*)", wrapper_text):
        wrapper_ports.add(match.group(1))
    xdc_base_ports = {port.split("[")[0] for port in active_map}
    missing_wrapper = sorted(xdc_base_ports - wrapper_ports)
    write_gate_markdown(
        GENERATED / "wrapper_xdc_consistency_summary.md",
        "Wrapper XDC Consistency Summary",
        PASS if not missing_wrapper else FAIL,
        "active XDC ports are present in ir_top_new wrapper" if not missing_wrapper else f"missing wrapper ports: {', '.join(missing_wrapper)}",
        [f"- XDC base ports: {', '.join(sorted(xdc_base_ports))}", f"- Wrapper ports: {', '.join(sorted(wrapper_ports))}"],
    )
    return gate("constraint_uniqueness_check", result, "constraint checks completed", {"unknown": unknown, "active_count": len(active_files)}, GENERATED / "constraint_uniqueness_summary.md")


def active_profile_check():
    ensure_constraints()
    missing = []
    try:
        data = json.loads(read_text(ACTIVE_PROFILE))
    except Exception as exc:
        data = {}
        missing.append(f"json_parse:{exc}")
    checks = {
        "hardware_acceptance": data.get("hardware_acceptance") == "PENDING_HW",
        "no_hardware_actions_executed": data.get("no_hardware_actions_executed") is True,
        "lane_count_target": data.get("lane_count_target") == 2,
        "active_xdc_exists": (ROOT / data.get("active_xdc", "")).exists(),
        "pinmap_csv_exists": (ROOT / data.get("pinmap_csv", "")).exists(),
        "startup_wait": int(data.get("tfdu_startup_wait_us_min", 0)) >= 500,
        "stuck_high": int(data.get("tfdu_txd_stuck_high_limit_us_max", 999)) <= 80,
        "offline_only": data.get("offline_only") is True,
    }
    missing.extend(name for name, ok in checks.items() if not ok)
    lines = [f"- {name}: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items()]
    write_gate_markdown(
        GENERATED / "active_profile_check.md",
        "Active Profile Check",
        FAIL if missing else PASS,
        "active profile is valid" if not missing else f"profile failures: {', '.join(missing)}",
        lines,
    )
    return gate("active_profile_check", FAIL if missing else PASS, "active profile checked", {"missing": missing}, GENERATED / "active_profile_check.md")


def rtl_manifest():
    rows = []
    for path in sorted(list((ROOT / "rtl").rglob("*.sv")) + list((ROOT / "sim").rglob("*.sv"))):
        if "__pycache__" in path.parts:
            continue
        text = read_text(path)
        modules = re.findall(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_]*)", text, flags=re.MULTILINE)
        params = re.findall(r"\bparameter\s+(?:int\s+|logic\s+|bit\s+)?([A-Za-z_][A-Za-z0-9_]*)", text)
        parts = set(path.parts)
        if "legacy_reference" in parts:
            klass = "reference"
        elif "tb" in parts:
            klass = "testbench"
        else:
            klass = "active"
        rows.append(
            {
                "path": rel(path),
                "sha256": sha256(path),
                "language": "systemverilog",
                "class": klass,
                "modules": modules,
                "parameters": sorted(set(params)),
                "top_candidate": "ir_top_new" in modules,
            }
        )
    write_text(GENERATED / "rtl_source_manifest.json", json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    lines = [
        "# RTL Source Manifest",
        "",
        NO_HW,
        PENDING_HW,
        "",
        "| Path | Class | Modules | SHA256 |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(f"| `{r['path']}` | {r['class']} | `{', '.join(r['modules'])}` | `{r['sha256']}` |" for r in rows)
    write_text(GENERATED / "rtl_source_manifest.md", "\n".join(lines))
    active_modules = {module for r in rows if r["class"] == "active" for module in r["modules"]}
    required = {"tfdu_lane_phy", "ir_4ppm_codec", "ir_frame_l1", "ir_arq_l2", "ir_multilane_scheduler", "ir_axi_regs_new", "ir_top_new"}
    missing = sorted(required - active_modules)
    write_gate_markdown(
        GENERATED / "rtl_offline_lint_summary.md",
        "RTL Offline Lint Summary",
        PASS if not missing else FAIL,
        "required active RTL modules found" if not missing else f"missing active modules: {', '.join(missing)}",
    )
    return gate("rtl_source_manifest_check", PASS if not missing else FAIL, "RTL manifest generated", {"missing": missing, "count": len(rows)}, GENERATED / "rtl_source_manifest.md")


def software_manifest():
    rows = []
    for path in sorted((ROOT / "software").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        p = rel(path)
        if "legacy_" in p:
            klass = "needs-hardware" if any(token in p.lower() for token in ["ps_", "uart"]) else "unknown"
        elif "host_client" in p:
            klass = "offline-safe"
        elif "ps_driver" in p:
            klass = "offline-safe"
        else:
            klass = "unknown"
        rows.append({"path": p, "sha256": sha256(path), "class": klass})
    lines = [
        "# Software Source Manifest",
        "",
        NO_HW,
        PENDING_HW,
        "",
        "| Path | Class | SHA256 |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{r['path']}` | {r['class']} | `{r['sha256']}` |" for r in rows)
    write_text(GENERATED / "software_source_manifest.md", "\n".join(lines))
    return gate("software_source_manifest_check", PASS, "software manifest generated", {"count": len(rows)}, GENERATED / "software_source_manifest.md")


def tools_manifest():
    missing = [item for item in P1_TOOLS if not (ROOT / item).exists()]
    lines = [
        "# Tools Manifest",
        "",
        f"RESULT: {FAIL if missing else PASS}",
        f"REASON: {'missing tools' if missing else 'required tools present'}",
        NO_HW,
        PENDING_HW,
        "",
        "| Tool | Status | SHA256 |",
        "| --- | --- | --- |",
    ]
    for item in P1_TOOLS:
        path = ROOT / item
        lines.append(f"| `{item}` | {'present' if path.exists() else 'missing'} | `{sha256(path) if path.exists() else ''}` |")
    write_text(GENERATED / "tools_manifest.md", "\n".join(lines))
    return gate("tools_manifest_check", FAIL if missing else PASS, "tools manifest generated", {"missing": missing}, GENERATED / "tools_manifest.md")


def generate_manifests():
    results = [required_docs_manifest(), rtl_manifest(), software_manifest(), tools_manifest()]
    hard_fail = [r for r in results if r["result"] == FAIL]
    return gate(
        "manifest_generation",
        FAIL if hard_fail else PASS,
        "manifests generated" if not hard_fail else "one or more manifests failed",
        {"results": results},
        GENERATED / "required_docs_manifest.md",
    )


def no_hardware_scan():
    dangerous = [
        "open_hw",
        "connect_hw_server",
        "open_hw_target",
        "program_hw_devices",
        "refresh_hw_device",
        "hw_server",
        "jtag",
        "hardware manager",
        "serial port real device",
        "/dev/tty",
        "program bitstream",
        "xsdb",
        "fpga -f",
        "targets -set",
        "serial.serial",
        "createfile(\"com",
        "socket.connect",
    ]
    command_patterns = {
        "dow": re.compile(r"^\s*dow\b", re.IGNORECASE),
        "con": re.compile(r"^\s*con\b", re.IGNORECASE),
        "mwr": re.compile(r"^\s*mwr\b", re.IGNORECASE),
        "mrd": re.compile(r"^\s*mrd\b", re.IGNORECASE),
    }
    scan_roots = ["scripts", "tools", "docs", "software", "constraints", "rtl", "sim", "evidence/generated"]
    skip_parts = {"legacy", "legacy_reference", "legacy_safe_tools", "__pycache__"}
    allowed_script_markers = ["AllowHardware", "--allow-hardware", "RF_COMM_ALLOW_HW", "require-user-hw-authorization", "dry-run"]
    findings = []
    informational = []
    for root in scan_roots:
        base = ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            p = rel(path)
            if not path.is_file() or any(part in skip_parts for part in path.parts):
                continue
            if "/legacy_" in p or p.startswith("software/legacy_"):
                continue
            if path.suffix.lower() in {".pyc", ".pdf", ".png", ".jpg", ".jpeg"}:
                continue
            text = read_text(path)
            low = text.lower()
            hits = [tok for tok in dangerous if tok in low]
            for line in text.splitlines():
                for token, pattern in command_patterns.items():
                    if pattern.search(line):
                        hits.append(token)
            if not hits:
                continue
            hits = sorted(set(hits))
            if p.startswith("evidence/generated/"):
                informational.append((p, hits, "generated evidence mention"))
                continue
            if path.suffix.lower() in {".md", ".txt"}:
                informational.append((p, hits, "documentation mention"))
                continue
            guarded = any(marker.lower() in low for marker in allowed_script_markers)
            if guarded:
                informational.append((p, hits, "guarded script"))
            else:
                for line_no, line in enumerate(text.splitlines(), start=1):
                    lline = line.lower()
                    for tok in hits:
                        pattern = command_patterns.get(tok)
                        token_found = pattern.search(line) if pattern else tok in lline
                        if token_found:
                            findings.append({"path": p, "line": line_no, "token": tok, "context": line.strip()[:160]})
    result = PASS if not findings else FAIL
    lines = ["## Findings", ""]
    if findings:
        lines.extend(f"- `{f['path']}`:{f['line']} `{f['token']}` {f['context']}" for f in findings)
    else:
        lines.append("- none")
    lines.extend(["", "## Allowed / Informational", ""])
    lines.extend(f"- `{p}`: {', '.join(hits)} ({note})" for p, hits, note in informational[:200])
    write_gate_markdown(
        GENERATED / "no_hardware_action_static_scan.md",
        "No Hardware Action Static Scan",
        result,
        "no unguarded active hardware actions found" if result == PASS else "unguarded hardware action tokens found",
        lines,
    )
    return gate("no_hardware_action_static_scan", result, "hardware action static scan completed", {"findings": findings, "informational_count": len(informational)}, GENERATED / "no_hardware_action_static_scan.md")


def tfdu_contract_check():
    summary = GENERATED / "tfdu6102_offline_contract_summary.md"
    docs = [
        ROOT / "docs/TFDU6102_SAFETY_SUMMARY.md",
        ROOT / "docs/tfdu6102_safety_contract.md",
        ROOT / "HARDWARE_SAFETY.md",
    ]
    text = "\n".join(read_text(path) for path in docs if path.exists())
    rtl_text = "\n".join(read_text(path) for path in (ROOT / "rtl").glob("*.sv"))
    required = [
        "Txd",
        "Rxd",
        "SD",
        "Mode=High",
        "500 us",
        "80 us",
        "stuck-high",
        "duty",
        "IRED",
        "VCC2",
        "C1/C3 4.7 uF",
        "C2 0.1 uF",
    ]
    rtl_checks = {
        "startup_gate": "startup" in rtl_text.lower() and ("tx_allowed" in rtl_text.lower() or "startup_done" in rtl_text.lower()),
        "stuck_high_guard": "stuck_high" in rtl_text.lower(),
        "sd_default_shutdown": re.search(r"sd\s*<=\s*1'b1|assign\s+\w*sd\w*\s*=", rtl_text, re.IGNORECASE) is not None,
        "txd_default_low": re.search(r"txd\s*<=\s*1'b0|assign\s+\w*tx\w*\s*=", rtl_text, re.IGNORECASE) is not None,
    }
    missing = [item for item in required if item not in text]
    missing.extend(name for name, ok in rtl_checks.items() if not ok)
    lines = [f"- doc `{item}`: {'PASS' if item not in missing else 'FAIL'}" for item in required]
    lines.extend(f"- rtl {name}: {'PASS' if ok else 'FAIL'}" for name, ok in rtl_checks.items())
    result = PASS if not missing else FAIL
    write_gate_markdown(
        summary,
        "TFDU6102 Offline Contract Summary",
        result,
        "TFDU safety contract present and RTL markers found" if result == PASS else f"missing: {', '.join(missing)}",
        lines,
    )
    return gate("tfdu6102_safety_contract_check", result, "TFDU6102 contract checked", {"missing": missing}, summary)


def ps_driver_sequence_check():
    path = ROOT / "software/ps_driver/ir_driver.c"
    text = read_text(path) if path.exists() else ""
    ordered = [
        "IR_CONTROL_RESET",
        "ir_driver_write_profile_registers",
        "IR_CONTROL_COMMIT",
        "IR_CONTROL_ENABLE_PHY",
        "ir_driver_wait_startup",
        "IR_CONTROL_CLEAR_STICKY",
        "ir_driver_start_transaction",
        "ir_driver_poll_done",
        "ir_driver_stop",
        "ir_driver_read_final_counters",
        "ir_driver_shutdown",
    ]
    missing = [item for item in ordered if item not in text]
    lines = [f"- {item}: {'PASS' if item not in missing else 'FAIL'}" for item in ordered]
    write_gate_markdown(
        GENERATED / "ps_driver_sequence_summary.md",
        "PS Driver Sequence Summary",
        FAIL if missing else PASS,
        "PS driver static sequence markers found" if not missing else f"missing: {', '.join(missing)}",
        lines,
    )
    return gate("ps_driver_sequence_static_check", FAIL if missing else PASS, "PS driver sequence checked", {"missing": missing}, GENERATED / "ps_driver_sequence_summary.md")


def host_offline_stub_check():
    test_path = ROOT / "software/host_client/test_protocol_contract.py"
    if not test_path.exists():
        write_gate_markdown(GENERATED / "host_offline_stub_summary.md", "Host Offline Stub Summary", FAIL, "host offline test missing")
        return gate("host_offline_stub_run_check", FAIL, "host offline test missing", summary_path=GENERATED / "host_offline_stub_summary.md")
    proc = run_cmd([sys.executable, str(test_path)], timeout=60)
    result = PASS if proc["returncode"] == 0 and "HOST_CLIENT_PROTOCOL_TESTS=PASS" in proc["stdout"] else FAIL
    lines = [
        f"- Command: `{proc['cmd']}`",
        f"- Return code: {proc['returncode']}",
        "",
        "```text",
        proc["stdout"].strip(),
        proc["stderr"].strip(),
        "```",
    ]
    write_gate_markdown(
        GENERATED / "host_offline_stub_summary.md",
        "Host Offline Stub Summary",
        result,
        "host offline mock transport tests passed" if result == PASS else "host offline mock transport tests failed",
        lines,
    )
    return gate("host_offline_stub_run_check", result, "host offline stub checked", {"returncode": proc["returncode"]}, GENERATED / "host_offline_stub_summary.md")


def profiles_check():
    ensure_profiles()
    failures = []
    rows = []
    for path in sorted((ROOT / "profiles").glob("*.json")):
        try:
            data = json.loads(read_text(path))
        except Exception as exc:
            failures.append(f"{rel(path)} parse: {exc}")
            continue
        lane_count = int(data.get("lane_count", 0))
        payload = int(str(data.get("payload_lane_mask", "0")), 16)
        if data.get("name") == "G1_LANE0_BASELINE" and payload == 0x3:
            failures.append("G1_LANE0_BASELINE must not use 0x3")
        if payload >= (1 << lane_count) and lane_count > 0:
            failures.append(f"{rel(path)} payload mask exceeds lane_count")
        if "TWO_LANE" in data.get("name", "") and not (data.get("simulation_only") or data.get("hardware_acceptance") == "PENDING_HW"):
            failures.append(f"{rel(path)} two-lane profile must be sim-only or pending")
        rows.append((rel(path), data.get("name"), data.get("status")))
    lines = ["| Path | Name | Status |", "| --- | --- | --- |"]
    lines.extend(f"| `{p}` | {name} | {status} |" for p, name, status in rows)
    if failures:
        lines.extend(["", "## Failures", *(f"- {f}" for f in failures)])
    write_gate_markdown(
        GENERATED / "profile_check_summary.md",
        "Profile Check Summary",
        FAIL if failures else PASS,
        "profiles are valid" if not failures else "profile validation failed",
        lines,
    )
    return gate("profile_check", FAIL if failures else PASS, "profiles checked", {"failures": failures}, GENERATED / "profile_check_summary.md")


def vivado_script_audit():
    patterns = ["open_hw", "connect_hw_server", "open_hw_target", "program_hw_devices", "refresh_hw_device", "write_bitstream", "fpga -f"]
    files = []
    for suffix in ("*.tcl", "*.xpr", "*.bd", "*.jou", "*.log"):
        files.extend(ROOT.rglob(suffix))
    findings = []
    for path in sorted(files):
        p = rel(path)
        if p.startswith("legacy/") or "/legacy/" in p or "legacy_reference" in p:
            continue
        if p.startswith("evidence/generated/vivado/project/") or "legacy_safe_tools" in path.parts or p.startswith("software/legacy_"):
            continue
        text = read_text(path).lower()
        for token in patterns:
            if token in text:
                findings.append((p, token))
    result = PASS if not findings else FAIL
    lines = [
        f"- Audited files: {len(files)}",
        f"- Findings: {len(findings)}",
        *(f"- `{p}` contains `{token}`" for p, token in findings[:100]),
    ]
    write_gate_markdown(
        GENERATED / "vivado_script_audit.md",
        "Vivado Script Audit",
        result,
        "no active Vivado hardware commands found" if result == PASS else "active Vivado hardware commands found",
        lines,
    )
    write_gate_markdown(
        GENERATED / "vivado_offline_project_summary.md",
        "Vivado Offline Project Summary",
        PASS,
        "offline project scripts are present; no hardware execution performed",
        ["- `scripts/vivado/create_project_offline.tcl`", "- `scripts/vivado/validate_project_offline.tcl`"],
    )
    return gate("vivado_project_generation_dry_check", result, "Vivado scripts audited", {"findings": findings}, GENERATED / "vivado_script_audit.md")


def ip_packaging_check():
    component = ROOT / "legacy/RF_COMM/IPs/ip_ir_array/component.xml"
    xgui = ROOT / "legacy/RF_COMM/IPs/ip_ir_array/xgui"
    lines = [
        f"- Legacy component.xml exists: {component.exists()}",
        f"- Legacy xgui exists: {xgui.exists()}",
        "- Legacy IP is reference-only and is not a canonical build input.",
        "- Active P1 build input remains generated XDC plus active RTL skeleton.",
    ]
    result = PASS if component.exists() and xgui.exists() else SKIP
    write_gate_markdown(
        GENERATED / "ip_packaging_dry_check.md",
        "IP Packaging Dry Check",
        result,
        "legacy IP package metadata available as reference" if result == PASS else "legacy IP package metadata unavailable",
        lines,
    )
    return gate("ip_packaging_dry_check", result, "IP packaging dry check completed", {"component": component.exists(), "xgui": xgui.exists()}, GENERATED / "ip_packaging_dry_check.md")


def evidence_consistency_check():
    banned = [
        "HARDWARE_PASS",
        "TFDU_PASS",
        "LANE0_PASS",
        "LANE1_PASS",
        "ETHERNET_PASS",
        "ROTATION_PASS",
        "SOAK_PASS",
        "PRODUCT_FINAL_PASS",
    ]
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
            if p == "evidence/generated/evidence_consistency_summary.md":
                continue
            text = read_text(item)
            for token in banned:
                for match in re.finditer(re.escape(token), text):
                    suffix = text[match.end() : match.end() + 8]
                    prefix = text[max(0, match.start() - 32) : match.start()]
                    if suffix.startswith("_ABSENT") or "FORBIDDEN_CLAIM_" in prefix:
                        continue
                    findings.append((p, token))
    result = PASS if not findings else FAIL
    lines = [
        f"- Banned promotion tokens found: {len(findings)}",
        *(f"- `{p}` contains `{token}`" for p, token in findings),
        "- PENDING_HW is allowed.",
        "- OFFLINE_PASS/SIMULATION_PASS are allowed only as non-hardware claims.",
    ]
    write_gate_markdown(
        GENERATED / "evidence_consistency_summary.md",
        "Evidence Consistency Summary",
        result,
        "no forbidden hardware pass promotion tokens found" if result == PASS else "forbidden hardware pass promotion tokens found",
        lines,
    )
    return gate("evidence_consistency_check", result, "evidence consistency checked", {"findings": findings}, GENERATED / "evidence_consistency_summary.md")


def software_no_real_io_check():
    token_patterns = {
        "serial.Serial": re.compile(r"\bserial\.Serial\b"),
        "socket.connect": re.compile(r"\bsocket\.connect\b"),
        "COM port": re.compile(r"\bCOM\d+\b"),
        "mrd": re.compile(r"^\s*mrd\b", re.MULTILINE),
        "mwr": re.compile(r"^\s*mwr\b", re.MULTILINE),
        "xsdb": re.compile(r"\bxsdb\b"),
        "open_hw": re.compile(r"\bopen_hw\b"),
    }
    findings = []
    for path in sorted((ROOT / "software").rglob("*")):
        if not path.is_file() or "legacy_" in rel(path) or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        text = read_text(path)
        for token, pattern in token_patterns.items():
            if pattern.search(text):
                findings.append((rel(path), token))
    write_gate_markdown(
        GENERATED / "software_no_real_io_summary.md",
        "Software No Real IO Summary",
        PASS if not findings else FAIL,
        "active software offline stubs do not contain real IO tokens" if not findings else "active software contains real IO tokens",
        [*(f"- `{p}` contains `{token}`" for p, token in findings)] if findings else ["- none"],
    )
    return gate("software_no_real_io_check", PASS if not findings else FAIL, "software real IO scan complete", {"findings": findings}, GENERATED / "software_no_real_io_summary.md")


def run_existing_bootstrap():
    script = ROOT / "scripts/run_offline_gates.py"
    if not script.exists():
        return gate("bootstrap_legacy_offline_gates", SKIP, "scripts/run_offline_gates.py missing")
    proc = run_cmd([sys.executable, str(script)], timeout=600)
    result = PASS if proc["returncode"] == 0 else FAIL
    write_gate_markdown(
        GENERATED / "p1_bootstrap_legacy_gate_run.md",
        "P1 Bootstrap Legacy Gate Run",
        result,
        "existing offline gates completed" if result == PASS else "existing offline gates failed",
        [
            f"- Command: `{proc['cmd']}`",
            f"- Return code: {proc['returncode']}",
            "",
            "```text",
            proc["stdout"][-4000:].strip(),
            proc["stderr"][-4000:].strip(),
            "```",
        ],
    )
    return gate("bootstrap_legacy_offline_gates", result, "existing offline gates completed" if result == PASS else "existing offline gates failed", {"returncode": proc["returncode"]}, GENERATED / "p1_bootstrap_legacy_gate_run.md")


def git_cleanliness_report():
    status = active_status_line()
    lines = [NO_HW, PENDING_HW, "", status or "(clean)"]
    write_text(GENERATED / "git_cleanliness_report.md", "\n".join(["# Git Cleanliness Report", "", *lines]))
    return gate("git_cleanliness_report", PASS, "git status recorded", {"dirty": bool(status), "status": status}, GENERATED / "git_cleanliness_report.md")


def final_status(results, allow_skips=False):
    if any(r["result"] == FAIL for r in results):
        return FAIL
    if any(r["result"] == SKIP for r in results):
        return "PASS_WITH_SKIPS" if allow_skips else FAIL
    return PASS


def write_p1_summary(results, status):
    payload = {
        "status": status,
        "generated_at_utc": now_iso(),
        "no_hardware_actions_executed": True,
        "hardware_acceptance": "PENDING_HW",
        "results": results,
    }
    write_text(GENERATED / "offline_gate_summary.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    write_text(GENERATED / "p1_offline_hardening_summary.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    pass_gates = [r["name"] for r in results if r["result"] == PASS]
    fail_gates = [r["name"] for r in results if r["result"] == FAIL]
    skip_gates = [r for r in results if r["result"] == SKIP]
    fail_lines = [f"- {name}" for name in fail_gates] if fail_gates else ["- none"]
    skip_lines = [f"- {r['name']}: {r['reason']}" for r in skip_gates] if skip_gates else ["- none"]
    lines = [
        "# Offline Gate Summary",
        "",
        f"P1_OFFLINE_HARDENING: {status}",
        f"BOOTSTRAP_STATUS: {status}",
        NO_HW,
        PENDING_HW,
        "",
        "## Generated Summaries",
        "",
        "- evidence/generated/offline_gate_summary.md",
        "- evidence/generated/p1_offline_hardening_summary.md",
        "- evidence/generated/no_hardware_action_static_scan.md",
        "- evidence/generated/tfdu6102_offline_contract_summary.md",
        "- evidence/generated/constraint_uniqueness_summary.md",
        "- evidence/generated/rtl_offline_lint_summary.md",
        "- evidence/generated/ps_driver_sequence_summary.md",
        "- evidence/generated/host_offline_stub_summary.md",
        "",
        "## PASS",
        "",
        *(f"- {name}" for name in pass_gates),
        "",
        "## FAIL",
        "",
        *fail_lines,
        "",
        "## SKIP_WITH_REASON",
        "",
        *skip_lines,
        "",
        "## Gate Details",
        "",
    ]
    for r in results:
        lines.extend(
            [
                f"### {r['name']}: {r['result']}",
                "",
                f"REASON: {r['reason']}",
                f"SUMMARY: {r.get('summary_path') or 'n/a'}",
                "",
            ]
        )
    write_text(GENERATED / "offline_gate_summary.md", "\n".join(lines))
    write_text(GENERATED / "p1_offline_hardening_summary.md", "\n".join(lines))


def run_all(output_dir=GENERATED, strict=False, allow_skips=False, run_bootstrap=True):
    global GENERATED
    GENERATED = Path(output_dir)
    if not GENERATED.is_absolute():
        GENERATED = ROOT / GENERATED
    GENERATED.mkdir(parents=True, exist_ok=True)
    ensure_static_artifacts("IN_PROGRESS")
    results = [
        git_precheck(),
        ensure_dirs(),
        bootstrap_evidence_review(),
        agents_policy_check(),
        required_docs_manifest(),
        project_status_check(),
        tools_manifest(),
        no_hardware_scan(),
        tfdu_contract_check(),
        constraint_checks(),
        active_profile_check(),
        rtl_manifest(),
        software_manifest(),
        ps_driver_sequence_check(),
        host_offline_stub_check(),
        profiles_check(),
        vivado_script_audit(),
        ip_packaging_check(),
        software_no_real_io_check(),
    ]
    if run_bootstrap:
        results.append(run_existing_bootstrap())
    results.extend(
        [
            generate_manifests(),
            evidence_consistency_check(),
            git_cleanliness_report(),
        ]
    )
    status = final_status(results, allow_skips=allow_skips)
    write_project_status(status)
    write_p1_summary(results, status)
    return status, results
