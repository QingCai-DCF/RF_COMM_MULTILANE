`timescale 1ns/1ps
module tb_ir_selective_repeat_tx;
  logic clk = 1'b0;
  always #5 clk = ~clk;
  logic rst_n, clear_counters, session_reset, abort_all;
  logic [31:0] session_epoch;
  logic allocate_valid, allocate_ready, allocate_pulse;
  logic [15:0] allocate_payload_ref, allocate_payload_length, allocate_descriptor;
  logic [2:0] allocate_priority;
  logic [15:0] allocated_sequence;
  logic [4:0] allocated_entry;
  logic attempt_valid, attempt_ready;
  logic [4:0] attempt_entry;
  logic [15:0] attempt_sequence, attempt_payload_ref, attempt_payload_length;
  logic [15:0] attempt_descriptor;
  logic [2:0] attempt_priority, attempt_last_lane, selected_lane;
  logic attempt_is_retry;
  logic [15:0] selected_path_epoch;
  logic ack_valid;
  logic [31:0] ack_session_epoch;
  logic [15:0] ack_base;
  logic [31:0] ack_bitmap;
  logic [5:0] ack_width;
  logic completion_pulse;
  logic [31:0] completion_batch;
  logic [15:0] tx_next, tx_ack_base;
  logic [5:0] outstanding, high_watermark;
  logic [31:0] attempt_count, retry_count, exhausted_count, timeout_count;
  logic [31:0] duplicate_ack_count, stale_ack_count, out_of_window_ack_count;
  logic [31:0] migration_count;
  logic exhausted_sticky;

  ir_selective_repeat_tx #(
    .WINDOW_SIZE(32), .SACK_BITS(32), .MAX_RETRY(2), .RTO_CYCLES(4)
  ) dut (
    .clk, .rst_n, .clear_counters_i(clear_counters), .session_reset_i(session_reset),
    .initial_sequence_i(16'd0),
    .session_epoch_i(session_epoch), .abort_all_i(abort_all),
    .allocate_valid_i(allocate_valid), .allocate_ready_o(allocate_ready),
    .allocate_payload_ref_i(allocate_payload_ref),
    .allocate_payload_length_i(allocate_payload_length),
    .allocate_descriptor_i(allocate_descriptor), .allocate_priority_i(allocate_priority),
    .allocate_pulse_o(allocate_pulse), .allocated_sequence_o(allocated_sequence),
    .allocated_entry_o(allocated_entry), .attempt_valid_o(attempt_valid),
    .attempt_ready_i(attempt_ready), .attempt_entry_o(attempt_entry),
    .attempt_sequence_o(attempt_sequence), .attempt_payload_ref_o(attempt_payload_ref),
    .attempt_payload_length_o(attempt_payload_length),
    .attempt_descriptor_o(attempt_descriptor), .attempt_priority_o(attempt_priority),
    .attempt_is_retry_o(attempt_is_retry), .attempt_last_lane_o(attempt_last_lane),
    .selected_lane_i(selected_lane), .selected_path_epoch_i(selected_path_epoch),
    .ack_valid_i(ack_valid), .ack_session_epoch_i(ack_session_epoch),
    .ack_base_i(ack_base), .ack_bitmap_i(ack_bitmap), .ack_width_i(ack_width),
    .completion_pulse_o(completion_pulse),
    .completion_batch_count_o(completion_batch), .tx_next_sequence_o(tx_next),
    .tx_ack_base_o(tx_ack_base), .outstanding_count_o(outstanding),
    .outstanding_high_watermark_o(high_watermark), .attempt_count_o(attempt_count),
    .retry_count_o(retry_count), .retry_exhausted_count_o(exhausted_count),
    .timeout_count_o(timeout_count), .duplicate_ack_count_o(duplicate_ack_count),
    .stale_ack_count_o(stale_ack_count),
    .out_of_window_ack_count_o(out_of_window_ack_count),
    .migration_count_o(migration_count), .retry_exhausted_sticky_o(exhausted_sticky)
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "TX_EXPECT_FAIL: %s", message);
  endtask

  task automatic allocate_one(input int tag);
    begin
      @(negedge clk);
      allocate_payload_ref = tag[15:0];
      allocate_payload_length = 16'd128;
      allocate_descriptor = tag[15:0];
      allocate_priority = tag[2:0];
      allocate_valid = 1'b1;
      while (!allocate_ready) @(negedge clk);
      @(posedge clk); #1;
      check_expect(allocate_pulse, "allocation must pulse");
      allocate_valid = 1'b0;
    end
  endtask

  task automatic wait_attempt_valid(input int bound);
    int cycles;
    begin
      cycles = 0;
      while (!attempt_valid && cycles < bound) begin
        @(negedge clk); cycles = cycles + 1;
      end
      check_expect(attempt_valid,
                   "attempt selection completes within bounded window scan latency");
    end
  endtask

  task automatic send_attempt(input logic [2:0] lane);
    begin
      selected_lane = lane;
      wait_attempt_valid(160);
      attempt_ready = 1'b1;
      @(posedge clk); #1;
      attempt_ready = 1'b0;
    end
  endtask

  task automatic send_ack(input logic [31:0] epoch,
                          input logic [15:0] base,
                          input logic [31:0] bitmap);
    begin
      @(negedge clk);
      ack_session_epoch = epoch;
      ack_base = base;
      ack_bitmap = bitmap;
      ack_width = 6'd32;
      ack_valid = 1'b1;
      @(posedge clk); #1;
      ack_valid = 1'b0;
    end
  endtask

  task automatic wait_outstanding(input int expected, input int bound);
    int cycles;
    begin
      cycles = 0;
      while (outstanding != expected && cycles < bound) begin
        @(posedge clk); #1; cycles = cycles + 1;
      end
      check_expect(outstanding == expected, "bounded ACK/reclaim pipeline completes");
    end
  endtask

  task automatic wait_counter(input int selector, input int expected, input int bound);
    int cycles;
    begin
      cycles = 0;
      while (((selector == 0 ? retry_count :
               selector == 1 ? exhausted_count :
               selector == 2 ? duplicate_ack_count : stale_ack_count) != expected) &&
             cycles < bound) begin
        @(posedge clk); #1; cycles = cycles + 1;
      end
      check_expect((selector == 0 ? retry_count :
                    selector == 1 ? exhausted_count :
                    selector == 2 ? duplicate_ack_count : stale_ack_count) == expected,
                   "bounded background engine updates counter");
    end
  endtask

  initial begin
    rst_n = 1'b0; clear_counters = 1'b0; session_reset = 1'b0; abort_all = 1'b0;
    session_epoch = 32'h1234; allocate_valid = 1'b0; allocate_payload_ref = '0;
    allocate_payload_length = '0; allocate_descriptor = '0; allocate_priority = '0;
    attempt_ready = 1'b0; selected_lane = 3'd0; selected_path_epoch = 16'd9;
    ack_valid = 1'b0; ack_session_epoch = session_epoch; ack_base = 16'd0;
    ack_bitmap = '0; ack_width = 6'd32;
    repeat (3) @(posedge clk); rst_n = 1'b1; @(posedge clk); #1;

    for (int entry = 0; entry < 32; entry++) allocate_one(entry);
    check_expect(outstanding == 32, "global window holds 32 outstanding entries");
    check_expect(!allocate_ready, "full window applies backpressure");
    check_expect(high_watermark == 32, "high watermark records full window");
    send_ack(session_epoch, 16'd32, 32'd0);
    wait_outstanding(0, 160);
    check_expect(outstanding == 0 && completion_pulse && completion_batch == 32,
           "cumulative ACK completes each entry once");
    send_ack(session_epoch, 16'd32, 32'd0);
    wait_counter(2, 1, 160);
    check_expect(duplicate_ack_count == 1, "duplicate ACK is harmless");

    // A repeated SACK snapshot can have an ACK base just behind the newly
    // advanced TX base.  It is still a bounded, idempotent duplicate rather
    // than a future/malformed ACK, and it must not reclaim a live hole.
    session_reset = 1'b1; @(posedge clk); #1; session_reset = 1'b0;
    allocate_one(40);
    allocate_one(41);
    send_ack(session_epoch, 16'd0, 32'h0000_0001);
    wait_outstanding(1, 160);
    send_ack(session_epoch, 16'd0, 32'h0000_0001);
    wait_counter(2, 2, 160);
    check_expect(outstanding == 1 && tx_ack_base == 16'd1,
                 "old-base duplicate SACK preserves the live hole");

    // Reclaiming sequence zero creates a bounded interval in which its RAM
    // slot is free but the cumulative base has not yet advanced. Occupancy
    // alone must never allow sequence 32 to reuse that slot while its distance
    // from the registered base is still the full 32-frame window.
    session_reset = 1'b1; @(posedge clk); #1; session_reset = 1'b0;
    for (int entry = 0; entry < 32; entry++) allocate_one(100 + entry);
    send_ack(session_epoch, 16'd0, 32'h0000_0001);
    begin : wait_reclaim_before_base_advance
      int cycles;
      cycles = 0;
      while (!(outstanding == 31 && tx_ack_base == 0) && cycles < 160) begin
        @(posedge clk); #1; cycles = cycles + 1;
      end
      check_expect(outstanding == 31 && tx_ack_base == 0,
                   "test observes reclaim before cumulative-base advance");
    end
    check_expect(!allocate_ready,
                 "sequence span blocks modulo-slot reuse at full window distance");
    begin : wait_base_advance
      int cycles;
      cycles = 0;
      while (tx_ack_base != 1 && cycles < 160) begin
        @(posedge clk); #1; cycles = cycles + 1;
      end
      check_expect(tx_ack_base == 1 && allocate_ready,
                   "allocation reopens only after cumulative base advances");
    end
    allocate_one(132);
    check_expect(allocated_sequence == 32,
                 "first safe modulo-slot reuse allocates sequence 32");

    send_ack(session_epoch - 1, 16'd32, 32'd0);
    wait_counter(3, 1, 80);
    check_expect(stale_ack_count == 1, "stale-session ACK is rejected");

    session_reset = 1'b1; @(posedge clk); #1; session_reset = 1'b0;
    allocate_one(77);
    check_expect(outstanding == 1, "session reset restarts sequence space");
    send_attempt(3'd0);
    wait_counter(0, 1, 96);
    wait_attempt_valid(160);
    check_expect(attempt_sequence == 0 && attempt_is_retry, "first timeout queues a retry");
    send_attempt(3'd1);
    wait_counter(0, 2, 96);
    wait_attempt_valid(160);
    check_expect(attempt_is_retry, "second timeout remains bounded retry");
    send_attempt(3'd1);
    wait_counter(1, 1, 96);
    check_expect(exhausted_count == 1 && outstanding == 0 && exhausted_sticky,
           "retry exhaustion deterministically releases window ownership");
    check_expect(migration_count == 1, "only the unacknowledged retry migrated");

    allocate_one(88);
    abort_all = 1'b1; @(posedge clk); #1; abort_all = 1'b0;
    check_expect(outstanding == 0 && tx_next == 0, "abort deterministically clears entries");
    $display("P8D_GLOBAL_OUTSTANDING_32_PASS=1");
    $display("P8D_RETRY_EXHAUSTION_BOUNDED_PASS=1");
    $display("P8D_ACKED_FRAME_SINGLE_COMPLETION_PASS=1");
    $display("TB_IR_SELECTIVE_REPEAT_TX_PASS=1");
    $finish;
  end
endmodule
