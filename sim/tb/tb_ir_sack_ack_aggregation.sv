`timescale 1ns/1ps
module tb_ir_sack_ack_aggregation;
  logic clk=0; always #5 clk=~clk;
  logic rst_n, clear_counters, rx_accept, gap_blocked, control_event;
  logic direction_boundary, explicit_request, ack_valid, ack_ready;
  logic [31:0] session_epoch, ack_session_epoch;
  logic [15:0] ack_base_in, ack_base_out, credit_in, credit_out, query_sequence;
  logic [31:0] bitmap_in, bitmap_out;
  logic [5:0] width_in, width_out;
  logic [31:0] aggregation_count, timer_count, sent_count;
  logic cumulative, selective, query_acked, malformed;

  ir_sack_codec #(.SACK_BITS(32)) codec (
    .ack_base_i(ack_base_in), .sack_bitmap_i(bitmap_in), .bitmap_width_i(width_in),
    .query_sequence_i(query_sequence), .query_cumulative_acked_o(cumulative),
    .query_sack_acked_o(selective), .query_acked_o(query_acked), .malformed_o(malformed)
  );
  ir_ack_aggregator #(
    .SACK_BITS(32), .FRAME_THRESHOLD(4), .MAX_DELAY_CYCLES(6),
    .CREDIT_LOW_WATERMARK(2)
  ) aggregator (
    .clk, .rst_n, .clear_counters_i(clear_counters), .rx_accept_i(rx_accept),
    .session_epoch_i(session_epoch), .ack_base_i(ack_base_in),
    .sack_bitmap_i(bitmap_in), .sack_width_i(width_in), .receiver_credit_i(credit_in),
    .gap_blocked_i(gap_blocked), .control_event_i(control_event),
    .direction_boundary_i(direction_boundary), .explicit_request_i(explicit_request),
    .ack_valid_o(ack_valid), .ack_ready_i(ack_ready),
    .ack_session_epoch_o(ack_session_epoch), .ack_base_o(ack_base_out),
    .ack_bitmap_o(bitmap_out), .ack_width_o(width_out),
    .ack_receiver_credit_o(credit_out), .aggregation_count_o(aggregation_count),
    .timer_expiry_count_o(timer_count), .ack_frames_sent_o(sent_count)
  );

  task automatic check_expect(input logic condition, input string message);
    if(!condition) $fatal(1,"SACK_ACK_EXPECT_FAIL: %s",message);
  endtask
  task automatic accept_frame;
    begin rx_accept=1; @(posedge clk); #1; rx_accept=0; end
  endtask
  task automatic consume_ack;
    begin ack_ready=1; @(posedge clk); #1; ack_ready=0; end
  endtask

  initial begin
    rst_n=0; clear_counters=0; rx_accept=0; gap_blocked=0; control_event=0;
    direction_boundary=0; explicit_request=0; ack_ready=0; session_epoch=32'h55aa;
    ack_base_in=16'hfffe; bitmap_in=32'h0000_0005; width_in=6'd32;
    credit_in=16'd20; query_sequence=16'h0000;
    repeat(3) @(posedge clk); rst_n=1; @(posedge clk); #1;

    check_expect(query_acked && selective && !malformed,
           "wrapped sequence is selected by SACK bitmap");
    query_sequence=16'hfffd; #1;
    check_expect(query_acked && cumulative, "sequence before ACK base is cumulative ACK");
    bitmap_in[31]=1; width_in=6'd31; #1;
    check_expect(malformed && !query_acked, "malformed width fails closed");
    width_in=6'd32; bitmap_in=32'h0000_0005;

    repeat(4) accept_frame();
    repeat(2) @(posedge clk); #1;
    check_expect(ack_valid && aggregation_count==4, "threshold produces one cumulative ACK");
    check_expect(ack_session_epoch==session_epoch && ack_base_out==ack_base_in &&
           bitmap_out==bitmap_in && width_out==32,
           "aggregated ACK captures complete SACK state");
    ack_base_in=16'h1234; bitmap_in=32'hffff_ffff; #1;
    check_expect(ack_base_out==16'hfffe && bitmap_out==32'h0000_0005,
           "ACK payload remains stable under backpressure");
    consume_ack();
    check_expect(sent_count==1 && !ack_valid, "ACK handshake counts exactly once");

    ack_base_in=16'h0100; bitmap_in=32'd1; accept_frame();
    repeat(7) @(posedge clk); #1;
    check_expect(ack_valid && timer_count==1, "bounded maximum delay triggers ACK");
    consume_ack();
    credit_in=16'd2; accept_frame(); repeat(2) @(posedge clk); #1;
    check_expect(ack_valid, "low receiver credit triggers immediate cumulative ACK");
    consume_ack();
    check_expect(sent_count==3, "all aggregate ACKs complete once");
    $display("P8D_SACK_ENCODE_DECODE_PASS=1");
    $display("P8D_ACK_AGGREGATION_BOUNDED_DELAY_PASS=1");
    $display("TB_IR_SACK_ACK_AGGREGATION_PASS=1");
    $finish;
  end
endmodule
