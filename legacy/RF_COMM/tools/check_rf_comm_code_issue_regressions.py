#!/usr/bin/env python3
"""Static regression checks for RF_COMM code issues found in review."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "IPs/ip_ir_array/src/ir_stream_array_top.sv"
SIM_RUNNER = ROOT / "IPs/ip_ir_array/run_loopback_single_lane.ps1"
ACK_MASK_ZERO_TB = ROOT / "IPs/ip_ir_array/sim/tb_ir_stream_ack_mask_zero.sv"
PS_MAIN = ROOT / "software/ps_ps_loopback/src/main.c"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def find_function(text: str, name: str) -> str:
    match = re.search(
        rf"function\s+automatic\s+logic\s+{re.escape(name)}\b(?P<body>.*?)endfunction",
        text,
        flags=re.S,
    )
    require(match is not None, f"missing {name}()")
    return match.group("body")


def main() -> int:
    rtl = RTL.read_text(encoding="utf-8")
    sim_runner = SIM_RUNNER.read_text(encoding="utf-8")
    ack_mask_zero_tb = ACK_MASK_ZERO_TB.read_text(encoding="utf-8")
    ps_main = PS_MAIN.read_text(encoding="utf-8")

    ack_fn = find_function(rtl, "find_ack_lane")
    enabled_fn = find_function(rtl, "find_enabled_lane")

    require("next_ack_lane" not in rtl, "stale next_ack_lane() fallback helper remains")
    require("next_enabled_lane" not in rtl, "stale next_enabled_lane() index-only helper remains")
    require("output logic [LANE_W-1:0] lane_o" in ack_fn, "find_ack_lane() must return a valid bit plus lane_o")
    require("ACK_LANE_MASK[cand]" in ack_fn, "find_ack_lane() must gate on ACK_LANE_MASK")
    require("find_enabled_lane" not in ack_fn, "find_ack_lane() must not fall back to an enabled data lane")
    require("output logic [LANE_W-1:0] lane_o" in enabled_fn, "find_enabled_lane() must return a valid bit plus lane_o")

    require(
        "found_ack_lane_valid_v = find_ack_lane(parse_lane, found_ack_lane_v);" in rtl,
        "data RX must check ACK lane validity before setting ack_pending",
    )
    require(
        re.search(
            r"if\s*\(found_ack_lane_valid_v\).*?ack_pending\s*<=\s*1'b1.*?ack_lane\s*<=\s*found_ack_lane_v.*?else\s+begin\s*ack_pending\s*<=\s*1'b0",
            rtl,
            flags=re.S,
        )
        is not None,
        "ACK pending must only be set when a valid ACK lane exists",
    )
    require(
        "lane_enable_mask[ack_lane] && ACK_LANE_MASK[ack_lane]" in rtl,
        "ACK transmit wait state must re-check ACK_LANE_MASK",
    )

    require(
        "found_tx_lane_valid_v = find_enabled_lane(tx_lane_rr, found_tx_lane_v);" in rtl,
        "data TX must validate that a lane is enabled before transmitting",
    )
    require(
        re.search(r"tx_payload_offset\s*=", rtl) is None,
        "tx_payload_offset must not be assigned with blocking assignment",
    )

    require(
        "selected_tx_first_byte = (ack_hdr_idx == '0);" in rtl,
        "ACK debug load pulse must be qualified by ack_hdr_idx",
    )
    require(
        "lane_tx_load_pulse_dbg[tx_active_lane] = selected_tx_valid && selected_tx_ready && selected_tx_first_byte;" in rtl,
        "lane_tx_load_pulse_dbg must use the state-specific first-byte qualifier",
    )
    require(
        "lane_tx_load_pulse_dbg[tx_active_lane] = selected_tx_valid && selected_tx_ready && (tx_hdr_idx == 0)" not in rtl,
        "stale byte-level ACK debug count expression remains",
    )

    require(
        "expected_ack_bitmap_bytes_v = ack_bitmap_bytes_fn(header_frag_count_v);" in rtl,
        "ACK parser must compute expected bitmap length from fragment count",
    )
    require(
        "(header_ack_bitmap_bytes_v != expected_ack_bitmap_bytes_v)" in rtl,
        "ACK parser must reject bitmap length mismatches",
    )
    require(
        re.search(
            r"\bparse_(session|seq|frag_idx|frag_count|total_len|payload_len|payload_idx|payload_offset|ack_bitmap_bytes|ack_complete)\s*(?<![<>=!])=(?!=)",
            rtl,
        )
        is None,
        "RX parser registers must not be written with blocking assignment",
    )
    require(
        re.search(r"rx_mux_tlast\s*!=\s*\(parse_ack_bitmap_bytes\s*==\s*0\)", rtl) is None,
        "ACK parser must not allow zero-length bitmap ACKs",
    )

    require("stream_ack_mask_zero" in sim_runner, "ACK-mask-zero simulation must stay in the runner")
    require("IR_STREAM_ACK_MASK_ZERO_PASS" in sim_runner, "ACK-mask-zero pass marker must stay in the runner")
    require(".ACK_LANE_MASK(1'b0)" in ack_mask_zero_tb, "ACK-mask-zero testbench must disable B ACKs")
    require("B transmitted with ACK_LANE_MASK=0" in ack_mask_zero_tb, "ACK-mask-zero testbench must fail on B TX")
    require("IR_STREAM_ACK_MASK_ZERO_PASS" in ack_mask_zero_tb, "ACK-mask-zero testbench pass marker is missing")

    require("#define PSPS_PAYLOAD_BYTES        16u" in ps_main, "default PSPS_PAYLOAD_BYTES must be at least 16")
    require("#if PSPS_PAYLOAD_BYTES < 16u" in ps_main, "PS payload length compile-time guard is missing")
    require('make_payload()' in ps_main, "PS payload guard message should identify make_payload()")

    print("RF_COMM_CODE_ISSUE_REGRESSIONS_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"RF_COMM_CODE_ISSUE_REGRESSIONS_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
