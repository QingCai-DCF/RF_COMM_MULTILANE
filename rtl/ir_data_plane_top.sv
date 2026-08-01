`timescale 1ns/1ps
// Portable P8D ARQ/scheduler integration.  This block owns one global sequence
// space per direction.  Logical lanes are attempt resources, never independent
// ARQ windows.  All physical-attempt admission is rechecked against live P8B
// mapping and P8C safety inputs at the final handshake boundary.
module ir_data_plane_top #(
  parameter int LANE_COUNT = 8,
  parameter int WINDOW_SIZE = 64,
  parameter int SACK_BITS = 64,
  parameter int MAX_RETRY = 7,
  parameter int RTO_CYCLES = 64000,
  parameter int ACK_FRAME_THRESHOLD = 8,
  parameter int ACK_MAX_DELAY_CYCLES = 32000,
  parameter int PAYLOAD_REF_WIDTH = 16,
  parameter int DESCRIPTOR_WIDTH = 16
) (
  input  logic                           clk,
  input  logic                           rst_n,
  input  logic                           clear_counters_i,
  input  logic                           session_reset_i,
  input  logic [15:0]                    initial_sequence_i,
  input  logic                           abort_all_i,
  input  logic [31:0]                    session_epoch_i,
  input  logic [15:0]                    path_epoch_i,
  input  logic                           path_epoch_valid_i,

  input  logic [LANE_COUNT*8-1:0]        lane_weights_i,
  input  logic [LANE_COUNT-1:0]          active_lane_mask_i,
  input  logic [LANE_COUNT-1:0]          lane_ready_i,
  input  logic [LANE_COUNT-1:0]          lane_health_i,
  input  logic [LANE_COUNT-1:0]          mapping_valid_i,
  input  logic [LANE_COUNT-1:0]          frame_admission_i,
  input  logic [LANE_COUNT-1:0]          lane_tx_permit_i,
  input  logic [LANE_COUNT-1:0]          duty_headroom_i,
  input  logic [LANE_COUNT-1:0]          fault_free_i,
  input  logic                           global_permit_effective_i,
  input  logic                           endpoint_armed_i,
  input  logic                           tx_kill_active_i,
  input  logic [15:0]                    peer_receiver_credit_i,

  input  logic                           tx_allocate_valid_i,
  output logic                           tx_allocate_ready_o,
  input  logic [PAYLOAD_REF_WIDTH-1:0]   tx_allocate_payload_ref_i,
  input  logic [15:0]                    tx_allocate_payload_length_i,
  input  logic [DESCRIPTOR_WIDTH-1:0]    tx_allocate_descriptor_i,
  input  logic [2:0]                     tx_allocate_priority_i,
  output logic                           tx_allocate_pulse_o,
  output logic [15:0]                    tx_allocated_sequence_o,

  output logic                           physical_attempt_valid_o,
  input  logic                           physical_attempt_ready_i,
  output logic [$clog2(WINDOW_SIZE)-1:0] physical_attempt_entry_o,
  output logic [15:0]                    physical_attempt_sequence_o,
  output logic [PAYLOAD_REF_WIDTH-1:0]   physical_attempt_payload_ref_o,
  output logic [15:0]                    physical_attempt_payload_length_o,
  output logic [DESCRIPTOR_WIDTH-1:0]    physical_attempt_descriptor_o,
  output logic [$clog2(LANE_COUNT)-1:0]  physical_attempt_lane_o,
  output logic [15:0]                    physical_attempt_path_epoch_o,
  output logic                           physical_attempt_is_retry_o,

  input  logic                           peer_ack_valid_i,
  input  logic [31:0]                    peer_ack_session_epoch_i,
  input  logic [15:0]                    peer_ack_base_i,
  input  logic [SACK_BITS-1:0]           peer_ack_bitmap_i,
  input  logic [$clog2(SACK_BITS):0]     peer_ack_width_i,

  input  logic                           rx_frame_valid_i,
  output logic                           rx_frame_ready_o,
  input  logic                           rx_l1_valid_i,
  input  logic [31:0]                    rx_session_epoch_i,
  input  logic [15:0]                    rx_sequence_i,
  input  logic [15:0]                    rx_path_epoch_i,
  input  logic [PAYLOAD_REF_WIDTH-1:0]   rx_payload_ref_i,
  input  logic [15:0]                    rx_payload_length_i,
  output logic                           rx_delivery_valid_o,
  input  logic                           rx_delivery_ready_i,
  output logic [15:0]                    rx_delivery_sequence_o,
  output logic [PAYLOAD_REF_WIDTH-1:0]   rx_delivery_payload_ref_o,
  output logic [15:0]                    rx_delivery_payload_length_o,
  output logic                           rx_accept_pulse_o,

  input  logic                           ack_control_event_i,
  input  logic                           ack_direction_boundary_i,
  input  logic                           ack_explicit_request_i,
  output logic                           local_ack_valid_o,
  input  logic                           local_ack_ready_i,
  output logic [31:0]                    local_ack_session_epoch_o,
  output logic [15:0]                    local_ack_base_o,
  output logic [SACK_BITS-1:0]           local_ack_bitmap_o,
  output logic [$clog2(SACK_BITS):0]     local_ack_width_o,
  output logic [15:0]                    local_ack_receiver_credit_o,

  output logic [15:0]                    tx_next_sequence_o,
  output logic [15:0]                    tx_ack_base_o,
  output logic [$clog2(WINDOW_SIZE+1)-1:0] tx_outstanding_count_o,
  output logic [$clog2(WINDOW_SIZE+1)-1:0] tx_outstanding_high_watermark_o,
  output logic [15:0]                    rx_base_sequence_o,
  output logic [SACK_BITS-1:0]           rx_sack_bitmap_o,
  output logic [$clog2(WINDOW_SIZE+1)-1:0] rx_receiver_credit_o,
  output logic [31:0]                    tx_attempt_count_o,
  output logic [31:0]                    tx_retry_count_o,
  output logic [31:0]                    tx_retry_exhausted_count_o,
  output logic [31:0]                    tx_timeout_count_o,
  output logic [31:0]                    tx_duplicate_ack_count_o,
  output logic [31:0]                    tx_stale_ack_count_o,
  output logic [31:0]                    tx_out_of_window_ack_count_o,
  output logic [31:0]                    tx_migration_count_o,
  output logic [31:0]                    rx_duplicate_count_o,
  output logic [31:0]                    rx_out_of_order_count_o,
  output logic [31:0]                    rx_old_count_o,
  output logic [31:0]                    rx_future_count_o,
  output logic [31:0]                    rx_stale_session_count_o,
  output logic [31:0]                    rx_stale_path_count_o,
  output logic [31:0]                    rx_gap_count_o,
  output logic [31:0]                    rx_delivery_count_o,
  output logic [31:0]                    rx_protocol_error_count_o,
  output logic [31:0]                    ack_aggregation_count_o,
  output logic [31:0]                    ack_timer_expiry_count_o,
  output logic [31:0]                    ack_frames_sent_o,
  output logic [3:0]                     scheduler_last_defer_reason_o,
  output logic [LANE_COUNT*32-1:0]       scheduler_frames_flat_o,
  output logic [LANE_COUNT*32-1:0]       scheduler_bytes_flat_o,
  output logic [LANE_COUNT*32-1:0]       scheduler_retries_flat_o,
  output logic [LANE_COUNT*32-1:0]       scheduler_migrations_flat_o,
  output logic [31:0]                    scheduler_maximum_starvation_o
);
  localparam int ENTRY_WIDTH = $clog2(WINDOW_SIZE);
  localparam int LANE_WIDTH = $clog2(LANE_COUNT);
  localparam logic [$clog2(SACK_BITS):0] CONFIGURED_SACK_WIDTH = SACK_BITS;

  logic tx_attempt_valid;
  logic tx_attempt_ready;
  logic [ENTRY_WIDTH-1:0] tx_attempt_entry;
  logic [15:0] tx_attempt_sequence;
  logic [PAYLOAD_REF_WIDTH-1:0] tx_attempt_payload_ref;
  logic [15:0] tx_attempt_payload_length;
  logic [DESCRIPTOR_WIDTH-1:0] tx_attempt_descriptor;
  logic [2:0] tx_attempt_priority;
  logic tx_attempt_is_retry;
  logic [2:0] tx_attempt_last_lane;
  logic [ENTRY_WIDTH-1:0] allocated_entry_unused;
  logic [31:0] completion_batch_unused;
  logic completion_pulse_unused;
  logic retry_exhausted_sticky_unused;

  logic request_inflight;
  logic [ENTRY_WIDTH-1:0] pending_entry;
  logic [15:0] pending_sequence;
  logic [PAYLOAD_REF_WIDTH-1:0] pending_payload_ref;
  logic [15:0] pending_payload_length;
  logic [DESCRIPTOR_WIDTH-1:0] pending_descriptor;
  logic pending_retry;
  logic [2:0] pending_last_lane;

  logic scheduler_request_valid;
  logic scheduler_request_ready;
  logic scheduler_decision_valid;
  logic scheduler_decision_ready;
  logic scheduler_decision_admit;
  logic [ENTRY_WIDTH-1:0] scheduler_decision_entry;
  logic [LANE_WIDTH-1:0] scheduler_decision_lane;
  logic [15:0] scheduler_decision_path_epoch;
  logic [3:0] scheduler_decision_defer_reason;
  logic [3:0] scheduler_migration_reason_unused;
  logic [LANE_COUNT-1:0] scheduler_eligible_mask;
  logic live_decision_path_safe;
  logic live_decision_transmit_ready;
  logic [2:0] selected_lane_padded;

  logic rx_accept_pulse;
  assign rx_accept_pulse_o = rx_accept_pulse;
  initial begin
    if (LANE_COUNT < 2 || LANE_COUNT > 8 || (LANE_COUNT & (LANE_COUNT-1)) != 0)
      $error("LANE_COUNT must be 2, 4, or 8");
    if (WINDOW_SIZE < 32 || WINDOW_SIZE >= 32768)
      $error("WINDOW_SIZE must be at least 32 and below sequence half-space");
  end

  // Transient serializer/backpressure readiness is deliberately not part of
  // the weighted choice.  Once a safe lane is selected, hold that choice until
  // the physical boundary is ready.  Permanent health/mapping/permit/fault
  // changes still cancel the decision immediately and force a fresh choice.
  assign scheduler_eligible_mask = active_lane_mask_i & lane_health_i &
                                   mapping_valid_i & frame_admission_i &
                                   lane_tx_permit_i & duty_headroom_i &
                                   fault_free_i;
  assign live_decision_path_safe = global_permit_effective_i && endpoint_armed_i &&
                                   !tx_kill_active_i && path_epoch_valid_i &&
                                   (peer_receiver_credit_i != 0) &&
                                   scheduler_eligible_mask[scheduler_decision_lane];
  assign live_decision_transmit_ready = live_decision_path_safe &&
                                        lane_ready_i[scheduler_decision_lane];
  assign selected_lane_padded = {{(3-LANE_WIDTH){1'b0}}, scheduler_decision_lane};

  assign scheduler_request_valid = tx_attempt_valid && !request_inflight;
  assign physical_attempt_valid_o = request_inflight && scheduler_decision_valid &&
                                    scheduler_decision_admit &&
                                    live_decision_transmit_ready;
  assign scheduler_decision_ready = scheduler_decision_valid &&
      ((!scheduler_decision_admit) || (!live_decision_path_safe) ||
       (lane_ready_i[scheduler_decision_lane] && physical_attempt_ready_i));
  assign tx_attempt_ready = physical_attempt_valid_o && physical_attempt_ready_i;
  assign physical_attempt_entry_o = pending_entry;
  assign physical_attempt_sequence_o = pending_sequence;
  assign physical_attempt_payload_ref_o = pending_payload_ref;
  assign physical_attempt_payload_length_o = pending_payload_length;
  assign physical_attempt_descriptor_o = pending_descriptor;
  assign physical_attempt_lane_o = scheduler_decision_lane;
  assign physical_attempt_path_epoch_o = scheduler_decision_path_epoch;
  assign physical_attempt_is_retry_o = pending_retry;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      request_inflight <= 1'b0;
      pending_entry <= '0;
      pending_sequence <= 16'd0;
      pending_payload_ref <= '0;
      pending_payload_length <= 16'd0;
      pending_descriptor <= '0;
      pending_retry <= 1'b0;
      pending_last_lane <= 3'd0;
      scheduler_last_defer_reason_o <= 4'd0;
    end else begin
      if (session_reset_i || abort_all_i) begin
        request_inflight <= 1'b0;
        scheduler_last_defer_reason_o <= 4'd0;
      end else begin
        if (scheduler_request_valid && scheduler_request_ready) begin
          request_inflight <= 1'b1;
          pending_entry <= tx_attempt_entry;
          pending_sequence <= tx_attempt_sequence;
          pending_payload_ref <= tx_attempt_payload_ref;
          pending_payload_length <= tx_attempt_payload_length;
          pending_descriptor <= tx_attempt_descriptor;
          pending_retry <= tx_attempt_is_retry;
          pending_last_lane <= tx_attempt_last_lane;
        end
        if (scheduler_decision_valid && scheduler_decision_ready) begin
          request_inflight <= 1'b0;
          if (!scheduler_decision_admit)
            scheduler_last_defer_reason_o <= scheduler_decision_defer_reason;
          else if (!live_decision_path_safe)
            scheduler_last_defer_reason_o <= 4'd6;
          else
            scheduler_last_defer_reason_o <= 4'd0;
        end
      end
    end
  end

  ir_selective_repeat_tx #(
    .WINDOW_SIZE(WINDOW_SIZE), .SACK_BITS(SACK_BITS), .MAX_RETRY(MAX_RETRY),
    .RTO_CYCLES(RTO_CYCLES), .PAYLOAD_REF_WIDTH(PAYLOAD_REF_WIDTH),
    .DESCRIPTOR_WIDTH(DESCRIPTOR_WIDTH)
  ) u_tx_window (
    .clk, .rst_n, .clear_counters_i, .session_reset_i, .initial_sequence_i,
    .session_epoch_i,
    .abort_all_i, .allocate_valid_i(tx_allocate_valid_i),
    .allocate_ready_o(tx_allocate_ready_o),
    .allocate_payload_ref_i(tx_allocate_payload_ref_i),
    .allocate_payload_length_i(tx_allocate_payload_length_i),
    .allocate_descriptor_i(tx_allocate_descriptor_i),
    .allocate_priority_i(tx_allocate_priority_i),
    .allocate_pulse_o(tx_allocate_pulse_o),
    .allocated_sequence_o(tx_allocated_sequence_o),
    .allocated_entry_o(allocated_entry_unused),
    .attempt_valid_o(tx_attempt_valid), .attempt_ready_i(tx_attempt_ready),
    .attempt_entry_o(tx_attempt_entry), .attempt_sequence_o(tx_attempt_sequence),
    .attempt_payload_ref_o(tx_attempt_payload_ref),
    .attempt_payload_length_o(tx_attempt_payload_length),
    .attempt_descriptor_o(tx_attempt_descriptor),
    .attempt_priority_o(tx_attempt_priority), .attempt_is_retry_o(tx_attempt_is_retry),
    .attempt_last_lane_o(tx_attempt_last_lane), .selected_lane_i(selected_lane_padded),
    .selected_path_epoch_i(scheduler_decision_path_epoch),
    .ack_valid_i(peer_ack_valid_i), .ack_session_epoch_i(peer_ack_session_epoch_i),
    .ack_base_i(peer_ack_base_i), .ack_bitmap_i(peer_ack_bitmap_i),
    .ack_width_i(peer_ack_width_i), .completion_pulse_o(completion_pulse_unused),
    .completion_batch_count_o(completion_batch_unused),
    .tx_next_sequence_o, .tx_ack_base_o, .outstanding_count_o(tx_outstanding_count_o),
    .outstanding_high_watermark_o(tx_outstanding_high_watermark_o),
    .attempt_count_o(tx_attempt_count_o), .retry_count_o(tx_retry_count_o),
    .retry_exhausted_count_o(tx_retry_exhausted_count_o),
    .timeout_count_o(tx_timeout_count_o),
    .duplicate_ack_count_o(tx_duplicate_ack_count_o),
    .stale_ack_count_o(tx_stale_ack_count_o),
    .out_of_window_ack_count_o(tx_out_of_window_ack_count_o),
    .migration_count_o(tx_migration_count_o),
    .retry_exhausted_sticky_o(retry_exhausted_sticky_unused)
  );

  ir_health_weighted_scheduler #(
    .LANE_COUNT(LANE_COUNT), .ENTRY_WIDTH(ENTRY_WIDTH)
  ) u_scheduler (
    .clk, .rst_n, .clear_counters_i,
    .state_reset_i(session_reset_i || abort_all_i), .lane_weights_i,
    .active_lane_mask_i, .lane_ready_i({LANE_COUNT{1'b1}}),
    .lane_health_i, .mapping_valid_i,
    .frame_admission_i, .lane_tx_permit_i, .duty_headroom_i, .fault_free_i,
    .global_permit_effective_i, .endpoint_armed_i, .tx_kill_active_i,
    .path_epoch_valid_i, .receiver_credit_i(peer_receiver_credit_i), .path_epoch_i,
    .request_valid_i(scheduler_request_valid), .request_ready_o(scheduler_request_ready),
    .request_entry_i(tx_attempt_entry),
    .request_cost_bytes_i(tx_attempt_payload_length + 16'd22),
    .request_priority_i(tx_attempt_priority), .request_retry_i(tx_attempt_is_retry),
    .request_last_lane_i(tx_attempt_last_lane[LANE_WIDTH-1:0]),
    .decision_valid_o(scheduler_decision_valid),
    .decision_ready_i(scheduler_decision_ready),
    .decision_admit_o(scheduler_decision_admit),
    .decision_entry_o(scheduler_decision_entry),
    .decision_lane_o(scheduler_decision_lane),
    .decision_path_epoch_o(scheduler_decision_path_epoch),
    .decision_defer_reason_o(scheduler_decision_defer_reason),
    .decision_migration_reason_o(scheduler_migration_reason_unused),
    .scheduled_frames_o(scheduler_frames_flat_o),
    .scheduled_bytes_o(scheduler_bytes_flat_o),
    .retry_count_o(scheduler_retries_flat_o),
    .migration_count_o(scheduler_migrations_flat_o),
    .maximum_starvation_o(scheduler_maximum_starvation_o)
  );

  ir_selective_repeat_rx #(
    .WINDOW_SIZE(WINDOW_SIZE), .SACK_BITS(SACK_BITS),
    .PAYLOAD_REF_WIDTH(PAYLOAD_REF_WIDTH)
  ) u_rx_window (
    .clk, .rst_n, .clear_counters_i, .session_reset_i, .initial_sequence_i,
    .session_epoch_i,
    .current_path_epoch_i(path_epoch_i), .rx_valid_i(rx_frame_valid_i),
    .rx_ready_o(rx_frame_ready_o), .rx_l1_valid_i,
    .rx_session_epoch_i, .rx_sequence_i, .rx_path_epoch_i,
    .rx_payload_ref_i, .rx_payload_length_i, .rx_accept_pulse_o(rx_accept_pulse),
    .delivery_valid_o(rx_delivery_valid_o), .delivery_ready_i(rx_delivery_ready_i),
    .delivery_sequence_o(rx_delivery_sequence_o),
    .delivery_payload_ref_o(rx_delivery_payload_ref_o),
    .delivery_payload_length_o(rx_delivery_payload_length_o),
    .rx_base_sequence_o, .sack_bitmap_o(rx_sack_bitmap_o),
    .receiver_credit_o(rx_receiver_credit_o),
    .out_of_order_count_o(rx_out_of_order_count_o),
    .duplicate_count_o(rx_duplicate_count_o), .old_count_o(rx_old_count_o),
    .future_count_o(rx_future_count_o),
    .stale_session_count_o(rx_stale_session_count_o),
    .stale_path_epoch_count_o(rx_stale_path_count_o), .gap_count_o(rx_gap_count_o),
    .delivery_count_o(rx_delivery_count_o),
    .protocol_error_count_o(rx_protocol_error_count_o)
  );

  ir_ack_aggregator #(
    .SACK_BITS(SACK_BITS),
    .FRAME_THRESHOLD(ACK_FRAME_THRESHOLD),
    .MAX_DELAY_CYCLES(ACK_MAX_DELAY_CYCLES)
  ) u_ack_aggregator (
    .clk, .rst_n, .clear_counters_i,
    .state_reset_i(session_reset_i || abort_all_i),
    .rx_accept_i(rx_accept_pulse),
    .session_epoch_i, .ack_base_i(rx_base_sequence_o),
    .sack_bitmap_i(rx_sack_bitmap_o), .sack_width_i(CONFIGURED_SACK_WIDTH),
    .receiver_credit_i({{(16-$clog2(WINDOW_SIZE+1)){1'b0}}, rx_receiver_credit_o}),
    .gap_blocked_i((|rx_sack_bitmap_o) && !rx_sack_bitmap_o[0]),
    .control_event_i(ack_control_event_i),
    .direction_boundary_i(ack_direction_boundary_i),
    .explicit_request_i(ack_explicit_request_i),
    .ack_valid_o(local_ack_valid_o), .ack_ready_i(local_ack_ready_i),
    .ack_session_epoch_o(local_ack_session_epoch_o), .ack_base_o(local_ack_base_o),
    .ack_bitmap_o(local_ack_bitmap_o), .ack_width_o(local_ack_width_o),
    .ack_receiver_credit_o(local_ack_receiver_credit_o),
    .aggregation_count_o(ack_aggregation_count_o),
    .timer_expiry_count_o(ack_timer_expiry_count_o),
    .ack_frames_sent_o(ack_frames_sent_o)
  );
endmodule
