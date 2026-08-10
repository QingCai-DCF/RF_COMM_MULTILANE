# P10.5 adjacent control-ACK collision diagnosis

- Status: `ROOT_CAUSE_REPRODUCED_AND_OFFLINE_REMEDIATED`
- Failed hardware run: `p10_5_20260810T040830Z_43cdde9f_e201ac59_e118ba87`
- Failed case: `oneplusone_f0_r1`
- Root cause: deterministic, symmetric control-only ACK self-quarantine on one connector
- Pre-fix XSIM: `FAIL`, 2,000 bytes delivered each way, one frame still outstanding each way, CRC bad `0`
- Post-fix focused XSIM: `PASS`, five adjacent 1+1 cases, CRC bad `0`, retry exhaustion `0`
- Remediation: fixed early slot at 32,000 clocks; rotating token response after 4,352-clock recovery guard; bounded escape at 64,000 clocks
- P10.4 connector quarantine and all safety paths: unchanged
- Hardware actions executed by remediation: `false`
- New hardware PASS inherited: `false`

The new RTL must be rebuilt into an immutable artifact bundle and subjected to
the complete P10.5 hardware campaign under a new exact current-run authorization.
