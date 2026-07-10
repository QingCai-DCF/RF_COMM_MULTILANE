# P7 Design Summary

source_commit_binding: `evidence/generated/p7_offline_gate_summary.json` field `source_commit`
source_commit_binding_status: PENDING_REGENERATION_FROM_FINAL_CLEAN_P7_SOURCE_COMMIT
PL_REUSED_FROM_P6: true
P7_DESIGN_GATE_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PENDING_HW
PS_PL_PHY_PL_PS_APPLICATION_PASS: false
STATIONARY_30MIN: PENDING_HW
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## Observable state

- Versioned PS mailbox descriptors, queue state, per-object terminal status and
  committed-output flag.
- P6 status, RX payload bytes, frame CRC/payload CRC results, retry counts,
  retry-exhausted, TX fail, maximum consecutive Txd-high cycles, duty violations
  and shutdown reason after every fragment.
- Input and output sizes, CRC32 and SHA256, fragment bitmap/count, session epoch,
  object ID and lane selected for each submitted fragment.
- PS global-timer fragment/object latency, queue high-water mark, backpressure,
  cumulative bytes, goodput and lane utilization.
- Target identity plus immutable bitstream, XSA, ELF, active XDC, pinmap,
  register-map, profile and shutdown-image hashes in every hardware stage.

## Controlled actions

- Host writes a bounded descriptor and object bytes to validated PS DDR ranges.
- PS splits each object into a 32-byte RFAP header plus at most 215 data bytes and
  submits the resulting 1..247-byte payload through the already verified P6 API.
- Application scheduling selects lane mask 0x1, 0x2, alternating 0x1/0x2, or
  replication mask 0x3. Test-only lane-unavailable injection occurs before P6
  submission and never creates a mask above 0x3.
- STOP, ABORT, CLEAR and SHUTDOWN are bounded controls. Hardware wrappers are
  dry-run by default and use shutdown-before plus shutdown-after in a finally
  boundary when explicitly authorized.
- The primary acceptance path is PS input memory -> the real P7 PS ELF and
  application service -> AXI/PL -> the physical TFDU link -> PL/AXI -> PS output
  memory. JTAG/AXI is auxiliary bring-up and cross-check ingress; it cannot set
  the real-PS application PASS by itself.

## Required guarantees

- A partial object is never marked complete. Completion is published last and
  only after fragment geometry, full length, whole-object CRC32 and input/output
  SHA256 all match.
- Identical duplicates are idempotent; different duplicates, stale epochs,
  conflicting metadata, missing fragments and strict-order violations are
  rejected without committing output.
- Queue growth is bounded at eight descriptors. Overflow is a recorded
  backpressure rejection and cannot corrupt already accepted objects.
- Any P6 error, invalid address, timeout, abort, safety violation, wrapper error
  or maximum-runtime breach stops new TX and invokes shutdown. A hardware stage
  is incomplete unless shutdown evidence contains SHUTDOWN_EXIT=0.
- Offline and simulation evidence keep hardware acceptance pending. Only a real
  P7 PS ELF using PS input memory, AXI, the physical TFDU path, PS output memory
  and valid shutdown boundaries may set PS_PL_PHY_PL_PS_APPLICATION_PASS=true.
- P7 permits exactly one final 1800-second stationary run: the first 300 seconds
  are its embedded calibration window and the following 1500 seconds are the
  acceptance window. No separate calibration or two-hour P7 soak is accepted.

## Scope boundary

Any eventual P7 hardware result is limited to stationary two-lane local
application transport. It uses no Ethernet cable, DHCP, TCP board link, motion,
rotation, third lane, or product-final acceptance. P6 mask 0x3 is replication;
application striping is
implemented by alternating single-lane fragments. Current host ingress is
JTAG/AXI plus the PS mailbox; the disabled TCP adapter has not been validated
over a real cable. Software-injected lane unavailability is scheduler fallback
evidence only, not evidence of a real optical fault. Product-final acceptance
remains pending Ethernet, rotation, and target lane-count validation.
