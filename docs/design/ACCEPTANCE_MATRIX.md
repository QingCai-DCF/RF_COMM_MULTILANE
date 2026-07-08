# Acceptance Matrix

| Stage | Status | Automation path |
|---|---|---|
| Import RF_COMM | PASS | manifest + sha256 |
| Constraint copy | PASS | constraint hash equality |
| XDC canonicalization | PASS | generated XDC equals active reference mapping |
| TFDU safety static | PASS | `scripts/check_tfdu_safety_static.py` |
| Multilane scheduler static | PASS | `scripts/check_scheduler_static.py` |
| Lane PHY sim | PASS | D:\Xilinx\Vivado\2023.1\bin Xilinx simulator bat tools |
| 4PPM codec sim | PASS | D:\Xilinx\Vivado\2023.1\bin Xilinx simulator bat tools |
| 4PPM + TFDU model integration sim | PASS | D:\Xilinx\Vivado\2023.1\bin Xilinx simulator bat tools |
| Lane0 frame CRC sim | PASS | D:\Xilinx\Vivado\2023.1\bin Xilinx simulator bat tools |
| Lane0 ACK sim | PASS | D:\Xilinx\Vivado\2023.1\bin Xilinx simulator bat tools |
| AXI regs sim | PASS | D:\Xilinx\Vivado\2023.1\bin Xilinx simulator bat tools |
| Multilane scheduler sim | PASS | D:\Xilinx\Vivado\2023.1\bin Xilinx simulator bat tools |
| Vivado build | PASS | D:\Xilinx\Vivado\2023.1\bin\vivado.bat, batch non-hardware build |
| M6 hardware prep wrappers | PASS | `scripts/check_m6_static.py`; wrappers refuse unless `-AllowHardware` |
| PS driver offline | PASS | host protocol unit test + generated headers |
| PS driver C compile | PENDING_TOOL | gcc/clang not on PATH |
| Host client offline protocol | PASS | encode/decode, error events, reconnect state machine mock |
| Ethernet real board | PENDING_HW_OR_DEFERRED | not automated unless user authorizes |
| Rotation 600 rpm | PENDING_EXTERNAL_FIXTURE | not automated by Codex |
| 2-hour soak | PENDING_HW | not automated by default |
| 8-lane | PENDING_DESIGN | blocked until lane1 and power strategy resolved |
