`timescale 1ns/1ps
module ir_ack_aggregator #(
  parameter int SACK_BITS = 64,
  parameter int FRAME_THRESHOLD = 8,
  parameter int MAX_DELAY_CYCLES = 32000,
  parameter int CREDIT_LOW_WATERMARK = 8,
  parameter bit P10_5_PIGGYBACK_CAPABLE = 1'b0
) (
  input  logic                       clk,
  input  logic                       rst_n,
  input  logic                       clear_counters_i,
  input  logic                       state_reset_i,
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
  input  logic                       piggyback_commit_i,
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
  wire effective_piggyback_commit = P10_5_PIGGYBACK_CAPABLE &&
      piggyback_commit_i;

  always_comb begin
    timer_trigger = (pending_frames != 0) &&
                    (delay_counter >= MAX_DELAY_CYCLES - 1);
    // A control or direction-boundary event may represent a retransmitted
    // frame after the previous ACK was lost.  In that case there need not be
    // a newly accepted reorder entry, but the current cumulative ACK/SACK
    // state still has to be emitted to make ACK loss recoverable.
    trigger_now = ((pending_frames >= FRAME_THRESHOLD) || timer_trigger ||
                   ((pending_frames != 0) &&
                    (receiver_credit_i <= CREDIT_LOW_WATERMARK)) ||
                   ((pending_frames != 0) && gap_blocked_i) ||
                   control_event_i || direction_boundary_i ||
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
      if (state_reset_i) begin
        // Session/object ownership changes invalidate every unsent ACK
        // snapshot and pending aggregation event. Telemetry counters remain
        // independently controlled by clear_counters_i.
        pending_frames <= '0;
        delay_counter <= 32'd0;
        ack_valid_o <= 1'b0;
        ack_session_epoch_o <= 32'd0;
        ack_base_o <= 16'd0;
        ack_bitmap_o <= '0;
        ack_width_o <= '0;
        ack_receiver_credit_o <= 16'd0;
      end else begin
        if (clear_counters_i) begin
          aggregation_count_o <= 32'd0;
          timer_expiry_count_o <= 32'd0;
          ack_frames_sent_o <= 32'd0;
        end
        if (effective_piggyback_commit) begin
          // A P10.5 piggyback snapshots the live cumulative ACK/SACK/credit
          // state at DATA-frame admission. It therefore covers every event
          // accumulated before this edge, including an older presented
          // control-only snapshot. Retaining those events would emit a
          // redundant control ACK after nearly every piggyback and repeatedly
          // interrupt the simultaneous opposite-direction DATA carrier. Only
          // a receive/control event on this same edge is newer than the
          // piggyback snapshot and must remain pending.
          ack_valid_o <= 1'b0;
          pending_frames <= (rx_accept_i || control_event_i ||
                             direction_boundary_i) ?
              {{(FRAME_COUNT_WIDTH-1){1'b0}}, 1'b1} : '0;
          if (rx_accept_i)
            aggregation_count_o <= aggregation_count_o + 1'b1;
          delay_counter <= 32'd0;
          ack_frames_sent_o <= ack_frames_sent_o + 1'b1;
        end else if (ack_valid_o && ack_ready_i) begin
          ack_valid_o <= 1'b0;
          // pending_frames counts receive/control events that occurred after
          // the currently presented immutable ACK snapshot. They must survive
          // this handshake so a following cumulative ACK can cover them.
          if (rx_accept_i) begin
            if (pending_frames < FRAME_THRESHOLD + 1)
              pending_frames <= pending_frames + 1'b1;
            aggregation_count_o <= aggregation_count_o + 1'b1;
          end
          if ((control_event_i || direction_boundary_i) &&
              pending_frames == 0 && !rx_accept_i)
            pending_frames <= {{(FRAME_COUNT_WIDTH-1){1'b0}}, 1'b1};
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
          if (ack_valid_o && (control_event_i || direction_boundary_i) &&
              pending_frames == 0 && !rx_accept_i)
            pending_frames <= {{(FRAME_COUNT_WIDTH-1){1'b0}}, 1'b1};
          if (!ack_valid_o && trigger_now) begin
            ack_valid_o <= 1'b1;
            ack_session_epoch_o <= session_epoch_i;
            ack_base_o <= ack_base_i;
            ack_bitmap_o <= sack_bitmap_i;
            ack_width_o <= sack_width_i;
            ack_receiver_credit_o <= receiver_credit_i;
            // All events accumulated so far are represented by this frozen
            // snapshot. New events arriving while VALID waits for READY are
            // accumulated independently above.
            pending_frames <= '0;
            delay_counter <= 32'd0;
            if (timer_trigger) timer_expiry_count_o <= timer_expiry_count_o + 1'b1;
          end
        end
      end
    end
  end
endmodule
