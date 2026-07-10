# P6 Recovered Failure Package

P6_RECOVERED_FAILURE_PACKAGE: RECOVERED_SUPERSEDED_BY_PASS

Stage: `lane0_dynamic_payload_initial_bringup`

Root cause: the first physical DATA frame decoded correctly, but the B-side ACK began before the A-side TFDU receiver had recovered from transmit turnaround. The stage ended with `ERROR_ACK_TIMEOUT=0x102`, `retry_exhausted=1`, and `tx_fail=1`.

Safety evidence recorded at failure:

- before-stage shutdown exit: `0`
- after-stage shutdown exit: `0`
- `TFDU_SHUTDOWN_PROGRAMMED`: true
- maximum Txd-high width: `8` cycles
- duty violation: `0`

The fix added a 4096-cycle turnaround guard before ACK transmission. The immutable replacement candidate is proven by the 160-case lane0 physical matrix at `evidence/hardware/p6/protocol/lane0_dynamic_payload/p6_jtag_axi_matrix_summary.json`.

The initial runner reused its stage log path, so the first raw log was overwritten by the later passing run. The JSON companion preserves the captured counters and explicitly records this retention limitation.
