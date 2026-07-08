module ir_loopback_b0_txguard_bd (
  input  wire clk_phy,
  input  wire rst_n,
  output wire ir_tx_out,
  input  wire ir_rx_in,
  output wire ir_sd,
  output wire ir_mode_out,
  output wire [31:0] debug_status
);
  ir_loopback_b0_bd u_impl (
    .clk_phy     (clk_phy),
    .rst_n       (rst_n),
    .ir_tx_out   (ir_tx_out),
    .ir_rx_in    (ir_rx_in),
    .ir_sd       (ir_sd),
    .ir_mode_out (ir_mode_out),
    .debug_status(debug_status)
  );
endmodule
