#include "p10_1_hal_ports.h"

#include <string.h>

int p10_1_host_hal_bind(p10_1_hal_t *destination,
                        const p10_1_hal_t *platform) {
  if (destination == NULL || platform == NULL)
    return -1;
  memcpy(destination, platform, sizeof(*destination));
  return 0;
}
