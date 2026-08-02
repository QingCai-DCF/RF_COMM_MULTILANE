# P10.1R current-run authorization readiness

- Status: `PENDING_NEW_AUTHORIZATION`
- Test ID: `P10_1R-CURRENT-RUN-AUTHORIZATION-READINESS`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`

The user authorization exists, but no run-bound authorization record has been created or consumed by this offline run.

Hardware execution must not begin until a fresh immutable current-run record is bound to the exact frozen hashes in this record.
