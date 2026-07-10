`timescale 1ns/1ps

module p6_axi_peripheral (
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

  output logic [1:0] ir_mode_out_0,
  input  logic [1:0] ir_rx_in_0,
  output logic [1:0] ir_sd_0,
  output logic [1:0] ir_tx_out_0,
  output logic [1:0] loop_mode_b0,
  input  logic [1:0] loop_rx_b0,
  output logic [1:0] loop_sd_b0,
  output logic [1:0] loop_tx_b0
);
  logic reg_wr_en;
  logic [11:0] reg_wr_addr;
  logic [31:0] reg_wr_data;
  logic reg_rd_en;
  logic [11:0] reg_rd_addr;
  logic [31:0] reg_rd_data;
  logic reg_rd_valid;

  logic engine_reset_pulse;
  logic engine_clear_pulse;
  logic engine_start_pulse;
  logic engine_stop_pulse;
  logic engine_shutdown_pulse;
  logic engine_enable_phy;
  logic [15:0] cfg_session;
  logic [7:0] cfg_lane_mask;
  logic [7:0] cfg_ack_lane_mask;
  logic [15:0] cfg_payload_len;
  logic [7:0] cfg_pattern_id;
  logic [31:0] cfg_seed;
  logic [31:0] cfg_timeout_cycles;
  logic [7:0] engine_tx_payload_read_index;
  logic [7:0] engine_tx_payload_read_data;
  logic [7:0] engine_compare_payload_read_index;
  logic [7:0] engine_compare_payload_read_data;
  logic [31:0] committed_payload_crc32;

  (* mark_debug = "true" *) logic engine_ready;
  (* mark_debug = "true" *) logic engine_busy;
  (* mark_debug = "true" *) logic engine_done_pulse;
  (* mark_debug = "true" *) logic engine_fail_pulse;
  (* mark_debug = "true" *) logic engine_timeout_pulse;
  (* mark_debug = "true" *) logic [31:0] engine_error_code;
  logic engine_rx_byte_write_pulse;
  logic [7:0] engine_rx_byte_write_index;
  logic [7:0] engine_rx_byte_write_data;
  logic [15:0] engine_rx_payload_len;
  logic [31:0] engine_rx_payload_crc32;
  logic [31:0] engine_rx_digest;
  (* mark_debug = "true" *) logic [1:0] engine_rx_good_mask;
  (* mark_debug = "true" *) logic [31:0] engine_crc_bad_count;
  (* mark_debug = "true" *) logic [31:0] engine_payload_mismatch_count;
  logic [31:0] engine_retry_count;
  (* mark_debug = "true" *) logic [31:0] engine_retry_exhausted_count;
  (* mark_debug = "true" *) logic [31:0] engine_tx_fail_count;
  (* mark_debug = "true" *) logic [31:0] engine_txd_high_max;
  (* mark_debug = "true" *) logic [31:0] engine_duty_violation_count;
  (* mark_debug = "true" *) logic [31:0] engine_shutdown_reason;
  logic [31:0] engine_tx_pulse_count;
  logic [31:0] engine_rx_raw_count;
  logic [31:0] engine_frame_good_count;
  logic [31:0] engine_frame_bad_count;
  logic [31:0] engine_ack_sent_count;
  logic [31:0] engine_ack_seen_count;
  (* mark_debug = "true" *) logic [31:0] engine_debug_status;
  (* mark_debug = "true" *) logic [31:0] regs_debug_status;
  logic [31:0] commit_count;

  p6_axi_lite_bridge u_axi_bridge (
    .s_axi_aclk, .s_axi_aresetn, .s_axi_awaddr, .s_axi_awprot, .s_axi_awvalid,
    .s_axi_awready, .s_axi_wdata, .s_axi_wstrb, .s_axi_wvalid, .s_axi_wready,
    .s_axi_bresp, .s_axi_bvalid, .s_axi_bready, .s_axi_araddr, .s_axi_arprot,
    .s_axi_arvalid, .s_axi_arready, .s_axi_rdata, .s_axi_rresp, .s_axi_rvalid,
    .s_axi_rready, .reg_wr_en, .reg_wr_addr, .reg_wr_data, .reg_rd_en,
    .reg_rd_addr, .reg_rd_data, .reg_rd_valid
  );

  p6_local_transport_regs u_regs (
    .clk(s_axi_aclk), .rst_n(s_axi_aresetn),
    .wr_en(reg_wr_en), .wr_addr(reg_wr_addr), .wr_data(reg_wr_data),
    .rd_en(reg_rd_en), .rd_addr(reg_rd_addr), .rd_data(reg_rd_data), .rd_valid(reg_rd_valid),
    .engine_reset_pulse, .engine_clear_pulse, .engine_start_pulse,
    .engine_stop_pulse, .engine_shutdown_pulse, .engine_enable_phy,
    .cfg_session, .cfg_lane_mask, .cfg_ack_lane_mask, .cfg_payload_len,
    .cfg_pattern_id, .cfg_seed, .cfg_timeout_cycles,
    .engine_tx_payload_read_index, .engine_tx_payload_read_data,
    .engine_compare_payload_read_index, .engine_compare_payload_read_data,
    .committed_payload_crc32,
    .engine_ready, .engine_busy, .engine_done_pulse, .engine_fail_pulse,
    .engine_timeout_pulse, .engine_error_code, .engine_rx_byte_write_pulse,
    .engine_rx_byte_write_index, .engine_rx_byte_write_data,
    .engine_rx_payload_len, .engine_rx_payload_crc32, .engine_rx_digest,
    .engine_rx_good_mask, .engine_crc_bad_count, .engine_payload_mismatch_count,
    .engine_retry_count, .engine_retry_exhausted_count, .engine_tx_fail_count,
    .engine_txd_high_max, .engine_duty_violation_count, .engine_shutdown_reason,
    .engine_tx_pulse_count, .engine_rx_raw_count, .engine_frame_good_count,
    .engine_frame_bad_count, .engine_ack_sent_count, .engine_ack_seen_count,
    .commit_count, .debug_status(regs_debug_status)
  );

  p6_dynamic_transport_engine u_engine (
    .clk(s_axi_aclk), .rst_n(s_axi_aresetn), .reset_pulse(engine_reset_pulse),
    .clear_pulse(engine_clear_pulse), .start_pulse(engine_start_pulse),
    .stop_pulse(engine_stop_pulse), .shutdown_pulse(engine_shutdown_pulse),
    .enable_phy(engine_enable_phy), .cfg_session, .cfg_lane_mask,
    .cfg_ack_lane_mask, .cfg_payload_len, .cfg_timeout_cycles,
    .tx_payload_read_index(engine_tx_payload_read_index),
    .tx_payload_read_data(engine_tx_payload_read_data),
    .compare_payload_read_index(engine_compare_payload_read_index),
    .compare_payload_read_data(engine_compare_payload_read_data),
    .tx_payload_crc32(committed_payload_crc32),
    .a_rxd(ir_rx_in_0), .a_txd(ir_tx_out_0), .a_sd(ir_sd_0), .a_mode(ir_mode_out_0),
    .b_rxd(loop_rx_b0), .b_txd(loop_tx_b0), .b_sd(loop_sd_b0), .b_mode(loop_mode_b0),
    .ready(engine_ready), .busy(engine_busy), .done_pulse(engine_done_pulse),
    .fail_pulse(engine_fail_pulse), .timeout_pulse(engine_timeout_pulse),
    .error_code(engine_error_code), .rx_byte_write_pulse(engine_rx_byte_write_pulse),
    .rx_byte_write_index(engine_rx_byte_write_index), .rx_byte_write_data(engine_rx_byte_write_data),
    .rx_payload_len(engine_rx_payload_len), .rx_payload_crc32(engine_rx_payload_crc32),
    .rx_digest(engine_rx_digest), .rx_good_mask(engine_rx_good_mask),
    .crc_bad_count(engine_crc_bad_count),
    .payload_mismatch_count(engine_payload_mismatch_count),
    .retry_count(engine_retry_count), .retry_exhausted_count(engine_retry_exhausted_count),
    .tx_fail_count(engine_tx_fail_count), .txd_high_max(engine_txd_high_max),
    .duty_violation_count(engine_duty_violation_count),
    .shutdown_reason(engine_shutdown_reason), .tx_pulse_count(engine_tx_pulse_count),
    .rx_raw_count(engine_rx_raw_count), .frame_good_count(engine_frame_good_count),
    .frame_bad_count(engine_frame_bad_count), .ack_sent_count(engine_ack_sent_count),
    .ack_seen_count(engine_ack_seen_count), .debug_status(engine_debug_status)
  );

  logic unused_cfg;
  assign unused_cfg = ^{cfg_pattern_id, cfg_seed, commit_count};
endmodule
