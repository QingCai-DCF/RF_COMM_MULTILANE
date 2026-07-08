`timescale 1ns/1ps

module tb_ir_payload_throughput_budget;
  import ir_protocol_pkg::*;

  localparam int FRAGMENT_BYTES       = 16;
  localparam int MAX_PACKET_BYTES     = 256;
  localparam int MAX_FRAGS            = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int ACK_BITMAP_BYTES     = (MAX_FRAGS + 7) / 8;
  localparam int DATA_FRAME_BYTES     = IRP_DATA_HDR_BYTES + FRAGMENT_BYTES;
  localparam int ACK_FRAME_BYTES      = IRP_ACK_HDR_BYTES + ACK_BITMAP_BYTES;
  localparam int MAX_PROTOCOL_FRAGMENT_BYTES = 255;
  localparam int SWEEP_PACKET_BYTES   = 16384;
  localparam int CNT_CHIP_MAX         = 7;
  localparam int CHIP_CYCLES          = CNT_CHIP_MAX + 1;
  localparam int CHIPS_PER_SYMBOL     = 4;
  localparam int BITS_PER_SYMBOL      = 2;
  localparam int CNT_PREAMBLE         = 16;
  localparam int PREAMBLE_GAP_SYMS    = 1;
  localparam int PHY_CRC_SYMBOLS      = 16;
  localparam int EOF_SILENCE_SYMS     = 3;
  localparam int HALF_DUPLEX_LANES    = 8;
  localparam int FDX_LANES_PER_DIR    = 4;

  localparam real CLK_FREQ_HZ         = 64_000_000.0;
  localparam real RAW_PHY_MBPS        = (BITS_PER_SYMBOL * CLK_FREQ_HZ) /
                                        (CHIPS_PER_SYMBOL * CHIP_CYCLES * 1_000_000.0);
  localparam real HALF_RAW_MBPS       = RAW_PHY_MBPS * HALF_DUPLEX_LANES;
  localparam real FDX_RAW_MBPS        = RAW_PHY_MBPS * FDX_LANES_PER_DIR;
  localparam real HALF_TARGET_MBPS    = 32.0;
  localparam real FDX_TARGET_MBPS     = 16.0;

  function automatic real frame_airtime_us(input int frame_bytes);
    int total_symbols;
    real symbol_time_us;
    begin
      total_symbols = CNT_PREAMBLE + PREAMBLE_GAP_SYMS + (frame_bytes * 4) + PHY_CRC_SYMBOLS + EOF_SILENCE_SYMS;
      symbol_time_us = (CHIPS_PER_SYMBOL * CHIP_CYCLES * 1_000_000.0) / CLK_FREQ_HZ;
      frame_airtime_us = total_symbols * symbol_time_us;
    end
  endfunction

  function automatic real payload_mbps_per_lane(input int payload_bytes, input int frame_bytes);
    real airtime_us;
    begin
      airtime_us = frame_airtime_us(frame_bytes);
      payload_mbps_per_lane = (payload_bytes * 8.0) / airtime_us;
    end
  endfunction

  function automatic int min_lanes_for_target(input real per_lane_mbps, input real target_mbps);
    int lanes;
    begin
      min_lanes_for_target = -1;
      for (lanes = 1; lanes <= 64; lanes++) begin
        if ((per_lane_mbps * lanes) >= target_mbps) begin
          min_lanes_for_target = lanes;
          break;
        end
      end
    end
  endfunction

  function automatic int ceil_div(input int num, input int den);
    begin
      ceil_div = (num + den - 1) / den;
    end
  endfunction

  function automatic real packet_ack_payload_mbps_per_lane(input int fragment_bytes, input int packet_bytes);
    int fragments;
    int ack_bitmap_bytes;
    real data_airtime;
    real ack_airtime;
    real packet_airtime;
    begin
      fragments = ceil_div(packet_bytes, fragment_bytes);
      ack_bitmap_bytes = ceil_div(fragments, 8);
      data_airtime = frame_airtime_us(IRP_DATA_HDR_BYTES + fragment_bytes);
      ack_airtime = frame_airtime_us(IRP_ACK_HDR_BYTES + ack_bitmap_bytes);
      packet_airtime = (fragments * data_airtime) + ack_airtime;
      packet_ack_payload_mbps_per_lane = (packet_bytes * 8.0) / packet_airtime;
    end
  endfunction

  real data_airtime_us;
  real ack_airtime_us;
  real payload_per_lane_mbps;
  real half_payload_upper_mbps;
  real fdx_payload_upper_mbps;
  int  half_payload_lanes_needed;
  int  fdx_payload_lanes_needed;
  real max_fragment_payload_per_lane_mbps;
  real max_fragment_half_no_ack_mbps;
  real max_fragment_fdx_no_ack_mbps;
  real best_packet_ack_per_lane_mbps;
  real best_packet_ack_half_mbps;
  real best_packet_ack_fdx_mbps;
  int  meets_16_8_packet_ack_count;
  int  meets_32_16_packet_ack_count;
  int  sweep_fragment_bytes [0:5];
  int  sweep_packet_bytes [0:3];

  initial begin
    sweep_fragment_bytes[0] = 16;
    sweep_fragment_bytes[1] = 32;
    sweep_fragment_bytes[2] = 64;
    sweep_fragment_bytes[3] = 128;
    sweep_fragment_bytes[4] = 247;
    sweep_fragment_bytes[5] = 255;
    sweep_packet_bytes[0] = 256;
    sweep_packet_bytes[1] = 1024;
    sweep_packet_bytes[2] = 4096;
    sweep_packet_bytes[3] = 16384;

    data_airtime_us = frame_airtime_us(DATA_FRAME_BYTES);
    ack_airtime_us = frame_airtime_us(ACK_FRAME_BYTES);
    payload_per_lane_mbps = payload_mbps_per_lane(FRAGMENT_BYTES, DATA_FRAME_BYTES);
    half_payload_upper_mbps = payload_per_lane_mbps * HALF_DUPLEX_LANES;
    fdx_payload_upper_mbps = payload_per_lane_mbps * FDX_LANES_PER_DIR;
    half_payload_lanes_needed = min_lanes_for_target(payload_per_lane_mbps, HALF_TARGET_MBPS);
    fdx_payload_lanes_needed = min_lanes_for_target(payload_per_lane_mbps, FDX_TARGET_MBPS);
    max_fragment_payload_per_lane_mbps =
      payload_mbps_per_lane(MAX_PROTOCOL_FRAGMENT_BYTES, IRP_DATA_HDR_BYTES + MAX_PROTOCOL_FRAGMENT_BYTES);
    max_fragment_half_no_ack_mbps = max_fragment_payload_per_lane_mbps * HALF_DUPLEX_LANES;
    max_fragment_fdx_no_ack_mbps = max_fragment_payload_per_lane_mbps * FDX_LANES_PER_DIR;
    best_packet_ack_per_lane_mbps = 0.0;
    meets_16_8_packet_ack_count = 0;
    meets_32_16_packet_ack_count = 0;

    for (int fi = 0; fi < 6; fi++) begin
      for (int pi = 0; pi < 4; pi++) begin
        real packet_ack_per_lane;
        real half_packet_ack;
        real fdx_packet_ack;
        if (sweep_packet_bytes[pi] >= sweep_fragment_bytes[fi]) begin
          packet_ack_per_lane = packet_ack_payload_mbps_per_lane(sweep_fragment_bytes[fi], sweep_packet_bytes[pi]);
          half_packet_ack = packet_ack_per_lane * HALF_DUPLEX_LANES;
          fdx_packet_ack = packet_ack_per_lane * FDX_LANES_PER_DIR;
          if (packet_ack_per_lane > best_packet_ack_per_lane_mbps) begin
            best_packet_ack_per_lane_mbps = packet_ack_per_lane;
          end
          if ((half_packet_ack >= 16.0) && (fdx_packet_ack >= 8.0)) begin
            meets_16_8_packet_ack_count++;
          end
          if ((half_packet_ack >= HALF_TARGET_MBPS) && (fdx_packet_ack >= FDX_TARGET_MBPS)) begin
            meets_32_16_packet_ack_count++;
          end
        end
      end
    end
    best_packet_ack_half_mbps = best_packet_ack_per_lane_mbps * HALF_DUPLEX_LANES;
    best_packet_ack_fdx_mbps = best_packet_ack_per_lane_mbps * FDX_LANES_PER_DIR;

    if ((DATA_FRAME_BYTES != 30) || (ACK_FRAME_BYTES != 14) || (MAX_FRAGS != 16)) begin
      $fatal(1,
        "Unexpected protocol budget constants data_frame_bytes=%0d ack_frame_bytes=%0d max_frags=%0d",
        DATA_FRAME_BYTES, ACK_FRAME_BYTES, MAX_FRAGS);
    end
    if ((RAW_PHY_MBPS < 3.999) || (RAW_PHY_MBPS > 4.001) ||
        (HALF_RAW_MBPS < 31.999) || (HALF_RAW_MBPS > 32.001) ||
        (FDX_RAW_MBPS < 15.999) || (FDX_RAW_MBPS > 16.001)) begin
      $fatal(1,
        "Raw PHY target mismatch raw=%0.6f half_raw=%0.6f fdx_raw=%0.6f",
        RAW_PHY_MBPS, HALF_RAW_MBPS, FDX_RAW_MBPS);
    end

    // With nonzero protocol/PHY overhead, effective payload cannot equal raw
    // line rate. This assertion keeps the current 32/16 Mbit/s evidence clearly
    // classified as raw-PHY capacity, not payload throughput evidence.
    if ((half_payload_upper_mbps >= HALF_TARGET_MBPS) ||
        (fdx_payload_upper_mbps >= FDX_TARGET_MBPS)) begin
      $fatal(1,
        "Throughput model no longer shows the expected raw-vs-payload gap half_payload=%0.6f fdx_payload=%0.6f",
        half_payload_upper_mbps, fdx_payload_upper_mbps);
    end
    if ((max_fragment_half_no_ack_mbps >= HALF_TARGET_MBPS) ||
        (max_fragment_fdx_no_ack_mbps >= FDX_TARGET_MBPS) ||
        (meets_32_16_packet_ack_count != 0)) begin
      $fatal(1,
        "Protocol max fragment unexpectedly reaches 32/16 payload target max_no_ack_half=%0.6f max_no_ack_fdx=%0.6f meets_32_16_count=%0d",
        max_fragment_half_no_ack_mbps, max_fragment_fdx_no_ack_mbps, meets_32_16_packet_ack_count);
    end
    if ((best_packet_ack_half_mbps < 28.9) || (best_packet_ack_half_mbps > 29.1) ||
        (best_packet_ack_fdx_mbps < 14.4) || (best_packet_ack_fdx_mbps > 14.6) ||
        (meets_16_8_packet_ack_count != 18)) begin
      $fatal(1,
        "Unexpected packet-ACK sweep result best_half=%0.6f best_fdx=%0.6f meets_16_8=%0d",
        best_packet_ack_half_mbps, best_packet_ack_fdx_mbps, meets_16_8_packet_ack_count);
    end

    $display("IR_PAYLOAD_THROUGHPUT_BUDGET_PASS clk_mhz=64.000 fragment_bytes=%0d data_frame_bytes=%0d ack_frame_bytes=%0d raw_mbps_per_lane=%0.6f half_raw_mbps=%0.6f fdx_raw_mbps_per_dir=%0.6f data_frame_airtime_us=%0.3f ack_frame_airtime_us=%0.3f payload_upper_mbps_per_lane_no_ack=%0.6f half_payload_upper_mbps_no_ack=%0.6f fdx_payload_upper_mbps_per_dir_no_ack=%0.6f half_payload_lanes_needed_no_ack=%0d fdx_payload_lanes_per_dir_needed_no_ack=%0d max_fragment_bytes=%0d max_fragment_half_payload_no_ack_mbps=%0.6f max_fragment_fdx_payload_no_ack_mbps=%0.6f best_packet_ack_half_mbps=%0.6f best_packet_ack_fdx_mbps=%0.6f meets_16_8_packet_ack_count=%0d meets_32_16_packet_ack_count=%0d current_rate_evidence=raw_phy_only",
      FRAGMENT_BYTES, DATA_FRAME_BYTES, ACK_FRAME_BYTES, RAW_PHY_MBPS,
      HALF_RAW_MBPS, FDX_RAW_MBPS, data_airtime_us, ack_airtime_us,
      payload_per_lane_mbps, half_payload_upper_mbps, fdx_payload_upper_mbps,
      half_payload_lanes_needed, fdx_payload_lanes_needed,
      MAX_PROTOCOL_FRAGMENT_BYTES, max_fragment_half_no_ack_mbps, max_fragment_fdx_no_ack_mbps,
      best_packet_ack_half_mbps, best_packet_ack_fdx_mbps,
      meets_16_8_packet_ack_count, meets_32_16_packet_ack_count);
    $finish;
  end
endmodule
