# P10 severe hardware blocker: TFDU partial-power and canonical Txd-low state are not established

`P10-SAFETY-POWERUP-001` is an open severe blocker. The current fast-track authorizes hardware actions, but it also requires Codex to stop for autonomous-TX/final-TX-kill safety violations.

Direct evidence:

- The supplied TFDU small-board `SchDoc` contains four 22-ohm signal series resistors, a 0-ohm VCC2 path, and a 47-ohm VCC1 filter. It contains no Txd pull-down and no SD pull-up.
- The official AX7020 schematic shows only 33-ohm series arrays on the selected J10 Txd/SD nets; it shows no discrete fail-safe bias on those nets.
- AX7020 R29 holds U13/`PUDC_B` low with 1 kohm. AMD UG470 states that low `PUDC_B` enables SelectIO internal pull-ups after power-up and during configuration, subject to power sequencing.
- The TFDU6102 pin description states Txd is active HIGH and SD is active-high shutdown (PDF page 4 / printed page 3). Its truth table states SD=HIGH forces transmitter=0 regardless of Txd (PDF page 10 / printed page 9).
- Consequently, during an ordinary powered configuration interval in which the internal pull-ups are active, SD and Txd are both expected HIGH and SD inhibits optical TX. Current evidence does **not** support claiming autonomous optical emission in that specific state.
- That state still violates the canonical physical Txd-default-LOW/full-shutdown SD=HIGH+Txd=LOW contract, and the lack of discrete bias does not guarantee any FPGA-unpowered/TFDU-powered or other partial-power sequence.
- A shutdown image controls pins only after PL configuration and cannot close the preceding configuration interval or partial-power guarantee.

The user confirms that all four TFDU small boards previously operated on AX7010. The supplied comparison records byte-identical AX7010/AX7020 base-PCB schematic and J10 circuitry. That is accepted as empirical module/circuit compatibility and removes any P10 request to re-inspect the four module markings, revisions, or photos. It does not establish canonical physical Txd-low/full-shutdown compliance or partial-power TX-disabled behavior.

The same schematic also places R29=1 kohm to ground on the requested B-position Rxd (`J10-26/U13`). This is not an output-to-output connection, but its approximately 3.3 mA high-state load exceeds the TFDU6102 datasheet's 250/500-uA VOH guarantee points. User-confirmed prior operation on the identical AX7010 base/J10 circuit makes this an empirical-operability-backed datasheet gap, not an independent damage-risk blocker.

The only hardware action recorded is bounded read-only JTAG cable-serial enumeration; it did not configure or reset the FPGA or drive TFDU pins. FPGA programming, ELF execution, UART writes, TFDU drive, reset, and configuration-changing actions remain blocked. Resolution requires existing as-built fail-safe circuit evidence plus sequence-bounded measurements, or a new authorization that permits a documented fail-safe hardware revision because the current goal prohibits rewiring.
