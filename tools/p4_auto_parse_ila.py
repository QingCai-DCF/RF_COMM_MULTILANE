#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


STATUS_WORDS = 24
STATUS_BITS = STATUS_WORDS * 32
MAGIC = 0x50344144
P5_SHORT_FRAME_MIN = 100
P5_SOAK_FRAME_MIN = 1800


def _parse_int(value: str) -> int | None:
    text = str(value).strip().replace("_", "")
    if not text or "?" in text:
        return None
    if text.startswith(("0x", "0X")):
        body = text[2:]
        if any(ch in body.lower() for ch in "xz"):
            return None
        return int(text, 16)
    if text.startswith(("0b", "0B")):
        body = text[2:]
        if any(ch in body.lower() for ch in "xz"):
            return None
        return int(text, 2)
    if any(ch in text.lower() for ch in "xz"):
        return None
    if re.fullmatch(r"[0-9a-fA-F]+h", text):
        return int(text[:-1], 16)
    if re.fullmatch(r"[01]+b", text):
        return int(text[:-1], 2)
    if re.fullmatch(r"[01]{16,}", text):
        return int(text, 2)
    if re.fullmatch(r"[0-9a-fA-F]{8,}", text) and re.search(r"[a-fA-F]", text):
        return int(text, 16)
    if re.fullmatch(r"\d+", text):
        return int(text, 10)
    return None


def _bit_index(name: str) -> int | None:
    match = re.search(r"(?:p4_auto_status_words_flat|status_words_flat|probe0)[^\[]*\[(\d+)\]", name)
    if not match:
        return None
    idx = int(match.group(1))
    return idx if 0 <= idx < STATUS_BITS else None


def _bus_column(name: str) -> bool:
    lowered = name.lower()
    return "status_words_flat" in lowered or "p4_auto_safe_idle_ila/probe0" in lowered or lowered.endswith("probe0")


def _reconstruct_bus(row: dict[str, str]) -> int | None:
    bits: dict[int, int] = {}
    for name, value in row.items():
        idx = _bit_index(name)
        if idx is None:
            continue
        parsed = _parse_int(value)
        if parsed is None:
            return None
        bits[idx] = parsed & 1
    if len(bits) == STATUS_BITS:
        value = 0
        for idx, bit in bits.items():
            value |= bit << idx
        return value
    for name, value in row.items():
        if not _bus_column(name):
            continue
        parsed = _parse_int(value)
        if parsed is not None:
            return parsed
    return None


def _words(bus_value: int) -> list[int]:
    return [(bus_value >> (word * 32)) & 0xFFFF_FFFF for word in range(STATUS_WORDS)]


def _lo(value: int) -> int:
    return value & 0xFFFF


def _hi(value: int) -> int:
    return (value >> 16) & 0xFFFF


def decode_safe_idle_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0x3
    lane_mask &= 0xFFFF
    mode = words[2] & lane_mask
    sd = words[3] & lane_mask
    txd = words[4] & lane_mask
    txd_max = max(words[11] & 0xFFFF, (words[11] >> 16) & 0xFFFF)
    txd_total = (words[12] & 0xFFFF) + ((words[12] >> 16) & 0xFFFF)
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    shutdown_state = 1 if (words[15] & (1 << 7)) else 0
    safe_idle_state = 1 if (words[15] & (1 << 6)) else 0
    checks = {
        "magic": words[0] == MAGIC,
        "mode_all_lanes": mode == lane_mask and lane_mask != 0,
        "sd_all_lanes": sd == lane_mask and lane_mask != 0,
        "txd_all_lanes_low": txd == 0,
        "txd_max_zero": txd_max == 0,
        "txd_total_zero": txd_total == 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
        "shutdown_state": shutdown_state == 1,
        "safe_idle_state": safe_idle_state == 1,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "SAFE_IDLE_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "LANE_MASK": f"0x{lane_mask:x}",
        "MODE_CMD_ALL_LANES": 1 if checks["mode_all_lanes"] else 0,
        "SD_CMD_ALL_LANES": 1 if checks["sd_all_lanes"] else 0,
        "TXD_CMD_ALL_LANES": 0 if checks["txd_all_lanes_low"] else "MISMATCH",
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "UNEXPECTED_TX_PULSE_COUNT": txd_total,
        "SHUTDOWN_STATE": shutdown_state,
        "SAFE_IDLE_STATE": safe_idle_state,
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_tfdu_control_idle_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0x3
    lane_mask &= 0xFFFF
    mode = words[2] & lane_mask
    sd = words[3] & lane_mask
    txd = words[4] & lane_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    txd_max = max(words[11] & 0xFFFF, (words[11] >> 16) & 0xFFFF)
    txd_total = (words[12] & 0xFFFF) + ((words[12] >> 16) & 0xFFFF)
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    shutdown_state = 1 if (words[15] & (1 << 7)) else 0
    safe_idle_state = 1 if (words[15] & (1 << 6)) else 0
    receive_active_idle_state = 1 if (words[15] & (1 << 5)) else 0
    checks = {
        "magic": words[0] == MAGIC,
        "mode_all_lanes": mode == lane_mask and lane_mask != 0,
        "sd_all_lanes_low": sd == 0 and lane_mask != 0,
        "txd_all_lanes_low": txd == 0,
        "lane_enable_all_lanes": lane_enable == lane_mask and lane_mask != 0,
        "startup_done_all_lanes": startup_done == lane_mask and lane_mask != 0,
        "txd_max_zero": txd_max == 0,
        "txd_total_zero": txd_total == 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
        "shutdown_state_low": shutdown_state == 0,
        "safe_idle_state_low": safe_idle_state == 0,
        "receive_active_idle_state": receive_active_idle_state == 1,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "TFDU_CONTROL_IDLE_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "LANE_MASK": f"0x{lane_mask:x}",
        "MODE_CMD_ALL_LANES": 1 if checks["mode_all_lanes"] else 0,
        "SD_CMD_ALL_ENABLED_LANES": 0 if checks["sd_all_lanes_low"] else "MISMATCH",
        "TXD_CMD_ALL_ENABLED_LANES": 0 if checks["txd_all_lanes_low"] else "MISMATCH",
        "LANE_ENABLE_ALL_LANES": 1 if checks["lane_enable_all_lanes"] else 0,
        "STARTUP_DONE": 1 if checks["startup_done_all_lanes"] else 0,
        "STARTUP_WAIT_US": 500 if checks["startup_done_all_lanes"] else "MISSING",
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "UNEXPECTED_TX_PULSE_COUNT": txd_total,
        "SHUTDOWN_STATE": shutdown_state,
        "SAFE_IDLE_STATE": safe_idle_state,
        "RECEIVE_ACTIVE_IDLE_STATE": receive_active_idle_state,
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_raw_pulse_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0x3
    lane_mask &= 0xFFFF
    mode = words[2] & lane_mask
    sd = words[3] & lane_mask
    txd = words[4] & lane_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    rx_lane0_count = words[8] & 0xFFFF
    rx_remote_lane0_count = words[9] & 0xFFFF
    txd_max = _lo(words[18]) or _lo(words[11])
    txd_total = _lo(words[20]) or _lo(words[12])
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    tx_pulse_count = _lo(words[16]) or ((words[15] >> 8) & 0xFFFF)
    enabled_mask = 0x5
    requested_count = 16
    requested_high_cycles = 8
    checks = {
        "magic": words[0] == MAGIC,
        "mode_enabled_lanes": (mode & enabled_mask) == enabled_mask,
        "sd_enabled_lanes_low": (sd & enabled_mask) == 0,
        "lane_enable_matches": lane_enable == enabled_mask,
        "startup_done_matches": startup_done == enabled_mask,
        "tx_pulse_count": tx_pulse_count == requested_count,
        "txd_low_at_capture": txd == 0,
        "txd_max_safe": 0 < txd_max <= requested_high_cycles,
        "txd_total_expected": txd_total == requested_count * requested_high_cycles,
        "rx_remote_counter_available": rx_remote_lane0_count > 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "RAW_PULSE_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "LANE_MASK": f"0x{lane_mask:x}",
        "ENABLED_MASK": f"0x{enabled_mask:x}",
        "TX_REQUESTED_COUNT": requested_count,
        "TX_PULSE_COUNT": tx_pulse_count,
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "RX_LOCAL_LANE0_ACTIVE_LOW_PULSE_COUNT": rx_lane0_count,
        "RX_REMOTE_LANE0_ACTIVE_LOW_PULSE_COUNT": rx_remote_lane0_count,
        "RX_PULSE_COUNT": rx_remote_lane0_count,
        "MODE_CMD_ENABLED_LANES": 1 if checks["mode_enabled_lanes"] else 0,
        "SD_CMD_ENABLED_LANES": 0 if checks["sd_enabled_lanes_low"] else "MISMATCH",
        "TXD_CMD_AT_CAPTURE": txd,
        "LANE_ENABLE": f"0x{lane_enable:x}",
        "STARTUP_DONE": f"0x{startup_done:x}",
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_raw_lane_matrix_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0xF
    lane_mask &= 0xFFFF
    mode = words[2] & lane_mask
    sd = words[3] & lane_mask
    txd = words[4] & lane_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    tx_ab_l0, tx_ba_l0 = _lo(words[16]), _hi(words[16])
    tx_ab_l1, tx_ba_l1 = _lo(words[17]), _hi(words[17])
    rx_ab_l0, rx_ba_l0 = _lo(words[18]), _hi(words[18])
    rx_ab_l1, rx_ba_l1 = _lo(words[19]), _hi(words[19])
    tx_max_ab_l0, tx_max_ba_l0 = _lo(words[20]), _hi(words[20])
    tx_total_ab_l0, tx_total_ba_l0 = _lo(words[21]), _hi(words[21])
    tx_max_ab_l1, tx_max_ba_l1 = _lo(words[22]), _hi(words[22])
    tx_total_ab_l1, tx_total_ba_l1 = _lo(words[23]), _hi(words[23])
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    requested_count = 64
    requested_high_cycles = 8
    expected_total = requested_count * requested_high_cycles
    directions = [
        {
            "direction": "AB_L0",
            "lane": 0,
            "source_endpoint": "A",
            "destination_endpoint": "B",
            "tx_requested_count": requested_count,
            "tx_observed_count": tx_ab_l0,
            "rx_active_low_pulse_count": rx_ab_l0,
            "rx_falling_edge_count": rx_ab_l0,
            "txd_high_max_cycles": tx_max_ab_l0,
            "txd_high_total_cycles": tx_total_ab_l0,
        },
        {
            "direction": "BA_L0",
            "lane": 0,
            "source_endpoint": "B",
            "destination_endpoint": "A",
            "tx_requested_count": requested_count,
            "tx_observed_count": tx_ba_l0,
            "rx_active_low_pulse_count": rx_ba_l0,
            "rx_falling_edge_count": rx_ba_l0,
            "txd_high_max_cycles": tx_max_ba_l0,
            "txd_high_total_cycles": tx_total_ba_l0,
        },
        {
            "direction": "AB_L1",
            "lane": 1,
            "source_endpoint": "A",
            "destination_endpoint": "B",
            "tx_requested_count": requested_count,
            "tx_observed_count": tx_ab_l1,
            "rx_active_low_pulse_count": rx_ab_l1,
            "rx_falling_edge_count": rx_ab_l1,
            "txd_high_max_cycles": tx_max_ab_l1,
            "txd_high_total_cycles": tx_total_ab_l1,
        },
        {
            "direction": "BA_L1",
            "lane": 1,
            "source_endpoint": "B",
            "destination_endpoint": "A",
            "tx_requested_count": requested_count,
            "tx_observed_count": tx_ba_l1,
            "rx_active_low_pulse_count": rx_ba_l1,
            "rx_falling_edge_count": rx_ba_l1,
            "txd_high_max_cycles": tx_max_ba_l1,
            "txd_high_total_cycles": tx_total_ba_l1,
        },
    ]
    for item in directions:
        checks = {
            "tx_requested_count": item["tx_observed_count"] == requested_count,
            "rx_counter_available": item["rx_active_low_pulse_count"] > 0,
            "txd_high_max_safe": 0 < item["txd_high_max_cycles"] <= requested_high_cycles,
            "txd_high_total_expected": item["txd_high_total_cycles"] == expected_total,
        }
        item["status"] = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
        item["checks"] = checks
    global_checks = {
        "magic": words[0] == MAGIC,
        "mode_all_lanes": mode == lane_mask and lane_mask == 0xF,
        "sd_all_lanes_low": sd == 0 and lane_mask == 0xF,
        "txd_low_at_capture": txd == 0,
        "lane_enable_all_lanes": lane_enable == 0xF,
        "startup_done_all_lanes": startup_done == 0xF,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
        "directions_pass": all(item["status"] == "PASS" for item in directions),
    }
    status = "PASS" if all(global_checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "RAW_LANE_MATRIX_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "LANE_MASK": f"0x{lane_mask:x}",
        "TX_REQUESTED_COUNT_PER_DIRECTION": requested_count,
        "MODE_CMD_ALL_LANES": 1 if global_checks["mode_all_lanes"] else 0,
        "SD_CMD_ALL_LANES": 0 if global_checks["sd_all_lanes_low"] else "MISMATCH",
        "TXD_CMD_AT_CAPTURE": txd,
        "LANE_ENABLE": f"0x{lane_enable:x}",
        "STARTUP_DONE": f"0x{startup_done:x}",
        "TXD_STUCK_HIGH_VIOLATION": 0 if global_checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if global_checks["duty_zero"] else duty,
        "direction_results": directions,
        "checks": global_checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_lane0_frame_crc_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0xF
    lane_mask &= 0xFFFF
    enabled_mask = 0x5
    mode = words[2] & enabled_mask
    sd = words[3] & enabled_mask
    txd = words[4] & enabled_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    rx_remote_lane0_count = _lo(words[9])
    txd_max = _lo(words[11])
    txd_total = _lo(words[12])
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    sent_frames = _lo(words[16])
    requested_frames = _hi(words[16])
    rx_good = _lo(words[17])
    frame_bad = _hi(words[17])
    crc_bad = _lo(words[18])
    payload_mismatch = _hi(words[18])
    session = _hi(words[19])
    lane_mask_readback = (words[19] >> 8) & 0xFF
    ack_lane_mask_readback = words[19] & 0xFF
    rx_symbol_errors = _lo(words[20])
    preamble_seen = _hi(words[20])
    stage_magic = words[23]
    checks = {
        "magic": words[0] == MAGIC,
        "stage_magic": stage_magic == 0x4C304643,
        "mode_enabled_lanes": mode == enabled_mask,
        "sd_enabled_lanes_low": sd == 0,
        "lane_enable_matches": lane_enable == enabled_mask,
        "startup_done_matches": startup_done == enabled_mask,
        "session_readback": session == 0x2201,
        "lane_mask_readback": lane_mask_readback == 0x01,
        "ack_mask_disabled": ack_lane_mask_readback == 0x00,
        "sent_frames": requested_frames >= P5_SHORT_FRAME_MIN and sent_frames == requested_frames,
        "rx_good_matches_sent": rx_good == sent_frames and rx_good > 0,
        "frame_bad_zero": frame_bad == 0,
        "crc_bad_zero": crc_bad == 0,
        "payload_mismatch_zero": payload_mismatch == 0,
        "rx_symbol_errors_zero": rx_symbol_errors == 0,
        "preamble_seen": preamble_seen >= sent_frames and preamble_seen > 0,
        "remote_rx_raw_seen": rx_remote_lane0_count > 0,
        "txd_low_at_capture": txd == 0,
        "txd_max_safe": 0 < txd_max <= 8,
        "txd_total_nonzero": txd_total > 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "LANE0_FRAME_CRC_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "STAGE_MAGIC": f"0x{stage_magic:08x}",
        "ENABLED_MASK": f"0x{enabled_mask:x}",
        "SESSION_READBACK": f"0x{session:04x}",
        "LANE_MASK_READBACK": f"0x{lane_mask_readback:x}",
        "ACK_LANE_MASK_READBACK": f"0x{ack_lane_mask_readback:x}",
        "SENT_FRAMES": sent_frames,
        "REQUESTED_FRAMES": requested_frames,
        "RX_GOOD": rx_good,
        "FRAME_BAD": frame_bad,
        "CRC_BAD": crc_bad,
        "PAYLOAD_MISMATCH": payload_mismatch,
        "RX_SYMBOL_ERRORS": rx_symbol_errors,
        "PREAMBLE_SEEN_COUNT": preamble_seen,
        "RX_REMOTE_LANE0_ACTIVE_LOW_PULSE_COUNT": rx_remote_lane0_count,
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "MODE_CMD_ENABLED_LANES": 1 if checks["mode_enabled_lanes"] else 0,
        "SD_CMD_ENABLED_LANES": 0 if checks["sd_enabled_lanes_low"] else "MISMATCH",
        "TXD_CMD_AT_CAPTURE": txd,
        "LANE_ENABLE": f"0x{lane_enable:x}",
        "STARTUP_DONE": f"0x{startup_done:x}",
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_lane1_frame_crc_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0xF
    lane_mask &= 0xFFFF
    enabled_mask = 0xA
    mode = words[2] & enabled_mask
    sd = words[3] & enabled_mask
    txd = words[4] & enabled_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    rx_remote_lane1_count = _hi(words[9])
    txd_max = _hi(words[11])
    txd_total = _hi(words[12])
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    sent_frames = _lo(words[16])
    requested_frames = _hi(words[16])
    rx_good = _lo(words[17])
    frame_bad = _hi(words[17])
    crc_bad = _lo(words[18])
    payload_mismatch = _hi(words[18])
    session = _hi(words[19])
    lane_mask_readback = (words[19] >> 8) & 0xFF
    ack_lane_mask_readback = words[19] & 0xFF
    rx_symbol_errors = _lo(words[20])
    preamble_seen = _hi(words[20])
    stage_magic = words[23]
    checks = {
        "magic": words[0] == MAGIC,
        "stage_magic": stage_magic == 0x4C314643,
        "mode_enabled_lanes": mode == enabled_mask,
        "sd_enabled_lanes_low": sd == 0,
        "lane_enable_matches": lane_enable == enabled_mask,
        "startup_done_matches": startup_done == enabled_mask,
        "session_readback": session == 0x2201,
        "lane_mask_readback": lane_mask_readback == 0x02,
        "ack_mask_disabled": ack_lane_mask_readback == 0x00,
        "sent_frames": requested_frames >= P5_SHORT_FRAME_MIN and sent_frames == requested_frames,
        "rx_good_matches_sent": rx_good == sent_frames and rx_good > 0,
        "frame_bad_zero": frame_bad == 0,
        "crc_bad_zero": crc_bad == 0,
        "payload_mismatch_zero": payload_mismatch == 0,
        "rx_symbol_errors_zero": rx_symbol_errors == 0,
        "preamble_seen": preamble_seen >= sent_frames and preamble_seen > 0,
        "remote_rx_raw_seen": rx_remote_lane1_count > 0,
        "txd_low_at_capture": txd == 0,
        "txd_max_safe": 0 < txd_max <= 8,
        "txd_total_nonzero": txd_total > 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "LANE1_FRAME_CRC_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "STAGE_MAGIC": f"0x{stage_magic:08x}",
        "ENABLED_MASK": f"0x{enabled_mask:x}",
        "SESSION_READBACK": f"0x{session:04x}",
        "LANE_MASK_READBACK": f"0x{lane_mask_readback:x}",
        "ACK_LANE_MASK_READBACK": f"0x{ack_lane_mask_readback:x}",
        "SENT_FRAMES": sent_frames,
        "REQUESTED_FRAMES": requested_frames,
        "RX_GOOD": rx_good,
        "FRAME_BAD": frame_bad,
        "CRC_BAD": crc_bad,
        "PAYLOAD_MISMATCH": payload_mismatch,
        "RX_SYMBOL_ERRORS": rx_symbol_errors,
        "PREAMBLE_SEEN_COUNT": preamble_seen,
        "RX_REMOTE_LANE1_ACTIVE_LOW_PULSE_COUNT": rx_remote_lane1_count,
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "MODE_CMD_ENABLED_LANES": 1 if checks["mode_enabled_lanes"] else 0,
        "SD_CMD_ENABLED_LANES": 0 if checks["sd_enabled_lanes_low"] else "MISMATCH",
        "TXD_CMD_AT_CAPTURE": txd,
        "LANE_ENABLE": f"0x{lane_enable:x}",
        "STARTUP_DONE": f"0x{startup_done:x}",
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_lane0_ack_retry_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0xF
    lane_mask &= 0xFFFF
    enabled_mask = 0x5
    mode = words[2] & enabled_mask
    sd = words[3] & enabled_mask
    txd = words[4] & enabled_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    a_ack_rx_count = _lo(words[8])
    b_data_rx_count = _lo(words[9])
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    sent_frames = _lo(words[16])
    requested_frames = _hi(words[16])
    b_rx_good = _lo(words[17])
    b_frame_bad = _hi(words[17])
    crc_bad = _lo(words[18])
    payload_mismatch = _hi(words[18])
    session = _hi(words[19])
    lane_mask_readback = (words[19] >> 8) & 0xFF
    ack_lane_mask_readback = words[19] & 0xFF
    a_ack_seen = _lo(words[20])
    b_ack_sent = _hi(words[20])
    tx_fail = _lo(words[21])
    retry_exhausted = _hi(words[21])
    txd_max = _lo(words[22])
    txd_total = _hi(words[22])
    stage_magic = words[23]
    checks = {
        "magic": words[0] == MAGIC,
        "stage_magic": stage_magic == 0x4C304152,
        "mode_enabled_lanes": mode == enabled_mask,
        "sd_enabled_lanes_low": sd == 0,
        "lane_enable_matches": lane_enable == enabled_mask,
        "startup_done_matches": startup_done == enabled_mask,
        "session_readback": session == 0x2201,
        "lane_mask_readback": lane_mask_readback == 0x01,
        "ack_mask_enabled": ack_lane_mask_readback == 0x01,
        "sent_frames": requested_frames >= P5_SHORT_FRAME_MIN and sent_frames == requested_frames,
        "b_rx_good_matches_sent": b_rx_good == sent_frames and b_rx_good > 0,
        "b_frame_bad_zero": b_frame_bad == 0,
        "crc_bad_zero": crc_bad == 0,
        "payload_mismatch_zero": payload_mismatch == 0,
        "b_ack_sent": b_ack_sent > 0,
        "a_ack_seen": a_ack_seen > 0,
        "ack_counts_match": a_ack_seen == b_ack_sent,
        "tx_retry_exhausted_zero": retry_exhausted == 0,
        "tx_fail_zero": tx_fail == 0,
        "data_raw_seen": b_data_rx_count > 0,
        "ack_raw_seen": a_ack_rx_count > 0,
        "txd_low_at_capture": txd == 0,
        "txd_max_safe": 0 < txd_max <= 8,
        "txd_total_nonzero": txd_total > 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "LANE0_ACK_RETRY_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "STAGE_MAGIC": f"0x{stage_magic:08x}",
        "ENABLED_MASK": f"0x{enabled_mask:x}",
        "SESSION_READBACK": f"0x{session:04x}",
        "LANE_MASK_READBACK": f"0x{lane_mask_readback:x}",
        "ACK_LANE_MASK_READBACK": f"0x{ack_lane_mask_readback:x}",
        "A_SENT_FRAMES": sent_frames,
        "REQUESTED_FRAMES": requested_frames,
        "B_RX_GOOD": b_rx_good,
        "B_FRAME_BAD": b_frame_bad,
        "CRC_BAD": crc_bad,
        "PAYLOAD_MISMATCH": payload_mismatch,
        "B_ACK_SENT": b_ack_sent,
        "A_ACK_SEEN": a_ack_seen,
        "TX_RETRY_EXHAUSTED": retry_exhausted,
        "TX_FAIL": tx_fail,
        "A_ACK_RX_ACTIVE_LOW_PULSE_COUNT": a_ack_rx_count,
        "B_DATA_RX_ACTIVE_LOW_PULSE_COUNT": b_data_rx_count,
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "MODE_CMD_ENABLED_LANES": 1 if checks["mode_enabled_lanes"] else 0,
        "SD_CMD_ENABLED_LANES": 0 if checks["sd_enabled_lanes_low"] else "MISMATCH",
        "TXD_CMD_AT_CAPTURE": txd,
        "LANE_ENABLE": f"0x{lane_enable:x}",
        "STARTUP_DONE": f"0x{startup_done:x}",
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_lane1_ack_retry_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0xF
    lane_mask &= 0xFFFF
    enabled_mask = 0xA
    mode = words[2] & enabled_mask
    sd = words[3] & enabled_mask
    txd = words[4] & enabled_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    a_ack_rx_count = _hi(words[8])
    b_data_rx_count = _hi(words[9])
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    sent_frames = _lo(words[16])
    requested_frames = _hi(words[16])
    b_rx_good = _lo(words[17])
    b_frame_bad = _hi(words[17])
    crc_bad = _lo(words[18])
    payload_mismatch = _hi(words[18])
    session = _hi(words[19])
    lane_mask_readback = (words[19] >> 8) & 0xFF
    ack_lane_mask_readback = words[19] & 0xFF
    a_ack_seen = _lo(words[20])
    b_ack_sent = _hi(words[20])
    tx_fail = _lo(words[21])
    retry_exhausted = _hi(words[21])
    txd_max = _lo(words[22])
    txd_total = _hi(words[22])
    stage_magic = words[23]
    checks = {
        "magic": words[0] == MAGIC,
        "stage_magic": stage_magic == 0x4C314152,
        "mode_enabled_lanes": mode == enabled_mask,
        "sd_enabled_lanes_low": sd == 0,
        "lane_enable_matches": lane_enable == enabled_mask,
        "startup_done_matches": startup_done == enabled_mask,
        "session_readback": session == 0x2201,
        "lane_mask_readback": lane_mask_readback == 0x02,
        "ack_mask_enabled": ack_lane_mask_readback == 0x02,
        "sent_frames": requested_frames >= P5_SHORT_FRAME_MIN and sent_frames == requested_frames,
        "b_rx_good_matches_sent": b_rx_good == sent_frames and b_rx_good > 0,
        "b_frame_bad_zero": b_frame_bad == 0,
        "crc_bad_zero": crc_bad == 0,
        "payload_mismatch_zero": payload_mismatch == 0,
        "b_ack_sent": b_ack_sent > 0,
        "a_ack_seen": a_ack_seen > 0,
        "ack_counts_match": a_ack_seen == b_ack_sent,
        "tx_retry_exhausted_zero": retry_exhausted == 0,
        "tx_fail_zero": tx_fail == 0,
        "data_raw_seen": b_data_rx_count > 0,
        "ack_raw_seen": a_ack_rx_count > 0,
        "txd_low_at_capture": txd == 0,
        "txd_max_safe": 0 < txd_max <= 8,
        "txd_total_nonzero": txd_total > 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "LANE1_ACK_RETRY_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "STAGE_MAGIC": f"0x{stage_magic:08x}",
        "ENABLED_MASK": f"0x{enabled_mask:x}",
        "SESSION_READBACK": f"0x{session:04x}",
        "LANE_MASK_READBACK": f"0x{lane_mask_readback:x}",
        "ACK_LANE_MASK_READBACK": f"0x{ack_lane_mask_readback:x}",
        "A_SENT_FRAMES": sent_frames,
        "REQUESTED_FRAMES": requested_frames,
        "B_RX_GOOD": b_rx_good,
        "B_FRAME_BAD": b_frame_bad,
        "CRC_BAD": crc_bad,
        "PAYLOAD_MISMATCH": payload_mismatch,
        "B_ACK_SENT": b_ack_sent,
        "A_ACK_SEEN": a_ack_seen,
        "TX_RETRY_EXHAUSTED": retry_exhausted,
        "TX_FAIL": tx_fail,
        "A_ACK_RX_ACTIVE_LOW_PULSE_COUNT": a_ack_rx_count,
        "B_DATA_RX_ACTIVE_LOW_PULSE_COUNT": b_data_rx_count,
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "MODE_CMD_ENABLED_LANES": 1 if checks["mode_enabled_lanes"] else 0,
        "SD_CMD_ENABLED_LANES": 0 if checks["sd_enabled_lanes_low"] else "MISMATCH",
        "TXD_CMD_AT_CAPTURE": txd,
        "LANE_ENABLE": f"0x{lane_enable:x}",
        "STARTUP_DONE": f"0x{startup_done:x}",
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_two_lane_minimal_words(words: list[int]) -> dict:
    lane_mask = (1 << (words[1] >> 16)) - 1 if words[1] >> 16 else 0xF
    lane_mask &= 0xFFFF
    enabled_mask = 0xF
    mode = words[2] & enabled_mask
    sd = words[3] & enabled_mask
    txd = words[4] & enabled_mask
    lane_enable = words[6] & lane_mask
    startup_done = words[7] & lane_mask
    a_ack_l0_count = _lo(words[8])
    a_ack_l1_count = _hi(words[8])
    b_data_l0_count = _lo(words[9])
    b_data_l1_count = _hi(words[9])
    stuck = words[13] & lane_mask
    duty = words[14] & lane_mask
    sent_frames_per_lane = _lo(words[16])
    requested_frames_per_lane = _hi(words[16])
    lane0_rx_good = _lo(words[17])
    lane1_rx_good = _hi(words[17])
    crc_bad = _lo(words[18])
    payload_mismatch = _hi(words[18])
    session = _hi(words[19])
    lane_mask_readback = (words[19] >> 8) & 0xFF
    ack_lane_mask_readback = words[19] & 0xFF
    lane0_ack_sent = _lo(words[20])
    lane1_ack_sent = _hi(words[20])
    tx_fail = _lo(words[21])
    retry_exhausted = _hi(words[21])
    txd_max = _lo(words[22])
    txd_total = _hi(words[22])
    stage_magic = words[23]
    checks = {
        "magic": words[0] == MAGIC,
        "stage_magic": stage_magic == 0x324C4152,
        "mode_all_lanes": mode == enabled_mask,
        "sd_all_lanes_low": sd == 0,
        "lane_enable_all_lanes": lane_enable == enabled_mask,
        "startup_done_all_lanes": startup_done == enabled_mask,
        "session_readback": session == 0x2201,
        "lane_mask_readback": lane_mask_readback == 0x03,
        "ack_mask_readback": ack_lane_mask_readback == 0x03,
        "sent_frames_per_lane": requested_frames_per_lane >= P5_SHORT_FRAME_MIN and sent_frames_per_lane == requested_frames_per_lane,
        "lane0_rx_good": lane0_rx_good >= requested_frames_per_lane and lane0_rx_good > 0,
        "lane1_rx_good": lane1_rx_good >= requested_frames_per_lane and lane1_rx_good > 0,
        "crc_bad_zero": crc_bad == 0,
        "payload_mismatch_zero": payload_mismatch == 0,
        "lane0_ack_sent": lane0_ack_sent > 0,
        "lane1_ack_sent": lane1_ack_sent > 0,
        "tx_retry_exhausted_zero": retry_exhausted == 0,
        "tx_fail_zero": tx_fail == 0,
        "lane0_data_raw_seen": b_data_l0_count > 0,
        "lane1_data_raw_seen": b_data_l1_count > 0,
        "lane0_ack_raw_seen": a_ack_l0_count > 0,
        "lane1_ack_raw_seen": a_ack_l1_count > 0,
        "txd_low_at_capture": txd == 0,
        "txd_max_safe": 0 < txd_max <= 8,
        "txd_total_nonzero": txd_total > 0,
        "stuck_zero": stuck == 0,
        "duty_zero": duty == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    return {
        "TWO_LANE_MINIMAL_ILA_PARSE": status,
        "ILA_MAGIC": f"0x{words[0]:08x}",
        "STAGE_MAGIC": f"0x{stage_magic:08x}",
        "ENABLED_MASK": f"0x{enabled_mask:x}",
        "SESSION_READBACK": f"0x{session:04x}",
        "LANE_MASK_READBACK": f"0x{lane_mask_readback:x}",
        "ACK_LANE_MASK_READBACK": f"0x{ack_lane_mask_readback:x}",
        "A_SENT_FRAMES_PER_LANE": sent_frames_per_lane,
        "REQUESTED_FRAMES_PER_LANE": requested_frames_per_lane,
        "LANE0_RX_GOOD": lane0_rx_good,
        "LANE1_RX_GOOD": lane1_rx_good,
        "TOTAL_RX_GOOD": lane0_rx_good + lane1_rx_good,
        "CRC_BAD": crc_bad,
        "PAYLOAD_MISMATCH": payload_mismatch,
        "LANE0_ACK_SENT": lane0_ack_sent,
        "LANE1_ACK_SENT": lane1_ack_sent,
        "TX_RETRY_EXHAUSTED": retry_exhausted,
        "TX_FAIL": tx_fail,
        "LANE0_ACK_RX_ACTIVE_LOW_PULSE_COUNT": a_ack_l0_count,
        "LANE1_ACK_RX_ACTIVE_LOW_PULSE_COUNT": a_ack_l1_count,
        "LANE0_DATA_RX_ACTIVE_LOW_PULSE_COUNT": b_data_l0_count,
        "LANE1_DATA_RX_ACTIVE_LOW_PULSE_COUNT": b_data_l1_count,
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": txd_max,
        "TXD_HIGH_TOTAL_CYCLES": txd_total,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["stuck_zero"] else stuck,
        "DUTY_WINDOW_VIOLATION": 0 if checks["duty_zero"] else duty,
        "MODE_CMD_ALL_LANES": 1 if checks["mode_all_lanes"] else 0,
        "SD_CMD_ALL_LANES": 0 if checks["sd_all_lanes_low"] else "MISMATCH",
        "TXD_CMD_AT_CAPTURE": txd,
        "LANE_ENABLE": f"0x{lane_enable:x}",
        "STARTUP_DONE": f"0x{startup_done:x}",
        "checks": checks,
        "status_words": [f"0x{word:08x}" for word in words],
    }


def decode_lane0_300s_soak_words(words: list[int]) -> dict:
    base = decode_lane0_ack_retry_words(words)
    sent_frames = int(base.get("A_SENT_FRAMES", 0))
    requested_frames = int(base.get("REQUESTED_FRAMES", 0))
    b_rx_good = int(base.get("B_RX_GOOD", 0))
    b_ack_sent = int(base.get("B_ACK_SENT", 0))
    a_ack_seen = int(base.get("A_ACK_SEEN", 0))
    checks = dict(base.get("checks", {}))
    checks["stage_magic"] = words[23] == 0x4C30534B
    checks["soak_requested_frames"] = requested_frames >= P5_SOAK_FRAME_MIN
    checks["soak_sent_frames"] = sent_frames >= P5_SOAK_FRAME_MIN
    checks["soak_rx_good_matches_sent"] = b_rx_good == sent_frames and b_rx_good >= P5_SOAK_FRAME_MIN
    checks["soak_ack_counts_match_sent"] = b_ack_sent == sent_frames and a_ack_seen == sent_frames
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    base.pop("LANE0_ACK_RETRY_ILA_PARSE", None)
    base.update(
        {
            "LANE0_300S_SOAK_ILA_PARSE": status,
            "STAGE_MAGIC": f"0x{words[23]:08x}",
            "SOAK_REQUESTED_FRAMES": requested_frames,
            "SOAK_SENT_FRAMES": sent_frames,
            "SOAK_RX_GOOD": b_rx_good,
            "checks": checks,
        }
    )
    return base


def decode_two_lane_300s_soak_words(words: list[int]) -> dict:
    base = decode_two_lane_minimal_words(words)
    sent_frames_per_lane = int(base.get("A_SENT_FRAMES_PER_LANE", 0))
    requested_frames_per_lane = int(base.get("REQUESTED_FRAMES_PER_LANE", 0))
    lane0_rx_good = int(base.get("LANE0_RX_GOOD", 0))
    lane1_rx_good = int(base.get("LANE1_RX_GOOD", 0))
    lane0_ack_sent = int(base.get("LANE0_ACK_SENT", 0))
    lane1_ack_sent = int(base.get("LANE1_ACK_SENT", 0))
    checks = dict(base.get("checks", {}))
    checks["stage_magic"] = words[23] == 0x324C534B
    checks["soak_requested_frames_per_lane"] = requested_frames_per_lane >= P5_SOAK_FRAME_MIN
    checks["soak_sent_frames_per_lane"] = sent_frames_per_lane >= P5_SOAK_FRAME_MIN
    checks["soak_lane0_rx_good_matches_sent"] = lane0_rx_good >= sent_frames_per_lane and lane0_rx_good >= P5_SOAK_FRAME_MIN
    checks["soak_lane1_rx_good_matches_sent"] = lane1_rx_good >= sent_frames_per_lane and lane1_rx_good >= P5_SOAK_FRAME_MIN
    checks["soak_ack_counts_present"] = lane0_ack_sent >= P5_SOAK_FRAME_MIN and lane1_ack_sent >= P5_SOAK_FRAME_MIN
    status = "PASS" if all(checks.values()) else "FAIL_WITH_EVIDENCE"
    base.pop("TWO_LANE_MINIMAL_ILA_PARSE", None)
    base.update(
        {
            "TWO_LANE_300S_SOAK_ILA_PARSE": status,
            "STAGE_MAGIC": f"0x{words[23]:08x}",
            "SOAK_REQUESTED_FRAMES_PER_LANE": requested_frames_per_lane,
            "SOAK_SENT_FRAMES_PER_LANE": sent_frames_per_lane,
            "SOAK_LANE0_RX_GOOD": lane0_rx_good,
            "SOAK_LANE1_RX_GOOD": lane1_rx_good,
            "checks": checks,
        }
    )
    return base


def parse_safe_idle_csv(path: Path) -> dict:
    if not path.exists():
        return {"SAFE_IDLE_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_safe_idle_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "SAFE_IDLE_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_tfdu_control_idle_csv(path: Path) -> dict:
    if not path.exists():
        return {"TFDU_CONTROL_IDLE_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_tfdu_control_idle_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "TFDU_CONTROL_IDLE_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_raw_pulse_csv(path: Path) -> dict:
    if not path.exists():
        return {"RAW_PULSE_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_raw_pulse_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "RAW_PULSE_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_raw_lane_matrix_csv(path: Path) -> dict:
    if not path.exists():
        return {"RAW_LANE_MATRIX_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_raw_lane_matrix_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "RAW_LANE_MATRIX_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane0_frame_crc_csv(path: Path) -> dict:
    if not path.exists():
        return {"LANE0_FRAME_CRC_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_lane0_frame_crc_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "LANE0_FRAME_CRC_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane1_frame_crc_csv(path: Path) -> dict:
    if not path.exists():
        return {"LANE1_FRAME_CRC_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_lane1_frame_crc_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "LANE1_FRAME_CRC_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane0_ack_retry_csv(path: Path) -> dict:
    if not path.exists():
        return {"LANE0_ACK_RETRY_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_lane0_ack_retry_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "LANE0_ACK_RETRY_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane1_ack_retry_csv(path: Path) -> dict:
    if not path.exists():
        return {"LANE1_ACK_RETRY_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_lane1_ack_retry_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "LANE1_ACK_RETRY_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_two_lane_minimal_csv(path: Path) -> dict:
    if not path.exists():
        return {"TWO_LANE_MINIMAL_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_two_lane_minimal_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "TWO_LANE_MINIMAL_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane0_300s_soak_csv(path: Path) -> dict:
    if not path.exists():
        return {"LANE0_300S_SOAK_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_lane0_300s_soak_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "LANE0_300S_SOAK_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_two_lane_300s_soak_csv(path: Path) -> dict:
    if not path.exists():
        return {"TWO_LANE_300S_SOAK_ILA_PARSE": "SKIP_WITH_REASON", "reason": f"missing CSV: {path}"}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for sample_index, row in reversed(list(enumerate(rows))):
        bus_value = _reconstruct_bus(row)
        if bus_value is None:
            continue
        decoded = decode_two_lane_300s_soak_words(_words(bus_value))
        decoded.update(
            {
                "csv": str(path),
                "rows": len(rows),
                "sample_index": sample_index,
                "columns": list(row.keys()),
                "NO_HARDWARE_ACTIONS_EXECUTED": True,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        )
        return decoded
    return {
        "TWO_LANE_300S_SOAK_ILA_PARSE": "SKIP_WITH_REASON",
        "reason": "no reconstructable p4_auto_status_words_flat/probe0 sample found",
        "csv": str(path),
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_safe_idle_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_safe_idle_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("SAFE_IDLE_ILA_PARSE") == "PASS"]
    return {
        "SAFE_IDLE_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_tfdu_control_idle_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_tfdu_control_idle_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("TFDU_CONTROL_IDLE_ILA_PARSE") == "PASS"]
    return {
        "TFDU_CONTROL_IDLE_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_raw_pulse_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_raw_pulse_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("RAW_PULSE_ILA_PARSE") == "PASS"]
    return {
        "RAW_PULSE_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_raw_lane_matrix_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_raw_lane_matrix_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("RAW_LANE_MATRIX_ILA_PARSE") == "PASS"]
    return {
        "RAW_LANE_MATRIX_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane0_frame_crc_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_lane0_frame_crc_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("LANE0_FRAME_CRC_ILA_PARSE") == "PASS"]
    return {
        "LANE0_FRAME_CRC_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane1_frame_crc_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_lane1_frame_crc_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("LANE1_FRAME_CRC_ILA_PARSE") == "PASS"]
    return {
        "LANE1_FRAME_CRC_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane0_ack_retry_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_lane0_ack_retry_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("LANE0_ACK_RETRY_ILA_PARSE") == "PASS"]
    return {
        "LANE0_ACK_RETRY_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane1_ack_retry_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_lane1_ack_retry_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("LANE1_ACK_RETRY_ILA_PARSE") == "PASS"]
    return {
        "LANE1_ACK_RETRY_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_two_lane_minimal_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_two_lane_minimal_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("TWO_LANE_MINIMAL_ILA_PARSE") == "PASS"]
    return {
        "TWO_LANE_MINIMAL_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_lane0_300s_soak_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_lane0_300s_soak_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("LANE0_300S_SOAK_ILA_PARSE") == "PASS"]
    return {
        "LANE0_300S_SOAK_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def parse_two_lane_300s_soak_capture_dir(path: Path) -> dict:
    csv_paths = sorted(path.glob("*.csv")) if path.exists() else []
    results = [parse_two_lane_300s_soak_csv(csv_path) for csv_path in csv_paths]
    passing = [result for result in results if result.get("TWO_LANE_300S_SOAK_ILA_PARSE") == "PASS"]
    return {
        "TWO_LANE_300S_SOAK_ILA_PARSE": "PASS" if passing else "SKIP_WITH_REASON" if not results else "FAIL_WITH_EVIDENCE",
        "capture_dir": str(path),
        "csv_count": len(csv_paths),
        "results": results,
        "best_result": passing[0] if passing else results[0] if results else {},
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse P4_AUTO ILA CSV safe-idle evidence without touching hardware.")
    parser.add_argument("--csv", default="")
    parser.add_argument("--capture-dir", default="")
    parser.add_argument("--stage", choices=["safe_idle", "tfdu_control_idle", "raw_pulse", "raw_lane_matrix", "lane0_frame_crc", "lane0_ack_retry", "lane1_frame_crc", "lane1_ack_retry", "two_lane_minimal", "lane0_300s_soak", "two_lane_300s_soak"], default="safe_idle")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    if args.stage == "two_lane_300s_soak" and args.capture_dir:
        payload = parse_two_lane_300s_soak_capture_dir(Path(args.capture_dir))
    elif args.stage == "two_lane_300s_soak" and args.csv:
        payload = parse_two_lane_300s_soak_csv(Path(args.csv))
    elif args.stage == "lane0_300s_soak" and args.capture_dir:
        payload = parse_lane0_300s_soak_capture_dir(Path(args.capture_dir))
    elif args.stage == "lane0_300s_soak" and args.csv:
        payload = parse_lane0_300s_soak_csv(Path(args.csv))
    elif args.stage == "two_lane_minimal" and args.capture_dir:
        payload = parse_two_lane_minimal_capture_dir(Path(args.capture_dir))
    elif args.stage == "two_lane_minimal" and args.csv:
        payload = parse_two_lane_minimal_csv(Path(args.csv))
    elif args.stage == "lane1_ack_retry" and args.capture_dir:
        payload = parse_lane1_ack_retry_capture_dir(Path(args.capture_dir))
    elif args.stage == "lane1_ack_retry" and args.csv:
        payload = parse_lane1_ack_retry_csv(Path(args.csv))
    elif args.stage == "lane1_frame_crc" and args.capture_dir:
        payload = parse_lane1_frame_crc_capture_dir(Path(args.capture_dir))
    elif args.stage == "lane1_frame_crc" and args.csv:
        payload = parse_lane1_frame_crc_csv(Path(args.csv))
    elif args.stage == "lane0_ack_retry" and args.capture_dir:
        payload = parse_lane0_ack_retry_capture_dir(Path(args.capture_dir))
    elif args.stage == "lane0_ack_retry" and args.csv:
        payload = parse_lane0_ack_retry_csv(Path(args.csv))
    elif args.stage == "lane0_frame_crc" and args.capture_dir:
        payload = parse_lane0_frame_crc_capture_dir(Path(args.capture_dir))
    elif args.stage == "lane0_frame_crc" and args.csv:
        payload = parse_lane0_frame_crc_csv(Path(args.csv))
    elif args.stage == "raw_lane_matrix" and args.capture_dir:
        payload = parse_raw_lane_matrix_capture_dir(Path(args.capture_dir))
    elif args.stage == "raw_lane_matrix" and args.csv:
        payload = parse_raw_lane_matrix_csv(Path(args.csv))
    elif args.stage == "raw_pulse" and args.capture_dir:
        payload = parse_raw_pulse_capture_dir(Path(args.capture_dir))
    elif args.stage == "raw_pulse" and args.csv:
        payload = parse_raw_pulse_csv(Path(args.csv))
    elif args.stage == "tfdu_control_idle" and args.capture_dir:
        payload = parse_tfdu_control_idle_capture_dir(Path(args.capture_dir))
    elif args.stage == "tfdu_control_idle" and args.csv:
        payload = parse_tfdu_control_idle_csv(Path(args.csv))
    elif args.capture_dir:
        payload = parse_safe_idle_capture_dir(Path(args.capture_dir))
    elif args.csv:
        payload = parse_safe_idle_csv(Path(args.csv))
    else:
        payload = {
            "SAFE_IDLE_ILA_PARSE": "SKIP_WITH_REASON",
            "reason": "no CSV or capture directory provided",
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    status = next(
        (
            payload[key]
            for key in [
                "SAFE_IDLE_ILA_PARSE",
                "TFDU_CONTROL_IDLE_ILA_PARSE",
                "RAW_PULSE_ILA_PARSE",
                "RAW_LANE_MATRIX_ILA_PARSE",
                "LANE0_FRAME_CRC_ILA_PARSE",
                "LANE0_ACK_RETRY_ILA_PARSE",
                "LANE1_FRAME_CRC_ILA_PARSE",
                "LANE1_ACK_RETRY_ILA_PARSE",
                "TWO_LANE_MINIMAL_ILA_PARSE",
                "LANE0_300S_SOAK_ILA_PARSE",
                "TWO_LANE_300S_SOAK_ILA_PARSE",
            ]
            if key in payload
        ),
        "FAIL_WITH_EVIDENCE",
    )
    return 0 if status in {"PASS", "SKIP_WITH_REASON"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
