# Known Issues From RF_COMM

- Current usable legacy configuration is `LANE0_DEGRADED_RELIABLE_2LANE_STATIC`.
- Payload lane mask is `0x1`.
- ACK lane mask is `0x1`.
- `AB_L1` is classified as raw-layer `NO_RX_RAW_PULSE`.
- Old active top XDC conflicts with IP-local legacy XDC.
- Legacy wrapper/BD/IP copies may drift and are reference-only.
- Session/mask confusion can create protocol-layer false failures.
- B0 endpoint is a test-only peer, not final remote protocol hardware.
- Ethernet, rotation, real 8-lane, soak, and lane1 recovery are not proven by imported evidence.
