# Z7020 rotating-endpoint I/O budget

Status: `PENDING_D12`. No LOC, IOSTANDARD, DDR, MIO, or actual clock pin is selected here.

The rotating endpoint budgets 8 TX, 8 RX, 8 local SD controls, one active-high `GLOBAL_PERMIT`, four local-FPGA SPI signals, at least four battery/BMS/fault inputs, and at least eight clock/reset/debug reserve signals. The current minimum is 41 single-ended signals. At least one clock-capable input should remain available; a low-jitter differential clock remains an option rather than a requirement.

Board/package choice, I/O bank voltage, rotating-side power and level translation, SPI voltage/rate, battery/BMS definitions, and the D17 physical permit circuit block D12 closure. Eight TX lines are budgeted, while runtime P8C one-hot, exact-duty, stuck-high, pulse-width, and raw permit-low kill rules remain unchanged.
