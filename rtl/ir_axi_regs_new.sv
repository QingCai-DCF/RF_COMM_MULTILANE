`timescale 1ns/1ps
module ir_axi_regs_new #(
  parameter logic [31:0] PROFILE_ID_VALUE = 32'h4731_2201
) (
  input  logic        clk,
  input  logic        rst_n,

  input  logic        wr_en,
  input  logic [11:0] wr_addr,
  input  logic [31:0] wr_data,
  input  logic        rd_en,
  input  logic [11:0] rd_addr,
  output logic [31:0] rd_data,
  output logic        rd_valid,

  output logic        core_reset_pulse,
  output logic        enable_phy,
  output logic        start_pulse,
  output logic        stop_pulse,
  output logic        clear_sticky_pulse,
  output logic        commit_pulse,
  output logic        profile_committed,

  output logic [7:0]  cfg_payload_lane_mask,
  output logic [7:0]  cfg_rx_lane_mask,
  output logic [7:0]  cfg_ack_lane_mask,
  output logic [15:0] cfg_session,
  output logic [15:0] cfg_payload_len,
  output logic [15:0] cfg_fragment_bytes,
  output logic [15:0] cfg_cnt_chip_max,
  output logic [15:0] cfg_cnt_preamble,
  output logic [7:0]  cfg_detect_start,
  output logic [7:0]  cfg_detect_end,
  output logic [31:0] cfg_guard_cycles,
  output logic [31:0] cfg_retry_timeout,
  output logic [15:0] cfg_startup_us,
  output logic [31:0] cfg_duty_window,
  output logic [15:0] cfg_duty_max_permille,
  output logic [15:0] cfg_stuck_high_limit_us,

  input  logic        status_phy_ready,
  input  logic        status_busy,
  input  logic        status_tx_done,
  input  logic        status_rx_done,
  input  logic        status_tx_fail,
  input  logic [7:0]  status_retry_count,
  input  logic [7:0]  status_crc_bad_count,
  input  logic [7:0]  status_session_bad_count,
  input  logic [7:0]  status_mask_bad_count,
  input  logic [31:0] safety_shutdown_reason,
  input  logic [31:0] counter_tx_pulse,
  input  logic [31:0] counter_rx_raw_pulse,
  input  logic [31:0] counter_frame_good,
  input  logic [31:0] counter_frame_bad,
  input  logic [31:0] counter_ack_sent,
  input  logic [31:0] counter_ack_seen,

  output logic [31:0] commit_count,
  output logic [31:0] debug_status
);
  localparam logic [11:0] REG_CONTROL                = 12'h000;
  localparam logic [11:0] REG_PROFILE_LANE_MASK      = 12'h004;
  localparam logic [11:0] REG_PROFILE_RX_LANE_MASK   = 12'h008;
  localparam logic [11:0] REG_PROFILE_ACK_LANE_MASK  = 12'h00C;
  localparam logic [11:0] REG_PROFILE_SESSION        = 12'h010;
  localparam logic [11:0] REG_PROFILE_PAYLOAD_LEN    = 12'h014;
  localparam logic [11:0] REG_PROFILE_FRAGMENT_BYTES = 12'h018;
  localparam logic [11:0] REG_TIMING_CNT_CHIP_MAX    = 12'h020;
  localparam logic [11:0] REG_TIMING_CNT_PREAMBLE    = 12'h024;
  localparam logic [11:0] REG_TIMING_DETECT_WINDOW   = 12'h028;
  localparam logic [11:0] REG_TIMING_GUARD_CYCLES    = 12'h02C;
  localparam logic [11:0] REG_TIMING_RETRY_TIMEOUT   = 12'h030;
  localparam logic [11:0] REG_SAFETY_STARTUP_US      = 12'h040;
  localparam logic [11:0] REG_SAFETY_DUTY_WINDOW     = 12'h044;
  localparam logic [11:0] REG_SAFETY_DUTY_MAX        = 12'h048;
  localparam logic [11:0] REG_SAFETY_STUCK_HIGH_LIMIT = 12'h04C;
  localparam logic [11:0] REG_SAFETY_SHUTDOWN_REASON = 12'h050;
  localparam logic [11:0] REG_STATUS                 = 12'h060;
  localparam logic [11:0] REG_STATUS_RETRY_COUNT     = 12'h064;
  localparam logic [11:0] REG_STATUS_ERROR_COUNTS    = 12'h068;
  localparam logic [11:0] REG_COUNTER_TX_PULSE       = 12'h080;
  localparam logic [11:0] REG_COUNTER_RX_RAW_PULSE   = 12'h084;
  localparam logic [11:0] REG_COUNTER_FRAME_GOOD     = 12'h088;
  localparam logic [11:0] REG_COUNTER_FRAME_BAD      = 12'h08C;
  localparam logic [11:0] REG_COUNTER_ACK_SENT       = 12'h090;
  localparam logic [11:0] REG_COUNTER_ACK_SEEN       = 12'h094;
  localparam logic [11:0] REG_PROFILE_ID             = 12'h0F0;

  logic [31:0] shutdown_reason_shadow;

  assign debug_status = {
    profile_committed,
    enable_phy,
    status_phy_ready,
    status_busy,
    status_tx_done,
    status_rx_done,
    status_tx_fail,
    1'b0,
    status_retry_count,
    cfg_payload_lane_mask,
    cfg_ack_lane_mask
  };

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      core_reset_pulse <= 1'b0;
      enable_phy <= 1'b0;
      start_pulse <= 1'b0;
      stop_pulse <= 1'b0;
      clear_sticky_pulse <= 1'b0;
      commit_pulse <= 1'b0;
      profile_committed <= 1'b0;
      cfg_payload_lane_mask <= 8'h01;
      cfg_rx_lane_mask <= 8'h01;
      cfg_ack_lane_mask <= 8'h01;
      cfg_session <= 16'h2201;
      cfg_payload_len <= 16'd256;
      cfg_fragment_bytes <= 16'd255;
      cfg_cnt_chip_max <= 16'd7;
      cfg_cnt_preamble <= 16'd16;
      cfg_detect_start <= 8'd0;
      cfg_detect_end <= 8'd7;
      cfg_guard_cycles <= 32'd4096;
      cfg_retry_timeout <= 32'd1024;
      cfg_startup_us <= 16'd500;
      cfg_duty_window <= 32'd1000;
      cfg_duty_max_permille <= 16'd200;
      cfg_stuck_high_limit_us <= 16'd20;
      shutdown_reason_shadow <= 32'd0;
      commit_count <= 32'd0;
    end else begin
      core_reset_pulse <= 1'b0;
      start_pulse <= 1'b0;
      stop_pulse <= 1'b0;
      clear_sticky_pulse <= 1'b0;
      commit_pulse <= 1'b0;

      if (wr_en) begin
        unique case (wr_addr)
          REG_CONTROL: begin
            core_reset_pulse <= wr_data[0];
            enable_phy <= wr_data[1];
            start_pulse <= wr_data[2];
            stop_pulse <= wr_data[3];
            clear_sticky_pulse <= wr_data[4];
            commit_pulse <= wr_data[5];
            if (wr_data[5]) begin
              profile_committed <= 1'b1;
              commit_count <= commit_count + 1'b1;
            end
          end
          REG_PROFILE_LANE_MASK: cfg_payload_lane_mask <= wr_data[7:0];
          REG_PROFILE_RX_LANE_MASK: cfg_rx_lane_mask <= wr_data[7:0];
          REG_PROFILE_ACK_LANE_MASK: cfg_ack_lane_mask <= wr_data[7:0];
          REG_PROFILE_SESSION: cfg_session <= wr_data[15:0];
          REG_PROFILE_PAYLOAD_LEN: cfg_payload_len <= wr_data[15:0];
          REG_PROFILE_FRAGMENT_BYTES: cfg_fragment_bytes <= wr_data[15:0];
          REG_TIMING_CNT_CHIP_MAX: cfg_cnt_chip_max <= wr_data[15:0];
          REG_TIMING_CNT_PREAMBLE: cfg_cnt_preamble <= wr_data[15:0];
          REG_TIMING_DETECT_WINDOW: begin
            cfg_detect_start <= wr_data[7:0];
            cfg_detect_end <= wr_data[15:8];
          end
          REG_TIMING_GUARD_CYCLES: cfg_guard_cycles <= wr_data;
          REG_TIMING_RETRY_TIMEOUT: cfg_retry_timeout <= wr_data;
          REG_SAFETY_STARTUP_US: cfg_startup_us <= wr_data[15:0];
          REG_SAFETY_DUTY_WINDOW: cfg_duty_window <= wr_data;
          REG_SAFETY_DUTY_MAX: cfg_duty_max_permille <= wr_data[15:0];
          REG_SAFETY_STUCK_HIGH_LIMIT: cfg_stuck_high_limit_us <= wr_data[15:0];
          REG_SAFETY_SHUTDOWN_REASON: shutdown_reason_shadow <= wr_data;
          default: begin
          end
        endcase
      end
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rd_data <= 32'd0;
      rd_valid <= 1'b0;
    end else begin
      rd_valid <= rd_en;
      if (rd_en) begin
        unique case (rd_addr)
          REG_CONTROL: rd_data <= {26'd0, profile_committed, commit_pulse, clear_sticky_pulse, stop_pulse, start_pulse, enable_phy};
          REG_PROFILE_LANE_MASK: rd_data <= {24'd0, cfg_payload_lane_mask};
          REG_PROFILE_RX_LANE_MASK: rd_data <= {24'd0, cfg_rx_lane_mask};
          REG_PROFILE_ACK_LANE_MASK: rd_data <= {24'd0, cfg_ack_lane_mask};
          REG_PROFILE_SESSION: rd_data <= {16'd0, cfg_session};
          REG_PROFILE_PAYLOAD_LEN: rd_data <= {16'd0, cfg_payload_len};
          REG_PROFILE_FRAGMENT_BYTES: rd_data <= {16'd0, cfg_fragment_bytes};
          REG_TIMING_CNT_CHIP_MAX: rd_data <= {16'd0, cfg_cnt_chip_max};
          REG_TIMING_CNT_PREAMBLE: rd_data <= {16'd0, cfg_cnt_preamble};
          REG_TIMING_DETECT_WINDOW: rd_data <= {16'd0, cfg_detect_end, cfg_detect_start};
          REG_TIMING_GUARD_CYCLES: rd_data <= cfg_guard_cycles;
          REG_TIMING_RETRY_TIMEOUT: rd_data <= cfg_retry_timeout;
          REG_SAFETY_STARTUP_US: rd_data <= {16'd0, cfg_startup_us};
          REG_SAFETY_DUTY_WINDOW: rd_data <= cfg_duty_window;
          REG_SAFETY_DUTY_MAX: rd_data <= {16'd0, cfg_duty_max_permille};
          REG_SAFETY_STUCK_HIGH_LIMIT: rd_data <= {16'd0, cfg_stuck_high_limit_us};
          REG_SAFETY_SHUTDOWN_REASON: rd_data <= (safety_shutdown_reason != 32'd0) ? safety_shutdown_reason : shutdown_reason_shadow;
          REG_STATUS: rd_data <= {26'd0, profile_committed, status_tx_fail, status_rx_done, status_tx_done, status_busy, status_phy_ready};
          REG_STATUS_RETRY_COUNT: rd_data <= {24'd0, status_retry_count};
          REG_STATUS_ERROR_COUNTS: rd_data <= {8'd0, status_mask_bad_count, status_session_bad_count, status_crc_bad_count};
          REG_COUNTER_TX_PULSE: rd_data <= counter_tx_pulse;
          REG_COUNTER_RX_RAW_PULSE: rd_data <= counter_rx_raw_pulse;
          REG_COUNTER_FRAME_GOOD: rd_data <= counter_frame_good;
          REG_COUNTER_FRAME_BAD: rd_data <= counter_frame_bad;
          REG_COUNTER_ACK_SENT: rd_data <= counter_ack_sent;
          REG_COUNTER_ACK_SEEN: rd_data <= counter_ack_seen;
          REG_PROFILE_ID: rd_data <= PROFILE_ID_VALUE;
          default: rd_data <= 32'hBAD0_0BAD;
        endcase
      end
    end
  end
endmodule
