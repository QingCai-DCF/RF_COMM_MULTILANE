`timescale 1ns/1ps
`default_nettype none

module tb_p10_lane_activity_leds;
  reg clk = 0;
  reg rst_n = 0;
  reg effective_full_shutdown = 0;
  reg [1:0] final_txd_activity = 0;
  reg [1:0] valid_rx_frame_activity = 0;
  wire [3:0] pl_led_n;
  integer errors = 0;

  always #5 clk = ~clk;

  p10_lane_activity_leds #(
    .CLK_HZ(4_000),
    .TICK_HZ(1_000),
    .HOLD_MS(3)
  ) dut (
    .clk(clk),
    .rst_n(rst_n),
    .effective_full_shutdown_i(effective_full_shutdown),
    .final_txd_activity_i(final_txd_activity),
    .valid_rx_frame_activity_i(valid_rx_frame_activity),
    .pl_led_n_o(pl_led_n)
  );

  task automatic expect_leds(input [3:0] expected, input [255:0] check_name);
    begin
      #1;
      if (pl_led_n !== expected) begin
        $display("P10_LED_MISMATCH context=%s expected=%b actual=%b",
                 check_name, expected, pl_led_n);
        errors = errors + 1;
      end
    end
  endtask

  task automatic pulse_and_check(
    input [1:0] tx_event,
    input [1:0] rx_event,
    input [3:0] expected,
    input [255:0] check_name
  );
    begin
      @(negedge clk);
      final_txd_activity = tx_event;
      valid_rx_frame_activity = rx_event;
      @(posedge clk);
      expect_leds(expected, check_name);
      @(negedge clk);
      final_txd_activity = 0;
      valid_rx_frame_activity = 0;
    end
  endtask

  task automatic clear_holds;
    begin
      @(negedge clk);
      final_txd_activity = 0;
      valid_rx_frame_activity = 0;
      effective_full_shutdown = 1;
      @(posedge clk);
      expect_leds(4'b1111, "clear holds in shutdown");
      @(negedge clk);
      effective_full_shutdown = 0;
      @(posedge clk);
      expect_leds(4'b1111, "leave shutdown with holds clear");
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    expect_leds(4'b1111, "reset forces every active-low LED off");

    effective_full_shutdown = 1;
    rst_n = 1;
    @(posedge clk);
    expect_leds(4'b1111, "shutdown forces every active-low LED off");

    effective_full_shutdown = 0;
    @(posedge clk);
    expect_leds(4'b1111, "idle after shutdown remains off");

    pulse_and_check(2'b01, 2'b00, 4'b1110, "LED1 lane0 TX");
    clear_holds();
    pulse_and_check(2'b00, 2'b01, 4'b1101, "LED2 lane0 RX");
    clear_holds();
    pulse_and_check(2'b10, 2'b00, 4'b1011, "LED3 lane1 TX");
    clear_holds();
    pulse_and_check(2'b00, 2'b10, 4'b0111, "LED4 lane1 RX");

    // Let every three-millisecond hold expire. The shared tick is four clocks.
    repeat (16) @(posedge clk);
    expect_leds(4'b1111, "visual holds expire");

    // Sustained activity must remain visible regardless of tick boundaries.
    @(negedge clk);
    valid_rx_frame_activity = 2'b10;
    repeat (20) begin
      @(posedge clk);
      expect_leds(4'b0111, "sustained lane1 RX remains lit");
    end
    @(negedge clk);
    valid_rx_frame_activity = 0;

    // Shutdown is immediate, clears all holds, and dominates concurrent events.
    @(negedge clk);
    final_txd_activity = 2'b11;
    valid_rx_frame_activity = 2'b11;
    effective_full_shutdown = 1;
    expect_leds(4'b1111, "shutdown combinational priority");
    @(posedge clk);
    @(negedge clk);
    final_txd_activity = 0;
    valid_rx_frame_activity = 0;
    effective_full_shutdown = 0;
    @(posedge clk);
    expect_leds(4'b1111, "shutdown clears every hold");

    // Reset has the same all-off priority and state-clear behavior.
    @(negedge clk);
    final_txd_activity = 2'b01;
    @(posedge clk);
    expect_leds(4'b1110, "activity visible before reset");
    @(negedge clk);
    rst_n = 0;
    expect_leds(4'b1111, "reset combinational priority");
    @(posedge clk);
    @(negedge clk);
    final_txd_activity = 0;
    rst_n = 1;
    @(posedge clk);
    expect_leds(4'b1111, "reset clears every hold");

    if (errors != 0) begin
      $display("TB_P10_LANE_ACTIVITY_LEDS=FAIL errors=%0d", errors);
      $fatal(1, "P10 LED monitor regression failed");
    end
    $display("TB_P10_LANE_ACTIVITY_LEDS=PASS");
    $finish;
  end
endmodule

`default_nettype wire
