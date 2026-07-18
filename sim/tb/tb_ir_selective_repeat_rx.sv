`timescale 1ns/1ps
module tb_ir_selective_repeat_rx;
  logic clk = 1'b0;
  always #5 clk = ~clk;
  logic rst_n, clear_counters, session_reset;
  logic [31:0] session_epoch, rx_session_epoch;
  logic [15:0] current_path_epoch, rx_sequence, rx_path_epoch;
  logic rx_valid, rx_ready, rx_l1_valid;
  logic [15:0] rx_payload_ref, rx_payload_length;
  logic rx_accept, delivery_valid, delivery_ready;
  logic [15:0] delivery_sequence, delivery_payload_ref, delivery_payload_length;
  logic [15:0] rx_base;
  logic [31:0] sack_bitmap;
  logic [5:0] credit;
  logic [31:0] out_of_order_count, duplicate_count, old_count, future_count;
  logic [31:0] stale_session_count, stale_path_count, gap_count, delivery_count;
  logic [31:0] protocol_error_count;
  integer expected_delivery;

  ir_selective_repeat_rx #(.WINDOW_SIZE(32), .SACK_BITS(32)) dut (
    .clk, .rst_n, .clear_counters_i(clear_counters), .session_reset_i(session_reset),
    .session_epoch_i(session_epoch), .current_path_epoch_i(current_path_epoch),
    .rx_valid_i(rx_valid), .rx_ready_o(rx_ready), .rx_l1_valid_i(rx_l1_valid),
    .rx_session_epoch_i(rx_session_epoch), .rx_sequence_i(rx_sequence),
    .rx_path_epoch_i(rx_path_epoch), .rx_payload_ref_i(rx_payload_ref),
    .rx_payload_length_i(rx_payload_length), .rx_accept_pulse_o(rx_accept),
    .delivery_valid_o(delivery_valid), .delivery_ready_i(delivery_ready),
    .delivery_sequence_o(delivery_sequence), .delivery_payload_ref_o(delivery_payload_ref),
    .delivery_payload_length_o(delivery_payload_length), .rx_base_sequence_o(rx_base),
    .sack_bitmap_o(sack_bitmap), .receiver_credit_o(credit),
    .out_of_order_count_o(out_of_order_count), .duplicate_count_o(duplicate_count),
    .old_count_o(old_count), .future_count_o(future_count),
    .stale_session_count_o(stale_session_count),
    .stale_path_epoch_count_o(stale_path_count), .gap_count_o(gap_count),
    .delivery_count_o(delivery_count), .protocol_error_count_o(protocol_error_count)
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "RX_EXPECT_FAIL: %s", message);
  endtask

  task automatic receive(input logic [31:0] epoch, input logic [15:0] seq,
                         input logic [15:0] path, input logic l1_ok,
                         input logic [15:0] payload);
    begin
      @(negedge clk);
      rx_session_epoch = epoch; rx_sequence = seq; rx_path_epoch = path;
      rx_l1_valid = l1_ok; rx_payload_ref = payload; rx_payload_length = 16'd64;
      rx_valid = 1'b1;
      while (!rx_ready) @(negedge clk);
      @(posedge clk); #1; rx_valid = 1'b0;
    end
  endtask

  always @(posedge clk) begin
    if (rst_n && delivery_valid && delivery_ready) begin
      if (delivery_sequence !== expected_delivery[15:0])
        $fatal(1, "RX_DELIVERY_ORDER_FAIL got=%0d expected=%0d",
               delivery_sequence, expected_delivery);
      expected_delivery = expected_delivery + 1;
    end
  end

  initial begin
    rst_n=0; clear_counters=0; session_reset=0; session_epoch=32'd7;
    current_path_epoch=16'd10; rx_valid=0; rx_l1_valid=1; rx_session_epoch=7;
    rx_sequence=0; rx_path_epoch=10; rx_payload_ref=0; rx_payload_length=64;
    delivery_ready=0; expected_delivery=0;
    repeat(3) @(posedge clk); rst_n=1; @(posedge clk); #1;

    receive(7, 16'd1, 16'd10, 1'b1, 16'h101);
    check_expect(rx_accept && sack_bitmap[1] && !sack_bitmap[0],
           "out-of-order frame creates a SACK hole");
    receive(7, 16'd1, 16'd10, 1'b1, 16'h101);
    check_expect(duplicate_count == 1 && credit == 31, "duplicate is suppressed without storage growth");
    receive(6, 16'd0, 16'd10, 1'b1, 16'h100);
    check_expect(stale_session_count == 1, "stale session data rejected");
    receive(7, 16'd0, 16'd7, 1'b1, 16'h100);
    check_expect(stale_path_count == 1, "stale path epoch rejected");
    receive(7, 16'd40, 16'd10, 1'b1, 16'h140);
    check_expect(future_count == 1, "future frame outside window rejected");
    receive(7, 16'd0, 16'd10, 1'b0, 16'h100);
    check_expect(protocol_error_count == 1, "L1-invalid frame cannot enter reorder storage");
    receive(7, 16'd0, 16'd10, 1'b1, 16'h100);
    check_expect(rx_accept && sack_bitmap[0], "gap closure is accepted once");
    delivery_ready=1;
    repeat(3) @(posedge clk); #1;
    check_expect(expected_delivery == 2 && delivery_count == 2 && rx_base == 2,
           "contiguous delivery releases frames exactly once in order");
    receive(7, 16'd0, 16'd10, 1'b1, 16'h100);
    check_expect(old_count == 1 && duplicate_count == 2,
           "old duplicate never reaches application delivery");
    check_expect(gap_count == 1 && out_of_order_count == 1,
           "gap accounting is bounded and deterministic");
    $display("P8D_RX_REORDER_DUPLICATE_SUPPRESSION_PASS=1");
    $display("P8D_STALE_SESSION_PATH_REJECTION_PASS=1");
    $display("TB_IR_SELECTIVE_REPEAT_RX_PASS=1");
    $finish;
  end
endmodule
