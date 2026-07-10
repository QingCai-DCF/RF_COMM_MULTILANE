`timescale 1ns/1ps

// P6 register window and mailbox front-end.  This block owns the host-visible
// payload/RX RAMs and delegates real TFDU transfer work to the external P6
// transport engine.  It intentionally contains no synthetic TX-to-RX copy.
module p6_local_transport_regs #(
  parameter logic [31:0] PROFILE_ID_VALUE = 32'h5036_2201,
  parameter int MAX_PAYLOAD_BYTES = 247
) (
  input  logic         clk,
  input  logic         rst_n,

  input  logic         wr_en,
  input  logic [11:0]  wr_addr,
  input  logic [31:0]  wr_data,
  input  logic         rd_en,
  input  logic [11:0]  rd_addr,
  output logic [31:0]  rd_data,
  output logic         rd_valid,

  output logic         engine_reset_pulse,
  output logic         engine_clear_pulse,
  output logic         engine_start_pulse,
  output logic         engine_stop_pulse,
  output logic         engine_shutdown_pulse,
  output logic         engine_enable_phy,
  output logic [15:0]  cfg_session,
  output logic [7:0]   cfg_lane_mask,
  output logic [7:0]   cfg_ack_lane_mask,
  output logic [15:0]  cfg_payload_len,
  output logic [7:0]   cfg_pattern_id,
  output logic [31:0]  cfg_seed,
  output logic [31:0]  cfg_timeout_cycles,
  input  logic [7:0]   engine_tx_payload_read_index,
  output logic [7:0]   engine_tx_payload_read_data,
  input  logic [7:0]   engine_compare_payload_read_index,
  output logic [7:0]   engine_compare_payload_read_data,
  output logic [31:0]  committed_payload_crc32,

  input  logic         engine_ready,
  input  logic         engine_busy,
  input  logic         engine_done_pulse,
  input  logic         engine_fail_pulse,
  input  logic         engine_timeout_pulse,
  input  logic [31:0]  engine_error_code,
  input  logic         engine_rx_byte_write_pulse,
  input  logic [7:0]   engine_rx_byte_write_index,
  input  logic [7:0]   engine_rx_byte_write_data,
  input  logic [15:0]  engine_rx_payload_len,
  input  logic [31:0]  engine_rx_payload_crc32,
  input  logic [31:0]  engine_rx_digest,
  input  logic [1:0]   engine_rx_good_mask,
  input  logic [31:0]  engine_crc_bad_count,
  input  logic [31:0]  engine_payload_mismatch_count,
  input  logic [31:0]  engine_retry_count,
  input  logic [31:0]  engine_retry_exhausted_count,
  input  logic [31:0]  engine_tx_fail_count,
  input  logic [31:0]  engine_txd_high_max,
  input  logic [31:0]  engine_duty_violation_count,
  input  logic [31:0]  engine_shutdown_reason,
  input  logic [31:0]  engine_tx_pulse_count,
  input  logic [31:0]  engine_rx_raw_count,
  input  logic [31:0]  engine_frame_good_count,
  input  logic [31:0]  engine_frame_bad_count,
  input  logic [31:0]  engine_ack_sent_count,
  input  logic [31:0]  engine_ack_seen_count,

  output logic [31:0]  commit_count,
  output logic [31:0]  debug_status
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
  localparam logic [11:0] REG_P6_TXD_HIGH_MAX        = 12'h14C;
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

  localparam logic [31:0] P6_ERROR_NONE          = 32'h0000_0000;
  localparam logic [31:0] P6_ERROR_SESSION       = 32'h0000_0001;
  localparam logic [31:0] P6_ERROR_LANE_MASK     = 32'h0000_0002;
  localparam logic [31:0] P6_ERROR_ACK_MASK      = 32'h0000_0003;
  localparam logic [31:0] P6_ERROR_PAYLOAD_LEN   = 32'h0000_0004;
  localparam logic [31:0] P6_ERROR_TIMEOUT_CFG   = 32'h0000_0005;
  localparam logic [31:0] P6_ERROR_NOT_COMMITTED = 32'h0000_0006;
  localparam logic [31:0] P6_ERROR_NOT_READY     = 32'h0000_0007;
  localparam logic [31:0] P6_STICKY_CONFIG       = 32'h0000_0001;
  localparam logic [31:0] P6_STICKY_TIMEOUT      = 32'h0000_0002;
  localparam logic [31:0] P6_STICKY_TX_FAIL      = 32'h0000_0004;
  localparam logic [31:0] P6_STICKY_SAFETY       = 32'h0000_0008;
  localparam logic [31:0] P6_MAILBOX_IDLE        = 32'h5036_4944; // P6ID
  localparam logic [31:0] P6_MAILBOX_COMMITTED   = 32'h5036_434d; // P6CM
  localparam logic [31:0] P6_MAILBOX_BUSY        = 32'h5036_4259; // P6BY
  localparam logic [31:0] P6_MAILBOX_DONE        = 32'h5036_4f4b; // P6OK
  localparam logic [31:0] P6_MAILBOX_FAIL        = 32'h5036_464c; // P6FL
  localparam logic [31:0] P6_CAPS_VALUE          = {8'h06, 8'h03, MAX_PAYLOAD_BYTES[15:0]};

  logic [31:0] payload_ram [0:63];
  logic [31:0] rx_ram [0:63];
  logic [5:0] payload_index;
  logic [5:0] rx_index;
  logic committed;
  logic busy;
  logic done;
  logic fail;
  logic config_rejected;
  logic timeout;
  logic [31:0] error_code;
  logic [31:0] sticky_error;
  logic [31:0] mailbox_status;
  logic [31:0] shutdown_reason;
  logic [31:0] tx_count;
  logic [31:0] rx_good_count_l0;
  logic [31:0] rx_good_count_l1;
  logic [31:0] rx_payload_crc32;
  logic [31:0] rx_digest;
  logic [15:0] rx_payload_len;
  logic commit_crc_busy;
  logic [8:0] commit_crc_index;
  logic [31:0] commit_crc_state;

  function automatic logic [31:0] crc32_next_byte(
    input logic [7:0] data,
    input logic [31:0] crc_in
  );
    logic [31:0] c;
    begin
      c = crc_in;
      for (int bit_idx = 0; bit_idx < 8; bit_idx++) begin
        c = (c[0] ^ data[bit_idx]) ? ((c >> 1) ^ 32'hEDB8_8320) : (c >> 1);
      end
      crc32_next_byte = c;
    end
  endfunction

  function automatic logic [7:0] payload_byte(input int byte_index);
    logic [31:0] word_value;
    begin
      word_value = payload_ram[byte_index >> 2];
      payload_byte = word_value[8*(byte_index & 3) +: 8];
    end
  endfunction

  function automatic logic [31:0] validate_config(input logic require_commit);
    begin
      if (require_commit && !committed) begin
        validate_config = P6_ERROR_NOT_COMMITTED;
      end else if (cfg_session != 16'h2201) begin
        validate_config = P6_ERROR_SESSION;
      end else if (!((cfg_lane_mask == 8'h01) || (cfg_lane_mask == 8'h02) || (cfg_lane_mask == 8'h03))) begin
        validate_config = P6_ERROR_LANE_MASK;
      end else if (cfg_ack_lane_mask != cfg_lane_mask) begin
        validate_config = P6_ERROR_ACK_MASK;
      end else if ((cfg_payload_len == 16'd0) || (cfg_payload_len > MAX_PAYLOAD_BYTES[15:0])) begin
        validate_config = P6_ERROR_PAYLOAD_LEN;
      end else if (cfg_timeout_cycles == 32'd0) begin
        validate_config = P6_ERROR_TIMEOUT_CFG;
      end else begin
        validate_config = P6_ERROR_NONE;
      end
    end
  endfunction

  task automatic reject_config(input logic [31:0] reject_code);
    begin
      committed <= 1'b0;
      engine_enable_phy <= 1'b0;
      busy <= 1'b0;
      done <= 1'b1;
      fail <= 1'b1;
      config_rejected <= 1'b1;
      timeout <= 1'b0;
      error_code <= reject_code;
      sticky_error <= sticky_error | P6_STICKY_CONFIG;
      mailbox_status <= P6_MAILBOX_FAIL;
    end
  endtask

  always_comb begin
    engine_tx_payload_read_data = payload_byte(engine_tx_payload_read_index);
    engine_compare_payload_read_data = payload_byte(engine_compare_payload_read_index);
    debug_status = {
      8'h50,
      engine_ready,
      engine_enable_phy,
      engine_busy,
      busy,
      done,
      fail,
      timeout,
      config_rejected,
      committed,
      11'd0,
      cfg_ack_lane_mask[1:0],
      cfg_lane_mask[1:0]
    };
  end

  always_ff @(posedge clk or negedge rst_n) begin
    logic [31:0] validation_result;
    if (!rst_n) begin
      engine_reset_pulse <= 1'b0;
      engine_clear_pulse <= 1'b0;
      engine_start_pulse <= 1'b0;
      engine_stop_pulse <= 1'b0;
      engine_shutdown_pulse <= 1'b0;

      engine_enable_phy <= 1'b0;
      cfg_session <= 16'h2201;
      cfg_lane_mask <= 8'h01;
      cfg_ack_lane_mask <= 8'h01;
      cfg_payload_len <= 16'd16;
      cfg_pattern_id <= 8'd0;
      cfg_seed <= 32'h0000_2201;
      cfg_timeout_cycles <= 32'd6_400_000;
      committed_payload_crc32 <= 32'd0;
      payload_index <= 6'd0;
      rx_index <= 6'd0;
      committed <= 1'b0;
      busy <= 1'b0;
      done <= 1'b0;
      fail <= 1'b0;
      config_rejected <= 1'b0;
      timeout <= 1'b0;
      error_code <= P6_ERROR_NONE;
      sticky_error <= 32'd0;
      mailbox_status <= P6_MAILBOX_IDLE;
      shutdown_reason <= 32'd0;
      tx_count <= 32'd0;
      rx_good_count_l0 <= 32'd0;
      rx_good_count_l1 <= 32'd0;
      rx_payload_crc32 <= 32'd0;
      rx_digest <= 32'd0;
      rx_payload_len <= 16'd0;
      commit_count <= 32'd0;
      commit_crc_busy <= 1'b0;
      commit_crc_index <= 9'd0;
      commit_crc_state <= 32'hFFFF_FFFF;
      for (int word_idx = 0; word_idx < 64; word_idx++) begin
        payload_ram[word_idx] <= 32'd0;
        rx_ram[word_idx] <= 32'd0;
      end
    end else begin
      engine_reset_pulse <= 1'b0;
      engine_clear_pulse <= 1'b0;
      engine_start_pulse <= 1'b0;
      engine_stop_pulse <= 1'b0;
      engine_shutdown_pulse <= 1'b0;

      if (engine_rx_byte_write_pulse) begin
        unique case (engine_rx_byte_write_index[1:0])
          2'd0: rx_ram[engine_rx_byte_write_index[7:2]][7:0] <= engine_rx_byte_write_data;
          2'd1: rx_ram[engine_rx_byte_write_index[7:2]][15:8] <= engine_rx_byte_write_data;
          2'd2: rx_ram[engine_rx_byte_write_index[7:2]][23:16] <= engine_rx_byte_write_data;
          default: rx_ram[engine_rx_byte_write_index[7:2]][31:24] <= engine_rx_byte_write_data;
        endcase
      end

      if (commit_crc_busy) begin
        logic [31:0] crc_next;
        crc_next = crc32_next_byte(payload_byte(commit_crc_index), commit_crc_state);
        if (commit_crc_index + 1'b1 >= cfg_payload_len) begin
          committed_payload_crc32 <= ~crc_next;
          committed <= 1'b1;
          engine_enable_phy <= 1'b1;
          commit_crc_busy <= 1'b0;
          commit_crc_index <= 9'd0;
          commit_crc_state <= 32'hFFFF_FFFF;
          commit_count <= commit_count + 1'b1;
          mailbox_status <= P6_MAILBOX_COMMITTED;
        end else begin
          commit_crc_state <= crc_next;
          commit_crc_index <= commit_crc_index + 1'b1;
        end
      end

      if (engine_done_pulse) begin
        busy <= 1'b0;
        done <= 1'b1;
        fail <= 1'b0;
        timeout <= 1'b0;
        error_code <= P6_ERROR_NONE;
        mailbox_status <= P6_MAILBOX_DONE;
        rx_payload_len <= engine_rx_payload_len;
        rx_payload_crc32 <= engine_rx_payload_crc32;
        rx_digest <= engine_rx_digest;
        tx_count <= tx_count + 1'b1;
        if (engine_rx_good_mask[0]) rx_good_count_l0 <= rx_good_count_l0 + 1'b1;
        if (engine_rx_good_mask[1]) rx_good_count_l1 <= rx_good_count_l1 + 1'b1;
      end
      if (engine_fail_pulse) begin
        busy <= 1'b0;
        done <= 1'b1;
        fail <= 1'b1;
        error_code <= (engine_error_code == 32'd0) ? P6_ERROR_NOT_READY : engine_error_code;
        sticky_error <= sticky_error | P6_STICKY_TX_FAIL;
        mailbox_status <= P6_MAILBOX_FAIL;
      end
      if (engine_timeout_pulse) begin
        busy <= 1'b0;
        done <= 1'b1;
        fail <= 1'b1;
        timeout <= 1'b1;
        error_code <= (engine_error_code == 32'd0) ? P6_ERROR_TIMEOUT_CFG : engine_error_code;
        sticky_error <= sticky_error | P6_STICKY_TIMEOUT;
        mailbox_status <= P6_MAILBOX_FAIL;
      end
      if (engine_duty_violation_count != 32'd0) begin
        sticky_error <= sticky_error | P6_STICKY_SAFETY;
      end

      if (wr_en) begin
        unique case (wr_addr)
          REG_CONTROL: begin
            if (wr_data[0]) begin
              engine_reset_pulse <= 1'b1;
              engine_enable_phy <= 1'b0;
              committed <= 1'b0;
              commit_crc_busy <= 1'b0;
            end
            if (wr_data[4]) engine_clear_pulse <= 1'b1;
            if (wr_data[3]) engine_stop_pulse <= 1'b1;
          end
          REG_PROFILE_LANE_MASK, REG_PROFILE_RX_LANE_MASK: begin
            cfg_lane_mask <= wr_data[7:0];
            committed <= 1'b0;
            engine_enable_phy <= 1'b0;
            commit_crc_busy <= 1'b0;
          end
          REG_PROFILE_ACK_LANE_MASK: begin
            cfg_ack_lane_mask <= wr_data[7:0];
            committed <= 1'b0;
            engine_enable_phy <= 1'b0;
            commit_crc_busy <= 1'b0;
          end
          REG_PROFILE_SESSION: begin
            cfg_session <= wr_data[15:0];
            committed <= 1'b0;
            engine_enable_phy <= 1'b0;
            commit_crc_busy <= 1'b0;
          end
          REG_PROFILE_PAYLOAD_LEN: begin
            cfg_payload_len <= wr_data[15:0];
            committed <= 1'b0;
            engine_enable_phy <= 1'b0;
            commit_crc_busy <= 1'b0;
          end
          REG_TIMING_RETRY_TIMEOUT: cfg_timeout_cycles <= wr_data;
          REG_SAFETY_SHUTDOWN_REASON: shutdown_reason <= wr_data;
          REG_P6_CTRL: begin
            if (wr_data[0]) begin
              engine_reset_pulse <= 1'b1;
              engine_enable_phy <= 1'b0;
              committed <= 1'b0;
              commit_crc_busy <= 1'b0;
              busy <= 1'b0;
              done <= 1'b0;
              fail <= 1'b0;
              config_rejected <= 1'b0;
              timeout <= 1'b0;
              error_code <= P6_ERROR_NONE;
              sticky_error <= 32'd0;
              mailbox_status <= P6_MAILBOX_IDLE;
              shutdown_reason <= 32'd0;
              tx_count <= 32'd0;
              rx_good_count_l0 <= 32'd0;
              rx_good_count_l1 <= 32'd0;
            end
            if (wr_data[1]) begin
              engine_clear_pulse <= 1'b1;
              done <= 1'b0;
              fail <= 1'b0;
              config_rejected <= 1'b0;
              timeout <= 1'b0;
              error_code <= P6_ERROR_NONE;
              sticky_error <= 32'd0;
              mailbox_status <= committed ? P6_MAILBOX_COMMITTED : P6_MAILBOX_IDLE;
            end
            if (wr_data[2]) begin
              validation_result = validate_config(1'b0);
              if (validation_result == P6_ERROR_NONE) begin
                committed <= 1'b0;
                engine_enable_phy <= 1'b0;
                commit_crc_busy <= 1'b1;
                commit_crc_index <= 9'd0;
                commit_crc_state <= 32'hFFFF_FFFF;
                busy <= 1'b0;
                done <= 1'b0;
                fail <= 1'b0;
                config_rejected <= 1'b0;
                timeout <= 1'b0;
                error_code <= P6_ERROR_NONE;
                mailbox_status <= P6_MAILBOX_BUSY;
              end else begin
                reject_config(validation_result);
              end
            end
            if (wr_data[3]) begin
              validation_result = validate_config(1'b1);
              if (validation_result == P6_ERROR_NONE && !engine_busy) begin
                engine_start_pulse <= 1'b1;
                busy <= 1'b1;
                done <= 1'b0;
                fail <= 1'b0;
                config_rejected <= 1'b0;
                timeout <= 1'b0;
                error_code <= P6_ERROR_NONE;
                mailbox_status <= P6_MAILBOX_BUSY;
              end else if (validation_result != P6_ERROR_NONE) begin
                reject_config(validation_result);
              end else begin
                reject_config(P6_ERROR_NOT_READY);
              end
            end
            if (wr_data[4]) begin
              engine_stop_pulse <= 1'b1;
              busy <= 1'b0;
            end
            if (wr_data[5]) begin
              engine_stop_pulse <= 1'b1;
              engine_shutdown_pulse <= 1'b1;
              engine_enable_phy <= 1'b0;
              busy <= 1'b0;
              committed <= 1'b0;
              commit_crc_busy <= 1'b0;
              shutdown_reason <= 32'h5446_4455;
              mailbox_status <= P6_MAILBOX_IDLE;
            end
          end
          REG_P6_SESSION: begin
            cfg_session <= wr_data[15:0]; committed <= 1'b0; engine_enable_phy <= 1'b0; commit_crc_busy <= 1'b0;
          end
          REG_P6_LANE_MASK: begin
            cfg_lane_mask <= wr_data[7:0]; committed <= 1'b0; engine_enable_phy <= 1'b0; commit_crc_busy <= 1'b0;
          end
          REG_P6_ACK_LANE_MASK: begin
            cfg_ack_lane_mask <= wr_data[7:0]; committed <= 1'b0; engine_enable_phy <= 1'b0; commit_crc_busy <= 1'b0;
          end
          REG_P6_PAYLOAD_LEN: begin
            cfg_payload_len <= wr_data[15:0]; committed <= 1'b0; engine_enable_phy <= 1'b0; commit_crc_busy <= 1'b0;
          end
          REG_P6_PAYLOAD_PATTERN_ID: cfg_pattern_id <= wr_data[7:0];
          REG_P6_PAYLOAD_SEED: cfg_seed <= wr_data;
          REG_P6_SHUTDOWN_REASON: shutdown_reason <= wr_data;
          REG_P6_TIMEOUT_CYCLES: cfg_timeout_cycles <= wr_data;
          REG_P6_PAYLOAD_WORD_INDEX: begin
            payload_index <= wr_data[5:0];
            if (wr_data[31:6] != 26'd0) reject_config(P6_ERROR_PAYLOAD_LEN);
          end
          REG_P6_PAYLOAD_WORD_DATA: begin
            if (!busy && !engine_busy && !commit_crc_busy) begin
              payload_ram[payload_index] <= wr_data;
              committed <= 1'b0;
              engine_enable_phy <= 1'b0;
              commit_crc_busy <= 1'b0;
            end
          end
          REG_P6_RX_WORD_INDEX: begin
            rx_index <= wr_data[5:0];
            if (wr_data[31:6] != 26'd0) reject_config(P6_ERROR_PAYLOAD_LEN);
          end
          default: begin
            if ((wr_addr >= REG_P6_PAYLOAD_WINDOW_BASE) &&
                (wr_addr < REG_P6_PAYLOAD_WINDOW_BASE + 12'h100) &&
                (wr_addr[1:0] == 2'b00) && !busy && !engine_busy && !commit_crc_busy) begin
              payload_ram[wr_addr[7:2]] <= wr_data;
              committed <= 1'b0;
              engine_enable_phy <= 1'b0;
            end
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
          REG_CONTROL: rd_data <= {26'd0, committed, 3'd0, engine_enable_phy};
          REG_PROFILE_LANE_MASK, REG_PROFILE_RX_LANE_MASK: rd_data <= {24'd0, cfg_lane_mask};
          REG_PROFILE_ACK_LANE_MASK: rd_data <= {24'd0, cfg_ack_lane_mask};
          REG_PROFILE_SESSION: rd_data <= {16'd0, cfg_session};
          REG_PROFILE_PAYLOAD_LEN: rd_data <= {16'd0, cfg_payload_len};
          REG_PROFILE_FRAGMENT_BYTES: rd_data <= 32'd247;
          REG_TIMING_CNT_CHIP_MAX: rd_data <= 32'd31;
          REG_TIMING_CNT_PREAMBLE: rd_data <= 32'd16;
          REG_TIMING_DETECT_WINDOW: rd_data <= 32'h0000_1f00;
          REG_TIMING_GUARD_CYCLES: rd_data <= 32'd4096;
          REG_TIMING_RETRY_TIMEOUT: rd_data <= cfg_timeout_cycles;
          REG_SAFETY_STARTUP_US: rd_data <= 32'd500;
          REG_SAFETY_DUTY_WINDOW: rd_data <= 32'd1000;
          REG_SAFETY_DUTY_MAX: rd_data <= 32'd200;
          REG_SAFETY_STUCK_HIGH_LIMIT: rd_data <= 32'd10;
          REG_SAFETY_SHUTDOWN_REASON: rd_data <= (engine_shutdown_reason != 32'd0) ? engine_shutdown_reason : shutdown_reason;
          REG_STATUS: rd_data <= {26'd0, committed, (engine_tx_fail_count != 0), done, done, (busy || engine_busy || commit_crc_busy), engine_ready};
          REG_STATUS_RETRY_COUNT: rd_data <= engine_retry_count;
          REG_STATUS_ERROR_COUNTS: rd_data <= {24'd0, engine_crc_bad_count[7:0]};
          REG_COUNTER_TX_PULSE: rd_data <= engine_tx_pulse_count;
          REG_COUNTER_RX_RAW_PULSE: rd_data <= engine_rx_raw_count;
          REG_COUNTER_FRAME_GOOD: rd_data <= engine_frame_good_count;
          REG_COUNTER_FRAME_BAD: rd_data <= engine_frame_bad_count;
          REG_COUNTER_ACK_SENT: rd_data <= engine_ack_sent_count;
          REG_COUNTER_ACK_SEEN: rd_data <= engine_ack_seen_count;
          REG_PROFILE_ID: rd_data <= PROFILE_ID_VALUE;
          REG_P6_CTRL: rd_data <= 32'd0;
          REG_P6_STATUS: rd_data <= {24'd0, timeout, config_rejected, fail, done, (busy || engine_busy || commit_crc_busy), committed, engine_ready, engine_enable_phy};
          REG_P6_SESSION: rd_data <= {16'd0, cfg_session};
          REG_P6_LANE_MASK: rd_data <= {24'd0, cfg_lane_mask};
          REG_P6_ACK_LANE_MASK: rd_data <= {24'd0, cfg_ack_lane_mask};
          REG_P6_PAYLOAD_LEN: rd_data <= {16'd0, cfg_payload_len};
          REG_P6_PAYLOAD_PATTERN_ID: rd_data <= {24'd0, cfg_pattern_id};
          REG_P6_PAYLOAD_SEED: rd_data <= cfg_seed;
          REG_P6_PAYLOAD_CRC32: rd_data <= committed_payload_crc32;
          REG_P6_RX_PAYLOAD_CRC32: rd_data <= rx_payload_crc32;
          REG_P6_RX_PAYLOAD_LEN: rd_data <= {16'd0, rx_payload_len};
          REG_P6_TX_COUNT: rd_data <= tx_count;
          REG_P6_RX_GOOD_COUNT_L0: rd_data <= rx_good_count_l0;
          REG_P6_RX_GOOD_COUNT_L1: rd_data <= rx_good_count_l1;
          REG_P6_CRC_BAD: rd_data <= engine_crc_bad_count;
          REG_P6_PAYLOAD_MISMATCH: rd_data <= engine_payload_mismatch_count;
          REG_P6_RETRY_COUNT: rd_data <= engine_retry_count;
          REG_P6_RETRY_EXHAUSTED: rd_data <= engine_retry_exhausted_count;
          REG_P6_TX_FAIL: rd_data <= engine_tx_fail_count;
          REG_P6_TXD_HIGH_MAX: rd_data <= engine_txd_high_max;
          REG_P6_DUTY_VIOLATION: rd_data <= engine_duty_violation_count;
          REG_P6_SHUTDOWN_REASON: rd_data <= (engine_shutdown_reason != 32'd0) ? engine_shutdown_reason : shutdown_reason;
          REG_P6_MAILBOX_STATUS: rd_data <= mailbox_status;
          REG_P6_TIMEOUT_CYCLES: rd_data <= cfg_timeout_cycles;
          REG_P6_ERROR_CODE: rd_data <= error_code;
          REG_P6_STICKY_ERROR: rd_data <= sticky_error;
          REG_P6_RX_DIGEST: rd_data <= rx_digest;
          REG_P6_PAYLOAD_WORD_INDEX: rd_data <= {26'd0, payload_index};
          REG_P6_PAYLOAD_WORD_DATA: rd_data <= payload_ram[payload_index];
          REG_P6_RX_WORD_INDEX: rd_data <= {26'd0, rx_index};
          REG_P6_RX_WORD_DATA: rd_data <= rx_ram[rx_index];
          REG_P6_CAPS: rd_data <= P6_CAPS_VALUE;
          default: begin
            if ((rd_addr >= REG_P6_PAYLOAD_WINDOW_BASE) &&
                (rd_addr < REG_P6_PAYLOAD_WINDOW_BASE + 12'h100) &&
                (rd_addr[1:0] == 2'b00)) begin
              rd_data <= payload_ram[rd_addr[7:2]];
            end else if ((rd_addr >= REG_P6_RX_WINDOW_BASE) &&
                         (rd_addr < REG_P6_RX_WINDOW_BASE + 12'h100) &&
                         (rd_addr[1:0] == 2'b00)) begin
              rd_data <= rx_ram[rd_addr[7:2]];
            end else begin
              rd_data <= 32'hBAD0_0BAD;
            end
          end
        endcase
      end
    end
  end
endmodule
