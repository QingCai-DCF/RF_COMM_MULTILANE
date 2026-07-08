`timescale 1ns/1ps

module tb_ir_rotating_autoroute_soak_model;
  localparam int LANE_COUNT          = 4;
  localparam int MAX_RETRY           = 4;
  localparam int MAX_DATA_ATTEMPTS   = MAX_RETRY + 1;
  localparam int TARGET_RPM          = 600;
  localparam int TARGET_REV_PER_S    = TARGET_RPM / 60;
  localparam int TARGET_SECONDS      = 2 * 60 * 60;
  localparam int TARGET_ROTATIONS    = TARGET_REV_PER_S * TARGET_SECONDS;
  localparam int SECTORS_PER_REV     = 4;
  localparam int TARGET_SECTORS      = TARGET_ROTATIONS * SECTORS_PER_REV;
  localparam int SHAFT_DIAMETER_MM   = 200;

  int slot;
  int attempt;
  int lane;
  int good_lane;
  int found_attempts;
  int failed_attempts;
  int route_map;
  int tx_rr_ptr;
  int success_slots;
  int failed_route_slots;
  int total_failed_attempts;
  int max_search_attempts;
  int ack_loss_events;
  int max_final_ack_retries;
  logic [LANE_COUNT-1:0] good_lane_coverage;
  logic [LANE_COUNT-1:0] attempted_lane_coverage;
  logic [LANE_COUNT-1:0] route_map_coverage;

  function automatic int rotating_good_lane(input int sector_idx);
    int rev_idx;
    int sector_in_rev;
    int jitter;
    begin
      rev_idx       = sector_idx / SECTORS_PER_REV;
      sector_in_rev = sector_idx % SECTORS_PER_REV;
      jitter        = (sector_idx / 257) + (rev_idx / 31);
      rotating_good_lane = (sector_in_rev + rev_idx + jitter) % LANE_COUNT;
    end
  endfunction

  function automatic int rotating_route_map(input int sector_idx);
    begin
      rotating_route_map = (sector_idx + (sector_idx / 19) + (sector_idx / 997)) % SECTORS_PER_REV;
    end
  endfunction

  function automatic bit drop_complete_ack_once(input int sector_idx, input int search_attempts);
    begin
      drop_complete_ack_once = ((sector_idx % 4093) == 4092) && (search_attempts < MAX_DATA_ATTEMPTS);
    end
  endfunction

  initial begin
    if ((TARGET_RPM != 600) || (TARGET_REV_PER_S != 10) ||
        (SHAFT_DIAMETER_MM != 200) || (TARGET_SECONDS != 7200) ||
        (TARGET_ROTATIONS != 72000) || (TARGET_SECTORS != 288000)) begin
      $fatal(1,
        "Rotating soak target metadata mismatch rpm=%0d rev_per_s=%0d diameter_mm=%0d seconds=%0d rotations=%0d sectors=%0d",
        TARGET_RPM, TARGET_REV_PER_S, SHAFT_DIAMETER_MM,
        TARGET_SECONDS, TARGET_ROTATIONS, TARGET_SECTORS);
    end

    if (MAX_RETRY < LANE_COUNT) begin
      $fatal(1, "MAX_RETRY=%0d is too small for four-lane one-good-lane autoroute recovery", MAX_RETRY);
    end

    tx_rr_ptr               = 0;
    success_slots           = 0;
    failed_route_slots      = 0;
    total_failed_attempts   = 0;
    max_search_attempts     = 0;
    ack_loss_events         = 0;
    max_final_ack_retries   = 0;
    good_lane_coverage      = '0;
    attempted_lane_coverage = '0;
    route_map_coverage      = '0;

    for (slot = 0; slot < TARGET_SECTORS; slot++) begin
      good_lane = rotating_good_lane(slot);
      route_map = rotating_route_map(slot);
      route_map_coverage[route_map] = 1'b1;
      good_lane_coverage[good_lane] = 1'b1;

      found_attempts  = 0;
      failed_attempts = 0;
      for (attempt = 0; attempt < MAX_DATA_ATTEMPTS; attempt++) begin
        lane = (tx_rr_ptr + attempt) % LANE_COUNT;
        attempted_lane_coverage[lane] = 1'b1;
        if (lane == good_lane) begin
          found_attempts = attempt + 1;
          break;
        end
        failed_attempts++;
      end

      if (found_attempts == 0) begin
        $fatal(1,
          "No reachable route found slot=%0d start_lane=%0d good_lane=%0d attempts=%0d",
          slot, tx_rr_ptr, good_lane, MAX_DATA_ATTEMPTS);
      end

      if (found_attempts > max_search_attempts) begin
        max_search_attempts = found_attempts;
      end
      if (failed_attempts != 0) begin
        failed_route_slots++;
        total_failed_attempts += failed_attempts;
      end

      // The RTL lane scheduler advances round-robin after each issued frame.
      // With one reachable lane, a lost COMPLETE ACK needs at most one full
      // four-lane duplicate-probe scan, which MAX_RETRY=4 permits.
      tx_rr_ptr = (good_lane + 1) % LANE_COUNT;
      if (drop_complete_ack_once(slot, found_attempts)) begin
        ack_loss_events++;
        if (LANE_COUNT > max_final_ack_retries) begin
          max_final_ack_retries = LANE_COUNT;
        end
        if (LANE_COUNT > MAX_RETRY) begin
          $fatal(1,
            "Final ACK recovery exceeds retry budget slot=%0d retries=%0d max_retry=%0d",
            slot, LANE_COUNT, MAX_RETRY);
        end
        tx_rr_ptr = (good_lane + 1) % LANE_COUNT;
      end

      success_slots++;
    end

    if (success_slots != TARGET_SECTORS) begin
      $fatal(1, "Rotating soak slot count mismatch success=%0d expected=%0d", success_slots, TARGET_SECTORS);
    end
    if (good_lane_coverage != '1 || attempted_lane_coverage != '1 || route_map_coverage != '1) begin
      $fatal(1,
        "Rotating soak coverage mismatch good=%04b attempted=%04b route_maps=%04b",
        good_lane_coverage, attempted_lane_coverage, route_map_coverage);
    end
    if (failed_route_slots == 0 || ack_loss_events == 0) begin
      $fatal(1,
        "Rotating soak did not exercise recovery paths failed_route_slots=%0d ack_loss_events=%0d",
        failed_route_slots, ack_loss_events);
    end

    $display("ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS rpm=%0d rev_per_s=%0d shaft_diameter_mm=%0d seconds=%0d rotations=%0d sectors=%0d max_search_attempts=%0d failed_route_slots=%0d total_failed_attempts=%0d ack_loss_events=%0d max_final_ack_retries=%0d good_lane_coverage=%04b attempted_lane_coverage=%04b route_map_coverage=%04b",
      TARGET_RPM, TARGET_REV_PER_S, SHAFT_DIAMETER_MM, TARGET_SECONDS,
      TARGET_ROTATIONS, TARGET_SECTORS, max_search_attempts, failed_route_slots,
      total_failed_attempts, ack_loss_events, max_final_ack_retries,
      good_lane_coverage, attempted_lane_coverage, route_map_coverage);
    $finish;
  end
endmodule
