# Build And Test Guide

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## P0 Bootstrap

Run `python scripts/run_offline_gates.py` to refresh the imported bootstrap
evidence. This is offline-only.

## P1 Offline Hardening

Run `python tools/run_offline_gate.py --allow-skips --json-summary`.
PowerShell users can run `powershell -ExecutionPolicy Bypass -File tools/run_offline_gate.ps1 -AllowSkips -JsonSummary`.

## P2 Simulation Baseline

P2 is prepared by `docs/P2_SIMULATION_BASELINE_PLAN.md`. It remains offline and
must not touch hardware.

## P3 RTL Refactor

P3 may split PHY, codec, frame, ARQ, scheduler, and AXI blocks only after P1/P2
evidence remains clean.

## P4 Pre-Hardware Acceptance

P4 prepares dry-run wrappers and authorization material only.

## P5 Authorized Hardware Smoke

P5 is future work and requires explicit user authorization. It is not authorized
by this guide.
