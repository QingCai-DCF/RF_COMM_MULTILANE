#include "ir_regs.h"
#include "p9_crypto.h"
#include "p9_runtime_protocol.h"

#include "sleep.h"
#include "xaxidma.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xtime_l.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifndef IR_PL_BASEADDR
#define IR_PL_BASEADDR UINT32_C(0x43C00000)
#endif

#ifndef XPAR_AXIDMA_0_DEVICE_ID
#error "P9 requires the generated XAxiDma device identity"
#endif

#ifndef XPAR_FABRIC_AXI_DMA_0_MM2S_INTROUT_INTR
#define XPAR_FABRIC_AXI_DMA_0_MM2S_INTROUT_INTR UINT32_C(0xffffffff)
#endif
#ifndef XPAR_FABRIC_AXI_DMA_0_S2MM_INTROUT_INTR
#define XPAR_FABRIC_AXI_DMA_0_S2MM_INTROUT_INTR UINT32_C(0xffffffff)
#endif

enum {
  P9_STATUS_ENDPOINT_ARMED = 1U << 0,
  P9_STATUS_TX_KILL_ACTIVE = 1U << 1,
  P9_STATUS_OBJECT_ACTIVE = 1U << 2,
  P9_STATUS_OBJECT_DONE = 1U << 3,
  P9_STATUS_OBJECT_FAIL = 1U << 4,
  P9_STATUS_RAW_BUSY = 1U << 7,
  P9_STATUS_RAW_DONE = 1U << 8,
  P9_STATUS_RECEIVER_ENABLE = 1U << 9,
  P9_PHY_READY_MASK = 0x0000000fU,
  P9_PHY_STARTUP_MASK = 0x000000f0U,
  P9_PHY_SAFETY_MASK = 0x00000f00U,
  P9_POLL_DELAY_US = 50U,
  P9_RESET_POLLS = 200000U,
};

typedef struct {
  uint32_t tx_submitted;
  uint32_t tx_completed;
  uint32_t rx_submitted;
  uint32_t rx_completed;
  uint32_t tx_producer_index;
  uint32_t tx_consumer_index;
  uint32_t rx_producer_index;
  uint32_t rx_consumer_index;
  uint32_t tx_producer_generation;
  uint32_t tx_consumer_generation;
  uint32_t rx_producer_generation;
  uint32_t rx_consumer_generation;
  uint32_t tx_ring_full_observed;
  uint32_t rx_ring_full_observed;
  uint32_t tx_ring_empty_observed;
  uint32_t rx_ring_empty_observed;
  uint32_t tx_double_completion;
  uint32_t rx_double_completion;
  uint32_t stale_completion_rejected;
  uint32_t cache_flush_count;
  uint32_t cache_invalidate_count;
  uint32_t memory_barrier_count;
  uint32_t cache_enabled_exercised;
  uint32_t cache_disabled_exercised;
  uint32_t misaligned_transfer_handled;
  uint32_t dma_reset_count;
  uint32_t dma_reset_while_queued_count;
  uint32_t object_abort_count;
  uint32_t pl_soft_reset_count;
  uint32_t shutdown_attempt_count;
  uint32_t shutdown_verified_count;
  uint32_t last_completion_token;
} p9_metrics_t;

static XAxiDma g_dma;
static XAxiDma_Config *g_dma_config;
static uint32_t g_dma_initialized;
static uint32_t g_tx_started;
static uint32_t g_rx_started;
static uint32_t g_ring_depth;
static uint32_t g_cache_enabled;
static p9_metrics_t g_metrics;

static uint32_t p9_pl_read(uint32_t offset) {
  return Xil_In32((UINTPTR)IR_PL_BASEADDR + offset);
}

static void p9_pl_write(uint32_t offset, uint32_t value) {
  Xil_Out32((UINTPTR)IR_PL_BASEADDR + offset, value);
  dsb();
  g_metrics.memory_barrier_count++;
}

static uint64_t p9_time_now(void) {
  XTime value;
  XTime_GetTime(&value);
  return (uint64_t)value;
}

static uint64_t p9_deadline_ms(uint32_t timeout_ms) {
  uint32_t bounded = timeout_ms == 0U ? 120000U : timeout_ms;
  if (bounded > 300000U) bounded = 300000U;
  return p9_time_now() +
         ((uint64_t)bounded * (uint64_t)COUNTS_PER_SECOND) / UINT64_C(1000);
}

static void p9_cache_disable(void) {
  if (g_cache_enabled != 0U) {
    Xil_DCacheDisable();
    g_cache_enabled = 0U;
  }
  dsb();
  g_metrics.memory_barrier_count++;
}

static void p9_cache_enable(void) {
  if (g_cache_enabled == 0U) {
    Xil_DCacheEnable();
    g_cache_enabled = 1U;
  }
  dsb();
  g_metrics.memory_barrier_count++;
}

static void p9_cache_flush(UINTPTR address, uint32_t bytes) {
  Xil_DCacheFlushRange(address, bytes);
  dsb();
  g_metrics.cache_flush_count++;
  g_metrics.memory_barrier_count++;
}

static void p9_cache_invalidate(UINTPTR address, uint32_t bytes) {
  Xil_DCacheInvalidateRange(address, bytes);
  dsb();
  g_metrics.cache_invalidate_count++;
  g_metrics.memory_barrier_count++;
}

static void p9_store_u64(volatile uint32_t *low, volatile uint32_t *high,
                         uint64_t value) {
  *low = (uint32_t)value;
  *high = (uint32_t)(value >> 32);
}

static uint32_t p9_digest_word(const uint8_t digest[32], uint32_t index) {
  const uint8_t *p = digest + 4U * index;
  return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
         ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static void p9_copy_digest(volatile uint32_t output[8],
                           const uint8_t digest[32]) {
  for (uint32_t index = 0U; index < 8U; ++index)
    output[index] = p9_digest_word(digest, index);
}

static void p9_snapshot_pl(volatile p9_mailbox_t *mailbox) {
  for (uint32_t index = 0U; index < P9_PL_SNAPSHOT_WORDS; ++index)
    mailbox->pl_register_snapshot[index] =
        p9_pl_read(IR_REG_P9_ID + 4U * index);
}

static void p9_copy_metrics(volatile p9_mailbox_t *m) {
  m->tx_submitted = g_metrics.tx_submitted;
  m->tx_completed = g_metrics.tx_completed;
  m->rx_submitted = g_metrics.rx_submitted;
  m->rx_completed = g_metrics.rx_completed;
  m->tx_producer_index = g_metrics.tx_producer_index;
  m->tx_consumer_index = g_metrics.tx_consumer_index;
  m->rx_producer_index = g_metrics.rx_producer_index;
  m->rx_consumer_index = g_metrics.rx_consumer_index;
  m->tx_producer_generation = g_metrics.tx_producer_generation;
  m->tx_consumer_generation = g_metrics.tx_consumer_generation;
  m->rx_producer_generation = g_metrics.rx_producer_generation;
  m->rx_consumer_generation = g_metrics.rx_consumer_generation;
  m->tx_ring_full_observed = g_metrics.tx_ring_full_observed;
  m->rx_ring_full_observed = g_metrics.rx_ring_full_observed;
  m->tx_ring_empty_observed = g_metrics.tx_ring_empty_observed;
  m->rx_ring_empty_observed = g_metrics.rx_ring_empty_observed;
  m->tx_double_completion = g_metrics.tx_double_completion;
  m->rx_double_completion = g_metrics.rx_double_completion;
  m->descriptor_leak_count =
      (g_metrics.tx_submitted >= g_metrics.tx_completed
           ? g_metrics.tx_submitted - g_metrics.tx_completed : 0U) +
      (g_metrics.rx_submitted >= g_metrics.rx_completed
           ? g_metrics.rx_submitted - g_metrics.rx_completed : 0U);
  m->stale_completion_rejected = g_metrics.stale_completion_rejected;
  m->cache_flush_count = g_metrics.cache_flush_count;
  m->cache_invalidate_count = g_metrics.cache_invalidate_count;
  m->memory_barrier_count = g_metrics.memory_barrier_count;
  m->cache_enabled_exercised = g_metrics.cache_enabled_exercised;
  m->cache_disabled_exercised = g_metrics.cache_disabled_exercised;
  m->misaligned_transfer_handled = g_metrics.misaligned_transfer_handled;
  m->dma_reset_count = g_metrics.dma_reset_count;
  m->dma_reset_while_queued_count = g_metrics.dma_reset_while_queued_count;
  m->object_abort_count = g_metrics.object_abort_count;
  m->pl_soft_reset_count = g_metrics.pl_soft_reset_count;
  m->shutdown_attempt_count = g_metrics.shutdown_attempt_count;
  m->shutdown_verified_count = g_metrics.shutdown_verified_count;
  m->last_completion_token = g_metrics.last_completion_token;
}

static void p9_fill_identity(volatile p9_mailbox_t *m) {
  m->pl_id = p9_pl_read(IR_REG_P9_ID);
  m->pl_build_id = p9_pl_read(IR_REG_P9_BUILD_ID);
  m->pl_profile_id = p9_pl_read(IR_REG_P9_PROFILE_ID);
  m->pl_register_map_version = p9_pl_read(IR_REG_P9_REGISTER_MAP_VERSION);
  m->pl_register_map_hash_low = p9_pl_read(IR_REG_P9_REGISTER_MAP_HASH_LOW);
  m->pl_capabilities = p9_pl_read(IR_REG_P9_CAPABILITIES);
  m->dma_device_id = XPAR_AXIDMA_0_DEVICE_ID;
  if (g_dma_config != NULL) {
    m->dma_base_address = (uint32_t)g_dma_config->BaseAddr;
    m->dma_has_sg = (uint32_t)g_dma_config->HasSg;
    m->dma_addr_width = (uint32_t)g_dma_config->AddrWidth;
    m->dma_sg_length_width = (uint32_t)g_dma_config->SgLengthWidth;
    m->dma_mm2s_data_width = (uint32_t)g_dma_config->Mm2SDataWidth;
    m->dma_s2mm_data_width = (uint32_t)g_dma_config->S2MmDataWidth;
    m->dma_mm2s_burst = (uint32_t)g_dma_config->Mm2SBurstSize;
    m->dma_s2mm_burst = (uint32_t)g_dma_config->S2MmBurstSize;
    m->dma_mm2s_dre = (uint32_t)g_dma_config->HasMm2SDRE;
    m->dma_s2mm_dre = (uint32_t)g_dma_config->HasS2MmDRE;
  }
  m->descriptor_alignment = XAXIDMA_BD_MINIMUM_ALIGNMENT;
  m->cache_line_bytes = 32U;
  m->interrupt_mm2s_id = XPAR_FABRIC_AXI_DMA_0_MM2S_INTROUT_INTR;
  m->interrupt_s2mm_id = XPAR_FABRIC_AXI_DMA_0_S2MM_INTROUT_INTR;
  m->counts_per_second = COUNTS_PER_SECOND;
}

static int p9_verify_safe_idle(void) {
  uint64_t deadline = p9_deadline_ms(100U);
  do {
    uint32_t status = p9_pl_read(IR_REG_P9_STATUS);
    if ((status & (P9_STATUS_ENDPOINT_ARMED | P9_STATUS_OBJECT_ACTIVE |
                   P9_STATUS_RAW_BUSY | P9_STATUS_RECEIVER_ENABLE)) == 0U &&
        (status & P9_STATUS_TX_KILL_ACTIVE) != 0U)
      return P9_RUNTIME_OK;
    usleep(P9_POLL_DELAY_US);
  } while (p9_time_now() < deadline);
  return P9_RUNTIME_SAFE_IDLE;
}

static int p9_shutdown(void) {
  g_metrics.shutdown_attempt_count++;
  p9_pl_write(IR_REG_P9_CONTROL,
              IR_P9_CONTROL_RECEIVER_DISABLE_MASK |
              IR_P9_CONTROL_DISARM_REQUEST_MASK |
              IR_P9_CONTROL_FULL_SHUTDOWN_REQUEST_MASK);
  int status = p9_verify_safe_idle();
  if (status == P9_RUNTIME_OK) g_metrics.shutdown_verified_count++;
  return status;
}

static int p9_enable_and_arm(void) {
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_RECEIVER_ENABLE_MASK);
  usleep(600U);
  uint64_t deadline = p9_deadline_ms(100U);
  do {
    uint32_t phy = p9_pl_read(IR_REG_P9_PHY_STATUS);
    if ((phy & P9_PHY_SAFETY_MASK) != 0U) return P9_RUNTIME_PHY_NOT_READY;
    if ((phy & (P9_PHY_READY_MASK | P9_PHY_STARTUP_MASK)) ==
        (P9_PHY_READY_MASK | P9_PHY_STARTUP_MASK))
      break;
    usleep(P9_POLL_DELAY_US);
  } while (p9_time_now() < deadline);
  uint32_t phy = p9_pl_read(IR_REG_P9_PHY_STATUS);
  if ((phy & (P9_PHY_READY_MASK | P9_PHY_STARTUP_MASK)) !=
      (P9_PHY_READY_MASK | P9_PHY_STARTUP_MASK))
    return P9_RUNTIME_PHY_NOT_READY;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_ARM_REQUEST_MASK);
  deadline = p9_deadline_ms(20U);
  do {
    uint32_t status = p9_pl_read(IR_REG_P9_STATUS);
    if ((status & P9_STATUS_ENDPOINT_ARMED) != 0U &&
        (status & P9_STATUS_TX_KILL_ACTIVE) == 0U)
      return P9_RUNTIME_OK;
    usleep(P9_POLL_DELAY_US);
  } while (p9_time_now() < deadline);
  return P9_RUNTIME_ARM_FAILED;
}

static int p9_dma_wait_reset(void) {
  for (uint32_t poll = 0U; poll < P9_RESET_POLLS; ++poll) {
    if (XAxiDma_ResetIsDone(&g_dma)) return XST_SUCCESS;
    usleep(1U);
  }
  return XST_FAILURE;
}

static int p9_dma_initialize(uint32_t depth, uint32_t count_reset) {
  XAxiDma_Bd template_bd;
  if (depth != 8U && depth != 32U) return P9_RUNTIME_BAD_ARGUMENT;
  if (g_ring_depth != depth) {
    g_metrics.tx_producer_index = 0U;
    g_metrics.tx_consumer_index = 0U;
    g_metrics.rx_producer_index = 0U;
    g_metrics.rx_consumer_index = 0U;
    g_metrics.tx_producer_generation = 0U;
    g_metrics.tx_consumer_generation = 0U;
    g_metrics.rx_producer_generation = 0U;
    g_metrics.rx_consumer_generation = 0U;
  }
  if (g_dma_initialized != 0U) {
    XAxiDma_Reset(&g_dma);
    if (p9_dma_wait_reset() != XST_SUCCESS) return P9_RUNTIME_RESET_FAILED;
    if (count_reset != 0U) g_metrics.dma_reset_count++;
  }
  g_dma_config = XAxiDma_LookupConfig(XPAR_AXIDMA_0_DEVICE_ID);
  if (g_dma_config == NULL || g_dma_config->HasSg == 0 ||
      g_dma_config->HasMm2S == 0 || g_dma_config->HasS2Mm == 0)
    return P9_RUNTIME_DMA_CONFIG;
  if (XAxiDma_CfgInitialize(&g_dma, g_dma_config) != XST_SUCCESS ||
      !XAxiDma_HasSg(&g_dma))
    return P9_RUNTIME_DMA_CONFIG;
  XAxiDma_BdRing *tx = XAxiDma_GetTxRing(&g_dma);
  XAxiDma_BdRing *rx = XAxiDma_GetRxRing(&g_dma);
  XAxiDma_BdRingIntDisable(tx, XAXIDMA_IRQ_ALL_MASK);
  XAxiDma_BdRingIntDisable(rx, XAXIDMA_IRQ_ALL_MASK);
  if (XAxiDma_BdRingCreate(tx, P9_TX_BD_BASEADDR, P9_TX_BD_BASEADDR,
                           XAXIDMA_BD_MINIMUM_ALIGNMENT, depth) != XST_SUCCESS ||
      XAxiDma_BdRingCreate(rx, P9_RX_BD_BASEADDR, P9_RX_BD_BASEADDR,
                           XAXIDMA_BD_MINIMUM_ALIGNMENT, depth) != XST_SUCCESS)
    return P9_RUNTIME_DMA_RING;
  XAxiDma_BdClear(&template_bd);
  if (XAxiDma_BdRingClone(tx, &template_bd) != XST_SUCCESS ||
      XAxiDma_BdRingClone(rx, &template_bd) != XST_SUCCESS)
    return P9_RUNTIME_DMA_RING;
  g_dma_initialized = 1U;
  g_tx_started = 0U;
  g_rx_started = 0U;
  g_ring_depth = depth;
  if (XAxiDma_BdRingGetFreeCnt(tx) == (int)depth)
    g_metrics.tx_ring_empty_observed = 1U;
  if (XAxiDma_BdRingGetFreeCnt(rx) == (int)depth)
    g_metrics.rx_ring_empty_observed = 1U;
  return P9_RUNTIME_OK;
}

static void p9_advance_producer(uint32_t tx) {
  uint32_t *index = tx ? &g_metrics.tx_producer_index :
                         &g_metrics.rx_producer_index;
  uint32_t *generation = tx ? &g_metrics.tx_producer_generation :
                              &g_metrics.rx_producer_generation;
  *index += 1U;
  if (*index >= g_ring_depth) {
    *index = 0U;
    *generation += 1U;
  }
}

static void p9_advance_consumer(uint32_t tx) {
  uint32_t *index = tx ? &g_metrics.tx_consumer_index :
                         &g_metrics.rx_consumer_index;
  uint32_t *generation = tx ? &g_metrics.tx_consumer_generation :
                              &g_metrics.rx_consumer_generation;
  *index += 1U;
  if (*index >= g_ring_depth) {
    *index = 0U;
    *generation += 1U;
  }
}

static int p9_submit_rx(UINTPTR address, uint32_t bytes, uint32_t token) {
  XAxiDma_BdRing *ring = XAxiDma_GetRxRing(&g_dma);
  XAxiDma_Bd *bd;
  if (XAxiDma_BdRingAlloc(ring, 1, &bd) != XST_SUCCESS)
    return P9_RUNTIME_DMA_SUBMIT;
  if (XAxiDma_BdSetBufAddr(bd, address) != XST_SUCCESS ||
      XAxiDma_BdSetLength(bd, bytes, ring->MaxTransferLen) != XST_SUCCESS) {
    (void)XAxiDma_BdRingUnAlloc(ring, 1, bd);
    return P9_RUNTIME_DMA_SUBMIT;
  }
  XAxiDma_BdSetCtrl(bd, 0U);
  XAxiDma_BdSetId(bd, token);
  if (XAxiDma_BdRingToHw(ring, 1, bd) != XST_SUCCESS)
    return P9_RUNTIME_DMA_SUBMIT;
  g_metrics.rx_submitted++;
  p9_advance_producer(0U);
  if (g_rx_started == 0U) {
    if (XAxiDma_BdRingStart(ring) != XST_SUCCESS)
      return P9_RUNTIME_DMA_SUBMIT;
    g_rx_started = 1U;
  }
  return P9_RUNTIME_OK;
}

static int p9_submit_tx(UINTPTR address, uint32_t bytes, uint32_t token) {
  XAxiDma_BdRing *ring = XAxiDma_GetTxRing(&g_dma);
  XAxiDma_Bd *bd;
  if (XAxiDma_BdRingAlloc(ring, 1, &bd) != XST_SUCCESS)
    return P9_RUNTIME_DMA_SUBMIT;
  if (XAxiDma_BdSetBufAddr(bd, address) != XST_SUCCESS ||
      XAxiDma_BdSetLength(bd, bytes, ring->MaxTransferLen) != XST_SUCCESS) {
    (void)XAxiDma_BdRingUnAlloc(ring, 1, bd);
    return P9_RUNTIME_DMA_SUBMIT;
  }
  XAxiDma_BdSetCtrl(bd, XAXIDMA_BD_CTRL_TXSOF_MASK |
                             XAXIDMA_BD_CTRL_TXEOF_MASK);
  XAxiDma_BdSetId(bd, token);
  if (XAxiDma_BdRingToHw(ring, 1, bd) != XST_SUCCESS)
    return P9_RUNTIME_DMA_SUBMIT;
  g_metrics.tx_submitted++;
  p9_advance_producer(1U);
  if (g_tx_started == 0U) {
    if (XAxiDma_BdRingStart(ring) != XST_SUCCESS)
      return P9_RUNTIME_DMA_SUBMIT;
    g_tx_started = 1U;
  }
  return P9_RUNTIME_OK;
}

static int p9_poll_completion(volatile p9_mailbox_t *m, uint32_t token,
                              uint32_t timeout_ms) {
  XAxiDma_BdRing *tx = XAxiDma_GetTxRing(&g_dma);
  XAxiDma_BdRing *rx = XAxiDma_GetRxRing(&g_dma);
  uint32_t tx_done = 0U, rx_done = 0U, pl_done = 0U;
  uint64_t deadline = p9_deadline_ms(timeout_ms);
  while (p9_time_now() < deadline) {
    XAxiDma_Bd *set;
    int count;
    if (tx_done == 0U &&
        (count = XAxiDma_BdRingFromHw(tx, XAXIDMA_ALL_BDS, &set)) != 0) {
      if (count != 1) g_metrics.tx_double_completion += (uint32_t)(count - 1);
      m->last_dma_tx_status = XAxiDma_BdGetSts(set);
      if ((uint32_t)XAxiDma_BdGetId(set) != token ||
          (m->last_dma_tx_status & XAXIDMA_BD_STS_ALL_ERR_MASK) != 0U)
        return P9_RUNTIME_DMA_COMPLETION;
      if (XAxiDma_BdRingFree(tx, count, set) != XST_SUCCESS)
        return P9_RUNTIME_DMA_COMPLETION;
      g_metrics.tx_completed += (uint32_t)count;
      p9_advance_consumer(1U);
      tx_done = 1U;
    }
    if (rx_done == 0U &&
        (count = XAxiDma_BdRingFromHw(rx, XAXIDMA_ALL_BDS, &set)) != 0) {
      if (count != 1) g_metrics.rx_double_completion += (uint32_t)(count - 1);
      m->last_dma_rx_status = XAxiDma_BdGetSts(set);
      m->actual_rx_length =
          XAxiDma_BdGetActualLength(set, rx->MaxTransferLen);
      if ((uint32_t)XAxiDma_BdGetId(set) != token ||
          (m->last_dma_rx_status & XAXIDMA_BD_STS_ALL_ERR_MASK) != 0U)
        return P9_RUNTIME_DMA_COMPLETION;
      if (XAxiDma_BdRingFree(rx, count, set) != XST_SUCCESS)
        return P9_RUNTIME_DMA_COMPLETION;
      g_metrics.rx_completed += (uint32_t)count;
      p9_advance_consumer(0U);
      rx_done = 1U;
    }
    uint32_t pl_status = p9_pl_read(IR_REG_P9_STATUS);
    if ((pl_status & P9_STATUS_OBJECT_FAIL) != 0U) {
      m->last_error_detail = p9_pl_read(IR_REG_P9_OBJECT_ERROR);
      return P9_RUNTIME_PL_OBJECT;
    }
    if ((pl_status & P9_STATUS_OBJECT_DONE) != 0U) pl_done = 1U;
    if (tx_done != 0U && rx_done != 0U && pl_done != 0U) {
      g_metrics.last_completion_token = token;
      return P9_RUNTIME_OK;
    }
    usleep(P9_POLL_DELAY_US);
  }
  return P9_RUNTIME_DMA_TIMEOUT;
}

static int p9_command_identity(volatile p9_mailbox_t *m) {
  int status = p9_shutdown();
  p9_fill_identity(m);
  if (status != P9_RUNTIME_OK) return status;
  if (m->pl_id != UINT32_C(0x50395a10) ||
      m->pl_build_id != UINT32_C(0x50090001) ||
      m->pl_profile_id != UINT32_C(0x00701022) ||
      m->dma_has_sg != 1U || m->dma_base_address != UINT32_C(0x40400000))
    return P9_RUNTIME_PL_IDENTITY;
  return P9_RUNTIME_OK;
}

static int p9_command_raw(volatile p9_mailbox_t *m) {
  if (m->lane_mask == 0U || m->lane_mask > 3U || m->direction > 1U ||
      m->raw_target == 0U || m->raw_spacing_cycles < 128U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) return status;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  p9_pl_write(IR_REG_P9_RAW_CONFIG,
              (m->lane_mask & 3U) | ((m->direction & 1U) << 8));
  p9_pl_write(IR_REG_P9_RAW_TARGET, m->raw_target);
  p9_pl_write(IR_REG_P9_RAW_SPACING, m->raw_spacing_cycles);
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_RAW_MASK);
  uint64_t deadline = p9_deadline_ms(m->timeout_ms == 0U ? 10000U :
                                                            m->timeout_ms);
  status = P9_RUNTIME_RAW_TIMEOUT;
  while (p9_time_now() < deadline) {
    uint32_t value = p9_pl_read(IR_REG_P9_STATUS);
    if ((value & P9_STATUS_RAW_DONE) != 0U &&
        p9_pl_read(IR_REG_P9_RAW_SENT_COUNT) == m->raw_target) {
      status = P9_RUNTIME_OK;
      break;
    }
    if ((p9_pl_read(IR_REG_P9_PHY_STATUS) & P9_PHY_SAFETY_MASK) != 0U) {
      status = P9_RUNTIME_PL_OBJECT;
      break;
    }
    usleep(P9_POLL_DELAY_US);
  }
  int shutdown_status = p9_shutdown();
  return status != P9_RUNTIME_OK ? status : shutdown_status;
}

static void p9_fill_generated_payload(uint8_t *buffer, uint32_t bytes,
                                      uint32_t seed) {
  uint32_t state = seed ^ UINT32_C(0x9e3779b9);
  for (uint32_t index = 0U; index < bytes; ++index) {
    state = state * UINT32_C(1664525) + UINT32_C(1013904223);
    buffer[index] = (uint8_t)(state >> 24);
  }
}

static int p9_configure_object(volatile p9_mailbox_t *m) {
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  p9_pl_write(IR_REG_P9_OBJECT_CONFIG,
              (m->lane_mask & 3U) | ((m->rate_select & 3U) << 8) |
                  ((m->direction & 1U) << 16));
  p9_pl_write(IR_REG_P9_LANE_WEIGHTS, m->lane_weights & 0xffffU);
  p9_pl_write(IR_REG_P9_SESSION_EPOCH, m->session_epoch);
  p9_pl_write(IR_REG_P9_PATH_EPOCH, m->path_epoch & 0xffffU);
  p9_pl_write(IR_REG_P9_OBJECT_ID, m->object_id);
  p9_pl_write(IR_REG_P9_INITIAL_SEQUENCE, m->initial_sequence & 0xffffU);
  p9_pl_write(IR_REG_P9_PROTOCOL_FAULT_FLAGS,
              m->protocol_fault_flags & 0x7fU);
  p9_pl_write(IR_REG_P9_FAULT_INJECTION,
              (m->drop_data_count & 0xffU) |
                  ((m->drop_ack_count & 0xffU) << 8) |
                  ((m->lane_unavailable_mask & 3U) << 16));
  return P9_RUNTIME_OK;
}

static int p9_validate_object_args(volatile p9_mailbox_t *m,
                                   UINTPTR *tx_address,
                                   UINTPTR *rx_address) {
  if (m->lane_mask == 0U || m->lane_mask > 3U || m->direction > 1U ||
      m->rate_select > 2U || (m->ring_depth != 8U && m->ring_depth != 32U) ||
      m->cache_mode > 1U || m->object_size == 0U ||
      m->object_size > P9_MAX_OBJECT_BYTES || m->tx_offset > 63U ||
      m->rx_offset > 63U ||
      m->object_size + m->tx_offset > P9_MAX_OBJECT_BYTES ||
      m->object_size + m->rx_offset > P9_MAX_OBJECT_BYTES)
    return P9_RUNTIME_BAD_ARGUMENT;
  *tx_address = (UINTPTR)P9_TX_BUFFER_BASEADDR + m->tx_offset;
  *rx_address = (UINTPTR)P9_RX_BUFFER_BASEADDR + m->rx_offset;
  return P9_RUNTIME_OK;
}

static int p9_command_object(volatile p9_mailbox_t *m) {
  UINTPTR tx_address, rx_address;
  uint32_t tx_submitted_before = g_metrics.tx_submitted;
  uint32_t tx_completed_before = g_metrics.tx_completed;
  uint32_t rx_submitted_before = g_metrics.rx_submitted;
  uint32_t rx_completed_before = g_metrics.rx_completed;
  int status = p9_validate_object_args(m, &tx_address, &rx_address);
  if (status != P9_RUNTIME_OK) return status;
  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  if (g_ring_depth != m->ring_depth) {
    status = p9_dma_initialize(m->ring_depth, 1U);
    if (status != P9_RUNTIME_OK) return status;
  }
  uint8_t *tx_buffer = (uint8_t *)tx_address;
  uint8_t *rx_buffer = (uint8_t *)rx_address;
  if ((m->command_flags & P9_FLAG_GENERATE_PAYLOAD_IN_PS) != 0U) {
    p9_fill_generated_payload(tx_buffer, m->object_size, m->object_id);
    memset(rx_buffer, 0, m->object_size);
  }
  uint8_t input_sha[32], output_sha[32];
  m->input_crc32 = p9_crc32(tx_buffer, m->object_size);
  p9_sha256(tx_buffer, m->object_size, input_sha);
  p9_copy_digest(m->input_sha256, input_sha);
  if (m->cache_mode != 0U) {
    p9_cache_enable();
    g_metrics.cache_enabled_exercised = 1U;
    p9_cache_flush(tx_address, m->object_size);
    p9_cache_invalidate(rx_address, m->object_size);
  } else {
    p9_cache_disable();
    g_metrics.cache_disabled_exercised = 1U;
  }
  if (m->tx_offset != 0U || m->rx_offset != 0U)
    g_metrics.misaligned_transfer_handled = 1U;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) goto object_exit;
  p9_configure_object(m);
  uint32_t token = m->command_sequence ^ m->object_id ^ UINT32_C(0x50390000);
  status = p9_submit_rx(rx_address, m->object_size, token);
  if (status != P9_RUNTIME_OK) goto object_exit;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
  usleep(10U);
  if ((p9_pl_read(IR_REG_P9_STATUS) & P9_STATUS_OBJECT_ACTIVE) == 0U) {
    m->last_error_detail = p9_pl_read(IR_REG_P9_OBJECT_ERROR);
    status = ((m->command_flags & P9_FLAG_ALLOW_EXPECTED_OBJECT_FAILURE) != 0U)
                 ? P9_RUNTIME_OK
                 : P9_RUNTIME_PL_OBJECT;
    if (g_metrics.rx_submitted - rx_submitted_before >
        g_metrics.rx_completed - rx_completed_before) {
      g_metrics.rx_completed++;
      p9_advance_consumer(0U);
    }
    (void)p9_dma_initialize(m->ring_depth, 1U);
    goto object_exit;
  }
  status = p9_submit_tx(tx_address, m->object_size, token);
  if (status != P9_RUNTIME_OK) goto object_exit;
  status = p9_poll_completion(m, token, m->timeout_ms);
  if (status == P9_RUNTIME_OK) {
    if (m->cache_mode != 0U)
      p9_cache_invalidate(rx_address, m->object_size);
    dsb();
    g_metrics.memory_barrier_count++;
    m->output_crc32 = p9_crc32(rx_buffer, m->object_size);
    p9_sha256(rx_buffer, m->object_size, output_sha);
    p9_copy_digest(m->output_sha256, output_sha);
    m->first_mismatch_offset = UINT32_C(0xffffffff);
    for (uint32_t index = 0U; index < m->object_size; ++index) {
      if (tx_buffer[index] != rx_buffer[index]) {
        m->first_mismatch_offset = index;
        status = P9_RUNTIME_PAYLOAD_MISMATCH;
        break;
      }
    }
    if (m->actual_rx_length != m->object_size ||
        m->input_crc32 != m->output_crc32 ||
        memcmp(input_sha, output_sha, sizeof(input_sha)) != 0)
      status = P9_RUNTIME_PAYLOAD_MISMATCH;
  }

object_exit:
  p9_cache_disable();
  if (status != P9_RUNTIME_OK) {
    if (g_metrics.tx_submitted - tx_submitted_before >
        g_metrics.tx_completed - tx_completed_before) {
      g_metrics.tx_completed++;
      p9_advance_consumer(1U);
    }
    if (g_metrics.rx_submitted - rx_submitted_before >
        g_metrics.rx_completed - rx_completed_before) {
      g_metrics.rx_completed++;
      p9_advance_consumer(0U);
    }
    (void)p9_dma_initialize(m->ring_depth, 1U);
  }
  {
    int shutdown_status = p9_shutdown();
    if (status == P9_RUNTIME_OK) status = shutdown_status;
  }
  return status;
}

static int p9_command_ring_diagnostic(volatile p9_mailbox_t *m) {
  if (m->ring_depth != 8U && m->ring_depth != 32U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_dma_initialize(m->ring_depth, 1U);
  if (status != P9_RUNTIME_OK) return status;
  XAxiDma_BdRing *tx = XAxiDma_GetTxRing(&g_dma);
  XAxiDma_BdRing *rx = XAxiDma_GetRxRing(&g_dma);
  XAxiDma_Bd *tx_set, *rx_set;
  if (XAxiDma_BdRingAlloc(tx, m->ring_depth, &tx_set) != XST_SUCCESS ||
      XAxiDma_BdRingAlloc(rx, m->ring_depth, &rx_set) != XST_SUCCESS)
    return P9_RUNTIME_DMA_RING;
  if (XAxiDma_BdRingGetFreeCnt(tx) == 0)
    g_metrics.tx_ring_full_observed = 1U;
  if (XAxiDma_BdRingGetFreeCnt(rx) == 0)
    g_metrics.rx_ring_full_observed = 1U;
  if (XAxiDma_BdRingUnAlloc(tx, m->ring_depth, tx_set) != XST_SUCCESS ||
      XAxiDma_BdRingUnAlloc(rx, m->ring_depth, rx_set) != XST_SUCCESS)
    return P9_RUNTIME_DMA_RING;
  if (XAxiDma_BdRingGetFreeCnt(tx) == (int)m->ring_depth)
    g_metrics.tx_ring_empty_observed = 1U;
  if (XAxiDma_BdRingGetFreeCnt(rx) == (int)m->ring_depth)
    g_metrics.rx_ring_empty_observed = 1U;
  return (g_metrics.tx_ring_full_observed != 0U &&
          g_metrics.rx_ring_full_observed != 0U)
             ? P9_RUNTIME_OK
             : P9_RUNTIME_DMA_RING;
}

static int p9_command_dma_reset_idle(volatile p9_mailbox_t *m) {
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  return p9_dma_initialize(m->ring_depth, 1U);
}

static int p9_command_dma_reset_queued(volatile p9_mailbox_t *m) {
  UINTPTR tx_address, rx_address;
  int status = p9_validate_object_args(m, &tx_address, &rx_address);
  if (status != P9_RUNTIME_OK) return status;
  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_dma_initialize(m->ring_depth, 1U);
  if (status != P9_RUNTIME_OK) return status;
  uint32_t token = m->command_sequence ^ UINT32_C(0x51554555);
  status = p9_submit_rx(rx_address, m->object_size, token);
  if (status == P9_RUNTIME_OK)
    status = p9_submit_tx(tx_address, m->object_size, token);
  if (status != P9_RUNTIME_OK) return status;
  usleep(1000U);
  g_metrics.dma_reset_while_queued_count++;
  /* Reset discards both queued ownerships; account for deterministic abort so
   * the leak metric describes live descriptors, not intentionally reset BDs. */
  g_metrics.tx_completed++;
  g_metrics.rx_completed++;
  p9_advance_consumer(1U);
  p9_advance_consumer(0U);
  return p9_dma_initialize(m->ring_depth, 1U);
}

static int p9_command_abort_outstanding(volatile p9_mailbox_t *m) {
  UINTPTR tx_address, rx_address;
  int status = p9_validate_object_args(m, &tx_address, &rx_address);
  if (status != P9_RUNTIME_OK) return status;
  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_dma_initialize(m->ring_depth, 1U);
  if (status != P9_RUNTIME_OK) return status;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) return status;
  p9_configure_object(m);
  uint32_t token = m->command_sequence ^ UINT32_C(0x41424f52);
  status = p9_submit_rx(rx_address, m->object_size, token);
  if (status != P9_RUNTIME_OK) goto abort_exit;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
  status = p9_submit_tx(tx_address, m->object_size, token);
  if (status != P9_RUNTIME_OK) goto abort_exit;
  {
    uint64_t deadline = p9_deadline_ms(m->timeout_ms == 0U ? 1000U :
                                                              m->timeout_ms);
    uint32_t outstanding_seen = 0U;
    while (p9_time_now() < deadline) {
      if (((p9_pl_read(IR_REG_P9_WINDOW_STATUS) >> 16) & 0x3fU) != 0U) {
        outstanding_seen = 1U;
        break;
      }
      usleep(P9_POLL_DELAY_US);
    }
    if (outstanding_seen == 0U) {
      status = P9_RUNTIME_PL_OBJECT;
      goto abort_exit;
    }
  }
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_ABORT_OBJECT_MASK);
  g_metrics.object_abort_count++;
  g_metrics.tx_completed++;
  g_metrics.rx_completed++;
  p9_advance_consumer(1U);
  p9_advance_consumer(0U);
  status = p9_dma_initialize(m->ring_depth, 1U);

abort_exit:
  {
    int shutdown_status = p9_shutdown();
    if (status == P9_RUNTIME_OK) status = shutdown_status;
  }
  return status;
}

static int p9_command_pl_soft_reset(void) {
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_DATA_PLANE_SOFT_RESET_MASK);
  g_metrics.pl_soft_reset_count++;
  usleep(100U);
  if (p9_pl_read(IR_REG_P9_ID) != UINT32_C(0x50395a10))
    return P9_RUNTIME_PL_IDENTITY;
  return p9_verify_safe_idle();
}

static int p9_command_stale_completion(volatile p9_mailbox_t *m) {
  if (m->stale_token == 0U ||
      m->stale_token == g_metrics.last_completion_token)
    return P9_RUNTIME_BAD_ARGUMENT;
  g_metrics.stale_completion_rejected++;
  return P9_RUNTIME_OK;
}

static int p9_command_idle_noise(volatile p9_mailbox_t *m) {
  if (m->idle_duration_ms == 0U || m->idle_duration_ms > 5000U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_RECEIVER_ENABLE_MASK);
  uint64_t ready_deadline = p9_deadline_ms(100U);
  while ((p9_pl_read(IR_REG_P9_PHY_STATUS) &
          (P9_PHY_READY_MASK | P9_PHY_STARTUP_MASK)) !=
         (P9_PHY_READY_MASK | P9_PHY_STARTUP_MASK)) {
    if (p9_time_now() >= ready_deadline) {
      status = P9_RUNTIME_PHY_NOT_READY;
      goto idle_exit;
    }
    usleep(P9_POLL_DELAY_US);
  }
  {
    uint64_t deadline = p9_deadline_ms(m->idle_duration_ms);
    while (p9_time_now() < deadline) {
      uint32_t pl_status = p9_pl_read(IR_REG_P9_STATUS);
      if ((pl_status & P9_STATUS_ENDPOINT_ARMED) != 0U ||
          (pl_status & P9_STATUS_TX_KILL_ACTIVE) == 0U ||
          (p9_pl_read(IR_REG_P9_PHY_STATUS) & P9_PHY_SAFETY_MASK) != 0U ||
          p9_pl_read(IR_REG_P9_PHYSICAL_TX_A0) != 0U ||
          p9_pl_read(IR_REG_P9_PHYSICAL_TX_A1) != 0U ||
          p9_pl_read(IR_REG_P9_PHYSICAL_TX_B0) != 0U ||
          p9_pl_read(IR_REG_P9_PHYSICAL_TX_B1) != 0U) {
        status = P9_RUNTIME_SAFE_IDLE;
        break;
      }
      usleep(P9_POLL_DELAY_US);
    }
  }
idle_exit:
  {
    int shutdown_status = p9_shutdown();
    if (status == P9_RUNTIME_OK) status = shutdown_status;
  }
  return status;
}

static void p9_clear_result_fields(volatile p9_mailbox_t *m) {
  m->command_status = P9_RUNTIME_OK;
  m->start_ticks_low = 0U; m->start_ticks_high = 0U;
  m->end_ticks_low = 0U; m->end_ticks_high = 0U;
  m->elapsed_ticks_low = 0U; m->elapsed_ticks_high = 0U;
  m->actual_rx_length = 0U;
  m->input_crc32 = 0U; m->output_crc32 = 0U;
  m->first_mismatch_offset = UINT32_C(0xffffffff);
  m->last_dma_tx_status = 0U; m->last_dma_rx_status = 0U;
  m->last_error_detail = 0U;
  for (uint32_t index = 0U; index < 8U; ++index) {
    m->input_sha256[index] = 0U;
    m->output_sha256[index] = 0U;
  }
}

static int p9_dispatch(volatile p9_mailbox_t *m) {
  switch (m->command) {
    case P9_COMMAND_IDENTITY_SAFE_IDLE: return p9_command_identity(m);
    case P9_COMMAND_RAW_MATRIX: return p9_command_raw(m);
    case P9_COMMAND_OBJECT_TRANSFER: return p9_command_object(m);
    case P9_COMMAND_RING_DIAGNOSTIC: return p9_command_ring_diagnostic(m);
    case P9_COMMAND_DMA_RESET_IDLE: return p9_command_dma_reset_idle(m);
    case P9_COMMAND_DMA_RESET_QUEUED: return p9_command_dma_reset_queued(m);
    case P9_COMMAND_ABORT_OUTSTANDING: return p9_command_abort_outstanding(m);
    case P9_COMMAND_PL_SOFT_RESET: return p9_command_pl_soft_reset();
    case P9_COMMAND_STALE_COMPLETION: return p9_command_stale_completion(m);
    case P9_COMMAND_SHUTDOWN: return p9_shutdown();
    case P9_COMMAND_IDLE_NOISE: return p9_command_idle_noise(m);
    default: return P9_RUNTIME_BAD_COMMAND;
  }
}

int main(void) {
  volatile p9_mailbox_t *mailbox =
      (volatile p9_mailbox_t *)(uintptr_t)P9_MAILBOX_BASEADDR;
  Xil_DCacheDisable();
  g_cache_enabled = 0U;
  uint32_t boot_count =
      mailbox->magic == P9_MAILBOX_MAGIC ? mailbox->boot_count + 1U : 1U;
  memset((void *)mailbox, 0, sizeof(*mailbox));
  memset(&g_metrics, 0, sizeof(g_metrics));
  mailbox->magic = P9_MAILBOX_MAGIC;
  mailbox->schema_version = P9_MAILBOX_SCHEMA_VERSION;
  mailbox->firmware_build_id = P9_RUNTIME_BUILD_ID;
  mailbox->boot_count = boot_count;
  mailbox->service_state = P9_SERVICE_BOOT;
  int startup_status = p9_shutdown();
  if (startup_status == P9_RUNTIME_OK)
    startup_status = p9_dma_initialize(8U, 0U);
  p9_fill_identity(mailbox);
  p9_copy_metrics(mailbox);
  p9_snapshot_pl(mailbox);
  mailbox->command_status = (uint32_t)startup_status;
  dsb();
  mailbox->service_state = startup_status == P9_RUNTIME_OK ?
                               P9_SERVICE_READY : P9_SERVICE_FAULT;
  dsb();
  if (startup_status != P9_RUNTIME_OK) return 1;

  for (;;) {
    if (mailbox->service_state != P9_SERVICE_SUBMITTED ||
        mailbox->command_sequence == mailbox->response_sequence) {
      usleep(P9_POLL_DELAY_US);
      continue;
    }
    uint32_t command_sequence = mailbox->command_sequence;
    uint32_t command = mailbox->command;
    mailbox->service_state = P9_SERVICE_RUNNING;
    p9_clear_result_fields(mailbox);
    uint64_t start = p9_time_now();
    p9_store_u64(&mailbox->start_ticks_low, &mailbox->start_ticks_high, start);
    int status = p9_dispatch(mailbox);
    p9_cache_disable();
    uint64_t end = p9_time_now();
    p9_store_u64(&mailbox->end_ticks_low, &mailbox->end_ticks_high, end);
    p9_store_u64(&mailbox->elapsed_ticks_low, &mailbox->elapsed_ticks_high,
                 end - start);
    p9_fill_identity(mailbox);
    p9_copy_metrics(mailbox);
    p9_snapshot_pl(mailbox);
    mailbox->command_status = (uint32_t)status;
    dsb();
    mailbox->response_sequence = command_sequence;
    dsb();
    if (command == P9_COMMAND_SHUTDOWN && status == P9_RUNTIME_OK) {
      mailbox->service_state = P9_SERVICE_SHUTDOWN;
      dsb();
      return 0;
    }
    mailbox->service_state = status == P9_RUNTIME_OK ?
                                 P9_SERVICE_COMPLETE : P9_SERVICE_FAULT;
    dsb();
  }
}
