`timescale 1ns/1ps
// Synthesizable bounded SG-ring ownership model.  Request and completion data
// are packed into single-write memories; ownership/generation remain explicit
// small state tables so reset/abort and stale-completion rejection are exact.
module ir_dma_descriptor_model #(
  parameter int RING_DEPTH=64,
  parameter int GENERATION_WIDTH=16,
  parameter int TAG_WIDTH=32
) (
  input logic clk,input logic rst_n,input logic clear_counters_i,
  input logic soft_reset_i,input logic abort_i,
  input logic cpu_prepare_valid_i,output logic cpu_prepare_ready_o,
  input logic [63:0] cpu_buffer_address_i,input logic [31:0] cpu_buffer_capacity_i,
  input logic [31:0] cpu_requested_length_i,input logic [TAG_WIDTH-1:0] cpu_user_tag_i,
  input logic [31:0] cpu_session_epoch_i,
  output logic hw_descriptor_valid_o,input logic hw_descriptor_ready_i,
  output logic [$clog2(RING_DEPTH)-1:0] hw_descriptor_index_o,
  output logic [GENERATION_WIDTH-1:0] hw_descriptor_generation_o,
  output logic [63:0] hw_buffer_address_o,output logic [31:0] hw_requested_length_o,
  output logic [TAG_WIDTH-1:0] hw_user_tag_o,
  input logic hw_complete_valid_i,
  input logic [$clog2(RING_DEPTH)-1:0] hw_complete_index_i,
  input logic [GENERATION_WIDTH-1:0] hw_complete_generation_i,
  input logic [31:0] hw_actual_length_i,input logic [15:0] hw_error_code_i,
  output logic hw_complete_accept_pulse_o,output logic hw_complete_reject_pulse_o,
  output logic cpu_completion_valid_o,input logic cpu_completion_ready_i,
  output logic [$clog2(RING_DEPTH)-1:0] cpu_completion_index_o,
  output logic [GENERATION_WIDTH-1:0] cpu_completion_generation_o,
  output logic [31:0] cpu_actual_length_o,
  output logic [TAG_WIDTH-1:0] cpu_completion_user_tag_o,
  output logic [15:0] cpu_completion_status_o,output logic [15:0] cpu_completion_error_o,
  output logic [31:0] producer_count_o,output logic [31:0] hardware_consumer_count_o,
  output logic [31:0] cpu_consumer_count_o,
  output logic [GENERATION_WIDTH-1:0] generation_o,
  output logic [$clog2(RING_DEPTH+1)-1:0] occupancy_o,
  output logic [$clog2(RING_DEPTH+1)-1:0] high_watermark_o,
  output logic [31:0] ring_full_count_o,output logic [31:0] completion_count_o,
  output logic [31:0] error_count_o,output logic [31:0] abort_count_o,
  output logic [31:0] stale_generation_count_o,
  output logic [$clog2(RING_DEPTH+1)-1:0] descriptor_leak_count_o
);
  localparam int INDEX_WIDTH=$clog2(RING_DEPTH);
  localparam int COUNT_WIDTH=$clog2(RING_DEPTH+1);
  localparam int REQUEST_WIDTH=64+32+32+TAG_WIDTH+32;
  localparam int COMPLETION_WIDTH=32+TAG_WIDTH+16+16;
  localparam logic [2:0] DESC_FREE=3'd0,DESC_CPU_PREPARED=3'd1,
    DESC_HW_OWNED=3'd2,DESC_HW_COMPLETED=3'd3,DESC_CPU_RECLAIMED=3'd4,
    DESC_ERROR=3'd5,DESC_ABORTED=3'd6;

  logic [2:0] state[0:RING_DEPTH-1];
  (* ram_style="distributed" *) logic [GENERATION_WIDTH-1:0] generation_hw_memory[0:RING_DEPTH-1];
  (* ram_style="distributed" *) logic [GENERATION_WIDTH-1:0] generation_complete_memory[0:RING_DEPTH-1];
  (* ram_style="distributed" *) logic [GENERATION_WIDTH-1:0] generation_cpu_memory[0:RING_DEPTH-1];
  // Three explicit replicas provide the independent hardware-dispatch,
  // completion-validation, and CPU-reclaim read ports.  Each replica has one
  // asynchronous read port and one common write port, which maps to LUTRAM;
  // a single three-read-port array otherwise expands into thousands of flops
  // and muxes on Zynq-7000.
  (* ram_style="distributed" *) logic [REQUEST_WIDTH-1:0] request_hw_memory[0:RING_DEPTH-1];
  (* ram_style="distributed" *) logic [REQUEST_WIDTH-1:0] request_complete_memory[0:RING_DEPTH-1];
  (* ram_style="distributed" *) logic [REQUEST_WIDTH-1:0] request_cpu_memory[0:RING_DEPTH-1];
  (* ram_style="distributed" *) logic [COMPLETION_WIDTH-1:0] completion_memory[0:RING_DEPTH-1];
  logic [INDEX_WIDTH-1:0] prepare_index,hw_index,completion_index;
  logic [REQUEST_WIDTH-1:0] hw_request,complete_request,cpu_request;
  logic [COMPLETION_WIDTH-1:0] cpu_completion;
  logic [15:0] completion_error_value;
  logic prepare_accept,completion_accept;

  initial begin
    if(RING_DEPTH<2||(RING_DEPTH&(RING_DEPTH-1))!=0)
      $error("RING_DEPTH must be a power of two");
    if(TAG_WIDTH!=32)$error("P8D descriptor model currently requires 32-bit user tag");
  end
  assign prepare_index=producer_count_o[INDEX_WIDTH-1:0];
  assign hw_index=hardware_consumer_count_o[INDEX_WIDTH-1:0];
  assign completion_index=cpu_consumer_count_o[INDEX_WIDTH-1:0];
  assign occupancy_o=producer_count_o-cpu_consumer_count_o;
  assign hw_request=request_hw_memory[hw_index];
  assign complete_request=request_complete_memory[hw_complete_index_i];
  assign cpu_request=request_cpu_memory[completion_index];
  assign cpu_completion=completion_memory[completion_index];
  assign completion_error_value=(hw_actual_length_i>complete_request[95:64])?
    16'd1:hw_error_code_i;
  assign prepare_accept=cpu_prepare_valid_i&&cpu_prepare_ready_o;
  assign completion_accept=hw_complete_valid_i&&hw_complete_generation_i==generation_o&&
    generation_complete_memory[hw_complete_index_i]==hw_complete_generation_i&&
    state[hw_complete_index_i]==DESC_HW_OWNED;

  assign cpu_prepare_ready_o=(occupancy_o<RING_DEPTH)&&
    ((state[prepare_index]==DESC_FREE)||(state[prepare_index]==DESC_CPU_RECLAIMED));
  assign hw_descriptor_valid_o=(hardware_consumer_count_o<producer_count_o)&&
    state[hw_index]==DESC_CPU_PREPARED&&generation_hw_memory[hw_index]==generation_o;
  assign hw_descriptor_index_o=hw_index;
  assign hw_descriptor_generation_o=generation_hw_memory[hw_index];
  assign hw_buffer_address_o=hw_request[63:0];
  assign hw_requested_length_o=hw_request[127:96];
  assign hw_user_tag_o=hw_request[159:128];
  assign cpu_completion_valid_o=(cpu_consumer_count_o<producer_count_o)&&
    ((state[completion_index]==DESC_HW_COMPLETED)||(state[completion_index]==DESC_ERROR)||
     (state[completion_index]==DESC_ABORTED));
  assign cpu_completion_index_o=completion_index;
  assign cpu_completion_generation_o=generation_cpu_memory[completion_index];
  assign cpu_actual_length_o=(state[completion_index]==DESC_ABORTED)?32'd0:cpu_completion[31:0];
  assign cpu_completion_user_tag_o=(state[completion_index]==DESC_ABORTED)?
    cpu_request[159:128]:cpu_completion[63:32];
  assign cpu_completion_status_o=(state[completion_index]==DESC_ABORTED)?16'd3:
    cpu_completion[79:64];
  assign cpu_completion_error_o=(state[completion_index]==DESC_ABORTED)?16'd2:
    cpu_completion[95:80];

  // Keep payload/status RAM writes out of the asynchronously-reset ownership
  // process.  The generation/state table makes stale contents unreachable, so
  // clearing these memories is neither required for correctness nor desirable
  // for RAM inference.
  always_ff @(posedge clk) begin:descriptor_memories
    if(rst_n&&!soft_reset_i&&!abort_i)begin
      if(prepare_accept)begin
        request_hw_memory[prepare_index]<={cpu_session_epoch_i,cpu_user_tag_i,
          cpu_requested_length_i,cpu_buffer_capacity_i,cpu_buffer_address_i};
        request_complete_memory[prepare_index]<={cpu_session_epoch_i,cpu_user_tag_i,
          cpu_requested_length_i,cpu_buffer_capacity_i,cpu_buffer_address_i};
        request_cpu_memory[prepare_index]<={cpu_session_epoch_i,cpu_user_tag_i,
          cpu_requested_length_i,cpu_buffer_capacity_i,cpu_buffer_address_i};
        generation_hw_memory[prepare_index]<=generation_o;
        generation_complete_memory[prepare_index]<=generation_o;
        generation_cpu_memory[prepare_index]<=generation_o;
      end
      if(completion_accept)begin
        completion_memory[hw_complete_index_i]<={completion_error_value,
          (completion_error_value!=0)?16'd2:16'd1,
          complete_request[159:128],hw_actual_length_i};
      end
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin:descriptor_state
    integer entry;
    integer aborted_entries;
    logic [GENERATION_WIDTH-1:0] next_generation;
    if(!rst_n) begin
      producer_count_o<=0;hardware_consumer_count_o<=0;cpu_consumer_count_o<=0;
      generation_o<={{(GENERATION_WIDTH-1){1'b0}},1'b1};high_watermark_o<=0;
      descriptor_leak_count_o<=0;
      ring_full_count_o<=0;completion_count_o<=0;error_count_o<=0;abort_count_o<=0;
      stale_generation_count_o<=0;hw_complete_accept_pulse_o<=0;
      hw_complete_reject_pulse_o<=0;
      for(entry=0;entry<RING_DEPTH;entry=entry+1)begin
        state[entry]<=DESC_FREE;
      end
    end else begin
      hw_complete_accept_pulse_o<=0;hw_complete_reject_pulse_o<=0;
      if(clear_counters_i)begin
        ring_full_count_o<=0;completion_count_o<=0;error_count_o<=0;abort_count_o<=0;
        stale_generation_count_o<=0;high_watermark_o<=occupancy_o;
      end
      if(soft_reset_i||abort_i)begin
        aborted_entries=0;next_generation=generation_o+1'b1;
        if(next_generation=='0)next_generation={{(GENERATION_WIDTH-1){1'b0}},1'b1};
        generation_o<=next_generation;hardware_consumer_count_o<=producer_count_o;
        descriptor_leak_count_o<=0;
        for(entry=0;entry<RING_DEPTH;entry=entry+1)begin
          if(state[entry]==DESC_CPU_PREPARED||state[entry]==DESC_HW_OWNED)begin
            state[entry]<=DESC_ABORTED;aborted_entries=aborted_entries+1;
          end
        end
        if(aborted_entries!=0)abort_count_o<=abort_count_o+aborted_entries;
      end else begin
        if(cpu_prepare_valid_i&&!cpu_prepare_ready_o)ring_full_count_o<=ring_full_count_o+1'b1;
        if(prepare_accept)begin
          state[prepare_index]<=DESC_CPU_PREPARED;
          producer_count_o<=producer_count_o+1'b1;
          if(occupancy_o+1'b1>high_watermark_o)high_watermark_o<=occupancy_o+1'b1;
        end
        if(hw_descriptor_valid_o&&hw_descriptor_ready_i)begin
          state[hw_index]<=DESC_HW_OWNED;
          hardware_consumer_count_o<=hardware_consumer_count_o+1'b1;
        end
        if(hw_complete_valid_i)begin
          if(hw_complete_generation_i!=generation_o||
             generation_complete_memory[hw_complete_index_i]!=hw_complete_generation_i)begin
            stale_generation_count_o<=stale_generation_count_o+1'b1;
            hw_complete_reject_pulse_o<=1;
          end else if(state[hw_complete_index_i]!=DESC_HW_OWNED)begin
            error_count_o<=error_count_o+1'b1;hw_complete_reject_pulse_o<=1;
          end else begin
            state[hw_complete_index_i]<=(completion_error_value!=0)?DESC_ERROR:DESC_HW_COMPLETED;
            if(completion_error_value!=0)error_count_o<=error_count_o+1'b1;
            completion_count_o<=completion_count_o+1'b1;
            hw_complete_accept_pulse_o<=1;
          end
        end
        case({prepare_accept,completion_accept})
          2'b10:descriptor_leak_count_o<=descriptor_leak_count_o+1'b1;
          2'b01:descriptor_leak_count_o<=descriptor_leak_count_o-1'b1;
          default:descriptor_leak_count_o<=descriptor_leak_count_o;
        endcase
        if(cpu_completion_valid_o&&cpu_completion_ready_i)begin
          state[completion_index]<=DESC_CPU_RECLAIMED;
          cpu_consumer_count_o<=cpu_consumer_count_o+1'b1;
        end
      end
    end
  end
endmodule
