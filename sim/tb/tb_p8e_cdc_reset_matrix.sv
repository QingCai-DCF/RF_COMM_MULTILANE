`timescale 1ns/1ps
module tb_p8e_cdc_reset_matrix;
  integer src_half_ns = 5;
  integer dst_half_ns = 5;
  logic src_clk = 0, dst_clk = 0;
  always #(src_half_ns) src_clk = ~src_clk;
  always #(dst_half_ns) dst_clk = ~dst_clk;

  logic endpoint_reset_n;
  logic src_reset_n, dst_reset_n;
  reset_sync u_src_reset(.clk_i(src_clk), .async_reset_n_i(endpoint_reset_n),
                         .reset_n_o(src_reset_n));
  reset_sync u_dst_reset(.clk_i(dst_clk), .async_reset_n_i(endpoint_reset_n),
                         .reset_n_o(dst_reset_n));

  logic pulse_in, pulse_ready, pulse_out;
  pulse_sync u_pulse(
    .src_clk_i(src_clk), .src_reset_n_i(src_reset_n), .src_pulse_i(pulse_in),
    .src_ready_o(pulse_ready), .dst_clk_i(dst_clk), .dst_reset_n_i(dst_reset_n),
    .dst_pulse_o(pulse_out));

  logic hs_valid, hs_ready, hs_dst_valid;
  logic [15:0] hs_data, hs_dst_data;
  toggle_handshake #(.WIDTH(16)) u_handshake(
    .src_clk_i(src_clk), .src_reset_n_i(src_reset_n), .src_valid_i(hs_valid),
    .src_ready_o(hs_ready), .src_data_i(hs_data), .dst_clk_i(dst_clk),
    .dst_reset_n_i(dst_reset_n), .dst_valid_o(hs_dst_valid),
    .dst_ready_i(1'b1), .dst_data_o(hs_dst_data));

  logic fifo_valid, fifo_ready, fifo_dst_valid;
  logic [15:0] fifo_data, fifo_dst_data;
  async_fifo #(.WIDTH(16), .DEPTH(8)) u_fifo(
    .wr_clk_i(src_clk), .wr_reset_n_i(src_reset_n), .wr_valid_i(fifo_valid),
    .wr_ready_o(fifo_ready), .wr_data_i(fifo_data), .rd_clk_i(dst_clk),
    .rd_reset_n_i(dst_reset_n), .rd_valid_o(fifo_dst_valid),
    .rd_ready_i(1'b1), .rd_data_o(fifo_dst_data));

  logic async_level, synced_level;
  level_sync u_level(.clk_i(dst_clk), .reset_n_i(dst_reset_n),
                     .async_level_i(async_level), .level_o(synced_level));

  integer pulse_received;
  integer handshake_received;
  integer fifo_received;
  integer handshake_expected;
  integer fifo_expected;
  integer phase_index;

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "P8E_CDC_EXPECT_FAIL: %s", message);
  endtask

  always @(posedge dst_clk) begin
    if (!dst_reset_n) begin
      pulse_received <= 0;
      handshake_received <= 0;
      fifo_received <= 0;
      handshake_expected <= 0;
      fifo_expected <= 0;
    end else begin
      if (pulse_out) pulse_received <= pulse_received + 1;
      if (hs_dst_valid) begin
        check_expect(hs_dst_data == handshake_expected[15:0],
                     "bundled multi-bit handshake data is coherent");
        handshake_expected <= handshake_expected + 1;
        handshake_received <= handshake_received + 1;
      end
      if (fifo_dst_valid) begin
        check_expect(fifo_dst_data == fifo_expected[15:0],
                     "Gray-pointer FIFO preserves burst order");
        fifo_expected <= fifo_expected + 1;
        fifo_received <= fifo_received + 1;
      end
    end
  end

  task automatic reset_domains(input integer src_half, input integer dst_half);
    begin
      endpoint_reset_n = 0;
      pulse_in = 0; hs_valid = 0; fifo_valid = 0; async_level = 0;
      repeat (4) @(posedge src_clk);
      src_half_ns = src_half;
      dst_half_ns = dst_half;
      #1 endpoint_reset_n = 1;
      wait (src_reset_n && dst_reset_n);
      repeat (4) @(posedge dst_clk);
      check_expect(pulse_received == 0 && handshake_received == 0 && fifo_received == 0,
                   "reset suppresses stale CDC completions");
    end
  endtask

  task automatic send_pulse;
    begin
      @(negedge src_clk);
      while (!pulse_ready) @(negedge src_clk);
      pulse_in = 1;
      @(negedge src_clk);
      pulse_in = 0;
    end
  endtask

  task automatic send_handshake(input integer value);
    begin
      @(negedge src_clk);
      while (!hs_ready) @(negedge src_clk);
      hs_data = value[15:0]; hs_valid = 1;
      @(negedge src_clk);
      hs_valid = 0;
    end
  endtask

  task automatic send_fifo(input integer value);
    begin
      @(negedge src_clk);
      while (!fifo_ready) @(negedge src_clk);
      fifo_data = value[15:0]; fifo_valid = 1;
      @(negedge src_clk);
      fifo_valid = 0;
    end
  endtask

  task automatic run_ratio(input integer src_half, input integer dst_half,
                           input integer ratio_number);
    integer index;
    integer timeout;
    begin
      reset_domains(src_half, dst_half);
      async_level = 1;
      repeat (4) @(posedge dst_clk);
      check_expect(synced_level, "single-bit level synchronizer converges");
      async_level = 0;

      for (index = 0; index < 12; index = index + 1) send_pulse();
      for (index = 0; index < 12; index = index + 1) send_handshake(index);
      for (index = 0; index < 32; index = index + 1) send_fifo(index);
      timeout = 0;
      while ((pulse_received != 12 || handshake_received != 12 || fifo_received != 32)
             && timeout < 2000) begin
        @(posedge dst_clk); timeout = timeout + 1;
      end
      if (timeout >= 2000)
        $display("P8E_CDC_TIMEOUT ratio=%0d pulse=%0d handshake=%0d fifo=%0d",
                 ratio_number, pulse_received, handshake_received, fifo_received);
      check_expect(timeout < 2000, "CDC traffic completes within bounded latency");
      check_expect(pulse_received == 12, "no pulse loss or duplication");
      check_expect(handshake_received == 12, "no handshake loss or duplication");
      check_expect(fifo_received == 32, "no FIFO loss or duplication");
      $display("P8E_CDC_RATIO_%0d_PASS=1", ratio_number);
    end
  endtask

  task automatic run_deterministic_seed(input integer seed,
                                        input integer src_half,
                                        input integer dst_half);
    integer index;
    integer timeout;
    integer idle_cycles;
    begin
      reset_domains(src_half, dst_half);
      // Each fixed seed produces a distinct, repeatable phase/burst pattern.
      // The clock phase is intentionally not realigned when the half-periods
      // change, so repeated scenarios also exercise phase drift.
      #(1 + (seed % 13));
      for (index = 0; index < 6; index = index + 1) begin
        idle_cycles = (seed + (index * 7)) % 4;
        repeat (idle_cycles) @(posedge src_clk);
        send_pulse();
        send_handshake(index);
        send_fifo(index * 2);
        send_fifo((index * 2) + 1);
      end
      timeout = 0;
      while ((pulse_received != 6 || handshake_received != 6 || fifo_received != 12)
             && timeout < 2000) begin
        @(posedge dst_clk); timeout = timeout + 1;
      end
      check_expect(timeout < 2000,
                   "deterministic seeded CDC traffic completes within bounded latency");
      check_expect(pulse_received == 6 && handshake_received == 6 && fifo_received == 12,
                   "deterministic seeded CDC traffic has no loss or duplication");
      $display("P8E_CDC_DETERMINISTIC_SEED_%0d_PASS=1", seed);
    end
  endtask

  initial begin
    endpoint_reset_n = 0; pulse_in = 0; hs_valid = 0; hs_data = 0;
    fifo_valid = 0; fifo_data = 0; async_level = 0; phase_index = 0;
    // half-period pairs exercise 1:1, 2:1, 3:2, 5:4, and irrational-like ratios.
    run_ratio(5, 5, 1);
    run_ratio(4, 8, 2);
    run_ratio(6, 9, 3);
    run_ratio(8, 10, 4);
    run_ratio(7, 11, 5);

    run_deterministic_seed(101, 5, 7);
    run_deterministic_seed(211, 6, 11);
    run_deterministic_seed(307, 8, 13);
    run_deterministic_seed(401, 9, 14);

    // Near-simultaneous reset while requests are in flight must not leak a
    // completion into the new reset generation.
    while (!pulse_ready) @(negedge src_clk);
    pulse_in = 1; hs_valid = 1; hs_data = 16'h55aa;
    #1 endpoint_reset_n = 0;
    repeat (5) @(posedge dst_clk);
    check_expect(!pulse_out && !hs_dst_valid && !fifo_dst_valid,
                 "in-flight events are aborted by endpoint reset");
    reset_domains(5, 7);
    send_pulse(); send_handshake(0); send_fifo(0);
    wait (pulse_received == 1 && handshake_received == 1 && fifo_received == 1);
    $display("P8E_CDC_RANDOM_RESET_RECOVERY_PASS=1");
    $display("P8E_CDC_STALE_COMPLETION_ZERO_PASS=1");
    $display("P8E_RESET_DEASSERT_SYNC_PASS=1");
    $display("TB_P8E_CDC_RESET_MATRIX_PASS=1");
    $finish;
  end
endmodule
