# P10 power-state finding reassessment

`P10-SAFETY-POWERUP-001` was originally classified as severe. It is now `PENDING_D17_NONBLOCKING_FOR_P10_SCOPED_NO_POWER_CYCLE_RUN` and is not a blocker for the already-powered, no-intentional-power-cycle P10 campaign. This does not waive or pass the D17 requirement.

Direct evidence:

- The supplied TFDU small-board `SchDoc` contains four 22-ohm signal series resistors, a 0-ohm VCC2 path, and a 47-ohm VCC1 filter. It contains no Txd pull-down and no SD pull-up.
- The official AX7020 schematic shows only 33-ohm series arrays on the selected J10 Txd/SD nets; it shows no discrete fail-safe bias on those nets.
- AX7020 R29 holds U13/`PUDC_B` low with 1 kohm. AMD UG470 states that low `PUDC_B` enables SelectIO internal pull-ups after power-up and during configuration, subject to power sequencing.
- The TFDU6102 pin description states Txd is active HIGH and SD is active-high shutdown (PDF page 4 / printed page 3). Its truth table states SD=HIGH forces transmitter=0 regardless of Txd (PDF page 10 / printed page 9).
- Consequently, during an ordinary powered configuration interval in which the internal pull-ups are active, SD and Txd are both expected HIGH and SD inhibits optical TX. Current evidence does **not** support claiming autonomous optical emission in that specific state.
- Configured reset/fault logic and both frozen role-specific shutdown images drive Txd LOW and SD HIGH. Their build evidence records Mode=0x3, SD=0x3, and Txd=0x0.
- The configuration state does not establish Txd LOW, and the lack of discrete bias does not guarantee any FPGA-unpowered/TFDU-powered or other partial-power sequence. Those external properties remain `PENDING_D17`.
- A shutdown image controls pins only after PL configuration and does not close the preceding configuration interval or partial-power guarantee; P10 makes no such claim.

The user confirms that all four TFDU small boards previously operated on AX7010. The supplied comparison records byte-identical AX7010/AX7020 base-PCB schematic and J10 circuitry. That is accepted as empirical module/circuit compatibility and removes any P10 request to re-inspect the four module markings, revisions, or photos. It does not establish canonical physical Txd-low/full-shutdown compliance or partial-power TX-disabled behavior.

The same schematic also places R29=1 kohm to ground on the requested B-position Rxd (`J10-26/U13`). This is not an output-to-output connection, but its approximately 3.3 mA high-state load exceeds the TFDU6102 datasheet's 250/500-uA VOH guarantee points. User-confirmed prior operation on the identical AX7010 base/J10 circuit makes this an empirical-operability-backed datasheet gap, not an independent damage-risk blocker.

The canonical safety contract assigns external power-up/open/unconfigured/partial-power fail-low and physical final-kill measurement to `PENDING_D17`. The canonical P9 result is PASS while preserving that boundary, and the P10 fast-track explicitly preserves `PHYSICAL_GLOBAL_PERMIT: PENDING_D17` after P10. Therefore this finding is nonblocking only within a no-intentional-power-cycle campaign that programs role-matched shutdown images first and aborts on target, rail, safe-state, or autonomous-emission anomalies.

The remaining P10 blocker is `NONE`. The only hardware action recorded so far is bounded read-only JTAG cable-serial enumeration; it did not configure or reset the FPGA or drive TFDU pins.
