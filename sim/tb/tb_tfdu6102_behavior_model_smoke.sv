`timescale 1ns/1ps
module tb_tfdu6102_behavior_model_smoke;
  reg Txd;
  reg SD;
  reg Mode;
  reg optical_i;
  wire optical_o;
  wire Rxd;
  wire startup_done;
  wire protect_fault;
  time t0;
  time width;

  tfdu6102_behavior_model #(.STARTUP_US(1), .JITTER_CYCLES(0), .DROP_EVERY_N_PULSE(0)) dut (
    .Txd(Txd),
    .SD(SD),
    .Mode(Mode),
    .optical_i(optical_i),
    .optical_o(optical_o),
    .Rxd(Rxd),
    .startup_done(startup_done),
    .protect_fault(protect_fault)
  );

  task automatic check(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  task automatic optical_pulse(input integer width_ns);
    begin
      optical_i = 1'b1;
      #(width_ns);
      optical_i = 1'b0;
    end
  endtask

  initial begin
    Txd = 1'b0;
    SD = 1'b1;
    Mode = 1'b1;
    optical_i = 1'b0;
    #100;
    check(Rxd == 1'b1, "shutdown idles Rxd high");
    check(optical_o == 1'b0, "shutdown disables optical output");
    SD = 1'b0;
    #1200;
    check(startup_done == 1'b1, "startup completes");
    optical_pulse(125);
    @(negedge Rxd);
    t0 = $time;
    @(posedge Rxd);
    width = $time - t0;
    check(width >= 100 && width <= 140, "125 ns optical input maps to 100-140 ns Rxd low");
    Txd = 1'b1;
    #125;
    check(optical_o == 1'b1, "Txd high emits optical event after startup");
    Txd = 1'b0;
    #200;
    Mode = 1'b0;
    optical_pulse(125);
    #500;
    check(Rxd == 1'b1, "Mode low drops high-speed FIR pulse");
    check(protect_fault == 1'b0, "short pulses do not trip protection");
    $display("TB_TFDU6102_BEHAVIOR_MODEL_SMOKE_PASS=1");
    $finish;
  end
endmodule
