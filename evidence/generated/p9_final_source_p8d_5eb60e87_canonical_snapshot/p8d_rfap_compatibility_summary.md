# P8D RFAP v1/vNext compatibility

- Status: `PASS`
- Test ID: `P8D-RFAP-V1-VNEXT-COMPATIBILITY`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `5eb60e875e459f6393d1a6ddb8519e733883f54d`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "evidence/generated/p9_final_source_p8d_5eb60e87/p8d_raw/formal_5eb60e875e45/rfap_compatibility.log",
  "generated_utc": "2026-07-29T09:04:54.781772Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "raw_summary": {
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
    "NO_HARDWARE_ACTIONS_EXECUTED": true,
    "atomic_publish_count": 1,
    "capability_mismatch_rejected": true,
    "legacy_header_bytes": 32,
    "legacy_useful_chunk_bytes": 215,
    "maximum_inflight_bytes": 65536,
    "mixed_version_malformed_rejected": true,
    "negotiation_matrix": {
      "legacy_request_vnext_capable_peer": 1,
      "v1_to_v1": 1,
      "vnext_request_legacy_peer": 1,
      "vnext_to_vnext": 2
    },
    "partial_object_publish_count": 0,
    "profile": "P8D_MULTI_PROFILE_OFFLINE",
    "reset_during_negotiation": "PASS",
    "rfap_v1_vector_count": 1200,
    "rfap_v1_vector_path": "tests/vectors/p7_app_protocol_vectors.json",
    "rfap_v1_vector_sha256": "b1015c343dec626328a3b5a1295754b065c1d28a681c87ca71dcb533463d36df",
    "schema_version": 1,
    "session_renegotiation": "PASS",
    "stale_replay_rejection": "PASS",
    "status": "PASS",
    "streamed_object_bytes": 67108864,
    "streaming_complete": true,
    "test_id": "P8D-RFAP-V1-VNEXT-COMPATIBILITY",
    "vnext_header_bytes": 48
  },
  "schema_version": 1,
  "source_commit": "5eb60e875e459f6393d1a6ddb8519e733883f54d",
  "status": "PASS",
  "test_id": "P8D-RFAP-V1-VNEXT-COMPATIBILITY"
}
```
