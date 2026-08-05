# P10.3F DMA-reset descriptor gate diagnosis

Status: `DIAGNOSED`

The immutable failed run `p10_3f_full_20260805T025754Z_650b94cf_1ff0885f_82ef5093` reached the planned DMA-reset boundary, killed TX, froze both forensic recorders, archived both captures, rebooted both endpoints, and completed the XSDB stage with `PASS`. Final dual-board shutdown also passed.

The host evaluator then produced a false failure because it treated the legacy mailbox `descriptor_leak=4` snapshot as a post-recovery leak. That snapshot was taken at the reset boundary: each endpoint had submitted eight descriptors, completed four, and therefore had four deliberately in flight. The canonical P10.1 post-reset result independently records `descriptors_reclaimed_by_reset=4`, while all canonical leak and double-completion counters are zero.

The remediation is limited to the host evaluator. For expected reset vectors only, it reconciles the reset-boundary outstanding count with the canonical reclaimed count and still requires zero post-reset leaks, zero legacy and canonical double completion, and exact descriptor accounting. Normal cases keep the original zero-leak rule. The failed run remains failed and is not promoted; a new immutable campaign and hardware run are required.

A read-only replay of the failed stage's exact raw inputs under the corrected evaluator produced `PASS` with no errors. This replay is diagnostic only and does not promote the immutable failed run.
