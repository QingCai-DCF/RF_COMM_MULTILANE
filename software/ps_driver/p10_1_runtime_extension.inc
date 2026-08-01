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
   * One lost cumulative ACK is not a deterministic duplicate-DATA stimulus:
   * a later ACK from the four-frame endpoint burst can cover it before the
   * 62.5 ms RTO.  Suppress a bounded receiver-only run of ACKs so at least
   * one real DATA retry must cross the optical path within the existing
   * 250 ms observation interval.
   */
  P10_1_DUPLICATE_ACK_DROP_COUNT = 0xffU,
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

static uint32_t p10_1_local_raw_offset(uint32_t lane) {
  if (P10_ENDPOINT_ROLE == 1)
    return lane == 0U ? IR_REG_P9_RAW_RX_A0 : IR_REG_P9_RAW_RX_A1;
  return lane == 0U ? IR_REG_P9_RAW_RX_B0 : IR_REG_P9_RAW_RX_B1;
}

static uint32_t p10_1_signal_lane(uint32_t lane_mask) {
  return (lane_mask & 1U) != 0U ? 0U : 1U;
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
    if ((p9_pl_read(IR_REG_P9_PHY_STATUS) & P9_PHY_SAFETY_MASK) != 0U)
      break;
    usleep(P9_POLL_DELAY_US);
  }
  return P10_1_RUNTIME_STATUS_SIGNAL_TIMEOUT;
}

static int p10_1_wait_signal(uint32_t lane_mask, uint32_t timeout_ms,
                             volatile p10_1_runtime_result_t *result) {
  uint32_t lane = p10_1_signal_lane(lane_mask);
  uint32_t offset = p10_1_local_raw_offset(lane);
  uint32_t before = p9_pl_read(offset);
  uint64_t started = p9_time_now();
  uint64_t deadline = p9_time_now() +
      ((uint64_t)timeout_ms * (uint64_t)COUNTS_PER_SECOND) /
          UINT64_C(1000);
  while (p9_time_now() < deadline) {
    uint32_t after = p9_pl_read(offset);
    if (after - before >= P10_1_RUNTIME_SIGNAL_PULSES) {
      uint64_t elapsed = p10_1_load64(
          &result->inter_object_signal_ticks_low,
          &result->inter_object_signal_ticks_high);
      elapsed += p9_time_now() - started;
      p10_1_store64(&result->inter_object_signal_ticks_low,
                    &result->inter_object_signal_ticks_high, elapsed);
      return P10_1_RUNTIME_STATUS_OK;
    }
    if ((p9_pl_read(IR_REG_P9_PHY_STATUS) & P9_PHY_SAFETY_MASK) != 0U)
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
  uint32_t physical_fault_injection =
      (mailbox->lane_unavailable_mask & 3U) << 16;
  if (inject_fault != 0U) {
    if ((command_flags & P10_1_RUNTIME_FLAG_STALE_SEGMENT) != 0U)
      protocol_fault_flags |= 1U;
    if ((command_flags & P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT) != 0U &&
        local_receiver != 0U)
      physical_fault_injection |=
          (P10_1_DUPLICATE_ACK_DROP_COUNT & 0xffU) << 8;
  }
  p9_pl_write(IR_REG_P9_OBJECT_CONFIG,
              (mailbox->lane_mask & 3U) |
                  ((mailbox->rate_select & 3U) << 8) |
                  ((mailbox->direction & 1U) << 16));
  p9_pl_write(IR_REG_P9_LANE_WEIGHTS, mailbox->lane_weights & 0xffffU);
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
    p9_sha256_context_t *input_sha_context, uint32_t *input_crc_state,
    uint64_t *prepare_ticks) {
  uint64_t stream_offset = (uint64_t)ordinal * result->object_bytes;
  uint32_t remaining = result->total_bytes - (uint32_t)stream_offset;
  uint32_t current = remaining < result->object_bytes ?
                         remaining : result->object_bytes;
  uint64_t phase_start;
  int status;

  if (slot->valid != 0U || stream_offset >= result->total_bytes ||
      current == 0U)
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;

  slot->ordinal = ordinal;
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
  *input_crc_state =
      p9_crc32_update(*input_crc_state, slot->tx_buffer, current);
  p9_sha256_update(input_sha_context, slot->tx_buffer, current);

  if (local_tx != 0U) {
    p9_cache_flush((UINTPTR)slot->tx_buffer, current);
    status = p10_1_submit_chain(
        1U, (UINTPTR)slot->tx_buffer, current, result->descriptor_bytes,
        slot->token_base, result);
  } else {
    memset(slot->rx_buffer, 0x5a ^ (uint8_t)ordinal, current);
    p9_cache_invalidate((UINTPTR)slot->rx_buffer, current);
    status = p10_1_submit_chain(
        0U, (UINTPTR)slot->rx_buffer, current, result->descriptor_bytes,
        slot->token_base, result);
  }
  if (status != P10_1_RUNTIME_STATUS_OK)
    return status;
  slot->valid = 1U;
  result->objects_submitted++;
  return P10_1_RUNTIME_STATUS_OK;
}

static int p10_1_validate_stream_args(
    volatile p9_mailbox_t *mailbox,
    volatile p10_1_runtime_result_t *result) {
  uint32_t total = mailbox->object_size;
  uint32_t object_bytes = mailbox->raw_target;
  uint32_t descriptor_bytes = mailbox->raw_spacing_cycles;
  uint32_t descriptor_count;
  uint32_t configured_buffer_count;
  uint32_t active_buffer_count;
  uint32_t abort_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_EXPECT_ABORT_25 |
       P10_1_RUNTIME_FLAG_EXPECT_ABORT_75);
  uint32_t reset_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER |
       P10_1_RUNTIME_FLAG_EXPECT_PL_RESET |
       P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER);
  uint32_t injected_fault_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |
       P10_1_RUNTIME_FLAG_STALE_SEGMENT);
  uint32_t service_reset_flags = mailbox->command_flags &
      (P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_SENDER |
       P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_RECEIVER);
  uint32_t recovery_vector_flags =
      abort_flags | reset_flags | injected_fault_flags;
  if (mailbox->lane_mask == 0U || mailbox->lane_mask > 3U ||
      mailbox->direction > 1U || mailbox->rate_select > 2U ||
      (mailbox->ring_depth != 8U && mailbox->ring_depth != 16U &&
       mailbox->ring_depth != 32U) ||
      mailbox->cache_mode != 1U ||
      total == 0U || object_bytes == 0U ||
      total > P10_1_RUNTIME_MAX_OBJECT_BYTES ||
      object_bytes > total ||
      object_bytes > P10_1_RUNTIME_MAX_OBJECT_BYTES ||
      descriptor_bytes == 0U || descriptor_bytes > object_bytes ||
      (descriptor_bytes & 3U) != 0U ||
      mailbox->timeout_ms == 0U ||
      mailbox->timeout_ms > P10_1_RUNTIME_MAX_TIMEOUT_MS ||
      abort_flags ==
          (P10_1_RUNTIME_FLAG_EXPECT_ABORT_25 |
           P10_1_RUNTIME_FLAG_EXPECT_ABORT_75) ||
      reset_flags ==
          (P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER |
           P10_1_RUNTIME_FLAG_EXPECT_PL_RESET) ||
      reset_flags ==
          (P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER |
           P10_1_RUNTIME_FLAG_EXPECT_PL_RESET) ||
      reset_flags ==
          (P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER |
           P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER) ||
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
  descriptor_count = p10_1_descriptor_count(object_bytes,
                                             descriptor_bytes);
  if (descriptor_count == 0U || descriptor_count > mailbox->ring_depth)
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;
  result->lane_mask = mailbox->lane_mask;
  result->direction = mailbox->direction;
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
  result->ack_threshold = mailbox->drop_data_count == 0U ?
      8U : mailbox->drop_data_count;
  result->outstanding_frames = mailbox->drop_ack_count == 0U ?
      32U : mailbox->drop_ack_count;
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
      result->ack_threshold != 8U ||
      result->outstanding_frames != 32U ||
      (uint64_t)result->object_bytes * result->buffer_count >
          P9_MAX_OBJECT_BYTES ||
      descriptor_count * active_buffer_count > result->ring_depth)
    return P10_1_RUNTIME_STATUS_BAD_ARGUMENT;
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
  if ((((flags & P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER) != 0U &&
        local_tx != 0U) ||
       ((flags & P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER) != 0U &&
        local_tx == 0U)) &&
      (flags & P10_1_RUNTIME_FLAG_EXPECT_PL_RESET) == 0U) {
    status = p9_dma_initialize(result->ring_depth, 1U);
  } else {
    status = p9_reset_stream_path(result->ring_depth, 1U, 1U);
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
  uint32_t local_tx;
  uint32_t local_rx;
  uint32_t initial_slot_count;
  uint32_t next_prepare_ordinal;
  uint32_t recovery_flags;
  uint32_t recovery_ordinal = UINT32_MAX;
  uint32_t injected_fault_before = 0U;
  uint64_t accepted_bytes = 0U;
  uint64_t committed_bytes = 0U;
  uint64_t wire_bytes = 0U;
  uint64_t prepare_ticks = 0U;
  uint64_t verify_ticks = 0U;
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
  local_tx = p9_local_sender(mailbox->direction);
  local_rx = !local_tx;
  recovery_flags = flags &
      (P10_1_RUNTIME_FLAG_EXPECT_ABORT_25 |
       P10_1_RUNTIME_FLAG_EXPECT_ABORT_75 |
       P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER |
       P10_1_RUNTIME_FLAG_EXPECT_PL_RESET |
       P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |
       P10_1_RUNTIME_FLAG_STALE_SEGMENT |
       P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER);
  if ((recovery_flags & P10_1_RUNTIME_FLAG_EXPECT_ABORT_25) != 0U) {
    recovery_ordinal = result->object_count / 4U;
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
  p9_cache_enable();
  g_metrics.cache_enabled_exercised = 1U;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) {
    status = P10_1_RUNTIME_STATUS_PL_OBJECT;
    goto stream_fail_v2;
  }

  /*
   * Stream-wide observability starts from one clear.  Object configuration
   * below deliberately never clears these counters.
   */
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
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
   * a 16-entry SG ring, and BdRingToHw batches of four.
   */
  initial_slot_count = result->buffer_count < result->object_count ?
      result->buffer_count : result->object_count;
  p10_1_publish_state(result, P10_1_RUNTIME_PRIMING);
  for (uint32_t ordinal = 0U; ordinal < initial_slot_count; ++ordinal) {
    status = p10_1_prepare_slot(
        result, &slots[ordinal], ordinal, ordinal, local_tx,
        &input_sha_context, &input_crc_state, &prepare_ticks);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
  }
  next_prepare_ordinal = initial_slot_count;

  for (uint32_t ordinal = 0U; ordinal < result->object_count; ++ordinal) {
    uint32_t slot_index = ordinal % result->buffer_count;
    p10_1_runtime_buffer_slot_t *slot = &slots[slot_index];

    if (slot->valid == 0U || slot->ordinal != ordinal) {
      status = P10_1_RUNTIME_STATUS_DMA_CHAIN;
      goto stream_fail_v2;
    }
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
    p10_1_configure_object(mailbox, flags, ordinal == recovery_ordinal,
                           local_rx);

    if (ordinal != 0U) {
      if (local_rx != 0U) {
        status = p10_1_send_signal(
            mailbox->direction, mailbox->lane_mask, 30000U, result);
      } else {
        status = p10_1_wait_signal(
            mailbox->lane_mask, 30000U, result);
        /*
         * The ready pulse is completed immediately before the receiver writes
         * START_OBJECT.  This bounded guard prevents the sender from winning
         * that cross-board software race.
         */
        if (status == P10_1_RUNTIME_STATUS_OK)
          usleep(600U);
      }
      if (status != P10_1_RUNTIME_STATUS_OK)
        goto stream_fail_v2;
    }

    p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
    if (ordinal == 0U) {
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
      p10_1_publish_state(
          result, local_rx != 0U ?
              P10_1_RUNTIME_PRIMED : P10_1_RUNTIME_RUNNING);
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
          next_prepare_ordinal, local_tx, &input_sha_context,
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

    status = p10_1_collect_chain(
        local_tx, slot->descriptor_count, slot->token_base,
        mailbox->timeout_ms, slot->bytes, result);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
    result->objects_completed++;
    accepted_bytes += slot->bytes;
    wire_bytes += slot->bytes;

    if (local_rx != 0U) {
      uint32_t object_input_crc;
      uint32_t object_output_crc;
      uint8_t object_input_sha[32];
      uint8_t object_output_sha[32];
      uint64_t phase_start = p9_time_now();

      p10_1_publish_state(result, P10_1_RUNTIME_VERIFYING);
      p9_cache_invalidate((UINTPTR)slot->rx_buffer, slot->bytes);
      object_input_crc = p9_crc32(slot->tx_buffer, slot->bytes);
      object_output_crc = p9_crc32(slot->rx_buffer, slot->bytes);
      p9_sha256(slot->tx_buffer, slot->bytes, object_input_sha);
      p9_sha256(slot->rx_buffer, slot->bytes, object_output_sha);
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
           index < slot->bytes &&
               status == P10_1_RUNTIME_STATUS_OK; ++index) {
        if (slot->tx_buffer[index] != slot->rx_buffer[index]) {
          result->first_mismatch_offset =
              ordinal * result->object_bytes + index;
          result->integrity_error_count++;
          status = P10_1_RUNTIME_STATUS_INTEGRITY;
        }
      }
      if (status != P10_1_RUNTIME_STATUS_OK)
        goto stream_fail_v2;
      output_crc_state =
          p9_crc32_update(output_crc_state, slot->rx_buffer, slot->bytes);
      p9_sha256_update(
          &output_sha_context, slot->rx_buffer, slot->bytes);
      verify_ticks += p9_time_now() - phase_start;
    }
    slot->valid = 0U;
  }

  if (result->objects_completed != result->object_count ||
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
    if (result->input_crc32 != result->output_crc32 ||
        memcmp(input_sha, output_sha, sizeof(input_sha)) != 0) {
      result->integrity_error_count++;
      status = P10_1_RUNTIME_STATUS_INTEGRITY;
      goto stream_fail_v2;
    }
    committed_bytes = result->total_bytes;
    result->atomic_commit_count = 1U;
    status = p10_1_send_signal(
        mailbox->direction, mailbox->lane_mask, 30000U, result);
    if (status != P10_1_RUNTIME_STATUS_OK)
      goto stream_fail_v2;
    result->remote_commit_confirmed = 1U;
  } else {
    status = p10_1_wait_signal(mailbox->lane_mask, 30000U, result);
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

  {
    uint64_t submitted =
        p10_1_load64(&result->descriptors_submitted_low,
                     &result->descriptors_submitted_high);
    uint64_t completed =
        p10_1_load64(&result->descriptors_completed_low,
                     &result->descriptors_completed_high);
    if (submitted != completed) {
      result->descriptor_leak_count =
          submitted > completed ? (uint32_t)(submitted - completed) : 1U;
      status = P10_1_RUNTIME_STATUS_DMA_COMPLETION;
      goto stream_fail_v2;
    }
  }
  result->retry_exhausted_count =
      p9_pl_read(IR_REG_P9_TX_RETRY_EXHAUSTED_COUNT);
  p9_pl_write(P10_1_PERF_COMMAND_OFFSET, 6U);
  p10_1_snapshot_perf(result);
  p10_1_snapshot_physical(result, 0U);
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

  status = p9_shutdown();
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
