# P10.1 preflight receiver-prime timeout root cause

Root-cause status: **PASS**  
Affected hardware runs: **FAIL, safely shut down**

The timeout reproduced twice with the exact same terminal state. The `failed_object_diagnostic` vector transfers 1 MiB while the selected immutable runtime configuration uses 512 KiB objects. It therefore contains two objects. Its 25% abort ordinal is computed with integer division: `2 / 4 = 0`.

The host publishes the receiver command first and waits for `PRIMED` before publishing the sender. At recovery ordinal zero, receiver firmware briefly publishes `PRIMED`, immediately completes the expected recovery without a launched sender, and settles in `COMPLETE (7)`. A 1 ms host poll is not guaranteed to observe the transient state, matching both captures: response/sequence `0x3F2`, main state `COMPLETE`, P10.1 state `7`, status `0`, and safe PL/PHY state.

The scoped fix is to make only this diagnostic vector 2 MiB. Four 512 KiB objects yield abort ordinal one, so ordinal zero remains genuinely primed until the sender is launched. This changes the immutable host plan and authorization hash only; RTL, firmware, protocol, bitstreams, XSAs, BSPs, and ELFs remain unchanged.

The earlier single-run “transient timeout” diagnosis remains preserved as history but is superseded by this two-run arithmetic/state-machine explanation.
