module pin_static_diag_top (
  output wire a_mode,
  output wire a_sd,
  output wire a_tx,
  input  wire a_rx,
  output wire b_mode,
  output wire b_sd,
  output wire b_tx,
  input  wire b_rx
);
  assign a_mode = 1'b1;
  assign a_sd   = 1'b0;
  assign a_tx   = 1'b1;

  assign b_mode = 1'b1;
  assign b_sd   = 1'b0;
  assign b_tx   = 1'b1;

  wire unused_inputs = a_rx ^ b_rx;
endmodule
