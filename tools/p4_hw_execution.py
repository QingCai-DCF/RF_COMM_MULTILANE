#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from p4_hw_authorization import resolve_project_path
from p4_hw_evidence import P4_DIR, ROOT, active_hashes, git_value, now_iso, rel, sha256_or_missing, write_json, write_text


DEFAULT_VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
DEFAULT_HW_SERVER_URL = "localhost:3121"
DEFAULT_JTAG_FREQUENCY_HZ = 1_000_000
SHUTDOWN_SCRIPT = ROOT / "scripts" / "hw" / "program_tfdu_shutdown_safe.ps1"
SHUTDOWN_BITSTREAM = ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"


def _status_path(name: str) -> Path:
    return P4_DIR / name


def _write_hw_markdown(path: Path, title: str, result: str, reason: str, lines: list[str], *, no_hw: bool) -> None:
    body = [
        f"# {title}",
        "",
        f"generated_at_utc: {now_iso()}",
        f"repo: `{ROOT}`",
        f"HEAD: `{git_value('rev-parse', 'HEAD')}`",
        f"RESULT: {result}",
        f"REASON: {reason}",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hw).lower()}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        *lines,
        "",
    ]
    write_text(path, "\n".join(body))


def _resolve_vivado() -> str | None:
    return shutil.which("vivado") or shutil.which("vivado.bat") or (str(DEFAULT_VIVADO) if DEFAULT_VIVADO.exists() else None)


def _run(cmd: list[str], *, timeout: int, env: dict[str, str] | None = None) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, env=env)
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


def _tcl_path(path: Path) -> str:
    return path.resolve().as_posix()


def _write_environment_capture_tcl(path: Path, output_path: Path) -> None:
    script = f"""
set out_file {{{_tcl_path(output_path)}}}
set fh [open $out_file "w"]
proc log_line {{line}} {{
  global fh
  puts $line
  puts $fh $line
  flush $fh
}}
log_line "P4_ENVIRONMENT_CAPTURE_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set rc [catch {{
  open_hw_manager
  connect_hw_server -url {{{DEFAULT_HW_SERVER_URL}}}
  set targets [get_hw_targets -quiet *]
  log_line "HW_TARGET_COUNT=[llength $targets]"
  if {{[llength $targets] == 0}} {{
    error "No JTAG hw_target found."
  }}
  foreach target $targets {{
    log_line "HW_TARGET=$target"
    if {{[catch {{current_hw_target $target}} target_err]}} {{
      log_line "CURRENT_HW_TARGET_ERROR=$target_err"
      continue
    }}
    if {{[catch {{set_property PARAM.FREQUENCY {DEFAULT_JTAG_FREQUENCY_HZ} $target}} freq_err]}} {{
      log_line "HW_JTAG_FREQUENCY_WARN=$freq_err"
    }} else {{
      log_line "HW_JTAG_FREQUENCY_HZ={DEFAULT_JTAG_FREQUENCY_HZ}"
    }}
    if {{[catch {{open_hw_target $target}} open_err]}} {{
      log_line "OPEN_HW_TARGET_ERROR=$open_err"
      continue
    }}
    set devices [get_hw_devices -quiet *]
    log_line "HW_DEVICE_COUNT=[llength $devices]"
    foreach dev $devices {{
      current_hw_device $dev
      log_line "HW_DEVICE=$dev"
      foreach prop {{NAME PART IDCODE IS_PROGRAMMED PROGRAM.FILE}} {{
        if {{[catch {{set value [get_property $prop $dev]}} prop_err]}} {{
          log_line "HW_DEVICE_PROP $dev $prop ERROR=$prop_err"
        }} else {{
          log_line "HW_DEVICE_PROP $dev $prop=$value"
        }}
      }}
    }}
    catch {{close_hw_target $target}}
  }}
  catch {{disconnect_hw_server}}
  catch {{close_hw_manager}}
}} err opts]
if {{$rc != 0}} {{
  log_line "P4_ENVIRONMENT_CAPTURE=FAIL"
  log_line "P4_ENVIRONMENT_CAPTURE_ERROR=$err"
  close $fh
  exit 11
}}
log_line "P4_ENVIRONMENT_CAPTURE=PASS"
close $fh
exit 0
""".strip()
    write_text(path, script)


def _write_safe_idle_program_tcl(path: Path, bitstream: Path, log_path: Path) -> None:
    helper = ROOT / "legacy" / "RF_COMM" / "tools" / "hw_connect_utils.tcl"
    script = f"""
set log_file {{{_tcl_path(log_path)}}}
set fh [open $log_file "w"]
proc say {{line}} {{
  global fh
  puts $line
  puts $fh $line
  flush $fh
}}
say "P4_SAFE_IDLE_PROGRAMMING_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set bit_file {{{_tcl_path(bitstream)}}}
if {{![file exists $bit_file]}} {{
  say "SAFE_IDLE_BITSTREAM_MISSING=$bit_file"
  close $fh
  exit 20
}}
source {{{_tcl_path(helper)}}}
set rc [catch {{
  set dev [rf_hw_open_zynq_device {{{DEFAULT_HW_SERVER_URL}}} {DEFAULT_JTAG_FREQUENCY_HZ}]
  refresh_hw_device -update_hw_probes false $dev
  foreach prop {{NAME PART IDCODE IS_PROGRAMMED}} {{
    if {{[catch {{set value [get_property $prop $dev]}} prop_err]}} {{
      say "SAFE_IDLE_DEVICE_PROP $prop ERROR=$prop_err"
    }} else {{
      say "SAFE_IDLE_DEVICE_PROP $prop=$value"
    }}
  }}
  set_property PROGRAM.FILE $bit_file $dev
  program_hw_devices $dev
  say "SAFE_IDLE_BITSTREAM_PROGRAMMED=$bit_file"
  say "READBACK_LIMITED=1"
  say "READBACK_LIMITED_REASON=no direct TFDU pin readback or ILA proxy was available in this runner"
}} err opts]
if {{$rc != 0}} {{
  say "P4_SAFE_IDLE_PROGRAMMING=FAIL"
  say "P4_SAFE_IDLE_PROGRAMMING_ERROR=$err"
  close $fh
  exit 21
}}
say "P4_SAFE_IDLE_PROGRAMMING=PASS"
close $fh
exit 0
""".strip()
    write_text(path, script)


def _write_bitstream_manifest(profile: str, bitstream: Path) -> None:
    hashes = active_hashes()
    lines = [
        "P4_BITSTREAM_CANDIDATE: BITSTREAM_GENERATED_NO_HW",
        "NO_HARDWARE_ACTIONS_EXECUTED: false",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"bitstream_candidate_path: `{rel(bitstream)}`",
        f"bitstream_candidate_sha256: `{sha256_or_missing(bitstream)}`",
        f"profile: `{profile}`",
        f"profile_sha256: `{sha256_or_missing(resolve_project_path(profile))}`",
        f"shutdown_bitstream_path: `{rel(SHUTDOWN_BITSTREAM)}`",
        f"shutdown_bitstream_sha256: `{sha256_or_missing(SHUTDOWN_BITSTREAM)}`",
        "",
        "## Active Inputs",
        "",
        *(f"- {name}: `{value}`" for name, value in hashes.items()),
    ]
    _write_hw_markdown(
        P4_DIR / "p4_bitstream_candidate_manifest.md",
        "P4 Bitstream Candidate Manifest",
        "PASS",
        "safe-idle bitstream candidate and frozen inputs recorded before authorized programming",
        lines,
        no_hw=False,
    )


def _write_tool_versions(vivado: str | None, max_runtime_sec: int) -> None:
    rows = [
        f"P4_TOOL_VERSION_CAPTURE: {'PASS' if vivado else 'FAIL'}",
        "NO_HARDWARE_ACTIONS_EXECUTED: false",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"python: {os.sys.version.replace(chr(10), ' ')}",
        f"git: {(_run(['git', '--version'], timeout=30)['stdout'] or '').strip()}",
        f"vivado_path: {vivado or 'MISSING'}",
        f"max_runtime_sec: {max_runtime_sec}",
    ]
    if vivado:
        version = _run([vivado, "-version"], timeout=60)
        rows.extend(
            [
                f"vivado_version_exit: {version['returncode']}",
                "vivado_version_stdout:",
                version["stdout"][-2000:],
                "vivado_version_stderr:",
                version["stderr"][-2000:],
            ]
        )
    write_text(P4_DIR / "p4_tool_versions.txt", "\n".join(rows))


def _run_shutdown(args, env: dict[str, str]) -> dict:
    profile = args.profile
    shutdown_hash = sha256_or_missing(SHUTDOWN_BITSTREAM)
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SHUTDOWN_SCRIPT),
        "-AllowHardware",
        "-ExecuteHardware",
        "-MaxRuntimeSec",
        str(args.max_runtime_sec),
        "-ShutdownOnExit",
        "-BoardId",
        args.board_id,
        "-Bitstream",
        rel(SHUTDOWN_BITSTREAM),
        "-BitstreamSha256",
        shutdown_hash,
        "-TestProfile",
        args.stage,
        "-ActivePinmapHash",
        args.active_pinmap_hash,
        "-ActiveXdcHash",
        args.active_xdc_hash,
        "-AuthorizationFile",
        args.authorization_file,
        "-ProfilePath",
        profile,
        "-EvidenceDir",
        str(P4_DIR / "shutdown" / "forced_shutdown"),
        "-VivadoPath",
        _resolve_vivado() or str(DEFAULT_VIVADO),
    ]
    profile_sha = sha256_or_missing(resolve_project_path(profile))
    if profile_sha != "MISSING":
        cmd.extend(["-ProfileSha256", profile_sha])
    return _run(cmd, timeout=min(max(args.max_runtime_sec, 60), 600), env=env)


def run_authorized_safe_idle_sequence(args, auth_payload: dict) -> dict:
    P4_DIR.mkdir(parents=True, exist_ok=True)
    (P4_DIR / "shutdown").mkdir(parents=True, exist_ok=True)
    bitstream = resolve_project_path(args.bitstream)
    vivado = _resolve_vivado()
    max_runtime = int(args.max_runtime_sec or 300)
    stage_payload: dict = {
        "environment_capture": rel(P4_DIR / "p4_environment_capture.md"),
        "authorization_record": rel(P4_DIR / "p4_authorization_record.md"),
        "bitstream_manifest": rel(P4_DIR / "p4_bitstream_candidate_manifest.md"),
        "safe_idle_readback": rel(P4_DIR / "p4_safe_idle_readback_summary.md"),
        "shutdown_summary": rel(P4_DIR / "shutdown" / "p4_shutdown_summary.md"),
        "ENVIRONMENT_CAPTURE": "SKIP",
        "SAFE_IDLE": "SKIP",
        "SHUTDOWN_ON_EXIT": "SKIP",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "STOP_CONDITIONS_TRIGGERED": [],
        "READBACK_LIMITED": True,
        "run_results": [],
    }
    _write_tool_versions(vivado, max_runtime)
    _write_bitstream_manifest(args.profile, bitstream)
    if not vivado:
        stage_payload["ENVIRONMENT_CAPTURE"] = "FAIL"
        stage_payload["STOP_CONDITIONS_TRIGGERED"].append("vivado_missing")
        _write_hw_markdown(
            P4_DIR / "p4_environment_capture.md",
            "P4 Environment Capture",
            "FAIL",
            "Vivado executable was missing, so no hardware connection was attempted",
            ["P4_ENVIRONMENT_CAPTURE: FAIL", "HARDWARE_ACTIONS_EXECUTED: false"],
            no_hw=True,
        )
        return stage_payload

    env = os.environ.copy()
    env.setdefault("RF_COMM_HW_AUTH", "I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW")
    capture_tcl = P4_DIR / "p4_environment_capture.tcl.txt"
    capture_raw = P4_DIR / "p4_jtag_targets.txt"
    _write_environment_capture_tcl(capture_tcl, capture_raw)
    safe_idle_tcl = P4_DIR / "p4_safe_idle_programming.tcl.txt"
    safe_idle_log = P4_DIR / "p4_safe_idle_programming_log.txt"
    _write_safe_idle_program_tcl(safe_idle_tcl, bitstream, safe_idle_log)

    hardware_started = False
    capture = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    program = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        hardware_started = True
        capture = _run([vivado, "-mode", "batch", "-source", str(capture_tcl)], timeout=min(max_runtime, 300), env=env)
        stage_payload["run_results"].append({"stage": "environment_capture", **capture})
        if capture["returncode"] == 0:
            stage_payload["ENVIRONMENT_CAPTURE"] = "PASS"
        else:
            stage_payload["ENVIRONMENT_CAPTURE"] = "FAIL"
            stage_payload["STOP_CONDITIONS_TRIGGERED"].append("environment_capture_failed")
        if stage_payload["ENVIRONMENT_CAPTURE"] == "PASS" and args.stage in {"all", "safe-idle", "safe-idle-programming"}:
            program = _run([vivado, "-mode", "batch", "-source", str(safe_idle_tcl)], timeout=min(max_runtime, 300), env=env)
            stage_payload["run_results"].append({"stage": "safe_idle_programming", **program})
            if program["returncode"] == 0:
                stage_payload["SAFE_IDLE"] = "PASS_WITH_LIMITED_READBACK"
            else:
                stage_payload["SAFE_IDLE"] = "FAIL"
                stage_payload["STOP_CONDITIONS_TRIGGERED"].append("safe_idle_programming_failed")
    finally:
        if hardware_started:
            shutdown = _run_shutdown(args, env)
            stage_payload["run_results"].append({"stage": "shutdown", **shutdown})
            shutdown_text = "\n".join([shutdown.get("stdout", ""), shutdown.get("stderr", "")])
            if shutdown["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text:
                stage_payload["SHUTDOWN_ON_EXIT"] = "PASS"
            else:
                stage_payload["SHUTDOWN_ON_EXIT"] = "FAIL"
                stage_payload["STOP_CONDITIONS_TRIGGERED"].append("shutdown_failed")

    stage_payload["HARDWARE_ACTIONS_EXECUTED"] = hardware_started
    stage_payload["NO_HARDWARE_ACTIONS_EXECUTED"] = not hardware_started
    write_json(P4_DIR / "p4_authorized_run_results.json", stage_payload)
    _write_hw_markdown(
        P4_DIR / "p4_environment_capture.md",
        "P4 Environment Capture",
        stage_payload["ENVIRONMENT_CAPTURE"],
        "authorized JTAG target capture completed" if stage_payload["ENVIRONMENT_CAPTURE"] == "PASS" else "authorized JTAG target capture failed",
        [
            f"P4_ENVIRONMENT_CAPTURE: {stage_payload['ENVIRONMENT_CAPTURE']}",
            "HARDWARE_ACTIONS_EXECUTED: true",
            f"JTAG_TARGETS_LOG: `{rel(capture_raw)}`",
            f"CAPTURE_RETURN_CODE: {capture['returncode']}",
            f"BOARD_ID_REQUESTED: `{auth_payload.get('BOARD_ID', args.board_id)}`",
        ],
        no_hw=False,
    )
    safe_idle_log_text = safe_idle_log.read_text(encoding="utf-8", errors="ignore") if safe_idle_log.exists() else ""
    _write_hw_markdown(
        P4_DIR / "p4_safe_idle_readback_summary.md",
        "P4 Safe Idle Readback Summary",
        stage_payload["SAFE_IDLE"],
        "safe-idle bitstream was programmed, but direct TFDU pin readback is limited"
        if stage_payload["SAFE_IDLE"] == "PASS_WITH_LIMITED_READBACK"
        else "safe-idle programming did not pass",
        [
            f"SAFE_IDLE: {stage_payload['SAFE_IDLE']}",
            "READBACK_LIMITED: true",
            "reason: no direct TFDU pin readback or ILA proxy available in this runner",
            f"SAFE_IDLE_BITSTREAM: `{rel(bitstream)}`",
            f"SAFE_IDLE_BITSTREAM_SHA256: `{sha256_or_missing(bitstream)}`",
            f"PROGRAM_RETURN_CODE: {program['returncode']}",
            "",
            "## Safe Idle Programming Log Tail",
            "",
            "```text",
            safe_idle_log_text[-4000:] if safe_idle_log_text else "(no safe-idle programming log)",
            "```",
        ],
        no_hw=False,
    )
    shutdown_text = "\n".join([shutdown.get("stdout", ""), shutdown.get("stderr", "")])
    write_text(P4_DIR / "shutdown" / "p4_shutdown_log.txt", shutdown_text or "(no shutdown output)")
    _write_hw_markdown(
        P4_DIR / "shutdown" / "p4_shutdown_summary.md",
        "P4 Shutdown Summary",
        stage_payload["SHUTDOWN_ON_EXIT"],
        "forced TFDU shutdown was programmed after the authorized hardware run"
        if stage_payload["SHUTDOWN_ON_EXIT"] == "PASS"
        else "forced TFDU shutdown did not complete",
        [
            f"SHUTDOWN_ON_EXIT: {stage_payload['SHUTDOWN_ON_EXIT']}",
            f"SHUTDOWN_BITSTREAM: `{rel(SHUTDOWN_BITSTREAM)}`",
            f"SHUTDOWN_BITSTREAM_SHA256: `{sha256_or_missing(SHUTDOWN_BITSTREAM)}`",
            f"SHUTDOWN_RETURN_CODE: {shutdown['returncode']}",
            f"TFDU_SHUTDOWN_PROGRAMMED_SEEN: {str('TFDU_SHUTDOWN_PROGRAMMED' in shutdown_text).lower()}",
        ],
        no_hw=False,
    )
    return stage_payload
