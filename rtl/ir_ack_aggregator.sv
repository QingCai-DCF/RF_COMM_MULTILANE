`timescale 1ns/1ps
module ir_ack_aggregator #(
  parameter int SACK_BITS = 64,
  parameter int FRAME_THRESHOLD = 8,
  parameter int MAX_DELAY_CYCLES = 32000,
  parameter int CREDIT_LOW_WATERMARK = 8
) (
  input  logic                       clk,
  input  logic                       rst_n,
  input  logic                       clear_counters_i,
  input  logic                       rx_accept_i,
  input  logic [31:0]                session_epoch_i,
  input  logic [15:0]                ack_base_i,
  input  logic [SACK_BITS-1:0]       sack_bitmap_i,
  input  logic [$clog2(SACK_BITS):0] sack_width_i,
  input  logic [15:0]                receiver_credit_i,
  input  logic                       gap_blocked_i,
  input  logic                       control_event_i,
  input  logic                       direction_boundary_i,
  input  logic                       explicit_request_i,
  output logic                       ack_valid_o,
  input  logic                       ack_ready_i,
  output logic [31:0]                ack_session_epoch_o,
  output logic [15:0]                ack_base_o,
  output logic [SACK_BITS-1:0]       ack_bitmap_o,
  output logic [$clog2(SACK_BITS):0] ack_width_o,
  output logic [15:0]                ack_receiver_credit_o,
  output logic [31:0]                aggregation_count_o,
  output logic [31:0]                timer_expiry_count_o,
  output logic [31:0]                ack_frames_sent_o
);
  localparam int FRAME_COUNT_WIDTH = $clog2(FRAME_THRESHOLD + 2);
  logic [FRAME_COUNT_WIDTH-1:0] pending_frames;
  logic [31:0] delay_counter;
  logic trigger_now;
  logic timer_trigger;

  always_comb begin
    timer_trigger = (pending_frames != 0) &&
                    (delay_counter >= MAX_DELAY_CYCLES - 1);
    trigger_now = ((pending_frames >= FRAME_THRESHOLD) || timer_trigger ||
                   ((pending_frames != 0) &&
                    (receiver_credit_i <= CREDIT_LOW_WATERMARK)) ||
                   ((pending_frames != 0) && gap_blocked_i) ||
                   ((pending_frames != 0) && control_event_i) ||
                   ((pending_frames != 0) && direction_boundary_i) ||
                   ((pending_frames != 0) && explicit_request_i));
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pending_frames <= '0;
      delay_counter <= 32'd0;
      ack_valid_o <= 1'b0;
      ack_session_epoch_o <= 32'd0;
      ack_base_o <= 16'd0;
      ack_bitmap_o <= '0;
      ack_width_o <= '0;
      ack_receiver_credit_o <= 16'd0;
      aggregation_count_o <= 32'd0;
      timer_expiry_count_o <= 32'd0;
      ack_frames_sent_o <= 32'd0;
    end else begin
      if (clear_counters_i) begin
        aggregation_count_o <= 32'd0;
        timer_expiry_count_o <= 32'd0;
        ack_frames_sent_o <= 32'd0;
      end
      if (ack_valid_o && ack_ready_i) begin
        ack_valid_o <= 1'b0;
        pending_frames <= '0;
        delay_counter <= 32'd0;
        ack_frames_sent_o <= ack_frames_sent_o + 1'b1;
      end else begin
        if (rx_accept_i) begin
          if (pending_frames < FRAME_THRESHOLD + 1) begin
            pending_frames <= pending_frames + 1'b1;
          end
          aggregation_count_o <= aggregation_count_o + 1'b1;
        end
        if (pending_frames != 0 && !ack_valid_o) begin
          delay_counter <= delay_counter + 1'b1;
        end
        if (!ack_valid_o && trigger_now) begin
          ack_valid_o <= 1'b1;
          ack_session_epoch_o <= session_epoch_i;
          ack_base_o <= ack_base_i;
          ack_bitmap_o <= sack_bitmap_i;
          ack_width_o <= sack_width_i;
          ack_receiver_credit_o <= receiver_credit_i;
          if (timer_trigger) timer_expiry_count_o <= timer_expiry_count_o + 1'b1;
        end
      end
    end
  end
endmodule
