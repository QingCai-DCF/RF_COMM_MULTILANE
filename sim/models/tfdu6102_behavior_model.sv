`timescale 1ns/1ps
module tfdu6102_behavior_model #(
  parameter int STARTUP_US = 500,
  parameter int JITTER_NS = 20,
  parameter int PULSE_LOSS_PERMILLE = 0,
  parameter int LONG_HIGH_LIMIT_US = 80,
  parameter bit NEAR_END_ECHO = 1'b0,
  parameter int RX_125_MIN_NS = 100,
  parameter int RX_125_MAX_NS = 140,
  parameter int RX_250_MIN_NS = 225,
  parameter int RX_250_MAX_NS = 275,
  parameter int ECHO_DELAY_NS = 400,
  parameter int ECHO_WIDTH_NS = 80
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
  integer pulse_count;

  initial begin
    Rxd = 1'b1;
    ready = 1'b0;
    optical_enabled = 1'b0;
    tx_start_time = 0;
    pulse_count = 0;
  end

  function automatic integer midpoint(input integer lo, input integer hi);
    midpoint = lo + ((hi - lo) / 2);
  endfunction

  function automatic integer bounded_loss_period();
    integer period;
    begin
      if (PULSE_LOSS_PERMILLE <= 0) begin
        bounded_loss_period = 0;
      end else if (PULSE_LOSS_PERMILLE >= 1000) begin
        bounded_loss_period = 1;
      end else begin
        period = 1000 / PULSE_LOSS_PERMILLE;
        bounded_loss_period = (period < 1) ? 1 : period;
      end
    end
  endfunction

  function automatic bit should_drop_pulse(input integer count);
    integer period;
    begin
      period = bounded_loss_period();
      should_drop_pulse = (period != 0) && ((count % period) == 0);
    end
  endfunction

  function automatic integer leading_edge_jitter_ns(input integer count);
    begin
      if (JITTER_NS <= 0) begin
        leading_edge_jitter_ns = 0;
      end else begin
        leading_edge_jitter_ns = (count % 2) ? JITTER_NS : 0;
      end
    end
  endfunction

  task automatic drive_rx_low_pulse(input integer start_delay_ns, input integer width_ns);
    fork
      begin
        #(start_delay_ns);
        if (!SD && ready && optical_enabled) begin
          Rxd = 1'b0;
          #(width_ns);
          Rxd = 1'b1;
        end
      end
    join_none
  endtask

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
    pulse_count = pulse_count + 1;
    if (ready && Mode && optical_enabled && !should_drop_pulse(pulse_count)) begin
      rx_width_ns = (high_ns <= 180) ? midpoint(RX_125_MIN_NS, RX_125_MAX_NS) : midpoint(RX_250_MIN_NS, RX_250_MAX_NS);
      drive_rx_low_pulse(leading_edge_jitter_ns(pulse_count), rx_width_ns);
      if (NEAR_END_ECHO) begin
        drive_rx_low_pulse(leading_edge_jitter_ns(pulse_count) + ECHO_DELAY_NS, ECHO_WIDTH_NS);
      end
    end
  end
endmodule
