#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "evidence" / "generated"


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def crc32_payload(data: bytes, crc: int = 0xFFFFFFFF) -> int:
    for byte in data:
        crc ^= byte
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
    header[9] = (len(payload) >> 8) & 0xFF
    header[10] = len(payload) & 0xFF
    header[11] = lane_mask & 0xFF
    header_crc = crc16_ccitt(header[:12])
    header[12] = header_crc & 0xFF
    header[13] = (header_crc >> 8) & 0xFF
    payload_crc = crc32_payload(payload)
    return bytes(header) + payload + payload_crc.to_bytes(4, "little")


def validate_frame(frame: bytes, expected_session: int, expected_lane_mask: int) -> dict[str, bool]:
    payload_len = frame[10] if len(frame) > 10 else 0
    payload_end = 14 + payload_len
    total_len = frame[8] | (frame[9] << 8) if len(frame) > 9 else -1
    session = frame[2] | (frame[3] << 8) if len(frame) > 3 else -1
    lane_mask = frame[11] if len(frame) > 11 else -1
    header_ok = len(frame) >= 18 and frame[0] == 0xA5 and frame[1] == 0x11
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


@dataclass
class ArqModel:
    timeout: int = 4
    max_retry: int = 2
    busy: bool = False
    retry_count: int = 0
    timeout_counter: int = 0
    tx_attempt_count: int = 0
    ack_seen_count: int = 0
    ack_timeout_count: int = 0
    retry_exhausted_count: int = 0
    retry_exhausted_sticky: bool = False

    def start(self) -> None:
        self.busy = True
        self.retry_count = 0
        self.timeout_counter = 0
        self.tx_attempt_count += 1

    def tick(self) -> None:
        if not self.busy:
            return
        if self.timeout_counter >= self.timeout - 1:
            self.ack_timeout_count += 1
            self.timeout_counter = 0
            if self.retry_count >= self.max_retry:
                self.retry_exhausted_sticky = True
                self.retry_exhausted_count += 1
                self.busy = False
            else:
                self.retry_count += 1
                self.tx_attempt_count += 1
        else:
            self.timeout_counter += 1


def main() -> int:
    good_frame = build_frame(0x2201, 0x01, bytes(range(16)))
    bad_crc_frame = bytearray(good_frame)
    bad_crc_frame[-4] ^= 0x01
    validation = validate_frame(bytes(bad_crc_frame), 0x2201, 0x01)
    crc_bad_detected = not validation["crc_ok"]
    ack_should_be_sent = all(validation.values())

    arq = ArqModel()
    arq.start()
    for _ in range(20):
        if ack_should_be_sent:
            arq.ack_seen_count += 1
            arq.busy = False
            break
        arq.tick()

    ack_suppressed = crc_bad_detected and arq.ack_seen_count == 0
    retry_exhausted = arq.retry_exhausted_sticky and arq.retry_exhausted_count == 1
    overall_pass = crc_bad_detected and ack_suppressed and retry_exhausted

    OUTDIR.mkdir(parents=True, exist_ok=True)
    data = {
        "marker": "M3_CRC_BAD_ACK_SUPPRESSION_REPORT",
        "status": "PASS" if overall_pass else "FAIL",
        "frame_validation": validation,
        "crc_bad_detected": crc_bad_detected,
        "ack_should_be_sent": ack_should_be_sent,
        "arq": {
            "tx_attempt_count": arq.tx_attempt_count,
            "ack_seen_count": arq.ack_seen_count,
            "ack_timeout_count": arq.ack_timeout_count,
            "retry_exhausted_count": arq.retry_exhausted_count,
            "retry_exhausted_sticky": arq.retry_exhausted_sticky,
        },
    }
    (OUTDIR / "m3_crc_bad_ack_reference.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# M3 CRC Bad ACK Suppression Reference",
        "",
        "M3_CRC_BAD_ACK_SUPPRESSION_REPORT=1",
        f"M3_CRC_BAD_FRAME_DETECTED={1 if crc_bad_detected else 0}",
        f"M3_CRC_BAD_ACK_SUPPRESSED={1 if ack_suppressed else 0}",
        f"M3_CRC_BAD_RETRY_EXHAUSTED={1 if retry_exhausted else 0}",
        f"M3_CRC_BAD_ACK_REFERENCE={'PASS' if overall_pass else 'FAIL'}",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| frame crc ok | {validation['crc_ok']} |",
        f"| ack sent | {ack_should_be_sent} |",
        f"| ARQ tx attempts | {arq.tx_attempt_count} |",
        f"| ARQ timeouts | {arq.ack_timeout_count} |",
        f"| ARQ retry exhausted | {arq.retry_exhausted_sticky} |",
        "",
        "This is an offline cross-layer reference for the lane0 ACK-only requirement: a CRC-bad L1 frame must not produce ACK, so L2 must observe ACK loss and exhaust retries according to the configured timeout/retry policy.",
        "",
    ]
    (OUTDIR / "m3_crc_bad_ack_reference.md").write_text("\n".join(lines), encoding="utf-8")

    print("M3_CRC_BAD_ACK_SUPPRESSION_REPORT=1")
    print(f"M3_CRC_BAD_FRAME_DETECTED={1 if crc_bad_detected else 0}")
    print(f"M3_CRC_BAD_ACK_SUPPRESSED={1 if ack_suppressed else 0}")
    print(f"M3_CRC_BAD_RETRY_EXHAUSTED={1 if retry_exhausted else 0}")
    print(f"M3_CRC_BAD_ACK_REFERENCE={'PASS' if overall_pass else 'FAIL'}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
