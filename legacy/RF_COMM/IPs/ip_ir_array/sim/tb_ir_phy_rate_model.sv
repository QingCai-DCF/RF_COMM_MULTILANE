module tb_ir_phy_rate_model;
  localparam int CNT_CHIP_MAX     = 7;
  localparam int CNT_PREAMBLE     = 16;
  localparam int PREAMBLE_GAP_SYMS = 1;
  localparam int EOF_SILENCE_SYMS = 3;
  localparam int FRAME_BYTES      = 30;
  localparam int HALF_DUPLEX_LANES = 8;
  localparam int FDX_LANES_PER_DIR = 4;

  localparam real CLK_FREQ_HZ       = 64_000_000.0;
  localparam real CLK_PERIOD_NS     = 1_000_000_000.0 / CLK_FREQ_HZ;
  localparam int  CHIP_CYCLES       = CNT_CHIP_MAX + 1;
  localparam int  CHIPS_PER_SYMBOL  = 4;
  localparam int  BITS_PER_SYMBOL   = 2;
  localparam int  DATA_SYMBOLS      = FRAME_BYTES * 4;
  localparam int  CRC_SYMBOLS       = 16;
  localparam int  TOTAL_SYMBOLS     = CNT_PREAMBLE + PREAMBLE_GAP_SYMS + DATA_SYMBOLS + CRC_SYMBOLS + EOF_SILENCE_SYMS;
  localparam int  TOTAL_PHY_CYCLES  = TOTAL_SYMBOLS * CHIPS_PER_SYMBOL * CHIP_CYCLES;
  localparam real RAW_PHY_MBPS      = (BITS_PER_SYMBOL * CLK_FREQ_HZ) /
                                      (CHIPS_PER_SYMBOL * CHIP_CYCLES * 1_000_000.0);
  localparam real HALF_DUPLEX_RAW_MBPS = RAW_PHY_MBPS * HALF_DUPLEX_LANES;
  localparam real FDX_PER_DIR_RAW_MBPS = RAW_PHY_MBPS * FDX_LANES_PER_DIR;
  localparam real FRAME_AIRTIME_US  = (TOTAL_PHY_CYCLES * CLK_PERIOD_NS) / 1000.0;

  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic enable = 1'b1;
  logic [7:0] s_axis_tdata;
  logic s_axis_tvalid;
  logic s_axis_tready;
  logic s_axis_tlast;
  logic tx_busy;
  logic ir_tx_out;

  longint unsigned cycle_count;
  longint unsigned busy_start_cycle;
  longint unsigned busy_end_cycle;
  longint unsigned busy_cycles;
  int sent_bytes;
  bit tx_busy_q;
  bit saw_busy_start;
  bit saw_busy_end;

  always #(CLK_PERIOD_NS / 2.0) clk = ~clk;

  ir_tx_4ppm_frame #(
    .CNT_CHIP_MAX    (CNT_CHIP_MAX),
    .CNT_PREAMBLE    (CNT_PREAMBLE),
    .CNT_EOF_SILENCE (EOF_SILENCE_SYMS)
  ) u_tx (
    .clk           (clk),
    .rst_n         (rst_n),
    .enable        (enable),
    .s_axis_tdata  (s_axis_tdata),
    .s_axis_tvalid (s_axis_tvalid),
    .s_axis_tready (s_axis_tready),
    .s_axis_tlast  (s_axis_tlast),
    .tx_busy       (tx_busy),
    .ir_tx_out     (ir_tx_out)
  );

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      cycle_count      <= '0;
      tx_busy_q        <= 1'b0;
      saw_busy_start   <= 1'b0;
      saw_busy_end     <= 1'b0;
      busy_start_cycle <= '0;
      busy_end_cycle   <= '0;
    end else begin
      cycle_count <= cycle_count + 1'b1;
      tx_busy_q   <= tx_busy;
      if (!tx_busy_q && tx_busy) begin
        saw_busy_start   <= 1'b1;
        busy_start_cycle <= cycle_count;
      end
      if (tx_busy_q && !tx_busy) begin
        saw_busy_end   <= 1'b1;
        busy_end_cycle <= cycle_count;
      end
    end
  end

  initial begin
    s_axis_tdata  = 8'h00;
    s_axis_tvalid = 1'b0;
    s_axis_tlast  = 1'b0;
    sent_bytes    = 0;

    repeat (8) @(posedge clk);
    rst_n = 1'b1;
    repeat (4) @(posedge clk);

    while (sent_bytes < FRAME_BYTES) begin
      @(negedge clk);
      s_axis_tvalid = 1'b1;
      s_axis_tdata  = 8'h30 + sent_bytes[7:0];
      s_axis_tlast  = (sent_bytes == FRAME_BYTES - 1);
      @(posedge clk);
      if (s_axis_tready) sent_bytes++;
    end

    @(negedge clk);
    s_axis_tvalid = 1'b0;
    s_axis_tlast  = 1'b0;

    wait (saw_busy_end);
    repeat (4) @(posedge clk);
    busy_cycles = busy_end_cycle - busy_start_cycle;

    if ((RAW_PHY_MBPS < 3.999) || (RAW_PHY_MBPS > 4.001)) begin
      $error("Raw PHY rate outside 4 Mbit/s target: %0.6f Mbit/s", RAW_PHY_MBPS);
      $finish;
    end
    if ((HALF_DUPLEX_RAW_MBPS < 31.999) || (HALF_DUPLEX_RAW_MBPS > 32.001)) begin
      $error("Eight-lane half-duplex raw PHY rate outside 32 Mbit/s target: %0.6f Mbit/s",
             HALF_DUPLEX_RAW_MBPS);
      $finish;
    end
    if ((FDX_PER_DIR_RAW_MBPS < 15.999) || (FDX_PER_DIR_RAW_MBPS > 16.001)) begin
      $error("4+4 lane full-duplex per-direction raw PHY rate outside 16 Mbit/s target: %0.6f Mbit/s",
             FDX_PER_DIR_RAW_MBPS);
      $finish;
    end
    if ((busy_cycles < (TOTAL_PHY_CYCLES - 4)) || (busy_cycles > (TOTAL_PHY_CYCLES + 4))) begin
      $error("Measured TX busy cycles outside expected range: measured=%0d expected=%0d",
             busy_cycles, TOTAL_PHY_CYCLES);
      $finish;
    end

    $display("IR_PHY_RATE_MODEL_PASS clk_mhz=%0.3f cnt_chip_max=%0d raw_mbps=%0.6f half_duplex_lanes=%0d half_duplex_raw_mbps=%0.6f full_duplex_lanes_per_dir=%0d full_duplex_per_dir_raw_mbps=%0.6f frame_bytes=%0d phy_cycles=%0d measured_busy_cycles=%0d frame_airtime_us=%0.3f",
             CLK_FREQ_HZ / 1_000_000.0, CNT_CHIP_MAX, RAW_PHY_MBPS,
             HALF_DUPLEX_LANES, HALF_DUPLEX_RAW_MBPS,
             FDX_LANES_PER_DIR, FDX_PER_DIR_RAW_MBPS, FRAME_BYTES,
             TOTAL_PHY_CYCLES, busy_cycles, FRAME_AIRTIME_US);
    $finish;
  end

  initial begin
    #200us;
    $error("Timeout waiting for PHY rate model completion");
    $finish;
  end
endmodule
