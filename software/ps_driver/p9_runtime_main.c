#include "ir_regs.h"
#include "p9_crypto.h"
#include "p9_runtime_protocol.h"
#include "p10_1_runtime_protocol.h"
#include "p10_5_dual_direction_config.h"

#include "sleep.h"
#include "xaxidma.h"
#ifdef P10_PS_ACTIVITY_LEDS
#include "xgpiops.h"
#endif
#include "xil_cache.h"
#include "xil_io.h"
#include "xparameters.h"
#include "xstatus.h"
#include "xtime_l.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifndef P10_ENDPOINT_ROLE
#define P10_ENDPOINT_ROLE 0
#endif

#ifndef P10_LANE_COUNT
#define P10_LANE_COUNT 2
#endif

#if P10_LANE_COUNT != 2 && P10_LANE_COUNT != 4
#error "P10_LANE_COUNT must be 2 or 4 for the AX7020 runtime"
#endif

#define P10_LANE_MASK ((UINT32_C(1) << P10_LANE_COUNT) - UINT32_C(1))
#define P10_PHYSICAL_STATUS_WIDTH (2U * P10_LANE_COUNT)
#define P10_PHY_READY_ALL_MASK \
  ((UINT32_C(1) << P10_PHYSICAL_STATUS_WIDTH) - UINT32_C(1))
#define P10_PHY_STARTUP_SHIFT P10_PHYSICAL_STATUS_WIDTH
#define P10_PHY_SAFETY_SHIFT (2U * P10_PHYSICAL_STATUS_WIDTH)

#if P10_ENDPOINT_ROLE < 0 || P10_ENDPOINT_ROLE > 2
#error "P10_ENDPOINT_ROLE must be 0 (legacy P9), 1 (fixed), or 2 (rotating)"
#endif

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
  P9_POLL_DELAY_US = 50U,
  P9_RESET_POLLS = 200000U,
  P9_RFAP_V1_HEADER_BYTES = 32U,
  P9_RFAP_V1_CHUNK_BYTES = 215U,
  P9_RFAP_V1_MAX_USEFUL_BYTES = 8U * 1024U * 1024U,
  P9_RFAP_VNEXT_HEADER_BYTES = 48U,
  P9_RFAP_VNEXT_CHUNK_BYTES = 64U * 1024U,
  P9_DMA_MAX_TRANSFER_BYTES = 0x03ffffffU,
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

/*
 * P10.3 AX7020 PS activity indicators.  The official board circuit connects
 * PS LED1 to MIO0 and PS LED2 to MIO13 through active-low sink paths.  These
 * GPIOs are monitor-only: no readback or LED state enters transport, permit,
 * SD, Txd kill, admission, flow-control, or recovery decisions.
 */
#ifdef P10_PS_ACTIVITY_LEDS
enum {
  P10_PS_LED_TX_MIO = 0U,
  P10_PS_LED_RX_MIO = 13U,
};
static XGpioPs g_ps_gpio;
static uint32_t g_ps_gpio_initialized;
static uint32_t g_ps_tx_descriptors_inflight;
static uint32_t g_ps_rx_descriptors_inflight;
static uint32_t g_ps_activity_counter_fault;

static void p10_ps_activity_leds_refresh(void) {
  if (g_ps_gpio_initialized != 0U) {
    XGpioPs_WritePin(&g_ps_gpio, P10_PS_LED_TX_MIO,
                     g_ps_tx_descriptors_inflight == 0U ? 1U : 0U);
    XGpioPs_WritePin(&g_ps_gpio, P10_PS_LED_RX_MIO,
                     g_ps_rx_descriptors_inflight == 0U ? 1U : 0U);
    dsb();
  }
}

static void p10_ps_activity_leds_force_off(void) {
  g_ps_tx_descriptors_inflight = 0U;
  g_ps_rx_descriptors_inflight = 0U;
  p10_ps_activity_leds_refresh();
}

static uint32_t p10_ps_activity_leds_faulted(void) {
  return g_ps_activity_counter_fault;
}

static void p10_ps_dma_activity_begin(uint32_t tx, uint32_t count) {
  uint32_t *inflight = tx != 0U ? &g_ps_tx_descriptors_inflight :
                                  &g_ps_rx_descriptors_inflight;
  if (count == 0U || *inflight > UINT32_MAX - count) {
    g_ps_activity_counter_fault = 1U;
    p10_ps_activity_leds_force_off();
    return;
  }
  *inflight += count;
  p10_ps_activity_leds_refresh();
}

static void p10_ps_dma_activity_end(uint32_t tx, uint32_t count) {
  uint32_t *inflight = tx != 0U ? &g_ps_tx_descriptors_inflight :
                                  &g_ps_rx_descriptors_inflight;
  if (count == 0U || *inflight < count) {
    g_ps_activity_counter_fault = 1U;
    p10_ps_activity_leds_force_off();
    return;
  }
  *inflight -= count;
  p10_ps_activity_leds_refresh();
}

static int p10_ps_activity_leds_initialize(void) {
  XGpioPs_Config *config = XGpioPs_LookupConfig(XPAR_XGPIOPS_0_DEVICE_ID);
  if (config == NULL ||
      XGpioPs_CfgInitialize(&g_ps_gpio, config, config->BaseAddr) !=
          XST_SUCCESS)
    return P9_RUNTIME_PS_LED_CONFIG;

  /* Disable output, then preload inactive HIGH before enabling either pin. */
  XGpioPs_SetOutputEnablePin(&g_ps_gpio, P10_PS_LED_TX_MIO, 0U);
  XGpioPs_SetOutputEnablePin(&g_ps_gpio, P10_PS_LED_RX_MIO, 0U);
  XGpioPs_WritePin(&g_ps_gpio, P10_PS_LED_TX_MIO, 1U);
  XGpioPs_WritePin(&g_ps_gpio, P10_PS_LED_RX_MIO, 1U);
  XGpioPs_SetDirectionPin(&g_ps_gpio, P10_PS_LED_TX_MIO, 1U);
  XGpioPs_SetDirectionPin(&g_ps_gpio, P10_PS_LED_RX_MIO, 1U);
  XGpioPs_SetOutputEnablePin(&g_ps_gpio, P10_PS_LED_TX_MIO, 1U);
  XGpioPs_SetOutputEnablePin(&g_ps_gpio, P10_PS_LED_RX_MIO, 1U);
  if (XGpioPs_GetDirectionPin(&g_ps_gpio, P10_PS_LED_TX_MIO) != 1U ||
      XGpioPs_GetDirectionPin(&g_ps_gpio, P10_PS_LED_RX_MIO) != 1U ||
      XGpioPs_GetOutputEnablePin(&g_ps_gpio, P10_PS_LED_TX_MIO) != 1U ||
      XGpioPs_GetOutputEnablePin(&g_ps_gpio, P10_PS_LED_RX_MIO) != 1U ||
      XGpioPs_ReadPin(&g_ps_gpio, P10_PS_LED_TX_MIO) != 1U ||
      XGpioPs_ReadPin(&g_ps_gpio, P10_PS_LED_RX_MIO) != 1U) {
    XGpioPs_WritePin(&g_ps_gpio, P10_PS_LED_TX_MIO, 1U);
    XGpioPs_WritePin(&g_ps_gpio, P10_PS_LED_RX_MIO, 1U);
    XGpioPs_SetOutputEnablePin(&g_ps_gpio, P10_PS_LED_TX_MIO, 0U);
    XGpioPs_SetOutputEnablePin(&g_ps_gpio, P10_PS_LED_RX_MIO, 0U);
    return P9_RUNTIME_PS_LED_CONFIG;
  }
  g_ps_gpio_initialized = 1U;
  g_ps_activity_counter_fault = 0U;
  p10_ps_activity_leds_force_off();
  return P9_RUNTIME_OK;
}
#else
static void p10_ps_activity_leds_force_off(void) {}
static void p10_ps_dma_activity_begin(uint32_t tx, uint32_t count) {
  (void)tx; (void)count;
}
static void p10_ps_dma_activity_end(uint32_t tx, uint32_t count) {
  (void)tx; (void)count;
}
static int p10_ps_activity_leds_initialize(void) { return P9_RUNTIME_OK; }
static uint32_t p10_ps_activity_leds_faulted(void) { return 0U; }
#endif

static uint32_t p9_local_sender(uint32_t direction) {
  if (P10_ENDPOINT_ROLE == 0) return 1U;
  return P10_ENDPOINT_ROLE == 1 ? (direction == 0U) : (direction == 1U);
}

static uint32_t p9_expected_phy_mask(void) {
  if (P10_ENDPOINT_ROLE == 1) return P10_LANE_MASK;
  if (P10_ENDPOINT_ROLE == 2) return P10_LANE_MASK << P10_LANE_COUNT;
  return P10_PHY_READY_ALL_MASK;
}

static uint32_t p9_expected_pl_id(void) {
  return P10_ENDPOINT_ROLE == 0 ? UINT32_C(0x50395a10) :
                                 UINT32_C(0x5031305a);
}

#if P10_ENDPOINT_ROLE != 0
#ifndef P10_EXPECTED_PL_BUILD_ID
#error "P10 role-bound runtime requires P10_EXPECTED_PL_BUILD_ID"
#endif
static uint32_t p9_expected_pl_build_id(void) {
  return P10_EXPECTED_PL_BUILD_ID;
}

static uint32_t p9_expected_pl_profile_id(void) {
  if (P10_ENDPOINT_ROLE == 1)
    return P10_LANE_COUNT == 4 ? UINT32_C(0x702004f0) :
                                UINT32_C(0x702000f0);
  if (P10_ENDPOINT_ROLE == 2)
    return P10_LANE_COUNT == 4 ? UINT32_C(0x702004a0) :
                                UINT32_C(0x702000a0);
  return UINT32_C(0x00701022);
}
#endif

static int p9_reset_stream_path(uint32_t depth, uint32_t count_pl_reset,
                                uint32_t count_dma_reset);

static void p9_write_u16_le(uint8_t *output, uint16_t value) {
  output[0] = (uint8_t)value;
  output[1] = (uint8_t)(value >> 8);
}

static void p9_write_u32_le(uint8_t *output, uint32_t value) {
  output[0] = (uint8_t)value;
  output[1] = (uint8_t)(value >> 8);
  output[2] = (uint8_t)(value >> 16);
  output[3] = (uint8_t)(value >> 24);
}

static void p9_write_u64_le(uint8_t *output, uint64_t value) {
  p9_write_u32_le(output, (uint32_t)value);
  p9_write_u32_le(output + 4U, (uint32_t)(value >> 32));
}

static uint16_t p9_read_u16_le(const uint8_t *input) {
  return (uint16_t)((uint16_t)input[0] | ((uint16_t)input[1] << 8));
}

static uint32_t p9_read_u32_le(const uint8_t *input) {
  return (uint32_t)input[0] | ((uint32_t)input[1] << 8) |
         ((uint32_t)input[2] << 16) | ((uint32_t)input[3] << 24);
}

static uint64_t p9_read_u64_le(const uint8_t *input) {
  return (uint64_t)p9_read_u32_le(input) |
         ((uint64_t)p9_read_u32_le(input + 4U) << 32);
}

static uint8_t p9_pattern_byte(uint32_t object_id, uint32_t index) {
  static const uint8_t binary_corpus[32] = {
      0x00, 0xff, 0x55, 0xaa, 0x7e, 0x81, 0x01, 0x80,
      0x10, 0xef, 0x33, 0xcc, 0x0f, 0xf0, 0x5a, 0xa5,
      0x52, 0x46, 0x41, 0x50, 0x00, 0x01, 0xfe, 0xff,
      0x13, 0x37, 0xde, 0xad, 0xbe, 0xef, 0xc3, 0x3c};
  uint32_t mode = object_id >> 28;
  if (mode == 1U) return 0U;
  if (mode == 2U) return 0xffU;
  if (mode == 3U) return (uint8_t)index;
  if (mode == 4U) return binary_corpus[index & 31U];
  uint32_t mixed = (object_id & UINT32_C(0x0fffffff)) ^
                   (index * UINT32_C(0x9e3779b9)) ^ UINT32_C(0xa5c31f27);
  mixed ^= mixed >> 16;
  mixed *= UINT32_C(0x7feb352d);
  mixed ^= mixed >> 15;
  mixed *= UINT32_C(0x846ca68b);
  mixed ^= mixed >> 16;
  return (uint8_t)(mixed >> 24);
}

static uint32_t p9_crc32_update_byte(uint32_t crc, uint8_t value) {
  crc ^= value;
  for (uint32_t bit = 0U; bit < 8U; ++bit)
    crc = (crc & 1U) != 0U ? (crc >> 1) ^ UINT32_C(0xedb88320) : crc >> 1;
  return crc;
}

static uint32_t p9_generated_crc32(uint32_t object_id, uint32_t bytes) {
  uint32_t crc = UINT32_C(0xffffffff);
  for (uint32_t index = 0U; index < bytes; ++index)
    crc = p9_crc32_update_byte(crc, p9_pattern_byte(object_id, index));
  return crc ^ UINT32_C(0xffffffff);
}

static uint32_t p9_pl_read(uint32_t offset) {
  return Xil_In32((UINTPTR)IR_PL_BASEADDR + offset);
}

static void p9_pl_write(uint32_t offset, uint32_t value) {
  Xil_Out32((UINTPTR)IR_PL_BASEADDR + offset, value);
  dsb();
  g_metrics.memory_barrier_count++;
}

static uint32_t p10_runtime_local_raw_count(uint32_t lane) {
#if P10_LANE_COUNT == 4
  uint32_t module = P10_ENDPOINT_ROLE == 2 ? lane + 4U : lane;
  p9_pl_write(IR_REG_P10_2_SNAPSHOT_CONTROL, 1U);
  return p9_pl_read(ir_p10_2_module_word_offset(module, 0U));
#else
  if (P10_ENDPOINT_ROLE == 1)
    return p9_pl_read(lane == 0U ? IR_REG_P9_RAW_RX_A0 :
                                   IR_REG_P9_RAW_RX_A1);
  if (P10_ENDPOINT_ROLE == 2)
    return p9_pl_read(lane == 0U ? IR_REG_P9_RAW_RX_B0 :
                                   IR_REG_P9_RAW_RX_B1);
  return p9_pl_read(IR_REG_P9_RAW_RX_A0 + 4U * lane);
#endif
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

static void p9_capture_terminal_window(volatile p9_mailbox_t *mailbox) {
  /* A full shutdown deliberately asserts abort_all_i in PL and clears the TX
   * next/ACK-base registers.  Capture the completed object's terminal window
   * directly from MMIO before shutdown, then publish the validity marker last.
   * The normal PL snapshot remains a separate, post-shutdown safety record. */
  mailbox->terminal_window_valid = 0U;
  mailbox->terminal_window_command_sequence = mailbox->command_sequence;
  mailbox->terminal_tx_sequence_base = p9_pl_read(IR_REG_P9_TX_SEQUENCE_BASE);
  mailbox->terminal_window_status = p9_pl_read(IR_REG_P9_WINDOW_STATUS);
  dsb();
  mailbox->terminal_window_valid = P9_TERMINAL_WINDOW_VALID;
  dsb();
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
  p10_ps_activity_leds_force_off();
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
  uint32_t expected = p9_expected_phy_mask();
  uint32_t expected_startup = expected << P10_PHY_STARTUP_SHIFT;
  uint32_t expected_safety = expected << P10_PHY_SAFETY_SHIFT;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_RECEIVER_ENABLE_MASK);
  usleep(600U);
  uint64_t deadline = p9_deadline_ms(100U);
  do {
    uint32_t phy = p9_pl_read(IR_REG_P9_PHY_STATUS);
    if ((phy & expected_safety) != 0U) return P9_RUNTIME_PHY_NOT_READY;
    if ((phy & (expected | expected_startup)) ==
        (expected | expected_startup))
      break;
    usleep(P9_POLL_DELAY_US);
  } while (p9_time_now() < deadline);
  uint32_t phy = p9_pl_read(IR_REG_P9_PHY_STATUS);
  if ((phy & (expected | expected_startup)) !=
      (expected | expected_startup))
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
  p10_ps_activity_leds_force_off();
  if (depth != 8U && depth != 16U && depth != 32U)
    return P9_RUNTIME_BAD_ARGUMENT;
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
  p10_ps_dma_activity_begin(0U, 1U);
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
  p10_ps_dma_activity_begin(1U, 1U);
  return P9_RUNTIME_OK;
}

static int p9_poll_completion(volatile p9_mailbox_t *m, uint32_t token,
                              uint32_t timeout_ms, uint32_t require_tx,
                              uint32_t require_rx) {
  XAxiDma_BdRing *tx = XAxiDma_GetTxRing(&g_dma);
  XAxiDma_BdRing *rx = XAxiDma_GetRxRing(&g_dma);
  uint32_t tx_done = require_tx == 0U;
  uint32_t rx_done = require_rx == 0U;
  uint32_t pl_done = 0U;
  uint64_t poll_start = p9_time_now();
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
      p10_ps_dma_activity_end(1U, (uint32_t)count);
      g_metrics.tx_completed += (uint32_t)count;
      p9_advance_consumer(1U);
      tx_done = 1U;
      p9_store_u64(&m->dma_tx_completion_ticks_low,
                   &m->dma_tx_completion_ticks_high,
                   p9_time_now() - poll_start);
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
      p10_ps_dma_activity_end(0U, (uint32_t)count);
      g_metrics.rx_completed += (uint32_t)count;
      p9_advance_consumer(0U);
      rx_done = 1U;
      p9_store_u64(&m->dma_rx_completion_ticks_low,
                   &m->dma_rx_completion_ticks_high,
                   p9_time_now() - poll_start);
    }
    uint32_t pl_status = p9_pl_read(IR_REG_P9_STATUS);
    if ((pl_status & P9_STATUS_OBJECT_FAIL) != 0U) {
      m->last_error_detail = p9_pl_read(IR_REG_P9_OBJECT_ERROR);
      return P9_RUNTIME_PL_OBJECT;
    }
    if ((pl_status & P9_STATUS_OBJECT_DONE) != 0U && pl_done == 0U) {
      pl_done = 1U;
      p9_store_u64(&m->pl_completion_ticks_low,
                   &m->pl_completion_ticks_high,
                   p9_time_now() - poll_start);
    }
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
#if P10_ENDPOINT_ROLE == 0
  /* Keep the frozen P9 identity literals explicit for source-level contract
   * checks and compile the P10 role identities only in their role-bound ELF. */
  if (m->pl_id != UINT32_C(0x50395a10) ||
      m->pl_build_id != UINT32_C(0x5009000b) ||
      m->pl_profile_id != UINT32_C(0x00701022) ||
      m->pl_register_map_version != IR_REGISTER_MAP_VERSION ||
      m->pl_register_map_hash_low != IR_REGISTER_MAP_HASH_LOW ||
      m->pl_capabilities != UINT32_C(0xf7204221) ||
      m->dma_has_sg != 1U || m->dma_base_address != UINT32_C(0x40400000))
    return P9_RUNTIME_PL_IDENTITY;
#else
  if (m->pl_id != p9_expected_pl_id() ||
      m->pl_build_id != p9_expected_pl_build_id() ||
      m->pl_profile_id != p9_expected_pl_profile_id() ||
      m->pl_register_map_version != IR_REGISTER_MAP_VERSION ||
      m->pl_register_map_hash_low != IR_REGISTER_MAP_HASH_LOW ||
      m->pl_capabilities !=
          (P10_LANE_COUNT == 4 ? UINT32_C(0xf7204441) :
                                UINT32_C(0xf7204221)) ||
      m->dma_has_sg != 1U || m->dma_base_address != UINT32_C(0x40400000))
    return P9_RUNTIME_PL_IDENTITY;
#endif
  return P9_RUNTIME_OK;
}

static int p9_command_raw(volatile p9_mailbox_t *m) {
  if (m->lane_mask == 0U || (m->lane_mask & ~P10_LANE_MASK) != 0U ||
      m->direction > 1U ||
      m->raw_target == 0U || m->raw_spacing_cycles < 128U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) return status;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  p9_pl_write(IR_REG_P9_RAW_CONFIG,
              (m->lane_mask & P10_LANE_MASK) |
                  ((m->direction & 1U) << 8));
  p9_pl_write(IR_REG_P9_RAW_TARGET, m->raw_target);
  p9_pl_write(IR_REG_P9_RAW_SPACING, m->raw_spacing_cycles);
  uint32_t local_source = p9_local_sender(m->direction);
  if (P10_ENDPOINT_ROLE == 0 || local_source != 0U)
    p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_RAW_MASK);
  uint64_t deadline = p9_deadline_ms(m->timeout_ms == 0U ? 10000U :
                                                            m->timeout_ms);
  status = P9_RUNTIME_RAW_TIMEOUT;
  while (p9_time_now() < deadline) {
    uint32_t value = p9_pl_read(IR_REG_P9_STATUS);
    if (P10_ENDPOINT_ROLE == 0 || local_source != 0U) {
      if ((value & P9_STATUS_RAW_DONE) != 0U &&
          p9_pl_read(IR_REG_P9_RAW_SENT_COUNT) == m->raw_target) {
        status = P9_RUNTIME_OK;
        break;
      }
    } else {
      uint32_t all_reached = 1U;
      for (uint32_t lane = 0U; lane < P10_LANE_COUNT; ++lane) {
        if ((m->lane_mask & (UINT32_C(1) << lane)) != 0U &&
            p10_runtime_local_raw_count(lane) < m->raw_target)
          all_reached = 0U;
      }
      if (all_reached != 0U) {
        status = P9_RUNTIME_OK;
        break;
      }
    }
    if ((p9_pl_read(IR_REG_P9_PHY_STATUS) &
         (P10_PHY_READY_ALL_MASK << P10_PHY_SAFETY_SHIFT)) != 0U) {
      status = P9_RUNTIME_PL_OBJECT;
      break;
    }
    usleep(P9_POLL_DELAY_US);
  }
  int shutdown_status = p9_shutdown();
  return status != P9_RUNTIME_OK ? status : shutdown_status;
}

static void p9_fill_generated_payload(uint8_t *buffer, uint32_t bytes,
                                      uint32_t object_id) {
  for (uint32_t index = 0U; index < bytes; ++index)
    buffer[index] = p9_pattern_byte(object_id, index);
}

static int p9_rfap_transfer_bytes(volatile p9_mailbox_t *m,
                                  uint32_t *transfer_bytes) {
  uint32_t rfap_flags = m->command_flags &
      (P9_FLAG_RFAP_V1_PAYLOAD | P9_FLAG_RFAP_VNEXT_PAYLOAD);
  if (rfap_flags == (P9_FLAG_RFAP_V1_PAYLOAD | P9_FLAG_RFAP_VNEXT_PAYLOAD))
    return P9_RUNTIME_BAD_ARGUMENT;
  uint64_t encoded = m->object_size;
  if (rfap_flags == P9_FLAG_RFAP_V1_PAYLOAD) {
    if (m->object_size > P9_RFAP_V1_MAX_USEFUL_BYTES)
      return P9_RUNTIME_BAD_ARGUMENT;
    uint32_t fragments =
        (m->object_size + P9_RFAP_V1_CHUNK_BYTES - 1U) /
        P9_RFAP_V1_CHUNK_BYTES;
    if (fragments == 0U || fragments > UINT16_MAX)
      return P9_RUNTIME_BAD_ARGUMENT;
    encoded += (uint64_t)fragments * P9_RFAP_V1_HEADER_BYTES;
  } else if (rfap_flags == P9_FLAG_RFAP_VNEXT_PAYLOAD) {
    uint32_t fragments =
        (m->object_size + P9_RFAP_VNEXT_CHUNK_BYTES - 1U) /
        P9_RFAP_VNEXT_CHUNK_BYTES;
    if (fragments == 0U) return P9_RUNTIME_BAD_ARGUMENT;
    encoded += (uint64_t)fragments * P9_RFAP_VNEXT_HEADER_BYTES;
  }
  if (encoded == 0U || encoded > P9_DMA_MAX_TRANSFER_BYTES)
    return P9_RUNTIME_BAD_ARGUMENT;
  *transfer_bytes = (uint32_t)encoded;
  return P9_RUNTIME_OK;
}

static int p9_encode_rfap_v1(volatile p9_mailbox_t *m, uint8_t *output,
                             uint32_t transfer_bytes) {
  uint32_t useful = m->object_size;
  uint32_t fragments =
      (useful + P9_RFAP_V1_CHUNK_BYTES - 1U) / P9_RFAP_V1_CHUNK_BYTES;
  uint32_t object_crc = p9_generated_crc32(m->object_id, useful);
  uint32_t useful_offset = 0U, encoded_offset = 0U;
  for (uint32_t fragment = 0U; fragment < fragments; ++fragment) {
    uint32_t remaining = useful - useful_offset;
    uint16_t chunk = (uint16_t)(remaining > P9_RFAP_V1_CHUNK_BYTES ?
                                    P9_RFAP_V1_CHUNK_BYTES : remaining);
    uint8_t *header = output + encoded_offset;
    header[0] = 'R'; header[1] = 'F'; header[2] = 'A'; header[3] = 'P';
    header[4] = 1U;
    header[5] = (uint8_t)((fragment == 0U ? 1U : 0U) |
                          (fragment + 1U == fragments ? 2U : 0U));
    p9_write_u16_le(header + 6U, P9_RFAP_V1_HEADER_BYTES);
    p9_write_u32_le(header + 8U, m->session_epoch);
    p9_write_u32_le(header + 12U, m->object_id);
    p9_write_u32_le(header + 16U, useful);
    p9_write_u16_le(header + 20U, (uint16_t)fragment);
    p9_write_u16_le(header + 22U, (uint16_t)fragments);
    p9_write_u16_le(header + 24U, chunk);
    p9_write_u16_le(header + 26U, 0U);
    p9_write_u32_le(header + 28U, object_crc);
    for (uint32_t index = 0U; index < chunk; ++index)
      header[P9_RFAP_V1_HEADER_BYTES + index] =
          p9_pattern_byte(m->object_id, useful_offset + index);
    useful_offset += chunk;
    encoded_offset += P9_RFAP_V1_HEADER_BYTES + chunk;
  }
  if (encoded_offset != transfer_bytes || useful_offset != useful)
    return P9_RUNTIME_RFAP_VALIDATION;
  m->rfap_mode = 1U;
  m->rfap_fragment_count = fragments;
  m->rfap_useful_bytes = useful;
  m->rfap_useful_crc32 = object_crc;
  return P9_RUNTIME_OK;
}

static int p9_encode_rfap_vnext(volatile p9_mailbox_t *m, uint8_t *output,
                                uint32_t transfer_bytes) {
  uint32_t useful = m->object_size;
  uint32_t fragments =
      (useful + P9_RFAP_VNEXT_CHUNK_BYTES - 1U) /
      P9_RFAP_VNEXT_CHUNK_BYTES;
  uint32_t useful_offset = 0U, encoded_offset = 0U;
  for (uint32_t fragment = 0U; fragment < fragments; ++fragment) {
    uint32_t remaining = useful - useful_offset;
    uint32_t chunk = remaining > P9_RFAP_VNEXT_CHUNK_BYTES ?
                         P9_RFAP_VNEXT_CHUNK_BYTES : remaining;
    uint8_t *header = output + encoded_offset;
    header[0] = 'R'; header[1] = 'F'; header[2] = 'A'; header[3] = 'P';
    header[4] = 2U;
    header[5] = (uint8_t)((fragment == 0U ? 1U : 0U) |
                          (fragment + 1U == fragments ? 2U : 0U));
    p9_write_u16_le(header + 6U, P9_RFAP_VNEXT_HEADER_BYTES);
    p9_write_u32_le(header + 8U, UINT32_C(0x70100001));
    p9_write_u32_le(header + 12U, m->session_epoch);
    p9_write_u32_le(header + 16U, 1U + m->direction);
    p9_write_u32_le(header + 20U, m->object_id);
    p9_write_u64_le(header + 24U, useful_offset);
    p9_write_u32_le(header + 32U, chunk);
    p9_write_u16_le(header + 36U,
                    (uint16_t)(m->initial_sequence + fragment));
    p9_write_u16_le(header + 38U, (uint16_t)m->path_epoch);
    p9_write_u64_le(header + 40U, useful);
    for (uint32_t index = 0U; index < chunk; ++index)
      header[P9_RFAP_VNEXT_HEADER_BYTES + index] =
          p9_pattern_byte(m->object_id, useful_offset + index);
    useful_offset += chunk;
    encoded_offset += P9_RFAP_VNEXT_HEADER_BYTES + chunk;
  }
  if (encoded_offset != transfer_bytes || useful_offset != useful)
    return P9_RUNTIME_RFAP_VALIDATION;
  m->rfap_mode = 2U;
  m->rfap_fragment_count = fragments;
  m->rfap_useful_bytes = useful;
  m->rfap_useful_crc32 = p9_generated_crc32(m->object_id, useful);
  return P9_RUNTIME_OK;
}

static int p9_prepare_payload(volatile p9_mailbox_t *m, uint8_t *output,
                              uint32_t transfer_bytes) {
  if ((m->command_flags & P9_FLAG_RFAP_V1_PAYLOAD) != 0U)
    return p9_encode_rfap_v1(m, output, transfer_bytes);
  if ((m->command_flags & P9_FLAG_RFAP_VNEXT_PAYLOAD) != 0U)
    return p9_encode_rfap_vnext(m, output, transfer_bytes);
  if ((m->command_flags & P9_FLAG_GENERATE_PAYLOAD_IN_PS) != 0U)
    p9_fill_generated_payload(output, transfer_bytes, m->object_id);
  return P9_RUNTIME_OK;
}

static int p9_validate_rfap_v1(volatile p9_mailbox_t *m,
                               const uint8_t *input,
                               uint32_t transfer_bytes) {
  uint32_t expected_fragments =
      (m->object_size + P9_RFAP_V1_CHUNK_BYTES - 1U) /
      P9_RFAP_V1_CHUNK_BYTES;
  uint32_t expected_crc = p9_generated_crc32(m->object_id, m->object_size);
  uint32_t encoded = 0U, useful = 0U;
  uint32_t crc = UINT32_C(0xffffffff);
  for (uint32_t fragment = 0U; fragment < expected_fragments; ++fragment) {
    if (encoded + P9_RFAP_V1_HEADER_BYTES > transfer_bytes)
      return P9_RUNTIME_RFAP_VALIDATION;
    const uint8_t *header = input + encoded;
    uint32_t remaining = m->object_size - useful;
    uint16_t chunk = (uint16_t)(remaining > P9_RFAP_V1_CHUNK_BYTES ?
                                    P9_RFAP_V1_CHUNK_BYTES : remaining);
    uint8_t flags = (uint8_t)((fragment == 0U ? 1U : 0U) |
                              (fragment + 1U == expected_fragments ? 2U : 0U));
    if (header[0] != 'R' || header[1] != 'F' || header[2] != 'A' ||
        header[3] != 'P' || header[4] != 1U || header[5] != flags ||
        p9_read_u16_le(header + 6U) != P9_RFAP_V1_HEADER_BYTES ||
        p9_read_u32_le(header + 8U) != m->session_epoch ||
        p9_read_u32_le(header + 12U) != m->object_id ||
        p9_read_u32_le(header + 16U) != m->object_size ||
        p9_read_u16_le(header + 20U) != fragment ||
        p9_read_u16_le(header + 22U) != expected_fragments ||
        p9_read_u16_le(header + 24U) != chunk ||
        p9_read_u16_le(header + 26U) != 0U ||
        p9_read_u32_le(header + 28U) != expected_crc ||
        encoded + P9_RFAP_V1_HEADER_BYTES + chunk > transfer_bytes)
      return P9_RUNTIME_RFAP_VALIDATION;
    for (uint32_t index = 0U; index < chunk; ++index) {
      uint8_t value = header[P9_RFAP_V1_HEADER_BYTES + index];
      if (value != p9_pattern_byte(m->object_id, useful + index))
        return P9_RUNTIME_RFAP_VALIDATION;
      crc = p9_crc32_update_byte(crc, value);
    }
    useful += chunk;
    encoded += P9_RFAP_V1_HEADER_BYTES + chunk;
  }
  if (encoded != transfer_bytes || useful != m->object_size ||
      (crc ^ UINT32_C(0xffffffff)) != expected_crc)
    return P9_RUNTIME_RFAP_VALIDATION;
  m->rfap_validation_pass = 1U;
  m->rfap_atomic_publish_count = 1U;
  m->rfap_useful_crc32 = expected_crc;
  return P9_RUNTIME_OK;
}

static int p9_validate_rfap_vnext(volatile p9_mailbox_t *m,
                                  const uint8_t *input,
                                  uint32_t transfer_bytes) {
  uint32_t expected_fragments =
      (m->object_size + P9_RFAP_VNEXT_CHUNK_BYTES - 1U) /
      P9_RFAP_VNEXT_CHUNK_BYTES;
  uint32_t encoded = 0U, useful = 0U;
  uint32_t crc = UINT32_C(0xffffffff);
  for (uint32_t fragment = 0U; fragment < expected_fragments; ++fragment) {
    if (encoded + P9_RFAP_VNEXT_HEADER_BYTES > transfer_bytes)
      return P9_RUNTIME_RFAP_VALIDATION;
    const uint8_t *header = input + encoded;
    uint32_t remaining = m->object_size - useful;
    uint32_t chunk = remaining > P9_RFAP_VNEXT_CHUNK_BYTES ?
                         P9_RFAP_VNEXT_CHUNK_BYTES : remaining;
    uint8_t flags = (uint8_t)((fragment == 0U ? 1U : 0U) |
                              (fragment + 1U == expected_fragments ? 2U : 0U));
    if (header[0] != 'R' || header[1] != 'F' || header[2] != 'A' ||
        header[3] != 'P' || header[4] != 2U || header[5] != flags ||
        p9_read_u16_le(header + 6U) != P9_RFAP_VNEXT_HEADER_BYTES ||
        p9_read_u32_le(header + 8U) != UINT32_C(0x70100001) ||
        p9_read_u32_le(header + 12U) != m->session_epoch ||
        p9_read_u32_le(header + 16U) != 1U + m->direction ||
        p9_read_u32_le(header + 20U) != m->object_id ||
        p9_read_u64_le(header + 24U) != useful ||
        p9_read_u32_le(header + 32U) != chunk ||
        p9_read_u16_le(header + 36U) !=
            (uint16_t)(m->initial_sequence + fragment) ||
        p9_read_u16_le(header + 38U) != (uint16_t)m->path_epoch ||
        p9_read_u64_le(header + 40U) != m->object_size ||
        encoded + P9_RFAP_VNEXT_HEADER_BYTES + chunk > transfer_bytes)
      return P9_RUNTIME_RFAP_VALIDATION;
    for (uint32_t index = 0U; index < chunk; ++index) {
      uint8_t value = header[P9_RFAP_VNEXT_HEADER_BYTES + index];
      if (value != p9_pattern_byte(m->object_id, useful + index))
        return P9_RUNTIME_RFAP_VALIDATION;
      crc = p9_crc32_update_byte(crc, value);
    }
    useful += chunk;
    encoded += P9_RFAP_VNEXT_HEADER_BYTES + chunk;
  }
  if (encoded != transfer_bytes || useful != m->object_size)
    return P9_RUNTIME_RFAP_VALIDATION;
  m->rfap_validation_pass = 1U;
  m->rfap_atomic_publish_count = 1U;
  m->rfap_useful_crc32 = crc ^ UINT32_C(0xffffffff);
  return P9_RUNTIME_OK;
}

static int p9_validate_rfap(volatile p9_mailbox_t *m, const uint8_t *input,
                            uint32_t transfer_bytes) {
  if ((m->command_flags & P9_FLAG_RFAP_V1_PAYLOAD) != 0U)
    return p9_validate_rfap_v1(m, input, transfer_bytes);
  if ((m->command_flags & P9_FLAG_RFAP_VNEXT_PAYLOAD) != 0U)
    return p9_validate_rfap_vnext(m, input, transfer_bytes);
  return P9_RUNTIME_OK;
}

static int p9_configure_object(volatile p9_mailbox_t *m) {
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  p9_pl_write(IR_REG_P9_OBJECT_CONFIG,
              (m->lane_mask & P10_LANE_MASK) |
                  ((m->rate_select & 3U) << 8) |
                  ((m->direction & 1U) << 16));
  p9_pl_write(IR_REG_P9_LANE_WEIGHTS,
              m->lane_weights & (P10_LANE_COUNT == 4 ? UINT32_MAX :
                                                         UINT32_C(0xffff)));
  p9_pl_write(IR_REG_P9_SESSION_EPOCH, m->session_epoch);
  p9_pl_write(IR_REG_P9_PATH_EPOCH, m->path_epoch & 0xffffU);
  p9_pl_write(IR_REG_P9_OBJECT_ID, m->object_id);
  p9_pl_write(IR_REG_P9_INITIAL_SEQUENCE, m->initial_sequence & 0xffffU);
  p9_pl_write(IR_REG_P9_PROTOCOL_FAULT_FLAGS,
              m->protocol_fault_flags & 0x7ffffU);
  p9_pl_write(IR_REG_P9_FAULT_INJECTION,
              (m->drop_data_count & 0xffU) |
                  ((m->drop_ack_count & 0xffU) << 8) |
                  ((m->lane_unavailable_mask & P10_LANE_MASK) << 16));
  return P9_RUNTIME_OK;
}

#if P10_ENDPOINT_ROLE != 0
typedef struct {
  uint32_t role_epoch;
  uint32_t role_status;
  uint32_t context_status;
  uint32_t local_tx_mask;
  uint32_t local_rx_mask;
  uint32_t piggyback_ack_tx_count;
  uint32_t piggyback_ack_rx_count;
  uint32_t control_only_ack_count;
  uint32_t direction_reject_count;
  uint32_t role_epoch_reject_count;
  uint32_t tx_bytes;
  uint32_t rx_bytes;
  uint32_t tx_window_occupancy;
  uint32_t rx_window_occupancy;
  uint32_t tx_receiver_credit;
  uint32_t rx_receiver_credit;
  uint32_t tx_retry_count;
  uint32_t tx_timeout_count;
  uint32_t ack_tx_bytes;
  uint32_t ack_rx_bytes;
  uint32_t control_tx_bytes;
  uint32_t application_committed_bytes;
  uint32_t tx_axis_stall;
  uint32_t rx_axis_stall;
  uint32_t control_queue_occupancy;
} p10_5_direction_snapshot_t;

static int p10_5_query_dual_direction_caps(void) {
  if (P10_LANE_COUNT != 4 ||
      p9_pl_read(IR_REG_P10_5_CAPS) != P10_5_CAPABILITY_WORD ||
      (p9_pl_read(IR_REG_P10_5_VERSION) & UINT32_C(0xffff)) !=
          P10_5_CAPABILITY_VERSION ||
      p9_pl_read(IR_REG_P10_5_TELEMETRY_SCHEMA) != UINT32_C(0x50310502))
    return P9_RUNTIME_P10_5_CAPABILITY;
  return P9_RUNTIME_OK;
}

static int p10_5_stage_role_masks(uint32_t active_mask,
                                  uint32_t f2r_mask,
                                  uint32_t r2f_mask) {
  if (active_mask == 0U || (active_mask & ~P10_LANE_MASK) != 0U ||
      f2r_mask == 0U || r2f_mask == 0U ||
      (f2r_mask & r2f_mask) != 0U ||
      (f2r_mask | r2f_mask) != active_mask)
    return P9_RUNTIME_BAD_ARGUMENT;
  p9_pl_write(IR_REG_P10_5_MODE_SHADOW, 1U);
  p9_pl_write(IR_REG_P10_5_ACTIVE_MASK_SHADOW, active_mask);
  p9_pl_write(IR_REG_P10_5_F2R_MASK_SHADOW, f2r_mask);
  p9_pl_write(IR_REG_P10_5_R2F_MASK_SHADOW, r2f_mask);
  dsb();
  return P9_RUNTIME_OK;
}

static int p10_5_commit_role_masks(uint32_t active_mask,
                                   uint32_t f2r_mask,
                                   uint32_t r2f_mask,
                                   uint32_t *role_epoch) {
  uint32_t before = p9_pl_read(IR_REG_P10_5_ROLE_EPOCH) & 0xffffU;
  p9_pl_write(IR_REG_P10_5_ROLE_COMMIT, UINT32_C(0xc05a0001));
  dsb();
  uint64_t deadline = p9_deadline_ms(20U);
  do {
    uint32_t epoch = p9_pl_read(IR_REG_P10_5_ROLE_EPOCH) & 0xffffU;
    uint32_t status = p9_pl_read(IR_REG_P10_5_ROLE_STATUS);
    uint32_t error = p9_pl_read(IR_REG_P10_5_ROLE_ERROR);
    if (error != 0U) return P9_RUNTIME_P10_5_ROLE_COMMIT;
    if (epoch != 0U && epoch != before && (status & 7U) == 7U) {
      uint32_t expected_tx = P10_ENDPOINT_ROLE == 1 ? f2r_mask : r2f_mask;
      uint32_t expected_rx = P10_ENDPOINT_ROLE == 1 ? r2f_mask : f2r_mask;
      if ((p9_pl_read(IR_REG_P10_5_ACTIVE_MASK) & P10_LANE_MASK) !=
              active_mask ||
          (p9_pl_read(IR_REG_P10_5_F2R_MASK) & P10_LANE_MASK) != f2r_mask ||
          (p9_pl_read(IR_REG_P10_5_R2F_MASK) & P10_LANE_MASK) != r2f_mask ||
          (p9_pl_read(IR_REG_P10_5_LOCAL_TX_MASK) & P10_LANE_MASK) !=
              expected_tx ||
          (p9_pl_read(IR_REG_P10_5_LOCAL_RX_MASK) & P10_LANE_MASK) !=
              expected_rx)
        return P9_RUNTIME_P10_5_ROLE_COMMIT;
      if (role_epoch != NULL) *role_epoch = epoch;
      return P9_RUNTIME_OK;
    }
    usleep(P9_POLL_DELAY_US);
  } while (p9_time_now() < deadline);
  return P9_RUNTIME_P10_5_ROLE_COMMIT;
}

static int p10_5_start_direction_stream(void) {
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
  usleep(10U);
  return (p9_pl_read(IR_REG_P9_STATUS) & P9_STATUS_OBJECT_ACTIVE) != 0U ?
             P9_RUNTIME_OK : P9_RUNTIME_P10_5_CONTEXT;
}

static int p10_5_abort_direction_stream(uint32_t abort_local_tx,
                                        uint32_t abort_local_rx) {
  uint32_t control = (abort_local_tx != 0U ? 1U : 0U) |
                     (abort_local_rx != 0U ? 2U : 0U);
  if (control == 0U) return P9_RUNTIME_BAD_ARGUMENT;
  p9_pl_write(IR_REG_P10_5_CONTEXT_CONTROL, control);
  dsb();
  return P9_RUNTIME_OK;
}

static int p10_5_stop_direction_stream(void) {
  if ((p9_pl_read(IR_REG_P9_STATUS) & P9_STATUS_OBJECT_ACTIVE) == 0U)
    return P9_RUNTIME_OK;
  int status = p10_5_abort_direction_stream(1U, 1U);
  if (status != P9_RUNTIME_OK) return status;
  uint64_t deadline = p9_deadline_ms(20U);
  do {
    if ((p9_pl_read(IR_REG_P9_STATUS) & P9_STATUS_OBJECT_ACTIVE) == 0U)
      return P9_RUNTIME_OK;
    usleep(P9_POLL_DELAY_US);
  } while (p9_time_now() < deadline);
  return P9_RUNTIME_P10_5_CONTEXT;
}

static int p10_5_snapshot_direction(p10_5_direction_snapshot_t *snapshot) {
  if (snapshot == NULL) return P9_RUNTIME_BAD_ARGUMENT;
  snapshot->role_epoch = p9_pl_read(IR_REG_P10_5_ROLE_EPOCH);
  snapshot->role_status = p9_pl_read(IR_REG_P10_5_ROLE_STATUS);
  snapshot->context_status = p9_pl_read(IR_REG_P10_5_CONTEXT_STATUS);
  snapshot->local_tx_mask = p9_pl_read(IR_REG_P10_5_LOCAL_TX_MASK);
  snapshot->local_rx_mask = p9_pl_read(IR_REG_P10_5_LOCAL_RX_MASK);
  snapshot->piggyback_ack_tx_count =
      p9_pl_read(IR_REG_P10_5_PIGGYBACK_ACK_TX_COUNT);
  snapshot->piggyback_ack_rx_count =
      p9_pl_read(IR_REG_P10_5_PIGGYBACK_ACK_RX_COUNT);
  snapshot->control_only_ack_count =
      p9_pl_read(IR_REG_P10_5_CONTROL_ACK_FALLBACK_COUNT);
  snapshot->direction_reject_count =
      p9_pl_read(IR_REG_P10_5_DIRECTION_REJECT_COUNT);
  snapshot->role_epoch_reject_count =
      p9_pl_read(IR_REG_P10_5_ROLE_EPOCH_REJECT_COUNT);
  snapshot->tx_bytes = p9_pl_read(IR_REG_P10_5_TX_BYTES);
  snapshot->rx_bytes = p9_pl_read(IR_REG_P10_5_RX_BYTES);
  snapshot->tx_window_occupancy =
      p9_pl_read(IR_REG_P10_5_TX_WINDOW_OCCUPANCY);
  snapshot->rx_window_occupancy =
      p9_pl_read(IR_REG_P10_5_RX_WINDOW_OCCUPANCY);
  snapshot->tx_receiver_credit =
      p9_pl_read(IR_REG_P10_5_TX_RECEIVER_CREDIT);
  snapshot->rx_receiver_credit =
      p9_pl_read(IR_REG_P10_5_RX_RECEIVER_CREDIT);
  snapshot->tx_retry_count = p9_pl_read(IR_REG_P10_5_TX_RETRY_COUNT);
  snapshot->tx_timeout_count = p9_pl_read(IR_REG_P10_5_TX_TIMEOUT_COUNT);
  snapshot->ack_tx_bytes = p9_pl_read(IR_REG_P10_5_ACK_TX_BYTES);
  snapshot->ack_rx_bytes = p9_pl_read(IR_REG_P10_5_ACK_RX_BYTES);
  snapshot->control_tx_bytes = p9_pl_read(IR_REG_P10_5_CONTROL_TX_BYTES);
  snapshot->application_committed_bytes =
      p9_pl_read(IR_REG_P10_5_APPLICATION_COMMITTED_BYTES);
  snapshot->tx_axis_stall = p9_pl_read(IR_REG_P10_5_TX_AXIS_STALL);
  snapshot->rx_axis_stall = p9_pl_read(IR_REG_P10_5_RX_AXIS_STALL);
  snapshot->control_queue_occupancy =
      p9_pl_read(IR_REG_P10_5_CONTROL_QUEUE_OCCUPANCY);
  return P9_RUNTIME_OK;
}

static int p10_5_clear_direction_errors(void) {
  if ((p9_pl_read(IR_REG_P9_STATUS) &
       (P9_STATUS_OBJECT_ACTIVE | P9_STATUS_RAW_BUSY)) != 0U)
    return P9_RUNTIME_P10_5_CONTEXT;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  dsb();
  return P9_RUNTIME_OK;
}

static uint32_t p10_5_direction_session(uint32_t base, uint32_t direction) {
  return direction == 0U ? base : base ^ UINT32_C(0x80000000);
}

static uint32_t p10_5_direction_path(uint32_t base, uint32_t direction) {
  return direction == 0U ? base & UINT32_C(0xffff) :
                           (base ^ UINT32_C(0x8000)) & UINT32_C(0xffff);
}

static int p10_5_program_dual_object_context(volatile p9_mailbox_t *m,
                                             uint32_t active_mask,
                                             uint32_t preserve_live_faults) {
  uint32_t local_direction = P10_ENDPOINT_ROLE == 2 ? 1U : 0U;
  uint32_t remote_direction = local_direction ^ 1U;
  uint32_t diagnostic = m->command_flags &
      P10_5_RUNTIME_FLAG_DIRECTION_FAULT_TEST;
  uint32_t fault_direction =
      (m->command_flags & P10_5_RUNTIME_FLAG_FAULT_TARGET_R2F) != 0U;
  uint32_t local_drop_data = m->drop_data_count & 0xffU;
  uint32_t local_drop_ack = m->drop_ack_count & 0xffU;
  uint32_t unavailable = m->lane_unavailable_mask & active_mask;
  if (diagnostic != 0U) {
    /* DATA belongs to the local TX context; ACK belongs to the local RX
     * context and therefore acknowledges the remote direction.  Scope each
     * one-shot fault to exactly the requested logical direction even though
     * both role-bound mailboxes carry the same immutable CASE record. */
    if (local_direction != fault_direction) local_drop_data = 0U;
    if (remote_direction != fault_direction) local_drop_ack = 0U;
  }
  if (preserve_live_faults != 0U)
    unavailable |= (p9_pl_read(IR_REG_P9_FAULT_INJECTION) >> 16) &
                   active_mask;
  p9_pl_write(IR_REG_P9_OBJECT_CONFIG,
              active_mask | ((m->rate_select & 3U) << 8) |
                  (local_direction << 16));
  p9_pl_write(IR_REG_P9_LANE_WEIGHTS, m->lane_weights);
  p9_pl_write(IR_REG_P9_SESSION_EPOCH,
              p10_5_direction_session(m->session_epoch, local_direction));
  p9_pl_write(IR_REG_P9_PATH_EPOCH,
              p10_5_direction_path(m->path_epoch, local_direction));
  p9_pl_write(IR_REG_P9_OBJECT_ID, m->object_id);
  p9_pl_write(IR_REG_P9_INITIAL_SEQUENCE, m->initial_sequence & 0xffffU);
  p9_pl_write(IR_REG_P9_PROTOCOL_FAULT_FLAGS,
              m->protocol_fault_flags & 0x7ffffU);
  p9_pl_write(IR_REG_P9_FAULT_INJECTION,
              local_drop_data | (local_drop_ack << 8) |
                  (unavailable << 16));
  p9_pl_write(IR_REG_P10_5_TX_SESSION,
              p10_5_direction_session(m->session_epoch, local_direction));
  p9_pl_write(IR_REG_P10_5_RX_SESSION,
              p10_5_direction_session(m->session_epoch, remote_direction));
  p9_pl_write(IR_REG_P10_5_TX_PATH,
              p10_5_direction_path(m->path_epoch, local_direction));
  p9_pl_write(IR_REG_P10_5_RX_PATH,
              p10_5_direction_path(m->path_epoch, remote_direction));
  p9_pl_write(IR_REG_P10_5_TX_OBJECT, m->object_id);
  p9_pl_write(IR_REG_P10_5_RX_OBJECT, m->object_id);
  p9_pl_write(IR_REG_P10_5_TX_INITIAL_SEQUENCE,
              m->initial_sequence & 0xffffU);
  p9_pl_write(IR_REG_P10_5_RX_INITIAL_SEQUENCE,
              m->initial_sequence & 0xffffU);
  dsb();
  return P9_RUNTIME_OK;
}

static int p10_5_configure_dual_object(volatile p9_mailbox_t *m,
                                       uint32_t active_mask,
                                       uint32_t f2r_mask,
                                       uint32_t r2f_mask,
                                       uint32_t *role_epoch) {
  int status = p10_5_clear_direction_errors();
  if (status != P9_RUNTIME_OK) return status;
  status = p10_5_stage_role_masks(active_mask, f2r_mask, r2f_mask);
  if (status != P9_RUNTIME_OK) return status;
  status = p10_5_commit_role_masks(active_mask, f2r_mask, r2f_mask,
                                   role_epoch);
  if (status != P9_RUNTIME_OK) return status;
  return p10_5_program_dual_object_context(m, active_mask, 0U);
}
#endif

static int p9_validate_object_args(volatile p9_mailbox_t *m,
                                   UINTPTR *tx_address,
                                   UINTPTR *rx_address,
                                   uint32_t *transfer_bytes) {
  if (m->lane_mask == 0U || (m->lane_mask & ~P10_LANE_MASK) != 0U ||
      m->direction > 1U ||
      m->rate_select > 2U ||
      (m->ring_depth != 8U && m->ring_depth != 16U &&
       m->ring_depth != 32U) ||
      m->cache_mode > 1U || m->object_size == 0U ||
      m->object_size > P9_MAX_OBJECT_BYTES || m->tx_offset > 63U ||
      m->rx_offset > 63U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_rfap_transfer_bytes(m, transfer_bytes);
  if (status != P9_RUNTIME_OK ||
      *transfer_bytes + m->tx_offset > P9_MAX_OBJECT_BYTES ||
      *transfer_bytes + m->rx_offset > P9_MAX_OBJECT_BYTES)
    return P9_RUNTIME_BAD_ARGUMENT;
  *tx_address = (UINTPTR)P9_TX_BUFFER_BASEADDR + m->tx_offset;
  *rx_address = (UINTPTR)P9_RX_BUFFER_BASEADDR + m->rx_offset;
  return P9_RUNTIME_OK;
}

#if P10_ENDPOINT_ROLE != 0
static int p10_5_validate_dual_object_args(volatile p9_mailbox_t *m,
                                           UINTPTR *tx_address,
                                           UINTPTR *rx_address,
                                           uint32_t *transfer_bytes,
                                           uint32_t *active_mask,
                                           uint32_t *f2r_mask,
                                           uint32_t *r2f_mask) {
  const uint32_t packed_mask_bits = UINT32_C(0x000f0f0f);
  *active_mask = (m->lane_mask >> P10_5_ACTIVE_MASK_SHIFT) & P10_LANE_MASK;
  *f2r_mask = (m->lane_mask >> P10_5_F2R_MASK_SHIFT) & P10_LANE_MASK;
  *r2f_mask = (m->lane_mask >> P10_5_R2F_MASK_SHIFT) & P10_LANE_MASK;
  if (P10_LANE_COUNT != 4 || (m->lane_mask & ~packed_mask_bits) != 0U ||
      *active_mask == 0U || *f2r_mask == 0U || *r2f_mask == 0U ||
      (*f2r_mask & *r2f_mask) != 0U ||
      (*f2r_mask | *r2f_mask) != *active_mask ||
      m->rate_select > 2U ||
      (m->ring_depth != 8U && m->ring_depth != 16U &&
       m->ring_depth != 32U) ||
      m->cache_mode > 1U || m->object_size == 0U ||
      m->object_size > P9_MAX_OBJECT_BYTES || m->tx_offset > 63U ||
      m->rx_offset > 63U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_rfap_transfer_bytes(m, transfer_bytes);
  if (status != P9_RUNTIME_OK ||
      *transfer_bytes + m->tx_offset > P9_MAX_OBJECT_BYTES ||
      *transfer_bytes + m->rx_offset > P9_MAX_OBJECT_BYTES)
    return P9_RUNTIME_BAD_ARGUMENT;
  *tx_address = (UINTPTR)P9_TX_BUFFER_BASEADDR + m->tx_offset;
  *rx_address = (UINTPTR)P9_RX_BUFFER_BASEADDR + m->rx_offset;
  return P9_RUNTIME_OK;
}

static void p10_5_select_payload_direction(volatile p9_mailbox_t *m,
                                           uint32_t direction,
                                           uint32_t *saved_direction,
                                           uint32_t *saved_session,
                                           uint32_t *saved_path) {
  *saved_direction = m->direction;
  *saved_session = m->session_epoch;
  *saved_path = m->path_epoch;
  m->direction = direction;
  m->session_epoch = p10_5_direction_session(*saved_session, direction);
  m->path_epoch = p10_5_direction_path(*saved_path, direction);
}

static void p10_5_restore_payload_context(volatile p9_mailbox_t *m,
                                          uint32_t direction,
                                          uint32_t session,
                                          uint32_t path) {
  m->direction = direction;
  m->session_epoch = session;
  m->path_epoch = path;
}

static int p10_5_prepare_direction_payload(volatile p9_mailbox_t *m,
                                           uint8_t *output,
                                           uint32_t transfer_bytes,
                                           uint32_t direction) {
  uint32_t saved_direction, saved_session, saved_path;
  p10_5_select_payload_direction(m, direction, &saved_direction,
                                 &saved_session, &saved_path);
  int status = p9_prepare_payload(m, output, transfer_bytes);
  p10_5_restore_payload_context(m, saved_direction, saved_session, saved_path);
  return status;
}

static int p10_5_validate_direction_payload(volatile p9_mailbox_t *m,
                                            const uint8_t *input,
                                            uint32_t transfer_bytes,
                                            uint32_t direction) {
  uint32_t saved_direction, saved_session, saved_path;
  p10_5_select_payload_direction(m, direction, &saved_direction,
                                 &saved_session, &saved_path);
  int status = p9_validate_rfap(m, input, transfer_bytes);
  p10_5_restore_payload_context(m, saved_direction, saved_session, saved_path);
  return status;
}
#endif

static int p9_command_object(volatile p9_mailbox_t *m) {
  UINTPTR tx_address, rx_address;
  uint32_t transfer_bytes = 0U;
  uint64_t object_runtime_start = p9_time_now();
  uint32_t tx_submitted_before = g_metrics.tx_submitted;
  uint32_t tx_completed_before = g_metrics.tx_completed;
  uint32_t rx_submitted_before = g_metrics.rx_submitted;
  uint32_t rx_completed_before = g_metrics.rx_completed;
  uint32_t local_tx = P10_ENDPOINT_ROLE == 0 || p9_local_sender(m->direction);
  uint32_t local_rx = P10_ENDPOINT_ROLE == 0 || !p9_local_sender(m->direction);
  int status = p9_validate_object_args(m, &tx_address, &rx_address,
                                       &transfer_bytes);
  if (status != P9_RUNTIME_OK) {
    p9_store_u64(&m->object_runtime_ticks_low,
                 &m->object_runtime_ticks_high,
                 p9_time_now() - object_runtime_start);
    return status;
  }
  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  if (g_ring_depth != m->ring_depth) {
    status = p9_dma_initialize(m->ring_depth, 1U);
    if (status != P9_RUNTIME_OK) return status;
  }
  uint8_t *tx_buffer = (uint8_t *)tx_address;
  uint8_t *rx_buffer = (uint8_t *)rx_address;
  uint64_t prepare_start = p9_time_now();
  status = p9_prepare_payload(m, tx_buffer, transfer_bytes);
  if (status != P9_RUNTIME_OK) goto object_exit;
  memset(rx_buffer, 0, transfer_bytes);
  uint8_t input_sha[32], output_sha[32];
  m->input_crc32 = p9_crc32(tx_buffer, transfer_bytes);
  p9_sha256(tx_buffer, transfer_bytes, input_sha);
  p9_copy_digest(m->input_sha256, input_sha);
  p9_store_u64(&m->payload_prepare_ticks_low,
               &m->payload_prepare_ticks_high,
               p9_time_now() - prepare_start);
  if (m->cache_mode != 0U) {
    p9_cache_enable();
    g_metrics.cache_enabled_exercised = 1U;
    p9_cache_flush(tx_address, transfer_bytes);
    p9_cache_invalidate(rx_address, transfer_bytes);
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
  if (local_rx != 0U) {
    status = p9_submit_rx(rx_address, transfer_bytes, token);
    if (status != P9_RUNTIME_OK) goto object_exit;
  }
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
  usleep(10U);
  if ((p9_pl_read(IR_REG_P9_STATUS) & P9_STATUS_OBJECT_ACTIVE) == 0U) {
    m->last_error_detail = p9_pl_read(IR_REG_P9_OBJECT_ERROR);
    status = ((m->command_flags & P9_FLAG_ALLOW_EXPECTED_OBJECT_FAILURE) != 0U)
                 ? P9_RUNTIME_OK
                 : P9_RUNTIME_PL_OBJECT;
    if (local_rx != 0U && g_metrics.rx_submitted - rx_submitted_before >
        g_metrics.rx_completed - rx_completed_before) {
      g_metrics.rx_completed++;
      p9_advance_consumer(0U);
    }
    (void)p9_dma_initialize(m->ring_depth, 1U);
    goto object_exit;
  }
  if (local_tx != 0U) {
    status = p9_submit_tx(tx_address, transfer_bytes, token);
    if (status != P9_RUNTIME_OK) goto object_exit;
  }
  status = p9_poll_completion(m, token, m->timeout_ms, local_tx, local_rx);
  if (status == P9_RUNTIME_OK) {
    if (local_tx != 0U) p9_capture_terminal_window(m);
    if (local_rx != 0U) {
      if (m->cache_mode != 0U)
        p9_cache_invalidate(rx_address, transfer_bytes);
      dsb();
      g_metrics.memory_barrier_count++;
      uint64_t integrity_start = p9_time_now();
      m->output_crc32 = p9_crc32(rx_buffer, transfer_bytes);
      p9_sha256(rx_buffer, transfer_bytes, output_sha);
      p9_copy_digest(m->output_sha256, output_sha);
      m->first_mismatch_offset = UINT32_C(0xffffffff);
      for (uint32_t index = 0U; index < transfer_bytes; ++index) {
        if (tx_buffer[index] != rx_buffer[index]) {
          m->first_mismatch_offset = index;
          status = P9_RUNTIME_PAYLOAD_MISMATCH;
          break;
        }
      }
      if (m->actual_rx_length != transfer_bytes ||
          m->input_crc32 != m->output_crc32 ||
          memcmp(input_sha, output_sha, sizeof(input_sha)) != 0)
        status = P9_RUNTIME_PAYLOAD_MISMATCH;
      if (status == P9_RUNTIME_OK)
        status = p9_validate_rfap(m, rx_buffer, transfer_bytes);
      p9_store_u64(&m->integrity_verify_ticks_low,
                   &m->integrity_verify_ticks_high,
                   p9_time_now() - integrity_start);
    }
  }

object_exit:
  p9_cache_disable();
  if (status != P9_RUNTIME_OK) {
    if (local_tx != 0U && g_metrics.tx_submitted - tx_submitted_before >
        g_metrics.tx_completed - tx_completed_before) {
      g_metrics.tx_completed++;
      p9_advance_consumer(1U);
    }
    if (local_rx != 0U && g_metrics.rx_submitted - rx_submitted_before >
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
  p9_store_u64(&m->object_runtime_ticks_low,
               &m->object_runtime_ticks_high,
               p9_time_now() - object_runtime_start);
  return status;
}

#if P10_ENDPOINT_ROLE != 0
static int p10_5_command_dual_object(volatile p9_mailbox_t *m) {
  UINTPTR tx_address, rx_address;
  uint32_t transfer_bytes = 0U;
  uint32_t active_mask = 0U, f2r_mask = 0U, r2f_mask = 0U;
  const uint32_t local_direction = P10_ENDPOINT_ROLE == 2 ? 1U : 0U;
  const uint32_t remote_direction = local_direction ^ 1U;
  uint64_t object_runtime_start = p9_time_now();
  uint32_t tx_submitted_before = g_metrics.tx_submitted;
  uint32_t tx_completed_before = g_metrics.tx_completed;
  uint32_t rx_submitted_before = g_metrics.rx_submitted;
  uint32_t rx_completed_before = g_metrics.rx_completed;
  int status = p10_5_query_dual_direction_caps();
  if (status == P9_RUNTIME_OK)
    status = p10_5_validate_dual_object_args(
        m, &tx_address, &rx_address, &transfer_bytes, &active_mask,
        &f2r_mask, &r2f_mask);
  if (status != P9_RUNTIME_OK) {
    p9_store_u64(&m->object_runtime_ticks_low,
                 &m->object_runtime_ticks_high,
                 p9_time_now() - object_runtime_start);
    return status;
  }

  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  if (g_ring_depth != m->ring_depth) {
    status = p9_dma_initialize(m->ring_depth, 1U);
    if (status != P9_RUNTIME_OK) return status;
  }

  uint8_t *tx_buffer = (uint8_t *)tx_address;
  uint8_t *rx_buffer = (uint8_t *)rx_address;
  uint64_t prepare_start = p9_time_now();
  status = p10_5_prepare_direction_payload(
      m, tx_buffer, transfer_bytes, local_direction);
  if (status != P9_RUNTIME_OK) goto dual_object_exit;
  memset(rx_buffer, 0, transfer_bytes);
  uint8_t input_sha[32], output_sha[32], expected_rx_sha[32];
  m->input_crc32 = p9_crc32(tx_buffer, transfer_bytes);
  p9_sha256(tx_buffer, transfer_bytes, input_sha);
  p9_copy_digest(m->input_sha256, input_sha);
  p9_store_u64(&m->payload_prepare_ticks_low,
               &m->payload_prepare_ticks_high,
               p9_time_now() - prepare_start);
  if (m->cache_mode != 0U) {
    p9_cache_enable();
    g_metrics.cache_enabled_exercised = 1U;
    p9_cache_flush(tx_address, transfer_bytes);
    p9_cache_invalidate(rx_address, transfer_bytes);
  } else {
    p9_cache_disable();
    g_metrics.cache_disabled_exercised = 1U;
  }
  if (m->tx_offset != 0U || m->rx_offset != 0U)
    g_metrics.misaligned_transfer_handled = 1U;

  uint32_t role_epoch = 0U;
  status = p10_5_configure_dual_object(
      m, active_mask, f2r_mask, r2f_mask, &role_epoch);
  if (status != P9_RUNTIME_OK) goto dual_object_exit;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) goto dual_object_exit;
  uint32_t token = m->command_sequence ^ m->object_id ^ UINT32_C(0x50350000);
  status = p9_submit_rx(rx_address, transfer_bytes, token);
  if (status != P9_RUNTIME_OK) goto dual_object_exit;
  status = p10_5_start_direction_stream();
  if (status != P9_RUNTIME_OK) {
    m->last_error_detail = p9_pl_read(IR_REG_P9_OBJECT_ERROR);
    goto dual_object_exit;
  }
  status = p9_submit_tx(tx_address, transfer_bytes, token);
  if (status != P9_RUNTIME_OK) goto dual_object_exit;
  status = p9_poll_completion(m, token, m->timeout_ms, 1U, 1U);
  if (status == P9_RUNTIME_OK) {
    p10_5_direction_snapshot_t snapshot;
    status = p10_5_snapshot_direction(&snapshot);
    if (status == P9_RUNTIME_OK &&
        ((snapshot.role_epoch & 0xffffU) != role_epoch ||
         (snapshot.local_tx_mask & P10_LANE_MASK) !=
             (P10_ENDPOINT_ROLE == 1 ? f2r_mask : r2f_mask) ||
         (snapshot.local_rx_mask & P10_LANE_MASK) !=
             (P10_ENDPOINT_ROLE == 1 ? r2f_mask : f2r_mask) ||
         (snapshot.context_status & UINT32_C(0x00f0)) != UINT32_C(0x0070) ||
         snapshot.tx_bytes != transfer_bytes ||
         snapshot.rx_bytes != transfer_bytes ||
         snapshot.direction_reject_count != 0U ||
         snapshot.role_epoch_reject_count != 0U)) {
      m->last_error_detail = snapshot.context_status;
      status = P9_RUNTIME_P10_5_CONTEXT;
    }
  }
  if (status == P9_RUNTIME_OK) {
    p9_capture_terminal_window(m);
    if (m->cache_mode != 0U)
      p9_cache_invalidate(rx_address, transfer_bytes);
    dsb();
    g_metrics.memory_barrier_count++;
    uint64_t integrity_start = p9_time_now();
    m->output_crc32 = p9_crc32(rx_buffer, transfer_bytes);
    p9_sha256(rx_buffer, transfer_bytes, output_sha);
    p9_copy_digest(m->output_sha256, output_sha);

    /* Once MM2S and the PL object are complete, reuse the TX staging buffer
     * to construct the byte-exact payload expected from the peer direction.
     * This matters for RFAP-vNext because direction/session/path fields are
     * intentionally different in the two simultaneous objects. */
    status = p10_5_prepare_direction_payload(
        m, tx_buffer, transfer_bytes, remote_direction);
    if (status == P9_RUNTIME_OK) {
      uint32_t expected_rx_crc = p9_crc32(tx_buffer, transfer_bytes);
      p9_sha256(tx_buffer, transfer_bytes, expected_rx_sha);
      m->first_mismatch_offset = UINT32_C(0xffffffff);
      for (uint32_t index = 0U; index < transfer_bytes; ++index) {
        if (tx_buffer[index] != rx_buffer[index]) {
          m->first_mismatch_offset = index;
          status = P9_RUNTIME_PAYLOAD_MISMATCH;
          break;
        }
      }
      if (m->actual_rx_length != transfer_bytes ||
          expected_rx_crc != m->output_crc32 ||
          memcmp(expected_rx_sha, output_sha, sizeof(expected_rx_sha)) != 0)
        status = P9_RUNTIME_PAYLOAD_MISMATCH;
    }
    if (status == P9_RUNTIME_OK)
      status = p10_5_validate_direction_payload(
          m, rx_buffer, transfer_bytes, remote_direction);
    p9_store_u64(&m->integrity_verify_ticks_low,
                 &m->integrity_verify_ticks_high,
                 p9_time_now() - integrity_start);
  }

dual_object_exit:
  p9_cache_disable();
  if (status != P9_RUNTIME_OK) {
    (void)p10_5_stop_direction_stream();
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
  p9_store_u64(&m->object_runtime_ticks_low,
               &m->object_runtime_ticks_high,
               p9_time_now() - object_runtime_start);
  return status;
}
#endif

static int p9_command_ring_diagnostic(volatile p9_mailbox_t *m) {
  if (m->ring_depth != 8U && m->ring_depth != 16U &&
      m->ring_depth != 32U)
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
  uint32_t transfer_bytes = 0U;
  int status = p9_validate_object_args(m, &tx_address, &rx_address,
                                       &transfer_bytes);
  if (status != P9_RUNTIME_OK) return status;
  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_dma_initialize(m->ring_depth, 1U);
  if (status != P9_RUNTIME_OK) return status;
  uint32_t token = m->command_sequence ^ UINT32_C(0x51554555);
  status = p9_submit_rx(rx_address, transfer_bytes, token);
  if (status == P9_RUNTIME_OK)
    status = p9_submit_tx(tx_address, transfer_bytes, token);
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
  uint32_t transfer_bytes = 0U;
  int status = p9_validate_object_args(m, &tx_address, &rx_address,
                                       &transfer_bytes);
  if (status != P9_RUNTIME_OK) return status;
  status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_dma_initialize(m->ring_depth, 1U);
  if (status != P9_RUNTIME_OK) return status;
  status = p9_prepare_payload(m, (uint8_t *)tx_address, transfer_bytes);
  if (status != P9_RUNTIME_OK) return status;
  memset((void *)rx_address, 0, transfer_bytes);
  if (m->cache_mode != 0U) {
    p9_cache_enable();
    p9_cache_flush(tx_address, transfer_bytes);
    p9_cache_invalidate(rx_address, transfer_bytes);
  }
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) return status;
  p9_configure_object(m);
  uint32_t token = m->command_sequence ^ UINT32_C(0x41424f52);
  status = p9_submit_rx(rx_address, transfer_bytes, token);
  if (status != P9_RUNTIME_OK) goto abort_exit;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_OBJECT_MASK);
  status = p9_submit_tx(tx_address, transfer_bytes, token);
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
  status = P9_RUNTIME_OK;

abort_exit:
  {
    int shutdown_status = p9_shutdown();
    int recovery_status = shutdown_status;
    if (shutdown_status == P9_RUNTIME_OK)
      recovery_status = p9_reset_stream_path(m->ring_depth, 1U, 1U);
    if (status == P9_RUNTIME_OK) status = recovery_status;
  }
  return status;
}

static int p9_reset_stream_path(uint32_t depth, uint32_t count_pl_reset,
                                uint32_t count_dma_reset) {
  if (depth != 8U && depth != 16U && depth != 32U) depth = 8U;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_DATA_PLANE_SOFT_RESET_MASK);
  if (count_pl_reset != 0U) g_metrics.pl_soft_reset_count++;
  /* The PL request is stretched and synchronously released in every stream
   * clock domain.  Wait well past that bound before rebuilding the real SG
   * rings whose hardware ownership was discarded by the reset. */
  usleep(100U);
  if (p9_pl_read(IR_REG_P9_ID) != p9_expected_pl_id())
    return P9_RUNTIME_PL_IDENTITY;
  int status = p9_verify_safe_idle();
  if (status != P9_RUNTIME_OK) return status;
  return p9_dma_initialize(depth, count_dma_reset);
}

static int p9_command_pl_soft_reset(void) {
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  return p9_reset_stream_path(g_ring_depth, 1U, 1U);
}

static int p9_command_stale_completion(volatile p9_mailbox_t *m) {
  if (m->stale_token == 0U ||
      m->stale_token == g_metrics.last_completion_token)
    return P9_RUNTIME_BAD_ARGUMENT;
  g_metrics.stale_completion_rejected++;
  return P9_RUNTIME_OK;
}

static void p9_read_physical_tx_counts(volatile uint32_t output[4]) {
#if P10_LANE_COUNT == 4
  p9_pl_write(IR_REG_P10_2_SNAPSHOT_CONTROL, 1U);
  for (uint32_t lane = 0U; lane < 4U; ++lane) {
    uint32_t module = P10_ENDPOINT_ROLE == 2 ? lane + 4U : lane;
    output[lane] = p9_pl_read(ir_p10_2_module_word_offset(module, 1U));
  }
#else
  output[0] = p9_pl_read(IR_REG_P9_PHYSICAL_TX_A0);
  output[1] = p9_pl_read(IR_REG_P9_PHYSICAL_TX_A1);
  output[2] = p9_pl_read(IR_REG_P9_PHYSICAL_TX_B0);
  output[3] = p9_pl_read(IR_REG_P9_PHYSICAL_TX_B1);
#endif
}

static int p9_command_permit_drop(volatile p9_mailbox_t *m) {
  if (m->lane_mask == 0U || (m->lane_mask & ~P10_LANE_MASK) != 0U ||
      m->direction > 1U ||
      m->raw_target < 64U || m->raw_spacing_cycles < 128U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  status = p9_enable_and_arm();
  if (status != P9_RUNTIME_OK) return status;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  p9_pl_write(IR_REG_P9_RAW_CONFIG,
              (m->lane_mask & P10_LANE_MASK) |
                  ((m->direction & 1U) << 8));
  p9_pl_write(IR_REG_P9_RAW_TARGET, m->raw_target);
  p9_pl_write(IR_REG_P9_RAW_SPACING, m->raw_spacing_cycles);
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_START_RAW_MASK);

  uint64_t deadline = p9_deadline_ms(m->timeout_ms == 0U ? 10000U :
                                                            m->timeout_ms);
  uint32_t active_seen = 0U;
  while (p9_time_now() < deadline) {
    uint32_t raw_sent = p9_pl_read(IR_REG_P9_RAW_SENT_COUNT);
    uint32_t pl_status = p9_pl_read(IR_REG_P9_STATUS);
    if (raw_sent >= 4U && (pl_status & P9_STATUS_RAW_BUSY) != 0U) {
      active_seen = 1U;
      break;
    }
    if ((p9_pl_read(IR_REG_P9_PHY_STATUS) &
         (P10_PHY_READY_ALL_MASK << P10_PHY_SAFETY_SHIFT)) != 0U)
      break;
    usleep(P9_POLL_DELAY_US);
  }
  if (active_seen == 0U) {
    status = P9_RUNTIME_PERMIT_DROP;
    goto permit_exit;
  }
  p9_read_physical_tx_counts(m->permit_tx_before_drop);
  m->permit_raw_sent_before_drop = p9_pl_read(IR_REG_P9_RAW_SENT_COUNT);
  m->permit_result_flags |= 1U << 0;

  /* This is the local endpoint disarm request.  It does not synthesize or
   * override the external single GLOBAL_PERMIT and it does not assert SD. */
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_DISARM_REQUEST_MASK);
  deadline = p9_deadline_ms(20U);
  while (p9_time_now() < deadline) {
    uint32_t pl_status = p9_pl_read(IR_REG_P9_STATUS);
    if ((pl_status & P9_STATUS_ENDPOINT_ARMED) == 0U &&
        (pl_status & P9_STATUS_TX_KILL_ACTIVE) != 0U &&
        (pl_status & P9_STATUS_RAW_BUSY) == 0U) {
      m->permit_result_flags |= (1U << 1) | (1U << 2);
      break;
    }
    usleep(P9_POLL_DELAY_US);
  }
  m->permit_status_after_drop = p9_pl_read(IR_REG_P9_STATUS);
  p9_read_physical_tx_counts(m->permit_tx_after_drop);
  m->permit_raw_sent_after_drop = p9_pl_read(IR_REG_P9_RAW_SENT_COUNT);
  usleep(1000U);
  volatile uint32_t stable_counts[4];
  p9_read_physical_tx_counts(stable_counts);
  uint32_t stable_sent = p9_pl_read(IR_REG_P9_RAW_SENT_COUNT);
  uint32_t stable = stable_sent == m->permit_raw_sent_after_drop;
  for (uint32_t index = 0U; index < 4U; ++index)
    if (stable_counts[index] != m->permit_tx_after_drop[index]) stable = 0U;
  if (stable != 0U) m->permit_result_flags |= 1U << 3;

  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_ARM_REQUEST_MASK);
  deadline = p9_deadline_ms(20U);
  while (p9_time_now() < deadline) {
    uint32_t pl_status = p9_pl_read(IR_REG_P9_STATUS);
    if ((pl_status & P9_STATUS_ENDPOINT_ARMED) != 0U &&
        (pl_status & P9_STATUS_TX_KILL_ACTIVE) == 0U) {
      m->permit_result_flags |= 1U << 4;
      break;
    }
    usleep(P9_POLL_DELAY_US);
  }
  usleep(1000U);
  m->permit_status_after_rearm = p9_pl_read(IR_REG_P9_STATUS);
  p9_read_physical_tx_counts(m->permit_tx_after_rearm);
  m->permit_raw_sent_after_rearm = p9_pl_read(IR_REG_P9_RAW_SENT_COUNT);
  uint32_t no_resume =
      (m->permit_status_after_rearm & P9_STATUS_RAW_BUSY) == 0U &&
      m->permit_raw_sent_after_rearm == m->permit_raw_sent_after_drop;
  for (uint32_t index = 0U; index < 4U; ++index)
    if (m->permit_tx_after_rearm[index] != m->permit_tx_after_drop[index])
      no_resume = 0U;
  if (no_resume != 0U) m->permit_result_flags |= 1U << 5;
  status = m->permit_result_flags == 0x3fU ?
               P9_RUNTIME_OK : P9_RUNTIME_PERMIT_DROP;

permit_exit:
  {
    int shutdown_status = p9_shutdown();
    if (status == P9_RUNTIME_OK) status = shutdown_status;
  }
  return status;
}

static int p9_command_idle_noise(volatile p9_mailbox_t *m) {
  if (m->idle_duration_ms == 0U || m->idle_duration_ms > 5000U)
    return P9_RUNTIME_BAD_ARGUMENT;
  int status = p9_shutdown();
  if (status != P9_RUNTIME_OK) return status;
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_CLEAR_COUNTERS_MASK);
  p9_pl_write(IR_REG_P9_CONTROL, IR_P9_CONTROL_RECEIVER_ENABLE_MASK);
  uint32_t expected = p9_expected_phy_mask();
  uint32_t expected_startup = expected << P10_PHY_STARTUP_SHIFT;
  uint64_t ready_deadline = p9_deadline_ms(100U);
  while ((p9_pl_read(IR_REG_P9_PHY_STATUS) &
          (expected | expected_startup)) != (expected | expected_startup)) {
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
          (p9_pl_read(IR_REG_P9_PHY_STATUS) &
           (P10_PHY_READY_ALL_MASK << P10_PHY_SAFETY_SHIFT)) != 0U) {
        status = P9_RUNTIME_SAFE_IDLE;
        break;
      }
      volatile uint32_t local_tx_counts[4];
      p9_read_physical_tx_counts(local_tx_counts);
      uint32_t any_local_tx = 0U;
      for (uint32_t lane = 0U; lane < P10_LANE_COUNT; ++lane)
        any_local_tx |= local_tx_counts[lane];
      if (any_local_tx != 0U) {
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

#if P10_ENDPOINT_ROLE != 0
#include "p10_1_runtime_extension.inc"
#endif

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
  volatile uint32_t *extended = &m->payload_prepare_ticks_low;
  for (uint32_t index = 0U; index < 41U; ++index) extended[index] = 0U;
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
    case P9_COMMAND_PERMIT_DROP_DIAGNOSTIC:
      return p9_command_permit_drop(m);
#if P10_ENDPOINT_ROLE != 0
    case P9_COMMAND_P10_1_AUTONOMOUS_STREAM:
      return p10_1_command_autonomous_stream(m);
    case P9_COMMAND_P10_5_AUTONOMOUS_DUAL_STREAM:
      return p10_1_command_autonomous_stream(m);
    case P9_COMMAND_P10_5_DUAL_OBJECT:
      return p10_5_command_dual_object(m);
#endif
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
#if P10_ENDPOINT_ROLE != 0
  p10_1_runtime_boot_init();
#endif
  int startup_status = p10_ps_activity_leds_initialize();
  int shutdown_status = p9_shutdown();
  if (startup_status == P9_RUNTIME_OK) startup_status = shutdown_status;
  if (startup_status == P9_RUNTIME_OK)
    startup_status = p9_reset_stream_path(8U, 0U, 0U);
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
    p10_ps_activity_leds_force_off();
    /* LED monitoring is deliberately outside command control flow and all
     * TX safety paths.  Preserve a sticky, evidence-only diagnostic if its
     * descriptor accounting ever underflows/overflows; do not turn the LED
     * monitor into a transport interlock or silently hide the defect. */
    if (p10_ps_activity_leds_faulted() != 0U &&
        mailbox->last_error_detail == 0U)
      mailbox->last_error_detail = UINT32_C(0x50534c44); /* PSLD */
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
