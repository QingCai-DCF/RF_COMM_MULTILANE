# P11 ABZ input requirements

No encoder is selected by this document. Candidate incremental resolutions
for engineering comparison are 1024, 2048, and 4096 PPR. With x4 quadrature
decoding their nominal phase quanta are approximately 0.0879°, 0.0439°, and
0.0220°. At 600 rpm (10 rev/s), their combined A/B quadrature edge rates are
40.96 kedge/s, 81.92 kedge/s, and 163.84 kedge/s. These calculations are
selection inputs, not acceptance of an encoder.

The selected ABZ source must freeze:

- PPR and whether it is specified per A cycle or decoded count;
- A/B/Z voltage standard, driver topology, common-mode range, polarity,
  termination, cable/shield, connector, and maximum cable length;
- minimum pulse width, duty/skew, maximum edge rate, input hysteresis,
  synchronization/filter strategy, and metastability/CDC treatment;
- direction convention and legal/illegal transition table;
- Z width/polarity, first-index acquisition, loss-of-Z behavior, and an
  optical or mechanical absolute-reference procedure;
- phase quantization, fixture tolerance, estimator uncertainty, update period
  (initial target `<=50 µs`), data-age limit, and bounded reacquisition.

Before phase validity, after illegal transitions, stale data, edge-rate
overflow, reset, or uncertainty beyond the frozen budget, new TX admission
must be removed and the endpoint must enter receive-only acquisition. Software
may observe and configure the estimator but may not bypass the physical
permit or PL safety path.
