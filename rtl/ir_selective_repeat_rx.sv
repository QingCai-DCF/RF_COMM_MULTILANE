`timescale 1ns/1ps
// P8E bounded RX reorder window with a registered presence/SACK bitmap.
module ir_selective_repeat_rx #(
  parameter int WINDOW_SIZE = 64,
  parameter int SACK_BITS = 64,
  parameter int PAYLOAD_REF_WIDTH = 16,
  parameter int ACCEPT_PREVIOUS_PATH_EPOCHS = 1
) (
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         clear_counters_i,
  input  logic                         session_reset_i,
  input  logic [31:0]                  session_epoch_i,
  input  logic [15:0]                  current_path_epoch_i,
  input  logic                         rx_valid_i,
  output logic                         rx_ready_o,
  input  logic                         rx_l1_valid_i,
  input  logic [31:0]                  rx_session_epoch_i,
  input  logic [15:0]                  rx_sequence_i,
  input  logic [15:0]                  rx_path_epoch_i,
  input  logic [PAYLOAD_REF_WIDTH-1:0] rx_payload_ref_i,
  input  logic [15:0]                  rx_payload_length_i,
  output logic                         rx_accept_pulse_o,
  output logic                         delivery_valid_o,
  input  logic                         delivery_ready_i,
  output logic [15:0]                  delivery_sequence_o,
  output logic [PAYLOAD_REF_WIDTH-1:0] delivery_payload_ref_o,
  output logic [15:0]                  delivery_payload_length_o,
  output logic [15:0]                  rx_base_sequence_o,
  output logic [SACK_BITS-1:0]         sack_bitmap_o,
  output logic [$clog2(WINDOW_SIZE+1)-1:0] receiver_credit_o,
  output logic [31:0]                  out_of_order_count_o,
  output logic [31:0]                  duplicate_count_o,
  output logic [31:0]                  old_count_o,
  output logic [31:0]                  future_count_o,
  output logic [31:0]                  stale_session_count_o,
  output logic [31:0]                  stale_path_epoch_count_o,
  output logic [31:0]                  gap_count_o,
  output logic [31:0]                  delivery_count_o,
  output logic [31:0]                  protocol_error_count_o
);
  import ir_seq_math_pkg::*;
  localparam int INDEX_WIDTH = $clog2(WINDOW_SIZE);
  localparam int COUNT_WIDTH = $clog2(WINDOW_SIZE + 1);
  localparam int META_WIDTH = 16 + PAYLOAD_REF_WIDTH + 16;

  logic [WINDOW_SIZE-1:0] entry_valid;
  (* ram_style="distributed" *) logic [META_WIDTH-1:0] entry_metadata [0:WINDOW_SIZE-1];
  logic [META_WIDTH-1:0] delivery_metadata;
  logic [15:0] delivery_stored_sequence;
  logic [COUNT_WIDTH-1:0] occupancy;
  logic [15:0] receive_distance;
  logic [15:0] path_age;
  logic receive_path_valid;
  logic [INDEX_WIDTH-1:0] receive_index;
  logic [INDEX_WIDTH-1:0] delivery_index;

  // A synchronous command stage isolates the RAM write enable from every
  // asynchronously asserted metadata reset.  The input is stalled for this
  // single commit cycle, giving deterministic reset/abort ownership semantics.
  logic metadata_commit_pending;
  logic [INDEX_WIDTH-1:0] metadata_commit_index;
  logic [15:0] metadata_commit_sequence;
  logic [PAYLOAD_REF_WIDTH-1:0] metadata_commit_payload_ref;
  logic [15:0] metadata_commit_payload_length;

  initial begin
    if (WINDOW_SIZE < 32 || (WINDOW_SIZE & (WINDOW_SIZE-1)) != 0)
      $error("RX WINDOW_SIZE must be power-of-two and at least 32");
    if (SACK_BITS < 32 || SACK_BITS > WINDOW_SIZE)
      $error("RX SACK_BITS must be 32..WINDOW_SIZE");
  end

  assign receive_distance = seq_distance(rx_sequence_i, rx_base_sequence_o);
  assign path_age = current_path_epoch_i - rx_path_epoch_i;
  assign receive_path_valid = (path_age <= ACCEPT_PREVIOUS_PATH_EPOCHS);
  assign receive_index = rx_sequence_i[INDEX_WIDTH-1:0];
  assign delivery_index = rx_base_sequence_o[INDEX_WIDTH-1:0];
  assign rx_ready_o = (occupancy < WINDOW_SIZE) && !metadata_commit_pending;
  assign receiver_credit_o = WINDOW_SIZE - occupancy;
  assign delivery_metadata = entry_metadata[delivery_index];
  assign delivery_stored_sequence = delivery_metadata[META_WIDTH-1 -: 16];
  assign delivery_valid_o = entry_valid[delivery_index] &&
                            delivery_stored_sequence == rx_base_sequence_o;
  assign delivery_sequence_o = rx_base_sequence_o;
  assign delivery_payload_ref_o = delivery_metadata[16 +: PAYLOAD_REF_WIDTH];
  assign delivery_payload_length_o = delivery_metadata[15:0];

  always_ff @(posedge clk) begin : reorder_metadata_memory
    if (!rst_n || session_reset_i) begin
      metadata_commit_pending <= 1'b0;
      metadata_commit_index <= '0;
      metadata_commit_sequence <= 16'd0;
      metadata_commit_payload_ref <= '0;
      metadata_commit_payload_length <= 16'd0;
    end else begin
      if (metadata_commit_pending)
        entry_metadata[metadata_commit_index] <=
            {metadata_commit_sequence, metadata_commit_payload_ref,
             metadata_commit_payload_length};
      metadata_commit_pending <= 1'b0;
      if (rx_valid_i && rx_ready_o && rx_l1_valid_i &&
          rx_session_epoch_i == session_epoch_i && receive_path_valid &&
          receive_distance < WINDOW_SIZE && !entry_valid[receive_index]) begin
        metadata_commit_pending <= 1'b1;
        metadata_commit_index <= receive_index;
        metadata_commit_sequence <= rx_sequence_i;
        metadata_commit_payload_ref <= rx_payload_ref_i;
        metadata_commit_payload_length <= rx_payload_length_i;
      end
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin : rx_state
    integer signed occupancy_delta;
    logic [SACK_BITS-1:0] sack_next;
    logic delivery_fire;
    logic [15:0] commit_base;
    logic [15:0] commit_distance;
    if (!rst_n) begin
      entry_valid <= '0;
      rx_base_sequence_o <= 16'd0;
      sack_bitmap_o <= '0;
      occupancy <= '0;
      rx_accept_pulse_o <= 1'b0;
      out_of_order_count_o <= 32'd0;
      duplicate_count_o <= 32'd0;
      old_count_o <= 32'd0;
      future_count_o <= 32'd0;
      stale_session_count_o <= 32'd0;
      stale_path_epoch_count_o <= 32'd0;
      gap_count_o <= 32'd0;
      delivery_count_o <= 32'd0;
      protocol_error_count_o <= 32'd0;
    end else begin
      rx_accept_pulse_o <= 1'b0;
      occupancy_delta = 0;
      sack_next = sack_bitmap_o;
      delivery_fire = delivery_valid_o && delivery_ready_i;

      if (clear_counters_i) begin
        out_of_order_count_o <= 32'd0;
        duplicate_count_o <= 32'd0;
        old_count_o <= 32'd0;
        future_count_o <= 32'd0;
        stale_session_count_o <= 32'd0;
        stale_path_epoch_count_o <= 32'd0;
        gap_count_o <= 32'd0;
        delivery_count_o <= 32'd0;
        protocol_error_count_o <= 32'd0;
      end

      if (session_reset_i) begin
        entry_valid <= '0;
        rx_base_sequence_o <= 16'd0;
        sack_bitmap_o <= '0;
        occupancy <= '0;
      end else begin
        if (delivery_fire) begin
          entry_valid[delivery_index] <= 1'b0;
          rx_base_sequence_o <= rx_base_sequence_o + 1'b1;
          sack_next = sack_next >> 1;
          delivery_count_o <= delivery_count_o + 1'b1;
          occupancy_delta = occupancy_delta - 1;
        end

        if (metadata_commit_pending) begin
          commit_base = delivery_fire ? rx_base_sequence_o + 1'b1 : rx_base_sequence_o;
          commit_distance = seq_distance(metadata_commit_sequence, commit_base);
          entry_valid[metadata_commit_index] <= 1'b1;
          if (commit_distance < SACK_BITS)
            sack_next[commit_distance[$clog2(SACK_BITS)-1:0]] = 1'b1;
          occupancy_delta = occupancy_delta + 1;
        end

        if (rx_valid_i && rx_ready_o) begin
          if (!rx_l1_valid_i) begin
            protocol_error_count_o <= protocol_error_count_o + 1'b1;
          end else if (rx_session_epoch_i != session_epoch_i) begin
            stale_session_count_o <= stale_session_count_o + 1'b1;
          end else if (!receive_path_valid) begin
            stale_path_epoch_count_o <= stale_path_epoch_count_o + 1'b1;
          end else if (receive_distance >= 16'h8000) begin
            old_count_o <= old_count_o + 1'b1;
            duplicate_count_o <= duplicate_count_o + 1'b1;
          end else if (receive_distance >= WINDOW_SIZE) begin
            future_count_o <= future_count_o + 1'b1;
          end else if (entry_valid[receive_index]) begin
            if (entry_metadata[receive_index][META_WIDTH-1 -: 16] == rx_sequence_i) begin
              duplicate_count_o <= duplicate_count_o + 1'b1;
              if (entry_metadata[receive_index][16 +: PAYLOAD_REF_WIDTH] != rx_payload_ref_i ||
                  entry_metadata[receive_index][15:0] != rx_payload_length_i)
                protocol_error_count_o <= protocol_error_count_o + 1'b1;
            end else begin
              protocol_error_count_o <= protocol_error_count_o + 1'b1;
            end
          end else begin
            rx_accept_pulse_o <= 1'b1;
            if (receive_distance != 0) begin
              out_of_order_count_o <= out_of_order_count_o + 1'b1;
              gap_count_o <= gap_count_o + 1'b1;
            end
          end
        end

        sack_bitmap_o <= sack_next;
        if (occupancy_delta != 0)
          occupancy <= occupancy + occupancy_delta;
      end
    end
  end
endmodule
