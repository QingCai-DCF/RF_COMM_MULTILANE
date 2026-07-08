#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "sleep.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xstatus.h"
#include "xtime_l.h"
#include "xuartps_hw.h"

#include "ir_hw.h"
#include "rf_protocol.h"

#ifndef PSPS_TX_ONLY
#define PSPS_TX_ONLY              0u
#endif
#ifndef PSPS_TDM_BIDIR
#define PSPS_TDM_BIDIR            0u
#endif
#ifndef PSPS_RX_ONLY
#define PSPS_RX_ONLY              0u
#endif
#ifndef PSPS_A2B_RX_SUMMARY
#define PSPS_A2B_RX_SUMMARY       0u
#endif
#ifndef PSPS_PAYLOAD_BYTES
#if (PSPS_TDM_BIDIR != 0u) || (PSPS_RX_ONLY != 0u)
#define PSPS_PAYLOAD_BYTES        247u
#else
#define PSPS_PAYLOAD_BYTES        16u
#endif
#endif
#if PSPS_PAYLOAD_BYTES < 16u
#error "PSPS_PAYLOAD_BYTES must be at least 16u for make_payload()"
#endif
#define PSPS_RX_TIMEOUT_US        500000u
#ifndef PSPS_POLL_SLEEP_US
#define PSPS_POLL_SLEEP_US        100u
#endif
#ifndef PSPS_INTER_PACKET_US
#define PSPS_INTER_PACKET_US      1000u
#endif
#ifndef PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY
#define PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY 0u
#endif
#ifndef PSPS_IR_ROUNDTRIP_RETRY_GAP_US
#define PSPS_IR_ROUNDTRIP_RETRY_GAP_US 2000u
#endif
#ifndef PSPS_STATS_INTERVAL_US
#define PSPS_STATS_INTERVAL_US    1000000u
#endif
#ifndef PSPS_STAGE_SECONDS
#define PSPS_STAGE_SECONDS        30u
#endif
#ifndef PSPS_RUN_ONCE
#define PSPS_RUN_ONCE             0u
#endif
#ifndef PSPS_WARMUP_STAGES
#define PSPS_WARMUP_STAGES        0u
#endif
#ifndef PSPS_MAX_OUTSTANDING
#define PSPS_MAX_OUTSTANDING      0u
#endif
#ifndef PSPS_WINDOW_START_GAP_US
#define PSPS_WINDOW_START_GAP_US  0u
#endif
#ifndef PSPS_2LANE_ONLY
#define PSPS_2LANE_ONLY           0u
#endif
#ifndef PSPS_STAGE_LANE_MASK
#if PSPS_2LANE_ONLY != 0u
#define PSPS_STAGE_LANE_MASK      0x00000003u
#else
#define PSPS_STAGE_LANE_MASK      0x00000001u
#endif
#endif
#define PSPS_SESSION_BASE         0x2200u
#ifndef PSPS_STAGE_SESSION_ID
#define PSPS_STAGE_SESSION_ID     (PSPS_SESSION_BASE + (PSPS_STAGE_LANE_MASK & 0x00ffu))
#endif
#ifndef PSPS_PAYLOAD_LANE_MASK
#define PSPS_PAYLOAD_LANE_MASK    PSPS_STAGE_LANE_MASK
#endif
#ifndef PSPS_RX_LANE_MASK
#define PSPS_RX_LANE_MASK         PSPS_STAGE_LANE_MASK
#endif
#ifndef PSPS_UART_OPERATOR
#define PSPS_UART_OPERATOR        0u
#endif
#ifndef PSPS_OPERATOR_COMMAND_BYTES
#define PSPS_OPERATOR_COMMAND_BYTES 128u
#endif
#ifndef PSPS_OPERATOR_MAX_STAGE_SECONDS
#define PSPS_OPERATOR_MAX_STAGE_SECONDS 600u
#endif

typedef struct {
	const char *name;
	uint32_t lane_mask;
	uint16_t session_id;
} test_stage_t;

typedef struct {
	uint32_t sent;
	uint32_t tx_fail;
	uint32_t rx_ok;
	uint32_t rx_timeout;
	uint32_t rx_bad;
	uint32_t rx_mismatch;
	uint32_t verified_bytes;
} counters_t;

#define B_RX_SUMMARY_MAGIC              0xebu
#define B_RX_FLAG_RX_GOOD_SEEN          (1u << 0)
#define B_RX_FLAG_RX_BAD_SEEN           (1u << 1)
#define B_RX_FLAG_RX_ERROR              (1u << 2)
#define B_RX_FLAG_DATA_TX_START         (1u << 3)
#define B_RX_FLAG_TX_ACTIVITY           (1u << 4)

typedef struct {
	uint32_t flags;
	uint32_t rx_good;
} b_rx_summary_t;

static ir_hw_t g_ir;
static uint8_t g_tx_payload[PSPS_PAYLOAD_BYTES] __attribute__((aligned(64)));
static uint8_t g_rx_payload[IR_HW_MAX_PAYLOAD_BYTES] __attribute__((aligned(64)));

static const test_stage_t g_stages[] = {
	{ "lane-mask", PSPS_STAGE_LANE_MASK, (uint16_t)PSPS_STAGE_SESSION_ID },
};

static void merge_counters(counters_t *dst, const counters_t *src);

static uint64_t now_ticks(void)
{
	XTime t;
	XTime_GetTime(&t);
	return (uint64_t)t;
}

static uint32_t ticks_to_us(uint64_t ticks)
{
	return (uint32_t)((ticks * 1000000ull) / (uint64_t)COUNTS_PER_SECOND);
}

static uint32_t elapsed_us(uint64_t start, uint64_t end)
{
	return ticks_to_us(end - start);
}

static uint32_t fixed_mbps_x1000(uint32_t bytes, uint32_t elapsed)
{
	uint64_t bits;

	if (elapsed == 0u) {
		return 0u;
	}

	bits = (uint64_t)bytes * 8ull;
	return (uint32_t)((bits * 1000ull) / (uint64_t)elapsed);
}

static uint32_t loss_permille(const counters_t *c)
{
	uint32_t lost;

	if (c->sent == 0u) {
		return 0u;
	}

	lost = c->tx_fail + c->rx_timeout + c->rx_bad + c->rx_mismatch;
	return (uint32_t)(((uint64_t)lost * 1000ull) / (uint64_t)c->sent);
}

static uint32_t counter_delta(uint32_t now, uint32_t before)
{
	return now - before;
}

static void reset_counters(counters_t *c)
{
	memset(c, 0, sizeof(*c));
}

static void make_payload(uint32_t seq, const test_stage_t *stage)
{
	uint32_t i;
	uint32_t payload_lane_mask = PSPS_PAYLOAD_LANE_MASK;

	g_tx_payload[0] = 'P';
	g_tx_payload[1] = 'S';
	g_tx_payload[2] = 'P';
	g_tx_payload[3] = 'S';
	rf_put_u32_le(&g_tx_payload[4], seq);
	rf_put_u32_le(&g_tx_payload[8], payload_lane_mask);
	rf_put_u32_le(&g_tx_payload[12], ~seq);

	for (i = 16u; i < PSPS_PAYLOAD_BYTES; i++) {
		g_tx_payload[i] = (uint8_t)(seq + (i * 17u) + payload_lane_mask);
	}
}

static int payload_matches(size_t length)
{
	if (length != PSPS_PAYLOAD_BYTES) {
		return 0;
	}

	return memcmp(g_tx_payload, g_rx_payload, PSPS_PAYLOAD_BYTES) == 0;
}

static uint8_t b2a_expected_byte(uint16_t seq, uint32_t idx)
{
	switch (idx) {
	case 0u:  return (uint8_t)'B';
	case 1u:  return (uint8_t)'2';
	case 2u:  return (uint8_t)'A';
	case 3u:  return (uint8_t)'!';
	case 4u:  return (uint8_t)(seq & 0xffu);
	case 5u:  return (uint8_t)((seq >> 8) & 0xffu);
	case 6u:  return 0x01u;
	case 7u:  return 0x00u;
	case 8u:  return (uint8_t)(~seq & 0xffu);
	case 9u:  return (uint8_t)((~seq >> 8) & 0xffu);
	case 10u: return 0xfeu;
	case 11u: return 0xffu;
	case 12u: return 0x42u;
	case 13u: return 0x44u;
	case 14u: return 0x4du;
	case 15u: return 0x31u;
	default:
		return (uint8_t)((seq & 0xffu) + (idx * 19u) + 0xb0u);
	}
}

static int b2a_payload_matches(size_t length)
{
	uint16_t seq;
	uint32_t i;

	if (length != PSPS_PAYLOAD_BYTES || length < 16u) {
		return 0;
	}

	seq = (uint16_t)g_rx_payload[4] | ((uint16_t)g_rx_payload[5] << 8);
	for (i = 0u; i < PSPS_PAYLOAD_BYTES; i++) {
		if (g_rx_payload[i] != b2a_expected_byte(seq, i)) {
			return 0;
		}
	}

	return 1;
}

static void print_mbps(uint32_t mbps_x1000)
{
	xil_printf("%lu.%03lu",
	           (unsigned long)(mbps_x1000 / 1000u),
	           (unsigned long)(mbps_x1000 % 1000u));
}

static void print_loss(uint32_t permille)
{
	xil_printf("%lu.%lu",
	           (unsigned long)(permille / 10u),
	           (unsigned long)(permille % 10u));
}

static void print_status_regs(const ir_hw_status_t *s)
{
	xil_printf(" status=0x%08lx sticky=0x%08lx tx_lane=0x%08lx rx_good=0x%08lx rx_crc=0x%08lx rx_err=0x%08lx phy0=0x%08lx rec=%lu",
	           (unsigned long)s->status,
	           (unsigned long)s->sticky,
	           (unsigned long)s->tx_lane_count,
	           (unsigned long)s->rx_lane_good_count,
	           (unsigned long)s->rx_lane_crc_count,
	           (unsigned long)s->rx_lane_err_count,
	           (unsigned long)s->phy_lane0_dbg,
	           (unsigned long)s->recovery_count);
	xil_printf(" pre_status=0x%08lx pre_sticky=0x%08lx pre_tx_lane=0x%08lx pre_rx_err=0x%08lx pre_phy0=0x%08lx",
	           (unsigned long)s->pre_recover_status,
	           (unsigned long)s->pre_recover_sticky,
	           (unsigned long)s->pre_recover_tx_lane_count,
	           (unsigned long)s->pre_recover_rx_lane_err_count,
	           (unsigned long)s->pre_recover_phy_lane0_dbg);
	xil_printf(" pre_dma_tx=0x%08lx pre_dma_rx=0x%08lx",
	           (unsigned long)s->pre_recover_dma_tx_status,
	           (unsigned long)s->pre_recover_dma_rx_status);
	xil_printf(" txp=0x%08lx txi=0x%08lx txa=0x%08lx rxb=0x%08lx",
	           (unsigned long)s->tx_frag_pending,
	           (unsigned long)s->tx_frag_inflight,
	           (unsigned long)s->tx_frag_acked,
	           (unsigned long)s->rx_recv_bitmap);
	xil_printf(" dma_tx=0x%08lx dma_rx=0x%08lx armed=%lu",
	           (unsigned long)s->dma_tx_status,
	           (unsigned long)s->dma_rx_status,
	           (unsigned long)s->rx_armed);
}

static int decode_b_rx_summary(uint32_t summary, b_rx_summary_t *decoded)
{
	if (((summary >> 24) & 0xffu) != B_RX_SUMMARY_MAGIC) {
		return 0;
	}

	decoded->flags = (summary >> 16) & 0xffu;
	decoded->rx_good = summary & 0xffffu;
	return 1;
}

static uint32_t counter16_delta(uint32_t now, uint32_t before)
{
	now &= 0xffffu;
	before &= 0xffffu;
	if (now >= before) {
		return now - before;
	}
	return (now + 65536u) - before;
}

static void print_b_rx_summary_line(const char *tag,
                                    const test_stage_t *stage,
                                    const counters_t *total,
                                    const counters_t *window,
                                    uint32_t window_us,
                                    uint32_t b_summary,
                                    int b_summary_valid)
{
	ir_hw_status_t status;
	b_rx_summary_t decoded;
	uint32_t rate_x1000;
	uint32_t b_flags;
	uint32_t b_rx_good_count;
	uint32_t b_rx_bad_seen;
	uint32_t b_rx_error;
	uint32_t b_tx_start;
	uint32_t b_tx_activity;

	ir_hw_get_status(&g_ir, &status);
	rate_x1000 = fixed_mbps_x1000(window->verified_bytes, window_us);
	b_flags = 0u;
	b_rx_good_count = 0u;
	b_rx_bad_seen = 0u;
	b_rx_error = 0u;
	b_tx_start = 0u;
	b_tx_activity = 0u;
	if (b_summary_valid != 0 && decode_b_rx_summary(b_summary, &decoded)) {
		b_flags = decoded.flags;
		b_rx_good_count = decoded.rx_good;
		b_rx_bad_seen = ((decoded.flags & B_RX_FLAG_RX_BAD_SEEN) != 0u) ? 1u : 0u;
		b_rx_error = ((decoded.flags & B_RX_FLAG_RX_ERROR) != 0u) ? 1u : 0u;
		b_tx_start = ((decoded.flags & B_RX_FLAG_DATA_TX_START) != 0u) ? 1u : 0u;
		b_tx_activity = ((decoded.flags & B_RX_FLAG_TX_ACTIVITY) != 0u) ? 1u : 0u;
	}

	xil_printf("%s stage=%s mask=0x%08lx sent=%lu rx_ok=%lu tx_fail=%lu rx_timeout=%lu rx_bad=%lu rx_mismatch=%lu loss=",
	           tag,
	           stage->name,
	           (unsigned long)stage->lane_mask,
	           (unsigned long)total->sent,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->tx_fail,
	           (unsigned long)total->rx_timeout,
	           (unsigned long)total->rx_bad,
	           (unsigned long)total->rx_mismatch);
	print_loss(loss_permille(total));
	xil_printf("%% win_rx_mbps=");
	print_mbps(rate_x1000);
	print_status_regs(&status);
	xil_printf(" b_summary=0x%08lx b_summary_valid=%lu b_flags=0x%02lx b_rx_good_count=%lu b_rx_bad_seen=%lu b_rx_error=%lu b_tx_start=%lu b_tx_activity=%lu payload_match=fixed_a_pattern last_error=%s\r\n",
	           (unsigned long)b_summary,
	           (unsigned long)((b_summary_valid != 0) ? 1u : 0u),
	           (unsigned long)b_flags,
	           (unsigned long)b_rx_good_count,
	           (unsigned long)b_rx_bad_seen,
	           (unsigned long)b_rx_error,
	           (unsigned long)b_tx_start,
	           (unsigned long)b_tx_activity,
	           ir_hw_last_error(&g_ir));
}

static void print_stats_line(const char *tag,
                             const test_stage_t *stage,
                             const counters_t *total,
                             const counters_t *window,
                             uint32_t window_us)
{
	ir_hw_status_t status;
	uint32_t rate_x1000;

	ir_hw_get_status(&g_ir, &status);
	rate_x1000 = fixed_mbps_x1000(window->verified_bytes, window_us);

	xil_printf("%s stage=%s mask=0x%08lx sent=%lu rx_ok=%lu tx_fail=%lu rx_timeout=%lu rx_bad=%lu rx_mismatch=%lu loss=",
	           tag,
	           stage->name,
	           (unsigned long)stage->lane_mask,
	           (unsigned long)total->sent,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->tx_fail,
	           (unsigned long)total->rx_timeout,
	           (unsigned long)total->rx_bad,
	           (unsigned long)total->rx_mismatch);
	print_loss(loss_permille(total));
	xil_printf("%% win_rx_mbps=");
	print_mbps(rate_x1000);
	print_status_regs(&status);
	xil_printf(" last_error=%s\r\n", ir_hw_last_error(&g_ir));
}

#if PSPS_UART_OPERATOR != 0u
#ifndef UARTOP_STDIN_BASEADDR
#if defined(STDIN_BASEADDRESS)
#define UARTOP_STDIN_BASEADDR STDIN_BASEADDRESS
#elif defined(XPAR_XUARTPS_0_BASEADDR)
#define UARTOP_STDIN_BASEADDR XPAR_XUARTPS_0_BASEADDR
#elif defined(XPAR_XUARTPS_1_BASEADDR)
#define UARTOP_STDIN_BASEADDR XPAR_XUARTPS_1_BASEADDR
#endif
#endif

static uint32_t g_uartop_lane_mask = PSPS_STAGE_LANE_MASK;
static uint32_t g_uartop_ack_mask = PSPS_RX_LANE_MASK;
static uint32_t g_uartop_payload_bytes = PSPS_PAYLOAD_BYTES;
static uint32_t g_uartop_stage_seconds = PSPS_STAGE_SECONDS;
static uint16_t g_uartop_session_id = (uint16_t)PSPS_STAGE_SESSION_ID;
static uint32_t g_uartop_seq = 1u;
static counters_t g_uartop_total;
static uint32_t g_uartop_first_bad_seq = 0u;
static uint32_t g_uartop_first_bad_offset = 0u;
static uint32_t g_uartop_expected_byte = 0u;
static uint32_t g_uartop_actual_byte = 0u;

static char ascii_upper(char ch)
{
	if (ch >= 'a' && ch <= 'z') {
		return (char)(ch - ('a' - 'A'));
	}
	return ch;
}

static int token_equals(const char *lhs, const char *rhs)
{
	while (*lhs != '\0' && *rhs != '\0') {
		if (ascii_upper(*lhs) != ascii_upper(*rhs)) {
			return 0;
		}
		lhs++;
		rhs++;
	}
	return (*lhs == '\0' && *rhs == '\0');
}

static int parse_u32_arg(const char *text, uint32_t *value)
{
	uint32_t base = 10u;
	uint32_t out = 0u;
	uint32_t digits = 0u;

	if (text == NULL || *text == '\0') {
		return 0;
	}
	if (text[0] == '0' && (text[1] == 'x' || text[1] == 'X')) {
		base = 16u;
		text += 2;
	}
	while (*text != '\0') {
		uint32_t digit;
		if (*text >= '0' && *text <= '9') {
			digit = (uint32_t)(*text - '0');
		} else if (base == 16u && *text >= 'a' && *text <= 'f') {
			digit = 10u + (uint32_t)(*text - 'a');
		} else if (base == 16u && *text >= 'A' && *text <= 'F') {
			digit = 10u + (uint32_t)(*text - 'A');
		} else {
			return 0;
		}
		if (digit >= base) {
			return 0;
		}
		out = (out * base) + digit;
		digits++;
		text++;
	}
	if (digits == 0u) {
		return 0;
	}
	*value = out;
	return 1;
}

static int parse_key_value_u32(const char *text, const char *key, uint32_t *value)
{
	size_t key_len;

	if (text == NULL || key == NULL) {
		return 0;
	}
	key_len = strlen(key);
	if (strncmp(text, key, key_len) != 0 || text[key_len] != '=') {
		return 0;
	}
	return parse_u32_arg(&text[key_len + 1u], value);
}

static int parse_pattern_value(const char *text, uint32_t *value)
{
	if (text == NULL || value == NULL) {
		return 0;
	}
	if (token_equals(text, "zero") || token_equals(text, "zeros")) {
		*value = 0u;
		return 1;
	}
	if (token_equals(text, "ones") || token_equals(text, "ff")) {
		*value = 1u;
		return 1;
	}
	if (token_equals(text, "inc") || token_equals(text, "incrementing")) {
		*value = 2u;
		return 1;
	}
	if (token_equals(text, "pseudo")) {
		*value = 3u;
		return 1;
	}
	return parse_u32_arg(text, value);
}

static int parse_key_value_pattern(const char *text, const char *key, uint32_t *value)
{
	size_t key_len;

	if (text == NULL || key == NULL) {
		return 0;
	}
	key_len = strlen(key);
	if (strncmp(text, key, key_len) != 0 || text[key_len] != '=') {
		return 0;
	}
	return parse_pattern_value(&text[key_len + 1u], value);
}

static int uartop_get_char(char *ch)
{
#if defined(UARTOP_STDIN_BASEADDR)
	if (XUartPs_IsReceiveData((uint32_t)UARTOP_STDIN_BASEADDR)) {
		*ch = (char)XUartPs_ReadReg((uint32_t)UARTOP_STDIN_BASEADDR,
		                            XUARTPS_FIFO_OFFSET);
		return 1;
	}
#else
	(void)ch;
#endif
	return 0;
}

static int uartop_read_line(char *line, size_t capacity)
{
	size_t used = 0u;

	if (capacity == 0u) {
		return 0;
	}

	while (1) {
		char ch;

		if (!uartop_get_char(&ch)) {
			usleep(1000u);
			continue;
		}

		if (ch == '\r' || ch == '\n') {
			if (used == 0u) {
				continue;
			}
			line[used] = '\0';
			return 1;
		}
		if (ch == '\b' || ch == 0x7fu) {
			if (used != 0u) {
				used--;
			}
			continue;
		}
		if (used + 1u < capacity) {
			line[used] = ch;
			used++;
		}
	}
}

static void make_operator_payload(uint32_t seq)
{
	uint32_t i;

	if (g_uartop_payload_bytes >= 1u) {
		g_tx_payload[0] = 'P';
	}
	if (g_uartop_payload_bytes >= 2u) {
		g_tx_payload[1] = '2';
	}
	if (g_uartop_payload_bytes >= 3u) {
		g_tx_payload[2] = 'O';
	}
	if (g_uartop_payload_bytes >= 4u) {
		g_tx_payload[3] = 'P';
	}
	if (g_uartop_payload_bytes >= 8u) {
		rf_put_u32_le(&g_tx_payload[4], seq);
	}
	if (g_uartop_payload_bytes >= 12u) {
		rf_put_u32_le(&g_tx_payload[8], g_uartop_lane_mask);
	}
	if (g_uartop_payload_bytes >= 16u) {
		rf_put_u32_le(&g_tx_payload[12], ~seq);
	}

	for (i = 16u; i < g_uartop_payload_bytes; i++) {
		g_tx_payload[i] = (uint8_t)(seq + (i * 17u) + g_uartop_lane_mask);
	}
}

static int operator_payload_matches(size_t length,
                                    uint32_t *first_bad_offset,
                                    uint8_t *expected_byte,
                                    uint8_t *actual_byte)
{
	uint32_t i;

	if (length != g_uartop_payload_bytes) {
		if (first_bad_offset != NULL) {
			*first_bad_offset = (uint32_t)length;
		}
		if (expected_byte != NULL) {
			*expected_byte = 0u;
		}
		if (actual_byte != NULL) {
			*actual_byte = 0u;
		}
		return 0;
	}

	for (i = 0u; i < g_uartop_payload_bytes; i++) {
		if (g_tx_payload[i] != g_rx_payload[i]) {
			if (first_bad_offset != NULL) {
				*first_bad_offset = i;
			}
			if (expected_byte != NULL) {
				*expected_byte = g_tx_payload[i];
			}
			if (actual_byte != NULL) {
				*actual_byte = g_rx_payload[i];
			}
			return 0;
		}
	}

	return 1;
}

static uint8_t synthetic_expected_byte(uint32_t pattern, uint16_t seq, uint32_t offset)
{
	switch (pattern) {
	case 0u:
		return 0x00u;
	case 1u:
		return 0xffu;
	case 2u:
		return (uint8_t)(offset & 0xffu);
	default:
		return (uint8_t)((seq & 0xffu) ^ (offset & 0xffu) ^ 0xa5u);
	}
}

static int synthetic_payload_matches(size_t length, uint32_t payload_bytes,
                                     uint32_t pattern, uint16_t seq,
                                     uint32_t *first_bad_offset,
                                     uint8_t *expected_byte,
                                     uint8_t *actual_byte)
{
	uint32_t i;

	if (length != payload_bytes) {
		if (first_bad_offset != NULL) {
			*first_bad_offset = (uint32_t)length;
		}
		if (expected_byte != NULL) {
			*expected_byte = 0u;
		}
		if (actual_byte != NULL) {
			*actual_byte = 0u;
		}
		return 0;
	}

	for (i = 0u; i < payload_bytes; i++) {
		uint8_t expected = synthetic_expected_byte(pattern, seq, i);
		if (g_rx_payload[i] != expected) {
			if (first_bad_offset != NULL) {
				*first_bad_offset = i;
			}
			if (expected_byte != NULL) {
				*expected_byte = expected;
			}
			if (actual_byte != NULL) {
				*actual_byte = g_rx_payload[i];
			}
			return 0;
		}
	}

	return 1;
}

static int wait_for_operator_loopback(counters_t *counters)
{
	uint64_t start;
	size_t rx_len;
	int poll_status;

	start = now_ticks();
	while (elapsed_us(start, now_ticks()) < PSPS_RX_TIMEOUT_US) {
		rx_len = 0u;
		poll_status = ir_hw_poll_payload(&g_ir, g_rx_payload,
		                                  sizeof(g_rx_payload), &rx_len);
		if (poll_status == XST_FAILURE) {
			counters->rx_bad++;
			return XST_FAILURE;
		}
		if (poll_status == IR_HW_POLL_DATA) {
			uint32_t bad_offset = 0u;
			uint8_t expected = 0u;
			uint8_t actual = 0u;
			if (operator_payload_matches(rx_len, &bad_offset, &expected, &actual)) {
				counters->rx_ok++;
				counters->verified_bytes += g_uartop_payload_bytes;
				return XST_SUCCESS;
			}
			counters->rx_mismatch++;
			g_uartop_first_bad_seq = (g_uartop_seq == 0u) ? 0u : (g_uartop_seq - 1u);
			g_uartop_first_bad_offset = bad_offset;
			g_uartop_expected_byte = expected;
			g_uartop_actual_byte = actual;
			return XST_FAILURE;
		}
		usleep(PSPS_POLL_SLEEP_US);
	}

	counters->rx_timeout++;
	ir_hw_note_rx_timeout(&g_ir);
	return XST_FAILURE;
}

static int wait_for_synthetic_payload(counters_t *counters, uint32_t payload_bytes,
                                      uint32_t pattern, uint16_t seq)
{
	uint64_t start;
	size_t rx_len;
	int poll_status;

	start = now_ticks();
	while (elapsed_us(start, now_ticks()) < PSPS_RX_TIMEOUT_US) {
		uint32_t bad_offset = 0u;
		uint8_t expected = 0u;
		uint8_t actual = 0u;

		rx_len = 0u;
		poll_status = ir_hw_poll_payload(&g_ir, g_rx_payload,
		                                  sizeof(g_rx_payload), &rx_len);
		if (poll_status == XST_FAILURE) {
			counters->rx_bad++;
			return XST_FAILURE;
		}
		if (poll_status == IR_HW_POLL_DATA) {
			if (synthetic_payload_matches(rx_len, payload_bytes, pattern, seq,
			                              &bad_offset, &expected, &actual)) {
				counters->rx_ok++;
				counters->verified_bytes += payload_bytes;
				return XST_SUCCESS;
			}
			counters->rx_mismatch++;
			g_uartop_first_bad_seq = seq;
			g_uartop_first_bad_offset = bad_offset;
			g_uartop_expected_byte = expected;
			g_uartop_actual_byte = actual;
			return XST_FAILURE;
		}
		usleep(PSPS_POLL_SLEEP_US);
	}

	counters->rx_timeout++;
	ir_hw_note_rx_timeout(&g_ir);
	return XST_FAILURE;
}

static int uartop_apply_config(uint8_t enable)
{
	return ir_hw_configure(&g_ir,
	                       RF_CONFIG_ENABLE | RF_CONFIG_SESSION |
	                       RF_CONFIG_LANE_MASK | RF_CONFIG_RX_LANE_MASK,
	                       enable,
	                       g_uartop_session_id,
	                       g_uartop_lane_mask,
	                       g_uartop_ack_mask);
}

static void uartop_print_config(void)
{
	xil_printf(" lane_mask=0x%08lx ack_mask=0x%08lx payload_bytes=%lu stage_seconds=%lu session=0x%04lx",
	           (unsigned long)g_uartop_lane_mask,
	           (unsigned long)g_uartop_ack_mask,
	           (unsigned long)g_uartop_payload_bytes,
	           (unsigned long)g_uartop_stage_seconds,
	           (unsigned long)g_uartop_session_id);
}

static void uartop_print_counters(const char *tag,
                                  const counters_t *total,
                                  const counters_t *window,
                                  uint32_t window_us)
{
	ir_hw_status_t status;
	uint32_t rate_x1000;

	ir_hw_get_status(&g_ir, &status);
	rate_x1000 = fixed_mbps_x1000(window->verified_bytes, window_us);

	xil_printf("%s sent=%lu rx_ok=%lu tx_fail=%lu rx_timeout=%lu rx_bad=%lu rx_mismatch=%lu loss=",
	           tag,
	           (unsigned long)total->sent,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->tx_fail,
	           (unsigned long)total->rx_timeout,
	           (unsigned long)total->rx_bad,
	           (unsigned long)total->rx_mismatch);
	print_loss(loss_permille(total));
	xil_printf("%% win_rx_mbps=");
	print_mbps(rate_x1000);
	uartop_print_config();
	print_status_regs(&status);
	xil_printf(" last_error=%s\r\n", ir_hw_last_error(&g_ir));
}

static void uartop_status_result(const char *command, int rc)
{
	xil_printf("UARTOP_RESULT command=%s rc=%d", command, rc);
	uartop_print_config();
	xil_printf(" cumulative_sent=%lu cumulative_rx_ok=%lu",
	           (unsigned long)g_uartop_total.sent,
	           (unsigned long)g_uartop_total.rx_ok);
	{
		ir_hw_status_t status;
		ir_hw_get_status(&g_ir, &status);
		print_status_regs(&status);
	}
	xil_printf(" last_error=%s\r\n", ir_hw_last_error(&g_ir));
}

static void uartop_simple_result(const char *command, int rc, const char *detail)
{
	xil_printf("UARTOP_RESULT command=%s rc=%d", command, rc);
	if (detail != NULL && detail[0] != '\0') {
		xil_printf(" %s", detail);
	}
	uartop_print_config();
	xil_printf(" last_error=%s\r\n", ir_hw_last_error(&g_ir));
}

static void uartop_test_error(const char *test_id, const char *error)
{
	xil_printf("UARTOP_RESULT command=TEST rc=1 test_id=%s error=%s",
	           test_id,
	           error);
	uartop_print_config();
	xil_printf(" last_error=%s\r\n", ir_hw_last_error(&g_ir));
}

static void uartop_config_command(char *key, char *value)
{
	uint32_t parsed;
	int rc = 0;
	const char *detail = "";

	if (key == NULL || value == NULL || !parse_u32_arg(value, &parsed)) {
		uartop_simple_result("CONFIG", 1, "error=bad_argument");
		return;
	}

	if (token_equals(key, "lane_mask")) {
		if (parsed == 0u) {
			rc = 1;
			detail = "error=bad_lane_mask";
		} else {
			g_uartop_lane_mask = parsed;
			g_uartop_session_id = (uint16_t)(PSPS_SESSION_BASE + (parsed & 0x00ffu));
		}
	} else if (token_equals(key, "session")) {
		if (parsed == 0u || parsed > 0xffffu) {
			rc = 1;
			detail = "error=bad_session";
		} else {
			g_uartop_session_id = (uint16_t)parsed;
		}
	} else if (token_equals(key, "ack_mask")) {
		if (parsed == 0u) {
			rc = 1;
			detail = "error=bad_ack_mask";
		} else {
			g_uartop_ack_mask = parsed;
		}
	} else if (token_equals(key, "payload_bytes")) {
		if (parsed < 16u || parsed > PSPS_PAYLOAD_BYTES) {
			rc = 1;
			detail = "error=payload_exceeds_build_limit";
		} else {
			g_uartop_payload_bytes = parsed;
		}
	} else if (token_equals(key, "stage_seconds")) {
		if (parsed == 0u || parsed > PSPS_OPERATOR_MAX_STAGE_SECONDS) {
			rc = 1;
			detail = "error=bad_stage_seconds";
		} else {
			g_uartop_stage_seconds = parsed;
		}
	} else {
		rc = 1;
		detail = "error=unknown_config_key";
	}

	if (rc == 0 && uartop_apply_config(0u) != XST_SUCCESS) {
		rc = 1;
		detail = "error=apply_config_failed";
	}

	xil_printf("UARTOP_RESULT command=CONFIG rc=%d key=%s value=%s %s",
	           rc, key, value, detail);
	uartop_print_config();
	xil_printf(" last_error=%s\r\n", ir_hw_last_error(&g_ir));
}

static void uartop_start_command(void)
{
	counters_t total;
	counters_t window;
	uint64_t stage_start;
	uint64_t window_start;
	uint32_t last_print_us = 0u;

	if (uartop_apply_config(1u) != XST_SUCCESS) {
		uartop_simple_result("START", 1, "error=apply_config_failed");
		return;
	}
	ir_hw_clear_sticky(&g_ir);
	usleep(10000u);

	reset_counters(&total);
	reset_counters(&window);
	stage_start = now_ticks();
	window_start = stage_start;
	xil_printf("UARTOP_EVENT command=START state=running\r\n");

	while (elapsed_us(stage_start, now_ticks()) < (g_uartop_stage_seconds * 1000000u)) {
		counters_t sample;
		uint64_t now;
		uint32_t win_us;

		reset_counters(&sample);
		make_operator_payload(g_uartop_seq);
		g_uartop_seq++;

		sample.sent = 1u;
		if (ir_hw_send_payload(&g_ir, g_tx_payload, g_uartop_payload_bytes) != XST_SUCCESS) {
			sample.tx_fail = 1u;
		} else if (PSPS_TX_ONLY != 0u) {
			sample.rx_ok = 1u;
			sample.verified_bytes += g_uartop_payload_bytes;
		} else {
			(void)wait_for_operator_loopback(&sample);
		}

		merge_counters(&total, &sample);
		merge_counters(&window, &sample);
		merge_counters(&g_uartop_total, &sample);

		now = now_ticks();
		win_us = elapsed_us(window_start, now);
		if (counter_delta(win_us, last_print_us) >= PSPS_STATS_INTERVAL_US) {
			uartop_print_counters("UARTOP_STATS", &total, &window, win_us);
			reset_counters(&window);
			window_start = now;
			last_print_us = 0u;
		}

		if (PSPS_INTER_PACKET_US > 0u) {
			usleep(PSPS_INTER_PACKET_US);
		}
	}

	(void)uartop_apply_config(0u);
	uartop_print_counters("UARTOP_RESULT command=START rc=0 link_disabled=1",
	                      &total, &window, elapsed_us(window_start, now_ticks()));
}

static void uartop_clear_error_command(void)
{
	ir_hw_status_t before;
	ir_hw_status_t after;

	ir_hw_get_status(&g_ir, &before);
	ir_hw_clear_sticky(&g_ir);
	ir_hw_get_status(&g_ir, &after);
	xil_printf("UARTOP_RESULT command=CLEAR rc=0 before_sticky=0x%08lx after_sticky=0x%08lx last_error=%s\r\n",
	           (unsigned long)before.sticky,
	           (unsigned long)after.sticky,
	           ir_hw_last_error(&g_ir));
}

static void uartop_clear_command(char **args, uint32_t argc)
{
	if (argc != 0u && args[0] != NULL && token_equals(args[0], "counters")) {
		reset_counters(&g_uartop_total);
		g_uartop_first_bad_seq = 0u;
		g_uartop_first_bad_offset = 0u;
		g_uartop_expected_byte = 0u;
		g_uartop_actual_byte = 0u;
		ir_hw_clear_sticky(&g_ir);
		xil_printf("UARTOP_RESULT command=CLEAR rc=0 item=counters last_error=%s\r\n",
		           ir_hw_last_error(&g_ir));
		return;
	}

	if (argc == 0u || args[0] == NULL ||
	    token_equals(args[0], "error") || token_equals(args[0], "sticky")) {
		uartop_clear_error_command();
		return;
	}

	uartop_simple_result("CLEAR", 1, "error=unknown_clear_target");
}

static void uartop_read_command(char **args, uint32_t argc)
{
	if (argc != 0u && args[0] != NULL) {
		if (token_equals(args[0], "build_id")) {
			xil_printf("UARTOP_RESULT command=READ rc=0 item=build_id value=p2_pspl_data_exchange_testmode_v1 payload_limit=%lu tx_only=%lu last_error=%s\r\n",
			           (unsigned long)PSPS_PAYLOAD_BYTES,
			           (unsigned long)PSPS_TX_ONLY,
			           ir_hw_last_error(&g_ir));
			return;
		}
		if (token_equals(args[0], "regmap_version")) {
			xil_printf("UARTOP_RESULT command=READ rc=0 item=regmap_version value=pspl_testmode_regmap_v1 test_control=control.bit8 test_start=commit.bit1 last_error=%s\r\n",
			           ir_hw_last_error(&g_ir));
			return;
		}
		if (token_equals(args[0], "rx_last_error")) {
			xil_printf("UARTOP_RESULT command=READ rc=0 item=rx_last_error value=%s first_bad_seq=%lu first_bad_offset=%lu expected_byte=0x%02lx actual_byte=0x%02lx\r\n",
			           ir_hw_last_error(&g_ir),
			           (unsigned long)g_uartop_first_bad_seq,
			           (unsigned long)g_uartop_first_bad_offset,
			           (unsigned long)g_uartop_expected_byte,
			           (unsigned long)g_uartop_actual_byte);
			return;
		}
		if (token_equals(args[0], "rx_stream_obs")) {
			ir_hw_status_t status;
			ir_hw_get_status(&g_ir, &status);
			xil_printf("UARTOP_RESULT command=READ rc=0 item=rx_stream_obs obs_sig=0x%08lx core_tvalid=%lu core_tready=%lu core_tlast=%lu core_bytes=%lu synth_tvalid=%lu synth_tlast=%lu synth_bytes=%lu mux_tvalid=%lu mux_tlast=%lu mux_bytes=%lu s2mm_arm=%lu s2mm_done=%lu s2mm_error=%lu s2mm_timeout=%lu rx_app_header_ok=%lu rx_app_header_bad=%lu rx_length_bad=%lu last_error=%s\r\n",
			           (unsigned long)status.obs_signature,
			           (unsigned long)status.core_rx_tvalid_count,
			           (unsigned long)status.core_rx_tready_count,
			           (unsigned long)status.core_rx_tlast_count,
			           (unsigned long)status.core_rx_byte_count,
			           (unsigned long)status.synth_rx_tvalid_count,
			           (unsigned long)status.synth_rx_tlast_count,
			           (unsigned long)status.synth_rx_byte_count,
			           (unsigned long)status.mux_rx_tvalid_count,
			           (unsigned long)status.mux_rx_tlast_count,
			           (unsigned long)status.mux_rx_byte_count,
			           (unsigned long)status.s2mm_arm_count,
			           (unsigned long)status.s2mm_done_count,
			           (unsigned long)status.s2mm_error_count,
			           (unsigned long)status.s2mm_timeout_count,
			           (unsigned long)status.rx_app_header_ok_count,
			           (unsigned long)status.rx_app_header_bad_count,
			           (unsigned long)status.rx_length_bad_count,
			           ir_hw_last_error(&g_ir));
			return;
		}
		if (token_equals(args[0], "failure_counters") ||
		    token_equals(args[0], "tx_failure_obs")) {
			ir_hw_status_t status;
			ir_hw_get_status(&g_ir, &status);
			xil_printf("UARTOP_RESULT command=READ rc=0 item=failure_counters tx_start_count=%lu tx_done_count=%lu tx_done_timeout_count=%lu tx_retry_count_total=%lu tx_retry_exhausted_count=%lu ack_timeout_count=%lu ack_late_count=%lu max_retry_seen=%lu recovery_count=%lu first_fail_sent_index=%lu first_fail_timestamp=%lu first_fail_seq=%lu first_fail_pre_sticky=0x%08lx first_fail_pre_phy0=0x%08lx first_fail_pre_tx_lane=0x%08lx first_fail_post_sticky=0x%08lx first_fail_post_phy0=0x%08lx last_error=%s\r\n",
			           (unsigned long)status.tx_start_count,
			           (unsigned long)status.tx_done_count,
			           (unsigned long)status.tx_done_timeout_count,
			           (unsigned long)status.tx_retry_count_total,
			           (unsigned long)status.tx_retry_exhausted_count,
			           (unsigned long)status.ack_timeout_count,
			           (unsigned long)status.ack_late_count,
			           (unsigned long)status.max_retry_seen,
			           (unsigned long)status.recovery_count,
			           (unsigned long)status.first_fail_sent_index,
			           (unsigned long)status.first_fail_timestamp,
			           (unsigned long)status.first_fail_seq,
			           (unsigned long)status.first_fail_pre_sticky,
			           (unsigned long)status.first_fail_pre_phy0,
			           (unsigned long)status.first_fail_pre_tx_lane,
			           (unsigned long)status.first_fail_post_sticky,
			           (unsigned long)status.first_fail_post_phy0,
			           ir_hw_last_error(&g_ir));
			return;
		}
		if (token_equals(args[0], "rx_frame_obs")) {
			ir_hw_status_t status;
			ir_hw_get_status(&g_ir, &status);
			xil_printf("UARTOP_RESULT command=READ rc=0 item=rx_frame_obs rx_raw_pulse_count=0 rx_frame_good_count=%lu rx_ack_frame_count=%lu rx_data_frame_count=%lu rx_crc_fail_count=%lu rx_header_drop_count=%lu rx_session_drop_count=0 rx_type_drop_count=0 rx_len_drop_count=%lu ack_consumed_internal_count=%lu data_forwarded_to_axis_count=%lu partial=1 last_error=%s\r\n",
			           (unsigned long)status.rx_lane_good_count,
			           (unsigned long)status.tx_done_count,
			           (unsigned long)status.core_rx_tvalid_count,
			           (unsigned long)status.rx_lane_crc_count,
			           (unsigned long)status.rx_app_header_bad_count,
			           (unsigned long)status.rx_length_bad_count,
			           (unsigned long)status.tx_done_count,
			           (unsigned long)status.core_rx_tvalid_count,
			           ir_hw_last_error(&g_ir));
			return;
		}
		if (token_equals(args[0], "dma_obs")) {
			ir_hw_status_t status;
			ir_hw_get_status(&g_ir, &status);
			xil_printf("UARTOP_RESULT command=READ rc=0 item=dma_obs axis_rx_tvalid_count=%lu axis_rx_tready_count=%lu axis_rx_tlast_count=%lu axis_rx_byte_count=%lu s2mm_arm_count=%lu s2mm_done_count=%lu s2mm_error_count=%lu s2mm_timeout_count=%lu dma_tx_status=0x%08lx dma_rx_status=0x%08lx rx_armed=%lu last_error=%s\r\n",
			           (unsigned long)status.mux_rx_tvalid_count,
			           (unsigned long)status.core_rx_tready_count,
			           (unsigned long)status.mux_rx_tlast_count,
			           (unsigned long)status.mux_rx_byte_count,
			           (unsigned long)status.s2mm_arm_count,
			           (unsigned long)status.s2mm_done_count,
			           (unsigned long)status.s2mm_error_count,
			           (unsigned long)status.s2mm_timeout_count,
			           (unsigned long)status.dma_tx_status,
			           (unsigned long)status.dma_rx_status,
			           (unsigned long)status.rx_armed,
			           ir_hw_last_error(&g_ir));
			return;
		}
	}

	uartop_status_result("READ", 0);
}

static uint32_t uartop_result_pass(const counters_t *total, uint32_t expected)
{
	return (total->sent == expected &&
	        total->rx_ok == expected &&
	        total->tx_fail == 0u &&
	        total->rx_timeout == 0u &&
	        total->rx_bad == 0u &&
	        total->rx_mismatch == 0u) ? 1u : 0u;
}

static void uartop_print_test_result(const char *test_id, uint32_t pass,
                                     const counters_t *total,
                                     uint32_t expected_packets,
                                     uint32_t pattern,
                                     uint32_t expect_pattern,
                                     uint32_t payload_bytes)
{
	uint32_t dma_rx_packets;

	dma_rx_packets = total->rx_ok + total->rx_mismatch;
	xil_printf("UARTOP_RESULT command=TEST rc=%lu test_id=%s pass=%lu source=synthetic_internal payload_bytes=%lu count=%lu expected_packets=%lu injected_packets=%lu dma_rx_packets=%lu rx_ok=%lu rx_timeout=%lu rx_bad=%lu rx_mismatch=%lu rx_payload_bytes_verified=%lu pattern=%lu expect_pattern=%lu first_bad_seq=%lu first_bad_offset=%lu expected_byte=0x%02lx actual_byte=0x%02lx last_error=%s\r\n",
	           (unsigned long)((pass != 0u) ? 0u : 1u),
	           test_id,
	           (unsigned long)pass,
	           (unsigned long)payload_bytes,
	           (unsigned long)expected_packets,
	           (unsigned long)expected_packets,
	           (unsigned long)total->sent,
	           (unsigned long)dma_rx_packets,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->rx_timeout,
	           (unsigned long)total->rx_bad,
	           (unsigned long)total->rx_mismatch,
	           (unsigned long)total->verified_bytes,
	           (unsigned long)pattern,
	           (unsigned long)expect_pattern,
	           (unsigned long)g_uartop_first_bad_seq,
	           (unsigned long)g_uartop_first_bad_offset,
	           (unsigned long)g_uartop_expected_byte,
	           (unsigned long)g_uartop_actual_byte,
	           ir_hw_last_error(&g_ir));
	xil_printf("RESULT test_id=%s pass=%lu source=synthetic_internal payload_bytes=%lu count=%lu injected_packets=%lu dma_rx_packets=%lu rx_ok=%lu rx_timeout=%lu rx_bad=%lu rx_mismatch=%lu rx_payload_bytes_verified=%lu first_bad_seq=%lu first_bad_offset=%lu last_error=%s\r\n",
	           test_id,
	           (unsigned long)pass,
	           (unsigned long)payload_bytes,
	           (unsigned long)expected_packets,
	           (unsigned long)total->sent,
	           (unsigned long)dma_rx_packets,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->rx_timeout,
	           (unsigned long)total->rx_bad,
	           (unsigned long)total->rx_mismatch,
	           (unsigned long)total->verified_bytes,
	           (unsigned long)g_uartop_first_bad_seq,
	           (unsigned long)g_uartop_first_bad_offset,
	           ir_hw_last_error(&g_ir));
}

static void uartop_print_tx_dma_result(const char *test_id,
                                       uint32_t pass,
                                       const counters_t *total,
                                       uint32_t expected_packets,
                                       uint32_t payload_bytes)
{
	uint32_t tx_payload_bytes = total->sent * payload_bytes;

	xil_printf("UARTOP_RESULT command=TEST rc=%lu test_id=%s pass=%lu payload_bytes=%lu count=%lu sent=%lu tx_ok=%lu ack_ok=%lu tx_fail=%lu tx_payload_bytes=%lu last_error=%s\r\n",
	           (unsigned long)((pass != 0u) ? 0u : 1u),
	           test_id,
	           (unsigned long)pass,
	           (unsigned long)payload_bytes,
	           (unsigned long)expected_packets,
	           (unsigned long)total->sent,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->tx_fail,
	           (unsigned long)tx_payload_bytes,
	           ir_hw_last_error(&g_ir));
	xil_printf("RESULT test_id=%s pass=%lu payload_bytes=%lu count=%lu sent=%lu tx_ok=%lu ack_ok=%lu tx_fail=%lu tx_payload_bytes=%lu last_error=%s\r\n",
	           test_id,
	           (unsigned long)pass,
	           (unsigned long)payload_bytes,
	           (unsigned long)expected_packets,
	           (unsigned long)total->sent,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->tx_fail,
	           (unsigned long)tx_payload_bytes,
	           ir_hw_last_error(&g_ir));
}

static uint32_t uartop_roundtrip_pass(const counters_t *total)
{
	return (total->sent > 0u &&
	        total->rx_ok == total->sent &&
	        total->tx_fail == 0u &&
	        total->rx_timeout == 0u &&
	        total->rx_bad == 0u &&
	        total->rx_mismatch == 0u) ? 1u : 0u;
}

static const char *uartop_roundtrip_failure_class(const counters_t *total)
{
	if (uartop_roundtrip_pass(total) != 0u) {
		return "none";
	}
	if (total->tx_fail != 0u) {
		return "TX_ACK_FAIL";
	}
	if (total->rx_timeout != 0u) {
		return "TIMEOUT_WAITING_PL_RX_STREAM";
	}
	if (total->rx_bad != 0u) {
		return "RX_DMA_COMPLETES_BAD_IRP1_HEADER";
	}
	if (total->rx_mismatch != 0u) {
		return "RX_DMA_COMPLETES_PAYLOAD_MISMATCH";
	}
	return "COMMAND_CONTRACT_ERROR";
}

static void uartop_print_pspl_roundtrip_result(const char *test_id,
                                               uint32_t pass,
                                               const counters_t *total,
                                               uint32_t payload_bytes,
                                               uint32_t count,
                                               uint32_t seconds,
                                               uint32_t echo_retry_count_total,
                                               uint32_t echo_retry_exhausted_count,
                                               uint32_t echo_max_retry_seen,
                                               uint32_t echo_retry_limit,
                                               const char *failure_class)
{
	uint32_t dma_rx_packets = total->rx_ok + total->rx_mismatch;
	const char *last_error = ir_hw_last_error(&g_ir);

	if (failure_class == NULL || failure_class[0] == '\0') {
		failure_class = uartop_roundtrip_failure_class(total);
	}
	xil_printf("UARTOP_RESULT command=TEST rc=%lu test_id=%s pass=%lu payload_bytes=%lu count=%lu seconds=%lu sent=%lu tx_ok=%lu tx_fail=%lu core_data_frame_count=%lu axis_rx_packets=%lu dma_rx_packets=%lu rx_ok=%lu rx_timeout=%lu rx_bad=%lu rx_mismatch=%lu rx_payload_bytes_verified=%lu verified_bytes=%lu first_bad_seq=%lu first_bad_offset=%lu echo_retry_count_total=%lu echo_retry_exhausted_count=%lu echo_max_retry_seen=%lu echo_retry_limit=%lu failure_class=%s last_error=%s\r\n",
	           (unsigned long)((pass != 0u) ? 0u : 1u),
	           test_id,
	           (unsigned long)pass,
	           (unsigned long)payload_bytes,
	           (unsigned long)count,
	           (unsigned long)seconds,
	           (unsigned long)total->sent,
	           (unsigned long)(total->sent - total->tx_fail),
	           (unsigned long)total->tx_fail,
	           (unsigned long)total->rx_ok,
	           (unsigned long)dma_rx_packets,
	           (unsigned long)dma_rx_packets,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->rx_timeout,
	           (unsigned long)total->rx_bad,
	           (unsigned long)total->rx_mismatch,
	           (unsigned long)total->verified_bytes,
	           (unsigned long)total->verified_bytes,
	           (unsigned long)g_uartop_first_bad_seq,
	           (unsigned long)g_uartop_first_bad_offset,
	           (unsigned long)echo_retry_count_total,
	           (unsigned long)echo_retry_exhausted_count,
	           (unsigned long)echo_max_retry_seen,
	           (unsigned long)echo_retry_limit,
	           failure_class,
	           last_error);
	xil_printf("RESULT test_id=%s pass=%lu payload_bytes=%lu count=%lu seconds=%lu sent=%lu tx_ok=%lu tx_fail=%lu core_data_frame_count=%lu axis_rx_packets=%lu dma_rx_packets=%lu rx_ok=%lu rx_timeout=%lu rx_bad=%lu rx_mismatch=%lu rx_payload_bytes_verified=%lu verified_bytes=%lu first_bad_seq=%lu first_bad_offset=%lu echo_retry_count_total=%lu echo_retry_exhausted_count=%lu echo_max_retry_seen=%lu echo_retry_limit=%lu failure_class=%s last_error=%s\r\n",
	           test_id,
	           (unsigned long)pass,
	           (unsigned long)payload_bytes,
	           (unsigned long)count,
	           (unsigned long)seconds,
	           (unsigned long)total->sent,
	           (unsigned long)(total->sent - total->tx_fail),
	           (unsigned long)total->tx_fail,
	           (unsigned long)total->rx_ok,
	           (unsigned long)dma_rx_packets,
	           (unsigned long)dma_rx_packets,
	           (unsigned long)total->rx_ok,
	           (unsigned long)total->rx_timeout,
	           (unsigned long)total->rx_bad,
	           (unsigned long)total->rx_mismatch,
	           (unsigned long)total->verified_bytes,
	           (unsigned long)total->verified_bytes,
	           (unsigned long)g_uartop_first_bad_seq,
	           (unsigned long)g_uartop_first_bad_offset,
	           (unsigned long)echo_retry_count_total,
	           (unsigned long)echo_retry_exhausted_count,
	           (unsigned long)echo_max_retry_seen,
	           (unsigned long)echo_retry_limit,
	           failure_class,
	           last_error);
}

static int uartop_run_roundtrip_packet(uint32_t seq,
                                       uint32_t max_echo_retries,
                                       counters_t *sample,
                                       uint32_t *echo_retry_used)
{
	uint32_t attempt;

	reset_counters(sample);
	sample->sent = 1u;
	*echo_retry_used = 0u;

	for (attempt = 0u; attempt <= max_echo_retries; attempt++) {
		counters_t attempt_counters;
		reset_counters(&attempt_counters);
		make_operator_payload(seq);
		if (ir_hw_send_payload(&g_ir, g_tx_payload, g_uartop_payload_bytes) != XST_SUCCESS) {
			sample->tx_fail = 1u;
			return XST_FAILURE;
		}
		if (wait_for_operator_loopback(&attempt_counters) == XST_SUCCESS) {
			sample->rx_ok = attempt_counters.rx_ok;
			sample->verified_bytes = attempt_counters.verified_bytes;
			return XST_SUCCESS;
		}
		if (attempt_counters.rx_bad != 0u || attempt_counters.rx_mismatch != 0u) {
			sample->rx_bad = attempt_counters.rx_bad;
			sample->rx_mismatch = attempt_counters.rx_mismatch;
			return XST_FAILURE;
		}
		if (attempt == max_echo_retries) {
			sample->rx_timeout = attempt_counters.rx_timeout;
			return XST_FAILURE;
		}
		(*echo_retry_used)++;
		if (PSPS_IR_ROUNDTRIP_RETRY_GAP_US > 0u) {
			usleep(PSPS_IR_ROUNDTRIP_RETRY_GAP_US);
		}
	}

	sample->rx_timeout = 1u;
	return XST_FAILURE;
}

static void uartop_test_rx_dma_synth_command(char **args, uint32_t argc)
{
	uint32_t payload_bytes = g_uartop_payload_bytes;
	uint32_t count = 1u;
	uint32_t pattern = 3u;
	uint32_t expect_pattern = 3u;
	uint32_t has_expect_pattern = 0u;
	uint32_t i;
	counters_t total;

	for (i = 1u; i < argc; i++) {
		uint32_t parsed;
		if (parse_key_value_u32(args[i], "payload", &parsed) ||
		    parse_key_value_u32(args[i], "payload_bytes", &parsed)) {
			payload_bytes = parsed;
		} else if (parse_key_value_u32(args[i], "count", &parsed) ||
		           parse_key_value_u32(args[i], "packets", &parsed)) {
			count = parsed;
		} else if (parse_key_value_pattern(args[i], "pattern", &parsed)) {
			pattern = parsed;
		} else if (parse_key_value_pattern(args[i], "expect_pattern", &parsed)) {
			expect_pattern = parsed;
			has_expect_pattern = 1u;
		} else {
			uartop_simple_result("TEST", 1, "test_id=RX_DMA_SYNTH error=bad_argument");
			return;
		}
	}

	if (payload_bytes == 0u || payload_bytes > PSPS_PAYLOAD_BYTES) {
		uartop_simple_result("TEST", 1, "test_id=RX_DMA_SYNTH error=bad_payload_bytes");
		return;
	}
	if (count == 0u || count > 100000u) {
		uartop_simple_result("TEST", 1, "test_id=RX_DMA_SYNTH error=bad_packet_count");
		return;
	}
	if (has_expect_pattern == 0u) {
		expect_pattern = pattern;
	}

	(void)uartop_apply_config(0u);
	reset_counters(&total);
	g_uartop_first_bad_seq = 0u;
	g_uartop_first_bad_offset = 0u;
	g_uartop_expected_byte = 0u;
	g_uartop_actual_byte = 0u;

	for (i = 0u; i < count; i++) {
		counters_t sample;
		uint16_t seq;

		reset_counters(&sample);
		seq = (uint16_t)(g_uartop_seq & 0xffffu);
		if (seq == 0u) {
			seq = 1u;
			g_uartop_seq = 1u;
		}
		g_uartop_seq++;

		sample.sent = 1u;
		if (ir_hw_inject_rx_synthetic(&g_ir, payload_bytes, pattern, seq) != XST_SUCCESS) {
			sample.rx_bad = 1u;
		} else {
			(void)wait_for_synthetic_payload(&sample, payload_bytes, expect_pattern, seq);
		}
		merge_counters(&total, &sample);
		merge_counters(&g_uartop_total, &sample);
		if (sample.rx_bad != 0u || sample.rx_timeout != 0u || sample.rx_mismatch != 0u) {
			break;
		}
	}

	ir_hw_disable_test_mode(&g_ir);
	uartop_print_test_result("RX_DMA_SYNTH",
	                         uartop_result_pass(&total, count),
	                         &total,
	                         count,
	                         pattern,
	                         expect_pattern,
	                         payload_bytes);
}

static void uartop_test_tx_dma_command(char **args, uint32_t argc,
                                       const char *test_id)
{
	uint32_t payload_bytes = g_uartop_payload_bytes;
	uint32_t count = 1u;
	uint32_t saved_payload_bytes;
	uint32_t i;
	counters_t total;

	for (i = 1u; i < argc; i++) {
		uint32_t parsed;
		if (parse_key_value_u32(args[i], "payload", &parsed) ||
		    parse_key_value_u32(args[i], "payload_bytes", &parsed)) {
			payload_bytes = parsed;
		} else if (parse_key_value_u32(args[i], "count", &parsed) ||
		           parse_key_value_u32(args[i], "packets", &parsed)) {
			count = parsed;
		} else {
			uartop_test_error(test_id, "bad_argument");
			return;
		}
	}

	if (payload_bytes < 16u || payload_bytes > PSPS_PAYLOAD_BYTES) {
		uartop_test_error(test_id, "bad_payload_bytes");
		return;
	}
	if (count == 0u || count > 100000u) {
		uartop_test_error(test_id, "bad_packet_count");
		return;
	}
	if (uartop_apply_config(1u) != XST_SUCCESS) {
		uartop_test_error(test_id, "apply_config_failed");
		return;
	}

	reset_counters(&total);
	saved_payload_bytes = g_uartop_payload_bytes;
	g_uartop_payload_bytes = payload_bytes;
	for (i = 0u; i < count; i++) {
		counters_t sample;
		reset_counters(&sample);
		make_operator_payload(g_uartop_seq++);
		sample.sent = 1u;
		if (ir_hw_send_payload(&g_ir, g_tx_payload, payload_bytes) != XST_SUCCESS) {
			sample.tx_fail = 1u;
		} else if (PSPS_TX_ONLY != 0u) {
			sample.rx_ok = 1u;
			sample.verified_bytes += payload_bytes;
		} else {
			(void)wait_for_operator_loopback(&sample);
		}
		merge_counters(&total, &sample);
		merge_counters(&g_uartop_total, &sample);
		if (sample.tx_fail != 0u || sample.rx_bad != 0u ||
		    sample.rx_timeout != 0u || sample.rx_mismatch != 0u) {
			break;
		}
	}
	g_uartop_payload_bytes = saved_payload_bytes;
	(void)uartop_apply_config(0u);
	uartop_print_tx_dma_result(test_id,
	                           uartop_result_pass(&total, count),
	                           &total,
	                           count,
	                           payload_bytes);
}

static void uartop_test_roundtrip_command(char **args, uint32_t argc,
                                         const char *test_id)
{
	uint32_t payload_bytes = g_uartop_payload_bytes;
	uint32_t count = 0u;
	uint32_t seconds = 0u;
	uint32_t has_count = 0u;
	uint32_t has_seconds = 0u;
	uint32_t saved_payload_bytes;
	uint32_t i;
	uint32_t echo_retry_limit = 0u;
	uint32_t echo_retry_count_total = 0u;
	uint32_t echo_retry_exhausted_count = 0u;
	uint32_t echo_max_retry_seen = 0u;
	counters_t total;

	for (i = 1u; i < argc; i++) {
		uint32_t parsed;
		if (parse_key_value_u32(args[i], "payload", &parsed) ||
		    parse_key_value_u32(args[i], "payload_bytes", &parsed)) {
			payload_bytes = parsed;
		} else if (parse_key_value_u32(args[i], "count", &parsed) ||
		           parse_key_value_u32(args[i], "packets", &parsed)) {
			count = parsed;
			has_count = 1u;
		} else if (parse_key_value_u32(args[i], "seconds", &parsed)) {
			seconds = parsed;
			has_seconds = 1u;
		} else {
			uartop_test_error(test_id, "bad_argument");
			return;
		}
	}

	if (payload_bytes == 0u || payload_bytes > PSPS_PAYLOAD_BYTES) {
		uartop_test_error(test_id, "bad_payload_bytes");
		return;
	}
	if (has_count != 0u && has_seconds != 0u) {
		uartop_test_error(test_id, "count_seconds_mutually_exclusive");
		return;
	}
	if (has_count == 0u && has_seconds == 0u) {
		uartop_test_error(test_id, "missing_count_or_seconds");
		return;
	}
	if (has_count != 0u && (count == 0u || count > 100000u)) {
		uartop_test_error(test_id, "bad_packet_count");
		return;
	}
	if (has_seconds != 0u && (seconds == 0u || seconds > PSPS_OPERATOR_MAX_STAGE_SECONDS)) {
		uartop_test_error(test_id, "bad_seconds");
		return;
	}
	if (g_uartop_lane_mask == 0u || g_uartop_ack_mask == 0u) {
		uartop_test_error(test_id, "bad_lane_or_ack_mask");
		return;
	}

	reset_counters(&total);
	g_uartop_first_bad_seq = 0u;
	g_uartop_first_bad_offset = 0u;
	g_uartop_expected_byte = 0u;
	g_uartop_actual_byte = 0u;

#if PSPS_TX_ONLY != 0u
	uartop_print_pspl_roundtrip_result(test_id,
	                                   0u, &total, payload_bytes, count, seconds,
	                                   0u, 0u, 0u, 0u,
	                                   "UNSUPPORTED_BUILD_CONFIG");
#else
	if (uartop_apply_config(1u) != XST_SUCCESS) {
		uartop_test_error(test_id, "apply_config_failed");
		return;
	}

	saved_payload_bytes = g_uartop_payload_bytes;
	g_uartop_payload_bytes = payload_bytes;
	if (token_equals(test_id, "IR_DATA_ROUNDTRIP")) {
		echo_retry_limit = PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY;
	}
	if (has_count != 0u) {
		for (i = 0u; i < count; i++) {
			counters_t sample;
			uint32_t echo_retry_used = 0u;
			uint32_t seq = g_uartop_seq;
			g_uartop_seq++;
			(void)uartop_run_roundtrip_packet(seq, echo_retry_limit,
			                                  &sample, &echo_retry_used);
			echo_retry_count_total += echo_retry_used;
			if (echo_retry_used > echo_max_retry_seen) {
				echo_max_retry_seen = echo_retry_used;
			}
			merge_counters(&total, &sample);
			merge_counters(&g_uartop_total, &sample);
			if (sample.tx_fail != 0u || sample.rx_bad != 0u ||
			    sample.rx_timeout != 0u || sample.rx_mismatch != 0u) {
				if (sample.rx_timeout != 0u && echo_retry_limit > 0u &&
				    echo_retry_used >= echo_retry_limit) {
					echo_retry_exhausted_count++;
				}
				break;
			}
			if (PSPS_INTER_PACKET_US > 0u) {
				usleep(PSPS_INTER_PACKET_US);
			}
		}
	} else {
		uint64_t start = now_ticks();
		while (elapsed_us(start, now_ticks()) < (seconds * 1000000u)) {
			counters_t sample;
			uint32_t echo_retry_used = 0u;
			uint32_t seq = g_uartop_seq;
			g_uartop_seq++;
			(void)uartop_run_roundtrip_packet(seq, echo_retry_limit,
			                                  &sample, &echo_retry_used);
			echo_retry_count_total += echo_retry_used;
			if (echo_retry_used > echo_max_retry_seen) {
				echo_max_retry_seen = echo_retry_used;
			}
			merge_counters(&total, &sample);
			merge_counters(&g_uartop_total, &sample);
			if (sample.tx_fail != 0u || sample.rx_bad != 0u ||
			    sample.rx_timeout != 0u || sample.rx_mismatch != 0u) {
				if (sample.rx_timeout != 0u && echo_retry_limit > 0u &&
				    echo_retry_used >= echo_retry_limit) {
					echo_retry_exhausted_count++;
				}
				break;
			}
			if (PSPS_INTER_PACKET_US > 0u) {
				usleep(PSPS_INTER_PACKET_US);
			}
		}
	}
	g_uartop_payload_bytes = saved_payload_bytes;
	(void)uartop_apply_config(0u);
	uartop_print_pspl_roundtrip_result(test_id,
	                                   uartop_roundtrip_pass(&total),
	                                   &total,
	                                   payload_bytes,
	                                   count,
	                                   seconds,
	                                   echo_retry_count_total,
	                                   echo_retry_exhausted_count,
	                                   echo_max_retry_seen,
	                                   echo_retry_limit,
	                                   NULL);
#endif
}

static void uartop_test_command(char **args, uint32_t argc)
{
	if (argc == 0u || args[0] == NULL) {
		uartop_simple_result("TEST", 1, "error=missing_test_id");
		return;
	}
	if (token_equals(args[0], "rx_dma_synth")) {
		uartop_test_rx_dma_synth_command(args, argc);
	} else if (token_equals(args[0], "tx_dma")) {
		uartop_test_tx_dma_command(args, argc, "TX_DMA");
	} else if (token_equals(args[0], "tx_dma_ack")) {
		uartop_test_tx_dma_command(args, argc, "TX_DMA_ACK");
	} else if (token_equals(args[0], "pspl_roundtrip")) {
		uartop_test_roundtrip_command(args, argc, "PSPL_ROUNDTRIP");
	} else if (token_equals(args[0], "ir_data_roundtrip")) {
		uartop_test_roundtrip_command(args, argc, "IR_DATA_ROUNDTRIP");
	} else {
		uartop_simple_result("TEST", 1, "error=unknown_test_id");
	}
}

static void uartop_dump_command(char **args, uint32_t argc)
{
	if (argc != 0u && args[0] != NULL && token_equals(args[0], "rx_first_bad")) {
		xil_printf("UARTOP_RESULT command=DUMP rc=0 item=rx_first_bad first_bad_seq=%lu first_bad_offset=%lu expected_byte=0x%02lx actual_byte=0x%02lx last_error=%s\r\n",
		           (unsigned long)g_uartop_first_bad_seq,
		           (unsigned long)g_uartop_first_bad_offset,
		           (unsigned long)g_uartop_expected_byte,
		           (unsigned long)g_uartop_actual_byte,
		           ir_hw_last_error(&g_ir));
		return;
	}
	if (argc != 0u && args[0] != NULL && token_equals(args[0], "per_lane_counters")) {
		uartop_status_result("DUMP", 0);
		return;
	}
	uartop_simple_result("DUMP", 1, "error=unknown_dump_target");
}

static void uartop_handle_line(char *line)
{
	char *cmd;
	char *args[8];
	uint32_t argc = 0u;

	cmd = strtok(line, " \t");
	if (cmd == NULL) {
		return;
	}
	while (argc < (sizeof(args) / sizeof(args[0]))) {
		args[argc] = strtok(NULL, " \t");
		if (args[argc] == NULL) {
			break;
		}
		argc++;
	}

	if (token_equals(cmd, "STATUS")) {
		uartop_status_result("STATUS", 0);
	} else if (token_equals(cmd, "CONFIG")) {
		uartop_config_command((argc > 0u) ? args[0] : NULL,
		                      (argc > 1u) ? args[1] : NULL);
	} else if (token_equals(cmd, "START")) {
		uartop_start_command();
	} else if (token_equals(cmd, "STOP")) {
		int rc = (uartop_apply_config(0u) == XST_SUCCESS) ? 0 : 1;
		uartop_simple_result("STOP", rc, "link_disabled=1");
	} else if (token_equals(cmd, "READ")) {
		uartop_read_command(args, argc);
	} else if (token_equals(cmd, "CLEAR")) {
		uartop_clear_command(args, argc);
	} else if (token_equals(cmd, "TEST")) {
		uartop_test_command(args, argc);
	} else if (token_equals(cmd, "DUMP")) {
		uartop_dump_command(args, argc);
	} else if (token_equals(cmd, "SHUTDOWN")) {
		int rc = (uartop_apply_config(0u) == XST_SUCCESS) ? 0 : 1;
		uartop_simple_result("SHUTDOWN", rc, "link_disabled=1 tfdu_drive_disabled=1");
	} else {
		uartop_simple_result("UNKNOWN", 1, "error=unknown_command");
	}
}

static int run_uart_operator(void)
{
	char line[PSPS_OPERATOR_COMMAND_BYTES];

	reset_counters(&g_uartop_total);
	(void)uartop_apply_config(0u);
	xil_printf("UARTOP_READY protocol=rf_comm_uart_operator stdin=%lu build_payload_limit=%lu tx_only=%lu\r\n",
#if defined(UARTOP_STDIN_BASEADDR)
	           1ul,
#else
	           0ul,
#endif
	           (unsigned long)PSPS_PAYLOAD_BYTES,
	           (unsigned long)PSPS_TX_ONLY);
	uartop_status_result("STATUS", 0);

	while (1) {
		if (uartop_read_line(line, sizeof(line))) {
			uartop_handle_line(line);
		}
	}

	return 0;
}
#endif

static int configure_stage(const test_stage_t *stage)
{
	int status;

	xil_printf("\r\nPSPS_STAGE_BEGIN name=%s lane_mask=0x%08lx session=0x%04lx\r\n",
	           stage->name,
	           (unsigned long)stage->lane_mask,
	           (unsigned long)stage->session_id);

	status = ir_hw_configure(&g_ir,
	                         RF_CONFIG_ENABLE | RF_CONFIG_SESSION |
	                         RF_CONFIG_LANE_MASK | RF_CONFIG_RX_LANE_MASK,
	                         1u,
	                         stage->session_id,
	                         stage->lane_mask,
	                         PSPS_RX_LANE_MASK);
	if (status != XST_SUCCESS) {
		xil_printf("PSPS_CONFIG_FAIL stage=%s error=%s\r\n",
		           stage->name, ir_hw_last_error(&g_ir));
		return status;
	}

	ir_hw_clear_sticky(&g_ir);
	usleep(10000u);
	return XST_SUCCESS;
}

static int wait_for_loopback(counters_t *counters)
{
	uint64_t start;
	size_t rx_len;
	int poll_status;

	start = now_ticks();
	while (elapsed_us(start, now_ticks()) < PSPS_RX_TIMEOUT_US) {
		rx_len = 0u;
		poll_status = ir_hw_poll_payload(&g_ir, g_rx_payload,
		                                  sizeof(g_rx_payload), &rx_len);
		if (poll_status == XST_FAILURE) {
			counters->rx_bad++;
			return XST_FAILURE;
		}
		if (poll_status == IR_HW_POLL_DATA) {
			if (payload_matches(rx_len)) {
				counters->rx_ok++;
				counters->verified_bytes += PSPS_PAYLOAD_BYTES;
				return XST_SUCCESS;
			}

			counters->rx_mismatch++;
			return XST_FAILURE;
		}
		usleep(PSPS_POLL_SLEEP_US);
	}

	counters->rx_timeout++;
	ir_hw_note_rx_timeout(&g_ir);
	return XST_FAILURE;
}

static void merge_counters(counters_t *dst, const counters_t *src)
{
	dst->sent += src->sent;
	dst->tx_fail += src->tx_fail;
	dst->rx_ok += src->rx_ok;
	dst->rx_timeout += src->rx_timeout;
	dst->rx_bad += src->rx_bad;
	dst->rx_mismatch += src->rx_mismatch;
	dst->verified_bytes += src->verified_bytes;
}

static uint32_t outstanding_b2a_packets(const counters_t *c)
{
	uint32_t accepted_tx;

	accepted_tx = c->sent - c->tx_fail;
	if (accepted_tx <= c->rx_ok) {
		return 0u;
	}
	return accepted_tx - c->rx_ok;
}

static void poll_tx_window_events(counters_t *sample, uint32_t *outstanding)
{
	uint32_t done_count;
	uint32_t fail_count;
	uint32_t done;

	if (ir_hw_poll_tx_events(&g_ir, &done_count, &fail_count) == XST_FAILURE) {
		fail_count = 1u;
	}

	done = done_count;
	if (done > *outstanding) {
		done = *outstanding;
	}
	if (done != 0u) {
		*outstanding -= done;
		sample->rx_ok += done;
		sample->verified_bytes += done * PSPS_PAYLOAD_BYTES;
	}

	if (fail_count != 0u && *outstanding != 0u) {
		sample->tx_fail += *outstanding;
		*outstanding = 0u;
	}
}

static void run_stage_tx_window(const test_stage_t *stage, uint32_t *seq)
{
	counters_t total;
	counters_t window;
	uint64_t stage_start;
	uint64_t window_start;
	uint32_t last_print_us;
	uint32_t outstanding;
	uint64_t last_start_ticks;

	if (configure_stage(stage) != XST_SUCCESS) {
		usleep(1000000u);
		return;
	}

	reset_counters(&total);
	reset_counters(&window);
	stage_start = now_ticks();
	window_start = stage_start;
	last_print_us = 0u;
	outstanding = 0u;
	last_start_ticks = 0u;

	while (elapsed_us(stage_start, now_ticks()) < (PSPS_STAGE_SECONDS * 1000000u)) {
		counters_t sample;
		uint64_t now;
		uint32_t win_us;

		reset_counters(&sample);
		poll_tx_window_events(&sample, &outstanding);

		while ((outstanding < PSPS_MAX_OUTSTANDING) &&
		       (elapsed_us(stage_start, now_ticks()) < (PSPS_STAGE_SECONDS * 1000000u))) {
			if ((PSPS_WINDOW_START_GAP_US != 0u) &&
			    (outstanding != 0u) &&
			    (last_start_ticks != 0u)) {
				uint32_t since_start_us;

				since_start_us = elapsed_us(last_start_ticks, now_ticks());
				if (since_start_us < PSPS_WINDOW_START_GAP_US) {
					usleep(PSPS_WINDOW_START_GAP_US - since_start_us);
				}
			}

			make_payload(*seq, stage);
			(*seq)++;

			sample.sent++;
			if (ir_hw_start_payload_async(&g_ir, g_tx_payload, PSPS_PAYLOAD_BYTES) == XST_SUCCESS) {
				outstanding++;
				last_start_ticks = now_ticks();
			} else {
				sample.tx_fail++;
				if (outstanding != 0u) {
					sample.tx_fail += outstanding;
					outstanding = 0u;
				}
			}
			poll_tx_window_events(&sample, &outstanding);
		}

		merge_counters(&total, &sample);
		merge_counters(&window, &sample);

		now = now_ticks();
		win_us = elapsed_us(window_start, now);
		if (counter_delta(win_us, last_print_us) >= PSPS_STATS_INTERVAL_US) {
			print_stats_line("PSPS_STATS", stage, &total, &window, win_us);
			reset_counters(&window);
			window_start = now;
			last_print_us = 0u;
		}

		if (outstanding >= PSPS_MAX_OUTSTANDING) {
			usleep(PSPS_POLL_SLEEP_US);
		}
	}

	{
		uint64_t drain_start;

		drain_start = now_ticks();
		while ((outstanding != 0u) &&
		       (elapsed_us(drain_start, now_ticks()) < PSPS_RX_TIMEOUT_US)) {
			counters_t sample;

			reset_counters(&sample);
			poll_tx_window_events(&sample, &outstanding);
			merge_counters(&total, &sample);
			merge_counters(&window, &sample);
			if (outstanding == 0u) {
				break;
			}
			usleep(PSPS_POLL_SLEEP_US);
		}

		if (outstanding != 0u) {
			counters_t sample;

			reset_counters(&sample);
			sample.tx_fail = outstanding;
			outstanding = 0u;
			merge_counters(&total, &sample);
			merge_counters(&window, &sample);
		}
	}

	print_stats_line("PSPS_STAGE_SUMMARY", stage, &total, &window,
	                 elapsed_us(window_start, now_ticks()));
}

static void sample_b_rx_summary(counters_t *sample,
                                uint32_t *last_rx_good,
                                int *rx_bad_seen,
                                int *b_tx_seen,
                                uint32_t *last_summary,
                                int *summary_valid)
{
	ir_hw_status_t status;
	b_rx_summary_t decoded;
	uint32_t rx_good_delta;

	ir_hw_get_status(&g_ir, &status);
	*last_summary = status.phy_lane0_dbg;
	if (!decode_b_rx_summary(status.phy_lane0_dbg, &decoded)) {
		*summary_valid = 0;
		return;
	}

	*summary_valid = 1;
	rx_good_delta = counter16_delta(decoded.rx_good, *last_rx_good);
	sample->rx_ok += rx_good_delta;
	sample->verified_bytes += rx_good_delta * PSPS_PAYLOAD_BYTES;
	if ((decoded.flags & (B_RX_FLAG_RX_BAD_SEEN | B_RX_FLAG_RX_ERROR)) != 0u &&
	    *rx_bad_seen == 0) {
		sample->rx_bad++;
		*rx_bad_seen = 1;
	}
	if ((decoded.flags & (B_RX_FLAG_DATA_TX_START | B_RX_FLAG_TX_ACTIVITY)) != 0u &&
	    *b_tx_seen == 0) {
		sample->rx_mismatch++;
		*b_tx_seen = 1;
	}
	*last_rx_good = decoded.rx_good;
}

static void run_stage_a2b_rx_summary(const test_stage_t *stage, uint32_t *seq)
{
	counters_t total;
	counters_t window;
	ir_hw_status_t start_status;
	uint64_t stage_start;
	uint64_t window_start;
	uint32_t last_print_us;
	uint32_t last_rx_good;
	uint32_t last_summary;
	b_rx_summary_t decoded_start_summary;
	int summary_valid;
	int rx_bad_seen;
	int b_tx_seen;

	if (configure_stage(stage) != XST_SUCCESS) {
		usleep(1000000u);
		return;
	}

	reset_counters(&total);
	reset_counters(&window);
	ir_hw_get_status(&g_ir, &start_status);
	last_summary = start_status.phy_lane0_dbg;
	summary_valid = decode_b_rx_summary(start_status.phy_lane0_dbg,
	                                    &decoded_start_summary);
	last_rx_good = summary_valid ? decoded_start_summary.rx_good : 0u;
	rx_bad_seen = (summary_valid &&
	               ((decoded_start_summary.flags &
	                 (B_RX_FLAG_RX_BAD_SEEN | B_RX_FLAG_RX_ERROR)) != 0u)) ? 1 : 0;
	b_tx_seen = (summary_valid &&
	             ((decoded_start_summary.flags &
	               (B_RX_FLAG_DATA_TX_START | B_RX_FLAG_TX_ACTIVITY)) != 0u)) ? 1 : 0;

	stage_start = now_ticks();
	window_start = stage_start;
	last_print_us = 0u;

	while (elapsed_us(stage_start, now_ticks()) < (PSPS_STAGE_SECONDS * 1000000u)) {
		counters_t sample;
		uint64_t now;
		uint32_t win_us;

		reset_counters(&sample);
		make_payload(*seq, stage);
		(*seq)++;

		sample.sent = 1u;
		if (ir_hw_start_payload_async(&g_ir, g_tx_payload, PSPS_PAYLOAD_BYTES) != XST_SUCCESS) {
			sample.tx_fail = 1u;
		}

		if (PSPS_INTER_PACKET_US > 0u) {
			usleep(PSPS_INTER_PACKET_US);
		}
		sample_b_rx_summary(&sample, &last_rx_good, &rx_bad_seen,
		                    &b_tx_seen, &last_summary, &summary_valid);

		merge_counters(&total, &sample);
		merge_counters(&window, &sample);

		now = now_ticks();
		win_us = elapsed_us(window_start, now);
		if (counter_delta(win_us, last_print_us) >= PSPS_STATS_INTERVAL_US) {
			print_b_rx_summary_line("PSPS_B_RX_ONLY_STATS", stage, &total,
			                        &window, win_us, last_summary,
			                        summary_valid);
			reset_counters(&window);
			window_start = now;
			last_print_us = 0u;
		}
	}

	{
		counters_t final_sample;

		reset_counters(&final_sample);
		usleep(PSPS_INTER_PACKET_US + 1000u);
		sample_b_rx_summary(&final_sample, &last_rx_good, &rx_bad_seen,
		                    &b_tx_seen, &last_summary, &summary_valid);
		merge_counters(&total, &final_sample);
		merge_counters(&window, &final_sample);
	}

	if (!summary_valid) {
		total.rx_mismatch++;
		window.rx_mismatch++;
	} else if (total.sent > 0u && total.rx_ok == 0u && total.rx_bad == 0u) {
		total.rx_timeout++;
		window.rx_timeout++;
	}

	print_b_rx_summary_line("PSPS_B_RX_ONLY_SUMMARY", stage, &total, &window,
	                        elapsed_us(window_start, now_ticks()), last_summary,
	                        summary_valid);
}

static void run_stage(const test_stage_t *stage, uint32_t *seq)
{
	counters_t total;
	counters_t window;
	uint64_t stage_start;
	uint64_t window_start;
	uint32_t last_print_us;

	if (configure_stage(stage) != XST_SUCCESS) {
		usleep(1000000u);
		return;
	}

	reset_counters(&total);
	reset_counters(&window);
	stage_start = now_ticks();
	window_start = stage_start;
	last_print_us = 0u;

	while (elapsed_us(stage_start, now_ticks()) < (PSPS_STAGE_SECONDS * 1000000u)) {
		counters_t sample;
		uint64_t now;
		uint32_t win_us;

		reset_counters(&sample);
		make_payload(*seq, stage);
		(*seq)++;

		sample.sent = 1u;
		if (ir_hw_send_payload(&g_ir, g_tx_payload, PSPS_PAYLOAD_BYTES) != XST_SUCCESS) {
			sample.tx_fail = 1u;
		} else if (PSPS_TX_ONLY != 0u) {
			sample.rx_ok = 1u;
			sample.verified_bytes += PSPS_PAYLOAD_BYTES;
		} else {
			(void)wait_for_loopback(&sample);
		}

		merge_counters(&total, &sample);
		merge_counters(&window, &sample);

		now = now_ticks();
		win_us = elapsed_us(window_start, now);
		if (counter_delta(win_us, last_print_us) >= PSPS_STATS_INTERVAL_US) {
			print_stats_line("PSPS_STATS", stage, &total, &window, win_us);
			reset_counters(&window);
			window_start = now;
			last_print_us = 0u;
		}

		if (PSPS_INTER_PACKET_US > 0u) {
			usleep(PSPS_INTER_PACKET_US);
		}
	}

	print_stats_line("PSPS_STAGE_SUMMARY", stage, &total, &window,
	                 elapsed_us(window_start, now_ticks()));
}

static void poll_b2a_packets(counters_t *sample)
{
	size_t rx_len;
	int poll_status;

	while (1) {
		rx_len = 0u;
		poll_status = ir_hw_poll_payload(&g_ir, g_rx_payload,
		                                  sizeof(g_rx_payload), &rx_len);
		if (poll_status == XST_FAILURE) {
			sample->rx_bad++;
			return;
		}
		if (poll_status != IR_HW_POLL_DATA) {
			return;
		}
		if (b2a_payload_matches(rx_len)) {
			sample->rx_ok++;
			sample->verified_bytes += (uint32_t)rx_len;
		} else {
			sample->rx_mismatch++;
		}
	}
}

static void poll_b2a_for_us(counters_t *sample, uint32_t duration_us)
{
	uint64_t start;

	if (duration_us == 0u) {
		poll_b2a_packets(sample);
		return;
	}

	start = now_ticks();
	while (elapsed_us(start, now_ticks()) < duration_us) {
		poll_b2a_packets(sample);
		usleep(PSPS_POLL_SLEEP_US);
	}
}

static void run_stage_tdm_bidir(const test_stage_t *stage, uint32_t *seq)
{
	counters_t total;
	counters_t window;
	uint64_t stage_start;
	uint64_t window_start;
	uint32_t last_print_us;

	if (configure_stage(stage) != XST_SUCCESS) {
		usleep(1000000u);
		return;
	}

	reset_counters(&total);
	reset_counters(&window);
	stage_start = now_ticks();
	window_start = stage_start;
	last_print_us = 0u;

	while (elapsed_us(stage_start, now_ticks()) < (PSPS_STAGE_SECONDS * 1000000u)) {
		counters_t sample;
		uint64_t now;
		uint32_t win_us;

		reset_counters(&sample);
		poll_b2a_packets(&sample);
		merge_counters(&total, &sample);
		merge_counters(&window, &sample);

		while ((PSPS_MAX_OUTSTANDING != 0u) &&
		       (outstanding_b2a_packets(&total) >= PSPS_MAX_OUTSTANDING) &&
		       (elapsed_us(stage_start, now_ticks()) < (PSPS_STAGE_SECONDS * 1000000u))) {
			reset_counters(&sample);
			poll_b2a_packets(&sample);
			merge_counters(&total, &sample);
			merge_counters(&window, &sample);
			if (outstanding_b2a_packets(&total) < PSPS_MAX_OUTSTANDING) {
				break;
			}
			usleep(PSPS_POLL_SLEEP_US);
		}

		reset_counters(&sample);
		make_payload(*seq, stage);
		(*seq)++;

		sample.sent = 1u;
		if (ir_hw_send_payload(&g_ir, g_tx_payload, PSPS_PAYLOAD_BYTES) != XST_SUCCESS) {
			sample.tx_fail = 1u;
		}
		poll_b2a_packets(&sample);

		poll_b2a_for_us(&sample, PSPS_INTER_PACKET_US);
		merge_counters(&total, &sample);
		merge_counters(&window, &sample);

		now = now_ticks();
		win_us = elapsed_us(window_start, now);
		if (counter_delta(win_us, last_print_us) >= PSPS_STATS_INTERVAL_US) {
			print_stats_line("PSPS_TDM_STATS", stage, &total, &window, win_us);
			reset_counters(&window);
			window_start = now;
			last_print_us = 0u;
		}
	}

	{
		counters_t final_sample;
		uint64_t drain_start;

		drain_start = now_ticks();
		while ((PSPS_MAX_OUTSTANDING != 0u) &&
		       (outstanding_b2a_packets(&total) != 0u) &&
		       (elapsed_us(drain_start, now_ticks()) < PSPS_RX_TIMEOUT_US)) {
			reset_counters(&final_sample);
			poll_b2a_packets(&final_sample);
			merge_counters(&total, &final_sample);
			merge_counters(&window, &final_sample);
			if (outstanding_b2a_packets(&total) == 0u) {
				break;
			}
			usleep(PSPS_POLL_SLEEP_US);
		}

		reset_counters(&final_sample);
		poll_b2a_packets(&final_sample);
		merge_counters(&total, &final_sample);
		merge_counters(&window, &final_sample);
	}
	print_stats_line("PSPS_TDM_STAGE_SUMMARY", stage, &total, &window,
	                 elapsed_us(window_start, now_ticks()));
}

static void run_stage_rx_only(const test_stage_t *stage)
{
	counters_t total;
	counters_t window;
	uint64_t stage_start;
	uint64_t window_start;
	uint32_t last_print_us;

	if (configure_stage(stage) != XST_SUCCESS) {
		usleep(1000000u);
		return;
	}

	reset_counters(&total);
	reset_counters(&window);
	stage_start = now_ticks();
	window_start = stage_start;
	last_print_us = 0u;

	while (elapsed_us(stage_start, now_ticks()) < (PSPS_STAGE_SECONDS * 1000000u)) {
		counters_t sample;
		uint64_t now;
		uint32_t win_us;

		reset_counters(&sample);
		poll_b2a_packets(&sample);
		merge_counters(&total, &sample);
		merge_counters(&window, &sample);

		now = now_ticks();
		win_us = elapsed_us(window_start, now);
		if (counter_delta(win_us, last_print_us) >= PSPS_STATS_INTERVAL_US) {
			print_stats_line("PSPS_RX_ONLY_STATS", stage, &total, &window, win_us);
			reset_counters(&window);
			window_start = now;
			last_print_us = 0u;
		}

		usleep(PSPS_POLL_SLEEP_US);
	}

	print_stats_line("PSPS_RX_ONLY_SUMMARY", stage, &total, &window,
	                 elapsed_us(window_start, now_ticks()));
}

int main(void)
{
	uint32_t seq = 1u;
	uint32_t stage_index = 0u;
	uint32_t completed_stages = 0u;

	Xil_ICacheEnable();
	Xil_DCacheEnable();

	xil_printf("\r\nRF_COMM PS-PS loopback experiment\r\n");
	xil_printf("No PC/TCP host is required. Watch UART only.\r\n");
	xil_printf("mode=%s\r\n",
	           (PSPS_A2B_RX_SUMMARY != 0u) ? "rx_only_a2b_b_summary_probe" :
	           ((PSPS_RX_ONLY != 0u) ? "rx_only_b2a_probe" :
	           ((PSPS_TDM_BIDIR != 0u) ? "stream_tdm_bidir" :
	           ((PSPS_TX_ONLY != 0u) ? "tx_only_halfduplex" : "roundtrip_loopback"))));
	xil_printf("payload_bytes=%lu rx_timeout_us=%lu stage_seconds=%lu\r\n",
	           (unsigned long)PSPS_PAYLOAD_BYTES,
	           (unsigned long)PSPS_RX_TIMEOUT_US,
	           (unsigned long)PSPS_STAGE_SECONDS);
	xil_printf("stats_interval_us=%lu run_once=%lu warmup_stages=%lu\r\n",
	           (unsigned long)PSPS_STATS_INTERVAL_US,
	           (unsigned long)PSPS_RUN_ONCE,
	           (unsigned long)PSPS_WARMUP_STAGES);
	xil_printf("max_outstanding=%lu\r\n", (unsigned long)PSPS_MAX_OUTSTANDING);
	xil_printf("payload_lane_mask=0x%08lx\r\n", (unsigned long)PSPS_PAYLOAD_LANE_MASK);
	xil_printf("rx_lane_mask=0x%08lx\r\n", (unsigned long)PSPS_RX_LANE_MASK);
	xil_printf("This app tests fixed TFDU A/B hardware loopback repeatedly.\r\n");

	if (ir_hw_init(&g_ir) != XST_SUCCESS) {
		xil_printf("PSPS_INIT_FAIL\r\n");
		while (1) {
			usleep(1000000u);
		}
	}

	xil_printf("PSPS_INIT_OK ir_base=0x%08lx dma_device_id=%lu\r\n",
	           (unsigned long)IR_HW_BASEADDR,
	           (unsigned long)IR_HW_DMA_DEVICE_ID);

#if PSPS_UART_OPERATOR != 0u
	return run_uart_operator();
#endif

	while (1) {
		if (completed_stages < PSPS_WARMUP_STAGES) {
			xil_printf("PSPS_WARMUP_BEGIN index=%lu of=%lu\r\n",
			           (unsigned long)(completed_stages + 1u),
			           (unsigned long)PSPS_WARMUP_STAGES);
		}
		if (PSPS_A2B_RX_SUMMARY != 0u) {
			run_stage_a2b_rx_summary(&g_stages[stage_index], &seq);
		} else if (PSPS_RX_ONLY != 0u) {
			run_stage_rx_only(&g_stages[stage_index]);
		} else if (PSPS_TDM_BIDIR != 0u) {
			run_stage_tdm_bidir(&g_stages[stage_index], &seq);
		} else if ((PSPS_TX_ONLY != 0u) && (PSPS_MAX_OUTSTANDING > 1u)) {
			run_stage_tx_window(&g_stages[stage_index], &seq);
		} else {
			run_stage(&g_stages[stage_index], &seq);
		}
		completed_stages++;
		stage_index++;
		if (stage_index >= (sizeof(g_stages) / sizeof(g_stages[0]))) {
			stage_index = 0u;
		}
		if ((PSPS_RUN_ONCE != 0u) && (completed_stages > PSPS_WARMUP_STAGES)) {
			(void)ir_hw_configure(&g_ir, RF_CONFIG_ENABLE, 0u,
			                      g_stages[0].session_id,
			                      g_stages[0].lane_mask,
			                      PSPS_RX_LANE_MASK);
			xil_printf("PSPS_RUN_ONCE_DONE link_disabled=1\r\n");
			while (1) {
				usleep(1000000u);
			}
		}
	}
}
