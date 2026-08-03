# P10.2 four-lane offline architecture

P10.2 parameterizes the existing P9/P10.1R transport; it does not create a second protocol fork. The board wrappers select `LANE_COUNT=4`, while the core continues to elaborate at 2, 4, and 8 lanes. The frozen two-lane wire encoding and register addresses remain unchanged. Four lanes consume an additional lane-ID bit in the existing header byte, and the new telemetry is appended as a versioned 128-word atomic snapshot at `0xB00`.

Each endpoint has exactly one active-high `GLOBAL_PERMIT`. Lane health, admission, duty headroom, mapping validity and retry eligibility are local gates, not additional permits. Permit low, reset, fault, or effective full shutdown forces every physical Txd low and every SD high. Receive-only operation may remain enabled with the permit low.

The four logical lanes are `F0-R0`, `F1-R1`, `F2-R2`, and `F3-R3`. A received DATA or ACK is accepted only when its endpoint source identity, direction, configured lane mask and encoded logical lane all match the physical receiver lane. Local physical Txd only quarantines the corresponding receive decoder; it cannot blank the other three lanes.

The scheduler accepts masks `0x1..0xF`, equal or weighted service, unavailable-lane removal, retry migration and recovery. ACKed entries cannot migrate. The selected offline resource point is 32 global outstanding frames, a 32-bit SACK window, 32-frame bundle bursts, ACK threshold 32, and four objects in flight. This is the smallest modeled point meeting the 8 Mbit/s hard feasibility target; it preserves the existing 32-bit ACK wire format.

The PL LEDs are diagnostic taps only. In the four-lane profile LED1..LED4 indicate combined final-TX or accepted-remote-RX activity for lanes 0..3. They are active low and are forced off during reset or effective shutdown. They do not prove electrical or optical success and have no path into safety, scheduling, admission, or flow control.

All P10.2 throughput, echo, crosstalk and streaming results are offline model or simulation evidence. P10.3 remains pending physical wiring, eight accepted modules, power qualification, new immutable artifacts and a new current-run authorization.
