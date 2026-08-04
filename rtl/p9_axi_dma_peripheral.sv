`timescale 1ns/1ps
`default_nettype wire
`include "generated/ir_register_map_defs.svh"

// P9 Z7010 peripheral boundary.  The AXI DMA owns DDR movement; this block
// owns only AXI-Stream framing, the optical transport, fail-closed controls,
// and read-only telemetry.  All logic is in the 64 MHz protocol domain.
module p9_axi_dma_peripheral #(
  parameter integer DEPLOYMENT_ROLE = 0,
  parameter integer LANE_COUNT = 2,
  parameter integer WINDOW_SIZE = 32,
  parameter integer SACK_BITS = 32,
  parameter logic [31:0] BUILD_ID = 32'h5009_000B,
  parameter logic [31:0] PROFILE_ID = 32'h0070_1022,
  parameter logic [31:0] IDENTITY_MAGIC = 32'h5039_5A10
) (
  input  logic         s_axi_aclk,
  input  logic         s_axi_aresetn,
  input  logic [11:0]  s_axi_awaddr,
  input  logic [2:0]   s_axi_awprot,
  input  logic         s_axi_awvalid,
  output logic         s_axi_awready,
  input  logic [31:0]  s_axi_wdata,
  input  logic [3:0]   s_axi_wstrb,
  input  logic         s_axi_wvalid,
  output logic         s_axi_wready,
  output logic [1:0]   s_axi_bresp,
  output logic         s_axi_bvalid,
  input  logic         s_axi_bready,
  input  logic [11:0]  s_axi_araddr,
  input  logic [2:0]   s_axi_arprot,
  input  logic         s_axi_arvalid,
  output logic         s_axi_arready,
  output logic [31:0]  s_axi_rdata,
  output logic [1:0]   s_axi_rresp,
  output logic         s_axi_rvalid,
  input  logic         s_axi_rready,

  input  logic         s_axis_tvalid,
  output logic         s_axis_tready,
  input  logic [31:0]  s_axis_tdata,
  input  logic [3:0]   s_axis_tkeep,
  input  logic         s_axis_tlast,
  output logic         m_axis_tvalid,
  input  logic         m_axis_tready,
  output logic [31:0]  m_axis_tdata,
  output logic [3:0]   m_axis_tkeep,
  output logic         m_axis_tlast,
  output logic         stream_reset_request_o,

  output logic [LANE_COUNT-1:0] ir_mode_out_0,
  input  logic [LANE_COUNT-1:0] ir_rx_in_0,
  output logic [LANE_COUNT-1:0] ir_sd_0,
  output logic [LANE_COUNT-1:0] ir_tx_out_0,
  output logic [LANE_COUNT-1:0] loop_mode_b0,
  input  logic [LANE_COUNT-1:0] loop_rx_b0,
  output logic [LANE_COUNT-1:0] loop_sd_b0,
  output logic [LANE_COUNT-1:0] loop_tx_b0,
  output logic [LANE_COUNT-1:0] monitor_valid_rx_frame_o,
  output logic         monitor_effective_full_shutdown_o
);
  localparam logic [31:0] P9_MAGIC = 32'h5039_5A10;
  localparam logic [31:0] P9_BUILD_ID = 32'h5009_000B;
  localparam logic [31:0] P9_PROFILE_ID = 32'h0070_1022;
  localparam integer P10_2_SNAPSHOT_WORDS = 128;
  localparam integer P10_FORENSIC_SNAPSHOT_WORDS = 24 + 10*LANE_COUNT;
  localparam integer P10_FORENSIC_EVENT_DEPTH = 256;
  localparam integer P10_FORENSIC_EVENT_WORDS = 8;
  wire [31:0] effective_magic = DEPLOYMENT_ROLE == 0 ? P9_MAGIC : IDENTITY_MAGIC;
  wire [31:0] effective_build_id = DEPLOYMENT_ROLE == 0 ? P9_BUILD_ID : BUILD_ID;
  wire [31:0] effective_profile_id = DEPLOYMENT_ROLE == 0 ? P9_PROFILE_ID : PROFILE_ID;

  logic reg_wr_en;
  logic [11:0] reg_wr_addr;
  logic [31:0] reg_wr_data;
  logic reg_rd_en;
  logic [11:0] reg_rd_addr;
  logic [31:0] reg_rd_data;
  logic reg_rd_valid;

  logic receiver_enable_q;
  logic arm_pulse_q;
  logic disarm_pulse_q;
  logic shutdown_pulse_q;
  logic clear_pulse_q;
  logic start_pulse_q;
  logic abort_pulse_q;
  logic raw_start_pulse_q;
  logic [5:0] stream_reset_hold_q;
  logic transport_resetn_q;
  logic [LANE_COUNT-1:0] core_a_mode;
  logic [LANE_COUNT-1:0] core_a_sd;
  logic [LANE_COUNT-1:0] core_a_txd;
  logic [LANE_COUNT-1:0] core_b_mode;
  logic [LANE_COUNT-1:0] core_b_sd;
  logic [LANE_COUNT-1:0] core_b_txd;
  logic [LANE_COUNT-1:0] cfg_lane_mask_q;
  logic [LANE_COUNT*8-1:0] cfg_lane_weights_q;
  logic [1:0] cfg_rate_q;
  logic cfg_direction_q;
  logic [31:0] cfg_session_q;
  logic [15:0] cfg_path_q;
  logic [31:0] cfg_object_q;
  logic [15:0] cfg_initial_sequence_q;
  logic [31:0] cfg_fault_flags_q;
  logic [7:0] cfg_drop_data_q;
  logic [7:0] cfg_drop_ack_q;
  logic [LANE_COUNT-1:0] cfg_lane_unavailable_q;
  logic raw_direction_q;
  logic [LANE_COUNT-1:0] raw_lane_mask_q;
  logic [31:0] raw_target_q;
  logic [31:0] raw_spacing_q;
  logic object_done_sticky_q;
  logic object_fail_sticky_q;
  logic object_fail_d_q;
  logic raw_done_sticky_q;

  logic endpoint_armed;
  logic tx_kill_active;
  logic [2*LANE_COUNT-1:0] phy_ready_mask;
  logic [2*LANE_COUNT-1:0] startup_done_mask;
  logic [2*LANE_COUNT-1:0] safety_fault_mask;
  logic object_active;
  logic object_done;
  logic object_fail;
  logic [31:0] object_error;
  logic input_complete;
  logic output_complete;
  logic [31:0] input_byte_count;
  logic [31:0] output_byte_count;
  logic raw_busy;
  logic raw_done;
  logic [31:0] raw_sent_count;
  logic [15:0] tx_next_sequence;
  logic [15:0] tx_ack_base;
  logic [5:0] tx_outstanding_count;
  logic [5:0] tx_outstanding_high_watermark;
  logic [15:0] rx_base_sequence;
  logic [31:0] rx_sack_bitmap;
  logic [31:0] tx_attempt_count;
  logic [31:0] tx_retry_count;
  logic [31:0] tx_retry_exhausted_count;
  logic [31:0] tx_timeout_count;
  logic [31:0] tx_duplicate_ack_count;
  logic [31:0] tx_stale_ack_count;
  logic [31:0] tx_out_of_window_ack_count;
  logic [31:0] tx_migration_count;
  logic [LANE_COUNT-1:0] effective_lane_unavailable;
  logic auto_migration_armed;
  logic auto_migration_triggered;
  logic [LANE_COUNT-1:0] auto_migration_target_mask;
  logic [15:0] auto_migration_trigger_sequence;
  logic [15:0] auto_migration_trigger_ack_base;
  logic [5:0] auto_migration_trigger_outstanding;
  logic [31:0] auto_migration_trigger_attempt_count;
  logic [31:0] auto_migration_trigger_physical_tx_count;
  logic [31:0] auto_migration_trigger_count;
  logic [31:0] auto_migration_trigger_migration_count;
  logic [31:0] auto_migration_trigger_scheduled_count;
  logic [31:0] rx_duplicate_count;
  logic [31:0] rx_out_of_order_count;
  logic [31:0] rx_old_count;
  logic [31:0] rx_future_count;
  logic [31:0] rx_stale_session_count;
  logic [31:0] rx_stale_path_count;
  logic [31:0] rx_gap_count;
  logic [31:0] rx_delivery_count;
  logic [31:0] rx_protocol_error_count;
  logic [31:0] ack_aggregation_count;
  logic [31:0] ack_timer_expiry_count;
  logic [31:0] ack_frames_sent;
  logic [LANE_COUNT*32-1:0] scheduler_frames_flat;
  logic [LANE_COUNT*32-1:0] scheduler_bytes_flat;
  logic [LANE_COUNT*32-1:0] scheduler_retries_flat;
  logic [LANE_COUNT*32-1:0] scheduler_migrations_flat;
  logic [31:0] scheduler_maximum_starvation;
  logic [31:0] physical_data_frames_good;
  logic [31:0] physical_ack_frames_good;
  logic [31:0] physical_crc_bad;
  logic [31:0] physical_frame_bad;
  logic [31:0] physical_preamble_count;
  logic [31:0] physical_symbol_error_count;
  logic [LANE_COUNT*32-1:0] physical_data_good_by_lane;
  logic [LANE_COUNT*32-1:0] physical_ack_good_by_lane;
  logic [LANE_COUNT*32-1:0] physical_crc_bad_by_lane;
  logic [LANE_COUNT*32-1:0] physical_frame_bad_by_lane;
  logic [LANE_COUNT*32-1:0] physical_preamble_by_lane;
  logic [LANE_COUNT*32-1:0] physical_symbol_error_by_lane;
  logic [31:0] physical_drop_data_count;
  logic [31:0] physical_drop_ack_count;
  logic [2*LANE_COUNT*32-1:0] raw_rx_counts_flat;
  logic [2*LANE_COUNT*32-1:0] physical_tx_counts_flat;
  logic [2*LANE_COUNT*32-1:0] tx_high_current_flat;
  logic [2*LANE_COUNT*32-1:0] tx_high_max_flat;
  logic [2*LANE_COUNT*32-1:0] duty_high_max_flat;
  logic [2*LANE_COUNT*32-1:0] duty_high_current_flat;
  logic [2*LANE_COUNT*32-1:0] duty_headroom_flat;
  logic [2*LANE_COUNT*32-1:0] duty_target_throttle_count_flat;
  logic [2*LANE_COUNT*32-1:0] duty_hard_fault_count_flat;
  logic [31:0] duty_window_cycles;
  logic [31:0] duty_hard_limit_cycles;
  logic [31:0] duty_target_limit_cycles;
  logic [31:0] rx_admission_status;
  logic [LANE_COUNT*32-1:0] rx_raw_while_local_tx_flat;
  logic [LANE_COUNT*32-1:0] rx_blanked_raw_pulse_flat;
  logic [LANE_COUNT*32-1:0] rx_blanked_frame_start_flat;
  logic [LANE_COUNT*32-1:0] rx_blanked_crc_valid_flat;
  logic [LANE_COUNT*32-1:0] rx_local_source_reject_flat;
  logic [LANE_COUNT*32-1:0] rx_accepted_remote_flat;
  logic [LANE_COUNT*32-1:0] rx_guard_total_flat;
  logic [LANE_COUNT*32-1:0] rx_guard_max_flat;
  logic [LANE_COUNT*32-1:0] rx_echo_tail_max_flat;
  logic [LANE_COUNT*32-1:0] rx_last_txd_rise_flat;
  logic [LANE_COUNT*32-1:0] rx_last_txd_fall_flat;
  logic [LANE_COUNT*32-1:0] rx_first_rxd_after_tx_flat;
  logic [LANE_COUNT*32-1:0] rx_last_rxd_after_tx_flat;
  logic [31:0] rx_overlap_violation_count;
  logic [31:0] rx_admission_violation_count;
  logic [31:0] rx_non_target_accepted_count;
  logic [31:0] rx_cross_lane_accepted_count;
  logic [LANE_COUNT*32-1:0] rx_decoder_clear_count_flat;
  logic [31:0] p10_1r_snapshot_generation_q;
  logic [31:0] p10_1r_snapshot_q [0:34];
  wire [LANE_COUNT*32-1:0] local_raw_rx_counts = DEPLOYMENT_ROLE == 2 ?
      raw_rx_counts_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      raw_rx_counts_flat[LANE_COUNT*32-1:0];
  logic [31:0] p10_2_snapshot_generation_q;
  logic [31:0] p10_2_snapshot_q [0:P10_2_SNAPSHOT_WORDS-1];
  logic [31:0] p10_1_reg_rd_data;
  logic [63:0] p10_1_timer;
  logic [31:0] p10_1_snapshot_generation;
  logic p10_1_perf_active;
  logic output_complete_d_q;
  logic [31:0] retry_exhausted_d_q;
  logic [2:0] p10_1_axis_bytes;
  integer p10_1r_snapshot_index;
  integer p10_2_snapshot_index;
  integer p10_2_snapshot_lane;
  integer p10_2_snapshot_module;

  logic [$clog2(P10_FORENSIC_SNAPSHOT_WORDS)-1:0]
      forensic_snapshot_index_q;
  logic [$clog2(P10_FORENSIC_EVENT_DEPTH)-1:0]
      forensic_event_index_q;
  logic [$clog2(P10_FORENSIC_EVENT_WORDS)-1:0]
      forensic_event_word_q;
  logic forensic_archive_digest_write_q;
  logic [2:0] forensic_archive_digest_index_q;
  logic [31:0] forensic_archive_digest_data_q;
  logic forensic_archive_commit_q;
  logic forensic_clear_key_write_q;
  logic [31:0] forensic_clear_key_q;
  logic forensic_checkpoint_event_q;
  logic [31:0] forensic_checkpoint_tag_q;
  logic [31:0] forensic_snapshot_data;
  logic [31:0] forensic_event_data;
  logic forensic_fault_hold;
  logic forensic_frozen;
  logic forensic_post_complete;
  logic forensic_snapshot_read_complete;
  logic forensic_event_read_complete;
  logic forensic_archive_committed;
  logic forensic_clear_armed;
  logic [31:0] forensic_fault_sequence;
  logic [63:0] forensic_fault_timestamp;
  logic [31:0] forensic_fault_cause_frozen;
  logic [31:0] forensic_pre_event_count;
  logic [31:0] forensic_post_event_count;
  logic [31:0] forensic_total_event_count;
  logic [31:0] forensic_clear_count;
  logic [31:0] forensic_clear_reject_count;
  logic [255:0] forensic_archive_digest;
  wire [LANE_COUNT-1:0] forensic_local_txd = DEPLOYMENT_ROLE == 2 ?
      core_b_txd : core_a_txd;
  wire [LANE_COUNT-1:0] forensic_local_sd = DEPLOYMENT_ROLE == 2 ?
      core_b_sd : core_a_sd;
  wire [LANE_COUNT-1:0] forensic_local_mode = DEPLOYMENT_ROLE == 2 ?
      core_b_mode : core_a_mode;
  wire [LANE_COUNT-1:0] forensic_local_phy_ready = DEPLOYMENT_ROLE == 2 ?
      phy_ready_mask[2*LANE_COUNT-1 -: LANE_COUNT] :
      phy_ready_mask[LANE_COUNT-1:0];
  wire [LANE_COUNT-1:0] forensic_local_startup = DEPLOYMENT_ROLE == 2 ?
      startup_done_mask[2*LANE_COUNT-1 -: LANE_COUNT] :
      startup_done_mask[LANE_COUNT-1:0];
  wire [LANE_COUNT-1:0] forensic_local_safety_fault = DEPLOYMENT_ROLE == 2 ?
      safety_fault_mask[2*LANE_COUNT-1 -: LANE_COUNT] :
      safety_fault_mask[LANE_COUNT-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_physical_tx = DEPLOYMENT_ROLE == 2 ?
      physical_tx_counts_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      physical_tx_counts_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_tx_high_current = DEPLOYMENT_ROLE == 2 ?
      tx_high_current_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      tx_high_current_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_tx_high_max = DEPLOYMENT_ROLE == 2 ?
      tx_high_max_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      tx_high_max_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_duty_current = DEPLOYMENT_ROLE == 2 ?
      duty_high_current_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      duty_high_current_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_duty_max = DEPLOYMENT_ROLE == 2 ?
      duty_high_max_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      duty_high_max_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_duty_headroom = DEPLOYMENT_ROLE == 2 ?
      duty_headroom_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      duty_headroom_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_target_throttle = DEPLOYMENT_ROLE == 2 ?
      duty_target_throttle_count_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      duty_target_throttle_count_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_hard_fault_count = DEPLOYMENT_ROLE == 2 ?
      duty_hard_fault_count_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      duty_hard_fault_count_flat[LANE_COUNT*32-1:0];
  wire [LANE_COUNT*32-1:0] forensic_local_raw_rx = DEPLOYMENT_ROLE == 2 ?
      raw_rx_counts_flat[2*LANE_COUNT*32-1 -: LANE_COUNT*32] :
      raw_rx_counts_flat[LANE_COUNT*32-1:0];
  wire forensic_capture_fault = (|forensic_local_safety_fault) || object_fail;
  wire [31:0] forensic_fault_cause = {
      object_error[15:0], 6'd0, (tx_retry_exhausted_count != 0),
      (object_error != 0), object_fail, forensic_local_safety_fault};

  initial begin
    if (LANE_COUNT != 2 && LANE_COUNT != 4)
      $error("AXI peripheral supports the frozen 2-lane and P10.2 4-lane profiles");
    if (WINDOW_SIZE != 32 || SACK_BITS != 32)
      $error("P10.2 peripheral freezes WINDOW_SIZE=SACK_BITS=32");
  end

  always_comb begin
    p10_1_axis_bytes = s_axis_tkeep[0] + s_axis_tkeep[1] +
                       s_axis_tkeep[2] + s_axis_tkeep[3];
  end

  p6_axi_lite_bridge u_axi_lite (
    .s_axi_aclk, .s_axi_aresetn, .s_axi_awaddr, .s_axi_awprot, .s_axi_awvalid,
    .s_axi_awready, .s_axi_wdata, .s_axi_wstrb, .s_axi_wvalid, .s_axi_wready,
    .s_axi_bresp, .s_axi_bvalid, .s_axi_bready, .s_axi_araddr, .s_axi_arprot,
    .s_axi_arvalid, .s_axi_arready, .s_axi_rdata, .s_axi_rresp, .s_axi_rvalid,
    .s_axi_rready, .reg_wr_en, .reg_wr_addr, .reg_wr_data, .reg_rd_en,
    .reg_rd_addr, .reg_rd_data, .reg_rd_valid
  );

  assign reg_rd_valid = reg_rd_en;
  // Register commands can gate inferred payload BRAM write/read ports in the
  // transport core.  Reset them synchronously; the core's independent final
  // endpoint/Txd kill remains asynchronously asserted from s_axi_aresetn.
  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      receiver_enable_q <= 0;
      arm_pulse_q <= 0;
      disarm_pulse_q <= 0;
      shutdown_pulse_q <= 0;
      clear_pulse_q <= 0;
      start_pulse_q <= 0;
      abort_pulse_q <= 0;
      raw_start_pulse_q <= 0;
      stream_reset_hold_q <= 0;
      stream_reset_request_o <= 0;
      cfg_lane_mask_q <= 0;
      cfg_lane_weights_q <= {LANE_COUNT{8'h01}};
      cfg_rate_q <= 2'd2;
      cfg_direction_q <= 0;
      cfg_session_q <= 32'h0000_0001;
      cfg_path_q <= 0;
      cfg_object_q <= 0;
      cfg_initial_sequence_q <= 0;
      cfg_fault_flags_q <= 0;
      cfg_drop_data_q <= 0;
      cfg_drop_ack_q <= 0;
      cfg_lane_unavailable_q <= 0;
      raw_direction_q <= 0;
      raw_lane_mask_q <= 0;
      raw_target_q <= 0;
      raw_spacing_q <= 32'd1024;
      object_done_sticky_q <= 0;
      object_fail_sticky_q <= 0;
      object_fail_d_q <= 0;
      raw_done_sticky_q <= 0;
      forensic_snapshot_index_q <= 0;
      forensic_event_index_q <= 0;
      forensic_event_word_q <= 0;
      forensic_archive_digest_write_q <= 0;
      forensic_archive_digest_index_q <= 0;
      forensic_archive_digest_data_q <= 0;
      forensic_archive_commit_q <= 0;
      forensic_clear_key_write_q <= 0;
      forensic_clear_key_q <= 0;
      forensic_checkpoint_event_q <= 0;
      forensic_checkpoint_tag_q <= 0;
      p10_1r_snapshot_generation_q <= 0;
      p10_2_snapshot_generation_q <= 0;
      for (p10_1r_snapshot_index = 0;
           p10_1r_snapshot_index < 35;
           p10_1r_snapshot_index = p10_1r_snapshot_index + 1)
        p10_1r_snapshot_q[p10_1r_snapshot_index] <= 0;
      for (p10_2_snapshot_index = 0;
           p10_2_snapshot_index < P10_2_SNAPSHOT_WORDS;
           p10_2_snapshot_index = p10_2_snapshot_index + 1)
        p10_2_snapshot_q[p10_2_snapshot_index] <= 0;
    end else begin
      arm_pulse_q <= 0;
      disarm_pulse_q <= 0;
      shutdown_pulse_q <= 0;
      clear_pulse_q <= 0;
      start_pulse_q <= 0;
      abort_pulse_q <= 0;
      raw_start_pulse_q <= 0;
      forensic_archive_digest_write_q <= 0;
      forensic_archive_commit_q <= 0;
      forensic_clear_key_write_q <= 0;
      forensic_checkpoint_event_q <= 0;
      if (stream_reset_hold_q != 0) begin
        stream_reset_hold_q <= stream_reset_hold_q - 1'b1;
        if (stream_reset_hold_q == 1) stream_reset_request_o <= 0;
      end
      object_fail_d_q <= object_fail;
      if (object_done) object_done_sticky_q <= 1;
      // object_fail is level-sticky in the core.  Latch only its rising edge;
      // otherwise the previous object's high level is sampled once more on
      // the cycle after START and resurrects a failure that START just cleared.
      if (object_fail && !object_fail_d_q) object_fail_sticky_q <= 1;
      if (raw_done) raw_done_sticky_q <= 1;
      if (safety_fault_mask != 0) receiver_enable_q <= 0;

      if (reg_wr_en) begin
        unique case (reg_wr_addr)
          12'h718: begin
            if (reg_wr_data[0]) receiver_enable_q <= 1;
            if (reg_wr_data[1]) receiver_enable_q <= 0;
            if (reg_wr_data[2]) arm_pulse_q <= 1;
            if (reg_wr_data[3]) disarm_pulse_q <= 1;
            if (reg_wr_data[4]) begin
              receiver_enable_q <= 0;
              // Preserve the last requested lane/rate/direction tuple for
              // post-shutdown evidence readback.  This is configuration only:
              // receiver_enable is cleared here and the independent core
              // shutdown pulse asynchronously owns endpoint arm, final TX
              // kill, Txd-low, and SD-high behavior.
              shutdown_pulse_q <= 1;
            end
            if (reg_wr_data[5]) begin
              clear_pulse_q <= 1;
              object_done_sticky_q <= 0;
              object_fail_sticky_q <= 0;
              raw_done_sticky_q <= 0;
            end
            if (reg_wr_data[6]) begin
              start_pulse_q <= 1;
              object_done_sticky_q <= 0;
              object_fail_sticky_q <= 0;
            end
            if (reg_wr_data[7]) abort_pulse_q <= 1;
            if (reg_wr_data[8]) begin
              raw_start_pulse_q <= 1;
              raw_done_sticky_q <= 0;
            end
            if (reg_wr_data[9]) begin
              receiver_enable_q <= 0;
              cfg_lane_mask_q <= 0;
              // Kill the physical transmitter before the registered local
              // transport reset is asserted on the following clock.  This
              // avoids deriving a high-fanout asynchronous reset through a
              // combinational LUT while preserving fail-closed behavior.
              shutdown_pulse_q <= 1;
              // Hold the request long enough for each proc_sys_reset instance
              // to observe it and synchronously release the 64/100/50 MHz
              // protocol-stream/DMA domains.  The transport core shares this
              // reset interval, so no stale AXI-Stream beat can survive an
              // abort/reset/reboot recovery sequence.
              stream_reset_hold_q <= 6'd32;
              stream_reset_request_o <= 1;
              object_done_sticky_q <= 0;
              object_fail_sticky_q <= 0;
              raw_done_sticky_q <= 0;
            end
          end
          12'h728: begin
            cfg_lane_mask_q <= reg_wr_data[LANE_COUNT-1:0];
            cfg_rate_q <= reg_wr_data[9:8];
            cfg_direction_q <= reg_wr_data[16];
          end
          12'h72C: cfg_lane_weights_q <= reg_wr_data[LANE_COUNT*8-1:0];
          12'h730: cfg_session_q <= reg_wr_data;
          12'h734: cfg_path_q <= reg_wr_data[15:0];
          12'h738: cfg_object_q <= reg_wr_data;
          12'h73C: begin
            cfg_drop_data_q <= reg_wr_data[7:0];
            cfg_drop_ack_q <= reg_wr_data[15:8];
            cfg_lane_unavailable_q <= reg_wr_data[16 +: LANE_COUNT];
          end
          12'h740: begin
            raw_lane_mask_q <= reg_wr_data[LANE_COUNT-1:0];
            raw_direction_q <= reg_wr_data[8];
          end
          12'h744: raw_target_q <= reg_wr_data;
          12'h748: raw_spacing_q <= reg_wr_data;
          12'h860: cfg_initial_sequence_q <= reg_wr_data[15:0];
          12'h864: cfg_fault_flags_q <= reg_wr_data;
          `IR_REG_P10_FF_SNAPSHOT_INDEX:
            forensic_snapshot_index_q <= reg_wr_data;
          `IR_REG_P10_FF_EVENT_INDEX:
            forensic_event_index_q <= reg_wr_data;
          `IR_REG_P10_FF_EVENT_WORD_INDEX:
            forensic_event_word_q <= reg_wr_data;
          `IR_REG_P10_FF_ARCHIVE_DIGEST0,
          `IR_REG_P10_FF_ARCHIVE_DIGEST1,
          `IR_REG_P10_FF_ARCHIVE_DIGEST2,
          `IR_REG_P10_FF_ARCHIVE_DIGEST3,
          `IR_REG_P10_FF_ARCHIVE_DIGEST4,
          `IR_REG_P10_FF_ARCHIVE_DIGEST5,
          `IR_REG_P10_FF_ARCHIVE_DIGEST6,
          `IR_REG_P10_FF_ARCHIVE_DIGEST7: begin
            forensic_archive_digest_write_q <= 1'b1;
            forensic_archive_digest_index_q <=
                (reg_wr_addr - `IR_REG_P10_FF_ARCHIVE_DIGEST0) >> 2;
            forensic_archive_digest_data_q <= reg_wr_data;
          end
          `IR_REG_P10_FF_ARCHIVE_COMMIT:
            if (reg_wr_data == 32'h4152_4348)
              forensic_archive_commit_q <= 1'b1;
          `IR_REG_P10_FF_CLEAR_KEY: begin
            forensic_clear_key_write_q <= 1'b1;
            forensic_clear_key_q <= reg_wr_data;
          end
          `IR_REG_P10_FF_CHECKPOINT: begin
            forensic_checkpoint_event_q <= 1'b1;
            forensic_checkpoint_tag_q <= reg_wr_data;
          end
          // Atomic P10.1R telemetry snapshot.  All values and the even
          // generation advance on the same protocol clock edge.
          12'hA00: if (reg_wr_data[0]) begin
            p10_1r_snapshot_generation_q <=
                p10_1r_snapshot_generation_q + 32'd2;
            p10_1r_snapshot_q[0] <= rx_admission_status;
            p10_1r_snapshot_q[1] <= local_raw_rx_counts[31:0];
            p10_1r_snapshot_q[2] <= local_raw_rx_counts[63:32];
            p10_1r_snapshot_q[3] <= rx_raw_while_local_tx_flat[31:0];
            p10_1r_snapshot_q[4] <= rx_raw_while_local_tx_flat[63:32];
            p10_1r_snapshot_q[5] <= rx_blanked_raw_pulse_flat[31:0];
            p10_1r_snapshot_q[6] <= rx_blanked_raw_pulse_flat[63:32];
            p10_1r_snapshot_q[7] <= rx_blanked_frame_start_flat[31:0];
            p10_1r_snapshot_q[8] <= rx_blanked_frame_start_flat[63:32];
            p10_1r_snapshot_q[9] <= rx_blanked_crc_valid_flat[31:0];
            p10_1r_snapshot_q[10] <= rx_blanked_crc_valid_flat[63:32];
            p10_1r_snapshot_q[11] <= rx_local_source_reject_flat[31:0];
            p10_1r_snapshot_q[12] <= rx_local_source_reject_flat[63:32];
            p10_1r_snapshot_q[13] <= rx_accepted_remote_flat[31:0];
            p10_1r_snapshot_q[14] <= rx_accepted_remote_flat[63:32];
            p10_1r_snapshot_q[15] <= rx_guard_total_flat[31:0];
            p10_1r_snapshot_q[16] <= rx_guard_total_flat[63:32];
            p10_1r_snapshot_q[17] <= rx_guard_max_flat[31:0];
            p10_1r_snapshot_q[18] <= rx_guard_max_flat[63:32];
            p10_1r_snapshot_q[19] <= rx_echo_tail_max_flat[31:0];
            p10_1r_snapshot_q[20] <= rx_echo_tail_max_flat[63:32];
            p10_1r_snapshot_q[21] <= rx_decoder_clear_count_flat[31:0];
            p10_1r_snapshot_q[22] <= rx_decoder_clear_count_flat[63:32];
            p10_1r_snapshot_q[23] <= rx_last_txd_rise_flat[31:0];
            p10_1r_snapshot_q[24] <= rx_last_txd_rise_flat[63:32];
            p10_1r_snapshot_q[25] <= rx_last_txd_fall_flat[31:0];
            p10_1r_snapshot_q[26] <= rx_last_txd_fall_flat[63:32];
            p10_1r_snapshot_q[27] <= rx_first_rxd_after_tx_flat[31:0];
            p10_1r_snapshot_q[28] <= rx_first_rxd_after_tx_flat[63:32];
            p10_1r_snapshot_q[29] <= rx_last_rxd_after_tx_flat[31:0];
            p10_1r_snapshot_q[30] <= rx_last_rxd_after_tx_flat[63:32];
            p10_1r_snapshot_q[31] <= rx_overlap_violation_count;
            p10_1r_snapshot_q[32] <= rx_admission_violation_count;
            p10_1r_snapshot_q[33] <= rx_non_target_accepted_count;
            p10_1r_snapshot_q[34] <= rx_cross_lane_accepted_count;
          end
          // P10.2 appends a versioned, atomic four-lane snapshot without
          // changing any frozen P9/P10.1R address or snapshot word.
          12'hB00: if (reg_wr_data[0]) begin
            p10_2_snapshot_generation_q <=
                p10_2_snapshot_generation_q + 32'd2;
            for (p10_2_snapshot_index = 0;
                 p10_2_snapshot_index < P10_2_SNAPSHOT_WORDS;
                 p10_2_snapshot_index = p10_2_snapshot_index + 1)
              p10_2_snapshot_q[p10_2_snapshot_index] <= 0;
            p10_2_snapshot_q[0] <= {8'd247, 8'(WINDOW_SIZE), 8'(LANE_COUNT),
                                     8'(2*LANE_COUNT)};
            p10_2_snapshot_q[1] <= {{(32-3*LANE_COUNT){1'b0}},
                safety_fault_mask[LANE_COUNT-1:0],
                startup_done_mask[LANE_COUNT-1:0],
                phy_ready_mask[LANE_COUNT-1:0]};
            p10_2_snapshot_q[2] <= {{(32-2*LANE_COUNT){1'b0}},
                                     effective_lane_unavailable,
                                     cfg_lane_mask_q};
            p10_2_snapshot_q[3] <= rx_admission_status;
            p10_2_snapshot_q[4] <= tx_attempt_count;
            p10_2_snapshot_q[5] <= tx_retry_count;
            p10_2_snapshot_q[6] <= tx_migration_count;
            p10_2_snapshot_q[7] <= {physical_ack_frames_good[15:0],
                                     physical_data_frames_good[15:0]};
            for (p10_2_snapshot_lane = 0;
                 p10_2_snapshot_lane < LANE_COUNT;
                 p10_2_snapshot_lane = p10_2_snapshot_lane + 1) begin
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+0] <=
                  scheduler_frames_flat[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+1] <=
                  scheduler_bytes_flat[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+2] <=
                  scheduler_retries_flat[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+3] <=
                  scheduler_migrations_flat[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+4] <=
                  physical_data_good_by_lane[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+5] <=
                  physical_ack_good_by_lane[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+6] <=
                  physical_crc_bad_by_lane[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+7] <=
                  physical_frame_bad_by_lane[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+8] <=
                  rx_raw_while_local_tx_flat[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+9] <=
                  rx_blanked_raw_pulse_flat[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+10] <=
                  rx_local_source_reject_flat[32*p10_2_snapshot_lane +: 32];
              p10_2_snapshot_q[8+12*p10_2_snapshot_lane+11] <=
                  rx_accepted_remote_flat[32*p10_2_snapshot_lane +: 32];
            end
            for (p10_2_snapshot_module = 0;
                 p10_2_snapshot_module < 2*LANE_COUNT;
                 p10_2_snapshot_module = p10_2_snapshot_module + 1) begin
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+0] <=
                  raw_rx_counts_flat[32*p10_2_snapshot_module +: 32];
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+1] <=
                  physical_tx_counts_flat[32*p10_2_snapshot_module +: 32];
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+2] <=
                  tx_high_max_flat[32*p10_2_snapshot_module +: 32];
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+3] <=
                  duty_high_max_flat[32*p10_2_snapshot_module +: 32];
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+4] <=
                  duty_high_current_flat[32*p10_2_snapshot_module +: 32];
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+5] <=
                  duty_headroom_flat[32*p10_2_snapshot_module +: 32];
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+6] <=
                  duty_target_throttle_count_flat[32*p10_2_snapshot_module +: 32];
              p10_2_snapshot_q[56+8*p10_2_snapshot_module+7] <=
                  duty_hard_fault_count_flat[32*p10_2_snapshot_module +: 32];
            end
            p10_2_snapshot_q[120] <= rx_overlap_violation_count;
            p10_2_snapshot_q[121] <= rx_admission_violation_count;
            p10_2_snapshot_q[122] <= rx_non_target_accepted_count;
            p10_2_snapshot_q[123] <= rx_cross_lane_accepted_count;
            p10_2_snapshot_q[124] <= duty_window_cycles;
            p10_2_snapshot_q[125] <= duty_hard_limit_cycles;
            p10_2_snapshot_q[126] <= duty_target_limit_cycles;
            p10_2_snapshot_q[127] <= 32'h5031_0201;
          end
          default: ;
        endcase
      end
    end
  end

  // Keep the transport/BRAM reset source free of an asynchronous set/reset so
  // RAMB control timing remains analyzable (REQP-1839=0). The physical output
  // boundary below independently gates reset to Txd-low/SD-high/Mode-high.
  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn)
      transport_resetn_q <= 1'b0;
    else
      transport_resetn_q <= !stream_reset_request_o;
  end

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      output_complete_d_q <= 1'b0;
      retry_exhausted_d_q <= '0;
    end else begin
      output_complete_d_q <= output_complete;
      retry_exhausted_d_q <= tx_retry_exhausted_count;
    end
  end

  p10_1_perf_monitor #(
    .PHYSICAL_MODULE_COUNT(2*LANE_COUNT)
  ) u_p10_1_perf_monitor (
    .clk(s_axi_aclk),
    .rst_n(s_axi_aresetn),
    .object_reset_i(stream_reset_request_o),
    .reg_wr_en_i(reg_wr_en),
    .reg_wr_addr_i(reg_wr_addr),
    .reg_wr_data_i(reg_wr_data),
    .reg_rd_en_i(reg_rd_en),
    .reg_rd_addr_i(reg_rd_addr),
    .reg_rd_data_o(p10_1_reg_rd_data),
    .axis_accept_i(s_axis_tvalid && s_axis_tready),
    .axis_accept_bytes_i(p10_1_axis_bytes),
    .axis_stall_i(s_axis_tvalid && !s_axis_tready),
    .descriptor_submit_i(s_axis_tvalid && s_axis_tready && s_axis_tlast),
    .descriptor_complete_i(m_axis_tvalid && m_axis_tready && m_axis_tlast),
    .application_commit_i(output_complete && !output_complete_d_q),
    .application_commit_bytes_i(output_byte_count),
    .physical_tx_symbols_flat_i(physical_tx_counts_flat),
    .queue_occupancy_i(tx_outstanding_count),
    .ack_wait_i(object_active && tx_outstanding_count != 0),
    .direction_quiet_i(!object_active),
    .retry_i(tx_retry_exhausted_count != retry_exhausted_d_q),
    .integrity_error_i(object_fail && !object_fail_d_q),
    .perf_active_o(p10_1_perf_active),
    .timer_o(p10_1_timer),
    .snapshot_generation_o(p10_1_snapshot_generation)
  );

  assign ir_mode_out_0 = s_axi_aresetn ? core_a_mode : {LANE_COUNT{1'b1}};
  assign ir_sd_0       = s_axi_aresetn ? core_a_sd   : {LANE_COUNT{1'b1}};
  assign ir_tx_out_0   = s_axi_aresetn ? core_a_txd  : {LANE_COUNT{1'b0}};
  assign loop_mode_b0  = s_axi_aresetn ? core_b_mode : {LANE_COUNT{1'b1}};
  assign loop_sd_b0    = s_axi_aresetn ? core_b_sd   : {LANE_COUNT{1'b1}};
  assign loop_tx_b0    = s_axi_aresetn ? core_b_txd  : {LANE_COUNT{1'b0}};

  always_comb begin
    reg_rd_data = 32'h0000_0000;
    unique case (reg_rd_addr)
      12'h700: reg_rd_data = effective_magic;
      12'h704: reg_rd_data = effective_build_id;
      12'h708: reg_rd_data = effective_profile_id;
      12'h70C: reg_rd_data = `IR_REGISTER_MAP_VERSION;
      12'h710: reg_rd_data = `IR_REGISTER_MAP_HASH_LOW;
      // Keep the frozen 2-lane capability word bit-for-bit compatible
      // (0xf7204221).  The two lane-count nibbles describe the physical and
      // logical lanes visible to this endpoint; the project-wide eight-module
      // count is reported by the versioned P10.2 snapshot schema instead.
      12'h714: reg_rd_data = {8'd247, 8'(WINDOW_SIZE), 4'd4,
                               4'(LANE_COUNT), 4'(LANE_COUNT), 4'd1};
      12'h718: reg_rd_data = 0;
      12'h71C: reg_rd_data = {22'd0, receiver_enable_q, raw_done_sticky_q,
          raw_busy, output_complete, input_complete, object_fail_sticky_q,
          object_done_sticky_q, object_active, tx_kill_active, endpoint_armed};
      12'h720: reg_rd_data = {{(32-6*LANE_COUNT){1'b0}},
          safety_fault_mask, startup_done_mask, phy_ready_mask};
      12'h724: reg_rd_data = object_error;
      12'h728: begin
        reg_rd_data = 0;
        reg_rd_data[LANE_COUNT-1:0] = cfg_lane_mask_q;
        reg_rd_data[9:8] = cfg_rate_q;
        reg_rd_data[16] = cfg_direction_q;
      end
      12'h72C: reg_rd_data = cfg_lane_weights_q;
      12'h730: reg_rd_data = cfg_session_q;
      12'h734: reg_rd_data = {16'd0, cfg_path_q};
      12'h738: reg_rd_data = cfg_object_q;
      12'h73C: begin
        reg_rd_data = {16'd0, cfg_drop_ack_q, cfg_drop_data_q};
        reg_rd_data[16 +: LANE_COUNT] = effective_lane_unavailable;
      end
      12'h740: begin
        reg_rd_data = 0;
        reg_rd_data[LANE_COUNT-1:0] = raw_lane_mask_q;
        reg_rd_data[8] = raw_direction_q;
      end
      12'h744: reg_rd_data = raw_target_q;
      12'h748: reg_rd_data = raw_spacing_q;
      12'h74C: reg_rd_data = raw_sent_count;
      12'h750: reg_rd_data = input_byte_count;
      12'h754: reg_rd_data = output_byte_count;
      12'h758: reg_rd_data = {tx_ack_base, tx_next_sequence};
      12'h75C: reg_rd_data = {4'd0, tx_outstanding_high_watermark,
                                  tx_outstanding_count, rx_base_sequence};
      12'h760: reg_rd_data = rx_sack_bitmap;
      12'h764: reg_rd_data = tx_attempt_count;
      12'h768: reg_rd_data = tx_retry_count;
      12'h76C: reg_rd_data = tx_retry_exhausted_count;
      12'h770: reg_rd_data = tx_timeout_count;
      12'h774: reg_rd_data = tx_migration_count;
      12'h778: reg_rd_data = rx_duplicate_count;
      12'h77C: reg_rd_data = ack_aggregation_count;
      12'h780: reg_rd_data = ack_timer_expiry_count;
      12'h784: reg_rd_data = ack_frames_sent;
      12'h788: reg_rd_data = tx_duplicate_ack_count;
      12'h78C: reg_rd_data = tx_stale_ack_count;
      12'h790: reg_rd_data = tx_out_of_window_ack_count;
      12'h794: reg_rd_data = rx_stale_session_count;
      12'h798: reg_rd_data = rx_stale_path_count;
      12'h79C: reg_rd_data = physical_data_frames_good;
      12'h7A0: reg_rd_data = physical_ack_frames_good;
      12'h7A4: reg_rd_data = physical_crc_bad;
      12'h7A8: reg_rd_data = physical_drop_data_count;
      12'h7AC: reg_rd_data = physical_drop_ack_count;
      12'h7B0: reg_rd_data = scheduler_frames_flat[31:0];
      12'h7B4: reg_rd_data = scheduler_frames_flat[63:32];
      12'h7B8: reg_rd_data = scheduler_bytes_flat[31:0];
      12'h7BC: reg_rd_data = scheduler_bytes_flat[63:32];
      12'h7C0: reg_rd_data = scheduler_retries_flat[31:0];
      12'h7C4: reg_rd_data = scheduler_retries_flat[63:32];
      12'h7C8: reg_rd_data = scheduler_migrations_flat[31:0];
      12'h7CC: reg_rd_data = scheduler_migrations_flat[63:32];
      12'h7D0: reg_rd_data = scheduler_maximum_starvation;
      12'h7D4: reg_rd_data = raw_rx_counts_flat[31:0];
      12'h7D8: reg_rd_data = raw_rx_counts_flat[63:32];
      12'h7DC: reg_rd_data = raw_rx_counts_flat[95:64];
      12'h7E0: reg_rd_data = raw_rx_counts_flat[127:96];
      12'h7E4: reg_rd_data = physical_tx_counts_flat[31:0];
      12'h7E8: reg_rd_data = physical_tx_counts_flat[63:32];
      12'h7EC: reg_rd_data = physical_tx_counts_flat[95:64];
      12'h7F0: reg_rd_data = physical_tx_counts_flat[127:96];
      12'h7F4: reg_rd_data = tx_high_max_flat[31:0];
      12'h7F8: reg_rd_data = tx_high_max_flat[63:32];
      12'h7FC: reg_rd_data = tx_high_max_flat[95:64];
      12'h800: reg_rd_data = tx_high_max_flat[127:96];
      12'h804: reg_rd_data = duty_high_max_flat[31:0];
      12'h808: reg_rd_data = duty_high_max_flat[63:32];
      12'h80C: reg_rd_data = duty_high_max_flat[95:64];
      12'h810: reg_rd_data = duty_high_max_flat[127:96];
      12'h814: reg_rd_data = duty_high_current_flat[31:0];
      12'h818: reg_rd_data = duty_high_current_flat[63:32];
      12'h81C: reg_rd_data = duty_high_current_flat[95:64];
      12'h820: reg_rd_data = duty_high_current_flat[127:96];
      12'h824: reg_rd_data = duty_headroom_flat[31:0];
      12'h828: reg_rd_data = duty_headroom_flat[63:32];
      12'h82C: reg_rd_data = duty_headroom_flat[95:64];
      12'h830: reg_rd_data = duty_headroom_flat[127:96];
      12'h834: reg_rd_data = duty_target_throttle_count_flat[31:0];
      12'h838: reg_rd_data = duty_target_throttle_count_flat[63:32];
      12'h83C: reg_rd_data = duty_target_throttle_count_flat[95:64];
      12'h840: reg_rd_data = duty_target_throttle_count_flat[127:96];
      12'h844: reg_rd_data = duty_hard_fault_count_flat[31:0];
      12'h848: reg_rd_data = duty_hard_fault_count_flat[63:32];
      12'h84C: reg_rd_data = duty_hard_fault_count_flat[95:64];
      12'h850: reg_rd_data = duty_hard_fault_count_flat[127:96];
      12'h854: reg_rd_data = duty_window_cycles;
      12'h858: reg_rd_data = duty_hard_limit_cycles;
      12'h85C: reg_rd_data = duty_target_limit_cycles;
      12'h860: reg_rd_data = {16'd0, cfg_initial_sequence_q};
      12'h864: reg_rd_data = cfg_fault_flags_q;
      12'h868: reg_rd_data = rx_out_of_order_count;
      12'h86C: reg_rd_data = rx_old_count;
      12'h870: reg_rd_data = rx_future_count;
      12'h874: reg_rd_data = rx_gap_count;
      12'h878: reg_rd_data = rx_delivery_count;
      12'h87C: reg_rd_data = rx_protocol_error_count;
      12'h880: reg_rd_data = physical_frame_bad;
      12'h884: reg_rd_data = physical_preamble_count;
      12'h888: reg_rd_data = physical_symbol_error_count;
      12'h88C: reg_rd_data = physical_data_good_by_lane[31:0];
      12'h890: reg_rd_data = physical_data_good_by_lane[63:32];
      12'h894: reg_rd_data = physical_ack_good_by_lane[31:0];
      12'h898: reg_rd_data = physical_ack_good_by_lane[63:32];
      12'h89C: reg_rd_data = physical_crc_bad_by_lane[31:0];
      12'h8A0: reg_rd_data = physical_crc_bad_by_lane[63:32];
      12'h8A4: reg_rd_data = physical_frame_bad_by_lane[31:0];
      12'h8A8: reg_rd_data = physical_frame_bad_by_lane[63:32];
      12'h8AC: reg_rd_data = physical_preamble_by_lane[31:0];
      12'h8B0: reg_rd_data = physical_preamble_by_lane[63:32];
      12'h8B4: reg_rd_data = physical_symbol_error_by_lane[31:0];
      12'h8B8: reg_rd_data = physical_symbol_error_by_lane[63:32];
      12'h8BC: begin
        reg_rd_data = 0;
        reg_rd_data[0] = auto_migration_armed;
        reg_rd_data[1] = auto_migration_triggered;
        reg_rd_data[2] = |auto_migration_target_mask;
        reg_rd_data[4 +: LANE_COUNT] = auto_migration_target_mask;
        reg_rd_data[8 +: LANE_COUNT] = effective_lane_unavailable;
      end
      12'h8C0: reg_rd_data = {auto_migration_trigger_ack_base,
                              auto_migration_trigger_sequence};
      12'h8C4: begin
        reg_rd_data = 0;
        reg_rd_data[5:0] = auto_migration_trigger_outstanding;
      end
      12'h8C8: reg_rd_data = auto_migration_trigger_attempt_count;
      12'h8CC: reg_rd_data = auto_migration_trigger_physical_tx_count;
      12'h8D0: reg_rd_data = auto_migration_trigger_count;
      12'h8D4: begin
        reg_rd_data = 0;
        reg_rd_data[LANE_COUNT-1:0] = effective_lane_unavailable;
      end
      12'h8D8: reg_rd_data = auto_migration_trigger_migration_count;
      12'h8DC: reg_rd_data = auto_migration_trigger_scheduled_count;
      12'hA00: reg_rd_data = 0;
      12'hA04: reg_rd_data = p10_1r_snapshot_generation_q;
      12'hA08: reg_rd_data = 32'h5231_0101;
      12'hA0C: reg_rd_data = p10_1r_snapshot_q[0];
      12'hA10: reg_rd_data = p10_1r_snapshot_q[1];
      12'hA14: reg_rd_data = p10_1r_snapshot_q[2];
      12'hA18: reg_rd_data = p10_1r_snapshot_q[3];
      12'hA1C: reg_rd_data = p10_1r_snapshot_q[4];
      12'hA20: reg_rd_data = p10_1r_snapshot_q[5];
      12'hA24: reg_rd_data = p10_1r_snapshot_q[6];
      12'hA28: reg_rd_data = p10_1r_snapshot_q[7];
      12'hA2C: reg_rd_data = p10_1r_snapshot_q[8];
      12'hA30: reg_rd_data = p10_1r_snapshot_q[9];
      12'hA34: reg_rd_data = p10_1r_snapshot_q[10];
      12'hA38: reg_rd_data = p10_1r_snapshot_q[11];
      12'hA3C: reg_rd_data = p10_1r_snapshot_q[12];
      12'hA40: reg_rd_data = p10_1r_snapshot_q[13];
      12'hA44: reg_rd_data = p10_1r_snapshot_q[14];
      12'hA48: reg_rd_data = p10_1r_snapshot_q[15];
      12'hA4C: reg_rd_data = p10_1r_snapshot_q[16];
      12'hA50: reg_rd_data = p10_1r_snapshot_q[17];
      12'hA54: reg_rd_data = p10_1r_snapshot_q[18];
      12'hA58: reg_rd_data = p10_1r_snapshot_q[19];
      12'hA5C: reg_rd_data = p10_1r_snapshot_q[20];
      12'hA60: reg_rd_data = p10_1r_snapshot_q[21];
      12'hA64: reg_rd_data = p10_1r_snapshot_q[22];
      12'hA68: reg_rd_data = p10_1r_snapshot_q[23];
      12'hA6C: reg_rd_data = p10_1r_snapshot_q[24];
      12'hA70: reg_rd_data = p10_1r_snapshot_q[25];
      12'hA74: reg_rd_data = p10_1r_snapshot_q[26];
      12'hA78: reg_rd_data = p10_1r_snapshot_q[27];
      12'hA7C: reg_rd_data = p10_1r_snapshot_q[28];
      12'hA80: reg_rd_data = p10_1r_snapshot_q[29];
      12'hA84: reg_rd_data = p10_1r_snapshot_q[30];
      12'hA88: reg_rd_data = p10_1r_snapshot_q[31];
      12'hA8C: reg_rd_data = p10_1r_snapshot_q[32];
      12'hA90: reg_rd_data = p10_1r_snapshot_q[33];
      12'hA94: reg_rd_data = p10_1r_snapshot_q[34];
      12'hA98: reg_rd_data = DEPLOYMENT_ROLE == 0 ? 32'd36864 : 32'd4096;
      12'hA9C: reg_rd_data = 32'd256;
      12'hAA0: reg_rd_data = 32'd131072;
      12'hAA4: reg_rd_data = LANE_COUNT;
      12'hAA8: reg_rd_data = (1 << LANE_COUNT) - 1;
      12'hB00: reg_rd_data = 0;
      12'hB04: reg_rd_data = p10_2_snapshot_generation_q;
      12'hB08: reg_rd_data = 32'h5031_0201;
      `IR_REG_P10_FF_CAPABILITIES:
        reg_rd_data = {8'h46, 4'(LANE_COUNT), 4'(LANE_COUNT),
                       8'(P10_FORENSIC_EVENT_WORDS),
                       8'(P10_FORENSIC_SNAPSHOT_WORDS)};
      `IR_REG_P10_FF_STATUS: reg_rd_data = {
          22'd0, forensic_capture_fault, tx_kill_active,
          monitor_effective_full_shutdown_o, forensic_fault_hold,
          forensic_clear_armed, forensic_archive_committed,
          forensic_event_read_complete, forensic_snapshot_read_complete,
          forensic_post_complete, forensic_frozen};
      `IR_REG_P10_FF_FAULT_SEQUENCE: reg_rd_data = forensic_fault_sequence;
      `IR_REG_P10_FF_FAULT_TIMESTAMP_LOW:
        reg_rd_data = forensic_fault_timestamp[31:0];
      `IR_REG_P10_FF_FAULT_TIMESTAMP_HIGH:
        reg_rd_data = forensic_fault_timestamp[63:32];
      `IR_REG_P10_FF_FAULT_CAUSE: reg_rd_data = forensic_fault_cause_frozen;
      `IR_REG_P10_FF_SNAPSHOT_WORDS:
        reg_rd_data = P10_FORENSIC_SNAPSHOT_WORDS;
      `IR_REG_P10_FF_PRE_EVENT_COUNT: reg_rd_data = forensic_pre_event_count;
      `IR_REG_P10_FF_POST_EVENT_COUNT: reg_rd_data = forensic_post_event_count;
      `IR_REG_P10_FF_TOTAL_EVENT_COUNT: reg_rd_data = forensic_total_event_count;
      `IR_REG_P10_FF_EVENT_DEPTH: reg_rd_data = P10_FORENSIC_EVENT_DEPTH;
      `IR_REG_P10_FF_SNAPSHOT_INDEX: reg_rd_data = forensic_snapshot_index_q;
      `IR_REG_P10_FF_SNAPSHOT_DATA: reg_rd_data = forensic_snapshot_data;
      `IR_REG_P10_FF_EVENT_INDEX: reg_rd_data = forensic_event_index_q;
      `IR_REG_P10_FF_EVENT_WORD_INDEX: reg_rd_data = forensic_event_word_q;
      `IR_REG_P10_FF_EVENT_DATA: reg_rd_data = forensic_event_data;
      `IR_REG_P10_FF_ARCHIVE_DIGEST0:
        reg_rd_data = forensic_archive_digest[31:0];
      `IR_REG_P10_FF_ARCHIVE_DIGEST1:
        reg_rd_data = forensic_archive_digest[63:32];
      `IR_REG_P10_FF_ARCHIVE_DIGEST2:
        reg_rd_data = forensic_archive_digest[95:64];
      `IR_REG_P10_FF_ARCHIVE_DIGEST3:
        reg_rd_data = forensic_archive_digest[127:96];
      `IR_REG_P10_FF_ARCHIVE_DIGEST4:
        reg_rd_data = forensic_archive_digest[159:128];
      `IR_REG_P10_FF_ARCHIVE_DIGEST5:
        reg_rd_data = forensic_archive_digest[191:160];
      `IR_REG_P10_FF_ARCHIVE_DIGEST6:
        reg_rd_data = forensic_archive_digest[223:192];
      `IR_REG_P10_FF_ARCHIVE_DIGEST7:
        reg_rd_data = forensic_archive_digest[255:224];
      `IR_REG_P10_FF_ARCHIVE_COMMIT: reg_rd_data = 0;
      `IR_REG_P10_FF_CLEAR_KEY: reg_rd_data = 0;
      `IR_REG_P10_FF_CLEAR_AUDIT:
        reg_rd_data = {forensic_clear_reject_count[15:0],
                       forensic_clear_count[15:0]};
      `IR_REG_P10_FF_CHECKPOINT: reg_rd_data = forensic_checkpoint_tag_q;
      `IR_REG_P10_FF_READ_PROGRESS: reg_rd_data = {
          16'd0, forensic_total_event_count[7:0], 2'd0,
          forensic_archive_committed, forensic_event_read_complete,
          forensic_snapshot_read_complete, forensic_post_complete,
          forensic_frozen, forensic_fault_hold};
      default: begin
        if (reg_rd_addr >= 12'h900 && reg_rd_addr <= 12'h9BC)
          reg_rd_data = p10_1_reg_rd_data;
        else if (reg_rd_addr >= 12'hB0C && reg_rd_addr <= 12'hD08)
          reg_rd_data = p10_2_snapshot_q[(reg_rd_addr-12'hB0C) >> 2];
        else
          reg_rd_data = 0;
      end
    endcase
  end

  p10_fault_forensics #(
    .CLK_HZ(64_000_000),
    .LANE_COUNT(LANE_COUNT),
    .MODULE_COUNT(LANE_COUNT),
    .SNAPSHOT_WORDS(P10_FORENSIC_SNAPSHOT_WORDS),
    .EVENT_DEPTH(P10_FORENSIC_EVENT_DEPTH),
    .POST_EVENT_COUNT(8),
    .EVENT_WORDS(P10_FORENSIC_EVENT_WORDS),
    .SAMPLE_INTERVAL_CYCLES(1024)
  ) u_fault_forensics (
    .clk(s_axi_aclk),
    .system_reset_n_i(s_axi_aresetn),
    .capture_fault_i(forensic_capture_fault),
    .fault_cause_i(forensic_fault_cause),
    .effective_shutdown_i(monitor_effective_full_shutdown_o),
    .endpoint_armed_i(endpoint_armed),
    .tx_kill_i(tx_kill_active),
    .receiver_enable_i(receiver_enable_q),
    .physical_txd_i(forensic_local_txd),
    .physical_sd_i(forensic_local_sd),
    .physical_mode_i(forensic_local_mode),
    .phy_ready_i(forensic_local_phy_ready),
    .startup_done_i(forensic_local_startup),
    .safety_fault_i(forensic_local_safety_fault),
    .configured_lane_mask_i(cfg_lane_mask_q),
    .unavailable_lane_mask_i(cfg_lane_unavailable_q),
    .raw_lane_mask_i(raw_lane_mask_q),
    .raw_busy_i(raw_busy),
    .raw_direction_i(raw_direction_q),
    .object_active_i(object_active),
    .object_done_i(object_done),
    .object_fail_i(object_fail),
    .object_id_i(cfg_object_q),
    .object_error_i(object_error),
    .tx_next_sequence_i(tx_next_sequence),
    .tx_ack_base_i(tx_ack_base),
    .tx_outstanding_i(tx_outstanding_count),
    .tx_outstanding_high_watermark_i(tx_outstanding_high_watermark),
    .rx_base_sequence_i(rx_base_sequence),
    .rx_sack_bitmap_i(rx_sack_bitmap),
    .tx_attempt_count_i(tx_attempt_count),
    .tx_retry_count_i(tx_retry_count),
    .tx_retry_exhausted_count_i(tx_retry_exhausted_count),
    .tx_timeout_count_i(tx_timeout_count),
    .tx_migration_count_i(tx_migration_count),
    .input_byte_count_i(input_byte_count),
    .output_byte_count_i(output_byte_count),
    .physical_tx_counts_flat_i(forensic_local_physical_tx),
    .tx_high_current_flat_i(forensic_local_tx_high_current),
    .tx_high_max_flat_i(forensic_local_tx_high_max),
    .duty_high_current_flat_i(forensic_local_duty_current),
    .duty_high_max_flat_i(forensic_local_duty_max),
    .duty_headroom_flat_i(forensic_local_duty_headroom),
    .duty_target_throttle_count_flat_i(forensic_local_target_throttle),
    .duty_hard_fault_count_flat_i(forensic_local_hard_fault_count),
    .raw_rx_counts_flat_i(forensic_local_raw_rx),
    .snapshot_read_index_i(forensic_snapshot_index_q),
    .snapshot_read_strobe_i(reg_rd_en &&
        reg_rd_addr == `IR_REG_P10_FF_SNAPSHOT_DATA),
    .snapshot_read_data_o(forensic_snapshot_data),
    .event_read_index_i(forensic_event_index_q),
    .event_read_word_i(forensic_event_word_q),
    .event_read_strobe_i(reg_rd_en &&
        reg_rd_addr == `IR_REG_P10_FF_EVENT_DATA),
    .event_read_data_o(forensic_event_data),
    .archive_digest_write_i(forensic_archive_digest_write_q),
    .archive_digest_index_i(forensic_archive_digest_index_q),
    .archive_digest_data_i(forensic_archive_digest_data_q),
    .archive_commit_i(forensic_archive_commit_q),
    .clear_key_write_i(forensic_clear_key_write_q),
    .clear_key_i(forensic_clear_key_q),
    .checkpoint_event_i(forensic_checkpoint_event_q),
    .checkpoint_tag_i(forensic_checkpoint_tag_q),
    .first_fault_hold_o(forensic_fault_hold),
    .frozen_o(forensic_frozen),
    .post_trace_complete_o(forensic_post_complete),
    .snapshot_read_complete_o(forensic_snapshot_read_complete),
    .event_read_complete_o(forensic_event_read_complete),
    .archive_committed_o(forensic_archive_committed),
    .clear_armed_o(forensic_clear_armed),
    .fault_sequence_o(forensic_fault_sequence),
    .fault_timestamp_o(forensic_fault_timestamp),
    .frozen_fault_cause_o(forensic_fault_cause_frozen),
    .pre_event_count_o(forensic_pre_event_count),
    .post_event_count_o(forensic_post_event_count),
    .total_event_count_o(forensic_total_event_count),
    .clear_count_o(forensic_clear_count),
    .clear_reject_count_o(forensic_clear_reject_count),
    .archive_digest_o(forensic_archive_digest)
  );

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(LANE_COUNT),
    .WINDOW_SIZE(WINDOW_SIZE), .SACK_BITS(SACK_BITS),
    .MAX_PAYLOAD_BYTES(247), .STORE_ADDR_WIDTH(13), .RTO_CYCLES(4_000_000),
    // Preserve the historical P9 monolithic defaults while P10.1R role-bound
    // endpoints use the directly measured guard selection.
    .ACK_TURNAROUND_GUARD_CYCLES(DEPLOYMENT_ROLE == 0 ? 37_120 : 4_352),
    .RX_MIN_POST_TX_GUARD_CYCLES(DEPLOYMENT_ROLE == 0 ? 36_864 : 4_096),
    .DEPLOYMENT_ROLE(DEPLOYMENT_ROLE)
  ) u_transport (
    .clk(s_axi_aclk), .rst_n(transport_resetn_q),
    .receiver_enable_i(receiver_enable_q), .arm_request_i(arm_pulse_q),
    .disarm_request_i(disarm_pulse_q), .full_shutdown_request_i(shutdown_pulse_q),
    .forensic_fault_hold_i(forensic_fault_hold),
    .clear_counters_i(clear_pulse_q), .start_object_i(start_pulse_q),
    .abort_object_i(abort_pulse_q), .cfg_lane_mask_i(cfg_lane_mask_q),
    .cfg_lane_weights_i(cfg_lane_weights_q), .cfg_rate_select_i(cfg_rate_q),
    .cfg_direction_i(cfg_direction_q), .cfg_session_epoch_i(cfg_session_q),
    .cfg_path_epoch_i(cfg_path_q), .cfg_object_id_i(cfg_object_q),
    .cfg_initial_sequence_i(cfg_initial_sequence_q),
    .cfg_fault_flags_i(cfg_fault_flags_q),
    .cfg_drop_data_count_i(cfg_drop_data_q), .cfg_drop_ack_count_i(cfg_drop_ack_q),
    .cfg_lane_unavailable_i(cfg_lane_unavailable_q),
    .raw_start_i(raw_start_pulse_q), .raw_direction_i(raw_direction_q),
    .raw_lane_mask_i(raw_lane_mask_q), .raw_pulse_target_i(raw_target_q),
    .raw_spacing_cycles_i(raw_spacing_q),
    .s_axis_tvalid_i(s_axis_tvalid), .s_axis_tready_o(s_axis_tready),
    .s_axis_tdata_i(s_axis_tdata), .s_axis_tkeep_i(s_axis_tkeep),
    .s_axis_tlast_i(s_axis_tlast), .m_axis_tvalid_o(m_axis_tvalid),
    .m_axis_tready_i(m_axis_tready), .m_axis_tdata_o(m_axis_tdata),
    .m_axis_tkeep_o(m_axis_tkeep), .m_axis_tlast_o(m_axis_tlast),
    .a_rxd_i(ir_rx_in_0), .a_txd_o(core_a_txd), .a_sd_o(core_a_sd),
    .a_mode_o(core_a_mode), .b_rxd_i(loop_rx_b0), .b_txd_o(core_b_txd),
    .b_sd_o(core_b_sd), .b_mode_o(core_b_mode),
    .endpoint_armed_o(endpoint_armed), .tx_kill_active_o(tx_kill_active),
    .phy_ready_mask_o(phy_ready_mask), .startup_done_mask_o(startup_done_mask),
    .safety_fault_mask_o(safety_fault_mask), .object_active_o(object_active),
    .object_done_o(object_done), .object_fail_o(object_fail),
    .object_error_o(object_error), .input_complete_o(input_complete),
    .output_complete_o(output_complete), .input_byte_count_o(input_byte_count),
    .output_byte_count_o(output_byte_count), .raw_busy_o(raw_busy),
    .raw_done_o(raw_done), .raw_sent_count_o(raw_sent_count),
    .tx_next_sequence_o(tx_next_sequence), .tx_ack_base_o(tx_ack_base),
    .tx_outstanding_count_o(tx_outstanding_count),
    .tx_outstanding_high_watermark_o(tx_outstanding_high_watermark),
    .rx_base_sequence_o(rx_base_sequence), .rx_sack_bitmap_o(rx_sack_bitmap),
    .tx_attempt_count_o(tx_attempt_count), .tx_retry_count_o(tx_retry_count),
    .tx_retry_exhausted_count_o(tx_retry_exhausted_count),
    .tx_timeout_count_o(tx_timeout_count),
    .tx_duplicate_ack_count_o(tx_duplicate_ack_count),
    .tx_stale_ack_count_o(tx_stale_ack_count),
    .tx_out_of_window_ack_count_o(tx_out_of_window_ack_count),
    .tx_migration_count_o(tx_migration_count), .rx_duplicate_count_o(rx_duplicate_count),
    .rx_out_of_order_count_o(rx_out_of_order_count),
    .rx_old_count_o(rx_old_count), .rx_future_count_o(rx_future_count),
    .rx_stale_session_count_o(rx_stale_session_count),
    .rx_stale_path_count_o(rx_stale_path_count),
    .rx_gap_count_o(rx_gap_count), .rx_delivery_count_o(rx_delivery_count),
    .rx_protocol_error_count_o(rx_protocol_error_count),
    .ack_aggregation_count_o(ack_aggregation_count),
    .ack_timer_expiry_count_o(ack_timer_expiry_count),
    .ack_frames_sent_o(ack_frames_sent), .scheduler_frames_flat_o(scheduler_frames_flat),
    .scheduler_bytes_flat_o(scheduler_bytes_flat),
    .scheduler_retries_flat_o(scheduler_retries_flat),
    .scheduler_migrations_flat_o(scheduler_migrations_flat),
    .scheduler_maximum_starvation_o(scheduler_maximum_starvation),
    .physical_data_frames_good_o(physical_data_frames_good),
    .physical_ack_frames_good_o(physical_ack_frames_good),
    .physical_crc_bad_o(physical_crc_bad),
    .physical_frame_bad_o(physical_frame_bad),
    .physical_preamble_count_o(physical_preamble_count),
    .physical_symbol_error_count_o(physical_symbol_error_count),
    .physical_data_good_by_lane_o(physical_data_good_by_lane),
    .physical_ack_good_by_lane_o(physical_ack_good_by_lane),
    .physical_crc_bad_by_lane_o(physical_crc_bad_by_lane),
    .physical_frame_bad_by_lane_o(physical_frame_bad_by_lane),
    .physical_preamble_by_lane_o(physical_preamble_by_lane),
    .physical_symbol_error_by_lane_o(physical_symbol_error_by_lane),
    .valid_rx_frame_activity_o(monitor_valid_rx_frame_o),
    .effective_full_shutdown_o(monitor_effective_full_shutdown_o),
    .physical_drop_data_count_o(physical_drop_data_count),
    .physical_drop_ack_count_o(physical_drop_ack_count),
    .raw_rx_counts_flat_o(raw_rx_counts_flat),
    .physical_tx_counts_flat_o(physical_tx_counts_flat),
    .tx_high_current_flat_o(tx_high_current_flat),
    .tx_high_max_flat_o(tx_high_max_flat), .duty_high_max_flat_o(duty_high_max_flat),
    .duty_high_current_flat_o(duty_high_current_flat),
    .duty_headroom_flat_o(duty_headroom_flat),
    .duty_target_throttle_count_flat_o(duty_target_throttle_count_flat),
    .duty_hard_fault_count_flat_o(duty_hard_fault_count_flat),
    .duty_window_cycles_o(duty_window_cycles),
    .duty_hard_limit_cycles_o(duty_hard_limit_cycles),
    .duty_target_limit_cycles_o(duty_target_limit_cycles),
    .effective_lane_unavailable_o(effective_lane_unavailable),
    .auto_migration_armed_o(auto_migration_armed),
    .auto_migration_triggered_o(auto_migration_triggered),
    .auto_migration_target_mask_o(auto_migration_target_mask),
    .auto_migration_trigger_sequence_o(auto_migration_trigger_sequence),
    .auto_migration_trigger_ack_base_o(auto_migration_trigger_ack_base),
    .auto_migration_trigger_outstanding_o(
        auto_migration_trigger_outstanding),
    .auto_migration_trigger_attempt_count_o(
        auto_migration_trigger_attempt_count),
    .auto_migration_trigger_physical_tx_count_o(
        auto_migration_trigger_physical_tx_count),
    .auto_migration_trigger_count_o(auto_migration_trigger_count),
    .auto_migration_trigger_migration_count_o(
        auto_migration_trigger_migration_count),
    .auto_migration_trigger_scheduled_count_o(
        auto_migration_trigger_scheduled_count),
    .rx_admission_status_o(rx_admission_status),
    .rx_raw_while_local_tx_flat_o(rx_raw_while_local_tx_flat),
    .rx_blanked_raw_pulse_flat_o(rx_blanked_raw_pulse_flat),
    .rx_blanked_frame_start_flat_o(rx_blanked_frame_start_flat),
    .rx_blanked_crc_valid_flat_o(rx_blanked_crc_valid_flat),
    .rx_local_source_reject_flat_o(rx_local_source_reject_flat),
    .rx_accepted_remote_flat_o(rx_accepted_remote_flat),
    .rx_guard_total_flat_o(rx_guard_total_flat),
    .rx_guard_max_flat_o(rx_guard_max_flat),
    .rx_echo_tail_max_flat_o(rx_echo_tail_max_flat),
    .rx_last_txd_rise_flat_o(rx_last_txd_rise_flat),
    .rx_last_txd_fall_flat_o(rx_last_txd_fall_flat),
    .rx_first_rxd_after_tx_flat_o(rx_first_rxd_after_tx_flat),
    .rx_last_rxd_after_tx_flat_o(rx_last_rxd_after_tx_flat),
    .rx_overlap_violation_count_o(rx_overlap_violation_count),
    .rx_admission_violation_count_o(rx_admission_violation_count),
    .rx_non_target_accepted_count_o(rx_non_target_accepted_count),
    .rx_cross_lane_accepted_count_o(rx_cross_lane_accepted_count),
    .rx_decoder_clear_count_flat_o(rx_decoder_clear_count_flat)
  );
endmodule

`default_nettype wire
