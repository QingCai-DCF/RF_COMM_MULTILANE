# Iteration 04 hypothesis

With Case A established, Case B should discriminate the first DDR boundary by
copying 30 aligned bytes from fixed OCM source to DDR scratch. The harness must
first prove the immutable OCM source, DDR canary fixture, and control record by
independent prestart readback. Any DDR prestart mismatch is itself a fail-closed
lower-level result and must prevent CPU release.
