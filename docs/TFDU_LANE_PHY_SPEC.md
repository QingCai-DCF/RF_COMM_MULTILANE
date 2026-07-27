# TFDU Lane PHY Specification

NO_HARDWARE_ACTIONS_EXECUTED: true

CURRENT_RUN_HARDWARE_AUTHORIZATION: false

HARDWARE_ACCEPTANCE: PENDING_HW

## Scope

P8C moves canonical safety ownership from logical lanes to physical TFDU modules. `rtl/ir_tfdu_physical_module_safety.sv` owns start-up, exact rolling duty, continuous-high protection, sticky faults, and telemetry for one physical module. `rtl/ir_tfdu_safety_endpoint.sv` applies endpoint arm, mapping/path conditions, SD separation, and the single raw permit final kill.

The P0-P7 `rtl/tfdu_lane_phy.sv` interface remains as a compatibility wrapper, but its former fixed-bucket implementation has been replaced by the P8C exact physical-module core. Legacy parameter names remain for source compatibility and cannot weaken the canonical 1 us / 18% protections.

## Physical-module state

State follows the electrical TFDU, not the logical lane that currently selects it:

```text
P8B active mapping + current path epoch + logical selection
  -> physical module ID
  -> per-module start-up/duty/continuous-high safety
  -> endpoint arm and safety qualification
  -> raw GLOBAL_PERMIT final AND
  -> physical Txd
```

A path change from module A to B and back to A finds A's prior ring history intact. Only explicit history invalidation or an accepted safety clear can discard it, and either action starts a full 1000 us zero-fill cooldown.

The compatibility `tfdu_lane_phy` keeps its historical controlled-safety-clear behavior by default. The P9 transport core explicitly selects telemetry-only `CLEAR_COUNTERS`: it clears measurement counters without clearing sticky safety faults, invalidating duty history, or reopening the cooldown. This matches the canonical separation between telemetry clear and safety-fault clear.

## Output and receive behavior

- Full shutdown: `SD=1`, `Txd=0`, start-up state cleared.
- Receive-only: `SD=0` when enabled, `GLOBAL_PERMIT=0`, `Txd=0`; active-low RX acquisition and counters remain available after start-up.
- Armed transmit: requires raw/synchronized permit, explicit arm, current mapping/path epoch, one-hot validity, no bank/module fault, complete start-up/history cooldown, frame admission, and waveform request.
- Raw permit deassertion: combinationally forces all local physical `Txd` outputs low and asynchronously clears arm.

## Canonical cycle values

At 64 MHz:

| Quantity | Cycles |
|---|---:|
| 500 us start-up | 32,000 |
| 1000 us duty window/cooldown | 64,000 |
| strict `<20%` legal maximum | 12,799 high cycles |
| `<=18%` target | 11,520 high cycles |
| 1 us continuous-high maximum | 64 |

Non-integral profile conversions fail elaboration/config verification rather than shortening a safety interval.

## Profiles and non-goals

P8C executes 2-module Z7010 development, 8-module rotating, and 32-module fixed accounting models. The latter two are logic models only and do not reuse the AX7010 XDC. This specification does not prove final pinout, electrical fail-low behavior, current delivery, optical power, rotation, or product hardware acceptance.
