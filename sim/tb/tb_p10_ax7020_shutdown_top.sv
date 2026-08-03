`timescale 1ns/1ps
`default_nettype none

module tb_p10_ax7020_shutdown_top;
  reg [1:0] tfdu_rxd = 2'b00;
  wire [1:0] tfdu_mode;
  wire [1:0] tfdu_sd;
  wire [1:0] tfdu_txd;
  wire [3:0] pl_activity_led_n;

  p10_ax7020_shutdown_top dut (
    .tfdu_mode_o(tfdu_mode),
    .tfdu_rxd_i(tfdu_rxd),
    .tfdu_sd_o(tfdu_sd),
    .tfdu_txd_o(tfdu_txd),
    .pl_activity_led_n_o(pl_activity_led_n)
  );

  task automatic check_shutdown_outputs(input [1:0] rxd_value);
    begin
      tfdu_rxd = rxd_value;
      #1;
      if (tfdu_mode !== 2'b11 || tfdu_sd !== 2'b11 ||
          tfdu_txd !== 2'b00 || pl_activity_led_n !== 4'b1111)
        $fatal(1,
          "P10 shutdown output mismatch rxd=%b mode=%b sd=%b txd=%b led_n=%b",
          tfdu_rxd, tfdu_mode, tfdu_sd, tfdu_txd, pl_activity_led_n);
    end
  endtask

  initial begin
    check_shutdown_outputs(2'b00);
    check_shutdown_outputs(2'b01);
    check_shutdown_outputs(2'b10);
    check_shutdown_outputs(2'b11);
    $display("TB_P10_AX7020_SHUTDOWN_TOP=PASS LED_N=1111");
    $finish;
  end
endmodule

`default_nettype wire
