# P8C TFDU Safety Architecture

NO_HARDWARE_ACTIONS_EXECUTED: true

CURRENT_RUN_HARDWARE_AUTHORIZATION: false

HARDWARE_SCOPE_PROMOTED: false

## Architecture

`config/tfdu_safety.yaml` generates RTL/Python/documentation constants. The exact accountant advances a per-physical-module ring every clock even while permit is low, the endpoint is disarmed, the path is idle, or SD is active. P8B remains the sole owner of active/shadow mapping and path epoch; the P8C adapter is stateless and only expands those canonical outputs to physical-module safety signals.

```text
canonical safety config
  -> generated exact constants
  -> physical-module ring + running sum + 1 us guard

P8B active mapping/path epoch
  -> stateless physical selection adapter
  -> one-hot/bank/lane/frame qualification
  -> ENDPOINT_ARMED
  -> physical pre-final Txd
  -> single raw GLOBAL_PERMIT final kill
```

The fixed endpoint distributes its one permit across all 32 modeled physical modules/eight banks. The rotating endpoint distributes its one permit across eight direct physical paths. Bank fault, lane permit, endpoint arm, and one-hot masks are necessary safety conditions; none is another global permit channel.

## Exact duty implementation

For a ring of `W` clocks, each update removes the outgoing physical-high bit and adds the current actual/conservative physical-high bit. `H=(W*20-1)//100` is the highest legal hard count and `T=(W*18)//100` is the admission target. Production canonical values are `W=64000`, `H=12799`, and `T=11520`. OOC synthesis infers two RAMB36 blocks per physical history, with no SRL implementation.

Reset does not claim that unknown RAM contents are zero. Instead, history is invalid and physical TX is forced low while all `W` locations are synchronously zero-filled. This separates the 1000 us safety cooldown from the independent 500 us TFDU receiver start-up timer.

## Permit assertion and deassertion

Raw high passes through two-stage synchronization and a configurable consecutive-high filter. It never arms automatically. A valid software arm request only sets `ENDPOINT_ARMED` when the endpoint is idle and every selected physical safety condition is valid.

Raw low is converted to `global_permit_raw_safe=0`, asynchronously clears synchronizer/arm state, and is the final combinational AND after all sequential waveform logic. If a frame was active, a partial-frame block persists until that old frame becomes inactive; a new stable high and explicit re-arm can only start a fresh frame.

XSIM's case-equality X/Z test is an RTL fail-low contract, not evidence of real open-circuit or partial-power behavior. Those physical properties require D17 evidence.

## SD and receive-only acquisition

Permit controls TX only. `physical_sd_o` depends on receive enable and full-shutdown request, not permit. Consequently the endpoint may synchronize active-low `Rxd`, complete start-up, and count receive pulses with permit low while the final kill holds every `Txd` low.

## Register and software boundary

The additive P8C register block begins at `0x0400`; all P0-P7 offsets remain unchanged. Raw/synchronized/effective permit fields and counters are read-only. Software may issue request pulses for arm, disarm, full shutdown, controlled safety clear, telemetry clear, and atomic indexed snapshot. There is no permit-high write or override API.

## Executable property coverage

| Property | Direct evidence |
|---|---|
| P1-P5, P9-P13, P17 | endpoint XSIM and static final-kill scan |
| P6-P7, P14-P16 | reduced/full-scale duty XSIM, profile matrix, Python/RTL trace |
| P8 | physical safety XSIM (`MAX`, `MAX+1`, fault/clear) |
| P18 | register XSIM, generator access checks, host C stub |
| P19-P20 | canonical-source identifier and module-port static scan |

The 2/8/32 profile matrix exercises 1, 2, 4, and 8 simultaneous logical requests, independent physical histories, P8B mapping commits/wrap, stale-epoch kill, and endpoint-wide permit drop. Full-scale XSIM runs multiple 64,000-cycle wraps. Python adds deterministic boundaries and seven recorded adversarial seeds.

## Acceptance boundary

P8C may claim portable RTL/function PASS only. `GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION` remains `PENDING_D17`; the board fail-low/pulldown contract is defined, but the current Z7010 profile has no frozen permit pin and remains `PENDING_P9_PIN_FREEZE`. External TFDU duty/current/optical measurement remains `PENDING_P9_OR_LATER`; Z7020, rotating, sector-bank, simultaneous-power, and final-product hardware acceptance remain pending. The existing P7 stationary Z7010 two-lane application PASS is preserved without extrapolation.
