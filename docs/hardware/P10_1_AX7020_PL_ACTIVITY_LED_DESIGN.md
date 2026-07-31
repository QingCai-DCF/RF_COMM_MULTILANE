# P10.1 AX7020 PL activity LED design

## Scope and evidence boundary

This change adds four active-low AX7020 PL user LEDs as human-visible,
non-intrusive lane activity monitors. It is an offline-only follow-up to the
frozen `p10.1-offline-performance-ready` checkpoint. No FPGA was programmed,
no JTAG or hardware target was opened, and no TFDU pin was driven while
developing or verifying this change.

The LED-enabled bitstreams are new artifacts. Existing P10/P10.1 hardware PASS
records remain valid only for their original content-addressed artifacts; they
do not validate these bitstreams. LED state is not safety evidence and is not
proof of electrical, protocol, or optical success.

## Fixed mapping

The port is `pl_activity_led_n_o[3:0]`; `0` lights the corresponding onboard
LED and `1` turns it off.

| LED | Package pin | Bank / VCCO | Common meaning | Fixed role | Rotating role |
|---|---|---|---|---|---|
| LED1 / bit 0 | `M14` (`IO_L23P_T3_35`) | 35 / 3.3 V | lane0 TX | F0 TX | R0 TX |
| LED2 / bit 1 | `M15` (`IO_L23N_T3_35`) | 35 / 3.3 V | lane0 RX | F0 RX | R0 RX |
| LED3 / bit 2 | `K16` (`IO_L24P_T3_35`) | 35 / 3.3 V | lane1 TX | F1 TX | R1 TX |
| LED4 / bit 3 | `J16` (`IO_L24N_T3_35`) | 35 / 3.3 V | lane1 RX | F1 RX | R1 RX |

Both role-specific AX7020 XDC files independently constrain these pins as
`LVCMOS33`, `DRIVE 4`, `SLEW SLOW`. No AX7010 XDC is reused.

Pin and polarity authority is the read-only ALINX AX7020 User Manual V2.2,
section 7.6 (lines 1250–1285 in its RST source), SHA256
`d5451ad97ad1b54edd646b3258d03c95b4f485d47b1da1a58a7aea2526b20f16`.
That section identifies all four pins, Bank 35, and low-active operation.
The official AX7020 schematic V2.0 and official package-pin workbook are the
cross-check sources recorded in
`config/hardware/p10_1_ax7020_pl_activity_leds.yaml`.

## Event semantics

TX activity is sampled from the role-local final `tfdu_txd_o` output, after
endpoint arm, shutdown latch, safety-fault and final TX-kill gating. The LED
tap therefore cannot display a requested pulse that the final safety boundary
suppressed.

RX activity is generated separately for each lane only when
`p9_4ppm_frame_rx` completes a frame and its CRC is valid. It does not use the
asynchronous Rxd pin, synchronized raw pulses, preamble-only activity, or a
CRC-invalid frame. Both valid DATA and valid ACK frames count as receive
activity.

A shared 1 kHz tick drives four 200 ms hold counters. Any new event reloads
its counter, so sustained traffic remains visibly lit. The monitor has no
`GLOBAL_PERMIT` input: deasserting transmit permission does not suppress RX
indication during permitted receive-only operation.

## Reset, fault, shutdown and power-up behavior

Reset, any role-local TFDU safety fault, the transport shutdown latch, or both
role-local SD outputs being high has priority over every activity event. That
condition immediately drives `4'b1111` and clears all hold counters. Leaving
shutdown without a new event therefore keeps all LEDs off.

After configuration, asserted reset drives all four outputs high. During FPGA
configuration the board’s active-low LED load and the AX7020 configuration
pull-up behavior are expected to keep the LEDs off; this visual condition is
not a functional status guarantee and is not part of the TFDU fail-safe claim.

## Isolation from transport and safety

`p10_lane_activity_leds` has inputs only from monitor taps and has one output
only to the onboard LEDs. Its output is not read by the transport, scheduler,
DMA, Txd, SD, Mode, `GLOBAL_PERMIT`, final TX kill, frame-admission, reset, or
fault logic. It cannot exert backpressure. Resource and timing changes are
validated independently for both endpoint roles.

## Verification obligations

The dedicated XSIM test covers mapping, active-low polarity, shared tick,
hold/reload behavior, sustained activity, reset priority, shutdown priority,
and state clearing. Static audits check both XDCs, source provenance, role
semantics, and the absence of LED feedback. The complete P10 dual-endpoint and
TFDU safety regressions, both routed AX7020 builds, DRC, methodology, CDC,
timing, utilization, the complete no-hardware offline gate, and evidence
consistency must pass against the new source checkpoint.

Hardware behavior remains `PENDING_NEW_BITSTREAM_HARDWARE_VALIDATION`.
