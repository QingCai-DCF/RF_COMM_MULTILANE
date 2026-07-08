# TFDU6102 Electrical Checklist

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

All measured electrical values are PENDING_P4. P3 may record planned FPGA pins from the active pinmap only.

| Lane | Side | Txd FPGA pin | Rxd FPGA pin | SD FPGA pin | Mode FPGA pin | Connector | Measurement fields |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | A | C20 | B19 | T11 | T12 | J10 | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 0 | B | V12 | U13 | T14 | V17 | J10 | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 1 | A | K14 | H15 | H16 | G17 | J11 | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 1 | B | E18 | G15 | M17 | L16 | J11 | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 2 | A | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 2 | B | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 3 | A | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 3 | B | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 4 | A | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 4 | B | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 5 | A | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 5 | B | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 6 | A | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 6 | B | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 7 | A | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |
| 7 | B | PENDING_P4 | PENDING_P4 | PENDING_P4 | PENDING_P4 | not mapped in P3 pinmap | VCC1, VCC2, droop, C1, C2, C3, R1, R2, ground continuity, IO bank voltage, idle levels: PENDING_P4 |

Required per-lane fields for P4: lane_id, physical module ID, orientation, TX optical direction, RX optical direction, Txd FPGA pin, Rxd FPGA pin, SD FPGA pin, Mode FPGA pin, VCC1 nominal voltage, VCC2 nominal voltage, VCC2 droop capture path, C1/C2/C3 value and location, R1/R2 presence and value, ground continuity, IO bank voltage, idle Txd, idle SD, idle Mode, and idle Rxd.
