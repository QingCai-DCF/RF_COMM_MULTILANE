package tfdu_lane_phy_pkg;
  parameter int CLK_HZ = 64_000_000;
  parameter int TFDU_STARTUP_US = 500;
  parameter int TX_STUCK_HIGH_LIMIT_US = 20; // static guard; lower than 80 us device limit
  parameter int DUTY_WINDOW_US = 1000;
  parameter int DUTY_MAX_PERMILLE = 200;
endpackage
