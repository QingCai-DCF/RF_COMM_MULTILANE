`timescale 1ns/1ps
module tb_lane0_ack_only;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic clear_sticky;
  logic start;
  logic stop;
  logic [7:0] payload_lane_mask;
  logic [7:0] ack_lane_mask;
  logic [7:0] expected_ack_lane_mask;
  logic [15:0] session_id;
  logic [31:0] retry_timeout_cycles;
  logic [7:0] max_retry;
  logic ack_valid;
  logic [15:0] ack_session_id;
  logic [15:0] ack_sequence;
  logic [7:0] ack_seen_lane_mask;
  logic ack_complete;
  logic busy;
  logic tx_start_pulse;
  logic tx_done_pulse;
  logic tx_fail_pulse;
  logic ack_seen_pulse;
  logic retry_exhausted_sticky;
  logic ack_session_bad_pulse;
  logic ack_lane_mask_bad_pulse;
  logic ack_duplicate_pulse;
  logic ack_expired_pulse;
  logic ack_late_pulse;
  logic [15:0] active_sequence;
  logic [15:0] next_sequence;
  logic [7:0] retry_count;
  logic [31:0] timeout_counter;
  logic [31:0] tx_attempt_count;
  logic [31:0] ack_seen_count;
  logic [31:0] retry_exhausted_count;
  logic [31:0] ack_timeout_count;
  logic [31:0] ack_session_bad_count;
  logic [31:0] ack_lane_mask_bad_count;
  logic [31:0] ack_duplicate_count;
  logic [31:0] ack_expired_count;
  logic [31:0] ack_late_count;
  logic [31:0] debug_status;

  ir_arq_l2 #(
    .DEFAULT_RETRY_TIMEOUT_CYCLES(4),
    .DEFAULT_MAX_RETRY(2)
  ) dut (
    .clk(clk),
    .rst_n(rst_n),
    .clear_sticky(clear_sticky),
    .start(start),
    .stop(stop),
    .payload_lane_mask(payload_lane_mask),
    .ack_lane_mask(ack_lane_mask),
    .expected_ack_lane_mask(expected_ack_lane_mask),
    .session_id(session_id),
    .retry_timeout_cycles(retry_timeout_cycles),
    .max_retry(max_retry),
    .ack_valid(ack_valid),
    .ack_session_id(ack_session_id),
    .ack_sequence(ack_sequence),
    .ack_seen_lane_mask(ack_seen_lane_mask),
    .ack_complete(ack_complete),
    .busy(busy),
    .tx_start_pulse(tx_start_pulse),
    .tx_done_pulse(tx_done_pulse),
    .tx_fail_pulse(tx_fail_pulse),
    .ack_seen_pulse(ack_seen_pulse),
    .retry_exhausted_sticky(retry_exhausted_sticky),
    .ack_session_bad_pulse(ack_session_bad_pulse),
    .ack_lane_mask_bad_pulse(ack_lane_mask_bad_pulse),
    .ack_duplicate_pulse(ack_duplicate_pulse),
    .ack_expired_pulse(ack_expired_pulse),
    .ack_late_pulse(ack_late_pulse),
    .active_sequence(active_sequence),
    .next_sequence(next_sequence),
    .retry_count(retry_count),
    .timeout_counter(timeout_counter),
    .tx_attempt_count(tx_attempt_count),
    .ack_seen_count(ack_seen_count),
    .retry_exhausted_count(retry_exhausted_count),
    .ack_timeout_count(ack_timeout_count),
    .ack_session_bad_count(ack_session_bad_count),
    .ack_lane_mask_bad_count(ack_lane_mask_bad_count),
    .ack_duplicate_count(ack_duplicate_count),
    .ack_expired_count(ack_expired_count),
    .ack_late_count(ack_late_count),
    .debug_status(debug_status)
  );

  task automatic check_expect(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  task automatic tick(input int n);
    repeat (n) @(posedge clk);
  endtask

  task automatic pulse_start;
    begin
      start <= 1'b1;
      tick(1);
      start <= 1'b0;
      tick(1);
    end
  endtask

  task automatic send_ack(input logic [15:0] session, input logic [15:0] seq, input logic [7:0] lane_mask, input logic complete);
    begin
      ack_session_id <= session;
      ack_sequence <= seq;
      ack_seen_lane_mask <= lane_mask;
      ack_complete <= complete;
      ack_valid <= 1'b1;
      tick(1);
      ack_valid <= 1'b0;
      ack_complete <= 1'b0;
      tick(1);
    end
  endtask

  initial begin
    rst_n = 1'b0;
    clear_sticky = 1'b0;
    start = 1'b0;
    stop = 1'b0;
    payload_lane_mask = 8'h01;
    ack_lane_mask = 8'h01;
    expected_ack_lane_mask = 8'h01;
    session_id = 16'h2201;
    retry_timeout_cycles = 32'd4;
    max_retry = 8'd2;
    ack_valid = 1'b0;
    ack_session_id = 16'h0000;
    ack_sequence = 16'h0000;
    ack_seen_lane_mask = 8'h00;
    ack_complete = 1'b0;
    tick(3);

    rst_n = 1'b1;
    tick(2);

    pulse_start();
    check_expect(busy, "transaction enters wait-ack state");
    check_expect(active_sequence == 16'd0, "first sequence is zero");
    check_expect(tx_attempt_count == 32'd1, "first start emits one TX attempt");
    send_ack(16'h2201, 16'd0, 8'h01, 1'b1);
    check_expect(!busy, "valid ACK completes transaction");
    check_expect(tx_done_pulse || ack_seen_count == 32'd1, "ACK seen increments count");
    check_expect(next_sequence == 16'd1, "next sequence advances after ACK");

    send_ack(16'h2201, 16'd0, 8'h01, 1'b1);
    check_expect(ack_duplicate_count == 32'd1, "duplicate ACK is observable after completion");
    check_expect(ack_late_count == 32'd1, "late ACK is observable while idle");

    pulse_start();
    check_expect(active_sequence == 16'd1, "second sequence uses advanced value");
    send_ack(16'h2202, 16'd1, 8'h01, 1'b1);
    check_expect(ack_session_bad_count == 32'd1, "session mismatch ACK counted");
    send_ack(16'h2201, 16'h00FF, 8'h01, 1'b1);
    check_expect(ack_expired_count == 32'd1, "expired/out-of-order ACK counted");
    send_ack(16'h2201, 16'd1, 8'h02, 1'b1);
    check_expect(ack_lane_mask_bad_count == 32'd1, "ACK lane mask mismatch counted");
    send_ack(16'h2201, 16'd1, 8'h01, 1'b1);
    check_expect(ack_seen_count == 32'd2, "valid second ACK counted");

    pulse_start();
    tick(20);
    check_expect(retry_exhausted_sticky, "missing ACK exhausts retries");
    check_expect(tx_fail_pulse || retry_exhausted_count == 32'd1, "retry exhaustion is counted");
    check_expect(ack_timeout_count >= 32'd3, "ACK lost causes timeout/retry accounting");
    check_expect(tx_attempt_count >= 32'd5, "ACK lost causes retry TX attempts");

    $display("TB_LANE0_ACK_ONLY_PASS=1");
    $finish;
  end
endmodule
