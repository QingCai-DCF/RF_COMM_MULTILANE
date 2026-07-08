module ir_axis_async_fifo #(
  parameter int DATA_W = 8,
  parameter int DEPTH  = 1024
)(
  input  logic              rst,
  input  logic              s_clk,
  input  logic [DATA_W-1:0] s_tdata,
  input  logic              s_tvalid,
  output logic              s_tready,
  input  logic              s_tlast,
  input  logic              m_clk,
  output logic [DATA_W-1:0] m_tdata,
  output logic              m_tvalid,
  input  logic              m_tready,
  output logic              m_tlast
);
  localparam int FIFO_W = DATA_W + 1;
  localparam int CNT_W  = (DEPTH <= 2) ? 2 : $clog2(DEPTH) + 1;

  logic [FIFO_W-1:0] din;
  logic [FIFO_W-1:0] dout;
  logic full;
  logic empty;
  logic wr_en;
  logic rd_en;
  logic wr_rst_busy;
  logic rd_rst_busy;

  assign din      = {s_tlast, s_tdata};
  assign wr_en    = s_tvalid && s_tready;
  assign rd_en    = m_tvalid && m_tready;
  assign s_tready = !full && !wr_rst_busy;
  assign m_tvalid = !empty && !rd_rst_busy;
  assign m_tdata  = dout[DATA_W-1:0];
  assign m_tlast  = dout[FIFO_W-1];

  xpm_fifo_async #(
    .FIFO_MEMORY_TYPE   ("auto"),
    .ECC_MODE           ("no_ecc"),
    .RELATED_CLOCKS     (0),
    .FIFO_WRITE_DEPTH   (DEPTH),
    .WRITE_DATA_WIDTH   (FIFO_W),
    .WR_DATA_COUNT_WIDTH(CNT_W),
    .PROG_FULL_THRESH   (10),
    .FULL_RESET_VALUE   (0),
    .READ_MODE          ("fwft"),
    .FIFO_READ_LATENCY  (0),
    .READ_DATA_WIDTH    (FIFO_W),
    .RD_DATA_COUNT_WIDTH(CNT_W),
    .PROG_EMPTY_THRESH  (10),
    .DOUT_RESET_VALUE   ("0"),
    .CDC_SYNC_STAGES    (2),
    .WAKEUP_TIME        (0),
    .USE_ADV_FEATURES   ("0000")
  ) u_fifo (
    .sleep         (1'b0),
    .rst           (rst),
    .wr_clk        (s_clk),
    .wr_en         (wr_en),
    .din           (din),
    .full          (full),
    .overflow      (),
    .wr_rst_busy   (wr_rst_busy),
    .rd_clk        (m_clk),
    .rd_en         (rd_en),
    .dout          (dout),
    .empty         (empty),
    .underflow     (),
    .rd_rst_busy   (rd_rst_busy),
    .prog_full     (),
    .prog_empty    (),
    .almost_full   (),
    .almost_empty  (),
    .data_valid    (),
    .dbiterr       (),
    .sbiterr       (),
    .wr_ack        (),
    .wr_data_count (),
    .rd_data_count (),
    .injectdbiterr (1'b0),
    .injectsbiterr (1'b0)
  );
endmodule
