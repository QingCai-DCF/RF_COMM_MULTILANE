"""Auto-generated P8E build profile constants; do not edit."""
P8E_BUILD_MATRIX_SHA256 = '5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502'
P8E_BUILD_HASH_LOW = 0xF7EDC502
P8E_BUILD_HASH_HIGH = 0x28484E8C
PROFILES = {
    'Z7010_2LANE_DEV_IMPLEMENTATION': {'PROFILE_ID': 7344130, 'PROFILE_VERSION': 1, 'ENDPOINT_ROLE': 0, 'LANE_COUNT': 2, 'PHYSICAL_MODULE_COUNT': 2, 'TX_WINDOW': 32, 'RX_WINDOW': 32, 'SACK_BITS': 32, 'DESCRIPTOR_RING_DEPTH': 64, 'AXIS_DATA_WIDTH': 64, 'CLOCK_TARGET_MHZ': 64, 'part': 'xc7z010clg400-1', 'top_module': 'z7010_2lane_dev_top', 'source_manifest': 'config/source_manifests/z7010_2lane_dev.json', 'board_pinmap': 'board_profiles/ax7010_tfdu_j10_j11_pinmap.csv', 'board_xdc': 'constraints/active/PORT1.generated.xdc'},
    'Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION': {'PROFILE_ID': 7348472, 'PROFILE_VERSION': 1, 'ENDPOINT_ROLE': 1, 'LANE_COUNT': 8, 'PHYSICAL_MODULE_COUNT': 32, 'TX_WINDOW': 64, 'RX_WINDOW': 64, 'SACK_BITS': 64, 'DESCRIPTOR_RING_DEPTH': 64, 'AXIS_DATA_WIDTH': 64, 'CLOCK_TARGET_MHZ': 64, 'part': 'xc7z020clg400-2', 'top_module': 'z7020_fixed_core_timing_top', 'source_manifest': 'config/source_manifests/z7020_fixed_core.json', 'board_pinmap': 'PENDING_D12', 'board_xdc': 'PENDING_D12'},
    'Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION': {'PROFILE_ID': 7348392, 'PROFILE_VERSION': 1, 'ENDPOINT_ROLE': 2, 'LANE_COUNT': 8, 'PHYSICAL_MODULE_COUNT': 8, 'TX_WINDOW': 64, 'RX_WINDOW': 64, 'SACK_BITS': 64, 'DESCRIPTOR_RING_DEPTH': 64, 'AXIS_DATA_WIDTH': 64, 'CLOCK_TARGET_MHZ': 64, 'part': 'xc7z020clg400-2', 'top_module': 'z7020_rotating_core_timing_top', 'source_manifest': 'config/source_manifests/z7020_rotating_core.json', 'board_pinmap': 'PENDING_D12', 'board_xdc': 'PENDING_D12'},
}
