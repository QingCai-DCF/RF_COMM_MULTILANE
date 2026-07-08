#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def crc32_payload(data: bytes, crc: int = 0xFFFFFFFF) -> int:
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = ((crc >> 1) ^ 0xEDB88320) & 0xFFFFFFFF
            else:
                crc = (crc >> 1) & 0xFFFFFFFF
    return (~crc) & 0xFFFFFFFF


def build_frame(session: int, lane_mask: int, payload: bytes) -> bytes:
    header = bytearray(14)
    header[0] = 0xA5
    header[1] = 0x11
    header[2] = session & 0xFF
    header[3] = (session >> 8) & 0xFF
    header[4] = 0x34
    header[5] = 0x12
    header[6] = 0
    header[7] = 1
    header[8] = len(payload) & 0xFF
    header[9] = 0
    header[10] = len(payload) & 0xFF
    header[11] = lane_mask & 0xFF
    hcrc = crc16_ccitt(header[:12])
    header[12] = hcrc & 0xFF
    header[13] = (hcrc >> 8) & 0xFF
    pcrc = crc32_payload(payload)
    return bytes(header) + payload + pcrc.to_bytes(4, "little")


def validate_frame(frame: bytes, expected_session: int, expected_lane_mask: int) -> dict[str, bool]:
    payload_len = frame[10] if len(frame) > 10 else 0
    payload_end = 14 + payload_len
    header_ok = len(frame) >= 18 and frame[0] == 0xA5 and frame[1] == 0x11
    session = frame[2] | (frame[3] << 8) if len(frame) > 3 else -1
    total_len = frame[8] | (frame[9] << 8) if len(frame) > 9 else -1
    lane_mask = frame[11] if len(frame) > 11 else -1
    payload_len_ok = len(frame) == payload_end + 4 and total_len == payload_len
    header_crc_ok = len(frame) > 13 and int.from_bytes(frame[12:14], "little") == crc16_ccitt(frame[:12])
    payload_crc_ok = (
        payload_len_ok
        and int.from_bytes(frame[payload_end : payload_end + 4], "little")
        == crc32_payload(frame[14:payload_end])
    )
    return {
        "header_ok": header_ok,
        "session_ok": session == expected_session,
        "lane_mask_ok": lane_mask == expected_lane_mask,
        "payload_len_ok": payload_len_ok,
        "crc_ok": header_crc_ok and payload_crc_ok,
    }


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


def main() -> int:
    errors: list[str] = []
    codec = (ROOT / "rtl/ir_4ppm_codec.sv").read_text(encoding="utf-8", errors="ignore")
    frame = (ROOT / "rtl/ir_frame_l1.sv").read_text(encoding="utf-8", errors="ignore")
    codec_tb = (ROOT / "sim/tb/tb_tfdu_4ppm_codec.sv").read_text(encoding="utf-8", errors="ignore")
    frame_tb = (ROOT / "sim/tb/tb_lane0_frame_crc.sv").read_text(encoding="utf-8", errors="ignore")
    model_tb = (ROOT / "sim/tb/tb_tfdu_4ppm_model_integration.sv").read_text(encoding="utf-8", errors="ignore")

    require("encode_4ppm" in codec and "decode_4ppm" in codec, "M2_4PPM_ENCODE_DECODE_PRESENT", errors)
    require("CNT_CHIP_MAX" in codec and "CNT_PREAMBLE" in codec and "DETECT_START_CYCLES" in codec, "M2_4PPM_PROFILE_PARAMS_PRESENT", errors)
    require("tx_pulse" in codec and "rx_pulse_active" in codec, "M2_4PPM_ABSTRACT_PULSE_INTERFACE", errors)
    require("session_bad_count" in frame and "lane_mask_bad_count" in frame, "M2_FRAME_SESSION_MASK_COUNTERS_PRESENT", errors)
    require("crc_bad_count" in frame and "payload_len_bad_count" in frame, "M2_FRAME_CRC_LENGTH_COUNTERS_PRESENT", errors)
    require("TB_TFDU_4PPM_CODEC_PASS=1" in codec_tb, "M2_4PPM_TB_PASS_MARKER_PRESENT", errors)
    require("tfdu6102_behavior_model" in model_tb and "rx_pulse_active(~model_rxd)" in model_tb, "M2_4PPM_TFDU_MODEL_INSTANTIATED", errors)
    require("TB_TFDU_4PPM_MODEL_INTEGRATION_PASS=1" in model_tb, "M2_4PPM_MODEL_INTEGRATION_TB_PASS_MARKER_PRESENT", errors)
    require("TB_LANE0_FRAME_CRC_PASS=1" in frame_tb, "M2_FRAME_TB_PASS_MARKER_PRESENT", errors)

    enc = {0: 0b1000, 1: 0b0100, 2: 0b0010, 3: 0b0001}
    dec = {v: k for k, v in enc.items()}
    require(all(dec[enc[i]] == i for i in range(4)), "M2_4PPM_REFERENCE_ROUNDTRIP_PASS", errors)

    good = build_frame(0x2201, 0x01, bytes(range(8)))
    good_result = validate_frame(good, 0x2201, 0x01)
    bad_crc = bytearray(good)
    bad_crc[-4] ^= 0x01
    session_bad = validate_frame(build_frame(0x2202, 0x01, bytes(range(8))), 0x2201, 0x01)
    mask_bad = validate_frame(build_frame(0x2201, 0x02, bytes(range(8))), 0x2201, 0x01)
    len_bad = validate_frame(good[:-1], 0x2201, 0x01)
    require(all(good_result.values()), "M2_FRAME_REFERENCE_GOOD_PASS", errors)
    require(not validate_frame(bytes(bad_crc), 0x2201, 0x01)["crc_ok"], "M2_FRAME_REFERENCE_CRC_BAD_DETECTED", errors)
    require(not session_bad["session_ok"], "M2_FRAME_REFERENCE_SESSION_BAD_DETECTED", errors)
    require(not mask_bad["lane_mask_ok"], "M2_FRAME_REFERENCE_MASK_BAD_DETECTED", errors)
    require(not len_bad["payload_len_ok"], "M2_FRAME_REFERENCE_LENGTH_BAD_DETECTED", errors)

    print(f"M2_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
