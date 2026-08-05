`timescale 1ns/1ps
`default_nettype none

module tb_p10_4_perf_command;
  integer metric_index;
  logic clk = 0, rst_n = 0;
  logic object_reset, wr, rd, axis_accept, axis_stall, desc_submit, desc_complete;
  logic commit, ack_wait, quiet, retry, integrity, active;
  logic tx_idle_ack, window_full, receiver_credit, turnaround_idle;
  logic [11:0] wr_addr, rd_addr;
  logic [31:0] wr_data, rd_data, commit_bytes, generation;
  logic [2:0] axis_bytes;
  logic [5:0] occupancy;
  logic [63:0] timer;
  logic [127:0] physical_tx_symbols;
  always #5 clk = ~clk;

  p10_1_perf_monitor #(.PHYSICAL_MODULE_COUNT(4)) dut (
    .clk(clk), .rst_n(rst_n), .object_reset_i(object_reset),
    .reg_wr_en_i(wr), .reg_wr_addr_i(wr_addr), .reg_wr_data_i(wr_data),
    .reg_rd_en_i(rd), .reg_rd_addr_i(rd_addr), .reg_rd_data_o(rd_data),
    .axis_accept_i(axis_accept), .axis_accept_bytes_i(axis_bytes),
    .axis_stall_i(axis_stall), .descriptor_submit_i(desc_submit),
    .descriptor_complete_i(desc_complete), .application_commit_i(commit),
    .application_commit_bytes_i(commit_bytes),
    .physical_tx_symbols_flat_i(physical_tx_symbols),
    .queue_occupancy_i(occupancy), .ack_wait_i(ack_wait),
    .direction_quiet_i(quiet), .tx_idle_due_to_ack_i(tx_idle_ack),
    .window_full_stall_i(window_full),
    .receiver_credit_stall_i(receiver_credit),
    .direction_turnaround_idle_i(turnaround_idle), .retry_i(retry),
    .integrity_error_i(integrity), .perf_active_o(active), .timer_o(timer),
    .snapshot_generation_o(generation));

  task write_reg(input [11:0] address, input [31:0] data);
    begin @(negedge clk); wr=1; wr_addr=address; wr_data=data;
      @(posedge clk); @(negedge clk); wr=0; end
  endtask

  initial begin
    object_reset=0; wr=0; rd=0; wr_addr=0; rd_addr=0; wr_data=0;
    axis_accept=0; axis_stall=0; desc_submit=0; desc_complete=0;
    commit=0; commit_bytes=0; occupancy=0; ack_wait=0; quiet=0;
    tx_idle_ack=0; window_full=0; receiver_credit=0; turnaround_idle=0;
    retry=0; integrity=0; axis_bytes=4; physical_tx_symbols=0;
    repeat (3) @(posedge clk); @(negedge clk); rst_n=1;
    write_reg(12'h908, 32'h0001_0003);
    if (!active) $fatal(1, "PERF_START failed");
    for (metric_index=0; metric_index<10; metric_index=metric_index+1) begin
      @(negedge clk); axis_accept=1; desc_submit=1; desc_complete=1; ack_wait=1;
      tx_idle_ack=(metric_index<8); window_full=(metric_index<6);
      receiver_credit=(metric_index<4); turnaround_idle=(metric_index<2);
      @(posedge clk);
    end
    @(negedge clk); axis_accept=0; desc_submit=0; desc_complete=0; ack_wait=0;
    tx_idle_ack=0; window_full=0; receiver_credit=0; turnaround_idle=0;
    commit=1; commit_bytes=40; @(posedge clk); @(negedge clk); commit=0;
    physical_tx_symbols={32'd16,32'd32,32'd48,32'd64};
    write_reg(12'h934, 1); repeat (3) @(posedge clk);
    rd=1;
    rd_addr=12'hd84; #1; if (rd_data != 32'h50310401) $fatal(1, "schema");
    rd_addr=12'hd88; #1; if (rd_data != 10) $fatal(1, "occupancy");
    rd_addr=12'hd90; #1; if (rd_data != 8) $fatal(1, "ack idle");
    rd_addr=12'hd98; #1; if (rd_data != 6) $fatal(1, "window full");
    rd_addr=12'hda0; #1; if (rd_data != 4) $fatal(1, "credit");
    rd_addr=12'hda8; #1; if (rd_data != 2) $fatal(1, "turnaround");
    $display("P10_4_PERF_COUNTER_SPLIT_XSIM=PASS");
    $finish;
  end
endmodule

`default_nettype wire
