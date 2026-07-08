# TFDU6102 Shutdown Requirements

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

Required future P4 exit sequence:

1. stop TX FSM
2. force Txd=0
3. wait guard interval
4. force SD=shutdown/high
5. disable lane enable masks
6. clear pending start bits
7. read back shutdown status
8. read final counters
9. write shutdown log
10. exit process

The shutdown sequence must run on normal completion, FAIL, exception, timeout,
Ctrl+C, PowerShell trap/finally, and Python try/finally paths.
