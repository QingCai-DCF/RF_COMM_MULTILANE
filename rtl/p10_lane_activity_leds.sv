`timescale 1ns/1ps
`default_nettype none

// AX7020 active-low PL user LEDs used only as non-intrusive activity monitors.
//
// Bit/LED mapping is intentionally identical for both P10 endpoint roles:
//   [0] LED1 = lane0 final physical TX activity
//   [1] LED2 = lane0 CRC-valid received-frame activity
//   [2] LED3 = lane1 final physical TX activity
//   [3] LED4 = lane1 CRC-valid received-frame activity
//
// This module has no control output into the transport or TFDU safety path.
module p10_lane_activity_leds #(
  parameter integer CLK_HZ = 64_000_000,
  parameter integer TICK_HZ = 1_000,
  parameter integer HOLD_MS = 200
) (
  input  wire       clk,
  input  wire       rst_n,
  input  wire       effective_full_shutdown_i,
  input  wire [1:0] final_txd_activity_i,
  input  wire [1:0] valid_rx_frame_activity_i,
  output wire [3:0] pl_led_n_o
);
  localparam integer TICK_CYCLES = CLK_HZ / TICK_HZ;
  localparam integer TICK_COUNTER_WIDTH =
      (TICK_CYCLES <= 1) ? 1 : $clog2(TICK_CYCLES);
  localparam integer HOLD_COUNTER_WIDTH =
      (HOLD_MS <= 1) ? 1 : $clog2(HOLD_MS + 1);

  reg [TICK_COUNTER_WIDTH-1:0] tick_counter_q;
  reg [HOLD_COUNTER_WIDTH-1:0] hold_counter_q [0:3];
  wire tick_1ms = tick_counter_q == TICK_CYCLES - 1;
  wire [3:0] activity_event = {
      valid_rx_frame_activity_i[1],
      final_txd_activity_i[1],
      valid_rx_frame_activity_i[0],
      final_txd_activity_i[0]
  };
  wire [3:0] held_activity = {
      hold_counter_q[3] != 0,
      hold_counter_q[2] != 0,
      hold_counter_q[1] != 0,
      hold_counter_q[0] != 0
  };

  initial begin
    if (CLK_HZ < 1 || TICK_HZ < 1 || CLK_HZ % TICK_HZ != 0)
      $error("P10 LED monitor requires an integral nonzero tick divisor");
    if (HOLD_MS < 1)
      $error("P10 LED monitor HOLD_MS must be at least one millisecond");
  end

  integer led_index;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tick_counter_q <= 0;
      for (led_index = 0; led_index < 4; led_index = led_index + 1)
        hold_counter_q[led_index] <= 0;
    end else if (effective_full_shutdown_i) begin
      tick_counter_q <= 0;
      for (led_index = 0; led_index < 4; led_index = led_index + 1)
        hold_counter_q[led_index] <= 0;
    end else begin
      if (tick_1ms)
        tick_counter_q <= 0;
      else
        tick_counter_q <= tick_counter_q + 1'b1;

      for (led_index = 0; led_index < 4; led_index = led_index + 1) begin
        if (activity_event[led_index])
          hold_counter_q[led_index] <= HOLD_MS;
        else if (tick_1ms && hold_counter_q[led_index] != 0)
          hold_counter_q[led_index] <= hold_counter_q[led_index] - 1'b1;
      end
    end
  end

  // Reset/fault/effective full shutdown has combinational highest priority.
  // GLOBAL_PERMIT is deliberately absent: receive-only indication remains
  // available while the endpoint transmitter is not permitted or not armed.
  assign pl_led_n_o = (!rst_n || effective_full_shutdown_i) ?
      4'b1111 : ~(activity_event | held_activity);
endmodule

`default_nettype wire
