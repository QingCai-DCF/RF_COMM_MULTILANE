`timescale 1ns/1ps
// P8E bounded-latency selective-repeat transmit window.
//
// The P8D implementation evaluated every window entry in one cycle for ACK,
// retry selection, base advance, and timeout maintenance.  This version keeps
// the same global sequence/window semantics while using three independent
// one-entry-per-cycle engines.  Allocation remains live while ACK reclaim is
// running; an ACK snapshot never applies to entries allocated after capture.
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
  localparam int PAYLOAD_META_WIDTH = PAYLOAD_REF_WIDTH + 16 + DESCRIPTOR_WIDTH;
  localparam int RETRY_BURST_WIDTH = $clog2(RETRY_PRIORITY_BURST_MAX + 1);
  localparam logic [3:0] ENTRY_NEW = 4'd2;
  localparam logic [3:0] ENTRY_SENT = 4'd4;
  localparam logic [3:0] ENTRY_RETRY = 4'd6;
  localparam logic [3:0] ENTRY_EXHAUSTED = 4'd8;
  localparam logic [3:0] ENTRY_ACKED = 4'd9;

  logic [WINDOW_SIZE-1:0] entry_valid;
  logic [3:0] entry_state [0:WINDOW_SIZE-1];
  logic [15:0] entry_sequence [0:WINDOW_SIZE-1];
  (* ram_style="distributed" *) logic [PAYLOAD_META_WIDTH-1:0]
    entry_payload_memory [0:WINDOW_SIZE-1];
  logic [2:0] entry_priority [0:WINDOW_SIZE-1];
  logic [2:0] entry_last_lane [0:WINDOW_SIZE-1];
  logic entry_have_lane [0:WINDOW_SIZE-1];
  logic [15:0] entry_path_epoch [0:WINDOW_SIZE-1];
  logic [7:0] entry_attempts [0:WINDOW_SIZE-1];
  logic [7:0] entry_retries [0:WINDOW_SIZE-1];
  logic [31:0] entry_expiry [0:WINDOW_SIZE-1];

  logic [31:0] time_counter;
  logic [INDEX_WIDTH-1:0] timer_scan_index;
  logic [31:0] timer_age;
  logic timer_due;
  logic timer_exhausts;

  logic allocation_fire;
  logic attempt_fire;
  logic attempt_candidate_live;
  logic [PAYLOAD_META_WIDTH-1:0] attempt_payload_metadata;
  logic [RETRY_BURST_WIDTH-1:0] retry_burst_count;

  // Reset-free metadata RAM is written only from a synchronously reset command
  // register.  Stale contents are unreachable while entry_valid is low.
  logic payload_write_pending;
  logic [INDEX_WIDTH-1:0] payload_write_index;
  logic [PAYLOAD_META_WIDTH-1:0] payload_write_data;

  // One-pass candidate scan tracks the best preferred and fallback class in
  // parallel, so selection is bounded by exactly WINDOW_SIZE scan cycles.
  logic attempt_scan_active;
  logic [INDEX_WIDTH:0] attempt_scan_count;
  logic [15:0] attempt_scan_sequence;
  logic attempt_scan_prefer_retry;
  logic attempt_scan_pref_found, attempt_scan_alt_found;
  logic [2:0] attempt_scan_pref_priority, attempt_scan_alt_priority;
  logic [INDEX_WIDTH-1:0] attempt_scan_pref_entry, attempt_scan_alt_entry;
  logic [15:0] attempt_scan_pref_sequence, attempt_scan_alt_sequence;
  logic attempt_scan_pref_retry, attempt_scan_alt_retry;
  logic attempt_hold_valid;
  logic [INDEX_WIDTH-1:0] attempt_hold_entry;
  logic [15:0] attempt_hold_sequence;
  logic [2:0] attempt_hold_priority;
  logic attempt_hold_retry;
  logic [INDEX_WIDTH-1:0] scan_entry_index;
  logic scan_entry_pref, scan_entry_alt;
  logic scan_pref_choose_current, scan_alt_choose_current;

  // ACK input has no ready signal.  The newest cumulative/SACK snapshot is
  // retained while the prior snapshot is processed; loss of an intermediate
  // cumulative ACK cannot violate correctness and the newest state is safest.
  logic ack_queued_valid;
  logic [31:0] ack_queued_session;
  logic [15:0] ack_queued_base;
  logic [SACK_BITS-1:0] ack_queued_bitmap;
  logic [$clog2(SACK_BITS):0] ack_queued_width;

  typedef enum logic [1:0] {ACK_IDLE, ACK_VALIDATE, ACK_RECLAIM, ACK_ADVANCE} ack_state_t;
  ack_state_t ack_state;
  logic [31:0] ack_session_capture;
  logic [15:0] ack_base_capture;
  logic [SACK_BITS-1:0] ack_bitmap_capture;
  logic [$clog2(SACK_BITS):0] ack_width_capture;
  logic [15:0] ack_window_start;
  logic [15:0] ack_active_span_snapshot;
  logic [$clog2(SACK_BITS):0] ack_validate_index;
  logic ack_malformed_seen;
  logic [INDEX_WIDTH:0] ack_scan_count;
  logic [31:0] ack_reclaimed_count;
  logic [INDEX_WIDTH:0] ack_advance_count;
  logic [INDEX_WIDTH-1:0] ack_scan_index;
  logic [15:0] ack_scan_sequence_value;
  logic [15:0] ack_scan_distance;
  logic [15:0] ack_scan_snapshot_distance;
  logic ack_scan_in_snapshot;
  logic ack_scan_sack_bit;
  logic ack_scan_match;
  logic ack_reclaim_fire;

  initial begin
    if (WINDOW_SIZE < 32 || (WINDOW_SIZE & (WINDOW_SIZE-1)) != 0)
      $error("WINDOW_SIZE must be power-of-two and at least 32");
    if (SACK_BITS < 32 || SACK_BITS > WINDOW_SIZE)
      $error("SACK_BITS must be 32..WINDOW_SIZE");
    if (RTO_CYCLES < 1 || RTO_CYCLES >= 32'h8000_0000)
      $error("RTO_CYCLES must fit the wrap-safe 31-bit timer interval");
  end

  assign allocation_fire = allocate_valid_i && allocate_ready_o;
  assign allocate_ready_o = (outstanding_count_o < WINDOW_SIZE) &&
                            !entry_valid[tx_next_sequence_o[INDEX_WIDTH-1:0]];

  assign scan_entry_index = attempt_scan_sequence[INDEX_WIDTH-1:0];
  assign scan_entry_pref = entry_valid[scan_entry_index] &&
      ((attempt_scan_prefer_retry && entry_state[scan_entry_index] == ENTRY_RETRY) ||
       (!attempt_scan_prefer_retry && entry_state[scan_entry_index] == ENTRY_NEW));
  assign scan_entry_alt = entry_valid[scan_entry_index] &&
      ((attempt_scan_prefer_retry && entry_state[scan_entry_index] == ENTRY_NEW) ||
       (!attempt_scan_prefer_retry && entry_state[scan_entry_index] == ENTRY_RETRY));
  assign scan_pref_choose_current = scan_entry_pref &&
      (!attempt_scan_pref_found || entry_priority[scan_entry_index] > attempt_scan_pref_priority);
  assign scan_alt_choose_current = scan_entry_alt &&
      (!attempt_scan_alt_found || entry_priority[scan_entry_index] > attempt_scan_alt_priority);

  assign attempt_candidate_live = attempt_hold_valid && entry_valid[attempt_hold_entry] &&
      entry_sequence[attempt_hold_entry] == attempt_hold_sequence &&
      ((attempt_hold_retry && entry_state[attempt_hold_entry] == ENTRY_RETRY) ||
       (!attempt_hold_retry && entry_state[attempt_hold_entry] == ENTRY_NEW));
  assign attempt_valid_o = attempt_candidate_live;
  assign attempt_fire = attempt_valid_o && attempt_ready_i;
  assign attempt_entry_o = attempt_hold_entry;
  assign attempt_sequence_o = attempt_hold_sequence;
  assign attempt_priority_o = attempt_hold_priority;
  assign attempt_is_retry_o = attempt_hold_retry;
  assign attempt_last_lane_o = entry_last_lane[attempt_hold_entry];
  assign attempt_payload_metadata = entry_payload_memory[attempt_hold_entry];
  assign attempt_payload_ref_o = attempt_payload_metadata[PAYLOAD_REF_WIDTH-1:0];
  assign attempt_payload_length_o = attempt_payload_metadata[PAYLOAD_REF_WIDTH +: 16];
  assign attempt_descriptor_o =
      attempt_payload_metadata[PAYLOAD_REF_WIDTH+16 +: DESCRIPTOR_WIDTH];

  assign timer_age = time_counter - entry_expiry[timer_scan_index];
  assign timer_due = entry_valid[timer_scan_index] &&
                     entry_state[timer_scan_index] == ENTRY_SENT && !timer_age[31];
  assign timer_exhausts = timer_due && entry_retries[timer_scan_index] >= MAX_RETRY;

  assign ack_scan_index = ack_scan_count[INDEX_WIDTH-1:0];
  assign ack_scan_sequence_value = entry_sequence[ack_scan_index];
  assign ack_scan_distance = seq_distance(ack_scan_sequence_value, ack_base_capture);
  assign ack_scan_snapshot_distance = seq_distance(ack_scan_sequence_value, ack_window_start);
  assign ack_scan_in_snapshot = (ack_scan_snapshot_distance < ack_active_span_snapshot);
  always_comb begin
    ack_scan_sack_bit = 1'b0;
    if (ack_scan_distance < SACK_BITS && ack_scan_distance < ack_width_capture)
      ack_scan_sack_bit = ack_bitmap_capture[ack_scan_distance[$clog2(SACK_BITS)-1:0]];
  end
  assign ack_scan_match = ack_state == ACK_RECLAIM && entry_valid[ack_scan_index] &&
      ack_scan_in_snapshot &&
      (seq_before(ack_scan_sequence_value, ack_base_capture) || ack_scan_sack_bit);
  assign ack_reclaim_fire = ack_scan_match;

  always_ff @(posedge clk) begin : payload_metadata_memory
    if (!rst_n || session_reset_i || abort_all_i) begin
      payload_write_pending <= 1'b0;
      payload_write_index <= '0;
      payload_write_data <= '0;
    end else begin
      if (payload_write_pending)
        entry_payload_memory[payload_write_index] <= payload_write_data;
      payload_write_pending <= allocation_fire;
      if (allocation_fire) begin
        payload_write_index <= tx_next_sequence_o[INDEX_WIDTH-1:0];
        payload_write_data <=
            {allocate_descriptor_i, allocate_payload_length_i, allocate_payload_ref_i};
      end
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin : tx_state
    integer signed occupancy_delta;
    logic [15:0] captured_distance;
    logic [15:0] captured_span;
    logic malformed_now;
    logic [31:0] reclaimed_total;
    logic [INDEX_WIDTH-1:0] allocation_index;
    if (!rst_n) begin
      entry_valid <= '0;
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
      time_counter <= 32'd0;
      timer_scan_index <= '0;
      attempt_scan_active <= 1'b0;
      attempt_scan_count <= '0;
      attempt_scan_sequence <= 16'd0;
      attempt_scan_prefer_retry <= 1'b0;
      attempt_scan_pref_found <= 1'b0;
      attempt_scan_alt_found <= 1'b0;
      attempt_scan_pref_priority <= 3'd0;
      attempt_scan_alt_priority <= 3'd0;
      attempt_scan_pref_entry <= '0;
      attempt_scan_alt_entry <= '0;
      attempt_scan_pref_sequence <= 16'd0;
      attempt_scan_alt_sequence <= 16'd0;
      attempt_scan_pref_retry <= 1'b0;
      attempt_scan_alt_retry <= 1'b0;
      attempt_hold_valid <= 1'b0;
      attempt_hold_entry <= '0;
      attempt_hold_sequence <= 16'd0;
      attempt_hold_priority <= 3'd0;
      attempt_hold_retry <= 1'b0;
      ack_queued_valid <= 1'b0;
      ack_queued_session <= 32'd0;
      ack_queued_base <= 16'd0;
      ack_queued_bitmap <= '0;
      ack_queued_width <= '0;
      ack_state <= ACK_IDLE;
      ack_session_capture <= 32'd0;
      ack_base_capture <= 16'd0;
      ack_bitmap_capture <= '0;
      ack_width_capture <= '0;
      ack_window_start <= 16'd0;
      ack_active_span_snapshot <= 16'd0;
      ack_validate_index <= '0;
      ack_malformed_seen <= 1'b0;
      ack_scan_count <= '0;
      ack_reclaimed_count <= 32'd0;
      ack_advance_count <= '0;
    end else begin
      allocate_pulse_o <= 1'b0;
      completion_pulse_o <= 1'b0;
      completion_batch_count_o <= 32'd0;
      occupancy_delta = 0;
      time_counter <= time_counter + 1'b1;
      timer_scan_index <= timer_scan_index + 1'b1;

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
        entry_valid <= '0;
        tx_next_sequence_o <= 16'd0;
        tx_ack_base_o <= 16'd0;
        outstanding_count_o <= '0;
        retry_burst_count <= '0;
        time_counter <= 32'd0;
        timer_scan_index <= '0;
        attempt_scan_active <= 1'b0;
        attempt_hold_valid <= 1'b0;
        ack_queued_valid <= 1'b0;
        ack_state <= ACK_IDLE;
      end else begin
        // Candidate selection engine.
        if (attempt_hold_valid && !attempt_candidate_live)
          attempt_hold_valid <= 1'b0;
        if (!attempt_hold_valid && !attempt_scan_active && outstanding_count_o != 0) begin
          attempt_scan_active <= 1'b1;
          attempt_scan_count <= '0;
          attempt_scan_sequence <= tx_ack_base_o;
          attempt_scan_prefer_retry <= retry_burst_count < RETRY_PRIORITY_BURST_MAX;
          attempt_scan_pref_found <= 1'b0;
          attempt_scan_alt_found <= 1'b0;
          attempt_scan_pref_priority <= 3'd0;
          attempt_scan_alt_priority <= 3'd0;
        end else if (attempt_scan_active) begin
          if (scan_pref_choose_current) begin
            attempt_scan_pref_found <= 1'b1;
            attempt_scan_pref_priority <= entry_priority[scan_entry_index];
            attempt_scan_pref_entry <= scan_entry_index;
            attempt_scan_pref_sequence <= attempt_scan_sequence;
            attempt_scan_pref_retry <= entry_state[scan_entry_index] == ENTRY_RETRY;
          end
          if (scan_alt_choose_current) begin
            attempt_scan_alt_found <= 1'b1;
            attempt_scan_alt_priority <= entry_priority[scan_entry_index];
            attempt_scan_alt_entry <= scan_entry_index;
            attempt_scan_alt_sequence <= attempt_scan_sequence;
            attempt_scan_alt_retry <= entry_state[scan_entry_index] == ENTRY_RETRY;
          end
          if (attempt_scan_count == WINDOW_SIZE-1) begin
            attempt_scan_active <= 1'b0;
            if (attempt_scan_pref_found || scan_entry_pref) begin
              attempt_hold_valid <= 1'b1;
              if (scan_pref_choose_current) begin
                attempt_hold_entry <= scan_entry_index;
                attempt_hold_sequence <= attempt_scan_sequence;
                attempt_hold_priority <= entry_priority[scan_entry_index];
                attempt_hold_retry <= entry_state[scan_entry_index] == ENTRY_RETRY;
              end else begin
                attempt_hold_entry <= attempt_scan_pref_entry;
                attempt_hold_sequence <= attempt_scan_pref_sequence;
                attempt_hold_priority <= attempt_scan_pref_priority;
                attempt_hold_retry <= attempt_scan_pref_retry;
              end
            end else if (attempt_scan_alt_found || scan_entry_alt) begin
              attempt_hold_valid <= 1'b1;
              if (scan_alt_choose_current) begin
                attempt_hold_entry <= scan_entry_index;
                attempt_hold_sequence <= attempt_scan_sequence;
                attempt_hold_priority <= entry_priority[scan_entry_index];
                attempt_hold_retry <= entry_state[scan_entry_index] == ENTRY_RETRY;
              end else begin
                attempt_hold_entry <= attempt_scan_alt_entry;
                attempt_hold_sequence <= attempt_scan_alt_sequence;
                attempt_hold_priority <= attempt_scan_alt_priority;
                attempt_hold_retry <= attempt_scan_alt_retry;
              end
            end
          end else begin
            attempt_scan_count <= attempt_scan_count + 1'b1;
            attempt_scan_sequence <= attempt_scan_sequence + 1'b1;
          end
        end

        if (attempt_fire) begin
          attempt_hold_valid <= 1'b0;
          if (attempt_hold_retry && entry_have_lane[attempt_hold_entry] &&
              entry_last_lane[attempt_hold_entry] != selected_lane_i)
            migration_count_o <= migration_count_o + 1'b1;
          entry_last_lane[attempt_hold_entry] <= selected_lane_i;
          entry_have_lane[attempt_hold_entry] <= 1'b1;
          entry_path_epoch[attempt_hold_entry] <= selected_path_epoch_i;
          entry_attempts[attempt_hold_entry] <= entry_attempts[attempt_hold_entry] + 1'b1;
          entry_expiry[attempt_hold_entry] <= time_counter + RTO_CYCLES;
          entry_state[attempt_hold_entry] <= ENTRY_SENT;
          attempt_count_o <= attempt_count_o + 1'b1;
          if (attempt_hold_retry) begin
            if (retry_burst_count < RETRY_PRIORITY_BURST_MAX)
              retry_burst_count <= retry_burst_count + 1'b1;
          end else begin
            retry_burst_count <= '0;
          end
        end

        // Shared timeout wheel: exactly one metadata entry is inspected per cycle.
        if (timer_due && !(ack_reclaim_fire && ack_scan_index == timer_scan_index)) begin
          timeout_count_o <= timeout_count_o + 1'b1;
          if (timer_exhausts) begin
            entry_valid[timer_scan_index] <= 1'b0;
            entry_state[timer_scan_index] <= ENTRY_EXHAUSTED;
            retry_exhausted_count_o <= retry_exhausted_count_o + 1'b1;
            retry_exhausted_sticky_o <= 1'b1;
            occupancy_delta = occupancy_delta - 1;
          end else begin
            entry_retries[timer_scan_index] <= entry_retries[timer_scan_index] + 1'b1;
            entry_state[timer_scan_index] <= ENTRY_RETRY;
            retry_count_o <= retry_count_o + 1'b1;
          end
        end

        // ACK validate/reclaim/base-advance pipeline.
        case (ack_state)
          ACK_IDLE: begin
            if (ack_queued_valid) begin
              ack_session_capture <= ack_queued_session;
              ack_base_capture <= ack_queued_base;
              ack_bitmap_capture <= ack_queued_bitmap;
              ack_width_capture <= ack_queued_width;
              ack_window_start <= tx_ack_base_o;
              ack_active_span_snapshot <= seq_distance(tx_next_sequence_o, tx_ack_base_o);
              ack_validate_index <= '0;
              ack_malformed_seen <= 1'b0;
              ack_queued_valid <= 1'b0;
              ack_state <= ACK_VALIDATE;
            end else if (tx_ack_base_o != tx_next_sequence_o &&
                         !(entry_valid[tx_ack_base_o[INDEX_WIDTH-1:0]] &&
                           entry_sequence[tx_ack_base_o[INDEX_WIDTH-1:0]] == tx_ack_base_o)) begin
              // Timeout/abort holes use the same bounded one-step base advance.
              tx_ack_base_o <= tx_ack_base_o + 1'b1;
            end
          end
          ACK_VALIDATE: begin
            malformed_now = (ack_validate_index >= ack_width_capture) &&
                            ack_bitmap_capture[ack_validate_index[$clog2(SACK_BITS)-1:0]];
            if (ack_session_capture != session_epoch_i) begin
              stale_ack_count_o <= stale_ack_count_o + 1'b1;
              ack_state <= ACK_IDLE;
            end else if (ack_width_capture < 32 || ack_width_capture > SACK_BITS) begin
              out_of_window_ack_count_o <= out_of_window_ack_count_o + 1'b1;
              ack_state <= ACK_IDLE;
            end else if (ack_validate_index == SACK_BITS-1) begin
              captured_distance = seq_distance(ack_base_capture, ack_window_start);
              captured_span = ack_active_span_snapshot;
              if (ack_malformed_seen || malformed_now ||
                  captured_distance > captured_span || captured_distance > WINDOW_SIZE) begin
                out_of_window_ack_count_o <= out_of_window_ack_count_o + 1'b1;
                ack_state <= ACK_IDLE;
              end else begin
                ack_scan_count <= '0;
                ack_reclaimed_count <= 32'd0;
                ack_state <= ACK_RECLAIM;
              end
            end else begin
              ack_malformed_seen <= ack_malformed_seen || malformed_now;
              ack_validate_index <= ack_validate_index + 1'b1;
            end
          end
          ACK_RECLAIM: begin
            if (ack_reclaim_fire) begin
              entry_valid[ack_scan_index] <= 1'b0;
              entry_state[ack_scan_index] <= ENTRY_ACKED;
              ack_reclaimed_count <= ack_reclaimed_count + 1'b1;
              occupancy_delta = occupancy_delta - 1;
            end
            if (ack_scan_count == WINDOW_SIZE-1) begin
              reclaimed_total = ack_reclaimed_count + (ack_reclaim_fire ? 1 : 0);
              if (reclaimed_total == 0) begin
                duplicate_ack_count_o <= duplicate_ack_count_o + 1'b1;
              end else begin
                completion_pulse_o <= 1'b1;
                completion_batch_count_o <= reclaimed_total;
              end
              ack_advance_count <= '0;
              ack_state <= ACK_ADVANCE;
            end else begin
              ack_scan_count <= ack_scan_count + 1'b1;
            end
          end
          ACK_ADVANCE: begin
            if (tx_ack_base_o == tx_next_sequence_o ||
                (entry_valid[tx_ack_base_o[INDEX_WIDTH-1:0]] &&
                 entry_sequence[tx_ack_base_o[INDEX_WIDTH-1:0]] == tx_ack_base_o) ||
                ack_advance_count == WINDOW_SIZE) begin
              ack_state <= ACK_IDLE;
            end else begin
              tx_ack_base_o <= tx_ack_base_o + 1'b1;
              ack_advance_count <= ack_advance_count + 1'b1;
            end
          end
          default: ack_state <= ACK_IDLE;
        endcase

        if (allocation_fire) begin
          allocation_index = tx_next_sequence_o[INDEX_WIDTH-1:0];
          entry_valid[allocation_index] <= 1'b1;
          entry_state[allocation_index] <= ENTRY_NEW;
          entry_sequence[allocation_index] <= tx_next_sequence_o;
          entry_priority[allocation_index] <= allocate_priority_i;
          entry_last_lane[allocation_index] <= 3'd0;
          entry_have_lane[allocation_index] <= 1'b0;
          entry_path_epoch[allocation_index] <= 16'd0;
          entry_attempts[allocation_index] <= 8'd0;
          entry_retries[allocation_index] <= 8'd0;
          entry_expiry[allocation_index] <= 32'd0;
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

        // Capture after queue consumption so a same-cycle newer ACK remains queued.
        if (ack_valid_i) begin
          ack_queued_valid <= 1'b1;
          ack_queued_session <= ack_session_epoch_i;
          ack_queued_base <= ack_base_i;
          ack_queued_bitmap <= ack_bitmap_i;
          ack_queued_width <= ack_width_i;
        end
      end
    end
  end
endmodule
