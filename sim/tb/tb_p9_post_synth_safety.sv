`timescale 1ns/1ps
`default_nettype none

module tb_p9_post_synth_safety;
  logic clk = 0;
  logic rst_n = 0;
  always #7.8125 clk = ~clk;

  logic receiver_enable_i = 0;
  logic arm_request_i = 0;
  logic disarm_request_i = 0;
  logic full_shutdown_request_i = 0;
  logic clear_counters_i = 0;
  logic start_object_i = 0;
  logic abort_object_i = 0;
  logic [1:0] cfg_lane_mask_i = 2'b11;
  logic [15:0] cfg_lane_weights_i = 16'h0101;
  logic [1:0] cfg_rate_select_i = 2'd2;
  logic cfg_direction_i = 0;
  logic [31:0] cfg_session_epoch_i = 32'h5009_0001;
  logic [15:0] cfg_path_epoch_i = 16'h0100;
  logic [31:0] cfg_object_id_i = 32'h9000_0001;
  logic [15:0] cfg_initial_sequence_i = 0;
  logic [31:0] cfg_fault_flags_i = 0;
  logic [7:0] cfg_drop_data_count_i = 0;
  logic [7:0] cfg_drop_ack_count_i = 0;
  logic [1:0] cfg_lane_unavailable_i = 0;
  logic raw_start_i = 0;
  logic raw_direction_i = 0;
  logic [1:0] raw_lane_mask_i = 2'b11;
  logic [31:0] raw_pulse_target_i = 1000;
  logic [31:0] raw_spacing_cycles_i = 128;
  logic s_axis_tvalid_i = 0;
  wire s_axis_tready_o;
  logic [31:0] s_axis_tdata_i = 0;
  logic [3:0] s_axis_tkeep_i = 0;
  logic s_axis_tlast_i = 0;
  wire m_axis_tvalid_o;
  logic m_axis_tready_i = 1;
  wire [31:0] m_axis_tdata_o;
  wire [3:0] m_axis_tkeep_o;
  wire m_axis_tlast_o;
  logic [1:0] a_rxd_i = 2'b11;
  wire [1:0] a_txd_o;
  wire [1:0] a_sd_o;
  wire [1:0] a_mode_o;
  logic [1:0] b_rxd_i = 2'b11;
  wire [1:0] b_txd_o;
  wire [1:0] b_sd_o;
  wire [1:0] b_mode_o;
  wire endpoint_armed_o;
  wire tx_kill_active_o;
  wire [3:0] phy_ready_mask_o;
  wire [3:0] startup_done_mask_o;
  wire [3:0] safety_fault_mask_o;
  wire object_active_o;
  wire object_done_o;
  wire object_fail_o;
  wire [31:0] object_error_o;
  wire input_complete_o;
  wire output_complete_o;
  wire [31:0] input_byte_count_o;
  wire [31:0] output_byte_count_o;
  wire raw_busy_o;
  wire raw_done_o;
  wire [31:0] raw_sent_count_o;
  wire [127:0] physical_tx_counts_flat_o;

  logic tx_seen = 0;
  always @(posedge clk) begin
    if (!rst_n) tx_seen <= 0;
    else if (|a_txd_o || |b_txd_o) tx_seen <= 1;
  end

  p9_optical_transport_core dut (
    .clk(clk), .rst_n(rst_n),
    .receiver_enable_i(receiver_enable_i), .arm_request_i(arm_request_i),
    .disarm_request_i(disarm_request_i),
    .full_shutdown_request_i(full_shutdown_request_i),
    .forensic_fault_hold_i(1'b0),
    .clear_counters_i(clear_counters_i), .start_object_i(start_object_i),
    .abort_object_i(abort_object_i), .cfg_lane_mask_i(cfg_lane_mask_i),
    .cfg_lane_weights_i(cfg_lane_weights_i), .cfg_rate_select_i(cfg_rate_select_i),
    .cfg_direction_i(cfg_direction_i), .cfg_session_epoch_i(cfg_session_epoch_i),
    .cfg_path_epoch_i(cfg_path_epoch_i), .cfg_object_id_i(cfg_object_id_i),
    .cfg_initial_sequence_i(cfg_initial_sequence_i),
    .cfg_fault_flags_i(cfg_fault_flags_i),
    .cfg_drop_data_count_i(cfg_drop_data_count_i),
    .cfg_drop_ack_count_i(cfg_drop_ack_count_i),
    .cfg_lane_unavailable_i(cfg_lane_unavailable_i),
    .raw_start_i(raw_start_i), .raw_direction_i(raw_direction_i),
    .raw_lane_mask_i(raw_lane_mask_i), .raw_pulse_target_i(raw_pulse_target_i),
    .raw_spacing_cycles_i(raw_spacing_cycles_i),
    .s_axis_tvalid_i(s_axis_tvalid_i), .s_axis_tready_o(s_axis_tready_o),
    .s_axis_tdata_i(s_axis_tdata_i), .s_axis_tkeep_i(s_axis_tkeep_i),
    .s_axis_tlast_i(s_axis_tlast_i), .m_axis_tvalid_o(m_axis_tvalid_o),
    .m_axis_tready_i(m_axis_tready_i), .m_axis_tdata_o(m_axis_tdata_o),
    .m_axis_tkeep_o(m_axis_tkeep_o), .m_axis_tlast_o(m_axis_tlast_o),
    .a_rxd_i(a_rxd_i), .a_txd_o(a_txd_o), .a_sd_o(a_sd_o), .a_mode_o(a_mode_o),
    .b_rxd_i(b_rxd_i), .b_txd_o(b_txd_o), .b_sd_o(b_sd_o), .b_mode_o(b_mode_o),
    .endpoint_armed_o(endpoint_armed_o), .tx_kill_active_o(tx_kill_active_o),
    .phy_ready_mask_o(phy_ready_mask_o), .startup_done_mask_o(startup_done_mask_o),
    .safety_fault_mask_o(safety_fault_mask_o), .object_active_o(object_active_o),
    .object_done_o(object_done_o), .object_fail_o(object_fail_o),
    .object_error_o(object_error_o), .input_complete_o(input_complete_o),
    .output_complete_o(output_complete_o), .input_byte_count_o(input_byte_count_o),
    .output_byte_count_o(output_byte_count_o), .raw_busy_o(raw_busy_o),
    .raw_done_o(raw_done_o), .raw_sent_count_o(raw_sent_count_o),
    .tx_next_sequence_o(), .tx_ack_base_o(), .tx_outstanding_count_o(),
    .tx_outstanding_high_watermark_o(), .rx_base_sequence_o(),
    .rx_sack_bitmap_o(), .tx_attempt_count_o(), .tx_retry_count_o(),
    .tx_retry_exhausted_count_o(), .tx_timeout_count_o(),
    .tx_duplicate_ack_count_o(), .tx_stale_ack_count_o(),
    .tx_out_of_window_ack_count_o(), .tx_migration_count_o(),
    .rx_duplicate_count_o(), .rx_out_of_order_count_o(), .rx_old_count_o(),
    .rx_future_count_o(), .rx_stale_session_count_o(), .rx_stale_path_count_o(),
    .rx_gap_count_o(), .rx_delivery_count_o(), .rx_protocol_error_count_o(),
    .ack_aggregation_count_o(), .ack_timer_expiry_count_o(),
    .ack_frames_sent_o(), .scheduler_frames_flat_o(), .scheduler_bytes_flat_o(),
    .scheduler_retries_flat_o(), .scheduler_migrations_flat_o(),
    .scheduler_maximum_starvation_o(), .physical_data_frames_good_o(),
    .physical_ack_frames_good_o(), .physical_crc_bad_o(), .physical_frame_bad_o(),
    .physical_preamble_count_o(), .physical_symbol_error_count_o(),
    .physical_drop_data_count_o(), .physical_drop_ack_count_o(),
    .raw_rx_counts_flat_o(), .physical_tx_counts_flat_o(physical_tx_counts_flat_o),
    .tx_high_max_flat_o(), .duty_high_max_flat_o(), .duty_high_current_flat_o(),
    .duty_headroom_flat_o(), .duty_target_throttle_count_flat_o(),
    .duty_hard_fault_count_flat_o(), .duty_window_cycles_o(),
    .duty_hard_limit_cycles_o(), .duty_target_limit_cycles_o()
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "P9_POST_SYNTH_EXPECT_FAIL: %s", message);
  endtask

  initial begin : campaign
    integer watchdog;
    logic [31:0] stopped_sent;
    logic [127:0] stopped_counts;

    repeat (8) @(posedge clk);
    #1;
    check_expect({b_txd_o, a_txd_o} === 4'h0, "Txd is not low in reset");
    check_expect({b_sd_o, a_sd_o} === 4'hf, "SD is not high in reset");
    check_expect(!endpoint_armed_o && tx_kill_active_o && !raw_busy_o,
           "reset lifecycle is not fail closed");
    $display("P9_POST_SYNTH_SAFE_RESET_PASS=1");

    rst_n = 1;
    receiver_enable_i = 1;
    for (watchdog = 0; watchdog < 100000 && phy_ready_mask_o != 4'hf;
         watchdog = watchdog + 1) begin
      @(posedge clk); #1;
      check_expect(safety_fault_mask_o == 0, "safety fault during cold start");
    end
    check_expect(phy_ready_mask_o == 4'hf && startup_done_mask_o == 4'hf,
           "all four physical modules did not become ready");
    @(negedge clk); arm_request_i = 1;
    @(posedge clk); #1;
    @(negedge clk); arm_request_i = 0;
    check_expect(endpoint_armed_o && !tx_kill_active_o, "explicit arm failed");

    @(negedge clk); raw_start_i = 1;
    @(posedge clk); #1;
    @(negedge clk); raw_start_i = 0;
    for (watchdog = 0; watchdog < 2048 && raw_sent_count_o < 4;
         watchdog = watchdog + 1) @(posedge clk);
    check_expect(raw_busy_o && raw_sent_count_o >= 4, "raw train did not become active");
    check_expect(tx_seen, "controlled raw train produced no physical Txd pulse");

    @(negedge clk); disarm_request_i = 1;
    @(posedge clk); #1;
    check_expect(!endpoint_armed_o && tx_kill_active_o && !raw_busy_o,
           "disarm did not synchronously kill and abort raw train");
    check_expect({b_txd_o, a_txd_o} === 4'h0, "Txd remained high after disarm");
    @(negedge clk); disarm_request_i = 0;
    stopped_sent = raw_sent_count_o;
    stopped_counts = physical_tx_counts_flat_o;
    repeat (300) @(posedge clk);
    check_expect(raw_sent_count_o == stopped_sent && physical_tx_counts_flat_o == stopped_counts,
           "raw train advanced while disarmed");
    $display("P9_POST_SYNTH_DISARM_KILL_PASS=1");

    @(negedge clk); arm_request_i = 1;
    @(posedge clk); #1;
    @(negedge clk); arm_request_i = 0;
    repeat (300) @(posedge clk);
    check_expect(endpoint_armed_o && !raw_busy_o && raw_sent_count_o == stopped_sent &&
           physical_tx_counts_flat_o == stopped_counts && {b_txd_o, a_txd_o} === 4'h0,
           "partial raw train resumed after explicit re-arm");
    $display("P9_POST_SYNTH_NO_PARTIAL_RESUME_PASS=1");

    receiver_enable_i = 0;
    @(negedge clk); full_shutdown_request_i = 1;
    repeat (4) @(posedge clk); #1;
    check_expect({b_txd_o, a_txd_o} === 4'h0 && {b_sd_o, a_sd_o} === 4'hf &&
           !endpoint_armed_o && tx_kill_active_o,
           "final full shutdown is not fail closed");
    $display("P9_POST_SYNTH_FINAL_SHUTDOWN_PASS=1");
    $display("TB_P9_POST_SYNTH_SAFETY=PASS");
    $finish;
  end
endmodule

`default_nettype wire
