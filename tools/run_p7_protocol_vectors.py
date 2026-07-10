#!/usr/bin/env python3
"""Generate and cross-check deterministic RFAP v1 Python/C golden vectors.

This runner is deliberately offline: it compiles a native C harness and does
not open a network connection or invoke any hardware-capable tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import p7_app_protocol as rfap


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VECTOR_COUNT = 1200
MINIMUM_VECTOR_COUNT = 1000
OBJECT_HEX_LIMIT = 4096


class VectorRunError(RuntimeError):
    """A deterministic generation, compilation, or comparison gate failed."""


def _scalar(text: str) -> Any:
    value = text.strip()
    if value == "":
        return {}
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        entries = value[1:-1].strip()
        return [] if not entries else [_scalar(item) for item in entries.split(",")]
    try:
        return int(value, 0)
    except ValueError:
        return value


def load_contract(path: Path) -> dict[str, Any]:
    """Load the small, mapping-only project YAML without an external package."""
    result: dict[str, Any] = {}
    parent: str | None = None
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent not in (0, 2) or ":" not in raw_line:
            raise VectorRunError(f"unsupported YAML syntax at {path}:{number}")
        key, value = raw_line.strip().split(":", 1)
        parsed = _scalar(value)
        if indent == 0:
            result[key] = parsed
            parent = key if parsed == {} else None
        else:
            if parent is None or not isinstance(result.get(parent), dict):
                raise VectorRunError(f"orphan nested YAML field at {path}:{number}")
            result[parent][key] = parsed
    return result


def check_python_contract(contract: dict[str, Any]) -> None:
    expected = {
        "name": "RF_COMM_APPLICATION_PROTOCOL",
        "version": rfap.VERSION,
        "byte_order": "little_endian",
        "magic_ascii": rfap.MAGIC.decode("ascii"),
        "header_bytes": rfap.HEADER_BYTES,
        "p6_max_payload_bytes": rfap.P6_MAX_PAYLOAD_BYTES,
        "max_chunk_bytes": rfap.MAX_CHUNK_BYTES,
        "max_object_bytes": rfap.MAX_OBJECT_BYTES,
        "descriptor_queue_depth": 8,
        "out_of_order_window": 0,
    }
    expected_flags = {
        "first": rfap.FLAG_FIRST,
        "last": rfap.FLAG_LAST,
        "retransmit": rfap.FLAG_RETRANSMIT,
        "control": rfap.FLAG_CONTROL,
    }
    expected_lane_policies = {
        "lane0_only": 1,
        "lane1_only": 2,
        "stripe_round_robin": 3,
        "replicate_0x3": 4,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise VectorRunError(
                f"contract mismatch for {key}: YAML={contract.get(key)!r}, Python={value!r}"
            )
    if contract.get("flags") != expected_flags:
        raise VectorRunError(
            f"contract mismatch for flags: YAML={contract.get('flags')!r}, Python={expected_flags!r}"
        )
    if contract.get("lane_policies") != expected_lane_policies:
        raise VectorRunError(
            "contract mismatch for lane_policies: "
            f"YAML={contract.get('lane_policies')!r}, expected={expected_lane_policies!r}"
        )
    constraints = contract.get("constraints")
    if not isinstance(constraints, dict):
        raise VectorRunError("constraints mapping is missing")
    required_constraints = {
        "allowed_lane_masks": [1, 2, 3],
        "network_allowed": False,
        "motion_allowed": False,
        "available_lanes": 2,
        "startup_wait_us_min": 500,
        "continuous_txd_high_us_hard_limit": 80,
    }
    if constraints != required_constraints:
        raise VectorRunError(
            f"constraint mismatch: YAML={constraints!r}, expected={required_constraints!r}"
        )


def deterministic_bytes(size: int, seed: int) -> bytes:
    pattern = bytes(
        ((index * 197 + seed * 101 + (seed >> 8) + (index ^ seed)) & 0xFF)
        for index in range(256)
    )
    return (pattern * ((size + 255) // 256))[:size]


def _header_fields(header: rfap.AppHeader) -> dict[str, int]:
    return {
        "session_epoch": header.session_epoch,
        "object_id": header.object_id,
        "total_length": header.total_length,
        "fragment_index": header.fragment_index,
        "fragment_count": header.fragment_count,
        "chunk_length": header.chunk_length,
        "object_crc32": header.object_crc32,
        "flags": header.flags,
        "reserved": header.reserved,
    }


def make_valid_vector(index: int) -> dict[str, Any]:
    boundary_sizes = (
        0,
        1,
        2,
        30,
        214,
        215,
        216,
        246,
        247,
        248,
        430,
        431,
        432,
        1024,
        4096,
        65536,
        1048576,
        rfap.MAX_OBJECT_BYTES,
    )
    if index < len(boundary_sizes):
        size = boundary_sizes[index]
    else:
        mixed = (index * 2654435761) ^ (index << 11) ^ (index >> 3)
        size = mixed % 8193
    data = deterministic_bytes(size, index + 1)
    count = rfap.fragment_count(size)
    if count == 1:
        fragment_index = 0
    elif index % 4 == 0:
        fragment_index = 0
    elif index % 4 == 1:
        fragment_index = count - 1
    elif index % 4 == 2:
        fragment_index = count // 2
    else:
        fragment_index = ((index * 4051) + 17) % count
    start = fragment_index * rfap.MAX_CHUNK_BYTES
    chunk = data[start : start + rfap.MAX_CHUNK_BYTES]
    flags = 0
    if fragment_index == 0:
        flags |= rfap.FLAG_FIRST
    if fragment_index == count - 1:
        flags |= rfap.FLAG_LAST
    if index % 5 == 0:
        flags |= rfap.FLAG_RETRANSMIT
    if index % 7 == 0:
        flags |= rfap.FLAG_CONTROL
    special_u32 = (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
    session_epoch = (
        special_u32[index]
        if index < len(special_u32)
        else (0x10203040 + index * 0x01010101) & 0xFFFFFFFF
    )
    object_id = (
        special_u32[-(index + 1)]
        if index < len(special_u32)
        else (0xA5A50000 ^ (index * 0x9E3779B1)) & 0xFFFFFFFF
    )
    header = rfap.AppHeader(
        session_epoch=session_epoch,
        object_id=object_id,
        total_length=size,
        fragment_index=fragment_index,
        fragment_count=count,
        chunk_length=len(chunk),
        object_crc32=rfap.crc32(data),
        flags=flags,
        reserved=0,
    )
    fragment = rfap.AppFragment(header=header, chunk=chunk)
    header_bytes = header.encode()
    encoded = fragment.encode()
    if rfap.AppHeader.decode(header_bytes) != header:
        raise VectorRunError(f"Python header roundtrip failed at valid vector {index}")
    if rfap.AppFragment.decode(encoded) != fragment:
        raise VectorRunError(f"Python fragment roundtrip failed at valid vector {index}")
    checked_object = size <= OBJECT_HEX_LIMIT
    return {
        "kind": "valid",
        "name": f"valid_{index:04d}_size_{size}_fragment_{fragment_index}",
        **_header_fields(header),
        "header_hex": header_bytes.hex(),
        "chunk_hex": chunk.hex(),
        "encoded_hex": encoded.hex(),
        "object_hex": data.hex() if checked_object else "",
        "chunk_crc32": rfap.crc32(chunk),
        "check_object_crc": int(checked_object),
    }


def _valid_header(
    *,
    total_length: int = 1,
    fragment_index: int = 0,
    flags: int | None = None,
) -> rfap.AppHeader:
    count = rfap.fragment_count(total_length)
    chunk_length = (
        0
        if total_length == 0
        else min(rfap.MAX_CHUNK_BYTES, total_length - fragment_index * rfap.MAX_CHUNK_BYTES)
    )
    actual_flags = flags
    if actual_flags is None:
        actual_flags = (rfap.FLAG_FIRST if fragment_index == 0 else 0) | (
            rfap.FLAG_LAST if fragment_index == count - 1 else 0
        )
    return rfap.AppHeader(
        session_epoch=0x10203040,
        object_id=0x50607080,
        total_length=total_length,
        fragment_index=fragment_index,
        fragment_count=count,
        chunk_length=chunk_length,
        object_crc32=rfap.crc32(deterministic_bytes(total_length, 0x55)),
        flags=actual_flags,
    )


def _mutate(raw: bytes, offset: int, payload: bytes) -> bytes:
    result = bytearray(raw)
    result[offset : offset + len(payload)] = payload
    return bytes(result)


def _python_error(action: Callable[[], object], name: str) -> str:
    try:
        action()
    except rfap.ProtocolError as error:
        return error.code
    raise VectorRunError(f"invalid vector {name} was accepted by Python")


def make_invalid_vectors() -> list[dict[str, Any]]:
    base_header = _valid_header()
    base_header_raw = base_header.encode()
    base_fragment_raw = rfap.AppFragment(base_header, b"B").encode()
    two_first = _valid_header(total_length=216, fragment_index=0)
    two_last = _valid_header(total_length=216, fragment_index=1)
    cases: list[tuple[str, str, bytes | rfap.AppHeader | int, bytes | None]] = [
        ("header_truncated", "decode_header", base_header_raw[:-1], None),
        ("bad_magic", "decode_header", _mutate(base_header_raw, 0, b"X"), None),
        ("bad_version", "decode_header", _mutate(base_header_raw, 4, b"\x02"), None),
        ("bad_header_length", "decode_header", _mutate(base_header_raw, 6, struct.pack("<H", 31)), None),
        ("object_too_large", "decode_header", _mutate(base_header_raw, 16, struct.pack("<I", rfap.MAX_OBJECT_BYTES + 1)), None),
        ("fragment_count_zero", "decode_header", _mutate(base_header_raw, 22, b"\x00\x00"), None),
        ("fragment_index_range", "decode_header", _mutate(base_header_raw, 20, b"\x01\x00"), None),
        ("chunk_too_large", "decode_header", _mutate(base_header_raw, 24, struct.pack("<H", rfap.MAX_CHUNK_BYTES + 1)), None),
        ("reserved_nonzero", "decode_header", _mutate(base_header_raw, 26, b"\x01\x00"), None),
        ("flags_unknown", "decode_header", _mutate(base_header_raw, 5, bytes([base_header.flags | 0x80])), None),
        ("first_flag_missing", "decode_header", _mutate(base_header_raw, 5, bytes([rfap.FLAG_LAST])), None),
        ("last_flag_unexpected", "decode_header", _mutate(two_first.encode(), 5, bytes([rfap.FLAG_FIRST | rfap.FLAG_LAST])), None),
        ("first_flag_unexpected", "decode_header", _mutate(two_last.encode(), 5, bytes([rfap.FLAG_FIRST | rfap.FLAG_LAST])), None),
        ("last_flag_missing", "decode_header", _mutate(two_last.encode(), 5, b"\x00"), None),
        ("fragment_count_geometry", "decode_header", _mutate(two_first.encode(), 22, struct.pack("<H", 3)), None),
        ("chunk_length_geometry", "decode_header", _mutate(base_header_raw, 24, b"\x00\x00"), None),
        ("fragment_missing_chunk", "decode_fragment", base_header_raw, None),
        ("fragment_trailing_byte", "decode_fragment", base_fragment_raw + b"\x00", None),
        ("encode_chunk_size", "encode_fragment", base_header, b""),
        ("fragment_count_too_large", "fragment_count", rfap.MAX_OBJECT_BYTES + 1, None),
    ]
    vectors: list[dict[str, Any]] = []
    for name, operation, value, chunk in cases:
        if operation == "decode_header":
            assert isinstance(value, bytes)
            error = _python_error(lambda value=value: rfap.AppHeader.decode(value), name)
            vector = {
                "kind": "invalid",
                "name": name,
                "operation": operation,
                "expected_error": error,
                "raw_hex": value.hex(),
            }
        elif operation == "decode_fragment":
            assert isinstance(value, bytes)
            error = _python_error(lambda value=value: rfap.AppFragment.decode(value), name)
            vector = {
                "kind": "invalid",
                "name": name,
                "operation": operation,
                "expected_error": error,
                "raw_hex": value.hex(),
            }
        elif operation == "encode_fragment":
            assert isinstance(value, rfap.AppHeader) and isinstance(chunk, bytes)
            error = _python_error(
                lambda value=value, chunk=chunk: rfap.AppFragment(value, chunk).encode(), name
            )
            vector = {
                "kind": "invalid",
                "name": name,
                "operation": operation,
                "expected_error": error,
                **_header_fields(value),
                "chunk_hex": chunk.hex(),
            }
        else:
            assert isinstance(value, int)
            error = _python_error(lambda value=value: rfap.fragment_count(value), name)
            vector = {
                "kind": "invalid",
                "name": name,
                "operation": operation,
                "expected_error": error,
                "total_length": value,
            }
        vectors.append(vector)
    expected_codes = {
        "HEADER_TRUNCATED",
        "MAGIC",
        "VERSION",
        "HEADER_LENGTH",
        "OBJECT_TOO_LARGE",
        "FRAGMENT_COUNT_ZERO",
        "FRAGMENT_INDEX_RANGE",
        "CHUNK_TOO_LARGE",
        "RESERVED_NONZERO",
        "FLAGS_UNKNOWN",
        "FIRST_FLAG",
        "LAST_FLAG",
        "FRAGMENT_COUNT",
        "CHUNK_LENGTH",
        "FRAGMENT_SIZE",
        "CHUNK_SIZE",
    }
    actual_codes = {vector["expected_error"] for vector in vectors}
    if not expected_codes <= actual_codes:
        raise VectorRunError(f"invalid vector coverage missing {sorted(expected_codes - actual_codes)}")
    return vectors


def write_vectors(path: Path, valid: list[dict[str, Any]], invalid: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": "rfap-v1-golden-v1",
        "generator": "tools/run_p7_protocol_vectors.py",
        "deterministic": True,
        "byte_order": "little_endian",
        "vector_count": len(valid) + len(invalid),
        "valid_vector_count": len(valid),
        "invalid_vector_count": len(invalid),
    }
    lines = ["{", f'  "metadata":{json.dumps(metadata, separators=(",", ":"))},', '  "valid_vectors":[']
    for index, vector in enumerate(valid):
        suffix = "," if index + 1 < len(valid) else ""
        lines.append(json.dumps(vector, separators=(",", ":"), sort_keys=True) + suffix)
    lines.append('  ],')
    lines.append('  "invalid_vectors":[')
    for index, vector in enumerate(invalid):
        suffix = "," if index + 1 < len(invalid) else ""
        lines.append(json.dumps(vector, separators=(",", ":"), sort_keys=True) + suffix)
    lines.extend(["  ]", "}", ""])
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_gcc(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    for executable in ("gcc", "gcc.exe"):
        located = shutil.which(executable)
        if located:
            candidates.append(Path(located))
    candidates.extend(
        [
            Path(r"D:\Xilinx\Vitis_HLS\2023.1\tps\mingw\8.3.0\win64.o\nt\bin\gcc.exe"),
            Path(r"D:\Xilinx\Vitis_HLS\2023.1\tps\win64\msys64\mingw64\bin\gcc.exe"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise VectorRunError("SKIP_WITH_REASON: native MinGW GCC was not found")


def run_checked(command: list[str], *, env: dict[str, str], log_path: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    log_path.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        + "EXIT_CODE=" + str(completed.returncode) + "\n"
        + "STDOUT\n" + completed.stdout
        + "\nSTDERR\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise VectorRunError(
            f"command failed with exit {completed.returncode}; see {log_path.relative_to(ROOT)}"
        )
    return completed


def parse_harness_summary(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "P7_C_GOLDEN_VECTOR_HARNESS" in parsed:
            return parsed
    raise VectorRunError("C harness did not emit its JSON result")


def check_c_contract(summary: dict[str, Any], contract: dict[str, Any]) -> None:
    mapping = {
        "header_bytes": contract["header_bytes"],
        "p6_max_payload_bytes": contract["p6_max_payload_bytes"],
        "max_chunk_bytes": contract["max_chunk_bytes"],
        "max_object_bytes": contract["max_object_bytes"],
        "flag_first": contract["flags"]["first"],
        "flag_last": contract["flags"]["last"],
        "flag_retransmit": contract["flags"]["retransmit"],
        "flag_control": contract["flags"]["control"],
        "lane0_only": contract["lane_policies"]["lane0_only"],
        "lane1_only": contract["lane_policies"]["lane1_only"],
        "stripe_round_robin": contract["lane_policies"]["stripe_round_robin"],
        "replicate_0x3": contract["lane_policies"]["replicate_0x3"],
    }
    for key, expected in mapping.items():
        if summary.get(key) != expected:
            raise VectorRunError(
                f"C/YAML contract mismatch for {key}: C={summary.get(key)!r}, YAML={expected!r}"
            )


def relative_or_absolute(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.vector_count < MINIMUM_VECTOR_COUNT:
        raise VectorRunError(
            f"--vector-count must be at least {MINIMUM_VECTOR_COUNT}, got {args.vector_count}"
        )
    contract_path = ROOT / "config" / "p7_app_protocol.yaml"
    contract = load_contract(contract_path)
    check_python_contract(contract)
    invalid = make_invalid_vectors()
    valid_count = args.vector_count - len(invalid)
    if valid_count <= 0:
        raise VectorRunError("vector count is smaller than mandatory invalid coverage")
    valid = [make_valid_vector(index) for index in range(valid_count)]
    vector_path = relative_or_absolute(args.vectors).resolve()
    vector_sha256 = write_vectors(vector_path, valid, invalid)

    build_dir = relative_or_absolute(args.build_dir).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    gcc = find_gcc(args.gcc)
    executable = build_dir / "rf_app_protocol_vectors.exe"
    env = os.environ.copy()
    env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")
    compile_command = [
        str(gcc),
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        "-I",
        str(ROOT / "software" / "common"),
        str(ROOT / "software" / "common" / "rf_app_protocol.c"),
        str(ROOT / "tests" / "p7" / "rf_app_protocol_vectors.c"),
        "-o",
        str(executable),
    ]
    run_checked(compile_command, env=env, log_path=build_dir / "compile.log")
    compiler_version = run_checked(
        [str(gcc), "--version"], env=env, log_path=build_dir / "compiler_version.log"
    ).stdout.splitlines()[0]
    harness_process = run_checked(
        [str(executable), str(vector_path)], env=env, log_path=build_dir / "harness.log"
    )
    harness = parse_harness_summary(harness_process.stdout)
    if harness.get("P7_C_GOLDEN_VECTOR_HARNESS") != "PASS":
        raise VectorRunError(f"C harness failed: {harness!r}")
    if harness.get("failures") != 0 or harness.get("total_vectors") != args.vector_count:
        raise VectorRunError(f"C harness count/failure mismatch: {harness!r}")
    if harness.get("valid_vectors") != len(valid) or harness.get("invalid_vectors") != len(invalid):
        raise VectorRunError(f"C harness valid/invalid count mismatch: {harness!r}")
    check_c_contract(harness, contract)
    parsed_vectors = json.loads(vector_path.read_text(encoding="utf-8"))
    if parsed_vectors.get("metadata", {}).get("vector_count") != args.vector_count:
        raise VectorRunError("written vector JSON metadata count is inconsistent")
    return {
        "P7_PROTOCOL_VECTORS": "PASS",
        "C_PYTHON_BYTE_FOR_BYTE": "PASS",
        "INVALID_FIELD_ERROR_MATCH": "PASS",
        "YAML_PYTHON_C_CONTRACT": "PASS",
        "vector_count": args.vector_count,
        "valid_vectors": len(valid),
        "invalid_vectors": len(invalid),
        "vector_sha256": vector_sha256,
        "vector_file": str(vector_path.relative_to(ROOT)),
        "compiler": compiler_version,
        "compiler_path": str(gcc),
        "c_harness": harness,
        "network_used": False,
        "hardware_actions_executed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vector-count", type=int, default=DEFAULT_VECTOR_COUNT)
    parser.add_argument("--vectors", default="tests/vectors/p7_app_protocol_vectors.json")
    parser.add_argument("--build-dir", default="build/p7_protocol_vectors")
    parser.add_argument("--gcc", help="explicit native GCC executable")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    try:
        result = execute(args)
    except (OSError, ValueError, VectorRunError) as error:
        failure = {
            "P7_PROTOCOL_VECTORS": "FAIL",
            "reason": str(error),
            "network_used": False,
            "hardware_actions_executed": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }
        print(json.dumps(failure, sort_keys=True) if args.json_summary else failure, file=sys.stderr)
        return 1
    if args.json_summary:
        print(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            if key != "c_harness":
                print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
