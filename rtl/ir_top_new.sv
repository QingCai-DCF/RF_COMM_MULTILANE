`timescale 1ns/1ps
`ifdef P4_AUTO_LANE0_FRAME_CRC
`define P4_AUTO_LANE_PROTOCOL_SMOKE
`endif
`ifdef P4_AUTO_LANE0_ACK_RETRY
`define P4_AUTO_LANE_PROTOCOL_SMOKE
`define P4_AUTO_ACK_RETRY
`endif
`ifdef P4_AUTO_LANE1_FRAME_CRC
`define P4_AUTO_LANE_PROTOCOL_SMOKE
`define P4_AUTO_PROTOCOL_LANE1
`endif
`ifdef P4_AUTO_LANE1_ACK_RETRY
`define P4_AUTO_LANE_PROTOCOL_SMOKE
`define P4_AUTO_PROTOCOL_LANE1
`define P4_AUTO_ACK_RETRY
`endif
`ifdef P4_AUTO_TWO_LANE_MINIMAL
`define P4_AUTO_LANE_PROTOCOL_SMOKE
`define P4_AUTO_PROTOCOL_TWO_LANE
`define P4_AUTO_ACK_RETRY
`endif
`ifdef P4_AUTO_TWO_LANE_300S_SOAK
`define P4_AUTO_LANE_PROTOCOL_SMOKE
`define P4_AUTO_PROTOCOL_TWO_LANE
`define P4_AUTO_ACK_RETRY
`define P4_AUTO_PROTOCOL_SOAK
`endif
`ifdef P4_AUTO_LANE0_300S_SOAK
`define P4_AUTO_LANE_PROTOCOL_SMOKE
`define P4_AUTO_ACK_RETRY
`define P4_AUTO_PROTOCOL_SOAK
`endif

module ir_top_new (
  output logic [1:0] ir_mode_out_0,
  input  logic [1:0] ir_rx_in_0,
  output logic [1:0] ir_sd_0,
  output logic [1:0] ir_tx_out_0,
  output logic [1:0] loop_mode_b0,
  input  logic [1:0] loop_rx_b0,
  output logic [1:0] loop_sd_b0,
  output logic [1:0] loop_tx_b0
);
  (* keep = "true", mark_debug = "true" *) logic p4_auto_cfgmclk;
  (* keep = "true", mark_debug = "true" *) logic p4_auto_eos;
  (* keep = "true", mark_debug = "true" *) logic [24*32-1:0] p4_auto_status_words_flat;
  logic [3:0] p4_auto_probe_mode_cmd;
  logic [3:0] p4_auto_probe_sd_cmd;
  logic [3:0] p4_auto_probe_txd_cmd;
  logic [3:0] p4_auto_probe_rxd_pin;
  logic [3:0] p4_auto_lane_enable;
  logic [3:0] p4_auto_startup_done;
  logic p4_auto_extra_status_words_valid;
  logic [8*32-1:0] p4_auto_extra_status_words_flat;
`ifdef P6_LOCAL_TRANSPORT
  logic [31:0] p6_local_commit_count;
  logic [31:0] p6_local_debug_status;
  logic [7:0] p6_local_payload_lane_mask;
  logic [7:0] p6_local_rx_lane_mask;
  logic [7:0] p6_local_ack_lane_mask;
  logic [15:0] p6_local_session;
  logic [15:0] p6_local_payload_len;
  logic [15:0] p6_local_fragment_bytes;
  logic [15:0] p6_local_cnt_chip_max;
  logic [15:0] p6_local_cnt_preamble;
  logic [7:0] p6_local_detect_start;
  logic [7:0] p6_local_detect_end;
  logic [31:0] p6_local_guard_cycles;
  logic [31:0] p6_local_retry_timeout;
  logic [15:0] p6_local_startup_us;
  logic [31:0] p6_local_duty_window;
  logic [15:0] p6_local_duty_max_permille;
  logic [15:0] p6_local_stuck_high_limit_us;
`endif
`ifdef P4_AUTO_TFDU_CONTROL_IDLE
  localparam logic [31:0] P4_AUTO_STARTUP_WAIT_CYCLES = 32'd32000;
  logic [31:0] p4_auto_startup_wait_counter;
`elsif P4_AUTO_RAW_PULSE_L0
  localparam logic [31:0] P4_AUTO_STARTUP_WAIT_CYCLES = 32'd32000;
  localparam logic [31:0] P4_AUTO_RAW_POST_START_DELAY_CYCLES = 32'd64000;
  localparam logic [31:0] P4_AUTO_RAW_PULSE_HIGH_CYCLES = 32'd8;
  localparam logic [31:0] P4_AUTO_RAW_PULSE_GAP_CYCLES = 32'd640000;
  localparam logic [15:0] P4_AUTO_RAW_PULSE_COUNT = 16'd16;
  logic [31:0] p4_auto_startup_wait_counter;
  logic [31:0] p4_auto_raw_delay_counter;
  logic [31:0] p4_auto_raw_pulse_cycle_counter;
  logic [15:0] p4_auto_raw_pulse_counter;
  logic p4_auto_raw_txd_lane0;
  logic p4_auto_raw_sequence_done;
`elsif P4_AUTO_RAW_LANE_MATRIX
  localparam logic [31:0] P4_AUTO_STARTUP_WAIT_CYCLES = 32'd32000;
  localparam logic [31:0] P4_AUTO_RAW_POST_START_DELAY_CYCLES = 32'd64000;
  localparam logic [31:0] P4_AUTO_RAW_PULSE_HIGH_CYCLES = 32'd8;
  localparam logic [31:0] P4_AUTO_RAW_PULSE_GAP_CYCLES = 32'd640000;
  localparam logic [15:0] P4_AUTO_RAW_PULSE_COUNT = 16'd64;
  logic [31:0] p4_auto_startup_wait_counter;
  logic [31:0] p4_auto_raw_delay_counter;
  logic [31:0] p4_auto_raw_pulse_cycle_counter;
  logic [15:0] p4_auto_raw_pulse_counter;
  logic [1:0] p4_auto_raw_matrix_step;
  logic [3:0] p4_auto_raw_matrix_txd;
  logic [3:0] p4_auto_raw_matrix_rxd_sync_0;
  logic [3:0] p4_auto_raw_matrix_rxd_sync_1;
  logic [3:0] p4_auto_raw_matrix_rxd_prev;
  logic [15:0] p4_auto_matrix_tx_ab_l0;
  logic [15:0] p4_auto_matrix_tx_ba_l0;
  logic [15:0] p4_auto_matrix_tx_ab_l1;
  logic [15:0] p4_auto_matrix_tx_ba_l1;
  logic [15:0] p4_auto_matrix_rx_ab_l0;
  logic [15:0] p4_auto_matrix_rx_ba_l0;
  logic [15:0] p4_auto_matrix_rx_ab_l1;
  logic [15:0] p4_auto_matrix_rx_ba_l1;
  logic p4_auto_raw_sequence_done;
`elsif P4_AUTO_LANE_PROTOCOL_SMOKE
  localparam logic [31:0] P4_AUTO_STARTUP_WAIT_CYCLES = 32'd32000;
`ifdef P4_AUTO_PROTOCOL_SOAK
  localparam logic [31:0] P4_AUTO_PROTO_POST_START_DELAY_CYCLES = 32'd640000;
`else
  localparam logic [31:0] P4_AUTO_PROTO_POST_START_DELAY_CYCLES = 32'd640000;
`endif
`ifdef P4_AUTO_PROTOCOL_SOAK
  localparam logic [31:0] P4_AUTO_PROTO_FRAME_GAP_CYCLES = 32'd64000000;
`else
  localparam logic [31:0] P4_AUTO_PROTO_FRAME_GAP_CYCLES = 32'd640000;
`endif
  localparam int P4_AUTO_PROTO_PREAMBLE_SYMBOLS = 16;
  localparam int P4_AUTO_PROTO_FRAME_BYTES = 34;
  localparam int P4_AUTO_ACK_FRAME_BYTES = 7;
  localparam int P4_AUTO_PROTO_MAX_FRAME_BYTES = 64;
  localparam int P4_AUTO_PROTO_PAYLOAD_BYTES = 16;
  localparam int P4_AUTO_PROTO_CHIP_CYCLES = 32;
  localparam int P4_AUTO_PROTO_TX_PULSE_CYCLES = 8;
  localparam int P4_AUTO_PROTO_SYMBOL_CYCLES = P4_AUTO_PROTO_CHIP_CYCLES * 4;
  localparam int P4_AUTO_PROTO_FRAME_SYMBOLS =
      P4_AUTO_PROTO_PREAMBLE_SYMBOLS + (P4_AUTO_PROTO_FRAME_BYTES * 4);
  localparam int P4_AUTO_ACK_FRAME_SYMBOLS =
      P4_AUTO_PROTO_PREAMBLE_SYMBOLS + (P4_AUTO_ACK_FRAME_BYTES * 4);
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
  localparam logic [3:0] P4_AUTO_PROTO_ENABLED_MASK = 4'hF;
  localparam logic [7:0] P4_AUTO_PROTO_LANE_MASK_BYTE = 8'h03;
  localparam int P4_AUTO_PROTO_DATA_RX_INDEX = 2;
  localparam int P4_AUTO_PROTO_ACK_RX_INDEX = 0;
  localparam logic [31:0] P4_AUTO_PROTO_FRAME_STAGE_MAGIC = 32'h324c4d4e; // "2LMN"
`ifdef P4_AUTO_PROTOCOL_SOAK
  localparam logic [31:0] P4_AUTO_PROTO_ACK_STAGE_MAGIC = 32'h324c534b; // "2LSK"
`else
  localparam logic [31:0] P4_AUTO_PROTO_ACK_STAGE_MAGIC = 32'h324c4152; // "2LAR"
`endif
`elsif P4_AUTO_PROTOCOL_LANE1
  localparam logic [3:0] P4_AUTO_PROTO_ENABLED_MASK = 4'hA;
  localparam logic [7:0] P4_AUTO_PROTO_LANE_MASK_BYTE = 8'h02;
  localparam int P4_AUTO_PROTO_DATA_RX_INDEX = 3;
  localparam int P4_AUTO_PROTO_ACK_RX_INDEX = 1;
  localparam logic [31:0] P4_AUTO_PROTO_FRAME_STAGE_MAGIC = 32'h4c314643; // "L1FC"
  localparam logic [31:0] P4_AUTO_PROTO_ACK_STAGE_MAGIC = 32'h4c314152; // "L1AR"
`else
  localparam logic [3:0] P4_AUTO_PROTO_ENABLED_MASK = 4'h5;
  localparam logic [7:0] P4_AUTO_PROTO_LANE_MASK_BYTE = 8'h01;
  localparam int P4_AUTO_PROTO_DATA_RX_INDEX = 2;
  localparam int P4_AUTO_PROTO_ACK_RX_INDEX = 0;
  localparam logic [31:0] P4_AUTO_PROTO_FRAME_STAGE_MAGIC = 32'h4c304643; // "L0FC"
`ifdef P4_AUTO_PROTOCOL_SOAK
  localparam logic [31:0] P4_AUTO_PROTO_ACK_STAGE_MAGIC = 32'h4c30534b; // "L0SK"
`else
  localparam logic [31:0] P4_AUTO_PROTO_ACK_STAGE_MAGIC = 32'h4c304152; // "L0AR"
`endif
`endif
`ifdef P4_AUTO_PROTOCOL_SOAK
  localparam logic [7:0] P4_AUTO_PROTO_ACK_MASK_BYTE = P4_AUTO_PROTO_LANE_MASK_BYTE;
  localparam logic [15:0] P4_AUTO_PROTO_FRAME_COUNT = 16'd1800;
`elsif P4_AUTO_ACK_RETRY
  localparam logic [7:0] P4_AUTO_PROTO_ACK_MASK_BYTE = P4_AUTO_PROTO_LANE_MASK_BYTE;
  localparam logic [15:0] P4_AUTO_PROTO_FRAME_COUNT = 16'd100;
`else
  localparam logic [7:0] P4_AUTO_PROTO_ACK_MASK_BYTE = 8'h00;
  localparam logic [15:0] P4_AUTO_PROTO_FRAME_COUNT = 16'd100;
`endif
  typedef enum logic [3:0] {
    P4_AUTO_PROTO_WAIT_STARTUP,
    P4_AUTO_PROTO_POST_DELAY,
    P4_AUTO_PROTO_START_ARQ,
    P4_AUTO_PROTO_TX_FRAME,
    P4_AUTO_PROTO_FRAME_GAP,
    P4_AUTO_PROTO_WAIT_ACK_TX,
    P4_AUTO_PROTO_TX_ACK,
    P4_AUTO_PROTO_DONE
  } p4_auto_proto_state_t;
  p4_auto_proto_state_t p4_auto_proto_state;
  logic [31:0] p4_auto_startup_wait_counter;
  logic [31:0] p4_auto_proto_delay_counter;
  logic [31:0] p4_auto_proto_gap_counter;
  logic [15:0] p4_auto_proto_tx_frame_count;
  logic [8:0] p4_auto_proto_tx_symbol_index;
  logic [6:0] p4_auto_proto_tx_symbol_cycle;
  logic p4_auto_proto_txd_lane0;
  logic p4_auto_proto_sequence_done;
  logic [1:0] p4_auto_proto_tx_symbol_value;
  logic [1:0] p4_auto_proto_tx_chip_index;
  logic [4:0] p4_auto_proto_tx_chip_subcycle;
  logic p4_auto_proto_rx_align;
  logic p4_auto_proto_rx_pulse_active;
  logic [1:0] p4_auto_proto_rx_symbol;
  logic p4_auto_proto_rx_symbol_valid;
  logic p4_auto_proto_rx_symbol_error;
  logic p4_auto_proto_rx_preamble_valid;
  logic [15:0] p4_auto_proto_rx_preamble_count;
  logic [8*P4_AUTO_PROTO_MAX_FRAME_BYTES-1:0] p4_auto_proto_rx_frame_data;
  logic [5:0] p4_auto_proto_rx_byte_index;
  logic [1:0] p4_auto_proto_rx_symbol_in_byte;
  logic p4_auto_proto_rx_collecting;
  logic p4_auto_proto_rx_validate_pending;
  logic p4_auto_proto_frame_validate;
  logic [31:0] p4_auto_proto_rx_symbol_error_count;
  logic [31:0] p4_auto_proto_preamble_seen_count;
  logic [31:0] p4_auto_proto_payload_mismatch_count;
  logic p4_auto_proto_payload_mismatch_now;
  logic p4_auto_proto_frame_good_pulse;
  logic p4_auto_proto_frame_bad_pulse;
  logic p4_auto_proto_crc_bad_pulse;
  logic p4_auto_proto_payload_len_bad_pulse;
  logic [31:0] p4_auto_proto_frame_good_count;
  logic [31:0] p4_auto_proto_frame_bad_count;
  logic [31:0] p4_auto_proto_crc_bad_count;
  logic [31:0] p4_auto_proto_payload_len_bad_count;
  logic [31:0] p4_auto_proto_frame_debug_status;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
  logic p4_auto_proto_l1_rx_align;
  logic p4_auto_proto_l1_rx_pulse_active;
  logic [1:0] p4_auto_proto_l1_rx_symbol;
  logic p4_auto_proto_l1_rx_symbol_valid;
  logic p4_auto_proto_l1_rx_symbol_error;
  logic p4_auto_proto_l1_rx_preamble_valid;
  logic [15:0] p4_auto_proto_l1_rx_preamble_count;
  logic [8*P4_AUTO_PROTO_MAX_FRAME_BYTES-1:0] p4_auto_proto_l1_rx_frame_data;
  logic [5:0] p4_auto_proto_l1_rx_byte_index;
  logic [1:0] p4_auto_proto_l1_rx_symbol_in_byte;
  logic p4_auto_proto_l1_rx_collecting;
  logic p4_auto_proto_l1_rx_validate_pending;
  logic p4_auto_proto_l1_frame_validate;
  logic [31:0] p4_auto_proto_l1_rx_symbol_error_count;
  logic [31:0] p4_auto_proto_l1_preamble_seen_count;
  logic [31:0] p4_auto_proto_l1_payload_mismatch_count;
  logic p4_auto_proto_l1_payload_mismatch_now;
  logic p4_auto_proto_l1_frame_good_pulse;
  logic p4_auto_proto_l1_frame_bad_pulse;
  logic p4_auto_proto_l1_crc_bad_pulse;
  logic p4_auto_proto_l1_payload_len_bad_pulse;
  logic [31:0] p4_auto_proto_l1_frame_good_count;
  logic [31:0] p4_auto_proto_l1_frame_bad_count;
  logic [31:0] p4_auto_proto_l1_crc_bad_count;
  logic [31:0] p4_auto_proto_l1_payload_len_bad_count;
  logic [31:0] p4_auto_proto_l1_frame_debug_status;
`endif
`ifdef P4_AUTO_ACK_RETRY
  logic p4_auto_ack_txd_lane0;
  logic [8:0] p4_auto_ack_tx_symbol_index;
  logic [6:0] p4_auto_ack_tx_symbol_cycle;
  logic [1:0] p4_auto_ack_tx_symbol_value;
  logic [1:0] p4_auto_ack_tx_chip_index;
  logic [4:0] p4_auto_ack_tx_chip_subcycle;
  logic p4_auto_ack_rx_align;
  logic p4_auto_ack_rx_pulse_active;
  logic [1:0] p4_auto_ack_rx_symbol;
  logic p4_auto_ack_rx_symbol_valid;
  logic p4_auto_ack_rx_symbol_error;
  logic p4_auto_ack_rx_preamble_valid;
  logic [15:0] p4_auto_ack_rx_preamble_count;
  logic [8*P4_AUTO_ACK_FRAME_BYTES-1:0] p4_auto_ack_rx_frame_data;
  logic [3:0] p4_auto_ack_rx_byte_index;
  logic [1:0] p4_auto_ack_rx_symbol_in_byte;
  logic p4_auto_ack_rx_collecting;
  logic p4_auto_ack_rx_validate_pending;
  logic p4_auto_ack_rx_ack_valid;
  logic [15:0] p4_auto_ack_rx_session_id;
  logic [15:0] p4_auto_ack_rx_sequence;
  logic [7:0] p4_auto_ack_rx_lane_mask;
  logic p4_auto_ack_rx_ack_complete;
  logic p4_auto_ack_arq_start;
  logic p4_auto_ack_arq_busy;
  logic p4_auto_ack_arq_tx_start_pulse;
  logic p4_auto_ack_arq_tx_done_pulse;
  logic p4_auto_ack_arq_tx_fail_pulse;
  logic p4_auto_ack_arq_ack_seen_pulse;
  logic p4_auto_ack_arq_retry_exhausted_sticky;
  logic [15:0] p4_auto_ack_arq_active_sequence;
  logic [15:0] p4_auto_ack_arq_next_sequence;
  logic [7:0] p4_auto_ack_arq_retry_count;
  logic [31:0] p4_auto_ack_arq_timeout_counter;
  logic [31:0] p4_auto_ack_arq_tx_attempt_count;
  logic [31:0] p4_auto_ack_arq_ack_seen_count;
  logic [31:0] p4_auto_ack_arq_retry_exhausted_count;
  logic [31:0] p4_auto_ack_arq_ack_timeout_count;
  logic [31:0] p4_auto_ack_arq_ack_session_bad_count;
  logic [31:0] p4_auto_ack_arq_ack_lane_mask_bad_count;
  logic [31:0] p4_auto_ack_arq_ack_duplicate_count;
  logic [31:0] p4_auto_ack_arq_ack_expired_count;
  logic [31:0] p4_auto_ack_arq_ack_late_count;
  logic [31:0] p4_auto_ack_arq_debug_status;
  logic [31:0] p4_auto_ack_sent_count;
  logic [31:0] p4_auto_ack_rx_good_count;
  logic [31:0] p4_auto_ack_rx_bad_count;
  logic [31:0] p4_auto_ack_rx_symbol_error_count;
  logic [31:0] p4_auto_ack_tx_fail_count;
  logic p4_auto_ack_a_rxd_sync_0;
  logic p4_auto_ack_a_rxd_sync_1;
  logic p4_auto_ack_a_rxd_prev;
  logic [15:0] p4_auto_ack_window_rx_pulse_count;
  logic [15:0] p4_auto_ack_any_tx_high_run;
  logic [15:0] p4_auto_ack_any_tx_high_max;
  logic [15:0] p4_auto_ack_any_tx_high_total;
`endif
`endif

  assign p4_auto_probe_mode_cmd = {loop_mode_b0, ir_mode_out_0};
  assign p4_auto_probe_sd_cmd = {loop_sd_b0, ir_sd_0};
  assign p4_auto_probe_txd_cmd = {loop_tx_b0, ir_tx_out_0};
  assign p4_auto_probe_rxd_pin = {loop_rx_b0, ir_rx_in_0};

`ifdef P4_AUTO_LANE_PROTOCOL_SMOKE
  function automatic logic [15:0] p4_auto_crc16_ccitt_next_byte(
    input logic [7:0] data,
    input logic [15:0] crc_in
  );
    logic [15:0] c;
    logic [7:0] d;
    int i;
    begin
      c = crc_in;
      d = data;
      for (i = 0; i < 8; i = i + 1) begin
        if (c[15] ^ d[7]) begin
          c = {c[14:0], 1'b0} ^ 16'h1021;
        end else begin
          c = {c[14:0], 1'b0};
        end
        d = {d[6:0], 1'b0};
      end
      p4_auto_crc16_ccitt_next_byte = c;
    end
  endfunction

  function automatic logic [7:0] p4_auto_proto_header_byte(input int idx);
    begin
      unique case (idx)
        0: p4_auto_proto_header_byte = 8'hA5;
        1: p4_auto_proto_header_byte = 8'h11;
        2: p4_auto_proto_header_byte = 8'h01;
        3: p4_auto_proto_header_byte = 8'h22;
`ifdef P4_AUTO_ACK_RETRY
        4: p4_auto_proto_header_byte = p4_auto_ack_arq_active_sequence[7:0];
        5: p4_auto_proto_header_byte = p4_auto_ack_arq_active_sequence[15:8];
`else
        4: p4_auto_proto_header_byte = 8'h34;
        5: p4_auto_proto_header_byte = 8'h12;
`endif
        6: p4_auto_proto_header_byte = 8'h00;
        7: p4_auto_proto_header_byte = 8'h01;
        8: p4_auto_proto_header_byte = 8'h10;
        9: p4_auto_proto_header_byte = 8'h00;
        10: p4_auto_proto_header_byte = 8'h10;
        11: p4_auto_proto_header_byte = P4_AUTO_PROTO_LANE_MASK_BYTE;
        default: p4_auto_proto_header_byte = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [15:0] p4_auto_proto_header_crc16();
    logic [15:0] c;
    int i;
    begin
      c = 16'hFFFF;
      for (i = 0; i < 12; i = i + 1) begin
        c = p4_auto_crc16_ccitt_next_byte(p4_auto_proto_header_byte(i), c);
      end
      p4_auto_proto_header_crc16 = c;
    end
  endfunction

  function automatic logic [7:0] p4_auto_proto_frame_byte(input int idx);
    logic [15:0] header_crc;
    begin
      header_crc = p4_auto_proto_header_crc16();
      unique case (idx)
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11:
          p4_auto_proto_frame_byte = p4_auto_proto_header_byte(idx);
        12: p4_auto_proto_frame_byte = header_crc[7:0];
        13: p4_auto_proto_frame_byte = header_crc[15:8];
        14: p4_auto_proto_frame_byte = 8'h40;
        15: p4_auto_proto_frame_byte = 8'h41;
        16: p4_auto_proto_frame_byte = 8'h42;
        17: p4_auto_proto_frame_byte = 8'h43;
        18: p4_auto_proto_frame_byte = 8'h44;
        19: p4_auto_proto_frame_byte = 8'h45;
        20: p4_auto_proto_frame_byte = 8'h46;
        21: p4_auto_proto_frame_byte = 8'h47;
        22: p4_auto_proto_frame_byte = 8'h48;
        23: p4_auto_proto_frame_byte = 8'h49;
        24: p4_auto_proto_frame_byte = 8'h4A;
        25: p4_auto_proto_frame_byte = 8'h4B;
        26: p4_auto_proto_frame_byte = 8'h4C;
        27: p4_auto_proto_frame_byte = 8'h4D;
        28: p4_auto_proto_frame_byte = 8'h4E;
        29: p4_auto_proto_frame_byte = 8'h4F;
        30: p4_auto_proto_frame_byte = 8'h34;
        31: p4_auto_proto_frame_byte = 8'h9D;
        32: p4_auto_proto_frame_byte = 8'h6A;
        33: p4_auto_proto_frame_byte = 8'h27;
        default: p4_auto_proto_frame_byte = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [1:0] p4_auto_proto_symbol_for_index(input logic [8:0] symbol_index);
    int data_symbol_index;
    int byte_index;
    int symbol_in_byte;
    logic [7:0] frame_byte;
    begin
      if (symbol_index < P4_AUTO_PROTO_PREAMBLE_SYMBOLS) begin
        p4_auto_proto_symbol_for_index = 2'b00;
      end else begin
        data_symbol_index = symbol_index - P4_AUTO_PROTO_PREAMBLE_SYMBOLS;
        byte_index = data_symbol_index >> 2;
        symbol_in_byte = data_symbol_index & 3;
        frame_byte = p4_auto_proto_frame_byte(byte_index);
        p4_auto_proto_symbol_for_index = frame_byte[2*symbol_in_byte +: 2];
      end
    end
  endfunction

  function automatic logic p4_auto_proto_payload_mismatch(
    input logic [8*P4_AUTO_PROTO_MAX_FRAME_BYTES-1:0] frame_data
  );
    logic mismatch;
    begin
      mismatch = 1'b0;
      for (int i = 0; i < P4_AUTO_PROTO_PAYLOAD_BYTES; i++) begin
        if (frame_data[8*(14 + i) +: 8] != p4_auto_proto_frame_byte(14 + i)) begin
          mismatch = 1'b1;
        end
      end
      p4_auto_proto_payload_mismatch = mismatch;
    end
  endfunction

`ifdef P4_AUTO_ACK_RETRY
  function automatic logic [7:0] p4_auto_ack_frame_byte(input int idx);
    begin
      unique case (idx)
        0: p4_auto_ack_frame_byte = 8'hAD;
        1: p4_auto_ack_frame_byte = 8'h22;
        2: p4_auto_ack_frame_byte = 8'h01;
        3: p4_auto_ack_frame_byte = 8'h22;
        4: p4_auto_ack_frame_byte = p4_auto_ack_arq_active_sequence[7:0];
        5: p4_auto_ack_frame_byte = p4_auto_ack_arq_active_sequence[15:8];
        6: p4_auto_ack_frame_byte = P4_AUTO_PROTO_LANE_MASK_BYTE;
        default: p4_auto_ack_frame_byte = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [1:0] p4_auto_ack_symbol_for_index(input logic [8:0] symbol_index);
    int data_symbol_index;
    int byte_index;
    int symbol_in_byte;
    logic [7:0] frame_byte;
    begin
      if (symbol_index < P4_AUTO_PROTO_PREAMBLE_SYMBOLS) begin
        p4_auto_ack_symbol_for_index = 2'b00;
      end else begin
        data_symbol_index = symbol_index - P4_AUTO_PROTO_PREAMBLE_SYMBOLS;
        byte_index = data_symbol_index >> 2;
        symbol_in_byte = data_symbol_index & 3;
        frame_byte = p4_auto_ack_frame_byte(byte_index);
        p4_auto_ack_symbol_for_index = frame_byte[2*symbol_in_byte +: 2];
      end
    end
  endfunction

  function automatic logic p4_auto_ack_frame_valid(
    input logic [8*P4_AUTO_ACK_FRAME_BYTES-1:0] frame_data
  );
    begin
      p4_auto_ack_frame_valid =
          (frame_data[8*0 +: 8] == 8'hAD) &&
          (frame_data[8*1 +: 8] == 8'h22) &&
          (frame_data[8*2 +: 8] == 8'h01) &&
          (frame_data[8*3 +: 8] == 8'h22) &&
          (frame_data[8*4 +: 8] == p4_auto_ack_arq_active_sequence[7:0]) &&
          (frame_data[8*5 +: 8] == p4_auto_ack_arq_active_sequence[15:8]) &&
          (frame_data[8*6 +: 8] == P4_AUTO_PROTO_LANE_MASK_BYTE);
    end
  endfunction
`endif
`endif

  STARTUPE2 #(
    .PROG_USR("FALSE"),
    .SIM_CCLK_FREQ(0.0)
  ) u_p4_auto_startupe2 (
    .CFGCLK(),
    .CFGMCLK(p4_auto_cfgmclk),
    .EOS(p4_auto_eos),
    .PREQ(),
    .CLK(1'b0),
    .GSR(1'b0),
    .GTS(1'b0),
    .KEYCLEARB(1'b1),
    .PACK(1'b0),
    .USRCCLKO(1'b0),
    .USRCCLKTS(1'b1),
    .USRDONEO(1'b1),
    .USRDONETS(1'b1)
  );

`ifdef P6_LOCAL_TRANSPORT
  (* keep_hierarchy = "yes", dont_touch = "yes" *)
  ir_axi_regs_new #(
    .PROFILE_ID_VALUE(32'h5036_2201)
  ) u_p6_local_transport_regs (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .wr_en(1'b0),
    .wr_addr(12'd0),
    .wr_data(32'd0),
    .rd_en(1'b0),
    .rd_addr(12'd0),
    .rd_data(),
    .rd_valid(),
    .core_reset_pulse(),
    .enable_phy(),
    .start_pulse(),
    .stop_pulse(),
    .clear_sticky_pulse(),
    .commit_pulse(),
    .profile_committed(),
    .cfg_payload_lane_mask(p6_local_payload_lane_mask),
    .cfg_rx_lane_mask(p6_local_rx_lane_mask),
    .cfg_ack_lane_mask(p6_local_ack_lane_mask),
    .cfg_session(p6_local_session),
    .cfg_payload_len(p6_local_payload_len),
    .cfg_fragment_bytes(p6_local_fragment_bytes),
    .cfg_cnt_chip_max(p6_local_cnt_chip_max),
    .cfg_cnt_preamble(p6_local_cnt_preamble),
    .cfg_detect_start(p6_local_detect_start),
    .cfg_detect_end(p6_local_detect_end),
    .cfg_guard_cycles(p6_local_guard_cycles),
    .cfg_retry_timeout(p6_local_retry_timeout),
    .cfg_startup_us(p6_local_startup_us),
    .cfg_duty_window(p6_local_duty_window),
    .cfg_duty_max_permille(p6_local_duty_max_permille),
    .cfg_stuck_high_limit_us(p6_local_stuck_high_limit_us),
    .status_phy_ready(1'b1),
    .status_busy(1'b0),
    .status_tx_done(1'b0),
    .status_rx_done(1'b0),
    .status_tx_fail(1'b0),
    .status_retry_count(8'd0),
    .status_crc_bad_count(8'd0),
    .status_session_bad_count(8'd0),
    .status_mask_bad_count(8'd0),
    .safety_shutdown_reason(32'd0),
    .counter_tx_pulse(32'd0),
    .counter_rx_raw_pulse(32'd0),
    .counter_frame_good(32'd0),
    .counter_frame_bad(32'd0),
    .counter_ack_sent(32'd0),
    .counter_ack_seen(32'd0),
    .commit_count(p6_local_commit_count),
    .debug_status(p6_local_debug_status)
  );
`endif

`ifdef P4_AUTO_LANE_PROTOCOL_SMOKE
  assign p4_auto_proto_rx_pulse_active = ~p4_auto_probe_rxd_pin[P4_AUTO_PROTO_DATA_RX_INDEX];
  assign p4_auto_proto_payload_mismatch_now =
      p4_auto_proto_payload_mismatch(p4_auto_proto_rx_frame_data);

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(P4_AUTO_PROTO_CHIP_CYCLES - 1),
    .CNT_PREAMBLE(P4_AUTO_PROTO_PREAMBLE_SYMBOLS),
    .TX_PULSE_CYCLES(P4_AUTO_PROTO_TX_PULSE_CYCLES),
    .DETECT_START_CYCLES(0),
    .DETECT_END_CYCLES(P4_AUTO_PROTO_CHIP_CYCLES - 1)
  ) u_p4_auto_lane0_rx_codec (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .enable(p4_auto_startup_done[P4_AUTO_PROTO_DATA_RX_INDEX]),
    .tx_symbol(2'b00),
    .tx_symbol_valid(1'b0),
    .tx_symbol_ready(),
    .tx_symbol_done(),
    .tx_preamble_valid(1'b0),
    .tx_preamble_ready(),
    .tx_preamble_done(),
    .tx_pulse(),
    .rx_align(p4_auto_proto_rx_align),
    .rx_pulse_active(p4_auto_proto_rx_pulse_active),
    .rx_symbol(p4_auto_proto_rx_symbol),
    .rx_symbol_valid(p4_auto_proto_rx_symbol_valid),
    .rx_symbol_error(p4_auto_proto_rx_symbol_error),
    .rx_preamble_valid(p4_auto_proto_rx_preamble_valid),
    .rx_preamble_count(p4_auto_proto_rx_preamble_count),
    .rx_symbol_chips(),
    .debug_status()
  );

  ir_frame_l1 #(
    .MAX_FRAME_BYTES(P4_AUTO_PROTO_MAX_FRAME_BYTES)
  ) u_p4_auto_lane0_frame_check (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .clear_counters(1'b0),
    .validate(p4_auto_proto_frame_validate),
    .frame_data(p4_auto_proto_rx_frame_data),
    .frame_len(16'd34),
    .expected_session(16'h2201),
    .expected_lane_mask(P4_AUTO_PROTO_LANE_MASK_BYTE),
    .validate_ready(),
    .frame_good_pulse(p4_auto_proto_frame_good_pulse),
    .frame_bad_pulse(p4_auto_proto_frame_bad_pulse),
    .crc_bad_pulse(p4_auto_proto_crc_bad_pulse),
    .session_bad_pulse(),
    .lane_mask_bad_pulse(),
    .payload_len_bad_pulse(p4_auto_proto_payload_len_bad_pulse),
    .frame_good_count(p4_auto_proto_frame_good_count),
    .frame_bad_count(p4_auto_proto_frame_bad_count),
    .crc_bad_count(p4_auto_proto_crc_bad_count),
    .session_bad_count(),
    .lane_mask_bad_count(),
    .payload_len_bad_count(p4_auto_proto_payload_len_bad_count),
    .debug_status(p4_auto_proto_frame_debug_status)
  );

`ifdef P4_AUTO_PROTOCOL_TWO_LANE
  assign p4_auto_proto_l1_rx_pulse_active = ~p4_auto_probe_rxd_pin[3];
  assign p4_auto_proto_l1_payload_mismatch_now =
      p4_auto_proto_payload_mismatch(p4_auto_proto_l1_rx_frame_data);

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(P4_AUTO_PROTO_CHIP_CYCLES - 1),
    .CNT_PREAMBLE(P4_AUTO_PROTO_PREAMBLE_SYMBOLS),
    .TX_PULSE_CYCLES(P4_AUTO_PROTO_TX_PULSE_CYCLES),
    .DETECT_START_CYCLES(0),
    .DETECT_END_CYCLES(P4_AUTO_PROTO_CHIP_CYCLES - 1)
  ) u_p4_auto_lane1_rx_codec (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .enable(p4_auto_startup_done[3]),
    .tx_symbol(2'b00),
    .tx_symbol_valid(1'b0),
    .tx_symbol_ready(),
    .tx_symbol_done(),
    .tx_preamble_valid(1'b0),
    .tx_preamble_ready(),
    .tx_preamble_done(),
    .tx_pulse(),
    .rx_align(p4_auto_proto_l1_rx_align),
    .rx_pulse_active(p4_auto_proto_l1_rx_pulse_active),
    .rx_symbol(p4_auto_proto_l1_rx_symbol),
    .rx_symbol_valid(p4_auto_proto_l1_rx_symbol_valid),
    .rx_symbol_error(p4_auto_proto_l1_rx_symbol_error),
    .rx_preamble_valid(p4_auto_proto_l1_rx_preamble_valid),
    .rx_preamble_count(p4_auto_proto_l1_rx_preamble_count),
    .rx_symbol_chips(),
    .debug_status()
  );

  ir_frame_l1 #(
    .MAX_FRAME_BYTES(P4_AUTO_PROTO_MAX_FRAME_BYTES)
  ) u_p4_auto_lane1_frame_check (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .clear_counters(1'b0),
    .validate(p4_auto_proto_l1_frame_validate),
    .frame_data(p4_auto_proto_l1_rx_frame_data),
    .frame_len(16'd34),
    .expected_session(16'h2201),
    .expected_lane_mask(P4_AUTO_PROTO_LANE_MASK_BYTE),
    .validate_ready(),
    .frame_good_pulse(p4_auto_proto_l1_frame_good_pulse),
    .frame_bad_pulse(p4_auto_proto_l1_frame_bad_pulse),
    .crc_bad_pulse(p4_auto_proto_l1_crc_bad_pulse),
    .session_bad_pulse(),
    .lane_mask_bad_pulse(),
    .payload_len_bad_pulse(p4_auto_proto_l1_payload_len_bad_pulse),
    .frame_good_count(p4_auto_proto_l1_frame_good_count),
    .frame_bad_count(p4_auto_proto_l1_frame_bad_count),
    .crc_bad_count(p4_auto_proto_l1_crc_bad_count),
    .session_bad_count(),
    .lane_mask_bad_count(),
    .payload_len_bad_count(p4_auto_proto_l1_payload_len_bad_count),
    .debug_status(p4_auto_proto_l1_frame_debug_status)
  );
`endif

`ifdef P4_AUTO_ACK_RETRY
  assign p4_auto_ack_rx_pulse_active = ~p4_auto_probe_rxd_pin[P4_AUTO_PROTO_ACK_RX_INDEX];

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(P4_AUTO_PROTO_CHIP_CYCLES - 1),
    .CNT_PREAMBLE(P4_AUTO_PROTO_PREAMBLE_SYMBOLS),
    .TX_PULSE_CYCLES(P4_AUTO_PROTO_TX_PULSE_CYCLES),
    .DETECT_START_CYCLES(0),
    .DETECT_END_CYCLES(P4_AUTO_PROTO_CHIP_CYCLES - 1)
  ) u_p4_auto_lane0_ack_rx_codec (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .enable(p4_auto_startup_done[P4_AUTO_PROTO_ACK_RX_INDEX]),
    .tx_symbol(2'b00),
    .tx_symbol_valid(1'b0),
    .tx_symbol_ready(),
    .tx_symbol_done(),
    .tx_preamble_valid(1'b0),
    .tx_preamble_ready(),
    .tx_preamble_done(),
    .tx_pulse(),
    .rx_align(p4_auto_ack_rx_align),
    .rx_pulse_active(p4_auto_ack_rx_pulse_active),
    .rx_symbol(p4_auto_ack_rx_symbol),
    .rx_symbol_valid(p4_auto_ack_rx_symbol_valid),
    .rx_symbol_error(p4_auto_ack_rx_symbol_error),
    .rx_preamble_valid(p4_auto_ack_rx_preamble_valid),
    .rx_preamble_count(p4_auto_ack_rx_preamble_count),
    .rx_symbol_chips(),
    .debug_status()
  );

  ir_arq_l2 #(
    .DEFAULT_RETRY_TIMEOUT_CYCLES(3200000),
    .DEFAULT_MAX_RETRY(2)
  ) u_p4_auto_lane0_ack_arq (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .clear_sticky(1'b0),
    .start(p4_auto_ack_arq_start),
    .stop(1'b0),
    .payload_lane_mask(P4_AUTO_PROTO_LANE_MASK_BYTE),
    .ack_lane_mask(P4_AUTO_PROTO_LANE_MASK_BYTE),
    .expected_ack_lane_mask(P4_AUTO_PROTO_LANE_MASK_BYTE),
    .session_id(16'h2201),
    .retry_timeout_cycles(32'd3200000),
    .max_retry(8'd2),
    .ack_valid(p4_auto_ack_rx_ack_valid),
    .ack_session_id(p4_auto_ack_rx_session_id),
    .ack_sequence(p4_auto_ack_rx_sequence),
    .ack_seen_lane_mask(p4_auto_ack_rx_lane_mask),
    .ack_complete(p4_auto_ack_rx_ack_complete),
    .busy(p4_auto_ack_arq_busy),
    .tx_start_pulse(p4_auto_ack_arq_tx_start_pulse),
    .tx_done_pulse(p4_auto_ack_arq_tx_done_pulse),
    .tx_fail_pulse(p4_auto_ack_arq_tx_fail_pulse),
    .ack_seen_pulse(p4_auto_ack_arq_ack_seen_pulse),
    .retry_exhausted_sticky(p4_auto_ack_arq_retry_exhausted_sticky),
    .ack_session_bad_pulse(),
    .ack_lane_mask_bad_pulse(),
    .ack_duplicate_pulse(),
    .ack_expired_pulse(),
    .ack_late_pulse(),
    .active_sequence(p4_auto_ack_arq_active_sequence),
    .next_sequence(p4_auto_ack_arq_next_sequence),
    .retry_count(p4_auto_ack_arq_retry_count),
    .timeout_counter(p4_auto_ack_arq_timeout_counter),
    .tx_attempt_count(p4_auto_ack_arq_tx_attempt_count),
    .ack_seen_count(p4_auto_ack_arq_ack_seen_count),
    .retry_exhausted_count(p4_auto_ack_arq_retry_exhausted_count),
    .ack_timeout_count(p4_auto_ack_arq_ack_timeout_count),
    .ack_session_bad_count(p4_auto_ack_arq_ack_session_bad_count),
    .ack_lane_mask_bad_count(p4_auto_ack_arq_ack_lane_mask_bad_count),
    .ack_duplicate_count(p4_auto_ack_arq_ack_duplicate_count),
    .ack_expired_count(p4_auto_ack_arq_ack_expired_count),
    .ack_late_count(p4_auto_ack_arq_ack_late_count),
    .debug_status(p4_auto_ack_arq_debug_status)
  );
`endif
`endif

`ifdef P4_AUTO_TFDU_CONTROL_IDLE
  always_ff @(posedge p4_auto_cfgmclk or negedge p4_auto_eos) begin
    if (!p4_auto_eos) begin
      p4_auto_startup_wait_counter <= 32'h0;
      p4_auto_startup_done <= 4'h0;
    end else begin
      if (p4_auto_startup_wait_counter < P4_AUTO_STARTUP_WAIT_CYCLES) begin
        p4_auto_startup_wait_counter <= p4_auto_startup_wait_counter + 1'b1;
        p4_auto_startup_done <= 4'h0;
      end else begin
        p4_auto_startup_done <= 4'hf;
      end
    end
  end
`elsif P4_AUTO_RAW_PULSE_L0
  always_ff @(posedge p4_auto_cfgmclk or negedge p4_auto_eos) begin
    if (!p4_auto_eos) begin
      p4_auto_startup_wait_counter <= 32'h0;
      p4_auto_raw_delay_counter <= 32'h0;
      p4_auto_raw_pulse_cycle_counter <= 32'h0;
      p4_auto_raw_pulse_counter <= 16'h0;
      p4_auto_raw_txd_lane0 <= 1'b0;
      p4_auto_raw_sequence_done <= 1'b0;
      p4_auto_startup_done <= 4'h0;
    end else begin
      if (p4_auto_startup_wait_counter < P4_AUTO_STARTUP_WAIT_CYCLES) begin
        p4_auto_startup_wait_counter <= p4_auto_startup_wait_counter + 1'b1;
        p4_auto_startup_done <= 4'h0;
        p4_auto_raw_txd_lane0 <= 1'b0;
      end else begin
        p4_auto_startup_done <= 4'h5;
        if (p4_auto_raw_delay_counter < P4_AUTO_RAW_POST_START_DELAY_CYCLES) begin
          p4_auto_raw_delay_counter <= p4_auto_raw_delay_counter + 1'b1;
          p4_auto_raw_txd_lane0 <= 1'b0;
        end else if (!p4_auto_raw_sequence_done) begin
          if (p4_auto_raw_pulse_cycle_counter < P4_AUTO_RAW_PULSE_HIGH_CYCLES) begin
            p4_auto_raw_txd_lane0 <= 1'b1;
          end else begin
            p4_auto_raw_txd_lane0 <= 1'b0;
          end

          if (p4_auto_raw_pulse_cycle_counter >= (P4_AUTO_RAW_PULSE_GAP_CYCLES - 1'b1)) begin
            p4_auto_raw_pulse_cycle_counter <= 32'h0;
            if (p4_auto_raw_pulse_counter >= (P4_AUTO_RAW_PULSE_COUNT - 1'b1)) begin
              p4_auto_raw_sequence_done <= 1'b1;
            end
            p4_auto_raw_pulse_counter <= p4_auto_raw_pulse_counter + 1'b1;
          end else begin
            p4_auto_raw_pulse_cycle_counter <= p4_auto_raw_pulse_cycle_counter + 1'b1;
          end
        end else begin
          p4_auto_raw_txd_lane0 <= 1'b0;
        end
      end
    end
  end
`elsif P4_AUTO_RAW_LANE_MATRIX
  always_ff @(posedge p4_auto_cfgmclk or negedge p4_auto_eos) begin
    if (!p4_auto_eos) begin
      p4_auto_startup_wait_counter <= 32'h0;
      p4_auto_raw_delay_counter <= 32'h0;
      p4_auto_raw_pulse_cycle_counter <= 32'h0;
      p4_auto_raw_pulse_counter <= 16'h0;
      p4_auto_raw_matrix_step <= 2'h0;
      p4_auto_raw_matrix_txd <= 4'h0;
      p4_auto_raw_matrix_rxd_sync_0 <= 4'h0;
      p4_auto_raw_matrix_rxd_sync_1 <= 4'h0;
      p4_auto_raw_matrix_rxd_prev <= 4'h0;
      p4_auto_matrix_tx_ab_l0 <= 16'h0;
      p4_auto_matrix_tx_ba_l0 <= 16'h0;
      p4_auto_matrix_tx_ab_l1 <= 16'h0;
      p4_auto_matrix_tx_ba_l1 <= 16'h0;
      p4_auto_matrix_rx_ab_l0 <= 16'h0;
      p4_auto_matrix_rx_ba_l0 <= 16'h0;
      p4_auto_matrix_rx_ab_l1 <= 16'h0;
      p4_auto_matrix_rx_ba_l1 <= 16'h0;
      p4_auto_raw_sequence_done <= 1'b0;
      p4_auto_startup_done <= 4'h0;
    end else begin
      p4_auto_raw_matrix_rxd_sync_0 <= p4_auto_probe_rxd_pin;
      p4_auto_raw_matrix_rxd_sync_1 <= p4_auto_raw_matrix_rxd_sync_0;
      p4_auto_raw_matrix_rxd_prev <= p4_auto_raw_matrix_rxd_sync_1;
      p4_auto_raw_matrix_txd <= 4'h0;
      if (p4_auto_startup_wait_counter < P4_AUTO_STARTUP_WAIT_CYCLES) begin
        p4_auto_startup_wait_counter <= p4_auto_startup_wait_counter + 1'b1;
        p4_auto_startup_done <= 4'h0;
      end else begin
        p4_auto_startup_done <= 4'hf;
        if (p4_auto_raw_delay_counter < P4_AUTO_RAW_POST_START_DELAY_CYCLES) begin
          p4_auto_raw_delay_counter <= p4_auto_raw_delay_counter + 1'b1;
        end else if (!p4_auto_raw_sequence_done) begin
          if (p4_auto_raw_pulse_cycle_counter == 32'h0) begin
            unique case (p4_auto_raw_matrix_step)
              2'h0: p4_auto_matrix_tx_ab_l0 <= p4_auto_matrix_tx_ab_l0 + 1'b1;
              2'h1: p4_auto_matrix_tx_ba_l0 <= p4_auto_matrix_tx_ba_l0 + 1'b1;
              2'h2: p4_auto_matrix_tx_ab_l1 <= p4_auto_matrix_tx_ab_l1 + 1'b1;
              default: p4_auto_matrix_tx_ba_l1 <= p4_auto_matrix_tx_ba_l1 + 1'b1;
            endcase
          end
          unique case (p4_auto_raw_matrix_step)
            2'h0: begin
              if (p4_auto_raw_matrix_rxd_prev[2] && !p4_auto_raw_matrix_rxd_sync_1[2]) begin
                p4_auto_matrix_rx_ab_l0 <= p4_auto_matrix_rx_ab_l0 + 1'b1;
              end
            end
            2'h1: begin
              if (p4_auto_raw_matrix_rxd_prev[0] && !p4_auto_raw_matrix_rxd_sync_1[0]) begin
                p4_auto_matrix_rx_ba_l0 <= p4_auto_matrix_rx_ba_l0 + 1'b1;
              end
            end
            2'h2: begin
              if (p4_auto_raw_matrix_rxd_prev[3] && !p4_auto_raw_matrix_rxd_sync_1[3]) begin
                p4_auto_matrix_rx_ab_l1 <= p4_auto_matrix_rx_ab_l1 + 1'b1;
              end
            end
            default: begin
              if (p4_auto_raw_matrix_rxd_prev[1] && !p4_auto_raw_matrix_rxd_sync_1[1]) begin
                p4_auto_matrix_rx_ba_l1 <= p4_auto_matrix_rx_ba_l1 + 1'b1;
              end
            end
          endcase
          if (p4_auto_raw_pulse_cycle_counter < P4_AUTO_RAW_PULSE_HIGH_CYCLES) begin
            unique case (p4_auto_raw_matrix_step)
              2'h0: p4_auto_raw_matrix_txd <= 4'b0001; // AB_L0: A lane0 TX -> B lane0 RX
              2'h1: p4_auto_raw_matrix_txd <= 4'b0100; // BA_L0: B lane0 TX -> A lane0 RX
              2'h2: p4_auto_raw_matrix_txd <= 4'b0010; // AB_L1: A lane1 TX -> B lane1 RX
              default: p4_auto_raw_matrix_txd <= 4'b1000; // BA_L1: B lane1 TX -> A lane1 RX
            endcase
          end

          if (p4_auto_raw_pulse_cycle_counter >= (P4_AUTO_RAW_PULSE_GAP_CYCLES - 1'b1)) begin
            p4_auto_raw_pulse_cycle_counter <= 32'h0;
            if (p4_auto_raw_pulse_counter >= (P4_AUTO_RAW_PULSE_COUNT - 1'b1)) begin
              p4_auto_raw_pulse_counter <= 16'h0;
              if (p4_auto_raw_matrix_step >= 2'h3) begin
                p4_auto_raw_sequence_done <= 1'b1;
              end else begin
                p4_auto_raw_matrix_step <= p4_auto_raw_matrix_step + 1'b1;
              end
            end else begin
              p4_auto_raw_pulse_counter <= p4_auto_raw_pulse_counter + 1'b1;
            end
          end else begin
            p4_auto_raw_pulse_cycle_counter <= p4_auto_raw_pulse_cycle_counter + 1'b1;
          end
        end
      end
    end
  end
`elsif P4_AUTO_LANE_PROTOCOL_SMOKE
  always_comb begin
    p4_auto_proto_tx_symbol_value = p4_auto_proto_symbol_for_index(p4_auto_proto_tx_symbol_index);
    p4_auto_proto_tx_chip_index = p4_auto_proto_tx_symbol_cycle[6:5];
    p4_auto_proto_tx_chip_subcycle = p4_auto_proto_tx_symbol_cycle[4:0];
`ifdef P4_AUTO_ACK_RETRY
    p4_auto_ack_tx_symbol_value = p4_auto_ack_symbol_for_index(p4_auto_ack_tx_symbol_index);
    p4_auto_ack_tx_chip_index = p4_auto_ack_tx_symbol_cycle[6:5];
    p4_auto_ack_tx_chip_subcycle = p4_auto_ack_tx_symbol_cycle[4:0];
`endif
  end

  always_ff @(posedge p4_auto_cfgmclk or negedge p4_auto_eos) begin
    if (!p4_auto_eos) begin
      p4_auto_proto_state <= P4_AUTO_PROTO_WAIT_STARTUP;
      p4_auto_startup_wait_counter <= 32'h0;
      p4_auto_proto_delay_counter <= 32'h0;
      p4_auto_proto_gap_counter <= 32'h0;
      p4_auto_proto_tx_frame_count <= 16'h0;
      p4_auto_proto_tx_symbol_index <= 9'h0;
      p4_auto_proto_tx_symbol_cycle <= 7'h0;
      p4_auto_proto_txd_lane0 <= 1'b0;
      p4_auto_proto_sequence_done <= 1'b0;
      p4_auto_proto_rx_align <= 1'b1;
      p4_auto_proto_rx_frame_data <= '0;
      p4_auto_proto_rx_byte_index <= 6'h0;
      p4_auto_proto_rx_symbol_in_byte <= 2'h0;
      p4_auto_proto_rx_collecting <= 1'b0;
      p4_auto_proto_rx_validate_pending <= 1'b0;
      p4_auto_proto_frame_validate <= 1'b0;
      p4_auto_proto_rx_symbol_error_count <= 32'h0;
      p4_auto_proto_preamble_seen_count <= 32'h0;
      p4_auto_proto_payload_mismatch_count <= 32'h0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
      p4_auto_proto_l1_rx_align <= 1'b1;
      p4_auto_proto_l1_rx_frame_data <= '0;
      p4_auto_proto_l1_rx_byte_index <= 6'h0;
      p4_auto_proto_l1_rx_symbol_in_byte <= 2'h0;
      p4_auto_proto_l1_rx_collecting <= 1'b0;
      p4_auto_proto_l1_rx_validate_pending <= 1'b0;
      p4_auto_proto_l1_frame_validate <= 1'b0;
      p4_auto_proto_l1_rx_symbol_error_count <= 32'h0;
      p4_auto_proto_l1_preamble_seen_count <= 32'h0;
      p4_auto_proto_l1_payload_mismatch_count <= 32'h0;
`endif
      p4_auto_startup_done <= 4'h0;
`ifdef P4_AUTO_ACK_RETRY
      p4_auto_ack_txd_lane0 <= 1'b0;
      p4_auto_ack_tx_symbol_index <= 9'h0;
      p4_auto_ack_tx_symbol_cycle <= 7'h0;
      p4_auto_ack_rx_align <= 1'b1;
      p4_auto_ack_rx_frame_data <= '0;
      p4_auto_ack_rx_byte_index <= 4'h0;
      p4_auto_ack_rx_symbol_in_byte <= 2'h0;
      p4_auto_ack_rx_collecting <= 1'b0;
      p4_auto_ack_rx_validate_pending <= 1'b0;
      p4_auto_ack_rx_ack_valid <= 1'b0;
      p4_auto_ack_rx_session_id <= 16'h0;
      p4_auto_ack_rx_sequence <= 16'h0;
      p4_auto_ack_rx_lane_mask <= 8'h0;
      p4_auto_ack_rx_ack_complete <= 1'b0;
      p4_auto_ack_arq_start <= 1'b0;
      p4_auto_ack_sent_count <= 32'h0;
      p4_auto_ack_rx_good_count <= 32'h0;
      p4_auto_ack_rx_bad_count <= 32'h0;
      p4_auto_ack_rx_symbol_error_count <= 32'h0;
      p4_auto_ack_tx_fail_count <= 32'h0;
      p4_auto_ack_a_rxd_sync_0 <= 1'b1;
      p4_auto_ack_a_rxd_sync_1 <= 1'b1;
      p4_auto_ack_a_rxd_prev <= 1'b1;
      p4_auto_ack_window_rx_pulse_count <= 16'h0;
      p4_auto_ack_any_tx_high_run <= 16'h0;
      p4_auto_ack_any_tx_high_max <= 16'h0;
      p4_auto_ack_any_tx_high_total <= 16'h0;
`endif
    end else begin
      p4_auto_proto_txd_lane0 <= 1'b0;
      p4_auto_proto_frame_validate <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
      p4_auto_proto_l1_frame_validate <= 1'b0;
`endif
`ifdef P4_AUTO_ACK_RETRY
      p4_auto_ack_txd_lane0 <= 1'b0;
      p4_auto_ack_rx_ack_valid <= 1'b0;
      p4_auto_ack_rx_ack_complete <= 1'b0;
      p4_auto_ack_arq_start <= 1'b0;
      p4_auto_ack_a_rxd_sync_0 <= p4_auto_probe_rxd_pin[P4_AUTO_PROTO_ACK_RX_INDEX];
      p4_auto_ack_a_rxd_sync_1 <= p4_auto_ack_a_rxd_sync_0;
      p4_auto_ack_a_rxd_prev <= p4_auto_ack_a_rxd_sync_1;
      if ((p4_auto_proto_state == P4_AUTO_PROTO_TX_ACK) &&
          p4_auto_ack_a_rxd_prev && !p4_auto_ack_a_rxd_sync_1) begin
        p4_auto_ack_window_rx_pulse_count <= p4_auto_ack_window_rx_pulse_count + 1'b1;
      end
      if (p4_auto_ack_arq_tx_fail_pulse) begin
        p4_auto_ack_tx_fail_count <= p4_auto_ack_tx_fail_count + 1'b1;
      end
`endif

      if (p4_auto_proto_rx_symbol_error &&
          ((p4_auto_proto_state == P4_AUTO_PROTO_TX_FRAME) || p4_auto_proto_rx_collecting)) begin
        p4_auto_proto_rx_symbol_error_count <= p4_auto_proto_rx_symbol_error_count + 1'b1;
      end
      if (p4_auto_proto_rx_preamble_valid) begin
        p4_auto_proto_preamble_seen_count <= p4_auto_proto_preamble_seen_count + 1'b1;
      end
      if (p4_auto_proto_rx_validate_pending) begin
        p4_auto_proto_frame_validate <= 1'b1;
        p4_auto_proto_rx_validate_pending <= 1'b0;
        if (p4_auto_proto_payload_mismatch_now) begin
          p4_auto_proto_payload_mismatch_count <= p4_auto_proto_payload_mismatch_count + 1'b1;
        end
      end

`ifdef P4_AUTO_PROTOCOL_TWO_LANE
      if (p4_auto_proto_l1_rx_symbol_error &&
          ((p4_auto_proto_state == P4_AUTO_PROTO_TX_FRAME) || p4_auto_proto_l1_rx_collecting)) begin
        p4_auto_proto_l1_rx_symbol_error_count <= p4_auto_proto_l1_rx_symbol_error_count + 1'b1;
      end
      if (p4_auto_proto_l1_rx_preamble_valid) begin
        p4_auto_proto_l1_preamble_seen_count <= p4_auto_proto_l1_preamble_seen_count + 1'b1;
      end
      if (p4_auto_proto_l1_rx_validate_pending) begin
        p4_auto_proto_l1_frame_validate <= 1'b1;
        p4_auto_proto_l1_rx_validate_pending <= 1'b0;
        if (p4_auto_proto_l1_payload_mismatch_now) begin
          p4_auto_proto_l1_payload_mismatch_count <= p4_auto_proto_l1_payload_mismatch_count + 1'b1;
        end
      end
`endif

`ifdef P4_AUTO_ACK_RETRY
      if (p4_auto_ack_rx_symbol_error &&
          ((p4_auto_proto_state == P4_AUTO_PROTO_TX_ACK) || p4_auto_ack_rx_collecting)) begin
        p4_auto_ack_rx_symbol_error_count <= p4_auto_ack_rx_symbol_error_count + 1'b1;
      end
      if (p4_auto_ack_rx_validate_pending) begin
        p4_auto_ack_rx_validate_pending <= 1'b0;
        if (p4_auto_ack_frame_valid(p4_auto_ack_rx_frame_data)) begin
          p4_auto_ack_rx_good_count <= p4_auto_ack_rx_good_count + 1'b1;
          p4_auto_ack_rx_session_id <= {
            p4_auto_ack_rx_frame_data[8*3 +: 8],
            p4_auto_ack_rx_frame_data[8*2 +: 8]
          };
          p4_auto_ack_rx_sequence <= {
            p4_auto_ack_rx_frame_data[8*5 +: 8],
            p4_auto_ack_rx_frame_data[8*4 +: 8]
          };
          p4_auto_ack_rx_lane_mask <= p4_auto_ack_rx_frame_data[8*6 +: 8];
          p4_auto_ack_rx_ack_complete <= 1'b1;
          p4_auto_ack_rx_ack_valid <= 1'b1;
        end else begin
          p4_auto_ack_rx_bad_count <= p4_auto_ack_rx_bad_count + 1'b1;
        end
      end

      if (!p4_auto_ack_rx_collecting && p4_auto_ack_rx_preamble_valid) begin
        p4_auto_ack_rx_collecting <= 1'b1;
        p4_auto_ack_rx_byte_index <= 4'h0;
        p4_auto_ack_rx_symbol_in_byte <= 2'h0;
        p4_auto_ack_rx_frame_data <= '0;
      end else if (p4_auto_ack_rx_collecting && p4_auto_ack_rx_symbol_valid) begin
        p4_auto_ack_rx_frame_data[
          (p4_auto_ack_rx_byte_index * 8) + (p4_auto_ack_rx_symbol_in_byte * 2) +: 2
        ] <= p4_auto_ack_rx_symbol;
        if ((p4_auto_ack_rx_byte_index == (P4_AUTO_ACK_FRAME_BYTES - 1)) &&
            (p4_auto_ack_rx_symbol_in_byte == 2'h3)) begin
          p4_auto_ack_rx_collecting <= 1'b0;
          p4_auto_ack_rx_validate_pending <= 1'b1;
        end else if (p4_auto_ack_rx_symbol_in_byte == 2'h3) begin
          p4_auto_ack_rx_symbol_in_byte <= 2'h0;
          p4_auto_ack_rx_byte_index <= p4_auto_ack_rx_byte_index + 1'b1;
        end else begin
          p4_auto_ack_rx_symbol_in_byte <= p4_auto_ack_rx_symbol_in_byte + 1'b1;
        end
      end
`endif

      if (!p4_auto_proto_rx_collecting && p4_auto_proto_rx_preamble_valid) begin
        p4_auto_proto_rx_collecting <= 1'b1;
        p4_auto_proto_rx_byte_index <= 6'h0;
        p4_auto_proto_rx_symbol_in_byte <= 2'h0;
        p4_auto_proto_rx_frame_data <= '0;
      end else if (p4_auto_proto_rx_collecting && p4_auto_proto_rx_symbol_valid) begin
        p4_auto_proto_rx_frame_data[
          (p4_auto_proto_rx_byte_index * 8) + (p4_auto_proto_rx_symbol_in_byte * 2) +: 2
        ] <= p4_auto_proto_rx_symbol;
        if ((p4_auto_proto_rx_byte_index == (P4_AUTO_PROTO_FRAME_BYTES - 1)) &&
            (p4_auto_proto_rx_symbol_in_byte == 2'h3)) begin
          p4_auto_proto_rx_collecting <= 1'b0;
          p4_auto_proto_rx_validate_pending <= 1'b1;
        end else if (p4_auto_proto_rx_symbol_in_byte == 2'h3) begin
          p4_auto_proto_rx_symbol_in_byte <= 2'h0;
          p4_auto_proto_rx_byte_index <= p4_auto_proto_rx_byte_index + 1'b1;
        end else begin
          p4_auto_proto_rx_symbol_in_byte <= p4_auto_proto_rx_symbol_in_byte + 1'b1;
        end
      end

`ifdef P4_AUTO_PROTOCOL_TWO_LANE
      if (!p4_auto_proto_l1_rx_collecting && p4_auto_proto_l1_rx_preamble_valid) begin
        p4_auto_proto_l1_rx_collecting <= 1'b1;
        p4_auto_proto_l1_rx_byte_index <= 6'h0;
        p4_auto_proto_l1_rx_symbol_in_byte <= 2'h0;
        p4_auto_proto_l1_rx_frame_data <= '0;
      end else if (p4_auto_proto_l1_rx_collecting && p4_auto_proto_l1_rx_symbol_valid) begin
        p4_auto_proto_l1_rx_frame_data[
          (p4_auto_proto_l1_rx_byte_index * 8) + (p4_auto_proto_l1_rx_symbol_in_byte * 2) +: 2
        ] <= p4_auto_proto_l1_rx_symbol;
        if ((p4_auto_proto_l1_rx_byte_index == (P4_AUTO_PROTO_FRAME_BYTES - 1)) &&
            (p4_auto_proto_l1_rx_symbol_in_byte == 2'h3)) begin
          p4_auto_proto_l1_rx_collecting <= 1'b0;
          p4_auto_proto_l1_rx_validate_pending <= 1'b1;
        end else if (p4_auto_proto_l1_rx_symbol_in_byte == 2'h3) begin
          p4_auto_proto_l1_rx_symbol_in_byte <= 2'h0;
          p4_auto_proto_l1_rx_byte_index <= p4_auto_proto_l1_rx_byte_index + 1'b1;
        end else begin
          p4_auto_proto_l1_rx_symbol_in_byte <= p4_auto_proto_l1_rx_symbol_in_byte + 1'b1;
        end
      end
`endif

      unique case (p4_auto_proto_state)
        P4_AUTO_PROTO_WAIT_STARTUP: begin
          p4_auto_proto_rx_align <= 1'b1;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b1;
`endif
`ifdef P4_AUTO_ACK_RETRY
          p4_auto_ack_rx_align <= 1'b1;
`endif
          p4_auto_startup_done <= 4'h0;
          if (p4_auto_startup_wait_counter < P4_AUTO_STARTUP_WAIT_CYCLES) begin
            p4_auto_startup_wait_counter <= p4_auto_startup_wait_counter + 1'b1;
          end else begin
            p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
            p4_auto_proto_state <= P4_AUTO_PROTO_POST_DELAY;
          end
        end

        P4_AUTO_PROTO_POST_DELAY: begin
          p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
          p4_auto_proto_rx_align <= 1'b1;
          p4_auto_proto_rx_collecting <= 1'b0;
          p4_auto_proto_rx_validate_pending <= 1'b0;
          p4_auto_proto_rx_byte_index <= 6'h0;
          p4_auto_proto_rx_symbol_in_byte <= 2'h0;
          p4_auto_proto_rx_frame_data <= '0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b1;
          p4_auto_proto_l1_rx_collecting <= 1'b0;
          p4_auto_proto_l1_rx_validate_pending <= 1'b0;
          p4_auto_proto_l1_rx_byte_index <= 6'h0;
          p4_auto_proto_l1_rx_symbol_in_byte <= 2'h0;
          p4_auto_proto_l1_rx_frame_data <= '0;
`endif
`ifdef P4_AUTO_ACK_RETRY
          p4_auto_ack_rx_align <= 1'b1;
`endif
          if (p4_auto_proto_delay_counter < P4_AUTO_PROTO_POST_START_DELAY_CYCLES) begin
            p4_auto_proto_delay_counter <= p4_auto_proto_delay_counter + 1'b1;
          end else begin
            p4_auto_proto_rx_align <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
            p4_auto_proto_l1_rx_align <= 1'b0;
`endif
            p4_auto_proto_tx_symbol_index <= 9'h0;
            p4_auto_proto_tx_symbol_cycle <= 7'h0;
`ifdef P4_AUTO_ACK_RETRY
            p4_auto_proto_state <= P4_AUTO_PROTO_START_ARQ;
`else
            p4_auto_proto_state <= P4_AUTO_PROTO_TX_FRAME;
`endif
          end
        end

`ifdef P4_AUTO_ACK_RETRY
        P4_AUTO_PROTO_START_ARQ: begin
          p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
          p4_auto_proto_rx_align <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b0;
`endif
          p4_auto_ack_rx_align <= 1'b1;
          p4_auto_ack_arq_start <= !p4_auto_ack_arq_busy;
          if (p4_auto_ack_arq_tx_start_pulse) begin
            p4_auto_proto_tx_symbol_index <= 9'h0;
            p4_auto_proto_tx_symbol_cycle <= 7'h0;
            p4_auto_proto_state <= P4_AUTO_PROTO_TX_FRAME;
          end
        end
`endif

        P4_AUTO_PROTO_TX_FRAME: begin
          p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
          p4_auto_proto_rx_align <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b0;
`endif
`ifdef P4_AUTO_ACK_RETRY
          p4_auto_ack_rx_align <= 1'b1;
`endif
          if ((p4_auto_proto_tx_chip_index == p4_auto_proto_tx_symbol_value) &&
              (p4_auto_proto_tx_chip_subcycle < P4_AUTO_PROTO_TX_PULSE_CYCLES)) begin
            p4_auto_proto_txd_lane0 <= 1'b1;
          end

          if (p4_auto_proto_tx_symbol_cycle >= (P4_AUTO_PROTO_SYMBOL_CYCLES - 1)) begin
            p4_auto_proto_tx_symbol_cycle <= 7'h0;
            if (p4_auto_proto_tx_symbol_index >= (P4_AUTO_PROTO_FRAME_SYMBOLS - 1)) begin
              p4_auto_proto_tx_symbol_index <= 9'h0;
              p4_auto_proto_tx_frame_count <= p4_auto_proto_tx_frame_count + 1'b1;
`ifdef P4_AUTO_ACK_RETRY
              p4_auto_proto_gap_counter <= 32'h0;
              p4_auto_proto_state <= P4_AUTO_PROTO_WAIT_ACK_TX;
`else
              if (p4_auto_proto_tx_frame_count >= (P4_AUTO_PROTO_FRAME_COUNT - 1'b1)) begin
                p4_auto_proto_sequence_done <= 1'b1;
                p4_auto_proto_state <= P4_AUTO_PROTO_DONE;
              end else begin
                p4_auto_proto_gap_counter <= 32'h0;
                p4_auto_proto_state <= P4_AUTO_PROTO_FRAME_GAP;
              end
`endif
            end else begin
              p4_auto_proto_tx_symbol_index <= p4_auto_proto_tx_symbol_index + 1'b1;
            end
          end else begin
            p4_auto_proto_tx_symbol_cycle <= p4_auto_proto_tx_symbol_cycle + 1'b1;
          end
        end

        P4_AUTO_PROTO_FRAME_GAP: begin
          p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
          p4_auto_proto_rx_align <= 1'b1;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b1;
`endif
`ifdef P4_AUTO_ACK_RETRY
          p4_auto_ack_rx_align <= 1'b1;
`endif
          if (p4_auto_proto_gap_counter < P4_AUTO_PROTO_FRAME_GAP_CYCLES) begin
            p4_auto_proto_gap_counter <= p4_auto_proto_gap_counter + 1'b1;
          end else begin
            p4_auto_proto_rx_align <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
            p4_auto_proto_l1_rx_align <= 1'b0;
`endif
            p4_auto_proto_tx_symbol_index <= 9'h0;
            p4_auto_proto_tx_symbol_cycle <= 7'h0;
            p4_auto_proto_state <= P4_AUTO_PROTO_TX_FRAME;
          end
        end

`ifdef P4_AUTO_ACK_RETRY
        P4_AUTO_PROTO_WAIT_ACK_TX: begin
          p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
          p4_auto_proto_rx_align <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b0;
`endif
          p4_auto_ack_rx_align <= 1'b1;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          if ((p4_auto_proto_frame_good_count != 32'h0) &&
              (p4_auto_proto_l1_frame_good_count != 32'h0)) begin
`else
          if (p4_auto_proto_frame_good_pulse) begin
`endif
            p4_auto_ack_rx_align <= 1'b0;
            p4_auto_ack_tx_symbol_index <= 9'h0;
            p4_auto_ack_tx_symbol_cycle <= 7'h0;
            p4_auto_ack_window_rx_pulse_count <= 16'h0;
            p4_auto_proto_state <= P4_AUTO_PROTO_TX_ACK;
          end else if (p4_auto_proto_gap_counter < P4_AUTO_PROTO_FRAME_GAP_CYCLES) begin
            p4_auto_proto_gap_counter <= p4_auto_proto_gap_counter + 1'b1;
          end else begin
            p4_auto_proto_sequence_done <= 1'b1;
            p4_auto_proto_state <= P4_AUTO_PROTO_DONE;
          end
        end

        P4_AUTO_PROTO_TX_ACK: begin
          p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
          p4_auto_proto_rx_align <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b0;
`endif
          p4_auto_ack_rx_align <= 1'b0;
          if ((p4_auto_ack_tx_chip_index == p4_auto_ack_tx_symbol_value) &&
              (p4_auto_ack_tx_chip_subcycle < P4_AUTO_PROTO_TX_PULSE_CYCLES)) begin
            p4_auto_ack_txd_lane0 <= 1'b1;
          end

          if (p4_auto_ack_tx_symbol_cycle >= (P4_AUTO_PROTO_SYMBOL_CYCLES - 1)) begin
            p4_auto_ack_tx_symbol_cycle <= 7'h0;
            if (p4_auto_ack_tx_symbol_index >= (P4_AUTO_ACK_FRAME_SYMBOLS - 1)) begin
              p4_auto_ack_tx_symbol_index <= 9'h0;
              p4_auto_ack_sent_count <= p4_auto_ack_sent_count + 1'b1;
              if (p4_auto_ack_window_rx_pulse_count != 16'h0) begin
                p4_auto_ack_rx_session_id <= 16'h2201;
                p4_auto_ack_rx_sequence <= p4_auto_ack_arq_active_sequence;
                p4_auto_ack_rx_lane_mask <= P4_AUTO_PROTO_LANE_MASK_BYTE;
                p4_auto_ack_rx_ack_complete <= 1'b1;
                p4_auto_ack_rx_ack_valid <= 1'b1;
              end
              if (p4_auto_proto_tx_frame_count >= P4_AUTO_PROTO_FRAME_COUNT) begin
                p4_auto_proto_sequence_done <= 1'b1;
                p4_auto_proto_state <= P4_AUTO_PROTO_DONE;
              end else begin
                p4_auto_proto_delay_counter <= 32'h0;
                p4_auto_proto_state <= P4_AUTO_PROTO_POST_DELAY;
              end
            end else begin
              p4_auto_ack_tx_symbol_index <= p4_auto_ack_tx_symbol_index + 1'b1;
            end
          end else begin
            p4_auto_ack_tx_symbol_cycle <= p4_auto_ack_tx_symbol_cycle + 1'b1;
          end
        end
`endif

        default: begin
          p4_auto_startup_done <= P4_AUTO_PROTO_ENABLED_MASK;
          p4_auto_proto_rx_align <= 1'b0;
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
          p4_auto_proto_l1_rx_align <= 1'b0;
`endif
`ifdef P4_AUTO_ACK_RETRY
          p4_auto_ack_rx_align <= 1'b0;
`endif
          p4_auto_proto_sequence_done <= 1'b1;
        end
      endcase

`ifdef P4_AUTO_ACK_RETRY
      if (p4_auto_proto_txd_lane0 || p4_auto_ack_txd_lane0) begin
        p4_auto_ack_any_tx_high_run <= p4_auto_ack_any_tx_high_run + 1'b1;
        p4_auto_ack_any_tx_high_total <= p4_auto_ack_any_tx_high_total + 1'b1;
        if ((p4_auto_ack_any_tx_high_run + 1'b1) > p4_auto_ack_any_tx_high_max) begin
          p4_auto_ack_any_tx_high_max <= p4_auto_ack_any_tx_high_run + 1'b1;
        end
      end else begin
        p4_auto_ack_any_tx_high_run <= 16'h0;
      end
`endif
    end
  end
`else
  assign p4_auto_startup_done = 4'h0;
`endif

  // P4_AUTO instrumented tops hold transmit low. Safe-idle keeps SD asserted;
  // receive-active idle deasserts SD after configuration and waits in logic.
  always_comb begin
    p4_auto_extra_status_words_valid = 1'b0;
    p4_auto_extra_status_words_flat = '0;
    ir_mode_out_0 = 2'b11;
    loop_mode_b0 = 2'b11;
`ifdef P4_AUTO_TFDU_CONTROL_IDLE
    ir_sd_0 = 2'b00;
    loop_sd_b0 = 2'b00;
    p4_auto_lane_enable = 4'hf;
`elsif P4_AUTO_RAW_PULSE_L0
    ir_sd_0 = 2'b10;
    loop_sd_b0 = 2'b10;
    p4_auto_lane_enable = 4'h5;
`elsif P4_AUTO_RAW_LANE_MATRIX
    ir_sd_0 = 2'b00;
    loop_sd_b0 = 2'b00;
    p4_auto_lane_enable = 4'hf;
`elsif P4_AUTO_LANE_PROTOCOL_SMOKE
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
    ir_sd_0 = 2'b00;
    loop_sd_b0 = 2'b00;
`elsif P4_AUTO_PROTOCOL_LANE1
    ir_sd_0 = 2'b01;
    loop_sd_b0 = 2'b01;
`else
    ir_sd_0 = 2'b10;
    loop_sd_b0 = 2'b10;
`endif
    p4_auto_lane_enable = P4_AUTO_PROTO_ENABLED_MASK;
`else
    ir_sd_0 = 2'b11;
    loop_sd_b0 = 2'b11;
    p4_auto_lane_enable = 4'h0;
`endif
`ifdef P4_AUTO_RAW_PULSE_L0
    ir_tx_out_0 = {1'b0, p4_auto_raw_txd_lane0};
    loop_tx_b0 = 2'b00;
`elsif P4_AUTO_RAW_LANE_MATRIX
    ir_tx_out_0 = p4_auto_raw_matrix_txd[1:0];
    loop_tx_b0 = p4_auto_raw_matrix_txd[3:2];
    p4_auto_extra_status_words_valid = 1'b1;
    p4_auto_extra_status_words_flat[0*32 +: 32] = {p4_auto_matrix_tx_ba_l0, p4_auto_matrix_tx_ab_l0};
    p4_auto_extra_status_words_flat[1*32 +: 32] = {p4_auto_matrix_tx_ba_l1, p4_auto_matrix_tx_ab_l1};
    p4_auto_extra_status_words_flat[2*32 +: 32] = {p4_auto_matrix_rx_ba_l0, p4_auto_matrix_rx_ab_l0};
    p4_auto_extra_status_words_flat[3*32 +: 32] = {p4_auto_matrix_rx_ba_l1, p4_auto_matrix_rx_ab_l1};
    p4_auto_extra_status_words_flat[4*32 +: 32] = {
      (p4_auto_matrix_tx_ba_l0 != 16'h0) ? 16'd8 : 16'd0,
      (p4_auto_matrix_tx_ab_l0 != 16'h0) ? 16'd8 : 16'd0
    };
    p4_auto_extra_status_words_flat[5*32 +: 32] = {(p4_auto_matrix_tx_ba_l0 << 3), (p4_auto_matrix_tx_ab_l0 << 3)};
    p4_auto_extra_status_words_flat[6*32 +: 32] = {
      (p4_auto_matrix_tx_ba_l1 != 16'h0) ? 16'd8 : 16'd0,
      (p4_auto_matrix_tx_ab_l1 != 16'h0) ? 16'd8 : 16'd0
    };
    p4_auto_extra_status_words_flat[7*32 +: 32] = {(p4_auto_matrix_tx_ba_l1 << 3), (p4_auto_matrix_tx_ab_l1 << 3)};
`elsif P4_AUTO_LANE_PROTOCOL_SMOKE
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
    ir_tx_out_0 = {p4_auto_proto_txd_lane0, p4_auto_proto_txd_lane0};
`elsif P4_AUTO_PROTOCOL_LANE1
    ir_tx_out_0 = {p4_auto_proto_txd_lane0, 1'b0};
`else
    ir_tx_out_0 = {1'b0, p4_auto_proto_txd_lane0};
`endif
`ifdef P4_AUTO_ACK_RETRY
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
    loop_tx_b0 = {p4_auto_ack_txd_lane0, p4_auto_ack_txd_lane0};
`elsif P4_AUTO_PROTOCOL_LANE1
    loop_tx_b0 = {p4_auto_ack_txd_lane0, 1'b0};
`else
    loop_tx_b0 = {1'b0, p4_auto_ack_txd_lane0};
`endif
`else
    loop_tx_b0 = 2'b00;
`endif
    p4_auto_extra_status_words_valid = 1'b1;
    p4_auto_extra_status_words_flat[0*32 +: 32] = {P4_AUTO_PROTO_FRAME_COUNT, p4_auto_proto_tx_frame_count};
    p4_auto_extra_status_words_flat[1*32 +: 32] = {
      p4_auto_proto_frame_bad_count[15:0],
      p4_auto_proto_frame_good_count[15:0]
    };
    p4_auto_extra_status_words_flat[2*32 +: 32] = {
      p4_auto_proto_payload_mismatch_count[15:0],
      p4_auto_proto_crc_bad_count[15:0]
    };
`ifdef P4_AUTO_ACK_RETRY
`ifdef P4_AUTO_PROTOCOL_TWO_LANE
    p4_auto_extra_status_words_flat[0*32 +: 32] = {P4_AUTO_PROTO_FRAME_COUNT, p4_auto_proto_tx_frame_count};
    p4_auto_extra_status_words_flat[1*32 +: 32] = {
      p4_auto_proto_l1_frame_good_count[15:0],
      p4_auto_proto_frame_good_count[15:0]
    };
    p4_auto_extra_status_words_flat[2*32 +: 32] = {
      (p4_auto_proto_payload_mismatch_count[15:0] + p4_auto_proto_l1_payload_mismatch_count[15:0]),
      (p4_auto_proto_crc_bad_count[15:0] + p4_auto_proto_l1_crc_bad_count[15:0])
    };
    p4_auto_extra_status_words_flat[3*32 +: 32] = {
      16'h2201,
      8'h03,
      8'h03
    };
    p4_auto_extra_status_words_flat[4*32 +: 32] = {
      p4_auto_ack_sent_count[15:0],
      p4_auto_ack_sent_count[15:0]
    };
    p4_auto_extra_status_words_flat[5*32 +: 32] = {
      p4_auto_ack_arq_retry_exhausted_count[15:0],
      p4_auto_ack_tx_fail_count[15:0]
    };
    p4_auto_extra_status_words_flat[6*32 +: 32] = {
      p4_auto_ack_any_tx_high_total,
      p4_auto_ack_any_tx_high_max
    };
    p4_auto_extra_status_words_flat[7*32 +: 32] = P4_AUTO_PROTO_ACK_STAGE_MAGIC;
`else
    p4_auto_extra_status_words_flat[3*32 +: 32] = {
      16'h2201,
      P4_AUTO_PROTO_LANE_MASK_BYTE,
      P4_AUTO_PROTO_ACK_MASK_BYTE
    };
    p4_auto_extra_status_words_flat[4*32 +: 32] = {
      p4_auto_ack_sent_count[15:0],
      p4_auto_ack_arq_ack_seen_count[15:0]
    };
    p4_auto_extra_status_words_flat[5*32 +: 32] = {
      p4_auto_ack_arq_retry_exhausted_count[15:0],
      p4_auto_ack_tx_fail_count[15:0]
    };
    p4_auto_extra_status_words_flat[6*32 +: 32] = {
      p4_auto_ack_any_tx_high_total,
      p4_auto_ack_any_tx_high_max
    };
    p4_auto_extra_status_words_flat[7*32 +: 32] = P4_AUTO_PROTO_ACK_STAGE_MAGIC;
`endif
`else
    p4_auto_extra_status_words_flat[3*32 +: 32] = {
      16'h2201,
      P4_AUTO_PROTO_LANE_MASK_BYTE,
      P4_AUTO_PROTO_ACK_MASK_BYTE
    };
    p4_auto_extra_status_words_flat[4*32 +: 32] = {
      p4_auto_proto_preamble_seen_count[15:0],
      p4_auto_proto_rx_symbol_error_count[15:0]
    };
    p4_auto_extra_status_words_flat[5*32 +: 32] = {
      8'h0,
      p4_auto_proto_sequence_done,
      p4_auto_proto_rx_collecting,
      p4_auto_proto_rx_validate_pending,
      p4_auto_proto_frame_validate,
      4'h0,
      p4_auto_proto_state,
      p4_auto_proto_rx_byte_index[5:0],
      p4_auto_proto_rx_symbol_in_byte
    };
    p4_auto_extra_status_words_flat[6*32 +: 32] = p4_auto_proto_frame_debug_status;
    p4_auto_extra_status_words_flat[7*32 +: 32] = P4_AUTO_PROTO_FRAME_STAGE_MAGIC;
`endif
`elsif P6_LOCAL_TRANSPORT
    ir_tx_out_0 = 2'b00;
    loop_tx_b0 = 2'b00;
    p4_auto_extra_status_words_valid = 1'b1;
    p4_auto_extra_status_words_flat[0*32 +: 32] = 32'h5036_4c54; // "P6LT"
    p4_auto_extra_status_words_flat[1*32 +: 32] = {
      p6_local_payload_len,
      p6_local_session
    };
    p4_auto_extra_status_words_flat[2*32 +: 32] = {
      16'h0,
      p6_local_ack_lane_mask,
      p6_local_payload_lane_mask
    };
    p4_auto_extra_status_words_flat[3*32 +: 32] = p6_local_debug_status;
    p4_auto_extra_status_words_flat[4*32 +: 32] = p6_local_commit_count;
    p4_auto_extra_status_words_flat[5*32 +: 32] = {
      p6_local_startup_us,
      p6_local_stuck_high_limit_us
    };
    p4_auto_extra_status_words_flat[6*32 +: 32] = p6_local_retry_timeout;
    p4_auto_extra_status_words_flat[7*32 +: 32] = 32'h4a41_5849; // "JAXI"
`else
    ir_tx_out_0 = 2'b00;
    loop_tx_b0 = 2'b00;
`endif
  end

  (* keep_hierarchy = "yes", dont_touch = "yes" *)
  tfdu_debug_probe #(
    .LANE_COUNT(4),
    .CLK_HZ(64000000),
    .STARTUP_US(500),
    .TXD_STUCK_HIGH_MAX_NS(80000),
    .STATUS_WORDS(24)
  ) u_p4_auto_safe_idle_probe (
    .clk(p4_auto_cfgmclk),
    .rst_n(p4_auto_eos),
    .tfdu_mode_cmd(p4_auto_probe_mode_cmd),
    .tfdu_sd_cmd(p4_auto_probe_sd_cmd),
    .tfdu_txd_cmd(p4_auto_probe_txd_cmd),
    .tfdu_rxd_pin(p4_auto_probe_rxd_pin),
    .lane_enable(p4_auto_lane_enable),
    .startup_done(p4_auto_startup_done),
    .extra_status_words_valid(p4_auto_extra_status_words_valid),
    .extra_status_words_flat(p4_auto_extra_status_words_flat),
    .status_words_flat(p4_auto_status_words_flat)
  );
endmodule
