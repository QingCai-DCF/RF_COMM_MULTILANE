# P7 Application Protocol

generated_at_utc: 2026-07-11T14:25:17+00:00
P7_APPLICATION_PROTOCOL: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Details

- header_bytes: 32
- max_chunk_bytes: 215
- p6_payload_bytes: 247
- run: {"command": "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python314\\python.exe C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\tools\\run_p7_protocol_vectors.py --json-summary", "returncode": 0}
- C_PYTHON_BYTE_FOR_BYTE: PASS
- HARDWARE_ACCEPTANCE: PENDING_HW
- INVALID_FIELD_ERROR_MATCH: PASS
- P7_PROTOCOL_VECTORS: PASS
- YAML_PYTHON_C_CONTRACT: PASS
- c_harness: {"P7_C_GOLDEN_VECTOR_HARNESS": "PASS", "failures": 0, "flag_control": 8, "flag_first": 1, "flag_last": 2, "flag_retransmit": 4, "header_bytes": 32, "invalid_vectors": 20, "lane0_only": 1, "lane1_only": 2, "max_chunk_bytes": 215, "max_object_bytes": 8388608, "p6_max_payload_bytes": 247, "replicate_0x3": 4, "stripe_round_robin": 3, "total_vectors": 1200, "valid_vectors": 1180}
- compiler: gcc.exe (GCC) 8.3.0
- compiler_path: D:\Xilinx\Vitis_HLS\2023.1\tps\mingw\8.3.0\win64.o\nt\bin\gcc.exe
- hardware_actions_executed: False
- invalid_vectors: 20
- network_used: False
- valid_vectors: 1180
- vector_count: 1200
- vector_file: tests\vectors\p7_app_protocol_vectors.json
- vector_sha256: b1015c343dec626328a3b5a1295754b065c1d28a681c87ca71dcb533463d36df
