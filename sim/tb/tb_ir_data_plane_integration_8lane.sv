`timescale 1ns/1ps
module tb_ir_data_plane_integration_8lane;
  p8d_data_plane_integration_common #(.LANE_COUNT(8),.WINDOW_SIZE(64),.SACK_BITS(64)) test();
endmodule
