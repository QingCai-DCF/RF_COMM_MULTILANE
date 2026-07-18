#include "p8e_profile.h"

static const p8e_profile_contract_t profiles[] = {
  {P8E_PROFILE_Z7010_2LANE_DEV, P8E_Z7010_2LANE_DEV_PROFILE_VERSION,
   P8E_BUILD_HASH_LOW, P8E_BUILD_HASH_HIGH,
   P8E_Z7010_2LANE_DEV_LANE_COUNT, P8E_Z7010_2LANE_DEV_PHYSICAL_MODULE_COUNT,
   P8E_Z7010_2LANE_DEV_TX_WINDOW, P8E_Z7010_2LANE_DEV_RX_WINDOW,
   P8E_Z7010_2LANE_DEV_SACK_BITS, P8E_Z7010_2LANE_DEV_DESCRIPTOR_RING_DEPTH,
   P8E_Z7010_2LANE_DEV_ENDPOINT_ROLE, {0u, 0u, 0u}},
  {P8E_PROFILE_Z7020_FIXED_8LANE, P8E_Z7020_FIXED_8LANE_PROFILE_VERSION,
   P8E_BUILD_HASH_LOW, P8E_BUILD_HASH_HIGH,
   P8E_Z7020_FIXED_8LANE_LANE_COUNT, P8E_Z7020_FIXED_8LANE_PHYSICAL_MODULE_COUNT,
   P8E_Z7020_FIXED_8LANE_TX_WINDOW, P8E_Z7020_FIXED_8LANE_RX_WINDOW,
   P8E_Z7020_FIXED_8LANE_SACK_BITS, P8E_Z7020_FIXED_8LANE_DESCRIPTOR_RING_DEPTH,
   P8E_Z7020_FIXED_8LANE_ENDPOINT_ROLE, {0u, 0u, 0u}},
  {P8E_PROFILE_Z7020_ROTATING_8LANE, P8E_Z7020_ROTATING_8LANE_PROFILE_VERSION,
   P8E_BUILD_HASH_LOW, P8E_BUILD_HASH_HIGH,
   P8E_Z7020_ROTATING_8LANE_LANE_COUNT, P8E_Z7020_ROTATING_8LANE_PHYSICAL_MODULE_COUNT,
   P8E_Z7020_ROTATING_8LANE_TX_WINDOW, P8E_Z7020_ROTATING_8LANE_RX_WINDOW,
   P8E_Z7020_ROTATING_8LANE_SACK_BITS, P8E_Z7020_ROTATING_8LANE_DESCRIPTOR_RING_DEPTH,
   P8E_Z7020_ROTATING_8LANE_ENDPOINT_ROLE, {0u, 0u, 0u}},
};

_Static_assert(sizeof(p8d_descriptor_t) == 64u, "descriptor ABI changed");
_Static_assert(sizeof(p8e_profile_contract_t) == 32u, "profile ABI changed");

const p8e_profile_contract_t *p8e_profile_contract(p8e_profile_id_t id) {
  uint32_t index;
  for (index = 0u; index < (uint32_t)(sizeof(profiles) / sizeof(profiles[0])); index++) {
    if (profiles[index].profile_id == (uint32_t)id) return &profiles[index];
  }
  return 0;
}

int p8e_validate_profile_contract(const p8e_profile_contract_t *profile) {
  if (profile == 0 || profile->profile_version != 1u) return -1;
  if (profile->build_hash_low != P8E_BUILD_HASH_LOW ||
      profile->build_hash_high != P8E_BUILD_HASH_HIGH) return -8;
  if (profile->lane_count != 2u && profile->lane_count != 8u) return -2;
  if (profile->tx_window < 32u || profile->rx_window < 32u) return -3;
  if (profile->sack_bits < 32u || profile->sack_bits > profile->tx_window) return -4;
  if (profile->descriptor_ring_depth != 64u) return -5;
  if (profile->endpoint_role == P8E_ROLE_FIXED && profile->physical_module_count != 32u)
    return -6;
  if (profile->endpoint_role == P8E_ROLE_ROTATING && profile->physical_module_count != 8u)
    return -7;
  return 0;
}

int p8e_validate_dma_cache_contract(const p8e_dma_cache_contract_t *contract) {
  if (contract == 0 || contract->cache_line_bytes == 0u) return -1;
  if (contract->cache.flush == 0 || contract->cache.invalidate == 0 ||
      contract->cache.ownership_barrier == 0) return -2;
  /* Offline P8E validates callbacks, never claims DDR/cache runtime evidence. */
  if (contract->ddr_runtime_validated != 0u) return -3;
  return 0;
}
