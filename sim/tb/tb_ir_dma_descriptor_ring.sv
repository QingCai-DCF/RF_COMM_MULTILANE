`timescale 1ns/1ps
module tb_ir_dma_descriptor_ring;
  logic clk=0; always #5 clk=~clk;
  logic rst_n, clear_counters, soft_reset, abort_ring;
  logic cpu_prepare_valid, cpu_prepare_ready;
  logic [63:0] cpu_address;
  logic [31:0] cpu_capacity,cpu_length,cpu_tag,cpu_session;
  logic hw_valid,hw_ready;
  logic [2:0] hw_index,complete_index,cpu_completion_index;
  logic [15:0] hw_generation,complete_generation,cpu_completion_generation,generation;
  logic [63:0] hw_address;
  logic [31:0] hw_length,hw_tag,actual_length,cpu_actual,cpu_completion_tag;
  logic [15:0] complete_error,cpu_completion_status,cpu_completion_error;
  logic hw_complete_valid,complete_accept,complete_reject,cpu_completion_valid,cpu_completion_ready;
  logic [31:0] producer_count,hw_consumer_count,cpu_consumer_count;
  logic [3:0] occupancy,high_watermark,leak_count;
  logic [31:0] full_count,completion_count,error_count,abort_count,stale_count;
  logic rx_prepare_valid,rx_prepare_ready;
  logic [31:0] rx_producer;

  ir_dma_descriptor_model #(.RING_DEPTH(8)) tx_ring (
    .clk,.rst_n,.clear_counters_i(clear_counters),.soft_reset_i(soft_reset),.abort_i(abort_ring),
    .cpu_prepare_valid_i(cpu_prepare_valid),.cpu_prepare_ready_o(cpu_prepare_ready),
    .cpu_buffer_address_i(cpu_address),.cpu_buffer_capacity_i(cpu_capacity),
    .cpu_requested_length_i(cpu_length),.cpu_user_tag_i(cpu_tag),
    .cpu_session_epoch_i(cpu_session),.hw_descriptor_valid_o(hw_valid),
    .hw_descriptor_ready_i(hw_ready),.hw_descriptor_index_o(hw_index),
    .hw_descriptor_generation_o(hw_generation),.hw_buffer_address_o(hw_address),
    .hw_requested_length_o(hw_length),.hw_user_tag_o(hw_tag),
    .hw_complete_valid_i(hw_complete_valid),.hw_complete_index_i(complete_index),
    .hw_complete_generation_i(complete_generation),.hw_actual_length_i(actual_length),
    .hw_error_code_i(complete_error),.hw_complete_accept_pulse_o(complete_accept),
    .hw_complete_reject_pulse_o(complete_reject),.cpu_completion_valid_o(cpu_completion_valid),
    .cpu_completion_ready_i(cpu_completion_ready),.cpu_completion_index_o(cpu_completion_index),
    .cpu_completion_generation_o(cpu_completion_generation),.cpu_actual_length_o(cpu_actual),
    .cpu_completion_user_tag_o(cpu_completion_tag),
    .cpu_completion_status_o(cpu_completion_status),
    .cpu_completion_error_o(cpu_completion_error),.producer_count_o(producer_count),
    .hardware_consumer_count_o(hw_consumer_count),.cpu_consumer_count_o(cpu_consumer_count),
    .generation_o(generation),.occupancy_o(occupancy),.high_watermark_o(high_watermark),
    .ring_full_count_o(full_count),.completion_count_o(completion_count),
    .error_count_o(error_count),.abort_count_o(abort_count),
    .stale_generation_count_o(stale_count),.descriptor_leak_count_o(leak_count)
  );
  ir_dma_descriptor_model #(.RING_DEPTH(8)) rx_ring (
    .clk,.rst_n,.clear_counters_i(1'b0),.soft_reset_i(1'b0),.abort_i(1'b0),
    .cpu_prepare_valid_i(rx_prepare_valid),.cpu_prepare_ready_o(rx_prepare_ready),
    .cpu_buffer_address_i(64'h2000),.cpu_buffer_capacity_i(32'd512),
    .cpu_requested_length_i(32'd256),.cpu_user_tag_i(32'habcdef),
    .cpu_session_epoch_i(32'd1),.hw_descriptor_valid_o(),.hw_descriptor_ready_i(1'b0),
    .hw_descriptor_index_o(),.hw_descriptor_generation_o(),.hw_buffer_address_o(),
    .hw_requested_length_o(),.hw_user_tag_o(),.hw_complete_valid_i(1'b0),
    .hw_complete_index_i(3'd0),.hw_complete_generation_i(16'd0),
    .hw_actual_length_i(32'd0),.hw_error_code_i(16'd0),
    .hw_complete_accept_pulse_o(),.hw_complete_reject_pulse_o(),
    .cpu_completion_valid_o(),.cpu_completion_ready_i(1'b0),
    .cpu_completion_index_o(),.cpu_completion_generation_o(),.cpu_actual_length_o(),
    .cpu_completion_user_tag_o(),.cpu_completion_status_o(),.cpu_completion_error_o(),
    .producer_count_o(rx_producer),.hardware_consumer_count_o(),.cpu_consumer_count_o(),
    .generation_o(),.occupancy_o(),.high_watermark_o(),.ring_full_count_o(),
    .completion_count_o(),.error_count_o(),.abort_count_o(),
    .stale_generation_count_o(),.descriptor_leak_count_o()
  );

  task automatic check_expect(input logic condition,input string message);
    if(!condition) $fatal(1,"DMA_EXPECT_FAIL: %s",message);
  endtask
  task automatic prepare(input integer tag);
    begin
      @(negedge clk); cpu_tag=tag; cpu_address=64'h1000+tag*64;
      cpu_capacity=512; cpu_length=256; cpu_prepare_valid=1;
      while(!cpu_prepare_ready) @(negedge clk);
      @(posedge clk); #1; cpu_prepare_valid=0;
    end
  endtask
  task automatic handoff(output logic [2:0] index,output logic [15:0] gen);
    begin
      while(!hw_valid) @(negedge clk);
      index=hw_index; gen=hw_generation; hw_ready=1;
      @(posedge clk); #1; hw_ready=0;
    end
  endtask
  task automatic complete(input logic [2:0] index,input logic [15:0] gen);
    begin
      @(negedge clk); complete_index=index; complete_generation=gen;
      actual_length=256; complete_error=0; hw_complete_valid=1;
      @(posedge clk); #1; hw_complete_valid=0;
    end
  endtask
  task automatic reap;
    begin
      while(!cpu_completion_valid) @(negedge clk);
      cpu_completion_ready=1; @(posedge clk); #1; cpu_completion_ready=0;
    end
  endtask

  logic [2:0] saved_index; logic [15:0] saved_generation;
  initial begin
    rst_n=0; clear_counters=0; soft_reset=0; abort_ring=0; cpu_prepare_valid=0;
    cpu_address=0;cpu_capacity=0;cpu_length=0;cpu_tag=0;cpu_session=32'd1;
    hw_ready=0;hw_complete_valid=0;complete_index=0;complete_generation=0;
    actual_length=0;complete_error=0;cpu_completion_ready=0;rx_prepare_valid=0;
    repeat(3) @(posedge clk);rst_n=1;@(posedge clk);#1;

    prepare(1); handoff(saved_index,saved_generation); complete(saved_index,saved_generation);
    check_expect(complete_accept && completion_count==1,"hardware completion accepted once");
    check_expect(cpu_completion_valid && cpu_completion_tag==1 && cpu_completion_status==1,
                 "CPU observes matching successful completion");
    reap(); complete(saved_index,saved_generation);
    check_expect(complete_reject && completion_count==1,"duplicate completion is rejected");

    rx_prepare_valid=1; @(posedge clk); #1; rx_prepare_valid=0;
    check_expect(rx_producer==1 && producer_count==1,
                 "independent RX producer cannot perturb TX ring");

    prepare(2); handoff(saved_index,saved_generation);
    abort_ring=1; @(posedge clk); #1; abort_ring=0;
    check_expect(generation!=saved_generation && abort_count==1,
                 "abort advances generation and terminates owned descriptor");
    complete(saved_index,saved_generation);
    check_expect(complete_reject && stale_count==1,"old-generation completion is rejected");
    reap();

    for(int descriptor=0;descriptor<8;descriptor++) prepare(100+descriptor);
    check_expect(occupancy==8 && !cpu_prepare_ready && leak_count==8,
                 "bounded ring applies full backpressure");
    cpu_prepare_valid=1; @(posedge clk); #1; cpu_prepare_valid=0;
    check_expect(full_count==1,"ring-full event is counted");
    abort_ring=1; @(posedge clk); #1; abort_ring=0;
    for(int descriptor=0;descriptor<8;descriptor++) reap();
    check_expect(occupancy==0 && leak_count==0 && abort_count==9,
                 "abort/reclaim is deterministic with zero descriptor leak");
    $display("P8D_TX_RX_RING_INDEPENDENCE_PASS=1");
    $display("P8D_DESCRIPTOR_SINGLE_COMPLETION_PASS=1");
    $display("P8D_RESET_ABORT_STALE_GENERATION_PASS=1");
    $display("P8D_DESCRIPTOR_LEAK_ZERO_PASS=1");
    $display("TB_IR_DMA_DESCRIPTOR_RING_PASS=1");
    $finish;
  end
endmodule
