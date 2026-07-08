`timescale 1ns/1ps
module tfdu6102_behavior_model #(
  parameter int STARTUP_US = 500,
  parameter int JITTER_NS = 20,
  parameter int PULSE_LOSS_PERMILLE = 0,
  parameter int LONG_HIGH_LIMIT_US = 80
) (
  input  logic Txd,
  input  logic SD,
  input  logic Mode,
  output logic Rxd
);
  initial Rxd = 1'b1;
  // Behavioral placeholder: active-high Txd produces low-active Rxd after startup.
  always @(*) begin
    if (SD) Rxd = 1'b1;
    else if (Txd && Mode) Rxd = 1'b0;
    else Rxd = 1'b1;
  end
endmodule
