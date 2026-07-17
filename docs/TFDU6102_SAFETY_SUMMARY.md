# TFDU6102 Safety Summary

NO_HARDWARE_ACTIONS_EXECUTED: true

CURRENT_RUN_HARDWARE_AUTHORIZATION: false

HARDWARE_ACCEPTANCE: PENDING_HW

`config/tfdu_safety.yaml` is the single machine-readable P8C safety source. Its generated canonical values are a 64 MHz clock, 500 us receiver start-up, an exact 64,000-cycle (1000 us) sliding window, strict `<20%` hard limit, `<=18%` admission target, and `MAX_CONTINUOUS_TXD_HIGH_US=1`.

## TFDU pin semantics

- `Txd` is active high and must default low.
- `Rxd` is active low.
- `SD` is active-high shutdown. Full shutdown is `SD=1` and `Txd=0`.
- Static `Mode=1` selects MIR/FIR. P8C does not mix this with dynamic mode programming.
- Normal RX or TX is not valid until at least 500 us after `SD` is released.

## Exact duty and pulse protection

Each physical TFDU owns its own history ring and running sum. Logical lane, mapping, path epoch, arm, and permit transitions do not clear that history. In every clock-aligned 1000 us interval, admitted physical-high charge satisfies:

```text
high_cycles * 100 < window_cycles * 20
```

At 64 MHz the highest legal hard count is 12,799 cycles; the normal admission target is 11,520 cycles. History invalidation or accepted safety-fault clear forces a complete 64,000-cycle all-TX-low refill before history becomes valid again. The separate continuous-high guard allows at most 64 cycles at 64 MHz and latches a stuck-high fault on a `MAX+1` request.

Because the `<=18%` property holds for every clock-aligned 1 ms interval, any clock-aligned 100 ms interval partitioned into 100 such intervals also meets the configured 18% long-term target.

## Single global permit

Each independent endpoint consumes exactly one local active-high `GLOBAL_PERMIT`. A raw-low value is the final combinational AND on every physical `Txd`; assertion passes through synchronization/filtering and still requires an explicit endpoint arm. A drop clears arm immediately, aborts an active frame, and prevents partial-frame resumption. Reassertion never auto-arms.

`GLOBAL_PERMIT=0` does not force `SD=1`: receive-only acquisition may keep `SD=0` while the final permit kill holds every `Txd=0`. Full shutdown remains a separate request.

The fail-low board/pulldown behavior is a defined contract, not current hardware evidence. The Z7010 development profile has no frozen permit pin (`PENDING_P9_PIN_FREEZE`), and open-circuit, partial-power, and external-buffer behavior remain `PENDING_D17`.

XSIM can prove RTL X/Z fail-low behavior, but it cannot prove open-circuit, FPGA-unconfigured, or partial-power electrical behavior. External bias, final buffer topology, and kill latency remain `PENDING_D17`. External duty/current/optical measurements remain `PENDING_P9_OR_LATER`.

## Evidence boundary

P8C evidence covers Python reference behavior, reduced and full-scale XSIM, 2/8/32-module models, register read-only behavior, static architecture checks, and out-of-context synthesis. It does not promote Z7020, rotating, sector-bank, optical, power, or final-product hardware acceptance. Historical P7 stationary two-lane acceptance remains scoped and unchanged.
