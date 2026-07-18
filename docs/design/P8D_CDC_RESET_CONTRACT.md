# P8D Clock-Domain and Reset Contract

The P8D protocol core, scheduler, AXI elastic boundaries, behavioral rings, and retained payload store are synchronous to one `core_clk` in the current portable top. There is no hidden multi-bit crossing inside `ir_data_plane_top`. A platform that uses a distinct DMA/AXI clock must place an async FIFO for payload beats and a proven handshake for descriptor/control metadata at the boundary.

`ir_p8d_async_descriptor_bridge` is the supplied bundled-data toggle handshake. The source registers and holds the entire metadata word before toggling request and does not modify it until a two-flop synchronized acknowledgement returns. The destination synchronizes only the toggle and captures the already-stable bus. Both toggles and valid state clear on coordinated session reset. It is not valid to reset one side independently and continue the old session.

Reset assertion is asynchronous. Each platform must synchronize reset deassertion separately in every clock domain, hold traffic disabled until both domains report ready, and issue a new session/ring generation. Reset or abort increments descriptor generation, clears ARQ ownership, rejects old completions, and never resumes a partial physical frame. P8C owns final Txd reset/kill, so data-plane reset cannot create a Txd glitch or illegal one-hot output.

XSIM directly checks metadata stability, ordering, no loss, and no duplicate at 1:1, 2:1, 3:2, and non-integer asynchronous phase relationships. P8E remains responsible for full dual-target CDC reports, timing exceptions, implementation timing, and board-clock integration.
