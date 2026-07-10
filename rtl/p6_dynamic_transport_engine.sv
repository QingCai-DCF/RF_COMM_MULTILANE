`timescale 1ns/1ps

// Real two-lane, stationary P6 transport engine.  A-side lanes transmit one
// dynamic DATA frame, B-side lanes validate it and return an ACK on the same
// selected mask.  The engine never uses an internal data loopback path.
module p6_dynamic_transport_engine #(
  parameter int CLK_HZ = 64_000_000,
  parameter int STARTUP_US = 500,
  parameter int CHIP_CYCLES = 32,
  parameter int TX_PULSE_CYCLES = 8,
  parameter int PREAMBLE_SYMBOLS = 16,
  parameter int TURNAROUND_CYCLES = 4096,
  parameter int MAX_RETRY = 3,
  parameter int MAX_PAYLOAD_BYTES = 247
) (
  input  logic         clk,
  input  logic         rst_n,
  input  logic         reset_pulse,
  input  logic         clear_pulse,
  input  logic         start_pulse,
  input  logic         stop_pulse,
  input  logic         shutdown_pulse,
  input  logic         enable_phy,
  input  logic [15:0]  cfg_session,
  input  logic [7:0]   cfg_lane_mask,
  input  logic [7:0]   cfg_ack_lane_mask,
  input  logic [15:0]  cfg_payload_len,
  input  logic [31:0]  cfg_timeout_cycles,
  output logic [7:0]   tx_payload_read_index,
  input  logic [7:0]   tx_payload_read_data,
  output logic [7:0]   compare_payload_read_index,
  input  logic [7:0]   compare_payload_read_data,
  input  logic [31:0]  tx_payload_crc32,

  input  logic [1:0]   a_rxd,
  output logic [1:0]   a_txd,
  output logic [1:0]   a_sd,
  output logic [1:0]   a_mode,
  input  logic [1:0]   b_rxd,
  output logic [1:0]   b_txd,
  output logic [1:0]   b_sd,
  output logic [1:0]   b_mode,

  output logic         ready,
  output logic         busy,
  output logic         done_pulse,
  output logic         fail_pulse,
  output logic         timeout_pulse,
  output logic [31:0]  error_code,
  output logic         rx_byte_write_pulse,
  output logic [7:0]   rx_byte_write_index,
  output logic [7:0]   rx_byte_write_data,
  output logic [15:0]  rx_payload_len,
  output logic [31:0]  rx_payload_crc32,
  output logic [31:0]  rx_digest,
  output logic [1:0]   rx_good_mask,
  output logic [31:0]  crc_bad_count,
  output logic [31:0]  payload_mismatch_count,
  output logic [31:0]  retry_count,
  output logic [31:0]  retry_exhausted_count,
  output logic [31:0]  tx_fail_count,
  output logic [31:0]  txd_high_max,
  output logic [31:0]  duty_violation_count,
  output logic [31:0]  shutdown_reason,
  output logic [31:0]  tx_pulse_count,
  output logic [31:0]  rx_raw_count,
  output logic [31:0]  frame_good_count,
  output logic [31:0]  frame_bad_count,
  output logic [31:0]  ack_sent_count,
  output logic [31:0]  ack_seen_count,
  output logic [31:0]  debug_status
);
  localparam int MAX_FRAME_BYTES = 14 + MAX_PAYLOAD_BYTES + 4;
  localparam int ACK_FRAME_BYTES = 7;
  localparam int SYMBOL_CYCLES = CHIP_CYCLES * 4;
  localparam logic [31:0] ERROR_DATA_TIMEOUT = 32'h0000_0101;
  localparam logic [31:0] ERROR_ACK_TIMEOUT  = 32'h0000_0102;
  localparam logic [31:0] ERROR_STOPPED      = 32'h0000_0103;
  localparam logic [31:0] ERROR_STUCK_HIGH   = 32'h0000_0201;
  localparam logic [31:0] ERROR_DUTY_LIMIT   = 32'h0000_0202;

  typedef enum logic [3:0] {
    S_IDLE,
    S_WAIT_READY,
    S_PREP_DATA,
    S_TX_DATA,
    S_WAIT_DATA,
    S_GUARD_ACK,
    S_PREP_ACK,
    S_TX_ACK,
    S_WAIT_ACK
  } state_t;

  state_t state;
  logic [15:0] active_session;
  logic [7:0] active_lane_mask;
  logic [7:0] active_ack_mask;
  logic [15:0] active_payload_len;
  logic [31:0] active_timeout_cycles;
  logic [31:0] active_payload_crc32;
  logic [15:0] active_sequence;
  logic [15:0] next_sequence;
  logic [15:0] active_frame_bytes;
  logic [31:0] timeout_counter;
  logic [31:0] turnaround_counter;
  logic [7:0] retry_in_transaction;

  logic [11:0] tx_symbol_index;
  logic [15:0] tx_symbol_cycle;
  logic [8:0] ack_symbol_index;
  logic [15:0] ack_symbol_cycle;
  logic [1:0] tx_symbol_value;
  logic [1:0] ack_symbol_value;
  integer tx_chip_index;
  integer tx_chip_subcycle;
  integer ack_chip_index;
  integer ack_chip_subcycle;
  logic data_tx_pulse_req;
  logic ack_tx_pulse_req;

  logic [1:0] a_phy_ready;
  logic [1:0] b_phy_ready;
  logic [1:0] a_rx_active;
  logic [1:0] b_rx_active;
  logic [1:0] a_fault_stuck;
  logic [1:0] b_fault_stuck;
  logic [1:0] a_fault_duty;
  logic [1:0] b_fault_duty;
  logic [31:0] a_tx_pulses [0:1];
  logic [31:0] b_tx_pulses [0:1];
  logic [31:0] a_rx_raw [0:1];
  logic [31:0] b_rx_raw [0:1];
  logic [31:0] a_txd_high [0:1];
  logic [31:0] b_txd_high [0:1];
  logic [31:0] txd_high_cycle_max;

  function automatic logic [31:0] p6_max_txd_high4(
    input logic [31:0] value0,
    input logic [31:0] value1,
    input logic [31:0] value2,
    input logic [31:0] value3
  );
    logic [31:0] result;
    begin
      result = value0;
      if (value1 > result) result = value1;
      if (value2 > result) result = value2;
      if (value3 > result) result = value3;
      p6_max_txd_high4 = result;
    end
  endfunction
  logic [1:0] a_tx_req;
  logic [1:0] b_tx_req;
  logic [1:0] phy_enable_mask;
  logic safety_shutdown_latched;
  logic any_stuck_fault;
  logic any_duty_fault;

  logic data_rx_align;
  logic ack_rx_align;
  logic [1:0] b_rx_symbol [0:1];
  logic [1:0] a_rx_symbol [0:1];
  logic [1:0] b_rx_symbol_valid;
  logic [1:0] a_rx_symbol_valid;
  logic [1:0] b_rx_symbol_error;
  logic [1:0] a_rx_symbol_error;
  logic [1:0] b_rx_preamble_valid;
  logic [1:0] a_rx_preamble_valid;

  logic [8*ACK_FRAME_BYTES-1:0] ack_rx_frame [0:1];
  logic [7:0] data_rx_header [0:1][0:13];
  logic [7:0] data_rx_current_byte [0:1];
  logic [31:0] data_rx_seen_payload_crc [0:1];
  logic [8:0] data_rx_byte_index [0:1];
  logic [2:0] ack_rx_byte_index [0:1];
  logic [1:0] data_rx_symbol_in_byte [0:1];
  logic [1:0] ack_rx_symbol_in_byte [0:1];
  logic [1:0] data_rx_collecting;
  logic [1:0] ack_rx_collecting;
  logic [1:0] data_validate_pending;
  logic [1:0] ack_validate_pending;
  logic [1:0] data_good_mask;
  logic [1:0] ack_good_mask;
  logic rx_payload_captured;
  logic [15:0] data_header_crc_state [0:1];
  logic [31:0] data_payload_crc_state [0:1];
  logic [1:0] data_payload_mismatch_seen;

  function automatic logic [15:0] crc16_next_byte(
    input logic [7:0] data,
    input logic [15:0] crc_in
  );
    logic [15:0] c;
    logic [7:0] d;
    begin
      c = crc_in;
      d = data;
      for (int idx = 0; idx < 8; idx++) begin
        c = (c[15] ^ d[7]) ? ({c[14:0], 1'b0} ^ 16'h1021) : {c[14:0], 1'b0};
        d = {d[6:0], 1'b0};
      end
      crc16_next_byte = c;
    end
  endfunction

  function automatic logic [31:0] crc32_next_byte(
    input logic [7:0] data,
    input logic [31:0] crc_in
  );
    logic [31:0] c;
    begin
      c = crc_in;
      for (int idx = 0; idx < 8; idx++) begin
        c = (c[0] ^ data[idx]) ? ((c >> 1) ^ 32'hEDB8_8320) : (c >> 1);
      end
      crc32_next_byte = c;
    end
  endfunction

  function automatic logic [7:0] header_byte(input int idx);
    begin
      unique case (idx)
        0: header_byte = 8'hA5;
        1: header_byte = 8'h11;
        2: header_byte = active_session[7:0];
        3: header_byte = active_session[15:8];
        4: header_byte = active_sequence[7:0];
        5: header_byte = active_sequence[15:8];
        6: header_byte = 8'h00;
        7: header_byte = 8'h01;
        8: header_byte = active_payload_len[7:0];
        9: header_byte = active_payload_len[15:8];
        10: header_byte = active_payload_len[7:0];
        11: header_byte = active_lane_mask;
        default: header_byte = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [15:0] header_crc16();
    logic [15:0] c;
    begin
      c = 16'hFFFF;
      for (int idx = 0; idx < 12; idx++) c = crc16_next_byte(header_byte(idx), c);
      header_crc16 = c;
    end
  endfunction

  function automatic logic [7:0] frame_byte(input int idx);
    logic [15:0] hcrc;
    int payload_offset;
    begin
      hcrc = header_crc16();
      payload_offset = idx - 14;
      if (idx < 12) frame_byte = header_byte(idx);
      else if (idx == 12) frame_byte = hcrc[7:0];
      else if (idx == 13) frame_byte = hcrc[15:8];
      else if ((payload_offset >= 0) && (payload_offset < active_payload_len)) begin
        frame_byte = tx_payload_read_data;
      end else if (idx == (14 + active_payload_len + 0)) frame_byte = active_payload_crc32[7:0];
      else if (idx == (14 + active_payload_len + 1)) frame_byte = active_payload_crc32[15:8];
      else if (idx == (14 + active_payload_len + 2)) frame_byte = active_payload_crc32[23:16];
      else if (idx == (14 + active_payload_len + 3)) frame_byte = active_payload_crc32[31:24];
      else frame_byte = 8'h00;
    end
  endfunction

  function automatic logic [7:0] ack_byte(input int idx);
    begin
      unique case (idx)
        0: ack_byte = 8'hAD;
        1: ack_byte = 8'h22;
        2: ack_byte = active_session[7:0];
        3: ack_byte = active_session[15:8];
        4: ack_byte = active_sequence[7:0];
        5: ack_byte = active_sequence[15:8];
        6: ack_byte = active_ack_mask;
        default: ack_byte = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [1:0] data_symbol(input int symbol_idx);
    int data_idx;
    int byte_idx;
    int symbol_in_byte;
    logic [7:0] byte_value;
    begin
      if (symbol_idx < PREAMBLE_SYMBOLS) data_symbol = 2'b00;
      else begin
        data_idx = symbol_idx - PREAMBLE_SYMBOLS;
        byte_idx = data_idx >> 2;
        symbol_in_byte = data_idx & 3;
        byte_value = frame_byte(byte_idx);
        data_symbol = byte_value[2*symbol_in_byte +: 2];
      end
    end
  endfunction

  function automatic logic [1:0] ack_symbol(input int symbol_idx);
    int data_idx;
    int byte_idx;
    int symbol_in_byte;
    logic [7:0] byte_value;
    begin
      if (symbol_idx < PREAMBLE_SYMBOLS) ack_symbol = 2'b00;
      else begin
        data_idx = symbol_idx - PREAMBLE_SYMBOLS;
        byte_idx = data_idx >> 2;
        symbol_in_byte = data_idx & 3;
        byte_value = ack_byte(byte_idx);
        ack_symbol = byte_value[2*symbol_in_byte +: 2];
      end
    end
  endfunction

  function automatic logic data_frame_header_valid(input int lane);
    logic [15:0] seen_crc;
    begin
      seen_crc = {data_rx_header[lane][13], data_rx_header[lane][12]};
      data_frame_header_valid =
          (data_rx_header[lane][0] == 8'hA5) &&
          (data_rx_header[lane][1] == 8'h11) &&
          ({data_rx_header[lane][3], data_rx_header[lane][2]} == active_session) &&
          ({data_rx_header[lane][5], data_rx_header[lane][4]} == active_sequence) &&
          ({data_rx_header[lane][9], data_rx_header[lane][8]} == active_payload_len) &&
          (data_rx_header[lane][10] == active_payload_len[7:0]) &&
          (data_rx_header[lane][11] == active_lane_mask) &&
          (seen_crc == data_header_crc_state[lane]);
    end
  endfunction

  function automatic logic data_frame_payload_valid(input int lane);
    begin
      data_frame_payload_valid = !data_payload_mismatch_seen[lane] &&
          (data_rx_seen_payload_crc[lane] == active_payload_crc32) &&
          (~data_payload_crc_state[lane] == active_payload_crc32);
    end
  endfunction

  function automatic logic ack_frame_valid(input logic [8*ACK_FRAME_BYTES-1:0] frame);
    begin
      ack_frame_valid =
          (frame[8*0 +: 8] == 8'hAD) &&
          (frame[8*1 +: 8] == 8'h22) &&
          ({frame[8*3 +: 8], frame[8*2 +: 8]} == active_session) &&
          ({frame[8*5 +: 8], frame[8*4 +: 8]} == active_sequence) &&
          (frame[8*6 +: 8] == active_ack_mask);
    end
  endfunction

  assign phy_enable_mask = enable_phy && !safety_shutdown_latched ? cfg_lane_mask[1:0] : 2'b00;
  assign ready = enable_phy && !safety_shutdown_latched &&
      ((a_phy_ready & cfg_lane_mask[1:0]) == cfg_lane_mask[1:0]) &&
      ((b_phy_ready & cfg_lane_mask[1:0]) == cfg_lane_mask[1:0]);
  assign busy = (state != S_IDLE);
  assign any_stuck_fault = |(a_fault_stuck | b_fault_stuck);
  assign any_duty_fault = |(a_fault_duty | b_fault_duty);
  assign tx_pulse_count = a_tx_pulses[0] + a_tx_pulses[1] + b_tx_pulses[0] + b_tx_pulses[1];
  assign rx_raw_count = a_rx_raw[0] + a_rx_raw[1] + b_rx_raw[0] + b_rx_raw[1];

  always_comb begin
    integer tx_data_symbol_index;
    integer tx_frame_byte_index;
    integer tx_payload_index_value;
    tx_symbol_value = data_symbol(tx_symbol_index);
    ack_symbol_value = ack_symbol(ack_symbol_index);
    tx_chip_index = tx_symbol_cycle / CHIP_CYCLES;
    tx_chip_subcycle = tx_symbol_cycle % CHIP_CYCLES;
    ack_chip_index = ack_symbol_cycle / CHIP_CYCLES;
    ack_chip_subcycle = ack_symbol_cycle % CHIP_CYCLES;
    data_tx_pulse_req = (state == S_TX_DATA) &&
        (tx_chip_index == tx_symbol_value) && (tx_chip_subcycle < TX_PULSE_CYCLES);
    ack_tx_pulse_req = (state == S_TX_ACK) &&
        (ack_chip_index == ack_symbol_value) && (ack_chip_subcycle < TX_PULSE_CYCLES);
    a_tx_req = active_lane_mask[1:0] & {2{data_tx_pulse_req}};
    b_tx_req = active_ack_mask[1:0] & {2{ack_tx_pulse_req}};
    tx_data_symbol_index = tx_symbol_index - PREAMBLE_SYMBOLS;
    tx_frame_byte_index = (tx_data_symbol_index < 0) ? 0 : (tx_data_symbol_index >> 2);
    tx_payload_index_value = tx_frame_byte_index - 14;
    if ((tx_payload_index_value >= 0) && (tx_payload_index_value < MAX_PAYLOAD_BYTES)) begin
      tx_payload_read_index = tx_payload_index_value[7:0];
    end else begin
      tx_payload_read_index = 8'd0;
    end
    if (active_lane_mask[0]) begin
      compare_payload_read_index = (data_rx_byte_index[0] >= 14) ?
          (data_rx_byte_index[0] - 14) : 8'd0;
    end else begin
      compare_payload_read_index = (data_rx_byte_index[1] >= 14) ?
          (data_rx_byte_index[1] - 14) : 8'd0;
    end
    data_rx_align = !((state == S_TX_DATA) || (state == S_WAIT_DATA));
    ack_rx_align = !((state == S_TX_ACK) || (state == S_WAIT_ACK));
    debug_status = {
      8'hD6,
      state,
      safety_shutdown_latched,
      ready,
      data_good_mask,
      ack_good_mask,
      active_lane_mask[1:0],
      active_ack_mask[1:0],
      retry_in_transaction,
      2'd0
    };
  end

  generate
    for (genvar lane = 0; lane < 2; lane++) begin : g_phy
      tfdu_lane_phy #(
        .CLK_HZ(CLK_HZ),
        .TFDU_STARTUP_US(STARTUP_US),
        .TX_STUCK_HIGH_LIMIT_US(10),
        .DUTY_WINDOW_US(1000),
        .DUTY_MAX_PERMILLE(200)
      ) u_a_phy (
        .clk(clk), .rst_n(rst_n), .enable_phy(phy_enable_mask[lane]),
        .clear_sticky(clear_pulse || reset_pulse), .tx_pulse_req(a_tx_req[lane]), .rxd(a_rxd[lane]),
        .Txd(a_txd[lane]), .SD(a_sd[lane]), .Mode(a_mode[lane]), .phy_ready(a_phy_ready[lane]),
        .rx_pulse_active(a_rx_active[lane]), .startup_done(), .shutdown_active(),
        .fault_stuck_high(a_fault_stuck[lane]), .fault_duty_limit(a_fault_duty[lane]),
        .rx_raw_count(a_rx_raw[lane]), .tx_pulse_count(a_tx_pulses[lane]),
        .rx_pulse_width_min(), .rx_pulse_width_max(), .rx_last_timestamp(),
        .tx_high_width_current(a_txd_high[lane]), .duty_window_count(), .duty_high_count()
      );
      tfdu_lane_phy #(
        .CLK_HZ(CLK_HZ),
        .TFDU_STARTUP_US(STARTUP_US),
        .TX_STUCK_HIGH_LIMIT_US(10),
        .DUTY_WINDOW_US(1000),
        .DUTY_MAX_PERMILLE(200)
      ) u_b_phy (
        .clk(clk), .rst_n(rst_n), .enable_phy(phy_enable_mask[lane]),
        .clear_sticky(clear_pulse || reset_pulse), .tx_pulse_req(b_tx_req[lane]), .rxd(b_rxd[lane]),
        .Txd(b_txd[lane]), .SD(b_sd[lane]), .Mode(b_mode[lane]), .phy_ready(b_phy_ready[lane]),
        .rx_pulse_active(b_rx_active[lane]), .startup_done(), .shutdown_active(),
        .fault_stuck_high(b_fault_stuck[lane]), .fault_duty_limit(b_fault_duty[lane]),
        .rx_raw_count(b_rx_raw[lane]), .tx_pulse_count(b_tx_pulses[lane]),
        .rx_pulse_width_min(), .rx_pulse_width_max(), .rx_last_timestamp(),
        .tx_high_width_current(b_txd_high[lane]), .duty_window_count(), .duty_high_count()
      );

      ir_4ppm_codec #(
        .CNT_CHIP_MAX(CHIP_CYCLES - 1), .CNT_PREAMBLE(PREAMBLE_SYMBOLS),
        .TX_PULSE_CYCLES(TX_PULSE_CYCLES), .DETECT_START_CYCLES(0),
        .DETECT_END_CYCLES(CHIP_CYCLES - 1)
      ) u_b_data_rx (
        .clk(clk), .rst_n(rst_n), .enable(b_phy_ready[lane]),
        .tx_symbol(2'b00), .tx_symbol_valid(1'b0), .tx_symbol_ready(), .tx_symbol_done(),
        .tx_preamble_valid(1'b0), .tx_preamble_ready(), .tx_preamble_done(), .tx_pulse(),
        .rx_align(data_rx_align), .rx_pulse_active(b_rx_active[lane]),
        .rx_symbol(b_rx_symbol[lane]), .rx_symbol_valid(b_rx_symbol_valid[lane]),
        .rx_symbol_error(b_rx_symbol_error[lane]), .rx_preamble_valid(b_rx_preamble_valid[lane]),
        .rx_preamble_count(), .rx_symbol_chips(), .debug_status()
      );
      ir_4ppm_codec #(
        .CNT_CHIP_MAX(CHIP_CYCLES - 1), .CNT_PREAMBLE(PREAMBLE_SYMBOLS),
        .TX_PULSE_CYCLES(TX_PULSE_CYCLES), .DETECT_START_CYCLES(0),
        .DETECT_END_CYCLES(CHIP_CYCLES - 1)
      ) u_a_ack_rx (
        .clk(clk), .rst_n(rst_n), .enable(a_phy_ready[lane]),
        .tx_symbol(2'b00), .tx_symbol_valid(1'b0), .tx_symbol_ready(), .tx_symbol_done(),
        .tx_preamble_valid(1'b0), .tx_preamble_ready(), .tx_preamble_done(), .tx_pulse(),
        .rx_align(ack_rx_align), .rx_pulse_active(a_rx_active[lane]),
        .rx_symbol(a_rx_symbol[lane]), .rx_symbol_valid(a_rx_symbol_valid[lane]),
        .rx_symbol_error(a_rx_symbol_error[lane]), .rx_preamble_valid(a_rx_preamble_valid[lane]),
        .rx_preamble_count(), .rx_symbol_chips(), .debug_status()
      );
    end
  endgenerate

  // DATA receive/validation, including byte-for-byte payload capture.
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      data_rx_collecting <= 2'b00;
      data_validate_pending <= 2'b00;
      data_good_mask <= 2'b00;
      rx_byte_write_pulse <= 1'b0;
      rx_byte_write_index <= 8'd0;
      rx_byte_write_data <= 8'd0;
      rx_payload_len <= 16'd0;
      rx_payload_crc32 <= 32'd0;
      rx_digest <= 32'd0;
      rx_payload_captured <= 1'b0;
      crc_bad_count <= 32'd0;
      payload_mismatch_count <= 32'd0;
      frame_good_count <= 32'd0;
      frame_bad_count <= 32'd0;
      for (int lane = 0; lane < 2; lane++) begin
        data_rx_byte_index[lane] <= '0;
        data_rx_symbol_in_byte[lane] <= '0;
        data_rx_current_byte[lane] <= 8'd0;
        data_rx_seen_payload_crc[lane] <= 32'd0;
        data_header_crc_state[lane] <= 16'hFFFF;
        data_payload_crc_state[lane] <= 32'hFFFF_FFFF;
        for (int byte_idx = 0; byte_idx < 14; byte_idx++) data_rx_header[lane][byte_idx] <= 8'd0;
      end
      data_payload_mismatch_seen <= 2'b00;
    end else if (reset_pulse) begin
      data_rx_collecting <= 2'b00;
      data_validate_pending <= 2'b00;
      data_good_mask <= 2'b00;
      rx_byte_write_pulse <= 1'b0;
      rx_byte_write_index <= 8'd0;
      rx_byte_write_data <= 8'd0;
      rx_payload_len <= 16'd0;
      rx_payload_crc32 <= 32'd0;
      rx_digest <= 32'd0;
      rx_payload_captured <= 1'b0;
      crc_bad_count <= 32'd0;
      payload_mismatch_count <= 32'd0;
      frame_good_count <= 32'd0;
      frame_bad_count <= 32'd0;
      data_payload_mismatch_seen <= 2'b00;
      for (int lane = 0; lane < 2; lane++) begin
        data_rx_current_byte[lane] <= 8'd0;
        data_rx_seen_payload_crc[lane] <= 32'd0;
        data_header_crc_state[lane] <= 16'hFFFF;
        data_payload_crc_state[lane] <= 32'hFFFF_FFFF;
        for (int byte_idx = 0; byte_idx < 14; byte_idx++) data_rx_header[lane][byte_idx] <= 8'd0;
      end
    end else begin
      rx_byte_write_pulse <= 1'b0;
      if (clear_pulse) begin
        crc_bad_count <= 32'd0;
        payload_mismatch_count <= 32'd0;
        frame_bad_count <= 32'd0;
      end
      if (state == S_PREP_DATA) begin
        data_rx_collecting <= 2'b00;
        data_validate_pending <= 2'b00;
        data_good_mask <= 2'b00;
        rx_payload_captured <= 1'b0;
        rx_payload_len <= 16'd0;
        rx_payload_crc32 <= 32'd0;
        rx_digest <= 32'd0;
        data_payload_mismatch_seen <= 2'b00;
        for (int lane = 0; lane < 2; lane++) begin
          data_rx_byte_index[lane] <= '0;
          data_rx_symbol_in_byte[lane] <= '0;
          data_rx_current_byte[lane] <= 8'd0;
          data_rx_seen_payload_crc[lane] <= 32'd0;
          data_header_crc_state[lane] <= 16'hFFFF;
          data_payload_crc_state[lane] <= 32'hFFFF_FFFF;
          for (int byte_idx = 0; byte_idx < 14; byte_idx++) data_rx_header[lane][byte_idx] <= 8'd0;
        end
      end else if (data_rx_align) begin
        data_rx_collecting <= 2'b00;
      end else begin
        for (int lane = 0; lane < 2; lane++) begin
          if (data_validate_pending[lane]) begin
            data_validate_pending[lane] <= 1'b0;
            if (data_frame_header_valid(lane) && data_frame_payload_valid(lane)) begin
              data_good_mask[lane] <= 1'b1;
              frame_good_count <= frame_good_count + 1'b1;
              if (!rx_payload_captured) begin
                rx_payload_len <= active_payload_len;
                rx_payload_crc32 <= ~data_payload_crc_state[lane];
                rx_digest <= ~data_payload_crc_state[lane];
                rx_payload_captured <= 1'b1;
              end
            end else begin
              frame_bad_count <= frame_bad_count + 1'b1;
              if (!data_frame_header_valid(lane) ||
                  (~data_payload_crc_state[lane] != active_payload_crc32)) begin
                crc_bad_count <= crc_bad_count + 1'b1;
              end
              if (!data_frame_payload_valid(lane)) begin
                payload_mismatch_count <= payload_mismatch_count + 1'b1;
              end
            end
          end
          if (!data_rx_collecting[lane] && b_rx_preamble_valid[lane] && active_lane_mask[lane]) begin
            data_rx_collecting[lane] <= 1'b1;
            data_rx_byte_index[lane] <= '0;
            data_rx_symbol_in_byte[lane] <= '0;
            data_rx_current_byte[lane] <= 8'd0;
            data_rx_seen_payload_crc[lane] <= 32'd0;
            data_header_crc_state[lane] <= 16'hFFFF;
            data_payload_crc_state[lane] <= 32'hFFFF_FFFF;
            data_payload_mismatch_seen[lane] <= 1'b0;
            for (int byte_idx = 0; byte_idx < 14; byte_idx++) data_rx_header[lane][byte_idx] <= 8'd0;
          end else if (data_rx_collecting[lane] && b_rx_symbol_valid[lane]) begin
            logic [7:0] completed_byte;
            int payload_index;
            int trailer_index;
            completed_byte = data_rx_current_byte[lane];
            completed_byte[2*data_rx_symbol_in_byte[lane] +: 2] = b_rx_symbol[lane];
            payload_index = data_rx_byte_index[lane] - 14;
            trailer_index = data_rx_byte_index[lane] - (14 + active_payload_len);
            data_rx_current_byte[lane] <= completed_byte;
            if (data_rx_symbol_in_byte[lane] == 2'd3) begin
              data_rx_current_byte[lane] <= 8'd0;
              if (data_rx_byte_index[lane] < 12) begin
                data_header_crc_state[lane] <= crc16_next_byte(completed_byte, data_header_crc_state[lane]);
              end
              if (data_rx_byte_index[lane] < 14) data_rx_header[lane][data_rx_byte_index[lane]] <= completed_byte;
              if ((payload_index >= 0) && (payload_index < active_payload_len)) begin
                data_payload_crc_state[lane] <= crc32_next_byte(completed_byte, data_payload_crc_state[lane]);
                if (completed_byte != compare_payload_read_data) data_payload_mismatch_seen[lane] <= 1'b1;
                if ((lane == 0 && active_lane_mask[0]) ||
                    (lane == 1 && !active_lane_mask[0] && active_lane_mask[1])) begin
                  rx_byte_write_pulse <= 1'b1;
                  rx_byte_write_index <= payload_index[7:0];
                  rx_byte_write_data <= completed_byte;
                end
              end
              if ((trailer_index >= 0) && (trailer_index < 4)) begin
                data_rx_seen_payload_crc[lane][8*trailer_index +: 8] <= completed_byte;
              end
            end
            if ((data_rx_byte_index[lane] == (active_frame_bytes - 1'b1)) &&
                (data_rx_symbol_in_byte[lane] == 2'd3)) begin
              data_rx_collecting[lane] <= 1'b0;
              data_validate_pending[lane] <= 1'b1;
            end else if (data_rx_symbol_in_byte[lane] == 2'd3) begin
              data_rx_symbol_in_byte[lane] <= 2'd0;
              data_rx_byte_index[lane] <= data_rx_byte_index[lane] + 1'b1;
            end else begin
              data_rx_symbol_in_byte[lane] <= data_rx_symbol_in_byte[lane] + 1'b1;
            end
          end
          if (b_rx_symbol_error[lane] && data_rx_collecting[lane]) begin
            frame_bad_count <= frame_bad_count + 1'b1;
          end
        end
      end
    end
  end

  // ACK receive/validation.
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      ack_rx_collecting <= 2'b00;
      ack_validate_pending <= 2'b00;
      ack_good_mask <= 2'b00;
      for (int lane = 0; lane < 2; lane++) begin
        ack_rx_frame[lane] <= '0;
        ack_rx_byte_index[lane] <= '0;
        ack_rx_symbol_in_byte[lane] <= '0;
      end
    end else if (reset_pulse || (state == S_PREP_ACK)) begin
      ack_rx_collecting <= 2'b00;
      ack_validate_pending <= 2'b00;
      ack_good_mask <= 2'b00;
      for (int lane = 0; lane < 2; lane++) begin
        ack_rx_frame[lane] <= '0;
        ack_rx_byte_index[lane] <= '0;
        ack_rx_symbol_in_byte[lane] <= '0;
      end
    end else if (ack_rx_align) begin
      ack_rx_collecting <= 2'b00;
    end else begin
      for (int lane = 0; lane < 2; lane++) begin
        if (ack_validate_pending[lane]) begin
          ack_validate_pending[lane] <= 1'b0;
          if (ack_frame_valid(ack_rx_frame[lane])) ack_good_mask[lane] <= 1'b1;
        end
        if (!ack_rx_collecting[lane] && a_rx_preamble_valid[lane] && active_ack_mask[lane]) begin
          ack_rx_collecting[lane] <= 1'b1;
          ack_rx_byte_index[lane] <= '0;
          ack_rx_symbol_in_byte[lane] <= '0;
          ack_rx_frame[lane] <= '0;
        end else if (ack_rx_collecting[lane] && a_rx_symbol_valid[lane]) begin
          ack_rx_frame[lane][
            (ack_rx_byte_index[lane] * 8) + (ack_rx_symbol_in_byte[lane] * 2) +: 2
          ] <= a_rx_symbol[lane];
          if ((ack_rx_byte_index[lane] == (ACK_FRAME_BYTES - 1)) &&
              (ack_rx_symbol_in_byte[lane] == 2'd3)) begin
            ack_rx_collecting[lane] <= 1'b0;
            ack_validate_pending[lane] <= 1'b1;
          end else if (ack_rx_symbol_in_byte[lane] == 2'd3) begin
            ack_rx_symbol_in_byte[lane] <= 2'd0;
            ack_rx_byte_index[lane] <= ack_rx_byte_index[lane] + 1'b1;
          end else begin
            ack_rx_symbol_in_byte[lane] <= ack_rx_symbol_in_byte[lane] + 1'b1;
          end
        end
      end
    end
  end

  // Transfer state machine, retries, bounded timeouts, and safety stop.
  always_comb begin
    txd_high_cycle_max = p6_max_txd_high4(
      a_txd_high[0], a_txd_high[1], b_txd_high[0], b_txd_high[1]
    );
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= S_IDLE;
      active_session <= 16'h2201;
      active_lane_mask <= 8'h01;
      active_ack_mask <= 8'h01;
      active_payload_len <= 16'd0;
      active_timeout_cycles <= 32'd1;
      active_payload_crc32 <= 32'd0;
      active_sequence <= 16'd0;
      next_sequence <= 16'd0;
      active_frame_bytes <= 16'd18;
      timeout_counter <= 32'd0;
      turnaround_counter <= 32'd0;
      retry_in_transaction <= 8'd0;
      tx_symbol_index <= 12'd0;
      tx_symbol_cycle <= 16'd0;
      ack_symbol_index <= 9'd0;
      ack_symbol_cycle <= 16'd0;
      done_pulse <= 1'b0;
      fail_pulse <= 1'b0;
      timeout_pulse <= 1'b0;
      error_code <= 32'd0;
      rx_good_mask <= 2'b00;
      retry_count <= 32'd0;
      retry_exhausted_count <= 32'd0;
      tx_fail_count <= 32'd0;
      ack_sent_count <= 32'd0;
      ack_seen_count <= 32'd0;
      txd_high_max <= 32'd0;
      duty_violation_count <= 32'd0;
      shutdown_reason <= 32'd0;
      safety_shutdown_latched <= 1'b0;
    end else begin
      done_pulse <= 1'b0;
      fail_pulse <= 1'b0;
      timeout_pulse <= 1'b0;

      if (txd_high_cycle_max > txd_high_max)
        txd_high_max <= txd_high_cycle_max;

      if (reset_pulse) begin
        state <= S_IDLE;
        safety_shutdown_latched <= 1'b0;
        shutdown_reason <= 32'd0;
        error_code <= 32'd0;
        rx_good_mask <= 2'b00;
        retry_count <= 32'd0;
        retry_exhausted_count <= 32'd0;
        tx_fail_count <= 32'd0;
        ack_sent_count <= 32'd0;
        ack_seen_count <= 32'd0;
        txd_high_max <= 32'd0;
        duty_violation_count <= 32'd0;
      end else if (shutdown_pulse) begin
        state <= S_IDLE;
        shutdown_reason <= 32'h5446_4455;
      end else if (any_stuck_fault || any_duty_fault) begin
        if (!safety_shutdown_latched) begin
          safety_shutdown_latched <= 1'b1;
          state <= S_IDLE;
          fail_pulse <= 1'b1;
          tx_fail_count <= tx_fail_count + 1'b1;
          if (any_stuck_fault) begin
            error_code <= ERROR_STUCK_HIGH;
            shutdown_reason <= ERROR_STUCK_HIGH;
          end else begin
            error_code <= ERROR_DUTY_LIMIT;
            shutdown_reason <= ERROR_DUTY_LIMIT;
            duty_violation_count <= duty_violation_count + 1'b1;
          end
        end
      end else if (stop_pulse && (state != S_IDLE)) begin
        state <= S_IDLE;
        fail_pulse <= 1'b1;
        tx_fail_count <= tx_fail_count + 1'b1;
        error_code <= ERROR_STOPPED;
      end else begin
        if (clear_pulse) begin
          error_code <= 32'd0;
          retry_count <= 32'd0;
          retry_exhausted_count <= 32'd0;
          tx_fail_count <= 32'd0;
          duty_violation_count <= 32'd0;
          shutdown_reason <= 32'd0;
        end
        unique case (state)
          S_IDLE: begin
        timeout_counter <= 32'd0;
        turnaround_counter <= 32'd0;
            if (start_pulse) begin
              active_session <= cfg_session;
              active_lane_mask <= cfg_lane_mask;
              active_ack_mask <= cfg_ack_lane_mask;
              active_payload_len <= cfg_payload_len;
              active_timeout_cycles <= (cfg_timeout_cycles == 0) ? 32'd1 : cfg_timeout_cycles;
              active_payload_crc32 <= tx_payload_crc32;
              active_sequence <= next_sequence;
              active_frame_bytes <= cfg_payload_len + 16'd18;
              retry_in_transaction <= 8'd0;
              rx_good_mask <= 2'b00;
              error_code <= 32'd0;
              state <= S_WAIT_READY;
            end
          end
          S_WAIT_READY: begin
            if (ready) begin
              timeout_counter <= 32'd0;
              state <= S_PREP_DATA;
            end else if (timeout_counter >= active_timeout_cycles - 1'b1) begin
              state <= S_IDLE;
              timeout_pulse <= 1'b1;
              fail_pulse <= 1'b1;
              tx_fail_count <= tx_fail_count + 1'b1;
              error_code <= ERROR_DATA_TIMEOUT;
            end else timeout_counter <= timeout_counter + 1'b1;
          end
          S_PREP_DATA: begin
            tx_symbol_index <= 12'd0;
            tx_symbol_cycle <= 16'd0;
            timeout_counter <= 32'd0;
            state <= S_TX_DATA;
          end
          S_TX_DATA: begin
            if (tx_symbol_cycle >= SYMBOL_CYCLES - 1) begin
              tx_symbol_cycle <= 16'd0;
              if (tx_symbol_index >= (PREAMBLE_SYMBOLS + active_frame_bytes * 4 - 1)) begin
                tx_symbol_index <= 12'd0;
                timeout_counter <= 32'd0;
                state <= S_WAIT_DATA;
              end else tx_symbol_index <= tx_symbol_index + 1'b1;
            end else tx_symbol_cycle <= tx_symbol_cycle + 1'b1;
          end
          S_WAIT_DATA: begin
            if ((data_good_mask & active_lane_mask[1:0]) == active_lane_mask[1:0]) begin
              timeout_counter <= 32'd0;
              turnaround_counter <= 32'd0;
              state <= S_GUARD_ACK;
            end else if (timeout_counter >= active_timeout_cycles - 1'b1) begin
              if (retry_in_transaction < MAX_RETRY) begin
                retry_in_transaction <= retry_in_transaction + 1'b1;
                retry_count <= retry_count + 1'b1;
                timeout_counter <= 32'd0;
                state <= S_PREP_DATA;
              end else begin
                state <= S_IDLE;
                timeout_pulse <= 1'b1;
                fail_pulse <= 1'b1;
                retry_exhausted_count <= retry_exhausted_count + 1'b1;
                tx_fail_count <= tx_fail_count + 1'b1;
                error_code <= ERROR_DATA_TIMEOUT;
              end
            end else timeout_counter <= timeout_counter + 1'b1;
          end
          S_GUARD_ACK: begin
            if (turnaround_counter >= TURNAROUND_CYCLES - 1) begin
              turnaround_counter <= 32'd0;
              state <= S_PREP_ACK;
            end else begin
              turnaround_counter <= turnaround_counter + 1'b1;
            end
          end
          S_PREP_ACK: begin
            ack_symbol_index <= 9'd0;
            ack_symbol_cycle <= 16'd0;
            timeout_counter <= 32'd0;
            state <= S_TX_ACK;
          end
          S_TX_ACK: begin
            if (ack_symbol_cycle >= SYMBOL_CYCLES - 1) begin
              ack_symbol_cycle <= 16'd0;
              if (ack_symbol_index >= (PREAMBLE_SYMBOLS + ACK_FRAME_BYTES * 4 - 1)) begin
                ack_symbol_index <= 9'd0;
                ack_sent_count <= ack_sent_count + 1'b1;
                timeout_counter <= 32'd0;
                state <= S_WAIT_ACK;
              end else ack_symbol_index <= ack_symbol_index + 1'b1;
            end else ack_symbol_cycle <= ack_symbol_cycle + 1'b1;
          end
          S_WAIT_ACK: begin
            if ((ack_good_mask & active_ack_mask[1:0]) == active_ack_mask[1:0]) begin
              state <= S_IDLE;
              done_pulse <= 1'b1;
              rx_good_mask <= data_good_mask;
              ack_seen_count <= ack_seen_count + 1'b1;
              next_sequence <= active_sequence + 1'b1;
              timeout_counter <= 32'd0;
            end else if (timeout_counter >= active_timeout_cycles - 1'b1) begin
              if (retry_in_transaction < MAX_RETRY) begin
                retry_in_transaction <= retry_in_transaction + 1'b1;
                retry_count <= retry_count + 1'b1;
                timeout_counter <= 32'd0;
                state <= S_PREP_DATA;
              end else begin
                state <= S_IDLE;
                timeout_pulse <= 1'b1;
                fail_pulse <= 1'b1;
                retry_exhausted_count <= retry_exhausted_count + 1'b1;
                tx_fail_count <= tx_fail_count + 1'b1;
                error_code <= ERROR_ACK_TIMEOUT;
              end
            end else timeout_counter <= timeout_counter + 1'b1;
          end
          default: state <= S_IDLE;
        endcase
      end
    end
  end
endmodule
