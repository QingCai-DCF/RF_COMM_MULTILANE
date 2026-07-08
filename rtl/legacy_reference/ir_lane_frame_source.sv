module ir_lane_frame_source #(
  parameter int MAX_FRAME_BYTES = 64
)(
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         load,
  input  logic [8*MAX_FRAME_BYTES-1:0] frame_data,
  input  logic [15:0]                  frame_len,
  output logic                         load_ready,
  output logic                         busy,
  output logic [7:0]                   m_axis_tdata,
  output logic                         m_axis_tvalid,
  input  logic                         m_axis_tready,
  output logic                         m_axis_tlast
);
  logic [8*MAX_FRAME_BYTES-1:0] frame_reg;
  logic [15:0] frame_len_reg;
  logic [15:0] rd_ptr;
  logic        handshake;

  assign load_ready    = !busy;
  assign m_axis_tvalid = busy && (rd_ptr < frame_len_reg);
  assign m_axis_tdata  = frame_reg[8*rd_ptr +: 8];
  assign m_axis_tlast  = m_axis_tvalid && (rd_ptr == frame_len_reg - 1'b1);
  assign handshake     = m_axis_tvalid && m_axis_tready;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      frame_len_reg <= '0;
      rd_ptr        <= '0;
      busy          <= 1'b0;
    end else begin
      if (load && !busy) begin
        frame_reg     <= frame_data;
        frame_len_reg <= frame_len;
        rd_ptr        <= '0;
        busy          <= (frame_len != 0);
      end else if (handshake) begin
        if (rd_ptr == frame_len_reg - 1'b1) begin
          rd_ptr <= '0;
          busy   <= 1'b0;
        end else begin
          rd_ptr <= rd_ptr + 1'b1;
        end
      end
    end
  end
endmodule
