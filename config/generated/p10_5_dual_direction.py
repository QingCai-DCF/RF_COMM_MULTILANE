# Generated from config/p10_5_dual_direction.yaml; do not edit.
P10_5_CAPABILITY_VERSION = 1
P10_5_CAPABILITY_WORD = 0x5035021F
P10_5_CONFIG_SHA256 = "fb79523627256fb10258e13bc5bbd1e1c0fab5214b916bbbac44aeb17e5a1db6"
P10_5_CONFIG_HASH_LOW = 0x7E5A1DB6
LANE_COUNT = 4
ACTIVE_LANE_MASK = 0xF
F_TO_R_LANE_MASK = 0x3
R_TO_F_LANE_MASK = 0xC
MODE_LEGACY_BUNDLE_HALF_DUPLEX = 0
MODE_SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL = 1
DIR_F_TO_R = 0
DIR_R_TO_F = 1
OUTSTANDING = 32
SACK_BITS = 32
ACK_THRESHOLD = 8
ACK_MAX_DELAY_CYCLES = 64000
TARGET_GOODPUT_BPS = 4000000
FORMAL_RUNTIME_SECONDS = 1800
AUTONOMOUS_DUAL_STREAM_COMMAND = 15
MAX_STREAM_BYTES = 0x70000000
INTERNAL_OBJECT_BYTES = 262144
DESCRIPTOR_BYTES = 65536
RUNTIME_RING_DEPTH = 32
RUNTIME_BUFFER_COUNT = 4
RUNTIME_DESCRIPTOR_BATCH = 8

def validate_masks(active, f_to_r, r_to_f, require_both=True):
    known = (1 << LANE_COUNT) - 1
    if active & ~known or f_to_r & ~known or r_to_f & ~known:
        return False, "UNKNOWN_LANE_BIT"
    if f_to_r & r_to_f:
        return False, "ROLE_MASK_OVERLAP"
    if (f_to_r | r_to_f) & ~active:
        return False, "ROLE_MASK_OUTSIDE_ACTIVE"
    if require_both and (not f_to_r or not r_to_f):
        return False, "EMPTY_REQUIRED_DIRECTION"
    return True, "NONE"
