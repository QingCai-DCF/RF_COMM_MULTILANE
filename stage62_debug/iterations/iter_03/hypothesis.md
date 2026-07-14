# Iteration 03 hypothesis

The corrected isolated Case A harness should complete a 30-byte aligned copy
from fixed OCM source to OCM scratch, publish a valid `COPY_OK` first-only
record, preserve the immutable source, and verify the final wipe. A valid PASS
would establish the OCM control only and would provide zero acceptance coverage.
