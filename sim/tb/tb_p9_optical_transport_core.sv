`timescale 1ns/1ps
`default_nettype none

module tb_p9_optical_transport_core;
  localparam integer MAX_OBJECT_BYTES = 8192;

  logic clk = 0;
  logic rst_n = 0;
  always #7.8125 clk = ~clk;

  logic receiver_enable;
  logic arm_request;
  logic disarm_request;
  logic full_shutdown_request;
  logic clear_counters;
  logic start_object;
  logic abort_object;
  logic [1:0] cfg_lane_mask;
  logic [15:0] cfg_lane_weights;
  logic [1:0] cfg_rate_select;
  logic cfg_direction;
  logic [31:0] cfg_session_epoch;
  logic [15:0] cfg_path_epoch;
  logic [31:0] cfg_object_id;
  logic [15:0] cfg_initial_sequence;
  logic [31:0] cfg_fault_flags;
  logic [7:0] cfg_drop_data_count;
  logic [7:0] cfg_drop_ack_count;
  logic [1:0] cfg_lane_unavailable;
  logic raw_start;
  logic raw_direction;
  logic [1:0] raw_lane_mask;
  logic [31:0] raw_pulse_target;
  logic [31:0] raw_spacing_cycles;

  logic s_axis_tvalid;
  wire s_axis_tready;
  logic [31:0] s_axis_tdata;
  logic [3:0] s_axis_tkeep;
  logic s_axis_tlast;
  wire m_axis_tvalid;
  logic m_axis_tready;
  wire [31:0] m_axis_tdata;
  wire [3:0] m_axis_tkeep;
  wire m_axis_tlast;

  wire [1:0] a_txd, a_sd, a_mode;
  wire [1:0] b_txd, b_sd, b_mode;
  localparam integer TB_TFDU_TURNAROUND_CYCLES = 4_096;
  logic [12:0] a_rx_recovery_cycles [0:1];
  logic [12:0] b_rx_recovery_cycles [0:1];
  logic [1:0] serializer_busy_previous;
  wire [1:0] combined_txd = a_txd | b_txd;
  // The frozen stationary Z7010 fixture exposes a selected-lane pulse at
  // both same-lane receivers.  Model that profile-specific near-end
  // visibility while the DUT continues to decode only the selected
  // destination side for each frame direction.  A module's receiver needs
  // the same conservative recovery interval after its own complete TX frame
  // that the stationary hardware requires before the opposite direction may
  // begin.  This catches missing guards in either DATA-to-ACK or ACK-to-DATA
  // transitions without weakening the exact same-lane raw visibility model.
  wire [1:0] a_rxd = ~(combined_txd & {
      a_rx_recovery_cycles[1] == 0,
      a_rx_recovery_cycles[0] == 0
  });
  wire [1:0] b_rxd = ~(combined_txd & {
      b_rx_recovery_cycles[1] == 0,
      b_rx_recovery_cycles[0] == 0
  });
  wire endpoint_armed;
  wire tx_kill_active;
  wire [3:0] phy_ready_mask;
  wire [3:0] startup_done_mask;
  wire [3:0] safety_fault_mask;
  wire object_active;
  wire object_done;
  wire object_fail;
  wire [31:0] object_error;
  wire input_complete;
  wire output_complete;
  wire [31:0] input_byte_count;
  wire [31:0] output_byte_count;
  wire raw_busy;
  wire raw_done;
  wire [31:0] raw_sent_count;
  wire [15:0] tx_next_sequence;
  wire [15:0] tx_ack_base;
  wire [5:0] tx_outstanding_count;
  wire [5:0] tx_outstanding_high_watermark;
  wire [15:0] rx_base_sequence;
  wire [31:0] rx_sack_bitmap;
  wire [31:0] tx_attempt_count;
  wire [31:0] tx_retry_count;
  wire [31:0] tx_retry_exhausted_count;
  wire [31:0] tx_timeout_count;
  wire [31:0] tx_duplicate_ack_count;
  wire [31:0] tx_migration_count;
  wire [31:0] rx_duplicate_count;
  wire [31:0] rx_out_of_order_count;
  wire [31:0] rx_old_count;
  wire [31:0] rx_future_count;
  wire [31:0] rx_stale_session_count;
  wire [31:0] rx_stale_path_count;
  wire [31:0] rx_gap_count;
  wire [31:0] rx_delivery_count;
  wire [31:0] ack_frames_sent;
  wire [63:0] scheduler_frames_flat;
  wire [31:0] physical_data_frames_good;
  wire [31:0] physical_ack_frames_good;
  wire [31:0] physical_crc_bad;
  wire [31:0] physical_symbol_error_count;
  wire [31:0] physical_frame_bad;
  wire [31:0] physical_drop_data_count;
  wire [31:0] physical_drop_ack_count;
  wire [127:0] tx_high_max_flat;
  wire [127:0] physical_tx_counts_flat;
  wire [127:0] raw_rx_counts_flat;
  wire [127:0] duty_high_max_flat;
  wire [31:0] duty_hard_limit_cycles;
  wire [31:0] duty_target_limit_cycles;

  logic capture_clear;
  integer captured_count;
  logic captured_last;
  logic [7:0] received [0:MAX_OBJECT_BYTES-1];

  function automatic [7:0] payload_pattern(input integer index, input integer seed);
    payload_pattern = ((index * 37) ^ (index >> 2) ^ seed) & 8'hff;
  endfunction

  function automatic integer keep_bytes(input [3:0] keep);
    case (keep)
      4'h1: keep_bytes = 1;
      4'h3: keep_bytes = 2;
      4'h7: keep_bytes = 3;
      4'hf: keep_bytes = 4;
      default: keep_bytes = 0;
    endcase
  endfunction

  always_ff @(posedge clk or negedge rst_n) begin : capture_output
    integer byte_lane;
    if (!rst_n) begin
      captured_count <= 0;
      captured_last <= 0;
    end else if (capture_clear) begin
      captured_count <= 0;
      captured_last <= 0;
    end else if (m_axis_tvalid && m_axis_tready) begin
      if (!m_axis_tlast && m_axis_tkeep !== 4'hf)
        $fatal(1, "non-final AXI DMA beat contains a TKEEP hole: %x",
               m_axis_tkeep);
      if (m_axis_tlast && !(m_axis_tkeep inside {4'h1, 4'h3, 4'h7, 4'hf}))
        $fatal(1, "final AXI DMA beat has non-contiguous TKEEP: %x",
               m_axis_tkeep);
      for (byte_lane = 0; byte_lane < 4; byte_lane = byte_lane + 1)
        if (m_axis_tkeep[byte_lane])
          received[captured_count + byte_lane] <= m_axis_tdata[8*byte_lane +: 8];
      captured_count <= captured_count + keep_bytes(m_axis_tkeep);
      if (m_axis_tlast) captured_last <= 1;
    end
  end

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .WINDOW_SIZE(32), .SACK_BITS(32),
    // Keep simulation accelerated relative to the 4,000,000-cycle hardware
    // RTO, but leave enough time for multiple DATA frames, turnaround, ACK
    // serialization, and the bounded ACK-reclaim scan.
    .MAX_PAYLOAD_BYTES(247), .STORE_ADDR_WIDTH(13), .RTO_CYCLES(500_000)
  ) dut (
    .clk, .rst_n,
    .receiver_enable_i(receiver_enable), .arm_request_i(arm_request),
    .disarm_request_i(disarm_request), .full_shutdown_request_i(full_shutdown_request),
    .clear_counters_i(clear_counters), .start_object_i(start_object),
    .abort_object_i(abort_object), .cfg_lane_mask_i(cfg_lane_mask),
    .cfg_lane_weights_i(cfg_lane_weights), .cfg_rate_select_i(cfg_rate_select),
    .cfg_direction_i(cfg_direction), .cfg_session_epoch_i(cfg_session_epoch),
    .cfg_path_epoch_i(cfg_path_epoch), .cfg_object_id_i(cfg_object_id),
    .cfg_initial_sequence_i(cfg_initial_sequence),
    .cfg_fault_flags_i(cfg_fault_flags),
    .cfg_drop_data_count_i(cfg_drop_data_count),
    .cfg_drop_ack_count_i(cfg_drop_ack_count),
    .cfg_lane_unavailable_i(cfg_lane_unavailable),
    .raw_start_i(raw_start), .raw_direction_i(raw_direction),
    .raw_lane_mask_i(raw_lane_mask), .raw_pulse_target_i(raw_pulse_target),
    .raw_spacing_cycles_i(raw_spacing_cycles),
    .s_axis_tvalid_i(s_axis_tvalid), .s_axis_tready_o(s_axis_tready),
    .s_axis_tdata_i(s_axis_tdata), .s_axis_tkeep_i(s_axis_tkeep),
    .s_axis_tlast_i(s_axis_tlast), .m_axis_tvalid_o(m_axis_tvalid),
    .m_axis_tready_i(m_axis_tready), .m_axis_tdata_o(m_axis_tdata),
    .m_axis_tkeep_o(m_axis_tkeep), .m_axis_tlast_o(m_axis_tlast),
    .a_rxd_i(a_rxd), .a_txd_o(a_txd), .a_sd_o(a_sd), .a_mode_o(a_mode),
    .b_rxd_i(b_rxd), .b_txd_o(b_txd), .b_sd_o(b_sd), .b_mode_o(b_mode),
    .endpoint_armed_o(endpoint_armed), .tx_kill_active_o(tx_kill_active),
    .phy_ready_mask_o(phy_ready_mask), .startup_done_mask_o(startup_done_mask),
    .safety_fault_mask_o(safety_fault_mask), .object_active_o(object_active),
    .object_done_o(object_done), .object_fail_o(object_fail),
    .object_error_o(object_error), .input_complete_o(input_complete),
    .output_complete_o(output_complete), .input_byte_count_o(input_byte_count),
    .output_byte_count_o(output_byte_count), .raw_busy_o(raw_busy),
    .raw_done_o(raw_done), .raw_sent_count_o(raw_sent_count),
    .tx_next_sequence_o(tx_next_sequence),
    .tx_ack_base_o(tx_ack_base), .tx_outstanding_count_o(tx_outstanding_count),
    .tx_outstanding_high_watermark_o(tx_outstanding_high_watermark),
    .rx_base_sequence_o(rx_base_sequence), .rx_sack_bitmap_o(rx_sack_bitmap),
    .tx_attempt_count_o(tx_attempt_count), .tx_retry_count_o(tx_retry_count),
    .tx_retry_exhausted_count_o(tx_retry_exhausted_count),
    .tx_timeout_count_o(tx_timeout_count),
    .tx_duplicate_ack_count_o(tx_duplicate_ack_count),
    .tx_stale_ack_count_o(), .tx_out_of_window_ack_count_o(),
    .tx_migration_count_o(tx_migration_count),
    .rx_duplicate_count_o(rx_duplicate_count),
    .rx_stale_session_count_o(rx_stale_session_count),
    .rx_out_of_order_count_o(rx_out_of_order_count),
    .rx_old_count_o(rx_old_count), .rx_future_count_o(rx_future_count),
    .rx_stale_path_count_o(rx_stale_path_count), .rx_gap_count_o(rx_gap_count),
    .rx_delivery_count_o(rx_delivery_count),
    .rx_protocol_error_count_o(), .ack_aggregation_count_o(),
    .ack_timer_expiry_count_o(), .ack_frames_sent_o(ack_frames_sent),
    .scheduler_frames_flat_o(scheduler_frames_flat), .scheduler_bytes_flat_o(),
    .scheduler_retries_flat_o(), .scheduler_migrations_flat_o(),
    .scheduler_maximum_starvation_o(),
    .physical_data_frames_good_o(physical_data_frames_good),
    .physical_ack_frames_good_o(physical_ack_frames_good),
    .physical_crc_bad_o(physical_crc_bad),
    .physical_frame_bad_o(physical_frame_bad), .physical_preamble_count_o(),
    .physical_symbol_error_count_o(physical_symbol_error_count),
    .physical_drop_data_count_o(physical_drop_data_count),
    .physical_drop_ack_count_o(physical_drop_ack_count),
    .raw_rx_counts_flat_o(raw_rx_counts_flat),
    .physical_tx_counts_flat_o(physical_tx_counts_flat),
    .tx_high_max_flat_o(tx_high_max_flat), .duty_high_max_flat_o(duty_high_max_flat),
    .duty_high_current_flat_o(), .duty_headroom_flat_o(),
    .duty_target_throttle_count_flat_o(), .duty_hard_fault_count_flat_o(),
    .duty_window_cycles_o(),
    .duty_hard_limit_cycles_o(duty_hard_limit_cycles),
    .duty_target_limit_cycles_o(duty_target_limit_cycles)
  );

  integer recovery_lane;
  always_ff @(posedge clk or negedge rst_n) begin : model_tfdu_turnaround_recovery
    if (!rst_n) begin
      serializer_busy_previous <= 0;
      for (recovery_lane = 0; recovery_lane < 2; recovery_lane = recovery_lane + 1) begin
        a_rx_recovery_cycles[recovery_lane] <= 0;
        b_rx_recovery_cycles[recovery_lane] <= 0;
      end
    end else begin
      for (recovery_lane = 0; recovery_lane < 2; recovery_lane = recovery_lane + 1) begin
        serializer_busy_previous[recovery_lane] <= dut.serializer_busy[recovery_lane];
        if (serializer_busy_previous[recovery_lane] &&
            !dut.serializer_busy[recovery_lane] &&
            dut.lane_source_a[recovery_lane]) begin
          a_rx_recovery_cycles[recovery_lane] <= TB_TFDU_TURNAROUND_CYCLES;
        end else if (a_rx_recovery_cycles[recovery_lane] != 0) begin
          a_rx_recovery_cycles[recovery_lane] <=
              a_rx_recovery_cycles[recovery_lane] - 1'b1;
        end
        if (serializer_busy_previous[recovery_lane] &&
            !dut.serializer_busy[recovery_lane] &&
            !dut.lane_source_a[recovery_lane]) begin
          b_rx_recovery_cycles[recovery_lane] <= TB_TFDU_TURNAROUND_CYCLES;
        end else if (b_rx_recovery_cycles[recovery_lane] != 0) begin
          b_rx_recovery_cycles[recovery_lane] <=
              b_rx_recovery_cycles[recovery_lane] - 1'b1;
        end
      end
    end
  end

  task automatic pulse_start;
    begin
      @(negedge clk);
      start_object = 1;
      @(posedge clk);
      @(negedge clk);
      start_object = 0;
    end
  endtask

  task automatic stream_object(input integer length, input integer seed);
    integer offset;
    integer bytes_this_word;
    integer lane;
    logic [31:0] word_value;
    logic [3:0] keep_value;
    begin
      offset = 0;
      while (offset < length) begin
        bytes_this_word = ((length - offset) >= 4) ? 4 : length - offset;
        word_value = 0;
        keep_value = 0;
        for (lane = 0; lane < bytes_this_word; lane = lane + 1) begin
          word_value[8*lane +: 8] = payload_pattern(offset + lane, seed);
          keep_value[lane] = 1;
        end
        @(negedge clk);
        s_axis_tvalid = 1;
        s_axis_tdata = word_value;
        s_axis_tkeep = keep_value;
        s_axis_tlast = (offset + bytes_this_word == length);
        do @(posedge clk); while (!s_axis_tready);
        @(negedge clk);
        s_axis_tvalid = 0;
        s_axis_tlast = 0;
        offset = offset + bytes_this_word;
      end
    end
  endtask

  task automatic run_object(
    input integer length,
    input integer seed,
    input logic direction,
    input integer drop_data,
    input integer drop_ack,
    input logic [15:0] initial_sequence,
    input logic [31:0] fault_flags
  );
    integer watchdog;
    integer index;
    integer expected_frames;
    logic [31:0] crc_before;
    logic [31:0] symbol_before;
    begin
      // Mirror the PS command lifecycle: every object begins from confirmed
      // full shutdown, then receiver startup, explicit arm, and telemetry
      // reset.  Duty history continues to age through shutdown and is not
      // erased by the counter clear.
      receiver_enable = 0;
      @(negedge clk); full_shutdown_request = 1;
      repeat (4) @(posedge clk);
      @(negedge clk); full_shutdown_request = 0; receiver_enable = 1;
      for (int object_ready_watchdog = 0;
           phy_ready_mask != 4'hf && object_ready_watchdog < 100_000;
           object_ready_watchdog = object_ready_watchdog + 1) @(posedge clk);
      if (phy_ready_mask != 4'hf || safety_fault_mask != 0)
        $fatal(1, "object lifecycle did not reach safe physical ready state");
      @(negedge clk); arm_request = 1;
      @(posedge clk); @(negedge clk); arm_request = 0;
      repeat (2) @(posedge clk);
      if (!endpoint_armed || tx_kill_active)
        $fatal(1, "object lifecycle explicit arm failed");
      cfg_direction = direction;
      cfg_session_epoch = cfg_session_epoch + 1;
      cfg_path_epoch = cfg_path_epoch + 1;
      cfg_object_id = cfg_object_id + 1;
      cfg_drop_data_count = drop_data;
      cfg_drop_ack_count = drop_ack;
      cfg_initial_sequence = initial_sequence;
      cfg_fault_flags = fault_flags;
      @(negedge clk);
      clear_counters = 1;
      @(posedge clk);
      @(negedge clk);
      clear_counters = 0;
      crc_before = physical_crc_bad;
      symbol_before = physical_symbol_error_count;
      capture_clear = 1;
      @(posedge clk);
      @(negedge clk);
      capture_clear = 0;
      pulse_start();
      watchdog = 0;
      while (!object_active && !object_fail && watchdog < 100) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (!object_active)
        $fatal(1, "object did not start dir=%0d error=%08x", direction, object_error);
      stream_object(length, seed);
      watchdog = 0;
      while (!object_done && !object_fail && watchdog < 5_000_000) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (object_fail) begin
        $display("CORE_FAIL_DIAG dir=%0d len=%0d attempts=%0d retries=%0d timeouts=%0d exhausted=%0d data=%0d ack=%0d crc=%0d frame_bad=%0d symbol_errors=%0d tx=%0d,%0d,%0d,%0d raw=%0d,%0d,%0d,%0d phase=%0d busy=%b rx_acquired=%0b rx_tick=%0d rx_chip=%0d rx_capture=%b chip_seen=%0b preambles=%0d parser_state=%0d",
                 direction, length, tx_attempt_count, tx_retry_count,
                 tx_timeout_count, tx_retry_exhausted_count,
                 physical_data_frames_good, physical_ack_frames_good,
                 physical_crc_bad, physical_frame_bad,
                 physical_symbol_error_count,
                 physical_tx_counts_flat[31:0], physical_tx_counts_flat[63:32],
                 physical_tx_counts_flat[95:64], physical_tx_counts_flat[127:96],
                 raw_rx_counts_flat[31:0], raw_rx_counts_flat[63:32],
                 raw_rx_counts_flat[95:64], raw_rx_counts_flat[127:96],
                 dut.phase_q, dut.serializer_busy,
                 dut.g_receive[0].u_codec.u_rx_4mbps.rx_phase_acquired,
                 dut.g_receive[0].u_codec.u_rx_4mbps.rx_tick,
                 dut.g_receive[0].u_codec.u_rx_4mbps.rx_chip_idx,
                 dut.g_receive[0].u_codec.u_rx_4mbps.rx_capture,
                 dut.g_receive[0].u_codec.u_rx_4mbps.chip_seen,
                 dut.rx_preamble_count[0], dut.g_receive[0].u_parser.state);
        $fatal(1, "object failed dir=%0d drops=%0d/%0d error=%08x",
               direction, drop_data, drop_ack, object_error);
      end
      if (!object_done) begin
        $display("CORE_DIAG dir=%0d len=%0d active=%0b in=%0b out=%0b bytes=%0d/%0d captured=%0d seq=%0d ack=%0d rxbase=%0d outstanding=%0d attempts=%0d retries=%0d timeouts=%0d data_good=%0d ack_good=%0d crc_bad=%0d phase=%0d",
                 direction, length, object_active, input_complete, output_complete,
                 input_byte_count, output_byte_count, captured_count,
                 tx_next_sequence, tx_ack_base, rx_base_sequence,
                 tx_outstanding_count, tx_attempt_count, tx_retry_count,
                 tx_timeout_count, physical_data_frames_good,
                 physical_ack_frames_good, physical_crc_bad, dut.phase_q);
        $fatal(1, "object completion timeout");
      end
      if (captured_count != length || !captured_last ||
          input_byte_count != length || output_byte_count != length)
        $fatal(1, "object byte accounting mismatch expected=%0d in=%0d out=%0d capture=%0d last=%0b",
               length, input_byte_count, output_byte_count, captured_count, captured_last);
      for (index = 0; index < length; index = index + 1)
        if (received[index] !== payload_pattern(index, seed))
          $fatal(1, "object byte mismatch dir=%0d index=%0d got=%02x expected=%02x",
                 direction, index, received[index], payload_pattern(index, seed));
      if (((fault_flags[4] == 0) && physical_crc_bad != crc_before) ||
          (fault_flags[4] && physical_crc_bad == crc_before) ||
          safety_fault_mask != 0 || tx_retry_exhausted_count != 0)
        $fatal(1, "integrity/safety counter failure crc=%0d safety=%x exhausted=%0d",
               physical_crc_bad, safety_fault_mask, tx_retry_exhausted_count);
      if (drop_data == 0 && drop_ack == 0 && fault_flags == 0) begin
        expected_frames = (length + 246) / 247;
        if (tx_retry_count != 0 || tx_timeout_count != 0 ||
            rx_duplicate_count != 0)
          $fatal(1, "clean object required retry/timeout/duplicate: retries=%0d timeouts=%0d duplicates=%0d attempts=%0d data=%0d acks=%0d txbase=%04x rxbase=%04x local=%04x/%08x peer=%04x/%08x",
                 tx_retry_count, tx_timeout_count, rx_duplicate_count,
                 tx_attempt_count, physical_data_frames_good,
                 physical_ack_frames_good, tx_ack_base, rx_base_sequence,
                 dut.dp_local_ack_base, dut.dp_local_ack_bitmap,
                 dut.dp_peer_ack_base_q, dut.dp_peer_ack_bitmap_q);
        if (physical_data_frames_good != expected_frames ||
            physical_crc_bad != crc_before ||
            physical_symbol_error_count != symbol_before)
          $fatal(1, "clean physical frame accounting mismatch expected=%0d good=%0d crc=%0d/%0d symbol=%0d/%0d",
                 expected_frames, physical_data_frames_good,
                 physical_crc_bad, crc_before,
                 physical_symbol_error_count, symbol_before);
      end
      $display("P9_CORE_OBJECT_PASS dir=%0d len=%0d drop_data=%0d drop_ack=%0d initial=%04x faults=%02x retries=%0d duplicates=%0d",
               direction, length, drop_data, drop_ack, initial_sequence,
               fault_flags[5:0], tx_retry_count, rx_duplicate_count);
      repeat (32) @(posedge clk);
    end
  endtask

  initial begin
    receiver_enable = 0;
    arm_request = 0;
    disarm_request = 0;
    full_shutdown_request = 0;
    clear_counters = 0;
    start_object = 0;
    abort_object = 0;
    cfg_lane_mask = 2'b11;
    cfg_lane_weights = 16'h0101;
    cfg_rate_select = 2'd2;
    cfg_direction = 0;
    cfg_session_epoch = 32'h5009_0000;
    cfg_path_epoch = 16'h0100;
    cfg_object_id = 32'h9000_0000;
    cfg_initial_sequence = 0;
    cfg_fault_flags = 0;
    cfg_drop_data_count = 0;
    cfg_drop_ack_count = 0;
    cfg_lane_unavailable = 0;
    raw_start = 0;
    raw_direction = 0;
    raw_lane_mask = 0;
    raw_pulse_target = 0;
    raw_spacing_cycles = 1024;
    s_axis_tvalid = 0;
    s_axis_tdata = 0;
    s_axis_tkeep = 0;
    s_axis_tlast = 0;
    m_axis_tready = 1;
    capture_clear = 0;

    repeat (8) @(posedge clk);
    rst_n = 1;
    @(posedge clk); #1;
    if ({b_sd, a_sd} != 4'hf || {b_txd, a_txd} != 0 || !tx_kill_active)
      $fatal(1, "reset did not fail closed");
    receiver_enable = 1;
    for (int ready_watchdog = 0; phy_ready_mask != 4'hf && ready_watchdog < 100_000;
         ready_watchdog = ready_watchdog + 1) begin
      @(posedge clk); #1;
      if (safety_fault_mask != 0) $fatal(1, "safety fault during startup");
    end
    if (phy_ready_mask != 4'hf || startup_done_mask != 4'hf)
      $fatal(1, "physical startup timeout ready=%x startup=%x", phy_ready_mask, startup_done_mask);
    @(negedge clk); arm_request = 1;
    @(posedge clk); @(negedge clk); arm_request = 0;
    repeat (2) @(posedge clk);
    if (!endpoint_armed || tx_kill_active) $fatal(1, "endpoint arm failed");

    // P9 CLEAR_COUNTERS is telemetry-only.  It must not invalidate the exact
    // duty-history ring or reopen the 1000 us TX-low cooldown.
    @(negedge clk); clear_counters = 1;
    @(posedge clk); @(negedge clk); clear_counters = 0;
    #1;
    if (phy_ready_mask != 4'hf || startup_done_mask != 4'hf ||
        !endpoint_armed || tx_kill_active)
      $fatal(1, "P9 telemetry clear invalidated safety/startup state");

    run_object(600, 8'h21, 1'b0, 0, 0, 16'h0000, 0);
    run_object(600, 8'h42, 1'b0, 1, 0, 16'h0100, 0);
    if (physical_drop_data_count != 1 || tx_retry_count == 0)
      $fatal(1, "DATA loss did not cause bounded retry");
    run_object(93, 8'h63, 1'b0, 0, 1, 16'h0200, 0);
    if (physical_drop_ack_count != 1 || rx_duplicate_count == 0)
      $fatal(1, "ACK loss did not recover through duplicate/re-ACK");
    run_object(600, 8'h84, 1'b1, 0, 0, 16'hfffe, 0);
    if (tx_next_sequence != 16'h0001 || tx_ack_base != 16'h0001 ||
        rx_base_sequence != 16'h0001)
      $fatal(1, "sequence wrap did not drain exactly next=%04x ack=%04x rx=%04x",
             tx_next_sequence, tx_ack_base, rx_base_sequence);

    run_object(91, 8'ha1, 1'b0, 0, 0, 16'h1000, 32'h01);
    if (rx_stale_session_count == 0 || tx_retry_count == 0)
      $fatal(1, "stale-session rejection/recovery not observed");
    run_object(91, 8'ha2, 1'b0, 0, 0, 16'h1100, 32'h02);
    if (rx_stale_path_count == 0 || tx_retry_count == 0)
      $fatal(1, "stale-path rejection/recovery not observed");
    run_object(91, 8'ha3, 1'b0, 0, 0, 16'h1200, 32'h04);
    if (rx_future_count == 0 || tx_retry_count == 0)
      $fatal(1, "future-window rejection/recovery not observed");
    run_object(91, 8'ha4, 1'b0, 0, 0, 16'h1300, 32'h08);
    if (rx_old_count == 0 || tx_retry_count == 0)
      $fatal(1, "old-sequence rejection/recovery not observed");
    run_object(91, 8'ha5, 1'b0, 0, 0, 16'h1400, 32'h10);
    if (physical_crc_bad == 0 || tx_retry_count == 0)
      $fatal(1, "CRC rejection/recovery not observed");
    run_object(91, 8'ha6, 1'b0, 0, 0, 16'h1500, 32'h20);
    if (tx_duplicate_ack_count == 0)
      $fatal(1, "duplicate ACK rejection not observed");
    run_object(600, 8'ha7, 1'b0, 0, 0, 16'h1600, 32'h40);
    if (rx_out_of_order_count == 0 || rx_gap_count == 0)
      $fatal(1, "out-of-order/SACK gap recovery not observed");
    if (tx_retry_count != 0 || tx_timeout_count != 0)
      $fatal(1, "SACK reorder recovery required an unnecessary retry");

    run_object(600, 8'hc7, 1'b0, 0, 0, 16'h2000, 0);

    // More than one full selective-repeat half-window is required here: the
    // former shared parser/codec tail kept the decoder running through each
    // variable inter-frame preparation gap and accumulated a chip-grid phase
    // error that short objects could not expose.
    cfg_rate_select = 2'd2;
    run_object(247*20, 8'hc8, 1'b0, 0, 0, 16'h3000, 0);

    if (scheduler_frames_flat[31:0] == 0 || scheduler_frames_flat[63:32] == 0)
      $fatal(1, "two-lane scheduler did not exercise both lanes: %h", scheduler_frames_flat);
    if (tx_high_max_flat[31:0] > 64 || tx_high_max_flat[63:32] > 64 ||
        tx_high_max_flat[95:64] > 64 || tx_high_max_flat[127:96] > 64)
      $fatal(1, "continuous-high safety maximum exceeded: %h", tx_high_max_flat);
    if (duty_hard_limit_cycles != 32'd12799 ||
        duty_target_limit_cycles != 32'd11520)
      $fatal(1, "noncanonical duty telemetry: hard=%0d target=%0d",
             duty_hard_limit_cycles, duty_target_limit_cycles);
    if (duty_high_max_flat[31:0] > duty_target_limit_cycles ||
        duty_high_max_flat[63:32] > duty_target_limit_cycles ||
        duty_high_max_flat[95:64] > duty_target_limit_cycles ||
        duty_high_max_flat[127:96] > duty_target_limit_cycles)
      $fatal(1, "rolling-duty 18 percent target exceeded: max=%h target=%0d",
             duty_high_max_flat, duty_target_limit_cycles);
    if (duty_target_limit_cycles == 0) $fatal(1, "invalid duty target telemetry");

    // Validation-only mapping and duty masks remove exactly one lane and
    // exercise the production scheduler defer inputs without creating permit.
    run_object(600, 8'hd1, 1'b0, 0, 0, 16'h2100, 32'h0000_0100);
    if (scheduler_frames_flat[31:0] != 0 || scheduler_frames_flat[63:32] == 0)
      $fatal(1, "mapping-invalid lane was scheduled: %h", scheduler_frames_flat);
    run_object(600, 8'hd2, 1'b1, 0, 0, 16'h2200, 32'h0000_0800);
    if (scheduler_frames_flat[31:0] == 0 || scheduler_frames_flat[63:32] != 0)
      $fatal(1, "duty-throttled lane was scheduled: %h", scheduler_frames_flat);

    // Drop the local arm while a long raw train is in progress.  Re-arming
    // must not resume any partial train or pulse.
    cfg_fault_flags = 0;
    raw_direction = 0;
    raw_lane_mask = 2'b11;
    raw_pulse_target = 1000;
    raw_spacing_cycles = 128;
    @(negedge clk); raw_start = 1;
    @(posedge clk); @(negedge clk); raw_start = 0;
    for (int raw_watchdog = 0; raw_sent_count < 4 && raw_watchdog < 2000;
         raw_watchdog = raw_watchdog + 1) @(posedge clk);
    if (!raw_busy || raw_sent_count < 4)
      $fatal(1, "raw disarm stimulus did not become active");
    @(negedge clk); disarm_request = 1;
    @(posedge clk); @(negedge clk); disarm_request = 0;
    repeat (4) @(posedge clk);
    if (raw_busy || endpoint_armed || !tx_kill_active || {b_txd, a_txd} != 0)
      $fatal(1, "disarm did not immediately kill and abort raw train");
    begin
      logic [127:0] stopped_counts;
      logic [31:0] stopped_sent;
      stopped_counts = physical_tx_counts_flat;
      stopped_sent = raw_sent_count;
      repeat (300) @(posedge clk);
      if (physical_tx_counts_flat != stopped_counts || raw_sent_count != stopped_sent)
        $fatal(1, "raw train advanced after disarm");
      @(negedge clk); arm_request = 1;
      @(posedge clk); @(negedge clk); arm_request = 0;
      repeat (300) @(posedge clk);
      if (!endpoint_armed || raw_busy || physical_tx_counts_flat != stopped_counts ||
          raw_sent_count != stopped_sent || {b_txd, a_txd} != 0)
        $fatal(1, "partial raw train resumed after explicit re-arm");
    end

    receiver_enable = 0;
    @(negedge clk); full_shutdown_request = 1;
    repeat (4) @(posedge clk);
    #1;
    if ({b_sd, a_sd} != 4'hf || {b_txd, a_txd} != 0 || endpoint_armed || !tx_kill_active)
      $fatal(1, "final shutdown did not fail closed");
    $display("TB_P9_OPTICAL_TRANSPORT_CORE=PASS");
    $finish;
  end
endmodule

`default_nettype wire
