`timescale 1ns/1ps
`default_nettype wire
`include "generated/ir_register_map_defs.svh"

module p10_1_perf_monitor #(
  parameter int unsigned EVENT_FIFO_DEPTH = 256
) (
  input  logic         clk,
  input  logic         rst_n,
  input  logic         object_reset_i,
  input  logic         reg_wr_en_i,
  input  logic [11:0]  reg_wr_addr_i,
  input  logic [31:0]  reg_wr_data_i,
  input  logic         reg_rd_en_i,
  input  logic [11:0]  reg_rd_addr_i,
  output logic [31:0]  reg_rd_data_o,
  input  logic         axis_accept_i,
  input  logic [2:0]   axis_accept_bytes_i,
  input  logic         axis_stall_i,
  input  logic         descriptor_submit_i,
  input  logic         descriptor_complete_i,
  input  logic         application_commit_i,
  input  logic [31:0]  application_commit_bytes_i,
  input  logic [5:0]   queue_occupancy_i,
  input  logic         ack_wait_i,
  input  logic         direction_quiet_i,
  input  logic         retry_i,
  input  logic         integrity_error_i,
  output logic         perf_active_o,
  output logic [63:0]  timer_o,
  output logic [31:0]  snapshot_generation_o
);
  localparam logic [31:0] PERF_CAPS = 32'h5031_3031;
  localparam logic [31:0] PERF_VERSION = 32'h0002_0001;

  logic [31:0] command_q;
  logic [31:0] status_q;
  logic [31:0] config0_q;
  logic [31:0] duration_q;
  logic [63:0] total_bytes_q;
  logic [31:0] object_size_q;
  logic [31:0] segment_size_q;
  logic [31:0] pattern_seed_q;
  logic [31:0] pipeline_config_q;
  logic [31:0] protocol_config_q;
  logic snapshot_pulse_q;
  logic counter_clear_pulse_q;
  logic trace_clear_pulse_q;

  logic [63:0] timer_snapshot;
  logic [63:0] application_accepted_live_q;
  logic [63:0] application_committed_live_q;
  logic [63:0] frame_acked_live_q;
  logic [63:0] wire_bytes_live_q;
  logic [63:0] descriptor_submitted_live_q;
  logic [63:0] descriptor_completed_live_q;
  logic [63:0] dma_stall_live_q;
  logic [63:0] axis_stall_live_q;
  logic [63:0] ack_wait_live_q;
  logic [63:0] direction_quiet_live_q;
  logic [63:0] integrity_error_live_q;
  logic [63:0] retry_exhausted_live_q;
  logic [63:0] descriptor_leak_live_q;
  logic [63:0] double_completion_live_q;
  logic [5:0] queue_occupancy_high_q;

  logic [63:0] application_accepted_snapshot_q;
  logic [63:0] application_committed_snapshot_q;
  logic [63:0] frame_acked_snapshot_q;
  logic [63:0] wire_bytes_snapshot_q;
  logic [63:0] descriptor_submitted_snapshot_q;
  logic [63:0] descriptor_completed_snapshot_q;
  logic [63:0] dma_stall_snapshot_q;
  logic [63:0] axis_stall_snapshot_q;
  logic [63:0] ack_wait_snapshot_q;
  logic [63:0] direction_quiet_snapshot_q;
  logic [63:0] integrity_error_snapshot_q;
  logic [63:0] retry_exhausted_snapshot_q;
  logic [63:0] descriptor_leak_snapshot_q;
  logic [63:0] double_completion_snapshot_q;
  logic [5:0] queue_occupancy_snapshot_q;

  logic event_push;
  logic [63:0] event_data;
  logic event_pop;
  logic [63:0] event_pop_data;
  logic event_empty;
  logic event_full;
  logic [$clog2(EVENT_FIFO_DEPTH):0] event_occupancy;
  logic [31:0] event_generation;
  logic [63:0] event_overflow;

  initial begin
    if (EVENT_FIFO_DEPTH != 256)
      $error("P10.1 canonical PL event FIFO depth must be 256");
  end

  p10_1_timer_snapshot u_timer (
    .clk,
    .rst_n,
    .object_reset_i,
    .snapshot_i(snapshot_pulse_q),
    .timer_o,
    .snapshot_o(timer_snapshot),
    .generation_o(snapshot_generation_o)
  );

  p10_1_event_fifo #(
    .WIDTH(64),
    .DEPTH(EVENT_FIFO_DEPTH)
  ) u_event_fifo (
    .clk,
    .rst_n,
    .clear_i(trace_clear_pulse_q),
    .push_i(event_push),
    .push_data_i(event_data),
    .pop_i(event_pop),
    .pop_data_o(event_pop_data),
    .empty_o(event_empty),
    .full_o(event_full),
    .occupancy_o(event_occupancy),
    .generation_o(event_generation),
    .overflow_count_o(event_overflow)
  );

  assign event_pop = reg_rd_en_i &&
                     reg_rd_addr_i == `IR_REG_P10_1_EVENT_FIFO_DATA;

  // One fixed-size debug record per cycle at most. Priority is explicit and
  // loss is represented only by the nonblocking FIFO overflow counter.
  always_comb begin
    event_push = 1'b0;
    event_data = '0;
    if (application_commit_i) begin
      event_push = 1'b1;
      event_data = {timer_o[31:0], 8'd15, application_commit_bytes_i[23:0]};
    end else if (integrity_error_i) begin
      event_push = 1'b1;
      event_data = {timer_o[31:0], 8'd14, 24'd0};
    end else if (retry_i) begin
      event_push = 1'b1;
      event_data = {timer_o[31:0], 8'd8, 24'd0};
    end else if (descriptor_complete_i) begin
      event_push = 1'b1;
      event_data = {timer_o[31:0], 8'd3, 24'd0};
    end else if (descriptor_submit_i) begin
      event_push = 1'b1;
      event_data = {timer_o[31:0], 8'd2, 24'd0};
    end else if (axis_accept_i) begin
      event_push = 1'b1;
      event_data = {timer_o[31:0], 8'd1, 21'd0, axis_accept_bytes_i};
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      command_q <= '0;
      status_q <= '0;
      config0_q <= 32'h0000_0003;
      duration_q <= 32'd30;
      total_bytes_q <= 64'd67_108_864;
      object_size_q <= 32'd1_048_576;
      segment_size_q <= 32'd65_536;
      pattern_seed_q <= 32'h0135_6BFB;
      pipeline_config_q <= {8'd16, 8'd64, 8'd8, 8'd0};
      protocol_config_q <= {8'd16, 8'd32, 8'd16, 8'd0};
      perf_active_o <= 1'b0;
      snapshot_pulse_q <= 1'b0;
      counter_clear_pulse_q <= 1'b0;
      trace_clear_pulse_q <= 1'b0;
      application_accepted_live_q <= '0;
      application_committed_live_q <= '0;
      frame_acked_live_q <= '0;
      wire_bytes_live_q <= '0;
      descriptor_submitted_live_q <= '0;
      descriptor_completed_live_q <= '0;
      dma_stall_live_q <= '0;
      axis_stall_live_q <= '0;
      ack_wait_live_q <= '0;
      direction_quiet_live_q <= '0;
      integrity_error_live_q <= '0;
      retry_exhausted_live_q <= '0;
      descriptor_leak_live_q <= '0;
      double_completion_live_q <= '0;
      queue_occupancy_high_q <= '0;
      application_accepted_snapshot_q <= '0;
      application_committed_snapshot_q <= '0;
      frame_acked_snapshot_q <= '0;
      wire_bytes_snapshot_q <= '0;
      descriptor_submitted_snapshot_q <= '0;
      descriptor_completed_snapshot_q <= '0;
      dma_stall_snapshot_q <= '0;
      axis_stall_snapshot_q <= '0;
      ack_wait_snapshot_q <= '0;
      direction_quiet_snapshot_q <= '0;
      integrity_error_snapshot_q <= '0;
      retry_exhausted_snapshot_q <= '0;
      descriptor_leak_snapshot_q <= '0;
      double_completion_snapshot_q <= '0;
      queue_occupancy_snapshot_q <= '0;
    end else begin
      snapshot_pulse_q <= 1'b0;
      counter_clear_pulse_q <= 1'b0;
      trace_clear_pulse_q <= 1'b0;
      if (reg_wr_en_i) begin
        unique case (reg_wr_addr_i)
          `IR_REG_P10_1_PERF_COMMAND: begin
            command_q <= reg_wr_data_i;
            unique case (reg_wr_data_i[3:0])
              4'd3: begin // PERF_START
                perf_active_o <= 1'b1;
                status_q <= 32'h0000_0001;
              end
              4'd6: begin // PERF_STOP
                perf_active_o <= 1'b0;
                status_q <= 32'h0000_0002;
              end
              4'd7: begin // PERF_ABORT
                perf_active_o <= 1'b0;
                status_q <= 32'h0000_0004;
              end
              4'd8: begin // PERF_CLEAR
                perf_active_o <= 1'b0;
                status_q <= '0;
                counter_clear_pulse_q <= 1'b1;
                trace_clear_pulse_q <= 1'b1;
              end
              default: status_q <= status_q;
            endcase
          end
          `IR_REG_P10_1_PERF_CONFIG0: config0_q <= reg_wr_data_i;
          `IR_REG_P10_1_PERF_DURATION_SECONDS: duration_q <= reg_wr_data_i;
          `IR_REG_P10_1_TOTAL_BYTES_LOW: total_bytes_q[31:0] <= reg_wr_data_i;
          `IR_REG_P10_1_TOTAL_BYTES_HIGH: total_bytes_q[63:32] <= reg_wr_data_i;
          `IR_REG_P10_1_OBJECT_SIZE_BYTES: object_size_q <= reg_wr_data_i;
          `IR_REG_P10_1_SEGMENT_SIZE_BYTES: segment_size_q <= reg_wr_data_i;
          `IR_REG_P10_1_PATTERN_SEED: pattern_seed_q <= reg_wr_data_i;
          `IR_REG_P10_1_PIPELINE_CONFIG: pipeline_config_q <= reg_wr_data_i;
          `IR_REG_P10_1_PROTOCOL_CONFIG: protocol_config_q <= reg_wr_data_i;
          `IR_REG_P10_1_SNAPSHOT_CONTROL: begin
            snapshot_pulse_q <= reg_wr_data_i[0];
            counter_clear_pulse_q <= reg_wr_data_i[1];
            trace_clear_pulse_q <= reg_wr_data_i[2];
          end
          default: ;
        endcase
      end

      if (counter_clear_pulse_q) begin
        application_accepted_live_q <= '0;
        application_committed_live_q <= '0;
        frame_acked_live_q <= '0;
        wire_bytes_live_q <= '0;
        descriptor_submitted_live_q <= '0;
        descriptor_completed_live_q <= '0;
        dma_stall_live_q <= '0;
        axis_stall_live_q <= '0;
        ack_wait_live_q <= '0;
        direction_quiet_live_q <= '0;
        integrity_error_live_q <= '0;
        retry_exhausted_live_q <= '0;
        descriptor_leak_live_q <= '0;
        double_completion_live_q <= '0;
        queue_occupancy_high_q <= '0;
      end else begin
        if (axis_accept_i) begin
          application_accepted_live_q <=
              application_accepted_live_q + axis_accept_bytes_i;
          wire_bytes_live_q <= wire_bytes_live_q + axis_accept_bytes_i;
        end
        if (application_commit_i) begin
          application_committed_live_q <= application_committed_live_q +
              application_commit_bytes_i;
          frame_acked_live_q <= frame_acked_live_q +
              application_commit_bytes_i;
        end
        if (descriptor_submit_i)
          descriptor_submitted_live_q <= descriptor_submitted_live_q + 1'b1;
        if (descriptor_complete_i)
          descriptor_completed_live_q <= descriptor_completed_live_q + 1'b1;
        if (axis_stall_i) begin
          axis_stall_live_q <= axis_stall_live_q + 1'b1;
          dma_stall_live_q <= dma_stall_live_q + 1'b1;
        end
        if (ack_wait_i)
          ack_wait_live_q <= ack_wait_live_q + 1'b1;
        if (direction_quiet_i)
          direction_quiet_live_q <= direction_quiet_live_q + 1'b1;
        if (integrity_error_i)
          integrity_error_live_q <= integrity_error_live_q + 1'b1;
        if (retry_i)
          retry_exhausted_live_q <= retry_exhausted_live_q + 1'b1;
        if (queue_occupancy_i > queue_occupancy_high_q)
          queue_occupancy_high_q <= queue_occupancy_i;
      end

      if (snapshot_pulse_q) begin
        application_accepted_snapshot_q <= application_accepted_live_q;
        application_committed_snapshot_q <= application_committed_live_q;
        frame_acked_snapshot_q <= frame_acked_live_q;
        wire_bytes_snapshot_q <= wire_bytes_live_q;
        descriptor_submitted_snapshot_q <= descriptor_submitted_live_q;
        descriptor_completed_snapshot_q <= descriptor_completed_live_q;
        dma_stall_snapshot_q <= dma_stall_live_q;
        axis_stall_snapshot_q <= axis_stall_live_q;
        ack_wait_snapshot_q <= ack_wait_live_q;
        direction_quiet_snapshot_q <= direction_quiet_live_q;
        integrity_error_snapshot_q <= integrity_error_live_q;
        retry_exhausted_snapshot_q <= retry_exhausted_live_q;
        descriptor_leak_snapshot_q <= descriptor_leak_live_q;
        double_completion_snapshot_q <= double_completion_live_q;
        queue_occupancy_snapshot_q <= queue_occupancy_high_q;
      end
    end
  end

  always_comb begin
    reg_rd_data_o = '0;
    unique case (reg_rd_addr_i)
      `IR_REG_P10_1_PERF_CAPS: reg_rd_data_o = PERF_CAPS;
      `IR_REG_P10_1_PERF_VERSION: reg_rd_data_o = PERF_VERSION;
      `IR_REG_P10_1_PERF_COMMAND: reg_rd_data_o = command_q;
      `IR_REG_P10_1_PERF_STATUS: reg_rd_data_o =
          {24'd0, status_q[6:0], perf_active_o};
      `IR_REG_P10_1_PERF_CONFIG0: reg_rd_data_o = config0_q;
      `IR_REG_P10_1_PERF_DURATION_SECONDS: reg_rd_data_o = duration_q;
      `IR_REG_P10_1_TOTAL_BYTES_LOW: reg_rd_data_o = total_bytes_q[31:0];
      `IR_REG_P10_1_TOTAL_BYTES_HIGH: reg_rd_data_o = total_bytes_q[63:32];
      `IR_REG_P10_1_OBJECT_SIZE_BYTES: reg_rd_data_o = object_size_q;
      `IR_REG_P10_1_SEGMENT_SIZE_BYTES: reg_rd_data_o = segment_size_q;
      `IR_REG_P10_1_PATTERN_SEED: reg_rd_data_o = pattern_seed_q;
      `IR_REG_P10_1_PIPELINE_CONFIG: reg_rd_data_o = pipeline_config_q;
      `IR_REG_P10_1_PROTOCOL_CONFIG: reg_rd_data_o = protocol_config_q;
      `IR_REG_P10_1_SNAPSHOT_GENERATION:
          reg_rd_data_o = snapshot_generation_o;
      `IR_REG_P10_1_TIMER_SNAPSHOT_LOW:
          reg_rd_data_o = timer_snapshot[31:0];
      `IR_REG_P10_1_TIMER_SNAPSHOT_HIGH:
          reg_rd_data_o = timer_snapshot[63:32];
      `IR_REG_P10_1_APPLICATION_ACCEPTED_LOW:
          reg_rd_data_o = application_accepted_snapshot_q[31:0];
      `IR_REG_P10_1_APPLICATION_ACCEPTED_HIGH:
          reg_rd_data_o = application_accepted_snapshot_q[63:32];
      `IR_REG_P10_1_APPLICATION_COMMITTED_LOW:
          reg_rd_data_o = application_committed_snapshot_q[31:0];
      `IR_REG_P10_1_APPLICATION_COMMITTED_HIGH:
          reg_rd_data_o = application_committed_snapshot_q[63:32];
      `IR_REG_P10_1_FRAME_ACKED_LOW:
          reg_rd_data_o = frame_acked_snapshot_q[31:0];
      `IR_REG_P10_1_FRAME_ACKED_HIGH:
          reg_rd_data_o = frame_acked_snapshot_q[63:32];
      `IR_REG_P10_1_WIRE_BYTES_LOW:
          reg_rd_data_o = wire_bytes_snapshot_q[31:0];
      `IR_REG_P10_1_WIRE_BYTES_HIGH:
          reg_rd_data_o = wire_bytes_snapshot_q[63:32];
      `IR_REG_P10_1_DESCRIPTOR_SUBMITTED:
          reg_rd_data_o = descriptor_submitted_snapshot_q[31:0];
      `IR_REG_P10_1_DESCRIPTOR_COMPLETED:
          reg_rd_data_o = descriptor_completed_snapshot_q[31:0];
      `IR_REG_P10_1_DMA_STALL_LOW:
          reg_rd_data_o = dma_stall_snapshot_q[31:0];
      `IR_REG_P10_1_DMA_STALL_HIGH:
          reg_rd_data_o = dma_stall_snapshot_q[63:32];
      `IR_REG_P10_1_AXIS_STALL_LOW:
          reg_rd_data_o = axis_stall_snapshot_q[31:0];
      `IR_REG_P10_1_AXIS_STALL_HIGH:
          reg_rd_data_o = axis_stall_snapshot_q[63:32];
      `IR_REG_P10_1_QUEUE_OCCUPANCY:
          reg_rd_data_o = {20'd0, queue_occupancy_snapshot_q,
                           queue_occupancy_i};
      `IR_REG_P10_1_ACK_WAIT_LOW:
          reg_rd_data_o = ack_wait_snapshot_q[31:0];
      `IR_REG_P10_1_ACK_WAIT_HIGH:
          reg_rd_data_o = ack_wait_snapshot_q[63:32];
      `IR_REG_P10_1_DIRECTION_QUIET_LOW:
          reg_rd_data_o = direction_quiet_snapshot_q[31:0];
      `IR_REG_P10_1_DIRECTION_QUIET_HIGH:
          reg_rd_data_o = direction_quiet_snapshot_q[63:32];
      `IR_REG_P10_1_PS_PREPARE_LOW: reg_rd_data_o = 32'd0;
      `IR_REG_P10_1_PS_PREPARE_HIGH: reg_rd_data_o = 32'd0;
      `IR_REG_P10_1_CRC_SHA_LOW: reg_rd_data_o = 32'd0;
      `IR_REG_P10_1_CRC_SHA_HIGH: reg_rd_data_o = 32'd0;
      `IR_REG_P10_1_TRACE_STATUS: reg_rd_data_o =
          {event_generation[7:0], event_overflow[7:0],
           5'd0, event_occupancy,
           event_full, event_empty};
      `IR_REG_P10_1_STREAM_STATUS: reg_rd_data_o =
          {23'd0, status_q[7:0], perf_active_o};
      `IR_REG_P10_1_EVENT_FIFO_DATA:
          reg_rd_data_o = event_pop_data[31:0];
      `IR_REG_P10_1_EVENT_FIFO_STATUS: reg_rd_data_o =
          {event_generation[7:0], event_overflow[7:0],
           5'd0, event_occupancy,
           event_full, event_empty};
      `IR_REG_P10_1_INTEGRITY_ERROR_COUNT:
          reg_rd_data_o = integrity_error_snapshot_q[31:0];
      `IR_REG_P10_1_RETRY_EXHAUSTED_COUNT:
          reg_rd_data_o = retry_exhausted_snapshot_q[31:0];
      `IR_REG_P10_1_DESCRIPTOR_LEAK_COUNT:
          reg_rd_data_o = descriptor_leak_snapshot_q[31:0];
      `IR_REG_P10_1_DOUBLE_COMPLETION_COUNT:
          reg_rd_data_o = double_completion_snapshot_q[31:0];
      default: reg_rd_data_o = '0;
    endcase
  end
endmodule

`default_nettype wire
