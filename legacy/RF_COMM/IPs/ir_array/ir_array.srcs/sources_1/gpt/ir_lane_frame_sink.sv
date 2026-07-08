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

  assign s_axis_tready = !frame_valid;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      frame_valid     <= 1'b0;
      frame_data      <= '0;
      frame_len       <= '0;
      wr_ptr          <= '0;
      overflow_error  <= 1'b0;
    end else begin
      if (frame_valid && frame_ready) begin
        frame_valid <= 1'b0;
        frame_len   <= '0;
        wr_ptr      <= '0;
      end

      if (s_axis_tvalid && s_axis_tready) begin
        if (wr_ptr < MAX_FRAME_BYTES) begin
          frame_data[8*wr_ptr +: 8] <= s_axis_tdata;
          if (s_axis_tlast) begin
            frame_len   <= wr_ptr + 1'b1;
            frame_valid <= 1'b1;
            wr_ptr      <= '0;
          end else begin
            wr_ptr      <= wr_ptr + 1'b1;
          end
        end else begin
          overflow_error <= 1'b1;
          if (s_axis_tlast) wr_ptr <= '0;
        end
      end
    end
  end
endmodule
