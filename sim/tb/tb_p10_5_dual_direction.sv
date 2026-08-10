`timescale 1ns/1ps
`default_nettype none

module tb_p10_5_dual_direction #(
  parameter bit ADJACENT_ONLY = 1'b0
);
  localparam integer LANE_COUNT = 4;
  localparam integer MAX_OBJECT_BYTES = 10000;
  localparam integer CREDIT_REOPEN_BYTES = 8500;
  localparam integer ADJACENT_OBJECT_BYTES = 496;

  logic f_clk = 0;
  logic r_clk = 0;
  logic rst_n = 0;
  always #7.8125 f_clk = ~f_clk;
  initial begin
    #2.3;
    // Independent clock object with a non-integral phase relationship.  The
    // nominal frequency matches the frozen 64 MHz board clock contract.
    forever #7.8125 r_clk = ~r_clk;
  end

  logic f_receiver_enable, r_receiver_enable;
  logic f_arm, r_arm, f_disarm, r_disarm;
  logic f_shutdown, r_shutdown, f_clear, r_clear;
  logic f_start, r_start, f_abort, r_abort;
  logic f_abort_tx, f_abort_rx, r_abort_tx, r_abort_rx;
  logic [31:0] f_tx_session, f_rx_session, r_tx_session, r_rx_session;
  logic [15:0] f_tx_path, f_rx_path, r_tx_path, r_rx_path;
  logic [31:0] f_tx_object, f_rx_object, r_tx_object, r_rx_object;
  logic [15:0] f_tx_initial, f_rx_initial, r_tx_initial, r_rx_initial;
  logic [15:0] f_role_cfg, r_role_cfg;
  logic [3:0] f_cfg_tx_mask, f_cfg_rx_mask;
  logic [3:0] r_cfg_tx_mask, r_cfg_rx_mask;

  logic f_s_valid, r_s_valid;
  wire f_s_ready, r_s_ready;
  logic [31:0] f_s_data, r_s_data;
  logic [3:0] f_s_keep, r_s_keep;
  logic f_s_last, r_s_last;
  wire f_m_valid, r_m_valid;
  wire [31:0] f_m_data, r_m_data;
  wire [3:0] f_m_keep, r_m_keep;
  wire f_m_last, r_m_last;
  logic f_m_ready, r_m_ready;

  wire [3:0] f_a_txd, f_a_sd, f_a_mode;
  wire [3:0] f_b_txd, f_b_sd, f_b_mode;
  wire [3:0] r_a_txd, r_a_sd, r_a_mode;
  wire [3:0] r_b_txd, r_b_sd, r_b_mode;
  wire [3:0] f_a_rxd = ~r_b_txd;
  wire [3:0] r_b_rxd = ~f_a_txd;

  wire f_armed, r_armed, f_tx_kill, r_tx_kill;
  wire [7:0] f_phy_ready, r_phy_ready, f_startup_done, r_startup_done;
  wire [7:0] f_safety_fault, r_safety_fault;
  wire f_object_active, r_object_active, f_object_done, r_object_done;
  wire f_object_fail, r_object_fail;
  wire [31:0] f_object_error, r_object_error;
  wire f_input_complete, r_input_complete, f_output_complete, r_output_complete;
  wire [31:0] f_input_bytes, r_input_bytes, f_output_bytes, r_output_bytes;
  wire [31:0] f_crc_bad, r_crc_bad, f_retry_exhausted, r_retry_exhausted;
  wire [31:0] f_retry_count, r_retry_count, f_timeout_count, r_timeout_count;
  wire [255:0] f_tx_high_max, r_tx_high_max, f_duty_high_max, r_duty_high_max;
  wire f_dual_active, r_dual_active;
  wire [3:0] f_tx_mask, f_rx_mask, r_tx_mask, r_rx_mask;
  wire [15:0] f_role_epoch, r_role_epoch;
  wire [31:0] f_piggy_tx, f_piggy_rx, r_piggy_tx, r_piggy_rx;
  wire [31:0] f_fallback, r_fallback, f_dir_reject, r_dir_reject;
  wire [31:0] f_epoch_reject, r_epoch_reject;
  wire f_tx_aborted, f_rx_aborted, r_tx_aborted, r_rx_aborted;

  logic capture_clear;
  integer f_capture_count, r_capture_count;
  logic f_capture_last, r_capture_last;
  logic [7:0] f_received [0:MAX_OBJECT_BYTES-1];
  logic [7:0] r_received [0:MAX_OBJECT_BYTES-1];
  integer simultaneous_physical_cycles;
  integer f_retry_before_adjacent, r_retry_before_adjacent;
  integer f_timeout_before_adjacent, r_timeout_before_adjacent;

  function automatic [7:0] payload_pattern(input integer index,
                                            input integer seed);
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

  always_ff @(posedge f_clk or negedge rst_n) begin : fixed_capture
    integer byte_lane;
    if (!rst_n) begin
      f_capture_count <= 0;
      f_capture_last <= 0;
    end else begin
      if (capture_clear) begin
        f_capture_count <= 0;
        f_capture_last <= 0;
      end else if (f_m_valid && f_m_ready) begin
        if (!f_m_last && f_m_keep != 4'hf)
          $fatal(1, "fixed non-final AXI beat sparse TKEEP=%x", f_m_keep);
        for (byte_lane = 0; byte_lane < 4; byte_lane = byte_lane + 1)
          if (f_m_keep[byte_lane])
            f_received[f_capture_count + byte_lane] <=
                f_m_data[8*byte_lane +: 8];
        f_capture_count <= f_capture_count + keep_bytes(f_m_keep);
        if (f_m_last) f_capture_last <= 1;
      end
    end
  end

  always_ff @(posedge r_clk or negedge rst_n) begin : rotating_capture
    integer byte_lane;
    if (!rst_n) begin
      r_capture_count <= 0;
      r_capture_last <= 0;
    end else begin
      if (capture_clear) begin
        r_capture_count <= 0;
        r_capture_last <= 0;
      end else if (r_m_valid && r_m_ready) begin
        if (!r_m_last && r_m_keep != 4'hf)
          $fatal(1, "rotating non-final AXI beat sparse TKEEP=%x", r_m_keep);
        for (byte_lane = 0; byte_lane < 4; byte_lane = byte_lane + 1)
          if (r_m_keep[byte_lane])
            r_received[r_capture_count + byte_lane] <=
                r_m_data[8*byte_lane +: 8];
        r_capture_count <= r_capture_count + keep_bytes(r_m_keep);
        if (r_m_last) r_capture_last <= 1;
      end
    end
  end

  always_ff @(posedge f_clk or negedge rst_n) begin
    if (!rst_n) begin
      simultaneous_physical_cycles <= 0;
    end else begin
      if ((|f_a_txd) && (|r_b_txd))
        simultaneous_physical_cycles <= simultaneous_physical_cycles + 1;
      if (|(f_a_txd & f_cfg_rx_mask))
        $fatal(1, "fixed transmitted on LOCAL_RX_MASK: %x", f_a_txd);
      if (|(r_b_txd & r_cfg_rx_mask))
        $fatal(1, "rotating transmitted on LOCAL_RX_MASK: %x", r_b_txd);
      if (|(f_a_txd & r_b_txd))
        $fatal(1, "same physical lane TX/RX role overlap");
    end
  end

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(4), .WINDOW_SIZE(32), .SACK_BITS(32),
    .MAX_PAYLOAD_BYTES(247), .STORE_ADDR_WIDTH(13), .RTO_CYCLES(1_000_000),
    .ACK_FRAME_THRESHOLD(8), .ACK_MAX_DELAY_CYCLES(64_000),
    .CONTROL_COLLISION_BACKOFF_CYCLES(32_000),
    .DEPLOYMENT_ROLE(1), .P10_5_DUAL_CAPABLE(1)
  ) fixed_endpoint (
    .clk(f_clk), .rst_n, .receiver_enable_i(f_receiver_enable),
    .arm_request_i(f_arm), .disarm_request_i(f_disarm),
    .full_shutdown_request_i(f_shutdown), .forensic_fault_hold_i(1'b0),
    .clear_counters_i(f_clear), .start_object_i(f_start),
    .abort_object_i(f_abort), .cfg_lane_mask_i(f_cfg_tx_mask | f_cfg_rx_mask),
    .cfg_lane_weights_i(32'h0101_0101), .cfg_rate_select_i(2'd2),
    .cfg_direction_i(1'b0), .cfg_session_epoch_i(f_tx_session),
    .cfg_path_epoch_i(f_tx_path), .cfg_object_id_i(f_tx_object),
    .cfg_initial_sequence_i(f_tx_initial), .cfg_fault_flags_i(32'd0),
    .cfg_drop_data_count_i(8'd0), .cfg_drop_ack_count_i(8'd0),
    .cfg_lane_unavailable_i(4'd0),
    .cfg_p10_5_dual_direction_i(1'b1), .cfg_tx_lane_mask_i(f_cfg_tx_mask),
    .cfg_rx_lane_mask_i(f_cfg_rx_mask), .cfg_role_epoch_i(f_role_cfg),
    .cfg_rx_session_epoch_i(f_rx_session), .cfg_rx_path_epoch_i(f_rx_path),
    .cfg_rx_object_id_i(f_rx_object),
    .cfg_rx_initial_sequence_i(f_rx_initial),
    .abort_tx_context_i(f_abort_tx), .abort_rx_context_i(f_abort_rx),
    .local_source_test_inject_i(4'd0),
    .raw_start_i(1'b0), .raw_direction_i(1'b0), .raw_lane_mask_i(4'd0),
    .raw_pulse_target_i(32'd0), .raw_spacing_cycles_i(32'd128),
    .s_axis_tvalid_i(f_s_valid), .s_axis_tready_o(f_s_ready),
    .s_axis_tdata_i(f_s_data), .s_axis_tkeep_i(f_s_keep),
    .s_axis_tlast_i(f_s_last),
    .m_axis_tvalid_o(f_m_valid), .m_axis_tready_i(f_m_ready),
    .m_axis_tdata_o(f_m_data), .m_axis_tkeep_o(f_m_keep),
    .m_axis_tlast_o(f_m_last),
    .a_rxd_i(f_a_rxd), .a_txd_o(f_a_txd), .a_sd_o(f_a_sd),
    .a_mode_o(f_a_mode), .b_rxd_i(4'hf), .b_txd_o(f_b_txd),
    .b_sd_o(f_b_sd), .b_mode_o(f_b_mode),
    .endpoint_armed_o(f_armed), .tx_kill_active_o(f_tx_kill),
    .phy_ready_mask_o(f_phy_ready), .startup_done_mask_o(f_startup_done),
    .safety_fault_mask_o(f_safety_fault), .object_active_o(f_object_active),
    .object_done_o(f_object_done), .object_fail_o(f_object_fail),
    .object_error_o(f_object_error), .input_complete_o(f_input_complete),
    .output_complete_o(f_output_complete), .input_byte_count_o(f_input_bytes),
    .output_byte_count_o(f_output_bytes),
    .physical_crc_bad_o(f_crc_bad),
    .tx_retry_count_o(f_retry_count), .tx_timeout_count_o(f_timeout_count),
    .tx_retry_exhausted_count_o(f_retry_exhausted),
    .tx_high_max_flat_o(f_tx_high_max), .duty_high_max_flat_o(f_duty_high_max),
    .p10_5_dual_direction_active_o(f_dual_active),
    .p10_5_tx_lane_mask_o(f_tx_mask), .p10_5_rx_lane_mask_o(f_rx_mask),
    .p10_5_role_epoch_o(f_role_epoch),
    .p10_5_piggyback_ack_tx_count_o(f_piggy_tx),
    .p10_5_piggyback_ack_rx_count_o(f_piggy_rx),
    .p10_5_control_ack_fallback_count_o(f_fallback),
    .p10_5_direction_reject_count_o(f_dir_reject),
    .p10_5_role_epoch_reject_count_o(f_epoch_reject),
    .p10_5_tx_context_aborted_o(f_tx_aborted),
    .p10_5_rx_context_aborted_o(f_rx_aborted)
  );

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(4), .WINDOW_SIZE(32), .SACK_BITS(32),
    .MAX_PAYLOAD_BYTES(247), .STORE_ADDR_WIDTH(13), .RTO_CYCLES(1_000_000),
    .ACK_FRAME_THRESHOLD(8), .ACK_MAX_DELAY_CYCLES(64_000),
    .CONTROL_COLLISION_BACKOFF_CYCLES(32_000),
    .DEPLOYMENT_ROLE(2), .P10_5_DUAL_CAPABLE(1)
  ) rotating_endpoint (
    .clk(r_clk), .rst_n, .receiver_enable_i(r_receiver_enable),
    .arm_request_i(r_arm), .disarm_request_i(r_disarm),
    .full_shutdown_request_i(r_shutdown), .forensic_fault_hold_i(1'b0),
    .clear_counters_i(r_clear), .start_object_i(r_start),
    .abort_object_i(r_abort), .cfg_lane_mask_i(r_cfg_tx_mask | r_cfg_rx_mask),
    .cfg_lane_weights_i(32'h0101_0101), .cfg_rate_select_i(2'd2),
    .cfg_direction_i(1'b1), .cfg_session_epoch_i(r_tx_session),
    .cfg_path_epoch_i(r_tx_path), .cfg_object_id_i(r_tx_object),
    .cfg_initial_sequence_i(r_tx_initial), .cfg_fault_flags_i(32'd0),
    .cfg_drop_data_count_i(8'd0), .cfg_drop_ack_count_i(8'd0),
    .cfg_lane_unavailable_i(4'd0),
    .cfg_p10_5_dual_direction_i(1'b1), .cfg_tx_lane_mask_i(r_cfg_tx_mask),
    .cfg_rx_lane_mask_i(r_cfg_rx_mask), .cfg_role_epoch_i(r_role_cfg),
    .cfg_rx_session_epoch_i(r_rx_session), .cfg_rx_path_epoch_i(r_rx_path),
    .cfg_rx_object_id_i(r_rx_object),
    .cfg_rx_initial_sequence_i(r_rx_initial),
    .abort_tx_context_i(r_abort_tx), .abort_rx_context_i(r_abort_rx),
    .local_source_test_inject_i(4'd0),
    .raw_start_i(1'b0), .raw_direction_i(1'b0), .raw_lane_mask_i(4'd0),
    .raw_pulse_target_i(32'd0), .raw_spacing_cycles_i(32'd128),
    .s_axis_tvalid_i(r_s_valid), .s_axis_tready_o(r_s_ready),
    .s_axis_tdata_i(r_s_data), .s_axis_tkeep_i(r_s_keep),
    .s_axis_tlast_i(r_s_last),
    .m_axis_tvalid_o(r_m_valid), .m_axis_tready_i(r_m_ready),
    .m_axis_tdata_o(r_m_data), .m_axis_tkeep_o(r_m_keep),
    .m_axis_tlast_o(r_m_last),
    .a_rxd_i(4'hf), .a_txd_o(r_a_txd), .a_sd_o(r_a_sd),
    .a_mode_o(r_a_mode), .b_rxd_i(r_b_rxd), .b_txd_o(r_b_txd),
    .b_sd_o(r_b_sd), .b_mode_o(r_b_mode),
    .endpoint_armed_o(r_armed), .tx_kill_active_o(r_tx_kill),
    .phy_ready_mask_o(r_phy_ready), .startup_done_mask_o(r_startup_done),
    .safety_fault_mask_o(r_safety_fault), .object_active_o(r_object_active),
    .object_done_o(r_object_done), .object_fail_o(r_object_fail),
    .object_error_o(r_object_error), .input_complete_o(r_input_complete),
    .output_complete_o(r_output_complete), .input_byte_count_o(r_input_bytes),
    .output_byte_count_o(r_output_bytes),
    .physical_crc_bad_o(r_crc_bad),
    .tx_retry_count_o(r_retry_count), .tx_timeout_count_o(r_timeout_count),
    .tx_retry_exhausted_count_o(r_retry_exhausted),
    .tx_high_max_flat_o(r_tx_high_max), .duty_high_max_flat_o(r_duty_high_max),
    .p10_5_dual_direction_active_o(r_dual_active),
    .p10_5_tx_lane_mask_o(r_tx_mask), .p10_5_rx_lane_mask_o(r_rx_mask),
    .p10_5_role_epoch_o(r_role_epoch),
    .p10_5_piggyback_ack_tx_count_o(r_piggy_tx),
    .p10_5_piggyback_ack_rx_count_o(r_piggy_rx),
    .p10_5_control_ack_fallback_count_o(r_fallback),
    .p10_5_direction_reject_count_o(r_dir_reject),
    .p10_5_role_epoch_reject_count_o(r_epoch_reject),
    .p10_5_tx_context_aborted_o(r_tx_aborted),
    .p10_5_rx_context_aborted_o(r_rx_aborted)
  );

  task automatic stream_fixed(input integer length, input integer seed);
    integer offset, count, lane, ready_wait;
    logic [31:0] word_value;
    logic [3:0] keep_value;
    begin
      offset = 0;
      while (offset < length) begin
        count = ((length - offset) >= 4) ? 4 : length - offset;
        word_value = 0;
        keep_value = 0;
        for (lane = 0; lane < count; lane = lane + 1) begin
          word_value[8*lane +: 8] = payload_pattern(offset + lane, seed);
          keep_value[lane] = 1;
        end
        @(negedge f_clk);
        f_s_valid = 1;
        f_s_data = word_value;
        f_s_keep = keep_value;
        f_s_last = offset + count == length;
        ready_wait = 0;
        do begin
          @(posedge f_clk);
          ready_wait = ready_wait + 1;
          if (ready_wait >= 200_000)
            $fatal(1, "fixed AXI ingress stalled active=%0b fail=%0b error=%08x bytes=%0d",
                   f_object_active, f_object_fail, f_object_error, f_input_bytes);
        end while (!f_s_ready);
        @(negedge f_clk);
        f_s_valid = 0;
        f_s_last = 0;
        offset = offset + count;
      end
    end
  endtask

  task automatic stream_rotating(input integer length, input integer seed);
    integer offset, count, lane, ready_wait;
    logic [31:0] word_value;
    logic [3:0] keep_value;
    begin
      offset = 0;
      while (offset < length) begin
        count = ((length - offset) >= 4) ? 4 : length - offset;
        word_value = 0;
        keep_value = 0;
        for (lane = 0; lane < count; lane = lane + 1) begin
          word_value[8*lane +: 8] = payload_pattern(offset + lane, seed);
          keep_value[lane] = 1;
        end
        @(negedge r_clk);
        r_s_valid = 1;
        r_s_data = word_value;
        r_s_keep = keep_value;
        r_s_last = offset + count == length;
        ready_wait = 0;
        do begin
          @(posedge r_clk);
          ready_wait = ready_wait + 1;
          if (ready_wait >= 200_000)
            $fatal(1, "rotating AXI ingress stalled active=%0b fail=%0b error=%08x bytes=%0d",
                   r_object_active, r_object_fail, r_object_error, r_input_bytes);
        end while (!r_s_ready);
        @(negedge r_clk);
        r_s_valid = 0;
        r_s_last = 0;
        offset = offset + count;
      end
    end
  endtask

  task automatic pulse_starts;
    begin
      fork
        begin @(negedge f_clk); f_start = 1; @(posedge f_clk);
              @(negedge f_clk); f_start = 0; end
        begin @(negedge r_clk); r_start = 1; @(posedge r_clk);
              @(negedge r_clk); r_start = 0; end
      join
    end
  endtask

  task automatic wait_both_done(input integer watchdog_limit);
    integer watchdog;
    logic f_seen, r_seen;
    begin
      watchdog = 0;
      f_seen = 0;
      r_seen = 0;
      while (!(f_seen && r_seen) && watchdog < watchdog_limit) begin
        @(posedge f_clk); #1;
        if (f_object_done) f_seen = 1;
        if (r_object_done) r_seen = 1;
        if (f_object_fail || r_object_fail)
          $fatal(1, "dual object failed fixed=%08x rotating=%08x",
                 f_object_error, r_object_error);
        if ((watchdog % 50_000) == 49_999)
          $display("P10_5_WAIT watchdog=%0d active=%0b/%0b complete=%0b/%0b/%0b/%0b bytes=%0d/%0d/%0d/%0d outstanding=%0d/%0d phase=%0d/%0d piggy=%0d/%0d fallback=%0d/%0d",
                   watchdog + 1, f_object_active, r_object_active,
                   f_input_complete, f_output_complete,
                   r_input_complete, r_output_complete,
                   f_input_bytes, f_output_bytes, r_input_bytes, r_output_bytes,
                   fixed_endpoint.tx_outstanding_count_o,
                   rotating_endpoint.tx_outstanding_count_o,
                   fixed_endpoint.phase_q, rotating_endpoint.phase_q,
                   f_piggy_tx, r_piggy_tx, f_fallback, r_fallback);
        if ((watchdog % 50_000) == 49_999) begin
          $display("P10_5_FIXED_SCHED attempt=%0b lane=%0d ready=%b sched=%b duty_empty=%b schedule=%b busy=%b pending=%b kill=%0b armed=%0b phy=%b faults=%b",
                   fixed_endpoint.dp_attempt_valid,
                   fixed_endpoint.dp_attempt_lane,
                   fixed_endpoint.lane_runtime_ready,
                   fixed_endpoint.schedulable_lane_mask,
                   fixed_endpoint.data_duty_history_empty,
                   fixed_endpoint.data_frame_schedule_ready,
                   fixed_endpoint.serializer_busy,
                   fixed_endpoint.lane_start_pending,
                   f_tx_kill, f_armed, f_phy_ready, f_safety_fault);
          $display("P10_5_FIXED_DP txvalid=%0b inflight=%0b req=%0b/%0b decision=%0b/%0b/%0b live=%0b credit=%0d reset=%0b abort=%0b state=%b",
                   fixed_endpoint.u_data_plane.tx_attempt_valid,
                   fixed_endpoint.u_data_plane.request_inflight,
                   fixed_endpoint.u_data_plane.scheduler_request_valid,
                   fixed_endpoint.u_data_plane.scheduler_request_ready,
                   fixed_endpoint.u_data_plane.scheduler_decision_valid,
                   fixed_endpoint.u_data_plane.scheduler_decision_admit,
                   fixed_endpoint.u_data_plane.scheduler_decision_ready,
                   fixed_endpoint.u_data_plane.live_decision_transmit_ready,
                   fixed_endpoint.dp_peer_ack_credit_q,
                   fixed_endpoint.u_data_plane.effective_tx_session_reset,
                   fixed_endpoint.u_data_plane.effective_tx_abort,
                   {fixed_endpoint.u_data_plane.u_tx_window.entry_state[3],
                    fixed_endpoint.u_data_plane.u_tx_window.entry_state[2],
                    fixed_endpoint.u_data_plane.u_tx_window.entry_state[1],
                    fixed_endpoint.u_data_plane.u_tx_window.entry_state[0]});
          $display("P10_5_FIXED_RX admission=%b raw=%0d/%0d/%0d/%0d preamble=%0d/%0d/%0d/%0d good=%0d bad=%0d crc=%0d symbol=%0d pulses=%b",
                   fixed_endpoint.rx_admission_enable,
                   fixed_endpoint.a_raw_count[0], fixed_endpoint.a_raw_count[1],
                   fixed_endpoint.a_raw_count[2], fixed_endpoint.a_raw_count[3],
                   fixed_endpoint.rx_preamble_count[0],
                   fixed_endpoint.rx_preamble_count[1],
                   fixed_endpoint.rx_preamble_count[2],
                   fixed_endpoint.rx_preamble_count[3],
                   fixed_endpoint.physical_data_frames_good_o,
                   fixed_endpoint.physical_frame_bad_o,
                   fixed_endpoint.physical_crc_bad_o,
                   fixed_endpoint.physical_symbol_error_count_o,
                   fixed_endpoint.a_rx_pulse);
          $display("P10_5_ROT_SCHED attempt=%0b lane=%0d ready=%b sched=%b duty_empty=%b schedule=%b busy=%b pending=%b kill=%0b armed=%0b phy=%b faults=%b",
                   rotating_endpoint.dp_attempt_valid,
                   rotating_endpoint.dp_attempt_lane,
                   rotating_endpoint.lane_runtime_ready,
                   rotating_endpoint.schedulable_lane_mask,
                   rotating_endpoint.data_duty_history_empty,
                   rotating_endpoint.data_frame_schedule_ready,
                   rotating_endpoint.serializer_busy,
                   rotating_endpoint.lane_start_pending,
                   r_tx_kill, r_armed, r_phy_ready, r_safety_fault);
          $display("P10_5_ROT_DP txvalid=%0b inflight=%0b req=%0b/%0b decision=%0b/%0b/%0b live=%0b credit=%0d reset=%0b abort=%0b state=%b",
                   rotating_endpoint.u_data_plane.tx_attempt_valid,
                   rotating_endpoint.u_data_plane.request_inflight,
                   rotating_endpoint.u_data_plane.scheduler_request_valid,
                   rotating_endpoint.u_data_plane.scheduler_request_ready,
                   rotating_endpoint.u_data_plane.scheduler_decision_valid,
                   rotating_endpoint.u_data_plane.scheduler_decision_admit,
                   rotating_endpoint.u_data_plane.scheduler_decision_ready,
                   rotating_endpoint.u_data_plane.live_decision_transmit_ready,
                   rotating_endpoint.dp_peer_ack_credit_q,
                   rotating_endpoint.u_data_plane.effective_tx_session_reset,
                   rotating_endpoint.u_data_plane.effective_tx_abort,
                   {rotating_endpoint.u_data_plane.u_tx_window.entry_state[3],
                    rotating_endpoint.u_data_plane.u_tx_window.entry_state[2],
                    rotating_endpoint.u_data_plane.u_tx_window.entry_state[1],
                    rotating_endpoint.u_data_plane.u_tx_window.entry_state[0]});
          $display("P10_5_ROT_RX admission=%b raw=%0d/%0d/%0d/%0d preamble=%0d/%0d/%0d/%0d good=%0d bad=%0d crc=%0d symbol=%0d pulses=%b",
                   rotating_endpoint.rx_admission_enable,
                   rotating_endpoint.b_raw_count[0], rotating_endpoint.b_raw_count[1],
                   rotating_endpoint.b_raw_count[2], rotating_endpoint.b_raw_count[3],
                   rotating_endpoint.rx_preamble_count[0],
                   rotating_endpoint.rx_preamble_count[1],
                   rotating_endpoint.rx_preamble_count[2],
                   rotating_endpoint.rx_preamble_count[3],
                   rotating_endpoint.physical_data_frames_good_o,
                   rotating_endpoint.physical_frame_bad_o,
                   rotating_endpoint.physical_crc_bad_o,
                   rotating_endpoint.physical_symbol_error_count_o,
                   rotating_endpoint.b_rx_pulse);
        end
        watchdog = watchdog + 1;
      end
      if (!(f_seen && r_seen))
        $fatal(1, "dual object timed out active=%0b/%0b bytes=%0d/%0d/%0d/%0d",
               f_object_active, r_object_active, f_input_bytes, f_output_bytes,
               r_input_bytes, r_output_bytes);
    end
  endtask

  task automatic clear_capture;
    begin
      capture_clear = 1;
      repeat (3) @(posedge f_clk);
      capture_clear = 0;
    end
  endtask

  task automatic set_contexts(input [31:0] f_object,
                               input [31:0] r_object);
    begin
      f_tx_session = 32'h1111_0000 | {16'd0, f_object[15:0]};
      f_rx_session = 32'h8222_0000 | {16'd0, r_object[15:0]};
      r_tx_session = f_rx_session;
      r_rx_session = f_tx_session;
      f_tx_path = 16'h0101;
      f_rx_path = 16'h8202;
      r_tx_path = f_rx_path;
      r_rx_path = f_tx_path;
      f_tx_object = f_object;
      f_rx_object = r_object;
      r_tx_object = r_object;
      r_rx_object = f_object;
      f_tx_initial = 16'h0020;
      f_rx_initial = 16'h0020;
      r_tx_initial = 16'h0020;
      r_rx_initial = 16'h0020;
    end
  endtask

  task automatic run_adjacent_one_plus_one;
    integer adjacent_case;
    integer f_tx_lane;
    integer r_tx_lane;
    begin
      // Hardware-realistic adjacent 1+1: local TX and local RX occupy the two
      // modules of one connector.  Exercise both orientations on J10 and J11,
      // then repeat the first topology with fresh object/session identities.
      // P10.4 quarantine remains enabled throughout.
      f_retry_before_adjacent = f_retry_count;
      r_retry_before_adjacent = r_retry_count;
      f_timeout_before_adjacent = f_timeout_count;
      r_timeout_before_adjacent = r_timeout_count;
      for (adjacent_case = 0; adjacent_case < 5;
           adjacent_case = adjacent_case + 1) begin
        case (adjacent_case)
          0, 4: begin f_tx_lane = 0; r_tx_lane = 1; end
          1:    begin f_tx_lane = 1; r_tx_lane = 0; end
          2:    begin f_tx_lane = 2; r_tx_lane = 3; end
          default: begin f_tx_lane = 3; r_tx_lane = 2; end
        endcase
        f_cfg_tx_mask = 4'b0001 << f_tx_lane;
        f_cfg_rx_mask = 4'b0001 << r_tx_lane;
        r_cfg_tx_mask = 4'b0001 << r_tx_lane;
        r_cfg_rx_mask = 4'b0001 << f_tx_lane;
        set_contexts(32'h0000_0100 + adjacent_case,
                     32'h8000_0180 + adjacent_case);
        clear_capture();
        pulse_starts();
        repeat (4) @(posedge f_clk); #1;
        if (!f_object_active || !r_object_active ||
            f_object_fail || r_object_fail)
          $fatal(1, "adjacent 1+1 case %0d start failed active=%0b/%0b fail=%0b/%0b error=%08x/%08x",
                 adjacent_case, f_object_active, r_object_active,
                 f_object_fail, r_object_fail, f_object_error, r_object_error);
        fork
          stream_fixed(ADJACENT_OBJECT_BYTES, 8'h19 + adjacent_case);
          stream_rotating(ADJACENT_OBJECT_BYTES, 8'h91 + adjacent_case);
        join
        wait_both_done(4_000_000);
        if (f_tx_mask != f_cfg_tx_mask || f_rx_mask != f_cfg_rx_mask ||
            r_tx_mask != r_cfg_tx_mask || r_rx_mask != r_cfg_rx_mask)
          $fatal(1, "adjacent 1+1 case %0d role state mismatch", adjacent_case);
        if (f_input_bytes != ADJACENT_OBJECT_BYTES ||
            f_output_bytes != ADJACENT_OBJECT_BYTES ||
            r_input_bytes != ADJACENT_OBJECT_BYTES ||
            r_output_bytes != ADJACENT_OBJECT_BYTES ||
            f_capture_count != ADJACENT_OBJECT_BYTES ||
            r_capture_count != ADJACENT_OBJECT_BYTES)
          $fatal(1, "adjacent 1+1 case %0d byte accounting mismatch",
                 adjacent_case);
      end
      // A control-only ACK can deliberately preempt reverse DATA on the same
      // connector and force a bounded SR retry.  The acceptance contract is
      // progress without deadlock/exhaustion or integrity error, not zero
      // retries under this deliberately adversarial topology.
      if ((f_retry_count - f_retry_before_adjacent) > 5 ||
          (r_retry_count - r_retry_before_adjacent) > 5 ||
          (f_timeout_count - f_timeout_before_adjacent) !=
              (f_retry_count - f_retry_before_adjacent) ||
          (r_timeout_count - r_timeout_before_adjacent) !=
              (r_retry_count - r_retry_before_adjacent) ||
          f_retry_exhausted != 0 || r_retry_exhausted != 0 ||
          f_crc_bad != 0 || r_crc_bad != 0 ||
          simultaneous_physical_cycles == 0)
        $fatal(1, "adjacent 1+1 connector matrix was not bounded retry_delta=%0d/%0d timeout_delta=%0d/%0d exhaust=%0d/%0d crc=%0d/%0d fallback=%0d/%0d",
               f_retry_count - f_retry_before_adjacent,
               r_retry_count - r_retry_before_adjacent,
               f_timeout_count - f_timeout_before_adjacent,
               r_timeout_count - r_timeout_before_adjacent,
               f_retry_exhausted, r_retry_exhausted, f_crc_bad, r_crc_bad,
               f_fallback, r_fallback);
    end
  endtask

  integer watchdog, index, lane_index;
  integer f_fallback_before_credit_reopen;
  integer r_fallback_before_credit_reopen;
  initial begin
    f_receiver_enable = 0; r_receiver_enable = 0;
    f_arm = 0; r_arm = 0; f_disarm = 0; r_disarm = 0;
    f_shutdown = 0; r_shutdown = 0; f_clear = 0; r_clear = 0;
    f_start = 0; r_start = 0; f_abort = 0; r_abort = 0;
    f_abort_tx = 0; f_abort_rx = 0; r_abort_tx = 0; r_abort_rx = 0;
    f_s_valid = 0; f_s_data = 0; f_s_keep = 0; f_s_last = 0;
    r_s_valid = 0; r_s_data = 0; r_s_keep = 0; r_s_last = 0;
    f_m_ready = 1; r_m_ready = 1;
    capture_clear = 0;
    f_role_cfg = 1;
    r_role_cfg = 1;
    f_cfg_tx_mask = 4'h3;
    f_cfg_rx_mask = 4'hc;
    r_cfg_tx_mask = 4'hc;
    r_cfg_rx_mask = 4'h3;
    set_contexts(32'h0000_00a1, 32'h8000_00b2);

    repeat (10) @(posedge f_clk);
    rst_n = 1;
    repeat (3) @(posedge f_clk); #1;
    if (f_a_sd != 4'hf || r_b_sd != 4'hf || f_a_txd != 0 || r_b_txd != 0 ||
        !f_tx_kill || !r_tx_kill)
      $fatal(1, "reset did not fail closed");

    f_shutdown = 1; r_shutdown = 1;
    repeat (4) @(posedge f_clk);
    f_shutdown = 0; r_shutdown = 0;
    f_receiver_enable = 1; r_receiver_enable = 1;
    watchdog = 0;
    while ((f_phy_ready != 8'h0f || r_phy_ready != 8'hf0) &&
           watchdog < 100_000) begin
      @(posedge f_clk); #1;
      watchdog = watchdog + 1;
    end
    if (f_phy_ready != 8'h0f || r_phy_ready != 8'hf0 ||
        f_startup_done != 8'h0f || r_startup_done != 8'hf0 ||
        f_safety_fault != 0 || r_safety_fault != 0)
      $fatal(1, "startup failed ready=%x/%x startup=%x/%x fault=%x/%x",
             f_phy_ready, r_phy_ready, f_startup_done, r_startup_done,
             f_safety_fault, r_safety_fault);
    fork
      begin @(negedge f_clk); f_arm = 1; @(posedge f_clk);
            @(negedge f_clk); f_arm = 0; end
      begin @(negedge r_clk); r_arm = 1; @(posedge r_clk);
            @(negedge r_clk); r_arm = 0; end
    join
    repeat (4) @(posedge f_clk); #1;
    if (!f_armed || !r_armed || f_tx_kill || r_tx_kill)
      $fatal(1, "arm failed");

    if (ADJACENT_ONLY) begin
      run_adjacent_one_plus_one();
      f_receiver_enable = 0; r_receiver_enable = 0;
      f_shutdown = 1; r_shutdown = 1;
      repeat (6) @(posedge f_clk); #1;
      if (f_a_sd != 4'hf || r_b_sd != 4'hf || f_a_txd != 0 || r_b_txd != 0 ||
          f_armed || r_armed || !f_tx_kill || !r_tx_kill)
        $fatal(1, "adjacent 1+1 final shutdown did not fail closed");
      $display("TB_P10_5_ADJACENT_1PLUS1=PASS fallback=%0d/%0d",
               f_fallback, r_fallback);
      $finish;
    end

    // A CRC-valid vNext frame with a stale role generation is observed but
    // cannot advance either RX window, ACK state, DMA output, or object.
    f_role_cfg = 16'd1;
    r_role_cfg = 16'd2;
    clear_capture();
    pulse_starts();
    fork
      stream_fixed(247, 8'h11);
      stream_rotating(247, 8'h22);
    join
    watchdog = 0;
    while ((f_epoch_reject == 0 || r_epoch_reject == 0) &&
           watchdog < 150_000) begin
      @(posedge f_clk); #1;
      watchdog = watchdog + 1;
    end
    if (f_epoch_reject == 0 || r_epoch_reject == 0 ||
        f_output_bytes != 0 || r_output_bytes != 0)
      $fatal(1, "stale role epoch was not rejected without commit");
    fork
      begin @(negedge f_clk); f_abort = 1; @(posedge f_clk);
            @(negedge f_clk); f_abort = 0; end
      begin @(negedge r_clk); r_abort = 1; @(posedge r_clk);
            @(negedge r_clk); r_abort = 0; end
    join
    repeat (4) @(posedge f_clk);
    f_clear = 1; r_clear = 1;
    repeat (2) @(posedge f_clk);
    f_clear = 0; r_clear = 0;
    f_role_cfg = 16'd1;
    r_role_cfg = 16'd1;
    fork
      begin @(negedge f_clk); f_arm = 1; @(posedge f_clk);
            @(negedge f_clk); f_arm = 0; end
      begin @(negedge r_clk); r_arm = 1; @(posedge r_clk);
            @(negedge r_clk); r_arm = 0; end
    join
    repeat (4) @(posedge f_clk); #1;
    if (!f_armed || !r_armed || f_epoch_reject != 0 || r_epoch_reject != 0)
      $fatal(1, "stale-role recovery/clear failed");

    // Hold both AXI receive consumers until each selective-repeat window has
    // advertised zero credit. Releasing the consumers changes ACK base/SACK
    // and credit without accepting another optical DATA frame. A correct
    // implementation must therefore emit a fresh control-only ACK and reopen
    // both transmitters; relying only on rx_accept would deadlock here.
    clear_capture();
    f_m_ready = 0;
    r_m_ready = 0;
    pulse_starts();
    fork
      stream_fixed(CREDIT_REOPEN_BYTES, 8'h5a);
      stream_rotating(CREDIT_REOPEN_BYTES, 8'ha5);
      begin : credit_reopen_coordinator
        watchdog = 0;
        while ((fixed_endpoint.dp_peer_ack_credit_q != 0 ||
                rotating_endpoint.dp_peer_ack_credit_q != 0) &&
               watchdog < 5_000_000) begin
          @(posedge f_clk); #1;
          watchdog = watchdog + 1;
        end
        if (fixed_endpoint.dp_peer_ack_credit_q != 0 ||
            rotating_endpoint.dp_peer_ack_credit_q != 0)
          $fatal(1, "zero-credit setup did not fill both RX windows credit=%0d/%0d",
                 fixed_endpoint.dp_peer_ack_credit_q,
                 rotating_endpoint.dp_peer_ack_credit_q);
        f_fallback_before_credit_reopen = f_fallback;
        r_fallback_before_credit_reopen = r_fallback;
        repeat (8) @(posedge f_clk);
        f_m_ready = 1;
        r_m_ready = 1;
      end
    join
    wait_both_done(8_000_000);
    if (f_output_bytes != CREDIT_REOPEN_BYTES ||
        r_output_bytes != CREDIT_REOPEN_BYTES ||
        f_capture_count != CREDIT_REOPEN_BYTES ||
        r_capture_count != CREDIT_REOPEN_BYTES ||
        !f_capture_last || !r_capture_last)
      $fatal(1, "credit-reopen byte accounting mismatch");
    if (f_fallback <= f_fallback_before_credit_reopen ||
        r_fallback <= r_fallback_before_credit_reopen)
      $fatal(1, "delivery did not force fresh control ACK fallback=%0d/%0d before=%0d/%0d",
             f_fallback, r_fallback, f_fallback_before_credit_reopen,
             r_fallback_before_credit_reopen);
    for (index = 0; index < CREDIT_REOPEN_BYTES; index = index + 1) begin
      if (f_received[index] !== payload_pattern(index, 8'ha5)) begin
        $display("CREDIT_REOPEN_R2F_STORE tx2_0=%02x tx3_0=%02x rx0=%02x temp2_0=%02x temp3_0=%02x tx_next=%0d rx_base=%0d",
                 rotating_endpoint.tx_store[2][0],
                 rotating_endpoint.tx_store[3][0],
                 fixed_endpoint.rx_store[0],
                 fixed_endpoint.rx_temp[2][0],
                 fixed_endpoint.rx_temp[3][0],
                 rotating_endpoint.tx_next_sequence_o,
                 fixed_endpoint.rx_base_sequence_o);
        $fatal(1, "credit-reopen R-to-F mismatch index=%0d actual=%02x expected=%02x",
               index, f_received[index], payload_pattern(index, 8'ha5));
      end
      if (r_received[index] !== payload_pattern(index, 8'h5a))
        $fatal(1, "credit-reopen F-to-R mismatch index=%0d actual=%02x expected=%02x",
               index, r_received[index], payload_pattern(index, 8'h5a));
    end

    clear_capture();
    pulse_starts();
    fork
      stream_fixed(800, 8'h35);
      stream_rotating(800, 8'hac);
    join
    wait_both_done(500_000);

    if (!f_dual_active || !r_dual_active || f_tx_mask != 4'h3 ||
        f_rx_mask != 4'hc || r_tx_mask != 4'hc || r_rx_mask != 4'h3 ||
        f_role_epoch != 1 || r_role_epoch != 1)
      $fatal(1, "dual role state mismatch");
    if (f_input_bytes != 800 || f_output_bytes != 800 ||
        r_input_bytes != 800 || r_output_bytes != 800 ||
        f_capture_count != 800 || r_capture_count != 800 ||
        !f_capture_last || !r_capture_last)
      $fatal(1, "dual byte accounting mismatch");
    for (index = 0; index < 800; index = index + 1) begin
      if (f_received[index] !== payload_pattern(index, 8'hac))
        $fatal(1, "R-to-F payload mismatch index=%0d", index);
      if (r_received[index] !== payload_pattern(index, 8'h35))
        $fatal(1, "F-to-R payload mismatch index=%0d", index);
    end
    if (simultaneous_physical_cycles == 0)
      $fatal(1, "no simultaneous opposite-direction physical TX observed");
    if (f_piggy_tx == 0 || r_piggy_tx == 0 ||
        f_piggy_rx == 0 || r_piggy_rx == 0)
      $fatal(1, "ACK piggyback not exercised tx=%0d/%0d rx=%0d/%0d",
             f_piggy_tx, r_piggy_tx, f_piggy_rx, r_piggy_rx);
    if (f_fallback == 0 || r_fallback == 0)
      $fatal(1, "control-only ACK fallback not exercised %0d/%0d",
             f_fallback, r_fallback);
    if (f_dir_reject != 0 || r_dir_reject != 0 ||
        f_epoch_reject != 0 || r_epoch_reject != 0 ||
        f_crc_bad != 0 || r_crc_bad != 0 ||
        f_retry_exhausted != 0 || r_retry_exhausted != 0)
      $fatal(1, "dual protocol integrity counters nonzero");

    run_adjacent_one_plus_one();

    f_cfg_tx_mask = 4'h3;
    f_cfg_rx_mask = 4'hc;
    r_cfg_tx_mask = 4'hc;
    r_cfg_rx_mask = 4'h3;

    // Abort only F-to-R: fixed TX context and rotating RX context.  The
    // opposite R-to-F stream, ACK path, DMA ingress and DMA egress must finish.
    clear_capture();
    set_contexts(32'h0000_00c3, 32'h8000_00d4);
    pulse_starts();
    fork
      stream_fixed(600, 8'h55);
      stream_rotating(800, 8'hea);
    join
    watchdog = 0;
    while ((fixed_endpoint.tx_attempt_count_o == 0 ||
            rotating_endpoint.tx_attempt_count_o == 0) &&
           watchdog < 500_000) begin
      @(posedge f_clk); watchdog = watchdog + 1;
    end
    @(negedge f_clk); f_abort_tx = 1;
    @(negedge r_clk); r_abort_rx = 1;
    @(posedge f_clk); @(negedge f_clk); f_abort_tx = 0;
    @(posedge r_clk); @(negedge r_clk); r_abort_rx = 0;
    wait_both_done(500_000);
    if (!f_tx_aborted || f_rx_aborted || r_tx_aborted || !r_rx_aborted)
      $fatal(1, "direction-scoped abort state mismatch");
    if (f_output_bytes != 800 || f_capture_count != 800 || !f_capture_last)
      $fatal(1, "opposite direction did not survive scoped abort");
    for (index = 0; index < 800; index = index + 1)
      if (f_received[index] !== payload_pattern(index, 8'hea))
        $fatal(1, "post-abort R-to-F payload mismatch index=%0d", index);

    for (lane_index = 0; lane_index < 4; lane_index = lane_index + 1) begin
      if (f_tx_high_max[32*lane_index +: 32] > 64 ||
          r_tx_high_max[32*(4+lane_index) +: 32] > 64)
        $fatal(1, "continuous-high maximum exceeded lane=%0d", lane_index);
      if (f_duty_high_max[32*lane_index +: 32] > 11512 ||
          r_duty_high_max[32*(4+lane_index) +: 32] > 11512)
        $fatal(1, "rolling-duty target exceeded lane=%0d", lane_index);
    end

    f_receiver_enable = 0; r_receiver_enable = 0;
    f_shutdown = 1; r_shutdown = 1;
    repeat (6) @(posedge f_clk); #1;
    if (f_a_sd != 4'hf || r_b_sd != 4'hf || f_a_txd != 0 || r_b_txd != 0 ||
        f_armed || r_armed || !f_tx_kill || !r_tx_kill)
      $fatal(1, "final shutdown did not fail closed");
    $display("TB_P10_5_DUAL_DIRECTION_L2=PASS");
    $display("TB_P10_5_ACK_PIGGYBACK=PASS");
    $display("TB_P10_5_CONTROL_ONLY_ACK=PASS");
    $display("TB_P10_5_CREDIT_REOPEN=PASS");
    $display("TB_P10_5_BIDIRECTIONAL_DMA=PASS");
    $display("TB_P10_5_ROLE_EPOCH_STALE=PASS");
    $display("TB_P10_5_DIRECTION_ABORT_ISOLATION=PASS");
    $display("TB_P10_5_DUAL_DIRECTION_FAULTS=PASS");
    $display("TB_P10_5_DUAL_ENDPOINT_INTEGRATION=PASS");
    $display("TB_P10_5_DUAL_DIRECTION=PASS piggy=%0d/%0d fallback=%0d/%0d simultaneous=%0d",
             f_piggy_tx, r_piggy_tx, f_fallback, r_fallback,
             simultaneous_physical_cycles);
    $finish;
  end
endmodule

module tb_p10_5_adjacent_1plus1;
  tb_p10_5_dual_direction #(.ADJACENT_ONLY(1'b1)) u_test();
endmodule

`default_nettype wire
