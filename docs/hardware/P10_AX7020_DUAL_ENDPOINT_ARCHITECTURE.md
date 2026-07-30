# P10 AX7020 dual-independent-endpoint architecture

## Scope and acceptance boundary

P10 builds two role-bound AX7020 images from common RTL.  The fixed image owns
`F0/F1`; the rotating-role image owns `R0/R1`.  Each image contains its own
Zynq PS, DDR controller, AXI DMA, descriptor state, transport state, payload
storage, clocks, resets, and two physical TFDU interfaces.  There is no shared
RAM, AXI link, Ethernet link, or control wire between the two endpoints.

This is an offline design/build result for existing requirement
`SYS-ARCH-001`.  That requirement remains `PENDING` because independent
physical-board identity, real DDR/DMA operation, optical transfer, and reset
recovery have not been measured.  No Z7020 hardware or product scope is
promoted by this document.

## Role binding

| Image role | RTL role | Build ID | Profile ID | Local modules | Direction value that makes it the sender |
|---|---:|---:|---:|---|---:|
| AX7020-F | `DEPLOYMENT_ROLE=1` | `0x50313046` | `0x702000F0` | F0, F1 | `0` (F to R) |
| AX7020-R | `DEPLOYMENT_ROLE=2` | `0x50313052` | `0x702000A0` | R0, R1 | `1` (R to F) |

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

P10 endpoint mode uses bounded DATA bursts of four frames.  The last DATA frame
of a burst, or the final frame of an object, carries the protocol turnaround
request in DATA flag bit 1.  The sender then stops scheduling DATA and waits
for an ACK.  The receiver delays its timer ACK until the explicit boundary and
returns cumulative ACK/SACK plus its local receiver credit.  Valid ACK receipt
releases the sender for the next burst.  Timeout retains selective-repeat retry
behavior.

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

## Safety boundary and hardware admission

The functional RTL retains the existing exact 1 ms rolling-duty accountant,
continuous-high guard, stuck-high guard, shutdown latch, and final TX kill.
Endpoint mode observes and arms only the two role-local physical modules.  A
separate shutdown image drives `Mode=HIGH`, `SD=HIGH`, and `Txd=LOW` after PL
configuration.

Hardware admission is nevertheless `false`.  Open severe blocker
`P10-SAFETY-POWERUP-001` establishes that the supplied board/module schematics
do not guarantee passive `Txd=LOW` and `SD=HIGH` while the FPGA is unconfigured,
reset, open-circuit, or partially powered.  `P10-RX-B-R29-001` also leaves the
TFDU Rxd high level at J10 pin 26 outside the supplied datasheet's guaranteed
load point.  A configured shutdown image cannot close either electrical gap.

Accordingly, the offline bitstreams and ELFs are build artifacts only.  They
must not be programmed or executed until the blocker is resolved and the two
physical boards can be uniquely bound to the fixed and rotating roles.

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
