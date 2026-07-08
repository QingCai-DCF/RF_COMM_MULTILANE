#ifndef IR_HW_H
#define IR_HW_H

#include <stdint.h>
#include <stddef.h>

#include "xaxidma.h"
#include "xparameters.h"

#define IR_HW_BASEADDR_FALLBACK       0x43C00000u
#define IR_HW_DMA_DEVICE_ID_FALLBACK  0u

#if defined(XPAR_IR_ARRAY_TOP_AXI_0_BASEADDR)
#define IR_HW_BASEADDR XPAR_IR_ARRAY_TOP_AXI_0_BASEADDR
#elif defined(XPAR_IR_ARRAY_TOP_AXI_0_S_AXI_BASEADDR)
#define IR_HW_BASEADDR XPAR_IR_ARRAY_TOP_AXI_0_S_AXI_BASEADDR
#elif defined(XPAR_XIR_ARRAY_TOP_AXI_0_BASEADDR)
#define IR_HW_BASEADDR XPAR_XIR_ARRAY_TOP_AXI_0_BASEADDR
#else
#define IR_HW_BASEADDR IR_HW_BASEADDR_FALLBACK
#endif

#if defined(XPAR_AXIDMA_0_DEVICE_ID)
#define IR_HW_DMA_DEVICE_ID XPAR_AXIDMA_0_DEVICE_ID
#elif defined(XPAR_AXI_DMA_0_DEVICE_ID)
#define IR_HW_DMA_DEVICE_ID XPAR_AXI_DMA_0_DEVICE_ID
#else
#define IR_HW_DMA_DEVICE_ID IR_HW_DMA_DEVICE_ID_FALLBACK
#endif

#define IR_HW_REG_CONTROL             0x00u
#define IR_HW_REG_SESSION             0x04u
#define IR_HW_REG_LANE_MASK           0x08u
#define IR_HW_REG_STATUS              0x0cu
#define IR_HW_REG_STICKY              0x10u
#define IR_HW_REG_COMMIT              0x14u
#define IR_HW_REG_TX_FRAG_PENDING     0x18u
#define IR_HW_REG_TX_FRAG_INFLIGHT    0x1cu
#define IR_HW_REG_TX_FRAG_ACKED       0x20u
#define IR_HW_REG_RX_RECV_BITMAP      0x24u
#define IR_HW_REG_RX_LANE_MASK        0x28u
#define IR_HW_REG_TX_LANE_COUNT       0x2cu
#define IR_HW_REG_RX_LANE_GOOD_COUNT  0x30u
#define IR_HW_REG_RX_LANE_CRC_COUNT   0x34u
#define IR_HW_REG_RX_LANE_ERR_COUNT   0x38u
#define IR_HW_REG_PHY_LANE0_DBG       0x3cu
#define IR_HW_REG_OBS_SELECT          IR_HW_REG_TEST_RX_PACKET_COUNT
#define IR_HW_REG_OBS_DATA            IR_HW_REG_PHY_LANE0_DBG

#define IR_HW_OBS_SELECT_MAGIC        0xA5000000u
#define IR_HW_OBS_SIGNATURE_EXPECTED  0x50330007u
#define IR_HW_OBS_SIG                 0u
#define IR_HW_OBS_CORE_TVALID         1u
#define IR_HW_OBS_CORE_TREADY         2u
#define IR_HW_OBS_CORE_TLAST          3u
#define IR_HW_OBS_CORE_BYTES          4u
#define IR_HW_OBS_SYNTH_TVALID        5u
#define IR_HW_OBS_SYNTH_TLAST         6u
#define IR_HW_OBS_SYNTH_BYTES         7u
#define IR_HW_OBS_MUX_TVALID          8u
#define IR_HW_OBS_MUX_TLAST           9u
#define IR_HW_OBS_MUX_BYTES           10u

#define IR_HW_REG_TEST_RX_PAYLOAD_BYTES IR_HW_REG_TX_FRAG_PENDING
#define IR_HW_REG_TEST_RX_PATTERN_ID    IR_HW_REG_TX_FRAG_INFLIGHT
#define IR_HW_REG_TEST_RX_SEQ_BASE      IR_HW_REG_TX_FRAG_ACKED
#define IR_HW_REG_TEST_RX_PACKET_COUNT  IR_HW_REG_RX_RECV_BITMAP

#define IR_HW_CONTROL_ENABLE             (1u << 0)
#define IR_HW_CONTROL_TEST_MODE_ENABLE   (1u << 8)
#define IR_HW_COMMIT_CONFIG              (1u << 0)
#define IR_HW_COMMIT_TEST_RX_INJECT      (1u << 1)

#define IR_HW_STICKY_TX_DONE          (1u << 0)
#define IR_HW_STICKY_RX_DONE          (1u << 1)
#define IR_HW_STICKY_TX_OVERFLOW      (1u << 2)
#define IR_HW_STICKY_TX_RETRY_EXH     (1u << 3)
#define IR_HW_STICKY_RX_HEADER_ERR    (1u << 4)
#define IR_HW_STICKY_RX_PROTOCOL_ERR  (1u << 5)
#define IR_HW_STICKY_RX_FRAME_OVF     (1u << 6)
#define IR_HW_STICKY_RX_CRC_ERR       (1u << 7)
#define IR_HW_STICKY_RX_OVERRUN       (1u << 8)
#define IR_HW_STICKY_ALL              0x000001ffu

#ifndef IR_HW_MAX_PACKET_BYTES
#define IR_HW_MAX_PACKET_BYTES        256u
#endif
#ifndef IR_HW_APP_HEADER_BYTES
#define IR_HW_APP_HEADER_BYTES        8u
#endif
#if IR_HW_MAX_PACKET_BYTES <= IR_HW_APP_HEADER_BYTES
#error "IR_HW_MAX_PACKET_BYTES must be larger than IR_HW_APP_HEADER_BYTES"
#endif
#define IR_HW_MAX_PAYLOAD_BYTES       (IR_HW_MAX_PACKET_BYTES - IR_HW_APP_HEADER_BYTES)
#ifndef IR_HW_RX_TRANSFER_BYTES
#define IR_HW_RX_TRANSFER_BYTES       IR_HW_MAX_PACKET_BYTES
#endif
#if IR_HW_RX_TRANSFER_BYTES > IR_HW_MAX_PACKET_BYTES
#error "IR_HW_RX_TRANSFER_BYTES must not exceed IR_HW_MAX_PACKET_BYTES"
#endif
#define IR_HW_DEFAULT_LANE_MASK       0x00000001u
#define IR_HW_DEFAULT_SESSION         0x0001u

#define IR_HW_POLL_NO_DATA            0
#define IR_HW_POLL_DATA               2

#define IR_HW_TX_NO_EVENT             0
#define IR_HW_TX_EVENT                2

typedef struct {
	uint32_t status;
	uint32_t sticky;
	uint32_t tx_frag_pending;
	uint32_t tx_frag_inflight;
	uint32_t tx_frag_acked;
	uint32_t rx_recv_bitmap;
	uint32_t tx_ok;
	uint32_t tx_fail;
	uint32_t tx_start_count;
	uint32_t tx_done_count;
	uint32_t tx_done_timeout_count;
	uint32_t tx_retry_count_total;
	uint32_t tx_retry_exhausted_count;
	uint32_t ack_timeout_count;
	uint32_t ack_late_count;
	uint32_t max_retry_seen;
	uint32_t first_fail_sent_index;
	uint32_t first_fail_timestamp;
	uint32_t first_fail_seq;
	uint32_t first_fail_pre_sticky;
	uint32_t first_fail_pre_phy0;
	uint32_t first_fail_pre_tx_lane;
	uint32_t first_fail_post_sticky;
	uint32_t first_fail_post_phy0;
	uint32_t rx_ok;
	uint32_t rx_bad;
	uint32_t tx_lane_mask;
	uint32_t rx_lane_mask;
	uint32_t tx_lane_count;
	uint32_t rx_lane_good_count;
	uint32_t rx_lane_crc_count;
	uint32_t rx_lane_err_count;
	uint32_t phy_lane0_dbg;
	uint32_t obs_signature;
	uint32_t core_rx_tvalid_count;
	uint32_t core_rx_tready_count;
	uint32_t core_rx_tlast_count;
	uint32_t core_rx_byte_count;
	uint32_t synth_rx_tvalid_count;
	uint32_t synth_rx_tlast_count;
	uint32_t synth_rx_byte_count;
	uint32_t mux_rx_tvalid_count;
	uint32_t mux_rx_tlast_count;
	uint32_t mux_rx_byte_count;
	uint32_t s2mm_arm_count;
	uint32_t s2mm_done_count;
	uint32_t s2mm_error_count;
	uint32_t s2mm_timeout_count;
	uint32_t rx_app_header_ok_count;
	uint32_t rx_app_header_bad_count;
	uint32_t rx_length_bad_count;
	uint32_t recovery_count;
	uint32_t pre_recover_status;
	uint32_t pre_recover_sticky;
	uint32_t pre_recover_tx_lane_count;
	uint32_t pre_recover_rx_lane_err_count;
	uint32_t pre_recover_phy_lane0_dbg;
	uint32_t pre_recover_dma_tx_status;
	uint32_t pre_recover_dma_rx_status;
	uint32_t dma_tx_status;
	uint32_t dma_rx_status;
	uint32_t rx_armed;
} ir_hw_status_t;

typedef struct {
	XAxiDma dma;
	uintptr_t ir_base;
	uint16_t session_id;
	uint16_t next_app_seq;
	uint32_t lane_mask;
	uint32_t rx_lane_mask;
	uint32_t tx_ok;
	uint32_t tx_fail;
	uint32_t tx_start_count;
	uint32_t tx_done_count;
	uint32_t tx_done_timeout_count;
	uint32_t tx_retry_count_total;
	uint32_t tx_retry_exhausted_count;
	uint32_t ack_timeout_count;
	uint32_t ack_late_count;
	uint32_t max_retry_seen;
	uint32_t first_fail_sent_index;
	uint32_t first_fail_timestamp;
	uint32_t first_fail_seq;
	uint32_t first_fail_pre_sticky;
	uint32_t first_fail_pre_phy0;
	uint32_t first_fail_pre_tx_lane;
	uint32_t first_fail_post_sticky;
	uint32_t first_fail_post_phy0;
	uint32_t rx_ok;
	uint32_t rx_bad;
	uint32_t recovery_count;
	uint32_t pre_recover_status;
	uint32_t pre_recover_sticky;
	uint32_t pre_recover_tx_lane_count;
	uint32_t pre_recover_rx_lane_err_count;
	uint32_t pre_recover_phy_lane0_dbg;
	uint32_t pre_recover_dma_tx_status;
	uint32_t pre_recover_dma_rx_status;
	uint32_t s2mm_arm_count;
	uint32_t s2mm_done_count;
	uint32_t s2mm_error_count;
	uint32_t s2mm_timeout_count;
	uint32_t rx_app_header_ok_count;
	uint32_t rx_app_header_bad_count;
	uint32_t rx_length_bad_count;
	int rx_armed;
	int enabled;
	const char *last_error;
} ir_hw_t;

int ir_hw_init(ir_hw_t *hw);
int ir_hw_configure(ir_hw_t *hw, uint8_t mask, uint8_t enable,
                    uint16_t session_id, uint32_t lane_mask,
                    uint32_t rx_lane_mask);
int ir_hw_send_payload(ir_hw_t *hw, const uint8_t *payload, size_t length);
int ir_hw_start_payload_async(ir_hw_t *hw, const uint8_t *payload, size_t length);
int ir_hw_poll_tx_events(ir_hw_t *hw, uint32_t *done_count, uint32_t *fail_count);
int ir_hw_poll_payload(ir_hw_t *hw, uint8_t *payload, size_t capacity, size_t *length);
int ir_hw_inject_rx_synthetic(ir_hw_t *hw, size_t payload_bytes,
                              uint32_t pattern_id, uint16_t seq_base);
void ir_hw_disable_test_mode(ir_hw_t *hw);
void ir_hw_get_status(ir_hw_t *hw, ir_hw_status_t *status);
void ir_hw_clear_sticky(ir_hw_t *hw);
void ir_hw_note_rx_timeout(ir_hw_t *hw);
const char *ir_hw_last_error(const ir_hw_t *hw);

#endif
