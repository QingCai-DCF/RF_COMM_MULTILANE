`timescale 1ns/1ps
module ir_selective_repeat_tx #(
  parameter int WINDOW_SIZE = 32,
  parameter int SACK_BITS = 64,
  parameter int MAX_RETRY = 7,
  parameter int RTO_CYCLES = 64000,
  parameter int RETRY_PRIORITY_BURST_MAX = 8,
  parameter int PAYLOAD_REF_WIDTH = 16,
  parameter int DESCRIPTOR_WIDTH = 16
) (
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         clear_counters_i,
  input  logic                         session_reset_i,
  input  logic [31:0]                  session_epoch_i,
  input  logic                         abort_all_i,
  input  logic                         allocate_valid_i,
  output logic                         allocate_ready_o,
  input  logic [PAYLOAD_REF_WIDTH-1:0] allocate_payload_ref_i,
  input  logic [15:0]                  allocate_payload_length_i,
  input  logic [DESCRIPTOR_WIDTH-1:0]  allocate_descriptor_i,
  input  logic [2:0]                   allocate_priority_i,
  output logic                         allocate_pulse_o,
  output logic [15:0]                  allocated_sequence_o,
  output logic [$clog2(WINDOW_SIZE)-1:0] allocated_entry_o,
  output logic                         attempt_valid_o,
  input  logic                         attempt_ready_i,
  output logic [$clog2(WINDOW_SIZE)-1:0] attempt_entry_o,
  output logic [15:0]                  attempt_sequence_o,
  output logic [PAYLOAD_REF_WIDTH-1:0] attempt_payload_ref_o,
  output logic [15:0]                  attempt_payload_length_o,
  output logic [DESCRIPTOR_WIDTH-1:0]  attempt_descriptor_o,
  output logic [2:0]                   attempt_priority_o,
  output logic                         attempt_is_retry_o,
  output logic [2:0]                   attempt_last_lane_o,
  input  logic [2:0]                   selected_lane_i,
  input  logic [15:0]                  selected_path_epoch_i,
  input  logic                         ack_valid_i,
  input  logic [31:0]                  ack_session_epoch_i,
  input  logic [15:0]                  ack_base_i,
  input  logic [SACK_BITS-1:0]         ack_bitmap_i,
  input  logic [$clog2(SACK_BITS):0]   ack_width_i,
  output logic                         completion_pulse_o,
  output logic [31:0]                  completion_batch_count_o,
  output logic [15:0]                  tx_next_sequence_o,
  output logic [15:0]                  tx_ack_base_o,
  output logic [$clog2(WINDOW_SIZE+1)-1:0] outstanding_count_o,
  output logic [$clog2(WINDOW_SIZE+1)-1:0] outstanding_high_watermark_o,
  output logic [31:0]                  attempt_count_o,
  output logic [31:0]                  retry_count_o,
  output logic [31:0]                  retry_exhausted_count_o,
  output logic [31:0]                  timeout_count_o,
  output logic [31:0]                  duplicate_ack_count_o,
  output logic [31:0]                  stale_ack_count_o,
  output logic [31:0]                  out_of_window_ack_count_o,
  output logic [31:0]                  migration_count_o,
  output logic                         retry_exhausted_sticky_o
);
  import ir_seq_math_pkg::*;
  localparam int INDEX_WIDTH = $clog2(WINDOW_SIZE);
  localparam int COUNT_WIDTH = $clog2(WINDOW_SIZE + 1);
  localparam int TIMER_WIDTH = $clog2(RTO_CYCLES + 1);

  logic entry_valid [0:WINDOW_SIZE-1];
  logic [3:0] entry_state [0:WINDOW_SIZE-1];
  localparam int PAYLOAD_META_WIDTH=PAYLOAD_REF_WIDTH+16+DESCRIPTOR_WIDTH;
  (* ram_style="distributed" *) logic [PAYLOAD_META_WIDTH-1:0]
    entry_payload_memory [0:WINDOW_SIZE-1];
  logic [PAYLOAD_META_WIDTH-1:0] attempt_payload_metadata;
  logic [2:0] entry_priority [0:WINDOW_SIZE-1];
  logic [2:0] entry_last_lane [0:WINDOW_SIZE-1];
  logic entry_have_lane [0:WINDOW_SIZE-1];
  logic [15:0] entry_path_epoch [0:WINDOW_SIZE-1];
  logic [7:0] entry_attempts [0:WINDOW_SIZE-1];
  logic [7:0] entry_retries [0:WINDOW_SIZE-1];
  logic [TIMER_WIDTH-1:0] entry_timer [0:WINDOW_SIZE-1];
  logic [WINDOW_SIZE-1:0] ack_match;
  logic ack_malformed;
  logic ack_window_valid;
  logic [15:0] ack_cumulative_distance;
  logic [15:0] active_span;
  logic [$clog2(RETRY_PRIORITY_BURST_MAX+1)-1:0] retry_burst_count;

  initial begin
    if (WINDOW_SIZE < 32 || (WINDOW_SIZE & (WINDOW_SIZE-1)) != 0)
      $error("WINDOW_SIZE must be power-of-two and at least 32");
    if (SACK_BITS < 32 || SACK_BITS > WINDOW_SIZE)
      $error("SACK_BITS must be 32..WINDOW_SIZE");
  end

  assign allocate_ready_o = (outstanding_count_o < WINDOW_SIZE) &&
                            !entry_valid[tx_next_sequence_o[INDEX_WIDTH-1:0]];
  assign attempt_payload_metadata=entry_payload_memory[attempt_entry_o];
  assign attempt_payload_ref_o=attempt_payload_metadata[PAYLOAD_REF_WIDTH-1:0];
  assign attempt_payload_length_o=
    attempt_payload_metadata[PAYLOAD_REF_WIDTH +: 16];
  assign attempt_descriptor_o=
    attempt_payload_metadata[PAYLOAD_REF_WIDTH+16 +: DESCRIPTOR_WIDTH];
  assign ack_cumulative_distance = seq_distance(ack_base_i, tx_ack_base_o);
  assign active_span = seq_distance(tx_next_sequence_o, tx_ack_base_o);
  assign ack_window_valid = (ack_cumulative_distance <= active_span) &&
                            (ack_cumulative_distance <= WINDOW_SIZE);

  always_comb begin : ack_decode
    ack_malformed = (ack_width_i < 32) || (ack_width_i > SACK_BITS);
    for (int bit_index = 0; bit_index < SACK_BITS; bit_index++) begin
      if ((bit_index >= ack_width_i) && ack_bitmap_i[bit_index]) ack_malformed = 1'b1;
    end
    ack_match = '0;
    for (int offset = 0; offset < WINDOW_SIZE; offset++) begin
      logic [15:0] scan_sequence;
      logic [INDEX_WIDTH-1:0] scan_index;
      logic [15:0] distance;
      scan_sequence=tx_ack_base_o+offset;
      scan_index=scan_sequence[INDEX_WIDTH-1:0];
      distance = seq_distance(scan_sequence, ack_base_i);
      if (ack_valid_i && ack_session_epoch_i == session_epoch_i &&
          !ack_malformed && ack_window_valid && entry_valid[scan_index]) begin
        if (seq_before(scan_sequence, ack_base_i) ||
            ((distance < ack_width_i) && ack_bitmap_i[distance])) begin
          ack_match[scan_index] = 1'b1;
        end
      end
    end
  end

  always_comb begin : attempt_select
    logic found;
    logic prefer_retry;
    logic [2:0] best_priority;
    found = 1'b0;
    prefer_retry = (retry_burst_count < RETRY_PRIORITY_BURST_MAX);
    best_priority = 3'd0;
    attempt_valid_o = 1'b0;
    attempt_entry_o = '0;
    attempt_sequence_o = 16'd0;
    attempt_priority_o = 3'd0;
    attempt_is_retry_o = 1'b0;
    attempt_last_lane_o = 3'd0;
    // Retry traffic is preferred only for a bounded burst.  Within each class,
    // higher application/control priority wins and modular sequence order breaks
    // ties.  A normal entry is therefore guaranteed an admission opportunity.
    for (int offset = 0; offset < WINDOW_SIZE; offset++) begin
      logic [15:0] candidate_sequence;
      logic [INDEX_WIDTH-1:0] candidate_index;
      candidate_sequence = tx_ack_base_o + offset;
      candidate_index = candidate_sequence[INDEX_WIDTH-1:0];
      if (entry_valid[candidate_index] &&
          ((prefer_retry && entry_state[candidate_index] == 4'd6) ||
           (!prefer_retry && entry_state[candidate_index] == 4'd2)) &&
          (!found || entry_priority[candidate_index] > best_priority)) begin
        found = 1'b1;
        best_priority = entry_priority[candidate_index];
        attempt_valid_o = 1'b1;
        attempt_entry_o = candidate_index;
        attempt_sequence_o = candidate_sequence;
        attempt_priority_o = entry_priority[candidate_index];
        attempt_is_retry_o = (entry_state[candidate_index] == 4'd6);
        attempt_last_lane_o = entry_last_lane[candidate_index];
      end
    end
    // Fall back to the other class when the preferred class is empty.
    if (!found) begin
      best_priority = 3'd0;
      for (int offset = 0; offset < WINDOW_SIZE; offset++) begin
        logic [15:0] candidate_sequence;
        logic [INDEX_WIDTH-1:0] candidate_index;
        candidate_sequence = tx_ack_base_o + offset;
        candidate_index = candidate_sequence[INDEX_WIDTH-1:0];
        if (entry_valid[candidate_index] &&
            ((prefer_retry && entry_state[candidate_index] == 4'd2) ||
             (!prefer_retry && entry_state[candidate_index] == 4'd6)) &&
            (!found || entry_priority[candidate_index] > best_priority)) begin
          found = 1'b1;
          best_priority = entry_priority[candidate_index];
          attempt_valid_o = 1'b1;
          attempt_entry_o = candidate_index;
          attempt_sequence_o = candidate_sequence;
          attempt_priority_o = entry_priority[candidate_index];
          attempt_is_retry_o = (entry_state[candidate_index] == 4'd6);
          attempt_last_lane_o = entry_last_lane[candidate_index];
        end
      end
    end
  end

  // Payload/descriptor metadata is invalid whenever entry_valid is low, so it
  // need not be reset.  Keeping its write in a reset-free process allows the
  // shared global window to map this storage into LUTRAM instead of replicated
  // flip-flop/mux banks.
  always_ff @(posedge clk) begin:payload_metadata_memory
    if(rst_n&&!session_reset_i&&!abort_all_i&&allocate_valid_i&&allocate_ready_o)
      entry_payload_memory[tx_next_sequence_o[INDEX_WIDTH-1:0]]<=
        {allocate_descriptor_i,allocate_payload_length_i,allocate_payload_ref_i};
  end

  always_ff @(posedge clk or negedge rst_n) begin : tx_state
    integer entry;
    integer occupancy_delta;
    integer acked_count;
    logic [INDEX_WIDTH-1:0] allocation_index;
    logic [15:0] candidate_base;
    logic base_found;
    if (!rst_n) begin
      tx_next_sequence_o <= 16'd0;
      tx_ack_base_o <= 16'd0;
      outstanding_count_o <= '0;
      outstanding_high_watermark_o <= '0;
      allocate_pulse_o <= 1'b0;
      allocated_sequence_o <= 16'd0;
      allocated_entry_o <= '0;
      completion_pulse_o <= 1'b0;
      completion_batch_count_o <= 32'd0;
      attempt_count_o <= 32'd0;
      retry_count_o <= 32'd0;
      retry_exhausted_count_o <= 32'd0;
      timeout_count_o <= 32'd0;
      duplicate_ack_count_o <= 32'd0;
      stale_ack_count_o <= 32'd0;
      out_of_window_ack_count_o <= 32'd0;
      migration_count_o <= 32'd0;
      retry_exhausted_sticky_o <= 1'b0;
      retry_burst_count <= '0;
      for (entry = 0; entry < WINDOW_SIZE; entry = entry + 1) begin
        entry_valid[entry] <= 1'b0;
        entry_state[entry] <= 4'd0;
        entry_priority[entry] <= 3'd0;
        entry_last_lane[entry] <= 3'd0;
        entry_have_lane[entry] <= 1'b0;
        entry_path_epoch[entry] <= 16'd0;
        entry_attempts[entry] <= 8'd0;
        entry_retries[entry] <= 8'd0;
        entry_timer[entry] <= '0;
      end
    end else begin
      allocate_pulse_o <= 1'b0;
      completion_pulse_o <= 1'b0;
      completion_batch_count_o <= 32'd0;
      occupancy_delta = 0;
      acked_count = 0;
      if (clear_counters_i) begin
        attempt_count_o <= 32'd0;
        retry_count_o <= 32'd0;
        retry_exhausted_count_o <= 32'd0;
        timeout_count_o <= 32'd0;
        duplicate_ack_count_o <= 32'd0;
        stale_ack_count_o <= 32'd0;
        out_of_window_ack_count_o <= 32'd0;
        migration_count_o <= 32'd0;
        outstanding_high_watermark_o <= outstanding_count_o;
        retry_exhausted_sticky_o <= 1'b0;
      end
      if (session_reset_i || abort_all_i) begin
        for (entry = 0; entry < WINDOW_SIZE; entry = entry + 1) begin
          entry_valid[entry] <= 1'b0;
          entry_state[entry] <= 4'd0;
          entry_timer[entry] <= '0;
        end
        tx_next_sequence_o <= 16'd0;
        tx_ack_base_o <= 16'd0;
        outstanding_count_o <= '0;
        retry_burst_count <= '0;
      end else begin
        if (ack_valid_i) begin
          if (ack_session_epoch_i != session_epoch_i) begin
            stale_ack_count_o <= stale_ack_count_o + 1'b1;
          end else if (ack_malformed || !ack_window_valid) begin
            out_of_window_ack_count_o <= out_of_window_ack_count_o + 1'b1;
          end else begin
            for (entry = 0; entry < WINDOW_SIZE; entry = entry + 1) begin
              if (ack_match[entry]) begin
                entry_valid[entry] <= 1'b0;
                entry_state[entry] <= 4'd9;
                entry_timer[entry] <= '0;
                occupancy_delta = occupancy_delta - 1;
                acked_count = acked_count + 1;
              end
            end
            if (acked_count == 0) duplicate_ack_count_o <= duplicate_ack_count_o + 1'b1;
            else begin
              completion_pulse_o <= 1'b1;
              completion_batch_count_o <= acked_count;
            end
            candidate_base = tx_ack_base_o;
            base_found = 1'b0;
            for (entry = 0; entry < WINDOW_SIZE; entry = entry + 1) begin
              logic [15:0] scan_sequence;
              logic [INDEX_WIDTH-1:0] scan_index;
              scan_sequence = tx_ack_base_o + entry;
              scan_index = scan_sequence[INDEX_WIDTH-1:0];
              if (!base_found && entry_valid[scan_index] && !ack_match[scan_index] &&
                  seq_in_window(scan_sequence,tx_ack_base_o,WINDOW_SIZE)) begin
                candidate_base = scan_sequence;
                base_found = 1'b1;
              end
            end
            if (!base_found) candidate_base = tx_next_sequence_o;
            tx_ack_base_o <= candidate_base;
          end
        end
        for (entry = 0; entry < WINDOW_SIZE; entry = entry + 1) begin
          if (entry_valid[entry] && !ack_match[entry] && entry_state[entry] == 4'd4) begin
            if (entry_timer[entry] >= RTO_CYCLES - 1) begin
              entry_timer[entry] <= '0;
              timeout_count_o <= timeout_count_o + 1'b1;
              if (entry_retries[entry] >= MAX_RETRY) begin
                entry_valid[entry] <= 1'b0;
                entry_state[entry] <= 4'd8;
                retry_exhausted_count_o <= retry_exhausted_count_o + 1'b1;
                retry_exhausted_sticky_o <= 1'b1;
                occupancy_delta = occupancy_delta - 1;
              end else begin
                entry_retries[entry] <= entry_retries[entry] + 1'b1;
                entry_state[entry] <= 4'd6;
                retry_count_o <= retry_count_o + 1'b1;
              end
            end else begin
              entry_timer[entry] <= entry_timer[entry] + 1'b1;
            end
          end
        end
        if (attempt_valid_o && attempt_ready_i) begin
          if (attempt_is_retry_o && entry_have_lane[attempt_entry_o] &&
              entry_last_lane[attempt_entry_o] != selected_lane_i)
            migration_count_o <= migration_count_o + 1'b1;
          entry_last_lane[attempt_entry_o] <= selected_lane_i;
          entry_have_lane[attempt_entry_o] <= 1'b1;
          entry_path_epoch[attempt_entry_o] <= selected_path_epoch_i;
          entry_attempts[attempt_entry_o] <= entry_attempts[attempt_entry_o] + 1'b1;
          entry_timer[attempt_entry_o] <= '0;
          entry_state[attempt_entry_o] <= 4'd4;
          attempt_count_o <= attempt_count_o + 1'b1;
          if (attempt_is_retry_o) begin
            if (retry_burst_count < RETRY_PRIORITY_BURST_MAX)
              retry_burst_count <= retry_burst_count + 1'b1;
          end else begin
            retry_burst_count <= '0;
          end
        end
        if (allocate_valid_i && allocate_ready_o) begin
          allocation_index = tx_next_sequence_o[INDEX_WIDTH-1:0];
          entry_valid[allocation_index] <= 1'b1;
          entry_state[allocation_index] <= 4'd2;
          entry_priority[allocation_index] <= allocate_priority_i;
          entry_last_lane[allocation_index] <= 3'd0;
          entry_have_lane[allocation_index] <= 1'b0;
          entry_path_epoch[allocation_index] <= 16'd0;
          entry_attempts[allocation_index] <= 8'd0;
          entry_retries[allocation_index] <= 8'd0;
          entry_timer[allocation_index] <= '0;
          allocated_sequence_o <= tx_next_sequence_o;
          allocated_entry_o <= allocation_index;
          allocate_pulse_o <= 1'b1;
          tx_next_sequence_o <= tx_next_sequence_o + 1'b1;
          occupancy_delta = occupancy_delta + 1;
        end
        if (occupancy_delta != 0) begin
          outstanding_count_o <= outstanding_count_o + occupancy_delta;
          if (outstanding_count_o + occupancy_delta > outstanding_high_watermark_o)
            outstanding_high_watermark_o <= outstanding_count_o + occupancy_delta;
        end
      end
    end
  end
endmodule
