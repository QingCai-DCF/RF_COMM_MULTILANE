`timescale 1ns/1ps
module tb_p8e_z7010_post_synth_smoke;
  logic protocol_clk_i = 0, axis_dma_clk_i = 0, axi_lite_clk_i = 0;
  always #7.8125 protocol_clk_i = ~protocol_clk_i;
  always #5 axis_dma_clk_i = ~axis_dma_clk_i;
  always #10 axi_lite_clk_i = ~axi_lite_clk_i;
  logic reset_n_i, global_permit_i, endpoint_arm_request_i, dma_tx_kick_i;
  logic control_abort_i, protocol_ack_event_i;
  logic [31:0] stimulus_seed_i;
  logic [1:0] ir_rx_in_0, loop_rx_b0;
  wire [1:0] ir_tx_out_0, ir_sd_0, ir_mode_out_0;
  wire [1:0] loop_tx_b0, loop_sd_b0, loop_mode_b0;
  wire architecture_status_o, clock_domain_status_o;

  z7010_2lane_dev_top dut(.*);

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "P8E_POST_SYNTH_EXPECT_FAIL: %s", message);
  endtask

  initial begin
    reset_n_i = 0; global_permit_i = 0; endpoint_arm_request_i = 0;
    dma_tx_kick_i = 0; control_abort_i = 0; protocol_ack_event_i = 0;
    stimulus_seed_i = 32'h1234abcd; ir_rx_in_0 = 2'b11; loop_rx_b0 = 2'b11;
    repeat (6) @(posedge protocol_clk_i); #1;
    check_expect(ir_tx_out_0 === 2'b00, "Txd is low during reset");
    check_expect(ir_sd_0 === 2'b11, "SD is high during reset");
    reset_n_i = 1;
    repeat (8) @(posedge protocol_clk_i); #1;
    dma_tx_kick_i = 1;
    repeat (3) @(posedge axis_dma_clk_i); #1; dma_tx_kick_i = 0;
    repeat (16) @(posedge protocol_clk_i); #1;
    check_expect(ir_tx_out_0 === 2'b00, "permit-low receive/control operation cannot enable Txd");
    check_expect((^{ir_tx_out_0,ir_sd_0,ir_mode_out_0,loop_tx_b0,
                    loop_sd_b0,loop_mode_b0}) !== 1'bx,
                 "critical physical control outputs leave X state");
    $display("P8E_POST_SYNTH_SAFE_RESET_PASS=1");
    $display("P8E_POST_SYNTH_PERMIT_LOW_TXD_ZERO_PASS=1");
    $display("P8E_POST_SYNTH_CONTROL_X_ZERO_PASS=1");
    $display("TB_P8E_Z7010_POST_SYNTH_SMOKE_PASS=1");
    $finish;
  end
endmodule
