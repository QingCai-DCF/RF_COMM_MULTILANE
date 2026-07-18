# Z7020 fixed-endpoint I/O budget

Status: `PENDING_D12`. This is a board-selection input, not a pinout and not evidence that any board satisfies the requirement.

The fixed endpoint budgets 8 TX, 8 current RX, 8 candidate RX, three sector-bank address lines, one latch, one readback, eight bank-fault inputs, a four-wire serialized interface for 32 SD controls, one active-high `GLOBAL_PERMIT`, three ABZ inputs, and at least ten service/debug reserve signals. That is a minimum of 52 single-ended signals before conditional Ethernet/MDIO, PS DDR/MIO, SPI, and external-clock choices.

At least two clock-capable inputs should remain available. Differential-pair demand is not frozen; an Ethernet or external low-jitter clock choice may add pairs. Bank voltage, simultaneous-switching constraints, level translation, PS DDR/MIO, Ethernet topology, ABZ electrical details, and the D17 physical permit circuit block a pin freeze.

The eight TX lines are a capacity budget only. Runtime one-hot, frame-admission, exact duty, stuck-high, pulse-width, and the single raw-low permit kill remain mandatory.
