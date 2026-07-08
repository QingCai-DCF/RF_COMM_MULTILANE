# Hardware Acceptance Runbook

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P3 writes this future P4 runbook only. No command in this document is run by P3.

## P4A: visual/electrical pre-power review

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4B: no-emission idle IO verification

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4C: SD/Mode static level verification

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4D: startup gate observation

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4E: single-lane single-pulse raw PHY smoke

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4F: AB/BA raw lane matrix

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4G: lane0 frame+CRC only

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4H: lane0 ACK-only

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4I: lane1 raw only, if lane1 is installed

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4J: 2-lane protocol only after all raw directions pass

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.

## P4K: shutdown and evidence packaging

purpose: define a bounded future hardware acceptance step.
preconditions: user authorization, dry-run gate pass, matching hashes, max runtime, and shutdown-on-exit.
commands to run in future P4: use the `tools/hw_*.py --execute-hardware` entrypoint after authorization.
expected observations: bounded electrical or protocol evidence matching the step scope.
required evidence: schema-compliant file under `evidence/hardware/` plus scope/logic/VCC/shutdown artifacts when applicable.
pass criteria: all required observations present, counters consistent, shutdown confirmed.
fail criteria: stop condition, missing evidence, mismatch, timeout, unsafe level, or shutdown failure.
stop conditions: follow `docs/TFDU6102_STOP_CONDITIONS.md`.
shutdown requirement: follow `docs/TFDU6102_SHUTDOWN_REQUIREMENTS.md`.
