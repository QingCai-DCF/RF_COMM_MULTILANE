module ir_comm_lane #(
  parameter int MAX_FRAME_BYTES  = 64,
  parameter int CNT_CHIP_MAX     = 7,
  parameter int CNT_PREAMBLE     = 16,
  parameter int EOF_SILENCE_SYMS = 3
)(
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         enable,
  input  logic                         load_frame,
  input  logic [8*MAX_FRAME_BYTES-1:0] frame_data,
  input  logic [15:0]                  frame_len,
  output logic                         load_ready,
  output logic                         lane_tx_busy,
  output logic                         rx_frame_valid,
  input  logic                         rx_frame_ready,
  output logic [8*MAX_FRAME_BYTES-1:0] rx_frame_data,
  output logic [15:0]                  rx_frame_len,
  output logic                         rx_frame_overflow,
  output logic                         rx_crc_error,
  output logic                         rx_overrun_error,
  output logic                         ir_tx_out,
  input  logic                         ir_rx_in,
  output logic                         ir_sd,
  output logic                         ir_mode_out
);
  logic [7:0] tx_axis_tdata;
  logic       tx_axis_tvalid;
  logic       tx_axis_tready;
  logic       tx_axis_tlast;
  logic [7:0] rx_axis_tdata;
  logic       rx_axis_tvalid;
  logic       rx_axis_tready;
  logic       rx_axis_tlast;
  logic       tx_busy;
  logic       src_busy;
  logic       rx_in_masked;

  assign lane_tx_busy = tx_busy || src_busy;
  assign rx_in_masked = ir_tx_out ? 1'b1 : ir_rx_in;
  assign ir_sd        = ~enable;
  assign ir_mode_out  = 1'b1;

  ir_lane_frame_source #(
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
  ) u_src (
    .clk          (clk),
    .rst_n        (rst_n),
    .load         (load_frame),
    .frame_data   (frame_data),
    .frame_len    (frame_len),
    .load_ready   (load_ready),
    .busy         (src_busy),
    .m_axis_tdata (tx_axis_tdata),
    .m_axis_tvalid(tx_axis_tvalid),
    .m_axis_tready(tx_axis_tready),
    .m_axis_tlast (tx_axis_tlast)
  );

  ir_tx_4ppm_frame #(
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(CNT_PREAMBLE),
    .CNT_EOF_SILENCE(EOF_SILENCE_SYMS + 4)
  ) u_tx (
    .clk         (clk),
    .rst_n       (rst_n),
    .enable      (enable),
    .s_axis_tdata(tx_axis_tdata),
    .s_axis_tvalid(tx_axis_tvalid),
    .s_axis_tready(tx_axis_tready),
    .s_axis_tlast(tx_axis_tlast),
    .tx_busy     (tx_busy),
    .ir_tx_out   (ir_tx_out)
  );

  ir_rx_4ppm_frame #(
    .MAX_FRAME_BYTES (MAX_FRAME_BYTES),
    .CNT_CHIP_MAX    (CNT_CHIP_MAX),
    .PREAMBLE_SYMS   (CNT_PREAMBLE),
    .EOF_SILENCE_SYMS(EOF_SILENCE_SYMS)
  ) u_rx (
    .clk           (clk),
    .rst_n         (rst_n),
    .enable        (enable),
    .ir_rx_in      (rx_in_masked),
    .m_axis_tdata  (rx_axis_tdata),
    .m_axis_tvalid (rx_axis_tvalid),
    .m_axis_tready (rx_axis_tready),
    .m_axis_tlast  (rx_axis_tlast),
    .rx_active     (),
    .crc_error     (rx_crc_error),
    .overrun_error (rx_overrun_error)
  );

  ir_lane_frame_sink #(
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
  ) u_sink (
    .clk           (clk),
    .rst_n         (rst_n),
    .s_axis_tdata  (rx_axis_tdata),
    .s_axis_tvalid (rx_axis_tvalid),
    .s_axis_tready (rx_axis_tready),
    .s_axis_tlast  (rx_axis_tlast),
    .frame_valid   (rx_frame_valid),
    .frame_ready   (rx_frame_ready),
    .frame_data    (rx_frame_data),
    .frame_len     (rx_frame_len),
    .overflow_error(rx_frame_overflow)
  );
endmodule
