`timescale 1ns/1ps
module tb_ir_axis_backpressure;
  logic clk=0; always #5 clk=~clk;
  logic rst_n, clear_counters;
  logic tx_desc_valid, tx_desc_ready, rx_desc_valid, rx_desc_ready;
  logic [31:0] desc_length;
  logic [63:0] desc_user;
  logic s_valid, s_ready, s_last;
  logic [63:0] s_data, s_user;
  logic [7:0] s_keep;
  logic mid_valid, mid_ready, mid_last;
  logic [63:0] mid_data, mid_user;
  logic [7:0] mid_keep;
  logic m_valid, m_ready, m_last;
  logic [63:0] m_data, m_user;
  logic [7:0] m_keep;
  logic tx_complete, tx_error, rx_complete, rx_error;
  logic [31:0] tx_stalls, tx_errors, tx_packets;
  logic [31:0] rx_stalls, rx_errors, rx_packets;
  logic [31:0] lfsr;
  logic stalled_previous;
  logic [63:0] held_data, held_user;
  logic [7:0] held_keep;
  logic held_last;
  logic malformed_phase;
  integer output_packet, output_beat;

  ir_axis_tx_frontend #(.DATA_WIDTH(64),.USER_WIDTH(64)) tx_frontend (
    .clk,.rst_n,.clear_counters_i(clear_counters),
    .descriptor_valid_i(tx_desc_valid),.descriptor_ready_o(tx_desc_ready),
    .descriptor_length_i(desc_length),.descriptor_user_i(desc_user),
    .s_axis_tvalid_i(s_valid),.s_axis_tready_o(s_ready),.s_axis_tdata_i(s_data),
    .s_axis_tkeep_i(s_keep),.s_axis_tlast_i(s_last),.s_axis_tuser_i(s_user),
    .m_axis_tvalid_o(mid_valid),.m_axis_tready_i(mid_ready),.m_axis_tdata_o(mid_data),
    .m_axis_tkeep_o(mid_keep),.m_axis_tlast_o(mid_last),.m_axis_tuser_o(mid_user),
    .descriptor_complete_pulse_o(tx_complete),.protocol_error_pulse_o(tx_error),
    .stall_cycles_o(tx_stalls),.protocol_error_count_o(tx_errors),.packet_count_o(tx_packets)
  );
  ir_axis_rx_backend #(.DATA_WIDTH(64),.USER_WIDTH(64)) rx_backend (
    .clk,.rst_n,.clear_counters_i(clear_counters),
    .descriptor_valid_i(rx_desc_valid),.descriptor_ready_o(rx_desc_ready),
    .descriptor_length_i(desc_length),.descriptor_user_i(desc_user),
    .s_axis_tvalid_i(mid_valid),.s_axis_tready_o(mid_ready),.s_axis_tdata_i(mid_data),
    .s_axis_tkeep_i(mid_keep),.s_axis_tlast_i(mid_last),.s_axis_tuser_i(mid_user),
    .m_axis_tvalid_o(m_valid),.m_axis_tready_i(m_ready),.m_axis_tdata_o(m_data),
    .m_axis_tkeep_o(m_keep),.m_axis_tlast_o(m_last),.m_axis_tuser_o(m_user),
    .descriptor_complete_pulse_o(rx_complete),.protocol_error_pulse_o(rx_error),
    .stall_cycles_o(rx_stalls),.protocol_error_count_o(rx_errors),.packet_count_o(rx_packets)
  );

  function automatic logic [63:0] beat_data(input integer packet, input integer beat);
    beat_data = {packet[31:0],16'h5aa5,beat[15:0]};
  endfunction
  task automatic check_expect(input logic condition,input string message);
    if(!condition) $fatal(1,"AXIS_EXPECT_FAIL: %s",message);
  endtask
  task automatic post_descriptors(input integer packet,input integer length);
    logic tx_handshake;
    logic rx_handshake;
    begin
      @(negedge clk); desc_length=length; desc_user=packet;
      tx_desc_valid=1; rx_desc_valid=1;
      while(tx_desc_valid || rx_desc_valid) begin
        @(posedge clk);
        tx_handshake = tx_desc_valid && tx_desc_ready;
        rx_handshake = rx_desc_valid && rx_desc_ready;
        #1;
        if(tx_handshake) tx_desc_valid=0;
        if(rx_handshake) rx_desc_valid=0;
      end
    end
  endtask
  task automatic send_beat(input integer packet,input integer beat,
                           input logic [7:0] keep,input logic last);
    begin
      @(negedge clk); s_data=beat_data(packet,beat); s_keep=keep;
      s_last=last; s_user=packet; s_valid=1;
      while(!s_ready) @(negedge clk);
      @(posedge clk); #1; s_valid=0;
    end
  endtask

  always @(negedge clk) begin
    if(!rst_n) begin lfsr<=32'h1ace_b00c; m_ready<=0; end
    else begin
      lfsr <= {lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      m_ready <= lfsr[0] | lfsr[3];
    end
  end
  always @(posedge clk) begin
    if(!rst_n) begin
      stalled_previous=0; output_packet=0; output_beat=0;
    end else begin
      if(stalled_previous) begin
        check_expect(m_valid,"TVALID must remain asserted while stalled");
        check_expect(m_data==held_data && m_keep==held_keep && m_last==held_last &&
                     m_user==held_user,"AXI payload must remain stable while stalled");
      end
      stalled_previous = m_valid && !m_ready;
      if(stalled_previous) begin
        held_data=m_data; held_keep=m_keep; held_last=m_last; held_user=m_user;
      end
      if(m_valid && m_ready && !malformed_phase) begin
        check_expect(m_data==beat_data(output_packet,output_beat),"no data loss or reordering");
        check_expect(m_user==output_packet,"descriptor metadata follows payload");
        if(output_beat==0) begin
          check_expect(m_keep==8'hff && !m_last,"first beat shape");
          output_beat=1;
        end else begin
          check_expect(m_keep==8'h0f && m_last,"last beat shape");
          output_beat=0; output_packet=output_packet+1;
        end
      end
    end
  end

  initial begin
    rst_n=0; clear_counters=0; tx_desc_valid=0; rx_desc_valid=0;
    desc_length=0; desc_user=0; s_valid=0; s_data=0; s_keep=0; s_last=0; s_user=0;
    m_ready=0; lfsr=32'h1ace_b00c; malformed_phase=0;
    repeat(4) @(posedge clk); rst_n=1; @(posedge clk); #1;
    for(int packet=0;packet<128;packet++) begin
      post_descriptors(packet,12);
      send_beat(packet,0,8'hff,1'b0);
      send_beat(packet,1,8'h0f,1'b1);
    end
    while(output_packet<128) @(posedge clk);
    repeat(3) @(posedge clk); #1;
    check_expect(tx_packets==128 && rx_packets==128,"each descriptor completes exactly once");
    check_expect(tx_stalls>0 || rx_stalls>0,"random campaign exercised backpressure");
    check_expect(tx_errors==0 && rx_errors==0,"well-formed stream has no protocol error");

    malformed_phase=1;
    post_descriptors(999,8);
    send_beat(999,0,8'h0f,1'b1);
    repeat(8) @(posedge clk); #1;
    check_expect(tx_errors==1 && rx_errors==1,"malformed TKEEP/length fails closed at both boundaries");
    $display("P8D_AXIS_RANDOM_BACKPRESSURE_PASS=1");
    $display("P8D_AXIS_NO_LOSS_NO_DUPLICATE_PASS=1");
    $display("P8D_AXIS_MALFORMED_PACKET_REJECTION_PASS=1");
    $display("TB_IR_AXIS_BACKPRESSURE_PASS=1");
    $finish;
  end
endmodule
