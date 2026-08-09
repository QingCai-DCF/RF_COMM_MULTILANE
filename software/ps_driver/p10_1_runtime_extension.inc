/*
 * Role-bound P10.1 board-autonomous streaming extension.
 *
 * This file is included by p9_runtime_main.c after the reviewed P9/P10
 * transport helpers.  It deliberately reuses the same fail-closed endpoint
 * arm/shutdown path and the same AXI-DMA instance.  One mailbox command owns
 * an entire logical stream: XSDB is not involved per object, segment, or DMA
 * descriptor.
 */
#include "p10_1_runtime_protocol.h"

enum {
  P10_1_PATTERN_PRBS = 0,
  P10_1_PATTERN_ZERO = 1,
  P10_1_PATTERN_ONE = 2,
  P10_1_PATTERN_COUNTER = 3,
  P10_1_PATTERN_CORPUS = 4,
  P10_1_PERF_COMMAND_OFFSET = 0x0908U,
  P10_1_PERF_SNAPSHOT_CONTROL_OFFSET = 0x0934U,
  P10_1_PERF_SNAPSHOT_GENERATION_OFFSET = 0x0938U,
  P10_1_PERF_TIMER_LOW_OFFSET = 0x093cU,
  P10_1_PERF_TIMER_HIGH_OFFSET = 0x0940U,
  P10_1_PER_LANE_DATA_GOOD_0 = 0x088cU,
  P10_1_PER_LANE_DATA_GOOD_1 = 0x0890U,
  P10_1_PER_LANE_ACK_GOOD_0 = 0x0894U,
  P10_1_PER_LANE_ACK_GOOD_1 = 0x0898U,
  P10_1_PER_LANE_CRC_BAD_0 = 0x089cU,
  P10_1_PER_LANE_CRC_BAD_1 = 0x08a0U,
  P10_1_PER_LANE_FRAME_BAD_0 = 0x08a4U,
  P10_1_PER_LANE_FRAME_BAD_1 = 0x08a8U,
  P10_1_PER_LANE_PREAMBLE_0 = 0x08acU,
  P10_1_PER_LANE_PREAMBLE_1 = 0x08b0U,
  P10_1_PER_LANE_SYMBOL_ERROR_0 = 0x08b4U,
  P10_1_PER_LANE_SYMBOL_ERROR_1 = 0x08b8U,
  /*
   * Existing protocol fault bit 3 sends the first three DATA attempts with
   * sequence initial_sequence-1 while retaining their canonical payload
   * metadata.  The receiver must classify those same-session, behind-base
   * frames as duplicates before a normal sequence is retried.
   */
  P10_1_DUPLICATE_PAST_SEQUENCE_FLAG = 1U << 3,
};

static volatile p10_1_runtime_result_t *p10_1_result(void) {
  return (volatile p10_1_runtime_result_t *)(uintptr_t)
      P10_1_RUNTIME_MAILBOX_BASEADDR;
}

static void p10_1_publish_state(volatile p10_1_runtime_result_t *result,
                                uint32_t state) {
  /*
   * The P10.1 result page is at 0x00020400.  The Cortex-A9 standalone BSP
   * maps the containing 1-MiB section as normal write-back cacheable memory.
   * Once the payload path enables D-cache, a DSB alone does not make this
   * host-polled publication record visible to XSDB.  Treat service_state as
   * the release word for the complete record: write it last, clean every
   * preceding result field plus the state itself to the point of coherency,
   * then complete the publication barrier.
   */
  dsb();
  result->service_state = state;
  if (g_cache_enabled != 0U)
    Xil_DCacheFlushRange((UINTPTR)result, sizeof(*result));
  dsb();
}

static void p10_1_store64(volatile uint32_t *low,
                          volatile uint32_t *high, uint64_t value) {
  *low = (uint32_t)value;
  *high = (uint32_t)(value >> 32);
}

static uint64_t p10_1_load64(volatile const uint32_t *low,
                             volatile const uint32_t *high) {
  return (uint64_t)*low | ((uint64_t)*high << 32);
}

static int p10_5_wait_for_paired_launch_release(
    volatile p9_mailbox_t *mailbox,
    volatile p10_1_runtime_result_t *result) {
  uint64_t started = p9_time_now();
  uint64_t deadline = started +
      ((uint64_t)P10_5_LAUNCH_BARRIER_TIMEOUT_MS *
       (uint64_t)COUNTS_PER_SECOND) / UINT64_C(1000);

  /*
   * protocol_fault_flags shares a write-back OCM cache line with other
   * command inputs.  Flush all CPU-side command edits before publishing
   * PRIMED.  The host cannot set RELEASE until it observes PRIMED on both
   * endpoints, so subsequent invalidations cannot discard a dirty neighbor.
   */
  result->p10_5_launch_barrier_waited = 1U;
  if (g_cache_enabled != 0U)
    p9_cache_flush((UINTPTR)&mailbox->protocol_fault_flags,
                   sizeof(mailbox->protocol_fault_flags));
  p10_1_publish_state(result, P10_1_RUNTIME_PRIMED);

  do {
    uint32_t live_flags;
    if (g_cache_enabled != 0U)
      p9_cache_invalidate((UINTPTR)&mailbox->protocol_fault_flags,
                          sizeof(mailbox->protocol_fault_flags));
    dsb();
    live_flags = mailbox->protocol_fault_flags;
    if ((live_flags & P10_5_HOST_LAUNCH_RELEASE_MASK) != 0U) {
      result->p10_5_launch_release_seen = 1U;
      p10_1_store64(&result->p10_5_launch_wait_ticks_low,
                    &result->p10_5_launch_wait_ticks_high,
                    p9_time_now() - started);
      return P10_1_RUNTIME_STATUS_OK;
    }
    usleep(1000U);
  } while (p9_time_now() < deadline);

  p10_1_store64(&result->p10_5_launch_wait_ticks_low,
                &result->p10_5_launch_wait_ticks_high,
                p9_time_now() - started);
  result->last_error_detail = UINT32_C(0x42415252); /* BARR */
  return P10_1_RUNTIME_STATUS_HOST_LAUNCH_BARRIER;
}

static uint32_t p10_1_mix32(uint32_t value) {
  value ^= value >> 16;
  value *= UINT32_C(0x7feb352d);
  value ^= value >> 15;
  value *= UINT32_C(0x846ca68b);
  value ^= value >> 16;
  return value;
}

static void p10_1_fill_payload(uint8_t *output, uint32_t bytes,
                               uint32_t pattern, uint32_t seed,
                               uint32_t object_ordinal) {
  static const uint8_t corpus[32] = {
      0x00, 0xff, 0x55, 0xaa, 0x7e, 0x81, 0x01, 0x80,
      0x10, 0xef, 0x33, 0xcc, 0x0f, 0xf0, 0x5a, 0xa5,
      0x52, 0x46, 0x41, 0x50, 0x00, 0x01, 0xfe, 0xff,
      0x13, 0x37, 0xde, 0xad, 0xbe, 0xef, 0xc3, 0x3c};
  if (pattern == P10_1_PATTERN_ZERO || pattern == P10_1_PATTERN_ONE) {
    memset(output, pattern == P10_1_PATTERN_ZERO ? 0x00 : 0xff, bytes);
    return;
  }
  for (uint32_t index = 0U; index < bytes; ++index) {
    if (pattern == P10_1_PATTERN_COUNTER) {
      output[index] = (uint8_t)(index + object_ordinal);
    } else if (pattern == P10_1_PATTERN_CORPUS) {
      output[index] = corpus[(index + object_ordinal) & 31U];
    } else {
      uint32_t word = p10_1_mix32(seed ^ (object_ordinal *
          UINT32_C(0x9e3779b9)) ^ (index >> 2));
      output[index] = (uint8_t)(word >> ((index & 3U) * 8U));
    }
  }
}

static void p10_1_copy_digest_words(volatile uint32_t output[8],
                                    const uint8_t digest[32]) {
  for (uint32_t index = 0U; index < 8U; ++index) {
    output[index] = ((uint32_t)digest[index * 4U]) |
                    ((uint32_t)digest[index * 4U + 1U] << 8) |
                    ((uint32_t)digest[index * 4U + 2U] << 16) |
                    ((uint32_t)digest[index * 4U + 3U] << 24);
  }
}

static uint64_t p10_1_pl_snapshot(void) {
  uint32_t generation;
  uint32_t low;
  uint32_t high;
  p9_pl_write(P10_1_PERF_SNAPSHOT_CONTROL_OFFSET, 1U);
  usleep(10U);
  for (uint32_t attempt = 0U; attempt < 1000U; ++attempt) {
    generation = p9_pl_read(P10_1_PERF_SNAPSHOT_GENERATION_OFFSET);
    if ((generation & 1U) == 0U) {
      high = p9_pl_read(P10_1_PERF_TIMER_HIGH_OFFSET);
      low = p9_pl_read(P10_1_PERF_TIMER_LOW_OFFSET);
      if (generation ==
              p9_pl_read(P10_1_PERF_SNAPSHOT_GENERATION_OFFSET))
        return (uint64_t)low | ((uint64_t)high << 32);
    }
    usleep(1U);
  }
  return UINT64_MAX;
}

static void p10_1_read_quad(uint32_t first_offset,
                            volatile uint32_t output[4]) {
  for (uint32_t index = 0U; index < 4U; ++index)
    output[index] = p9_pl_read(first_offset + 4U * index);
}

static void p10_1_read_pair(uint32_t first_offset,
                            volatile uint32_t output[2]) {
  output[0] = p9_pl_read(first_offset);
  output[1] = p9_pl_read(first_offset + 4U);
}

static void p10_1_snapshot_physical(
    volatile p10_1_runtime_result_t *result, uint32_t before) {
#if P10_LANE_COUNT == 4
  p9_pl_write(IR_REG_P10_2_SNAPSHOT_CONTROL, 1U);
  for (uint32_t lane = 0U; lane < 4U; ++lane) {
    uint32_t module = P10_ENDPOINT_ROLE == 2 ? lane + 4U : lane;
    volatile uint32_t *raw = before != 0U ? result->raw_rx_before :
                                            result->raw_rx_after;
    volatile uint32_t *tx = before != 0U ? result->physical_tx_before :
                                           result->physical_tx_after;
    raw[lane] = p9_pl_read(ir_p10_2_module_word_offset(module, 0U));
    tx[lane] = p9_pl_read(ir_p10_2_module_word_offset(module, 1U));
    if (before == 0U) {
      result->tx_high_max_after[lane] =
          p9_pl_read(ir_p10_2_module_word_offset(module, 2U));
      result->duty_high_max_after[lane] =
          p9_pl_read(ir_p10_2_module_word_offset(module, 3U));
      result->duty_hard_fault_after[lane] =
          p9_pl_read(ir_p10_2_module_word_offset(module, 7U));
    }
  }
  if (before != 0U) return;
  /* Frozen P10.1 result fields retain lanes 0/1 for old readers.  The
   * complete four-lane view is the versioned P10.2 atomic snapshot. */
  for (uint32_t lane = 0U; lane < 2U; ++lane) {
    result->physical_data_good_by_lane_after[lane] =
        p9_pl_read(ir_p10_2_lane_word_offset(lane, 4U));
    result->physical_ack_good_by_lane_after[lane] =
        p9_pl_read(ir_p10_2_lane_word_offset(lane, 5U));
    result->physical_crc_bad_by_lane_after[lane] =
        p9_pl_read(ir_p10_2_lane_word_offset(lane, 6U));
    result->physical_frame_bad_by_lane_after[lane] =
        p9_pl_read(ir_p10_2_lane_word_offset(lane, 7U));
  }
  return;
#else
  if (before != 0U) {
    p10_1_read_quad(IR_REG_P9_RAW_RX_A0, result->raw_rx_before);
    p10_1_read_quad(IR_REG_P9_PHYSICAL_TX_A0, result->physical_tx_before);
    return;
  }
  p10_1_read_quad(IR_REG_P9_RAW_RX_A0, result->raw_rx_after);
  p10_1_read_quad(IR_REG_P9_PHYSICAL_TX_A0, result->physical_tx_after);
  p10_1_read_quad(IR_REG_P9_DUTY_MAX_A0, result->duty_high_max_after);
  p10_1_read_quad(IR_REG_P9_DUTY_HARD_FAULT_A0,
                  result->duty_hard_fault_after);
  p10_1_read_quad(IR_REG_P9_TX_HIGH_MAX_A0, result->tx_high_max_after);
  p10_1_read_pair(P10_1_PER_LANE_DATA_GOOD_0,
                  result->physical_data_good_by_lane_after);
  p10_1_read_pair(P10_1_PER_LANE_ACK_GOOD_0,
                  result->physical_ack_good_by_lane_after);
  p10_1_read_pair(P10_1_PER_LANE_CRC_BAD_0,
                  result->physical_crc_bad_by_lane_after);
  p10_1_read_pair(P10_1_PER_LANE_FRAME_BAD_0,
                  result->physical_frame_bad_by_lane_after);
  p10_1_read_pair(P10_1_PER_LANE_PREAMBLE_0,
                  result->physical_preamble_by_lane_after);
  p10_1_read_pair(P10_1_PER_LANE_SYMBOL_ERROR_0,
                  result->physical_symbol_error_by_lane_after);
#endif
}

static void p10_1_snapshot_perf(
    volatile p10_1_runtime_result_t *result) {
  uint32_t *first = (uint32_t *)&result->perf_snapshot_generation;
  p9_pl_write(P10_1_PERF_SNAPSHOT_CONTROL_OFFSET, 1U);
  usleep(10U);
  first[0] = p9_pl_read(0x0938U);
  first[1] = p9_pl_read(0x0944U);
  first[2] = p9_pl_read(0x0948U);
  first[3] = p9_pl_read(0x094cU);
  first[4] = p9_pl_read(0x0950U);
  first[5] = p9_pl_read(0x0954U);
  first[6] = p9_pl_read(0x0958U);
  first[7] = p9_pl_read(0x095cU);
  first[8] = p9_pl_read(0x0960U);
  first[9] = p9_pl_read(0x0964U);
  first[10] = p9_pl_read(0x0968U);
  first[11] = p9_pl_read(0x096cU);
  first[12] = p9_pl_read(0x0970U);
  first[13] = p9_pl_read(0x0974U);
  first[14] = p9_pl_read(0x0978U);
  first[15] = p9_pl_read(0x097cU);
  first[16] = p9_pl_read(0x0980U);
  first[17] = p9_pl_read(0x0984U);
  first[18] = p9_pl_read(0x0988U);
  first[19] = p9_pl_read(0x098cU);
  first[20] = p9_pl_read(0x09b0U);
  first[21] = p9_pl_read(0x09b4U);
  first[22] = p9_pl_read(0x09b8U);
  first[23] = p9_pl_read(0x09bcU);
  result->perf_outstanding_unacked_low = p9_pl_read(0x0d88U);
  result->perf_outstanding_unacked_high = p9_pl_read(0x0d8cU);
  result->perf_tx_idle_due_to_ack_low = p9_pl_read(0x0d90U);
  result->perf_tx_idle_due_to_ack_high = p9_pl_read(0x0d94U);
  result->perf_window_full_stall_low = p9_pl_read(0x0d98U);
  result->perf_window_full_stall_high = p9_pl_read(0x0d9cU);
  result->perf_receiver_credit_stall_low = p9_pl_read(0x0da0U);
  result->perf_receiver_credit_stall_high = p9_pl_read(0x0da4U);
  result->perf_direction_turnaround_idle_low = p9_pl_read(0x0da8U);
  result->perf_direction_turnaround_idle_high = p9_pl_read(0x0dacU);
  /*
   * The PL wire counter is derived from actual final-boundary TFDU symbol
   * pulses, not from DMA payload acceptance.  Publish that local optical
   * byte-equivalent in the generic result field so evidence never labels
   * application bytes as wire bytes.
   */
  p10_1_store64(
      &result->wire_bytes_low, &result->wire_bytes_high,
      p10_1_load64(
          &result->perf_wire_bytes_low, &result->perf_wire_bytes_high));
}

static uint32_t p10_1_descriptor_count(uint32_t bytes,
                                       uint32_t descriptor_bytes) {
  return (bytes + descriptor_bytes - 1U) / descriptor_bytes;
}

static int p10_1_submit_chain(uint32_t tx_direction, UINTPTR address,
                              uint32_t bytes, uint32_t descriptor_bytes,
                              uint32_t token_base,
                              volatile p10_1_runtime_result_t *result) {
  XAxiDma_BdRing *ring = tx_direction != 0U ?
      XAxiDma_GetTxRing(&g_dma) : XAxiDma_GetRxRing(&g_dma);
  uint32_t count = p10_1_descriptor_count(bytes, descriptor_bytes);
  XAxiDma_Bd *set;
  XAxiDma_Bd *bd;
  uint32_t offset = 0U;
  uint32_t submitted_count = 0U;
  if (count == 0U || count > g_ring_depth ||
      XAxiDma_BdRingGetFreeCnt(ring) < (int)count ||
      XAxiDma_BdRingAlloc(ring, (int)count, &set) != XST_SUCCESS)
    return P10_1_RUNTIME_STATUS_DMA_CHAIN;
  bd = set;
  for (uint32_t index = 0U; index < count; ++index) {
    uint32_t remaining = bytes - offset;
    uint32_t length = remaining < descriptor_bytes ?
                          remaining : descriptor_bytes;
    uint32_t control = 0U;
    if (tx_direction != 0U) {
      if (index == 0U) control |= XAXIDMA_BD_CTRL_TXSOF_MASK;
      if (index + 1U == count) control |= XAXIDMA_BD_CTRL_TXEOF_MASK;
    }
    if (XAxiDma_BdSetBufAddr(bd, address + offset) != XST_SUCCESS ||
        XAxiDma_BdSetLength(bd, length, ring->MaxTransferLen) != XST_SUCCESS) {
      (void)XAxiDma_BdRingUnAlloc(ring, (int)count, set);
      return P10_1_RUNTIME_STATUS_DMA_CHAIN;
    }
    XAxiDma_BdSetCtrl(bd, control);
    XAxiDma_BdSetId(bd, token_base + index);
    offset += length;
    bd = (XAxiDma_Bd *)XAxiDma_BdRingNext(ring, bd);
  }
  if (offset != bytes)
    return P10_1_RUNTIME_STATUS_DMA_CHAIN;
  bd = set;
  while (submitted_count < count) {
    uint32_t batch = count - submitted_count;
    if (batch > result->descriptor_batch)
      batch = result->descriptor_batch;
    if (XAxiDma_BdRingToHw(ring, (int)batch, bd) != XST_SUCCESS)
      return P10_1_RUNTIME_STATUS_DMA_CHAIN;
    if (tx_direction != 0U) {
      if (g_tx_started == 0U) {
        if (XAxiDma_BdRingStart(ring) != XST_SUCCESS)
          return P10_1_RUNTIME_STATUS_DMA_CHAIN;
        g_tx_started = 1U;
      }
    } else if (g_rx_started == 0U) {
      if (XAxiDma_BdRingStart(ring) != XST_SUCCESS)
        return P10_1_RUNTIME_STATUS_DMA_CHAIN;
      g_rx_started = 1U;
    }
    p10_ps_dma_activity_begin(tx_direction, batch);
    for (uint32_t index = 0U; index < batch; ++index)
      bd = (XAxiDma_Bd *)XAxiDma_BdRingNext(ring, bd);
    submitted_count += batch;
  }
  if (tx_direction != 0U) {
    g_metrics.tx_submitted += count;
    for (uint32_t index = 0U; index < count; ++index)
      p9_advance_producer(1U);
  } else {
    g_metrics.rx_submitted += count;
    for (uint32_t index = 0U; index < count; ++index)
      p9_advance_producer(0U);
  }
  {
    uint64_t submitted = p10_1_load64(&result->descriptors_submitted_low,
                                      &result->descriptors_submitted_high);
    submitted += count;
    p10_1_store64(&result->descriptors_submitted_low,
                  &result->descriptors_submitted_high, submitted);
  }
  result->fast_path_segment_count += count;
  return P10_1_RUNTIME_STATUS_OK;
}

static int p10_1_collect_chain(uint32_t tx_direction, uint32_t expected,
                               uint32_t token_base, uint32_t timeout_ms,
                               uint32_t expected_bytes,
                               volatile p10_1_runtime_result_t *result) {
  XAxiDma_BdRing *ring = tx_direction != 0U ?
      XAxiDma_GetTxRing(&g_dma) : XAxiDma_GetRxRing(&g_dma);
  uint32_t completed = 0U;
  uint32_t seen = 0U;
  uint64_t actual_bytes = 0U;
  uint64_t deadline = p9_time_now() +
      ((uint64_t)timeout_ms * (uint64_t)COUNTS_PER_SECOND) / UINT64_C(1000);
  uint32_t pl_done = 0U;
  while (p9_time_now() < deadline) {
    XAxiDma_Bd *set;
    int count = XAxiDma_BdRingFromHw(ring, XAXIDMA_ALL_BDS, &set);
    if (count > 0) {
      XAxiDma_Bd *bd = set;
      for (int index = 0; index < count; ++index) {
        uint32_t token = (uint32_t)XAxiDma_BdGetId(bd);
        uint32_t relative = token - token_base;
        uint32_t status = XAxiDma_BdGetSts(bd);
        if (relative >= expected || relative >= 32U ||
            (seen & (1U << relative)) != 0U ||
            (status & XAXIDMA_BD_STS_ALL_ERR_MASK) != 0U)
          return P10_1_RUNTIME_STATUS_DMA_COMPLETION;
        seen |= 1U << relative;
        if (tx_direction == 0U)
          actual_bytes += XAxiDma_BdGetActualLength(bd,
                                                    ring->MaxTransferLen);
        bd = (XAxiDma_Bd *)XAxiDma_BdRingNext(ring, bd);
      }
      if (XAxiDma_BdRingFree(ring, count, set) != XST_SUCCESS)
        return P10_1_RUNTIME_STATUS_DMA_COMPLETION;
      p10_ps_dma_activity_end(tx_direction, (uint32_t)count);
      completed += (uint32_t)count;
      if (tx_direction != 0U) {
        g_metrics.tx_completed += (uint32_t)count;
        for (int index = 0; index < count; ++index)
          p9_advance_consumer(1U);
      } else {
        g_metrics.rx_completed += (uint32_t)count;
        for (int index = 0; index < count; ++index)
          p9_advance_consumer(0U);
      }
      {
        uint64_t total = p10_1_load64(&result->descriptors_completed_low,
                                      &result->descriptors_completed_high);
        total += (uint32_t)count;
        p10_1_store64(&result->descriptors_completed_low,
                      &result->descriptors_completed_high, total);
      }
    }
    {
      uint32_t pl_status = p9_pl_read(IR_REG_P9_STATUS);
      if ((pl_status & P9_STATUS_OBJECT_FAIL) != 0U) {
        result->last_error_detail = p9_pl_read(IR_REG_P9_OBJECT_ERROR);
        return P10_1_RUNTIME_STATUS_PL_OBJECT;
      }
      if ((pl_status & P9_STATUS_OBJECT_DONE) != 0U) pl_done = 1U;
    }
    if (completed == expected && pl_done != 0U) {
      if (tx_direction == 0U && actual_bytes != expected_bytes)
        return P10_1_RUNTIME_STATUS_DMA_COMPLETION;
      return P10_1_RUNTIME_STATUS_OK;
    }
    usleep(P9_POLL_DELAY_US);
  }
  return P10_1_RUNTIME_STATUS_DMA_COMPLETION;
}

static uint32_t p10_1_signal_lane(uint32_t lane_mask) {
  for (uint32_t lane = 0U; lane < P10_LANE_COUNT; ++lane)
    if ((lane_mask & (UINT32_C(1) << lane)) != 0U) return lane;
  return 0U;
}

static int p10_1_send_signal(uint32_t original_direction,
                             uint32_t lane_mask, uint32_t timeout_ms,
                             volatile p10_1_runtime_result_t *result) {
  uint32_t lane = p10_1_signal_lane(lane_mask);
  uint64_t started = p9_time_now();
  uint32_t reverse_direction = original_direction ^ 1U;
  p9_pl_write(IR_REG_P9_RAW_CONFIG,
              (1U << lane) | (reverse_direction << 8));
  p9_pl_write(IR_REG_P9_RAW_TARGET, P10_1_RUNTIME_SIGNAL_PULSES);
  p9_pl_write(IR_REG_P9_RAW_SPACING,
              P10_1_RUNTIME_SIGNAL_SPACING_CYCLES);
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_RAW_MASK);
  uint64_t deadline = p9_time_now() +
      ((uint64_t)timeout_ms * (uint64_t)COUNTS_PER_SECOND) /
          UINT64_C(1000);
  while (p9_time_now() < deadline) {
    uint32_t status = p9_pl_read(IR_REG_P9_STATUS);
    if ((status & P9_STATUS_RAW_DONE) != 0U &&
        p9_pl_read(IR_REG_P9_RAW_SENT_COUNT) ==
            P10_1_RUNTIME_SIGNAL_PULSES) {
      uint64_t elapsed = p10_1_load64(
          &result->inter_object_signal_ticks_low,
          &result->inter_object_signal_ticks_high);
      elapsed += p9_time_now() - started;
      p10_1_store64(&result->inter_object_signal_ticks_low,
                    &result->inter_object_signal_ticks_high, elapsed);
      return P10_1_RUNTIME_STATUS_OK;
    }
    if ((p9_pl_read(IR_REG_P9_PHY_STATUS) &
         (P10_PHY_READY_ALL_MASK << P10_PHY_SAFETY_SHIFT)) != 0U)
      break;
    usleep(P9_POLL_DELAY_US);
  }
  return P10_1_RUNTIME_STATUS_SIGNAL_TIMEOUT;
}

static int p10_1_wait_signal(uint32_t lane_mask, uint32_t timeout_ms,
                             volatile p10_1_runtime_result_t *result) {
  uint32_t lane = p10_1_signal_lane(lane_mask);
  uint32_t before = p10_runtime_local_raw_count(lane);
  uint64_t started = p9_time_now();
  uint64_t deadline = p9_time_now() +
      ((uint64_t)timeout_ms * (uint64_t)COUNTS_PER_SECOND) /
          UINT64_C(1000);
  while (p9_time_now() < deadline) {
    uint32_t after = p10_runtime_local_raw_count(lane);
    if (after - before >= P10_1_RUNTIME_SIGNAL_PULSES) {
      uint64_t elapsed = p10_1_load64(
          &result->inter_object_signal_ticks_low,
          &result->inter_object_signal_ticks_high);
      elapsed += p9_time_now() - started;
      p10_1_store64(&result->inter_object_signal_ticks_low,
                    &result->inter_object_signal_ticks_high, elapsed);
      return P10_1_RUNTIME_STATUS_OK;
    }
    if ((p9_pl_read(IR_REG_P9_PHY_STATUS) &
         (P10_PHY_READY_ALL_MASK << P10_PHY_SAFETY_SHIFT)) != 0U)
      break;
    usleep(P9_POLL_DELAY_US);
  }
  return P10_1_RUNTIME_STATUS_SIGNAL_TIMEOUT;
}

static void p10_1_finalize_timer(
    volatile p10_1_runtime_result_t *result) {
  uint64_t ps_start = p10_1_load64(&result->ps_start_ticks_low,
                                   &result->ps_start_ticks_high);
  uint64_t ps_end = p10_1_load64(&result->ps_end_ticks_low,
                                 &result->ps_end_ticks_high);
  uint64_t pl_start = p10_1_load64(&result->pl_start_ticks_low,
                                   &result->pl_start_ticks_high);
  uint64_t pl_end = p10_1_load64(&result->pl_end_ticks_low,
                                 &result->pl_end_ticks_high);
  uint64_t ps_elapsed = ps_end - ps_start;
  uint64_t pl_elapsed = pl_end - pl_start;
  uint64_t ps_us = (ps_elapsed * UINT64_C(1000000)) /
                   (uint64_t)COUNTS_PER_SECOND;
  uint64_t pl_us = (pl_elapsed * UINT64_C(1000000)) /
                   P10_1_RUNTIME_PL_TIMER_HZ;
  uint64_t maximum = ps_us > pl_us ? ps_us : pl_us;
  uint64_t difference = ps_us > pl_us ? ps_us - pl_us : pl_us - ps_us;
  uint64_t ppm = maximum == 0U ? UINT64_MAX :
      (difference * UINT64_C(1000000)) / maximum;
  p10_1_store64(&result->ps_elapsed_ticks_low,
                &result->ps_elapsed_ticks_high, ps_elapsed);
  p10_1_store64(&result->pl_elapsed_ticks_low,
                &result->pl_elapsed_ticks_high, pl_elapsed);
  result->timer_error_ppm = ppm > UINT32_MAX ? UINT32_MAX : (uint32_t)ppm;
  result->timer_crosscheck_pass = ppm <= UINT64_C(10000);
}

/*
 * P10.1 owns one autonomous multi-object stream.  The normal P9 helper clears
 * every PL counter at each object boundary, which would make stream-wide
 * physical accounting impossible.  Clear once at stream admission and use
 * this no-clear form for every object in the stream.
 */
static void p10_1_configure_object(volatile p9_mailbox_t *mailbox,
                                   uint32_t command_flags,
                                   uint32_t inject_fault,
                                   uint32_t local_receiver) {
  uint32_t protocol_fault_flags = mailbox->protocol_fault_flags & 0xfffU;
  /* Lane health is live during an autonomous stream.  Preserve a bounded
   * host-injected unavailable mask across later object boundaries; otherwise
   * the next object configuration silently clears the fault before retry
   * migration can be observed.  DATA/ACK drop fields stay zero for command
   * 13 because the legacy mailbox words carrying ACK threshold/outstanding
   * are not physical-drop controls in this command schema. */
  uint32_t physical_fault_injection =
      p9_pl_read(IR_REG_P9_FAULT_INJECTION) &
      ((uint32_t)P10_LANE_MASK << 16);
  physical_fault_injection |=
      (mailbox->lane_unavailable_mask & P10_LANE_MASK) << 16;
  if (inject_fault != 0U) {
    if ((command_flags & P10_1_RUNTIME_FLAG_STALE_SEGMENT) != 0U)
      protocol_fault_flags |= 1U;
    if ((command_flags & P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT) != 0U &&
        local_receiver == 0U)
      protocol_fault_flags |= P10_1_DUPLICATE_PAST_SEQUENCE_FLAG;
  }
  p9_pl_write(IR_REG_P9_OBJECT_CONFIG,
              (mailbox->lane_mask & P10_LANE_MASK) |
                  ((mailbox->rate_select & 3U) << 8) |
                  ((mailbox->direction & 1U) << 16));
  p9_pl_write(IR_REG_P9_LANE_WEIGHTS,
              mailbox->lane_weights &
                  (P10_LANE_COUNT == 4 ? UINT32_MAX : UINT32_C(0xffff)));
  p9_pl_write(IR_REG_P9_SESSION_EPOCH, mailbox->session_epoch);
  p9_pl_write(IR_REG_P9_PATH_EPOCH, mailbox->path_epoch & 0xffffU);
  p9_pl_write(IR_REG_P9_OBJECT_ID, mailbox->object_id);
  p9_pl_write(IR_REG_P9_INITIAL_SEQUENCE,
              mailbox->initial_sequence & 0xffffU);
  p9_pl_write(IR_REG_P9_PROTOCOL_FAULT_FLAGS,
              protocol_fault_flags);
  p9_pl_write(IR_REG_P9_FAULT_INJECTION, physical_fault_injection);
}

typedef struct p10_1_runtime_buffer_slot {
  uint32_t valid;
  uint32_t tx_submitted;
  uint32_t rx_submitted;
  uint32_t ordinal;
  uint32_t bytes;
  uint32_t descriptor_count;
  uint32_t token_base;
  uint8_t *tx_buffer;
  uint8_t *rx_buffer;
} p10_1_runtime_buffer_slot_t;

static int p10_1_prepare_slot(
    volatile p10_1_runtime_result_t *result,
    p10_1_runtime_buffer_slot_t *slot,
    uint32_t slot_index, uint32_t ordinal, uint32_t local_tx,
    uint32_t local_rx, uint32_t hash_on_prepare, uint32_t defer_tx,
    p9_sha256_context_t *input_sha_context, uint32_t *input_crc_state,
    uint64_t *prepare_ticks) {
  uint64_t stream_offset = (uint64_t)ordinal * result->object_bytes;
  uint32_t remaining = result->total_bytes - (uint32_t)stream_offset;
  uint32_t current = remaining < result->object_bytes ?
                         remaining : result->object_bytes;
  uint64_t phase_start;
  int status;

  if ((local_tx | local_rx) == 0U ||
      (defer_tx != 0U && (local_tx == 0U || local_rx == 0U)) ||
      slot->valid != 0U || stream_offset >= result->total_bytes ||
      current == 0U)
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;

  slot->ordinal = ordinal;
  slot->tx_submitted = 0U;
  slot->rx_submitted = 0U;
  slot->bytes = current;
  slot->descriptor_count =
      p10_1_descriptor_count(current, result->descriptor_bytes);
  slot->token_base = result->command_sequence ^ UINT32_C(0xA1000000) ^
                     (ordinal << 8);
  slot->tx_buffer = (uint8_t *)(uintptr_t)
      (P9_TX_BUFFER_BASEADDR + slot_index * result->object_bytes);
  slot->rx_buffer = (uint8_t *)(uintptr_t)
      (P9_RX_BUFFER_BASEADDR + slot_index * result->object_bytes);

  phase_start = p9_time_now();
  p10_1_fill_payload(slot->tx_buffer, current, result->payload_pattern,
                     result->first_object_id, ordinal);
  *prepare_ticks += p9_time_now() - phase_start;
  if (hash_on_prepare != 0U) {
    *input_crc_state =
        p9_crc32_update(*input_crc_state, slot->tx_buffer, current);
    p9_sha256_update(input_sha_context, slot->tx_buffer, current);
  }

  if (local_tx != 0U) {
    p9_cache_flush((UINTPTR)slot->tx_buffer, current);
    if (defer_tx == 0U) {
      status = p10_1_submit_chain(
          1U, (UINTPTR)slot->tx_buffer, current, result->descriptor_bytes,
          slot->token_base, result);
      if (status != P10_1_RUNTIME_STATUS_OK)
        return status;
      slot->tx_submitted = 1U;
    }
  }
  if (local_rx != 0U) {
    memset(slot->rx_buffer, 0x5a ^ (uint8_t)ordinal, current);
    p9_cache_invalidate((UINTPTR)slot->rx_buffer, current);
    status = p10_1_submit_chain(
        0U, (UINTPTR)slot->rx_buffer, current, result->descriptor_bytes,
        slot->token_base, result);
    if (status != P10_1_RUNTIME_STATUS_OK)
      return status;
    slot->rx_submitted = 1U;
  }
  slot->valid = 1U;
  result->objects_submitted++;
  return P10_1_RUNTIME_STATUS_OK;
}

static int p10_1_submit_deferred_tx_slot(
    volatile p10_1_runtime_result_t *result,
    p10_1_runtime_buffer_slot_t *slot) {
  int status;
  if (slot->valid == 0U || slot->tx_submitted != 0U ||
      slot->rx_submitted == 0U || slot->bytes == 0U ||
      slot->descriptor_count == 0U)
    return P10_1_RUNTIME_STATUS_DMA_CHAIN;
  status = p10_1_submit_chain(
      1U, (UINTPTR)slot->tx_buffer, slot->bytes,
      result->descriptor_bytes, slot->token_base, result);
  if (status == P10_1_RUNTIME_STATUS_OK)
    slot->tx_submitted = 1U;
  return status;
}

static int p10_1_validate_stream_args(
    volatile p9_mailbox_t *mailbox,
    volatile p10_1_runtime_result_t *result) {
  uint32_t total = mailbox->object_size;
  uint32_t object_bytes = mailbox->raw_target;
  uint32_t descriptor_bytes = mailbox->raw_spacing_cycles;
  uint32_t dual_mode =
      mailbox->command == P9_COMMAND_P10_5_AUTONOMOUS_DUAL_STREAM;
  uint32_t duration_mode = dual_mode != 0U && mailbox->idle_duration_ms != 0U;
  uint32_t direction_fault_test = mailbox->command_flags &
      P10_5_RUNTIME_FLAG_DIRECTION_FAULT_TEST;
  uint32_t stale_role_epoch_test = mailbox->command_flags &
      P10_5_RUNTIME_FLAG_STALE_ROLE_EPOCH_ONCE;
  uint32_t direction_fault_kind_count =
      (mailbox->drop_data_count != 0U) +
      (mailbox->drop_ack_count != 0U) +
      ((mailbox->command_flags &
        P10_5_RUNTIME_FLAG_ABORT_TARGET_DIRECTION) != 0U) +
      ((mailbox->command_flags &
        P10_5_RUNTIME_FLAG_DMA_TX_BACKPRESSURE) != 0U);
  uint32_t active_mask = mailbox->lane_mask & P10_LANE_MASK;
  uint32_t f2r_mask =
      (mailbox->lane_mask >> P10_5_F2R_MASK_SHIFT) & P10_LANE_MASK;
  uint32_t r2f_mask =
      (mailbox->lane_mask >> P10_5_R2F_MASK_SHIFT) & P10_LANE_MASK;
  uint32_t lane_encoding_valid = dual_mode != 0U ?
      ((mailbox->lane_mask & ~UINT32_C(0x000f0f0f)) == 0U &&
       active_mask != 0U && f2r_mask != 0U && r2f_mask != 0U &&
       (f2r_mask & r2f_mask) == 0U &&
       (f2r_mask | r2f_mask) == active_mask) :
      (mailbox->lane_mask != 0U &&
       (mailbox->lane_mask & ~P10_LANE_MASK) == 0U);
  uint32_t stream_limit = dual_mode != 0U ?
      P10_5_MAX_STREAM_BYTES : P10_1_RUNTIME_MAX_STREAM_BYTES;
  uint32_t descriptor_count;
  uint32_t configured_buffer_count;
  uint32_t active_buffer_count;
  uint32_t abort_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_EXPECT_ABORT_25 |
       P10_1_RUNTIME_FLAG_EXPECT_ABORT_75 |
       P10_1_RUNTIME_FLAG_EXPECT_ABORT_50);
  uint32_t reset_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER |
       P10_1_RUNTIME_FLAG_EXPECT_PL_RESET |
       P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER |
       P10_1_RUNTIME_FLAG_EXPECT_PL_RESET_LOCAL_TX);
  uint32_t injected_fault_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |
       P10_1_RUNTIME_FLAG_STALE_SEGMENT);
  uint32_t service_reset_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_SENDER |
       P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_RECEIVER);
  uint32_t recovery_vector_flags =
      abort_flags | reset_flags | injected_fault_flags;
  if (lane_encoding_valid == 0U ||
      (dual_mode != 0U ? mailbox->direction != 2U :
                        mailbox->direction > 1U) ||
      mailbox->rate_select > 2U ||
      (mailbox->ring_depth != 8U && mailbox->ring_depth != 16U &&
       mailbox->ring_depth != 32U) ||
      mailbox->cache_mode != 1U ||
      total == 0U || object_bytes == 0U ||
      total > stream_limit ||
      object_bytes > total ||
      object_bytes > P10_1_RUNTIME_MAX_OBJECT_BYTES ||
      descriptor_bytes == 0U || descriptor_bytes > object_bytes ||
      (descriptor_bytes & 3U) != 0U ||
      mailbox->timeout_ms == 0U ||
      mailbox->timeout_ms > P10_1_RUNTIME_MAX_TIMEOUT_MS ||
      (reset_flags != 0U &&
       (reset_flags & (reset_flags - 1U)) != 0U) ||
      injected_fault_flags ==
          (P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |
           P10_1_RUNTIME_FLAG_STALE_SEGMENT) ||
      service_reset_flags ==
          (P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_SENDER |
           P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_RECEIVER) ||
      (recovery_vector_flags != 0U &&
       (recovery_vector_flags & (recovery_vector_flags - 1U)) != 0U) ||
      (recovery_vector_flags != 0U && service_reset_flags != 0U))
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;
  if (dual_mode != 0U &&
      (recovery_vector_flags != 0U || service_reset_flags != 0U ||
       ((mailbox->drop_data_count != 0U ||
         mailbox->drop_ack_count != 0U) && direction_fault_test == 0U) ||
       (mailbox->lane_unavailable_mask & ~active_mask) != 0U ||
       mailbox->idle_duration_ms > P10_1_RUNTIME_MAX_TIMEOUT_MS ||
       (direction_fault_test != 0U &&
        (duration_mode != 0U || total != object_bytes ||
         object_bytes != P10_5_INTERNAL_OBJECT_BYTES ||
         direction_fault_kind_count != 1U ||
         mailbox->drop_data_count > 1U ||
         mailbox->drop_ack_count > 1U)) ||
       (direction_fault_test == 0U &&
         (mailbox->command_flags &
          (P10_5_RUNTIME_FLAG_FAULT_TARGET_R2F |
           P10_5_RUNTIME_FLAG_ABORT_TARGET_DIRECTION |
           P10_5_RUNTIME_FLAG_DMA_TX_BACKPRESSURE)) != 0U) ||
        (mailbox->protocol_fault_flags &
         ~IR_P9_PROTOCOL_FAULT_FLAGS_STALE_ROLE_EPOCH_ONCE_MASK) != 0U ||
        (stale_role_epoch_test != 0U &&
         mailbox->protocol_fault_flags != UINT32_C(0x00001000)) ||
        (stale_role_epoch_test == 0U &&
         (mailbox->protocol_fault_flags & UINT32_C(0x00001000)) != 0U) ||
       (duration_mode != 0U &&
        ((uint64_t)total <
         (uint64_t)mailbox->idle_duration_ms * UINT64_C(1000) ||
         mailbox->timeout_ms < mailbox->idle_duration_ms))))
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;
  descriptor_count = p10_1_descriptor_count(object_bytes,
                                             descriptor_bytes);
  if (descriptor_count == 0U || descriptor_count > mailbox->ring_depth)
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;
  result->lane_mask = active_mask;
  result->direction = dual_mode != 0U ? 2U : mailbox->direction;
  result->p10_5_dual_direction_mode = dual_mode;
  result->p10_5_active_mask = dual_mode != 0U ? active_mask : 0U;
  result->p10_5_f2r_mask = dual_mode != 0U ? f2r_mask : 0U;
  result->p10_5_r2f_mask = dual_mode != 0U ? r2f_mask : 0U;
  result->p10_5_local_tx_mask = dual_mode != 0U ?
      (P10_ENDPOINT_ROLE == 1 ? f2r_mask : r2f_mask) : 0U;
  result->p10_5_local_rx_mask = dual_mode != 0U ?
      (P10_ENDPOINT_ROLE == 1 ? r2f_mask : f2r_mask) : 0U;
  result->p10_5_duration_target_ms = duration_mode != 0U ?
      mailbox->idle_duration_ms : 0U;
  result->p10_5_stream_ceiling_bytes = duration_mode != 0U ? total : 0U;
  result->rate_select = mailbox->rate_select;
  result->total_bytes = total;
  result->object_bytes = object_bytes;
  result->descriptor_bytes = descriptor_bytes;
  result->descriptor_count_per_object = descriptor_count;
  result->object_count = (total + object_bytes - 1U) / object_bytes;
  result->ring_depth = mailbox->ring_depth;
  result->descriptor_batch = mailbox->initial_sequence == 0U ?
      descriptor_count : mailbox->initial_sequence;
  configured_buffer_count = mailbox->stale_token == 0U ?
      4U : mailbox->stale_token;
  result->buffer_count = configured_buffer_count;
  result->ack_threshold = dual_mode != 0U ? 32U :
      (mailbox->drop_data_count == 0U ? 32U : mailbox->drop_data_count);
  result->outstanding_frames = dual_mode != 0U ? 32U :
      (mailbox->drop_ack_count == 0U ? 32U : mailbox->drop_ack_count);
  if (direction_fault_test != 0U) {
    result->p10_5_fault_target_direction =
        (mailbox->command_flags &
         P10_5_RUNTIME_FLAG_FAULT_TARGET_R2F) != 0U;
    result->p10_5_fault_test_kind =
        mailbox->drop_data_count != 0U ? 1U :
        (mailbox->drop_ack_count != 0U ? 2U :
         ((mailbox->command_flags &
           P10_5_RUNTIME_FLAG_ABORT_TARGET_DIRECTION) != 0U ? 3U : 4U));
  }
  result->timeout_ms = mailbox->timeout_ms;
  result->session_epoch = mailbox->session_epoch;
  result->path_epoch = mailbox->path_epoch;
  result->first_object_id = mailbox->object_id;
  result->payload_pattern =
      (mailbox->command_flags & P10_1_RUNTIME_FLAG_PATTERN_MASK) >>
      P10_1_RUNTIME_FLAG_PATTERN_SHIFT;
  active_buffer_count = result->buffer_count < result->object_count ?
      result->buffer_count : result->object_count;
  if (result->payload_pattern > P10_1_PATTERN_CORPUS ||
      result->descriptor_batch == 0U ||
      result->descriptor_batch > result->ring_depth ||
      result->descriptor_batch < descriptor_count ||
      result->buffer_count < 2U || result->buffer_count > 16U ||
      result->ack_threshold != 32U ||
      result->outstanding_frames != 32U ||
      (uint64_t)result->object_bytes * result->buffer_count >
          P9_MAX_OBJECT_BYTES ||
      descriptor_count * active_buffer_count > result->ring_depth)
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;
  return P10_1_RUNTIME_STATUS_OK;
}

static int p10_1_snapshot_p10_5(
    volatile p10_1_runtime_result_t *result, uint32_t require_clean) {
  p10_5_direction_snapshot_t snapshot;
  uint32_t last_object_bytes;
  int status;
  if (result->p10_5_dual_direction_mode == 0U)
    return P10_1_RUNTIME_STATUS_OK;
  status = p10_5_snapshot_direction(&snapshot);
  if (status != P9_RUNTIME_OK)
    return P10_1_RUNTIME_STATUS_PL_OBJECT;
  result->p10_5_role_epoch = snapshot.role_epoch & 0xffffU;
  result->p10_5_context_status = snapshot.context_status;
  result->p10_5_local_tx_mask = snapshot.local_tx_mask & P10_LANE_MASK;
  result->p10_5_local_rx_mask = snapshot.local_rx_mask & P10_LANE_MASK;
  result->p10_5_piggyback_ack_tx_count =
      snapshot.piggyback_ack_tx_count;
  result->p10_5_piggyback_ack_rx_count =
      snapshot.piggyback_ack_rx_count;
  result->p10_5_control_only_ack_count =
      snapshot.control_only_ack_count;
  result->p10_5_direction_reject_count =
      snapshot.direction_reject_count;
  result->p10_5_role_epoch_reject_count =
      snapshot.role_epoch_reject_count;
  result->p10_5_tx_bytes = snapshot.tx_bytes;
  result->p10_5_rx_bytes = snapshot.rx_bytes;
  result->p10_5_tx_retry_count = snapshot.tx_retry_count;
  result->p10_5_tx_timeout_count = snapshot.tx_timeout_count;
  result->p10_5_tx_axis_stall = snapshot.tx_axis_stall;
  result->p10_5_rx_axis_stall = snapshot.rx_axis_stall;
  result->p10_5_control_queue_occupancy =
      snapshot.control_queue_occupancy;
  result->p10_5_tx_window_occupancy = snapshot.tx_window_occupancy;
  result->p10_5_rx_window_occupancy = snapshot.rx_window_occupancy;
  result->p10_5_tx_receiver_credit = snapshot.tx_receiver_credit;
  result->p10_5_rx_receiver_credit = snapshot.rx_receiver_credit;
  result->p10_5_ack_tx_bytes = snapshot.ack_tx_bytes;
  result->p10_5_ack_rx_bytes = snapshot.ack_rx_bytes;
  result->p10_5_control_tx_bytes = snapshot.control_tx_bytes;
  result->p10_5_application_committed_bytes =
      snapshot.application_committed_bytes;
  if (require_clean == 0U)
    return P10_1_RUNTIME_STATUS_OK;
  last_object_bytes = result->total_bytes -
      (result->object_count - 1U) * result->object_bytes;
  if (result->p10_5_role_epoch == 0U ||
      result->p10_5_local_tx_mask !=
          (P10_ENDPOINT_ROLE == 1 ? result->p10_5_f2r_mask :
                                   result->p10_5_r2f_mask) ||
      result->p10_5_local_rx_mask !=
          (P10_ENDPOINT_ROLE == 1 ? result->p10_5_r2f_mask :
                                   result->p10_5_f2r_mask) ||
      (snapshot.context_status & UINT32_C(0x00f0)) != UINT32_C(0x0070) ||
      snapshot.tx_bytes != last_object_bytes ||
      snapshot.rx_bytes != last_object_bytes ||
      snapshot.direction_reject_count != 0U ||
      (((result->flags & P10_5_RUNTIME_FLAG_STALE_ROLE_EPOCH_ONCE) != 0U) ?
       (snapshot.role_epoch_reject_count == 0U) :
       (snapshot.role_epoch_reject_count != 0U)))
    return P10_1_RUNTIME_STATUS_PL_OBJECT;
  return P10_1_RUNTIME_STATUS_OK;
}

static void p10_1_runtime_boot_init(void) {
  volatile p10_1_runtime_result_t *result = p10_1_result();
  memset((void *)result, 0, sizeof(*result));
  result->magic = P10_1_RUNTIME_MAGIC;
  result->schema_version = P10_1_RUNTIME_SCHEMA_VERSION;
  result->firmware_build_id = P9_RUNTIME_BUILD_ID;
  result->endpoint_role = P10_ENDPOINT_ROLE;
  result->ps_timer_frequency_hz = COUNTS_PER_SECOND;
  result->pl_timer_frequency_hz = P10_1_RUNTIME_PL_TIMER_HZ;
  p10_1_publish_state(result, P10_1_RUNTIME_SHUTDOWN);
}

static int p10_1_complete_expected_recovery(
    volatile p10_1_runtime_result_t *result, uint32_t flags,
    uint32_t local_tx,
    uint64_t accepted_bytes, uint64_t wire_bytes,
    uint64_t prepare_ticks, uint64_t verify_ticks) {
  uint64_t submitted;
  uint64_t completed;
  uint64_t pl_end;
  int status;

  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_ABORT_OBJECT_MASK);
  result->abort_count++;
  p10_1_store64(&result->ps_end_ticks_low,
                &result->ps_end_ticks_high, p9_time_now());
  pl_end = p10_1_pl_snapshot();
  if (pl_end == UINT64_MAX)
    return P10_1_RUNTIME_STATUS_TIMER;
  p10_1_store64(&result->pl_end_ticks_low,
                &result->pl_end_ticks_high, pl_end);
  p10_1_store64(&result->application_bytes_accepted_low,
                &result->application_bytes_accepted_high, accepted_bytes);
  p10_1_store64(&result->application_bytes_committed_low,
                &result->application_bytes_committed_high, 0U);
  p10_1_store64(&result->wire_bytes_low,
                &result->wire_bytes_high, wire_bytes);
  p10_1_store64(&result->payload_prepare_ticks_low,
                &result->payload_prepare_ticks_high, prepare_ticks);
  p10_1_store64(&result->integrity_verify_ticks_low,
                &result->integrity_verify_ticks_high, verify_ticks);
  p10_1_finalize_timer(result);

  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 7U);
  p10_1_snapshot_perf(result);
  p10_1_snapshot_physical(result, 0U);
  status = p9_shutdown();
  if (status != P9_RUNTIME_OK)
    return P10_1_RUNTIME_STATUS_ABORT_RECOVERY;
  if ((flags & P10_1_RUNTIME_FLAG_EXPECT_PL_RESET) != 0U ||
      ((flags & P10_1_RUNTIME_FLAG_EXPECT_PL_RESET_LOCAL_TX) != 0U &&
       local_tx != 0U)) {
    status = p9_reset_stream_path(result->ring_depth, 1U, 1U);
  } else {
    status = p9_dma_initialize(result->ring_depth, 1U);
  }
  if (status == P9_RUNTIME_OK)
    status = p9_shutdown();
  if (status != P9_RUNTIME_OK)
    return P10_1_RUNTIME_STATUS_ABORT_RECOVERY;

  submitted = p10_1_load64(&result->descriptors_submitted_low,
                           &result->descriptors_submitted_high);
  completed = p10_1_load64(&result->descriptors_completed_low,
                           &result->descriptors_completed_high);
  /*
   * The append-only schema-v1 recovery field records descriptors
   * abandoned by the in-flight test and reclaimed by the verified DMA/PL
   * reset.  A leak is what remains after that reset, not submitted-completed
   * before recovery.
   */
  result->descriptors_reclaimed_by_reset =
      submitted >= completed ? (uint32_t)(submitted - completed) : 0U;
  result->descriptor_leak_count = 0U;
  result->dma_reset_count = g_metrics.dma_reset_count;
  result->pl_reset_count = g_metrics.pl_soft_reset_count;
  result->shutdown_attempt_count = g_metrics.shutdown_attempt_count;
  result->shutdown_verified_count = g_metrics.shutdown_verified_count;
  result->final_pl_status = p9_pl_read(IR_REG_P9_STATUS);
  result->final_phy_status = p9_pl_read(IR_REG_P9_PHY_STATUS);
  result->status = P10_1_RUNTIME_STATUS_OK;
  p10_1_publish_state(result, P10_1_RUNTIME_EXPECTED_ABORT);
  return P10_1_RUNTIME_STATUS_OK;
}

#if 0
/* Superseded in-place by the pipelined implementation below. */
static int p10_1_command_autonomous_stream(
    volatile p9_mailbox_t *mailbox) {
  volatile p10_1_runtime_result_t *result = p10_1_result();
  uint32_t sequence = mailbox->command_sequence;
  uint32_t flags = mailbox->command_flags;
  uint32_t total;
  uint32_t remaining;
  uint32_t object_bytes;
  uint32_t descriptor_bytes;
  uint32_t local_tx;
  uint32_t local_rx;
  int status;
  p9_sha256_context_t input_sha_context;
  p9_sha256_context_t output_sha_context;
  uint32_t input_crc_state = p9_crc32_begin();
  uint32_t output_crc_state = p9_crc32_begin();
  uint8_t input_sha[32];
  uint8_t output_sha[32];
  uint64_t prepare_ticks = 0U;
  uint64_t verify_ticks = 0U;
  uint64_t accepted_bytes = 0U;
  uint64_t committed_bytes = 0U;
  uint64_t wire_bytes = 0U;

  memset((void *)result, 0, sizeof(*result));
  result->magic = P10_1_RUNTIME_MAGIC;
  result->schema_version = P10_1_RUNTIME_SCHEMA_VERSION;
  result->firmware_build_id = P9_RUNTIME_BUILD_ID;
  result->endpoint_role = P10_ENDPOINT_ROLE;
  result->command_sequence = sequence;
  result->flags = flags;
  result->host_command_count = 1U;
  result->ps_timer_frequency_hz = COUNTS_PER_SECOND;
  result->pl_timer_frequency_hz = P10_1_RUNTIME_PL_TIMER_HZ;
  result->first_mismatch_offset = UINT32_MAX;
  p10_1_publish_state(result, P10_1_RUNTIME_INITIALIZING);

  status = p10_1_validate_stream_args(mailbox, result);
  if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
  total = result->total_bytes;
  remaining = total;
  object_bytes = result->object_bytes;
  descriptor_bytes = result->descriptor_bytes;
  local_tx = p9_local_sender(mailbox->direction);
  local_rx = !local_tx;

  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail;
  }
  status = p9_dma_initialize(32U, 1U);
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_DMA_CHAIN;
    goto stream_fail;
  }
  p9_cache_enable();
  g_metrics.cache_enabled_exercised = 1U;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail;
  }
  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 8U);
  p9_pl_write(P10_1_PERF_SNAPSHOT_CONTROL_OFFSET, 2U);
  usleep(10U);
  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 3U);
  p10_1_snapshot_physical(result, 1U);
  p9_sha256_init(&input_sha_context);
  p9_sha256_init(&output_sha_context);

  for (uint32_t ordinal = 0U; ordinal < result->object_count; ++ordinal) {
    uint32_t current = remaining < object_bytes ? remaining : object_bytes;
    uint32_t descriptor_count =
        p10_1_descriptor_count(current, descriptor_bytes);
    uint32_t token_base = sequence ^ UINT32_C(0xA1000000) ^
                          (ordinal << 8);
    uint8_t *tx_buffer = (uint8_t *)(uintptr_t)P9_TX_BUFFER_BASEADDR;
    uint8_t *rx_buffer = (uint8_t *)(uintptr_t)P9_RX_BUFFER_BASEADDR;
    uint64_t phase_start = p9_time_now();
    p10_1_publish_state(result, P10_1_RUNTIME_PRIMING);
    p10_1_fill_payload(tx_buffer, current, result->payload_pattern,
                       mailbox->object_id, ordinal);
    prepare_ticks += p9_time_now() - phase_start;
    input_crc_state = p9_crc32_update(input_crc_state, tx_buffer, current);
    p9_sha256_update(&input_sha_context, tx_buffer, current);
    if (local_rx != 0U)
      memset(rx_buffer, 0x5a ^ (uint8_t)ordinal, current);
    p9_cache_flush((UINTPTR)tx_buffer, current);
    if (local_rx != 0U)
      p9_cache_invalidate((UINTPTR)rx_buffer, current);

    mailbox->object_id = result->first_object_id + ordinal;
    mailbox->initial_sequence = 0U;
    p9_configure_object(mailbox);
    if (local_rx != 0U) {
      status = p10_1_submit_chain(0U, (UINTPTR)rx_buffer, current,
                                  descriptor_bytes, token_base, result);
      if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
      if (ordinal != 0U) {
        status = p10_1_send_signal(mailbox->direction,
                                   mailbox->lane_mask, 30000U, result);
        if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
      }
      p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
      if (ordinal == 0U) {
        p10_1_store64(&result->ps_start_ticks_low,
                      &result->ps_start_ticks_high, p9_time_now());
        {
          uint64_t pl_start = p10_1_pl_snapshot();
          if (pl_start == UINT64_MAX) {
            status = P10_1_RUNTIME_STATUS_TIMER;
            goto stream_fail;
          }
          p10_1_store64(&result->pl_start_ticks_low,
                        &result->pl_start_ticks_high, pl_start);
        }
        p10_1_publish_state(result, P10_1_RUNTIME_PRIMED);
      } else {
        p10_1_publish_state(result, P10_1_RUNTIME_RUNNING);
      }
    } else {
      if (ordinal != 0U) {
        status = p10_1_wait_signal(mailbox->lane_mask, 30000U, result);
        if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
      }
      p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
      if (ordinal == 0U) {
        p10_1_store64(&result->ps_start_ticks_low,
                      &result->ps_start_ticks_high, p9_time_now());
        {
          uint64_t pl_start = p10_1_pl_snapshot();
          if (pl_start == UINT64_MAX) {
            status = P10_1_RUNTIME_STATUS_TIMER;
            goto stream_fail;
          }
          p10_1_store64(&result->pl_start_ticks_low,
                        &result->pl_start_ticks_high, pl_start);
        }
      }
      status = p10_1_submit_chain(1U, (UINTPTR)tx_buffer, current,
                                  descriptor_bytes, token_base, result);
      if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
      p10_1_publish_state(result, P10_1_RUNTIME_RUNNING);
    }
    result->objects_submitted++;

    status = p10_1_collect_chain(local_tx, descriptor_count, token_base,
                                  mailbox->timeout_ms, current, result);
    if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
    result->objects_completed++;
    accepted_bytes += current;
    wire_bytes += current;

    if (local_rx != 0U) {
      uint32_t object_input_crc;
      uint32_t object_output_crc;
      uint8_t object_input_sha[32];
      uint8_t object_output_sha[32];
      p10_1_publish_state(result, P10_1_RUNTIME_VERIFYING);
      phase_start = p9_time_now();
      p9_cache_invalidate((UINTPTR)rx_buffer, current);
      object_input_crc = p9_crc32(tx_buffer, current);
      object_output_crc = p9_crc32(rx_buffer, current);
      p9_sha256(tx_buffer, current, object_input_sha);
      p9_sha256(rx_buffer, current, object_output_sha);
      if (object_input_crc != object_output_crc) {
        result->crc_bad_count++;
        status = P10_1_RUNTIME_STATUS_INTEGRITY;
      }
      if (memcmp(object_input_sha, object_output_sha,
                 sizeof(object_input_sha)) != 0) {
        result->sha_mismatch_count++;
        status = P10_1_RUNTIME_STATUS_INTEGRITY;
      }
      for (uint32_t index = 0U;
           index < current && status == P10_1_RUNTIME_STATUS_OK; ++index) {
        if (tx_buffer[index] != rx_buffer[index]) {
          result->first_mismatch_offset =
              ordinal * object_bytes + index;
          result->integrity_error_count++;
          status = P10_1_RUNTIME_STATUS_INTEGRITY;
        }
      }
      if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
      output_crc_state =
          p9_crc32_update(output_crc_state, rx_buffer, current);
      p9_sha256_update(&output_sha_context, rx_buffer, current);
      verify_ticks += p9_time_now() - phase_start;
      committed_bytes += current;
      result->atomic_commit_count++;
      if (ordinal + 1U == result->object_count) {
        result->remote_commit_confirmed = 1U;
        p10_1_store64(&result->ps_end_ticks_low,
                      &result->ps_end_ticks_high, p9_time_now());
        {
          uint64_t pl_end = p10_1_pl_snapshot();
          if (pl_end == UINT64_MAX) {
            status = P10_1_RUNTIME_STATUS_TIMER;
            goto stream_fail;
          }
          p10_1_store64(&result->pl_end_ticks_low,
                        &result->pl_end_ticks_high, pl_end);
        }
      }
      status = p10_1_send_signal(mailbox->direction,
                                 mailbox->lane_mask, 30000U, result);
      if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
    } else if (ordinal + 1U == result->object_count) {
      status = p10_1_wait_signal(mailbox->lane_mask, 30000U, result);
      if (status != P10_1_RUNTIME_STATUS_OK) goto stream_fail;
      result->remote_commit_confirmed = 1U;
      committed_bytes = total;
      result->atomic_commit_count = result->object_count;
      p10_1_store64(&result->ps_end_ticks_low,
                    &result->ps_end_ticks_high, p9_time_now());
      {
        uint64_t pl_end = p10_1_pl_snapshot();
        if (pl_end == UINT64_MAX) {
          status = P10_1_RUNTIME_STATUS_TIMER;
          goto stream_fail;
        }
        p10_1_store64(&result->pl_end_ticks_low,
                      &result->pl_end_ticks_high, pl_end);
      }
    }
    remaining -= current;
  }

  if (remaining != 0U || accepted_bytes != total ||
      committed_bytes != total ||
      result->objects_completed != result->object_count) {
    status = P10_1_RUNTIME_STATUS_REMOTE_COMMIT;
    goto stream_fail;
  }
  p9_sha256_final(&input_sha_context, input_sha);
  result->input_crc32 = p9_crc32_end(input_crc_state);
  p10_1_copy_digest_words(result->input_sha256, input_sha);
  if (local_rx != 0U) {
    p9_sha256_final(&output_sha_context, output_sha);
    result->output_crc32 = p9_crc32_end(output_crc_state);
    p10_1_copy_digest_words(result->output_sha256, output_sha);
    if (result->input_crc32 != result->output_crc32 ||
        memcmp(input_sha, output_sha, sizeof(input_sha)) != 0) {
      result->integrity_error_count++;
      status = P10_1_RUNTIME_STATUS_INTEGRITY;
      goto stream_fail;
    }
  }
  p10_1_store64(&result->application_bytes_accepted_low,
                &result->application_bytes_accepted_high, accepted_bytes);
  p10_1_store64(&result->application_bytes_committed_low,
                &result->application_bytes_committed_high, committed_bytes);
  p10_1_store64(&result->wire_bytes_low,
                &result->wire_bytes_high, wire_bytes);
  p10_1_store64(&result->payload_prepare_ticks_low,
                &result->payload_prepare_ticks_high, prepare_ticks);
  p10_1_store64(&result->integrity_verify_ticks_low,
                &result->integrity_verify_ticks_high, verify_ticks);
  p10_1_finalize_timer(result);
  if (result->timer_crosscheck_pass == 0U) {
    status = P10_1_RUNTIME_STATUS_TIMER;
    goto stream_fail;
  }
  result->descriptor_leak_count =
      p10_1_load64(&result->descriptors_submitted_low,
                   &result->descriptors_submitted_high) -
      p10_1_load64(&result->descriptors_completed_low,
                   &result->descriptors_completed_high);
  result->retry_exhausted_count =
      p9_pl_read(IR_REG_P9_TX_RETRY_EXHAUSTED_COUNT);
  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 6U);
  p10_1_snapshot_perf(result);
  p10_1_snapshot_physical(result, 0U);
  status = p9_shutdown();
  result->shutdown_attempt_count = g_metrics.shutdown_attempt_count;
  result->shutdown_verified_count = g_metrics.shutdown_verified_count;
  result->final_pl_status = p9_pl_read(IR_REG_P9_STATUS);
  result->final_phy_status = p9_pl_read(IR_REG_P9_PHY_STATUS);
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail;
  }
  result->status = P10_1_RUNTIME_STATUS_OK;
  p10_1_publish_state(result, P10_1_RUNTIME_COMPLETE);
  return P9_RUNTIME_OK;

stream_fail:
  result->status = (uint32_t)status;
  result->last_error_detail = result->last_error_detail == 0U ?
      p9_pl_read(IR_REG_P9_OBJECT_ERROR) : result->last_error_detail;
  result->descriptor_leak_count =
      p10_1_load64(&result->descriptors_submitted_low,
                   &result->descriptors_submitted_high) -
      p10_1_load64(&result->descriptors_completed_low,
                   &result->descriptors_completed_high);
  (void)p9_shutdown();
  (void)p9_reset_stream_path(32U, 1U, 1U);
  (void)p9_shutdown();
  result->shutdown_attempt_count = g_metrics.shutdown_attempt_count;
  result->shutdown_verified_count = g_metrics.shutdown_verified_count;
  result->final_pl_status = p9_pl_read(IR_REG_P9_STATUS);
  result->final_phy_status = p9_pl_read(IR_REG_P9_PHY_STATUS);
  p10_1_publish_state(result, P10_1_RUNTIME_FAULT);
  return P9_RUNTIME_PL_OBJECT;
}
#endif

static int p10_1_command_autonomous_stream(
    volatile p9_mailbox_t *mailbox) {
  volatile p10_1_runtime_result_t *result = p10_1_result();
  p10_1_runtime_buffer_slot_t slots[16];
  p9_sha256_context_t input_sha_context;
  p9_sha256_context_t output_sha_context;
  uint8_t input_sha[32];
  uint8_t output_sha[32];
  uint32_t input_crc_state = p9_crc32_begin();
  uint32_t output_crc_state = p9_crc32_begin();
  uint32_t sequence = mailbox->command_sequence;
  uint32_t flags = mailbox->command_flags;
  uint32_t dual_mode;
  uint32_t duration_mode;
  uint32_t local_tx;
  uint32_t local_rx;
  uint32_t initial_slot_count;
  uint32_t next_prepare_ordinal;
  uint32_t next_object_prestarted = 0U;
  uint32_t duration_stop = 0U;
  uint32_t role_epoch = 0U;
  uint32_t recovery_flags;
  uint32_t recovery_ordinal = UINT32_MAX;
  uint32_t direction_fault_test;
  uint32_t direction_fault_target = 0U;
  uint32_t local_p10_5_direction =
      P10_ENDPOINT_ROLE == 2 ? 1U : 0U;
  uint32_t injected_fault_before = 0U;
  uint64_t accepted_bytes = 0U;
  uint64_t committed_bytes = 0U;
  uint64_t wire_bytes = 0U;
  uint64_t prepare_ticks = 0U;
  uint64_t verify_ticks = 0U;
  uint64_t duration_deadline = 0U;
  uint64_t object_started_ticks = 0U;
  uint64_t maximum_object_ticks = 0U;
  int status;

  memset((void *)result, 0, sizeof(*result));
  memset(slots, 0, sizeof(slots));
  result->magic = P10_1_RUNTIME_MAGIC;
  result->schema_version = P10_1_RUNTIME_SCHEMA_VERSION;
  result->firmware_build_id = P9_RUNTIME_BUILD_ID;
  result->endpoint_role = P10_ENDPOINT_ROLE;
  result->command_sequence = sequence;
  result->flags = flags;
  result->host_command_count = 1U;
  result->ps_timer_frequency_hz = COUNTS_PER_SECOND;
  result->pl_timer_frequency_hz = P10_1_RUNTIME_PL_TIMER_HZ;
  result->first_mismatch_offset = UINT32_MAX;
  p10_1_publish_state(result, P10_1_RUNTIME_INITIALIZING);

  status = p10_1_validate_stream_args(mailbox, result);
  if (status != P10_1_RUNTIME_STATUS_OK)
    goto stream_fail_v2;
  dual_mode = result->p10_5_dual_direction_mode;
  duration_mode = result->p10_5_duration_target_ms != 0U;
  direction_fault_test = flags & P10_5_RUNTIME_FLAG_DIRECTION_FAULT_TEST;
  if (direction_fault_test != 0U)
    direction_fault_target =
        (flags & P10_5_RUNTIME_FLAG_FAULT_TARGET_R2F) != 0U;
  local_tx = dual_mode != 0U ? 1U : p9_local_sender(mailbox->direction);
  local_rx = dual_mode != 0U ? 1U : !local_tx;
  recovery_flags = flags &
      (P10_1_RUNTIME_FLAG_EXPECT_ABORT_25 |
       P10_1_RUNTIME_FLAG_EXPECT_ABORT_75 |
       P10_1_RUNTIME_FLAG_EXPECT_ABORT_50 |
       P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER |
       P10_1_RUNTIME_FLAG_EXPECT_PL_RESET |
       P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |
       P10_1_RUNTIME_FLAG_STALE_SEGMENT |
       P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER |
       P10_1_RUNTIME_FLAG_EXPECT_PL_RESET_LOCAL_TX);
  /*
   * Duplicate/stale protocol stimuli must use object 0.  The host has already
   * observed the receiving endpoint in PRIMED with object 0 active before it
   * publishes the sender command.  A later recovery object deliberately has
   * no per-object optical-ready exchange; selecting it here lets a faster
   * sender consume the bounded corrupt-attempt budget before the receiver has
   * changed object identity, so the intended protocol counter is never
   * observable.  Keeping these diagnostic-only stimuli on the host-primed
   * object removes that race without adding a normal-stream handshake or
   * changing any TX safety path.
   */
  if ((recovery_flags &
       (P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |
        P10_1_RUNTIME_FLAG_STALE_SEGMENT)) != 0U) {
    recovery_ordinal = 0U;
  } else if ((recovery_flags &
              P10_1_RUNTIME_FLAG_EXPECT_ABORT_25) != 0U) {
    recovery_ordinal = result->object_count / 4U;
  } else if ((recovery_flags &
              P10_1_RUNTIME_FLAG_EXPECT_ABORT_50) != 0U) {
    recovery_ordinal = result->object_count / 2U;
  } else if ((recovery_flags &
              P10_1_RUNTIME_FLAG_EXPECT_ABORT_75) != 0U) {
    recovery_ordinal =
        (uint32_t)(((uint64_t)result->object_count * 3U) / 4U);
  } else if (recovery_flags != 0U) {
    recovery_ordinal = result->object_count / 2U;
  }
  if (recovery_flags != 0U &&
      recovery_ordinal >= result->object_count)
    recovery_ordinal = result->object_count - 1U;

  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail_v2;
  }
  status = p9_dma_initialize(result->ring_depth, 1U);
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_DMA_CHAIN;
    goto stream_fail_v2;
  }
  if (dual_mode != 0U) {
    status = p10_5_query_dual_direction_caps();
    if (status == P9_RUNTIME_OK)
      status = p10_5_clear_direction_errors();
    if (status == P9_RUNTIME_OK)
      status = p10_5_stage_role_masks(
          result->p10_5_active_mask, result->p10_5_f2r_mask,
          result->p10_5_r2f_mask);
    if (status == P9_RUNTIME_OK)
      status = p10_5_commit_role_masks(
          result->p10_5_active_mask, result->p10_5_f2r_mask,
          result->p10_5_r2f_mask, &role_epoch);
    if (status == P9_RUNTIME_OK)
      result->p10_5_role_epoch = role_epoch;
    if (status != P9_RUNTIME_OK) {
      status = P10_1_RUNTIME_STATUS_PL_OBJECT;
      goto stream_fail_v2;
    }
  }
  p9_cache_enable();
  g_metrics.cache_enabled_exercised = 1U;
  /*
   * Duration mode measures the complete TFDU-active interval, not merely the
   * payload loop.  Start the deadline before receiver-enable/arm so buffer
   * priming and the mandatory 500-us startup delay are inside the configured
   * maximum.  The matching shutdown is issued at the deadline before digest
   * finalization or descriptor cleanup can extend module operation.
   */
  if (duration_mode != 0U) {
    uint64_t pl_start;
    p10_1_store64(&result->ps_start_ticks_low,
                  &result->ps_start_ticks_high, p9_time_now());
    duration_deadline =
        p10_1_load64(&result->ps_start_ticks_low,
                     &result->ps_start_ticks_high) +
        ((uint64_t)result->p10_5_duration_target_ms *
         (uint64_t)COUNTS_PER_SECOND) / UINT64_C(1000);
    pl_start = p10_1_pl_snapshot();
    if (pl_start == UINT64_MAX) {
      status = P10_1_RUNTIME_STATUS_TIMER;
      goto stream_fail_v2;
    }
    p10_1_store64(&result->pl_start_ticks_low,
                  &result->pl_start_ticks_high, pl_start);
  }
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail_v2;
  }
  /*
   * Stream-wide observability starts from one clear.  Object configuration
   * below deliberately never clears these counters.
   */
  if (dual_mode == 0U) {
    p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
    /* A new command is a new fault-lifecycle boundary.  Clear any unavailable
     * mask left by the preceding command before object 0; a later live XSDB
     * injection is then deliberately retained by p10_1_configure_object(). */
    p9_pl_write(IR_REG_P9_FAULT_INJECTION,
                (mailbox->lane_unavailable_mask & P10_LANE_MASK) << 16);
  } else {
    p9_pl_write(IR_REG_P9_FAULT_INJECTION,
                (mailbox->lane_unavailable_mask &
                 result->p10_5_active_mask) << 16);
  }
  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 8U);
  p9_pl_write(P10_1_PERF_SNAPSHOT_CONTROL_OFFSET, 2U);
  usleep(10U);
  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 3U);
  p10_1_snapshot_physical(result, 1U);
  p9_sha256_init(&input_sha_context);
  p9_sha256_init(&output_sha_context);

  /*
   * Prime a real multi-buffer queue before the first object.  With the Goal
   * configuration this is four 256-KiB buffers, four descriptors per object,
   * a 32-entry SG ring, and BdRingToHw batches of up to eight.
   */
  initial_slot_count = result->buffer_count < result->object_count ?
      result->buffer_count : result->object_count;
  p10_1_publish_state(result, P10_1_RUNTIME_PRIMING);
  for (uint32_t ordinal = 0U; ordinal < initial_slot_count; ++ordinal) {
    status = p10_1_prepare_slot(
        result, &slots[ordinal], ordinal, ordinal, local_tx, local_rx,
        duration_mode == 0U, dual_mode != 0U,
        &input_sha_context, &input_crc_state, &prepare_ticks);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
  }
  if (dual_mode != 0U) {
    uint32_t held_descriptors = 0U;
    for (uint32_t index = 0U; index < initial_slot_count; ++index) {
      if (slots[index].valid == 0U || slots[index].tx_submitted != 0U ||
          slots[index].rx_submitted == 0U) {
        status = P10_1_RUNTIME_STATUS_DMA_CHAIN;
        goto stream_fail_v2;
      }
      held_descriptors += slots[index].descriptor_count;
    }
    result->p10_5_launch_tx_descriptors_held = held_descriptors;
  }
  next_prepare_ordinal = initial_slot_count;

  for (uint32_t ordinal = 0U; ordinal < result->object_count; ++ordinal) {
    uint32_t slot_index = ordinal % result->buffer_count;
    p10_1_runtime_buffer_slot_t *slot = &slots[slot_index];

    if (slot->valid == 0U || slot->ordinal != ordinal) {
      status = P10_1_RUNTIME_STATUS_DMA_CHAIN;
      goto stream_fail_v2;
    }
    if (next_object_prestarted == 0U) {
      mailbox->object_id = result->first_object_id + ordinal;
      mailbox->initial_sequence = 0U;
      if (ordinal == recovery_ordinal && local_rx != 0U) {
        if ((recovery_flags & P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT) != 0U)
          injected_fault_before =
              p9_pl_read(IR_REG_P9_RX_DUPLICATE_COUNT);
        else if ((recovery_flags & P10_1_RUNTIME_FLAG_STALE_SEGMENT) != 0U)
          injected_fault_before =
              p9_pl_read(IR_REG_P9_RX_STALE_SESSION_COUNT);
      }
      if (dual_mode != 0U) {
        status = p10_5_program_dual_object_context(
            mailbox, result->p10_5_active_mask, 1U);
        if (status != P9_RUNTIME_OK) {
          status = P10_1_RUNTIME_STATUS_PL_OBJECT;
          goto stream_fail_v2;
        }
      } else {
        p10_1_configure_object(mailbox, flags,
                               ordinal == recovery_ordinal, local_rx);
      }
      /*
       * P10.1R removes the per-object optical ready round trip.  The receiver
       * opens the next object immediately; the sender uses one deterministic
       * local lead interval.  No TFDU control pulse is exchanged and this
       * interval does not depend on object verification or host traffic.
       */
      if (ordinal != 0U && local_tx != 0U)
        usleep(2000U);
      if (dual_mode != 0U) {
        status = p10_5_start_direction_stream();
        if (status != P9_RUNTIME_OK) {
          status = P10_1_RUNTIME_STATUS_PL_OBJECT;
          goto stream_fail_v2;
        }
        object_started_ticks = p9_time_now();
        if (ordinal == 0U) {
          uint32_t context_status =
              p9_pl_read(IR_REG_P10_5_CONTEXT_STATUS);
          result->p10_5_launch_prestart_context_status = context_status;
          result->p10_5_launch_rx_object_prestarted =
              (context_status & UINT32_C(0x0000008f)) ==
                      UINT32_C(0x00000009) ?
                  1U : 0U;
          if (result->p10_5_launch_rx_object_prestarted == 0U ||
              result->p10_5_launch_tx_descriptors_held == 0U) {
            status = P10_1_RUNTIME_STATUS_PL_OBJECT;
            goto stream_fail_v2;
          }
          status = p10_5_wait_for_paired_launch_release(mailbox, result);
          if (status != P10_1_RUNTIME_STATUS_OK)
            goto stream_fail_v2;
          for (uint32_t index = 0U; index < initial_slot_count; ++index) {
            status = p10_1_submit_deferred_tx_slot(result, &slots[index]);
            if (status != P10_1_RUNTIME_STATUS_OK)
              goto stream_fail_v2;
            result->p10_5_launch_tx_descriptors_released +=
                slots[index].descriptor_count;
          }
          if (result->p10_5_launch_tx_descriptors_released !=
              result->p10_5_launch_tx_descriptors_held) {
            status = P10_1_RUNTIME_STATUS_DMA_CHAIN;
            goto stream_fail_v2;
          }
        }
      } else {
        p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
        object_started_ticks = p9_time_now();
      }

      if (direction_fault_test != 0U && ordinal == 0U &&
          (flags & P10_5_RUNTIME_FLAG_DMA_TX_BACKPRESSURE) != 0U &&
          local_p10_5_direction == direction_fault_target) {
        uint32_t stall_before = p9_pl_read(IR_REG_P10_5_TX_AXIS_STALL);
        result->p10_5_diagnostic_status_before =
            p9_pl_read(IR_REG_P10_5_DIAGNOSTIC_STATUS);
        p9_pl_write(IR_REG_P10_5_DIAGNOSTIC_CONTROL,
                    UINT32_C(0xD1A60001));
        if ((p9_pl_read(IR_REG_P10_5_DIAGNOSTIC_STATUS) & 1U) == 0U) {
          status = P10_1_RUNTIME_STATUS_PL_OBJECT;
          goto stream_fail_v2;
        }
        usleep(50000U);
        p9_pl_write(IR_REG_P10_5_DIAGNOSTIC_CONTROL, 0U);
        result->p10_5_diagnostic_status_after =
            p9_pl_read(IR_REG_P10_5_DIAGNOSTIC_STATUS);
        result->p10_5_diagnostic_stall_delta =
            p9_pl_read(IR_REG_P10_5_TX_AXIS_STALL) - stall_before;
        if ((result->p10_5_diagnostic_status_after & 1U) != 0U ||
            result->p10_5_diagnostic_stall_delta == 0U) {
          status = P10_1_RUNTIME_STATUS_PL_OBJECT;
          goto stream_fail_v2;
        }
      }
    } else {
      next_object_prestarted = 0U;
    }
    if (ordinal == 0U) {
      if (duration_mode == 0U) {
        uint64_t pl_start;
        p10_1_store64(&result->ps_start_ticks_low,
                      &result->ps_start_ticks_high, p9_time_now());
        pl_start = p10_1_pl_snapshot();
        if (pl_start == UINT64_MAX) {
          status = P10_1_RUNTIME_STATUS_TIMER;
          goto stream_fail_v2;
        }
        p10_1_store64(&result->pl_start_ticks_low,
                      &result->pl_start_ticks_high, pl_start);
      }
      p10_1_publish_state(
          result, dual_mode != 0U ? P10_1_RUNTIME_RUNNING :
              (local_rx != 0U ?
                   P10_1_RUNTIME_PRIMED : P10_1_RUNTIME_RUNNING));
    } else {
      p10_1_publish_state(result, P10_1_RUNTIME_RUNNING);
    }

    /*
     * Once object N starts, the buffer released by N-1 is filled and queued
     * for N+(buffer_count-1).  Generation/cache work therefore overlaps the
     * active PL/PHY transfer instead of introducing an object-boundary drain.
     */
    if (ordinal != 0U && next_prepare_ordinal < result->object_count) {
      uint32_t refill_index = (ordinal - 1U) % result->buffer_count;
      status = p10_1_prepare_slot(
          result, &slots[refill_index], refill_index,
          next_prepare_ordinal, local_tx, local_rx,
          duration_mode == 0U, 0U, &input_sha_context,
          &input_crc_state, &prepare_ticks);
      if (status != P10_1_RUNTIME_STATUS_OK)
        goto stream_fail_v2;
      next_prepare_ordinal++;
    }

    /*
     * Abort/reset vectors deliberately interrupt an active object.  They are
     * separate commands and never publish an application commit.
     */
    if (ordinal == recovery_ordinal) {
      uint64_t deadline = p9_deadline_ms(250U);
      while (p9_time_now() < deadline) {
        if ((p9_pl_read(IR_REG_P9_STATUS) &
             P9_STATUS_OBJECT_ACTIVE) != 0U)
          break;
        usleep(P9_POLL_DELAY_US);
      }
      if ((recovery_flags &
           (P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |
            P10_1_RUNTIME_FLAG_STALE_SEGMENT)) != 0U) {
        deadline = p9_deadline_ms(250U);
        while (p9_time_now() < deadline) {
          uint32_t observed = 0U;
          if (local_rx != 0U &&
              (recovery_flags &
               P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT) != 0U) {
            observed =
                p9_pl_read(IR_REG_P9_RX_DUPLICATE_COUNT) -
                injected_fault_before;
          } else if (local_rx != 0U &&
                     (recovery_flags &
                      P10_1_RUNTIME_FLAG_STALE_SEGMENT) != 0U) {
            observed =
                p9_pl_read(IR_REG_P9_RX_STALE_SESSION_COUNT) -
                injected_fault_before;
          }
          if (observed != 0U) {
            result->injected_fault_observed_count = observed;
            break;
          }
          usleep(P9_POLL_DELAY_US);
        }
      } else {
        usleep(1000U);
      }
      status = p10_1_complete_expected_recovery(
          result, recovery_flags, local_tx, accepted_bytes, wire_bytes,
          prepare_ticks, verify_ticks);
      if (status != P10_1_RUNTIME_STATUS_OK)
        goto stream_fail_v2;
      return P9_RUNTIME_OK;
    }

    if (direction_fault_test != 0U && ordinal == 0U &&
        (flags & P10_5_RUNTIME_FLAG_ABORT_TARGET_DIRECTION) != 0U) {
      uint32_t local_tx_is_affected =
          local_p10_5_direction == direction_fault_target;
      uint32_t unaffected_tx_direction = local_tx_is_affected ? 0U : 1U;
      uint64_t submitted;
      uint64_t completed;

      /* Let both directions make directly observable progress, then abort
       * only the selected logical context. The opposite DMA chain, L2 window,
       * ACK path, and optical lane group remain live until completion. */
      usleep(10000U);
      status = p10_5_abort_direction_stream(
          local_tx_is_affected, !local_tx_is_affected);
      if (status != P9_RUNTIME_OK) {
        status = P10_1_RUNTIME_STATUS_PL_OBJECT;
        goto stream_fail_v2;
      }
      usleep(10U);
      if ((p9_pl_read(IR_REG_P10_5_CONTEXT_STATUS) &
           (local_tx_is_affected ? 2U : 4U)) == 0U) {
        status = P10_1_RUNTIME_STATUS_PL_OBJECT;
        goto stream_fail_v2;
      }
      status = p10_1_collect_chain(
          unaffected_tx_direction, slot->descriptor_count, slot->token_base,
          mailbox->timeout_ms, slot->bytes, result);
      if (status != P10_1_RUNTIME_STATUS_OK)
        goto stream_fail_v2;

      if (local_tx_is_affected != 0U) {
        size_t mismatch;
        p9_cache_invalidate((UINTPTR)slot->rx_buffer, slot->bytes);
        output_crc_state = p9_crc32_update_compare(
            output_crc_state, slot->tx_buffer, slot->rx_buffer,
            slot->bytes, &mismatch);
        if (mismatch != SIZE_MAX) {
          result->first_mismatch_offset = (uint32_t)mismatch;
          result->integrity_error_count++;
          status = P10_1_RUNTIME_STATUS_INTEGRITY;
          goto stream_fail_v2;
        }
      }
      result->objects_completed = 1U;
      result->p10_5_unaffected_progress_bytes = slot->bytes;
      result->p10_5_affected_commit_count = 0U;
      result->p10_5_fault_recovery_pass = 1U;
      accepted_bytes = slot->bytes;
      committed_bytes = slot->bytes;
      wire_bytes = slot->bytes;
      result->atomic_commit_count = 1U;
      result->remote_commit_confirmed = 1U;
      p10_1_store64(&result->ps_end_ticks_low,
                    &result->ps_end_ticks_high, p9_time_now());
      {
        uint64_t pl_end = p10_1_pl_snapshot();
        if (pl_end == UINT64_MAX) {
          status = P10_1_RUNTIME_STATUS_TIMER;
          goto stream_fail_v2;
        }
        p10_1_store64(&result->pl_end_ticks_low,
                      &result->pl_end_ticks_high, pl_end);
      }
      p10_1_store64(&result->application_bytes_accepted_low,
                    &result->application_bytes_accepted_high, accepted_bytes);
      p10_1_store64(&result->application_bytes_committed_low,
                    &result->application_bytes_committed_high, committed_bytes);
      p10_1_store64(&result->wire_bytes_low,
                    &result->wire_bytes_high, wire_bytes);
      p10_1_store64(&result->payload_prepare_ticks_low,
                    &result->payload_prepare_ticks_high, prepare_ticks);
      p10_1_store64(&result->integrity_verify_ticks_low,
                    &result->integrity_verify_ticks_high, verify_ticks);
      p10_1_finalize_timer(result);
      p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 6U);
      p10_1_snapshot_perf(result);
      p10_1_snapshot_physical(result, 0U);
      (void)p10_1_snapshot_p10_5(result, 0U);
      status = p9_shutdown();
      if (status == P9_RUNTIME_OK)
        status = p9_reset_stream_path(result->ring_depth, 1U, 1U);
      if (status == P9_RUNTIME_OK)
        status = p9_shutdown();
      submitted = p10_1_load64(&result->descriptors_submitted_low,
                               &result->descriptors_submitted_high);
      completed = p10_1_load64(&result->descriptors_completed_low,
                               &result->descriptors_completed_high);
      result->descriptors_reclaimed_by_reset =
          submitted >= completed ? (uint32_t)(submitted - completed) : 0U;
      result->descriptor_leak_count = 0U;
      result->dma_reset_count = g_metrics.dma_reset_count;
      result->pl_reset_count = g_metrics.pl_soft_reset_count;
      result->shutdown_attempt_count = g_metrics.shutdown_attempt_count;
      result->shutdown_verified_count = g_metrics.shutdown_verified_count;
      result->final_pl_status = p9_pl_read(IR_REG_P9_STATUS);
      result->final_phy_status = p9_pl_read(IR_REG_P9_PHY_STATUS);
      if (status != P9_RUNTIME_OK) {
        status = P10_1_RUNTIME_STATUS_ABORT_RECOVERY;
        goto stream_fail_v2;
      }
      result->status = P10_1_RUNTIME_STATUS_OK;
      p10_1_publish_state(result, P10_1_RUNTIME_COMPLETE);
      return P9_RUNTIME_OK;
    }

    if ((local_tx != 0U && slot->tx_submitted == 0U) ||
        (local_rx != 0U && slot->rx_submitted == 0U)) {
      status = P10_1_RUNTIME_STATUS_DMA_CHAIN;
      goto stream_fail_v2;
    }
    status = p10_1_collect_chain(
        local_tx, slot->descriptor_count, slot->token_base,
        mailbox->timeout_ms, slot->bytes, result);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
    if (dual_mode != 0U) {
      status = p10_1_collect_chain(
          0U, slot->descriptor_count, slot->token_base,
          mailbox->timeout_ms, slot->bytes, result);
      if (status != P10_1_RUNTIME_STATUS_OK)
        goto stream_fail_v2;
    }
    result->objects_completed++;
    accepted_bytes += slot->bytes;
    wire_bytes += slot->bytes;
    if (duration_mode != 0U) {
      uint64_t now = p9_time_now();
      uint64_t object_ticks = now - object_started_ticks;
      uint64_t stop_guard;
      if (object_ticks > maximum_object_ticks)
        maximum_object_ticks = object_ticks;
      input_crc_state =
          p9_crc32_update(input_crc_state, slot->tx_buffer, slot->bytes);
      p9_sha256_update(&input_sha_context, slot->tx_buffer, slot->bytes);
      stop_guard = maximum_object_ticks + maximum_object_ticks / 4U +
          (uint64_t)COUNTS_PER_SECOND / UINT64_C(50);
      if (now >= duration_deadline ||
          duration_deadline - now <= stop_guard)
        duration_stop = 1U;
    }

    /*
     * Start N+1 before CPU integrity work for N.  Four DMA buffer slots and
     * their descriptor chains remain queued, while PL transfers N+1 and the
     * receiver verifies N.  The sender waits a fixed receiver-lead interval;
     * there is no per-object optical readiness exchange.
     */
    if (duration_stop == 0U && ordinal + 1U < result->object_count &&
        ordinal != recovery_ordinal && ordinal + 1U != recovery_ordinal) {
      mailbox->object_id = result->first_object_id + ordinal + 1U;
      mailbox->initial_sequence = 0U;
      if (dual_mode != 0U) {
        status = p10_5_program_dual_object_context(
            mailbox, result->p10_5_active_mask, 1U);
        if (status != P9_RUNTIME_OK) {
          status = P10_1_RUNTIME_STATUS_PL_OBJECT;
          goto stream_fail_v2;
        }
      } else {
        p10_1_configure_object(mailbox, flags, 0U, local_rx);
      }
      if (local_tx != 0U)
        usleep(2000U);
      if (dual_mode != 0U) {
        status = p10_5_start_direction_stream();
        if (status != P9_RUNTIME_OK) {
          status = P10_1_RUNTIME_STATUS_PL_OBJECT;
          goto stream_fail_v2;
        }
      } else {
        p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
      }
      object_started_ticks = p9_time_now();
      next_object_prestarted = 1U;
    }

    if (local_rx != 0U) {
      size_t object_mismatch;
      uint64_t phase_start = p9_time_now();

      p10_1_publish_state(result, P10_1_RUNTIME_VERIFYING);
      p9_cache_invalidate((UINTPTR)slot->rx_buffer, slot->bytes);
      /*
       * Preserve direct byte equality while folding that scan into the one
       * required incremental output CRC pass.  Input CRC/SHA was already
       * accumulated when the slot was prepared; output SHA remains an
       * independent incremental pass.  Redundant per-segment digests run only
       * on the error path so clean streaming is not serialized behind seven
       * complete memory passes.
       */
      output_crc_state =
          p9_crc32_update_compare(output_crc_state,
                                  slot->tx_buffer, slot->rx_buffer,
                                  slot->bytes, &object_mismatch);
      p9_sha256_update(
          &output_sha_context, slot->rx_buffer, slot->bytes);
      if (object_mismatch != SIZE_MAX) {
        uint32_t object_input_crc =
            p9_crc32(slot->tx_buffer, slot->bytes);
        uint32_t object_output_crc =
            p9_crc32(slot->rx_buffer, slot->bytes);
        uint8_t object_input_sha[32];
        uint8_t object_output_sha[32];

        p9_sha256(slot->tx_buffer, slot->bytes, object_input_sha);
        p9_sha256(slot->rx_buffer, slot->bytes, object_output_sha);
        if (object_input_crc != object_output_crc)
          result->crc_bad_count++;
        if (memcmp(object_input_sha, object_output_sha,
                   sizeof(object_input_sha)) != 0)
          result->sha_mismatch_count++;
        result->first_mismatch_offset =
            ordinal * result->object_bytes + (uint32_t)object_mismatch;
        result->integrity_error_count++;
        status = P10_1_RUNTIME_STATUS_INTEGRITY;
        goto stream_fail_v2;
      }
      verify_ticks += p9_time_now() - phase_start;
    }
    slot->valid = 0U;
    if (duration_stop != 0U)
      break;
  }

  if (duration_mode != 0U) {
    uint64_t start_ticks =
        p10_1_load64(&result->ps_start_ticks_low,
                     &result->ps_start_ticks_high);
    uint64_t now = p9_time_now();

    /*
     * A duration-mode stream stops only at a verified object boundary.  The
     * guard above leaves enough time for the last object to finish without
     * exceeding the configured module-runtime ceiling.  The endpoint remains
     * receive-capable but cannot start another object during the bounded tail;
     * final shutdown and descriptor reclamation follow immediately below.
     */
    if (duration_stop == 0U || result->objects_completed == 0U ||
        accepted_bytes == 0U || accepted_bytes > UINT32_MAX ||
        now > duration_deadline) {
      status = P10_1_RUNTIME_STATUS_TIMER;
      goto stream_fail_v2;
    }
    while (now < duration_deadline) {
      uint64_t remaining_ticks = duration_deadline - now;
      uint64_t remaining_us =
          (remaining_ticks * UINT64_C(1000000)) /
          (uint64_t)COUNTS_PER_SECOND;
      if (remaining_us > UINT64_C(1000))
        usleep(1000U);
      else if (remaining_us > UINT64_C(2))
        usleep((unsigned int)(remaining_us - UINT64_C(1)));
      else
        usleep(1U);
      now = p9_time_now();
    }
    /* Freeze clean direction and physical counters at the final verified
     * object boundary, then revoke RX/TX and verify safe idle immediately at
     * the runtime deadline.  Expensive CRC/SHA finalization happens only
     * after the modules are shut down. */
    result->total_bytes = (uint32_t)accepted_bytes;
    result->object_count = result->objects_completed;
    result->p10_5_prefetched_objects_reclaimed =
        result->objects_submitted - result->objects_completed;
    status = p10_1_snapshot_p10_5(result, 1U);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
    p10_1_snapshot_physical(result, 0U);
    status = p9_shutdown();
    if (status != P9_RUNTIME_OK) {
      status = P10_1_RUNTIME_STATUS_PL_OBJECT;
      goto stream_fail_v2;
    }
    result->p10_5_duration_elapsed_ms = (uint32_t)(
        ((now - start_ticks) * UINT64_C(1000)) /
        (uint64_t)COUNTS_PER_SECOND);
    if (result->p10_5_duration_elapsed_ms <
        result->p10_5_duration_target_ms) {
      status = P10_1_RUNTIME_STATUS_TIMER;
      goto stream_fail_v2;
    }
  } else if (result->objects_completed != result->object_count ||
             next_prepare_ordinal != result->object_count ||
             accepted_bytes != result->total_bytes) {
    status = P10_1_RUNTIME_STATUS_REMOTE_COMMIT;
    goto stream_fail_v2;
  }

  p9_sha256_final(&input_sha_context, input_sha);
  result->input_crc32 = p9_crc32_end(input_crc_state);
  p10_1_copy_digest_words(result->input_sha256, input_sha);
  if (local_rx != 0U) {
    p9_sha256_final(&output_sha_context, output_sha);
    result->output_crc32 = p9_crc32_end(output_crc_state);
    p10_1_copy_digest_words(result->output_sha256, output_sha);
    if (result->input_crc32 != result->output_crc32)
      result->crc_bad_count++;
    if (memcmp(input_sha, output_sha, sizeof(input_sha)) != 0)
      result->sha_mismatch_count++;
    if (result->crc_bad_count != 0U || result->sha_mismatch_count != 0U) {
      result->integrity_error_count++;
      status = P10_1_RUNTIME_STATUS_INTEGRITY;
      goto stream_fail_v2;
    }
    committed_bytes = result->total_bytes;
    result->atomic_commit_count = 1U;
    if (dual_mode == 0U) {
      status = p10_1_send_signal(
          mailbox->direction, result->lane_mask, 30000U, result);
      if (status != P10_1_RUNTIME_STATUS_OK)
        goto stream_fail_v2;
    }
    result->remote_commit_confirmed = 1U;
  } else {
    status = p10_1_wait_signal(result->lane_mask, 30000U, result);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
    committed_bytes = result->total_bytes;
    result->atomic_commit_count = 1U;
    result->remote_commit_confirmed = 1U;
  }

  p10_1_store64(&result->ps_end_ticks_low,
                &result->ps_end_ticks_high, p9_time_now());
  {
    uint64_t pl_end = p10_1_pl_snapshot();
    if (pl_end == UINT64_MAX) {
      status = P10_1_RUNTIME_STATUS_TIMER;
      goto stream_fail_v2;
    }
    p10_1_store64(&result->pl_end_ticks_low,
                  &result->pl_end_ticks_high, pl_end);
  }
  p10_1_store64(&result->application_bytes_accepted_low,
                &result->application_bytes_accepted_high, accepted_bytes);
  p10_1_store64(&result->application_bytes_committed_low,
                &result->application_bytes_committed_high, committed_bytes);
  p10_1_store64(&result->wire_bytes_low,
                &result->wire_bytes_high, wire_bytes);
  p10_1_store64(&result->payload_prepare_ticks_low,
                &result->payload_prepare_ticks_high, prepare_ticks);
  p10_1_store64(&result->integrity_verify_ticks_low,
                &result->integrity_verify_ticks_high, verify_ticks);
  p10_1_finalize_timer(result);
  if (result->timer_crosscheck_pass == 0U) {
    status = P10_1_RUNTIME_STATUS_TIMER;
    goto stream_fail_v2;
  }

  result->retry_exhausted_count =
      p9_pl_read(IR_REG_P9_TX_RETRY_EXHAUSTED_COUNT);
  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 6U);
  p10_1_snapshot_perf(result);
  p10_1_snapshot_physical(result, 0U);
  if (duration_mode == 0U) {
    status = p10_1_snapshot_p10_5(result, 1U);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
  }
  for (uint32_t module = 0U; module < 4U; ++module) {
    if (result->duty_hard_fault_after[module] != 0U ||
        result->tx_high_max_after[module] > 64U) {
      status = P10_1_RUNTIME_STATUS_PL_OBJECT;
      goto stream_fail_v2;
    }
  }
  if (result->retry_exhausted_count != 0U) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail_v2;
  }
  if (direction_fault_test != 0U) {
    result->p10_5_unaffected_progress_bytes = result->total_bytes;
    result->p10_5_affected_commit_count = 1U;
    result->p10_5_fault_recovery_pass = 1U;
  }

  {
    uint64_t submitted =
        p10_1_load64(&result->descriptors_submitted_low,
                     &result->descriptors_submitted_high);
    uint64_t completed =
        p10_1_load64(&result->descriptors_completed_low,
                     &result->descriptors_completed_high);

    if (submitted < completed) {
      result->descriptor_leak_count = 1U;
      status = P10_1_RUNTIME_STATUS_DMA_COMPLETION;
      goto stream_fail_v2;
    }
    if (duration_mode == 0U && submitted != completed) {
      result->descriptor_leak_count = (uint32_t)(submitted - completed);
      status = P10_1_RUNTIME_STATUS_DMA_COMPLETION;
      goto stream_fail_v2;
    }

    /*
     * Duration mode deliberately leaves up to buffer_count-1 prefetched
     * objects in the SG rings.  First revoke transmit permission and verify
     * shutdown, then reclaim those descriptors with the established DMA/PL
     * reset path.  All performance, physical and P10.5 context evidence was
     * captured above, before this cleanup can clear live counters.
     */
    status = p9_shutdown();
    if (status == P9_RUNTIME_OK && duration_mode != 0U) {
      result->descriptors_reclaimed_by_reset =
          (uint32_t)(submitted - completed);
      status = p9_reset_stream_path(result->ring_depth, 1U, 1U);
      if (status == P9_RUNTIME_OK) {
        result->descriptor_leak_count = 0U;
        status = p9_shutdown();
      }
      result->dma_reset_count = g_metrics.dma_reset_count;
      result->pl_reset_count = g_metrics.pl_soft_reset_count;
    }
  }
  result->shutdown_attempt_count = g_metrics.shutdown_attempt_count;
  result->shutdown_verified_count = g_metrics.shutdown_verified_count;
  result->final_pl_status = p9_pl_read(IR_REG_P9_STATUS);
  result->final_phy_status = p9_pl_read(IR_REG_P9_PHY_STATUS);
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail_v2;
  }
  result->status = P10_1_RUNTIME_STATUS_OK;
  p10_1_publish_state(result, P10_1_RUNTIME_COMPLETE);
  return P9_RUNTIME_OK;

stream_fail_v2:
  (void)p10_1_snapshot_p10_5(result, 0U);
  result->status = (uint32_t)status;
  result->last_error_detail = result->last_error_detail == 0U ?
      p9_pl_read(IR_REG_P9_OBJECT_ERROR) : result->last_error_detail;
  p10_1_store64(&result->application_bytes_accepted_low,
                &result->application_bytes_accepted_high, accepted_bytes);
  p10_1_store64(&result->application_bytes_committed_low,
                &result->application_bytes_committed_high, 0U);
  result->atomic_commit_count = 0U;
  result->remote_commit_confirmed = 0U;
  {
    uint64_t submitted =
        p10_1_load64(&result->descriptors_submitted_low,
                     &result->descriptors_submitted_high);
    uint64_t completed =
        p10_1_load64(&result->descriptors_completed_low,
                     &result->descriptors_completed_high);
    result->descriptors_reclaimed_by_reset =
        submitted >= completed ? (uint32_t)(submitted - completed) : 0U;
  }
  (void)p9_shutdown();
  if (p9_reset_stream_path(
          result->ring_depth == 0U ? 16U : result->ring_depth,
          1U, 1U) == P9_RUNTIME_OK) {
    result->descriptor_leak_count = 0U;
  } else {
    result->descriptor_leak_count =
        result->descriptors_reclaimed_by_reset;
  }
  (void)p9_shutdown();
  result->dma_reset_count = g_metrics.dma_reset_count;
  result->pl_reset_count = g_metrics.pl_soft_reset_count;
  result->shutdown_attempt_count = g_metrics.shutdown_attempt_count;
  result->shutdown_verified_count = g_metrics.shutdown_verified_count;
  result->final_pl_status = p9_pl_read(IR_REG_P9_STATUS);
  result->final_phy_status = p9_pl_read(IR_REG_P9_PHY_STATUS);
  p10_1_publish_state(result, P10_1_RUNTIME_FAULT);
  return P9_RUNTIME_PL_OBJECT;
}
