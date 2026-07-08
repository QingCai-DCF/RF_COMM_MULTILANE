`timescale 1ns/1ps
module tfdu6102_behavior_model #(
  parameter int STARTUP_US = 500,
  parameter int JITTER_NS = 20,
  parameter int PULSE_LOSS_PERMILLE = 0,
  parameter int LONG_HIGH_LIMIT_US = 80,
  parameter bit NEAR_END_ECHO = 1'b0
) (
  input  logic Txd,
  input  logic SD,
  input  logic Mode,
  output logic Rxd
);
  logic ready;
  logic optical_enabled;
  time tx_start_time;
  integer high_ns;
  integer rx_width_ns;

  initial begin
    Rxd = 1'b1;
    ready = 1'b0;
    optical_enabled = 1'b0;
    tx_start_time = 0;
  end

  always @(posedge SD) begin
    ready = 1'b0;
    optical_enabled = 1'b0;
    Rxd = 1'b1;
  end

  always @(negedge SD) begin
    fork
      begin
        #(STARTUP_US * 1000);
        if (!SD) begin
          ready = 1'b1;
          optical_enabled = 1'b1;
        end
      end
    join_none
  end

  always @(posedge Txd) begin
    tx_start_time = $time;
    fork
      begin
        #(LONG_HIGH_LIMIT_US * 1000);
        if (Txd) begin
          optical_enabled = 1'b0;
        end
      end
    join_none
  end

  always @(negedge Txd) begin
    high_ns = $time - tx_start_time;
    if (ready && Mode && optical_enabled && PULSE_LOSS_PERMILLE == 0) begin
      rx_width_ns = (high_ns <= 180) ? 120 : 250;
      fork
        begin
          #(JITTER_NS);
          Rxd = 1'b0;
          #(rx_width_ns);
          Rxd = 1'b1;
        end
        begin
          if (NEAR_END_ECHO) begin
            #(JITTER_NS + 20);
          end
        end
      join
    end
  end
endmodule
