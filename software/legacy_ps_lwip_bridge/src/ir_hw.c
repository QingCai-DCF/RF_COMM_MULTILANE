#include "ir_hw.h"

#include <string.h>

#include "sleep.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "xil_printf.h"
#include "xstatus.h"

#include "rf_protocol.h"

#define IR_APP_MAGIC0 'I'
#define IR_APP_MAGIC1 'R'
#define IR_APP_MAGIC2 'P'
#define IR_APP_MAGIC3 '1'
#define IR_TX_TIMEOUT_US 2000000u
#ifndef IR_TX_POLL_US
#define IR_TX_POLL_US 10u
#endif
#ifndef IR_CONFIG_COMMIT_US
#define IR_CONFIG_COMMIT_US 100u
#endif
#ifndef IR_STICKY_CLEAR_WAIT_US
#define IR_STICKY_CLEAR_WAIT_US 2000u
#endif
#ifndef IR_STICKY_CLEAR_POLL_US
#define IR_STICKY_CLEAR_POLL_US 1u
#endif
#ifndef IR_HW_SW_RETRY_LIMIT
#define IR_HW_SW_RETRY_LIMIT 2u
#endif
#define IR_CONFIG_MASK_VALID (RF_CONFIG_ENABLE | RF_CONFIG_SESSION | RF_CONFIG_LANE_MASK | RF_CONFIG_RX_LANE_MASK)
#define IR_HW_TX_STICKY_CLEAR_BITS (IR_HW_STICKY_TX_DONE | IR_HW_STICKY_TX_RETRY_EXH | IR_HW_STICKY_TX_OVERFLOW)
#define IR_HW_TX_FAIL_STICKY_BITS (IR_HW_STICKY_TX_RETRY_EXH | IR_HW_STICKY_TX_OVERFLOW)

static uint8_t tx_raw[IR_HW_MAX_PACKET_BYTES] __attribute__((aligned(64)));
static uint8_t rx_raw[IR_HW_MAX_PACKET_BYTES] __attribute__((aligned(64)));

static int arm_rx(ir_hw_t *hw);

static void note_sw_retry(ir_hw_t *hw, uint32_t retry_seen)
{
	hw->tx_retry_count_total++;
	if (retry_seen > hw->max_retry_seen) {
		hw->max_retry_seen = retry_seen;
	}
}

static void ir_set_error(ir_hw_t *hw, const char *error)
{
	hw->last_error = error;
}

static uint32_t ir_read(ir_hw_t *hw, uint32_t offset)
{
	return Xil_In32(hw->ir_base + offset);
}

static void ir_write(ir_hw_t *hw, uint32_t offset, uint32_t value)
{
	Xil_Out32(hw->ir_base + offset, value);
}

static uint32_t ir_read_obs(ir_hw_t *hw, uint32_t selector)
{
	ir_write(hw, IR_HW_REG_OBS_SELECT, IR_HW_OBS_SELECT_MAGIC | (selector & 0xffu));
	return ir_read(hw, IR_HW_REG_OBS_DATA);
}

static int clear_sticky_bits_wait(ir_hw_t *hw, uint32_t bits, uint32_t timeout_us)
{
	uint32_t polls;

	ir_write(hw, IR_HW_REG_STICKY, bits);
	if (timeout_us == 0u) {
		return XST_SUCCESS;
	}

	polls = (timeout_us + IR_STICKY_CLEAR_POLL_US - 1u) / IR_STICKY_CLEAR_POLL_US;
	while (polls > 0u) {
		if ((ir_read(hw, IR_HW_REG_STICKY) & bits) == 0u) {
			return XST_SUCCESS;
		}
		usleep(IR_STICKY_CLEAR_POLL_US);
		polls--;
	}

	ir_set_error(hw, "sticky_clear_timeout");
	return XST_FAILURE;
}

static void ir_commit_control(ir_hw_t *hw, uint32_t enable)
{
	ir_write(hw, IR_HW_REG_CONTROL, (enable != 0u) ? IR_HW_CONTROL_ENABLE : 0u);
	usleep(IR_CONFIG_COMMIT_US);
}

static uint32_t dma_status(ir_hw_t *hw, int direction)
{
	UINTPTR base;

	base = hw->dma.RegBase;
	if (direction == XAXIDMA_DEVICE_TO_DMA) {
		base += XAXIDMA_RX_OFFSET;
	}

	return XAxiDma_ReadReg(base, XAXIDMA_SR_OFFSET);
}

static int wait_dma_idle(ir_hw_t *hw, int direction, uint32_t timeout_us)
{
	uint32_t status;

	while (timeout_us > 0u) {
		status = dma_status(hw, direction);
		if ((status & XAXIDMA_ERR_ALL_MASK) != 0u) {
			return XST_FAILURE;
		}
		if ((status & (XAXIDMA_HALTED_MASK | XAXIDMA_IDLE_MASK)) != 0u) {
			return XST_SUCCESS;
		}
		usleep(1u);
		timeout_us--;
	}
	return XST_FAILURE;
}

static int reset_dma(ir_hw_t *hw)
{
	int timeout;

	XAxiDma_Reset(&hw->dma);
	timeout = 1000000;
	while (!XAxiDma_ResetIsDone(&hw->dma) && timeout > 0) {
		timeout--;
	}
	if (timeout == 0) {
		ir_set_error(hw, "dma_reset_timeout");
		return XST_FAILURE;
	}

	XAxiDma_IntrDisable(&hw->dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
	XAxiDma_IntrDisable(&hw->dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
	return XST_SUCCESS;
}

static int arm_rx(ir_hw_t *hw)
{
	int status;

	status = wait_dma_idle(hw, XAXIDMA_DEVICE_TO_DMA, 100000u);
	if (status != XST_SUCCESS) {
		hw->rx_armed = 0;
		hw->s2mm_timeout_count++;
		ir_set_error(hw, "rx_dma_busy_timeout");
		return status;
	}

	Xil_DCacheFlushRange((UINTPTR)rx_raw, IR_HW_RX_TRANSFER_BYTES);
	status = XAxiDma_SimpleTransfer(&hw->dma, (UINTPTR)rx_raw,
	                                IR_HW_RX_TRANSFER_BYTES,
	                                XAXIDMA_DEVICE_TO_DMA);
	if (status != XST_SUCCESS) {
		hw->rx_armed = 0;
		hw->s2mm_error_count++;
		ir_set_error(hw, "rx_dma_start_failed");
		return status;
	}

	hw->s2mm_arm_count++;
	hw->rx_armed = 1;
	return XST_SUCCESS;
}

static int recover_link(ir_hw_t *hw, const char *error)
{
	uint32_t was_enabled;
	uint32_t mark_first_fail;
	int status;

	hw->recovery_count++;
	hw->pre_recover_status = ir_read(hw, IR_HW_REG_STATUS);
	hw->pre_recover_sticky = ir_read(hw, IR_HW_REG_STICKY);
	hw->pre_recover_tx_lane_count = ir_read(hw, IR_HW_REG_TX_LANE_COUNT);
	hw->pre_recover_rx_lane_err_count = ir_read(hw, IR_HW_REG_RX_LANE_ERR_COUNT);
	hw->pre_recover_phy_lane0_dbg = ir_read(hw, IR_HW_REG_PHY_LANE0_DBG);
	hw->pre_recover_dma_tx_status = dma_status(hw, XAXIDMA_DMA_TO_DEVICE);
	hw->pre_recover_dma_rx_status = dma_status(hw, XAXIDMA_DEVICE_TO_DMA);
	mark_first_fail = (hw->first_fail_sent_index == 0u) ? 1u : 0u;
	if (mark_first_fail != 0u) {
		hw->first_fail_sent_index = hw->tx_start_count;
		hw->first_fail_timestamp = 0u;
		hw->first_fail_seq = (hw->next_app_seq == 0u) ? 0u : (uint32_t)(hw->next_app_seq - 1u);
		hw->first_fail_pre_sticky = hw->pre_recover_sticky;
		hw->first_fail_pre_phy0 = hw->pre_recover_phy_lane0_dbg;
		hw->first_fail_pre_tx_lane = hw->pre_recover_tx_lane_count;
	}
	was_enabled = (hw->enabled != 0) ? 1u : 0u;
	hw->rx_armed = 0;

	ir_commit_control(hw, 0u);
	ir_write(hw, IR_HW_REG_STICKY, IR_HW_STICKY_ALL);

	status = reset_dma(hw);
	if (status != XST_SUCCESS) {
		return status;
	}

	ir_write(hw, IR_HW_REG_SESSION, hw->session_id);
	ir_write(hw, IR_HW_REG_LANE_MASK, hw->lane_mask);
	ir_write(hw, IR_HW_REG_RX_LANE_MASK, hw->rx_lane_mask);
	ir_write(hw, IR_HW_REG_STICKY, IR_HW_STICKY_ALL);
	ir_commit_control(hw, was_enabled);
	hw->enabled = (int)was_enabled;

	if (was_enabled != 0u) {
		status = arm_rx(hw);
		if (status != XST_SUCCESS) {
			return status;
		}
	}

	if (mark_first_fail != 0u) {
		hw->first_fail_post_sticky = ir_read(hw, IR_HW_REG_STICKY);
		hw->first_fail_post_phy0 = ir_read(hw, IR_HW_REG_PHY_LANE0_DBG);
	}

	ir_set_error(hw, error);
	return XST_SUCCESS;
}

int ir_hw_init(ir_hw_t *hw)
{
	XAxiDma_Config *cfg;
	int status;

	memset(hw, 0, sizeof(*hw));
	hw->ir_base = IR_HW_BASEADDR;
	hw->session_id = IR_HW_DEFAULT_SESSION;
	hw->next_app_seq = 1u;
	hw->lane_mask = IR_HW_DEFAULT_LANE_MASK;
	hw->rx_lane_mask = IR_HW_DEFAULT_LANE_MASK;
	hw->last_error = "";
	hw->enabled = 1;

	cfg = XAxiDma_LookupConfig(IR_HW_DMA_DEVICE_ID);
	if (cfg == NULL) {
		xil_printf("AXI DMA config not found for device id %u\r\n",
		           (unsigned)IR_HW_DMA_DEVICE_ID);
		return XST_FAILURE;
	}

	status = XAxiDma_CfgInitialize(&hw->dma, cfg);
	if (status != XST_SUCCESS) {
		xil_printf("AXI DMA init failed: %d\r\n", status);
		return status;
	}

	status = reset_dma(hw);
	if (status != XST_SUCCESS) {
		xil_printf("AXI DMA reset timeout\r\n");
		return XST_FAILURE;
	}

	if (XAxiDma_HasSg(&hw->dma)) {
		xil_printf("AXI DMA is configured for SG mode; simple mode expected\r\n");
		return XST_FAILURE;
	}

	ir_write(hw, IR_HW_REG_SESSION, hw->session_id);
	ir_write(hw, IR_HW_REG_LANE_MASK, hw->lane_mask);
	ir_write(hw, IR_HW_REG_RX_LANE_MASK, hw->rx_lane_mask);
	ir_write(hw, IR_HW_REG_STICKY, IR_HW_STICKY_ALL);
	ir_commit_control(hw, 1u);

	return arm_rx(hw);
}

int ir_hw_configure(ir_hw_t *hw, uint8_t mask, uint8_t enable,
                    uint16_t session_id, uint32_t lane_mask,
                    uint32_t rx_lane_mask)
{
	int changing_link_params;
	uint32_t next_enable;
	uint16_t next_session;
	uint32_t next_lane_mask;
	uint32_t next_rx_lane_mask;

	if (mask == 0u || (mask & ~IR_CONFIG_MASK_VALID) != 0u) {
		ir_set_error(hw, "config_bad_mask");
		return XST_FAILURE;
	}

	next_enable = ((mask & RF_CONFIG_ENABLE) != 0u) ? ((enable != 0u) ? 1u : 0u) : (uint32_t)hw->enabled;
	next_session = ((mask & RF_CONFIG_SESSION) != 0u) ? session_id : hw->session_id;
	next_lane_mask = ((mask & RF_CONFIG_LANE_MASK) != 0u) ? lane_mask : hw->lane_mask;
	next_rx_lane_mask = hw->rx_lane_mask;
	if ((mask & RF_CONFIG_RX_LANE_MASK) != 0u) {
		next_rx_lane_mask = rx_lane_mask;
	} else if ((mask & RF_CONFIG_LANE_MASK) != 0u) {
		next_rx_lane_mask = lane_mask;
	}

	if (next_lane_mask == 0u) {
		ir_set_error(hw, "config_bad_lane_mask");
		return XST_FAILURE;
	}
	if (next_rx_lane_mask == 0u) {
		ir_set_error(hw, "config_bad_rx_lane_mask");
		return XST_FAILURE;
	}

	changing_link_params = ((mask & (RF_CONFIG_SESSION | RF_CONFIG_LANE_MASK | RF_CONFIG_RX_LANE_MASK)) != 0u);
	if (changing_link_params && hw->enabled && next_enable != 0u) {
		ir_commit_control(hw, 0u);
	}

	if ((mask & RF_CONFIG_SESSION) != 0u) {
		ir_write(hw, IR_HW_REG_SESSION, next_session);
	}
	if ((mask & RF_CONFIG_LANE_MASK) != 0u) {
		ir_write(hw, IR_HW_REG_LANE_MASK, next_lane_mask);
	}
	if ((mask & (RF_CONFIG_LANE_MASK | RF_CONFIG_RX_LANE_MASK)) != 0u) {
		ir_write(hw, IR_HW_REG_RX_LANE_MASK, next_rx_lane_mask);
	}

	ir_commit_control(hw, next_enable);

	hw->enabled = (int)next_enable;
	hw->session_id = next_session;
	hw->lane_mask = next_lane_mask;
	hw->rx_lane_mask = next_rx_lane_mask;
	ir_set_error(hw, "");
	return XST_SUCCESS;
}

void ir_hw_clear_sticky(ir_hw_t *hw)
{
	ir_write(hw, IR_HW_REG_STICKY, IR_HW_STICKY_ALL);
	hw->tx_start_count = 0u;
	hw->tx_done_count = 0u;
	hw->tx_done_timeout_count = 0u;
	hw->tx_retry_count_total = 0u;
	hw->tx_retry_exhausted_count = 0u;
	hw->ack_timeout_count = 0u;
	hw->ack_late_count = 0u;
	hw->max_retry_seen = 0u;
	hw->first_fail_sent_index = 0u;
	hw->first_fail_timestamp = 0u;
	hw->first_fail_seq = 0u;
	hw->first_fail_pre_sticky = 0u;
	hw->first_fail_pre_phy0 = 0u;
	hw->first_fail_pre_tx_lane = 0u;
	hw->first_fail_post_sticky = 0u;
	hw->first_fail_post_phy0 = 0u;
	hw->s2mm_arm_count = 0u;
	hw->s2mm_done_count = 0u;
	hw->s2mm_error_count = 0u;
	hw->s2mm_timeout_count = 0u;
	hw->rx_app_header_ok_count = 0u;
	hw->rx_app_header_bad_count = 0u;
	hw->rx_length_bad_count = 0u;
}

static int prepare_tx_raw(ir_hw_t *hw, const uint8_t *payload, size_t length,
                          size_t *raw_len)
{
	if (payload == NULL || length == 0u || length > IR_HW_MAX_PAYLOAD_BYTES) {
		ir_set_error(hw, "tx_invalid_payload");
		return XST_FAILURE;
	}

	*raw_len = length + IR_HW_APP_HEADER_BYTES;
	tx_raw[0] = IR_APP_MAGIC0;
	tx_raw[1] = IR_APP_MAGIC1;
	tx_raw[2] = IR_APP_MAGIC2;
	tx_raw[3] = IR_APP_MAGIC3;
	rf_put_u16_le(&tx_raw[4], hw->next_app_seq++);
	rf_put_u16_le(&tx_raw[6], (uint16_t)length);
	memcpy(&tx_raw[IR_HW_APP_HEADER_BYTES], payload, length);
	return XST_SUCCESS;
}

int ir_hw_start_payload_async(ir_hw_t *hw, const uint8_t *payload, size_t length)
{
	size_t raw_len;
	int status;

	status = prepare_tx_raw(hw, payload, length, &raw_len);
	if (status != XST_SUCCESS) {
		hw->tx_fail++;
		return status;
	}
	hw->tx_start_count++;

	status = wait_dma_idle(hw, XAXIDMA_DMA_TO_DEVICE, 100000u);
	if (status != XST_SUCCESS) {
		hw->tx_fail++;
		ir_set_error(hw, "tx_dma_busy_timeout");
		(void)recover_link(hw, "tx_dma_busy_timeout");
		return status;
	}

	Xil_DCacheFlushRange((UINTPTR)tx_raw, (u32)raw_len);
	status = XAxiDma_SimpleTransfer(&hw->dma, (UINTPTR)tx_raw, (u32)raw_len,
	                                XAXIDMA_DMA_TO_DEVICE);
	if (status != XST_SUCCESS) {
		hw->tx_fail++;
		ir_set_error(hw, "tx_dma_start_failed");
		(void)recover_link(hw, "tx_dma_start_failed");
		return status;
	}

	status = wait_dma_idle(hw, XAXIDMA_DMA_TO_DEVICE, 100000u);
	if (status != XST_SUCCESS) {
		hw->tx_fail++;
		ir_set_error(hw, "tx_dma_complete_timeout");
		(void)recover_link(hw, "tx_dma_complete_timeout");
		return status;
	}

	ir_set_error(hw, "");
	return XST_SUCCESS;
}

int ir_hw_poll_tx_events(ir_hw_t *hw, uint32_t *done_count, uint32_t *fail_count)
{
	uint32_t sticky;

	if (done_count == NULL || fail_count == NULL) {
		ir_set_error(hw, "tx_event_bad_arg");
		return XST_FAILURE;
	}

	*done_count = 0u;
	*fail_count = 0u;
	sticky = ir_read(hw, IR_HW_REG_STICKY);

	if ((sticky & IR_HW_STICKY_TX_DONE) != 0u) {
		*done_count = 1u;
		hw->tx_ok++;
		hw->tx_done_count++;
	}
	if ((sticky & (IR_HW_STICKY_TX_RETRY_EXH | IR_HW_STICKY_TX_OVERFLOW)) != 0u) {
		*fail_count = 1u;
		hw->tx_fail++;
		if ((sticky & IR_HW_STICKY_TX_RETRY_EXH) != 0u) {
			hw->tx_retry_exhausted_count++;
			hw->ack_timeout_count++;
		}
	}

	if ((*done_count == 0u) && (*fail_count == 0u)) {
		return IR_HW_TX_NO_EVENT;
	}

	ir_write(hw, IR_HW_REG_STICKY,
	         IR_HW_STICKY_TX_DONE | IR_HW_STICKY_TX_RETRY_EXH |
	         IR_HW_STICKY_TX_OVERFLOW);

	if (*fail_count != 0u) {
		(void)recover_link(hw, "tx_retry_exhausted");
	} else {
		ir_set_error(hw, "");
	}

	return IR_HW_TX_EVENT;
}

int ir_hw_send_payload(ir_hw_t *hw, const uint8_t *payload, size_t length)
{
	uint32_t sticky;
	size_t raw_len;
	int status;
	uint32_t timeout;
	uint32_t attempt;

	status = prepare_tx_raw(hw, payload, length, &raw_len);
	if (status != XST_SUCCESS) {
		hw->tx_fail++;
		return status;
	}
	hw->tx_start_count++;

	for (attempt = 0u; attempt <= IR_HW_SW_RETRY_LIMIT; attempt++) {
		/*
		 * TX_DONE can remain visible for several AXI cycles after a W1C clear
		 * because the underlying sticky bit crosses from the PHY clock domain.
		 * Gate only on stale failure bits here; waiting for TX_DONE to read
		 * back as zero creates false sticky_clear_timeout failures between
		 * otherwise successful packets.
		 */
		ir_write(hw, IR_HW_REG_STICKY, IR_HW_TX_STICKY_CLEAR_BITS);
		status = clear_sticky_bits_wait(hw, IR_HW_TX_FAIL_STICKY_BITS,
		                                IR_STICKY_CLEAR_WAIT_US);
		if (status != XST_SUCCESS) {
			(void)recover_link(hw, "sticky_clear_timeout");
			if (attempt < IR_HW_SW_RETRY_LIMIT) {
				note_sw_retry(hw, attempt + 1u);
				continue;
			}
			hw->tx_fail++;
			return status;
		}

		status = wait_dma_idle(hw, XAXIDMA_DMA_TO_DEVICE, 100000u);
		if (status != XST_SUCCESS) {
			ir_set_error(hw, "tx_dma_busy_timeout");
			(void)recover_link(hw, "tx_dma_busy_timeout");
			if (attempt < IR_HW_SW_RETRY_LIMIT) {
				note_sw_retry(hw, attempt + 1u);
				continue;
			}
			hw->tx_fail++;
			return status;
		}

		Xil_DCacheFlushRange((UINTPTR)tx_raw, (u32)raw_len);
		status = XAxiDma_SimpleTransfer(&hw->dma, (UINTPTR)tx_raw, (u32)raw_len,
		                                XAXIDMA_DMA_TO_DEVICE);
		if (status != XST_SUCCESS) {
			ir_set_error(hw, "tx_dma_start_failed");
			(void)recover_link(hw, "tx_dma_start_failed");
			if (attempt < IR_HW_SW_RETRY_LIMIT) {
				note_sw_retry(hw, attempt + 1u);
				continue;
			}
			hw->tx_fail++;
			return status;
		}

		status = wait_dma_idle(hw, XAXIDMA_DMA_TO_DEVICE, 100000u);
		if (status != XST_SUCCESS) {
			ir_set_error(hw, "tx_dma_complete_timeout");
			(void)recover_link(hw, "tx_dma_complete_timeout");
			if (attempt < IR_HW_SW_RETRY_LIMIT) {
				note_sw_retry(hw, attempt + 1u);
				continue;
			}
			hw->tx_fail++;
			return status;
		}

		timeout = (IR_TX_TIMEOUT_US + IR_TX_POLL_US - 1u) / IR_TX_POLL_US;
		while (timeout > 0u) {
			sticky = ir_read(hw, IR_HW_REG_STICKY);
			if ((sticky & IR_HW_STICKY_TX_RETRY_EXH) != 0u) {
				hw->tx_retry_exhausted_count++;
				hw->ack_timeout_count++;
				ir_set_error(hw, "tx_retry_exhausted");
				(void)recover_link(hw, "tx_retry_exhausted");
				if (attempt < IR_HW_SW_RETRY_LIMIT) {
					note_sw_retry(hw, attempt + 1u);
					break;
				}
				hw->tx_fail++;
				return XST_FAILURE;
			}
			if ((sticky & IR_HW_STICKY_TX_DONE) != 0u) {
				hw->tx_ok++;
				hw->tx_done_count++;
				ir_set_error(hw, "");
				return XST_SUCCESS;
			}
			usleep(IR_TX_POLL_US);
			timeout--;
		}

		if (timeout != 0u && attempt < IR_HW_SW_RETRY_LIMIT) {
			continue;
		}

		ir_set_error(hw, "tx_done_timeout");
		hw->tx_done_timeout_count++;
		(void)recover_link(hw, "tx_done_timeout");
		if (attempt < IR_HW_SW_RETRY_LIMIT) {
			note_sw_retry(hw, attempt + 1u);
			continue;
		}
		hw->tx_fail++;
		return XST_FAILURE;
	}

	hw->tx_fail++;
	ir_set_error(hw, "tx_sw_retry_exhausted");
	return XST_FAILURE;
}

int ir_hw_poll_payload(ir_hw_t *hw, uint8_t *payload, size_t capacity, size_t *length)
{
	uint16_t payload_len;
	int rearm_status;
	uint32_t rx_dma_status;

	if (!hw->rx_armed) {
		rearm_status = arm_rx(hw);
		return (rearm_status == XST_SUCCESS) ? IR_HW_POLL_NO_DATA : XST_FAILURE;
	}

	rx_dma_status = dma_status(hw, XAXIDMA_DEVICE_TO_DMA);
	if ((rx_dma_status & XAXIDMA_ERR_ALL_MASK) != 0u) {
		hw->rx_armed = 0;
		hw->s2mm_error_count++;
		(void)recover_link(hw, "rx_dma_error");
		return IR_HW_POLL_NO_DATA;
	}

	if (XAxiDma_Busy(&hw->dma, XAXIDMA_DEVICE_TO_DMA)) {
		return IR_HW_POLL_NO_DATA;
	}

	Xil_DCacheInvalidateRange((UINTPTR)rx_raw, IR_HW_RX_TRANSFER_BYTES);
	hw->rx_armed = 0;
	hw->s2mm_done_count++;

	if (rx_raw[0] != IR_APP_MAGIC0 || rx_raw[1] != IR_APP_MAGIC1 ||
	    rx_raw[2] != IR_APP_MAGIC2 || rx_raw[3] != IR_APP_MAGIC3) {
		hw->rx_bad++;
		hw->rx_app_header_bad_count++;
		ir_set_error(hw, "rx_bad_app_header");
		rearm_status = arm_rx(hw);
		return (rearm_status == XST_SUCCESS) ? IR_HW_POLL_NO_DATA : XST_FAILURE;
	}

	hw->rx_app_header_ok_count++;
	payload_len = rf_get_u16_le(&rx_raw[6]);
	if (payload_len == 0u || payload_len > IR_HW_MAX_PAYLOAD_BYTES ||
	    payload_len > capacity) {
		hw->rx_bad++;
		hw->rx_length_bad_count++;
		ir_set_error(hw, "rx_bad_app_length");
		rearm_status = arm_rx(hw);
		return (rearm_status == XST_SUCCESS) ? IR_HW_POLL_NO_DATA : XST_FAILURE;
	}

	memcpy(payload, &rx_raw[IR_HW_APP_HEADER_BYTES], payload_len);
	*length = payload_len;
	hw->rx_ok++;
	ir_set_error(hw, "");

	rearm_status = arm_rx(hw);

	return IR_HW_POLL_DATA;
}

int ir_hw_inject_rx_synthetic(ir_hw_t *hw, size_t payload_bytes,
                              uint32_t pattern_id, uint16_t seq_base)
{
	uint32_t control;
	int status;

	if (payload_bytes == 0u || payload_bytes > IR_HW_MAX_PAYLOAD_BYTES) {
		ir_set_error(hw, "rx_synth_bad_payload_bytes");
		return XST_FAILURE;
	}

	if (!hw->rx_armed) {
		status = arm_rx(hw);
		if (status != XST_SUCCESS) {
			return status;
		}
	}

	ir_write(hw, IR_HW_REG_STICKY,
	         IR_HW_STICKY_RX_DONE | IR_HW_STICKY_RX_HEADER_ERR |
	         IR_HW_STICKY_RX_PROTOCOL_ERR | IR_HW_STICKY_RX_FRAME_OVF |
	         IR_HW_STICKY_RX_CRC_ERR | IR_HW_STICKY_RX_OVERRUN);
	ir_write(hw, IR_HW_REG_TEST_RX_PAYLOAD_BYTES, (uint32_t)payload_bytes);
	ir_write(hw, IR_HW_REG_TEST_RX_PATTERN_ID, pattern_id);
	ir_write(hw, IR_HW_REG_TEST_RX_SEQ_BASE, (uint32_t)seq_base);
	ir_write(hw, IR_HW_REG_TEST_RX_PACKET_COUNT, 1u);

	control = ((hw->enabled != 0) ? IR_HW_CONTROL_ENABLE : 0u) |
	          IR_HW_CONTROL_TEST_MODE_ENABLE;
	ir_write(hw, IR_HW_REG_CONTROL, control);
	usleep(IR_CONFIG_COMMIT_US);
	ir_write(hw, IR_HW_REG_COMMIT, IR_HW_COMMIT_TEST_RX_INJECT);
	ir_set_error(hw, "");
	return XST_SUCCESS;
}

void ir_hw_disable_test_mode(ir_hw_t *hw)
{
	ir_write(hw, IR_HW_REG_CONTROL,
	         (hw->enabled != 0) ? IR_HW_CONTROL_ENABLE : 0u);
	usleep(IR_CONFIG_COMMIT_US);
}

void ir_hw_get_status(ir_hw_t *hw, ir_hw_status_t *status)
{
	memset(status, 0, sizeof(*status));
	status->status = ir_read(hw, IR_HW_REG_STATUS);
	status->sticky = ir_read(hw, IR_HW_REG_STICKY);
	status->tx_frag_pending = ir_read(hw, IR_HW_REG_TX_FRAG_PENDING);
	status->tx_frag_inflight = ir_read(hw, IR_HW_REG_TX_FRAG_INFLIGHT);
	status->tx_frag_acked = ir_read(hw, IR_HW_REG_TX_FRAG_ACKED);
	status->rx_recv_bitmap = ir_read(hw, IR_HW_REG_RX_RECV_BITMAP);
	status->tx_ok = hw->tx_ok;
	status->tx_fail = hw->tx_fail;
	status->tx_start_count = hw->tx_start_count;
	status->tx_done_count = hw->tx_done_count;
	status->tx_done_timeout_count = hw->tx_done_timeout_count;
	status->tx_retry_count_total = hw->tx_retry_count_total;
	status->tx_retry_exhausted_count = hw->tx_retry_exhausted_count;
	status->ack_timeout_count = hw->ack_timeout_count;
	status->ack_late_count = hw->ack_late_count;
	status->max_retry_seen = hw->max_retry_seen;
	status->first_fail_sent_index = hw->first_fail_sent_index;
	status->first_fail_timestamp = hw->first_fail_timestamp;
	status->first_fail_seq = hw->first_fail_seq;
	status->first_fail_pre_sticky = hw->first_fail_pre_sticky;
	status->first_fail_pre_phy0 = hw->first_fail_pre_phy0;
	status->first_fail_pre_tx_lane = hw->first_fail_pre_tx_lane;
	status->first_fail_post_sticky = hw->first_fail_post_sticky;
	status->first_fail_post_phy0 = hw->first_fail_post_phy0;
	status->rx_ok = hw->rx_ok;
	status->rx_bad = hw->rx_bad;
	status->tx_lane_mask = hw->lane_mask;
	status->rx_lane_mask = hw->rx_lane_mask;
	status->tx_lane_count = ir_read(hw, IR_HW_REG_TX_LANE_COUNT);
	status->rx_lane_good_count = ir_read(hw, IR_HW_REG_RX_LANE_GOOD_COUNT);
	status->rx_lane_crc_count = ir_read(hw, IR_HW_REG_RX_LANE_CRC_COUNT);
	status->rx_lane_err_count = ir_read(hw, IR_HW_REG_RX_LANE_ERR_COUNT);
	status->phy_lane0_dbg = ir_read(hw, IR_HW_REG_PHY_LANE0_DBG);
	status->obs_signature = ir_read_obs(hw, IR_HW_OBS_SIG);
	status->core_rx_tvalid_count = ir_read_obs(hw, IR_HW_OBS_CORE_TVALID);
	status->core_rx_tready_count = ir_read_obs(hw, IR_HW_OBS_CORE_TREADY);
	status->core_rx_tlast_count = ir_read_obs(hw, IR_HW_OBS_CORE_TLAST);
	status->core_rx_byte_count = ir_read_obs(hw, IR_HW_OBS_CORE_BYTES);
	status->synth_rx_tvalid_count = ir_read_obs(hw, IR_HW_OBS_SYNTH_TVALID);
	status->synth_rx_tlast_count = ir_read_obs(hw, IR_HW_OBS_SYNTH_TLAST);
	status->synth_rx_byte_count = ir_read_obs(hw, IR_HW_OBS_SYNTH_BYTES);
	status->mux_rx_tvalid_count = ir_read_obs(hw, IR_HW_OBS_MUX_TVALID);
	status->mux_rx_tlast_count = ir_read_obs(hw, IR_HW_OBS_MUX_TLAST);
	status->mux_rx_byte_count = ir_read_obs(hw, IR_HW_OBS_MUX_BYTES);
	status->s2mm_arm_count = hw->s2mm_arm_count;
	status->s2mm_done_count = hw->s2mm_done_count;
	status->s2mm_error_count = hw->s2mm_error_count;
	status->s2mm_timeout_count = hw->s2mm_timeout_count;
	status->rx_app_header_ok_count = hw->rx_app_header_ok_count;
	status->rx_app_header_bad_count = hw->rx_app_header_bad_count;
	status->rx_length_bad_count = hw->rx_length_bad_count;
	status->recovery_count = hw->recovery_count;
	status->pre_recover_status = hw->pre_recover_status;
	status->pre_recover_sticky = hw->pre_recover_sticky;
	status->pre_recover_tx_lane_count = hw->pre_recover_tx_lane_count;
	status->pre_recover_rx_lane_err_count = hw->pre_recover_rx_lane_err_count;
	status->pre_recover_phy_lane0_dbg = hw->pre_recover_phy_lane0_dbg;
	status->pre_recover_dma_tx_status = hw->pre_recover_dma_tx_status;
	status->pre_recover_dma_rx_status = hw->pre_recover_dma_rx_status;
	status->dma_tx_status = dma_status(hw, XAXIDMA_DMA_TO_DEVICE);
	status->dma_rx_status = dma_status(hw, XAXIDMA_DEVICE_TO_DMA);
	status->rx_armed = (uint32_t)((hw->rx_armed != 0) ? 1u : 0u);
}

void ir_hw_note_rx_timeout(ir_hw_t *hw)
{
	hw->s2mm_timeout_count++;
}

const char *ir_hw_last_error(const ir_hw_t *hw)
{
	if (hw->last_error == NULL || hw->last_error[0] == '\0') {
		return "none";
	}
	return hw->last_error;
}
