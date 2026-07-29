`timescale 1ns/1ps
`default_nettype none

module p9_optical_transport_core #(
  parameter integer CLK_HZ = 64_000_000,
  parameter integer WINDOW_SIZE = 32,
  parameter integer SACK_BITS = 32,
  parameter integer MAX_PAYLOAD_BYTES = 247,
  parameter integer STORE_ADDR_WIDTH = 13,
  parameter integer RTO_CYCLES = 4_000_000,
  // The stationary TFDU fixture directly showed that a short half-duplex
  // direction change begins the reverse frame before the transmitting
  // module's receiver has recovered.  Keep a conservative 64 us guard in
  // both DATA-to-ACK and ACK-to-DATA directions, matching the canonical
  // 4096-cycle interval at 64 MHz.
  parameter integer ACK_TURNAROUND_GUARD_CYCLES = 4_096,
  // A 4 Mbit/s FIR symbol contains one 125 ns pulse in 500 ns, so the
  // instantaneous frame duty is 25%.  Prevent a lane from launching another
  // frame for 320 us after completion.  Even if ACK generation is suppressed
  // by a fault-injection case, any clock-aligned 1 ms window then contains at
  // most 680 us of frame activity (170 us Txd high), below the 18% target.
  parameter integer FRAME_DUTY_GUARD_CYCLES = 20_480
) (
  input  wire         clk,
  input  wire         rst_n,

  input  wire         receiver_enable_i,
  input  wire         arm_request_i,
  input  wire         disarm_request_i,
  input  wire         full_shutdown_request_i,
  input  wire         clear_counters_i,
  input  wire         start_object_i,
  input  wire         abort_object_i,
  input  wire [1:0]   cfg_lane_mask_i,
  input  wire [15:0]  cfg_lane_weights_i,
  input  wire [1:0]   cfg_rate_select_i,
  input  wire         cfg_direction_i,
  input  wire [31:0]  cfg_session_epoch_i,
  input  wire [15:0]  cfg_path_epoch_i,
  input  wire [31:0]  cfg_object_id_i,
  input  wire [15:0]  cfg_initial_sequence_i,
  input  wire [31:0]  cfg_fault_flags_i,
  input  wire [7:0]   cfg_drop_data_count_i,
  input  wire [7:0]   cfg_drop_ack_count_i,
  input  wire [1:0]   cfg_lane_unavailable_i,

  input  wire         raw_start_i,
  input  wire         raw_direction_i,
  input  wire [1:0]   raw_lane_mask_i,
  input  wire [31:0]  raw_pulse_target_i,
  input  wire [31:0]  raw_spacing_cycles_i,

  input  wire         s_axis_tvalid_i,
  output wire         s_axis_tready_o,
  input  wire [31:0]  s_axis_tdata_i,
  input  wire [3:0]   s_axis_tkeep_i,
  input  wire         s_axis_tlast_i,

  output wire         m_axis_tvalid_o,
  input  wire         m_axis_tready_i,
  output wire [31:0]  m_axis_tdata_o,
  output wire [3:0]   m_axis_tkeep_o,
  output wire         m_axis_tlast_o,

  input  wire [1:0]   a_rxd_i,
  output wire [1:0]   a_txd_o,
  output wire [1:0]   a_sd_o,
  output wire [1:0]   a_mode_o,
  input  wire [1:0]   b_rxd_i,
  output wire [1:0]   b_txd_o,
  output wire [1:0]   b_sd_o,
  output wire [1:0]   b_mode_o,

  output wire         endpoint_armed_o,
  output wire         tx_kill_active_o,
  output wire [3:0]   phy_ready_mask_o,
  output wire [3:0]   startup_done_mask_o,
  output wire [3:0]   safety_fault_mask_o,
  output wire         object_active_o,
  output wire         object_done_o,
  output wire         object_fail_o,
  output wire [31:0]  object_error_o,
  output wire         input_complete_o,
  output wire         output_complete_o,
  output wire [31:0]  input_byte_count_o,
  output wire [31:0]  output_byte_count_o,
  output wire         raw_busy_o,
  output wire         raw_done_o,
  output wire [31:0]  raw_sent_count_o,

  output wire [15:0]  tx_next_sequence_o,
  output wire [15:0]  tx_ack_base_o,
  output wire [5:0]   tx_outstanding_count_o,
  output wire [5:0]   tx_outstanding_high_watermark_o,
  output wire [15:0]  rx_base_sequence_o,
  output wire [31:0]  rx_sack_bitmap_o,
  output wire [31:0]  tx_attempt_count_o,
  output wire [31:0]  tx_retry_count_o,
  output wire [31:0]  tx_retry_exhausted_count_o,
  output wire [31:0]  tx_timeout_count_o,
  output wire [31:0]  tx_duplicate_ack_count_o,
  output wire [31:0]  tx_stale_ack_count_o,
  output wire [31:0]  tx_out_of_window_ack_count_o,
  output wire [31:0]  tx_migration_count_o,
  output wire [31:0]  rx_duplicate_count_o,
  output wire [31:0]  rx_out_of_order_count_o,
  output wire [31:0]  rx_old_count_o,
  output wire [31:0]  rx_future_count_o,
  output wire [31:0]  rx_stale_session_count_o,
  output wire [31:0]  rx_stale_path_count_o,
  output wire [31:0]  rx_gap_count_o,
  output wire [31:0]  rx_delivery_count_o,
  output wire [31:0]  rx_protocol_error_count_o,
  output wire [31:0]  ack_aggregation_count_o,
  output wire [31:0]  ack_timer_expiry_count_o,
  output wire [31:0]  ack_frames_sent_o,
  output wire [63:0]  scheduler_frames_flat_o,
  output wire [63:0]  scheduler_bytes_flat_o,
  output wire [63:0]  scheduler_retries_flat_o,
  output wire [63:0]  scheduler_migrations_flat_o,
  output wire [31:0]  scheduler_maximum_starvation_o,
  output wire [31:0]  physical_data_frames_good_o,
  output wire [31:0]  physical_ack_frames_good_o,
  output wire [31:0]  physical_crc_bad_o,
  output wire [31:0]  physical_frame_bad_o,
  output wire [31:0]  physical_preamble_count_o,
  output wire [31:0]  physical_symbol_error_count_o,
  output wire [31:0]  physical_drop_data_count_o,
  output wire [31:0]  physical_drop_ack_count_o,
  output wire [127:0] raw_rx_counts_flat_o,
  output wire [127:0] physical_tx_counts_flat_o,
  output wire [127:0] tx_high_max_flat_o,
  output wire [127:0] duty_high_max_flat_o,
  output wire [127:0] duty_high_current_flat_o,
  output wire [127:0] duty_headroom_flat_o,
  output wire [127:0] duty_target_throttle_count_flat_o,
  output wire [127:0] duty_hard_fault_count_flat_o,
  output wire [31:0]  duty_window_cycles_o,
  output wire [31:0]  duty_hard_limit_cycles_o,
  output wire [31:0]  duty_target_limit_cycles_o
);
  localparam integer STORE_BYTES = WINDOW_SIZE * MAX_PAYLOAD_BYTES;
  localparam integer ENTRY_WIDTH = $clog2(WINDOW_SIZE);
  localparam integer FRAME_DUTY_GUARD_WIDTH =
      (FRAME_DUTY_GUARD_CYCLES < 1) ? 1 : $clog2(FRAME_DUTY_GUARD_CYCLES + 1);

  function automatic [31:0] crc32_next_byte(
    input [7:0] data, input [31:0] crc_in
  );
    reg [31:0] c;
    integer bit_index;
    begin
      c = crc_in;
      for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1)
        c = (c[0] ^ data[bit_index]) ? ((c >> 1) ^ 32'hEDB8_8320) : (c >> 1);
      crc32_next_byte = c;
    end
  endfunction

  function automatic [2:0] keep_count(input [3:0] keep);
    begin
      case (keep)
        4'b0001: keep_count = 1;
        4'b0011: keep_count = 2;
        4'b0111: keep_count = 3;
        4'b1111: keep_count = 4;
        default: keep_count = 0;
      endcase
    end
  endfunction

  reg receiver_enable_q;
  reg endpoint_armed_q;
  reg shutdown_latched_q;
  reg object_active_q;
  reg object_done_q;
  reg object_fail_q;
  reg [31:0] object_error_q;
  reg object_direction_q;
  reg [1:0] object_lane_mask_q;
  reg [15:0] object_lane_weights_q;
  reg [1:0] object_rate_q;
  reg [31:0] object_session_q;
  reg [15:0] object_path_q;
  reg [31:0] object_id_q;
  reg [15:0] object_initial_sequence_q;
  reg [31:0] fault_flags_remaining_q;
  reg [2:0] fault_attempt_budget_q;
  reg duplicate_ack_validation_pending_q;
  reg [31:0] duplicate_ack_validation_start_q;
  reg session_reset_pulse_q;
  reg [7:0] drop_data_remaining_q;
  reg [7:0] drop_ack_remaining_q;
  reg [31:0] dropped_data_count_q;
  reg [31:0] dropped_ack_count_q;

  wire [1:0] a_phy_ready;
  wire [1:0] b_phy_ready;
  wire [1:0] a_startup_done;
  wire [1:0] b_startup_done;
  wire [1:0] a_fault_stuck;
  wire [1:0] b_fault_stuck;
  wire [1:0] a_fault_duty;
  wire [1:0] b_fault_duty;
  wire [1:0] a_txd_internal;
  wire [1:0] b_txd_internal;
  wire [1:0] a_rx_pulse;
  wire [1:0] b_rx_pulse;
  wire any_safety_fault = |a_fault_stuck | |b_fault_stuck | |a_fault_duty | |b_fault_duty;
  wire tx_kill = !endpoint_armed_q || shutdown_latched_q || any_safety_fault;

  assign endpoint_armed_o = endpoint_armed_q;
  assign tx_kill_active_o = tx_kill;
  assign phy_ready_mask_o = {b_phy_ready[1], b_phy_ready[0], a_phy_ready[1], a_phy_ready[0]};
  assign startup_done_mask_o = {b_startup_done[1], b_startup_done[0],
                                a_startup_done[1], a_startup_done[0]};
  assign safety_fault_mask_o = {b_fault_stuck[1] | b_fault_duty[1],
                                b_fault_stuck[0] | b_fault_duty[0],
                                a_fault_stuck[1] | a_fault_duty[1],
                                a_fault_stuck[0] | a_fault_duty[0]};
  assign object_active_o = object_active_q;
  assign object_done_o = object_done_q;
  assign object_fail_o = object_fail_q;
  assign object_error_o = object_error_q;
  assign physical_drop_data_count_o = dropped_data_count_q;
  assign physical_drop_ack_count_o = dropped_ack_count_q;

  // AXI-stream ingress and immutable selective-repeat payload store.
  (* ram_style="block" *) reg [7:0] tx_store_lane0 [0:STORE_BYTES-1];
  (* ram_style="block" *) reg [7:0] tx_store_lane1 [0:STORE_BYTES-1];
  reg [31:0] tx_slot_crc [0:WINDOW_SIZE-1];
  reg tx_slot_final [0:WINDOW_SIZE-1];
  reg [31:0] tx_slot_fragment_offset [0:WINDOW_SIZE-1];
  reg [31:0] ingress_bytes_q;
  reg input_complete_q;
  reg beat_valid_q;
  reg [31:0] beat_data_q;
  reg [2:0] beat_byte_count_q;
  reg [2:0] beat_byte_index_q;
  reg beat_last_q;
  reg [15:0] ingress_frame_length_q;
  reg [31:0] ingress_frame_crc_q;
  reg [31:0] ingress_fragment_offset_q;
  reg allocate_pending_q;
  reg [15:0] allocate_length_q;
  reg allocate_final_q;
  reg [ENTRY_WIDTH-1:0] allocate_slot_q;
  reg ingress_error_pulse_q;

  wire dp_allocate_ready;
  wire dp_allocate_pulse;
  wire [15:0] dp_allocated_sequence;
  wire ingress_can_start_frame = ingress_frame_length_q != 0 || dp_allocate_ready;
  // A 247-byte fragment boundary can fall inside one 32-bit AXI beat.  The
  // beat may therefore already be buffered when the previous fragment fills
  // the selective-repeat window.  Recheck admission before consuming the
  // first byte of every fragment; otherwise the residual 1--3 bytes make the
  // next frame non-empty and allow it to overwrite a still-live circular
  // payload slot.
  wire ingress_byte_can_advance = ingress_frame_length_q != 0 ||
                                  dp_allocate_ready;
  wire [7:0] ingress_current_byte = beat_data_q[8*beat_byte_index_q +: 8];
  wire [31:0] ingress_next_crc = crc32_next_byte(ingress_current_byte,
                                                  ingress_frame_crc_q);
  wire ingress_end_of_object = beat_last_q &&
      (beat_byte_index_q == beat_byte_count_q - 1'b1);
  wire ingress_end_of_frame = ingress_end_of_object ||
      ingress_frame_length_q == MAX_PAYLOAD_BYTES-1;
  wire [ENTRY_WIDTH-1:0] ingress_current_slot =
      tx_next_sequence_o[ENTRY_WIDTH-1:0];
  wire [STORE_ADDR_WIDTH-1:0] ingress_write_address =
      ingress_current_slot * MAX_PAYLOAD_BYTES + ingress_frame_length_q;
  wire ingress_store_write = beat_valid_q && !allocate_pending_q &&
      ingress_byte_can_advance &&
      !start_object_i && !abort_object_i && !disarm_request_i &&
      !full_shutdown_request_i &&
      !any_safety_fault;

  // Keep all payload and immutable slot metadata memories out of the
  // asynchronously-reset control process.  This is the canonical synchronous
  // RAM template required for BRAM inference on 7-series devices.
  always @(posedge clk) begin : ingress_payload_memory
    if (ingress_store_write) begin
      tx_store_lane0[ingress_write_address] <= ingress_current_byte;
      tx_store_lane1[ingress_write_address] <= ingress_current_byte;
      if (ingress_end_of_frame) begin
        tx_slot_crc[ingress_current_slot] <= ~ingress_next_crc;
        tx_slot_final[ingress_current_slot] <= ingress_end_of_object;
        tx_slot_fragment_offset[ingress_current_slot] <= ingress_fragment_offset_q;
      end
    end
  end

  assign s_axis_tready_o = object_active_q && !object_fail_q && !disarm_request_i &&
      !input_complete_q &&
      !beat_valid_q && !allocate_pending_q && ingress_can_start_frame;
  assign input_complete_o = input_complete_q;
  assign input_byte_count_o = ingress_bytes_q;

  // This state drives the transmit payload BRAM write address and enable.
  // Use synchronous reset to satisfy RAMB async-control safety checks.
  always @(posedge clk) begin : ingress_and_store
    if (!rst_n) begin
      ingress_bytes_q <= 0;
      input_complete_q <= 0;
      beat_valid_q <= 0;
      beat_data_q <= 0;
      beat_byte_count_q <= 0;
      beat_byte_index_q <= 0;
      beat_last_q <= 0;
      ingress_frame_length_q <= 0;
      ingress_frame_crc_q <= 32'hFFFF_FFFF;
      ingress_fragment_offset_q <= 0;
      allocate_pending_q <= 0;
      allocate_length_q <= 0;
      allocate_final_q <= 0;
      allocate_slot_q <= 0;
      ingress_error_pulse_q <= 0;
    end else begin
      ingress_error_pulse_q <= 0;
      if (start_object_i) begin
        ingress_bytes_q <= 0;
        input_complete_q <= 0;
        beat_valid_q <= 0;
        ingress_frame_length_q <= 0;
        ingress_frame_crc_q <= 32'hFFFF_FFFF;
        ingress_fragment_offset_q <= 0;
        allocate_pending_q <= 0;
      end else if (abort_object_i || disarm_request_i || full_shutdown_request_i || any_safety_fault) begin
        beat_valid_q <= 0;
        allocate_pending_q <= 0;
      end else begin
        if (s_axis_tvalid_i && s_axis_tready_o) begin
          beat_valid_q <= 1;
          beat_data_q <= s_axis_tdata_i;
          beat_byte_count_q <= keep_count(s_axis_tkeep_i);
          beat_byte_index_q <= 0;
          beat_last_q <= s_axis_tlast_i;
          if (keep_count(s_axis_tkeep_i) == 0 ||
              (!s_axis_tlast_i && s_axis_tkeep_i != 4'hf)) begin
            beat_valid_q <= 0;
            ingress_error_pulse_q <= 1;
          end
        end
        if (beat_valid_q && !allocate_pending_q && ingress_byte_can_advance) begin
          ingress_bytes_q <= ingress_bytes_q + 1'b1;
          ingress_frame_crc_q <= ingress_next_crc;
          if (beat_byte_index_q == beat_byte_count_q - 1'b1)
            beat_valid_q <= 0;
          else
            beat_byte_index_q <= beat_byte_index_q + 1'b1;
          if (ingress_end_of_frame) begin
            allocate_slot_q <= ingress_current_slot;
            allocate_length_q <= ingress_frame_length_q + 1'b1;
            allocate_final_q <= ingress_end_of_object;
            allocate_pending_q <= 1;
            if (ingress_end_of_object) input_complete_q <= 1;
          end else begin
            ingress_frame_length_q <= ingress_frame_length_q + 1'b1;
          end
        end
        if (allocate_pending_q && dp_allocate_ready) begin
          allocate_pending_q <= 0;
          ingress_fragment_offset_q <= ingress_fragment_offset_q + allocate_length_q;
          ingress_frame_length_q <= 0;
          ingress_frame_crc_q <= 32'hFFFF_FFFF;
        end
      end
    end
  end

  // P8D selective-repeat, SACK aggregator and health-weighted scheduler.
  wire dp_attempt_valid;
  wire dp_attempt_ready;
  wire [ENTRY_WIDTH-1:0] dp_attempt_entry;
  wire [15:0] dp_attempt_sequence;
  wire [ENTRY_WIDTH-1:0] dp_attempt_payload_ref;
  wire [15:0] dp_attempt_payload_length;
  wire [15:0] dp_attempt_descriptor;
  wire dp_attempt_lane;
  wire [15:0] dp_attempt_path;
  wire dp_attempt_retry;
  reg dp_peer_ack_valid_q;
  reg [31:0] dp_peer_ack_session_q;
  reg [15:0] dp_peer_ack_base_q;
  reg [31:0] dp_peer_ack_bitmap_q;
  reg [5:0] dp_peer_ack_width_q;
  // The RX window commits metadata through a synchronous staging cycle.  A
  // control event asserted with dp_rx_frame_valid_q would therefore snapshot
  // the previous ACK/SACK state.  Delay the physical-frame classification
  // until both the registered SACK bitmap and rx_accept_pulse are observable.
  // Newly accepted DATA must remain subject to the bounded ACK aggregator;
  // only a valid frame that was not newly accepted (for example a duplicate
  // after ACK loss) forces an immediate cumulative re-ACK of stable state.
  reg [1:0] dp_ack_control_pipe_q;
  reg dp_rx_accept_delayed_q;
  reg dp_rx_frame_valid_q;
  reg dp_rx_l1_valid_q;
  reg [31:0] dp_rx_session_q;
  reg [15:0] dp_rx_sequence_q;
  reg [15:0] dp_rx_path_q;
  reg [ENTRY_WIDTH-1:0] dp_rx_payload_ref_q;
  reg [15:0] dp_rx_payload_length_q;
  wire dp_rx_frame_ready;
  wire dp_delivery_valid;
  reg dp_delivery_ready_q;
  wire [15:0] dp_delivery_sequence;
  wire [ENTRY_WIDTH-1:0] dp_delivery_payload_ref;
  wire [15:0] dp_delivery_payload_length;
  wire dp_local_ack_valid;
  reg dp_local_ack_ready_q;
  wire [31:0] dp_local_ack_session;
  wire [15:0] dp_local_ack_base;
  wire [31:0] dp_local_ack_bitmap;
  wire [5:0] dp_local_ack_width;
  wire [15:0] dp_local_ack_credit;
  wire [5:0] dp_rx_credit;
  wire [3:0] dp_scheduler_defer;
  wire [1:0] lane_runtime_ready;
  wire [1:0] effective_lane_mask = object_lane_mask_q & ~cfg_lane_unavailable_i;
  // The validation-only masks exercise the real scheduler defer paths.  They
  // can only remove a lane; they cannot create permit, mapping or duty
  // headroom.  Physical target-duty headroom remains independently enforced.
  wire [1:0] mapping_valid_mask = ~cfg_fault_flags_i[9:8];
  wire [1:0] injected_duty_headroom_mask = ~cfg_fault_flags_i[11:10];
  wire [1:0] physical_duty_headroom_mask =
      ~{a_fault_duty[1] | b_fault_duty[1],
        a_fault_duty[0] | b_fault_duty[0]};
  wire [1:0] schedulable_lane_mask = effective_lane_mask &
      mapping_valid_mask & injected_duty_headroom_mask &
      physical_duty_headroom_mask;

  ir_data_plane_top #(
    .LANE_COUNT(2), .WINDOW_SIZE(WINDOW_SIZE), .SACK_BITS(SACK_BITS),
    .MAX_RETRY(7), .RTO_CYCLES(RTO_CYCLES), .PAYLOAD_REF_WIDTH(ENTRY_WIDTH),
    .DESCRIPTOR_WIDTH(16)
  ) u_data_plane (
    .clk(clk), .rst_n(rst_n), .clear_counters_i(clear_counters_i),
    .session_reset_i(session_reset_pulse_q),
    .initial_sequence_i(object_initial_sequence_q),
    .abort_all_i(abort_object_i || disarm_request_i || full_shutdown_request_i || any_safety_fault ||
                 object_fail_q),
    .session_epoch_i(object_session_q), .path_epoch_i(object_path_q),
    .path_epoch_valid_i(1'b1), .lane_weights_i(object_lane_weights_q),
    .active_lane_mask_i(effective_lane_mask), .lane_ready_i(lane_runtime_ready),
    .lane_health_i(~cfg_lane_unavailable_i), .mapping_valid_i(mapping_valid_mask),
    .frame_admission_i(2'b11), .lane_tx_permit_i({2{endpoint_armed_q}}),
    .duty_headroom_i(physical_duty_headroom_mask &
                     injected_duty_headroom_mask),
    .fault_free_i(~{a_fault_stuck[1] | b_fault_stuck[1],
                    a_fault_stuck[0] | b_fault_stuck[0]}),
    .global_permit_effective_i(endpoint_armed_q), .endpoint_armed_i(endpoint_armed_q),
    .tx_kill_active_i(tx_kill),
    .peer_receiver_credit_i({10'd0, dp_rx_credit}),
    .tx_allocate_valid_i(allocate_pending_q), .tx_allocate_ready_o(dp_allocate_ready),
    .tx_allocate_payload_ref_i(allocate_slot_q),
    .tx_allocate_payload_length_i(allocate_length_q),
    .tx_allocate_descriptor_i({15'd0, allocate_final_q}),
    .tx_allocate_priority_i(3'd1), .tx_allocate_pulse_o(dp_allocate_pulse),
    .tx_allocated_sequence_o(dp_allocated_sequence),
    .physical_attempt_valid_o(dp_attempt_valid),
    .physical_attempt_ready_i(dp_attempt_ready),
    .physical_attempt_entry_o(dp_attempt_entry),
    .physical_attempt_sequence_o(dp_attempt_sequence),
    .physical_attempt_payload_ref_o(dp_attempt_payload_ref),
    .physical_attempt_payload_length_o(dp_attempt_payload_length),
    .physical_attempt_descriptor_o(dp_attempt_descriptor),
    .physical_attempt_lane_o(dp_attempt_lane),
    .physical_attempt_path_epoch_o(dp_attempt_path),
    .physical_attempt_is_retry_o(dp_attempt_retry),
    .peer_ack_valid_i(dp_peer_ack_valid_q),
    .peer_ack_session_epoch_i(dp_peer_ack_session_q),
    .peer_ack_base_i(dp_peer_ack_base_q), .peer_ack_bitmap_i(dp_peer_ack_bitmap_q),
    .peer_ack_width_i(dp_peer_ack_width_q),
    .rx_frame_valid_i(dp_rx_frame_valid_q), .rx_frame_ready_o(dp_rx_frame_ready),
    .rx_l1_valid_i(dp_rx_l1_valid_q), .rx_session_epoch_i(dp_rx_session_q),
    .rx_sequence_i(dp_rx_sequence_q), .rx_path_epoch_i(dp_rx_path_q),
    .rx_payload_ref_i(dp_rx_payload_ref_q),
    .rx_payload_length_i(dp_rx_payload_length_q),
    .rx_delivery_valid_o(dp_delivery_valid), .rx_delivery_ready_i(dp_delivery_ready_q),
    .rx_delivery_sequence_o(dp_delivery_sequence),
    .rx_delivery_payload_ref_o(dp_delivery_payload_ref),
    .rx_delivery_payload_length_o(dp_delivery_payload_length),
    // A validated physical DATA event that was not newly accepted forces a
    // cumulative response.  New frames participate in bounded aggregation;
    // duplicates force a re-ACK so reverse-path ACK loss is recoverable.
    .ack_control_event_i(dp_ack_control_pipe_q[1] &&
                         !dp_rx_accept_delayed_q),
    .ack_direction_boundary_i(1'b0),
    .ack_explicit_request_i(input_complete_q && tx_outstanding_count_o != 0),
    .local_ack_valid_o(dp_local_ack_valid), .local_ack_ready_i(dp_local_ack_ready_q),
    .local_ack_session_epoch_o(dp_local_ack_session),
    .local_ack_base_o(dp_local_ack_base), .local_ack_bitmap_o(dp_local_ack_bitmap),
    .local_ack_width_o(dp_local_ack_width),
    .local_ack_receiver_credit_o(dp_local_ack_credit),
    .tx_next_sequence_o(tx_next_sequence_o), .tx_ack_base_o(tx_ack_base_o),
    .tx_outstanding_count_o(tx_outstanding_count_o),
    .tx_outstanding_high_watermark_o(tx_outstanding_high_watermark_o),
    .rx_base_sequence_o(rx_base_sequence_o), .rx_sack_bitmap_o(rx_sack_bitmap_o),
    .rx_receiver_credit_o(dp_rx_credit), .tx_attempt_count_o(tx_attempt_count_o),
    .tx_retry_count_o(tx_retry_count_o),
    .tx_retry_exhausted_count_o(tx_retry_exhausted_count_o),
    .tx_timeout_count_o(tx_timeout_count_o),
    .tx_duplicate_ack_count_o(tx_duplicate_ack_count_o),
    .tx_stale_ack_count_o(tx_stale_ack_count_o),
    .tx_out_of_window_ack_count_o(tx_out_of_window_ack_count_o),
    .tx_migration_count_o(tx_migration_count_o),
    .rx_duplicate_count_o(rx_duplicate_count_o),
    .rx_out_of_order_count_o(rx_out_of_order_count_o),
    .rx_old_count_o(rx_old_count_o),
    .rx_future_count_o(rx_future_count_o),
    .rx_stale_session_count_o(rx_stale_session_count_o),
    .rx_stale_path_count_o(rx_stale_path_count_o),
    .rx_gap_count_o(rx_gap_count_o),
    .rx_delivery_count_o(rx_delivery_count_o),
    .rx_protocol_error_count_o(rx_protocol_error_count_o),
    .ack_aggregation_count_o(ack_aggregation_count_o),
    .ack_timer_expiry_count_o(ack_timer_expiry_count_o),
    .ack_frames_sent_o(ack_frames_sent_o),
    .scheduler_last_defer_reason_o(dp_scheduler_defer),
    .scheduler_frames_flat_o(scheduler_frames_flat_o),
    .scheduler_bytes_flat_o(scheduler_bytes_flat_o),
    .scheduler_retries_flat_o(scheduler_retries_flat_o),
    .scheduler_migrations_flat_o(scheduler_migrations_flat_o),
    .scheduler_maximum_starvation_o(scheduler_maximum_starvation_o)
  );

  always @(posedge clk or negedge rst_n) begin : ack_control_alignment
    if (!rst_n) begin
      dp_ack_control_pipe_q <= 2'b00;
      dp_rx_accept_delayed_q <= 1'b0;
    end else if (start_object_i || abort_object_i || disarm_request_i ||
                 full_shutdown_request_i || any_safety_fault) begin
      dp_ack_control_pipe_q <= 2'b00;
      dp_rx_accept_delayed_q <= 1'b0;
    end else begin
      dp_ack_control_pipe_q <= {
          dp_ack_control_pipe_q[0],
          dp_rx_frame_valid_q && dp_rx_l1_valid_q
      };
      dp_rx_accept_delayed_q <= rx_accept_pulse;
    end
  end

  // Two independent serializers read their own synchronous BRAM replica.
  // Each serializer holds its current byte while prefetching the next, so no
  // 247-byte asynchronous staging mux is present in the Z7010 datapath.
  wire [STORE_ADDR_WIDTH-1:0] tx_store_read_addr [0:1];
  reg [7:0] tx_store_read_data [0:1];
  reg [STORE_ADDR_WIDTH-1:0] lane_payload_base [0:1];
  reg lane_start_pending [0:1];
  reg lane_frame_ack [0:1];
  reg [31:0] lane_session [0:1];
  reg [15:0] lane_path [0:1];
  reg [15:0] lane_sequence [0:1];
  reg [15:0] lane_length [0:1];
  reg [31:0] lane_crc [0:1];
  reg [7:0] lane_flags [0:1];
  reg [31:0] lane_object [0:1];
  reg [31:0] lane_fragment [0:1];
  reg [15:0] lane_ack_base [0:1];
  reg [31:0] lane_ack_bitmap [0:1];
  reg [15:0] lane_ack_credit [0:1];
  reg lane_source_a [0:1];
  wire [STORE_ADDR_WIDTH-1:0] serializer_payload_address [0:1];
  wire serializer_start_ready [0:1];
  wire serializer_pulse [0:1];
  wire serializer_busy [0:1];
  wire serializer_done [0:1];
  reg serializer_busy_d [0:1];
  reg [6:0] receive_tail [0:1];
  reg receive_tail_destination_b [0:1];
  reg [FRAME_DUTY_GUARD_WIDTH-1:0] frame_duty_guard_q [0:1];

  always @(posedge clk) begin
    tx_store_read_data[0] <= tx_store_lane0[tx_store_read_addr[0]];
    tx_store_read_data[1] <= tx_store_lane1[tx_store_read_addr[1]];
  end
  assign tx_store_read_addr[0] = serializer_payload_address[0];
  assign tx_store_read_addr[1] = serializer_payload_address[1];

  typedef enum reg [2:0] {PH_DATA, PH_ACK_GUARD, PH_ACK_START,
                          PH_ACK_WAIT_DONE, PH_ACK_WAIT_RX,
                          PH_ACK_REPEAT_WAIT, PH_DATA_GUARD} phase_t;
  phase_t phase_q;
  reg [15:0] phase_guard_q;
  reg ack_lane_q;
  reg [31:0] ack_wait_q;
  reg ack_received_pulse_q;
  wire lanes_idle = serializer_start_ready[0] && serializer_start_ready[1] &&
                    !lane_start_pending[0] && !lane_start_pending[1];
  // Admit an entire encoded frame against the exact physical-module duty
  // headroom before its first symbol.  A DATA frame has 16 preamble symbols,
  // 24 header bytes, payload, and four CRC bytes; every 4PPM symbol requests
  // exactly eight Txd-high clock cycles at all supported raw rates.  Reserving
  // the complete frame prevents a target-policy throttle from deleting a chip
  // in the middle of an otherwise valid physical frame.
  wire [31:0] data_frame_required_high_cycles =
      32'd1024 + ({16'd0, dp_attempt_payload_length} << 5);
  wire [31:0] data_lane0_headroom = object_direction_q ?
      duty_headroom_flat_o[95:64] : duty_headroom_flat_o[31:0];
  wire [31:0] data_lane1_headroom = object_direction_q ?
      duty_headroom_flat_o[127:96] : duty_headroom_flat_o[63:32];
  wire [1:0] data_frame_duty_ready = {
      data_lane1_headroom >= data_frame_required_high_cycles,
      data_lane0_headroom >= data_frame_required_high_cycles
  };
  // ACK frames contain 16 preamble plus 20*4 data symbols, or 768 Txd-high
  // cycles.  ACKs travel from the opposite physical endpoint.
  wire [31:0] ack_lane0_headroom = object_direction_q ?
      duty_headroom_flat_o[31:0] : duty_headroom_flat_o[95:64];
  wire [31:0] ack_lane1_headroom = object_direction_q ?
      duty_headroom_flat_o[63:32] : duty_headroom_flat_o[127:96];
  wire [1:0] ack_frame_duty_ready = {
      ack_lane1_headroom >= 32'd768,
      ack_lane0_headroom >= 32'd768
  };
  wire [1:0] ack_schedulable_lane_mask =
      schedulable_lane_mask & ack_frame_duty_ready;
  assign lane_runtime_ready[0] = schedulable_lane_mask[0] && !serializer_busy[0] &&
      serializer_start_ready[0] && !lane_start_pending[0] &&
      frame_duty_guard_q[0] == 0 && data_frame_duty_ready[0] &&
      phase_q == PH_DATA;
  assign lane_runtime_ready[1] = schedulable_lane_mask[1] && !serializer_busy[1] &&
      serializer_start_ready[1] && !lane_start_pending[1] &&
      frame_duty_guard_q[1] == 0 && data_frame_duty_ready[1] &&
      phase_q == PH_DATA;
  assign dp_attempt_ready = phase_q == PH_DATA && !dp_local_ack_valid &&
      (dp_attempt_lane ? lane_runtime_ready[1] : lane_runtime_ready[0]);

  genvar tx_lane;
  generate
    for (tx_lane = 0; tx_lane < 2; tx_lane = tx_lane + 1) begin : g_serializer
      p9_4ppm_frame_tx #(.PAYLOAD_ADDR_WIDTH(STORE_ADDR_WIDTH)) u_serializer (
        .clk(clk), .rst_n(rst_n), .enable_i(endpoint_armed_q && !tx_kill),
        .abort_i(abort_object_i || disarm_request_i || full_shutdown_request_i),
        .rate_select_i(object_rate_q), .start_valid_i(lane_start_pending[tx_lane]),
        .start_ready_o(serializer_start_ready[tx_lane]),
        .frame_is_ack_i(lane_frame_ack[tx_lane]),
        .session_epoch_i(lane_session[tx_lane]), .path_epoch_i(lane_path[tx_lane]),
        .sequence_i(lane_sequence[tx_lane]), .payload_length_i(lane_length[tx_lane]),
        .payload_crc32_i(lane_crc[tx_lane]), .flags_i(lane_flags[tx_lane]),
        .lane_id_i(tx_lane[7:0]), .object_id_i(lane_object[tx_lane]),
        .fragment_offset_i(lane_fragment[tx_lane]),
        .ack_base_i(lane_ack_base[tx_lane]), .ack_bitmap_i(lane_ack_bitmap[tx_lane]),
        .ack_credit_i(lane_ack_credit[tx_lane]), .direction_i(object_direction_q),
        .payload_base_i(lane_payload_base[tx_lane]),
        .payload_read_address_o(serializer_payload_address[tx_lane]),
        .payload_read_data_i(tx_store_read_data[tx_lane]),
        .pulse_request_o(serializer_pulse[tx_lane]), .busy_o(serializer_busy[tx_lane]),
        .done_pulse_o(serializer_done[tx_lane]), .frame_count_o(), .byte_count_o()
      );
    end
  endgenerate

  integer copy_lane;
  // Lane metadata becomes the serializer payload-BRAM read address, so these
  // controls are synchronously reset.  Final Txd kill remains asynchronous.
  always @(posedge clk) begin : attempt_copy_and_ack_phase
    if (!rst_n) begin
      phase_q <= PH_DATA;
      phase_guard_q <= 0;
      ack_lane_q <= 0;
      ack_wait_q <= 0;
      dp_local_ack_ready_q <= 0;
      drop_data_remaining_q <= 0;
      drop_ack_remaining_q <= 0;
      fault_flags_remaining_q <= 0;
      fault_attempt_budget_q <= 0;
      duplicate_ack_validation_pending_q <= 0;
      duplicate_ack_validation_start_q <= 0;
      dropped_data_count_q <= 0;
      dropped_ack_count_q <= 0;
      for (copy_lane = 0; copy_lane < 2; copy_lane = copy_lane + 1) begin
        lane_payload_base[copy_lane] <= 0;
        lane_start_pending[copy_lane] <= 0;
        lane_frame_ack[copy_lane] <= 0;
        lane_session[copy_lane] <= 0;
        lane_path[copy_lane] <= 0;
        lane_sequence[copy_lane] <= 0;
        lane_length[copy_lane] <= 0;
        lane_crc[copy_lane] <= 0;
        lane_flags[copy_lane] <= 0;
        lane_object[copy_lane] <= 0;
        lane_fragment[copy_lane] <= 0;
        lane_ack_base[copy_lane] <= 0;
        lane_ack_bitmap[copy_lane] <= 0;
        lane_ack_credit[copy_lane] <= 0;
        lane_source_a[copy_lane] <= 0;
        serializer_busy_d[copy_lane] <= 0;
        receive_tail[copy_lane] <= 0;
        receive_tail_destination_b[copy_lane] <= 0;
        frame_duty_guard_q[copy_lane] <= 0;
      end
    end else begin
      dp_local_ack_ready_q <= 0;
      if (clear_counters_i) begin
        dropped_data_count_q <= 0;
        dropped_ack_count_q <= 0;
      end
      for (copy_lane = 0; copy_lane < 2; copy_lane = copy_lane + 1) begin
        serializer_busy_d[copy_lane] <= serializer_busy[copy_lane];
        if (serializer_done[copy_lane]) begin
          frame_duty_guard_q[copy_lane] <= FRAME_DUTY_GUARD_CYCLES;
        end else if (frame_duty_guard_q[copy_lane] != 0) begin
          frame_duty_guard_q[copy_lane] <= frame_duty_guard_q[copy_lane] - 1'b1;
        end
        if (lane_start_pending[copy_lane] && serializer_start_ready[copy_lane]) begin
          lane_start_pending[copy_lane] <= 0;
          lane_source_a[copy_lane] <= lane_frame_ack[copy_lane] ?
              object_direction_q : !object_direction_q;
          receive_tail_destination_b[copy_lane] <= lane_frame_ack[copy_lane] ?
              object_direction_q : !object_direction_q;
          if (phase_q == PH_ACK_START && copy_lane == ack_lane_q) begin
            dp_local_ack_ready_q <= 1;
            phase_q <= PH_ACK_WAIT_DONE;
          end
        end
        if (serializer_busy[copy_lane]) begin
          receive_tail[copy_lane] <= 7'd64;
        end else if (receive_tail[copy_lane] != 0) begin
          receive_tail[copy_lane] <= receive_tail[copy_lane] - 1'b1;
        end
      end

      if (start_object_i) begin
        phase_q <= PH_DATA;
        drop_data_remaining_q <= cfg_drop_data_count_i;
        drop_ack_remaining_q <= cfg_fault_flags_i[7] ?
            (cfg_drop_ack_count_i == 8'hff ? 8'hff :
             cfg_drop_ack_count_i + 1'b1) : cfg_drop_ack_count_i;
        fault_flags_remaining_q <= cfg_fault_flags_i;
        fault_attempt_budget_q <= (cfg_fault_flags_i[4:0] != 0) ? 3 : 0;
        duplicate_ack_validation_pending_q <= cfg_fault_flags_i[5];
        duplicate_ack_validation_start_q <= tx_duplicate_ack_count_o;
        for (copy_lane = 0; copy_lane < 2; copy_lane = copy_lane + 1) begin
          lane_start_pending[copy_lane] <= 0;
          receive_tail[copy_lane] <= 0;
        end
      end else if (abort_object_i || disarm_request_i || full_shutdown_request_i || any_safety_fault) begin
        phase_q <= PH_DATA;
        fault_flags_remaining_q <= 0;
        fault_attempt_budget_q <= 0;
        duplicate_ack_validation_pending_q <= 0;
        for (copy_lane = 0; copy_lane < 2; copy_lane = copy_lane + 1) begin
          lane_start_pending[copy_lane] <= 0;
        end
      end else if (!object_active_q) begin
        phase_q <= PH_DATA;
        drop_data_remaining_q <= 0;
        drop_ack_remaining_q <= 0;
        fault_flags_remaining_q <= 0;
        fault_attempt_budget_q <= 0;
        duplicate_ack_validation_pending_q <= 0;
      end else begin
        if (duplicate_ack_validation_pending_q &&
            tx_duplicate_ack_count_o != duplicate_ack_validation_start_q)
          duplicate_ack_validation_pending_q <= 0;
        if (dp_attempt_valid && dp_attempt_ready) begin
          if (drop_data_remaining_q != 0) begin
            drop_data_remaining_q <= drop_data_remaining_q - 1'b1;
            dropped_data_count_q <= dropped_data_count_q + 1'b1;
          end else begin
            lane_payload_base[dp_attempt_lane] <=
                dp_attempt_payload_ref * MAX_PAYLOAD_BYTES;
            lane_start_pending[dp_attempt_lane] <= 1;
            lane_frame_ack[dp_attempt_lane] <= 0;
            // Each test flag corrupts exactly the first non-dropped DATA
            // attempt.  The immutable slot metadata remains unchanged, so a
            // bounded retry exercises recovery with the canonical values.
            lane_session[dp_attempt_lane] <=
                (fault_attempt_budget_q != 0 && fault_flags_remaining_q[0]) ?
                object_session_q - 1'b1 : object_session_q;
            lane_path[dp_attempt_lane] <=
                (fault_attempt_budget_q != 0 && fault_flags_remaining_q[1]) ?
                object_path_q - 16'd2 : dp_attempt_path;
            lane_sequence[dp_attempt_lane] <=
                (fault_attempt_budget_q != 0 && fault_flags_remaining_q[2]) ?
                dp_attempt_sequence + WINDOW_SIZE :
                ((fault_attempt_budget_q != 0 && fault_flags_remaining_q[3]) ?
                 // Keep every bounded injected attempt strictly behind the
                 // receiver's object-start base.  Subtracting one from each
                 // attempt's own sequence can alias a later payload onto the
                 // current RX base and corrupt an otherwise recovered object.
                 object_initial_sequence_q - 1'b1 :
                 dp_attempt_sequence);
            lane_length[dp_attempt_lane] <= dp_attempt_payload_length;
            lane_crc[dp_attempt_lane] <=
                (fault_attempt_budget_q != 0 && fault_flags_remaining_q[4]) ?
                tx_slot_crc[dp_attempt_payload_ref] ^ 32'h0000_0001 :
                tx_slot_crc[dp_attempt_payload_ref];
            lane_flags[dp_attempt_lane] <= {7'd0, tx_slot_final[dp_attempt_payload_ref]};
            lane_object[dp_attempt_lane] <= object_id_q;
            lane_fragment[dp_attempt_lane] <= tx_slot_fragment_offset[dp_attempt_payload_ref];
            if (fault_attempt_budget_q != 0) begin
              fault_attempt_budget_q <= fault_attempt_budget_q - 1'b1;
              if (fault_attempt_budget_q == 1)
                fault_flags_remaining_q[4:0] <= 0;
            end
          end
        end

        case (phase_q)
          // READY is registered.  Once asserted for a validation-only dropped
          // ACK, do not consume the same held VALID again on the following
          // handshake cycle and accidentally serialize an ACK that was meant
          // to be lost.
          PH_DATA: if (dp_local_ack_valid && !dp_local_ack_ready_q) begin
            if (drop_ack_remaining_q != 0) begin
              drop_ack_remaining_q <= drop_ack_remaining_q - 1'b1;
              dropped_ack_count_q <= dropped_ack_count_q + 1'b1;
              dp_local_ack_ready_q <= 1;
            end else begin
              phase_q <= PH_ACK_GUARD;
              phase_guard_q <= ACK_TURNAROUND_GUARD_CYCLES;
            end
          end
          PH_ACK_GUARD: if (lanes_idle && ack_schedulable_lane_mask != 0) begin
            if (phase_guard_q != 0) phase_guard_q <= phase_guard_q - 1'b1;
            else begin
              ack_lane_q <= ack_schedulable_lane_mask[0] ? 1'b0 : 1'b1;
              lane_frame_ack[ack_schedulable_lane_mask[0] ? 0 : 1] <= 1;
              lane_session[ack_schedulable_lane_mask[0] ? 0 : 1] <= dp_local_ack_session;
              lane_path[ack_schedulable_lane_mask[0] ? 0 : 1] <= object_path_q;
              lane_sequence[ack_schedulable_lane_mask[0] ? 0 : 1] <= 0;
              lane_length[ack_schedulable_lane_mask[0] ? 0 : 1] <= 0;
              lane_crc[ack_schedulable_lane_mask[0] ? 0 : 1] <= 0;
              lane_flags[ack_schedulable_lane_mask[0] ? 0 : 1] <= 0;
              lane_object[ack_schedulable_lane_mask[0] ? 0 : 1] <= 0;
              lane_fragment[ack_schedulable_lane_mask[0] ? 0 : 1] <= 0;
              lane_ack_base[ack_schedulable_lane_mask[0] ? 0 : 1] <= dp_local_ack_base;
              lane_ack_bitmap[ack_schedulable_lane_mask[0] ? 0 : 1] <= dp_local_ack_bitmap;
              lane_ack_credit[ack_schedulable_lane_mask[0] ? 0 : 1] <= dp_local_ack_credit;
              lane_start_pending[ack_schedulable_lane_mask[0] ? 0 : 1] <= 1;
              phase_q <= PH_ACK_START;
            end
          end
          PH_ACK_WAIT_DONE: if (serializer_done[ack_lane_q]) begin
            phase_q <= PH_ACK_WAIT_RX;
            ack_wait_q <= 0;
          end
          PH_ACK_WAIT_RX: begin
            if (ack_received_pulse_q) begin
              // Re-emit the captured ACK once.  It traverses the reverse
              // optical path again and must be rejected as a duplicate by
              // the selective-repeat TX window.
              if (fault_flags_remaining_q[5]) begin
                fault_flags_remaining_q[5] <= 0;
                phase_q <= PH_ACK_REPEAT_WAIT;
              end else begin
                // The reverse transmitter has just completed an ACK.  Its
                // local receiver must recover before the next DATA frame is
                // allowed to start in the opposite direction.
                phase_q <= PH_DATA_GUARD;
                phase_guard_q <= ACK_TURNAROUND_GUARD_CYCLES;
              end
              ack_wait_q <= 0;
            end else begin
              ack_wait_q <= ack_wait_q + 1'b1;
              if (ack_wait_q >= RTO_CYCLES-1) phase_q <= PH_DATA;
            end
          end
          PH_ACK_REPEAT_WAIT: if (lanes_idle &&
              schedulable_lane_mask[ack_lane_q] &&
              ack_frame_duty_ready[ack_lane_q]) begin
            lane_start_pending[ack_lane_q] <= 1;
            phase_q <= PH_ACK_WAIT_DONE;
          end
          PH_DATA_GUARD: if (lanes_idle) begin
            if (phase_guard_q != 0) phase_guard_q <= phase_guard_q - 1'b1;
            else phase_q <= PH_DATA;
          end
          default: ;
        endcase
      end
    end
  end

  // Raw matrix generator.  It shares only the final physical pulse request;
  // its receiver evidence comes from the independent active-low Rxd counters.
  reg raw_busy_q;
  reg raw_done_q;
  reg raw_direction_q;
  reg [1:0] raw_mask_q;
  reg [31:0] raw_target_q;
  reg [31:0] raw_spacing_q;
  reg [31:0] raw_cycle_q;
  reg [31:0] raw_sent_q;
  wire raw_pulse_request = raw_busy_q && raw_cycle_q < 5;
  assign raw_busy_o = raw_busy_q;
  assign raw_done_o = raw_done_q;
  assign raw_sent_count_o = raw_sent_q;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      raw_busy_q <= 0; raw_done_q <= 0; raw_direction_q <= 0; raw_mask_q <= 0;
      raw_target_q <= 0; raw_spacing_q <= 1024; raw_cycle_q <= 0; raw_sent_q <= 0;
    end else begin
      raw_done_q <= 0;
      if (raw_start_i && !object_active_q && endpoint_armed_q &&
          raw_lane_mask_i != 0 && raw_pulse_target_i != 0 && raw_spacing_cycles_i >= 128) begin
        raw_busy_q <= 1; raw_direction_q <= raw_direction_i; raw_mask_q <= raw_lane_mask_i;
        raw_target_q <= raw_pulse_target_i; raw_spacing_q <= raw_spacing_cycles_i;
        raw_cycle_q <= 0; raw_sent_q <= 0;
      end else if (raw_busy_q) begin
        if (raw_cycle_q >= raw_spacing_q - 1'b1) begin
          raw_cycle_q <= 0;
          raw_sent_q <= raw_sent_q + 1'b1;
          if (raw_sent_q + 1'b1 >= raw_target_q) begin
            raw_busy_q <= 0; raw_done_q <= 1;
          end
        end else raw_cycle_q <= raw_cycle_q + 1'b1;
      end
      if (disarm_request_i || full_shutdown_request_i || any_safety_fault) begin
        raw_busy_q <= 0;
        raw_mask_q <= 0;
        raw_cycle_q <= 0;
      end
    end
  end

  wire [1:0] a_tx_request;
  wire [1:0] b_tx_request;
  generate
    for (tx_lane = 0; tx_lane < 2; tx_lane = tx_lane + 1) begin : g_tx_route
      assign a_tx_request[tx_lane] = endpoint_armed_q && !tx_kill &&
          ((serializer_pulse[tx_lane] && lane_source_a[tx_lane]) ||
           (raw_pulse_request && !raw_direction_q && raw_mask_q[tx_lane]));
      assign b_tx_request[tx_lane] = endpoint_armed_q && !tx_kill &&
          ((serializer_pulse[tx_lane] && !lane_source_a[tx_lane]) ||
           (raw_pulse_request && raw_direction_q && raw_mask_q[tx_lane]));
    end
  endgenerate

  // Four physical TFDU modules and exact P8C accounting.
  wire [31:0] a_raw_count [0:1];
  wire [31:0] b_raw_count [0:1];
  wire [31:0] a_tx_count [0:1];
  wire [31:0] b_tx_count [0:1];
  wire [31:0] a_high_max [0:1];
  wire [31:0] b_high_max [0:1];
  wire [31:0] a_duty_max [0:1];
  wire [31:0] b_duty_max [0:1];
  wire [31:0] a_duty_current [0:1];
  wire [31:0] b_duty_current [0:1];
  wire [31:0] a_window [0:1];
  wire [31:0] b_window [0:1];
  wire [31:0] a_hard_limit [0:1];
  wire [31:0] b_hard_limit [0:1];
  wire [31:0] a_target_limit [0:1];
  wire [31:0] b_target_limit [0:1];
  wire [31:0] a_duty_headroom [0:1];
  wire [31:0] b_duty_headroom [0:1];
  wire [31:0] a_target_throttle_count [0:1];
  wire [31:0] b_target_throttle_count [0:1];
  wire [31:0] a_hard_fault_count [0:1];
  wire [31:0] b_hard_fault_count [0:1];
  wire physical_enable = receiver_enable_q && !shutdown_latched_q;

  generate
    for (tx_lane = 0; tx_lane < 2; tx_lane = tx_lane + 1) begin : g_physical
      tfdu_lane_phy #(
        .CLK_HZ(CLK_HZ), .TFDU_STARTUP_US(500),
        .CLEAR_STICKY_INVALIDATES_HISTORY(0),
        .TARGET_THROTTLE_LATCHES_FAULT(0)
      ) u_a_phy (
        .clk(clk), .rst_n(rst_n), .enable_phy(physical_enable),
        .clear_sticky(clear_counters_i), .tx_pulse_req(a_tx_request[tx_lane]),
        .rxd(a_rxd_i[tx_lane]), .Txd(a_txd_internal[tx_lane]), .SD(a_sd_o[tx_lane]),
        .Mode(a_mode_o[tx_lane]), .phy_ready(a_phy_ready[tx_lane]),
        .rx_pulse_active(a_rx_pulse[tx_lane]), .startup_done(a_startup_done[tx_lane]),
        .shutdown_active(), .fault_stuck_high(a_fault_stuck[tx_lane]),
        .fault_duty_limit(a_fault_duty[tx_lane]), .rx_raw_count(a_raw_count[tx_lane]),
        .tx_pulse_count(a_tx_count[tx_lane]), .rx_pulse_width_min(),
        .rx_pulse_width_max(), .rx_last_timestamp(), .tx_high_width_current(),
        .duty_window_count(a_window[tx_lane]), .duty_high_count(a_duty_current[tx_lane]),
        .tx_high_width_max_seen(a_high_max[tx_lane]),
        .duty_high_max_seen(a_duty_max[tx_lane]),
        .duty_hard_limit_cycles(a_hard_limit[tx_lane]),
        .duty_target_limit_cycles(a_target_limit[tx_lane]),
        .duty_headroom_cycles(a_duty_headroom[tx_lane]),
        .duty_target_throttle_count(a_target_throttle_count[tx_lane]),
        .duty_hard_fault_count(a_hard_fault_count[tx_lane])
      );
      tfdu_lane_phy #(
        .CLK_HZ(CLK_HZ), .TFDU_STARTUP_US(500),
        .CLEAR_STICKY_INVALIDATES_HISTORY(0),
        .TARGET_THROTTLE_LATCHES_FAULT(0)
      ) u_b_phy (
        .clk(clk), .rst_n(rst_n), .enable_phy(physical_enable),
        .clear_sticky(clear_counters_i), .tx_pulse_req(b_tx_request[tx_lane]),
        .rxd(b_rxd_i[tx_lane]), .Txd(b_txd_internal[tx_lane]), .SD(b_sd_o[tx_lane]),
        .Mode(b_mode_o[tx_lane]), .phy_ready(b_phy_ready[tx_lane]),
        .rx_pulse_active(b_rx_pulse[tx_lane]), .startup_done(b_startup_done[tx_lane]),
        .shutdown_active(), .fault_stuck_high(b_fault_stuck[tx_lane]),
        .fault_duty_limit(b_fault_duty[tx_lane]), .rx_raw_count(b_raw_count[tx_lane]),
        .tx_pulse_count(b_tx_count[tx_lane]), .rx_pulse_width_min(),
        .rx_pulse_width_max(), .rx_last_timestamp(), .tx_high_width_current(),
        .duty_window_count(b_window[tx_lane]), .duty_high_count(b_duty_current[tx_lane]),
        .tx_high_width_max_seen(b_high_max[tx_lane]),
        .duty_high_max_seen(b_duty_max[tx_lane]),
        .duty_hard_limit_cycles(b_hard_limit[tx_lane]),
        .duty_target_limit_cycles(b_target_limit[tx_lane]),
        .duty_headroom_cycles(b_duty_headroom[tx_lane]),
        .duty_target_throttle_count(b_target_throttle_count[tx_lane]),
        .duty_hard_fault_count(b_hard_fault_count[tx_lane])
      );
      assign a_txd_o[tx_lane] = a_txd_internal[tx_lane] && endpoint_armed_q && !tx_kill;
      assign b_txd_o[tx_lane] = b_txd_internal[tx_lane] && endpoint_armed_q && !tx_kill;
    end
  endgenerate

  assign raw_rx_counts_flat_o = {b_raw_count[1], b_raw_count[0],
                                 a_raw_count[1], a_raw_count[0]};
  assign physical_tx_counts_flat_o = {b_tx_count[1], b_tx_count[0],
                                      a_tx_count[1], a_tx_count[0]};
  assign tx_high_max_flat_o = {b_high_max[1], b_high_max[0], a_high_max[1], a_high_max[0]};
  assign duty_high_max_flat_o = {b_duty_max[1], b_duty_max[0], a_duty_max[1], a_duty_max[0]};
  assign duty_high_current_flat_o = {b_duty_current[1], b_duty_current[0],
                                     a_duty_current[1], a_duty_current[0]};
  assign duty_headroom_flat_o = {b_duty_headroom[1], b_duty_headroom[0],
                                 a_duty_headroom[1], a_duty_headroom[0]};
  assign duty_target_throttle_count_flat_o = {
      b_target_throttle_count[1], b_target_throttle_count[0],
      a_target_throttle_count[1], a_target_throttle_count[0]};
  assign duty_hard_fault_count_flat_o = {
      b_hard_fault_count[1], b_hard_fault_count[0],
      a_hard_fault_count[1], a_hard_fault_count[0]};
  assign duty_window_cycles_o = a_window[0];
  assign duty_hard_limit_cycles_o = a_hard_limit[0];
  assign duty_target_limit_cycles_o = a_target_limit[0];

  // Each logical lane is half duplex: the scheduled DATA frame and its ACK
  // never overlap on that lane.  Time-share one decoder/parser per lane and
  // select the physical destination Rxd explicitly.  This preserves four
  // independent physical safety paths while avoiding four redundant protocol
  // parsers on the resource-limited Z7010.
  wire [1:0] rx_symbol [0:1];
  wire rx_symbol_valid [0:1];
  wire rx_symbol_error [0:1];
  wire rx_preamble [0:1];
  wire rx_payload_we [0:1];
  wire [7:0] rx_payload_index [0:1];
  wire [7:0] rx_payload_data [0:1];
  wire rx_frame_valid [0:1];
  wire rx_frame_ack [0:1];
  wire rx_frame_crc [0:1];
  wire [31:0] rx_frame_session [0:1];
  wire [15:0] rx_frame_path [0:1];
  wire [15:0] rx_frame_sequence [0:1];
  wire [15:0] rx_frame_length [0:1];
  wire [7:0] rx_frame_flags [0:1];
  wire [31:0] rx_frame_object [0:1];
  wire [31:0] rx_frame_fragment [0:1];
  wire [15:0] rx_ack_base [0:1];
  wire [31:0] rx_ack_bitmap [0:1];
  wire [15:0] rx_ack_credit [0:1];
  wire rx_ack_direction [0:1];
  wire [31:0] rx_good [0:1];
  wire [31:0] rx_crc_bad [0:1];
  wire [31:0] rx_frame_bad [0:1];
  wire [31:0] rx_preamble_count [0:1];
  wire [31:0] rx_symbol_error_count [0:1];
  (* ram_style="block" *) reg [7:0] rx_temp_lane0 [0:MAX_PAYLOAD_BYTES-1];
  (* ram_style="block" *) reg [7:0] rx_temp_lane1 [0:MAX_PAYLOAD_BYTES-1];

  generate
    for (tx_lane = 0; tx_lane < 2; tx_lane = tx_lane + 1) begin : g_receive
      wire receive_window = serializer_busy[tx_lane] || receive_tail[tx_lane] != 0;
      wire selected_phy_ready = receive_tail_destination_b[tx_lane] ?
          b_phy_ready[tx_lane] : a_phy_ready[tx_lane];
      wire selected_rx_pulse = receive_tail_destination_b[tx_lane] ?
          b_rx_pulse[tx_lane] : a_rx_pulse[tx_lane];
      wire serializer_busy_rise = serializer_busy[tx_lane] &&
          !serializer_busy_d[tx_lane];
      // Keep the decoder alive through the bounded post-frame receive tail:
      // the final optical symbol reaches Rxd after serializer busy falls.
      // A one-cycle align at every busy rising edge still prevents the
      // variable CRC-preparation gap from carrying a stale chip grid into the
      // next frame.  A completed-frame pulse returns the decoder to
      // first-pulse acquisition without manufacturing an empty tail symbol.
      // The TFDU Rxd synchronizer guarantees that the busy-edge align
      // precedes the first received preamble pulse.
      p9_rate_4ppm_rx u_codec (
        .clk(clk), .rst_n(rst_n), .enable_i(selected_phy_ready),
        .rate_select_i(object_rate_q),
        .align_i(!receive_window || serializer_busy_rise ||
                 rx_frame_valid[tx_lane]),
        .rx_pulse_active_i(selected_rx_pulse), .symbol_o(rx_symbol[tx_lane]),
        .symbol_valid_o(rx_symbol_valid[tx_lane]),
        .symbol_error_o(rx_symbol_error[tx_lane]),
        .preamble_valid_o(rx_preamble[tx_lane]), .preamble_count_o(), .symbol_chips_o()
      );
      p9_4ppm_frame_rx u_parser (
        .clk(clk), .rst_n(rst_n), .enable_i(selected_phy_ready), .align_i(!receive_window),
        .symbol_i(rx_symbol[tx_lane]), .symbol_valid_i(rx_symbol_valid[tx_lane]),
        .symbol_error_i(rx_symbol_error[tx_lane]), .preamble_valid_i(rx_preamble[tx_lane]),
        .payload_write_pulse_o(rx_payload_we[tx_lane]),
        .payload_write_index_o(rx_payload_index[tx_lane]),
        .payload_write_data_o(rx_payload_data[tx_lane]), .frame_valid_o(rx_frame_valid[tx_lane]),
        .frame_is_ack_o(rx_frame_ack[tx_lane]), .frame_crc_valid_o(rx_frame_crc[tx_lane]),
        .session_epoch_o(rx_frame_session[tx_lane]), .path_epoch_o(rx_frame_path[tx_lane]),
        .sequence_o(rx_frame_sequence[tx_lane]), .payload_length_o(rx_frame_length[tx_lane]),
        .flags_o(rx_frame_flags[tx_lane]), .lane_id_o(), .object_id_o(rx_frame_object[tx_lane]),
        .fragment_offset_o(rx_frame_fragment[tx_lane]), .ack_base_o(rx_ack_base[tx_lane]),
        .ack_bitmap_o(rx_ack_bitmap[tx_lane]), .ack_credit_o(rx_ack_credit[tx_lane]),
        .direction_o(rx_ack_direction[tx_lane]), .frame_good_count_o(rx_good[tx_lane]),
        .frame_bad_count_o(rx_frame_bad[tx_lane]),
        .crc_bad_count_o(rx_crc_bad[tx_lane]),
        .preamble_count_o(rx_preamble_count[tx_lane]),
        .symbol_error_count_o(rx_symbol_error_count[tx_lane])
      );
    end
  endgenerate

  reg [31:0] physical_data_good_q;
  reg [31:0] physical_ack_good_q;
  wire [1:0] physical_data_good_increment =
      {1'b0, (rx_frame_valid[0] && rx_frame_crc[0] && !rx_frame_ack[0])} +
      {1'b0, (rx_frame_valid[1] && rx_frame_crc[1] && !rx_frame_ack[1])};
  wire [1:0] physical_ack_good_increment =
      {1'b0, (rx_frame_valid[0] && rx_frame_crc[0] && rx_frame_ack[0])} +
      {1'b0, (rx_frame_valid[1] && rx_frame_crc[1] && rx_frame_ack[1])};
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      physical_data_good_q <= 0;
      physical_ack_good_q <= 0;
    end else if (clear_counters_i) begin
      physical_data_good_q <= 0;
      physical_ack_good_q <= 0;
    end else begin
      physical_data_good_q <= physical_data_good_q + physical_data_good_increment;
      physical_ack_good_q <= physical_ack_good_q + physical_ack_good_increment;
    end
  end
  assign physical_data_frames_good_o = physical_data_good_q;
  assign physical_ack_frames_good_o = physical_ack_good_q;
  assign physical_crc_bad_o = rx_crc_bad[0] + rx_crc_bad[1];
  assign physical_frame_bad_o = rx_frame_bad[0] + rx_frame_bad[1];
  assign physical_preamble_count_o = rx_preamble_count[0] + rx_preamble_count[1];
  assign physical_symbol_error_count_o =
      rx_symbol_error_count[0] + rx_symbol_error_count[1];

  // Receive completion queues and copy into the reorder-window store.
  reg rx_pending [0:1];
  reg rx_pending_l1 [0:1];
  reg [31:0] rx_pending_session [0:1];
  reg [15:0] rx_pending_path [0:1];
  reg [15:0] rx_pending_sequence [0:1];
  reg [15:0] rx_pending_length [0:1];
  reg rx_pending_final [0:1];
  reg [31:0] rx_pending_object [0:1];
  (* ram_style="block" *) reg [7:0] rx_store [0:STORE_BYTES-1];
  reg rx_final_slot [0:WINDOW_SIZE-1];
  typedef enum reg [1:0] {RXC_IDLE, RXC_PRIME, RXC_COPY, RXC_PULSE} rxc_state_t;
  rxc_state_t rxc_state_q;
  reg rxc_lane_q;
  reg [7:0] rxc_read_index_q;
  reg [7:0] rxc_write_index_q;
  reg [STORE_ADDR_WIDTH-1:0] rxc_base_q;
  reg [7:0] rx_temp_lane0_read_q;
  reg [7:0] rx_temp_lane1_read_q;
  reg reorder_hold_q;

  always @(posedge clk) begin : rx_lane_staging_memories
    if (rx_payload_we[0])
      rx_temp_lane0[rx_payload_index[0]] <= rx_payload_data[0];
    if (rx_payload_we[1])
      rx_temp_lane1[rx_payload_index[1]] <= rx_payload_data[1];
    rx_temp_lane0_read_q <= rx_temp_lane0[rxc_read_index_q];
    rx_temp_lane1_read_q <= rx_temp_lane1[rxc_read_index_q];
  end

  wire rxc_store_write = rxc_state_q == RXC_COPY && !start_object_i &&
      !abort_object_i && !disarm_request_i && !full_shutdown_request_i;
  always @(posedge clk) begin : rx_payload_memory
    if (rxc_store_write)
      rx_store[rxc_base_q + rxc_write_index_q] <= rxc_lane_q ?
          rx_temp_lane1_read_q : rx_temp_lane0_read_q;
  end

  integer rx_lane;
  // Copy indices and base directly drive receive BRAM ports.
  always @(posedge clk) begin : receive_queue_and_copy
    reg data_event;
    reg event_crc;
    reg [31:0] event_session;
    reg [15:0] event_path;
    reg [15:0] event_sequence;
    reg [15:0] event_length;
    reg event_final;
    reg [31:0] event_object;
    reg [15:0] receive_distance;
    reg selected_lane;
    if (!rst_n) begin
      rxc_state_q <= RXC_IDLE;
      rxc_lane_q <= 0;
      rxc_read_index_q <= 0;
      rxc_write_index_q <= 0;
      rxc_base_q <= 0;
      dp_rx_frame_valid_q <= 0;
      dp_rx_l1_valid_q <= 0;
      dp_rx_session_q <= 0;
      dp_rx_sequence_q <= 0;
      dp_rx_path_q <= 0;
      dp_rx_payload_ref_q <= 0;
      dp_rx_payload_length_q <= 0;
      reorder_hold_q <= 0;
      for (rx_lane = 0; rx_lane < 2; rx_lane = rx_lane + 1) rx_pending[rx_lane] <= 0;
      for (rx_lane = 0; rx_lane < WINDOW_SIZE; rx_lane = rx_lane + 1) rx_final_slot[rx_lane] <= 0;
    end else begin
      dp_rx_frame_valid_q <= 0;
      for (rx_lane = 0; rx_lane < 2; rx_lane = rx_lane + 1) begin
        data_event = rx_frame_valid[rx_lane] && !rx_frame_ack[rx_lane];
        event_crc = rx_frame_crc[rx_lane];
        event_session = rx_frame_session[rx_lane];
        event_path = rx_frame_path[rx_lane];
        event_sequence = rx_frame_sequence[rx_lane];
        event_length = rx_frame_length[rx_lane];
        event_final = rx_frame_flags[rx_lane][0];
        event_object = rx_frame_object[rx_lane];
        if (data_event && !rx_pending[rx_lane]) begin
          rx_pending[rx_lane] <= 1;
          rx_pending_l1[rx_lane] <= event_crc && event_object == object_id_q;
          rx_pending_session[rx_lane] <= event_session;
          rx_pending_path[rx_lane] <= event_path;
          rx_pending_sequence[rx_lane] <= event_sequence;
          rx_pending_length[rx_lane] <= event_length;
          rx_pending_final[rx_lane] <= event_final;
          rx_pending_object[rx_lane] <= event_object;
        end
      end

      if (start_object_i) begin
        rxc_state_q <= RXC_IDLE;
        reorder_hold_q <= cfg_fault_flags_i[6];
        for (rx_lane = 0; rx_lane < 2; rx_lane = rx_lane + 1) rx_pending[rx_lane] <= 0;
        for (rx_lane = 0; rx_lane < WINDOW_SIZE; rx_lane = rx_lane + 1) rx_final_slot[rx_lane] <= 0;
      end else if (abort_object_i || disarm_request_i || full_shutdown_request_i) begin
        rxc_state_q <= RXC_IDLE;
        reorder_hold_q <= 0;
        for (rx_lane = 0; rx_lane < 2; rx_lane = rx_lane + 1) rx_pending[rx_lane] <= 0;
      end else begin
        case (rxc_state_q)
          RXC_IDLE: begin
            // A bounded validation-only reorder holds the first completed
            // physical frame until the other logical lane also completes,
            // then submits the later sequence first.  Payload and sequence
            // metadata remain paired, so SACK fill/drain must recover without
            // altering object bytes.
            if ((rx_pending[0] || rx_pending[1]) &&
                (!reorder_hold_q || (rx_pending[0] && rx_pending[1]))) begin
              selected_lane = reorder_hold_q ?
                  ((rx_pending_sequence[1] - rx_base_sequence_o) >
                   (rx_pending_sequence[0] - rx_base_sequence_o)) :
                  !rx_pending[0];
              rxc_lane_q <= selected_lane;
              rxc_read_index_q <= 0;
              rxc_write_index_q <= 0;
              rxc_base_q <= rx_pending_sequence[selected_lane][ENTRY_WIDTH-1:0] *
                            MAX_PAYLOAD_BYTES;
              receive_distance = rx_pending_sequence[selected_lane] - rx_base_sequence_o;
              if (rx_pending_l1[selected_lane] &&
                  rx_pending_session[selected_lane] == object_session_q &&
                  receive_distance < WINDOW_SIZE &&
                  rx_pending_length[selected_lane] != 0)
                rxc_state_q <= RXC_PRIME;
              else
                rxc_state_q <= RXC_PULSE;
              if (reorder_hold_q) reorder_hold_q <= 0;
            end
          end
          RXC_PRIME: begin
            rxc_write_index_q <= 0;
            rxc_read_index_q <= 1;
            rxc_state_q <= RXC_COPY;
          end
          RXC_COPY: begin
            if (rxc_write_index_q == rx_pending_length[rxc_lane_q] - 1'b1) begin
              rx_final_slot[rx_pending_sequence[rxc_lane_q][ENTRY_WIDTH-1:0]] <=
                  rx_pending_final[rxc_lane_q];
              rxc_state_q <= RXC_PULSE;
            end else begin
              rxc_write_index_q <= rxc_write_index_q + 1'b1;
              rxc_read_index_q <= rxc_read_index_q + 1'b1;
            end
          end
          RXC_PULSE: if (dp_rx_frame_ready) begin
            dp_rx_frame_valid_q <= 1;
            dp_rx_l1_valid_q <= rx_pending_l1[rxc_lane_q];
            dp_rx_session_q <= rx_pending_session[rxc_lane_q];
            dp_rx_sequence_q <= rx_pending_sequence[rxc_lane_q];
            dp_rx_path_q <= rx_pending_path[rxc_lane_q];
            dp_rx_payload_ref_q <= rx_pending_sequence[rxc_lane_q][ENTRY_WIDTH-1:0];
            dp_rx_payload_length_q <= rx_pending_length[rxc_lane_q];
            rx_pending[rxc_lane_q] <= 0;
            rxc_state_q <= RXC_IDLE;
          end
          default: rxc_state_q <= RXC_IDLE;
        endcase
      end
    end
  end

  // ACK receive events traverse the reverse optical direction before reaching
  // the transmit window.  They are not wired directly from the local SACK.
  always @(posedge clk or negedge rst_n) begin : ack_receive
    reg ack_event;
    reg ack_crc;
    reg [31:0] ack_session_value;
    reg [15:0] ack_base_value;
    reg [31:0] ack_bitmap_value;
    reg ack_direction_value;
    if (!rst_n) begin
      dp_peer_ack_valid_q <= 0;
      dp_peer_ack_session_q <= 0;
      dp_peer_ack_base_q <= 0;
      dp_peer_ack_bitmap_q <= 0;
      dp_peer_ack_width_q <= 6'd32;
      ack_received_pulse_q <= 0;
    end else begin
      dp_peer_ack_valid_q <= 0;
      ack_received_pulse_q <= 0;
      for (rx_lane = 0; rx_lane < 2; rx_lane = rx_lane + 1) begin
        ack_event = rx_frame_valid[rx_lane] && rx_frame_ack[rx_lane];
        ack_crc = rx_frame_crc[rx_lane];
        ack_session_value = rx_frame_session[rx_lane];
        ack_base_value = rx_ack_base[rx_lane];
        ack_bitmap_value = rx_ack_bitmap[rx_lane];
        ack_direction_value = rx_ack_direction[rx_lane];
        if (ack_event && ack_crc && ack_direction_value == object_direction_q) begin
          dp_peer_ack_valid_q <= 1;
          dp_peer_ack_session_q <= ack_session_value;
          dp_peer_ack_base_q <= ack_base_value;
          dp_peer_ack_bitmap_q <= ack_bitmap_value;
          dp_peer_ack_width_q <= 6'd32;
          ack_received_pulse_q <= 1;
        end
      end
    end
  end

  // Ordered receive frames are copied to a small staging buffer and emitted
  // to AXI DMA S2MM as one byte-contiguous packet.  A payload fragment is 247
  // bytes, so emitting each fragment independently would put TKEEP=4'h7 on
  // an intermediate (non-TLAST) beat.  AXI DMA does not accept those holes as
  // a continuation of one packet: its descriptor byte accounting then loses
  // four bytes at every fragment boundary.  The pack register below carries
  // 1--3 residual bytes into the next fragment; consequently every non-final
  // beat has TKEEP=4'hf and only the object-final beat may be partial.
  reg [STORE_ADDR_WIDTH-1:0] rx_store_read_addr_q;
  reg [7:0] rx_store_read_data_q;
  always @(posedge clk) rx_store_read_data_q <= rx_store[rx_store_read_addr_q];
  // Three pad bytes make every final 32-bit AXI read in bounds.  They are
  // explicitly cleared for each fragment and masked by TKEEP.
  (* ram_style="distributed" *) reg [7:0] output_stage [0:MAX_PAYLOAD_BYTES+2];
  typedef enum reg [2:0] {
    OUT_IDLE, OUT_PRIME, OUT_COPY, OUT_STREAM, OUT_DRAIN, OUT_COMMIT
  } out_state_t;
  out_state_t out_state_q;
  reg [7:0] out_copy_index_q;
  reg [7:0] out_stream_index_q;
  reg [15:0] out_length_q;
  reg out_final_q;
  reg [31:0] out_pack_data_q;
  reg [2:0] out_pack_count_q;
  reg out_pack_valid_q;
  reg out_pack_last_q;
  reg output_complete_q;
  reg [31:0] output_bytes_q;
  assign m_axis_tvalid_o = out_pack_valid_q && !abort_object_i &&
      !disarm_request_i && !full_shutdown_request_i;
  assign m_axis_tdata_o = out_pack_data_q;
  assign m_axis_tkeep_o = out_pack_count_q == 4 ? 4'hf :
                          out_pack_count_q == 3 ? 4'h7 :
                          out_pack_count_q == 2 ? 4'h3 : 4'h1;
  assign m_axis_tlast_o = out_pack_last_q;
  assign output_complete_o = output_complete_q;
  assign output_byte_count_o = output_bytes_q;

  wire output_stage_write = out_state_q == OUT_COPY && !start_object_i &&
      !abort_object_i && !disarm_request_i && !full_shutdown_request_i;
  always @(posedge clk) begin : output_stage_memory
    if (output_stage_write)
      output_stage[out_copy_index_q] <= rx_store_read_data_q;
  end

  // Output read address directly drives the receive reorder BRAM.
  always @(posedge clk) begin : output_backend
    if (!rst_n) begin
      out_state_q <= OUT_IDLE;
      out_copy_index_q <= 0;
      out_stream_index_q <= 0;
      out_length_q <= 0;
      out_final_q <= 0;
      out_pack_data_q <= 0;
      out_pack_count_q <= 0;
      out_pack_valid_q <= 0;
      out_pack_last_q <= 0;
      output_complete_q <= 0;
      output_bytes_q <= 0;
      dp_delivery_ready_q <= 0;
      rx_store_read_addr_q <= 0;
    end else begin
      dp_delivery_ready_q <= 0;
      if (start_object_i) begin
        out_state_q <= OUT_IDLE;
        out_pack_count_q <= 0;
        out_pack_valid_q <= 0;
        out_pack_last_q <= 0;
        output_complete_q <= 0;
        output_bytes_q <= 0;
      end else if (abort_object_i || disarm_request_i || full_shutdown_request_i) begin
        out_state_q <= OUT_IDLE;
        out_pack_count_q <= 0;
        out_pack_valid_q <= 0;
        out_pack_last_q <= 0;
      end else begin
        case (out_state_q)
          OUT_IDLE: if (dp_delivery_valid) begin
            out_length_q <= dp_delivery_payload_length;
            out_final_q <= rx_final_slot[dp_delivery_payload_ref];
            out_copy_index_q <= 0;
            rx_store_read_addr_q <= dp_delivery_payload_ref * MAX_PAYLOAD_BYTES;
            out_state_q <= OUT_PRIME;
          end
          OUT_PRIME: begin
            rx_store_read_addr_q <= rx_store_read_addr_q + 1'b1;
            out_state_q <= OUT_COPY;
          end
          OUT_COPY: begin
            if (out_copy_index_q == out_length_q - 1'b1) begin
              out_stream_index_q <= 0;
              out_state_q <= OUT_STREAM;
            end else begin
              out_copy_index_q <= out_copy_index_q + 1'b1;
              rx_store_read_addr_q <= rx_store_read_addr_q + 1'b1;
            end
          end
          OUT_STREAM: begin
            if (out_pack_valid_q) begin
              if (m_axis_tvalid_o && m_axis_tready_i) begin
                output_bytes_q <= output_bytes_q + out_pack_count_q;
                out_pack_count_q <= 0;
                out_pack_valid_q <= 0;
                out_pack_last_q <= 0;
              end
            end else begin
              out_pack_data_q[8*out_pack_count_q +: 8] <=
                  output_stage[out_stream_index_q];
              if (out_stream_index_q == out_length_q - 1'b1) begin
                if (out_final_q || out_pack_count_q == 3) begin
                  out_pack_count_q <= out_pack_count_q + 1'b1;
                  out_pack_valid_q <= 1;
                  out_pack_last_q <= out_final_q;
                  out_state_q <= OUT_DRAIN;
                end else begin
                  // Keep a partial word across this non-final fragment.  It
                  // will be completed with bytes from the next delivery.
                  out_pack_count_q <= out_pack_count_q + 1'b1;
                  out_state_q <= OUT_COMMIT;
                end
              end else begin
                out_stream_index_q <= out_stream_index_q + 1'b1;
                if (out_pack_count_q == 3) begin
                  out_pack_count_q <= 4;
                  out_pack_valid_q <= 1;
                  out_pack_last_q <= 0;
                end else begin
                  out_pack_count_q <= out_pack_count_q + 1'b1;
                end
              end
            end
          end
          OUT_DRAIN: if (m_axis_tvalid_o && m_axis_tready_i) begin
            output_bytes_q <= output_bytes_q + out_pack_count_q;
            if (out_pack_last_q) output_complete_q <= 1;
            out_pack_count_q <= 0;
            out_pack_valid_q <= 0;
            out_pack_last_q <= 0;
            out_state_q <= OUT_COMMIT;
          end
          OUT_COMMIT: begin
            // Pulse registered READY for exactly one cycle.  A contiguous
            // reorder drain can keep VALID asserted while its base advances;
            // waiting for VALID to fall would therefore consume multiple
            // entries without staging them to AXI Stream.
            if (!dp_delivery_ready_q) begin
              dp_delivery_ready_q <= 1;
            end else begin
              dp_delivery_ready_q <= 0;
              out_state_q <= OUT_IDLE;
            end
          end
          default: out_state_q <= OUT_IDLE;
        endcase
      end
    end
  end

  // Safe lifecycle and object result ownership.
  integer reset_index;
  always @(posedge clk or negedge rst_n) begin : lifecycle
    if (!rst_n) begin
      receiver_enable_q <= 0;
      endpoint_armed_q <= 0;
      shutdown_latched_q <= 1;
      object_active_q <= 0;
      object_done_q <= 0;
      object_fail_q <= 0;
      object_error_q <= 0;
      object_direction_q <= 0;
      object_lane_mask_q <= 1;
      object_lane_weights_q <= 16'h0101;
      object_rate_q <= 2;
      object_session_q <= 1;
      object_path_q <= 0;
      object_id_q <= 0;
      object_initial_sequence_q <= 0;
      session_reset_pulse_q <= 0;
    end else begin
      session_reset_pulse_q <= 0;
      object_done_q <= 0;
      if (full_shutdown_request_i || any_safety_fault) begin
        receiver_enable_q <= 0;
        endpoint_armed_q <= 0;
        shutdown_latched_q <= 1;
        if (object_active_q) begin
          object_active_q <= 0;
          object_fail_q <= 1;
          object_error_q <= any_safety_fault ? 32'h5009_0002 : 32'h5009_0001;
        end
      end else begin
        if (clear_counters_i && !object_active_q) begin
          object_fail_q <= 0;
          object_error_q <= 0;
        end
        if (receiver_enable_i) begin
          receiver_enable_q <= 1;
          shutdown_latched_q <= 0;
        end
        if (disarm_request_i) begin
          endpoint_armed_q <= 0;
          if (object_active_q) begin
            object_active_q <= 0;
            object_fail_q <= 1;
            object_error_q <= 32'h5009_0008;
          end
        end else if (arm_request_i && receiver_enable_q && &phy_ready_mask_o)
          endpoint_armed_q <= 1;
        if (abort_object_i) begin
          endpoint_armed_q <= 0;
          object_active_q <= 0;
          object_fail_q <= 1;
          object_error_q <= 32'h5009_0003;
        end
        if (start_object_i) begin
          object_done_q <= 0;
          if (!endpoint_armed_q || raw_busy_q || cfg_lane_mask_i == 0 ||
              (cfg_lane_mask_i & ~cfg_lane_unavailable_i) == 0 ||
              (cfg_lane_mask_i & ~cfg_lane_unavailable_i &
               ~cfg_fault_flags_i[9:8] & ~cfg_fault_flags_i[11:10]) == 0 ||
              cfg_rate_select_i == 2'd3) begin
            object_active_q <= 0;
            object_fail_q <= 1;
            object_error_q <= 32'h5009_0005;
          end else begin
            object_active_q <= 1;
            object_fail_q <= 0;
            object_error_q <= 0;
            object_direction_q <= cfg_direction_i;
            object_lane_mask_q <= cfg_lane_mask_i;
            object_lane_weights_q <= cfg_lane_weights_i;
            object_rate_q <= cfg_rate_select_i;
            object_session_q <= cfg_session_epoch_i;
            object_path_q <= cfg_path_epoch_i;
            object_id_q <= cfg_object_id_i;
            object_initial_sequence_q <= cfg_initial_sequence_i;
            session_reset_pulse_q <= 1;
          end
        end
        if (ingress_error_pulse_q && object_active_q) begin
          object_active_q <= 0;
          object_fail_q <= 1;
          object_error_q <= 32'h5009_0006;
        end
        if (object_active_q && effective_lane_mask == 0) begin
          object_active_q <= 0;
          object_fail_q <= 1;
          object_error_q <= 32'h5009_0007;
        end
        if (object_active_q && input_complete_q && output_complete_q &&
            tx_outstanding_count_o == 0 && !allocate_pending_q &&
            !duplicate_ack_validation_pending_q) begin
          object_active_q <= 0;
          object_done_q <= 1;
        end
        if (tx_retry_exhausted_count_o != 0 && object_active_q) begin
          object_active_q <= 0;
          object_fail_q <= 1;
          object_error_q <= 32'h5009_0004;
        end
      end
    end
  end
endmodule

`default_nettype wire
