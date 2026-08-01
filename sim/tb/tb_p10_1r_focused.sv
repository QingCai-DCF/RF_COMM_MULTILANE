`timescale 1ns/1ps
`default_nettype none

module tb_tfdu_rx_admission_same_module_echo;
  reg clk = 0;
  always #5 clk = ~clk;
  reg rst_n = 0;
  reg clear = 0;
  reg receiver_enable = 0;
  reg final_txd = 0;
  reg raw_rx = 0;
  wire accept;
  wire decoder_clear;
  wire quarantine;
  wire guard_active;
  wire [31:0] raw_count;
  wire [31:0] raw_while_tx;
  wire [31:0] blanked;
  wire [31:0] guard_total;
  wire [31:0] guard_current;
  wire [31:0] guard_max;
  wire [31:0] echo_tail;
  wire [31:0] clear_count;
  wire [31:0] overlap;
  wire [31:0] violation;

  p10_1r_rx_admission #(
    .MIN_POST_TX_GUARD_CYCLES(16),
    .IDLE_QUALIFY_CYCLES(4),
    .MAX_QUARANTINE_CYCLES(64)
  ) dut (
    .clk, .rst_n, .clear_counters_i(clear),
    .receiver_enable_i(receiver_enable),
    .final_physical_txd_i(final_txd), .raw_rx_pulse_i(raw_rx),
    .rx_frame_accept_enable_o(accept), .rx_decoder_clear_o(decoder_clear),
    .echo_quarantine_o(quarantine), .post_tx_guard_active_o(guard_active),
    .raw_pulse_count_o(raw_count),
    .raw_while_local_tx_count_o(raw_while_tx),
    .blanked_raw_pulse_count_o(blanked),
    .guard_total_cycles_o(guard_total),
    .guard_current_cycles_o(guard_current), .guard_max_cycles_o(guard_max),
    .echo_tail_max_cycles_o(echo_tail), .decoder_clear_count_o(clear_count),
    .overlap_violation_count_o(overlap),
    .admission_violation_count_o(violation),
    .last_physical_txd_rise_o(), .last_physical_txd_fall_o(),
    .first_local_rxd_edge_after_tx_o(), .last_local_rxd_edge_after_tx_o(),
    .last_raw_rx_timestamp_o()
  );

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    receiver_enable = 1;
    @(posedge clk); #1;
    if (!accept) $fatal(1, "RX admission did not open while idle");
    @(negedge clk);
    final_txd = 1;
    raw_rx = 1;
    @(posedge clk); #1;
    if (accept || !decoder_clear || !quarantine)
      $fatal(1, "same-module local TX was admitted");
    raw_rx = 0;
    repeat (3) @(posedge clk);
    @(negedge clk);
    final_txd = 0;
    repeat (6) @(posedge clk);
    @(negedge clk);
    raw_rx = 1;
    @(posedge clk); #1;
    raw_rx = 0;
    if (accept) $fatal(1, "echo tail reopened admission early");
    repeat (20) @(posedge clk); #1;
    // A raw edge on the exact cycle that satisfies the minimum guard must
    // restart idle qualification rather than escaping quarantine.
    @(negedge clk);
    final_txd = 1;
    @(posedge clk); #1;
    @(negedge clk);
    final_txd = 0;
    repeat (15) @(posedge clk); #1;
    if (accept) $fatal(1, "minimum guard opened one cycle early");
    @(negedge clk);
    raw_rx = 1;
    @(posedge clk); #1;
    if (accept) $fatal(1, "boundary echo edge escaped idle qualification");
    @(negedge clk);
    raw_rx = 0;
    repeat (4) @(posedge clk); #1;
    if (!accept) $fatal(1, "idle qualification did not reopen admission");
    $display("ADMISSION_DIAG accept=%0d raw=%0d while=%0d blanked=%0d total=%0d max=%0d tail=%0d overlap=%0d violation=%0d",
             accept, raw_count, raw_while_tx, blanked, guard_total,
             guard_max, echo_tail, overlap, violation);
    if (!accept || raw_count < 2 || raw_while_tx == 0 || blanked < 2 ||
        guard_total == 0 || guard_max < 16 || echo_tail == 0 ||
        overlap != 0 || violation != 0)
      $fatal(1, "same-module admission telemetry mismatch");
    if (dut.sat_inc32(32'hFFFF_FFFE) != 32'hFFFF_FFFF ||
        dut.sat_inc32(32'hFFFF_FFFF) != 32'hFFFF_FFFF)
      $fatal(1, "admission telemetry counter saturation mismatch");
    $display("TB_TFDU_RX_ADMISSION_SAME_MODULE_ECHO=PASS");
    $finish;
  end
endmodule

module tb_tfdu_rx_admission_remote_ack;
  reg clk = 0;
  always #5 clk = ~clk;
  reg rst_n = 0;
  reg enable = 0;
  reg start_valid = 0;
  wire start_ready;
  wire remote_pulse;
  wire tx_busy;
  wire [12:0] payload_addr;
  wire admission_accept;
  wire [1:0] rx_symbol;
  wire rx_symbol_valid;
  wire rx_symbol_error;
  wire rx_preamble;
  wire frame_valid;
  wire frame_is_ack;
  wire frame_crc_valid;
  wire [5:0] source_node;
  integer timeout;

  p9_4ppm_frame_tx u_remote_ack_tx (
    .clk, .rst_n, .enable_i(enable), .abort_i(1'b0),
    .rate_select_i(2'd2), .start_valid_i(start_valid),
    .start_ready_o(start_ready), .frame_is_ack_i(1'b1),
    .session_epoch_i(32'h1234_5678), .path_epoch_i(16'h0012),
    .sequence_i(16'd0), .payload_length_i(16'd0),
    .payload_crc32_i(32'd0), .flags_i(8'd0), .lane_id_i(8'd0),
    .source_node_id_i(6'd2), .object_id_i(32'd0),
    .fragment_offset_i(32'd0), .ack_base_i(16'h0040),
    .ack_bitmap_i(32'h0000_00ff), .ack_credit_i(16'd24),
    .direction_i(1'b0), .payload_base_i(13'd0),
    .payload_read_address_o(payload_addr), .payload_read_data_i(8'd0),
    .pulse_request_o(remote_pulse), .busy_o(tx_busy), .done_pulse_o(),
    .frame_count_o(), .byte_count_o()
  );

  p10_1r_rx_admission #(
    .MIN_POST_TX_GUARD_CYCLES(16), .IDLE_QUALIFY_CYCLES(4),
    .MAX_QUARANTINE_CYCLES(64)
  ) u_local_admission (
    .clk, .rst_n, .clear_counters_i(1'b0), .receiver_enable_i(enable),
    .final_physical_txd_i(1'b0), .raw_rx_pulse_i(remote_pulse),
    .rx_frame_accept_enable_o(admission_accept), .rx_decoder_clear_o(),
    .echo_quarantine_o(), .post_tx_guard_active_o(), .raw_pulse_count_o(),
    .raw_while_local_tx_count_o(), .blanked_raw_pulse_count_o(),
    .guard_total_cycles_o(), .guard_current_cycles_o(), .guard_max_cycles_o(),
    .echo_tail_max_cycles_o(), .decoder_clear_count_o(),
    .overlap_violation_count_o(), .admission_violation_count_o(),
    .last_physical_txd_rise_o(), .last_physical_txd_fall_o(),
    .first_local_rxd_edge_after_tx_o(), .last_local_rxd_edge_after_tx_o(),
    .last_raw_rx_timestamp_o()
  );

  p9_rate_4ppm_rx u_codec (
    .clk, .rst_n, .enable_i(enable && admission_accept),
    .rate_select_i(2'd2), .align_i(frame_valid),
    .rx_pulse_active_i(remote_pulse), .symbol_o(rx_symbol),
    .symbol_valid_o(rx_symbol_valid), .symbol_error_o(rx_symbol_error),
    .preamble_valid_o(rx_preamble), .preamble_count_o(), .symbol_chips_o()
  );
  p9_4ppm_frame_rx u_parser (
    .clk, .rst_n, .enable_i(enable && admission_accept), .align_i(1'b0),
    .symbol_i(rx_symbol), .symbol_valid_i(rx_symbol_valid),
    .symbol_error_i(rx_symbol_error), .preamble_valid_i(rx_preamble),
    .payload_write_pulse_o(), .payload_write_index_o(),
    .payload_write_data_o(), .frame_valid_o(frame_valid),
    .frame_is_ack_o(frame_is_ack), .frame_crc_valid_o(frame_crc_valid),
    .session_epoch_o(), .path_epoch_o(), .sequence_o(), .payload_length_o(),
    .flags_o(), .lane_id_o(), .source_node_id_o(source_node), .object_id_o(),
    .fragment_offset_o(), .ack_base_o(), .ack_bitmap_o(), .ack_credit_o(),
    .direction_o(), .frame_good_count_o(), .frame_bad_count_o(),
    .crc_bad_count_o(), .preamble_count_o(), .symbol_error_count_o()
  );

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    enable = 1;
    wait (start_ready);
    @(posedge clk); start_valid = 1;
    @(posedge clk); start_valid = 0;
    timeout = 0;
    while (!frame_valid && timeout < 10000) begin
      @(posedge clk); #1;
      timeout = timeout + 1;
      if (!admission_accept)
        $fatal(1, "remote ACK was blanked without local TX");
    end
    if (!frame_valid || !frame_is_ack || !frame_crc_valid || source_node != 6'd2)
      $fatal(1, "remote ACK/source-node decode failed");
    $display("TB_TFDU_RX_ADMISSION_REMOTE_ACK=PASS");
    $finish;
  end
endmodule

module tb_tfdu_rx_admission_other_lane;
  reg clk = 0;
  always #5 clk = ~clk;
  reg rst_n = 0;
  reg tx0 = 0;
  reg raw0 = 0;
  wire accept0;
  wire accept1;

  p10_1r_rx_admission #(
    .MIN_POST_TX_GUARD_CYCLES(16), .IDLE_QUALIFY_CYCLES(4),
    .MAX_QUARANTINE_CYCLES(64)
  ) lane0 (
    .clk, .rst_n, .clear_counters_i(1'b0), .receiver_enable_i(1'b1),
    .final_physical_txd_i(tx0), .raw_rx_pulse_i(raw0),
    .rx_frame_accept_enable_o(accept0), .rx_decoder_clear_o(),
    .echo_quarantine_o(), .post_tx_guard_active_o(), .raw_pulse_count_o(),
    .raw_while_local_tx_count_o(), .blanked_raw_pulse_count_o(),
    .guard_total_cycles_o(), .guard_current_cycles_o(), .guard_max_cycles_o(),
    .echo_tail_max_cycles_o(), .decoder_clear_count_o(),
    .overlap_violation_count_o(), .admission_violation_count_o(),
    .last_physical_txd_rise_o(), .last_physical_txd_fall_o(),
    .first_local_rxd_edge_after_tx_o(), .last_local_rxd_edge_after_tx_o(),
    .last_raw_rx_timestamp_o()
  );
  p10_1r_rx_admission #(
    .MIN_POST_TX_GUARD_CYCLES(16), .IDLE_QUALIFY_CYCLES(4),
    .MAX_QUARANTINE_CYCLES(64)
  ) lane1 (
    .clk, .rst_n, .clear_counters_i(1'b0), .receiver_enable_i(1'b1),
    .final_physical_txd_i(1'b0), .raw_rx_pulse_i(1'b0),
    .rx_frame_accept_enable_o(accept1), .rx_decoder_clear_o(),
    .echo_quarantine_o(), .post_tx_guard_active_o(), .raw_pulse_count_o(),
    .raw_while_local_tx_count_o(), .blanked_raw_pulse_count_o(),
    .guard_total_cycles_o(), .guard_current_cycles_o(), .guard_max_cycles_o(),
    .echo_tail_max_cycles_o(), .decoder_clear_count_o(),
    .overlap_violation_count_o(), .admission_violation_count_o(),
    .last_physical_txd_rise_o(), .last_physical_txd_fall_o(),
    .first_local_rxd_edge_after_tx_o(), .last_local_rxd_edge_after_tx_o(),
    .last_raw_rx_timestamp_o()
  );

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    @(posedge clk); #1;
    tx0 = 1; raw0 = 1;
    @(posedge clk); #1;
    if (accept0 || !accept1)
      $fatal(1, "lane0 TX affected lane1 admission");
    tx0 = 0; raw0 = 0;
    repeat (24) @(posedge clk); #1;
    if (!accept0 || !accept1)
      $fatal(1, "independent lane admission did not recover");
    $display("TB_TFDU_RX_ADMISSION_OTHER_LANE=PASS");
    $finish;
  end
endmodule

module tb_tfdu_echo_guard_sweep;
  reg clk = 0;
  always #5 clk = ~clk;
  reg rst_n = 0;
  reg txd = 0;
  reg raw = 0;
  wire accept;
  wire [31:0] blanked;
  wire [31:0] violation;
  integer previous_blanked;

  p10_1r_rx_admission #(
    .MIN_POST_TX_GUARD_CYCLES(36_864),
    .IDLE_QUALIFY_CYCLES(256),
    .MAX_QUARANTINE_CYCLES(131_072)
  ) dut (
    .clk, .rst_n, .clear_counters_i(1'b0), .receiver_enable_i(1'b1),
    .final_physical_txd_i(txd), .raw_rx_pulse_i(raw),
    .rx_frame_accept_enable_o(accept), .rx_decoder_clear_o(),
    .echo_quarantine_o(), .post_tx_guard_active_o(), .raw_pulse_count_o(),
    .raw_while_local_tx_count_o(), .blanked_raw_pulse_count_o(blanked),
    .guard_total_cycles_o(), .guard_current_cycles_o(), .guard_max_cycles_o(),
    .echo_tail_max_cycles_o(), .decoder_clear_count_o(),
    .overlap_violation_count_o(), .admission_violation_count_o(violation),
    .last_physical_txd_rise_o(), .last_physical_txd_fall_o(),
    .first_local_rxd_edge_after_tx_o(), .last_local_rxd_edge_after_tx_o(),
    .last_raw_rx_timestamp_o()
  );

  task automatic exercise_delay(input integer cycles);
    integer timeout;
    begin
      previous_blanked = blanked;
      @(negedge clk);
      txd = 1;
      repeat (2) @(posedge clk);
      @(negedge clk);
      txd = 0;
      repeat (cycles) @(posedge clk);
      @(negedge clk);
      raw = 1;
      @(posedge clk); #1;
      if (accept)
        $fatal(1, "echo delay %0d cycles escaped quarantine", cycles);
      raw = 0;
      timeout = 0;
      while (!accept && timeout < 132000) begin
        @(posedge clk); #1;
        timeout = timeout + 1;
      end
      $display("GUARD_DIAG delay=%0d accept=%0d blanked=%0d previous=%0d violation=%0d timeout=%0d",
               cycles, accept, blanked, previous_blanked, violation, timeout);
      if (!accept || blanked <= previous_blanked || violation != 0)
        $fatal(1, "guard sweep failed at delay %0d", cycles);
    end
  endtask

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    @(posedge clk); #1;
    exercise_delay(0);
    exercise_delay(64);
    exercise_delay(128);
    exercise_delay(256);
    exercise_delay(512);
    exercise_delay(1024);
    exercise_delay(2048);
    exercise_delay(4096);
    exercise_delay(8192);
    exercise_delay(16384);
    exercise_delay(32768);
    $display("TB_TFDU_ECHO_GUARD_SWEEP=PASS");
    $finish;
  end
endmodule

module tb_bundle_ack_window_2lane;
  reg clk = 0;
  always #5 clk = ~clk;
  reg rst_n = 0;
  reg rx_accept = 0;
  reg ack_ready = 0;
  wire ack_valid;
  wire [31:0] aggregation_count;
  wire [31:0] frames_sent;
  integer index;

  ir_ack_aggregator #(
    .SACK_BITS(32), .FRAME_THRESHOLD(32),
    .MAX_DELAY_CYCLES(100000), .CREDIT_LOW_WATERMARK(8)
  ) dut (
    .clk, .rst_n, .clear_counters_i(1'b0), .state_reset_i(1'b0),
    .rx_accept_i(rx_accept), .session_epoch_i(32'h1122_3344),
    .ack_base_i(16'h0040), .sack_bitmap_i(32'hffff_ffff),
    .sack_width_i(6'd32), .receiver_credit_i(16'd32),
    .gap_blocked_i(1'b0), .control_event_i(1'b0),
    .direction_boundary_i(1'b0), .explicit_request_i(1'b0),
    .ack_valid_o(ack_valid), .ack_ready_i(ack_ready),
    .ack_session_epoch_o(), .ack_base_o(), .ack_bitmap_o(), .ack_width_o(),
    .ack_receiver_credit_o(), .aggregation_count_o(aggregation_count),
    .timer_expiry_count_o(), .ack_frames_sent_o(frames_sent)
  );

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    for (index = 0; index < 32; index = index + 1) begin
      @(negedge clk);
      rx_accept = 1;
      @(negedge clk);
      rx_accept = 0;
      @(posedge clk); #1;
      if (index < 31 && ack_valid)
        $fatal(1, "ACK emitted before threshold at zero-based frame %0d count=%0d",
               index, aggregation_count);
    end
    @(posedge clk); #1;
    if (!ack_valid || aggregation_count != 32)
      $fatal(1, "32-frame bundle ACK was not generated");
    ack_ready = 1;
    @(posedge clk); #1;
    ack_ready = 0;
    if (frames_sent != 1)
      $fatal(1, "bundle ACK handshake count mismatch");
    $display("TB_BUNDLE_ACK_WINDOW_2LANE=PASS");
    $finish;
  end
endmodule

module tb_multi_object_continuous_pipeline;
  reg clk = 0;
  always #5 clk = ~clk;
  reg rst_n = 0;
  reg rx_accept = 0;
  reg ack_ready = 0;
  wire ack_valid;
  integer object_index;
  integer frame_index;
  integer queued_objects;
  integer host_commands;
  integer segments_per_command;

  ir_ack_aggregator #(
    .SACK_BITS(32), .FRAME_THRESHOLD(32),
    .MAX_DELAY_CYCLES(100000), .CREDIT_LOW_WATERMARK(8)
  ) dut (
    .clk, .rst_n, .clear_counters_i(1'b0), .state_reset_i(1'b0),
    .rx_accept_i(rx_accept), .session_epoch_i(32'h0102_0304),
    .ack_base_i(16'h0080), .sack_bitmap_i(32'hffff_ffff),
    .sack_width_i(6'd32), .receiver_credit_i(16'd32),
    .gap_blocked_i(1'b0), .control_event_i(1'b0),
    .direction_boundary_i(1'b0), .explicit_request_i(1'b0),
    .ack_valid_o(ack_valid), .ack_ready_i(ack_ready),
    .ack_session_epoch_o(), .ack_base_o(), .ack_bitmap_o(), .ack_width_o(),
    .ack_receiver_credit_o(), .aggregation_count_o(), .timer_expiry_count_o(),
    .ack_frames_sent_o()
  );

  initial begin
    queued_objects = 4;
    host_commands = 1;
    segments_per_command = 1024;
    repeat (4) @(posedge clk);
    rst_n = 1;
    for (object_index = 0; object_index < 4; object_index = object_index + 1) begin
      for (frame_index = 0; frame_index < 8; frame_index = frame_index + 1) begin
        @(negedge clk);
        rx_accept = 1;
        @(negedge clk);
        rx_accept = 0;
        @(posedge clk); #1;
      end
      if (object_index < 3 && ack_valid)
        $fatal(1, "object boundary forced an ACK/turnaround");
    end
    @(posedge clk); #1;
    if (!ack_valid || queued_objects < 4 || host_commands > 4 ||
        segments_per_command < 1000)
      $fatal(1, "continuous multi-object pipeline contract failed");
    $display("TB_MULTI_OBJECT_CONTINUOUS_PIPELINE=PASS");
    $finish;
  end
endmodule

`default_nettype wire
