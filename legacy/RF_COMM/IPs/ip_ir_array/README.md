# IR array packaged IP

This directory is the packaged Vivado IP used by the main Zynq-7010 project.
It is constrained by the project goal file at the repository root:
`项目约束(目标）.txt`.

Do not change the goal file from this directory. RTL, simulation, PS software,
host software, and documentation changes should support the stated targets:
single-lane 4 Mbit/s bring-up first, later scaling toward up to 8 lanes for
32 Mbit/s half-duplex and 16 Mbit/s-per-direction full-duplex, with robust
recovery and PS-to-PC TCP communication.

## Important files

- `src/`: synthesizable RTL and IP support files.
- `sim/tb_ir_array_loopback_single_lane.sv`: internal two-node single-lane
  loopback testbench.
- `sim/tb_ir_array_loopback_impair_single_lane.sv`: internal two-node
  single-lane loopback testbench with one dropped data frame and one dropped
  final ACK.
- `sim/tb_ir_array_loopback_crc_single_lane.sv`: internal two-node single-lane
  loopback testbench with one deliberately corrupted 4PPM DATA symbol.
- `sim/tb_ir_phy_rate_model.sv`: PHY-rate model check for the current 64 MHz,
  `CNT_CHIP_MAX=7`, single-lane 4 Mbit/s raw-rate target, plus projected
  eight-lane 32 Mbit/s half-duplex and 4+4 lane 16 Mbit/s-per-direction
  full-duplex raw PHY targets.
- `sim/tb_ir_array_loopback_retry_exhaust_single_lane.sv`: internal two-node
  single-lane testbench with a permanent A-to-B optical outage.
- `sim/tb_ir_array_loopback_recover_after_exhaust_single_lane.sv`: internal
  two-node single-lane testbench that restores the link after retry exhaustion
  and verifies the next packet can be transferred.
- `sim/tb_ir_array_loopback_burst_single_lane.sv`: internal two-node
  single-lane burst testbench with five consecutive packets and RX
  AXI-Stream backpressure.
- `sim/tb_ir_array_loopback_long_packet_latency.sv`: internal two-node
  single-lane long-packet testbench with one 256-byte payload split into
  sixteen 16-byte fragments and no-retry latency measurement.
- `sim/tb_ir_payload_throughput_budget.sv`: static throughput-budget model
  that separates raw PHY capacity from optimistic effective payload throughput
  for the current 16-byte fragment format.
- `sim/tb_ir_array_loopback_bidirectional_single_lane.sv`: internal two-node
  single-lane bidirectional testbench that sends one packet A-to-B and one
  packet B-to-A with RX AXI-Stream backpressure.
- `sim/tb_ir_array_loopback_full_duplex_lane_partition.sv`: internal two-node
  four-lane testbench with lane 0/1 assigned to A-to-B and lane 2/3 assigned
  to B-to-A, so both directions transmit continuous packet pairs at the same
  time.
- `sim/tb_ir_axi_regs_config_masks.sv`: AXI-Lite register testbench for the
  backward-compatible combined lane mask and the independent RX lane mask.
- `sim/tb_ir_array_loopback_multi_lane.sv`: internal two-node four-lane
  loopback testbench that checks continuous packet transfer with concurrent
  fragment issue across all lanes.
- `sim/tb_ir_array_loopback_multi_lane_impair.sv`: internal two-node
  four-lane loopback testbench with a lane-0 A-to-B outage, one dropped
  B-to-A complete ACK, and RX AXI-Stream backpressure.
- `sim/tb_ir_array_loopback_multi_lane_degrade.sv`: internal two-node
  four-lane loopback testbench that switches lane masks between packets to
  cover 4-lane, 3-lane, 2-lane, 1-lane, and restored 4-lane operation.
- `sim/tb_ir_array_loopback_multi_lane_route.sv`: internal two-node four-lane
  loopback testbench with rotating-side TX/RX lane correspondence changes
  between packets.
- `sim/tb_ir_array_loopback_multi_lane_autoroute.sv`: internal two-node
  four-lane loopback testbench where only one A-to-B optical source lane is
  reachable per packet and the reachable lane changes between packets.
- `sim/tb_ir_array_loopback_rotating_autoroute_stress.sv`: extended
  rotating-sector autoroute stress test with 600 rpm / 20 cm target metadata
  and 40 continuous packets over ten four-sector route-change cycles.
- `sim/tb_ir_rotating_autoroute_soak_model.sv`: two-hour equivalent rotating
  autoroute search model covering 72000 rotations and 288000 sector changes at
  the 600 rpm / 20 cm target.
- `sim/tb_ir_protocol_defensive_cases.sv`: protocol-manager unit test for
  duplicate DATA suppression, mismatched in-progress DATA rejection, and
  wrong-session/stale ACK rejection.
- `sim/tb_ir_array_top_axi_lane_counters.sv`: internal two-node AXI-wrapper
  testbench that drives AXI-Lite configuration plus AXI-Stream payloads through
  `ir_array_top_axi`, then reads lane-health counters from the wrapper
  registers.
- `run_loopback_single_lane.ps1`: repeatable XSim entry for the current
  single-lane bring-up target and the multi-lane expansion check.
- `repackage_ip.tcl`: Vivado IP-XACT repackaging script after RTL edits.
- `component.xml`: packaged IP metadata. The active repackaged revision is 14.

## Repeat the internal loopback simulation

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1'
```

The script uses Vivado 2023.1 tools by default:

```text
D:\Xilinx\Vivado\2023.1\bin
```

Override the tool path or job count if needed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -VivadoBin 'D:\Xilinx\Vivado\2023.1\bin' -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_SINGLE_LANE_PASS
```

Run the PHY-rate model check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test phy_rate -Jobs 16
```

The expected pass signature is:

```text
IR_PHY_RATE_MODEL_PASS
```

This case verifies that the simulation clock is 64 MHz and that
`CNT_CHIP_MAX=7` 4PPM timing gives a 4.000 Mbit/s single-lane raw PHY rate.
The same static check also verifies the raw multi-lane capacity basis for the
final targets: eight parallel lanes provide 32.000 Mbit/s half-duplex raw PHY
capacity, and a 4+4 lane partition provides 16.000 Mbit/s raw PHY capacity per
direction in full-duplex mode. This is PHY-capacity evidence, not measured
end-to-end payload throughput.
The frame-airtime check includes the transmitter's one-symbol preamble gap, so
the current 30-byte DATA frame occupies 4992 PHY clock cycles, or 78.000 us at
64 MHz.

Run the payload-throughput budget model:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test payload_budget -Jobs 16
```

The expected pass signature is:

```text
IR_PAYLOAD_THROUGHPUT_BUDGET_PASS
```

This case keeps the final-rate evidence honest: with 16-byte fragments, each
DATA frame carries 16 payload bytes inside a 30-byte protocol frame, then still
pays 4PPM preamble, one preamble-gap symbol, PHY CRC, and frame-tail silence.
The model therefore marks the current 32/16 Mbit/s result as raw-PHY capacity
evidence only. Under the current frame format, optimistic no-ACK payload
throughput is below the final 32 Mbit/s half-duplex and 16 Mbit/s-per-direction
full-duplex payload targets, so payload or end-to-end throughput acceptance
must use later design changes and real measurement.

Run the impairment/recovery case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test impair -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_IMPAIR_SINGLE_LANE_PASS
```

This case forces the first A-to-B data frame to be lost, then forces one
B-to-A final complete ACK to be lost. Passing means the sender retransmits
after timeout, the receiver delivers the payload once, and the sender recovers
from the missing final ACK through the duplicate-fragment complete-ACK path.

Run the CRC error/recovery case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test crc -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_CRC_SINGLE_LANE_PASS
```

This case changes one valid 4PPM DATA symbol into another valid 4PPM symbol.
Passing means the receiver detects the physical CRC mismatch, rejects the bad
frame, does not deliver corrupted payload, and the sender recovers by timeout
retransmission.

Run the retry-exhaustion case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test exhaust -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_RETRY_EXHAUST_SINGLE_LANE_PASS
```

This case holds the A-to-B optical input idle for the whole run. Passing means
the sender attempts the original frame plus the configured retries, asserts the
retry-exhausted error state, and does not falsely report TX completion.

Run the recovery-after-retry-exhaustion case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test recover_after_exhaust -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_RECOVER_AFTER_EXHAUST_SINGLE_LANE_PASS
```

This case sends one packet while the A-to-B link is held in outage until retry
exhaustion, then restores the link and sends a second packet. Passing means the
failed transfer does not leave stale TX/RX state that blocks later traffic.

Run the consecutive-packet/backpressure case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test burst -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_BURST_SINGLE_LANE_PASS
```

This case sends five packets with lengths 1, 16, 17, 48, and 64 bytes while
the receiver periodically deasserts `m_axis_rx_tready`. Passing means all
packets are delivered once, in order, byte-accurate, with matching TX/RX done
counts and no stuck packet or reassembly state.

Run the 256-byte single-lane long-packet latency case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test long_packet -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_SINGLE_LANE_256B_LATENCY_PASS
```

This case sends one 256-byte packet over one lane with 16-byte fragments.
Passing means exactly sixteen DATA fragments are received, all 256 bytes are
delivered once and in order, and the no-retry receive and final-ACK completion
latencies stay in the millisecond range.

Run the bidirectional single-lane case:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test bidir -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_BIDIR_SINGLE_LANE_PASS
```

This case sends one packet from A to B, waits for delivery and TX completion,
then sends one packet from B to A. Passing means the same single-lane PHY and
reliability state machines can complete traffic in both directions without
byte corruption, duplicate delivery, stale reassembly state, or stuck TX/RX
contexts.

Run the lane-partition full-duplex digital check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test fdx -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_FULL_DUPLEX_LANE_PARTITION_PASS
```

This case uses four internal lanes with independent TX/RX lane masks. A
transmits on lanes 0/1 while receiving on lanes 2/3; B transmits on lanes 2/3
while receiving on lanes 0/1. Passing means both directions can carry eight
continuous 64-byte packet pairs concurrently, with at least two in-flight
fragments per direction, no byte corruption, no duplicate delivery, no
packet-count drift, and no stuck TX/RX contexts. This is the digital protocol
evidence toward the later 16 Mbit/s-per-direction full-duplex target; physical
TFDU direction assignment, 4+4 lane scaling, and board wiring still need
hardware verification.

Run the AXI-Lite config-mask register check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test regs -Jobs 16
```

The expected pass signature is:

```text
AXI_REGS_CONFIG_MASKS_PASS
```

This case verifies that writing the legacy `LANE_MASK` register still updates
both TX and RX masks for single-lane bring-up compatibility, and that the new
`RX_LANE_MASK` register can independently override the RX lane assignment for
future lane-partition full-duplex hardware tests.
It also checks the lane-health counter readback registers:
`0x2c` TX lane attempt count, `0x30` RX good-frame count, `0x34` RX CRC-error
count, and `0x38` RX overflow/overrun-error count. These counters are packed
as one saturating byte per lane and clear when sticky status is cleared.

Run the AXI wrapper lane-health counter simulation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test axi_counters -Jobs 16
```

The expected pass signature is:

```text
AXI_TOP_LANE_COUNTERS_PASS
```

This case instantiates two `ir_array_top_axi` wrappers, enables them through
AXI-Lite, sends a 16-byte AXI-Stream payload from A to B, verifies payload
delivery through the wrapper FIFOs, reads the TX/RX lane-health counters from
AXI-Lite, checks that data and ACK paths increment, checks that CRC/error
counters stay zero, and confirms sticky-clear writes also clear the counters.

Run all internal IP tests:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test all -Jobs 16
```

The expected final pass signature is:

```text
ALL_IR_ARRAY_TESTS_PASS
```

Run only the four-lane expansion check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test multi -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_MULTI_LANE_PASS
```

This case sends eight continuous 64-byte packets through a four-lane internal
loopback. Passing means all four lanes are used on every packet, four lane
transmitters are busy concurrently, four fragments are in flight concurrently,
and each reassembled payload is delivered once and intact without packet-count
drift. The main Vivado project can still instantiate the IP as `LANE_COUNT=1`
for the current 4 Mbit/s bring-up stage.

Run the four-lane unstable-link recovery check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test multi_impair -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_MULTI_LANE_IMPAIR_PASS
```

This case sends a 64-byte packet over four lanes, holds lane 0 idle during its
first A-to-B data frame, drops one B-to-A complete ACK, and periodically
deasserts the receiver AXI-Stream ready signal. Passing means the protocol
keeps the other lanes active, retransmits the missing fragment, delivers the
payload once and intact, recovers from the missing final ACK, and leaves no
stuck TX/RX context.

Run the multi-lane degradation and restoration check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test degrade -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_MULTI_LANE_DEGRADE_PASS
```

This case sends five packets while changing the enabled lane mask between
packets: 4 lanes, 3 lanes, 2 lanes, 1 lane, then restored 4 lanes. Passing
means no disabled lane is used, the expected number of enabled lanes and
in-flight fragments are exercised for each packet, all payloads arrive once
and intact, and lane-mask changes between packets leave no stale protocol
state.

Run the rotating-side route-change check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test route -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_MULTI_LANE_ROUTE_PASS
```

This case changes the physical mapping between TX lanes and RX lanes between
packets. Passing means data frames may arrive on RX lanes whose indices no
longer match the transmitting lane, ACK frames may return through a different
mapping, and the protocol still completes packet delivery without byte
corruption, duplicate delivery, disabled-lane assumptions, or stuck state.
It is the current digital evidence for rotating-side automatic path tolerance;
the AXI lane-health counters provide the observation path for PS/PC-side route
scoring during hardware bring-up.

Run the rotating-side automatic route-finding recovery check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test autoroute -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_MULTI_LANE_AUTOROUTE_PASS
```

This case keeps all TX/RX lanes enabled, but for each packet only one A-to-B
source lane is actually optically reachable. The reachable source lane changes
between packets. Passing means the sender first exercises failed routes, then
uses timeout retransmission plus lane round-robin to find the currently
reachable route, delivers the payload once and intact, and receives the ACK
through a separately mapped B-to-A path.
The AXI wrapper exposes lane-health counters so PS software and the PC tool can
observe which lanes were tried, which lanes received valid frames, and which
lanes reported CRC or receive-buffer errors during rotating-side route changes.

Run the continuous rotating-sector autoroute stress check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test rotating_autoroute -Jobs 16
```

The expected pass signature is:

```text
LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS
```

This case records the 600 rpm, 20 cm shaft target metadata and models ten
repeated four-sector route-change cycles with 40 continuous packets. Each
packet has only one currently reachable A-to-B source lane, all lanes remain
enabled, and each packet must exercise at least one failed route before finding
the reachable path. It is scaled simulation evidence for continuous automatic
path finding under rotating-style correspondence changes; it is not a
substitute for later 20 cm, 600 rpm optical/shaft validation or the 2-hour soak.

Run the two-hour equivalent rotating autoroute search model:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test rotating_soak_model -Jobs 16
```

The expected pass signature is:

```text
ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS
```

This model checks the target metadata for a 20 cm shaft at 600 rpm, then
exercises 72000 rotations and 288000 four-sector route changes. For each sector
only one source lane is treated as reachable; the round-robin route search must
find it within the configured retry budget while also covering deterministic
complete-ACK loss events. This is long-horizon autoroute coverage for the
simulation phase, not measured optical throughput or real-time shaft soak
evidence.

Run the protocol defensive-behavior unit check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\IPs\ip_ir_array\run_loopback_single_lane.ps1' -Test defensive -Jobs 16
```

The expected pass signature is:

```text
IR_PROTOCOL_DEFENSIVE_CASES_PASS
```

This case directly drives the TX/RX protocol managers. It verifies that a
duplicate DATA fragment and a duplicate completed packet do not create extra
delivered payload, that a mismatched in-progress DATA frame raises
`protocol_error` without false delivery, and that wrong-session or stale ACKs
do not advance the transmitter state.

The detailed simulation log is written under:

```text
IPs/ip_ir_array/.sim_<test>_<suffix>/<test>_<suffix>.sim/sim_1/behav/xsim/simulate.log
```

## Repackage after RTL edits

After editing files in `src/`, repackage the IP before relying on the main
Vivado project to pick up the new implementation:

```powershell
& 'D:\Xilinx\Vivado\2023.1\bin\vivado.bat' -mode batch -source '.\IPs\ip_ir_array\repackage_ip.tcl'
```

Then refresh or upgrade the IP in the main project and rebuild synthesis,
implementation, bitstream, XSA, and PS software as needed.

## Current verified evidence

- Internal PHY-rate model simulation passes for the current and future-lane
  settings: 64 MHz clock, `CNT_CHIP_MAX=7`, 4.000 Mbit/s raw 4PPM PHY rate per
  lane, 32.000 Mbit/s raw PHY capacity with eight half-duplex lanes, and
  16.000 Mbit/s raw PHY capacity per direction with a 4+4 full-duplex lane
  partition. The measured 30-byte DATA-frame busy window is 4992 cycles
  (78.000 us), including the transmitter's one-symbol preamble gap. The shared
  PHY simulation clock has been aligned to the exact 64 MHz target rather than
  the earlier 62.5 MHz approximation.
- Payload-throughput budget simulation passes and records the current
  rate-evidence boundary: 16-byte fragments produce 30-byte DATA frames, so
  the present 32/16 Mbit/s result is raw-PHY capacity evidence only. Including
  the preamble-gap symbol, the model reports optimistic no-ACK payload upper
  bounds of 13.128205 Mbit/s for 8-lane half-duplex and 6.564103 Mbit/s per
  direction for 4+4 lane full-duplex, keeping final payload/end-to-end
  throughput as a later measured acceptance item rather than an implied result
  of the raw-rate model.
- Internal single-lane loopback simulation passes for a 48-byte packet split
  into three 16-byte fragments.
- Internal single-lane impairment simulation passes with one dropped data
  frame and one dropped final ACK, covering timeout retransmission and final
  ACK recovery.
- Internal single-lane CRC simulation passes with one corrupted 4PPM symbol,
  covering CRC rejection of bad data and timeout retransmission recovery.
- Internal single-lane retry-exhaustion simulation passes under a permanent
  A-to-B outage, covering explicit retry-exhausted error reporting with no
  false payload delivery.
- Internal single-lane recovery-after-exhaustion simulation passes by forcing
  one packet to retry-exhaust under outage, then restoring the link and
  successfully delivering a new 32-byte packet, covering recovery to usable
  state after an unrecoverable transfer failure.
- Internal single-lane burst simulation passes for five consecutive packets
  under RX AXI-Stream backpressure, covering packet order, length integrity,
  byte integrity, done counts, and no stuck packet/reassembly state.
- Internal single-lane 256-byte long-packet latency simulation passes with
  sixteen 16-byte fragments. The current no-retry digital loopback evidence
  shows receive completion at about 1.958 ms and final ACK completion at about
  2.048 ms under the exact 64 MHz simulation clock.
- Internal single-lane bidirectional simulation passes for A-to-B then B-to-A
  packets under RX AXI-Stream backpressure, covering both traffic directions
  for the current half-duplex bring-up mode.
- Internal four-lane lane-partition simulation passes with eight continuous
  bidirectional 64-byte packet pairs over a 2+2 lane split, covering the
  digital protocol path and multi-packet state stability needed toward the
  later 8-lane, 16 Mbit/s-per-direction full-duplex target.
- AXI-Lite register simulation passes for legacy combined lane-mask writes and
  independent RX lane-mask writes, covering the PS/PC configuration path needed
  for future lane-partition full-duplex bring-up.
- Internal four-lane loopback simulation passes with eight continuous 64-byte
  packets, four concurrent in-flight fragments per packet, and each lane used
  on every packet, covering the expansion path and multi-packet state stability
  needed toward later 8-lane, 32 Mbit/s half-duplex work while preserving the
  current single-lane configuration.
- Internal four-lane unstable-link simulation passes with one lost lane-0 data
  frame, one lost complete ACK, and RX backpressure, covering multi-lane
  timeout retransmission, duplicate suppression, final-ACK recovery, and
  no stuck TX/RX context.
- Internal multi-lane degradation simulation passes across 4-lane, 3-lane,
  2-lane, 1-lane, and restored 4-lane packet transfers, covering mask-based
  lane fallback/restoration without disabled-lane use, stale state, byte
  corruption, or duplicate delivery.
- Internal multi-lane route-change simulation passes with A-to-B and B-to-A
  lane correspondence changing between packets, covering the protocol's
  ability to accept data and ACK frames through changing rotating-side lane
  mappings instead of fixed lane-index pairs.
- Internal multi-lane automatic route-finding simulation passes with all lanes
  enabled while only one A-to-B source lane is physically reachable per packet.
  The sender retries failed routes and eventually finds the currently reachable
  route by timeout retransmission and lane round-robin, with no duplicate
  delivery or stuck state.
- Internal rotating-sector autoroute stress simulation passes with explicit
  600 rpm / 20 cm target metadata for 40 continuous packets over ten
  four-sector route-change cycles. Each packet first exercises failed routes
  and then recovers through timeout retransmission plus lane round-robin,
  covering sustained automatic path finding under rotating-style correspondence
  changes.
- The two-hour equivalent rotating autoroute search model passes for 72000
  rotations and 288000 sector changes at the 600 rpm / 20 cm target. It covers
  all route maps, all reachable source lanes, repeated failed-route recovery,
  and deterministic complete-ACK loss within the retry budget.
- Protocol defensive simulation passes for duplicate DATA suppression,
  mismatched in-progress DATA rejection, wrong-session ACK rejection, and stale
  ACK rejection, covering the requirement that duplicate/expired/abnormal
  protocol events must not be accepted as valid payload.
- AXI-Lite lane-health counter readback is covered for TX attempts, RX good
  frames, RX CRC errors, and RX overflow/overrun errors. The counters support
  PS/PC route-health observation for rotating-side automatic path selection.
- AXI-wrapper lane-health counter simulation passes with two `ir_array_top_axi`
  instances, AXI-Lite configuration, AXI-Stream payload transfer, counter
  readback, zero error-counter checks, and clear-to-zero behavior.
- The repackaged IP removes the previous IR FIFO RAMB18 asynchronous-control
  critical warning in the generated main-project implementation.
- The latest main-project route and bitstream build passed timing with no
  critical warnings.

The current reduced target is simulation-only. Board-level TFDU optical
communication, PS-to-PC TCP/DHCP behavior, rotating shaft operation, 2-hour
soak, and final multi-lane throughput are outside this simulation-stage
acceptance scope.
