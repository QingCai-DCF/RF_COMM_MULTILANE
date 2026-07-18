`timescale 1ns/1ps
`default_nettype none

// Parameterized OOC-only architecture wrapper.  The three audited profiles set
// PHYSICAL_MODULE_COUNT to 2/8/32 while keeping one shared P8D data plane.  This
// wrapper has no board pins and is never a hardware-run top.
module ir_p8d_resource_top #(
  parameter integer LANE_COUNT=8,
  parameter integer WINDOW_SIZE=64,
  parameter integer SACK_BITS=64,
  parameter integer DATA_WIDTH=64,
  parameter integer PHYSICAL_MODULE_COUNT=8
) (
  input  wire clk,input wire rst_n,input wire global_permit_i,input wire endpoint_armed_i,
  input  wire tx_request_i,input wire rx_request_i,input wire ack_valid_i,input wire abort_i,
  input  wire [15:0] payload_length_i,input wire [15:0] sequence_i,
  input  wire [$clog2(WINDOW_SIZE)-1:0] descriptor_index_i,
  input  wire [DATA_WIDTH-1:0] s_axis_tdata_i,
  input  wire [DATA_WIDTH/8-1:0] s_axis_tkeep_i,
  input  wire s_axis_tvalid_i,input wire s_axis_tlast_i,
  input  wire [$clog2((288+(DATA_WIDTH/8)-1)/(DATA_WIDTH/8))-1:0] payload_beat_i,
  input  wire [5:0] tx_complete_index_i,input wire [15:0] tx_complete_generation_i,
  input  wire tx_complete_valid_i,input wire [5:0] rx_complete_index_i,
  input  wire [15:0] rx_complete_generation_i,input wire rx_complete_valid_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0] safety_frame_admitted_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0] safety_waveform_i,
  output wire [PHYSICAL_MODULE_COUNT-1:0] safety_txd_o,
  output wire physical_attempt_valid_o,
  output wire [$clog2(LANE_COUNT)-1:0] physical_attempt_lane_o,
  output wire [15:0] physical_attempt_sequence_o,
  output wire s_axis_tready_o,output wire m_axis_tvalid_o,
  output wire [DATA_WIDTH-1:0] m_axis_tdata_o,
  output wire [DATA_WIDTH/8-1:0] m_axis_tkeep_o,output wire m_axis_tlast_o,
  output wire [DATA_WIDTH-1:0] payload_read_data_o,
  output wire [DATA_WIDTH/8-1:0] payload_read_keep_o,
  output wire ring_status_o,output wire architecture_status_o
);
  localparam logic [$clog2(SACK_BITS):0] SACK_WIDTH_VALUE=SACK_BITS;
  localparam logic [15:0] WINDOW_CREDIT_VALUE=WINDOW_SIZE;
  wire [15:0] tx_next,tx_ack_base,rx_base;
  wire [$clog2(WINDOW_SIZE+1)-1:0] outstanding,outstanding_hwm,rx_credit;
  wire [SACK_BITS-1:0] rx_sack;
  wire [31:0] attempts,retries,exhausted,timeouts,duplicate_acks,stale_acks,bad_acks;
  wire [31:0] migrations,rx_duplicates,rx_stale_session,rx_stale_path;
  wire [31:0] ack_aggregation_count,ack_timer_expiry_count,ack_frames_sent;
  wire [3:0] scheduler_last_defer_reason;
  wire [LANE_COUNT*32-1:0] scheduled_frames,scheduled_bytes,lane_retries,lane_migrations;
  wire [31:0] starvation;
  wire physical_attempt_ready;
  assign physical_attempt_ready=1'b1;

  ir_data_plane_top #(.LANE_COUNT(LANE_COUNT),.WINDOW_SIZE(WINDOW_SIZE),
    .SACK_BITS(SACK_BITS)) data_plane (
    .clk,.rst_n,.clear_counters_i(1'b0),.session_reset_i(1'b0),.abort_all_i(abort_i),
    .session_epoch_i(32'd1),.path_epoch_i(16'd1),.path_epoch_valid_i(1'b1),
    .lane_weights_i({LANE_COUNT{8'h01}}),.active_lane_mask_i({LANE_COUNT{1'b1}}),
    .lane_ready_i({LANE_COUNT{1'b1}}),.lane_health_i({LANE_COUNT{1'b1}}),
    .mapping_valid_i({LANE_COUNT{1'b1}}),.frame_admission_i({LANE_COUNT{1'b1}}),
    .lane_tx_permit_i({LANE_COUNT{1'b1}}),.duty_headroom_i({LANE_COUNT{1'b1}}),
    .fault_free_i({LANE_COUNT{1'b1}}),.global_permit_effective_i(global_permit_i),
    .endpoint_armed_i,.tx_kill_active_i(1'b0),.peer_receiver_credit_i(WINDOW_CREDIT_VALUE),
    .tx_allocate_valid_i(tx_request_i),.tx_allocate_ready_o(),
    .tx_allocate_payload_ref_i({{(16-$clog2(WINDOW_SIZE)){1'b0}},descriptor_index_i}),
    .tx_allocate_payload_length_i(payload_length_i),
    .tx_allocate_descriptor_i({{(16-$clog2(WINDOW_SIZE)){1'b0}},descriptor_index_i}),
    .tx_allocate_priority_i(3'd0),.tx_allocate_pulse_o(),.tx_allocated_sequence_o(),
    .physical_attempt_valid_o,.physical_attempt_ready_i(physical_attempt_ready),
    .physical_attempt_entry_o(),.physical_attempt_sequence_o,
    .physical_attempt_payload_ref_o(),.physical_attempt_payload_length_o(),
    .physical_attempt_descriptor_o(),.physical_attempt_lane_o,
    .physical_attempt_path_epoch_o(),.physical_attempt_is_retry_o(),
    .peer_ack_valid_i(ack_valid_i),.peer_ack_session_epoch_i(32'd1),
    .peer_ack_base_i(sequence_i),.peer_ack_bitmap_i({SACK_BITS{1'b0}}),
    .peer_ack_width_i(SACK_WIDTH_VALUE),.rx_frame_valid_i(rx_request_i),
    .rx_frame_ready_o(),.rx_l1_valid_i(1'b1),.rx_session_epoch_i(32'd1),
    .rx_sequence_i(sequence_i),.rx_path_epoch_i(16'd1),
    .rx_payload_ref_i({{(16-$clog2(WINDOW_SIZE)){1'b0}},descriptor_index_i}),
    .rx_payload_length_i(payload_length_i),.rx_delivery_valid_o(),
    .rx_delivery_ready_i(1'b1),.rx_delivery_sequence_o(),.rx_delivery_payload_ref_o(),
    .rx_delivery_payload_length_o(),.ack_control_event_i(1'b0),
    .ack_direction_boundary_i(1'b0),.ack_explicit_request_i(1'b0),
    .local_ack_valid_o(),.local_ack_ready_i(1'b1),.local_ack_session_epoch_o(),
    .local_ack_base_o(),.local_ack_bitmap_o(),.local_ack_width_o(),
    .local_ack_receiver_credit_o(),.tx_next_sequence_o(tx_next),.tx_ack_base_o(tx_ack_base),
    .tx_outstanding_count_o(outstanding),.tx_outstanding_high_watermark_o(outstanding_hwm),
    .rx_base_sequence_o(rx_base),.rx_sack_bitmap_o(rx_sack),.rx_receiver_credit_o(rx_credit),
    .tx_attempt_count_o(attempts),.tx_retry_count_o(retries),
    .tx_retry_exhausted_count_o(exhausted),.tx_timeout_count_o(timeouts),
    .tx_duplicate_ack_count_o(duplicate_acks),.tx_stale_ack_count_o(stale_acks),
    .tx_out_of_window_ack_count_o(bad_acks),.tx_migration_count_o(migrations),
    .rx_duplicate_count_o(rx_duplicates),.rx_stale_session_count_o(rx_stale_session),
    .rx_stale_path_count_o(rx_stale_path),.scheduler_frames_flat_o(scheduled_frames),
    .scheduler_bytes_flat_o(scheduled_bytes),.scheduler_retries_flat_o(lane_retries),
    .scheduler_migrations_flat_o(lane_migrations),.scheduler_maximum_starvation_o(starvation),
    .ack_aggregation_count_o(ack_aggregation_count),
    .ack_timer_expiry_count_o(ack_timer_expiry_count),.ack_frames_sent_o(ack_frames_sent),
    .scheduler_last_defer_reason_o(scheduler_last_defer_reason)
  );

  wire axis_complete,axis_error;
  wire [31:0] axis_stalls,axis_errors,axis_packets;
  ir_axis_tx_frontend #(.DATA_WIDTH(DATA_WIDTH),.USER_WIDTH(64)) axis_frontend (
    .clk,.rst_n,.clear_counters_i(1'b0),.descriptor_valid_i(tx_request_i),
    .descriptor_ready_o(),.descriptor_length_i(payload_length_i),
    .descriptor_user_i({48'd0,sequence_i}),.s_axis_tvalid_i,
    .s_axis_tready_o,.s_axis_tdata_i,.s_axis_tkeep_i,.s_axis_tlast_i,
    .s_axis_tuser_i({48'd0,sequence_i}),.m_axis_tvalid_o,
    .m_axis_tready_i(1'b1),.m_axis_tdata_o,.m_axis_tkeep_o,.m_axis_tlast_o,
    .m_axis_tuser_o(),.descriptor_complete_pulse_o(axis_complete),
    .protocol_error_pulse_o(axis_error),.stall_cycles_o(axis_stalls),
    .protocol_error_count_o(axis_errors),.packet_count_o(axis_packets)
  );

  wire tx_hw_valid,rx_hw_valid,tx_cpu_valid,rx_cpu_valid;
  wire [5:0] tx_hw_index,rx_hw_index,tx_cpu_index,rx_cpu_index;
  wire [15:0] tx_hw_generation,rx_hw_generation,tx_cpu_generation,rx_cpu_generation;
  wire [63:0] tx_hw_address,rx_hw_address;
  wire [31:0] tx_hw_length,rx_hw_length,tx_hw_tag,rx_hw_tag;
  wire [31:0] tx_cpu_actual,rx_cpu_actual,tx_cpu_tag,rx_cpu_tag;
  wire [15:0] tx_cpu_status,rx_cpu_status,tx_cpu_error,rx_cpu_error;
  wire [31:0] tx_producer,rx_producer,tx_hw_consumer,rx_hw_consumer;
  wire [31:0] tx_cpu_consumer,rx_cpu_consumer;
  wire [15:0] tx_generation,rx_generation;
  wire [6:0] tx_occupancy,rx_occupancy,tx_hwm,rx_hwm,tx_leaks,rx_leaks;
  wire [31:0] tx_full,rx_full,tx_completions,rx_completions,tx_errors,rx_errors;
  wire [31:0] tx_aborts,rx_aborts,tx_stale,rx_stale;

  ir_dma_descriptor_model #(.RING_DEPTH(64)) tx_ring (
    .clk,.rst_n,.clear_counters_i(1'b0),.soft_reset_i(1'b0),.abort_i(abort_i),
    .cpu_prepare_valid_i(tx_request_i),.cpu_prepare_ready_o(),
    .cpu_buffer_address_i({{(48-$clog2(WINDOW_SIZE)){1'b0}},descriptor_index_i,16'd0}),
    .cpu_buffer_capacity_i(32'd288),.cpu_requested_length_i(payload_length_i),
    .cpu_user_tag_i({16'd0,sequence_i}),.cpu_session_epoch_i(32'd1),
    .hw_descriptor_valid_o(tx_hw_valid),.hw_descriptor_ready_i(physical_attempt_ready),
    .hw_descriptor_index_o(tx_hw_index),.hw_descriptor_generation_o(tx_hw_generation),
    .hw_buffer_address_o(tx_hw_address),.hw_requested_length_o(tx_hw_length),
    .hw_user_tag_o(tx_hw_tag),.hw_complete_valid_i(tx_complete_valid_i),
    .hw_complete_index_i(tx_complete_index_i),.hw_complete_generation_i(tx_complete_generation_i),
    .hw_actual_length_i(payload_length_i),.hw_error_code_i(16'd0),
    .hw_complete_accept_pulse_o(),.hw_complete_reject_pulse_o(),
    .cpu_completion_valid_o(tx_cpu_valid),.cpu_completion_ready_i(1'b1),
    .cpu_completion_index_o(tx_cpu_index),.cpu_completion_generation_o(tx_cpu_generation),
    .cpu_actual_length_o(tx_cpu_actual),.cpu_completion_user_tag_o(tx_cpu_tag),
    .cpu_completion_status_o(tx_cpu_status),.cpu_completion_error_o(tx_cpu_error),
    .producer_count_o(tx_producer),.hardware_consumer_count_o(tx_hw_consumer),
    .cpu_consumer_count_o(tx_cpu_consumer),.generation_o(tx_generation),
    .occupancy_o(tx_occupancy),.high_watermark_o(tx_hwm),.ring_full_count_o(tx_full),
    .completion_count_o(tx_completions),.error_count_o(tx_errors),.abort_count_o(tx_aborts),
    .stale_generation_count_o(tx_stale),.descriptor_leak_count_o(tx_leaks)
  );
  ir_dma_descriptor_model #(.RING_DEPTH(64)) rx_ring (
    .clk,.rst_n,.clear_counters_i(1'b0),.soft_reset_i(1'b0),.abort_i(abort_i),
    .cpu_prepare_valid_i(rx_request_i),.cpu_prepare_ready_o(),
    .cpu_buffer_address_i({{(48-$clog2(WINDOW_SIZE)){1'b0}},descriptor_index_i,16'd0}),
    .cpu_buffer_capacity_i(32'd288),.cpu_requested_length_i(payload_length_i),
    .cpu_user_tag_i({16'd0,sequence_i}),.cpu_session_epoch_i(32'd1),
    .hw_descriptor_valid_o(rx_hw_valid),.hw_descriptor_ready_i(1'b1),
    .hw_descriptor_index_o(rx_hw_index),.hw_descriptor_generation_o(rx_hw_generation),
    .hw_buffer_address_o(rx_hw_address),.hw_requested_length_o(rx_hw_length),
    .hw_user_tag_o(rx_hw_tag),.hw_complete_valid_i(rx_complete_valid_i),
    .hw_complete_index_i(rx_complete_index_i),.hw_complete_generation_i(rx_complete_generation_i),
    .hw_actual_length_i(payload_length_i),.hw_error_code_i(16'd0),
    .hw_complete_accept_pulse_o(),.hw_complete_reject_pulse_o(),
    .cpu_completion_valid_o(rx_cpu_valid),.cpu_completion_ready_i(1'b1),
    .cpu_completion_index_o(rx_cpu_index),.cpu_completion_generation_o(rx_cpu_generation),
    .cpu_actual_length_o(rx_cpu_actual),.cpu_completion_user_tag_o(rx_cpu_tag),
    .cpu_completion_status_o(rx_cpu_status),.cpu_completion_error_o(rx_cpu_error),
    .producer_count_o(rx_producer),.hardware_consumer_count_o(rx_hw_consumer),
    .cpu_consumer_count_o(rx_cpu_consumer),.generation_o(rx_generation),
    .occupancy_o(rx_occupancy),.high_watermark_o(rx_hwm),.ring_full_count_o(rx_full),
    .completion_count_o(rx_completions),.error_count_o(rx_errors),.abort_count_o(rx_aborts),
    .stale_generation_count_o(rx_stale),.descriptor_leak_count_o(rx_leaks)
  );

  wire store_allocate_ready,store_error;
  wire [$clog2(WINDOW_SIZE+1)-1:0] store_used,store_hwm;
  ir_shared_payload_store #(.ENTRY_COUNT(WINDOW_SIZE),.MAX_FRAME_BYTES(288),
    .DATA_WIDTH(DATA_WIDTH)) payload_store (
    .clk,.rst_n,.allocate_valid_i(tx_request_i),.allocate_ready_o(store_allocate_ready),
    .allocate_entry_i(descriptor_index_i),.release_valid_i(ack_valid_i),
    .release_entry_i(descriptor_index_i),.write_valid_i(s_axis_tvalid_i),
    .write_entry_i(descriptor_index_i),.write_beat_i(payload_beat_i),
    .write_data_i(s_axis_tdata_i),.write_keep_i(s_axis_tkeep_i),
    .read_valid_i(rx_request_i),.read_entry_i(descriptor_index_i),
    .read_beat_i(payload_beat_i),.read_data_o(payload_read_data_o),
    .read_keep_o(payload_read_keep_o),.used_entries_o(store_used),
    .high_watermark_o(store_hwm),.ownership_error_sticky_o(store_error)
  );

  wire safety_status;
  ir_p8c_resource_top #(.PHYSICAL_MODULE_COUNT(PHYSICAL_MODULE_COUNT)) safety_accounting (
    .clk,.rst_n,.global_permit_i,.arm_request_i(endpoint_armed_i),
    .frame_admitted_i(safety_frame_admitted_i),.waveform_i(safety_waveform_i),
    .txd_o(safety_txd_o),.safety_status_o(safety_status)
  );

  assign ring_status_o=^{tx_hw_valid,rx_hw_valid,tx_cpu_valid,rx_cpu_valid,
    tx_hw_index,rx_hw_index,tx_hw_generation,rx_hw_generation,tx_hw_address,rx_hw_address,
    tx_hw_length,rx_hw_length,tx_hw_tag,rx_hw_tag,tx_cpu_index,rx_cpu_index,
    tx_cpu_generation,rx_cpu_generation,tx_cpu_actual,rx_cpu_actual,tx_cpu_tag,rx_cpu_tag,
    tx_cpu_status,rx_cpu_status,tx_cpu_error,rx_cpu_error,tx_producer,rx_producer,
    tx_hw_consumer,rx_hw_consumer,tx_cpu_consumer,rx_cpu_consumer,tx_generation,rx_generation,
    tx_occupancy,rx_occupancy,tx_hwm,rx_hwm,tx_full,rx_full,tx_completions,rx_completions,
    tx_errors,rx_errors,tx_aborts,rx_aborts,tx_stale,rx_stale,tx_leaks,rx_leaks};
  assign architecture_status_o=^{tx_next,tx_ack_base,rx_base,outstanding,outstanding_hwm,
    rx_credit,rx_sack,attempts,retries,exhausted,timeouts,duplicate_acks,stale_acks,bad_acks,
    migrations,rx_duplicates,rx_stale_session,rx_stale_path,scheduled_frames,scheduled_bytes,
    lane_retries,lane_migrations,starvation,axis_complete,axis_error,axis_stalls,axis_errors,
    axis_packets,ack_aggregation_count,ack_timer_expiry_count,ack_frames_sent,
    scheduler_last_defer_reason,store_allocate_ready,store_used,store_hwm,store_error,safety_status};
endmodule
`default_nettype wire
