# Software Offline Policy

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

PS driver checks are syntax-only or mock-MMIO checks. Host checks use offline
mock transport only. Unknown or legacy hardware-facing software is not runnable
without explicit hardware authorization.
