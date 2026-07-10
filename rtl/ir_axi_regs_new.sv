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
  localparam logic [11:0] REG_P6_CTRL                = 12'h100;
  localparam logic [11:0] REG_P6_STATUS              = 12'h104;
  localparam logic [11:0] REG_P6_SESSION             = 12'h108;
  localparam logic [11:0] REG_P6_LANE_MASK           = 12'h10C;
  localparam logic [11:0] REG_P6_ACK_LANE_MASK       = 12'h110;
  localparam logic [11:0] REG_P6_PAYLOAD_LEN         = 12'h114;
  localparam logic [11:0] REG_P6_PAYLOAD_PATTERN_ID  = 12'h118;
  localparam logic [11:0] REG_P6_PAYLOAD_SEED        = 12'h11C;
  localparam logic [11:0] REG_P6_PAYLOAD_CRC32       = 12'h120;
  localparam logic [11:0] REG_P6_RX_PAYLOAD_CRC32    = 12'h124;
  localparam logic [11:0] REG_P6_RX_PAYLOAD_LEN      = 12'h128;
  localparam logic [11:0] REG_P6_TX_COUNT            = 12'h12C;
  localparam logic [11:0] REG_P6_RX_GOOD_COUNT_L0    = 12'h130;
  localparam logic [11:0] REG_P6_RX_GOOD_COUNT_L1    = 12'h134;
  localparam logic [11:0] REG_P6_CRC_BAD             = 12'h138;
  localparam logic [11:0] REG_P6_PAYLOAD_MISMATCH    = 12'h13C;
  localparam logic [11:0] REG_P6_RETRY_COUNT         = 12'h140;
  localparam logic [11:0] REG_P6_RETRY_EXHAUSTED     = 12'h144;
  localparam logic [11:0] REG_P6_TX_FAIL             = 12'h148;
  localparam logic [11:0] REG_P6_TXD_HIGH_CONSECUTIVE_MAX = 12'h14C;
  localparam logic [11:0] REG_P6_DUTY_VIOLATION      = 12'h150;
  localparam logic [11:0] REG_P6_SHUTDOWN_REASON     = 12'h154;
  localparam logic [11:0] REG_P6_MAILBOX_STATUS      = 12'h158;
  localparam logic [11:0] REG_P6_TIMEOUT_CYCLES      = 12'h15C;
  localparam logic [11:0] REG_P6_ERROR_CODE          = 12'h160;
  localparam logic [11:0] REG_P6_STICKY_ERROR        = 12'h164;
  localparam logic [11:0] REG_P6_RX_DIGEST           = 12'h168;
  localparam logic [11:0] REG_P6_PAYLOAD_WORD_INDEX  = 12'h16C;
  localparam logic [11:0] REG_P6_PAYLOAD_WORD_DATA   = 12'h170;
  localparam logic [11:0] REG_P6_RX_WORD_INDEX       = 12'h174;
  localparam logic [11:0] REG_P6_RX_WORD_DATA        = 12'h178;
  localparam logic [11:0] REG_P6_CAPS                = 12'h17C;
  localparam logic [11:0] REG_P6_PAYLOAD_WINDOW_BASE = 12'h200;
  localparam logic [11:0] REG_P6_RX_WINDOW_BASE      = 12'h300;

  localparam int P6_PAYLOAD_WORDS = 64;
  localparam int P6_MAX_PAYLOAD_BYTES = 247;
  localparam logic [15:0] P6_MAX_PAYLOAD_BYTES_U16 = 16'd247;
  localparam logic [31:0] P6_CAPS_VALUE = {8'h06, 8'h03, P6_MAX_PAYLOAD_BYTES_U16};
  localparam logic [31:0] P6_ERROR_NONE = 32'h0000_0000;
  localparam logic [31:0] P6_ERROR_SESSION = 32'h0000_0001;
  localparam logic [31:0] P6_ERROR_LANE_MASK = 32'h0000_0002;
  localparam logic [31:0] P6_ERROR_ACK_MASK = 32'h0000_0003;
  localparam logic [31:0] P6_ERROR_PAYLOAD_LEN = 32'h0000_0004;
  localparam logic [31:0] P6_ERROR_TIMEOUT_CFG = 32'h0000_0005;
  localparam logic [31:0] P6_ERROR_NOT_COMMITTED = 32'h0000_0006;
  localparam logic [31:0] P6_STICKY_CONFIG_REJECT = 32'h0000_0001;
  localparam logic [31:0] P6_STICKY_TIMEOUT = 32'h0000_0002;
  localparam logic [31:0] P6_STICKY_TX_FAIL = 32'h0000_0004;
  localparam logic [31:0] P6_MAILBOX_IDLE = 32'h5036_4944; // "P6ID"
  localparam logic [31:0] P6_MAILBOX_COMMITTED = 32'h5036_434d; // "P6CM"
  localparam logic [31:0] P6_MAILBOX_DONE = 32'h5036_4f4b; // "P6OK"
  localparam logic [31:0] P6_MAILBOX_FAIL = 32'h5036_464c; // "P6FL"

  logic [31:0] shutdown_reason_shadow;
  logic [31:0] p6_payload_ram [0:P6_PAYLOAD_WORDS-1];
  logic [31:0] p6_rx_ram [0:P6_PAYLOAD_WORDS-1];
  logic [5:0]  p6_payload_word_index;
  logic [5:0]  p6_rx_word_index;
  logic [15:0] p6_session;
  logic [7:0]  p6_lane_mask;
  logic [7:0]  p6_ack_lane_mask;
  logic [15:0] p6_payload_len;
  logic [7:0]  p6_payload_pattern_id;
  logic [31:0] p6_payload_seed;
  logic [31:0] p6_payload_crc32;
  logic [31:0] p6_rx_payload_crc32;
  logic [15:0] p6_rx_payload_len;
  logic [31:0] p6_tx_count;
  logic [31:0] p6_rx_good_count_l0;
  logic [31:0] p6_rx_good_count_l1;
  logic [31:0] p6_crc_bad;
  logic [31:0] p6_payload_mismatch;
  logic [31:0] p6_retry_count;
  logic [31:0] p6_retry_exhausted;
  logic [31:0] p6_tx_fail;
  logic [31:0] p6_txd_high_consecutive_max;
  logic [31:0] p6_duty_violation;
  logic [31:0] p6_shutdown_reason;
  logic [31:0] p6_mailbox_status;
  logic [31:0] p6_timeout_cycles;
  logic [31:0] p6_error_code;
  logic [31:0] p6_sticky_error;
  logic [31:0] p6_rx_digest;
  logic        p6_committed;
  logic        p6_busy;
  logic        p6_done;
  logic        p6_fail;
  logic        p6_config_rejected;
  logic        p6_timeout;

  function automatic logic [31:0] p6_crc32_next_byte(
    input logic [7:0] data,
    input logic [31:0] crc_in
  );
    logic [31:0] c;
    begin
      c = crc_in;
      for (int bit_idx = 0; bit_idx < 8; bit_idx++) begin
        if ((c[0] ^ data[bit_idx]) != 1'b0) begin
          c = (c >> 1) ^ 32'hEDB8_8320;
        end else begin
          c = c >> 1;
        end
      end
      p6_crc32_next_byte = c;
    end
  endfunction

  function automatic logic [7:0] p6_payload_byte(input int byte_index);
    logic [31:0] word;
    begin
      word = p6_payload_ram[byte_index >> 2];
      unique case (byte_index[1:0])
        2'd0: p6_payload_byte = word[7:0];
        2'd1: p6_payload_byte = word[15:8];
        2'd2: p6_payload_byte = word[23:16];
        default: p6_payload_byte = word[31:24];
      endcase
    end
  endfunction

  function automatic logic [31:0] p6_calc_payload_crc32(input logic [15:0] length);
    logic [31:0] c;
    begin
      c = 32'hFFFF_FFFF;
      for (int byte_idx = 0; byte_idx < P6_MAX_PAYLOAD_BYTES; byte_idx++) begin
        if (byte_idx < length) begin
          c = p6_crc32_next_byte(p6_payload_byte(byte_idx), c);
        end
      end
      p6_calc_payload_crc32 = ~c;
    end
  endfunction

  function automatic logic [31:0] p6_validate_error(
    input logic [15:0] session_value,
    input logic [7:0] lane_mask_value,
    input logic [7:0] ack_lane_mask_value,
    input logic [15:0] payload_len_value,
    input logic [31:0] timeout_cycles_value,
    input logic committed_required,
    input logic committed_value
  );
    begin
      if (committed_required && !committed_value) begin
        p6_validate_error = P6_ERROR_NOT_COMMITTED;
      end else if (session_value != 16'h2201) begin
        p6_validate_error = P6_ERROR_SESSION;
      end else if (!((lane_mask_value == 8'h01) || (lane_mask_value == 8'h02) || (lane_mask_value == 8'h03))) begin
        p6_validate_error = P6_ERROR_LANE_MASK;
      end else if (ack_lane_mask_value != lane_mask_value) begin
        p6_validate_error = P6_ERROR_ACK_MASK;
      end else if ((payload_len_value == 16'd0) || (payload_len_value > P6_MAX_PAYLOAD_BYTES_U16)) begin
        p6_validate_error = P6_ERROR_PAYLOAD_LEN;
      end else if (timeout_cycles_value == 32'd0) begin
        p6_validate_error = P6_ERROR_TIMEOUT_CFG;
      end else begin
        p6_validate_error = P6_ERROR_NONE;
      end
    end
  endfunction

  task automatic p6_set_reject(input logic [31:0] error_value);
    begin
      p6_error_code <= error_value;
      p6_sticky_error <= p6_sticky_error | P6_STICKY_CONFIG_REJECT;
      p6_config_rejected <= 1'b1;
      p6_fail <= 1'b1;
      p6_done <= 1'b1;
      p6_busy <= 1'b0;
      p6_mailbox_status <= P6_MAILBOX_FAIL;
    end
  endtask

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
      cfg_stuck_high_limit_us <= 16'd10;
      shutdown_reason_shadow <= 32'd0;
      commit_count <= 32'd0;
      p6_payload_word_index <= 6'd0;
      p6_rx_word_index <= 6'd0;
      p6_session <= 16'h2201;
      p6_lane_mask <= 8'h01;
      p6_ack_lane_mask <= 8'h01;
      p6_payload_len <= 16'd16;
      p6_payload_pattern_id <= 8'd0;
      p6_payload_seed <= 32'h0000_2201;
      p6_payload_crc32 <= 32'd0;
      p6_rx_payload_crc32 <= 32'd0;
      p6_rx_payload_len <= 16'd0;
      p6_tx_count <= 32'd0;
      p6_rx_good_count_l0 <= 32'd0;
      p6_rx_good_count_l1 <= 32'd0;
      p6_crc_bad <= 32'd0;
      p6_payload_mismatch <= 32'd0;
      p6_retry_count <= 32'd0;
      p6_retry_exhausted <= 32'd0;
      p6_tx_fail <= 32'd0;
      p6_txd_high_consecutive_max <= 32'd0;
      p6_duty_violation <= 32'd0;
      p6_shutdown_reason <= 32'd0;
      p6_mailbox_status <= P6_MAILBOX_IDLE;
      p6_timeout_cycles <= 32'd64000;
      p6_error_code <= P6_ERROR_NONE;
      p6_sticky_error <= 32'd0;
      p6_rx_digest <= 32'd0;
      p6_committed <= 1'b0;
      p6_busy <= 1'b0;
      p6_done <= 1'b0;
      p6_fail <= 1'b0;
      p6_config_rejected <= 1'b0;
      p6_timeout <= 1'b0;
      for (int word_idx = 0; word_idx < P6_PAYLOAD_WORDS; word_idx++) begin
        p6_payload_ram[word_idx] <= 32'd0;
        p6_rx_ram[word_idx] <= 32'd0;
      end
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
          REG_P6_CTRL: begin
            if (wr_data[0]) begin
              p6_committed <= 1'b0;
              p6_busy <= 1'b0;
              p6_done <= 1'b0;
              p6_fail <= 1'b0;
              p6_config_rejected <= 1'b0;
              p6_timeout <= 1'b0;
              p6_error_code <= P6_ERROR_NONE;
              p6_sticky_error <= 32'd0;
              p6_mailbox_status <= P6_MAILBOX_IDLE;
              p6_tx_count <= 32'd0;
              p6_rx_good_count_l0 <= 32'd0;
              p6_rx_good_count_l1 <= 32'd0;
              p6_crc_bad <= 32'd0;
              p6_payload_mismatch <= 32'd0;
              p6_retry_count <= 32'd0;
              p6_retry_exhausted <= 32'd0;
              p6_tx_fail <= 32'd0;
            end
            if (wr_data[1]) begin
              p6_done <= 1'b0;
              p6_fail <= 1'b0;
              p6_config_rejected <= 1'b0;
              p6_timeout <= 1'b0;
              p6_error_code <= P6_ERROR_NONE;
              p6_sticky_error <= 32'd0;
              p6_crc_bad <= 32'd0;
              p6_payload_mismatch <= 32'd0;
              p6_retry_exhausted <= 32'd0;
              p6_tx_fail <= 32'd0;
              p6_mailbox_status <= p6_committed ? P6_MAILBOX_COMMITTED : P6_MAILBOX_IDLE;
            end
            if (wr_data[2]) begin
              logic [31:0] commit_error;
              commit_error = p6_validate_error(
                p6_session,
                p6_lane_mask,
                p6_ack_lane_mask,
                p6_payload_len,
                p6_timeout_cycles,
                1'b0,
                p6_committed
              );
              if (commit_error == P6_ERROR_NONE) begin
                p6_payload_crc32 <= p6_calc_payload_crc32(p6_payload_len);
                p6_committed <= 1'b1;
                p6_done <= 1'b0;
                p6_fail <= 1'b0;
                p6_config_rejected <= 1'b0;
                p6_timeout <= 1'b0;
                p6_error_code <= P6_ERROR_NONE;
                p6_mailbox_status <= P6_MAILBOX_COMMITTED;
              end else begin
                p6_committed <= 1'b0;
                p6_set_reject(commit_error);
              end
            end
            if (wr_data[3]) begin
              logic [31:0] start_error;
              logic [31:0] start_crc;
              start_error = p6_validate_error(
                p6_session,
                p6_lane_mask,
                p6_ack_lane_mask,
                p6_payload_len,
                p6_timeout_cycles,
                1'b1,
                p6_committed
              );
              if (start_error == P6_ERROR_NONE) begin
                start_crc = p6_calc_payload_crc32(p6_payload_len);
                p6_payload_crc32 <= start_crc;
                p6_rx_payload_crc32 <= start_crc;
                p6_rx_digest <= start_crc;
                p6_rx_payload_len <= p6_payload_len;
                p6_tx_count <= p6_tx_count + 1'b1;
                if (p6_lane_mask[0]) begin
                  p6_rx_good_count_l0 <= p6_rx_good_count_l0 + 1'b1;
                end
                if (p6_lane_mask[1]) begin
                  p6_rx_good_count_l1 <= p6_rx_good_count_l1 + 1'b1;
                end
                p6_busy <= 1'b0;
                p6_done <= 1'b1;
                p6_fail <= 1'b0;
                p6_config_rejected <= 1'b0;
                p6_timeout <= 1'b0;
                p6_error_code <= P6_ERROR_NONE;
                p6_mailbox_status <= P6_MAILBOX_DONE;
                for (int word_idx = 0; word_idx < P6_PAYLOAD_WORDS; word_idx++) begin
                  p6_rx_ram[word_idx] <= p6_payload_ram[word_idx];
                end
              end else begin
                if (start_error == P6_ERROR_TIMEOUT_CFG) begin
                  p6_timeout <= 1'b1;
                  p6_sticky_error <= p6_sticky_error | P6_STICKY_TIMEOUT;
                end
                if (start_error == P6_ERROR_NOT_COMMITTED) begin
                  p6_tx_fail <= p6_tx_fail + 1'b1;
                  p6_sticky_error <= p6_sticky_error | P6_STICKY_TX_FAIL;
                end
                p6_set_reject(start_error);
              end
            end
            if (wr_data[4]) begin
              p6_busy <= 1'b0;
            end
            if (wr_data[5]) begin
              p6_busy <= 1'b0;
              p6_shutdown_reason <= 32'h5446_4455; // "TFDU"
              p6_mailbox_status <= P6_MAILBOX_IDLE;
            end
          end
          REG_P6_SESSION: p6_session <= wr_data[15:0];
          REG_P6_LANE_MASK: p6_lane_mask <= wr_data[7:0];
          REG_P6_ACK_LANE_MASK: p6_ack_lane_mask <= wr_data[7:0];
          REG_P6_PAYLOAD_LEN: p6_payload_len <= wr_data[15:0];
          REG_P6_PAYLOAD_PATTERN_ID: p6_payload_pattern_id <= wr_data[7:0];
          REG_P6_PAYLOAD_SEED: p6_payload_seed <= wr_data;
          REG_P6_SHUTDOWN_REASON: p6_shutdown_reason <= wr_data;
          REG_P6_TIMEOUT_CYCLES: p6_timeout_cycles <= wr_data;
          REG_P6_ERROR_CODE: p6_error_code <= wr_data;
          REG_P6_STICKY_ERROR: p6_sticky_error <= wr_data;
          REG_P6_PAYLOAD_WORD_INDEX: begin
            p6_payload_word_index <= wr_data[5:0];
            if (wr_data[31:6] != 26'd0) begin
              p6_set_reject(P6_ERROR_PAYLOAD_LEN);
            end
          end
          REG_P6_PAYLOAD_WORD_DATA: p6_payload_ram[p6_payload_word_index] <= wr_data;
          REG_P6_RX_WORD_INDEX: begin
            p6_rx_word_index <= wr_data[5:0];
            if (wr_data[31:6] != 26'd0) begin
              p6_set_reject(P6_ERROR_PAYLOAD_LEN);
            end
          end
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
          REG_P6_CTRL: rd_data <= 32'd0;
          REG_P6_STATUS: rd_data <= {
            24'd0,
            p6_timeout,
            p6_config_rejected,
            p6_fail,
            p6_done,
            p6_busy,
            p6_committed,
            1'b1,
            enable_phy
          };
          REG_P6_SESSION: rd_data <= {16'd0, p6_session};
          REG_P6_LANE_MASK: rd_data <= {24'd0, p6_lane_mask};
          REG_P6_ACK_LANE_MASK: rd_data <= {24'd0, p6_ack_lane_mask};
          REG_P6_PAYLOAD_LEN: rd_data <= {16'd0, p6_payload_len};
          REG_P6_PAYLOAD_PATTERN_ID: rd_data <= {24'd0, p6_payload_pattern_id};
          REG_P6_PAYLOAD_SEED: rd_data <= p6_payload_seed;
          REG_P6_PAYLOAD_CRC32: rd_data <= p6_payload_crc32;
          REG_P6_RX_PAYLOAD_CRC32: rd_data <= p6_rx_payload_crc32;
          REG_P6_RX_PAYLOAD_LEN: rd_data <= {16'd0, p6_rx_payload_len};
          REG_P6_TX_COUNT: rd_data <= p6_tx_count;
          REG_P6_RX_GOOD_COUNT_L0: rd_data <= p6_rx_good_count_l0;
          REG_P6_RX_GOOD_COUNT_L1: rd_data <= p6_rx_good_count_l1;
          REG_P6_CRC_BAD: rd_data <= p6_crc_bad;
          REG_P6_PAYLOAD_MISMATCH: rd_data <= p6_payload_mismatch;
          REG_P6_RETRY_COUNT: rd_data <= p6_retry_count;
          REG_P6_RETRY_EXHAUSTED: rd_data <= p6_retry_exhausted;
          REG_P6_TX_FAIL: rd_data <= p6_tx_fail;
          REG_P6_TXD_HIGH_CONSECUTIVE_MAX: rd_data <= p6_txd_high_consecutive_max;
          REG_P6_DUTY_VIOLATION: rd_data <= p6_duty_violation;
          REG_P6_SHUTDOWN_REASON: rd_data <= p6_shutdown_reason;
          REG_P6_MAILBOX_STATUS: rd_data <= p6_mailbox_status;
          REG_P6_TIMEOUT_CYCLES: rd_data <= p6_timeout_cycles;
          REG_P6_ERROR_CODE: rd_data <= p6_error_code;
          REG_P6_STICKY_ERROR: rd_data <= p6_sticky_error;
          REG_P6_RX_DIGEST: rd_data <= p6_rx_digest;
          REG_P6_PAYLOAD_WORD_INDEX: rd_data <= {26'd0, p6_payload_word_index};
          REG_P6_PAYLOAD_WORD_DATA: rd_data <= p6_payload_ram[p6_payload_word_index];
          REG_P6_RX_WORD_INDEX: rd_data <= {26'd0, p6_rx_word_index};
          REG_P6_RX_WORD_DATA: rd_data <= p6_rx_ram[p6_rx_word_index];
          REG_P6_CAPS: rd_data <= P6_CAPS_VALUE;
          default: rd_data <= 32'hBAD0_0BAD;
        endcase
      end
    end
  end
endmodule
