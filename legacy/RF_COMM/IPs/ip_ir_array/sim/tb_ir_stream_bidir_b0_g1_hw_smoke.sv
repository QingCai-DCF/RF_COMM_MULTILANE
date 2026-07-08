`timescale 1ns/1ps

module tfdu_edge_channel_model_g1 #(
  parameter int DELAY_CYCLES = 4,
  parameter int PULSE_CYCLES = 4
)(
  input  logic clk,
  input  logic rst_n,
  input  logic tx_in,
  output logic rx_out_n
);
  localparam int DELAY_W = (DELAY_CYCLES <= 0) ? 1 : DELAY_CYCLES;
  logic [DELAY_W:0] edge_pipe;
  logic tx_in_d;
  int unsigned low_count;
  logic delayed_edge;

  assign delayed_edge = edge_pipe[DELAY_W];

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      edge_pipe <= '0;
      tx_in_d   <= 1'b0;
      low_count <= 0;
      rx_out_n  <= 1'b1;
    end else begin
      tx_in_d   <= tx_in;
      edge_pipe <= {edge_pipe[DELAY_W-1:0], tx_in && !tx_in_d};

      if (delayed_edge) begin
        low_count <= (PULSE_CYCLES > 0) ? (PULSE_CYCLES - 1) : 0;
      end else if (low_count != 0) begin
        low_count <= low_count - 1;
      end

      rx_out_n <= !(delayed_edge || (low_count != 0));
    end
  end
endmodule

module tb_ir_stream_bidir_b0_g1_hw_smoke;
  localparam int LANE_COUNT       = 2;
  localparam int RAW_PACKET_BYTES = 264;
  localparam int APP_PAYLOAD_BYTES = 256;
`ifdef TB_G1_FRAG_FULL
  localparam int FRAGMENT_BYTES   = (RAW_PACKET_BYTES > 255) ? 255 : RAW_PACKET_BYTES;
`else
  localparam int FRAGMENT_BYTES   = 64;
`endif
  localparam int MAX_FRAGS        = (RAW_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
`ifdef TB_CNT15
  localparam int CNT_CHIP_MAX     = 15;
`else
  localparam int CNT_CHIP_MAX     = 7;
`endif
  localparam int CNT_PREAMBLE     = 16;
`ifdef TB_RX_DETECT_LATE
  localparam int RX_DETECT_START  = 3;
  localparam int RX_DETECT_END    = (CNT_CHIP_MAX >= 7) ? 7 : CNT_CHIP_MAX;
`else
  localparam int RX_DETECT_START  = 0;
  localparam int RX_DETECT_END    = (CNT_CHIP_MAX >= 15) ? 10 : ((CNT_CHIP_MAX >= 7) ? (CNT_CHIP_MAX - 2) : CNT_CHIP_MAX);
`endif
`ifdef TB_RX_REALIGN_ON
  localparam int RX_REALIGN_EDGE  = 1;
`else
  localparam int RX_REALIGN_EDGE  = 0;
`endif
  localparam int PACKETS_A_TO_B   = 4;
  localparam int EXPECTED_ACKS    = PACKETS_A_TO_B * MAX_FRAGS;
`ifdef TB_G1_GUARD_1408
  localparam int G1_GUARD_CYCLES  = 1408;
`else
  localparam int G1_GUARD_CYCLES  = 4096;
`endif
`ifdef TB_B_DEBUG_SELECT_RX_STATUS
  localparam int B_DEBUG_SELECT_RX_STATUS = 1;
`elsif TB_B_DEBUG_SELECT_STREAM
  localparam int B_DEBUG_SELECT_RX_STATUS = 3;
`else
  localparam int B_DEBUG_SELECT_RX_STATUS = 0;
`endif

  logic clk;
  logic rst_n;
  logic a_tx_valid;
  logic a_tx_ready;
  logic a_tx_last;
  logic [7:0] a_tx_data;
  logic a_rx_valid;
  logic a_rx_ready;
  logic a_rx_last;
  logic [7:0] a_rx_data;
  logic [LANE_COUNT-1:0] a_ir_tx_out;
  logic [LANE_COUNT-1:0] a_ir_rx_in;
  logic [LANE_COUNT-1:0] a_ir_sd;
  logic [LANE_COUNT-1:0] a_ir_mode_out;
  logic [LANE_COUNT-1:0] a_lane_tx_busy;
  logic [LANE_COUNT-1:0] unused_lane_pulse_a;
  logic [LANE_COUNT-1:0] unused_rx_pulse_a;
  logic [LANE_COUNT-1:0] unused_crc_a;
  logic [LANE_COUNT-1:0] unused_err_a;
  logic [MAX_FRAGS-1:0] a_tx_pending;
  logic [MAX_FRAGS-1:0] a_tx_inflight;
  logic [MAX_FRAGS-1:0] a_tx_acked;
  logic [MAX_FRAGS-1:0] a_rx_bitmap;
  logic a_tx_done;
  logic a_tx_overflow;
  logic a_tx_exhaust;
  logic a_rx_done;
  logic a_rx_header_error;
  logic a_rx_protocol_error;
  logic a_rx_frame_overflow_any;
  logic a_rx_crc_error_any;
  logic a_rx_overrun_any;
  logic unused_rx_ctx_valid_a;
  logic unused_rx_ctx_complete_a;
  logic [31:0] debug_a;

  logic [LANE_COUNT-1:0] b_ir_tx_out;
  logic [LANE_COUNT-1:0] b_ir_rx_in;
  logic [LANE_COUNT-1:0] b_ir_sd;
  logic [LANE_COUNT-1:0] b_ir_mode_out;
  logic [31:0] debug_b;

  int a_tx_done_count;
  time start_time;
  time done_time;
  longint duration_ns;
  longint app_mbps_x1000;
  longint raw_mbps_x1000;

  always #7.8125 clk = ~clk;

`ifdef TB_DIRECT_WIRE
  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];
`else
  tfdu_edge_channel_model_g1 #(
    .DELAY_CYCLES(4),
    .PULSE_CYCLES(4)
  ) ch_b_to_a (
    .clk(clk),
    .rst_n(rst_n),
    .tx_in(b_ir_tx_out[0]),
    .rx_out_n(a_ir_rx_in[0])
  );

  tfdu_edge_channel_model_g1 #(
    .DELAY_CYCLES(4),
    .PULSE_CYCLES(4)
  ) ch_a_to_b (
    .clk(clk),
    .rst_n(rst_n),
    .tx_in(a_ir_tx_out[0]),
    .rx_out_n(b_ir_rx_in[0])
  );
`endif

  assign a_ir_rx_in[1] = 1'b1;
  assign b_ir_rx_in[1] = 1'b1;

  function automatic logic [7:0] a_payload_byte(
    input int idx,
    input logic [31:0] seq_f
  );
    begin
      case (idx)
        0:  a_payload_byte = "P";
        1:  a_payload_byte = "S";
        2:  a_payload_byte = "P";
        3:  a_payload_byte = "S";
        4:  a_payload_byte = seq_f[7:0];
        5:  a_payload_byte = seq_f[15:8];
        6:  a_payload_byte = seq_f[23:16];
        7:  a_payload_byte = seq_f[31:24];
        8:  a_payload_byte = 8'h01;
        9:  a_payload_byte = 8'h00;
        10: a_payload_byte = 8'h00;
        11: a_payload_byte = 8'h00;
        12: a_payload_byte = ~seq_f[7:0];
        13: a_payload_byte = ~seq_f[15:8];
        14: a_payload_byte = ~seq_f[23:16];
        15: a_payload_byte = ~seq_f[31:24];
        default: a_payload_byte = (seq_f[7:0] + (idx * 17) + 8'h01) & 8'hff;
      endcase
    end
  endfunction

  function automatic logic [7:0] a_raw_byte(
    input int idx,
    input logic [31:0] seq_f
  );
    int payload_idx;
    begin
      payload_idx = idx - 8;
      case (idx)
        0: a_raw_byte = "I";
        1: a_raw_byte = "R";
        2: a_raw_byte = "P";
        3: a_raw_byte = "1";
        4: a_raw_byte = seq_f[7:0];
        5: a_raw_byte = seq_f[15:8];
        6: a_raw_byte = APP_PAYLOAD_BYTES[7:0];
        7: a_raw_byte = APP_PAYLOAD_BYTES[15:8];
        default: a_raw_byte = a_payload_byte(payload_idx, seq_f);
      endcase
    end
  endfunction

  task automatic send_a_packet(input logic [31:0] seq_f);
    begin
      for (int k = 0; k < RAW_PACKET_BYTES; k++) begin
        @(negedge clk);
        a_tx_data  = a_raw_byte(k, seq_f);
        a_tx_valid = 1'b1;
        a_tx_last  = (k == RAW_PACKET_BYTES - 1);
        do @(posedge clk); while (!a_tx_ready);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
    end
  endtask

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    a_tx_data = 8'h00;
    a_rx_ready = 1'b1;
    start_time = 0;
    done_time = 0;
    duration_ns = 0;
    app_mbps_x1000 = 0;
    raw_mbps_x1000 = 0;
`ifdef TB_DIRECT_WIRE
    $display("G1_HW_SMOKE_SIM_MODE direct_wire=1 b_debug_select=%0d cnt=%0d detect=%0d..%0d realign=%0d guard=%0d",
             B_DEBUG_SELECT_RX_STATUS, CNT_CHIP_MAX, RX_DETECT_START, RX_DETECT_END, RX_REALIGN_EDGE,
             G1_GUARD_CYCLES);
`else
    $display("G1_HW_SMOKE_SIM_MODE direct_wire=0 b_debug_select=%0d cnt=%0d detect=%0d..%0d realign=%0d guard=%0d",
             B_DEBUG_SELECT_RX_STATUS, CNT_CHIP_MAX, RX_DETECT_START, RX_DETECT_END, RX_REALIGN_EDGE,
             G1_GUARD_CYCLES);
`endif
    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (200) @(posedge clk);

    start_time = $time;
    for (int pkt = 1; pkt <= PACKETS_A_TO_B; pkt++) begin
      send_a_packet(pkt);
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      a_tx_done_count <= 0;
    end else begin
      if (a_tx_done) a_tx_done_count <= a_tx_done_count + 1;

      if (a_tx_overflow || a_tx_exhaust || a_rx_header_error ||
          a_rx_protocol_error || a_rx_frame_overflow_any ||
          a_rx_crc_error_any || a_rx_overrun_any) begin
        $fatal(1,
          "Unexpected G1 HW-smoke stream error a_done=%0d a_pending=%05b a_acked=%05b a_dbg=%08x b_dbg=%08x",
          a_tx_done_count, a_tx_pending, a_tx_acked, debug_a, debug_b);
      end
    end
  end

  ir_stream_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .NODE_ID(0),
    .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAGS(MAX_FRAGS),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(CNT_PREAMBLE),
    .RX_DETECT_START_CYCLES(RX_DETECT_START),
    .RX_DETECT_END_CYCLES(RX_DETECT_END),
    .RX_PREAMBLE_REALIGN_EDGE(RX_REALIGN_EDGE),
    .FRAG_TIMEOUT_CYCLES(50000),
    .TX_TO_RX_GUARD_CYCLES(G1_GUARD_CYCLES),
    .BACKOFF_SLOT_CYCLES(1024),
    .REASSEMBLY_TIMEOUT_CYCLES(200000),
    .MAX_FRAME_BYTES(14 + FRAGMENT_BYTES)
  ) dut_a (
    .clk_phy(clk),
    .rst_n(rst_n),
    .enable(1'b1),
    .session_id(16'h2201),
    .lane_enable_mask(2'b01),
    .rx_lane_enable_mask(2'b01),
    .s_axis_tx_tdata(a_tx_data),
    .s_axis_tx_tvalid(a_tx_valid),
    .s_axis_tx_tready(a_tx_ready),
    .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data),
    .m_axis_rx_tvalid(a_rx_valid),
    .m_axis_rx_tready(a_rx_ready),
    .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out),
    .ir_rx_in(a_ir_rx_in),
    .ir_sd(a_ir_sd),
    .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(),
    .tx_packet_loading(),
    .tx_done_pulse(a_tx_done),
    .tx_error_overflow(a_tx_overflow),
    .tx_error_retry_exhausted(a_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_a),
    .rx_ctx_complete(unused_rx_ctx_complete_a),
    .rx_done_pulse(a_rx_done),
    .rx_header_error(a_rx_header_error),
    .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(a_rx_frame_overflow_any),
    .rx_crc_error_any(a_rx_crc_error_any),
    .rx_overrun_error_any(a_rx_overrun_any),
    .lane_tx_busy_dbg(a_lane_tx_busy),
    .lane_tx_load_pulse_dbg(unused_lane_pulse_a),
    .lane_rx_frame_pulse_dbg(unused_rx_pulse_a),
    .lane_rx_crc_error_dbg(unused_crc_a),
    .lane_rx_error_dbg(unused_err_a),
    .lane_rx_debug_status_dbg(),
    .tx_frag_pending_dbg(a_tx_pending),
    .tx_frag_inflight_dbg(a_tx_inflight),
    .tx_frag_acked_dbg(a_tx_acked),
    .rx_recv_bitmap_dbg(a_rx_bitmap),
    .debug_status(debug_a)
  );

  ir_stream_bidir_vec_bd #(
    .LANE_COUNT(LANE_COUNT),
    .B_SESSION_ID(16'h2201),
    .B_CNT_CHIP_MAX(CNT_CHIP_MAX),
    .B_CNT_PREAMBLE(CNT_PREAMBLE),
    .B_RX_DATA_PHASE_DELAY_CYCLES(0),
    .B_RX_DETECT_START_CYCLES(RX_DETECT_START),
    .B_RX_DETECT_END_CYCLES(RX_DETECT_END),
    .B_RX_PREAMBLE_REALIGN_EDGE(RX_REALIGN_EDGE),
    .B_GUARD_CYCLES(G1_GUARD_CYCLES),
    .B_BACKOFF_SLOT_CYCLES(1024),
    .B_START_IDLE_CYCLES(100000),
    .B_RECOVERY_RESET_CYCLES(2048),
    .B_PARALLEL_2LANE_MODE(0),
    .B_DEBUG_SELECT_RX_STATUS(B_DEBUG_SELECT_RX_STATUS),
    .B_ACK_LANE_MASK(1),
    .B_TX_LANE_MASK(1),
    .B_RX_LANE_MASK(1),
    .B_EXPECTED_A_LANE_MASK(1),
    .RAW_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .APP_PAYLOAD_BYTES(APP_PAYLOAD_BYTES),
    .B2A_ENABLE(0),
    .B2A_FREE_RUN(0),
    .TX_GAP_CYCLES(0)
  ) dut_b (
    .clk_phy(clk),
    .rst_n(rst_n),
    .ir_tx_out(b_ir_tx_out),
    .ir_rx_in(b_ir_rx_in),
    .ir_sd(b_ir_sd),
    .ir_mode_out(b_ir_mode_out),
    .debug_status(debug_b)
  );

  initial begin
    repeat (16000000) begin
      @(posedge clk);
      if (a_tx_done_count >= PACKETS_A_TO_B &&
          dut_b.u_core.rx_good_count >= PACKETS_A_TO_B &&
          dut_b.u_core.ack_tx_lane0_count >= EXPECTED_ACKS &&
          a_tx_pending == '0 &&
          a_tx_acked == frag_mask_all()) begin
        done_time = $time;
        duration_ns = done_time - start_time;
        if (duration_ns <= 0) begin
          $fatal(1, "Invalid G1 HW-smoke elapsed time start=%0t done=%0t", start_time, done_time);
        end
        app_mbps_x1000 = (64'd1000000 * PACKETS_A_TO_B * APP_PAYLOAD_BYTES * 8) / duration_ns;
        raw_mbps_x1000 = (64'd1000000 * PACKETS_A_TO_B * RAW_PACKET_BYTES * 8) / duration_ns;
        $display("IR_STREAM_BIDIR_B0_G1_HW_SMOKE_PASS packets=%0d raw_bytes=%0d app_bytes=%0d frags=%0d elapsed_ns=%0d app_mbps=%0d.%03d raw_mbps=%0d.%03d a_done=%0d b_rx_good=%0d b_ack_lane0=%0d a_acked=%05b debug_a=%08x debug_b=%08x",
                 PACKETS_A_TO_B, RAW_PACKET_BYTES, APP_PAYLOAD_BYTES, MAX_FRAGS,
                 duration_ns, app_mbps_x1000 / 1000, app_mbps_x1000 % 1000,
                 raw_mbps_x1000 / 1000, raw_mbps_x1000 % 1000,
                 a_tx_done_count, dut_b.u_core.rx_good_count,
                 dut_b.u_core.ack_tx_lane0_count, a_tx_acked, debug_a, debug_b);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for G1 HW-smoke sim pass a_done=%0d b_rx_good=%0d b_ack_lane0=%0d a_pending=%05b a_inflight=%05b a_acked=%05b debug_a=%08x debug_b=%08x",
      a_tx_done_count, dut_b.u_core.rx_good_count, dut_b.u_core.ack_tx_lane0_count,
      a_tx_pending, a_tx_inflight, a_tx_acked, debug_a, debug_b);
  end

  function automatic logic [MAX_FRAGS-1:0] frag_mask_all;
    begin
      frag_mask_all = '1;
    end
  endfunction
endmodule
