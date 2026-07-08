`timescale 1ns/1ps
module tfdu_lane_phy #(
  parameter int CLK_HZ = 64_000_000,
  parameter int TFDU_STARTUP_US = 500,
  parameter int TX_STUCK_HIGH_LIMIT_US = 20,
  parameter int DUTY_WINDOW_US = 1000,
  parameter int DUTY_MAX_PERMILLE = 200
) (
  input  logic clk,
  input  logic rst_n,
  input  logic enable_phy,
  input  logic tx_pulse_req,
  input  logic rxd,
  output logic Txd,
  output logic SD,
  output logic Mode,
  output logic phy_ready,
  output logic rx_pulse_active,
  output logic startup_done,
  output logic shutdown_active,
  output logic fault_stuck_high,
  output logic fault_duty_limit,
  output logic [31:0] rx_raw_count,
  output logic [31:0] tx_pulse_count
);
  localparam bit MODE_STATIC_HIGH = 1'b1; // Mode=1 high-speed static policy.
  localparam int STARTUP_CYCLES = (CLK_HZ / 1_000_000) * TFDU_STARTUP_US;
  localparam int STUCK_HIGH_CYCLES = (CLK_HZ / 1_000_000) * TX_STUCK_HIGH_LIMIT_US;
  localparam int DUTY_WINDOW_CYCLES = (CLK_HZ / 1_000_000) * DUTY_WINDOW_US;
  localparam int DUTY_LIMIT_CYCLES = (DUTY_WINDOW_CYCLES * DUTY_MAX_PERMILLE) / 1000;

  logic rxd_ff1, rxd_sync, rxd_sync_d;
  logic [31:0] startup_ctr, tx_high_ctr, duty_window_ctr, duty_high_ctr;

  assign rx_pulse_active = ~rxd_sync; // TFDU6102 Rxd is low-active.
  assign Mode = MODE_STATIC_HIGH;
  assign phy_ready = startup_done && !shutdown_active;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      Txd <= 1'b0;
      SD <= 1'b1;
      shutdown_active <= 1'b1;
      startup_done <= 1'b0;
      fault_stuck_high <= 1'b0;
      fault_duty_limit <= 1'b0;
      rx_raw_count <= 32'd0;
      tx_pulse_count <= 32'd0;
      startup_ctr <= 32'd0;
      tx_high_ctr <= 32'd0;
      duty_window_ctr <= 32'd0;
      duty_high_ctr <= 32'd0;
      rxd_ff1 <= 1'b1;
      rxd_sync <= 1'b1;
      rxd_sync_d <= 1'b1;
    end else begin
      rxd_ff1 <= rxd;
      rxd_sync <= rxd_ff1;
      rxd_sync_d <= rxd_sync;

      if (!enable_phy || fault_stuck_high || fault_duty_limit) begin
        Txd <= 1'b0;
        SD <= 1'b1;
        shutdown_active <= 1'b1;
        startup_done <= 1'b0;
        startup_ctr <= 32'd0;
      end else begin
        SD <= 1'b0;
        shutdown_active <= 1'b0;
        if (!startup_done) begin
          startup_ctr <= startup_ctr + 1'b1;
          if (startup_ctr >= STARTUP_CYCLES[31:0]) startup_done <= 1'b1;
        end
        Txd <= phy_ready && tx_pulse_req;
        if (phy_ready && tx_pulse_req) tx_pulse_count <= tx_pulse_count + 1'b1;
      end

      if (Txd) tx_high_ctr <= tx_high_ctr + 1'b1; else tx_high_ctr <= 32'd0;
      if (tx_high_ctr >= STUCK_HIGH_CYCLES[31:0]) fault_stuck_high <= 1'b1;

      if (duty_window_ctr >= DUTY_WINDOW_CYCLES[31:0]) begin
        duty_window_ctr <= 32'd0;
        duty_high_ctr <= 32'd0;
      end else begin
        duty_window_ctr <= duty_window_ctr + 1'b1;
        if (Txd) duty_high_ctr <= duty_high_ctr + 1'b1;
      end
      if (duty_high_ctr > DUTY_LIMIT_CYCLES[31:0]) fault_duty_limit <= 1'b1;

      if (!rxd_sync && rxd_sync_d) rx_raw_count <= rx_raw_count + 1'b1;
    end
  end
endmodule
