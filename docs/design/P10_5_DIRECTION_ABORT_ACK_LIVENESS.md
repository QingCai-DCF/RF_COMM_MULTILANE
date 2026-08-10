# P10.5 direction-abort ACK liveness remediation

## Scope and disposition

The immutable hardware run
`p10_5_20260810T070056Z_eefca40c_78726594_498ca074` failed at
`fault_abort_r2f`. Both boards then entered verified full shutdown. The failed
run remains immutable and is not promoted to PASS.

The failure is a deterministic cumulative-ACK liveness defect, not an unknown
optical, CRC, DMA-integrity, wiring, or module failure. The old artifact bundle
is retired from further acceptance. This remediation requires a new source
commit, bitstreams, XSAs, BSPs, ELFs, hashes, authorization, and full hardware
campaign; no old hardware PASS is inherited.

## Direct evidence

- Fixed, the unaffected F-to-R sender, had accepted exactly 12,844 bytes (52
  full 247-byte fragments). Its frozen TX window showed `next=52`,
  `ack_base=21`, `outstanding=31`, `retry=224`, `timeout=225`, and
  `retry_exhausted=1`.
- Rotating had received 12,844 F-to-R bytes but emitted only three
  control-only ACK fallbacks before its R-to-F TX context was aborted.
- Fixed ended with `0x50090004` (retry exhaustion); rotating ended with
  `0x50090001` after the direction-scoped abort. CRC, SHA, descriptor-leak,
  double-completion, and wrong-object counters remained zero.
- Both first-fault snapshots report `tx_kill=true` and
  `effective_full_shutdown=true`. Final fixed and rotating shutdown markers
  are PASS.

The old RTL cleared `p10_5_ack_dirty_q` when scheduling a DATA piggyback. If
that physical DATA was canceled by a direction-scoped local TX abort, a later
duplicate DATA frame raised `p10_5_immediate_control_event` and refreshed the
fallback timer and ACK aggregator, but did not restore `p10_5_ack_dirty_q`.
Control-only scheduling requires both aggregator state and dirty state, so the
still-live RX context could no longer retransmit its cumulative ACK. The peer
therefore exhausted all retries for the remaining 31-frame window.

## RTL remediation

`p10_5_immediate_control_event` now atomically:

1. restores `p10_5_ack_dirty_q`;
2. moves the control fallback timer to the grace boundary;
3. leaves all existing RX-context abort, full-shutdown, fault, permit, TX-kill,
   SD, Mode, exact-duty, and stuck-high priority paths unchanged.

Later same-cycle lifecycle branches retain priority: a full object abort,
fault, shutdown, or RX-context abort still clears pending ACK state. The new
assignment is only an ACK-liveness recovery for a still-live RX context and
cannot enable a TX path by itself.

## Regression and runtime/rest correction

The dual-direction XSIM regression now includes the symmetric R-to-F abort at
the observed 52-fragment boundary and requires the unaffected F-to-R payload
to complete byte-exactly without retry exhaustion. The firmware contract also
requires every duplicate/credit-reopen immediate event to reconstruct dirty
state.

The failed run exposed a separate safety-accounting defect: firmware terminal
timers were zero on the failed case, so the runner recorded only 12.027 seconds
of earlier successful cases although XSDB observed 617.530 seconds across the
11 non-shutdown cases, including 600.403 seconds for `fault_abort_r2f`. The
runner now conservatively sums XSDB `started_ms..finished_ms` intervals and
uses the larger of this value and parsed firmware timers. A failed case can no
longer shorten the mandatory half-runtime cooldown. The faults planned bound
is 900 seconds, still below the 1,800-second per-module hard maximum.

## Acceptance boundary

Offline remediation does not establish hardware PASS. The next hardware run
must use only the newly frozen artifacts, start with shutdown-before, remain at
lane masks `0x1..0xF`, observe the 30-minute/half-runtime rest policy, and
shutdown both boards on normal exit, failure, timeout, or interruption.
