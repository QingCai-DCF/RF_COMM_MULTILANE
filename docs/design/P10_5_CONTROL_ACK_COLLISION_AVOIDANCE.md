# P10.5 control-only ACK collision avoidance

## Scope

This design closes the adjacent-module 1+1 deadlock observed after the first
P10.5 hardware attempt. It changes only P10.5 split-lane control scheduling.
The P10.4 connector-local ACK/RX quarantine and every physical TX safety path
remain unchanged.

## Directly observed failure

The failed hardware case used fixed TX lane 0 and rotating TX lane 1. Both
directions transferred one 256 KiB internal object, then stopped making
progress while awaiting the final cumulative control ACK. CRC, SHA, descriptor,
and safety counters stayed clean, but the rotating endpoint reached 105 TX
timeouts. Shutdown-before and shutdown-after both passed.

An XSIM reproduction using the same adjacent J10 topology delivered 2,000
bytes in each direction with zero CRC errors, but ended with one outstanding
frame on each endpoint. Both endpoints emitted control-only ACKs in the same
64,000-cycle slot. P10.4 correctly quarantined the connector-mate receiver
during each local ACK transmission, so the two ACKs were lost in lockstep.

## Remediation

The unchanged ACK maximum delay is 64,000 clocks. The fixed role owns the
early control-only slot at 32,000 clocks. The rotating role normally waits for
a CRC-valid fixed-role control ACK token, then waits the existing 4,352-clock
post-TX receiver-recovery guard before replying. If the token is lost, the
rotating endpoint escapes at the original 64,000-clock maximum; it never waits
past the existing starvation bound.

The ACK scheduler also prefers an eligible TX module whose connector mate is
not in the local RX mask. If an adjacent 1+1 topology offers no such module,
the role-ordered schedule supplies liveness. A control ACK may still preempt an
adjacent reverse DATA frame; selective repeat handles this as a bounded retry.
The design does not claim a zero-retry link.

## Safety and isolation invariants

- Exactly one local active-high `GLOBAL_PERMIT` remains in each endpoint.
- P10.4 connector ACK/RX quarantine is neither weakened nor bypassed.
- The final Txd kill, SD, Mode, duty, stuck-high, pulse-width, and fault paths
  are unchanged.
- A received token is accepted only from a CRC-valid, role/session/direction
  valid control ACK on an admitted RX lane.
- Reset, abort, disarm, object failure, or full shutdown clears pending control
  state and leaves the physical shutdown behavior unchanged.
- The fixed slot, guarded rotating response, and rotating escape are all below
  the retransmission timeout and at or below the frozen ACK starvation limit.

## Verification boundary

The focused post-fix XSIM test exercises both orientations on J10 and J11 and
repeats J10 with fresh object/session identities. All five cases completed in
both directions with zero CRC errors, zero retry exhaustion, simultaneous
physical activity, and only bounded selective-repeat retries. This is offline
evidence only. It does not inherit or create hardware PASS for the new RTL;
new immutable bitstreams, XSA, BSP, ELF, hashes, authorization, and complete
hardware acceptance are required.
