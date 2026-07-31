`timescale 1ns/1ps
`default_nettype none

module tb_p10_1_metric_counter;
  logic clk = 0, rst_n = 0, clear, add_valid, wrap;
  logic [7:0] add_value, value;
  always #5 clk = ~clk;
  p10_1_metric_counter #(.WIDTH(8)) dut(
    .clk, .rst_n, .clear_i(clear), .add_valid_i(add_valid),
    .add_value_i(add_value), .value_o(value), .wrap_o(wrap));
  initial begin
    clear = 0; add_valid = 0; add_value = 0;
    repeat (3) @(posedge clk); @(negedge clk); rst_n = 1;
    add_valid = 1; add_value = 8'd250; @(posedge clk); @(negedge clk);
    add_value = 8'd10; @(posedge clk); @(negedge clk); add_valid = 0; #1;
    if (value != 8'd4 || !wrap) $fatal(1, "counter wrap semantics");
    clear = 1; @(posedge clk); @(negedge clk); clear = 0; #1;
    if (value != 0 || wrap) $fatal(1, "counter clear semantics");
    $display("P10_1_METRIC_COUNTER=PASS"); $finish;
  end
endmodule

module tb_p10_1_timer_snapshot;
  logic clk = 0, rst_n = 0, object_reset, snapshot;
  logic [63:0] timer, captured, before_reset;
  logic [31:0] generation;
  always #5 clk = ~clk;
  p10_1_timer_snapshot dut(
    .clk, .rst_n, .object_reset_i(object_reset), .snapshot_i(snapshot),
    .timer_o(timer), .snapshot_o(captured), .generation_o(generation));
  initial begin
    object_reset = 0; snapshot = 0;
    repeat (3) @(posedge clk); @(negedge clk); rst_n = 1;
    repeat (8) @(posedge clk); before_reset = timer;
    @(negedge clk); object_reset = 1; @(posedge clk);
    @(negedge clk); object_reset = 0;
    repeat (2) @(posedge clk);
    if (timer <= before_reset) $fatal(1, "object reset cleared timer");
    @(negedge clk); snapshot = 1; @(posedge clk);
    @(negedge clk); snapshot = 0;
    repeat (2) @(posedge clk); #1;
    if (generation[0] || captured == 0) $fatal(1, "snapshot not coherent");
    $display("P10_1_TIMER_SNAPSHOT=PASS"); $finish;
  end
endmodule

module tb_p10_1_trace_fifo;
  logic clk = 0, rst_n = 0, clear, push, pop, empty, full;
  logic [63:0] push_data, pop_data, overflow;
  logic [3:0] occupancy;
  logic [31:0] generation;
  integer index;
  always #5 clk = ~clk;
  p10_1_event_fifo #(.WIDTH(64), .DEPTH(8)) dut(
    .clk, .rst_n, .clear_i(clear), .push_i(push), .push_data_i(push_data),
    .pop_i(pop), .pop_data_o(pop_data), .empty_o(empty), .full_o(full),
    .occupancy_o(occupancy), .generation_o(generation),
    .overflow_count_o(overflow));
  initial begin
    clear = 0; push = 0; pop = 0; push_data = 0;
    repeat (3) @(posedge clk); @(negedge clk); rst_n = 1;
    for (index = 0; index < 12; index = index + 1) begin
      @(negedge clk); push = 1; push_data = index; @(posedge clk);
    end
    @(negedge clk); push = 0; #1;
    if (!full || overflow != 4) $fatal(1, "FIFO overflow accounting");
    for (index = 0; index < 8; index = index + 1) begin
      #1; if (pop_data != index) $fatal(1, "FIFO ordering");
      pop = 1; @(posedge clk); @(negedge clk); pop = 0;
    end
    #1; if (!empty) $fatal(1, "FIFO did not drain");
    $display("P10_1_TRACE_FIFO=PASS"); $finish;
  end
endmodule

module tb_p10_1_perf_command;
  logic clk = 0, rst_n = 0;
  logic object_reset, wr, rd, axis_accept, axis_stall, desc_submit, desc_complete;
  logic commit, ack_wait, quiet, retry, integrity, active;
  logic [11:0] wr_addr, rd_addr;
  logic [31:0] wr_data, rd_data, commit_bytes, generation;
  logic [2:0] axis_bytes;
  logic [5:0] occupancy;
  logic [63:0] timer;
  logic [127:0] physical_tx_symbols;
  always #5 clk = ~clk;
  p10_1_perf_monitor dut(
    .clk, .rst_n, .object_reset_i(object_reset),
    .reg_wr_en_i(wr), .reg_wr_addr_i(wr_addr), .reg_wr_data_i(wr_data),
    .reg_rd_en_i(rd), .reg_rd_addr_i(rd_addr), .reg_rd_data_o(rd_data),
    .axis_accept_i(axis_accept), .axis_accept_bytes_i(axis_bytes),
    .axis_stall_i(axis_stall), .descriptor_submit_i(desc_submit),
    .descriptor_complete_i(desc_complete), .application_commit_i(commit),
    .application_commit_bytes_i(commit_bytes),
    .physical_tx_symbols_flat_i(physical_tx_symbols),
    .queue_occupancy_i(occupancy),
    .ack_wait_i(ack_wait), .direction_quiet_i(quiet), .retry_i(retry),
    .integrity_error_i(integrity), .perf_active_o(active), .timer_o(timer),
    .snapshot_generation_o(generation));
  task write_reg(input [11:0] address, input [31:0] data);
    begin
      @(negedge clk); wr_addr=address; wr_data=data; wr=1;
      @(posedge clk); @(negedge clk); wr=0;
    end
  endtask
  initial begin
    object_reset=0; wr=0; rd=0; wr_addr=0; rd_addr=0; wr_data=0;
    axis_accept=0; axis_stall=0; desc_submit=0; desc_complete=0;
    commit=0; commit_bytes=0; occupancy=0; ack_wait=0; quiet=0;
    retry=0; integrity=0; axis_bytes=4; physical_tx_symbols=0;
    repeat (3) @(posedge clk); @(negedge clk); rst_n=1;
    write_reg(12'h908, 32'h0001_0003);
    if (!active) $fatal(1, "PERF_START failed");
    repeat (10) begin
      @(negedge clk);
      axis_accept=1; desc_submit=1; desc_complete=1; @(posedge clk);
    end
    @(negedge clk); axis_accept=0; desc_submit=0; desc_complete=0;
    commit=1; commit_bytes=40; @(posedge clk); @(negedge clk); commit=0;
    physical_tx_symbols={32'd16,32'd32,32'd48,32'd64};
    write_reg(12'h934, 1); repeat (3) @(posedge clk);
    rd=1; rd_addr=12'h94C; #1;
    if (rd_data != 40 || generation[0]) $fatal(1, "snapshot data");
    rd_addr=12'h95C; #1;
    if (rd_data != 40) $fatal(1, "physical wire byte accounting");
    rd_addr=12'h900; #1;
    if (rd_data != 32'h50313031) $fatal(1, "capability identity");
    rd=0; write_reg(12'h908, 32'h0002_0006);
    if (active) $fatal(1, "PERF_STOP failed");
    $display("P10_1_PERF_COMMAND=PASS"); $finish;
  end
endmodule

module tb_p10_1_axis_sustained;
  logic clk=0, rst_n=0, clear, s_last, s_valid, s_ready, m_last, m_valid, m_ready;
  logic [31:0] s_data, m_data;
  logic [3:0] s_keep, m_keep;
  logic [63:0] bytes, beats, stalls, first_latency, last_latency;
  integer sent, received;
  logic [15:0] lfsr;
  always #5 clk=~clk;
  p10_1_axis_sustained dut(
    .clk, .rst_n, .clear_i(clear), .s_axis_tdata(s_data),
    .s_axis_tkeep(s_keep), .s_axis_tlast(s_last), .s_axis_tvalid(s_valid),
    .s_axis_tready(s_ready), .m_axis_tdata(m_data), .m_axis_tkeep(m_keep),
    .m_axis_tlast(m_last), .m_axis_tvalid(m_valid), .m_axis_tready(m_ready),
    .accepted_bytes_o(bytes), .accepted_beats_o(beats),
    .stall_cycles_o(stalls), .first_beat_latency_o(first_latency),
    .last_beat_latency_o(last_latency));
  always @(posedge clk) begin
    if (!rst_n) begin lfsr<=16'hACE1; m_ready<=0; end
    else begin
      lfsr <= {lfsr[14:0],lfsr[15]^lfsr[13]^lfsr[12]^lfsr[10]};
      m_ready <= lfsr[0] | lfsr[3];
      if (s_valid && s_ready) begin sent<=sent+1; s_data<=s_data+1; end
      if (m_valid && m_ready) begin
        if (m_data != received) $fatal(1, "beat loss/duplication");
        received<=received+1;
      end
    end
  end
  initial begin
    clear=0; s_last=0; s_valid=0; s_data=0; s_keep=4'hf;
    sent=0; received=0; m_ready=0;
    repeat(3) @(posedge clk); @(negedge clk); rst_n=1; s_valid=1;
    while(sent < 1000) @(posedge clk);
    @(negedge clk); s_valid=0; while(received < 1000) @(posedge clk); #1;
    if(beats != 1000 || bytes != 4000 || stalls == 0)
      $fatal(1, "AXIS counters");
    $display("P10_1_AXIS_SUSTAINED=PASS"); $finish;
  end
endmodule

module tb_p10_1_buffer_pool;
  logic clk=0, rst_n=0, allocate, valid, reclaim;
  logic [2:0] alloc_index, reclaim_index;
  logic [31:0] alloc_generation, reclaim_generation, free_count;
  logic [63:0] double_reclaim;
  integer loop;
  always #5 clk=~clk;
  p10_1_buffer_pool #(.BUFFER_COUNT(8)) dut(
    .clk, .rst_n, .allocate_i(allocate), .allocate_valid_o(valid),
    .allocate_index_o(alloc_index), .allocate_generation_o(alloc_generation),
    .reclaim_i(reclaim), .reclaim_index_i(reclaim_index),
    .reclaim_generation_i(reclaim_generation), .free_count_o(free_count),
    .double_reclaim_count_o(double_reclaim));
  initial begin
    allocate=0; reclaim=0; reclaim_index=0; reclaim_generation=0;
    repeat(3) @(posedge clk); @(negedge clk); rst_n=1;
    for(loop=0; loop<1000; loop=loop+1) begin
      @(negedge clk); allocate=1; #1;
      if(!valid) $fatal(1,"allocation unavailable");
      reclaim_index=alloc_index; reclaim_generation=alloc_generation;
      @(posedge clk); @(negedge clk); allocate=0; reclaim=1;
      @(posedge clk); @(negedge clk); reclaim=0;
    end
    #1; if(free_count != 8 || double_reclaim != 0)
      $fatal(1,"buffer leak/double reclaim");
    $display("P10_1_BUFFER_POOL=PASS"); $finish;
  end
endmodule

module tb_p10_1_descriptor_batch;
  logic clk=0, rst_n=0, clear, submit, submit_ready, complete, complete_valid, irq;
  logic [6:0] outstanding;
  logic [31:0] producer_generation, consumer_generation;
  logic [63:0] submitted, completed, double_completion;
  integer loop;
  always #5 clk=~clk;
  p10_1_descriptor_batch #(.RING_DEPTH(64),.BATCH(16)) dut(
    .clk,.rst_n,.clear_i(clear),.submit_i(submit),.submit_ready_o(submit_ready),
    .complete_i(complete),.complete_valid_o(complete_valid),.interrupt_o(irq),
    .outstanding_o(outstanding),.producer_generation_o(producer_generation),
    .consumer_generation_o(consumer_generation),.submitted_o(submitted),
    .completed_o(completed),.double_completion_o(double_completion));
  initial begin
    clear=0;submit=0;complete=0;
    repeat(3) @(posedge clk);@(negedge clk);rst_n=1;
    for(loop=0;loop<1024;loop=loop+1) begin
      submit=1;complete=0;@(posedge clk);@(negedge clk);
      submit=0;complete=1;@(posedge clk);@(negedge clk);
    end
    complete=0;#1;
    if(outstanding!=0 || submitted!=1024 || completed!=1024 ||
       double_completion!=0 || producer_generation!=16 ||
       consumer_generation!=16) $fatal(1,"descriptor accounting");
    $display("P10_1_DESCRIPTOR_BATCH=PASS");$finish;
  end
endmodule

module tb_p10_1_streaming_chain;
  logic clk=0,rst_n=0,configure,start,abort,valid,ready,last,active,complete,aborted;
  logic [31:0] data;
  logic [3:0] keep;
  logic [63:0] generated,verified,errors,commits;
  always #5 clk=~clk;
  p10_1_autonomous_perf dut(
    .clk,.rst_n,.configure_i(configure),.total_bytes_i(64'd64),
    .seed_i(32'h1234),.stream_id_i(17),.object_id_i(31),.generation_i(7),
    .start_i(start),.abort_i(abort),.m_axis_tdata(data),.m_axis_tkeep(keep),
    .m_axis_tlast(last),.m_axis_tvalid(valid),.m_axis_tready(ready),
    .verify_tdata_i(data),.verify_tkeep_i(keep),.verify_tlast_i(last),
    .verify_tvalid_i(valid),.verify_tready_o(ready),.active_o(active),
    .complete_o(complete),.aborted_o(aborted),.generated_bytes_o(generated),
    .verified_bytes_o(verified),.pattern_error_count_o(errors),
    .atomic_commit_count_o(commits));
  initial begin
    configure=0;start=0;abort=0;
    repeat(3) @(posedge clk);@(negedge clk);rst_n=1;
    configure=1;@(posedge clk);@(negedge clk);configure=0;start=1;
    @(posedge clk);@(negedge clk);start=0;
    wait(complete);#1;
    if(generated!=64 || verified!=64 || errors!=0 || commits!=1) begin
      $display("STREAM_DEBUG configured=%0d generated=%0d verified=%0d errors=%0d commits=%0d last=%0b",
               dut.configured_bytes_q, generated, verified, errors, commits, last);
      $fatal(1,"stream chain");
    end
    $display("P10_1_STREAMING_CHAIN=PASS");$finish;
  end
endmodule

module tb_p10_1_stream_abort_reset;
  logic clk=0,rst_n=0,configure,start,abort,valid,ready,last,active,complete,aborted;
  logic [31:0] data;
  logic [3:0] keep;
  logic [63:0] generated,verified,errors,commits;
  always #5 clk=~clk;
  p10_1_autonomous_perf dut(
    .clk,.rst_n,.configure_i(configure),.total_bytes_i(64'd128),
    .seed_i(1),.stream_id_i(2),.object_id_i(3),.generation_i(4),
    .start_i(start),.abort_i(abort),.m_axis_tdata(data),.m_axis_tkeep(keep),
    .m_axis_tlast(last),.m_axis_tvalid(valid),.m_axis_tready(ready),
    .verify_tdata_i(data),.verify_tkeep_i(keep),.verify_tlast_i(last),
    .verify_tvalid_i(valid),.verify_tready_o(ready),.active_o(active),
    .complete_o(complete),.aborted_o(aborted),.generated_bytes_o(generated),
    .verified_bytes_o(verified),.pattern_error_count_o(errors),
    .atomic_commit_count_o(commits));
  initial begin
    configure=0;start=0;abort=0;
    repeat(3) @(posedge clk);@(negedge clk);rst_n=1;
    configure=1;@(posedge clk);@(negedge clk);configure=0;start=1;
    @(posedge clk);@(negedge clk);start=0;
    repeat(5) @(posedge clk);@(negedge clk);abort=1;
    @(posedge clk);@(negedge clk);abort=0;#1;
    if(!aborted || commits!=0) begin
      $display("ABORT_DEBUG configured=%0d generated=%0d verified=%0d active=%0b aborted=%0b complete=%0b commits=%0d",
               dut.configured_bytes_q, generated, verified, active, aborted,
               complete, commits);
      $fatal(1,"abort atomicity");
    end
    rst_n=0;repeat(2)@(posedge clk);@(negedge clk);rst_n=1;
    configure=1;@(posedge clk);@(negedge clk);configure=0;start=1;
    @(posedge clk);@(negedge clk);start=0;
    wait(complete);#1;
    if(commits!=1 || errors!=0) $fatal(1,"restart atomicity");
    $display("P10_1_STREAM_ABORT_RESET=PASS");$finish;
  end
endmodule

module tb_p10_1_dual_endpoint_perf;
  logic fixed_clk=0,rotating_clk=0,rst_n=0;
  logic f_config,f_start,f_abort,f_valid,f_ready,f_last,f_active,f_complete,f_aborted;
  logic r_config,r_start,r_abort,r_valid,r_ready,r_last,r_active,r_complete,r_aborted;
  logic [31:0] f_data,r_data;
  logic [3:0] f_keep,r_keep;
  logic [63:0] f_gen,f_ver,f_err,f_commit,r_gen,r_ver,r_err,r_commit;
  always #5 fixed_clk=~fixed_clk;
  always #7 rotating_clk=~rotating_clk;
  p10_1_autonomous_perf fixed(
    .clk(fixed_clk),.rst_n,.configure_i(f_config),.total_bytes_i(64'd256),
    .seed_i(1),.stream_id_i(1),.object_id_i(1),.generation_i(1),
    .start_i(f_start),.abort_i(f_abort),.m_axis_tdata(f_data),
    .m_axis_tkeep(f_keep),.m_axis_tlast(f_last),.m_axis_tvalid(f_valid),
    .m_axis_tready(f_ready),.verify_tdata_i(f_data),.verify_tkeep_i(f_keep),
    .verify_tlast_i(f_last),.verify_tvalid_i(f_valid),.verify_tready_o(f_ready),
    .active_o(f_active),.complete_o(f_complete),.aborted_o(f_aborted),
    .generated_bytes_o(f_gen),.verified_bytes_o(f_ver),
    .pattern_error_count_o(f_err),.atomic_commit_count_o(f_commit));
  p10_1_autonomous_perf rotating(
    .clk(rotating_clk),.rst_n,.configure_i(r_config),.total_bytes_i(64'd256),
    .seed_i(7),.stream_id_i(2),.object_id_i(2),.generation_i(2),
    .start_i(r_start),.abort_i(r_abort),.m_axis_tdata(r_data),
    .m_axis_tkeep(r_keep),.m_axis_tlast(r_last),.m_axis_tvalid(r_valid),
    .m_axis_tready(r_ready),.verify_tdata_i(r_data),.verify_tkeep_i(r_keep),
    .verify_tlast_i(r_last),.verify_tvalid_i(r_valid),.verify_tready_o(r_ready),
    .active_o(r_active),.complete_o(r_complete),.aborted_o(r_aborted),
    .generated_bytes_o(r_gen),.verified_bytes_o(r_ver),
    .pattern_error_count_o(r_err),.atomic_commit_count_o(r_commit));
  initial begin
    f_config=0;f_start=0;f_abort=0;r_config=0;r_start=0;r_abort=0;
    repeat(3)@(posedge fixed_clk);@(negedge fixed_clk);rst_n=1;
    @(negedge fixed_clk);f_config=1;
    @(negedge rotating_clk);r_config=1;
    @(posedge fixed_clk);@(negedge fixed_clk);f_config=0;
    @(posedge rotating_clk);@(negedge rotating_clk);r_config=0;
    @(negedge fixed_clk);f_start=1;
    @(negedge rotating_clk);r_start=1;
    @(posedge fixed_clk);@(negedge fixed_clk);f_start=0;
    @(posedge rotating_clk);@(negedge rotating_clk);r_start=0;
    wait(f_complete && r_complete);#1;
    if(f_commit!=1 || r_commit!=1 || f_err!=0 || r_err!=0)
      $fatal(1,"dual endpoint independent services");
    $display("P10_1_DUAL_ENDPOINT_PERF=PASS");$finish;
  end
endmodule

`default_nettype wire
