#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ArqModel:
    session: int = 0x2201
    payload_lane_mask: int = 0x01
    ack_lane_mask: int = 0x01
    expected_ack_lane_mask: int = 0x01
    timeout: int = 4
    max_retry: int = 2
    busy: bool = False
    active_sequence: int = 0
    next_sequence: int = 0
    last_acked_sequence: int | None = None
    retry_count: int = 0
    timeout_counter: int = 0
    tx_attempt_count: int = 0
    ack_seen_count: int = 0
    retry_exhausted_count: int = 0
    ack_timeout_count: int = 0
    ack_session_bad_count: int = 0
    ack_lane_mask_bad_count: int = 0
    ack_duplicate_count: int = 0
    ack_expired_count: int = 0
    ack_late_count: int = 0
    retry_exhausted_sticky: bool = False

    def start(self) -> None:
        assert self.payload_lane_mask and self.ack_lane_mask and self.expected_ack_lane_mask
        assert not self.busy
        self.busy = True
        self.active_sequence = self.next_sequence
        self.retry_count = 0
        self.timeout_counter = 0
        self.tx_attempt_count += 1

    def ack(self, session: int, sequence: int, lane_mask: int, complete: bool = True) -> None:
        if not self.busy:
            self.ack_late_count += 1
            if session == self.session and self.last_acked_sequence == sequence:
                self.ack_duplicate_count += 1
            return
        if session != self.session:
            self.ack_session_bad_count += 1
            return
        if self.last_acked_sequence == sequence:
            self.ack_duplicate_count += 1
            return
        if sequence != self.active_sequence:
            self.ack_expired_count += 1
            return
        lane_ok = (lane_mask & self.ack_lane_mask) != 0 and (lane_mask & self.expected_ack_lane_mask) == self.expected_ack_lane_mask
        if not lane_ok:
            self.ack_lane_mask_bad_count += 1
            return
        if complete:
            self.ack_seen_count += 1
            self.last_acked_sequence = self.active_sequence
            self.next_sequence = (self.active_sequence + 1) & 0xFFFF
            self.busy = False
            self.timeout_counter = 0

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


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


def main() -> int:
    errors: list[str] = []
    rtl = (ROOT / "rtl/ir_arq_l2.sv").read_text(encoding="utf-8", errors="ignore")
    tb = (ROOT / "sim/tb/tb_lane0_ack_only.sv").read_text(encoding="utf-8", errors="ignore")
    crc_ref_script = (ROOT / "scripts/generate_m3_crc_bad_ack_reference.py").read_text(encoding="utf-8", errors="ignore")
    crc_ref_path = ROOT / "evidence/generated/m3_crc_bad_ack_reference.md"
    crc_ref = crc_ref_path.read_text(encoding="utf-8", errors="ignore") if crc_ref_path.exists() else ""

    require("payload_lane_mask" in rtl and "ack_lane_mask" in rtl, "M3_PAYLOAD_ACK_MASKS_SEPARATE", errors)
    require("retry_exhausted_sticky" in rtl and "retry_exhausted_count" in rtl, "M3_RETRY_EXHAUSTED_STICKY_PRESENT", errors)
    require("ack_session_bad_count" in rtl, "M3_ACK_SESSION_BAD_OBSERVABLE", errors)
    require("ack_duplicate_count" in rtl, "M3_ACK_DUPLICATE_OBSERVABLE", errors)
    require("ack_expired_count" in rtl, "M3_ACK_EXPIRED_OBSERVABLE", errors)
    require("ack_late_count" in rtl, "M3_ACK_LATE_OBSERVABLE", errors)
    require("retry_timeout_cycles" in rtl and "max_retry" in rtl, "M3_TIMEOUT_RETRY_PROFILED", errors)
    require("TB_LANE0_ACK_ONLY_PASS=1" in tb, "M3_ACK_ONLY_TB_PASS_MARKER_PRESENT", errors)
    require(
        "crc_bad_detected" in crc_ref_script and "ack_suppressed" in crc_ref_script,
        "M3_CRC_BAD_ACK_REFERENCE_SCRIPT_PRESENT",
        errors,
    )
    require(
        "M3_CRC_BAD_ACK_SUPPRESSION_REPORT=1" in crc_ref
        and "M3_CRC_BAD_ACK_REFERENCE=PASS" in crc_ref,
        "M3_CRC_BAD_ACK_REFERENCE_REPORT_PRESENT",
        errors,
    )

    model = ArqModel()
    model.start()
    require(model.tx_attempt_count == 1 and model.active_sequence == 0, "M3_REFERENCE_START_TX_PASS", errors)
    model.ack(0x2201, 0, 0x01)
    require((not model.busy) and model.ack_seen_count == 1 and model.next_sequence == 1, "M3_REFERENCE_ACK_SEEN_PASS", errors)
    model.ack(0x2201, 0, 0x01)
    require(model.ack_duplicate_count == 1 and model.ack_late_count == 1, "M3_REFERENCE_DUPLICATE_LATE_ACK_PASS", errors)
    model.start()
    model.ack(0x2202, 1, 0x01)
    model.ack(0x2201, 0x00FF, 0x01)
    model.ack(0x2201, 1, 0x02)
    require(model.ack_session_bad_count == 1, "M3_REFERENCE_SESSION_BAD_PASS", errors)
    require(model.ack_expired_count == 1, "M3_REFERENCE_EXPIRED_ACK_PASS", errors)
    require(model.ack_lane_mask_bad_count == 1, "M3_REFERENCE_ACK_MASK_BAD_PASS", errors)
    model.ack(0x2201, 1, 0x01)
    require(model.ack_seen_count == 2, "M3_REFERENCE_SECOND_ACK_PASS", errors)
    model.start()
    for _ in range(20):
        model.tick()
    require(model.retry_exhausted_sticky and model.retry_exhausted_count == 1, "M3_REFERENCE_RETRY_EXHAUSTED_PASS", errors)
    require(model.ack_timeout_count >= 3 and model.tx_attempt_count >= 5, "M3_REFERENCE_RETRY_ACCOUNTING_PASS", errors)
    require("M3_CRC_BAD_FRAME_DETECTED=1" in crc_ref, "M3_REFERENCE_CRC_BAD_FRAME_DETECTED", errors)
    require("M3_CRC_BAD_ACK_SUPPRESSED=1" in crc_ref, "M3_REFERENCE_CRC_BAD_ACK_SUPPRESSED", errors)
    require("M3_CRC_BAD_RETRY_EXHAUSTED=1" in crc_ref, "M3_REFERENCE_CRC_BAD_RETRY_EXHAUSTED", errors)

    print(f"M3_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
