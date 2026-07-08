# Raw PHY Smoke Runbook

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

Future P4 raw PHY order:

1. keep SD shutdown, Txd low, Mode static selected
2. observe idle electrical levels
3. enable one lane only
4. wait >= 500 us startup
5. send one short pulse or bounded pulse train
6. observe remote Rxd active-low pulse
7. read raw pulse counter
8. force shutdown
9. verify Txd low and SD shutdown
10. archive scope/logic-analyzer/counter evidence

Raw PHY smoke allows no CRC, ACK, retry, Ethernet, or rotation.
