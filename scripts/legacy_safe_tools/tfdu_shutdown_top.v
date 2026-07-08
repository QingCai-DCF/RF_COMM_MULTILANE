module tfdu_shutdown_top (
  output wire j10_a_mode,
  output wire j10_a_sd,
  output wire j10_a_tx,
  input  wire j10_a_rx,

  output wire j10_b_mode,
  output wire j10_b_sd,
  output wire j10_b_tx,
  input  wire j10_b_rx,

  output wire j11_a_mode,
  output wire j11_a_sd,
  output wire j11_a_tx,
  input  wire j11_a_rx,

  output wire j11_b_mode,
  output wire j11_b_sd,
  output wire j11_b_tx,
  input  wire j11_b_rx
);
  assign j10_a_mode = 1'b0;
  assign j10_a_sd   = 1'b1;
  assign j10_a_tx   = 1'b0;

  assign j10_b_mode = 1'b0;
  assign j10_b_sd   = 1'b1;
  assign j10_b_tx   = 1'b0;

  assign j11_a_mode = 1'b0;
  assign j11_a_sd   = 1'b1;
  assign j11_a_tx   = 1'b0;

  assign j11_b_mode = 1'b0;
  assign j11_b_sd   = 1'b1;
  assign j11_b_tx   = 1'b0;

  wire unused_rx = j10_a_rx ^ j10_b_rx ^ j11_a_rx ^ j11_b_rx;
endmodule
