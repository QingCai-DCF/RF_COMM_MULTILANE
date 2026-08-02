# P10 AX7020 dual-independent-endpoint architecture

## Scope and acceptance boundary

P10 builds two role-bound AX7020 images from common RTL.  The fixed image owns
`F0/F1`; the rotating-role image owns `R0/R1`.  Each image contains its own
Zynq PS, DDR controller, AXI DMA, descriptor state, transport state, payload
storage, clocks, resets, and two physical TFDU interfaces.  There is no shared
RAM, AXI link, Ethernet link, or control wire between the two endpoints.

This architecture and its content-addressed artifacts are ready for the
current, stationary P10 FastTrack hardware campaign.  The hardware results
remain `PENDING` until one complete evidence run directly measures independent
DDR/DMA operation, optical transfer, reset recovery, and the 1800-second
stationary interval.  No later Z7020 geometry, rotation, Ethernet, or product
scope is promoted by this document.

## Role binding

| Image role | RTL role | Build ID | Profile ID | Local modules | Direction value that makes it the sender |
|---|---:|---:|---:|---|---:|
| AX7020-F | `DEPLOYMENT_ROLE=1` | `0x50313046` | `0x702000F0` | F0, F1 | `0` (F to R) |
| AX7020-R | `DEPLOYMENT_ROLE=2` | `0x50313052` | `0x702000A0` | R0, R1 | `1` (R to F) |

The current physical binding is keyed only by the stable JTAG cable serial:

- AX7020-F: `210249855178`;
- AX7020-R: `210512180081`.

The binding rule is independent of transient XSDB target order.  Each active
stage must rediscover one `xc7z020`, one APU, and one Cortex-A9 #0 beneath each
authorized serial before it can reset, program, download, or access memory.

Both roles expose identity magic `0x5031305A`, register-map version `P9-3`,
AXI-Lite registers at `0x43C00000`, and a role-local scatter-gather AXI DMA at
`0x40400000`.  The fixed and rotating XSA/BSP/ELF outputs are built separately,
and their role-specific identity is checked before an artifact is frozen.

The physical lane map is fixed and non-crossed:

- lane0 is F0 to/from R0, using J10 position A;
- lane1 is F1 to/from R1, using J10 position B;
- allowed lane masks are `0x1`, `0x2`, and `0x3` only.

The complete connector/package-pin/bank/VCCO mapping is maintained in
`config/hardware/p10_active_wiring.yaml` and in the two independent AX7020
profile directories.  No AX7010 XDC is a P10 build input.

## Data and control ownership

Each endpoint's PS publishes descriptors to its own DDR ring.  Its local AXI
DMA is the only block that moves that endpoint's object bytes between DDR and
the local PL AXI-Stream boundary.  The sending endpoint accepts MM2S stream
data; the receiving endpoint produces S2MM stream data.  A receiver does not
accept an ingress object stream, and a sender does not report a locally
received object.  Consequently, an end-to-end object can cross the node
boundary only as encoded DATA frames through a paired TFDU optical path.

Selective-repeat state, receiver credit, SACK state, session state, retry
state, and completion state are instantiated separately in each FPGA.  A
session/abort reset also invalidates unsent ACK snapshots so an ACK from the
previous object/session cannot be emitted after ownership changes.

## Half-duplex turnaround

P10.1R endpoint mode uses bounded DATA bursts of 32 frames.  The last DATA frame
of a burst, or the final frame of an object, carries the protocol turnaround
request in DATA flag bit 1.  The sender then stops scheduling DATA and waits
for an ACK. Because the two serializers can finish out of sequence, the
receiver records the tagged frame sequence and waits until its wrap-safe
cumulative RX base has advanced past that sequence before returning cumulative
ACK/SACK plus local receiver credit. A 64,000-cycle fallback returns SACK state
for a genuinely missing earlier frame, still well before the 4,000,000-cycle
retransmission timeout. Normal no-loss traffic is event-driven and does not pay
a fixed 1 ms fallback. Valid ACK receipt releases the sender for the next
burst; timeout retains selective-repeat retry behavior.

The turnaround mechanism is local protocol state carried over the optical
frames; it is not a shared scheduler and introduces no second permit channel.
`DEPLOYMENT_ROLE=0` retains the accepted P9 monolithic fixture behavior.  The
portable regression therefore runs both a two-instance P10 testbench and the
legacy P9 transport test from the modified common RTL.

## Clock, reset, and build structure

The functional block design uses the exact part `xc7z020clg400-2` and the
official-derived AX7020 PS preset:

- 64 MHz protocol/TFDU clock;
- 100 MHz AXI DMA and HP0 clock;
- 50 MHz PS GP0/AXI-Lite clock;
- AXI clock converters at both control and stream boundaries;
- independent reset synchronizers in every clock domain;
- 32-bit DDR3 `MT41J256M16 RE-125` at the official AX7020 timing/pin preset;
- Ethernet, USB, SD, and QSPI disabled; UART1 retained for local diagnostics.

Functional builds generate a role-bound bitstream and XSA.  Vitis then derives
a role-bound BSP and standalone ELF from that role's XSA.  The runtime is linked
entirely below the `0x00020000` OCM boundary so the software image can start and
verify identity without relying on an already-tested DDR data path.  Content
addresses cover every RTL/profile/build input and the produced artifact bytes.

## Safety boundary and scoped hardware admission

The functional RTL retains the existing exact 1 ms rolling-duty accountant,
continuous-high guard, stuck-high guard, shutdown latch, and final TX kill.
Endpoint mode observes and arms only the two role-local physical modules.  A
separate shutdown image drives `Mode=HIGH`, `SD=HIGH`, and `Txd=LOW` after PL
configuration.

The FastTrack goal grants current-run hardware authorization for this exact
already-wired, already-powered, stationary two-board fixture.  The configured
shutdown images, role-specific artifacts, immutable hashes, and stable JTAG
serial binding therefore admit the scoped P10 run without an intentional power
cycle.  Every stage is bracketed by independent programming of both shutdown
images; normal exit, failure, timeout, Ctrl+C, and wrapper failure all execute
the same dual-shutdown path.  A stage cannot arm until both role runtimes report
safe boot with `Txd request=0`, `endpoint armed=0`, active TX mask zero, final
TX kill active, no autonomous physical TX count, and no sticky safety fault.

`P10-SAFETY-POWERUP-001` is not erased or promoted.  Passive fail-low behavior
while the FPGA is unconfigured, open-circuit, or partially powered remains
`PENDING_D17`; this campaign neither intentionally power-cycles a board nor
claims that requirement.  `P10-RX-B-R29-001` likewise remains a documented
electrical-guarantee gap.  The user's prior successful use of the same TFDU
small boards on the byte-identical AX7010 J10 circuit is accepted as fixture
compatibility context, not as a replacement for later product evidence.

The active wrapper is `scripts/p10_hardware_runtime.py`.  Its machine-readable
authorization binds the two serials, all eight bit/XSA/ELF inputs, every SHA256,
the exact stage plans, lane masks `0x1/0x2/0x3`, the 1800-second bound, and the
prohibitions on Ethernet, movement, rotation, rewiring, and intentional power
cycling.

## Offline verification records

The final evidence checkpoint binds this document to:

- `evidence/generated/p10_dual_endpoint_regression/summary.json`;
- `evidence/generated/p10_ax7020_shutdown_build_summary.json`;
- `evidence/generated/p10_ax7020_functional_build_summary.json`;
- `evidence/generated/p10_ax7020_ps_runtime_build_summary.json`;
- `evidence/generated/p10_dual_endpoint_architecture_audit.json`;
- `evidence/generated/p10_fasttrack_final_summary.json`.

These records can establish offline simulation, synthesis, route, timing, DRC,
CDC severity, XSA identity, BSP/ELF construction, and artifact hashes.  They do
not establish safe boot, shutdown confirmation on hardware, optical rate,
crosstalk, real DMA/DDR/cache correctness, application objects, restart
recovery, throughput, or the 30-minute stationary run.
