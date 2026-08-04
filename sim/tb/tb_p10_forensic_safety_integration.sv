`timescale 1ns/1ps
`default_nettype none

module tb_p10_forensic_safety_integration;
  localparam integer LANES = 4;

  reg clk = 1'b0;
  reg rst_n = 1'b0;
  always #7.8125 clk = ~clk;

  reg receiver_enable = 1'b0;
  reg arm_request = 1'b0;
  reg raw_start = 1'b0;
  reg forensic_hold = 1'b0;
  wire [LANES-1:0] a_txd;
  wire [LANES-1:0] a_sd;
  wire [LANES-1:0] b_txd;
  wire [LANES-1:0] b_sd;
  wire [2*LANES-1:0] phy_ready;
  wire endpoint_armed;
  wire tx_kill;
  wire full_shutdown;

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(LANES), .WINDOW_SIZE(32),
    .SACK_BITS(32), .DEPLOYMENT_ROLE(1)
  ) dut (
    .clk(clk), .rst_n(rst_n), .receiver_enable_i(receiver_enable),
    .arm_request_i(arm_request), .disarm_request_i(1'b0),
    .full_shutdown_request_i(1'b0),
    .forensic_fault_hold_i(forensic_hold), .clear_counters_i(1'b0),
    .start_object_i(1'b0), .abort_object_i(1'b0),
    .cfg_lane_mask_i(4'hf), .cfg_lane_weights_i(32'h0101_0101),
    .cfg_rate_select_i(2'd2), .cfg_direction_i(1'b0),
    .cfg_session_epoch_i(32'hA103_0001), .cfg_path_epoch_i(16'h0103),
    .cfg_object_id_i(32'hF300_0001), .cfg_initial_sequence_i(16'd0),
    .cfg_fault_flags_i(32'd0), .cfg_drop_data_count_i(8'd0),
    .cfg_drop_ack_count_i(8'd0), .cfg_lane_unavailable_i(4'd0),
    .raw_start_i(raw_start), .raw_direction_i(1'b0),
    .raw_lane_mask_i(4'h1), .raw_pulse_target_i(32'd64),
    .raw_spacing_cycles_i(32'd1024),
    .s_axis_tvalid_i(1'b0), .s_axis_tdata_i(32'd0),
    .s_axis_tkeep_i(4'd0), .s_axis_tlast_i(1'b0),
    .m_axis_tready_i(1'b1), .a_rxd_i(4'hf), .b_rxd_i(4'hf),
    .a_txd_o(a_txd), .a_sd_o(a_sd), .b_txd_o(b_txd), .b_sd_o(b_sd),
    .phy_ready_mask_o(phy_ready), .endpoint_armed_o(endpoint_armed),
    .tx_kill_active_o(tx_kill), .effective_full_shutdown_o(full_shutdown)
  );

  integer watchdog;
  initial begin
    repeat (8) @(posedge clk);
    rst_n = 1'b1;
    receiver_enable = 1'b1;
    watchdog = 0;
    while (phy_ready[3:0] != 4'hf && watchdog < 100_000) begin
      @(posedge clk); #1; watchdog = watchdog + 1;
    end
    if (phy_ready[3:0] != 4'hf)
      $fatal(1, "forensic integration startup failed ready=%h", phy_ready);
    @(negedge clk); arm_request = 1'b1;
    @(posedge clk); @(negedge clk); arm_request = 1'b0;
    repeat (4) @(posedge clk);
    if (!endpoint_armed || tx_kill || full_shutdown)
      $fatal(1, "forensic integration arm failed");
    @(negedge clk); raw_start = 1'b1;
    @(posedge clk); @(negedge clk); raw_start = 1'b0;
    watchdog = 0;
    while (a_txd[0] !== 1'b1 && watchdog < 200_000) begin
      @(posedge clk); #1; watchdog = watchdog + 1;
    end
    if (a_txd[0] !== 1'b1)
      $fatal(1, "raw physical TX event was not observed");

    // A frozen first-fault hold is a pure combinational removal of permission
    // at the final TX gate and physical-enable/SD path; no PS transaction or
    // protocol state transition is required.
    forensic_hold = 1'b1;
    #1;
    if (a_txd != 0 || b_txd != 0 || a_sd != 4'hf || b_sd != 4'hf ||
        !tx_kill || !full_shutdown)
      $fatal(1, "forensic hold did not immediately kill TX/full-shutdown");

    // Functional reset cannot weaken a still-frozen recorder hold.
    rst_n = 1'b0;
    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    repeat (4) @(posedge clk); #1;
    if (a_txd != 0 || b_txd != 0 || a_sd != 4'hf || b_sd != 4'hf ||
        !tx_kill || !full_shutdown)
      $fatal(1, "functional reset weakened forensic full shutdown");

    $display("P10_FORENSIC_SAFETY_INTEGRATION_XSIM=PASS");
    $finish;
  end
endmodule

`default_nettype wire
