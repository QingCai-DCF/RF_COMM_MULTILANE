`timescale 1ns/1ps
module ir_arq_l2 #(
  parameter int DEFAULT_RETRY_TIMEOUT_CYCLES = 1024,
  parameter int DEFAULT_MAX_RETRY = 12
) (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        clear_sticky,
  input  logic        start,
  input  logic        stop,

  input  logic [7:0]  payload_lane_mask,
  input  logic [7:0]  ack_lane_mask,
  input  logic [7:0]  expected_ack_lane_mask,
  input  logic [15:0] session_id,
  input  logic [31:0] retry_timeout_cycles,
  input  logic [7:0]  max_retry,

  input  logic        ack_valid,
  input  logic [15:0] ack_session_id,
  input  logic [15:0] ack_sequence,
  input  logic [7:0]  ack_seen_lane_mask,
  input  logic        ack_complete,

  output logic        busy,
  output logic        tx_start_pulse,
  output logic        tx_done_pulse,
  output logic        tx_fail_pulse,
  output logic        ack_seen_pulse,
  output logic        retry_exhausted_sticky,
  output logic        ack_session_bad_pulse,
  output logic        ack_lane_mask_bad_pulse,
  output logic        ack_duplicate_pulse,
  output logic        ack_expired_pulse,
  output logic        ack_late_pulse,

  output logic [15:0] active_sequence,
  output logic [15:0] next_sequence,
  output logic [7:0]  retry_count,
  output logic [31:0] timeout_counter,
  output logic [31:0] tx_attempt_count,
  output logic [31:0] ack_seen_count,
  output logic [31:0] retry_exhausted_count,
  output logic [31:0] ack_timeout_count,
  output logic [31:0] ack_session_bad_count,
  output logic [31:0] ack_lane_mask_bad_count,
  output logic [31:0] ack_duplicate_count,
  output logic [31:0] ack_expired_count,
  output logic [31:0] ack_late_count,
  output logic [31:0] debug_status
);
  typedef enum logic [1:0] {
    S_IDLE,
    S_WAIT_ACK
  } state_t;

  state_t state;
  logic [15:0] last_acked_sequence;
  logic have_last_acked;
  logic [31:0] timeout_limit;
  logic [7:0] retry_limit;
  logic ack_session_ok;
  logic ack_sequence_ok;
  logic ack_duplicate;
  logic ack_lane_mask_ok;
  logic ack_accept;
  logic lane_config_ok;

  assign timeout_limit = (retry_timeout_cycles == 32'd0) ? DEFAULT_RETRY_TIMEOUT_CYCLES : retry_timeout_cycles;
  assign retry_limit = (max_retry == 8'd0) ? DEFAULT_MAX_RETRY : max_retry;
  assign ack_session_ok = (ack_session_id == session_id);
  assign ack_sequence_ok = (ack_sequence == active_sequence);
  assign ack_duplicate = have_last_acked && (ack_sequence == last_acked_sequence);
  assign ack_lane_mask_ok =
      ((ack_seen_lane_mask & ack_lane_mask) != 8'h00) &&
      ((ack_seen_lane_mask & expected_ack_lane_mask) == expected_ack_lane_mask);
  assign ack_accept = ack_valid && ack_complete && ack_session_ok && ack_sequence_ok && ack_lane_mask_ok;
  assign lane_config_ok = (payload_lane_mask != 8'h00) && (ack_lane_mask != 8'h00) && (expected_ack_lane_mask != 8'h00);
  assign debug_status = {
    busy,
    retry_exhausted_sticky,
    ack_accept,
    ack_session_ok,
    ack_sequence_ok,
    ack_lane_mask_ok,
    lane_config_ok,
    1'b0,
    retry_count,
    active_sequence[7:0],
    ack_seen_lane_mask
  };

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= S_IDLE;
      busy <= 1'b0;
      tx_start_pulse <= 1'b0;
      tx_done_pulse <= 1'b0;
      tx_fail_pulse <= 1'b0;
      ack_seen_pulse <= 1'b0;
      retry_exhausted_sticky <= 1'b0;
      ack_session_bad_pulse <= 1'b0;
      ack_lane_mask_bad_pulse <= 1'b0;
      ack_duplicate_pulse <= 1'b0;
      ack_expired_pulse <= 1'b0;
      ack_late_pulse <= 1'b0;
      active_sequence <= 16'd0;
      next_sequence <= 16'd0;
      last_acked_sequence <= 16'd0;
      have_last_acked <= 1'b0;
      retry_count <= 8'd0;
      timeout_counter <= 32'd0;
      tx_attempt_count <= 32'd0;
      ack_seen_count <= 32'd0;
      retry_exhausted_count <= 32'd0;
      ack_timeout_count <= 32'd0;
      ack_session_bad_count <= 32'd0;
      ack_lane_mask_bad_count <= 32'd0;
      ack_duplicate_count <= 32'd0;
      ack_expired_count <= 32'd0;
      ack_late_count <= 32'd0;
    end else begin
      tx_start_pulse <= 1'b0;
      tx_done_pulse <= 1'b0;
      tx_fail_pulse <= 1'b0;
      ack_seen_pulse <= 1'b0;
      ack_session_bad_pulse <= 1'b0;
      ack_lane_mask_bad_pulse <= 1'b0;
      ack_duplicate_pulse <= 1'b0;
      ack_expired_pulse <= 1'b0;
      ack_late_pulse <= 1'b0;

      if (clear_sticky) begin
        retry_exhausted_sticky <= 1'b0;
        retry_exhausted_count <= 32'd0;
        ack_timeout_count <= 32'd0;
        ack_session_bad_count <= 32'd0;
        ack_lane_mask_bad_count <= 32'd0;
        ack_duplicate_count <= 32'd0;
        ack_expired_count <= 32'd0;
        ack_late_count <= 32'd0;
      end

      if (ack_valid && !busy) begin
        ack_late_pulse <= 1'b1;
        ack_late_count <= ack_late_count + 1'b1;
        if (ack_session_ok && ack_duplicate) begin
          ack_duplicate_pulse <= 1'b1;
          ack_duplicate_count <= ack_duplicate_count + 1'b1;
        end
      end

      case (state)
        S_IDLE: begin
          busy <= 1'b0;
          timeout_counter <= 32'd0;
          retry_count <= 8'd0;
          if (start && lane_config_ok) begin
            state <= S_WAIT_ACK;
            busy <= 1'b1;
            active_sequence <= next_sequence;
            timeout_counter <= 32'd0;
            retry_count <= 8'd0;
            tx_start_pulse <= 1'b1;
            tx_attempt_count <= tx_attempt_count + 1'b1;
          end else if (start && !lane_config_ok) begin
            tx_fail_pulse <= 1'b1;
            ack_lane_mask_bad_pulse <= 1'b1;
            ack_lane_mask_bad_count <= ack_lane_mask_bad_count + 1'b1;
          end
        end

        S_WAIT_ACK: begin
          busy <= 1'b1;
          if (stop) begin
            state <= S_IDLE;
            busy <= 1'b0;
            tx_fail_pulse <= 1'b1;
          end else if (ack_valid) begin
            if (!ack_session_ok) begin
              ack_session_bad_pulse <= 1'b1;
              ack_session_bad_count <= ack_session_bad_count + 1'b1;
            end else if (ack_duplicate) begin
              ack_duplicate_pulse <= 1'b1;
              ack_duplicate_count <= ack_duplicate_count + 1'b1;
            end else if (!ack_sequence_ok) begin
              ack_expired_pulse <= 1'b1;
              ack_expired_count <= ack_expired_count + 1'b1;
            end else if (!ack_lane_mask_ok) begin
              ack_lane_mask_bad_pulse <= 1'b1;
              ack_lane_mask_bad_count <= ack_lane_mask_bad_count + 1'b1;
            end else if (ack_accept) begin
              ack_seen_pulse <= 1'b1;
              tx_done_pulse <= 1'b1;
              ack_seen_count <= ack_seen_count + 1'b1;
              last_acked_sequence <= active_sequence;
              have_last_acked <= 1'b1;
              next_sequence <= active_sequence + 1'b1;
              state <= S_IDLE;
              busy <= 1'b0;
              timeout_counter <= 32'd0;
            end
          end else if (timeout_counter >= timeout_limit - 1'b1) begin
            ack_timeout_count <= ack_timeout_count + 1'b1;
            timeout_counter <= 32'd0;
            if (retry_count >= retry_limit) begin
              retry_exhausted_sticky <= 1'b1;
              retry_exhausted_count <= retry_exhausted_count + 1'b1;
              tx_fail_pulse <= 1'b1;
              state <= S_IDLE;
              busy <= 1'b0;
            end else begin
              retry_count <= retry_count + 1'b1;
              tx_start_pulse <= 1'b1;
              tx_attempt_count <= tx_attempt_count + 1'b1;
            end
          end else begin
            timeout_counter <= timeout_counter + 1'b1;
          end
        end

        default: begin
          state <= S_IDLE;
          busy <= 1'b0;
        end
      endcase
    end
  end
endmodule
