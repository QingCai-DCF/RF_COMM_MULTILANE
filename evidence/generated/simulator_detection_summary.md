# Simulator Detection Summary

generated_at_utc: 2026-07-09T11:04:43+00:00
command: python tools/sim/detect_simulator.py
RESULT: PASS
REASON: HDL simulator selected
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

| Tool | Result | Version | Path / Reason |
| --- | --- | --- | --- |
| iverilog_vvp | SKIP_WITH_REASON | `` | iverilog=missing; vvp=missing; missing executables: iverilog, vvp |
| verilator | SKIP_WITH_REASON | `` | verilator=missing; missing executables: verilator |
| xsim | PASS | `Vivado Simulator v2023.1` | xvlog=D:\Xilinx\Vivado\2023.1\bin\xvlog.bat; xelab=D:\Xilinx\Vivado\2023.1\bin\xelab.bat; xsim=D:\Xilinx\Vivado\2023.1\bin\xsim.bat; detected |
| vivado_batch_compile | SKIP_WITH_REASON | `` | vivado=D:\Xilinx\Vivado\2023.1\bin\vivado.bat; version command failed |

SELECTED: xsim
PYTHON_REFERENCE_FALLBACK: false
