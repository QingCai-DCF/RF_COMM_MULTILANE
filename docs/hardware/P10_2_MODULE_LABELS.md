# P10.2 module and harness label template

Apply labels only while all AX7020 and TFDU supplies are off. Labels identify inventory; they do not create electrical or hardware acceptance.

| Module label | Endpoint | Lane | Pair | Inventory gate |
|---|---|---:|---|---|
| F0 | AX7020-F | 0 | F0-R0 | accepted P10.1R baseline |
| F1 | AX7020-F | 1 | F1-R1 | must be the recorded replacement F1 |
| F2 | AX7020-F / J11-A | 2 | F2-R2 | future intake required |
| F3 | AX7020-F / J11-B | 3 | F3-R3 | future intake required |
| R0 | AX7020-R | 0 | F0-R0 | accepted P10.1R baseline |
| R1 | AX7020-R | 1 | F1-R1 | accepted P10.1R baseline |
| R2 | AX7020-R / J11-A | 2 | F2-R2 | future intake required |
| R3 | AX7020-R / J11-B | 3 | F3-R3 | future intake required |

Each four-conductor signal harness must carry matching endpoint/module and signal labels: `Mode`, `SD`, `Rxd`, and `Txd`. Power and ground harnesses require rail, polarity, endpoint, module, and return-path labels. `F1_ORIGINAL-QUARANTINE-DO NOT USE` must be physically distinguishable from every accepted or pending module.
