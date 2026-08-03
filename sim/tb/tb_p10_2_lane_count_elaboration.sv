`timescale 1ns/1ps
`default_nettype none

module p10_2_core_elaboration_fixture #(
  parameter integer LANE_COUNT = 2
);
  reg clk = 1'b0;
  reg rst_n = 1'b0;
  always #5 clk = ~clk;
  initial begin
    #30 rst_n = 1'b1;
  end

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(LANE_COUNT),
    .WINDOW_SIZE(32), .SACK_BITS(32), .DEPLOYMENT_ROLE(1)
  ) dut (
    .clk(clk), .rst_n(rst_n),
    .receiver_enable_i(1'b0), .arm_request_i(1'b0),
    .disarm_request_i(1'b0), .full_shutdown_request_i(1'b0),
    .clear_counters_i(1'b0), .start_object_i(1'b0),
    .abort_object_i(1'b0),
    .cfg_lane_mask_i({LANE_COUNT{1'b1}}),
    .cfg_lane_weights_i({LANE_COUNT{8'h01}}),
    .cfg_rate_select_i(2'd2), .cfg_direction_i(1'b0),
    .cfg_session_epoch_i(32'd1), .cfg_path_epoch_i(16'd0),
    .cfg_object_id_i(32'd1), .cfg_initial_sequence_i(16'd0),
    .cfg_fault_flags_i(32'd0), .cfg_drop_data_count_i(8'd0),
    .cfg_drop_ack_count_i(8'd0),
    .cfg_lane_unavailable_i({LANE_COUNT{1'b0}}),
    .raw_start_i(1'b0), .raw_direction_i(1'b0),
    .raw_lane_mask_i({LANE_COUNT{1'b0}}),
    .raw_pulse_target_i(32'd0), .raw_spacing_cycles_i(32'd1024),
    .s_axis_tvalid_i(1'b0), .s_axis_tdata_i(32'd0),
    .s_axis_tkeep_i(4'd0), .s_axis_tlast_i(1'b0),
    .m_axis_tready_i(1'b1),
    .a_rxd_i({LANE_COUNT{1'b1}}),
    .b_rxd_i({LANE_COUNT{1'b1}})
  );
endmodule

module tb_p10_2_lane_count_elaboration;
  p10_2_core_elaboration_fixture #(.LANE_COUNT(2)) u_lane2();
  p10_2_core_elaboration_fixture #(.LANE_COUNT(4)) u_lane4();
  p10_2_core_elaboration_fixture #(.LANE_COUNT(8)) u_lane8();
  initial begin
    #100;
    $display("TB_P10_2_LANE_COUNT_ELABORATION=PASS lane_counts=2,4,8");
    $finish;
  end
endmodule

`default_nettype wire
