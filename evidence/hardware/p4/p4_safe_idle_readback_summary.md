# P4 Safe Idle Readback Summary

generated_at_utc: 2026-07-08T15:50:15+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
RESULT: PASS_WITH_LIMITED_READBACK
REASON: safe-idle bitstream was programmed, but direct TFDU pin readback is limited
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

SAFE_IDLE: PASS_WITH_LIMITED_READBACK
READBACK_LIMITED: true
reason: no direct TFDU pin readback or ILA proxy available in this runner
SAFE_IDLE_BITSTREAM: `evidence/generated/vivado/ir_top_new_safe_idle.bit`
SAFE_IDLE_BITSTREAM_SHA256: `7626b8ca160a47e44fbf00557dfc60b14a4c291961c4a7be12df4f8380c53544`
PROGRAM_RETURN_CODE: 0

## Safe Idle Programming Log Tail

```text
P4_SAFE_IDLE_PROGRAMMING_BEGIN 2026-07-08T23:48:43+0800
HW_TARGET_COUNT 1
HW_TARGET localhost:3121/xilinx_tcf/Digilent/210512180081
HW_JTAG_FREQUENCY_HZ 1000000
HW_DEVICE xc7z010_1
SAFE_IDLE_DEVICE_PROP NAME=xc7z010_1
SAFE_IDLE_DEVICE_PROP PART=xc7z010
SAFE_IDLE_DEVICE_PROP IDCODE=00010011011100100010000010010011
SAFE_IDLE_DEVICE_PROP IS_PROGRAMMED ERROR=ERROR: [Labtoolstcl 44-56] hw_device [xc7z010_1] does not have a [IS_PROGRAMMED] property

SAFE_IDLE_BITSTREAM_PROGRAMMED=C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/vivado/ir_top_new_safe_idle.bit
READBACK_LIMITED=1
READBACK_LIMITED_REASON=no direct TFDU pin readback or ILA proxy was available in this runner
P4_SAFE_IDLE_PROGRAMMING=PASS

```
