`timescale 1ns/1ps

// Datasheet-timing regression for the P9 4 Mbit/s path.  A causal buffered
// timing shim measures each complete Txd-high segment, then maps 125 ns input
// pulses to 100..140 ns Rxd pulses and merged 250 ns inputs to 225..275 ns.
// This exercises the TFDU6102 FIR timing ranges and leading-edge jitter rather
// than an ideal logic loopback.  It is not an analog or acceptance model.
module tb_p9_tfdu_fir_frame_link #(
  parameter integer RX_125_WIDTH_NS = 120,
  parameter integer RX_250_WIDTH_NS = 250,
  parameter integer RX_JITTER_NS = 20
);
  logic clk = 0;
  logic rst_n = 0;
  always #7.8125 clk = ~clk;

  logic enable, abort, start_valid, start_ready, frame_is_ack, direction;
  logic model_rxd;
  logic model_rxd_ff1, model_rxd_sync;
  logic [1:0] rate_select;
  logic [31:0] session, object_id, fragment_offset, ack_bitmap;
  logic [15:0] path_epoch, tx_sequence, payload_length, ack_base, ack_credit;
  logic [7:0] flags, lane_id;
  logic [12:0] payload_base, payload_address;
  logic [7:0] payload_data;
  logic tx_pulse, tx_busy, tx_done;
  logic [31:0] tx_frames, tx_bytes, payload_crc32;
  logic [7:0] source [0:246];
  logic [7:0] received [0:246];

  logic rx_align;
  logic tx_busy_d;
  logic [7:0] rx_tail_window;
  logic [1:0] rx_symbol;
  logic rx_symbol_valid, rx_symbol_error, rx_preamble_valid;
  logic [15:0] rx_preamble_count;
  logic [3:0] rx_symbol_chips;
  logic rx_payload_we;
  logic [7:0] rx_payload_index, rx_payload_data;
  logic rx_frame_valid, rx_is_ack, rx_crc_valid;
  logic [31:0] rx_session, rx_object, rx_fragment, rx_ack_bitmap;
  logic [15:0] rx_path, rx_sequence, rx_length, rx_ack_base, rx_ack_credit;
  logic [7:0] rx_flags, rx_lane;
  logic rx_direction;
  logic [31:0] parser_good, parser_bad, parser_crc_bad;
  logic [31:0] parser_preambles, parser_symbol_errors;
  integer observed_tx_high_max, observed_tx_high_current;
  integer segment_count, current_segment, active_rx_segments;
  integer observed_125_segments, observed_250_segments, invalid_segments;
  logic segment_open;
  time segment_start [0:4095];
  integer segment_width_ns [0:4095];
  logic segment_ready [0:4095];

  always_comb payload_data = source[payload_address];
  always_ff @(posedge clk) begin
    if (rx_payload_we) received[rx_payload_index] <= rx_payload_data;
    if (!rst_n) begin
      observed_tx_high_max <= 0;
      observed_tx_high_current <= 0;
    end else if (tx_pulse) begin
      observed_tx_high_current <= observed_tx_high_current + 1;
      if (observed_tx_high_current + 1 > observed_tx_high_max)
        observed_tx_high_max <= observed_tx_high_current + 1;
    end else begin
      observed_tx_high_current <= 0;
    end
  end

  // Match the physical receive path used by tfdu_lane_phy.  The TFDU output
  // is asynchronous to the 64 MHz protocol clock and reaches the codec only
  // after the same two-flop synchronizer used in hardware.  Besides modeling
  // metastability containment, this quantizes the data-sheet edge jitter at
  // the exact boundary exercised by the implemented receiver.
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      model_rxd_ff1 <= 1'b1;
      model_rxd_sync <= 1'b1;
    end else begin
      model_rxd_ff1 <= model_rxd;
      model_rxd_sync <= model_rxd_ff1;
    end
  end

  p9_4ppm_frame_tx u_tx (
    .clk, .rst_n, .enable_i(enable), .abort_i(abort),
    .rate_select_i(rate_select), .start_valid_i(start_valid),
    .start_ready_o(start_ready), .frame_is_ack_i(frame_is_ack),
    .session_epoch_i(session), .path_epoch_i(path_epoch),
    .sequence_i(tx_sequence), .payload_length_i(payload_length),
    .payload_crc32_i(payload_crc32), .flags_i(flags), .lane_id_i(lane_id),
    .object_id_i(object_id), .fragment_offset_i(fragment_offset),
    .ack_base_i(ack_base), .ack_bitmap_i(ack_bitmap),
    .ack_credit_i(ack_credit), .direction_i(direction),
    .payload_base_i(payload_base), .payload_read_address_o(payload_address),
    .payload_read_data_i(payload_data), .pulse_request_o(tx_pulse),
    .busy_o(tx_busy), .done_pulse_o(tx_done), .frame_count_o(tx_frames),
    .byte_count_o(tx_bytes)
  );

  // Delay output by 500 ns so the complete input segment is known before its
  // mapped Rxd pulse starts.  The fixed delay is removed by preamble phase
  // acquisition and is well inside the receiver-tail bound used below.
  always @(posedge tx_pulse) begin : start_tfdu_segment
    integer new_segment;
    if (rst_n && enable) begin
      new_segment = segment_count;
      segment_count = segment_count + 1;
      current_segment = new_segment;
      segment_start[new_segment] = $time;
      segment_ready[new_segment] = 1'b0;
      segment_open = 1'b1;
      fork
        begin : emit_tfdu_segment
          automatic integer emit_segment = new_segment;
          automatic integer leading_jitter =
              ((new_segment & 1) == 0) ? RX_JITTER_NS : 0;
          #(500 + leading_jitter);
          wait (segment_ready[emit_segment]);
          active_rx_segments = active_rx_segments + 1;
          model_rxd = 1'b0;
          #(segment_width_ns[emit_segment]);
          active_rx_segments = active_rx_segments - 1;
          if (active_rx_segments == 0) model_rxd = 1'b1;
        end
      join_none
    end
  end

  always @(negedge tx_pulse) begin : finish_tfdu_segment
    integer input_width_ns;
    if (segment_open) begin
      segment_open = 1'b0;
      input_width_ns = $time - segment_start[current_segment];
      // $time rounds the 15.625 ns protocol clock edges to integer ns.
      if (input_width_ns >= 124 && input_width_ns <= 126)
        observed_125_segments = observed_125_segments + 1;
      else if (input_width_ns >= 249 && input_width_ns <= 251)
        observed_250_segments = observed_250_segments + 1;
      else invalid_segments = invalid_segments + 1;
      segment_width_ns[current_segment] =
          (input_width_ns <= 180) ? RX_125_WIDTH_NS : RX_250_WIDTH_NS;
      segment_ready[current_segment] = 1'b1;
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rx_tail_window <= 0;
      tx_busy_d <= 0;
    end else begin
      tx_busy_d <= tx_busy;
      // Match p9_optical_transport_core exactly: 64 protocol clocks cover the
      // 500 ns modeled TFDU latency, synchronizer latency and the widest Rxd
      // pulse, while ending before an idle all-zero symbol can be fabricated.
      if (tx_busy) rx_tail_window <= 8'd64;
      else if (rx_tail_window != 0) rx_tail_window <= rx_tail_window - 1'b1;
    end
  end
  assign rx_align = !(tx_busy || rx_tail_window != 0) || (tx_busy && !tx_busy_d);

  p9_rate_4ppm_rx u_codec (
    .clk, .rst_n, .enable_i(enable), .rate_select_i(rate_select),
    .align_i(rx_align), .rx_pulse_active_i(~model_rxd_sync),
    .symbol_o(rx_symbol), .symbol_valid_o(rx_symbol_valid),
    .symbol_error_o(rx_symbol_error), .preamble_valid_o(rx_preamble_valid),
    .preamble_count_o(rx_preamble_count), .symbol_chips_o(rx_symbol_chips)
  );

  p9_4ppm_frame_rx u_rx (
    .clk, .rst_n, .enable_i(enable), .align_i(rx_align),
    .symbol_i(rx_symbol), .symbol_valid_i(rx_symbol_valid),
    .symbol_error_i(rx_symbol_error), .preamble_valid_i(rx_preamble_valid),
    .payload_write_pulse_o(rx_payload_we),
    .payload_write_index_o(rx_payload_index),
    .payload_write_data_o(rx_payload_data), .frame_valid_o(rx_frame_valid),
    .frame_is_ack_o(rx_is_ack), .frame_crc_valid_o(rx_crc_valid),
    .session_epoch_o(rx_session), .path_epoch_o(rx_path),
    .sequence_o(rx_sequence), .payload_length_o(rx_length),
    .flags_o(rx_flags), .lane_id_o(rx_lane), .object_id_o(rx_object),
    .fragment_offset_o(rx_fragment), .ack_base_o(rx_ack_base),
    .ack_bitmap_o(rx_ack_bitmap), .ack_credit_o(rx_ack_credit),
    .direction_o(rx_direction), .frame_good_count_o(parser_good),
    .frame_bad_count_o(parser_bad), .crc_bad_count_o(parser_crc_bad),
    .preamble_count_o(parser_preambles),
    .symbol_error_count_o(parser_symbol_errors)
  );

  task automatic send_data(input integer length);
    integer watchdog;
    logic [31:0] crc;
    begin
      crc = 32'hFFFF_FFFF;
      for (int byte_index = 0; byte_index < length; byte_index++) begin
        for (int bit_index = 0; bit_index < 8; bit_index++)
          crc = (crc[0] ^ source[byte_index][bit_index]) ?
              ((crc >> 1) ^ 32'hEDB8_8320) : (crc >> 1);
      end
      payload_crc32 = ~crc;
      frame_is_ack = 0;
      payload_length = length;
      @(negedge clk); start_valid = 1;
      do @(posedge clk); while (!start_ready);
      @(negedge clk); start_valid = 0;
      watchdog = 0;
      while (!rx_frame_valid && watchdog < 250000) begin
        @(posedge clk); watchdog++;
      end
      if (!rx_frame_valid)
        $fatal(1, "FIR DATA timeout width=%0d/%0d jitter=%0d bad=%0d symerr=%0d",
               RX_125_WIDTH_NS, RX_250_WIDTH_NS, RX_JITTER_NS,
               parser_bad, parser_symbol_errors);
      if (!rx_crc_valid || rx_is_ack) $fatal(1, "FIR DATA CRC/type failure");
      if (rx_session != session || rx_path != path_epoch ||
          rx_sequence != tx_sequence || rx_length != length ||
          rx_flags != flags || rx_lane != lane_id || rx_object != object_id ||
          rx_fragment != fragment_offset)
        $fatal(1, "FIR DATA metadata failure");
      for (int idx = 0; idx < length; idx++)
        if (received[idx] !== source[idx]) $fatal(1, "FIR DATA byte %0d", idx);
      tx_sequence++;
      repeat (96) @(posedge clk);
    end
  endtask

  task automatic send_ack;
    integer watchdog;
    begin
      frame_is_ack = 1;
      payload_length = 0;
      @(negedge clk); start_valid = 1;
      do @(posedge clk); while (!start_ready);
      @(negedge clk); start_valid = 0;
      watchdog = 0;
      while (!rx_frame_valid && watchdog < 250000) begin
        @(posedge clk); watchdog++;
      end
      if (!rx_frame_valid || !rx_crc_valid || !rx_is_ack)
        $fatal(1, "FIR ACK failure good=%0d bad=%0d crc=%0d symerr=%0d",
               parser_good, parser_bad, parser_crc_bad, parser_symbol_errors);
      if (rx_ack_base != ack_base || rx_ack_bitmap != ack_bitmap ||
          rx_ack_credit != ack_credit || rx_direction != direction)
        $fatal(1, "FIR ACK metadata failure");
      repeat (96) @(posedge clk);
    end
  endtask

  initial begin
    enable = 0; abort = 0; start_valid = 0; frame_is_ack = 0;
    model_rxd = 1; segment_count = 0; current_segment = 0;
    active_rx_segments = 0; observed_125_segments = 0;
    observed_250_segments = 0; invalid_segments = 0; segment_open = 0;
    rate_select = 2;
    session = 32'h11223344; path_epoch = 16'h5566; tx_sequence = 16'hfffe;
    payload_length = 0; flags = 8'h01; lane_id = 8'h01;
    object_id = 32'h89abcdef; fragment_offset = 32'h00102030;
    ack_base = 16'h0007; ack_bitmap = 32'ha5c33c5a; ack_credit = 16'd29;
    direction = 1; payload_base = 0; payload_crc32 = 0;
    for (int idx = 0; idx < 247; idx++) begin
      source[idx] = (idx * 29 + 7) & 8'hff;
      received[idx] = 8'hxx;
    end
    repeat (8) @(posedge clk);
    rst_n = 1;
    enable = 1;
    repeat (8) @(posedge clk);
    send_data(1);
    send_data(31);
    send_data(247);
    send_ack();
    if (observed_tx_high_max > 16 || observed_125_segments == 0 ||
        observed_250_segments == 0 || invalid_segments != 0)
      $fatal(1, "invalid FIR Txd segments max=%0d 125ns=%0d 250ns=%0d other=%0d",
             observed_tx_high_max, observed_125_segments,
             observed_250_segments, invalid_segments);
    if (parser_bad != 0 || parser_crc_bad != 0 || parser_symbol_errors != 0)
      $fatal(1, "FIR parser errors bad=%0d crc=%0d symbol=%0d",
             parser_bad, parser_crc_bad, parser_symbol_errors);
    $display("P9_FIR_RX_125_WIDTH_NS=%0d", RX_125_WIDTH_NS);
    $display("P9_FIR_RX_250_WIDTH_NS=%0d", RX_250_WIDTH_NS);
    $display("P9_FIR_RX_JITTER_NS=%0d", RX_JITTER_NS);
    $display("P9_FIR_TX_PULSE_CYCLES=8");
    $display("TB_P9_TFDU_FIR_FRAME_LINK=PASS");
    $finish;
  end
endmodule

module tb_p9_tfdu_fir_frame_link_min;
  tb_p9_tfdu_fir_frame_link #(
    .RX_125_WIDTH_NS(100), .RX_250_WIDTH_NS(225), .RX_JITTER_NS(20)
  ) test();
endmodule

module tb_p9_tfdu_fir_frame_link_typ;
  tb_p9_tfdu_fir_frame_link #(
    .RX_125_WIDTH_NS(120), .RX_250_WIDTH_NS(250), .RX_JITTER_NS(20)
  ) test();
endmodule

module tb_p9_tfdu_fir_frame_link_max;
  tb_p9_tfdu_fir_frame_link #(
    .RX_125_WIDTH_NS(140), .RX_250_WIDTH_NS(275), .RX_JITTER_NS(20)
  ) test();
endmodule
