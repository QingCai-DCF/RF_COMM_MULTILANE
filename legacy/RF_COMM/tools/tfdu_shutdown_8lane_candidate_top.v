module tfdu_shutdown_8lane_candidate_top (
  output wire [7:0] ir_mode_out_0,
  input  wire [7:0] ir_rx_in_0,
  output wire [7:0] ir_sd_0,
  output wire [7:0] ir_tx_out_0,

  output wire [7:0] loop_mode_b0,
  input  wire [7:0] loop_rx_b0,
  output wire [7:0] loop_sd_b0,
  output wire [7:0] loop_tx_b0
);
  assign ir_mode_out_0 = 8'h00;
  assign ir_sd_0       = 8'hff;
  assign ir_tx_out_0   = 8'h00;

  assign loop_mode_b0  = 8'h00;
  assign loop_sd_b0    = 8'hff;
  assign loop_tx_b0    = 8'h00;

  wire unused_rx = (^ir_rx_in_0) ^ (^loop_rx_b0);
endmodule
