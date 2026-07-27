`timescale 1ns/1ps
module tb_p9_4ppm_frame_link;
  logic clk = 0;
  logic rst_n = 0;
  always #7.8125 clk = ~clk;

  logic enable, abort, start_valid, start_ready, frame_is_ack, direction;
  logic [1:0] rate_select;
  logic [31:0] session, object_id, fragment_offset, ack_bitmap;
  logic [15:0] path_epoch, tx_sequence, payload_length, ack_base, ack_credit;
  logic [7:0] flags, lane_id;
  logic [12:0] payload_base, payload_address;
  logic [7:0] payload_data;
  logic tx_pulse, tx_busy, tx_done;
  // The standalone link bench bypasses tfdu_lane_phy and the external TFDU
  // pair.  Preserve the stationary-fixture failure mode with a bounded path
  // delay: an 8-cycle pulse shifted by 12 cycles crosses a 16-cycle 2 Mbit/s
  // chip boundary unless the receiver acquires phase from the preamble.
  localparam integer RX_PATH_DELAY_CYCLES = 12;
  logic [RX_PATH_DELAY_CYCLES-1:0] rx_path_delay;
  wire delayed_rx_pulse = rx_path_delay[RX_PATH_DELAY_CYCLES-1];
  logic rx_align;
  logic [7:0] rx_tail_window;
  logic [31:0] tx_frames, tx_bytes;
  logic [31:0] payload_crc32;
  logic [7:0] source [0:246];
  logic [7:0] received [0:246];
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
  logic [31:0] parser_good, parser_bad, parser_crc_bad, parser_preambles, parser_symbol_errors;
  integer observed_tx_high_cycles, observed_symbols, observed_preambles;

  always_comb payload_data = source[payload_address];
  always_ff @(posedge clk) if (rx_payload_we) received[rx_payload_index] <= rx_payload_data;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) rx_path_delay <= '0;
    else rx_path_delay <= {rx_path_delay[RX_PATH_DELAY_CYCLES-2:0], tx_pulse};
  end
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      observed_tx_high_cycles <= 0;
      observed_symbols <= 0;
      observed_preambles <= 0;
    end else begin
      if (tx_pulse) observed_tx_high_cycles <= observed_tx_high_cycles + 1;
      if (rx_symbol_valid) observed_symbols <= observed_symbols + 1;
      if (rx_preamble_valid) observed_preambles <= observed_preambles + 1;
    end
  end

  p9_4ppm_frame_tx u_tx (
    .clk, .rst_n, .enable_i(enable), .abort_i(abort), .rate_select_i(rate_select),
    .start_valid_i(start_valid), .start_ready_o(start_ready), .frame_is_ack_i(frame_is_ack),
    .session_epoch_i(session), .path_epoch_i(path_epoch), .sequence_i(tx_sequence),
    .payload_length_i(payload_length), .payload_crc32_i(payload_crc32),
    .flags_i(flags), .lane_id_i(lane_id),
    .object_id_i(object_id), .fragment_offset_i(fragment_offset),
    .ack_base_i(ack_base), .ack_bitmap_i(ack_bitmap), .ack_credit_i(ack_credit),
    .direction_i(direction), .payload_base_i(payload_base),
    .payload_read_address_o(payload_address), .payload_read_data_i(payload_data),
    .pulse_request_o(tx_pulse), .busy_o(tx_busy), .done_pulse_o(tx_done),
    .frame_count_o(tx_frames), .byte_count_o(tx_bytes)
  );

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) rx_tail_window <= 0;
    else if (tx_busy) rx_tail_window <= 8'd32;
    else if (rx_tail_window != 0) rx_tail_window <= rx_tail_window - 1'b1;
  end
  assign rx_align = !(tx_busy || rx_tail_window != 0);

  p9_rate_4ppm_rx u_codec (
    .clk, .rst_n, .enable_i(enable), .rate_select_i(rate_select), .align_i(rx_align),
    .rx_pulse_active_i(delayed_rx_pulse), .symbol_o(rx_symbol), .symbol_valid_o(rx_symbol_valid),
    .symbol_error_o(rx_symbol_error), .preamble_valid_o(rx_preamble_valid),
    .preamble_count_o(rx_preamble_count), .symbol_chips_o(rx_symbol_chips)
  );

  p9_4ppm_frame_rx u_rx (
    .clk, .rst_n, .enable_i(enable), .align_i(rx_align), .symbol_i(rx_symbol),
    .symbol_valid_i(rx_symbol_valid), .symbol_error_i(rx_symbol_error),
    .preamble_valid_i(rx_preamble_valid), .payload_write_pulse_o(rx_payload_we),
    .payload_write_index_o(rx_payload_index), .payload_write_data_o(rx_payload_data),
    .frame_valid_o(rx_frame_valid), .frame_is_ack_o(rx_is_ack),
    .frame_crc_valid_o(rx_crc_valid), .session_epoch_o(rx_session),
    .path_epoch_o(rx_path), .sequence_o(rx_sequence), .payload_length_o(rx_length),
    .flags_o(rx_flags), .lane_id_o(rx_lane), .object_id_o(rx_object),
    .fragment_offset_o(rx_fragment), .ack_base_o(rx_ack_base),
    .ack_bitmap_o(rx_ack_bitmap), .ack_credit_o(rx_ack_credit),
    .direction_o(rx_direction), .frame_good_count_o(parser_good),
    .frame_bad_count_o(parser_bad), .crc_bad_count_o(parser_crc_bad),
    .preamble_count_o(parser_preambles), .symbol_error_count_o(parser_symbol_errors)
  );

  task automatic send_data(input logic [1:0] rate, input integer length);
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
      rate_select = rate;
      frame_is_ack = 0;
      payload_length = length;
      @(negedge clk);
      start_valid = 1;
      do @(posedge clk); while (!start_ready);
      @(negedge clk);
      start_valid = 0;
      watchdog = 0;
      while (!rx_frame_valid && watchdog < 200000) begin
        @(posedge clk);
        watchdog = watchdog + 1;
      end
      if (!rx_frame_valid) begin
        $display("DIAG rate=%0d tx_busy=%0b tx_done=%0b tx_frames=%0d tx_bytes=%0d tx_high=%0d symbols=%0d preamble_events=%0d parser_preambles=%0d parser_good=%0d parser_bad=%0d parser_crc_bad=%0d parser_symerr=%0d rx_state=%0d rx_byte=%0d rx_sym=%0d",
                 rate, tx_busy, tx_done, tx_frames, tx_bytes,
                 observed_tx_high_cycles, observed_symbols, observed_preambles,
                 parser_preambles, parser_good, parser_bad, parser_crc_bad,
                 parser_symbol_errors, u_rx.state, u_rx.byte_index, u_rx.symbol_index);
        $fatal(1, "DATA receive timeout rate=%0d", rate);
      end
      if (!rx_crc_valid || rx_is_ack) $fatal(1, "DATA CRC/type failure rate=%0d", rate);
      if (rx_session != session || rx_path != path_epoch || rx_sequence != tx_sequence ||
          rx_length != length || rx_flags != flags || rx_lane != lane_id ||
          rx_object != object_id || rx_fragment != fragment_offset)
        $fatal(1, "DATA metadata mismatch rate=%0d", rate);
      for (int idx = 0; idx < length; idx++)
        if (received[idx] !== source[idx]) $fatal(1, "DATA byte mismatch idx=%0d", idx);
      tx_sequence = tx_sequence + 1;
      repeat (32) @(posedge clk);
    end
  endtask

  task automatic send_ack;
    integer watchdog;
    begin
      rate_select = 2;
      frame_is_ack = 1;
      payload_length = 0;
      @(negedge clk);
      start_valid = 1;
      do @(posedge clk); while (!start_ready);
      @(negedge clk);
      start_valid = 0;
      watchdog = 0;
      while (!rx_frame_valid && watchdog < 200000) begin
        @(posedge clk);
        watchdog = watchdog + 1;
      end
      if (!rx_frame_valid) $fatal(1, "ACK receive timeout");
      if (!rx_crc_valid || !rx_is_ack) $fatal(1, "ACK CRC/type failure");
      if (rx_ack_base != ack_base || rx_ack_bitmap != ack_bitmap ||
          rx_ack_credit != ack_credit || rx_direction != direction)
        $fatal(1, "ACK metadata mismatch");
      repeat (32) @(posedge clk);
    end
  endtask

  initial begin
    enable = 0; abort = 0; start_valid = 0; frame_is_ack = 0; rate_select = 2;
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
    send_data(0, 1);
    send_data(1, 31);
    send_data(2, 247);
    send_ack();
    $display("TB_P9_4PPM_FRAME_LINK_DELAYED=PASS");
    $display("TB_P9_4PPM_FRAME_LINK=PASS");
    $finish;
  end
endmodule
