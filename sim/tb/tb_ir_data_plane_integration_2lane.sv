`timescale 1ns/1ps
module tb_ir_data_plane_integration_2lane;
  p8d_data_plane_integration_common #(.LANE_COUNT(2),.WINDOW_SIZE(32),.SACK_BITS(32)) test();
endmodule
