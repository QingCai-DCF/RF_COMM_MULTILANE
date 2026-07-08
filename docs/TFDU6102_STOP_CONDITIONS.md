# TFDU6102 Stop Conditions

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

Future P4 tests must stop immediately if any condition occurs:

- Txd stuck high
- Txd high duration exceeds configured guard
- SD fails to enter shutdown at test end
- unexpected optical emission during dry-run or idle
- VCC2 droop exceeds predefined threshold
- VCC1 droop or brownout observed
- Rxd remains stuck low after shutdown/idle
- device overheats
- operator activates emergency stop
- script loses connection before shutdown confirmation
- raw counter behavior is impossible or inconsistent
- wrong active XDC hash
- wrong bitstream hash
- authorization mismatch
