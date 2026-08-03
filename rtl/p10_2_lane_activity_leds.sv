`timescale 1ns/1ps
`default_nettype none

// P10.2 four-lane active-low PL LED monitor. Each LED is a read-only tap for
// the corresponding logical lane and combines final physical TX activity with
// CRC-valid accepted remote RX activity. It cannot gate, admit, retry, or
// backpressure transport traffic.
module p10_2_lane_activity_leds #(
  parameter integer CLK_HZ = 64_000_000,
  parameter integer TICK_HZ = 1_000,
  parameter integer HOLD_MS = 200
) (
  input  wire       clk,
  input  wire       rst_n,
  input  wire       effective_full_shutdown_i,
  input  wire [3:0] final_txd_activity_i,
  input  wire [3:0] valid_rx_frame_activity_i,
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
  wire [3:0] activity_event =
      final_txd_activity_i | valid_rx_frame_activity_i;
  wire [3:0] held_activity = {
      hold_counter_q[3] != 0, hold_counter_q[2] != 0,
      hold_counter_q[1] != 0, hold_counter_q[0] != 0
  };

  initial begin
    if (CLK_HZ < 1 || TICK_HZ < 1 || CLK_HZ % TICK_HZ != 0)
      $error("P10.2 LED monitor requires an integral nonzero tick divisor");
    if (HOLD_MS < 1)
      $error("P10.2 LED monitor HOLD_MS must be at least one millisecond");
  end

  integer led_index;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n || effective_full_shutdown_i) begin
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

  // Combinational highest priority guarantees active-low LEDs are off during
  // reset or effective full shutdown, including the shutdown image state.
  assign pl_led_n_o = (!rst_n || effective_full_shutdown_i) ?
      4'b1111 : ~(activity_event | held_activity);
endmodule

`default_nettype wire
