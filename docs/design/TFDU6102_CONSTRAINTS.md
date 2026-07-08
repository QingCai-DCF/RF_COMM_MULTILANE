# TFDU6102 Constraints

TFDU_DATASHEET_COPY=COPIED

- `Txd`: active high; reset/default idle must be `0`.
- `Rxd`: low active; RTL internal raw pulse must use `~rxd_sync`.
- `SD`: high means shutdown; active operation drives `0`.
- `Mode`: static high-speed policy uses `Mode=1`; dynamic programming must be Hi-Z isolated if introduced later.
- Startup: after `SD` changes from `1` to `0`, TX/RX FSMs must wait at least 500 us before valid operation.
- Long-high guard: `Txd` continuous high must stay below the device 80 us limit; this project uses a lower static guard.
- TX duty: rolling-window duty count must force shutdown on limit violation.
- IRED current is board-level, typically hundreds of mA; do not assume weak GPIO LED loading.
- Recommended decoupling: C1/C3 4.7 uF and C2 0.1 uF are board prerequisites.
- FIR pulse model: 125 ns optical pulse maps to roughly 100-140 ns low-active `Rxd`; 250 ns maps to roughly 225-275 ns.
- Jitter model: default injectable leading-edge jitter is 20 ns.
