#include "tcp_bridge.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "lwip/err.h"
#include "lwip/pbuf.h"
#include "lwip/tcp.h"
#include "xil_printf.h"
#include "xstatus.h"

#include "rf_protocol.h"

#define TCP_BRIDGE_RX_BUFFER_BYTES 1024u
#define TCP_BRIDGE_TX_BUFFER_BYTES (RF_PROTO_HEADER_BYTES + RF_PROTO_MAX_PAYLOAD)

typedef struct {
	struct tcp_pcb *listen_pcb;
	struct tcp_pcb *client_pcb;
	ir_hw_t *hw;
	uint8_t rx_buf[TCP_BRIDGE_RX_BUFFER_BYTES];
	size_t rx_len;
	uint16_t tx_seq;
	uint16_t synth_seq;
	uint32_t mode;
	uint8_t ir_rx_buf[IR_HW_MAX_PAYLOAD_BYTES];
} tcp_bridge_state_t;

static tcp_bridge_state_t g_bridge;
static uint8_t g_tx_frame[TCP_BRIDGE_TX_BUFFER_BYTES];

static err_t bridge_close_pcb(struct tcp_pcb *pcb)
{
	err_t close_err;

	if (pcb == NULL) {
		return ERR_OK;
	}

	tcp_arg(pcb, NULL);
	tcp_recv(pcb, NULL);
	tcp_err(pcb, NULL);
	close_err = tcp_close(pcb);
	if (close_err != ERR_OK) {
		tcp_abort(pcb);
		return ERR_ABRT;
	}
	return ERR_OK;
}

static err_t bridge_close_client(void)
{
	if (g_bridge.client_pcb != NULL) {
		struct tcp_pcb *pcb = g_bridge.client_pcb;
		g_bridge.client_pcb = NULL;
		g_bridge.rx_len = 0u;
		return bridge_close_pcb(pcb);
	}
	g_bridge.rx_len = 0u;
	return ERR_OK;
}

static err_t bridge_send_frame(uint8_t type, uint16_t seq,
                               const uint8_t *payload, size_t length)
{
	err_t err;

	if (g_bridge.client_pcb == NULL) {
		return ERR_CLSD;
	}
	if (length > RF_PROTO_MAX_PAYLOAD) {
		return ERR_ARG;
	}
	if (tcp_sndbuf(g_bridge.client_pcb) < (RF_PROTO_HEADER_BYTES + length)) {
		return ERR_MEM;
	}

	g_tx_frame[0] = RF_PROTO_MAGIC0;
	g_tx_frame[1] = RF_PROTO_MAGIC1;
	g_tx_frame[2] = RF_PROTO_MAGIC2;
	g_tx_frame[3] = RF_PROTO_MAGIC3;
	g_tx_frame[4] = RF_PROTO_VERSION;
	g_tx_frame[5] = type;
	rf_put_u16_le(&g_tx_frame[6], seq);
	rf_put_u32_le(&g_tx_frame[8], (uint32_t)length);

	if (length > 0u && payload != NULL) {
		memcpy(&g_tx_frame[RF_PROTO_HEADER_BYTES], payload, length);
	}

	err = tcp_write(g_bridge.client_pcb, g_tx_frame,
	                (u16_t)(RF_PROTO_HEADER_BYTES + length),
	                TCP_WRITE_FLAG_COPY);
	if (err == ERR_OK) {
		(void)tcp_output(g_bridge.client_pcb);
	}
	return err;
}

static void bridge_send_text(uint8_t type, uint16_t seq, const char *text)
{
	(void)bridge_send_frame(type, seq, (const uint8_t *)text, strlen(text));
}

static const char *bridge_mode_name(uint32_t mode)
{
	switch (mode) {
	case RF_MODE_NETWORK_MEMORY_ECHO:
		return "network_memory_echo";
	case RF_MODE_PSPL_SYNTH_LOOPBACK:
		return "pspl_synth_loopback";
	case RF_MODE_IR_PHYSICAL:
		return "ir_physical";
	default:
		return "unknown";
	}
}

static int bridge_mode_is_supported(uint32_t mode)
{
	return mode == RF_MODE_NETWORK_MEMORY_ECHO ||
	       mode == RF_MODE_PSPL_SYNTH_LOOPBACK;
}

static int bridge_set_network_mode(uint32_t mode)
{
	int status;

	if (!bridge_mode_is_supported(mode)) {
		return XST_FAILURE;
	}

	status = ir_hw_configure(g_bridge.hw, RF_CONFIG_ENABLE, 0u, 0u, 0u, 0u);
	if (status != XST_SUCCESS) {
		return status;
	}
	g_bridge.mode = mode;
	return XST_SUCCESS;
}

static int parse_positive_decimal(const char *text, uint32_t *value)
{
	uint32_t accum = 0u;
	const char *cursor = text;

	if (text == NULL || value == NULL || *text == '\0') {
		return 0;
	}
	while (*cursor != '\0') {
		if (*cursor < '0' || *cursor > '9') {
			return 0;
		}
		accum = (accum * 10u) + (uint32_t)(*cursor - '0');
		cursor++;
	}
	if (accum == 0u || accum > RF_PROTO_MAX_PAYLOAD) {
		return 0;
	}
	*value = accum;
	return 1;
}

static void bridge_send_status(uint16_t seq)
{
	ir_hw_status_t status;
	uint8_t payload[64];

	ir_hw_get_status(g_bridge.hw, &status);
	rf_put_u32_le(&payload[0], status.status);
	rf_put_u32_le(&payload[4], status.sticky);
	rf_put_u32_le(&payload[8], status.tx_frag_pending);
	rf_put_u32_le(&payload[12], status.tx_frag_inflight);
	rf_put_u32_le(&payload[16], status.tx_frag_acked);
	rf_put_u32_le(&payload[20], status.rx_recv_bitmap);
	rf_put_u32_le(&payload[24], status.tx_ok);
	rf_put_u32_le(&payload[28], status.tx_fail);
	rf_put_u32_le(&payload[32], status.rx_ok);
	rf_put_u32_le(&payload[36], status.rx_bad);
	rf_put_u32_le(&payload[40], status.tx_lane_mask);
	rf_put_u32_le(&payload[44], status.rx_lane_mask);
	rf_put_u32_le(&payload[48], status.tx_lane_count);
	rf_put_u32_le(&payload[52], status.rx_lane_good_count);
	rf_put_u32_le(&payload[56], status.rx_lane_crc_count);
	rf_put_u32_le(&payload[60], status.rx_lane_err_count);

	(void)bridge_send_frame(RF_FRAME_STATUS_RSP, seq, payload, sizeof(payload));
}

static void bridge_handle_command(uint16_t seq, const uint8_t *payload, size_t length)
{
	char command[RF_PROTO_MAX_PAYLOAD + 1u];
	const char *text;
	uint32_t payload_bytes;
	int status;

	if (length == 0u || length > RF_PROTO_MAX_PAYLOAD) {
		bridge_send_text(RF_FRAME_ERROR, seq, "ERR_BAD_ARG");
		return;
	}

	memcpy(command, payload, length);
	command[length] = '\0';
	while (length > 0u &&
	       (command[length - 1u] == '\r' ||
	        command[length - 1u] == '\n' ||
	        command[length - 1u] == ' ' ||
	        command[length - 1u] == '\t')) {
		command[length - 1u] = '\0';
		length--;
	}
	text = command;
	while (*text == ' ' || *text == '\t') {
		text++;
	}
	if (*text == '\0') {
		bridge_send_text(RF_FRAME_ERROR, seq, "ERR_BAD_ARG");
		return;
	}

	if (strcmp(text, "PING") == 0) {
		bridge_send_text(RF_FRAME_ACK, seq, "PONG");
	} else if (strcmp(text, "GET_VERSION") == 0) {
		bridge_send_text(RF_FRAME_ACK, seq, "VERSION 1");
	} else if (strcmp(text, "GET_BUILD_ID") == 0 ||
	           strcmp(text, "READ build_id") == 0) {
		bridge_send_text(RF_FRAME_ACK, seq, "BUILD_ID rf_comm_ps_bridge_n03_network_first");
	} else if (strcmp(text, "STATUS") == 0 ||
	           strcmp(text, "READ counters") == 0 ||
	           strcmp(text, "READ pspl_status") == 0) {
		bridge_send_status(seq);
	} else if (strcmp(text, "READ network_status") == 0) {
		bridge_send_text(RF_FRAME_ACK, seq, "network_status tcp_connected=1 port=5001");
	} else if (strncmp(text, "CONFIG payload_bytes ", 21u) == 0) {
		if (!parse_positive_decimal(text + 21u, &payload_bytes)) {
			bridge_send_text(RF_FRAME_ERROR, seq, "ERR_BAD_ARG");
			return;
		}
		bridge_send_text(RF_FRAME_ACK, seq, "payload_bytes_accepted");
	} else if (strcmp(text, "CONFIG mode network_memory_echo") == 0) {
		status = bridge_set_network_mode(RF_MODE_NETWORK_MEMORY_ECHO);
		if (status == XST_SUCCESS) {
			bridge_send_text(RF_FRAME_ACK, seq, bridge_mode_name(g_bridge.mode));
		} else {
			bridge_send_text(RF_FRAME_ERROR, seq, ir_hw_last_error(g_bridge.hw));
		}
	} else if (strcmp(text, "CONFIG mode pspl_synth_loopback") == 0) {
		status = bridge_set_network_mode(RF_MODE_PSPL_SYNTH_LOOPBACK);
		if (status == XST_SUCCESS) {
			bridge_send_text(RF_FRAME_ACK, seq, bridge_mode_name(g_bridge.mode));
		} else {
			bridge_send_text(RF_FRAME_ERROR, seq, ir_hw_last_error(g_bridge.hw));
		}
	} else if (strcmp(text, "CONFIG mode ir_physical") == 0 ||
	           strcmp(text, "START ir_tx") == 0 ||
	           strcmp(text, "START 2lane") == 0 ||
	           strcmp(text, "START ir_physical") == 0) {
		bridge_send_text(RF_FRAME_ERROR, seq,
		                 "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE");
	} else if (strcmp(text, "CLEAR") == 0 ||
	           strcmp(text, "CLEAR counters") == 0 ||
	           strcmp(text, "CLEAR sticky") == 0) {
		ir_hw_clear_sticky(g_bridge.hw);
		bridge_send_text(RF_FRAME_ACK, seq, "cleared");
	} else if (strcmp(text, "START") == 0) {
		status = bridge_set_network_mode(g_bridge.mode);
		if (status == XST_SUCCESS) {
			bridge_send_text(RF_FRAME_ACK, seq, "started_network_mode");
		} else {
			bridge_send_text(RF_FRAME_ERROR, seq, ir_hw_last_error(g_bridge.hw));
		}
	} else if (strcmp(text, "STOP") == 0) {
		(void)ir_hw_configure(g_bridge.hw, RF_CONFIG_ENABLE, 0u, 0u, 0u, 0u);
		ir_hw_disable_test_mode(g_bridge.hw);
		bridge_send_text(RF_FRAME_ACK, seq, "stopped");
	} else if (strcmp(text, "SHUTDOWN_SAFE") == 0) {
		(void)ir_hw_configure(g_bridge.hw, RF_CONFIG_ENABLE, 0u, 0u, 0u, 0u);
		ir_hw_disable_test_mode(g_bridge.hw);
		bridge_send_text(RF_FRAME_ACK, seq, "shutdown_safe");
	} else {
		bridge_send_text(RF_FRAME_ERROR, seq, "ERR_UNKNOWN_CMD");
	}
}

static void bridge_handle_frame(uint8_t type, uint16_t seq,
                                const uint8_t *payload, size_t length)
{
	int status;
	uint8_t mask;
	uint8_t ir_mask;
	uint32_t requested_mode;

	switch (type) {
	case RF_FRAME_HELLO:
		bridge_send_text(RF_FRAME_ACK, seq, "rf_comm_ps_bridge_n03_network_first");
		break;
	case RF_FRAME_STATUS_REQ:
		bridge_send_status(seq);
		break;
	case RF_FRAME_CLEAR:
		ir_hw_clear_sticky(g_bridge.hw);
		bridge_send_text(RF_FRAME_ACK, seq, "cleared");
		break;
	case RF_FRAME_CONFIG:
		if (length != 8u && length != 12u && length != 16u) {
			bridge_send_text(RF_FRAME_ERROR, seq, "bad_config_payload");
			break;
		}
		mask = payload[0];
		if ((mask & ~(RF_CONFIG_ENABLE | RF_CONFIG_SESSION |
		              RF_CONFIG_LANE_MASK | RF_CONFIG_RX_LANE_MASK |
		              RF_CONFIG_MODE)) != 0u) {
			bridge_send_text(RF_FRAME_ERROR, seq, "bad_config_mask");
			break;
		}
		if ((mask & RF_CONFIG_RX_LANE_MASK) != 0u && length < 12u) {
			bridge_send_text(RF_FRAME_ERROR, seq, "bad_config_payload");
			break;
		}
		if ((mask & RF_CONFIG_MODE) != 0u && length < 16u) {
			bridge_send_text(RF_FRAME_ERROR, seq, "bad_config_payload");
			break;
		}
		requested_mode = ((mask & RF_CONFIG_MODE) != 0u) ?
		                 rf_get_u32_le(&payload[12]) : g_bridge.mode;
		if (requested_mode == RF_MODE_IR_PHYSICAL) {
			bridge_send_text(RF_FRAME_ERROR, seq,
			                 "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE");
			break;
		}
		if (!bridge_mode_is_supported(requested_mode)) {
			bridge_send_text(RF_FRAME_ERROR, seq, "bad_config_mode");
			break;
		}

		ir_mask = mask & (RF_CONFIG_ENABLE | RF_CONFIG_SESSION |
		                  RF_CONFIG_LANE_MASK | RF_CONFIG_RX_LANE_MASK);
		if (ir_mask != 0u) {
			/*
			 * N03 network-first modes must not enable TFDU traffic. Preserve
			 * session/lane observability, but force the physical IR control bit off.
			 */
			status = ir_hw_configure(g_bridge.hw, ir_mask, 0u,
			                         rf_get_u16_le(&payload[2]),
			                         rf_get_u32_le(&payload[4]),
			                         (length >= 12u) ? rf_get_u32_le(&payload[8]) : rf_get_u32_le(&payload[4]));
			if (status != XST_SUCCESS) {
				bridge_send_text(RF_FRAME_ERROR, seq, ir_hw_last_error(g_bridge.hw));
				break;
			}
		}
		g_bridge.mode = requested_mode;
		bridge_send_text(RF_FRAME_ACK, seq, bridge_mode_name(g_bridge.mode));
		break;
	case RF_FRAME_COMMAND:
		bridge_handle_command(seq, payload, length);
		break;
	case RF_FRAME_TX_DATA:
		if (length == 0u) {
			bridge_send_text(RF_FRAME_ERROR, seq, "tx_invalid_payload");
			break;
		}
		if (g_bridge.mode == RF_MODE_NETWORK_MEMORY_ECHO) {
			bridge_send_text(RF_FRAME_ACK, seq, "memory_echo_done");
			(void)bridge_send_frame(RF_FRAME_RX_DATA, g_bridge.tx_seq++,
			                        payload, length);
		} else if (g_bridge.mode == RF_MODE_PSPL_SYNTH_LOOPBACK) {
			status = ir_hw_inject_rx_synthetic(g_bridge.hw, length, 2u,
			                                  g_bridge.synth_seq++);
			if (status == XST_SUCCESS) {
				bridge_send_text(RF_FRAME_ACK, seq, "pspl_synth_started");
			} else {
				bridge_send_text(RF_FRAME_ERROR, seq, ir_hw_last_error(g_bridge.hw));
			}
		} else {
			bridge_send_text(RF_FRAME_ERROR, seq,
			                 "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE");
		}
		break;
	default:
		bridge_send_text(RF_FRAME_ERROR, seq, "unknown_frame_type");
		break;
	}
}

static void bridge_parse_rx(void)
{
	size_t pos = 0u;
	int desync_reported = 0;

	while (g_bridge.rx_len - pos >= RF_PROTO_HEADER_BYTES) {
		uint32_t length;
		uint16_t seq;
		uint8_t type;

		if (g_bridge.rx_buf[pos] != RF_PROTO_MAGIC0 ||
		    g_bridge.rx_buf[pos + 1u] != RF_PROTO_MAGIC1 ||
		    g_bridge.rx_buf[pos + 2u] != RF_PROTO_MAGIC2 ||
		    g_bridge.rx_buf[pos + 3u] != RF_PROTO_MAGIC3) {
			if (desync_reported == 0) {
				bridge_send_text(RF_FRAME_ERROR, 0u, "bad_magic");
				desync_reported = 1;
			}
			pos++;
			continue;
		}

		seq = rf_get_u16_le(&g_bridge.rx_buf[pos + 6u]);
		length = rf_get_u32_le(&g_bridge.rx_buf[pos + 8u]);

		if (g_bridge.rx_buf[pos + 4u] != RF_PROTO_VERSION) {
			bridge_send_text(RF_FRAME_ERROR, seq, "unsupported_version");
			g_bridge.rx_len = 0u;
			return;
		}

		type = g_bridge.rx_buf[pos + 5u];
		if (length > RF_PROTO_MAX_PAYLOAD) {
			bridge_send_text(RF_FRAME_ERROR, seq, "payload_too_large");
			g_bridge.rx_len = 0u;
			return;
		}

		if (g_bridge.rx_len - pos < RF_PROTO_HEADER_BYTES + length) {
			break;
		}

		bridge_handle_frame(type, seq,
		                    &g_bridge.rx_buf[pos + RF_PROTO_HEADER_BYTES],
		                    length);
		pos += RF_PROTO_HEADER_BYTES + length;
	}

	if (pos > 0u) {
		memmove(g_bridge.rx_buf, &g_bridge.rx_buf[pos], g_bridge.rx_len - pos);
		g_bridge.rx_len -= pos;
	}
}

static err_t bridge_recv(void *arg, struct tcp_pcb *pcb, struct pbuf *p, err_t err)
{
	struct pbuf *q;
	(void)arg;

	if (err != ERR_OK || p == NULL) {
		if (p != NULL) {
			pbuf_free(p);
		}
		return bridge_close_client();
	}

	tcp_recved(pcb, p->tot_len);

	for (q = p; q != NULL; q = q->next) {
		if ((g_bridge.rx_len + q->len) > sizeof(g_bridge.rx_buf)) {
			g_bridge.rx_len = 0u;
			bridge_send_text(RF_FRAME_ERROR, 0u, "tcp_rx_overflow");
			break;
		}
		memcpy(&g_bridge.rx_buf[g_bridge.rx_len], q->payload, q->len);
		g_bridge.rx_len += q->len;
	}

	pbuf_free(p);
	bridge_parse_rx();
	return ERR_OK;
}

static void bridge_err(void *arg, err_t err)
{
	(void)arg;
	(void)err;
	g_bridge.client_pcb = NULL;
	g_bridge.rx_len = 0u;
}

static err_t bridge_accept(void *arg, struct tcp_pcb *new_pcb, err_t err)
{
	(void)arg;

	if (err != ERR_OK || new_pcb == NULL) {
		return ERR_VAL;
	}

	if (g_bridge.client_pcb != NULL) {
		return bridge_close_pcb(new_pcb);
	}

	g_bridge.client_pcb = new_pcb;
	g_bridge.rx_len = 0u;
	tcp_arg(new_pcb, &g_bridge);
	tcp_recv(new_pcb, bridge_recv);
	tcp_err(new_pcb, bridge_err);
	tcp_nagle_disable(new_pcb);
	bridge_send_text(RF_FRAME_ACK, 0u, "connected");
	return ERR_OK;
}

int tcp_bridge_start(ir_hw_t *hw, unsigned short port)
{
	err_t err;
	struct tcp_pcb *pcb;

	memset(&g_bridge, 0, sizeof(g_bridge));
	g_bridge.hw = hw;
	g_bridge.tx_seq = 1u;
	g_bridge.synth_seq = 1u;
	g_bridge.mode = RF_MODE_NETWORK_MEMORY_ECHO;
	(void)ir_hw_configure(g_bridge.hw, RF_CONFIG_ENABLE, 0u, 0u, 0u, 0u);

	pcb = tcp_new();
	if (pcb == NULL) {
		return XST_FAILURE;
	}

	err = tcp_bind(pcb, IP_ADDR_ANY, port);
	if (err != ERR_OK) {
		tcp_close(pcb);
		return XST_FAILURE;
	}

	g_bridge.listen_pcb = tcp_listen(pcb);
	if (g_bridge.listen_pcb == NULL) {
		tcp_close(pcb);
		return XST_FAILURE;
	}

	tcp_accept(g_bridge.listen_pcb, bridge_accept);
	xil_printf("RF TCP bridge listening on port %u\r\n", port);
	return XST_SUCCESS;
}

void tcp_bridge_poll(void)
{
	size_t length = 0u;
	int status;

	if (g_bridge.mode != RF_MODE_PSPL_SYNTH_LOOPBACK) {
		return;
	}

	status = ir_hw_poll_payload(g_bridge.hw, g_bridge.ir_rx_buf,
	                            sizeof(g_bridge.ir_rx_buf), &length);
	if (status == IR_HW_POLL_DATA && g_bridge.client_pcb != NULL) {
		(void)bridge_send_frame(RF_FRAME_RX_DATA, g_bridge.tx_seq++,
		                        g_bridge.ir_rx_buf, length);
		ir_hw_disable_test_mode(g_bridge.hw);
	} else if (status == XST_FAILURE && g_bridge.client_pcb != NULL) {
		bridge_send_text(RF_FRAME_ERROR, g_bridge.tx_seq++,
		                 ir_hw_last_error(g_bridge.hw));
		ir_hw_disable_test_mode(g_bridge.hw);
	}
}
