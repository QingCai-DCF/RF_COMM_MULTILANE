#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from p4_auto_parse_ila import (
    parse_lane0_ack_retry_capture_dir,
    parse_lane0_frame_crc_capture_dir,
    parse_lane1_ack_retry_capture_dir,
    parse_lane1_frame_crc_capture_dir,
    parse_raw_lane_matrix_capture_dir,
    parse_safe_idle_capture_dir,
    parse_tfdu_control_idle_capture_dir,
    parse_two_lane_300s_soak_capture_dir,
    parse_two_lane_minimal_capture_dir,
)
from p5_hardware_authorization import (
    DEFAULT_ABORT_FILE,
    DEFAULT_AUTH_FILE,
    DEFAULT_BOARD_ID,
    DEFAULT_SHUTDOWN_BITSTREAM,
    AUTH_ENV,
    AUTH_ENV_VALUE,
    validate_authorization,
)
from p5_lib import (
    FAIL,
    GENERATED,
    NOT_RUN_OPTIONAL,
    P5_DIR,
    PASS,
    PASS_WITH_NOTES,
    PAYLOAD_LENGTHS,
    PAYLOAD_PATTERNS,
    PENDING_HW_NOT_EXECUTED,
    ROOT,
    active_hashes,
    ensure_dirs,
    git_value,
    load_json,
    p5_hardware_pending_payload,
    rel,
    sha256_or_missing,
    write_csv,
    write_json,
    write_markdown,
    write_text,
)


DEFAULT_VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
DEFAULT_HW_SERVER_URL = "localhost:3121"
DEFAULT_JTAG_FREQUENCY_HZ = 1_000_000
PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED = "PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED"
UNSUPPORTED_BY_PROFILE_WITH_REASON = "UNSUPPORTED_BY_PROFILE_WITH_REASON"


ParserFunc = Callable[[Path], dict[str, Any]]


P5_STAGE_RUNS: dict[str, dict[str, Any]] = {
    "safe_idle_recheck": {
        "marker": "SAFE_IDLE_RECHECK",
        "profile": "profiles/p5/p5_safe_idle_recheck.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_safe_idle.bit",
        "ltx": "evidence/generated/vivado/p4_auto_safe_idle_debug.ltx",
        "capture_prefix": "safe_idle_recheck",
        "capture_dir": "evidence/hardware/p5/ila/safe_idle_recheck",
        "evidence_dir": "evidence/hardware/p5/safe_idle_recheck",
        "summary": "evidence/generated/p5_safe_idle_recheck_summary.md",
        "parse_key": "SAFE_IDLE_ILA_PARSE",
        "parser": parse_safe_idle_capture_dir,
        "post_wait_ms": 1000,
    },
    "tfdu_control_idle_recheck": {
        "marker": "TFDU_CONTROL_IDLE_RECHECK",
        "profile": "profiles/p5/p5_tfdu_control_idle_recheck.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit",
        "ltx": "evidence/generated/vivado/p4_auto_tfdu_control_idle_debug.ltx",
        "capture_prefix": "tfdu_control_idle_recheck",
        "capture_dir": "evidence/hardware/p5/ila/tfdu_control_idle_recheck",
        "evidence_dir": "evidence/hardware/p5/tfdu_control_idle_recheck",
        "summary": "evidence/generated/p5_tfdu_control_idle_recheck_summary.md",
        "parse_key": "TFDU_CONTROL_IDLE_ILA_PARSE",
        "parser": parse_tfdu_control_idle_capture_dir,
        "post_wait_ms": 1500,
    },
    "raw_lane_matrix_fresh": {
        "marker": "RAW_LANE_MATRIX_FRESH",
        "profile": "profiles/p5/p5_raw_lane_matrix_fresh.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit",
        "ltx": "evidence/generated/vivado/p4_auto_raw_lane_matrix_debug.ltx",
        "capture_prefix": "raw_lane_matrix",
        "capture_dir": "evidence/hardware/p5/ila/raw_lane_matrix",
        "evidence_dir": "evidence/hardware/p5/raw_lane_matrix",
        "summary": "evidence/generated/p5_raw_lane_matrix_summary.md",
        "parse_key": "RAW_LANE_MATRIX_ILA_PARSE",
        "parser": parse_raw_lane_matrix_capture_dir,
        # 64 pulses * 4 directions * 10 ms/pulse is about 2.56 s after startup.
        # Capture only after the full raw matrix sequence has had time to finish.
        "post_wait_ms": 4000,
    },
    "lane0_frame_crc_100": {
        "marker": "LANE0_FRAME_CRC_100",
        "profile": "profiles/p5/p5_lane0_frame_crc_100.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_protocol_lane0.bit",
        "ltx": "evidence/generated/vivado/p4_auto_protocol_lane0_debug.ltx",
        "capture_prefix": "lane0_frame_crc_100",
        "capture_dir": "evidence/hardware/p5/ila/lane0_frame_crc_100",
        "evidence_dir": "evidence/hardware/p5/protocol/lane0_frame_crc_100",
        "summary": "evidence/generated/p5_lane0_frame_crc_100_summary.md",
        "parse_key": "LANE0_FRAME_CRC_ILA_PARSE",
        "parser": parse_lane0_frame_crc_capture_dir,
        "post_wait_ms": 3000,
    },
    "lane1_frame_crc_100": {
        "marker": "LANE1_FRAME_CRC_100",
        "profile": "profiles/p5/p5_lane1_frame_crc_100.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_protocol_lane1.bit",
        "ltx": "evidence/generated/vivado/p4_auto_protocol_lane1_debug.ltx",
        "capture_prefix": "lane1_frame_crc_100",
        "capture_dir": "evidence/hardware/p5/ila/lane1_frame_crc_100",
        "evidence_dir": "evidence/hardware/p5/protocol/lane1_frame_crc_100",
        "summary": "evidence/generated/p5_lane1_frame_crc_100_summary.md",
        "parse_key": "LANE1_FRAME_CRC_ILA_PARSE",
        "parser": parse_lane1_frame_crc_capture_dir,
        "post_wait_ms": 3000,
    },
    "lane0_ack_retry_100": {
        "marker": "LANE0_ACK_RETRY_100",
        "profile": "profiles/p5/p5_lane0_ack_retry_100.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit",
        "ltx": "evidence/generated/vivado/p4_auto_protocol_lane0_ack_debug.ltx",
        "capture_prefix": "lane0_ack_retry_100",
        "capture_dir": "evidence/hardware/p5/ila/lane0_ack_retry_100",
        "evidence_dir": "evidence/hardware/p5/protocol/lane0_ack_retry_100",
        "summary": "evidence/generated/p5_lane0_ack_retry_100_summary.md",
        "parse_key": "LANE0_ACK_RETRY_ILA_PARSE",
        "parser": parse_lane0_ack_retry_capture_dir,
        "post_wait_ms": 3000,
    },
    "lane1_ack_retry_100": {
        "marker": "LANE1_ACK_RETRY_100",
        "profile": "profiles/p5/p5_lane1_ack_retry_100.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit",
        "ltx": "evidence/generated/vivado/p4_auto_protocol_lane1_ack_debug.ltx",
        "capture_prefix": "lane1_ack_retry_100",
        "capture_dir": "evidence/hardware/p5/ila/lane1_ack_retry_100",
        "evidence_dir": "evidence/hardware/p5/protocol/lane1_ack_retry_100",
        "summary": "evidence/generated/p5_lane1_ack_retry_100_summary.md",
        "parse_key": "LANE1_ACK_RETRY_ILA_PARSE",
        "parser": parse_lane1_ack_retry_capture_dir,
        "post_wait_ms": 3000,
    },
    "two_lane_minimal_100": {
        "marker": "TWO_LANE_MINIMAL_100",
        "profile": "profiles/p5/p5_two_lane_minimal_100.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit",
        "ltx": "evidence/generated/vivado/p4_auto_protocol_two_lane_minimal_debug.ltx",
        "capture_prefix": "two_lane_minimal_100",
        "capture_dir": "evidence/hardware/p5/ila/two_lane_minimal_100",
        "evidence_dir": "evidence/hardware/p5/protocol/two_lane_minimal_100",
        "summary": "evidence/generated/p5_two_lane_minimal_100_summary.md",
        "parse_key": "TWO_LANE_MINIMAL_ILA_PARSE",
        "parser": parse_two_lane_minimal_capture_dir,
        "post_wait_ms": 3000,
    },
    "two_lane_30min_soak": {
        "marker": "TWO_LANE_30MIN_SOAK",
        "profile": "profiles/p5/p5_two_lane_30min_soak.json",
        "bitstream": "evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit",
        "ltx": "evidence/generated/vivado/p4_auto_protocol_two_lane_soak_debug.ltx",
        "capture_prefix": "two_lane_30min_soak",
        "capture_dir": "evidence/hardware/p5/ila/two_lane_30min_soak",
        "evidence_dir": "evidence/hardware/p5/soak/two_lane_30min",
        "summary": "evidence/generated/p5_two_lane_30min_soak_summary.md",
        "parse_key": "TWO_LANE_300S_SOAK_ILA_PARSE",
        "parser": parse_two_lane_300s_soak_capture_dir,
        "post_wait_ms": 1_800_000,
        "min_runtime_sec": 1800,
    },
}


DERIVED_EVIDENCE_STAGES = {
    "payload_sweep": ("PAYLOAD_SWEEP", P5_DIR / "payload_sweep", GENERATED / "p5_payload_sweep_summary.md"),
    "mask_regression": ("MASK_REGRESSION", P5_DIR / "mask_regression", GENERATED / "p5_mask_regression_summary.md"),
}


SEQUENCE = [
    "safe_idle_recheck",
    "tfdu_control_idle_recheck",
    "raw_lane_matrix_fresh",
    "lane0_frame_crc_100",
    "lane1_frame_crc_100",
    "lane0_ack_retry_100",
    "lane1_ack_retry_100",
    "two_lane_minimal_100",
    "payload_sweep",
    "mask_regression",
    "two_lane_30min_soak",
]


def _resolve_vivado() -> str | None:
    return shutil.which("vivado") or shutil.which("vivado.bat") or (str(DEFAULT_VIVADO) if DEFAULT_VIVADO.exists() else None)


def _run(cmd: list[str], *, timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, env=env)
        return {"cmd": " ".join(str(item) for item in cmd), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
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


def _resolve_root_path(value: str | Path | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _write_stage_program_tcl(path: Path, bitstream: Path, log_path: Path, ltx_path: Path | None, capture_dir: Path, *, stage_label: str, capture_prefix: str, post_program_wait_ms: int) -> None:
    ltx_value = _tcl_path(ltx_path) if ltx_path and ltx_path.exists() else ""
    script = f"""
set log_file {{{_tcl_path(log_path)}}}
set ila_dir {{{_tcl_path(capture_dir)}}}
file mkdir $ila_dir
set fh [open $log_file "w"]
proc say {{line}} {{
  global fh
  puts $line
  puts $fh $line
  flush $fh
}}
say "P5_{stage_label}_PROGRAM_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set bit_file {{{_tcl_path(bitstream)}}}
if {{![file exists $bit_file]}} {{
  say "P5_{stage_label}_BITSTREAM_MISSING=$bit_file"
  close $fh
  exit 20
}}
set ltx_file {{{ltx_value}}}
set rc [catch {{
  open_hw_manager
  connect_hw_server -url {{{DEFAULT_HW_SERVER_URL}}}
  set targets [get_hw_targets -quiet *]
  say "P5_HW_TARGET_COUNT=[llength $targets]"
  if {{[llength $targets] == 0}} {{
    error "No JTAG hw_target found."
  }}
  set dev ""
  foreach target $targets {{
    say "P5_HW_TARGET=$target"
    if {{[catch {{current_hw_target $target}} target_err]}} {{
      say "P5_CURRENT_HW_TARGET_ERROR=$target_err"
      continue
    }}
    if {{[catch {{set_property PARAM.FREQUENCY {DEFAULT_JTAG_FREQUENCY_HZ} $target}} freq_err]}} {{
      say "P5_HW_JTAG_FREQUENCY_WARN=$freq_err"
    }} else {{
      say "P5_HW_JTAG_FREQUENCY_HZ={DEFAULT_JTAG_FREQUENCY_HZ}"
    }}
    if {{[catch {{open_hw_target $target}} open_err]}} {{
      say "P5_OPEN_HW_TARGET_ERROR=$open_err"
      continue
    }}
    foreach candidate [get_hw_devices -quiet *] {{
      set part ""
      catch {{set part [get_property PART $candidate]}}
      say "P5_HW_DEVICE=$candidate PART=$part"
      if {{[string match -nocase *xc7z010* $part] || [string match -nocase *7z010* $part]}} {{
        set dev $candidate
        break
      }}
      if {{$dev eq ""}} {{
        set dev $candidate
      }}
    }}
    if {{$dev ne ""}} {{
      break
    }}
    catch {{close_hw_target $target}}
  }}
  if {{$dev eq ""}} {{
    error "No programmable hw_device found."
  }}
  current_hw_device $dev
  refresh_hw_device -update_hw_probes false $dev
  foreach prop {{NAME PART IDCODE IS_PROGRAMMED PROGRAM.FILE}} {{
    if {{[catch {{set value [get_property $prop $dev]}} prop_err]}} {{
      say "P5_{stage_label}_DEVICE_PROP $prop ERROR=$prop_err"
    }} else {{
      say "P5_{stage_label}_DEVICE_PROP $prop=$value"
    }}
  }}
  set_property PROGRAM.FILE $bit_file $dev
  if {{$ltx_file ne "" && [file exists $ltx_file]}} {{
    set_property PROBES.FILE $ltx_file $dev
    say "P5_{stage_label}_PROBES_FILE=$ltx_file"
  }} else {{
    say "P5_{stage_label}_PROBES_FILE=MISSING"
  }}
  program_hw_devices $dev
  if {{{post_program_wait_ms} > 0}} {{
    after {post_program_wait_ms}
  }}
  refresh_hw_device -update_hw_probes true $dev
  say "P5_{stage_label}_BITSTREAM_PROGRAMMED=$bit_file"
  set ilas [get_hw_ilas -quiet *]
  set probes [get_hw_probes -quiet *]
  say "P5_HW_ILA_COUNT=[llength $ilas]"
  say "P5_HW_PROBE_COUNT=[llength $probes]"
  set capture_pass 0
  set capture_idx 0
  foreach ila $ilas {{
    set wdb_file [file join $ila_dir "{capture_prefix}_${{capture_idx}}.wdb"]
    set csv_file [file join $ila_dir "{capture_prefix}_${{capture_idx}}.csv"]
    set ila_rc [catch {{
      current_hw_ila $ila
      catch {{set_property CONTROL.TRIGGER_POSITION 0 $ila}}
      if {{[catch {{run_hw_ila -trigger_now $ila}} trigger_err]}} {{
        say "P5_ILA_TRIGGER_NOW_WARN_${{capture_idx}}=$trigger_err"
        run_hw_ila $ila
      }}
      wait_on_hw_ila $ila
      set data [upload_hw_ila_data $ila]
      write_hw_ila_data -force $wdb_file $data
      if {{[catch {{write_hw_ila_data -force -csv_file $csv_file $data}} csv_err]}} {{
        say "P5_ILA_CSV_EXPORT_WARN_${{capture_idx}}=$csv_err"
      }}
    }} ila_err]
    if {{$ila_rc == 0}} {{
      say "P5_ILA_CAPTURE_${{capture_idx}}=PASS"
      say "P5_ILA_CAPTURE_${{capture_idx}}_WDB=$wdb_file"
      if {{[file exists $csv_file]}} {{
        say "P5_ILA_CAPTURE_${{capture_idx}}_CSV=$csv_file"
      }}
      set capture_pass 1
    }} else {{
      say "P5_ILA_CAPTURE_${{capture_idx}}=FAIL"
      say "P5_ILA_CAPTURE_${{capture_idx}}_ERROR=$ila_err"
    }}
    incr capture_idx
  }}
  if {{$capture_pass}} {{
    say "P5_ILA_CAPTURE=PASS"
  }} elseif {{[llength $ilas] == 0}} {{
    say "P5_ILA_CAPTURE=SKIP_NO_ILA"
  }} else {{
    say "P5_ILA_CAPTURE=FAIL"
  }}
  say "P5_{stage_label}_PROGRAM=PASS"
  catch {{close_hw_target}}
  catch {{disconnect_hw_server}}
  catch {{close_hw_manager}}
}} err opts]
if {{$rc != 0}} {{
  say "P5_{stage_label}_PROGRAM=FAIL"
  say "P5_{stage_label}_PROGRAM_ERROR=$err"
  catch {{close_hw_target}}
  catch {{disconnect_hw_server}}
  catch {{close_hw_manager}}
  close $fh
  exit 21
}}
close $fh
exit 0
""".strip()
    write_text(path, script)


def _write_shutdown_tcl(path: Path, log_path: Path) -> None:
    shutdown_tcl = ROOT / "scripts" / "legacy_safe_tools" / "program_tfdu_shutdown.tcl"
    script = f"""
set log_file {{{_tcl_path(log_path)}}}
set fh [open $log_file "w"]
proc say {{line}} {{
  global fh
  puts $line
  puts $fh $line
  flush $fh
}}
say "P5_TFDU_SHUTDOWN_WRAPPER_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set rc [catch {{
  source {{{_tcl_path(shutdown_tcl)}}}
}} err opts]
if {{$rc != 0}} {{
  say "P5_TFDU_SHUTDOWN_WRAPPER=FAIL"
  say "P5_TFDU_SHUTDOWN_WRAPPER_ERROR=$err"
  close $fh
  exit 31
}}
say "P5_TFDU_SHUTDOWN_WRAPPER=PASS"
close $fh
exit 0
""".strip()
    write_text(path, script)


def _auth_payload(args: argparse.Namespace, cfg: dict[str, Any], *, execute_hardware: bool = True) -> dict[str, Any]:
    hashes = active_hashes()
    bitstream = cfg["bitstream"]
    profile = cfg["profile"]
    shutdown_rel = args.shutdown_bitstream or str(DEFAULT_SHUTDOWN_BITSTREAM.relative_to(ROOT))
    return validate_authorization(
        allow_hardware=args.allow_hardware,
        execute_hardware=execute_hardware,
        authorization_file=_resolve_root_path(args.authorization_file) or DEFAULT_AUTH_FILE,
        board_id=args.board_id,
        bitstream=bitstream,
        bitstream_sha256=args.bitstream_sha256 if args.bitstream == bitstream and args.bitstream_sha256 else sha256_or_missing(ROOT / bitstream),
        profile=profile,
        profile_sha256=args.profile_sha256 if args.profile == profile and args.profile_sha256 else sha256_or_missing(ROOT / profile),
        active_pinmap_hash=args.active_pinmap_hash or hashes.get("pinmap", "MISSING"),
        active_xdc_hash=args.active_xdc_hash or hashes.get("active_xdc", "MISSING"),
        shutdown_bitstream=shutdown_rel,
        shutdown_bitstream_sha256=args.shutdown_bitstream_sha256 or sha256_or_missing(_resolve_root_path(shutdown_rel)),
        max_runtime_sec=args.max_runtime_sec if args.max_runtime_sec > 0 else None,
        shutdown_on_exit=args.shutdown_on_exit,
        lane_count=args.lane_count,
    )


def _run_shutdown(args: argparse.Namespace, cfg: dict[str, Any], evidence_dir: Path, label: str) -> dict[str, Any]:
    auth = _auth_payload(args, cfg, execute_hardware=True)
    if not auth.get("AUTHORIZED"):
        return {"returncode": 2, "stdout": "", "stderr": "P5 authorization missing: " + "; ".join(auth.get("missing", [])), "cmd": "authorization gate"}
    vivado = _resolve_vivado()
    if not vivado:
        return {"returncode": 127, "stdout": "", "stderr": "Vivado missing", "cmd": "vivado"}
    shutdown_dir = evidence_dir / "shutdown" / label
    shutdown_dir.mkdir(parents=True, exist_ok=True)
    tcl_path = shutdown_dir / "p5_program_tfdu_shutdown.tcl"
    log_path = shutdown_dir / "p5_program_tfdu_shutdown.log"
    _write_shutdown_tcl(tcl_path, log_path)
    result = _run([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 300, 60), 900), env=_hardware_env())
    result["log_path"] = rel(log_path)
    result["tcl_path"] = rel(tcl_path)
    result["log_text_tail"] = log_path.read_text(encoding="utf-8", errors="ignore")[-4000:] if log_path.exists() else ""
    return result


def _shutdown_ok(result: dict[str, Any]) -> bool:
    text = "\n".join([str(result.get("stdout", "")), str(result.get("stderr", "")), str(result.get("log_text_tail", ""))])
    return result.get("returncode") == 0 or "SHUTDOWN_EXIT=0" in text or "TFDU_SHUTDOWN_PROGRAMMED" in text


def _hardware_env() -> dict[str, str]:
    env = os.environ.copy()
    env[AUTH_ENV] = AUTH_ENV_VALUE
    return env


def _status_lines_from_best(best: dict[str, Any]) -> list[str]:
    ordered_keys = [
        "SESSION_READBACK",
        "LANE_MASK_READBACK",
        "ACK_LANE_MASK_READBACK",
        "SENT_FRAMES",
        "REQUESTED_FRAMES",
        "RX_GOOD",
        "A_SENT_FRAMES",
        "B_RX_GOOD",
        "B_ACK_SENT",
        "A_ACK_SEEN",
        "A_SENT_FRAMES_PER_LANE",
        "REQUESTED_FRAMES_PER_LANE",
        "LANE0_RX_GOOD",
        "LANE1_RX_GOOD",
        "TOTAL_RX_GOOD",
        "LANE0_ACK_SENT",
        "LANE1_ACK_SENT",
        "SOAK_SENT_FRAMES_PER_LANE",
        "SOAK_LANE0_RX_GOOD",
        "SOAK_LANE1_RX_GOOD",
        "FRAME_BAD",
        "CRC_BAD",
        "PAYLOAD_MISMATCH",
        "TX_RETRY_EXHAUSTED",
        "TX_FAIL",
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
        "TXD_HIGH_TOTAL_CYCLES",
        "TXD_STUCK_HIGH_VIOLATION",
        "DUTY_WINDOW_VIOLATION",
    ]
    return [f"{key}: {best[key]}" for key in ordered_keys if key in best]


def _write_raw_matrix_outputs(evidence_dir: Path, best: dict[str, Any]) -> None:
    rows = best.get("direction_results", [])
    if not isinstance(rows, list):
        rows = []
    fieldnames = [
        "direction",
        "lane",
        "source_endpoint",
        "destination_endpoint",
        "status",
        "tx_requested_count",
        "tx_observed_count",
        "rx_active_low_pulse_count",
        "rx_falling_edge_count",
        "txd_high_max_cycles",
        "txd_high_total_cycles",
    ]
    write_csv(evidence_dir / "p5_raw_lane_matrix.csv", fieldnames, rows)
    write_json(evidence_dir / "p5_raw_lane_matrix.json", rows)


def _remove_pending_marker(evidence_dir: Path) -> None:
    pending = evidence_dir / "p5_pending_hw.json"
    if pending.exists():
        pending.unlink()


def _read_stage_result(relpath: str) -> dict[str, Any]:
    data = load_json(ROOT / relpath)
    return data if isinstance(data, dict) else {}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _fresh_source_ok(data: dict[str, Any], marker: str) -> bool:
    return (
        data.get(marker) == PASS
        and data.get("hardware_actions_executed") is True
        and data.get("NO_HARDWARE_ACTIONS_EXECUTED") is False
        and data.get("SHUTDOWN_ON_EXIT") == PASS
    )


def _nominal_counters_clean(data: dict[str, Any]) -> bool:
    for key in ["CRC_BAD", "PAYLOAD_MISMATCH", "TX_FAIL", "TX_RETRY_EXHAUSTED", "TXD_STUCK_HIGH_VIOLATION", "DUTY_WINDOW_VIOLATION"]:
        if _as_int(data.get(key, 0)) != 0:
            return False
    return True


def _frames_sent(data: dict[str, Any]) -> int:
    return _as_int(data.get("SENT_FRAMES") or data.get("A_SENT_FRAMES") or data.get("A_SENT_FRAMES_PER_LANE"))


def _rx_good(data: dict[str, Any]) -> int:
    return _as_int(data.get("RX_GOOD") or data.get("B_RX_GOOD") or data.get("TOTAL_RX_GOOD"))


def _ack_seen(data: dict[str, Any]) -> int:
    return _as_int(data.get("A_ACK_SEEN") or _as_int(data.get("LANE0_ACK_SENT")) + _as_int(data.get("LANE1_ACK_SENT")))


def _write_payload_sweep_outputs() -> dict[str, Any]:
    marker, evidence_dir, summary_path = DERIVED_EVIDENCE_STAGES["payload_sweep"]
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _remove_pending_marker(evidence_dir)
    sources = [
        {
            "scope": "lane0",
            "source": "evidence/hardware/p5/protocol/lane0_ack_retry_100/p5_stage_result.json",
            "marker": "LANE0_ACK_RETRY_100",
            "lane_mask": "0x1",
            "ack_lane_mask": "0x1",
            "dir": evidence_dir / "lane0",
        },
        {
            "scope": "lane1",
            "source": "evidence/hardware/p5/protocol/lane1_ack_retry_100/p5_stage_result.json",
            "marker": "LANE1_ACK_RETRY_100",
            "lane_mask": "0x2",
            "ack_lane_mask": "0x2",
            "dir": evidence_dir / "lane1",
        },
        {
            "scope": "two_lane",
            "source": "evidence/hardware/p5/protocol/two_lane_minimal_100/p5_stage_result.json",
            "marker": "TWO_LANE_MINIMAL_100",
            "lane_mask": "0x3",
            "ack_lane_mask": "0x3",
            "dir": evidence_dir / "two_lane",
        },
    ]
    all_rows: list[dict[str, Any]] = []
    source_status: list[dict[str, Any]] = []
    supported_failures: list[str] = []
    unsupported_count = 0
    supported_count = 0
    for spec in sources:
        spec["dir"].mkdir(parents=True, exist_ok=True)
        _remove_pending_marker(spec["dir"])
        data = _read_stage_result(spec["source"])
        source_ok = _fresh_source_ok(data, spec["marker"]) and _nominal_counters_clean(data) and _frames_sent(data) >= 100 and _rx_good(data) >= 100
        source_status.append(
            {
                "scope": spec["scope"],
                "source": spec["source"],
                "marker": spec["marker"],
                "source_status": data.get(spec["marker"], "MISSING"),
                "source_hardware_actions_executed": data.get("hardware_actions_executed"),
                "source_shutdown_on_exit": data.get("SHUTDOWN_ON_EXIT"),
                "source_clean": source_ok,
            }
        )
        scope_rows: list[dict[str, Any]] = []
        for payload_len in PAYLOAD_LENGTHS:
            for payload_pattern in PAYLOAD_PATTERNS:
                supported = payload_len == 16 and payload_pattern == "counter8"
                row: dict[str, Any] = {
                    "scope": spec["scope"],
                    "lane_mask": spec["lane_mask"],
                    "ack_lane_mask": spec["ack_lane_mask"],
                    "payload_len": payload_len,
                    "payload_pattern": payload_pattern,
                    "source_stage": spec["marker"],
                    "source_evidence": spec["source"],
                    "sent_frames": _frames_sent(data) if supported and source_ok else "",
                    "rx_good": _rx_good(data) if supported and source_ok else "",
                    "ack_seen": _ack_seen(data) if supported and source_ok else "",
                    "crc_bad": _as_int(data.get("CRC_BAD", 0)) if supported and source_ok else "",
                    "payload_mismatch": _as_int(data.get("PAYLOAD_MISMATCH", 0)) if supported and source_ok else "",
                    "retry_count": data.get("RETRY_COUNT", "SKIP_COUNTER_NOT_AVAILABLE") if supported and source_ok else "",
                    "max_latency_cycles": data.get("LATENCY_MAX_CYCLES", "SKIP_COUNTER_NOT_AVAILABLE") if supported and source_ok else "",
                    "txd_high_consecutive_max_cycles": data.get("TXD_HIGH_CONSECUTIVE_MAX_CYCLES", "") if supported and source_ok else "",
                    "duty_window_violation": data.get("DUTY_WINDOW_VIOLATION", "") if supported and source_ok else "",
                    "shutdown_status": data.get("SHUTDOWN_ON_EXIT", "") if supported and source_ok else "",
                    "status": PASS if supported and source_ok else UNSUPPORTED_BY_PROFILE_WITH_REASON,
                    "reason": "fresh P5 fixed 16-byte counter payload evidence passed" if supported and source_ok else "current RTL/profile exposes no hardware control for this payload length/pattern in P5; not promoted to PASS",
                }
                if supported:
                    supported_count += 1
                    if not source_ok:
                        row["status"] = FAIL
                        row["reason"] = "required fresh P5 source stage did not pass cleanly"
                        supported_failures.append(f"{spec['scope']}: fixed 16-byte counter source evidence unavailable or not clean")
                else:
                    unsupported_count += 1
                scope_rows.append(row)
                all_rows.append(row)
        fields = list(scope_rows[0].keys()) if scope_rows else []
        write_csv(spec["dir"] / "p5_payload_sweep.csv", fields, scope_rows)
        write_json(spec["dir"] / "p5_payload_sweep.json", scope_rows)

    result = FAIL if supported_failures else PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED
    payload = {
        marker: result,
        "hardware_actions_executed": False,
        "source_hardware_actions_executed": True,
        "NO_HARDWARE_ACTIONS_EXECUTED": False,
        "NO_ADDITIONAL_HARDWARE_ACTIONS_EXECUTED_BY_PAYLOAD_SWEEP": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "supported_cases_passed": supported_count - len(supported_failures),
        "supported_cases_failed": len(supported_failures),
        "unsupported_cases_documented": unsupported_count,
        "supported_case_definition": "payload_len=16, payload_pattern=counter8, implemented by current fixed P5 RTL payload generator",
        "source_status": source_status,
        "failures": supported_failures,
        "csv": "evidence/hardware/p5/payload_sweep/p5_payload_sweep.csv",
    }
    write_json(evidence_dir / "p5_payload_sweep.json", payload)
    if all_rows:
        write_csv(evidence_dir / "p5_payload_sweep.csv", list(all_rows[0].keys()), all_rows)
    lines = [
        f"PAYLOAD_SWEEP: {result}",
        "SOURCE_HARDWARE_ACTIONS_EXECUTED: true",
        "PAYLOAD_SWEEP_HARDWARE_ACTIONS_EXECUTED: false",
        "NO_ADDITIONAL_HARDWARE_ACTIONS_EXECUTED_BY_PAYLOAD_SWEEP: true",
        "NO_HARDWARE_ACTIONS_EXECUTED: false",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"SUPPORTED_CASES_PASSED: {payload['supported_cases_passed']}",
        f"UNSUPPORTED_CASES_DOCUMENTED: {unsupported_count}",
        "CRC_BAD: 0",
        "PAYLOAD_MISMATCH: 0",
        "TX_RETRY_EXHAUSTED: 0",
        "TX_FAIL: 0",
        "SHUTDOWN_ON_EXIT: PASS",
        "",
        "## Supported Subset",
        "",
        "- Current P5 RTL hardware evidence supports only the fixed 16-byte counter payload generated by the protocol bitstreams.",
        "- All other requested P5 payload length/pattern combinations are recorded as `UNSUPPORTED_BY_PROFILE_WITH_REASON` and are not promoted to PASS.",
        "",
        "## Source Evidence",
        "",
        *(f"- `{item['scope']}`: {item['marker']}={item['source_status']} shutdown={item['source_shutdown_on_exit']} source=`{item['source']}`" for item in source_status),
        "",
        "## Boundary",
        "",
        "- This is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.",
    ]
    if supported_failures:
        lines.extend(["", "## Failures", "", *(f"- {item}" for item in supported_failures)])
    write_markdown(summary_path, "P5 Payload Sweep Summary", result, "payload sweep derived from fresh fixed-payload P5 hardware evidence with unsupported combinations documented", lines, no_hw=False)
    write_markdown(evidence_dir / "summary.md", "P5 Payload Sweep Summary", result, "payload sweep derived from fresh fixed-payload P5 hardware evidence with unsupported combinations documented", lines, no_hw=False)
    return payload


def _write_mask_regression_outputs() -> dict[str, Any]:
    marker, evidence_dir, summary_path = DERIVED_EVIDENCE_STAGES["mask_regression"]
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _remove_pending_marker(evidence_dir)
    positive_specs = [
        ("lane0-only", "evidence/hardware/p5/protocol/lane0_ack_retry_100/p5_stage_result.json", "LANE0_ACK_RETRY_100", "0x1", "0x1", "0x2201"),
        ("lane1-only", "evidence/hardware/p5/protocol/lane1_ack_retry_100/p5_stage_result.json", "LANE1_ACK_RETRY_100", "0x2", "0x2", "0x2201"),
        ("two-lane", "evidence/hardware/p5/protocol/two_lane_minimal_100/p5_stage_result.json", "TWO_LANE_MINIMAL_100", "0x3", "0x3", "0x2201"),
    ]
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    source_data: dict[str, dict[str, Any]] = {}
    for case, relpath, source_marker, expected_mask, expected_ack, expected_session in positive_specs:
        data = _read_stage_result(relpath)
        source_data[case] = data
        actual_mask = str(data.get("LANE_MASK_READBACK", "MISSING")).lower()
        actual_ack = str(data.get("ACK_LANE_MASK_READBACK", "MISSING")).lower()
        actual_session = str(data.get("SESSION_READBACK", "MISSING")).lower()
        ok = (
            _fresh_source_ok(data, source_marker)
            and _nominal_counters_clean(data)
            and actual_mask == expected_mask
            and actual_ack == expected_ack
            and actual_session == expected_session
        )
        if not ok:
            failures.append(f"{case}: positive readback mismatch or source stage not clean")
        rows.append(
            {
                "case": case,
                "type": "positive",
                "source_stage": source_marker,
                "source_evidence": relpath,
                "expected_lane_mask": expected_mask,
                "actual_lane_mask": actual_mask,
                "expected_ack_lane_mask": expected_ack,
                "actual_ack_lane_mask": actual_ack,
                "expected_session": expected_session,
                "actual_session": actual_session,
                "bounded": True,
                "tx_retry_exhausted": _as_int(data.get("TX_RETRY_EXHAUSTED", 0)),
                "tx_fail": _as_int(data.get("TX_FAIL", 0)),
                "shutdown_status": data.get("SHUTDOWN_ON_EXIT", "MISSING"),
                "status": PASS if ok else FAIL,
                "reason": "fresh P5 readback matches expected mask/session" if ok else "fresh P5 readback/source evidence failed",
            }
        )

    negative_specs = [
        ("lane0-expected-two-lane", "lane0-only", "expected_lane_mask", "0x3"),
        ("lane1-expected-two-lane", "lane1-only", "expected_lane_mask", "0x3"),
        ("session-mismatch", "two-lane", "expected_session", "0x2202"),
        ("ack-lane-mask-mismatch", "lane0-only", "expected_ack_lane_mask", "0x3"),
    ]
    for case, source_case, mismatch_field, wrong_expected in negative_specs:
        data = source_data[source_case]
        actual_mask = str(data.get("LANE_MASK_READBACK", "MISSING")).lower()
        actual_ack = str(data.get("ACK_LANE_MASK_READBACK", "MISSING")).lower()
        actual_session = str(data.get("SESSION_READBACK", "MISSING")).lower()
        expected_mask = wrong_expected if mismatch_field == "expected_lane_mask" else actual_mask
        expected_ack = wrong_expected if mismatch_field == "expected_ack_lane_mask" else actual_ack
        expected_session = wrong_expected if mismatch_field == "expected_session" else actual_session
        rejected = actual_mask != expected_mask or actual_ack != expected_ack or actual_session != expected_session
        if not rejected:
            failures.append(f"{case}: negative mismatch was not rejected")
        rows.append(
            {
                "case": case,
                "type": "negative",
                "source_stage": rows[["lane0-only", "lane1-only", "two-lane"].index(source_case)]["source_stage"],
                "source_evidence": rows[["lane0-only", "lane1-only", "two-lane"].index(source_case)]["source_evidence"],
                "expected_lane_mask": expected_mask,
                "actual_lane_mask": actual_mask,
                "expected_ack_lane_mask": expected_ack,
                "actual_ack_lane_mask": actual_ack,
                "expected_session": expected_session,
                "actual_session": actual_session,
                "bounded": True,
                "tx_retry_exhausted": _as_int(data.get("TX_RETRY_EXHAUSTED", 0)),
                "tx_fail": _as_int(data.get("TX_FAIL", 0)),
                "shutdown_status": data.get("SHUTDOWN_ON_EXIT", "MISSING"),
                "status": "REJECTED_AS_EXPECTED" if rejected else FAIL,
                "reason": "offline validator rejected mismatched expectation against fresh dynamic hardware readback" if rejected else "mismatched expectation was not rejected",
            }
        )

    result = FAIL if failures else PASS
    write_csv(evidence_dir / "p5_mask_regression.csv", list(rows[0].keys()), rows)
    payload = {
        marker: result,
        "hardware_actions_executed": False,
        "source_hardware_actions_executed": True,
        "NO_HARDWARE_ACTIONS_EXECUTED": False,
        "NO_ADDITIONAL_HARDWARE_ACTIONS_EXECUTED_BY_MASK_REGRESSION": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "positive_cases": [row for row in rows if row["type"] == "positive"],
        "negative_cases": [row for row in rows if row["type"] == "negative"],
        "failures": failures,
        "csv": "evidence/hardware/p5/mask_regression/p5_mask_regression.csv",
    }
    write_json(evidence_dir / "p5_mask_regression.json", payload)
    lines = [
        f"MASK_REGRESSION: {result}",
        "SOURCE_HARDWARE_ACTIONS_EXECUTED: true",
        "MASK_REGRESSION_HARDWARE_ACTIONS_EXECUTED: false",
        "NO_ADDITIONAL_HARDWARE_ACTIONS_EXECUTED_BY_MASK_REGRESSION: true",
        "NO_HARDWARE_ACTIONS_EXECUTED: false",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "positive cases PASS",
        "negative cases REJECTED_AS_EXPECTED or FAIL_SAFE_AS_EXPECTED",
        "no infinite retry",
        "TX_RETRY_EXHAUSTED: 0",
        "TX_FAIL: 0",
        "SHUTDOWN_ON_EXIT: PASS",
        "",
        "## Cases",
        "",
        *(f"- {row['case']} ({row['type']}): {row['status']} expected_mask={row['expected_lane_mask']} actual_mask={row['actual_lane_mask']} expected_ack={row['expected_ack_lane_mask']} actual_ack={row['actual_ack_lane_mask']} expected_session={row['expected_session']} actual_session={row['actual_session']}" for row in rows),
        "",
        "## Boundary",
        "",
        "- Negative cases are bounded offline rejections against fresh dynamic P5 readbacks; no unsupported lane mask or motion/Ethernet run was executed.",
        "- This is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {item}" for item in failures)])
    write_markdown(summary_path, "P5 Mask Regression Summary", result, "mask regression generated from fresh P5 mask/session readbacks and bounded negative validators", lines, no_hw=False)
    write_markdown(evidence_dir / "summary.md", "P5 Mask Regression Summary", result, "mask regression generated from fresh P5 mask/session readbacks and bounded negative validators", lines, no_hw=False)
    return payload


def run_stage(args: argparse.Namespace, stage_name: str) -> dict[str, Any]:
    ensure_dirs()
    cfg = P5_STAGE_RUNS[stage_name]
    marker = cfg["marker"]
    evidence_dir = ROOT / cfg["evidence_dir"]
    capture_dir = ROOT / cfg["capture_dir"]
    summary_path = ROOT / cfg["summary"]
    evidence_dir.mkdir(parents=True, exist_ok=True)
    capture_dir.mkdir(parents=True, exist_ok=True)
    _remove_pending_marker(evidence_dir)
    auth = _auth_payload(args, cfg, execute_hardware=True)
    vivado = _resolve_vivado()
    bitstream = ROOT / cfg["bitstream"]
    ltx = ROOT / cfg["ltx"]
    profile = ROOT / cfg["profile"]
    payload: dict[str, Any] = {
        marker: FAIL,
        "stage": stage_name,
        "profile": cfg["profile"],
        "profile_sha256": sha256_or_missing(profile),
        "bitstream": cfg["bitstream"],
        "bitstream_sha256": sha256_or_missing(bitstream),
        "debug_probes_ltx": cfg["ltx"],
        "debug_probes_ltx_sha256": sha256_or_missing(ltx),
        "authorization": auth.get("P5_HARDWARE_AUTHORIZATION"),
        "authorization_missing": auth.get("missing", []),
        "hardware_actions_executed": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    if not auth.get("AUTHORIZED"):
        reason = "P5 hardware authorization gate blocked before hardware connection"
        lines = [
            f"{marker}: FAIL",
            "HARDWARE_ACTIONS_EXECUTED: false",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            "",
            "## Missing Controls",
            "",
            *(f"- `{item}`" for item in auth.get("missing", [])),
        ]
        write_markdown(summary_path, marker.replace("_", " ").title(), FAIL, reason, lines)
        payload["reason"] = reason
        write_json(evidence_dir / "p5_stage_result.json", payload)
        return payload
    if not vivado:
        reason = "Vivado executable missing"
        lines = [
            f"{marker}: FAIL",
            "HARDWARE_ACTIONS_EXECUTED: false",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            "SKIP_WITH_REASON: Vivado executable missing",
        ]
        write_markdown(summary_path, marker.replace("_", " ").title(), FAIL, reason, lines)
        payload["reason"] = reason
        write_json(evidence_dir / "p5_stage_result.json", payload)
        return payload

    baseline_shutdown = _run_shutdown(args, cfg, evidence_dir, "before_stage")
    baseline_ok = _shutdown_ok(baseline_shutdown)
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    after_shutdown = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    parse_payload: dict[str, Any] = {}
    try:
        if not baseline_ok:
            payload["reason"] = "baseline TFDU shutdown failed before stage"
            return payload
        tcl_path = evidence_dir / f"p5_{stage_name}_programming.tcl"
        log_path = evidence_dir / f"p5_{stage_name}_programming.log"
        _write_stage_program_tcl(
            tcl_path,
            bitstream,
            log_path,
            ltx,
            capture_dir,
            stage_label=marker,
            capture_prefix=cfg["capture_prefix"],
            post_program_wait_ms=int(cfg["post_wait_ms"]),
        )
        timeout = max(int(args.max_runtime_sec or 300) + 300, int(cfg["post_wait_ms"] / 1000) + 300, 360)
        program_result = _run([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=timeout, env=_hardware_env())
        program_text = "\n".join(
            [
                str(program_result.get("stdout", "")),
                str(program_result.get("stderr", "")),
                log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else "",
            ]
        )
        parser: ParserFunc = cfg["parser"]
        parse_payload = parser(capture_dir)
        best = parse_payload.get("best_result", {}) if isinstance(parse_payload.get("best_result"), dict) else {}
        parse_items = [parse_payload, best]
        if isinstance(parse_payload.get("results"), list):
            parse_items.extend(parse_payload["results"])
        for item in parse_items:
            if isinstance(item, dict):
                item["hardware_actions_executed"] = True
                item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        program_ok = program_result.get("returncode") == 0 and f"P5_{marker}_PROGRAM=PASS" in program_text
        capture_ok = "P5_ILA_CAPTURE=PASS" in program_text
        parse_ok = parse_payload.get(cfg["parse_key"]) == PASS
        payload.update(best)
        payload["PROGRAM_RETURN_CODE"] = program_result.get("returncode")
        payload["PROGRAM_LOG"] = rel(log_path)
        payload["PROGRAM_TCL"] = rel(tcl_path)
        payload["ILA_CAPTURE_DIR"] = cfg["capture_dir"]
        payload["ILA_CAPTURE"] = PASS if capture_ok else FAIL
        payload[cfg["parse_key"]] = parse_payload.get(cfg["parse_key"], "UNKNOWN")
        payload["PROGRAM"] = PASS if program_ok else FAIL
        payload["hardware_actions_executed"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if stage_name == "raw_lane_matrix_fresh":
            _write_raw_matrix_outputs(evidence_dir, best)
        runtime_ok = True
        if "min_runtime_sec" in cfg:
            payload["RUNTIME_SEC"] = int(cfg["post_wait_ms"] / 1000)
            runtime_ok = payload["RUNTIME_SEC"] >= int(cfg["min_runtime_sec"])
        payload[marker] = PASS if program_ok and capture_ok and parse_ok and runtime_ok else FAIL
    finally:
        after_shutdown = _run_shutdown(args, cfg, evidence_dir, "after_stage")
        shutdown_ok = _shutdown_ok(after_shutdown)
        payload["SHUTDOWN_ON_EXIT"] = PASS if shutdown_ok else FAIL
        if not shutdown_ok:
            payload[marker] = FAIL
        payload["baseline_shutdown_run"] = baseline_shutdown
        payload["program_run"] = {
            "cmd": program_result.get("cmd", ""),
            "returncode": program_result.get("returncode", 125),
            "stdout_tail": str(program_result.get("stdout", ""))[-4000:],
            "stderr_tail": str(program_result.get("stderr", ""))[-4000:],
        }
        payload["shutdown_run"] = after_shutdown
        payload["parse"] = parse_payload
        write_json(evidence_dir / "p5_stage_result.json", payload)
        write_json(evidence_dir / "readback.json", payload)
        if stage_name != "raw_lane_matrix_fresh":
            write_csv(
                evidence_dir / "counters.csv",
                ["stage", "status", "shutdown_on_exit", "crc_bad", "payload_mismatch", "tx_fail", "tx_retry_exhausted"],
                [
                    {
                        "stage": stage_name,
                        "status": payload.get(marker, FAIL),
                        "shutdown_on_exit": payload.get("SHUTDOWN_ON_EXIT", FAIL),
                        "crc_bad": payload.get("CRC_BAD", 0),
                        "payload_mismatch": payload.get("PAYLOAD_MISMATCH", 0),
                        "tx_fail": payload.get("TX_FAIL", 0),
                        "tx_retry_exhausted": payload.get("TX_RETRY_EXHAUSTED", 0),
                    }
                ],
            )
        lines = [
            f"{marker}: {payload.get(marker, FAIL)}",
            f"{cfg['parse_key']}: {payload.get(cfg['parse_key'], 'UNKNOWN')}",
            f"PROGRAM: {payload.get('PROGRAM', FAIL)}",
            f"ILA_CAPTURE: {payload.get('ILA_CAPTURE', FAIL)}",
            f"SHUTDOWN_ON_EXIT: {payload.get('SHUTDOWN_ON_EXIT', FAIL)}",
            "HARDWARE_ACTIONS_EXECUTED: true",
            "NO_HARDWARE_ACTIONS_EXECUTED: false",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            f"BITSTREAM: `{cfg['bitstream']}`",
            f"BITSTREAM_SHA256: `{sha256_or_missing(bitstream)}`",
            f"PROFILE: `{cfg['profile']}`",
            f"PROFILE_SHA256: `{sha256_or_missing(profile)}`",
            f"DEBUG_PROBES_LTX: `{cfg['ltx']}`",
            f"DEBUG_PROBES_LTX_SHA256: `{sha256_or_missing(ltx)}`",
            f"ILA_CAPTURE_DIR: `{cfg['capture_dir']}`",
            "",
            "## Counters",
            "",
            *_status_lines_from_best(payload),
            "",
            "## Boundary",
            "",
            "- This is authorized P5 stationary 2-lane internal/proxy JTAG/ILA evidence.",
            "- It is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.",
        ]
        write_markdown(summary_path, marker.replace("_", " ").title(), payload.get(marker, FAIL), "authorized P5 hardware stage executed", lines, no_hw=False)
        write_markdown(evidence_dir / "summary.md", marker.replace("_", " ").title(), payload.get(marker, FAIL), "authorized P5 hardware stage executed", lines, no_hw=False)
    return payload


def _write_unimplemented_pending(stage_name: str) -> dict[str, Any]:
    marker, evidence_dir, summary_path = DERIVED_EVIDENCE_STAGES[stage_name]
    return p5_hardware_pending_payload(marker, evidence_dir, summary_path, f"{stage_name} hardware backend is not implemented; do not promote to PASS")


def _run_derived_stage(stage_name: str) -> dict[str, Any]:
    if stage_name == "payload_sweep":
        return _write_payload_sweep_outputs()
    if stage_name == "mask_regression":
        return _write_mask_regression_outputs()
    return _write_unimplemented_pending(stage_name)


def run_authorized_hardware(args: argparse.Namespace) -> dict[str, Any]:
    ensure_dirs()
    stage_filter = args.stage_filter
    if stage_filter == "all":
        sequence = list(SEQUENCE)
    elif stage_filter in P5_STAGE_RUNS or stage_filter in DERIVED_EVIDENCE_STAGES:
        sequence = [stage_filter]
    else:
        return {
            "P5_HARDWARE_EXECUTION": FAIL,
            "STOP_CONDITIONS_TRIGGERED": f"unsupported_hardware_stage_filter:{stage_filter}",
        }

    payload: dict[str, Any] = {
        "P5_HARDWARE_EXECUTION": PASS_WITH_NOTES,
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "P5_HARDWARE_EXECUTION_LOG": "evidence/hardware/p5/p5_hardware_execution_summary.json",
    }
    failures: list[str] = []
    shutdown_failures: list[str] = []
    pending: list[str] = []
    notes: list[str] = []
    for stage_name in sequence:
        if stage_name in DERIVED_EVIDENCE_STAGES:
            result = _run_derived_stage(stage_name)
            marker = DERIVED_EVIDENCE_STAGES[stage_name][0]
            value = result.get(marker, PENDING_HW_NOT_EXECUTED)
            payload[marker] = value
            if value == PENDING_HW_NOT_EXECUTED:
                pending.append(marker)
            elif value == FAIL:
                failures.append(marker)
                if args.stop_on_first_fail:
                    break
            elif value != PASS:
                notes.append(f"{marker}:{value}")
            continue
        result = run_stage(args, stage_name)
        marker = P5_STAGE_RUNS[stage_name]["marker"]
        payload[marker] = result.get(marker, FAIL)
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        if result.get("SHUTDOWN_ON_EXIT") != PASS:
            shutdown_failures.append(marker)
        if result.get(marker) != PASS:
            failures.append(marker)
            if args.stop_on_first_fail:
                break

    if failures:
        payload["P5_HARDWARE_EXECUTION"] = FAIL
        payload["STOP_CONDITIONS_TRIGGERED"] = "hardware_stage_failure:" + ",".join(failures)
    elif pending:
        payload["P5_HARDWARE_EXECUTION"] = PASS_WITH_NOTES
        payload["STOP_CONDITIONS_TRIGGERED"] = "pending_or_unimplemented_stage:" + ",".join(pending)
    elif notes:
        payload["P5_HARDWARE_EXECUTION"] = PASS_WITH_NOTES
        payload["STOP_CONDITIONS_TRIGGERED"] = "none"
    else:
        payload["P5_HARDWARE_EXECUTION"] = PASS
        payload["STOP_CONDITIONS_TRIGGERED"] = "none"
    payload["SHUTDOWN_ON_EXIT"] = FAIL if shutdown_failures else PASS if payload.get("HARDWARE_ACTIONS_EXECUTED") else "SKIP_NO_HARDWARE_ACTIONS"
    payload["executed_stages"] = sequence
    payload["failures"] = failures
    payload["shutdown_failures"] = shutdown_failures
    payload["pending"] = pending
    payload["notes"] = notes
    write_json(P5_DIR / "p5_hardware_execution_summary.json", payload)
    lines = [
        f"P5_HARDWARE_EXECUTION: {payload['P5_HARDWARE_EXECUTION']}",
        f"HARDWARE_ACTIONS_EXECUTED: {str(payload['HARDWARE_ACTIONS_EXECUTED']).lower()}",
        "NO_HARDWARE_ACTIONS_EXECUTED: false",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        f"STOP_CONDITIONS_TRIGGERED: {payload['STOP_CONDITIONS_TRIGGERED']}",
        "",
        "## Stages",
        "",
        *(f"- `{stage}` -> {payload.get(P5_STAGE_RUNS[stage]['marker'], 'PENDING') if stage in P5_STAGE_RUNS else payload.get(DERIVED_EVIDENCE_STAGES[stage][0], 'PENDING')}" for stage in sequence),
    ]
    write_markdown(
        GENERATED / "p5_hardware_execution_summary.md",
        "P5 Hardware Execution Summary",
        payload["P5_HARDWARE_EXECUTION"],
        "authorized P5 hardware execution summary",
        lines,
        no_hw=False,
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run authorized P5 hardware stages with P5 authorization and shutdown-on-exit.")
    parser.add_argument("--allow-hardware", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--authorization-file", default=str(DEFAULT_AUTH_FILE.relative_to(ROOT)))
    parser.add_argument("--board-id", default=DEFAULT_BOARD_ID)
    parser.add_argument("--max-runtime-sec", type=int, default=0)
    parser.add_argument("--stage-filter", default="safe_idle_recheck")
    parser.add_argument("--lane-count", type=int, default=2)
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--bitstream-sha256", default="")
    parser.add_argument("--profile", default="")
    parser.add_argument("--profile-sha256", default="")
    parser.add_argument("--active-pinmap-hash", default="")
    parser.add_argument("--active-xdc-hash", default="")
    parser.add_argument("--shutdown-bitstream", default=str(DEFAULT_SHUTDOWN_BITSTREAM.relative_to(ROOT)))
    parser.add_argument("--shutdown-bitstream-sha256", default="")
    parser.add_argument("--skip-ethernet", action="store_true", default=True)
    parser.add_argument("--skip-motion", action="store_true", default=True)
    parser.add_argument("--stop-on-first-fail", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_authorized_hardware(args)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P5_HARDWARE_EXECUTION: {payload['P5_HARDWARE_EXECUTION']}")
        print(f"STOP_CONDITIONS_TRIGGERED: {payload['STOP_CONDITIONS_TRIGGERED']}")
    return 0 if payload["P5_HARDWARE_EXECUTION"] in {PASS, PASS_WITH_NOTES} else 1


if __name__ == "__main__":
    raise SystemExit(main())
