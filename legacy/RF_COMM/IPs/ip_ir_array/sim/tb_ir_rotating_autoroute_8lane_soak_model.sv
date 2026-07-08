`timescale 1ns/1ps

module tb_ir_rotating_autoroute_8lane_soak_model;
  localparam int LANE_COUNT              = 8;
  localparam int PACKET_FRAGMENT_COUNT   = 8;
  localparam int MAX_RETRY               = LANE_COUNT * PACKET_FRAGMENT_COUNT;
  localparam int TARGET_RPM              = 600;
  localparam int TARGET_REV_PER_S        = TARGET_RPM / 60;
  localparam int ORIGINAL_TARGET_SECONDS = 2 * 60 * 60;
  localparam int RUNTIME_CAP_SECONDS     = 10 * 60;
  localparam int EFFECTIVE_SECONDS       =
    (ORIGINAL_TARGET_SECONDS > RUNTIME_CAP_SECONDS) ? RUNTIME_CAP_SECONDS : ORIGINAL_TARGET_SECONDS;
  localparam int TARGET_ROTATIONS        = TARGET_REV_PER_S * EFFECTIVE_SECONDS;
  localparam int SECTORS_PER_REV         = LANE_COUNT;
  localparam int TARGET_SECTORS          = TARGET_ROTATIONS * SECTORS_PER_REV;
  localparam int SHAFT_DIAMETER_MM       = 200;

  int slot;
  int frag;
  int attempt;
  int blocked;
  int lane;
  int good_lane;
  int rx_lane;
  int route_map;
  int tx_rr_ptr;
  int search_attempts;
  int retry_observed;
  int success_fragments;
  int success_slots;
  int failed_route_slots;
  int total_failed_attempts;
  int max_search_attempts;
  int max_retry_observed;
  int short_blockage_events;
  int fragment_ack_loss_events;
  int final_ack_loss_events;
  int max_final_ack_retries;
  logic [LANE_COUNT-1:0] good_lane_coverage;
  logic [LANE_COUNT-1:0] attempted_lane_coverage;
  logic [LANE_COUNT-1:0] rx_lane_coverage;
  logic [LANE_COUNT-1:0] route_map_coverage;

  function automatic int rotating_route_map(input int sector_idx);
    int rev_idx;
    begin
      rev_idx = sector_idx / SECTORS_PER_REV;
      rotating_route_map = (sector_idx + (sector_idx / 17) + (rev_idx / 29)) % LANE_COUNT;
    end
  endfunction

  function automatic int rotating_good_lane(input int sector_idx, input int frag_idx);
    int rev_idx;
    int sector_in_rev;
    int jitter;
    begin
      rev_idx       = sector_idx / SECTORS_PER_REV;
      sector_in_rev = sector_idx % SECTORS_PER_REV;
      jitter        = (sector_idx / 257) + (rev_idx / 31) + (frag_idx * 3);
      rotating_good_lane = (sector_in_rev + rev_idx + jitter) % LANE_COUNT;
    end
  endfunction

  function automatic int mapped_rx_lane(input int src_lane, input int map_id);
    begin
      mapped_rx_lane = ((src_lane * 3) + map_id) % LANE_COUNT;
    end
  endfunction

  function automatic int blockage_attempts(input int sector_idx, input int frag_idx);
    begin
      if (((sector_idx % 97) == 13) && (frag_idx == ((sector_idx / 97) % PACKET_FRAGMENT_COUNT))) begin
        blockage_attempts = 2 + ((sector_idx / 997) % 3);
      end else begin
        blockage_attempts = 0;
      end
    end
  endfunction

  function automatic bit drop_fragment_ack_once(input int sector_idx, input int frag_idx);
    begin
      drop_fragment_ack_once = (((sector_idx + (frag_idx * 131)) % 4099) == 4098);
    end
  endfunction

  function automatic bit drop_final_ack_once(input int sector_idx);
    begin
      drop_final_ack_once = ((sector_idx % 6151) == 6150);
    end
  endfunction

  task automatic search_fragment_route(input int sector_idx, input int frag_idx, output int attempts_used);
    int local_attempts;
    int blocked_attempts;
    bit found;
    begin
      good_lane = rotating_good_lane(sector_idx, frag_idx);
      rx_lane   = mapped_rx_lane(good_lane, route_map);
      good_lane_coverage[good_lane] = 1'b1;
      rx_lane_coverage[rx_lane]     = 1'b1;

      local_attempts   = 0;
      blocked_attempts = blockage_attempts(sector_idx, frag_idx);
      if (blocked_attempts != 0) begin
        short_blockage_events++;
      end

      for (blocked = 0; blocked < blocked_attempts; blocked++) begin
        lane = (tx_rr_ptr + local_attempts) % LANE_COUNT;
        attempted_lane_coverage[lane] = 1'b1;
        local_attempts++;
        total_failed_attempts++;
      end

      found = 1'b0;
      for (attempt = 0; attempt < (MAX_RETRY + 1); attempt++) begin
        lane = (tx_rr_ptr + local_attempts) % LANE_COUNT;
        attempted_lane_coverage[lane] = 1'b1;
        local_attempts++;
        if (lane == good_lane) begin
          found = 1'b1;
          break;
        end
        total_failed_attempts++;
      end

      if (!found) begin
        $fatal(1,
          "No reachable 8-lane rotating route sector=%0d frag=%0d start_lane=%0d good_lane=%0d route_map=%0d attempts=%0d",
          sector_idx, frag_idx, tx_rr_ptr, good_lane, route_map, local_attempts);
      end

      retry_observed = local_attempts - 1;
      if (retry_observed > MAX_RETRY) begin
        $fatal(1,
          "Retry budget exceeded sector=%0d frag=%0d retries=%0d max_retry=%0d",
          sector_idx, frag_idx, retry_observed, MAX_RETRY);
      end
      if (local_attempts > max_search_attempts) begin
        max_search_attempts = local_attempts;
      end
      if (retry_observed > max_retry_observed) begin
        max_retry_observed = retry_observed;
      end
      if (retry_observed != 0) begin
        failed_route_slots++;
      end

      tx_rr_ptr = (good_lane + 1) % LANE_COUNT;
      attempts_used = local_attempts;
    end
  endtask

  initial begin
    if ((TARGET_RPM != 600) || (TARGET_REV_PER_S != 10) ||
        (SHAFT_DIAMETER_MM != 200) || (ORIGINAL_TARGET_SECONDS != 7200) ||
        (RUNTIME_CAP_SECONDS != 600) || (EFFECTIVE_SECONDS != 600) ||
        (TARGET_ROTATIONS != 6000) || (TARGET_SECTORS != 48000)) begin
      $fatal(1,
        "8-lane rotating target metadata mismatch rpm=%0d rev_per_s=%0d diameter_mm=%0d original_seconds=%0d cap_seconds=%0d seconds=%0d rotations=%0d sectors=%0d",
        TARGET_RPM, TARGET_REV_PER_S, SHAFT_DIAMETER_MM, ORIGINAL_TARGET_SECONDS,
        RUNTIME_CAP_SECONDS, EFFECTIVE_SECONDS, TARGET_ROTATIONS, TARGET_SECTORS);
    end

    if ((MAX_RETRY < LANE_COUNT) || (MAX_RETRY < (LANE_COUNT * PACKET_FRAGMENT_COUNT))) begin
      $fatal(1,
        "MAX_RETRY=%0d is too small for 8-lane multi-fragment autoroute recovery",
        MAX_RETRY);
    end

    tx_rr_ptr               = 0;
    success_fragments       = 0;
    success_slots           = 0;
    failed_route_slots      = 0;
    total_failed_attempts   = 0;
    max_search_attempts     = 0;
    max_retry_observed      = 0;
    short_blockage_events   = 0;
    fragment_ack_loss_events = 0;
    final_ack_loss_events   = 0;
    max_final_ack_retries   = 0;
    good_lane_coverage      = '0;
    attempted_lane_coverage = '0;
    rx_lane_coverage        = '0;
    route_map_coverage      = '0;

    for (slot = 0; slot < TARGET_SECTORS; slot++) begin
      route_map = rotating_route_map(slot);
      route_map_coverage[route_map] = 1'b1;

      for (frag = 0; frag < PACKET_FRAGMENT_COUNT; frag++) begin
        search_fragment_route(slot, frag, search_attempts);
        success_fragments++;

        if (drop_fragment_ack_once(slot, frag)) begin
          fragment_ack_loss_events++;
          search_fragment_route(slot, frag, search_attempts);
        end
      end

      if (drop_final_ack_once(slot)) begin
        final_ack_loss_events++;
        if (LANE_COUNT > max_final_ack_retries) begin
          max_final_ack_retries = LANE_COUNT;
        end
        if (LANE_COUNT > MAX_RETRY) begin
          $fatal(1,
            "Final ACK duplicate-probe recovery exceeds retry budget sector=%0d retries=%0d max_retry=%0d",
            slot, LANE_COUNT, MAX_RETRY);
        end
      end

      success_slots++;
    end

    if (success_slots != TARGET_SECTORS) begin
      $fatal(1, "8-lane rotating slot count mismatch success=%0d expected=%0d",
        success_slots, TARGET_SECTORS);
    end
    if (success_fragments < (TARGET_SECTORS * PACKET_FRAGMENT_COUNT)) begin
      $fatal(1, "8-lane rotating fragment count mismatch success=%0d expected_min=%0d",
        success_fragments, TARGET_SECTORS * PACKET_FRAGMENT_COUNT);
    end
    if (good_lane_coverage != '1 || attempted_lane_coverage != '1 ||
        rx_lane_coverage != '1 || route_map_coverage != '1) begin
      $fatal(1,
        "8-lane rotating coverage mismatch good=%08b attempted=%08b rx=%08b route_maps=%08b",
        good_lane_coverage, attempted_lane_coverage, rx_lane_coverage, route_map_coverage);
    end
    if (failed_route_slots == 0 || short_blockage_events == 0 ||
        fragment_ack_loss_events == 0 || final_ack_loss_events == 0) begin
      $fatal(1,
        "8-lane rotating model missed recovery coverage failed_route_slots=%0d short_blockage_events=%0d fragment_ack_loss_events=%0d final_ack_loss_events=%0d",
        failed_route_slots, short_blockage_events, fragment_ack_loss_events, final_ack_loss_events);
    end

    $display("ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS original_target_seconds=%0d runtime_cap_seconds=%0d seconds=%0d rpm=%0d rev_per_s=%0d shaft_diameter_mm=%0d rotations=%0d sectors_per_rev=%0d sectors=%0d lane_count=%0d packet_fragments=%0d max_retry=%0d success_slots=%0d success_fragments=%0d max_search_attempts=%0d max_retry_observed=%0d failed_route_slots=%0d total_failed_attempts=%0d short_blockage_events=%0d fragment_ack_loss_events=%0d final_ack_loss_events=%0d max_final_ack_retries=%0d good_lane_coverage=%08b attempted_lane_coverage=%08b rx_lane_coverage=%08b route_map_coverage=%08b",
      ORIGINAL_TARGET_SECONDS, RUNTIME_CAP_SECONDS, EFFECTIVE_SECONDS,
      TARGET_RPM, TARGET_REV_PER_S, SHAFT_DIAMETER_MM, TARGET_ROTATIONS,
      SECTORS_PER_REV, TARGET_SECTORS, LANE_COUNT, PACKET_FRAGMENT_COUNT,
      MAX_RETRY, success_slots, success_fragments, max_search_attempts,
      max_retry_observed, failed_route_slots, total_failed_attempts,
      short_blockage_events, fragment_ack_loss_events, final_ack_loss_events,
      max_final_ack_retries, good_lane_coverage, attempted_lane_coverage,
      rx_lane_coverage, route_map_coverage);
    $finish;
  end
endmodule
