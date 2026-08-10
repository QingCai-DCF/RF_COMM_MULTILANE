`timescale 1ns/1ps
`default_nettype none

module p9_optical_transport_core #(
  parameter integer CLK_HZ = 64_000_000,
  parameter integer LANE_COUNT = 2,
  parameter integer WINDOW_SIZE = 32,
  parameter integer SACK_BITS = 32,
  parameter integer MAX_PAYLOAD_BYTES = 247,
  parameter integer STORE_ADDR_WIDTH = 13,
  parameter integer RTO_CYCLES = 4_000_000,
  // P10.1R's four-module calibration observed no post-TX raw edge.  Keep the
  // measured 4,096-cycle deterministic margin plus the independent 256-cycle
  // idle qualification before a reverse frame can begin.
  parameter integer ACK_TURNAROUND_GUARD_CYCLES = 4_352,
  // P10.1R freezes one cumulative ACK per full 32-frame bundle window.  P9
  // dual-fixture builds retain their historical threshold at the data-plane
  // parameter boundary below.
  parameter integer ACK_FRAME_THRESHOLD = 32,
  parameter integer ACK_MAX_DELAY_CYCLES = 64_000,
  // Independent P10.1R endpoints use a proved frame-boundary schedule.  At
  // 64 MHz and 4 Mbit/s, a maximum DATA frame occupies 1,116 32-cycle symbol
  // slots.  A 17,984-cycle (562-slot) post-frame guard bounds every 1 ms
  // window to at most 1,439 pulse intersections, or 11,512 high cycles.  That
  // remains strictly below the exact accountant's 11,520-cycle 18% threshold.
  // The first DATA frame after reset, raw mode, fault, shutdown, abort, or a
  // direction change still waits for an empty exact-duty history.  P9's
  // monolithic role retains its historical 20,480-cycle guard below.
  parameter integer FRAME_DUTY_GUARD_CYCLES = 17_984,
  // 0 keeps the frozen P9 single-FPGA fixture behavior. P10 instantiates one
  // physical endpoint per AX7020: 1 owns side A (fixed), 2 owns side B
  // (rotating role). The two instances exchange DATA and ACK frames only
  // through independent TFDU pins; no payload RAM is shared between nodes.
  parameter integer DEPLOYMENT_ROLE = 0,
  // Independent endpoints use a bounded DATA burst followed by an explicit
  // turnaround-request flag. The receiver suppresses timer ACK transmission
  // until that boundary, preventing DATA/ACK optical collisions without a
  // shared scheduler or shared memory between the two FPGAs.
  parameter integer ENDPOINT_BURST_FRAMES = 32,
  // Hardware-selected bound: measured maximum post-TX echo tail (zero cycles
  // in 1,000 samples on each of F0/F1/R0/R1) plus 4,096-cycle margin.
  parameter integer RX_MIN_POST_TX_GUARD_CYCLES = 4_096,
  parameter integer RX_IDLE_QUALIFY_CYCLES = 256,
  parameter integer RX_MAX_QUARANTINE_CYCLES = 131_072,
  parameter integer P10_5_DUAL_CAPABLE = 0
) (
  input  wire         clk,
  input  wire         rst_n,

  input  wire         receiver_enable_i,
  input  wire         arm_request_i,
  input  wire         disarm_request_i,
  input  wire         full_shutdown_request_i,
  // Persistent first-fault hold from the reset-independent forensic domain.
  // It may only add shutdown/TX kill; it is never an enable or permit.
  input  wire         forensic_fault_hold_i,
  input  wire         clear_counters_i,
  input  wire         start_object_i,
  input  wire         abort_object_i,
  input  wire [LANE_COUNT-1:0] cfg_lane_mask_i,
  input  wire [LANE_COUNT*8-1:0] cfg_lane_weights_i,
  input  wire [1:0]   cfg_rate_select_i,
  input  wire         cfg_direction_i,
  input  wire [31:0]  cfg_session_epoch_i,
  input  wire [15:0]  cfg_path_epoch_i,
  input  wire [31:0]  cfg_object_id_i,
  input  wire [15:0]  cfg_initial_sequence_i,
  input  wire [31:0]  cfg_fault_flags_i,
  input  wire [7:0]   cfg_drop_data_count_i,
  input  wire [7:0]   cfg_drop_ack_count_i,
  input  wire [LANE_COUNT-1:0] cfg_lane_unavailable_i,
  // P10.5 split-lane simultaneous bidirectional context. Legacy builds set
  // P10_5_DUAL_CAPABLE=0 and ignore these appended ports at elaboration.
  input  wire         cfg_p10_5_dual_direction_i,
  input  wire [LANE_COUNT-1:0] cfg_tx_lane_mask_i,
  input  wire [LANE_COUNT-1:0] cfg_rx_lane_mask_i,
  input  wire [15:0]  cfg_role_epoch_i,
  input  wire [31:0]  cfg_rx_session_epoch_i,
  input  wire [15:0]  cfg_rx_path_epoch_i,
  input  wire [31:0]  cfg_rx_object_id_i,
  input  wire [15:0]  cfg_rx_initial_sequence_i,
  input  wire         abort_tx_context_i,
  input  wire         abort_rx_context_i,
  // P10.4 validation-only source-ID injection.  The peripheral may pulse
  // these bits only while the endpoint is fully shut down, TX-killed, and
  // idle.  The pulse enters the source-ID rejection predicate directly; it
  // cannot create a physical frame, RX delivery, or application commit.
  input  wire [LANE_COUNT-1:0] local_source_test_inject_i,

  input  wire         raw_start_i,
  input  wire         raw_direction_i,
  input  wire [LANE_COUNT-1:0] raw_lane_mask_i,
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

  input  wire [LANE_COUNT-1:0] a_rxd_i,
  output wire [LANE_COUNT-1:0] a_txd_o,
  output wire [LANE_COUNT-1:0] a_sd_o,
  output wire [LANE_COUNT-1:0] a_mode_o,
  input  wire [LANE_COUNT-1:0] b_rxd_i,
  output wire [LANE_COUNT-1:0] b_txd_o,
  output wire [LANE_COUNT-1:0] b_sd_o,
  output wire [LANE_COUNT-1:0] b_mode_o,

  output wire         endpoint_armed_o,
  output wire         tx_kill_active_o,
  output wire [2*LANE_COUNT-1:0] phy_ready_mask_o,
  output wire [2*LANE_COUNT-1:0] startup_done_mask_o,
  output wire [2*LANE_COUNT-1:0] safety_fault_mask_o,
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
  // P10.4 direct stall semantics.  These are instantaneous predicates for
  // the performance monitor, not reconstructed host-side classifications.
  output wire         tx_idle_due_to_ack_o,
  output wire         window_full_stall_o,
  output wire         receiver_credit_stall_o,
  output wire         direction_turnaround_idle_o,
  output wire [LANE_COUNT*32-1:0] scheduler_frames_flat_o,
  output wire [LANE_COUNT*32-1:0] scheduler_bytes_flat_o,
  output wire [LANE_COUNT*32-1:0] scheduler_retries_flat_o,
  output wire [LANE_COUNT*32-1:0] scheduler_migrations_flat_o,
  output wire [31:0]  scheduler_maximum_starvation_o,
  output wire [31:0]  physical_data_frames_good_o,
  output wire [31:0]  physical_ack_frames_good_o,
  output wire [31:0]  physical_crc_bad_o,
  output wire [31:0]  physical_frame_bad_o,
  output wire [31:0]  physical_preamble_count_o,
  output wire [31:0]  physical_symbol_error_count_o,
  output wire [LANE_COUNT*32-1:0] physical_data_good_by_lane_o,
  output wire [LANE_COUNT*32-1:0] physical_ack_good_by_lane_o,
  output wire [LANE_COUNT*32-1:0] physical_crc_bad_by_lane_o,
  output wire [LANE_COUNT*32-1:0] physical_frame_bad_by_lane_o,
  output wire [LANE_COUNT*32-1:0] physical_preamble_by_lane_o,
  output wire [LANE_COUNT*32-1:0] physical_symbol_error_by_lane_o,
  output wire [LANE_COUNT-1:0] valid_rx_frame_activity_o,
  output wire         effective_full_shutdown_o,
  output wire [31:0]  physical_drop_data_count_o,
  output wire [31:0]  physical_drop_ack_count_o,
  output wire [2*LANE_COUNT*32-1:0] raw_rx_counts_flat_o,
  output wire [2*LANE_COUNT*32-1:0] physical_tx_counts_flat_o,
  output wire [2*LANE_COUNT*32-1:0] tx_high_current_flat_o,
  output wire [2*LANE_COUNT*32-1:0] tx_high_max_flat_o,
  output wire [2*LANE_COUNT*32-1:0] duty_high_max_flat_o,
  output wire [2*LANE_COUNT*32-1:0] duty_high_current_flat_o,
  output wire [2*LANE_COUNT*32-1:0] duty_headroom_flat_o,
  output wire [2*LANE_COUNT*32-1:0] duty_target_throttle_count_flat_o,
  output wire [2*LANE_COUNT*32-1:0] duty_hard_fault_count_flat_o,
  output wire [31:0]  duty_window_cycles_o,
  output wire [31:0]  duty_hard_limit_cycles_o,
  output wire [31:0]  duty_target_limit_cycles_o,
  // Validation-only atomic retry-migration evidence.  This path can only
  // restrict scheduler lane eligibility; it never creates permit, PHY
  // readiness, duty headroom, or a physical TX request.
  output wire [LANE_COUNT-1:0] effective_lane_unavailable_o,
  output wire         auto_migration_armed_o,
  output wire         auto_migration_triggered_o,
  output wire [LANE_COUNT-1:0] auto_migration_target_mask_o,
  output wire [15:0]  auto_migration_trigger_sequence_o,
  output wire [15:0]  auto_migration_trigger_ack_base_o,
  output wire [5:0]   auto_migration_trigger_outstanding_o,
  output wire [31:0]  auto_migration_trigger_attempt_count_o,
  output wire [31:0]  auto_migration_trigger_physical_tx_count_o,
  output wire [31:0]  auto_migration_trigger_count_o,
  output wire [31:0]  auto_migration_trigger_migration_count_o,
  output wire [31:0]  auto_migration_trigger_scheduled_count_o,
  output wire [31:0]  rx_admission_status_o,
  output wire [LANE_COUNT*32-1:0] rx_raw_while_local_tx_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_blanked_raw_pulse_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_blanked_frame_start_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_blanked_crc_valid_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_local_source_reject_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_accepted_remote_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_guard_total_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_guard_max_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_echo_tail_max_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_last_txd_rise_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_last_txd_fall_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_first_rxd_after_tx_flat_o,
  output wire [LANE_COUNT*32-1:0] rx_last_rxd_after_tx_flat_o,
  output wire [31:0]  rx_overlap_violation_count_o,
  output wire [31:0]  rx_admission_violation_count_o,
  output wire [31:0]  rx_non_target_accepted_count_o,
  output wire [31:0]  rx_cross_lane_accepted_count_o,
  output wire [LANE_COUNT*32-1:0] rx_decoder_clear_count_flat_o,
  output wire         p10_5_dual_direction_active_o,
  output wire [LANE_COUNT-1:0] p10_5_tx_lane_mask_o,
  output wire [LANE_COUNT-1:0] p10_5_rx_lane_mask_o,
  output wire [15:0]  p10_5_role_epoch_o,
  output wire [31:0]  p10_5_piggyback_ack_tx_count_o,
  output wire [31:0]  p10_5_piggyback_ack_rx_count_o,
  output wire [31:0]  p10_5_control_ack_fallback_count_o,
  output wire [31:0]  p10_5_direction_reject_count_o,
  output wire [31:0]  p10_5_role_epoch_reject_count_o,
  output wire         p10_5_tx_context_aborted_o,
  output wire         p10_5_rx_context_aborted_o,
  output wire [5:0]   p10_5_rx_receiver_credit_o,
  output wire [15:0]  p10_5_peer_receiver_credit_o,
  output wire [15:0]  p10_5_peer_ack_base_o,
  output wire [31:0]  p10_5_peer_ack_bitmap_o,
  output wire [1:0]   p10_5_control_queue_occupancy_o,
  output wire [31:0]  p10_5_tx_axis_stall_count_o,
  output wire [31:0]  p10_5_rx_axis_stall_count_o
);
  import ir_seq_math_pkg::*;

  localparam integer STORE_BYTES = WINDOW_SIZE * MAX_PAYLOAD_BYTES;
  localparam integer ENTRY_WIDTH = $clog2(WINDOW_SIZE);
  localparam integer LANE_WIDTH = $clog2(LANE_COUNT);
  localparam integer ROLE_P9_DUAL = 0;
  localparam integer ROLE_FIXED_A = 1;
  localparam integer ROLE_ROTATING_B = 2;
  localparam integer AUTO_MIGRATION_ENABLE_BIT = 16;
  localparam integer AUTO_MIGRATION_TARGET_LSB = 17;
  localparam integer ENDPOINT_MIN_FRAME_DUTY_GUARD_CYCLES = 17_984;
  localparam integer ENDPOINT_MAX_DATA_FRAME_SYMBOLS =
      P10_5_DUAL_CAPABLE != 0 ? 1_180 : 1_116;
  localparam integer ENDPOINT_DUTY_WINDOW_SYMBOLS = 2_000;
  localparam integer ENDPOINT_MAX_WINDOW_PULSE_INTERSECTIONS =
      ENDPOINT_DUTY_WINDOW_SYMBOLS -
      ENDPOINT_MIN_FRAME_DUTY_GUARD_CYCLES / 32 + 1;
  localparam integer ENDPOINT_MAX_WINDOW_HIGH_CYCLES =
      ENDPOINT_MAX_WINDOW_PULSE_INTERSECTIONS * 8;
  localparam integer ENDPOINT_TARGET_HIGH_CYCLES = 11_520;
  localparam integer EFFECTIVE_FRAME_DUTY_GUARD_CYCLES =
      DEPLOYMENT_ROLE == ROLE_P9_DUAL ? 20_480 : FRAME_DUTY_GUARD_CYCLES;
  localparam integer EFFECTIVE_ACK_TURNAROUND_GUARD_CYCLES =
      DEPLOYMENT_ROLE == ROLE_P9_DUAL ? 4_096 :
      ACK_TURNAROUND_GUARD_CYCLES;
  localparam integer FRAME_DUTY_GUARD_WIDTH =
      (EFFECTIVE_FRAME_DUTY_GUARD_CYCLES < 1) ? 1 :
      $clog2(EFFECTIVE_FRAME_DUTY_GUARD_CYCLES + 1);

  initial begin
    if (LANE_COUNT != 2 && LANE_COUNT != 4 && LANE_COUNT != 8)
      $error("LANE_COUNT must be 2, 4, or 8");
    if (SACK_BITS != 32)
      $error("P10.2 freezes the unchanged 32-bit ACK wire format");
    if (DEPLOYMENT_ROLE < ROLE_P9_DUAL || DEPLOYMENT_ROLE > ROLE_ROTATING_B)
      $error("DEPLOYMENT_ROLE must be 0 (P9 dual), 1 (fixed A), or 2 (rotating B)");
    if (ENDPOINT_BURST_FRAMES < 1 || ENDPOINT_BURST_FRAMES > WINDOW_SIZE)
      $error("ENDPOINT_BURST_FRAMES must be within the selective-repeat window");
    if (DEPLOYMENT_ROLE != ROLE_P9_DUAL &&
        (ACK_MAX_DELAY_CYCLES < 1 || ACK_MAX_DELAY_CYCLES >= RTO_CYCLES))
      $error("endpoint ACK fallback must be positive and below the retransmission timeout");
    if (DEPLOYMENT_ROLE != ROLE_P9_DUAL && CLK_HZ != 64_000_000)
      $error("P10.1R frame-boundary duty proof requires the canonical 64 MHz clock");
    if (DEPLOYMENT_ROLE != ROLE_P9_DUAL &&
        FRAME_DUTY_GUARD_CYCLES < ENDPOINT_MIN_FRAME_DUTY_GUARD_CYCLES)
      $error("P10.1R endpoint frame-duty guard is below the proved minimum");
    if (DEPLOYMENT_ROLE != ROLE_P9_DUAL &&
        ENDPOINT_DUTY_WINDOW_SYMBOLS <
        ENDPOINT_MAX_DATA_FRAME_SYMBOLS +
        ENDPOINT_MIN_FRAME_DUTY_GUARD_CYCLES / 32)
      $error("P10.1R duty proof assumes one complete DATA run and guard per window");
    if (DEPLOYMENT_ROLE != ROLE_P9_DUAL &&
        ENDPOINT_DUTY_WINDOW_SYMBOLS >=
        2 * (ENDPOINT_MAX_DATA_FRAME_SYMBOLS +
             ENDPOINT_MIN_FRAME_DUTY_GUARD_CYCLES / 32))
      $error("P10.1R duty proof assumes at most one complete DATA run per window");
    if (DEPLOYMENT_ROLE != ROLE_P9_DUAL &&
        ENDPOINT_MAX_WINDOW_HIGH_CYCLES >= ENDPOINT_TARGET_HIGH_CYCLES)
      $error("P10.1R frame-boundary duty proof does not close below 18 percent");
  end

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

  function automatic [31:0] sat_inc32(input [31:0] value);
    begin
      sat_inc32 = (&value) ? value : value + 32'd1;
    end
  endfunction

  function automatic [31:0] sat_add2_32(
    input [31:0] value, input [1:0] increment
  );
    reg [32:0] sum;
    begin
      sum = {1'b0, value} + {{31{1'b0}}, increment};
      sat_add2_32 = sum[32] ? 32'hFFFF_FFFF : sum[31:0];
    end
  endfunction

  function automatic [31:0] sat_add32(
    input [31:0] left, input [31:0] right
  );
    reg [32:0] sum;
    begin
      sum = {1'b0, left} + {1'b0, right};
      sat_add32 = sum[32] ? 32'hFFFF_FFFF : sum[31:0];
    end
  endfunction

  function automatic [LANE_WIDTH-1:0] first_set_lane(
    input [LANE_COUNT-1:0] mask
  );
    integer lane_index;
    reg found;
    begin
      first_set_lane = {LANE_WIDTH{1'b0}};
      found = 1'b0;
      for (lane_index = 0; lane_index < LANE_COUNT;
           lane_index = lane_index + 1) begin
        if (mask[lane_index] && !found) begin
          first_set_lane = lane_index[LANE_WIDTH-1:0];
          found = 1'b1;
        end
      end
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
  reg object_dual_direction_q;
  reg [LANE_COUNT-1:0] object_tx_lane_mask_q;
  reg [LANE_COUNT-1:0] object_rx_lane_mask_q;
  reg [15:0] object_role_epoch_q;
  reg [31:0] object_rx_session_q;
  reg [15:0] object_rx_path_q;
  reg [31:0] object_rx_id_q;
  reg [15:0] object_rx_initial_sequence_q;
  reg tx_context_aborted_q;
  reg rx_context_aborted_q;
  reg [LANE_COUNT-1:0] object_lane_mask_q;
  reg [LANE_COUNT*8-1:0] object_lane_weights_q;
  reg [1:0] object_rate_q;
  reg [31:0] object_session_q;
  reg [15:0] object_path_q;
  reg [31:0] object_id_q;
  reg [15:0] object_initial_sequence_q;
  reg [31:0] fault_flags_remaining_q;
  reg [2:0] fault_attempt_budget_q;
  reg auto_migration_mode_q;
  reg auto_migration_armed_q;
  reg auto_migration_triggered_q;
  reg [LANE_WIDTH-1:0] auto_migration_target_lane_q;
  reg [LANE_COUNT-1:0] auto_migration_target_mask_q;
  reg [15:0] auto_migration_trigger_sequence_q;
  reg [15:0] auto_migration_trigger_ack_base_q;
  reg [5:0] auto_migration_trigger_outstanding_q;
  reg [31:0] auto_migration_trigger_attempt_count_q;
  reg [31:0] auto_migration_trigger_physical_tx_count_q;
  reg [31:0] auto_migration_trigger_count_q;
  reg [31:0] auto_migration_trigger_migration_count_q;
  reg [31:0] auto_migration_trigger_scheduled_count_q;
  reg [LANE_COUNT-1:0] lane_auto_migration_pending_q;
  reg [15:0] lane_auto_migration_sequence_q [0:LANE_COUNT-1];
  reg duplicate_ack_validation_pending_q;
  reg [31:0] duplicate_ack_validation_start_q;
  reg session_reset_pulse_q;
  reg [7:0] drop_data_remaining_q;
  reg [7:0] drop_ack_remaining_q;
  reg [31:0] dropped_data_count_q;
  reg [31:0] dropped_ack_count_q;
  reg [31:0] p10_5_piggyback_ack_tx_count_q;
  reg [31:0] p10_5_piggyback_ack_rx_count_q;
  reg [31:0] p10_5_control_ack_fallback_count_q;
  reg [31:0] p10_5_direction_reject_count_q;
  reg [31:0] p10_5_role_epoch_reject_count_q;
  reg [31:0] p10_5_tx_axis_stall_count_q;
  reg [31:0] p10_5_rx_axis_stall_count_q;

  wire [LANE_COUNT-1:0] a_phy_ready;
  wire [LANE_COUNT-1:0] b_phy_ready;
  wire [LANE_COUNT-1:0] a_startup_done;
  wire [LANE_COUNT-1:0] b_startup_done;
  wire [LANE_COUNT-1:0] a_fault_stuck;
  wire [LANE_COUNT-1:0] b_fault_stuck;
  wire [LANE_COUNT-1:0] a_fault_duty;
  wire [LANE_COUNT-1:0] b_fault_duty;
  wire [LANE_COUNT-1:0] a_txd_internal;
  wire [LANE_COUNT-1:0] b_txd_internal;
  wire [LANE_COUNT-1:0] a_rx_pulse;
  wire [LANE_COUNT-1:0] b_rx_pulse;
  wire endpoint_mode = DEPLOYMENT_ROLE != ROLE_P9_DUAL;
  wire local_is_a = DEPLOYMENT_ROLE != ROLE_ROTATING_B;
  wire [5:0] local_node_id = local_is_a ? 6'd1 : 6'd2;
  wire [LANE_COUNT-1:0] local_phy_ready = local_is_a ? a_phy_ready : b_phy_ready;
  wire [LANE_COUNT-1:0] local_startup_done = local_is_a ? a_startup_done : b_startup_done;
  wire [LANE_COUNT-1:0] local_fault_stuck = local_is_a ? a_fault_stuck : b_fault_stuck;
  wire [LANE_COUNT-1:0] local_fault_duty = local_is_a ? a_fault_duty : b_fault_duty;
  wire detected_safety_fault = endpoint_mode ?
      (|local_fault_stuck | |local_fault_duty) :
      (|a_fault_stuck | |b_fault_stuck | |a_fault_duty | |b_fault_duty);
  wire any_safety_fault = detected_safety_fault || forensic_fault_hold_i;
  wire tx_kill = !endpoint_armed_q || shutdown_latched_q || any_safety_fault;
  wire local_sender = object_dual_direction_q || !endpoint_mode ||
      (local_is_a ? !object_direction_q : object_direction_q);
  wire local_receiver = object_dual_direction_q || !endpoint_mode || !local_sender;
  wire requested_dual_direction = P10_5_DUAL_CAPABLE != 0 &&
      cfg_p10_5_dual_direction_i;
  wire [LANE_COUNT-1:0] selected_tx_lane_mask = object_dual_direction_q ?
      object_tx_lane_mask_q : object_lane_mask_q;
  wire [LANE_COUNT-1:0] selected_rx_lane_mask = object_dual_direction_q ?
      object_rx_lane_mask_q : object_lane_mask_q;
  // Direction 0 is fixed-to-rotating and direction 1 is rotating-to-fixed.
  wire local_tx_direction = object_dual_direction_q ? !local_is_a :
      object_direction_q;
  wire local_rx_direction = object_dual_direction_q ? local_is_a :
      object_direction_q;
  wire endpoint_phy_ready_all = endpoint_mode ? &local_phy_ready :
      (&a_phy_ready && &b_phy_ready);
  wire cfg_auto_migration_request =
      cfg_fault_flags_i[AUTO_MIGRATION_ENABLE_BIT];
  wire [1:0] cfg_auto_migration_target_lane =
      cfg_fault_flags_i[AUTO_MIGRATION_TARGET_LSB +: 2];
  wire cfg_auto_migration_target_valid =
      cfg_auto_migration_target_lane < LANE_COUNT;
  wire [LANE_COUNT-1:0] cfg_auto_migration_target_mask =
      {{(LANE_COUNT-1){1'b0}}, 1'b1} << cfg_auto_migration_target_lane;
  wire cfg_auto_migration_config_valid = endpoint_mode &&
      cfg_auto_migration_request &&
      cfg_fault_flags_i[4] && cfg_fault_flags_i[3:0] == 0 &&
      cfg_auto_migration_target_valid &&
      |(cfg_lane_mask_i & cfg_auto_migration_target_mask) &&
      !(|(cfg_lane_unavailable_i & cfg_auto_migration_target_mask));
  // Before the deliberately CRC-bad target frame completes, admit only that
  // target.  On serializer completion atomically swap to target-unavailable.
  // External unavailable bits are always ORed and can never be overridden.
  wire [LANE_COUNT-1:0] auto_migration_internal_unavailable_mask =
      auto_migration_armed_q ? ~auto_migration_target_mask_q :
      (auto_migration_triggered_q ? auto_migration_target_mask_q :
                                   {LANE_COUNT{1'b0}});
  wire [LANE_COUNT-1:0] effective_lane_unavailable =
      cfg_lane_unavailable_i | auto_migration_internal_unavailable_mask;
  wire [LANE_COUNT-1:0] effective_lane_mask =
      selected_tx_lane_mask & ~effective_lane_unavailable;

  assign endpoint_armed_o = endpoint_armed_q;
  assign tx_kill_active_o = tx_kill;
  assign effective_full_shutdown_o = shutdown_latched_q || any_safety_fault;
  assign phy_ready_mask_o = endpoint_mode ?
      (local_is_a ? {{LANE_COUNT{1'b0}}, local_phy_ready} :
                    {local_phy_ready, {LANE_COUNT{1'b0}}}) :
      {b_phy_ready, a_phy_ready};
  assign startup_done_mask_o = endpoint_mode ?
      (local_is_a ? {{LANE_COUNT{1'b0}}, local_startup_done} :
                    {local_startup_done, {LANE_COUNT{1'b0}}}) :
      {b_startup_done, a_startup_done};
  // Preserve the causal physical fault bits.  The persistent forensic hold is
  // reported separately by its register window and must not masquerade as a
  // newly detected module fault after a functional reset.
  assign safety_fault_mask_o = endpoint_mode ?
      (local_is_a ? {{LANE_COUNT{1'b0}},
                     (local_fault_stuck | local_fault_duty)} :
                    {(local_fault_stuck | local_fault_duty),
                     {LANE_COUNT{1'b0}}}) :
      {(b_fault_stuck | b_fault_duty), (a_fault_stuck | a_fault_duty)};
  assign object_active_o = object_active_q;
  assign object_done_o = object_done_q;
  assign object_fail_o = object_fail_q;
  assign object_error_o = object_error_q;
  assign physical_drop_data_count_o = dropped_data_count_q;
  assign physical_drop_ack_count_o = dropped_ack_count_q;
  assign p10_5_dual_direction_active_o = object_dual_direction_q;
  assign p10_5_tx_lane_mask_o = selected_tx_lane_mask;
  assign p10_5_rx_lane_mask_o = selected_rx_lane_mask;
  assign p10_5_role_epoch_o = object_role_epoch_q;
  assign p10_5_piggyback_ack_tx_count_o =
      p10_5_piggyback_ack_tx_count_q;
  assign p10_5_piggyback_ack_rx_count_o =
      p10_5_piggyback_ack_rx_count_q;
  assign p10_5_control_ack_fallback_count_o =
      p10_5_control_ack_fallback_count_q;
  assign p10_5_direction_reject_count_o = p10_5_direction_reject_count_q;
  assign p10_5_role_epoch_reject_count_o =
      p10_5_role_epoch_reject_count_q;
  assign p10_5_tx_context_aborted_o = tx_context_aborted_q;
  assign p10_5_rx_context_aborted_o = rx_context_aborted_q;
  assign p10_5_tx_axis_stall_count_o = p10_5_tx_axis_stall_count_q;
  assign p10_5_rx_axis_stall_count_o = p10_5_rx_axis_stall_count_q;
  assign effective_lane_unavailable_o = effective_lane_unavailable;
  assign auto_migration_armed_o = auto_migration_armed_q;
  assign auto_migration_triggered_o = auto_migration_triggered_q;
  assign auto_migration_target_mask_o = auto_migration_target_mask_q;
  assign auto_migration_trigger_sequence_o =
      auto_migration_trigger_sequence_q;
  assign auto_migration_trigger_ack_base_o =
      auto_migration_trigger_ack_base_q;
  assign auto_migration_trigger_outstanding_o =
      auto_migration_trigger_outstanding_q;
  assign auto_migration_trigger_attempt_count_o =
      auto_migration_trigger_attempt_count_q;
  assign auto_migration_trigger_physical_tx_count_o =
      auto_migration_trigger_physical_tx_count_q;
  assign auto_migration_trigger_count_o = auto_migration_trigger_count_q;
  assign auto_migration_trigger_migration_count_o =
      auto_migration_trigger_migration_count_q;
  assign auto_migration_trigger_scheduled_count_o =
      auto_migration_trigger_scheduled_count_q;

  // Direction-context abort is protocol state, not a physical safety kill.
  // Keep these registers synchronously reset so that neither one can become
  // an asynchronously-reset control feeding the inferred payload BRAM ports
  // (Vivado REQP-1839).  The independent full-shutdown/Txd-kill path remains
  // asynchronous and does not wait on these context flags.
  always @(posedge clk) begin : p10_5_direction_context_lifecycle
    if (!rst_n) begin
      tx_context_aborted_q <= 1'b0;
      rx_context_aborted_q <= 1'b0;
    end else if (start_object_i) begin
      tx_context_aborted_q <= 1'b0;
      rx_context_aborted_q <= 1'b0;
    end else if (object_active_q && object_dual_direction_q) begin
      if (abort_tx_context_i) tx_context_aborted_q <= 1'b1;
      if (abort_rx_context_i) rx_context_aborted_q <= 1'b1;
    end
  end

  // AXI-stream ingress and immutable selective-repeat payload store.
  (* ram_style="block" *) reg [7:0] tx_store [0:LANE_COUNT-1][0:STORE_BYTES-1];
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
      !full_shutdown_request_i && !tx_context_aborted_q &&
      !any_safety_fault;

  // Keep all payload and immutable slot metadata memories out of the
  // asynchronously-reset control process.  This is the canonical synchronous
  // RAM template required for BRAM inference on 7-series devices.
  integer store_lane;
  always @(posedge clk) begin : ingress_payload_memory
    if (ingress_store_write) begin
      for (store_lane = 0; store_lane < LANE_COUNT; store_lane = store_lane + 1)
        tx_store[store_lane][ingress_write_address] <= ingress_current_byte;
      if (ingress_end_of_frame) begin
        tx_slot_crc[ingress_current_slot] <= ~ingress_next_crc;
        tx_slot_final[ingress_current_slot] <= ingress_end_of_object;
        tx_slot_fragment_offset[ingress_current_slot] <= ingress_fragment_offset_q;
      end
    end
  end

  assign s_axis_tready_o = object_active_q && local_sender &&
      !object_fail_q && !disarm_request_i && !tx_context_aborted_q &&
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
      end else if (abort_object_i || disarm_request_i ||
                   full_shutdown_request_i || any_safety_fault ||
                   tx_context_aborted_q) begin
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
  wire [LANE_WIDTH-1:0] dp_attempt_lane;
  wire [15:0] dp_attempt_path;
  wire dp_attempt_retry;
  wire auto_migration_target_attempt = auto_migration_mode_q &&
      auto_migration_armed_q &&
      dp_attempt_lane == auto_migration_target_lane_q;
  wire fault_attempt_eligible = fault_attempt_budget_q != 0 &&
      (!auto_migration_mode_q || auto_migration_target_attempt);
  wire auto_migration_bad_crc_attempt = fault_attempt_eligible &&
      fault_flags_remaining_q[4] && auto_migration_mode_q;
  reg dp_peer_ack_valid_q;
  reg [31:0] dp_peer_ack_session_q;
  reg [15:0] dp_peer_ack_base_q;
  reg [31:0] dp_peer_ack_bitmap_q;
  reg [5:0] dp_peer_ack_width_q;
  reg [15:0] dp_peer_ack_credit_q;
  // The RX window commits metadata through a synchronous staging cycle.  A
  // control event asserted with dp_rx_frame_valid_q would therefore snapshot
  // the previous ACK/SACK state.  Delay the physical-frame classification
  // until both the registered SACK bitmap and dp_rx_accept_pulse are observable.
  // Newly accepted DATA must remain subject to the bounded ACK aggregator;
  // only a valid frame that was not newly accepted (for example a duplicate
  // after ACK loss) forces an immediate cumulative re-ACK of stable state.
  reg [1:0] dp_ack_control_pipe_q;
  reg [1:0] dp_turnaround_pipe_q;
  reg [15:0] dp_turnaround_sequence_pipe_q [0:1];
  reg dp_rx_accept_delayed_q;
  reg dp_rx_delivery_delayed_q;
  reg dp_rx_frame_valid_q;
  reg dp_rx_l1_valid_q;
  reg dp_rx_turnaround_q;
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
  wire dp_rx_accept_pulse;
  wire dp_local_ack_valid;
  reg dp_local_ack_ready_q;
  wire [31:0] dp_local_ack_session;
  wire [15:0] dp_local_ack_base;
  wire [31:0] dp_local_ack_bitmap;
  wire [5:0] dp_local_ack_width;
  wire [15:0] dp_local_ack_credit;
  reg dp_ack_piggyback_commit_q;
  reg p10_5_ack_dirty_q;
  wire [5:0] dp_rx_credit;
  reg [5:0] p10_5_rx_credit_d_q;
  reg [31:0] p10_5_control_fallback_wait_q;
  wire p10_5_credit_reopen_event = object_dual_direction_q &&
      p10_5_rx_credit_d_q == 0 && dp_rx_credit != 0;
  localparam integer P10_5_CONTROL_FALLBACK_GRACE_CYCLES =
      ACK_MAX_DELAY_CYCLES;
  wire p10_5_duplicate_reack_event = object_dual_direction_q &&
      dp_ack_control_pipe_q[1] && !dp_rx_accept_delayed_q;
  wire p10_5_dirty_timeout_event = object_dual_direction_q &&
      p10_5_ack_dirty_q &&
      p10_5_control_fallback_wait_q ==
          P10_5_CONTROL_FALLBACK_GRACE_CYCLES-1;
  wire p10_5_immediate_control_event =
      p10_5_duplicate_reack_event || p10_5_credit_reopen_event;
  wire dp_local_ack_snapshot_stale = endpoint_mode &&
      (dp_local_ack_base != rx_base_sequence_o ||
       dp_local_ack_bitmap != rx_sack_bitmap_o ||
       dp_local_ack_credit != {10'd0, dp_rx_credit});
  wire p10_5_piggyback_available = object_dual_direction_q &&
      !rx_context_aborted_q &&
      (p10_5_ack_dirty_q || dp_local_ack_valid);
  wire [3:0] dp_scheduler_defer;
  assign p10_5_rx_receiver_credit_o = dp_rx_credit;
  assign p10_5_peer_receiver_credit_o = dp_peer_ack_credit_q;
  assign p10_5_peer_ack_base_o = dp_peer_ack_base_q;
  assign p10_5_peer_ack_bitmap_o = dp_peer_ack_bitmap_q;
  assign p10_5_control_queue_occupancy_o =
      {1'b0, dp_local_ack_valid} + {1'b0, p10_5_ack_dirty_q};
  wire [LANE_COUNT-1:0] lane_runtime_ready;
  // The validation-only masks exercise the real scheduler defer paths.  They
  // can only remove a lane; they cannot create permit, mapping or duty
  // headroom.  Physical target-duty headroom remains independently enforced.
  wire [LANE_COUNT-1:0] mapping_valid_mask =
      ~cfg_fault_flags_i[8 +: LANE_COUNT];
  wire [LANE_COUNT-1:0] injected_duty_headroom_mask =
      ~cfg_fault_flags_i[8+LANE_COUNT +: LANE_COUNT];
  wire [LANE_COUNT-1:0] physical_duty_headroom_mask = endpoint_mode ?
      ~local_fault_duty :
      ~(a_fault_duty | b_fault_duty);
  wire [LANE_COUNT-1:0] physical_fault_free_mask = endpoint_mode ?
      ~local_fault_stuck :
      ~(a_fault_stuck | b_fault_stuck);
  wire [LANE_COUNT-1:0] schedulable_lane_mask = effective_lane_mask &
      mapping_valid_mask & injected_duty_headroom_mask &
      physical_duty_headroom_mask;

  ir_data_plane_top #(
    .LANE_COUNT(LANE_COUNT), .WINDOW_SIZE(WINDOW_SIZE), .SACK_BITS(SACK_BITS),
    .MAX_RETRY(7), .RTO_CYCLES(RTO_CYCLES), .PAYLOAD_REF_WIDTH(ENTRY_WIDTH),
    .DESCRIPTOR_WIDTH(16),
    .P10_5_DUAL_CONTEXT(P10_5_DUAL_CAPABLE != 0),
    .SCHEDULER_OVERHEAD_BYTES(P10_5_DUAL_CAPABLE != 0 ? 38 : 22),
    .ACK_FRAME_THRESHOLD(DEPLOYMENT_ROLE == ROLE_P9_DUAL ?
                         8 : ACK_FRAME_THRESHOLD),
    .ACK_MAX_DELAY_CYCLES(DEPLOYMENT_ROLE == ROLE_P9_DUAL ?
                          32_000 : ACK_MAX_DELAY_CYCLES)
  ) u_data_plane (
    .clk(clk), .rst_n(rst_n), .clear_counters_i(clear_counters_i),
    .session_reset_i(session_reset_pulse_q),
    .initial_sequence_i(object_initial_sequence_q),
    .tx_session_reset_i(session_reset_pulse_q),
    .rx_session_reset_i(session_reset_pulse_q),
    .tx_abort_i(tx_context_aborted_q),
    .rx_abort_i(rx_context_aborted_q),
    .tx_initial_sequence_i(object_initial_sequence_q),
    .rx_initial_sequence_i(object_rx_initial_sequence_q),
    .tx_session_epoch_i(object_session_q),
    .rx_context_session_epoch_i(object_rx_session_q),
    .rx_context_path_epoch_i(object_rx_path_q),
    .abort_all_i(abort_object_i || disarm_request_i || full_shutdown_request_i || any_safety_fault ||
                 object_fail_q),
    .session_epoch_i(object_session_q), .path_epoch_i(object_path_q),
    .path_epoch_valid_i(1'b1), .lane_weights_i(object_lane_weights_q),
    .active_lane_mask_i(effective_lane_mask), .lane_ready_i(lane_runtime_ready),
    .lane_health_i(~effective_lane_unavailable),
    .mapping_valid_i(mapping_valid_mask),
    .frame_admission_i({LANE_COUNT{1'b1}}),
    .lane_tx_permit_i({LANE_COUNT{endpoint_armed_q}}),
    .duty_headroom_i(physical_duty_headroom_mask &
                     injected_duty_headroom_mask),
    .fault_free_i(physical_fault_free_mask),
    .global_permit_effective_i(endpoint_armed_q), .endpoint_armed_i(endpoint_armed_q),
    .tx_kill_active_i(tx_kill),
    .peer_receiver_credit_i(endpoint_mode ? dp_peer_ack_credit_q :
                            {10'd0, dp_rx_credit}),
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
    .rx_accept_pulse_o(dp_rx_accept_pulse),
    // A validated physical DATA event that was not newly accepted forces a
    // cumulative response.  New frames participate in bounded aggregation;
    // duplicates force a re-ACK so reverse-path ACK loss is recoverable.
    .ack_control_event_i(p10_5_immediate_control_event ||
                         p10_5_dirty_timeout_event),
    .ack_direction_boundary_i(endpoint_mode &&
                              endpoint_turnaround_ack_eligible),
    .ack_explicit_request_i(!endpoint_mode && input_complete_q &&
                            tx_outstanding_count_o != 0),
    .ack_piggyback_commit_i(dp_ack_piggyback_commit_q),
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

  // Direct P10.5 AXI-stream backpressure telemetry.  These counters observe
  // the already-existing stream handshakes and never feed readiness, safety,
  // permit, scheduling, or retry decisions.
  always @(posedge clk or negedge rst_n) begin : p10_5_axis_stall_telemetry
    if (!rst_n) begin
      p10_5_tx_axis_stall_count_q <= 0;
      p10_5_rx_axis_stall_count_q <= 0;
    end else if (clear_counters_i) begin
      p10_5_tx_axis_stall_count_q <= 0;
      p10_5_rx_axis_stall_count_q <= 0;
    end else if (object_dual_direction_q) begin
      if (s_axis_tvalid_i && !s_axis_tready_o &&
          p10_5_tx_axis_stall_count_q != 32'hffff_ffff)
        p10_5_tx_axis_stall_count_q <= p10_5_tx_axis_stall_count_q + 1'b1;
      if (m_axis_tvalid_o && !m_axis_tready_i &&
          p10_5_rx_axis_stall_count_q != 32'hffff_ffff)
        p10_5_rx_axis_stall_count_q <= p10_5_rx_axis_stall_count_q + 1'b1;
    end
  end

  always @(posedge clk or negedge rst_n) begin : ack_control_alignment
    if (!rst_n) begin
      dp_ack_control_pipe_q <= 2'b00;
      dp_turnaround_pipe_q <= 2'b00;
      dp_turnaround_sequence_pipe_q[0] <= 16'd0;
      dp_turnaround_sequence_pipe_q[1] <= 16'd0;
      dp_rx_accept_delayed_q <= 1'b0;
      dp_rx_delivery_delayed_q <= 1'b0;
      p10_5_rx_credit_d_q <= WINDOW_SIZE;
    end else if (start_object_i || abort_object_i || disarm_request_i ||
                 full_shutdown_request_i || any_safety_fault) begin
      dp_ack_control_pipe_q <= 2'b00;
      dp_turnaround_pipe_q <= 2'b00;
      dp_turnaround_sequence_pipe_q[0] <= 16'd0;
      dp_turnaround_sequence_pipe_q[1] <= 16'd0;
      dp_rx_accept_delayed_q <= 1'b0;
      dp_rx_delivery_delayed_q <= 1'b0;
      p10_5_rx_credit_d_q <= WINDOW_SIZE;
    end else begin
      dp_ack_control_pipe_q <= {
          dp_ack_control_pipe_q[0],
          dp_rx_frame_valid_q && dp_rx_l1_valid_q
      };
      dp_turnaround_pipe_q <= {
          dp_turnaround_pipe_q[0],
          dp_rx_frame_valid_q && dp_rx_l1_valid_q && dp_rx_turnaround_q
      };
      dp_turnaround_sequence_pipe_q[0] <= dp_rx_sequence_q;
      dp_turnaround_sequence_pipe_q[1] <=
          dp_turnaround_sequence_pipe_q[0];
      dp_rx_accept_delayed_q <= dp_rx_accept_pulse;
      // The RX reorder window updates base/SACK/credit on this handshake.
      // Delay delivery observation one cycle so dirty/credit logic sees the
      // post-delivery base, SACK, and receiver-credit state.
      dp_rx_delivery_delayed_q <= dp_delivery_valid && dp_delivery_ready_q;
      p10_5_rx_credit_d_q <= dp_rx_credit;
    end
  end

  // Each lane serializer reads its own synchronous BRAM replica.
  // Each serializer holds its current byte while prefetching the next, so no
  // 247-byte asynchronous staging mux is present in the Z7010 datapath.
  wire [STORE_ADDR_WIDTH-1:0] tx_store_read_addr [0:LANE_COUNT-1];
  reg [7:0] tx_store_read_data [0:LANE_COUNT-1];
  reg [STORE_ADDR_WIDTH-1:0] lane_payload_base [0:LANE_COUNT-1];
  reg [LANE_COUNT-1:0] lane_start_pending;
  reg [LANE_COUNT-1:0] lane_frame_ack;
  // Actual final physical Txd is the only trigger.  P10.4 additionally
  // quarantines the paired receiver while an adjacent connector module emits
  // an ACK; ordinary DATA TX still does not blank the peer lane.
  wire [LANE_COUNT-1:0] local_final_txd = local_is_a ? a_txd_o : b_txd_o;
  wire [LANE_COUNT-1:0] paired_ack_physical_txd;
  wire [LANE_COUNT-1:0] local_rx_quarantine_source;
  p10_4_connector_ack_rx_quarantine #(.LANE_COUNT(LANE_COUNT))
      u_connector_ack_rx_quarantine (
        .final_local_txd_i(local_final_txd),
        .local_tx_is_ack_i(lane_frame_ack),
        .paired_ack_txd_o(paired_ack_physical_txd),
        .rx_quarantine_source_o(local_rx_quarantine_source)
      );
  reg [31:0] lane_session [0:LANE_COUNT-1];
  reg [15:0] lane_path [0:LANE_COUNT-1];
  reg [15:0] lane_sequence [0:LANE_COUNT-1];
  reg [15:0] lane_length [0:LANE_COUNT-1];
  reg [31:0] lane_crc [0:LANE_COUNT-1];
  reg [7:0] lane_flags [0:LANE_COUNT-1];
  reg [31:0] lane_object [0:LANE_COUNT-1];
  reg [31:0] lane_fragment [0:LANE_COUNT-1];
  reg [15:0] lane_ack_base [0:LANE_COUNT-1];
  reg [31:0] lane_ack_bitmap [0:LANE_COUNT-1];
  reg [15:0] lane_ack_credit [0:LANE_COUNT-1];
  reg [5:0] lane_source_node [0:LANE_COUNT-1];
  reg [LANE_COUNT-1:0] lane_source_a;
  reg [LANE_COUNT-1:0] lane_vnext;
  reg [LANE_COUNT-1:0] lane_direction;
  reg [15:0] lane_role_epoch [0:LANE_COUNT-1];
  reg [LANE_COUNT-1:0] lane_piggyback_ack_valid;
  reg [LANE_COUNT-1:0] lane_piggyback_ack_direction;
  reg [31:0] lane_piggyback_ack_session [0:LANE_COUNT-1];
  reg [15:0] lane_piggyback_ack_base [0:LANE_COUNT-1];
  reg [31:0] lane_piggyback_ack_bitmap [0:LANE_COUNT-1];
  reg [15:0] lane_piggyback_ack_credit [0:LANE_COUNT-1];
  wire [STORE_ADDR_WIDTH-1:0] serializer_payload_address [0:LANE_COUNT-1];
  wire [LANE_COUNT-1:0] serializer_start_ready;
  wire [LANE_COUNT-1:0] serializer_pulse;
  wire [LANE_COUNT-1:0] serializer_busy;
  wire [LANE_COUNT-1:0] serializer_done;
  wire [31:0] a_tx_count [0:LANE_COUNT-1];
  wire [31:0] b_tx_count [0:LANE_COUNT-1];
  reg [LANE_COUNT-1:0] serializer_busy_d;
  reg [6:0] receive_tail [0:LANE_COUNT-1];
  reg [LANE_COUNT-1:0] receive_tail_destination_b;
  reg [FRAME_DUTY_GUARD_WIDTH-1:0] frame_duty_guard_q [0:LANE_COUNT-1];
  reg [LANE_COUNT-1:0] frame_schedule_valid_q;
  reg [LANE_COUNT-1:0] frame_schedule_direction_q;

  always @(posedge clk) begin
    for (store_lane = 0; store_lane < LANE_COUNT; store_lane = store_lane + 1)
      tx_store_read_data[store_lane] <=
          tx_store[store_lane][tx_store_read_addr[store_lane]];
  end

  typedef enum reg [2:0] {PH_DATA, PH_ACK_GUARD, PH_ACK_START,
                          PH_ACK_WAIT_DONE, PH_ACK_WAIT_RX,
                          PH_ACK_REPEAT_WAIT, PH_DATA_GUARD} phase_t;
  phase_t phase_q;
  reg [15:0] phase_guard_q;
  reg [LANE_WIDTH-1:0] ack_lane_q;
  reg [31:0] ack_wait_q;
  reg ack_received_pulse_q;
  reg [5:0] endpoint_tx_burst_count_q;
  reg endpoint_waiting_for_ack_q;
  reg [31:0] endpoint_wait_ack_timer_q;
  reg endpoint_turnaround_pending_q;
  reg [15:0] endpoint_turnaround_boundary_sequence_q;
  reg [31:0] endpoint_turnaround_settle_timer_q;
  wire endpoint_turnaround_request_pulse;
  // A boundary flag rides one of two concurrently serialized DATA frames.  It
  // can be decoded before an older sequence still in flight on the other lane.
  // Do not release the half-duplex direction until the cumulative RX base has
  // passed the tagged sequence.  The bounded fallback still emits SACK state
  // for a genuinely lost earlier frame, well before the retransmission timer.
  wire endpoint_turnaround_cumulative_ready =
      endpoint_turnaround_pending_q &&
      seq_before(endpoint_turnaround_boundary_sequence_q,
                 rx_base_sequence_o);
  wire endpoint_turnaround_fallback_ready =
      endpoint_turnaround_pending_q &&
      endpoint_turnaround_settle_timer_q >= ACK_MAX_DELAY_CYCLES-1;
  wire endpoint_turnaround_ack_eligible =
      endpoint_turnaround_cumulative_ready ||
      endpoint_turnaround_fallback_ready;
  wire endpoint_valid_ack_pulse = ack_received_pulse_q &&
      dp_peer_ack_session_q == object_session_q;
  wire endpoint_data_boundary = endpoint_mode && !object_dual_direction_q &&
      local_sender &&
      ((endpoint_tx_burst_count_q >= ENDPOINT_BURST_FRAMES-1) ||
       dp_attempt_descriptor[0] || dp_attempt_retry);
  wire lanes_idle = (&serializer_start_ready) && !(|lane_start_pending) &&
                    !(|serializer_busy);
  // ``endpoint_waiting_for_ack_q`` is asserted only after an accepted final
  // physical DATA-frame launch closes the bounded burst.  Counting it while
  // all serializers are idle therefore measures TX idle caused specifically
  // by awaiting the reverse ACK, rather than merely having unacked frames.
  assign tx_idle_due_to_ack_o = object_active_q && local_sender &&
      endpoint_waiting_for_ack_q && lanes_idle;
  // Allocation is held at a fragment boundary only when the selective-repeat
  // window cannot accept another immutable slot.  Require the directly
  // observed full occupancy to keep this counter semantically narrow.
  assign window_full_stall_o = object_active_q && local_sender &&
      allocate_pending_q && !dp_allocate_ready &&
      tx_outstanding_count_o == WINDOW_SIZE;
  // A ready retry/new attempt together with zero peer-advertised credit is a
  // direct receiver-credit stall.  Safety/mapping/serializer deferrals are
  // intentionally excluded and remain observable through their own paths.
  assign receiver_credit_stall_o = object_active_q && local_sender &&
      dp_attempt_valid &&
      ((endpoint_mode ? dp_peer_ack_credit_q : {10'd0, dp_rx_credit}) == 0);
  // Count only deliberate half-duplex turnaround/wait intervals in which no
  // serializer is active.  ACK serialization itself is useful wire activity,
  // not idle time, and is excluded.
  assign direction_turnaround_idle_o = object_active_q && lanes_idle &&
      (endpoint_waiting_for_ack_q || phase_q == PH_ACK_GUARD ||
       phase_q == PH_ACK_START || phase_q == PH_ACK_WAIT_RX ||
       phase_q == PH_ACK_REPEAT_WAIT || phase_q == PH_DATA_GUARD);
  // P9's monolithic fixture admits an entire encoded frame against current
  // headroom.  Independent P10.1R endpoints instead establish a clean exact-
  // duty history before the first DATA frame, then use the proved fixed
  // frame-boundary schedule.  The exact sliding accountant remains the final
  // per-pulse backstop; the qualified schedule is designed never to invoke a
  // target throttle in the middle of a valid frame.
  wire [31:0] data_frame_required_high_cycles =
      (object_dual_direction_q ? 32'd1536 : 32'd1024) +
      ({16'd0, dp_attempt_payload_length} << 5);
  wire [LANE_COUNT-1:0] data_frame_duty_ready;
  wire [LANE_COUNT-1:0] data_duty_history_empty;
  wire [LANE_COUNT-1:0] data_frame_schedule_ready;
  // ACK frames contain 16 preamble plus 20*4 data symbols, or 768 Txd-high
  // cycles.  ACKs travel from the opposite physical endpoint.
  wire [LANE_COUNT-1:0] ack_frame_duty_ready;
  wire [LANE_COUNT-1:0] ack_schedulable_lane_mask =
      schedulable_lane_mask & ack_frame_duty_ready &
      {LANE_COUNT{local_receiver && !rx_context_aborted_q}};
  wire [LANE_WIDTH-1:0] ack_selected_lane =
      first_set_lane(ack_schedulable_lane_mask);
  genvar eligibility_lane;
  generate
    for (eligibility_lane = 0; eligibility_lane < LANE_COUNT;
         eligibility_lane = eligibility_lane + 1) begin : g_lane_eligibility
      wire [31:0] data_headroom = (object_dual_direction_q ? !local_is_a :
          object_direction_q) ?
          duty_headroom_flat_o[32*(LANE_COUNT+eligibility_lane) +: 32] :
          duty_headroom_flat_o[32*eligibility_lane +: 32];
      wire [31:0] ack_headroom = object_dual_direction_q ? data_headroom :
          (object_direction_q ?
          duty_headroom_flat_o[32*eligibility_lane +: 32] :
          duty_headroom_flat_o[32*(LANE_COUNT+eligibility_lane) +: 32]);
      assign data_frame_duty_ready[eligibility_lane] =
          data_headroom >= data_frame_required_high_cycles;
      assign data_duty_history_empty[eligibility_lane] =
          data_headroom == duty_target_limit_cycles_o;
      assign data_frame_schedule_ready[eligibility_lane] = endpoint_mode ?
          ((frame_schedule_valid_q[eligibility_lane] &&
            frame_schedule_direction_q[eligibility_lane] == local_tx_direction) ||
           (!frame_schedule_valid_q[eligibility_lane] &&
            data_duty_history_empty[eligibility_lane])) :
          data_frame_duty_ready[eligibility_lane];
      assign ack_frame_duty_ready[eligibility_lane] = ack_headroom >=
          (object_dual_direction_q ? 32'd832 : 32'd768);
      assign lane_runtime_ready[eligibility_lane] =
          local_sender && !tx_context_aborted_q &&
          !endpoint_waiting_for_ack_q &&
          schedulable_lane_mask[eligibility_lane] &&
          !serializer_busy[eligibility_lane] &&
          serializer_start_ready[eligibility_lane] &&
          !lane_start_pending[eligibility_lane] &&
          !serializer_done[eligibility_lane] &&
          frame_duty_guard_q[eligibility_lane] == 0 &&
          data_frame_schedule_ready[eligibility_lane] && phase_q == PH_DATA;
    end
  endgenerate
  assign dp_attempt_ready = phase_q == PH_DATA &&
      (object_dual_direction_q || !dp_local_ack_valid) &&
      lane_runtime_ready[dp_attempt_lane];

  genvar tx_lane;
  generate
    for (tx_lane = 0; tx_lane < LANE_COUNT; tx_lane = tx_lane + 1) begin : g_serializer
      assign tx_store_read_addr[tx_lane] = serializer_payload_address[tx_lane];
      p9_4ppm_frame_tx #(.PAYLOAD_ADDR_WIDTH(STORE_ADDR_WIDTH),
                         .LANE_COUNT(LANE_COUNT),
                         .P10_5_VNEXT_CAPABLE(P10_5_DUAL_CAPABLE != 0))
      u_serializer (
        .clk(clk), .rst_n(rst_n), .enable_i(endpoint_armed_q && !tx_kill),
        .abort_i(abort_object_i || disarm_request_i || full_shutdown_request_i ||
                 (object_dual_direction_q &&
                  (lane_frame_ack[tx_lane] ? rx_context_aborted_q :
                                             tx_context_aborted_q))),
        .rate_select_i(object_rate_q), .start_valid_i(lane_start_pending[tx_lane]),
        .start_ready_o(serializer_start_ready[tx_lane]),
        .frame_is_ack_i(lane_frame_ack[tx_lane]),
        .session_epoch_i(lane_session[tx_lane]), .path_epoch_i(lane_path[tx_lane]),
        .sequence_i(lane_sequence[tx_lane]), .payload_length_i(lane_length[tx_lane]),
        .payload_crc32_i(lane_crc[tx_lane]), .flags_i(lane_flags[tx_lane]),
        .lane_id_i(tx_lane[7:0]),
        .source_node_id_i(lane_source_node[tx_lane]),
        .object_id_i(lane_object[tx_lane]),
        .fragment_offset_i(lane_fragment[tx_lane]),
        .ack_base_i(lane_ack_base[tx_lane]), .ack_bitmap_i(lane_ack_bitmap[tx_lane]),
        .ack_credit_i(lane_ack_credit[tx_lane]),
        .direction_i(lane_direction[tx_lane]),
        .vnext_i(lane_vnext[tx_lane]),
        .role_epoch_i(lane_role_epoch[tx_lane]),
        .piggyback_ack_valid_i(lane_piggyback_ack_valid[tx_lane]),
        .piggyback_ack_direction_i(
            lane_piggyback_ack_direction[tx_lane]),
        .piggyback_ack_session_i(lane_piggyback_ack_session[tx_lane]),
        .piggyback_ack_base_i(lane_piggyback_ack_base[tx_lane]),
        .piggyback_ack_bitmap_i(lane_piggyback_ack_bitmap[tx_lane]),
        .piggyback_ack_credit_i(lane_piggyback_ack_credit[tx_lane]),
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
      auto_migration_mode_q <= 0;
      auto_migration_armed_q <= 0;
      auto_migration_triggered_q <= 0;
      auto_migration_target_lane_q <= 0;
      auto_migration_target_mask_q <= 0;
      auto_migration_trigger_sequence_q <= 0;
      auto_migration_trigger_ack_base_q <= 0;
      auto_migration_trigger_outstanding_q <= 0;
      auto_migration_trigger_attempt_count_q <= 0;
      auto_migration_trigger_physical_tx_count_q <= 0;
      auto_migration_trigger_count_q <= 0;
      auto_migration_trigger_migration_count_q <= 0;
      auto_migration_trigger_scheduled_count_q <= 0;
      lane_auto_migration_pending_q <= 0;
      duplicate_ack_validation_pending_q <= 0;
      duplicate_ack_validation_start_q <= 0;
      dropped_data_count_q <= 0;
      dropped_ack_count_q <= 0;
      p10_5_piggyback_ack_tx_count_q <= 0;
      p10_5_control_ack_fallback_count_q <= 0;
      dp_ack_piggyback_commit_q <= 0;
      p10_5_ack_dirty_q <= 0;
      p10_5_control_fallback_wait_q <= 0;
      endpoint_tx_burst_count_q <= 0;
      endpoint_waiting_for_ack_q <= 0;
      endpoint_wait_ack_timer_q <= 0;
      endpoint_turnaround_pending_q <= 0;
      endpoint_turnaround_boundary_sequence_q <= 0;
      endpoint_turnaround_settle_timer_q <= 0;
      for (copy_lane = 0; copy_lane < LANE_COUNT; copy_lane = copy_lane + 1) begin
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
        lane_source_node[copy_lane] <= 0;
        lane_source_a[copy_lane] <= 0;
        lane_vnext[copy_lane] <= 0;
        lane_direction[copy_lane] <= 0;
        lane_role_epoch[copy_lane] <= 0;
        lane_piggyback_ack_valid[copy_lane] <= 0;
        lane_piggyback_ack_direction[copy_lane] <= 0;
        lane_piggyback_ack_session[copy_lane] <= 0;
        lane_piggyback_ack_base[copy_lane] <= 0;
        lane_piggyback_ack_bitmap[copy_lane] <= 0;
        lane_piggyback_ack_credit[copy_lane] <= 0;
        serializer_busy_d[copy_lane] <= 0;
        receive_tail[copy_lane] <= 0;
        receive_tail_destination_b[copy_lane] <= 0;
        frame_duty_guard_q[copy_lane] <= 0;
        frame_schedule_valid_q[copy_lane] <= 0;
        frame_schedule_direction_q[copy_lane] <= 0;
        lane_auto_migration_sequence_q[copy_lane] <= 0;
      end
    end else begin
      dp_local_ack_ready_q <= 0;
      dp_ack_piggyback_commit_q <= 0;
      if (dp_rx_accept_pulse || dp_rx_delivery_delayed_q)
        p10_5_ack_dirty_q <= 1;
      // Time from the first cumulative-state change not yet carried by a
      // reverse DATA piggyback. This is the Goal's ACK max-delay bound, not a
      // second delay that starts only after the aggregator presents VALID.
      if (!object_dual_direction_q || !p10_5_ack_dirty_q) begin
        p10_5_control_fallback_wait_q <= 0;
      end else if (p10_5_control_fallback_wait_q <
                   P10_5_CONTROL_FALLBACK_GRACE_CYCLES) begin
        p10_5_control_fallback_wait_q <=
            p10_5_control_fallback_wait_q + 1'b1;
      end
      if (p10_5_immediate_control_event)
        p10_5_control_fallback_wait_q <=
            P10_5_CONTROL_FALLBACK_GRACE_CYCLES;
      if (clear_counters_i) begin
        dropped_data_count_q <= 0;
        dropped_ack_count_q <= 0;
        p10_5_piggyback_ack_tx_count_q <= 0;
        p10_5_control_ack_fallback_count_q <= 0;
        if (!object_active_q) begin
          auto_migration_mode_q <= 0;
          auto_migration_armed_q <= 0;
          auto_migration_triggered_q <= 0;
          auto_migration_target_lane_q <= 0;
          auto_migration_target_mask_q <= 0;
          auto_migration_trigger_sequence_q <= 0;
          auto_migration_trigger_ack_base_q <= 0;
          auto_migration_trigger_outstanding_q <= 0;
          auto_migration_trigger_attempt_count_q <= 0;
          auto_migration_trigger_physical_tx_count_q <= 0;
          auto_migration_trigger_count_q <= 0;
          auto_migration_trigger_migration_count_q <= 0;
          auto_migration_trigger_scheduled_count_q <= 0;
          lane_auto_migration_pending_q <= 0;
        end
      end
      for (copy_lane = 0; copy_lane < LANE_COUNT; copy_lane = copy_lane + 1) begin
        serializer_busy_d[copy_lane] <= serializer_busy[copy_lane];
        if (serializer_done[copy_lane]) begin
          frame_duty_guard_q[copy_lane] <=
              EFFECTIVE_FRAME_DUTY_GUARD_CYCLES;
          if (endpoint_mode && !lane_frame_ack[copy_lane] && local_sender) begin
            frame_schedule_valid_q[copy_lane] <= 1;
            frame_schedule_direction_q[copy_lane] <= local_tx_direction;
          end
          if (lane_auto_migration_pending_q[copy_lane] &&
              auto_migration_armed_q && !auto_migration_triggered_q) begin
            // serializer_done is the final accepted physical-frame event, not
            // a host-timing proxy.  The deliberately invalid CRC makes this
            // exact sequence unacknowledgeable.  Swap lane eligibility in the
            // same PL clock so JTAG latency cannot race cumulative ACK state.
            auto_migration_armed_q <= 0;
            auto_migration_triggered_q <= 1;
            auto_migration_trigger_sequence_q <=
                lane_auto_migration_sequence_q[copy_lane];
            auto_migration_trigger_ack_base_q <= tx_ack_base_o;
            auto_migration_trigger_outstanding_q <=
                tx_outstanding_count_o;
            auto_migration_trigger_attempt_count_q <= tx_attempt_count_o;
            auto_migration_trigger_physical_tx_count_q <= local_is_a ?
                a_tx_count[copy_lane] : b_tx_count[copy_lane];
            auto_migration_trigger_count_q <=
                auto_migration_trigger_count_q + 1'b1;
            auto_migration_trigger_migration_count_q <=
                tx_migration_count_o;
            auto_migration_trigger_scheduled_count_q <=
                scheduler_frames_flat_o[32*copy_lane +: 32];
            fault_attempt_budget_q <= 0;
            fault_flags_remaining_q[4] <= 0;
          end
          lane_auto_migration_pending_q[copy_lane] <= 0;
        end else if (frame_duty_guard_q[copy_lane] != 0) begin
          frame_duty_guard_q[copy_lane] <= frame_duty_guard_q[copy_lane] - 1'b1;
        end
        if (lane_start_pending[copy_lane] && serializer_start_ready[copy_lane]) begin
          lane_start_pending[copy_lane] <= 0;
          lane_source_a[copy_lane] <= object_dual_direction_q ? local_is_a :
              (lane_frame_ack[copy_lane] ? object_direction_q :
                                           !object_direction_q);
          receive_tail_destination_b[copy_lane] <=
              object_dual_direction_q ? !local_is_a :
              (lane_frame_ack[copy_lane] ? object_direction_q :
                                           !object_direction_q);
          if (phase_q == PH_ACK_START && copy_lane == ack_lane_q) begin
            dp_local_ack_ready_q <= 1;
            endpoint_turnaround_pending_q <= 0;
            endpoint_turnaround_settle_timer_q <= 0;
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
        fault_attempt_budget_q <= (cfg_fault_flags_i[4:0] != 0) ?
            (cfg_auto_migration_request ? 3'd1 : 3'd3) :
            (cfg_fault_flags_i[12] ? 3'd1 : 3'd0);
        auto_migration_mode_q <= cfg_auto_migration_config_valid;
        auto_migration_armed_q <= cfg_auto_migration_config_valid &&
            (local_is_a ? !cfg_direction_i : cfg_direction_i);
        auto_migration_triggered_q <= 0;
        auto_migration_target_lane_q <= cfg_auto_migration_config_valid ?
            cfg_auto_migration_target_lane[LANE_WIDTH-1:0] : {LANE_WIDTH{1'b0}};
        auto_migration_target_mask_q <= cfg_auto_migration_config_valid ?
            cfg_auto_migration_target_mask : {LANE_COUNT{1'b0}};
        auto_migration_trigger_sequence_q <= 0;
        auto_migration_trigger_ack_base_q <= 0;
        auto_migration_trigger_outstanding_q <= 0;
        auto_migration_trigger_attempt_count_q <= 0;
        auto_migration_trigger_physical_tx_count_q <= 0;
        auto_migration_trigger_migration_count_q <= 0;
        auto_migration_trigger_scheduled_count_q <= 0;
        duplicate_ack_validation_pending_q <= cfg_fault_flags_i[5];
        duplicate_ack_validation_start_q <= tx_duplicate_ack_count_o;
        endpoint_tx_burst_count_q <= 0;
        endpoint_waiting_for_ack_q <= 0;
        endpoint_wait_ack_timer_q <= 0;
        endpoint_turnaround_pending_q <= 0;
        endpoint_turnaround_boundary_sequence_q <= 0;
        endpoint_turnaround_settle_timer_q <= 0;
        p10_5_ack_dirty_q <= 0;
        p10_5_control_fallback_wait_q <= 0;
        for (copy_lane = 0; copy_lane < LANE_COUNT; copy_lane = copy_lane + 1) begin
          lane_start_pending[copy_lane] <= 0;
          lane_auto_migration_pending_q[copy_lane] <= 0;
          lane_auto_migration_sequence_q[copy_lane] <= 0;
          receive_tail[copy_lane] <= 0;
          if (!frame_schedule_valid_q[copy_lane] ||
              frame_schedule_direction_q[copy_lane] !=
              (requested_dual_direction ? !local_is_a : cfg_direction_i)) begin
            frame_schedule_valid_q[copy_lane] <= 0;
            frame_schedule_direction_q[copy_lane] <=
                requested_dual_direction ? !local_is_a : cfg_direction_i;
          end
        end
      end else if (abort_object_i || disarm_request_i ||
                   full_shutdown_request_i || any_safety_fault ||
                   object_fail_q) begin
        phase_q <= PH_DATA;
        fault_flags_remaining_q <= 0;
        fault_attempt_budget_q <= 0;
        auto_migration_mode_q <= 0;
        auto_migration_armed_q <= 0;
        duplicate_ack_validation_pending_q <= 0;
        endpoint_tx_burst_count_q <= 0;
        endpoint_waiting_for_ack_q <= 0;
        endpoint_wait_ack_timer_q <= 0;
        endpoint_turnaround_pending_q <= 0;
        endpoint_turnaround_boundary_sequence_q <= 0;
        endpoint_turnaround_settle_timer_q <= 0;
        p10_5_ack_dirty_q <= 0;
        p10_5_control_fallback_wait_q <= 0;
        for (copy_lane = 0; copy_lane < LANE_COUNT; copy_lane = copy_lane + 1) begin
          lane_start_pending[copy_lane] <= 0;
          lane_auto_migration_pending_q[copy_lane] <= 0;
          frame_schedule_valid_q[copy_lane] <= 0;
        end
      end else if (object_dual_direction_q && rx_context_aborted_q &&
                   phase_q != PH_DATA) begin
        // RX-context abort cancels only its ACK/control serialization.  The
        // independent local DATA transmitter and TX selective-repeat window
        // continue without an endpoint-wide arm or permit transition.
        phase_q <= PH_DATA;
        phase_guard_q <= 0;
        dp_local_ack_ready_q <= dp_local_ack_valid;
        p10_5_ack_dirty_q <= 0;
        p10_5_control_fallback_wait_q <= 0;
        for (copy_lane = 0; copy_lane < LANE_COUNT;
             copy_lane = copy_lane + 1)
          if (lane_frame_ack[copy_lane])
            lane_start_pending[copy_lane] <= 0;
      end else if (!object_active_q) begin
        phase_q <= PH_DATA;
        drop_data_remaining_q <= 0;
        drop_ack_remaining_q <= 0;
        fault_flags_remaining_q <= 0;
        fault_attempt_budget_q <= 0;
        auto_migration_mode_q <= 0;
        auto_migration_armed_q <= 0;
        lane_auto_migration_pending_q <= 0;
        duplicate_ack_validation_pending_q <= 0;
        endpoint_tx_burst_count_q <= 0;
        endpoint_waiting_for_ack_q <= 0;
        endpoint_wait_ack_timer_q <= 0;
        endpoint_turnaround_pending_q <= 0;
        endpoint_turnaround_boundary_sequence_q <= 0;
        endpoint_turnaround_settle_timer_q <= 0;
        p10_5_ack_dirty_q <= 0;
        p10_5_control_fallback_wait_q <= 0;
      end else begin
        for (copy_lane = 0; copy_lane < LANE_COUNT;
             copy_lane = copy_lane + 1) begin
          if (lane_start_pending[copy_lane] &&
              ((lane_frame_ack[copy_lane] && rx_context_aborted_q) ||
               (!lane_frame_ack[copy_lane] && tx_context_aborted_q)))
            lane_start_pending[copy_lane] <= 0;
        end
        if (endpoint_turnaround_request_pulse) begin
          endpoint_turnaround_pending_q <= 1;
          endpoint_turnaround_boundary_sequence_q <=
              dp_turnaround_sequence_pipe_q[1];
          endpoint_turnaround_settle_timer_q <= 0;
        end else if (endpoint_turnaround_pending_q &&
                     !endpoint_turnaround_cumulative_ready &&
                     !endpoint_turnaround_fallback_ready) begin
          endpoint_turnaround_settle_timer_q <=
              endpoint_turnaround_settle_timer_q + 1'b1;
        end else if (!endpoint_turnaround_pending_q) begin
          endpoint_turnaround_settle_timer_q <= 0;
        end
        if (endpoint_mode && local_sender) begin
          if (endpoint_valid_ack_pulse) begin
            endpoint_tx_burst_count_q <= 0;
            endpoint_waiting_for_ack_q <= 0;
            endpoint_wait_ack_timer_q <= 0;
          end else if (endpoint_waiting_for_ack_q) begin
            if (endpoint_wait_ack_timer_q >= RTO_CYCLES-1) begin
              // Allow the selective-repeat window to present its bounded
              // retry after an absent DATA or ACK frame.
              endpoint_tx_burst_count_q <= 0;
              endpoint_waiting_for_ack_q <= 0;
              endpoint_wait_ack_timer_q <= 0;
            end else begin
              endpoint_wait_ack_timer_q <= endpoint_wait_ack_timer_q + 1'b1;
            end
          end else begin
            endpoint_wait_ack_timer_q <= 0;
          end
        end
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
            lane_auto_migration_pending_q[dp_attempt_lane] <=
                auto_migration_bad_crc_attempt;
            lane_auto_migration_sequence_q[dp_attempt_lane] <=
                dp_attempt_sequence;
            // Each test flag corrupts exactly the first non-dropped DATA
            // attempt.  The immutable slot metadata remains unchanged, so a
            // bounded retry exercises recovery with the canonical values.
            lane_session[dp_attempt_lane] <=
                (fault_attempt_eligible && fault_flags_remaining_q[0]) ?
                object_session_q - 1'b1 : object_session_q;
            lane_path[dp_attempt_lane] <=
                (fault_attempt_eligible && fault_flags_remaining_q[1]) ?
                object_path_q - 16'd2 : dp_attempt_path;
            lane_sequence[dp_attempt_lane] <=
                (fault_attempt_eligible && fault_flags_remaining_q[2]) ?
                dp_attempt_sequence + WINDOW_SIZE :
                ((fault_attempt_eligible && fault_flags_remaining_q[3]) ?
                 // Keep every bounded injected attempt strictly behind the
                 // receiver's object-start base.  Subtracting one from each
                 // attempt's own sequence can alias a later payload onto the
                 // current RX base and corrupt an otherwise recovered object.
                 object_initial_sequence_q - 1'b1 :
                 dp_attempt_sequence);
            lane_length[dp_attempt_lane] <= dp_attempt_payload_length;
            lane_crc[dp_attempt_lane] <=
                (fault_attempt_eligible && fault_flags_remaining_q[4]) ?
                tx_slot_crc[dp_attempt_payload_ref] ^ 32'h0000_0001 :
                tx_slot_crc[dp_attempt_payload_ref];
            lane_flags[dp_attempt_lane] <= {
                6'd0, endpoint_data_boundary,
                tx_slot_final[dp_attempt_payload_ref]};
            lane_source_node[dp_attempt_lane] <=
                object_dual_direction_q ? local_node_id :
                (object_direction_q ? 6'd2 : 6'd1);
            lane_object[dp_attempt_lane] <= object_id_q;
            lane_fragment[dp_attempt_lane] <= tx_slot_fragment_offset[dp_attempt_payload_ref];
            lane_vnext[dp_attempt_lane] <= object_dual_direction_q;
            lane_direction[dp_attempt_lane] <= local_tx_direction;
            lane_role_epoch[dp_attempt_lane] <=
                (fault_attempt_eligible && fault_flags_remaining_q[12]) ?
                object_role_epoch_q - 1'b1 : object_role_epoch_q;
            lane_piggyback_ack_valid[dp_attempt_lane] <=
                p10_5_piggyback_available;
            lane_piggyback_ack_direction[dp_attempt_lane] <=
                local_rx_direction;
            lane_piggyback_ack_session[dp_attempt_lane] <=
                object_rx_session_q;
            lane_piggyback_ack_base[dp_attempt_lane] <= rx_base_sequence_o;
            lane_piggyback_ack_bitmap[dp_attempt_lane] <=
                rx_sack_bitmap_o;
            lane_piggyback_ack_credit[dp_attempt_lane] <=
                {10'd0, dp_rx_credit};
            if (p10_5_piggyback_available) begin
              dp_ack_piggyback_commit_q <= 1;
              if (dp_local_ack_valid) dp_local_ack_ready_q <= 1;
              // The DATA header snapshots the pre-edge ACK state. Preserve
              // dirty when this same edge accepts another RX entry or retires
              // one from the reorder window. The shared dirty-age timer emits
              // bounded control-only fallback if no later DATA can carry it.
              p10_5_ack_dirty_q <=
                  dp_rx_accept_pulse || dp_rx_delivery_delayed_q;
              p10_5_control_fallback_wait_q <= 0;
              p10_5_piggyback_ack_tx_count_q <=
                  p10_5_piggyback_ack_tx_count_q + 1'b1;
            end
            if (endpoint_mode && local_sender) begin
              if (endpoint_data_boundary) begin
                endpoint_tx_burst_count_q <= 0;
                endpoint_waiting_for_ack_q <= 1;
                endpoint_wait_ack_timer_q <= 0;
              end else begin
                endpoint_tx_burst_count_q <= endpoint_tx_burst_count_q + 1'b1;
              end
            end
            if (fault_attempt_eligible) begin
              fault_attempt_budget_q <= fault_attempt_budget_q - 1'b1;
              if (fault_attempt_budget_q == 1)
                fault_flags_remaining_q[4:0] <= 0;
              if (fault_flags_remaining_q[12])
                fault_flags_remaining_q[12] <= 0;
            end
          end
        end

        // Apply the role-specific recovery window in both DATA-to-ACK and ACK-to-DATA directions;
        // neither endpoint may begin a reverse frame
        // while the peer's same-module RX decoder is still quarantined.
        case (phase_q)
          // READY is registered.  Once asserted for a validation-only dropped
          // ACK, do not consume the same held VALID again on the following
          // handshake cycle and accidentally serialize an ACK that was meant
          // to be lost.
          PH_DATA: begin
            if (endpoint_mode && !object_dual_direction_q && local_sender &&
                endpoint_valid_ack_pulse) begin
              // The DATA sender has just received the reverse ACK. Hold the
              // next DATA frame until the peer ACK transmitter's local TFDU
              // receiver has completed the same bounded recovery interval.
              phase_q <= PH_DATA_GUARD;
              phase_guard_q <= EFFECTIVE_ACK_TURNAROUND_GUARD_CYCLES + 0;
            end else if (dp_local_ack_valid && !dp_local_ack_ready_q &&
                         !(object_dual_direction_q && dp_attempt_valid &&
                           dp_attempt_ready) &&
                         (!object_dual_direction_q ||
                          p10_5_control_fallback_wait_q >=
                          P10_5_CONTROL_FALLBACK_GRACE_CYCLES-1) &&
                         (object_dual_direction_q || !endpoint_mode ||
                          endpoint_turnaround_ack_eligible)) begin
              if (dp_local_ack_snapshot_stale) begin
                // A timer may have frozen an ACK snapshot while the bounded
                // DATA burst was still arriving or while an in-order delivery
                // run was releasing receiver credit. Consume that stale local
                // snapshot without transmitting it; the held direction
                // boundary immediately requests a fresh cumulative ACK.
                dp_local_ack_ready_q <= 1;
                p10_5_control_fallback_wait_q <= 0;
              end else if (drop_ack_remaining_q != 0) begin
                drop_ack_remaining_q <= drop_ack_remaining_q - 1'b1;
                dropped_ack_count_q <= dropped_ack_count_q + 1'b1;
                dp_local_ack_ready_q <= 1;
                p10_5_control_fallback_wait_q <= 0;
              end else begin
                phase_q <= PH_ACK_GUARD;
                phase_guard_q <= object_dual_direction_q ? 0 :
                    EFFECTIVE_ACK_TURNAROUND_GUARD_CYCLES;
              end
            end
          end
          PH_ACK_GUARD: if (lanes_idle && ack_schedulable_lane_mask != 0) begin
            if (phase_guard_q != 0) phase_guard_q <= phase_guard_q - 1'b1;
            else if (dp_local_ack_snapshot_stale) begin
              // Credit, base, or SACK state can change during the physical
              // turnaround guard. Never advertise that frozen state after the
              // guard: keep the direction boundary pending and recapture the
              // cumulative ACK before serialization.
              dp_local_ack_ready_q <= 1;
              phase_q <= PH_DATA;
            end else begin
              ack_lane_q <= ack_selected_lane;
              lane_frame_ack[ack_selected_lane] <= 1;
              lane_session[ack_selected_lane] <= dp_local_ack_session;
              lane_path[ack_selected_lane] <= object_dual_direction_q ?
                  object_rx_path_q : object_path_q;
              lane_sequence[ack_selected_lane] <= 0;
              lane_length[ack_selected_lane] <= 0;
              lane_crc[ack_selected_lane] <= 0;
              lane_flags[ack_selected_lane] <= 0;
              lane_source_node[ack_selected_lane] <=
                  object_dual_direction_q ? local_node_id :
                  (object_direction_q ? 6'd1 : 6'd2);
              lane_object[ack_selected_lane] <= 0;
              lane_fragment[ack_selected_lane] <= 0;
              lane_ack_base[ack_selected_lane] <= dp_local_ack_base;
              lane_ack_bitmap[ack_selected_lane] <= dp_local_ack_bitmap;
              lane_ack_credit[ack_selected_lane] <= dp_local_ack_credit;
              lane_vnext[ack_selected_lane] <= object_dual_direction_q;
              lane_direction[ack_selected_lane] <= local_rx_direction;
              lane_role_epoch[ack_selected_lane] <= object_role_epoch_q;
              lane_piggyback_ack_valid[ack_selected_lane] <= 0;
              lane_piggyback_ack_direction[ack_selected_lane] <= 0;
              lane_piggyback_ack_session[ack_selected_lane] <= 0;
              lane_piggyback_ack_base[ack_selected_lane] <= 0;
              lane_piggyback_ack_bitmap[ack_selected_lane] <= 0;
              lane_piggyback_ack_credit[ack_selected_lane] <= 0;
              lane_start_pending[ack_selected_lane] <= 1;
              if (object_dual_direction_q)
                // Clear only at snapshot capture. A same-edge RX acceptance
                // or delivery reasserts dirty and restarts the bounded
                // fallback interval; both survive the later start handshake.
                p10_5_ack_dirty_q <=
                    dp_rx_accept_pulse || dp_rx_delivery_delayed_q;
              if (object_dual_direction_q)
                p10_5_control_fallback_wait_q <= 0;
              if (object_dual_direction_q)
                p10_5_control_ack_fallback_count_q <=
                    p10_5_control_ack_fallback_count_q + 1'b1;
              phase_q <= PH_ACK_START;
            end
          end
          PH_ACK_WAIT_DONE: if (serializer_done[ack_lane_q]) begin
            if (object_dual_direction_q) begin
              phase_q <= PH_DATA;
            end else if (endpoint_mode) begin
              // The independent receiver node owns the ACK transmitter. For
              // the bounded duplicate-ACK injection, repeat the retained ACK
              // metadata on the real reverse optical path exactly once. The
              // sender must consume and reject that second cumulative ACK.
              if (fault_flags_remaining_q[5]) begin
                fault_flags_remaining_q[5] <= 0;
                phase_q <= PH_ACK_REPEAT_WAIT;
              end else begin
                // The peer consumes the ACK; this node must not wait to
                // receive its own reverse frame through a fixture loopback.
                phase_q <= PH_DATA_GUARD;
                phase_guard_q <= EFFECTIVE_ACK_TURNAROUND_GUARD_CYCLES + 0;
              end
            end else begin
              phase_q <= PH_ACK_WAIT_RX;
              ack_wait_q <= 0;
            end
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
                phase_guard_q <= EFFECTIVE_ACK_TURNAROUND_GUARD_CYCLES;
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

      // Raw validation traffic uses the same physical pulse/accountant path
      // but not the DATA-frame schedule.  Any request therefore invalidates
      // the qualification, even if another guard later rejects that request.
      if (raw_start_i) begin
        for (copy_lane = 0; copy_lane < LANE_COUNT; copy_lane = copy_lane + 1)
          frame_schedule_valid_q[copy_lane] <= 0;
      end
    end
  end

  // Raw matrix generator.  It shares only the final physical pulse request;
  // its receiver evidence comes from the independent active-low Rxd counters.
  reg raw_busy_q;
  reg raw_done_q;
  reg raw_direction_q;
  reg [LANE_COUNT-1:0] raw_mask_q;
  reg [31:0] raw_target_q;
  reg [31:0] raw_spacing_q;
  reg [31:0] raw_cycle_q;
  reg [31:0] raw_sent_q;
  // Match one normal 4PPM optical chip at 64 MHz.  The previous five-cycle
  // diagnostic pulse was only 78.125 ns and was not representative of the
  // qualified physical waveform.  Raw diagnostics still traverse the same
  // final arm, kill, pulse-width, one-hot, and exact-duty safety boundary.
  localparam integer RAW_CONNECTIVITY_PULSE_CYCLES = 8;
  wire raw_pulse_request =
      raw_busy_q && raw_cycle_q < RAW_CONNECTIVITY_PULSE_CYCLES;
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

  wire [LANE_COUNT-1:0] a_tx_request;
  wire [LANE_COUNT-1:0] b_tx_request;
  generate
    for (tx_lane = 0; tx_lane < LANE_COUNT; tx_lane = tx_lane + 1) begin : g_tx_route
      assign a_tx_request[tx_lane] = endpoint_armed_q && !tx_kill &&
          ((serializer_pulse[tx_lane] && lane_source_a[tx_lane]) ||
           (raw_pulse_request && !raw_direction_q && raw_mask_q[tx_lane]));
      assign b_tx_request[tx_lane] = endpoint_armed_q && !tx_kill &&
          ((serializer_pulse[tx_lane] && !lane_source_a[tx_lane]) ||
           (raw_pulse_request && raw_direction_q && raw_mask_q[tx_lane]));
    end
  endgenerate

  // Two physical endpoints, each with LANE_COUNT independent TFDU safety
  // paths and exact sliding-duty accountants.
  wire [31:0] a_raw_count [0:LANE_COUNT-1];
  wire [31:0] b_raw_count [0:LANE_COUNT-1];
  wire [31:0] a_high_current [0:LANE_COUNT-1];
  wire [31:0] b_high_current [0:LANE_COUNT-1];
  wire [31:0] a_high_max [0:LANE_COUNT-1];
  wire [31:0] b_high_max [0:LANE_COUNT-1];
  wire [31:0] a_duty_max [0:LANE_COUNT-1];
  wire [31:0] b_duty_max [0:LANE_COUNT-1];
  wire [31:0] a_duty_current [0:LANE_COUNT-1];
  wire [31:0] b_duty_current [0:LANE_COUNT-1];
  wire [31:0] a_window [0:LANE_COUNT-1];
  wire [31:0] b_window [0:LANE_COUNT-1];
  wire [31:0] a_hard_limit [0:LANE_COUNT-1];
  wire [31:0] b_hard_limit [0:LANE_COUNT-1];
  wire [31:0] a_target_limit [0:LANE_COUNT-1];
  wire [31:0] b_target_limit [0:LANE_COUNT-1];
  wire [31:0] a_duty_headroom [0:LANE_COUNT-1];
  wire [31:0] b_duty_headroom [0:LANE_COUNT-1];
  wire [31:0] a_target_throttle_count [0:LANE_COUNT-1];
  wire [31:0] b_target_throttle_count [0:LANE_COUNT-1];
  wire [31:0] a_hard_fault_count [0:LANE_COUNT-1];
  wire [31:0] b_hard_fault_count [0:LANE_COUNT-1];
  // Any detected or archived first fault is a full-endpoint shutdown.  This
  // raises every SD and kills every Txd without waiting for PS evidence reads.
  wire physical_enable = receiver_enable_q && !shutdown_latched_q &&
                         !any_safety_fault;

  generate
    for (tx_lane = 0; tx_lane < LANE_COUNT; tx_lane = tx_lane + 1) begin : g_physical
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
        .rx_pulse_width_max(), .rx_last_timestamp(),
        .tx_high_width_current(a_high_current[tx_lane]),
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
        .rx_pulse_width_max(), .rx_last_timestamp(),
        .tx_high_width_current(b_high_current[tx_lane]),
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
      assign raw_rx_counts_flat_o[32*tx_lane +: 32] = a_raw_count[tx_lane];
      assign raw_rx_counts_flat_o[32*(LANE_COUNT+tx_lane) +: 32] = b_raw_count[tx_lane];
      assign physical_tx_counts_flat_o[32*tx_lane +: 32] = a_tx_count[tx_lane];
      assign physical_tx_counts_flat_o[32*(LANE_COUNT+tx_lane) +: 32] = b_tx_count[tx_lane];
      assign tx_high_current_flat_o[32*tx_lane +: 32] = a_high_current[tx_lane];
      assign tx_high_current_flat_o[32*(LANE_COUNT+tx_lane) +: 32] =
          b_high_current[tx_lane];
      assign tx_high_max_flat_o[32*tx_lane +: 32] = a_high_max[tx_lane];
      assign tx_high_max_flat_o[32*(LANE_COUNT+tx_lane) +: 32] = b_high_max[tx_lane];
      assign duty_high_max_flat_o[32*tx_lane +: 32] = a_duty_max[tx_lane];
      assign duty_high_max_flat_o[32*(LANE_COUNT+tx_lane) +: 32] = b_duty_max[tx_lane];
      assign duty_high_current_flat_o[32*tx_lane +: 32] = a_duty_current[tx_lane];
      assign duty_high_current_flat_o[32*(LANE_COUNT+tx_lane) +: 32] = b_duty_current[tx_lane];
      assign duty_headroom_flat_o[32*tx_lane +: 32] = a_duty_headroom[tx_lane];
      assign duty_headroom_flat_o[32*(LANE_COUNT+tx_lane) +: 32] = b_duty_headroom[tx_lane];
      assign duty_target_throttle_count_flat_o[32*tx_lane +: 32] =
          a_target_throttle_count[tx_lane];
      assign duty_target_throttle_count_flat_o[32*(LANE_COUNT+tx_lane) +: 32] =
          b_target_throttle_count[tx_lane];
      assign duty_hard_fault_count_flat_o[32*tx_lane +: 32] =
          a_hard_fault_count[tx_lane];
      assign duty_hard_fault_count_flat_o[32*(LANE_COUNT+tx_lane) +: 32] =
          b_hard_fault_count[tx_lane];
    end
  endgenerate
  assign duty_window_cycles_o = a_window[0];
  assign duty_hard_limit_cycles_o = a_hard_limit[0];
  assign duty_target_limit_cycles_o = a_target_limit[0];

  // Each logical lane is half duplex: the scheduled DATA frame and its ACK
  // never overlap on that lane.  Time-share one decoder/parser per lane and
  // select the physical destination Rxd explicitly.  This preserves four
  // independent physical safety paths while avoiding four redundant protocol
  // parsers on the resource-limited Z7010.
  wire [1:0] rx_symbol [0:LANE_COUNT-1];
  wire [LANE_COUNT-1:0] rx_symbol_valid;
  wire [LANE_COUNT-1:0] rx_symbol_error;
  wire [LANE_COUNT-1:0] rx_preamble;
  wire [LANE_COUNT-1:0] rx_payload_we;
  wire [7:0] rx_payload_index [0:LANE_COUNT-1];
  wire [7:0] rx_payload_data [0:LANE_COUNT-1];
  wire [LANE_COUNT-1:0] rx_frame_valid;
  wire [LANE_COUNT-1:0] rx_frame_ack;
  wire [LANE_COUNT-1:0] rx_frame_crc;
  wire [31:0] rx_frame_session [0:LANE_COUNT-1];
  wire [15:0] rx_frame_path [0:LANE_COUNT-1];
  wire [15:0] rx_frame_sequence [0:LANE_COUNT-1];
  wire [15:0] rx_frame_length [0:LANE_COUNT-1];
  wire [7:0] rx_frame_flags [0:LANE_COUNT-1];
  wire [7:0] rx_frame_lane_id [0:LANE_COUNT-1];
  wire [31:0] rx_frame_object [0:LANE_COUNT-1];
  wire [31:0] rx_frame_fragment [0:LANE_COUNT-1];
  wire [5:0] rx_frame_source_node [0:LANE_COUNT-1];
  wire [15:0] rx_ack_base [0:LANE_COUNT-1];
  wire [31:0] rx_ack_bitmap [0:LANE_COUNT-1];
  wire [15:0] rx_ack_credit [0:LANE_COUNT-1];
  wire [LANE_COUNT-1:0] rx_ack_direction;
  wire [LANE_COUNT-1:0] rx_frame_vnext;
  wire [15:0] rx_frame_role_epoch [0:LANE_COUNT-1];
  wire [LANE_COUNT-1:0] rx_piggyback_ack_valid;
  wire [LANE_COUNT-1:0] rx_piggyback_ack_direction;
  wire [31:0] rx_piggyback_ack_session [0:LANE_COUNT-1];
  wire [15:0] rx_piggyback_ack_base [0:LANE_COUNT-1];
  wire [31:0] rx_piggyback_ack_bitmap [0:LANE_COUNT-1];
  wire [15:0] rx_piggyback_ack_credit [0:LANE_COUNT-1];
  wire [31:0] rx_good [0:LANE_COUNT-1];
  wire [31:0] rx_crc_bad [0:LANE_COUNT-1];
  wire [31:0] rx_frame_bad [0:LANE_COUNT-1];
  wire [31:0] rx_preamble_count [0:LANE_COUNT-1];
  wire [31:0] rx_symbol_error_count [0:LANE_COUNT-1];
  wire [LANE_COUNT-1:0] rx_admission_enable;
  wire [LANE_COUNT-1:0] rx_decoder_clear;
  wire [LANE_COUNT-1:0] rx_echo_quarantine;
  wire [LANE_COUNT-1:0] rx_post_tx_guard;
  wire [31:0] rx_admission_raw_count [0:LANE_COUNT-1];
  wire [31:0] rx_raw_while_local_tx [0:LANE_COUNT-1];
  wire [31:0] rx_blanked_raw_pulse [0:LANE_COUNT-1];
  wire [31:0] rx_guard_total [0:LANE_COUNT-1];
  wire [31:0] rx_guard_current [0:LANE_COUNT-1];
  wire [31:0] rx_guard_max [0:LANE_COUNT-1];
  wire [31:0] rx_echo_tail_max [0:LANE_COUNT-1];
  wire [31:0] rx_decoder_clear_count [0:LANE_COUNT-1];
  wire [31:0] rx_overlap_violation [0:LANE_COUNT-1];
  wire [31:0] rx_admission_violation [0:LANE_COUNT-1];
  wire [31:0] rx_last_txd_rise [0:LANE_COUNT-1];
  wire [31:0] rx_last_txd_fall [0:LANE_COUNT-1];
  wire [31:0] rx_first_rxd_after_tx [0:LANE_COUNT-1];
  wire [31:0] rx_last_rxd_after_tx [0:LANE_COUNT-1];
  wire [31:0] rx_last_raw_timestamp [0:LANE_COUNT-1];
  wire [1:0] rx_shadow_symbol [0:LANE_COUNT-1];
  wire [LANE_COUNT-1:0] rx_shadow_symbol_valid;
  wire [LANE_COUNT-1:0] rx_shadow_symbol_error;
  wire [LANE_COUNT-1:0] rx_shadow_preamble;
  wire [LANE_COUNT-1:0] rx_shadow_frame_valid;
  wire [LANE_COUNT-1:0] rx_shadow_frame_crc;
  assign endpoint_turnaround_request_pulse = endpoint_mode && local_receiver &&
      dp_turnaround_pipe_q[1];
  (* ram_style="block" *) reg [7:0] rx_temp [0:LANE_COUNT-1][0:MAX_PAYLOAD_BYTES-1];

  generate
    for (tx_lane = 0; tx_lane < LANE_COUNT; tx_lane = tx_lane + 1) begin : g_receive
      // P9 time-shares a parser with the selected internal destination.  P10
      // instead keeps each independent node's local receiver open for the
      // complete object so DATA and reverse ACK frames cross the optical link.
      wire serializer_busy_rise = serializer_busy[tx_lane] &&
          !serializer_busy_d[tx_lane];
      wire selected_phy_ready = endpoint_mode ? local_phy_ready[tx_lane] :
          (receive_tail_destination_b[tx_lane] ?
           b_phy_ready[tx_lane] : a_phy_ready[tx_lane]);
      wire selected_rx_pulse = endpoint_mode ?
          (local_is_a ? a_rx_pulse[tx_lane] : b_rx_pulse[tx_lane]) :
          (receive_tail_destination_b[tx_lane] ?
           b_rx_pulse[tx_lane] : a_rx_pulse[tx_lane]);
      wire selected_final_txd = local_is_a ?
          a_txd_o[tx_lane] : b_txd_o[tx_lane];
      wire selected_rx_quarantine_source = endpoint_mode ?
          local_rx_quarantine_source[tx_lane] : selected_final_txd;

      p10_1r_rx_admission #(
        .MIN_POST_TX_GUARD_CYCLES(RX_MIN_POST_TX_GUARD_CYCLES),
        .IDLE_QUALIFY_CYCLES(RX_IDLE_QUALIFY_CYCLES),
        .MAX_QUARANTINE_CYCLES(RX_MAX_QUARANTINE_CYCLES)
      ) u_rx_admission (
        .clk(clk), .rst_n(rst_n), .clear_counters_i(clear_counters_i),
        .receiver_enable_i(endpoint_mode && selected_phy_ready),
        // The signal remains derived exclusively from actual final Txd.  In
        // endpoint mode it includes an adjacent physical ACK on the same
        // two-module connector, but never an ordinary peer-lane DATA TX.
        .final_physical_txd_i(selected_rx_quarantine_source),
        .raw_rx_pulse_i(selected_rx_pulse),
        .rx_frame_accept_enable_o(rx_admission_enable[tx_lane]),
        .rx_decoder_clear_o(rx_decoder_clear[tx_lane]),
        .echo_quarantine_o(rx_echo_quarantine[tx_lane]),
        .post_tx_guard_active_o(rx_post_tx_guard[tx_lane]),
        .raw_pulse_count_o(rx_admission_raw_count[tx_lane]),
        .raw_while_local_tx_count_o(rx_raw_while_local_tx[tx_lane]),
        .blanked_raw_pulse_count_o(rx_blanked_raw_pulse[tx_lane]),
        .guard_total_cycles_o(rx_guard_total[tx_lane]),
        .guard_current_cycles_o(rx_guard_current[tx_lane]),
        .guard_max_cycles_o(rx_guard_max[tx_lane]),
        .echo_tail_max_cycles_o(rx_echo_tail_max[tx_lane]),
        .decoder_clear_count_o(rx_decoder_clear_count[tx_lane]),
        .overlap_violation_count_o(rx_overlap_violation[tx_lane]),
        .admission_violation_count_o(rx_admission_violation[tx_lane]),
        .last_physical_txd_rise_o(rx_last_txd_rise[tx_lane]),
        .last_physical_txd_fall_o(rx_last_txd_fall[tx_lane]),
        .first_local_rxd_edge_after_tx_o(rx_first_rxd_after_tx[tx_lane]),
        .last_local_rxd_edge_after_tx_o(rx_last_rxd_after_tx[tx_lane]),
        .last_raw_rx_timestamp_o(rx_last_raw_timestamp[tx_lane])
      );

      wire receive_window = endpoint_mode ?
          (object_active_q && rx_admission_enable[tx_lane]) :
          (serializer_busy[tx_lane] || receive_tail[tx_lane] != 0);
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
                 (endpoint_mode && rx_decoder_clear[tx_lane]) ||
                 rx_frame_valid[tx_lane]),
        .rx_pulse_active_i(selected_rx_pulse), .symbol_o(rx_symbol[tx_lane]),
        .symbol_valid_o(rx_symbol_valid[tx_lane]),
        .symbol_error_o(rx_symbol_error[tx_lane]),
        .preamble_valid_o(rx_preamble[tx_lane]), .preamble_count_o(), .symbol_chips_o()
      );
      p9_4ppm_frame_rx #(.LANE_COUNT(LANE_COUNT)) u_parser (
        .clk(clk), .rst_n(rst_n), .enable_i(selected_phy_ready),
        .align_i(!receive_window ||
                 (endpoint_mode && rx_decoder_clear[tx_lane])),
        .symbol_i(rx_symbol[tx_lane]), .symbol_valid_i(rx_symbol_valid[tx_lane]),
        .symbol_error_i(rx_symbol_error[tx_lane]), .preamble_valid_i(rx_preamble[tx_lane]),
        .payload_write_pulse_o(rx_payload_we[tx_lane]),
        .payload_write_index_o(rx_payload_index[tx_lane]),
        .payload_write_data_o(rx_payload_data[tx_lane]), .frame_valid_o(rx_frame_valid[tx_lane]),
        .frame_is_ack_o(rx_frame_ack[tx_lane]), .frame_crc_valid_o(rx_frame_crc[tx_lane]),
        .session_epoch_o(rx_frame_session[tx_lane]), .path_epoch_o(rx_frame_path[tx_lane]),
        .sequence_o(rx_frame_sequence[tx_lane]), .payload_length_o(rx_frame_length[tx_lane]),
        .flags_o(rx_frame_flags[tx_lane]),
        .lane_id_o(rx_frame_lane_id[tx_lane]),
        .source_node_id_o(rx_frame_source_node[tx_lane]),
        .object_id_o(rx_frame_object[tx_lane]),
        .fragment_offset_o(rx_frame_fragment[tx_lane]), .ack_base_o(rx_ack_base[tx_lane]),
        .ack_bitmap_o(rx_ack_bitmap[tx_lane]), .ack_credit_o(rx_ack_credit[tx_lane]),
        .direction_o(rx_ack_direction[tx_lane]),
        .vnext_o(rx_frame_vnext[tx_lane]),
        .role_epoch_o(rx_frame_role_epoch[tx_lane]),
        .piggyback_ack_valid_o(rx_piggyback_ack_valid[tx_lane]),
        .piggyback_ack_direction_o(rx_piggyback_ack_direction[tx_lane]),
        .piggyback_ack_session_o(rx_piggyback_ack_session[tx_lane]),
        .piggyback_ack_base_o(rx_piggyback_ack_base[tx_lane]),
        .piggyback_ack_bitmap_o(rx_piggyback_ack_bitmap[tx_lane]),
        .piggyback_ack_credit_o(rx_piggyback_ack_credit[tx_lane]),
        .frame_good_count_o(rx_good[tx_lane]),
        .frame_bad_count_o(rx_frame_bad[tx_lane]),
        .crc_bad_count_o(rx_crc_bad[tx_lane]),
        .preamble_count_o(rx_preamble_count[tx_lane]),
        .symbol_error_count_o(rx_symbol_error_count[tx_lane])
      );

      // Read-only shadow decode preserves evidence about a blanked local
      // echo.  It cannot write the receive window, generate an ACK, light an
      // activity LED, or affect admission.  Its only consumers are the two
      // observability counters below.
      p9_rate_4ppm_rx u_echo_shadow_codec (
        .clk(clk), .rst_n(rst_n), .enable_i(endpoint_mode && selected_phy_ready),
        .rate_select_i(object_rate_q),
        .align_i(rx_shadow_frame_valid[tx_lane]),
        .rx_pulse_active_i(selected_rx_pulse),
        .symbol_o(rx_shadow_symbol[tx_lane]),
        .symbol_valid_o(rx_shadow_symbol_valid[tx_lane]),
        .symbol_error_o(rx_shadow_symbol_error[tx_lane]),
        .preamble_valid_o(rx_shadow_preamble[tx_lane]),
        .preamble_count_o(), .symbol_chips_o()
      );
      p9_4ppm_frame_rx #(.LANE_COUNT(LANE_COUNT)) u_echo_shadow_parser (
        .clk(clk), .rst_n(rst_n),
        .enable_i(endpoint_mode && selected_phy_ready),
        .align_i(!endpoint_mode || !selected_phy_ready),
        .symbol_i(rx_shadow_symbol[tx_lane]),
        .symbol_valid_i(rx_shadow_symbol_valid[tx_lane]),
        .symbol_error_i(rx_shadow_symbol_error[tx_lane]),
        .preamble_valid_i(rx_shadow_preamble[tx_lane]),
        .payload_write_pulse_o(), .payload_write_index_o(),
        .payload_write_data_o(),
        .frame_valid_o(rx_shadow_frame_valid[tx_lane]), .frame_is_ack_o(),
        .frame_crc_valid_o(rx_shadow_frame_crc[tx_lane]),
        .session_epoch_o(), .path_epoch_o(), .sequence_o(),
        .payload_length_o(), .flags_o(), .lane_id_o(), .source_node_id_o(),
        .object_id_o(), .fragment_offset_o(), .ack_base_o(),
        .ack_bitmap_o(), .ack_credit_o(), .direction_o(), .vnext_o(),
        .role_epoch_o(), .piggyback_ack_valid_o(),
        .piggyback_ack_direction_o(), .piggyback_ack_session_o(),
        .piggyback_ack_base_o(),
        .piggyback_ack_bitmap_o(), .piggyback_ack_credit_o(),
        .frame_good_count_o(), .frame_bad_count_o(), .crc_bad_count_o(),
        .preamble_count_o(), .symbol_error_count_o()
      );
    end
  endgenerate

  wire [LANE_COUNT-1:0] rx_role_valid;
  wire [LANE_COUNT-1:0] rx_remote_accepted;
  wire [LANE_COUNT-1:0] rx_local_source_rejected;
  wire [LANE_COUNT-1:0] rx_p10_5_epoch_valid;
  wire [LANE_COUNT-1:0] rx_p10_5_direction_valid;
  reg [31:0] physical_data_good_q;
  reg [31:0] physical_ack_good_q;
  reg [31:0] physical_data_good_lane_q [0:LANE_COUNT-1];
  reg [31:0] physical_ack_good_lane_q [0:LANE_COUNT-1];
  reg [31:0] rx_local_source_reject_q [0:LANE_COUNT-1];
  reg [31:0] rx_accepted_remote_q [0:LANE_COUNT-1];
  reg [31:0] rx_blanked_frame_start_q [0:LANE_COUNT-1];
  reg [31:0] rx_blanked_crc_valid_q [0:LANE_COUNT-1];
  reg [31:0] rx_non_target_accepted_q;
  reg [31:0] rx_cross_lane_accepted_q;
  reg [31:0] physical_data_good_increment;
  reg [31:0] physical_ack_good_increment;
  reg [31:0] physical_crc_bad_sum;
  reg [31:0] physical_frame_bad_sum;
  reg [31:0] physical_preamble_sum;
  reg [31:0] physical_symbol_error_sum;
  reg [31:0] rx_overlap_violation_sum;
  reg [31:0] rx_admission_violation_sum;
  reg any_non_target_accepted;
  reg any_cross_lane_accepted;
  integer sum_lane;
  integer counter_lane;

  genvar rx_status_lane;
  generate
    for (rx_status_lane = 0; rx_status_lane < LANE_COUNT;
         rx_status_lane = rx_status_lane + 1) begin : g_rx_status
      assign rx_p10_5_epoch_valid[rx_status_lane] =
          rx_frame_vnext[rx_status_lane] &&
          rx_frame_role_epoch[rx_status_lane] == object_role_epoch_q;
      assign rx_p10_5_direction_valid[rx_status_lane] =
          rx_ack_direction[rx_status_lane] ==
          (rx_frame_ack[rx_status_lane] ? local_tx_direction :
                                          local_rx_direction);
      assign rx_role_valid[rx_status_lane] = object_dual_direction_q ?
          (rx_p10_5_epoch_valid[rx_status_lane] &&
           rx_p10_5_direction_valid[rx_status_lane]) :
          (!endpoint_mode ||
           (rx_frame_ack[rx_status_lane] ? local_sender : local_receiver));
      assign rx_remote_accepted[rx_status_lane] =
          rx_frame_valid[rx_status_lane] && rx_frame_crc[rx_status_lane] &&
          selected_rx_lane_mask[rx_status_lane] &&
          rx_frame_lane_id[rx_status_lane] == rx_status_lane &&
          (!endpoint_mode ||
           (rx_admission_enable[rx_status_lane] &&
            rx_frame_source_node[rx_status_lane] != local_node_id &&
            rx_role_valid[rx_status_lane]));
      assign rx_local_source_rejected[rx_status_lane] = endpoint_mode &&
          ((rx_frame_valid[rx_status_lane] && rx_frame_crc[rx_status_lane] &&
            rx_frame_source_node[rx_status_lane] == local_node_id) ||
           (local_source_test_inject_i[rx_status_lane] &&
            effective_full_shutdown_o && tx_kill && !object_active_q));
      assign physical_data_good_by_lane_o[32*rx_status_lane +: 32] =
          physical_data_good_lane_q[rx_status_lane];
      assign physical_ack_good_by_lane_o[32*rx_status_lane +: 32] =
          physical_ack_good_lane_q[rx_status_lane];
      assign physical_crc_bad_by_lane_o[32*rx_status_lane +: 32] =
          rx_crc_bad[rx_status_lane];
      assign physical_frame_bad_by_lane_o[32*rx_status_lane +: 32] =
          rx_frame_bad[rx_status_lane];
      assign physical_preamble_by_lane_o[32*rx_status_lane +: 32] =
          rx_preamble_count[rx_status_lane];
      assign physical_symbol_error_by_lane_o[32*rx_status_lane +: 32] =
          rx_symbol_error_count[rx_status_lane];
      assign rx_raw_while_local_tx_flat_o[32*rx_status_lane +: 32] =
          rx_raw_while_local_tx[rx_status_lane];
      assign rx_blanked_raw_pulse_flat_o[32*rx_status_lane +: 32] =
          rx_blanked_raw_pulse[rx_status_lane];
      assign rx_blanked_frame_start_flat_o[32*rx_status_lane +: 32] =
          rx_blanked_frame_start_q[rx_status_lane];
      assign rx_blanked_crc_valid_flat_o[32*rx_status_lane +: 32] =
          rx_blanked_crc_valid_q[rx_status_lane];
      assign rx_local_source_reject_flat_o[32*rx_status_lane +: 32] =
          rx_local_source_reject_q[rx_status_lane];
      assign rx_accepted_remote_flat_o[32*rx_status_lane +: 32] =
          rx_accepted_remote_q[rx_status_lane];
      assign rx_guard_total_flat_o[32*rx_status_lane +: 32] =
          rx_guard_total[rx_status_lane];
      assign rx_guard_max_flat_o[32*rx_status_lane +: 32] =
          rx_guard_max[rx_status_lane];
      assign rx_echo_tail_max_flat_o[32*rx_status_lane +: 32] =
          rx_echo_tail_max[rx_status_lane];
      assign rx_last_txd_rise_flat_o[32*rx_status_lane +: 32] =
          rx_last_txd_rise[rx_status_lane];
      assign rx_last_txd_fall_flat_o[32*rx_status_lane +: 32] =
          rx_last_txd_fall[rx_status_lane];
      assign rx_first_rxd_after_tx_flat_o[32*rx_status_lane +: 32] =
          rx_first_rxd_after_tx[rx_status_lane];
      assign rx_last_rxd_after_tx_flat_o[32*rx_status_lane +: 32] =
          rx_last_rxd_after_tx[rx_status_lane];
      assign rx_decoder_clear_count_flat_o[32*rx_status_lane +: 32] =
          rx_decoder_clear_count[rx_status_lane];
    end
  endgenerate

  always @* begin
    physical_data_good_increment = 0;
    physical_ack_good_increment = 0;
    physical_crc_bad_sum = 0;
    physical_frame_bad_sum = 0;
    physical_preamble_sum = 0;
    physical_symbol_error_sum = 0;
    rx_overlap_violation_sum = 0;
    rx_admission_violation_sum = 0;
    any_non_target_accepted = 0;
    any_cross_lane_accepted = 0;
    for (sum_lane = 0; sum_lane < LANE_COUNT; sum_lane = sum_lane + 1) begin
      if (rx_remote_accepted[sum_lane] && !rx_frame_ack[sum_lane])
        physical_data_good_increment = physical_data_good_increment + 1'b1;
      if (rx_remote_accepted[sum_lane] && rx_frame_ack[sum_lane])
        physical_ack_good_increment = physical_ack_good_increment + 1'b1;
      physical_crc_bad_sum = physical_crc_bad_sum + rx_crc_bad[sum_lane];
      physical_frame_bad_sum = physical_frame_bad_sum + rx_frame_bad[sum_lane];
      physical_preamble_sum = physical_preamble_sum + rx_preamble_count[sum_lane];
      physical_symbol_error_sum =
          physical_symbol_error_sum + rx_symbol_error_count[sum_lane];
      rx_overlap_violation_sum =
          rx_overlap_violation_sum + rx_overlap_violation[sum_lane];
      rx_admission_violation_sum =
          rx_admission_violation_sum + rx_admission_violation[sum_lane];
      if (rx_frame_valid[sum_lane] && rx_frame_crc[sum_lane] &&
          !selected_rx_lane_mask[sum_lane])
        any_non_target_accepted = 1'b1;
      if (rx_remote_accepted[sum_lane] && rx_frame_lane_id[sum_lane] != sum_lane)
        any_cross_lane_accepted = 1'b1;
    end
  end

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n || clear_counters_i) begin
      physical_data_good_q <= 0;
      physical_ack_good_q <= 0;
      rx_non_target_accepted_q <= 0;
      rx_cross_lane_accepted_q <= 0;
      for (counter_lane = 0; counter_lane < LANE_COUNT;
           counter_lane = counter_lane + 1) begin
        physical_data_good_lane_q[counter_lane] <= 0;
        physical_ack_good_lane_q[counter_lane] <= 0;
        rx_local_source_reject_q[counter_lane] <= 0;
        rx_accepted_remote_q[counter_lane] <= 0;
        rx_blanked_frame_start_q[counter_lane] <= 0;
        rx_blanked_crc_valid_q[counter_lane] <= 0;
      end
    end else begin
      physical_data_good_q <=
          sat_add32(physical_data_good_q, physical_data_good_increment);
      physical_ack_good_q <=
          sat_add32(physical_ack_good_q, physical_ack_good_increment);
      if (any_non_target_accepted)
        rx_non_target_accepted_q <= sat_inc32(rx_non_target_accepted_q);
      if (any_cross_lane_accepted)
        rx_cross_lane_accepted_q <= sat_inc32(rx_cross_lane_accepted_q);
      for (counter_lane = 0; counter_lane < LANE_COUNT;
           counter_lane = counter_lane + 1) begin
        if (rx_remote_accepted[counter_lane] && !rx_frame_ack[counter_lane])
          physical_data_good_lane_q[counter_lane] <=
              sat_inc32(physical_data_good_lane_q[counter_lane]);
        if (rx_remote_accepted[counter_lane] && rx_frame_ack[counter_lane])
          physical_ack_good_lane_q[counter_lane] <=
              sat_inc32(physical_ack_good_lane_q[counter_lane]);
        if (rx_local_source_rejected[counter_lane])
          rx_local_source_reject_q[counter_lane] <=
              sat_inc32(rx_local_source_reject_q[counter_lane]);
        if (rx_remote_accepted[counter_lane])
          rx_accepted_remote_q[counter_lane] <=
              sat_inc32(rx_accepted_remote_q[counter_lane]);
        if (rx_shadow_preamble[counter_lane] && rx_echo_quarantine[counter_lane])
          rx_blanked_frame_start_q[counter_lane] <=
              sat_inc32(rx_blanked_frame_start_q[counter_lane]);
        if (rx_shadow_frame_valid[counter_lane] &&
            rx_shadow_frame_crc[counter_lane] &&
            rx_echo_quarantine[counter_lane])
          rx_blanked_crc_valid_q[counter_lane] <=
              sat_inc32(rx_blanked_crc_valid_q[counter_lane]);
      end
    end
  end

  assign physical_data_frames_good_o = physical_data_good_q;
  assign physical_ack_frames_good_o = physical_ack_good_q;
  assign physical_crc_bad_o = physical_crc_bad_sum;
  assign physical_frame_bad_o = physical_frame_bad_sum;
  assign physical_preamble_count_o = physical_preamble_sum;
  assign physical_symbol_error_count_o = physical_symbol_error_sum;
  // Activity indication consumes only accepted, CRC-valid remote events. It
  // never observes raw Rxd/self echo and has no return path into RX.
  assign valid_rx_frame_activity_o = rx_remote_accepted;
  generate
    if (LANE_COUNT == 2) begin : g_admission_status_2lane
      assign rx_admission_status_o = {18'd0, local_node_id, 2'd0,
          rx_admission_enable, rx_post_tx_guard, rx_echo_quarantine};
    end else if (LANE_COUNT == 4) begin : g_admission_status_4lane
      assign rx_admission_status_o = {2'd0, local_node_id, 12'd0,
          rx_admission_enable, rx_post_tx_guard, rx_echo_quarantine};
    end else begin : g_admission_status_8lane
      assign rx_admission_status_o = {2'd0, local_node_id,
          rx_admission_enable, rx_post_tx_guard, rx_echo_quarantine};
    end
  endgenerate
  assign rx_overlap_violation_count_o = rx_overlap_violation_sum;
  assign rx_admission_violation_count_o = rx_admission_violation_sum;
  assign rx_non_target_accepted_count_o = rx_non_target_accepted_q;
  assign rx_cross_lane_accepted_count_o = rx_cross_lane_accepted_q;

  // Receive completion queues and copy into the reorder-window store.
  reg [LANE_COUNT-1:0] rx_pending;
  reg [LANE_COUNT-1:0] rx_pending_l1;
  reg [31:0] rx_pending_session [0:LANE_COUNT-1];
  reg [15:0] rx_pending_path [0:LANE_COUNT-1];
  reg [15:0] rx_pending_sequence [0:LANE_COUNT-1];
  reg [15:0] rx_pending_length [0:LANE_COUNT-1];
  reg [LANE_COUNT-1:0] rx_pending_final;
  reg [LANE_COUNT-1:0] rx_pending_turnaround;
  reg [31:0] rx_pending_object [0:LANE_COUNT-1];
  (* ram_style="block" *) reg [7:0] rx_store [0:STORE_BYTES-1];
  reg rx_final_slot [0:WINDOW_SIZE-1];
  typedef enum reg [2:0] {
    RXC_IDLE, RXC_CLASSIFY, RXC_PRIME, RXC_COPY, RXC_PULSE
  } rxc_state_t;
  rxc_state_t rxc_state_q;
  reg [LANE_WIDTH-1:0] rxc_lane_q;
  reg [7:0] rxc_read_index_q;
  reg [7:0] rxc_write_index_q;
  reg [STORE_ADDR_WIDTH-1:0] rxc_base_q;
  reg rxc_payload_copied_q;
  reg [7:0] rx_temp_read_q [0:LANE_COUNT-1];
  reg reorder_hold_q;
  integer staging_lane;

  // The output backend may retire the current base on the same edge that the
  // copy coordinator classifies a newly completed physical frame.  Express
  // that one-entry shift as a boundary predicate instead of adding one to the
  // base before every modular subtraction.  The former expression cascaded
  // two 16-bit carry chains into the RX copy FSM and could not close 64 MHz.
  // RXC_CLASSIFY also registers the selected lane before the window decision,
  // keeping the fail-closed payload-copy invariant off that selection tree.
  wire rxc_base_retiring = dp_delivery_valid && dp_delivery_ready_q;

  always @(posedge clk) begin : rx_lane_staging_memories
    for (staging_lane = 0; staging_lane < LANE_COUNT;
         staging_lane = staging_lane + 1) begin
      if (rx_payload_we[staging_lane])
        rx_temp[staging_lane][rx_payload_index[staging_lane]] <=
            rx_payload_data[staging_lane];
      rx_temp_read_q[staging_lane] <=
          rx_temp[staging_lane][rxc_read_index_q];
    end
  end

  wire rxc_store_write = rxc_state_q == RXC_COPY && !start_object_i &&
      !abort_object_i && !disarm_request_i && !full_shutdown_request_i &&
      !rx_context_aborted_q;
  always @(posedge clk) begin : rx_payload_memory
    if (rxc_store_write)
      rx_store[rxc_base_q + rxc_write_index_q] <= rx_temp_read_q[rxc_lane_q];
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
    reg receive_in_window;
    reg [LANE_WIDTH-1:0] selected_lane;
    reg [15:0] selected_distance;
    integer pending_count;
    if (!rst_n) begin
      rxc_state_q <= RXC_IDLE;
      rxc_lane_q <= 0;
      rxc_read_index_q <= 0;
      rxc_write_index_q <= 0;
      rxc_base_q <= 0;
      rxc_payload_copied_q <= 0;
      dp_rx_frame_valid_q <= 0;
      dp_rx_l1_valid_q <= 0;
      dp_rx_turnaround_q <= 0;
      dp_rx_session_q <= 0;
      dp_rx_sequence_q <= 0;
      dp_rx_path_q <= 0;
      dp_rx_payload_ref_q <= 0;
      dp_rx_payload_length_q <= 0;
      reorder_hold_q <= 0;
      for (rx_lane = 0; rx_lane < LANE_COUNT; rx_lane = rx_lane + 1) begin
        rx_pending[rx_lane] <= 0;
        rx_pending_turnaround[rx_lane] <= 0;
      end
      for (rx_lane = 0; rx_lane < WINDOW_SIZE; rx_lane = rx_lane + 1) rx_final_slot[rx_lane] <= 0;
    end else begin
      dp_rx_frame_valid_q <= 0;
      dp_rx_turnaround_q <= 0;
      for (rx_lane = 0; rx_lane < LANE_COUNT; rx_lane = rx_lane + 1) begin
        // A deployed endpoint can optically observe its own transmitter.
        // Preserve that observation in the physical counters, but only the
        // endpoint that owns the receive role for this object may admit DATA
        // into the selective-repeat RX window.  Otherwise a sender-side
        // self-echo creates a local ACK snapshot that this role cannot emit
        // and permanently backpressures the next DATA attempt.
        data_event = rx_frame_valid[rx_lane] && !rx_frame_ack[rx_lane] &&
            !rx_context_aborted_q &&
            selected_rx_lane_mask[rx_lane] &&
            rx_frame_lane_id[rx_lane] == rx_lane &&
            (!endpoint_mode ||
             (local_receiver && rx_admission_enable[rx_lane] &&
              rx_frame_source_node[rx_lane] != local_node_id)) &&
            (!object_dual_direction_q ||
             (rx_p10_5_epoch_valid[rx_lane] &&
              rx_p10_5_direction_valid[rx_lane]));
        event_crc = rx_frame_crc[rx_lane];
        event_session = rx_frame_session[rx_lane];
        event_path = rx_frame_path[rx_lane];
        event_sequence = rx_frame_sequence[rx_lane];
        event_length = rx_frame_length[rx_lane];
        event_final = rx_frame_flags[rx_lane][0];
        event_object = rx_frame_object[rx_lane];
        if (data_event && !rx_pending[rx_lane]) begin
          rx_pending[rx_lane] <= 1;
          rx_pending_l1[rx_lane] <= event_crc &&
              event_object == (object_dual_direction_q ? object_rx_id_q :
                                                         object_id_q);
          rx_pending_session[rx_lane] <= event_session;
          rx_pending_path[rx_lane] <= event_path;
          rx_pending_sequence[rx_lane] <= event_sequence;
          rx_pending_length[rx_lane] <= event_length;
          rx_pending_final[rx_lane] <= event_final;
          // DATA headers do not encode direction; endpoint role and the
          // physical A/B link establish it. Bit 1 is the explicit burst
          // turnaround request carried in the DATA flags byte.
          rx_pending_turnaround[rx_lane] <=
              !object_dual_direction_q && rx_frame_flags[rx_lane][1];
          rx_pending_object[rx_lane] <= event_object;
        end
      end

      if (start_object_i) begin
        rxc_state_q <= RXC_IDLE;
        rxc_payload_copied_q <= 0;
        reorder_hold_q <= cfg_fault_flags_i[6];
        for (rx_lane = 0; rx_lane < LANE_COUNT; rx_lane = rx_lane + 1) begin
          rx_pending[rx_lane] <= 0;
          rx_pending_turnaround[rx_lane] <= 0;
        end
        for (rx_lane = 0; rx_lane < WINDOW_SIZE; rx_lane = rx_lane + 1) rx_final_slot[rx_lane] <= 0;
      end else if (abort_object_i || disarm_request_i ||
                   full_shutdown_request_i || rx_context_aborted_q) begin
        rxc_state_q <= RXC_IDLE;
        rxc_payload_copied_q <= 0;
        reorder_hold_q <= 0;
        for (rx_lane = 0; rx_lane < LANE_COUNT; rx_lane = rx_lane + 1) begin
          rx_pending[rx_lane] <= 0;
          rx_pending_turnaround[rx_lane] <= 0;
        end
      end else begin
        case (rxc_state_q)
          RXC_IDLE: begin
            // A bounded validation-only reorder holds the first completed
            // physical frame until the other logical lane also completes,
            // then submits the later sequence first.  Payload and sequence
            // metadata remain paired, so SACK fill/drain must recover without
            // altering object bytes.
            pending_count = 0;
            selected_lane = first_set_lane(rx_pending);
            selected_distance = 0;
            for (rx_lane = 0; rx_lane < LANE_COUNT; rx_lane = rx_lane + 1) begin
              if (rx_pending[rx_lane]) begin
                pending_count = pending_count + 1;
                if ((rx_pending_sequence[rx_lane] - rx_base_sequence_o) >=
                    selected_distance) begin
                  selected_lane = rx_lane[LANE_WIDTH-1:0];
                  selected_distance =
                      rx_pending_sequence[rx_lane] - rx_base_sequence_o;
                end
              end
            end
            if ((|rx_pending) && (!reorder_hold_q || pending_count >= 2)) begin
              rxc_lane_q <= selected_lane;
              rxc_read_index_q <= 0;
              rxc_write_index_q <= 0;
              rxc_payload_copied_q <= 0;
              rxc_state_q <= RXC_CLASSIFY;
              if (reorder_hold_q) reorder_hold_q <= 0;
            end
          end
          RXC_CLASSIFY: begin
            rxc_base_q <=
                rx_pending_sequence[rxc_lane_q][ENTRY_WIDTH-1:0] *
                MAX_PAYLOAD_BYTES;
            receive_distance =
                rx_pending_sequence[rxc_lane_q] - rx_base_sequence_o;
            // After a same-edge base retirement, distance zero names the
            // just-retired entry and distance WINDOW_SIZE becomes newly
            // admissible.  All other distances retain their normal meaning.
            receive_in_window =
                (!rxc_base_retiring && receive_distance < WINDOW_SIZE) ||
                (rxc_base_retiring && receive_distance != 0 &&
                 receive_distance <= WINDOW_SIZE);
            if (rx_pending_l1[rxc_lane_q] &&
                rx_pending_session[rxc_lane_q] ==
                (object_dual_direction_q ? object_rx_session_q :
                                           object_session_q) &&
                receive_in_window &&
                rx_pending_length[rxc_lane_q] != 0) begin
              rxc_payload_copied_q <= 1;
              rxc_state_q <= RXC_PRIME;
            end else begin
              rxc_payload_copied_q <= 0;
              rxc_state_q <= RXC_PULSE;
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
            receive_distance =
                rx_pending_sequence[rxc_lane_q] - rx_base_sequence_o;
            receive_in_window =
                (!rxc_base_retiring && receive_distance < WINDOW_SIZE) ||
                (rxc_base_retiring && receive_distance != 0 &&
                 receive_distance <= WINDOW_SIZE);
            dp_rx_frame_valid_q <= 1;
            dp_rx_l1_valid_q <= rx_pending_l1[rxc_lane_q] &&
                (rxc_payload_copied_q ||
                 rx_pending_session[rxc_lane_q] !=
                     (object_dual_direction_q ? object_rx_session_q :
                                                object_session_q) ||
                 !receive_in_window);
            dp_rx_session_q <= rx_pending_session[rxc_lane_q];
            dp_rx_sequence_q <= rx_pending_sequence[rxc_lane_q];
            dp_rx_path_q <= rx_pending_path[rxc_lane_q];
            dp_rx_payload_ref_q <= rx_pending_sequence[rxc_lane_q][ENTRY_WIDTH-1:0];
            dp_rx_payload_length_q <= rx_pending_length[rxc_lane_q];
            dp_rx_turnaround_q <= rx_pending_turnaround[rxc_lane_q];
            rx_pending[rxc_lane_q] <= 0;
            rxc_payload_copied_q <= 0;
            rxc_state_q <= RXC_IDLE;
          end
          default: rxc_state_q <= RXC_IDLE;
        endcase
      end
    end
  end

  // ACK receive events traverse the reverse optical direction before reaching
  // the transmit window.  They are not wired directly from the local SACK.
  integer ack_rx_lane;
  always @(posedge clk or negedge rst_n) begin : ack_receive
    reg ack_event;
    reg piggy_event;
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
      dp_peer_ack_credit_q <= WINDOW_SIZE;
      ack_received_pulse_q <= 0;
      p10_5_piggyback_ack_rx_count_q <= 0;
      p10_5_direction_reject_count_q <= 0;
      p10_5_role_epoch_reject_count_q <= 0;
    end else begin
      dp_peer_ack_valid_q <= 0;
      ack_received_pulse_q <= 0;
      if (clear_counters_i) begin
        p10_5_piggyback_ack_rx_count_q <= 0;
        p10_5_direction_reject_count_q <= 0;
        p10_5_role_epoch_reject_count_q <= 0;
      end
      if (start_object_i)
        dp_peer_ack_credit_q <= WINDOW_SIZE;
      for (ack_rx_lane = 0; ack_rx_lane < LANE_COUNT;
           ack_rx_lane = ack_rx_lane + 1) begin
        // Symmetrically, only the object sender consumes reverse-path ACKs in
        // independent-endpoint mode.  The monolithic P9 role retains its
        // original bidirectional behavior.
        ack_event = rx_frame_valid[ack_rx_lane] && rx_frame_ack[ack_rx_lane] &&
            !tx_context_aborted_q &&
            selected_rx_lane_mask[ack_rx_lane] &&
            rx_frame_lane_id[ack_rx_lane] == ack_rx_lane &&
            (!endpoint_mode ||
             (local_sender && rx_admission_enable[ack_rx_lane] &&
              rx_frame_source_node[ack_rx_lane] != local_node_id)) &&
            (!object_dual_direction_q ||
             (rx_frame_vnext[ack_rx_lane] &&
              rx_frame_role_epoch[ack_rx_lane] == object_role_epoch_q));
        piggy_event = object_dual_direction_q &&
            !tx_context_aborted_q &&
            rx_frame_valid[ack_rx_lane] && !rx_frame_ack[ack_rx_lane] &&
            rx_frame_crc[ack_rx_lane] &&
            selected_rx_lane_mask[ack_rx_lane] &&
            rx_frame_lane_id[ack_rx_lane] == ack_rx_lane &&
            rx_admission_enable[ack_rx_lane] &&
            rx_frame_source_node[ack_rx_lane] != local_node_id &&
            rx_frame_vnext[ack_rx_lane] &&
            rx_frame_role_epoch[ack_rx_lane] == object_role_epoch_q &&
            rx_ack_direction[ack_rx_lane] == local_rx_direction &&
            rx_piggyback_ack_valid[ack_rx_lane] &&
            rx_piggyback_ack_direction[ack_rx_lane] == local_tx_direction;
        ack_crc = rx_frame_crc[ack_rx_lane];
        ack_session_value = rx_frame_session[ack_rx_lane];
        ack_base_value = rx_ack_base[ack_rx_lane];
        ack_bitmap_value = rx_ack_bitmap[ack_rx_lane];
        ack_direction_value = rx_ack_direction[ack_rx_lane];
        if (ack_event && ack_crc &&
            ack_direction_value == local_tx_direction &&
            (!endpoint_mode || ack_session_value == object_session_q)) begin
          dp_peer_ack_valid_q <= 1;
          dp_peer_ack_session_q <= ack_session_value;
          dp_peer_ack_base_q <= ack_base_value;
          dp_peer_ack_bitmap_q <= ack_bitmap_value;
          dp_peer_ack_width_q <= 6'd32;
          dp_peer_ack_credit_q <= rx_ack_credit[ack_rx_lane];
          ack_received_pulse_q <= 1;
        end
        if (piggy_event &&
            rx_piggyback_ack_session[ack_rx_lane] == object_session_q) begin
          dp_peer_ack_valid_q <= 1;
          dp_peer_ack_session_q <=
              rx_piggyback_ack_session[ack_rx_lane];
          dp_peer_ack_base_q <= rx_piggyback_ack_base[ack_rx_lane];
          dp_peer_ack_bitmap_q <= rx_piggyback_ack_bitmap[ack_rx_lane];
          dp_peer_ack_width_q <= 6'd32;
          dp_peer_ack_credit_q <= rx_piggyback_ack_credit[ack_rx_lane];
          ack_received_pulse_q <= 1;
          p10_5_piggyback_ack_rx_count_q <=
              p10_5_piggyback_ack_rx_count_q + 1'b1;
        end
        if (object_dual_direction_q && object_active_q &&
            rx_frame_valid[ack_rx_lane] && rx_frame_crc[ack_rx_lane] &&
            selected_rx_lane_mask[ack_rx_lane] &&
            rx_frame_source_node[ack_rx_lane] != local_node_id) begin
          if (!rx_frame_vnext[ack_rx_lane] ||
              rx_frame_role_epoch[ack_rx_lane] != object_role_epoch_q)
            p10_5_role_epoch_reject_count_q <=
                p10_5_role_epoch_reject_count_q + 1'b1;
          else if (rx_ack_direction[ack_rx_lane] !=
                   (rx_frame_ack[ack_rx_lane] ? local_tx_direction :
                                                     local_rx_direction) ||
                   (!rx_frame_ack[ack_rx_lane] &&
                    rx_piggyback_ack_valid[ack_rx_lane] &&
                    rx_piggyback_ack_direction[ack_rx_lane] !=
                    local_tx_direction))
            p10_5_direction_reject_count_q <=
                p10_5_direction_reject_count_q + 1'b1;
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
      !disarm_request_i && !full_shutdown_request_i &&
      !rx_context_aborted_q;
  assign m_axis_tdata_o = out_pack_data_q;
  assign m_axis_tkeep_o = out_pack_count_q == 4 ? 4'hf :
                          out_pack_count_q == 3 ? 4'h7 :
                          out_pack_count_q == 2 ? 4'h3 : 4'h1;
  assign m_axis_tlast_o = out_pack_last_q;
  assign output_complete_o = output_complete_q;
  assign output_byte_count_o = output_bytes_q;

  wire output_stage_write = out_state_q == OUT_COPY && !start_object_i &&
      !abort_object_i && !disarm_request_i && !full_shutdown_request_i &&
      !rx_context_aborted_q;
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
      end else if (abort_object_i || disarm_request_i ||
                   full_shutdown_request_i || rx_context_aborted_q) begin
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
      object_dual_direction_q <= 0;
      object_tx_lane_mask_q <= {{(LANE_COUNT-1){1'b0}}, 1'b1};
      object_rx_lane_mask_q <= {{(LANE_COUNT-1){1'b0}}, 1'b1};
      object_role_epoch_q <= 0;
      object_rx_session_q <= 1;
      object_rx_path_q <= 0;
      object_rx_id_q <= 0;
      object_rx_initial_sequence_q <= 0;
      object_lane_mask_q <= {{(LANE_COUNT-1){1'b0}}, 1'b1};
      object_lane_weights_q <= {LANE_COUNT{8'h01}};
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
        end else if (arm_request_i && receiver_enable_q && endpoint_phy_ready_all)
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
              (requested_dual_direction &&
               (!endpoint_mode || cfg_role_epoch_i == 0 ||
                cfg_tx_lane_mask_i == 0 || cfg_rx_lane_mask_i == 0 ||
                (|(cfg_tx_lane_mask_i & cfg_rx_lane_mask_i)) ||
                ((cfg_tx_lane_mask_i | cfg_rx_lane_mask_i) !=
                 cfg_lane_mask_i))) ||
              (cfg_auto_migration_request &&
               !cfg_auto_migration_config_valid) ||
              (cfg_lane_mask_i & ~cfg_lane_unavailable_i) == 0 ||
              (cfg_lane_mask_i & ~cfg_lane_unavailable_i &
               mapping_valid_mask & injected_duty_headroom_mask) == 0 ||
              cfg_rate_select_i == 2'd3) begin
            object_active_q <= 0;
            object_fail_q <= 1;
            object_error_q <= 32'h5009_0005;
            object_dual_direction_q <= 0;
          end else begin
            object_active_q <= 1;
            object_fail_q <= 0;
            object_error_q <= 0;
            object_direction_q <= requested_dual_direction ?
                !local_is_a : cfg_direction_i;
            object_dual_direction_q <= requested_dual_direction;
            object_tx_lane_mask_q <= requested_dual_direction ?
                cfg_tx_lane_mask_i : cfg_lane_mask_i;
            object_rx_lane_mask_q <= requested_dual_direction ?
                cfg_rx_lane_mask_i : cfg_lane_mask_i;
            object_role_epoch_q <= requested_dual_direction ?
                cfg_role_epoch_i : 16'd0;
            object_rx_session_q <= requested_dual_direction ?
                cfg_rx_session_epoch_i : cfg_session_epoch_i;
            object_rx_path_q <= requested_dual_direction ?
                cfg_rx_path_epoch_i : cfg_path_epoch_i;
            object_rx_id_q <= requested_dual_direction ?
                cfg_rx_object_id_i : cfg_object_id_i;
            object_rx_initial_sequence_q <= requested_dual_direction ?
                cfg_rx_initial_sequence_i : cfg_initial_sequence_i;
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
        if (object_active_q &&
            ((!endpoint_mode && input_complete_q && output_complete_q &&
              tx_outstanding_count_o == 0 && !allocate_pending_q &&
              !duplicate_ack_validation_pending_q) ||
             (endpoint_mode && !object_dual_direction_q && local_sender &&
              input_complete_q &&
              tx_outstanding_count_o == 0 && !allocate_pending_q &&
              !duplicate_ack_validation_pending_q && lanes_idle &&
              phase_q == PH_DATA) ||
             (endpoint_mode && object_dual_direction_q &&
              (tx_context_aborted_q ||
               (input_complete_q && tx_outstanding_count_o == 0 &&
                !allocate_pending_q &&
                !duplicate_ack_validation_pending_q)) &&
              (rx_context_aborted_q ||
               (output_complete_q && !p10_5_ack_dirty_q &&
                !dp_local_ack_valid &&
                !(|rx_pending) && rxc_state_q == RXC_IDLE)) &&
              lanes_idle && phase_q == PH_DATA) ||
             (endpoint_mode && !object_dual_direction_q && local_receiver &&
              output_complete_q &&
              !dp_local_ack_valid && lanes_idle && phase_q == PH_DATA &&
              !endpoint_turnaround_pending_q &&
              !(|rx_pending) && rxc_state_q == RXC_IDLE))) begin
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
