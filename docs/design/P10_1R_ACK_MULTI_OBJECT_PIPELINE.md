# P10.1R ACK window and multi-object pipeline

Status: offline implementation and model; direct performance validation pending.

The frozen remediation defaults are a shared two-lane 32-frame selective-repeat window, `ENDPOINT_BURST_FRAMES=32`, `ACK_THRESHOLD=32`, a 1 ms ACK maximum delay, and a 37,120-cycle (580 us) direction guard. Receiver-credit pressure, a blocking gap, fault/control, explicit stop, or timer expiry may close the window early. Every physical retransmission carries an explicit DATA-to-ACK direction boundary, guaranteeing a fresh cumulative ACK after a late gap fill even when an object-final frame arrived earlier on the other lane. An object boundary does not itself request an ACK, reverse optical direction, re-prime the receiver, drain the pipeline, or exchange an optical ready pulse.

The existing exact clock-aligned 1 ms duty accountant and complete-next-frame headroom reservation remain authoritative. P10.1R removes the redundant endpoint fixed post-frame delay; the legacy P9 monolithic role retains its historical 20,480-cycle delay. This removes double-counting without changing the `<20%` hard limit, `<=18%` target, 1 us continuous-high limit, final TX kill, or any permit path.

The PS runtime uses four 256 KiB buffers, a 32-entry SG descriptor ring, batches of up to eight descriptors, and one board-autonomous stream command per direction. Four buffers/descriptors are prepared before the first object. During transfer, released slots are refilled, object N+1 is started before CPU integrity verification of N, and incremental CRC32/SHA256 plus atomic stream commit remain enforced. The single final stream-level coordination exchange replaces per-object optical ready round trips. Host control is outside the per-object fast path; the contract caps blocking commands at four per direction and requires at least 1,000 segments per command.

The corrected airtime model includes two 4 Mbit/s lanes, 247-byte L1 payloads, 215 useful RFAP bytes per frame, exact duty, DATA/ACK airtime, the shared post-TX/direction guard, PER/retry, and DMA/PS overlap. Post-TX admission guard and direction quiet describe the same physical interval and are not added as unrelated overhead. The offline candidate predicts 4.091 Mbit/s in each half-duplex direction, clearing the 4.0 Mbit/s feasibility gate but not creating a hardware PASS.

Any change to RTL, protocol, firmware, XSA, BSP, or ELF creates new immutable artifacts and invalidates inheritance from prior P10/P10.1 hardware results.
