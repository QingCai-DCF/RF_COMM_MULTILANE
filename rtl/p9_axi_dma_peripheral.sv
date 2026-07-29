`timescale 1ns/1ps
`default_nettype wire
`include "generated/ir_register_map_defs.svh"

// P9 Z7010 peripheral boundary.  The AXI DMA owns DDR movement; this block
// owns only AXI-Stream framing, the optical transport, fail-closed controls,
// and read-only telemetry.  All logic is in the 64 MHz protocol domain.
module p9_axi_dma_peripheral (
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

  output logic [1:0]   ir_mode_out_0,
  input  logic [1:0]   ir_rx_in_0,
  output logic [1:0]   ir_sd_0,
  output logic [1:0]   ir_tx_out_0,
  output logic [1:0]   loop_mode_b0,
  input  logic [1:0]   loop_rx_b0,
  output logic [1:0]   loop_sd_b0,
  output logic [1:0]   loop_tx_b0
);
  localparam logic [31:0] P9_MAGIC = 32'h5039_5A10;
  localparam logic [31:0] P9_BUILD_ID = 32'h5009_000B;
  localparam logic [31:0] P9_PROFILE_ID = 32'h0070_1022;

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
  logic [1:0] cfg_lane_mask_q;
  logic [15:0] cfg_lane_weights_q;
  logic [1:0] cfg_rate_q;
  logic cfg_direction_q;
  logic [31:0] cfg_session_q;
  logic [15:0] cfg_path_q;
  logic [31:0] cfg_object_q;
  logic [15:0] cfg_initial_sequence_q;
  logic [31:0] cfg_fault_flags_q;
  logic [7:0] cfg_drop_data_q;
  logic [7:0] cfg_drop_ack_q;
  logic [1:0] cfg_lane_unavailable_q;
  logic raw_direction_q;
  logic [1:0] raw_lane_mask_q;
  logic [31:0] raw_target_q;
  logic [31:0] raw_spacing_q;
  logic object_done_sticky_q;
  logic object_fail_sticky_q;
  logic object_fail_d_q;
  logic raw_done_sticky_q;

  logic endpoint_armed;
  logic tx_kill_active;
  logic [3:0] phy_ready_mask;
  logic [3:0] startup_done_mask;
  logic [3:0] safety_fault_mask;
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
  logic [63:0] scheduler_frames_flat;
  logic [63:0] scheduler_bytes_flat;
  logic [63:0] scheduler_retries_flat;
  logic [63:0] scheduler_migrations_flat;
  logic [31:0] scheduler_maximum_starvation;
  logic [31:0] physical_data_frames_good;
  logic [31:0] physical_ack_frames_good;
  logic [31:0] physical_crc_bad;
  logic [31:0] physical_frame_bad;
  logic [31:0] physical_preamble_count;
  logic [31:0] physical_symbol_error_count;
  logic [31:0] physical_drop_data_count;
  logic [31:0] physical_drop_ack_count;
  logic [127:0] raw_rx_counts_flat;
  logic [127:0] physical_tx_counts_flat;
  logic [127:0] tx_high_max_flat;
  logic [127:0] duty_high_max_flat;
  logic [127:0] duty_high_current_flat;
  logic [127:0] duty_headroom_flat;
  logic [127:0] duty_target_throttle_count_flat;
  logic [127:0] duty_hard_fault_count_flat;
  logic [31:0] duty_window_cycles;
  logic [31:0] duty_hard_limit_cycles;
  logic [31:0] duty_target_limit_cycles;

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
      cfg_lane_weights_q <= 16'h0101;
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
    end else begin
      arm_pulse_q <= 0;
      disarm_pulse_q <= 0;
      shutdown_pulse_q <= 0;
      clear_pulse_q <= 0;
      start_pulse_q <= 0;
      abort_pulse_q <= 0;
      raw_start_pulse_q <= 0;
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
            cfg_lane_mask_q <= reg_wr_data[1:0];
            cfg_rate_q <= reg_wr_data[9:8];
            cfg_direction_q <= reg_wr_data[16];
          end
          12'h72C: cfg_lane_weights_q <= reg_wr_data[15:0];
          12'h730: cfg_session_q <= reg_wr_data;
          12'h734: cfg_path_q <= reg_wr_data[15:0];
          12'h738: cfg_object_q <= reg_wr_data;
          12'h73C: begin
            cfg_drop_data_q <= reg_wr_data[7:0];
            cfg_drop_ack_q <= reg_wr_data[15:8];
            cfg_lane_unavailable_q <= reg_wr_data[17:16];
          end
          12'h740: begin
            raw_lane_mask_q <= reg_wr_data[1:0];
            raw_direction_q <= reg_wr_data[8];
          end
          12'h744: raw_target_q <= reg_wr_data;
          12'h748: raw_spacing_q <= reg_wr_data;
          12'h860: cfg_initial_sequence_q <= reg_wr_data[15:0];
          12'h864: cfg_fault_flags_q <= reg_wr_data;
          default: ;
        endcase
      end
    end
  end

  always_comb begin
    reg_rd_data = 32'h0000_0000;
    unique case (reg_rd_addr)
      12'h700: reg_rd_data = P9_MAGIC;
      12'h704: reg_rd_data = P9_BUILD_ID;
      12'h708: reg_rd_data = P9_PROFILE_ID;
      12'h70C: reg_rd_data = `IR_REGISTER_MAP_VERSION;
      12'h710: reg_rd_data = `IR_REGISTER_MAP_HASH_LOW;
      12'h714: reg_rd_data = {8'd247, 8'd32, 4'd4, 4'd2, 4'd2, 4'd1};
      12'h718: reg_rd_data = 0;
      12'h71C: reg_rd_data = {22'd0, receiver_enable_q, raw_done_sticky_q,
          raw_busy, output_complete, input_complete, object_fail_sticky_q,
          object_done_sticky_q, object_active, tx_kill_active, endpoint_armed};
      12'h720: reg_rd_data = {16'd0, safety_fault_mask, startup_done_mask, phy_ready_mask};
      12'h724: reg_rd_data = object_error;
      12'h728: reg_rd_data = {15'd0, cfg_direction_q, 6'd0, cfg_rate_q, 6'd0, cfg_lane_mask_q};
      12'h72C: reg_rd_data = {16'd0, cfg_lane_weights_q};
      12'h730: reg_rd_data = cfg_session_q;
      12'h734: reg_rd_data = {16'd0, cfg_path_q};
      12'h738: reg_rd_data = cfg_object_q;
      12'h73C: reg_rd_data = {14'd0, cfg_lane_unavailable_q, cfg_drop_ack_q, cfg_drop_data_q};
      12'h740: reg_rd_data = {23'd0, raw_direction_q, 6'd0, raw_lane_mask_q};
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
      default: reg_rd_data = 0;
    endcase
  end

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .WINDOW_SIZE(32), .SACK_BITS(32),
    .MAX_PAYLOAD_BYTES(247), .STORE_ADDR_WIDTH(13), .RTO_CYCLES(4_000_000)
  ) u_transport (
    .clk(s_axi_aclk), .rst_n(s_axi_aresetn && !stream_reset_request_o),
    .receiver_enable_i(receiver_enable_q), .arm_request_i(arm_pulse_q),
    .disarm_request_i(disarm_pulse_q), .full_shutdown_request_i(shutdown_pulse_q),
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
    .a_rxd_i(ir_rx_in_0), .a_txd_o(ir_tx_out_0), .a_sd_o(ir_sd_0),
    .a_mode_o(ir_mode_out_0), .b_rxd_i(loop_rx_b0), .b_txd_o(loop_tx_b0),
    .b_sd_o(loop_sd_b0), .b_mode_o(loop_mode_b0),
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
    .physical_drop_data_count_o(physical_drop_data_count),
    .physical_drop_ack_count_o(physical_drop_ack_count),
    .raw_rx_counts_flat_o(raw_rx_counts_flat),
    .physical_tx_counts_flat_o(physical_tx_counts_flat),
    .tx_high_max_flat_o(tx_high_max_flat), .duty_high_max_flat_o(duty_high_max_flat),
    .duty_high_current_flat_o(duty_high_current_flat),
    .duty_headroom_flat_o(duty_headroom_flat),
    .duty_target_throttle_count_flat_o(duty_target_throttle_count_flat),
    .duty_hard_fault_count_flat_o(duty_hard_fault_count_flat),
    .duty_window_cycles_o(duty_window_cycles),
    .duty_hard_limit_cycles_o(duty_hard_limit_cycles),
    .duty_target_limit_cycles_o(duty_target_limit_cycles)
  );
endmodule

`default_nettype wire
