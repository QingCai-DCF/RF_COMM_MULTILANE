`timescale 1ns/1ps
`default_nettype none

module tb_p10_dual_endpoint_pair;
  localparam integer MAX_OBJECT_BYTES = 16384;
  localparam integer TFDU_RECOVERY_CYCLES = 4096;

  logic clk = 0;
  logic rst_n = 0;
  always #7.8125 clk = ~clk;

  logic receiver_enable;
  logic arm_request;
  logic disarm_request;
  logic full_shutdown_request;
  logic clear_counters;
  logic abort_object;
  logic f_start_object;
  logic r_start_object;
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

  logic f_raw_start;
  logic r_raw_start;
  logic raw_direction;
  logic [1:0] raw_lane_mask;
  logic [31:0] raw_pulse_target;
  logic [31:0] raw_spacing_cycles;

  logic f_s_valid;
  wire f_s_ready;
  logic [31:0] f_s_data;
  logic [3:0] f_s_keep;
  logic f_s_last;
  wire f_m_valid;
  logic f_m_ready;
  wire [31:0] f_m_data;
  wire [3:0] f_m_keep;
  wire f_m_last;

  logic r_s_valid;
  wire r_s_ready;
  logic [31:0] r_s_data;
  logic [3:0] r_s_keep;
  logic r_s_last;
  wire r_m_valid;
  logic r_m_ready;
  wire [31:0] r_m_data;
  wire [3:0] r_m_keep;
  wire r_m_last;

  wire [1:0] f_a_txd;
  wire [1:0] f_a_sd;
  wire [1:0] f_a_mode;
  wire [1:0] f_b_txd;
  wire [1:0] f_b_sd;
  wire [1:0] f_b_mode;
  wire [1:0] r_a_txd;
  wire [1:0] r_a_sd;
  wire [1:0] r_a_mode;
  wire [1:0] r_b_txd;
  wire [1:0] r_b_sd;
  wire [1:0] r_b_mode;
  logic [12:0] f_recovery [0:1];
  logic [12:0] r_recovery [0:1];
  logic [1:0] f_txd_d;
  logic [1:0] r_txd_d;
  wire [1:0] f_recovery_clear = {f_recovery[1] == 0, f_recovery[0] == 0};
  wire [1:0] r_recovery_clear = {r_recovery[1] == 0, r_recovery[0] == 0};
  // The real stationary fixture can expose each module to a reflection of
  // its own Txd.  Inject that self-echo independently of the cross-endpoint
  // recovery guard so the endpoint-role filter is exercised directly.
  wire [1:0] f_a_rxd = ~((r_b_txd & f_recovery_clear) | f_a_txd);
  wire [1:0] r_b_rxd = ~((f_a_txd & r_recovery_clear) | r_b_txd);

  wire f_armed;
  wire r_armed;
  wire f_tx_kill;
  wire r_tx_kill;
  wire [3:0] f_phy_ready;
  wire [3:0] r_phy_ready;
  wire [3:0] f_startup_done;
  wire [3:0] r_startup_done;
  wire [3:0] f_safety_fault;
  wire [3:0] r_safety_fault;
  wire f_object_active;
  wire r_object_active;
  wire f_object_done;
  wire r_object_done;
  wire f_object_fail;
  wire r_object_fail;
  wire [31:0] f_object_error;
  wire [31:0] r_object_error;
  wire f_input_complete;
  wire r_input_complete;
  wire f_output_complete;
  wire r_output_complete;
  wire [31:0] f_input_bytes;
  wire [31:0] r_input_bytes;
  wire [31:0] f_output_bytes;
  wire [31:0] r_output_bytes;
  wire f_raw_busy;
  wire r_raw_busy;
  wire f_raw_done;
  wire r_raw_done;
  wire [31:0] f_raw_sent;
  wire [31:0] r_raw_sent;
  wire [127:0] f_raw_rx_counts;
  wire [127:0] r_raw_rx_counts;
  wire [127:0] f_tx_counts;
  wire [127:0] r_tx_counts;
  wire [127:0] f_tx_high_max;
  wire [127:0] r_tx_high_max;
  wire [127:0] f_duty_high_max;
  wire [127:0] r_duty_high_max;
  wire [127:0] f_duty_throttle;
  wire [127:0] r_duty_throttle;
  wire [31:0] f_data_good;
  wire [31:0] r_data_good;
  wire [31:0] f_ack_good;
  wire [31:0] r_ack_good;
  wire [31:0] f_crc_bad;
  wire [31:0] r_crc_bad;
  wire [31:0] f_retry_exhausted;
  wire [31:0] r_retry_exhausted;
  wire [31:0] f_retry_count;
  wire [31:0] r_retry_count;
  wire [31:0] f_rx_out_of_order;
  wire [31:0] r_rx_out_of_order;
  wire [31:0] f_rx_gap;
  wire [31:0] r_rx_gap;
  wire [5:0] f_outstanding_hwm;
  wire [5:0] r_outstanding_hwm;

  logic capture_clear;
  logic done_clear;
  logic f_done_seen;
  logic r_done_seen;
  integer f_capture_count;
  integer r_capture_count;
  logic f_capture_last;
  logic r_capture_last;
  logic [7:0] f_received [0:MAX_OBJECT_BYTES-1];
  logic [7:0] r_received [0:MAX_OBJECT_BYTES-1];

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

  integer recovery_lane;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      f_txd_d <= 0;
      r_txd_d <= 0;
      for (recovery_lane = 0; recovery_lane < 2; recovery_lane = recovery_lane + 1) begin
        f_recovery[recovery_lane] <= 0;
        r_recovery[recovery_lane] <= 0;
      end
    end else begin
      f_txd_d <= f_a_txd;
      r_txd_d <= r_b_txd;
      for (recovery_lane = 0; recovery_lane < 2; recovery_lane = recovery_lane + 1) begin
        if (f_txd_d[recovery_lane] && !f_a_txd[recovery_lane])
          f_recovery[recovery_lane] <= TFDU_RECOVERY_CYCLES;
        else if (f_recovery[recovery_lane] != 0)
          f_recovery[recovery_lane] <= f_recovery[recovery_lane] - 1'b1;
        if (r_txd_d[recovery_lane] && !r_b_txd[recovery_lane])
          r_recovery[recovery_lane] <= TFDU_RECOVERY_CYCLES;
        else if (r_recovery[recovery_lane] != 0)
          r_recovery[recovery_lane] <= r_recovery[recovery_lane] - 1'b1;
      end
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin : capture_and_completion
    integer byte_lane;
    if (!rst_n) begin
      f_capture_count <= 0;
      r_capture_count <= 0;
      f_capture_last <= 0;
      r_capture_last <= 0;
      f_done_seen <= 0;
      r_done_seen <= 0;
    end else begin
      if (capture_clear) begin
        f_capture_count <= 0;
        r_capture_count <= 0;
        f_capture_last <= 0;
        r_capture_last <= 0;
      end
      if (done_clear) begin
        f_done_seen <= 0;
        r_done_seen <= 0;
      end else begin
        if (f_object_done) f_done_seen <= 1;
        if (r_object_done) r_done_seen <= 1;
      end
      if (f_m_valid && f_m_ready) begin
        if (!f_m_last && f_m_keep != 4'hf)
          $fatal(1, "fixed non-final AXI beat has sparse TKEEP=%x", f_m_keep);
        for (byte_lane = 0; byte_lane < 4; byte_lane = byte_lane + 1)
          if (f_m_keep[byte_lane])
            f_received[f_capture_count + byte_lane] <= f_m_data[8*byte_lane +: 8];
        f_capture_count <= f_capture_count + keep_bytes(f_m_keep);
        if (f_m_last) f_capture_last <= 1;
      end
      if (r_m_valid && r_m_ready) begin
        if (!r_m_last && r_m_keep != 4'hf)
          $fatal(1, "rotating non-final AXI beat has sparse TKEEP=%x", r_m_keep);
        for (byte_lane = 0; byte_lane < 4; byte_lane = byte_lane + 1)
          if (r_m_keep[byte_lane])
            r_received[r_capture_count + byte_lane] <= r_m_data[8*byte_lane +: 8];
        r_capture_count <= r_capture_count + keep_bytes(r_m_keep);
        if (r_m_last) r_capture_last <= 1;
      end
    end
  end

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .WINDOW_SIZE(32), .SACK_BITS(32),
    .MAX_PAYLOAD_BYTES(247), .STORE_ADDR_WIDTH(13), .RTO_CYCLES(500_000),
    .DEPLOYMENT_ROLE(1)
  ) fixed_endpoint (
    .clk, .rst_n, .receiver_enable_i(receiver_enable), .arm_request_i(arm_request),
    .disarm_request_i(disarm_request), .full_shutdown_request_i(full_shutdown_request),
    .clear_counters_i(clear_counters), .start_object_i(f_start_object),
    .abort_object_i(abort_object), .cfg_lane_mask_i(cfg_lane_mask),
    .cfg_lane_weights_i(cfg_lane_weights), .cfg_rate_select_i(cfg_rate_select),
    .cfg_direction_i(cfg_direction), .cfg_session_epoch_i(cfg_session_epoch),
    .cfg_path_epoch_i(cfg_path_epoch), .cfg_object_id_i(cfg_object_id),
    .cfg_initial_sequence_i(cfg_initial_sequence), .cfg_fault_flags_i(cfg_fault_flags),
    .cfg_drop_data_count_i(cfg_drop_data_count),
    .cfg_drop_ack_count_i(cfg_drop_ack_count),
    .cfg_lane_unavailable_i(cfg_lane_unavailable), .raw_start_i(f_raw_start),
    .raw_direction_i(raw_direction), .raw_lane_mask_i(raw_lane_mask),
    .raw_pulse_target_i(raw_pulse_target), .raw_spacing_cycles_i(raw_spacing_cycles),
    .s_axis_tvalid_i(f_s_valid), .s_axis_tready_o(f_s_ready),
    .s_axis_tdata_i(f_s_data), .s_axis_tkeep_i(f_s_keep), .s_axis_tlast_i(f_s_last),
    .m_axis_tvalid_o(f_m_valid), .m_axis_tready_i(f_m_ready),
    .m_axis_tdata_o(f_m_data), .m_axis_tkeep_o(f_m_keep), .m_axis_tlast_o(f_m_last),
    .a_rxd_i(f_a_rxd), .a_txd_o(f_a_txd), .a_sd_o(f_a_sd), .a_mode_o(f_a_mode),
    .b_rxd_i(2'b11), .b_txd_o(f_b_txd), .b_sd_o(f_b_sd), .b_mode_o(f_b_mode),
    .endpoint_armed_o(f_armed), .tx_kill_active_o(f_tx_kill),
    .phy_ready_mask_o(f_phy_ready), .startup_done_mask_o(f_startup_done),
    .safety_fault_mask_o(f_safety_fault), .object_active_o(f_object_active),
    .object_done_o(f_object_done), .object_fail_o(f_object_fail),
    .object_error_o(f_object_error), .input_complete_o(f_input_complete),
    .output_complete_o(f_output_complete), .input_byte_count_o(f_input_bytes),
    .output_byte_count_o(f_output_bytes), .raw_busy_o(f_raw_busy),
    .raw_done_o(f_raw_done), .raw_sent_count_o(f_raw_sent),
    .tx_outstanding_high_watermark_o(f_outstanding_hwm),
    .tx_retry_count_o(f_retry_count), .tx_retry_exhausted_count_o(f_retry_exhausted),
    .rx_out_of_order_count_o(f_rx_out_of_order), .rx_gap_count_o(f_rx_gap),
    .physical_data_frames_good_o(f_data_good), .physical_ack_frames_good_o(f_ack_good),
    .physical_crc_bad_o(f_crc_bad), .raw_rx_counts_flat_o(f_raw_rx_counts),
    .physical_tx_counts_flat_o(f_tx_counts), .tx_high_max_flat_o(f_tx_high_max),
    .duty_high_max_flat_o(f_duty_high_max),
    .duty_target_throttle_count_flat_o(f_duty_throttle)
  );

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .WINDOW_SIZE(32), .SACK_BITS(32),
    .MAX_PAYLOAD_BYTES(247), .STORE_ADDR_WIDTH(13), .RTO_CYCLES(500_000),
    .DEPLOYMENT_ROLE(2)
  ) rotating_endpoint (
    .clk, .rst_n, .receiver_enable_i(receiver_enable), .arm_request_i(arm_request),
    .disarm_request_i(disarm_request), .full_shutdown_request_i(full_shutdown_request),
    .clear_counters_i(clear_counters), .start_object_i(r_start_object),
    .abort_object_i(abort_object), .cfg_lane_mask_i(cfg_lane_mask),
    .cfg_lane_weights_i(cfg_lane_weights), .cfg_rate_select_i(cfg_rate_select),
    .cfg_direction_i(cfg_direction), .cfg_session_epoch_i(cfg_session_epoch),
    .cfg_path_epoch_i(cfg_path_epoch), .cfg_object_id_i(cfg_object_id),
    .cfg_initial_sequence_i(cfg_initial_sequence), .cfg_fault_flags_i(cfg_fault_flags),
    .cfg_drop_data_count_i(cfg_drop_data_count),
    .cfg_drop_ack_count_i(cfg_drop_ack_count),
    .cfg_lane_unavailable_i(cfg_lane_unavailable), .raw_start_i(r_raw_start),
    .raw_direction_i(raw_direction), .raw_lane_mask_i(raw_lane_mask),
    .raw_pulse_target_i(raw_pulse_target), .raw_spacing_cycles_i(raw_spacing_cycles),
    .s_axis_tvalid_i(r_s_valid), .s_axis_tready_o(r_s_ready),
    .s_axis_tdata_i(r_s_data), .s_axis_tkeep_i(r_s_keep), .s_axis_tlast_i(r_s_last),
    .m_axis_tvalid_o(r_m_valid), .m_axis_tready_i(r_m_ready),
    .m_axis_tdata_o(r_m_data), .m_axis_tkeep_o(r_m_keep), .m_axis_tlast_o(r_m_last),
    .a_rxd_i(2'b11), .a_txd_o(r_a_txd), .a_sd_o(r_a_sd), .a_mode_o(r_a_mode),
    .b_rxd_i(r_b_rxd), .b_txd_o(r_b_txd), .b_sd_o(r_b_sd), .b_mode_o(r_b_mode),
    .endpoint_armed_o(r_armed), .tx_kill_active_o(r_tx_kill),
    .phy_ready_mask_o(r_phy_ready), .startup_done_mask_o(r_startup_done),
    .safety_fault_mask_o(r_safety_fault), .object_active_o(r_object_active),
    .object_done_o(r_object_done), .object_fail_o(r_object_fail),
    .object_error_o(r_object_error), .input_complete_o(r_input_complete),
    .output_complete_o(r_output_complete), .input_byte_count_o(r_input_bytes),
    .output_byte_count_o(r_output_bytes), .raw_busy_o(r_raw_busy),
    .raw_done_o(r_raw_done), .raw_sent_count_o(r_raw_sent),
    .tx_outstanding_high_watermark_o(r_outstanding_hwm),
    .tx_retry_count_o(r_retry_count), .tx_retry_exhausted_count_o(r_retry_exhausted),
    .rx_out_of_order_count_o(r_rx_out_of_order), .rx_gap_count_o(r_rx_gap),
    .physical_data_frames_good_o(r_data_good), .physical_ack_frames_good_o(r_ack_good),
    .physical_crc_bad_o(r_crc_bad), .raw_rx_counts_flat_o(r_raw_rx_counts),
    .physical_tx_counts_flat_o(r_tx_counts), .tx_high_max_flat_o(r_tx_high_max),
    .duty_high_max_flat_o(r_duty_high_max),
    .duty_target_throttle_count_flat_o(r_duty_throttle)
  );

  task automatic pulse_both_start;
    begin
      @(negedge clk);
      f_start_object = 1;
      r_start_object = 1;
      @(posedge clk);
      @(negedge clk);
      f_start_object = 0;
      r_start_object = 0;
    end
  endtask

  task automatic stream_object(input integer length, input integer seed,
                               input logic direction);
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
        if (!direction) begin
          f_s_valid = 1;
          f_s_data = word_value;
          f_s_keep = keep_value;
          f_s_last = offset + bytes_this_word == length;
          do @(posedge clk); while (!f_s_ready);
          @(negedge clk);
          f_s_valid = 0;
          f_s_last = 0;
        end else begin
          r_s_valid = 1;
          r_s_data = word_value;
          r_s_keep = keep_value;
          r_s_last = offset + bytes_this_word == length;
          do @(posedge clk); while (!r_s_ready);
          @(negedge clk);
          r_s_valid = 0;
          r_s_last = 0;
        end
        offset = offset + bytes_this_word;
      end
    end
  endtask

  task automatic prepare_endpoints;
    integer watchdog;
    begin
      receiver_enable = 0;
      @(negedge clk); full_shutdown_request = 1;
      repeat (4) @(posedge clk);
      @(negedge clk); full_shutdown_request = 0; receiver_enable = 1;
      watchdog = 0;
      while ((f_phy_ready != 4'h3 || r_phy_ready != 4'hc) && watchdog < 100_000) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (f_phy_ready != 4'h3 || r_phy_ready != 4'hc ||
          f_startup_done != 4'h3 || r_startup_done != 4'hc ||
          f_safety_fault != 0 || r_safety_fault != 0)
        $fatal(1, "P10 endpoint startup failed ready=%x/%x startup=%x/%x fault=%x/%x",
               f_phy_ready, r_phy_ready, f_startup_done, r_startup_done,
               f_safety_fault, r_safety_fault);
      @(negedge clk); arm_request = 1;
      @(posedge clk); @(negedge clk); arm_request = 0;
      repeat (3) @(posedge clk);
      if (!f_armed || !r_armed || f_tx_kill || r_tx_kill)
        $fatal(1, "P10 endpoint explicit arm failed");
    end
  endtask

  task automatic run_raw(input logic direction, input integer lane);
    integer watchdog;
    logic [31:0] before_count;
    logic [31:0] after_count;
    begin
      @(negedge clk); clear_counters = 1;
      @(posedge clk); @(negedge clk); clear_counters = 0;
      repeat (2) @(posedge clk);
      raw_direction = direction;
      raw_lane_mask = 1 << lane;
      raw_pulse_target = 64;
      raw_spacing_cycles = 128;
      // Opposite-direction raw cases are intentionally adjacent. Respect the
      // same local TFDU receiver-recovery interval as a real half-duplex
      // direction change before beginning the next source train.
      while (direction ? (f_recovery[lane] != 0) :
                           (r_recovery[lane] != 0))
        @(posedge clk);
      before_count = direction ?
          (lane ? f_raw_rx_counts[63:32] : f_raw_rx_counts[31:0]) :
          (lane ? r_raw_rx_counts[127:96] : r_raw_rx_counts[95:64]);
      @(negedge clk);
      if (!direction) f_raw_start = 1; else r_raw_start = 1;
      @(posedge clk); @(negedge clk);
      f_raw_start = 0;
      r_raw_start = 0;
      watchdog = 0;
      while ((direction ? r_raw_busy : f_raw_busy) && watchdog < 100_000) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if ((direction ? r_raw_sent : f_raw_sent) != 64)
        $fatal(1, "P10 raw source count mismatch direction=%0d lane=%0d sent=%0d",
               direction, lane, direction ? r_raw_sent : f_raw_sent);
      repeat (32) @(posedge clk);
      after_count = direction ?
          (lane ? f_raw_rx_counts[63:32] : f_raw_rx_counts[31:0]) :
          (lane ? r_raw_rx_counts[127:96] : r_raw_rx_counts[95:64]);
      if (after_count - before_count != 64)
        $fatal(1, "P10 raw receive count mismatch direction=%0d lane=%0d delta=%0d",
               direction, lane, after_count - before_count);
      if ((!direction && (lane ? r_raw_rx_counts[95:64] : r_raw_rx_counts[127:96]) != 0) ||
          (direction && (lane ? f_raw_rx_counts[31:0] : f_raw_rx_counts[63:32]) != 0))
        $fatal(1, "P10 raw off-lane crosstalk direction=%0d lane=%0d", direction, lane);
      $display("P10_DUAL_RAW_PASS direction=%0d lane=%0d pulses=64", direction, lane);
    end
  endtask

  task automatic run_object(input integer length, input integer seed,
                            input logic direction, input logic [1:0] lane_mask,
                            input logic [15:0] initial_sequence,
                            input logic [31:0] fault_flags,
                            input integer drop_data, input integer drop_ack);
    integer watchdog;
    integer index;
    begin
      prepare_endpoints();
      cfg_direction = direction;
      cfg_lane_mask = lane_mask;
      cfg_initial_sequence = initial_sequence;
      cfg_fault_flags = fault_flags;
      cfg_drop_data_count = drop_data;
      cfg_drop_ack_count = drop_ack;
      cfg_session_epoch = cfg_session_epoch + 1;
      cfg_path_epoch = cfg_path_epoch + 1;
      cfg_object_id = cfg_object_id + 1;
      @(negedge clk); clear_counters = 1; capture_clear = 1; done_clear = 1;
      @(posedge clk); @(negedge clk);
      clear_counters = 0; capture_clear = 0; done_clear = 0;
      pulse_both_start();
      watchdog = 0;
      while ((!f_object_active || !r_object_active) &&
             !f_object_fail && !r_object_fail && watchdog < 1000) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (!f_object_active || !r_object_active)
        $fatal(1, "P10 object did not start dir=%0d active=%0b/%0b error=%08x/%08x",
               direction, f_object_active, r_object_active, f_object_error, r_object_error);
      stream_object(length, seed, direction);
      watchdog = 0;
      while (!(f_done_seen && r_done_seen) && !f_object_fail && !r_object_fail &&
             watchdog < 8_000_000) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (f_object_fail || r_object_fail || !(f_done_seen && r_done_seen)) begin
        $display("P10_DUAL_DIAG dir=%0d active=%0b/%0b done=%0b/%0b fail=%0b/%0b error=%08x/%08x in=%0d/%0d out=%0d/%0d capture=%0d/%0d data=%0d/%0d ack=%0d/%0d retry=%0d/%0d phase=%0d/%0d outstanding=%0d/%0d",
                 direction, f_object_active, r_object_active, f_done_seen, r_done_seen,
                 f_object_fail, r_object_fail, f_object_error, r_object_error,
                 f_input_bytes, r_input_bytes, f_output_bytes, r_output_bytes,
                 f_capture_count, r_capture_count, f_data_good, r_data_good,
                 f_ack_good, r_ack_good, f_retry_count, r_retry_count,
                 fixed_endpoint.phase_q, rotating_endpoint.phase_q,
                 fixed_endpoint.tx_outstanding_count_o,
                 rotating_endpoint.tx_outstanding_count_o);
        $display("P10_FIXED_SCHED local_sender=%0b ready=%b sched=%b duty=%b attempt=%0b/%0b lane=%0d waiting=%0b lanes_idle=%0b frame_guard=%0d/%0d credit=%0d phy=%b fault=%b",
                 fixed_endpoint.local_sender, fixed_endpoint.lane_runtime_ready,
                 fixed_endpoint.schedulable_lane_mask,
                 fixed_endpoint.data_frame_duty_ready,
                 fixed_endpoint.dp_attempt_valid, fixed_endpoint.dp_attempt_ready,
                 fixed_endpoint.dp_attempt_lane,
                 fixed_endpoint.endpoint_waiting_for_ack_q,
                 fixed_endpoint.lanes_idle,
                 fixed_endpoint.frame_duty_guard_q[0],
                 fixed_endpoint.frame_duty_guard_q[1],
                 fixed_endpoint.dp_peer_ack_credit_q,
                 fixed_endpoint.local_phy_ready, fixed_endpoint.local_fault_duty);
        $display("P10_ROTATING_SCHED local_sender=%0b ready=%b sched=%b duty=%b attempt=%0b/%0b lane=%0d waiting=%0b lanes_idle=%0b frame_guard=%0d/%0d credit=%0d phy=%b fault=%b",
                 rotating_endpoint.local_sender, rotating_endpoint.lane_runtime_ready,
                 rotating_endpoint.schedulable_lane_mask,
                 rotating_endpoint.data_frame_duty_ready,
                 rotating_endpoint.dp_attempt_valid, rotating_endpoint.dp_attempt_ready,
                 rotating_endpoint.dp_attempt_lane,
                 rotating_endpoint.endpoint_waiting_for_ack_q,
                 rotating_endpoint.lanes_idle,
                 rotating_endpoint.frame_duty_guard_q[0],
                 rotating_endpoint.frame_duty_guard_q[1],
                 rotating_endpoint.dp_peer_ack_credit_q,
                 rotating_endpoint.local_phy_ready, rotating_endpoint.local_fault_duty);
        $fatal(1, "P10 independent endpoint object failed or timed out");
      end
      if (!direction) begin
        if (f_input_bytes != length || r_output_bytes != length ||
            r_capture_count != length || !r_capture_last ||
            r_input_bytes != 0 || f_output_bytes != 0)
          $fatal(1, "P10 F-to-R role-local byte accounting failed");
        for (index = 0; index < length; index = index + 1)
          if (r_received[index] !== payload_pattern(index, seed))
            $fatal(1, "P10 F-to-R payload mismatch index=%0d", index);
      end else begin
        if (r_input_bytes != length || f_output_bytes != length ||
            f_capture_count != length || !f_capture_last ||
            f_input_bytes != 0 || r_output_bytes != 0)
          $fatal(1, "P10 R-to-F role-local byte accounting failed");
        for (index = 0; index < length; index = index + 1)
          if (f_received[index] !== payload_pattern(index, seed))
            $fatal(1, "P10 R-to-F payload mismatch index=%0d", index);
      end
      if (f_safety_fault != 0 || r_safety_fault != 0 ||
          f_crc_bad != 0 || r_crc_bad != 0 ||
          f_retry_exhausted != 0 || r_retry_exhausted != 0 ||
          f_duty_throttle != 0 || r_duty_throttle != 0)
        $fatal(1, "P10 object integrity/safety failure");
      $display("P10_DUAL_OBJECT_PASS direction=%0d lanes=%x length=%0d initial=%04x faults=%08x drops=%0d/%0d hwm=%0d/%0d retries=%0d/%0d",
               direction, lane_mask, length, initial_sequence, fault_flags,
               drop_data, drop_ack, f_outstanding_hwm, r_outstanding_hwm,
               f_retry_count, r_retry_count);
    end
  endtask

  initial begin
    receiver_enable = 0;
    arm_request = 0;
    disarm_request = 0;
    full_shutdown_request = 0;
    clear_counters = 0;
    abort_object = 0;
    f_start_object = 0;
    r_start_object = 0;
    cfg_lane_mask = 2'b11;
    cfg_lane_weights = 16'h0101;
    cfg_rate_select = 2'd2;
    cfg_direction = 0;
    cfg_session_epoch = 32'h5010_0000;
    cfg_path_epoch = 16'h1000;
    cfg_object_id = 32'hA010_0000;
    cfg_initial_sequence = 0;
    cfg_fault_flags = 0;
    cfg_drop_data_count = 0;
    cfg_drop_ack_count = 0;
    cfg_lane_unavailable = 0;
    f_raw_start = 0;
    r_raw_start = 0;
    raw_direction = 0;
    raw_lane_mask = 0;
    raw_pulse_target = 0;
    raw_spacing_cycles = 128;
    f_s_valid = 0;
    f_s_data = 0;
    f_s_keep = 0;
    f_s_last = 0;
    r_s_valid = 0;
    r_s_data = 0;
    r_s_keep = 0;
    r_s_last = 0;
    f_m_ready = 1;
    r_m_ready = 1;
    capture_clear = 0;
    done_clear = 0;

    repeat (8) @(posedge clk);
    rst_n = 1;
    @(posedge clk); #1;
    if (f_a_sd != 2'b11 || r_b_sd != 2'b11 || f_a_txd != 0 || r_b_txd != 0 ||
        !f_tx_kill || !r_tx_kill)
      $fatal(1, "P10 reset did not fail closed");

    prepare_endpoints();
    run_raw(1'b0, 0);
    run_raw(1'b1, 0);
    run_raw(1'b0, 1);
    run_raw(1'b1, 1);

    run_object(600, 8'h22, 1'b1, 2'b10, 16'h0100, 0, 0, 0);
    run_object(600, 8'h21, 1'b0, 2'b01, 16'h0000, 0, 0, 0);
    run_object(247*40, 8'h31, 1'b0, 2'b11, 16'h0200, 0, 0, 0);
    // Losing sequence zero while the following 31 entries fill the receive
    // window must not leave the sender parked on a stale zero-credit ACK.
    run_object(247*40, 8'h32, 1'b1, 2'b11, 16'h0300, 0, 1, 0);
    if (r_retry_count == 0)
      $fatal(1, "P10 full-window DATA loss did not exercise retry");
    run_object(600, 8'h42, 1'b1, 2'b11, 16'hfffe, 0, 0, 0);
    run_object(600, 8'h53, 1'b0, 2'b11, 16'h1000, 32'h40, 0, 0);
    if (r_rx_out_of_order == 0 || r_rx_gap == 0)
      $fatal(1, "P10 receiver SACK reorder path was not exercised");
    run_object(600, 8'h64, 1'b1, 2'b11, 16'h2000, 0, 1, 1);
    if (r_retry_count == 0)
      $fatal(1, "P10 bounded DATA/ACK loss did not exercise retry");

    if (f_tx_high_max[31:0] > 64 || f_tx_high_max[63:32] > 64 ||
        r_tx_high_max[95:64] > 64 || r_tx_high_max[127:96] > 64)
      $fatal(1, "P10 continuous-high maximum exceeded");
    if (f_duty_high_max[31:0] > 11520 || f_duty_high_max[63:32] > 11520 ||
        r_duty_high_max[95:64] > 11520 || r_duty_high_max[127:96] > 11520)
      $fatal(1, "P10 rolling-duty design target exceeded");

    receiver_enable = 0;
    @(negedge clk); full_shutdown_request = 1;
    repeat (4) @(posedge clk); #1;
    if (f_a_sd != 2'b11 || r_b_sd != 2'b11 || f_a_txd != 0 || r_b_txd != 0 ||
        f_armed || r_armed || !f_tx_kill || !r_tx_kill)
      $fatal(1, "P10 final shutdown did not fail closed");
    $display("TB_P10_DUAL_ENDPOINT_PAIR=PASS");
    $finish;
  end
endmodule

`default_nettype wire
