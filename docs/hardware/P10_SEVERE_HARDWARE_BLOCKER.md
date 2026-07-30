# P10 severe hardware blocker: TFDU power-up fail-safe is not established

`P10-SAFETY-POWERUP-001` is an open severe blocker. The current fast-track authorizes hardware actions, but it also requires Codex to stop for autonomous-TX/final-TX-kill safety violations.

Direct evidence:

- The supplied TFDU small-board `SchDoc` contains four 22-ohm signal series resistors, a 0-ohm VCC2 path, and a 47-ohm VCC1 filter. It contains no Txd pull-down and no SD pull-up.
- The official AX7020 schematic shows only 33-ohm series arrays on the selected J10 Txd/SD nets; it shows no discrete fail-safe bias on those nets.
- AX7020 R29 holds U13/`PUDC_B` low with 1 kohm. The 7-series configuration contract therefore enables internal SelectIO pull-ups during configuration, subject to power sequencing. That cannot establish the required physical Txd-low/SD-high state in every power/reset/fault/partial-power condition.
- A shutdown image controls pins only after PL configuration and cannot prove FPGA-unconfigured or partial-power behavior.

The user confirms that all four TFDU small boards previously operated on AX7010. The supplied comparison records byte-identical AX7010/AX7020 base-PCB schematic and J10 circuitry. That is accepted as empirical module/circuit compatibility and removes any P10 request to re-inspect the four module markings, revisions, or photos. It does not establish the passive unconfigured/reset/partial-power safety state required by the canonical project constraints.

The same schematic also places R29=1 kohm to ground on the requested B-position Rxd (`J10-26/U13`). This is not an output-to-output connection, but its approximately 3.3 mA high-state load exceeds the TFDU6102 datasheet's 250/500-uA VOH guarantee points. User-confirmed prior operation on the identical AX7010 base/J10 circuit makes this an empirical-operability-backed datasheet gap, not an independent damage-risk blocker.

At artifact-generation time no hardware action was performed. A bounded read-only JTAG cable-serial enumeration is allowed because it neither configures the FPGA nor drives TFDU pins. FPGA programming, ELF execution, UART writes, TFDU drive, reset, and configuration-changing actions remain blocked. Resolution requires existing fail-low circuit/measurement evidence, or a new authorization that permits a documented fail-safe hardware revision because the current goal prohibits rewiring.
