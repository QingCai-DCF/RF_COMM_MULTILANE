#pragma once

#include <stdint.h>

#include "p8d_driver.h"
#include "p8e_profile_config.h"

typedef enum {
  P8E_PROFILE_Z7010_2LANE_DEV = P8E_Z7010_2LANE_DEV_PROFILE_ID,
  P8E_PROFILE_Z7020_FIXED_8LANE = P8E_Z7020_FIXED_8LANE_PROFILE_ID,
  P8E_PROFILE_Z7020_ROTATING_8LANE = P8E_Z7020_ROTATING_8LANE_PROFILE_ID,
} p8e_profile_id_t;

typedef enum {
  P8E_ROLE_DEVELOPMENT = 0,
  P8E_ROLE_FIXED = 1,
  P8E_ROLE_ROTATING = 2,
} p8e_endpoint_role_t;

typedef struct {
  uint32_t profile_id;
  uint32_t profile_version;
  uint32_t build_hash_low;
  uint32_t build_hash_high;
  uint16_t lane_count;
  uint16_t physical_module_count;
  uint16_t tx_window;
  uint16_t rx_window;
  uint16_t sack_bits;
  uint16_t descriptor_ring_depth;
  uint8_t endpoint_role;
  uint8_t reserved[3];
} p8e_profile_contract_t;

typedef struct {
  p8d_cache_ops_t cache;
  uint32_t cache_line_bytes;
  uint8_t ddr_runtime_validated;
} p8e_dma_cache_contract_t;

const p8e_profile_contract_t *p8e_profile_contract(p8e_profile_id_t id);
int p8e_validate_profile_contract(const p8e_profile_contract_t *profile);
int p8e_validate_dma_cache_contract(const p8e_dma_cache_contract_t *contract);
