#ifndef TCP_BRIDGE_H
#define TCP_BRIDGE_H

#include "ir_hw.h"

int tcp_bridge_start(ir_hw_t *hw, unsigned short port);
void tcp_bridge_poll(void);

#endif

