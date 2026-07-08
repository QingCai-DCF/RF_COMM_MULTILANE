# G1 Frozen Lane0 Baseline

Generated: 2026-06-27T17:08:00+08:00

This file freezes the latest verified single-lane G1 baseline. It is evidence
for the constrained project workflow, not consultation material and not final
full-target acceptance.

## Scope

- Stage: `G1_LANE0_FRAG255_HW_SMOKE_PASS_PENDING_LONG_SOAK`
- Hardware scope: one AX7010 board with board-internal TFDU A/B lane0 loopback
- Communication mode: single-lane half-duplex A-to-B payload with ACK return
- Current physical run cap: no continuous TFDU-driving run above 10 minutes
- Ethernet/TCP/DHCP hardware acceptance: deferred because the board has no
  Ethernet cable connected
- Rotation acceptance: deferred because no rotating fixture is available
- Final 8-lane/32 Mbit/s/16 Mbit/s target: not claimed by this baseline

## Key Configuration

| item | value |
| --- | --- |
| Vivado/Vitis | 2023.1 |
| part | xc7z010 |
| lane count in current build | 2-capable design, test uses lane0 only |
| tested lane mask | `0x00000001` |
| session | `0x2201` |
| application payload bytes | `256` |
| raw packet bytes | `264` |
| fragment bytes | `255` |
| max retry | `12` |
| guard cycles | `4096` |
| preamble cycles | `16` |
| chip max | `7` |
| A RX detect window | `0..5` |
| B RX detect window | `0..7` |
| preamble realign | `0` |
| PS max outstanding | `0` |

## Artifact Hashes

| artifact | sha256 |
| --- | --- |
| bit | `DE38629FC94A4DF812B2B59C82482CD7CB8592B12F45E46E3FC6F337EC51240C` |
| ltx | `32805D7AE4FDFB411F74E821A6CCF99702C879E825318548224640062F18913C` |
| xsa | `6D87CF1ECB7602DE1358B40F1135234B147F06F35F23BC1B0910E09FCDCF34DF` |
| elf | `076FBB4F08FEC3B17BCF30719D5BA259671DF327BF9267511E606A04148FAC0C` |
| shutdown bit | `F72680DD3EDA852E64F0B844F54D372368FDB3BDEB775B75507623E6DC167765` |
| hard constraint | `CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11` |
| UART evidence copy | `321F06EC55B43CF07647E21B1EDDCA0B3F2B17B77F2614E977A50F41CB31E9C4` |
| hardware smoke summary | `0AB1006FCFB30350ED5304CBDA0C31E5E8DA546FB66CB6B7FD1DA22364B22F52` |
| inner hardware run summary | `8C0063B55F141784E2D600ECAD73ACCF832FCD4B9B5EB123640EDC9E771946AA` |
| shutdown log | `1E89E6BEB87795BCBFD8AA374BE45DA2A4B844AB1B9AA01846D99BC70E571523` |
| guard4096 frag255 simulation log | `E4094C25D6C86B60878848AB19C72C4878FCDAB7EF71A4865B30AA5389801091` |
| G1 artifact hash index | `E72E0E7EAA67631A4C5BE16061FF872697B9C969AC9BA76570AE626868401CBD` |

## Evidence Files

| evidence | path |
| --- | --- |
| build summary | `reports/g0_lane0_build_20260627_165200_066_35396.summary.txt` |
| build validation | `reports/g1_lane0_smoke_build_validated_20260627_170037.summary.txt` |
| hardware wrapper summary | `reports/g1_lane0_hw_smoke_safe_20260627_170053.summary.txt` |
| inner hardware run summary | `reports/lane0_hw_loopback_safe_20260627_170053.summary.txt` |
| UART original | `reports/uart_lane0_hw_loopback_safe_20260627_170053.log` |
| UART frozen copy | `evidence/G1_freeze/G1_frozen_uart.log` |
| shutdown log | `reports/program_tfdu_shutdown_after_lane0_loopback_20260627_170053.log` |
| sim estimate | `reports/g1_hw_smoke_sim_guard4096_frag255_20260627_165120.log` |
| hash index | `reports/G1_artifacts_hashes.txt` |

## Verified Result

| metric | value |
| --- | ---: |
| sent | 20194 |
| rx_ok | 20194 |
| tx_fail | 0 |
| rx_timeout | 0 |
| rx_bad | 0 |
| rx_mismatch | 0 |
| loss | 0.0% |
| window payload throughput | 1.749 Mbit/s |
| last_error | none |
| shutdown_exit | 0 |
| TFDU drive window to shutdown end | 77.1 s |

Simulation with the same guard and `FRAGMENT_BYTES=255` reported
`app_mbps=1.882`, so the measured board result is close to the expected
protocol-level range.

## Not Yet Proven

- G1 one-hour stationary soak is not proven by this short smoke.
- Four-direction lane0/lane1 matrix is not proven by this file.
- Real Ethernet TCP/DHCP is not proven because no Ethernet cable is connected.
- Real rotating 600 rpm and 2-hour rotating communication are not proven.
- Final 8-lane maximum rate targets are not proven.

## Board Safety State

After the physical run, `tfdu_shutdown_j10_j11.bit` was programmed
successfully. The shutdown log contains:

```text
TFDU_SHUTDOWN_PROGRAMMED C:/Users/user/Documents/RF_COMM/shutdown_bitstream/tfdu_shutdown_j10_j11.bit
```
