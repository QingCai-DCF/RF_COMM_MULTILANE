#include "p8e_profile.h"

static int cache_noop(void *ctx, uintptr_t address, size_t length) {
  (void)ctx; (void)address; (void)length; return 0;
}
static void barrier_noop(void *ctx) { (void)ctx; }

int main(void) {
  const p8e_profile_contract_t *z7010 = p8e_profile_contract(P8E_PROFILE_Z7010_2LANE_DEV);
  const p8e_profile_contract_t *fixed = p8e_profile_contract(P8E_PROFILE_Z7020_FIXED_8LANE);
  const p8e_profile_contract_t *rotating = p8e_profile_contract(P8E_PROFILE_Z7020_ROTATING_8LANE);
  p8e_dma_cache_contract_t cache = {
    .cache = {.ctx = 0, .flush = cache_noop, .invalidate = cache_noop,
              .ownership_barrier = barrier_noop},
    .cache_line_bytes = 64u,
    .ddr_runtime_validated = 0u,
  };
  if (p8e_validate_profile_contract(z7010) != 0 || z7010->tx_window != 32u) return 1;
  if (p8e_validate_profile_contract(fixed) != 0 || fixed->physical_module_count != 32u) return 2;
  if (p8e_validate_profile_contract(rotating) != 0 || rotating->lane_count != 8u) return 3;
  if (p8e_validate_dma_cache_contract(&cache) != 0) return 4;
  return 0;
}
