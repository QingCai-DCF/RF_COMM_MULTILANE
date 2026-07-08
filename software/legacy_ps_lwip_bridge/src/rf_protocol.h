#ifndef RF_PROTOCOL_H
#define RF_PROTOCOL_H

#include <stdint.h>

#define RF_PROTO_MAGIC0          'R'
#define RF_PROTO_MAGIC1          'F'
#define RF_PROTO_MAGIC2          'C'
#define RF_PROTO_MAGIC3          'M'
#define RF_PROTO_VERSION         1u
#define RF_PROTO_HEADER_BYTES    12u
#define RF_PROTO_MAX_PAYLOAD     512u

#define RF_FRAME_HELLO           0x01u
#define RF_FRAME_STATUS_REQ      0x02u
#define RF_FRAME_STATUS_RSP      0x03u
#define RF_FRAME_ACK             0x04u
#define RF_FRAME_ERROR           0x05u
#define RF_FRAME_TX_DATA         0x10u
#define RF_FRAME_RX_DATA         0x11u
#define RF_FRAME_CLEAR           0x20u
#define RF_FRAME_CONFIG          0x21u
#define RF_FRAME_COMMAND         0x22u

#define RF_CONFIG_ENABLE         (1u << 0)
#define RF_CONFIG_SESSION        (1u << 1)
#define RF_CONFIG_LANE_MASK      (1u << 2)
#define RF_CONFIG_RX_LANE_MASK   (1u << 3)
#define RF_CONFIG_MODE           (1u << 4)

#define RF_MODE_NETWORK_MEMORY_ECHO    0u
#define RF_MODE_PSPL_SYNTH_LOOPBACK    1u
#define RF_MODE_IR_PHYSICAL            2u

static inline void rf_put_u16_le(uint8_t *dst, uint16_t value)
{
	dst[0] = (uint8_t)(value & 0xffu);
	dst[1] = (uint8_t)((value >> 8) & 0xffu);
}

static inline void rf_put_u32_le(uint8_t *dst, uint32_t value)
{
	dst[0] = (uint8_t)(value & 0xffu);
	dst[1] = (uint8_t)((value >> 8) & 0xffu);
	dst[2] = (uint8_t)((value >> 16) & 0xffu);
	dst[3] = (uint8_t)((value >> 24) & 0xffu);
}

static inline uint16_t rf_get_u16_le(const uint8_t *src)
{
	return (uint16_t)src[0] | ((uint16_t)src[1] << 8);
}

static inline uint32_t rf_get_u32_le(const uint8_t *src)
{
	return (uint32_t)src[0] |
	       ((uint32_t)src[1] << 8) |
	       ((uint32_t)src[2] << 16) |
	       ((uint32_t)src[3] << 24);
}

#endif
