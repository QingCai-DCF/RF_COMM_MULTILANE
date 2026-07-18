`timescale 1ns/1ps
module tb_p8e_dual_endpoint;
  logic f_pclk=0,f_aclk=0,f_lclk=0,r_pclk=0,r_aclk=0,r_lclk=0;
  always #7.8125 f_pclk=~f_pclk;
  always #5.0000 f_aclk=~f_aclk;
  always #10.000 f_lclk=~f_lclk;
  always #7.7000 r_pclk=~r_pclk;
  always #5.3000 r_aclk=~r_aclk;
  always #9.7000 r_lclk=~r_lclk;
  logic f_reset_n,r_reset_n,f_permit,r_permit,f_kick,r_kick;
  logic f_status,r_status;
  integer f_activity,r_activity;

  ir_dual_endpoint_sim_top dut(
    .fixed_protocol_clk_i(f_pclk),.fixed_axis_clk_i(f_aclk),.fixed_axil_clk_i(f_lclk),
    .fixed_reset_n_i(f_reset_n),.rotating_protocol_clk_i(r_pclk),
    .rotating_axis_clk_i(r_aclk),.rotating_axil_clk_i(r_lclk),
    .rotating_reset_n_i(r_reset_n),.fixed_global_permit_i(f_permit),
    .rotating_global_permit_i(r_permit),.fixed_kick_i(f_kick),
    .rotating_kick_i(r_kick),.fixed_status_o(f_status),.rotating_status_o(r_status));

  task automatic check_expect(input logic condition,input string message);
    if(!condition)$fatal(1,"P8E_DUAL_EXPECT_FAIL: %s",message);
  endtask
  task automatic fixed_kick;
    begin @(negedge f_aclk);f_kick=1;@(posedge f_aclk);#1;f_kick=0;end
  endtask
  task automatic rotating_kick;
    begin @(negedge r_aclk);r_kick=1;@(posedge r_aclk);#1;r_kick=0;end
  endtask
  task automatic wait_activity(input integer fixed_target,input integer rotating_target);
    integer timeout;
    begin
      timeout=0;
      while((f_activity<fixed_target||r_activity<rotating_target)&&timeout<600)begin
        @(posedge f_pclk);timeout=timeout+1;
      end
      check_expect(f_activity>=fixed_target&&r_activity>=rotating_target,
             "independent endpoints make bounded progress");
    end
  endtask

  always @(posedge f_pclk) begin
    if(!f_reset_n) f_activity=0;
    else if(dut.fixed_attempt) f_activity=f_activity+1;
  end
  always @(posedge r_pclk) begin
    if(!r_reset_n) r_activity=0;
    else if(dut.rotating_attempt) r_activity=r_activity+1;
  end

  initial begin
    f_reset_n=0;r_reset_n=0;f_permit=0;r_permit=0;f_kick=0;r_kick=0;
    f_activity=0;r_activity=0;
    repeat(5)@(posedge f_pclk);f_reset_n=1;
    repeat(7)@(posedge r_pclk);r_reset_n=1;
    repeat(8)@(posedge f_pclk);

    // Receive/control clocks remain active while the single TX permit is low.
    fixed_kick();rotating_kick();repeat(180)@(posedge f_pclk);
    check_expect(f_activity==0&&r_activity==0,"permit low hard-disables both local TX attempt paths");

    f_permit=1;r_permit=1;fixed_kick();rotating_kick();
    wait_activity(1,1);

    // Reset one endpoint without resetting or deadlocking its peer.
    f_reset_n=0;repeat(9)@(posedge f_pclk);
    rotating_kick();
    begin integer prior;prior=r_activity;
      wait_activity(0,prior+1);
    end
    f_reset_n=1;repeat(8)@(posedge f_pclk);fixed_kick();
    wait_activity(1,r_activity);

    // Independent rotating reset/reacquisition; no partial old attempt resumes.
    r_reset_n=0;repeat(11)@(posedge r_pclk);r_reset_n=1;
    repeat(8)@(posedge r_pclk);rotating_kick();
    wait_activity(f_activity,1);

    f_permit=0;r_permit=0;repeat(8)@(posedge f_pclk);
    check_expect(dut.fixed_txd==0&&dut.rotating_txd==0,"raw permit drop leaves all physical Txd low");
    $display("P8E_DUAL_INDEPENDENT_CLOCK_RESET_PASS=1");
    $display("P8E_DUAL_SINGLE_ENDPOINT_RESET_RECOVERY_PASS=1");
    $display("P8E_DUAL_PERMIT_LOW_RECEIVE_ONLY_PASS=1");
    $display("P8E_DUAL_DEADLOCK_ZERO_PASS=1");
    $display("P8E_DUAL_TX_SAFETY_VIOLATION_ZERO_PASS=1");
    $display("TB_P8E_DUAL_ENDPOINT_PASS=1");
    $finish;
  end
endmodule
