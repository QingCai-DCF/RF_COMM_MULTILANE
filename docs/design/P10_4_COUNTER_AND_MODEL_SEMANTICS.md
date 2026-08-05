# P10.4 counter and performance-model semantics

Status: offline implementation complete; current-artifact hardware reconciliation pending.

## Direct counter meanings

The historical `ack_wait_ratio` is retained only as `DEPRECATED_AMBIGUOUS`. Its underlying predicate means “an object is active and at least one frame is unacknowledged”; it does not prove that the transmitter is idle or that ACK latency is the bottleneck. New analysis must use the append-only P10.4 counters:

| Metric | Direct PL predicate | Ratio denominator |
|---|---|---|
| `outstanding_unacked_occupancy_ratio` | active object and `tx_outstanding_count != 0` | performance-active protocol clocks |
| `tx_idle_due_to_ack_ratio` | local sender, serializers idle, and explicit endpoint ACK wait | performance-active protocol clocks |
| `window_full_stall_ratio` | allocation pending, allocator not ready, and outstanding count exactly 32 | performance-active protocol clocks |
| `receiver_credit_stall_ratio` | a DATA attempt is ready while directly advertised peer credit is zero | performance-active protocol clocks |
| `direction_turnaround_idle_ratio` | serializers idle in an explicit DATA/ACK guard or turnaround state | performance-active protocol clocks |

The first metric is an occupancy measure and may overlap useful transmission. The other four are narrow causal predicates; host tooling must not reconstruct or infer them from unrelated counters. All five values are captured by the same atomic performance snapshot. The old field remains byte-for-byte compatible but is excluded from automatic bottleneck selection.

## Local-source rejection injection

Register `P10_4_LOCAL_SOURCE_TEST_CONTROL` accepts the key `0x4C53` and a nonzero four-lane mask only when the endpoint is disarmed, object-idle, TX-killed, and in effective full shutdown. The accepted one-clock pulse enters the real source-ID rejection predicate after CRC/source classification. It cannot create a frame, DMA delivery, application commit, permit, Mode/SD change, or physical Txd event.

The offline XSIM test proves that an armed endpoint cannot use the input and that a fully shut down endpoint increments the requested rejection counter without Txd. The hardware counter-semantics stage additionally compares coherent pre/post per-lane reject counters, application-commit bytes, and final physical-TX counters. Any mismatch is fail closed.

## Performance taxonomy

`PHY_RAW_BPS`, `FRAME_GOODPUT_BPS`, `RFAP_USEFUL_BPS`, `APPLICATION_GOODPUT_BPS`, and `HOST_ORCHESTRATED_BPS` are distinct. Each model record includes payload geometry, DATA and ACK airtime, the exact 18% duty schedule, ACK/SACK assumptions, direction quiet time, and retry assumption.

`APPLICATION_GOODPUT_BPS` uses integrity-verified, remotely committed
command-object bytes. In the current transport these occupy the full 247-byte
L1 payload. `RFAP_USEFUL_BPS` is a separate 215-byte projection and must not be
substituted for the hardware application counter; doing so would create a false
ceiling below the immutable P10.3 measurement.

For the current 32-frame, four-lane bundle, each physical lane carries eight DATA frames per burst. The qualified DATA-frame start spacing is 840 us; DATA-to-ACK-to-DATA recovery overlaps the final DATA module’s duty recovery, so only the slower path is charged. The model keeps the 8 Mbit/s retention threshold mandatory and treats 9.0 and 9.6 Mbit/s as nonblocking targets; no safety interval is shortened to make them pass.

Measured reconciliation uses the sender’s direct PS and PL timers, requires their error to remain within 1%, and reports measured/model and measured/airtime-ceiling ratios. Host-orchestrated wall time is diagnostic and never substitutes for endpoint application goodput.

## Safety and scope boundary

The counters and injection are monitor/test paths only. They do not feed back into scheduling, DMA backpressure, `GLOBAL_PERMIT`, Mode, SD, Txd kill, first-fault shutdown, rolling-duty, or continuous-high protection. Internal rail/temperature telemetry remains internal telemetry, not external electrical acceptance. P10.3 immutable hardware PASS is retained only for its frozen P10.3 artifacts; the P10.4 artifact bundle requires fresh acceptance.
