`timescale 1ns/1ps
// Offline digital behavior model only. This is not an electrical, optical, or
// datasheet-equivalent TFDU6102 model.
module tfdu6102_behavior_model #(
  parameter int CLK_HZ = 64_000_000,
  parameter int STARTUP_US = 500,
  parameter int TXD_PROTECT_US = 80,
  parameter int MODE_STATIC_HIGH = 1,
  parameter int JITTER_CYCLES = 0,
  parameter int DROP_EVERY_N_PULSE = 0,
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
  input  logic optical_i,
  output logic optical_o,
  output logic Rxd,
  output logic startup_done,
  output logic protect_fault
);
  logic receiver_ready;
  logic optical_enabled;
  time tx_start_time;
  time optical_start_time;
  integer tx_high_ns;
  integer optical_high_ns;
  integer rx_width_ns;
  integer pulse_count;

  initial begin
    Rxd = 1'b1;
    startup_done = 1'b0;
    protect_fault = 1'b0;
    receiver_ready = 1'b0;
    optical_enabled = 1'b0;
    tx_start_time = 0;
    optical_start_time = 0;
    pulse_count = 0;
  end

  function automatic integer midpoint(input integer lo, input integer hi);
    midpoint = lo + ((hi - lo) / 2);
  endfunction

  function automatic integer leading_edge_jitter_ns(input integer count);
    integer cycle_ns;
    begin
      if (JITTER_CYCLES <= 0) begin
        leading_edge_jitter_ns = ((count % 2) == 0) ? 0 : JITTER_NS;
      end else begin
        cycle_ns = 1_000_000_000 / CLK_HZ;
        leading_edge_jitter_ns = ((count % 2) == 0) ? 0 : (JITTER_CYCLES * cycle_ns);
      end
    end
  endfunction

  function automatic integer bounded_loss_period();
    integer period;
    begin
      if (DROP_EVERY_N_PULSE > 0) begin
        bounded_loss_period = DROP_EVERY_N_PULSE;
      end else if (PULSE_LOSS_PERMILLE <= 0) begin
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

  function automatic integer map_rx_width_ns(input integer optical_width_ns);
    begin
      if (optical_width_ns <= 180) begin
        map_rx_width_ns = midpoint(RX_125_MIN_NS, RX_125_MAX_NS);
      end else begin
        map_rx_width_ns = midpoint(RX_250_MIN_NS, RX_250_MAX_NS);
      end
    end
  endfunction

  task automatic drive_rx_low_pulse(input integer start_delay_ns, input integer width_ns);
    fork
      begin
        #(start_delay_ns);
        if (!SD && receiver_ready && optical_enabled && Mode) begin
          Rxd = 1'b0;
          #(width_ns);
          Rxd = 1'b1;
        end
      end
    join_none
  endtask

  task automatic receive_optical_pulse(input integer optical_width_ns);
    begin
      pulse_count = pulse_count + 1;
      if (!SD && receiver_ready && Mode && optical_enabled && !should_drop_pulse(pulse_count)) begin
        rx_width_ns = map_rx_width_ns(optical_width_ns);
        drive_rx_low_pulse(leading_edge_jitter_ns(pulse_count), rx_width_ns);
      end
    end
  endtask

  always_comb begin
    optical_o = (!SD && receiver_ready && optical_enabled && Mode && Txd && !protect_fault);
  end

  always @(posedge SD) begin
    receiver_ready = 1'b0;
    optical_enabled = 1'b0;
    startup_done = 1'b0;
    Rxd = 1'b1;
  end

  always @(negedge SD) begin
    fork
      begin
        #(STARTUP_US * 1000);
        if (!SD) begin
          receiver_ready = 1'b1;
          optical_enabled = 1'b1;
          startup_done = 1'b1;
        end
      end
    join_none
  end

  always @(posedge Txd) begin
    tx_start_time = $time;
    fork
      begin
        #(TXD_PROTECT_US * 1000);
        if (Txd) begin
          optical_enabled = 1'b0;
          protect_fault = 1'b1;
        end
      end
    join_none
  end

  always @(negedge Txd) begin
    tx_high_ns = $time - tx_start_time;
    if (NEAR_END_ECHO && receiver_ready && optical_enabled && Mode && (tx_high_ns > 0)) begin
      receive_optical_pulse(tx_high_ns);
      drive_rx_low_pulse(leading_edge_jitter_ns(pulse_count) + ECHO_DELAY_NS, ECHO_WIDTH_NS);
    end
  end

  always @(posedge optical_i) begin
    optical_start_time = $time;
  end

  always @(negedge optical_i) begin
    optical_high_ns = $time - optical_start_time;
    if (optical_high_ns > 0) begin
      receive_optical_pulse(optical_high_ns);
    end
  end
endmodule
