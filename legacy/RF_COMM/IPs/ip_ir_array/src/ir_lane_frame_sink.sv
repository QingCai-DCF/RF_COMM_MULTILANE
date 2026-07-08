module ir_lane_frame_sink #(
  parameter int MAX_FRAME_BYTES = 64
)(
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic [7:0]                   s_axis_tdata,
  input  logic                         s_axis_tvalid,
  output logic                         s_axis_tready,
  input  logic                         s_axis_tlast,
  output logic                         frame_valid,
  input  logic                         frame_ready,
  output logic [8*MAX_FRAME_BYTES-1:0] frame_data,
  output logic [15:0]                  frame_len,
  output logic                         overflow_error
);
  logic [15:0] wr_ptr;
  logic        drop_mode;
  logic [8*MAX_FRAME_BYTES-1:0] frame_data_insert;
  integer insert_i;

  assign s_axis_tready = !frame_valid;

  always_comb begin
    frame_data_insert = frame_data;
    for (insert_i = 0; insert_i < MAX_FRAME_BYTES; insert_i = insert_i + 1) begin
      if (wr_ptr == insert_i) frame_data_insert[8*insert_i +: 8] = s_axis_tdata;
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      frame_valid     <= 1'b0;
      frame_len       <= '0;
      wr_ptr          <= '0;
      overflow_error  <= 1'b0;
      drop_mode       <= 1'b0;
    end else begin
      overflow_error <= 1'b0;

      if (frame_valid && frame_ready) begin
        frame_valid <= 1'b0;
        frame_len   <= '0;
        wr_ptr      <= '0;
      end

      if (s_axis_tvalid && s_axis_tready) begin
        if (drop_mode) begin
          if (s_axis_tlast) begin
            drop_mode <= 1'b0;
            wr_ptr    <= '0;
          end
        end else if (wr_ptr < MAX_FRAME_BYTES) begin
          frame_data <= frame_data_insert;
          if (s_axis_tlast) begin
            frame_len   <= wr_ptr + 1'b1;
            frame_valid <= 1'b1;
            wr_ptr      <= '0;
          end else begin
            wr_ptr      <= wr_ptr + 1'b1;
          end
        end else begin
          overflow_error <= 1'b1;
          drop_mode      <= 1'b1;
          if (s_axis_tlast) begin
            drop_mode <= 1'b0;
            wr_ptr    <= '0;
          end
        end
      end
    end
  end
endmodule
