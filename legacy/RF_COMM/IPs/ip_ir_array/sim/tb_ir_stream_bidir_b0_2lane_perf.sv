`timescale 1ns/1ps

`ifdef TB_PKTS16
`define TB_PACKETS_PER_DIR_VALUE 16
`else
`define TB_PACKETS_PER_DIR_VALUE 64
`endif

`ifdef TB_CNT7
`define TB_CNT_CHIP_MAX_VALUE 7
`else
`define TB_CNT_CHIP_MAX_VALUE 15
`endif

`ifdef TB_REALIGN1
`define TB_RX_PREAMBLE_REALIGN_EDGE_VALUE 1
`else
`define TB_RX_PREAMBLE_REALIGN_EDGE_VALUE 0
`endif

`ifdef TB_OUTSTANDING_0
`define TB_MAX_OUTSTANDING_VALUE 0
`elsif TB_OUTSTANDING_2
`define TB_MAX_OUTSTANDING_VALUE 2
`elsif TB_OUTSTANDING_4
`define TB_MAX_OUTSTANDING_VALUE 4
`else
`define TB_MAX_OUTSTANDING_VALUE 1
`endif

`ifdef TB_A_GUARD_512
`define TB_A_GUARD_CYCLES_VALUE 512
`elsif TB_A_GUARD_1024
`define TB_A_GUARD_CYCLES_VALUE 1024
`else
`define TB_A_GUARD_CYCLES_VALUE 1408
`endif

`ifdef TB_A_BACKOFF_0
`define TB_A_BACKOFF_SLOT_CYCLES_VALUE 0
`else
`define TB_A_BACKOFF_SLOT_CYCLES_VALUE 1024
`endif

`ifdef TB_B_GUARD_512
`define TB_B_GUARD_CYCLES_VALUE 512
`elsif TB_B_GUARD_1024
`define TB_B_GUARD_CYCLES_VALUE 1024
`else
`define TB_B_GUARD_CYCLES_VALUE 1408
`endif

`ifdef TB_B_BACKOFF_0
`define TB_B_BACKOFF_SLOT_CYCLES_VALUE 0
`elsif TB_B_BACKOFF_1024
`define TB_B_BACKOFF_SLOT_CYCLES_VALUE 1024
`else
`define TB_B_BACKOFF_SLOT_CYCLES_VALUE 100000
`endif

`ifdef TB_B_START_IDLE_0
`define TB_B_START_IDLE_CYCLES_VALUE 0
`elsif TB_B_START_IDLE_1024
`define TB_B_START_IDLE_CYCLES_VALUE 1024
`else
`define TB_B_START_IDLE_CYCLES_VALUE 100000
`endif

`ifdef TB_A_PARALLEL_2LANE
`define TB_A_PARALLEL_2LANE_VALUE 1
`else
`define TB_A_PARALLEL_2LANE_VALUE 0
`endif

`ifdef TB_B_PARALLEL_2LANE
`define TB_B_PARALLEL_2LANE_VALUE 1
`else
`define TB_B_PARALLEL_2LANE_VALUE 0
`endif

`ifdef TB_A2B_ONLY
`define TB_B2A_ENABLE_VALUE 0
`else
`define TB_B2A_ENABLE_VALUE 1
`endif

`ifdef TB_B_ACK_LANE0
`define TB_B_ACK_LANE_MASK_VALUE 1
`else
`define TB_B_ACK_LANE_MASK_VALUE -1
`endif

module tb_ir_stream_bidir_b0_2lane_perf #(
  parameter int PACKETS_PER_DIR          = `TB_PACKETS_PER_DIR_VALUE,
  parameter int MAX_OUTSTANDING          = `TB_MAX_OUTSTANDING_VALUE,
  parameter int A_GUARD_CYCLES           = `TB_A_GUARD_CYCLES_VALUE,
  parameter int A_BACKOFF_SLOT_CYCLES    = `TB_A_BACKOFF_SLOT_CYCLES_VALUE,
  parameter int B_GUARD_CYCLES           = `TB_B_GUARD_CYCLES_VALUE,
  parameter int B_BACKOFF_SLOT_CYCLES    = `TB_B_BACKOFF_SLOT_CYCLES_VALUE,
  parameter int B_START_IDLE_CYCLES      = `TB_B_START_IDLE_CYCLES_VALUE,
  parameter int A_PARALLEL_2LANE_MODE    = `TB_A_PARALLEL_2LANE_VALUE,
  parameter int B_PARALLEL_2LANE_MODE    = `TB_B_PARALLEL_2LANE_VALUE,
  parameter int B2A_ENABLE               = `TB_B2A_ENABLE_VALUE,
  parameter int B_ACK_LANE_MASK          = `TB_B_ACK_LANE_MASK_VALUE
);
  localparam int LANE_COUNT        = 2;
  localparam int RAW_PACKET_BYTES  = 255;
  localparam int APP_PAYLOAD_BYTES = 247;
  localparam int FRAGMENT_BYTES    = 128;
  localparam int CNT_CHIP_MAX      = `TB_CNT_CHIP_MAX_VALUE;
  localparam int RX_DETECT_START   = (CNT_CHIP_MAX >= 15) ? 0 : ((CNT_CHIP_MAX >= 7) ? 2 : 0);
  localparam int RX_DETECT_END     = (CNT_CHIP_MAX >= 15) ? 10 : ((CNT_CHIP_MAX >= 7) ? (CNT_CHIP_MAX - 2) : CNT_CHIP_MAX);
  localparam int RX_PREAMBLE_REALIGN_EDGE = `TB_RX_PREAMBLE_REALIGN_EDGE_VALUE;
  localparam int MAX_FRAGS         = 2;
  localparam int MAX_FRAME_BYTES   = 14 + FRAGMENT_BYTES;
  localparam logic [31:0] LANE_MASK_U32 = (32'h0000_0001 << LANE_COUNT) - 1;

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
  logic [32*LANE_COUNT-1:0] unused_lane_debug_a;
  logic [MAX_FRAGS-1:0] unused_tx_pending_a;
  logic [MAX_FRAGS-1:0] unused_tx_inflight_a;
  logic [MAX_FRAGS-1:0] unused_tx_acked_a;
  logic [MAX_FRAGS-1:0] unused_rx_bitmap_a;
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
  int a_rx_packet_count;
  int a_rx_byte_idx;
  int a_tx_packet_sent;
  int halfduplex_overlap_count;
  int a_lane0_tx_load_count;
  int a_lane1_tx_load_count;

  real start_ns;
  real end_ns;
  real elapsed_us;
  real one_dir_mbps;
  real aggregate_mbps;
  bit measure_started;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];
  assign b_ir_rx_in[1] = ~a_ir_tx_out[1];
`ifdef TB_BREAK_LANE1_B2A
  assign a_ir_rx_in[1] = 1'b1;
`else
  assign a_ir_rx_in[1] = ~b_ir_tx_out[1];
`endif

  function automatic logic [7:0] a_payload_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    begin
      case (idx)
        0:  a_payload_byte = "P";
        1:  a_payload_byte = "S";
        2:  a_payload_byte = "P";
        3:  a_payload_byte = "S";
        4:  a_payload_byte = seq_f[7:0];
        5:  a_payload_byte = seq_f[15:8];
        6:  a_payload_byte = 8'h00;
        7:  a_payload_byte = 8'h00;
        8:  a_payload_byte = LANE_MASK_U32[7:0];
        9:  a_payload_byte = LANE_MASK_U32[15:8];
        10: a_payload_byte = LANE_MASK_U32[23:16];
        11: a_payload_byte = LANE_MASK_U32[31:24];
        12: a_payload_byte = ~seq_f[7:0];
        13: a_payload_byte = ~seq_f[15:8];
        14: a_payload_byte = 8'hff;
        15: a_payload_byte = 8'hff;
        default: a_payload_byte = (seq_f[7:0] + (idx * 17) + LANE_MASK_U32[7:0]) & 8'hff;
      endcase
    end
  endfunction

  function automatic logic [7:0] a_raw_byte(
    input int idx,
    input logic [15:0] seq_f
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

  function automatic logic [7:0] b_payload_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    begin
      case (idx)
        0:  b_payload_byte = "B";
        1:  b_payload_byte = "2";
        2:  b_payload_byte = "A";
        3:  b_payload_byte = "!";
        4:  b_payload_byte = seq_f[7:0];
        5:  b_payload_byte = seq_f[15:8];
        6:  b_payload_byte = 8'h01;
        7:  b_payload_byte = 8'h00;
        8:  b_payload_byte = ~seq_f[7:0];
        9:  b_payload_byte = ~seq_f[15:8];
        10: b_payload_byte = 8'hfe;
        11: b_payload_byte = 8'hff;
        12: b_payload_byte = 8'h42;
        13: b_payload_byte = 8'h44;
        14: b_payload_byte = 8'h4d;
        15: b_payload_byte = 8'h31;
        default: b_payload_byte = (seq_f[7:0] + (idx * 19) + 8'hb0) & 8'hff;
      endcase
    end
  endfunction

  function automatic logic [7:0] b_raw_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    int payload_idx;
    begin
      payload_idx = idx - 8;
      case (idx)
        0: b_raw_byte = "I";
        1: b_raw_byte = "R";
        2: b_raw_byte = "P";
        3: b_raw_byte = "1";
        4: b_raw_byte = seq_f[7:0];
        5: b_raw_byte = seq_f[15:8];
        6: b_raw_byte = APP_PAYLOAD_BYTES[7:0];
        7: b_raw_byte = APP_PAYLOAD_BYTES[15:8];
        default: b_raw_byte = b_payload_byte(payload_idx, seq_f);
      endcase
    end
  endfunction

  task automatic wait_for_outstanding_room(input int sent_count);
    begin
      while ((MAX_OUTSTANDING != 0) &&
             ((sent_count - a_rx_packet_count) >= MAX_OUTSTANDING)) begin
        @(posedge clk);
      end
    end
  endtask

  task automatic send_a_packet(input logic [15:0] seq_f);
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
    measure_started = 1'b0;

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (200) @(posedge clk);

    measure_started = 1'b1;
    start_ns = $realtime;
    for (int pkt = 1; pkt <= PACKETS_PER_DIR; pkt++) begin
      wait_for_outstanding_room(pkt - 1);
      send_a_packet(pkt[15:0]);
      a_tx_packet_sent = pkt;
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      a_tx_done_count <= 0;
      a_rx_packet_count <= 0;
      a_rx_byte_idx <= 0;
      a_tx_packet_sent <= 0;
      halfduplex_overlap_count <= 0;
      a_lane0_tx_load_count <= 0;
      a_lane1_tx_load_count <= 0;
    end else begin
      if (a_tx_done) a_tx_done_count <= a_tx_done_count + 1;
      if (unused_lane_pulse_a[0]) a_lane0_tx_load_count <= a_lane0_tx_load_count + 1;
      if (unused_lane_pulse_a[1]) a_lane1_tx_load_count <= a_lane1_tx_load_count + 1;

      if ((|a_ir_tx_out) && (|b_ir_tx_out)) begin
        halfduplex_overlap_count <= halfduplex_overlap_count + 1;
        $fatal(1, "Half-duplex overlap t=%0t a_tx=%b b_tx=%b debug_a=%08x debug_b=%08x",
               $time, a_ir_tx_out, b_ir_tx_out, debug_a, debug_b);
      end

      if (a_tx_overflow || a_tx_exhaust || a_rx_header_error ||
          a_rx_protocol_error || a_rx_frame_overflow_any ||
          a_rx_crc_error_any || a_rx_overrun_any) begin
        $fatal(1, "Unexpected 2lane B0 error tx_overflow=%0b tx_exhaust=%0b rx_header=%0b rx_protocol=%0b rx_frame_overflow=%0b rx_crc=%0b rx_overrun=%0b debug_a=%08x debug_b=%08x",
               a_tx_overflow, a_tx_exhaust, a_rx_header_error,
               a_rx_protocol_error, a_rx_frame_overflow_any,
               a_rx_crc_error_any, a_rx_overrun_any, debug_a, debug_b);
      end

      if (a_rx_valid && a_rx_ready) begin
        if (a_rx_packet_count < PACKETS_PER_DIR) begin
          if (a_rx_byte_idx >= RAW_PACKET_BYTES) $fatal(1, "A received too many B bytes");
          if (a_rx_data !== b_raw_byte(a_rx_byte_idx, a_rx_packet_count + 1)) begin
            $fatal(1, "B-to-A raw mismatch pkt=%0d byte=%0d exp=%02x got=%02x",
                   a_rx_packet_count + 1, a_rx_byte_idx,
                   b_raw_byte(a_rx_byte_idx, a_rx_packet_count + 1), a_rx_data);
          end
        end

        if (a_rx_last) begin
          if (a_rx_byte_idx != RAW_PACKET_BYTES - 1) $fatal(1, "B-to-A length mismatch");
          a_rx_packet_count <= a_rx_packet_count + 1;
          a_rx_byte_idx <= 0;
        end else begin
          a_rx_byte_idx <= a_rx_byte_idx + 1;
        end
      end
    end
  end

  generate
    if (A_PARALLEL_2LANE_MODE != 0) begin : g_a_parallel
      ir_stream_parallel_2lane_top #(
        .NODE_ID(0),
        .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_RETRY(4),
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .CNT_PREAMBLE(64),
        .RX_DATA_PHASE_DELAY_CYCLES(0),
        .RX_DETECT_START_CYCLES(RX_DETECT_START),
        .RX_DETECT_END_CYCLES(RX_DETECT_END),
        .RX_PREAMBLE_REALIGN_EDGE(RX_PREAMBLE_REALIGN_EDGE),
        .FRAG_TIMEOUT_CYCLES(120000),
        .TX_TO_RX_GUARD_CYCLES(A_GUARD_CYCLES),
        .BACKOFF_SLOT_CYCLES(A_BACKOFF_SLOT_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES(200000),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) dut_a (
        .clk_phy(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .session_id(16'h2203),
        .lane_enable_mask(2'b11),
        .rx_lane_enable_mask(2'b11),
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
        .lane_rx_debug_status_dbg(unused_lane_debug_a),
        .tx_frag_pending_dbg(unused_tx_pending_a),
        .tx_frag_inflight_dbg(unused_tx_inflight_a),
        .tx_frag_acked_dbg(unused_tx_acked_a),
        .rx_recv_bitmap_dbg(unused_rx_bitmap_a),
        .debug_status(debug_a)
      );
    end else begin : g_a_legacy
      ir_stream_array_top #(
        .LANE_COUNT(LANE_COUNT),
        .NODE_ID(0),
        .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_RETRY(4),
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .CNT_PREAMBLE(64),
        .RX_DATA_PHASE_DELAY_CYCLES(0),
        .RX_DETECT_START_CYCLES(0),
        .RX_DETECT_END_CYCLES(10),
        .RX_PREAMBLE_REALIGN_EDGE(0),
        .FRAG_TIMEOUT_CYCLES(120000),
        .TX_TO_RX_GUARD_CYCLES(A_GUARD_CYCLES),
        .BACKOFF_SLOT_CYCLES(A_BACKOFF_SLOT_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES(200000),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) dut_a (
        .clk_phy(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .session_id(16'h2203),
        .lane_enable_mask({LANE_COUNT{1'b1}}),
        .rx_lane_enable_mask({LANE_COUNT{1'b1}}),
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
        .lane_rx_debug_status_dbg(unused_lane_debug_a),
        .tx_frag_pending_dbg(unused_tx_pending_a),
        .tx_frag_inflight_dbg(unused_tx_inflight_a),
        .tx_frag_acked_dbg(unused_tx_acked_a),
        .rx_recv_bitmap_dbg(unused_rx_bitmap_a),
        .debug_status(debug_a)
      );
    end
  endgenerate

  ir_stream_bidir_vec_bd #(
    .LANE_COUNT(LANE_COUNT),
    .B_SESSION_ID(16'h2203),
    .B_CNT_CHIP_MAX(CNT_CHIP_MAX),
    .B_CNT_PREAMBLE(64),
    .B_RX_DATA_PHASE_DELAY_CYCLES(0),
    .B_RX_DETECT_START_CYCLES(RX_DETECT_START),
    .B_RX_DETECT_END_CYCLES(RX_DETECT_END),
    .B_RX_PREAMBLE_REALIGN_EDGE(RX_PREAMBLE_REALIGN_EDGE),
    .B_GUARD_CYCLES(B_GUARD_CYCLES),
    .B_BACKOFF_SLOT_CYCLES(B_BACKOFF_SLOT_CYCLES),
    .B_START_IDLE_CYCLES(B_START_IDLE_CYCLES),
    .B_RECOVERY_RESET_CYCLES(2048),
    .B_PARALLEL_2LANE_MODE(B_PARALLEL_2LANE_MODE),
    .B_ACK_LANE_MASK(B_ACK_LANE_MASK),
    .RAW_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .APP_PAYLOAD_BYTES(APP_PAYLOAD_BYTES),
    .B2A_ENABLE(B2A_ENABLE)
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
    repeat (80000000) begin
      @(posedge clk);
      if (measure_started &&
`ifdef TB_A2B_ONLY
          a_tx_done_count >= PACKETS_PER_DIR &&
          debug_b[7:0] >= PACKETS_PER_DIR[7:0] &&
          a_lane1_tx_load_count > 0) begin
`else
          a_tx_done_count >= PACKETS_PER_DIR &&
          a_rx_packet_count >= PACKETS_PER_DIR) begin
`endif
        end_ns = $realtime;
        elapsed_us = (end_ns - start_ns) / 1000.0;
        one_dir_mbps = (PACKETS_PER_DIR * APP_PAYLOAD_BYTES * 8.0) / elapsed_us;
        aggregate_mbps = one_dir_mbps * 2.0;
        $display("IR_STREAM_BIDIR_B0_2LANE_PERF_PASS packets_each_direction=%0d app_payload_bytes=%0d elapsed_us=%0.3f one_dir_mbps=%0.6f aggregate_mbps=%0.6f cnt_chip_max=%0d max_outstanding=%0d a_guard=%0d a_backoff=%0d b_guard=%0d b_backoff=%0d b_start_idle=%0d a_parallel=%0d b_parallel=%0d b2a_enable=%0d b_ack_lane_mask=%0d a_lane0_loads=%0d a_lane1_loads=%0d halfduplex_overlaps=%0d debug_a=%08x debug_b=%08x",
                 PACKETS_PER_DIR, APP_PAYLOAD_BYTES, elapsed_us, one_dir_mbps,
                 aggregate_mbps, CNT_CHIP_MAX, MAX_OUTSTANDING, A_GUARD_CYCLES,
                 A_BACKOFF_SLOT_CYCLES, B_GUARD_CYCLES, B_BACKOFF_SLOT_CYCLES,
                  B_START_IDLE_CYCLES, A_PARALLEL_2LANE_MODE,
                  B_PARALLEL_2LANE_MODE, B2A_ENABLE, B_ACK_LANE_MASK,
                  a_lane0_tx_load_count, a_lane1_tx_load_count,
                  halfduplex_overlap_count, debug_a, debug_b);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for 2lane B0 perf pass sent=%0d a_tx_done=%0d a_rx_packets=%0d a_lane0_loads=%0d a_lane1_loads=%0d debug_a=%08x debug_b=%08x",
      a_tx_packet_sent, a_tx_done_count, a_rx_packet_count,
      a_lane0_tx_load_count, a_lane1_tx_load_count, debug_a, debug_b);
  end
endmodule
