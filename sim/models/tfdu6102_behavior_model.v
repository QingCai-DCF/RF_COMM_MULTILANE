`timescale 1ns/1ps
/* Verilog-compatible offline TFDU6102 behavior fallback. This model is not an
 * electrical, optical, or datasheet-equivalent model. */
module tfdu6102_behavior_model_v #(
  parameter integer CLK_HZ = 64000000,
  parameter integer STARTUP_US = 500,
  parameter integer TXD_PROTECT_US = 80,
  parameter integer JITTER_CYCLES = 0,
  parameter integer DROP_EVERY_N_PULSE = 0
) (
  input wire Txd,
  input wire SD,
  input wire Mode,
  input wire optical_i,
  output reg optical_o,
  output reg Rxd,
  output reg startup_done,
  output reg protect_fault
);
  reg receiver_ready;
  reg transmitter_enabled;
  time tx_start_time;
  time optical_start_time;
  integer pulse_count;
  integer optical_high_ns;
  integer rx_width_ns;

  initial begin
    optical_o = 1'b0;
    Rxd = 1'b1;
    startup_done = 1'b0;
    protect_fault = 1'b0;
    receiver_ready = 1'b0;
    transmitter_enabled = 1'b0;
    pulse_count = 0;
  end

  always @(*) begin
    optical_o = (!SD && receiver_ready && transmitter_enabled && Mode && Txd && !protect_fault);
  end

  always @(posedge SD) begin
    receiver_ready = 1'b0;
    transmitter_enabled = 1'b0;
    startup_done = 1'b0;
    Rxd = 1'b1;
  end

  always @(negedge SD) begin
    fork
      begin
        #(STARTUP_US * 1000);
        if (!SD) begin
          receiver_ready = 1'b1;
          transmitter_enabled = 1'b1;
          startup_done = 1'b1;
        end
      end
    join
  end

  always @(posedge Txd) begin
    tx_start_time = $time;
    fork
      begin
        #(TXD_PROTECT_US * 1000);
        if (Txd) begin
          transmitter_enabled = 1'b0;
          protect_fault = 1'b1;
        end
      end
    join
  end

  always @(posedge optical_i) begin
    optical_start_time = $time;
  end

  always @(negedge optical_i) begin
    optical_high_ns = $time - optical_start_time;
    pulse_count = pulse_count + 1;
    if (!SD && receiver_ready && transmitter_enabled && Mode &&
        (DROP_EVERY_N_PULSE == 0 || (pulse_count % DROP_EVERY_N_PULSE) != 0)) begin
      rx_width_ns = (optical_high_ns <= 180) ? 120 : 250;
      Rxd = 1'b0;
      #(rx_width_ns);
      Rxd = 1'b1;
    end
  end
endmodule
