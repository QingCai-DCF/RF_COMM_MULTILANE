# Iteration 02 hypothesis

The isolated Stage62 microtest A (`OCM fixed source -> OCM scratch`, length 30,
source/destination alignment 0) should provide a valid, zero-coverage control
record and let the official host postprocessor classify the copy boundary.

R35 did not validly test that hypothesis. The hardware transaction reached raw
terminal markers, but the official wrapper failed in host postprocessing before
it could publish a terminal summary. R35 is therefore invalid for diagnosis and
acceptance.
