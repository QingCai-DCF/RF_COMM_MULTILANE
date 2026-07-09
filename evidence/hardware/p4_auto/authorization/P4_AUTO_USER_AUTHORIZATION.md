# P4 Auto User Authorization

generated_at_utc: 2026-07-09T10:03:07+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: RECORDED
reason: user-confirmed supply and no-manual-intervention flags recorded without touching hardware
hardware_actions_executed: false
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

AUTHORIZED_STAGE: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
USER_CONFIRMED_SUPPLY_OK: true
MANUAL_INTERVENTION_REQUIRED: false
ALLOWED_AUTOMATION: Vivado batch, JTAG, XSDB, AXI/JTAG-to-AXI, PS driver, ILA, VIO, debug registers, log parsing
FORBIDDEN: manual scope requirement, manual voltage measurement requirement, unbounded TX, long soak beyond profile, stale bitstream, untracked bitstream
MAX_RUNTIME_PER_STAGE_SEC: profile-bounded
SHUTDOWN_ON_EXIT: required
LOW_DUTY_ONLY_UNTIL_PROTOCOL_PASS: true
AUTHORIZATION_FILE: `.hardware_authorization/P4_AUTO_APPROVED.txt`
AUTHORIZATION_TEMPLATE: `.hardware_authorization/P4_AUTO_APPROVED.txt.template`
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
