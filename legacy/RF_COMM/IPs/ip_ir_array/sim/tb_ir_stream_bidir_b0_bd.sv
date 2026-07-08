`timescale 1ns/1ps

module tb_ir_stream_bidir_b0_bd;
  localparam int RAW_PACKET_BYTES  = 255;
  localparam int APP_PAYLOAD_BYTES = 247;
  localparam int FRAGMENT_BYTES    = 128;
  localparam int CNT_CHIP_MAX      = 15;
  localparam int MAX_FRAGS         = 2;
  localparam int PACKETS_A_TO_B    = 16;
  localparam int PACKETS_B_TO_A    = 16;
`ifdef TB_B2A_ECHO_ENABLE
  localparam int B2A_ECHO_ENABLE = 1;
`else
  localparam int B2A_ECHO_ENABLE = 0;
`endif
`ifdef TB_B_DEBUG_SELECT_RX_STATUS
  localparam int B_DEBUG_SELECT_RX_STATUS = 1;
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
  logic [0:0] a_ir_tx_out;
  logic [0:0] a_ir_rx_in;
  logic [0:0] a_ir_sd;
  logic [0:0] a_ir_mode_out;
  logic [0:0] a_lane_tx_busy;
  logic [0:0] unused_lane_pulse_a;
  logic [0:0] unused_rx_pulse_a;
  logic [0:0] unused_crc_a;
  logic [0:0] unused_err_a;
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

  logic b_ir_tx_out;
  logic b_ir_rx_in;
  logic b_ir_sd;
  logic b_ir_mode_out;
  logic [31:0] debug_b;
  logic b_rx_debug_active_seen;

  int a_tx_done_count;
  int a_rx_packet_count;
  int a_rx_byte_idx;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in[0] = ~b_ir_tx_out;
  assign b_ir_rx_in    = ~a_ir_tx_out[0];

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
        8:  a_payload_byte = 8'h01;
        9:  a_payload_byte = 8'h00;
        10: a_payload_byte = 8'h00;
        11: a_payload_byte = 8'h00;
        12: a_payload_byte = ~seq_f[7:0];
        13: a_payload_byte = ~seq_f[15:8];
        14: a_payload_byte = 8'hff;
        15: a_payload_byte = 8'hff;
        default: a_payload_byte = (seq_f[7:0] + (idx * 17) + 8'h01) & 8'hff;
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

  function automatic logic [7:0] expected_b2a_raw_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    begin
      if (B2A_ECHO_ENABLE != 0) begin
        expected_b2a_raw_byte = a_raw_byte(idx, seq_f);
      end else begin
        expected_b2a_raw_byte = b_raw_byte(idx, seq_f);
      end
    end
  endfunction

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
    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (200) @(posedge clk);

    for (int pkt = 1; pkt <= PACKETS_A_TO_B; pkt++) begin
      send_a_packet(pkt);
      if (B2A_ECHO_ENABLE != 0) begin
        wait (a_rx_packet_count >= pkt);
        repeat (200) @(posedge clk);
      end
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      a_tx_done_count <= 0;
      a_rx_packet_count <= 0;
      a_rx_byte_idx <= 0;
      b_rx_debug_active_seen <= 1'b0;
    end else begin
      if (a_tx_done) a_tx_done_count <= a_tx_done_count + 1;
      if ((B_DEBUG_SELECT_RX_STATUS != 0) && debug_b[31]) begin
        b_rx_debug_active_seen <= 1'b1;
      end

      if (a_tx_overflow || a_tx_exhaust || a_rx_header_error ||
          a_rx_protocol_error || a_rx_frame_overflow_any ||
          a_rx_crc_error_any || a_rx_overrun_any) begin
        $fatal(1, "Unexpected stream B0 error debug_a=%08x debug_b=%08x", debug_a, debug_b);
      end

      if (a_rx_valid && a_rx_ready) begin
        if (a_rx_packet_count < PACKETS_B_TO_A) begin
          if (a_rx_byte_idx >= RAW_PACKET_BYTES) $fatal(1, "A received too many B bytes");
          if (a_rx_data !== expected_b2a_raw_byte(a_rx_byte_idx, a_rx_packet_count + 1)) begin
            $fatal(1, "B-to-A raw mismatch pkt=%0d byte=%0d exp=%02x got=%02x",
                   a_rx_packet_count + 1, a_rx_byte_idx,
                   expected_b2a_raw_byte(a_rx_byte_idx, a_rx_packet_count + 1), a_rx_data);
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

  ir_stream_array_top #(
    .LANE_COUNT(1),
    .NODE_ID(0),
    .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAGS(MAX_FRAGS),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(64),
    .FRAG_TIMEOUT_CYCLES(120000),
    .TX_TO_RX_GUARD_CYCLES(1408),
    .BACKOFF_SLOT_CYCLES(1024),
    .REASSEMBLY_TIMEOUT_CYCLES(200000),
    .MAX_FRAME_BYTES(14 + FRAGMENT_BYTES)
  ) dut_a (
    .clk_phy(clk),
    .rst_n(rst_n),
    .enable(1'b1),
    .session_id(16'h2201),
    .lane_enable_mask(1'b1),
    .rx_lane_enable_mask(1'b1),
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
    .tx_frag_pending_dbg(unused_tx_pending_a),
    .tx_frag_inflight_dbg(unused_tx_inflight_a),
    .tx_frag_acked_dbg(unused_tx_acked_a),
    .rx_recv_bitmap_dbg(unused_rx_bitmap_a),
    .debug_status(debug_a)
  );

  ir_stream_bidir_b0_bd #(
    .B_CNT_CHIP_MAX(CNT_CHIP_MAX),
    .B_CNT_PREAMBLE(64),
    .B_RX_DATA_PHASE_DELAY_CYCLES(0),
    .B_RX_DETECT_START_CYCLES(2),
    .B_RX_DETECT_END_CYCLES(CNT_CHIP_MAX - 2),
    .B_RX_PREAMBLE_REALIGN_EDGE(0),
    .B_GUARD_CYCLES(1408),
    .B_BACKOFF_SLOT_CYCLES(100000),
    .B_START_IDLE_CYCLES(100000),
    .B_RECOVERY_RESET_CYCLES(2048),
    .B_DEBUG_SELECT_RX_STATUS(B_DEBUG_SELECT_RX_STATUS),
    .B2A_ECHO_ENABLE(B2A_ECHO_ENABLE),
    .RAW_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .APP_PAYLOAD_BYTES(APP_PAYLOAD_BYTES)
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
    repeat (12000000) begin
      @(posedge clk);
      if ((B_DEBUG_SELECT_RX_STATUS == 0) &&
          a_tx_done_count >= PACKETS_A_TO_B &&
          a_rx_packet_count >= PACKETS_B_TO_A &&
          debug_b[7:0] >= PACKETS_A_TO_B &&
          debug_b[15:8] >= PACKETS_B_TO_A) begin
        $display("IR_STREAM_BIDIR_B0_BD_PASS a_to_b=%0d b_to_a=%0d b_rx_good=%0d b_tx_done=%0d b_tx_start=%0d debug_b=%08x",
                 PACKETS_A_TO_B, PACKETS_B_TO_A, debug_b[7:0], debug_b[15:8], debug_b[23:16], debug_b);
        $finish;
      end else if ((B_DEBUG_SELECT_RX_STATUS != 0) &&
          a_tx_done_count >= PACKETS_A_TO_B &&
          a_rx_packet_count >= PACKETS_B_TO_A &&
          dut_b.u_core.rx_good_count >= PACKETS_A_TO_B &&
          dut_b.u_core.ack_tx_lane0_count >= PACKETS_A_TO_B &&
          b_rx_debug_active_seen) begin
        $display("IR_STREAM_BIDIR_B0_BD_PASS debug_select=%0d a_to_b=%0d b_to_a=%0d b_rx_good=%0d b_ack_lane0=%0d rx_debug_seen=%0b debug_b=%08x",
                 B_DEBUG_SELECT_RX_STATUS, PACKETS_A_TO_B, PACKETS_B_TO_A,
                 dut_b.u_core.rx_good_count, dut_b.u_core.ack_tx_lane0_count,
                 b_rx_debug_active_seen, debug_b);
        $finish;
      end
    end

    $fatal(1, "Timeout waiting for stream B0 pass a_tx_done=%0d a_rx_packets=%0d debug_b=%08x",
           a_tx_done_count, a_rx_packet_count, debug_b);
  end
endmodule
