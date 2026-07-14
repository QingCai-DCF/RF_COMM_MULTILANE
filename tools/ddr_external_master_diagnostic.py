#!/usr/bin/env python3
"""Offline contracts for DDR external-master diagnosis.

This module does not connect to hardware.  It builds byte-exact diagnostic
patterns, validates the approved slot-0 DDR output scratch range, renders
reviewable XSDB transaction plans, and compares raw binary readbacks without
normalizing or decoding payload bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DDR_SCRATCH_START = 0x00900000
DDR_SCRATCH_END = 0x01100000
DEFAULT_TRANSFER_BYTES = 256
ADDRESS_MATRIX = (0x00900000, 0x00900100, 0x00900200, 0x00900300)
PATTERN_NAMES = (
    "stage62_fixture",
    "a5_5a_3c_c3",
    "nonzero_counter",
    "prbs15",
)
ACCESS_METHODS = ("download", "block", "byte", "halfword", "word")
HEX32_RE = re.compile(r"^0x[0-9a-fA-F]{8}$")
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,126}$")
R37_RUN_ID = "p7_20260714_stage62_microtest_r37_diag_only"
R37_FIXTURE_SHA256 = (
    "b7ef71102905bfadd7b60c7ff310f2a9adf2a31f327c18c2c9c1411119ea7776"
)
R37_READBACK_SHA256 = (
    "3198a52a7e09dde9d05a82db251f6497845399c4d749c8441fa39866ca92f3bb"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, *, relative_to: Path | None = None) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    record_path = (
        resolved.relative_to(relative_to.resolve(strict=True)).as_posix()
        if relative_to is not None
        else str(resolved)
    )
    return {
        "path": record_path,
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def parse_hex32(value: str) -> int:
    """Accept only an explicit, fixed-width hexadecimal address."""

    if not HEX32_RE.fullmatch(value):
        raise ValueError("address must be exactly 0x plus eight hexadecimal digits")
    return int(value, 16)


def hex32(value: int) -> str:
    if isinstance(value, bool) or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("value is outside uint32")
    return f"0x{value:08x}"


def validate_scratch_range(address: int, length: int) -> None:
    if isinstance(address, bool) or isinstance(length, bool):
        raise ValueError("DDR scratch address and length must be integers")
    if length <= 0:
        raise ValueError("DDR scratch transfer length must be positive")
    end = address + length
    if end < address:
        raise ValueError("DDR scratch range wrapped")
    if address < DDR_SCRATCH_START or end > DDR_SCRATCH_END:
        raise ValueError("DDR scratch range is outside the fixed slot-0 output window")


def _prbs15(length: int, seed: int = 0x4A6D) -> bytes:
    state = seed & 0x7FFF or 1
    output = bytearray(length)
    for index in range(length):
        value = 0
        for bit in range(8):
            value |= (state & 1) << bit
            feedback = ((state >> 14) ^ (state >> 13)) & 1
            state = ((state << 1) & 0x7FFF) | feedback
        output[index] = value or 0xA7
    return bytes(output)


def build_pattern(
    name: str,
    *,
    length: int = DEFAULT_TRANSFER_BYTES,
    stage62_fixture: bytes | None = None,
) -> bytes:
    if name not in PATTERN_NAMES:
        raise ValueError(f"unsupported DDR diagnostic pattern: {name}")
    if length <= 0:
        raise ValueError("pattern length must be positive")
    if name == "stage62_fixture":
        if stage62_fixture is None:
            raise ValueError("stage62_fixture pattern requires immutable fixture bytes")
        if len(stage62_fixture) != length:
            raise ValueError("Stage62 fixture length does not match requested length")
        return bytes(stage62_fixture)
    if name == "a5_5a_3c_c3":
        unit = bytes((0xA5, 0x5A, 0x3C, 0xC3))
        return (unit * ((length + len(unit) - 1) // len(unit)))[:length]
    if name == "nonzero_counter":
        return bytes((index % 255) + 1 for index in range(length))
    return _prbs15(length)


def _tcl_path(path: Path) -> str:
    normalized = str(path.resolve(strict=False)).replace("\\", "/")
    if any(character in normalized for character in "{}\r\n"):
        raise ValueError("XSDB plan path contains unsupported Tcl metacharacters")
    return "{" + normalized + "}"


def _little_endian_value(payload: bytes) -> int:
    return int.from_bytes(payload, "little", signed=False)


def _scalar_write_commands(
    payload: bytes, address: int, *, width: int, size_name: str
) -> list[str]:
    if len(payload) % width:
        raise ValueError(f"payload length is not divisible by {width}-byte accesses")
    commands: list[str] = []
    for offset in range(0, len(payload), width):
        value = _little_endian_value(payload[offset : offset + width])
        commands.append(
            f"mwr -size {size_name} {hex32(address + offset)} "
            f"0x{value:0{2 * width}x} 1"
        )
    return commands


def render_xsdb_transaction_plan(
    *,
    write_path: Path,
    readback_path: Path,
    payload: bytes,
    address: int,
    access_method: str,
) -> list[str]:
    """Render one write, completion-read, and raw binary readback plan.

    Scalar access plans deliberately issue one command per value.  This keeps
    byte, halfword, and word access widths distinguishable instead of allowing
    XSDB to coalesce a list of byte values into wider target accesses.
    """

    if access_method not in ACCESS_METHODS:
        raise ValueError(f"unsupported DDR access method: {access_method}")
    validate_scratch_range(address, len(payload))
    if access_method in {"halfword", "word"}:
        width = 2 if access_method == "halfword" else 4
        if address % width:
            raise ValueError(f"{access_method} access address is not aligned")
    write_literal = _tcl_path(write_path)
    readback_literal = _tcl_path(readback_path)
    if access_method == "download":
        commands = [f"dow -data {write_literal} {hex32(address)}"]
    elif access_method == "block":
        commands = [
            f"mwr -size b -bin -file {write_literal} {hex32(address)} {len(payload)}"
        ]
    elif access_method == "byte":
        commands = _scalar_write_commands(payload, address, width=1, size_name="b")
    elif access_method == "halfword":
        commands = _scalar_write_commands(payload, address, width=2, size_name="h")
    else:
        commands = _scalar_write_commands(payload, address, width=4, size_name="w")

    # A same-target read-after-write is the explicit transaction-completion
    # observation.  The full binary dump remains an independent readback.
    barrier_address = address + len(payload) - 4
    barrier_address -= barrier_address % 4
    commands.extend(
        (
            f"set ddr_completion_word [mrd -value -size w {hex32(barrier_address)} 1]",
            "if {[llength $ddr_completion_word] != 1} { error \"DDR completion read failed\" }",
            f"mrd -size b -bin -file {readback_literal} {hex32(address)} {len(payload)}",
        )
    )
    return commands


def compare_payloads(expected: bytes, observed: bytes, *, address: int) -> dict[str, Any]:
    validate_scratch_range(address, len(expected))
    mismatches: list[dict[str, int | str]] = []
    shared = min(len(expected), len(observed))
    for offset in range(shared):
        if expected[offset] != observed[offset]:
            mismatches.append(
                {
                    "offset": offset,
                    "absolute_address": hex32(address + offset),
                    "expected": expected[offset],
                    "observed": observed[offset],
                }
            )
    if len(expected) != len(observed):
        for offset in range(shared, max(len(expected), len(observed))):
            mismatches.append(
                {
                    "offset": offset,
                    "absolute_address": hex32(address + offset),
                    "expected": expected[offset] if offset < len(expected) else -1,
                    "observed": observed[offset] if offset < len(observed) else -1,
                }
            )
    return {
        "expected_size_bytes": len(expected),
        "observed_size_bytes": len(observed),
        "expected_sha256": sha256_bytes(expected),
        "observed_sha256": sha256_bytes(observed),
        "mismatch_count": len(mismatches),
        "first_mismatch": mismatches[0] if mismatches else None,
        "passed": not mismatches,
    }


@dataclass(frozen=True)
class DiagnosticCase:
    run_id: str
    pattern: str
    address: int
    access_method: str
    repetition: int

    def validate(self) -> None:
        if not RUN_ID_RE.fullmatch(self.run_id):
            raise ValueError("DDR diagnostic run ID is missing or malformed")
        if self.pattern not in PATTERN_NAMES:
            raise ValueError("DDR diagnostic pattern is invalid")
        if self.access_method not in ACCESS_METHODS:
            raise ValueError("DDR diagnostic access method is invalid")
        if self.repetition not in range(1, 4):
            raise ValueError("DDR diagnostic repetition must be 1, 2, or 3")
        if self.address % 64:
            raise ValueError("DDR diagnostic base must be 64-byte aligned")
        validate_scratch_range(self.address, DEFAULT_TRANSFER_BYTES)

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "run_id": self.run_id,
            "pattern": self.pattern,
            "address": hex32(self.address),
            "access_method": self.access_method,
            "repetition": self.repetition,
            "length": DEFAULT_TRANSFER_BYTES,
            "diagnostic_only": True,
            "coverage_claimed": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }


def build_minimum_matrix(run_prefix: str) -> list[DiagnosticCase]:
    """Build distinct run IDs for the mandatory pattern repetitions.

    The original Stage62 fixture is tested with the historical download path;
    distinguishable patterns use the explicit-count block path.  Address and
    scalar-width expansion are separate adaptive stages after this minimum
    reproduction matrix.
    """

    if not RUN_ID_RE.fullmatch(run_prefix):
        raise ValueError("DDR diagnostic run prefix is malformed")
    cases: list[DiagnosticCase] = []
    for pattern in PATTERN_NAMES[:3]:
        method = "download" if pattern == "stage62_fixture" else "block"
        for repetition in range(1, 4):
            cases.append(
                DiagnosticCase(
                    run_id=f"{run_prefix}_{pattern}_rep{repetition}",
                    pattern=pattern,
                    address=DDR_SCRATCH_START,
                    access_method=method,
                    repetition=repetition,
                )
            )
    for case in cases:
        case.validate()
    if len({case.run_id for case in cases}) != len(cases):
        raise AssertionError("DDR diagnostic matrix contains duplicate run IDs")
    return cases


def materialize_case(
    *,
    output_dir: Path,
    case: DiagnosticCase,
    stage62_fixture_path: Path | None = None,
) -> dict[str, Any]:
    """Create a new, immutable-by-construction offline case package.

    The directory must not already exist.  The package contains only the
    fixture and a reviewable transaction plan; it cannot connect to XSDB or
    hardware and it never creates a readback file on behalf of a run.
    """

    case.validate()
    stage62_fixture = None
    if case.pattern == "stage62_fixture":
        if stage62_fixture_path is None or not stage62_fixture_path.is_file():
            raise ValueError("stage62 fixture path is required and must exist")
        stage62_fixture = stage62_fixture_path.read_bytes()
    elif stage62_fixture_path is not None:
        raise ValueError("stage62 fixture path is only accepted for stage62_fixture")
    payload = build_pattern(
        case.pattern,
        length=DEFAULT_TRANSFER_BYTES,
        stage62_fixture=stage62_fixture,
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    fixture_path = output_dir / "ddr_external_master_fixture.bin"
    plan_path = output_dir / "xsdb_transaction_plan.txt"
    manifest_path = output_dir / "offline_case_manifest.json"
    readback_path = output_dir / "ddr_external_master_readback.bin"
    fixture_path.write_bytes(payload)
    commands = render_xsdb_transaction_plan(
        write_path=fixture_path,
        readback_path=readback_path,
        payload=payload,
        address=case.address,
        access_method=case.access_method,
    )
    plan_path.write_text("\n".join(commands) + "\n", encoding="utf-8", newline="\n")
    manifest: dict[str, Any] = {
        "schema": "rf-comm-ddr-external-master-offline-case-v1",
        **case.as_dict(),
        "fixture": file_record(fixture_path, relative_to=output_dir),
        "transaction_plan": file_record(plan_path, relative_to=output_dir),
        "planned_readback_path": readback_path.name,
        "hardware_actions_executed": False,
        "safe_wrapper_required_for_execution": True,
    }
    if stage62_fixture_path is not None:
        manifest["stage62_fixture_source"] = file_record(stage62_fixture_path)
    manifest_path.write_text(
        _json_dump(manifest) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def _parse_fixed_plan(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    if not lines or lines[0] != "P7_PS_EXECUTION_PLAN_V1" or lines[-1] != "END":
        raise ValueError("R37 execution plan framing is invalid")
    values: dict[str, str] = {}
    for line in lines[1:-1]:
        fields = line.split(maxsplit=1)
        if len(fields) != 2 or fields[0] in values:
            raise ValueError(f"R37 execution plan field is malformed: {line}")
        values[fields[0]] = fields[1]
    return values


def audit_r37_prestart_evidence(
    *, evidence_dir: Path, command_file: Path, tcl_file: Path
) -> dict[str, Any]:
    """Re-audit the immutable R37 host write and raw prestart readback path."""

    project_root = tcl_file.resolve(strict=True).parents[2]
    bundle = evidence_dir / "bundle"
    fixture_path = bundle / "stage62_microtest_destination_fixture.bin"
    readback_path = bundle / "stage62_microtest_destination_prestart.bin"
    plan_path = bundle / "execution_plan.txt"
    raw_path = evidence_dir / "p7_ps_application_raw_result.log"
    summary_path = evidence_dir / "p7_ps_application_stage_summary.json"
    diff_path = evidence_dir / "ddr_prestart_diff.json"
    required = (
        fixture_path,
        readback_path,
        plan_path,
        raw_path,
        summary_path,
        diff_path,
        command_file,
        tcl_file,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"R37 audit inputs missing: {missing}")

    failures: list[str] = []
    fixture = fixture_path.read_bytes()
    readback = readback_path.read_bytes()
    comparison = compare_payloads(fixture, readback, address=DDR_SCRATCH_START)
    if len(fixture) != DEFAULT_TRANSFER_BYTES or fixture[9] != 0xC3:
        failures.append("R37 fixture is not the exact 256-byte offset-9=0xC3 input")
    if sha256_bytes(fixture) != R37_FIXTURE_SHA256:
        failures.append("R37 fixture SHA256 changed")
    if len(readback) != DEFAULT_TRANSFER_BYTES or readback[9] != 0x00:
        failures.append("R37 readback is not the exact 256-byte offset-9=0x00 result")
    if sha256_bytes(readback) != R37_READBACK_SHA256:
        failures.append("R37 readback SHA256 changed")
    expected_first = {
        "offset": 9,
        "absolute_address": "0x00900009",
        "expected": 0xC3,
        "observed": 0x00,
    }
    if comparison["mismatch_count"] != 1 or comparison["first_mismatch"] != expected_first:
        failures.append("R37 raw comparison does not preserve the one exact mismatch")

    plan = _parse_fixed_plan(plan_path)
    required_plan = {
        "MODE": "stage62-microtest",
        "EXECUTION_SCOPE": "STAGE62_ONLY",
        "RUN_ID": R37_RUN_ID,
        "DIAGNOSTIC_ONLY": "1",
        "COVERAGE_CLAIMED": "0",
        "MICROTEST_CASE": "B",
        "MICROTEST_LENGTH": "30",
        "MICROTEST_SOURCE_ALIGNMENT": "0",
        "MICROTEST_DESTINATION_ALIGNMENT": "0",
        "CASE_COUNT": "0",
        "BOUNDARY_COUNT": "0",
    }
    for key, expected in required_plan.items():
        if plan.get(key) != expected:
            failures.append(
                f"R37 execution plan mismatch: {key} expected={expected} observed={plan.get(key)}"
            )

    command_text = command_file.read_text(encoding="utf-8", errors="strict")
    for token in (
        "--execute-hardware",
        "--mode stage62-microtest",
        "--stage62-only",
        f"--run-id {R37_RUN_ID}",
        "--stage62-microtest-case B",
        "--microtest-length 30",
    ):
        if token not in command_text:
            failures.append(f"R37 recorded host command is missing: {token}")

    summary = json.loads(summary_path.read_text(encoding="utf-8", errors="strict"))
    attested_sources = (
        summary.get("core_hardware_readiness", {})
        .get("attestation", {})
        .get("sources", {})
    )
    source_match = re.search(r"(?:^|\s)--source-commit\s+([0-9a-fA-F]{40})(?:\s|$)", command_text)
    historical_tcl_bytes = b""
    historical_tcl_commit = source_match.group(1).lower() if source_match else "MISSING"
    if source_match is None:
        failures.append("R37 recorded host command does not bind a full source commit")
    else:
        completed = subprocess.run(
            [
                "git",
                "show",
                f"{historical_tcl_commit}:scripts/hw/p7_ps_application_execute.tcl",
            ],
            cwd=project_root,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if completed.returncode != 0:
            failures.append("R37 source commit Tcl bytes are unavailable from Git")
        else:
            historical_tcl_bytes = completed.stdout
            historical_tcl_sha = sha256_bytes(historical_tcl_bytes)
            if (
                attested_sources.get("scripts/hw/p7_ps_application_execute.tcl")
                != historical_tcl_sha
            ):
                failures.append(
                    "R37 readiness attestation does not bind its source-commit Tcl bytes"
                )

    try:
        tcl_text = historical_tcl_bytes.decode("utf-8", errors="strict")
    except UnicodeError:
        tcl_text = ""
        failures.append("R37 source-commit Tcl is not strict UTF-8")
    case_b = re.search(
        r"B\s*\{.*?set\s+micro_destination_address\s+0x00900000.*?\}",
        tcl_text,
        re.DOTALL,
    )
    if case_b is None:
        failures.append("audited Tcl does not map Case B destination to 0x00900000")
    ordered_snippets = (
        "dow -data [file join $bundle_dir stage62_microtest_destination_fixture.bin]",
        "p7_atomic_dump $micro_destination_prestart $micro_destination_address 256",
        "[file join $bundle_dir stage62_microtest_destination_fixture.bin] \\",
        'p7_say $result_handle "P7_STAGE62_MICROTEST_PRESTART_READBACK=PASS"',
        "\n    con\n",
    )
    cursor = 0
    for snippet in ordered_snippets:
        position = tcl_text.find(snippet, cursor)
        if position < 0:
            failures.append(f"audited Tcl host-write/readback ordering missing: {snippet}")
            break
        cursor = position + len(snippet)

    raw_text = raw_path.read_text(encoding="utf-8", errors="strict")
    required_raw = (
        "P7_PS_CANDIDATE_PROGRAMMED=1",
        "P7_PS_ELF_DOWNLOADED=1",
        "P7_PS_STAGE_RESULT=FAIL",
        "P7_PS_STAGE_ERROR=P7 Stage62 microtest destination prestart binary readback differs",
    )
    for marker in required_raw:
        if marker not in raw_text:
            failures.append(f"R37 raw result marker is missing: {marker}")
    if "P7_STAGE62_MICROTEST_PRESTART_READBACK=PASS" in raw_text:
        failures.append("R37 raw result incorrectly reports prestart readback PASS")
    if "P7_STAGE62_MICROTEST=1" in raw_text:
        failures.append("R37 raw result incorrectly reports firmware microtest execution")

    if summary.get("hardware_actions_executed") is not True:
        failures.append("R37 summary does not record the historical hardware action")
    if summary.get("functional_stages_1_61_executed") is not False:
        failures.append("R37 summary does not exclude stages 1-61")
    if summary.get("stage62_executed") is not False:
        failures.append("R37 summary does not exclude Stage62 execution")
    if summary.get("drove_tfdu_txd") is not False:
        failures.append("R37 summary does not exclude TFDU Txd drive")
    if summary.get("shutdown_after", {}).get("passed") is not True:
        failures.append("R37 shutdown-after is not PASS")

    recorded_diff = json.loads(diff_path.read_text(encoding="utf-8", errors="strict"))
    if recorded_diff.get("expected", {}).get("sha256") != R37_FIXTURE_SHA256:
        failures.append("R37 diff does not bind the exact fixture SHA256")
    if recorded_diff.get("actual", {}).get("sha256") != R37_READBACK_SHA256:
        failures.append("R37 diff does not bind the exact readback SHA256")
    if recorded_diff.get("first_mismatch", {}) != {
        "absolute_address": "0x00900009",
        "actual": 0,
        "expected": 195,
        "offset": 9,
    }:
        failures.append("R37 recorded diff first mismatch changed")

    return {
        "schema": "rf-comm-ddr-r37-host-prestart-audit-v1",
        "passed": not failures,
        "failures": failures,
        "offline_audit_only": True,
        "hardware_actions_executed_now": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "run_id": R37_RUN_ID,
        "destination_address": hex32(DDR_SCRATCH_START),
        "intended_firmware_target": "0x00900040",
        "fixture": file_record(fixture_path, relative_to=evidence_dir),
        "recorded_host_command": file_record(command_file, relative_to=project_root),
        "audited_tcl": {
            "path": (
                f"git:{historical_tcl_commit}:"
                "scripts/hw/p7_ps_application_execute.tcl"
            ),
            "size_bytes": len(historical_tcl_bytes),
            "sha256": sha256_bytes(historical_tcl_bytes),
            "git_commit": historical_tcl_commit,
        },
        "current_tcl": file_record(tcl_file, relative_to=project_root),
        "execution_plan": file_record(plan_path, relative_to=evidence_dir),
        "raw_readback": file_record(readback_path, relative_to=evidence_dir),
        "raw_result": file_record(raw_path, relative_to=evidence_dir),
        "comparison": comparison,
        "host_path_findings": {
            "fixture_is_raw_binary": True,
            "fixture_offset_9_is_0xc3": len(fixture) > 9 and fixture[9] == 0xC3,
            "address_is_fixed_tcl_hex_literal": case_b is not None,
            "tcl_writes_the_manifest_bound_fixture_filename": True,
            "readback_is_raw_binary": True,
            "readback_precedes_cpu_release": True,
            "text_conversion_observed": False,
            "parser_normalization_observed": False,
        },
    }


def analyze_files(expected_path: Path, observed_path: Path, *, address: int) -> dict[str, Any]:
    expected = expected_path.read_bytes()
    observed = observed_path.read_bytes()
    result = compare_payloads(expected, observed, address=address)
    result.update(
        {
            "expected_path": str(expected_path.resolve(strict=False)),
            "observed_path": str(observed_path.resolve(strict=False)),
        }
    )
    return result


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="compare immutable fixture and raw readback")
    analyze.add_argument("--expected", required=True)
    analyze.add_argument("--observed", required=True)
    analyze.add_argument("--address", required=True)

    matrix = subparsers.add_parser("matrix", help="emit the minimum new-run pattern matrix")
    matrix.add_argument("--run-prefix", required=True)

    plan = subparsers.add_parser("plan", help="render an offline XSDB transaction plan")
    plan.add_argument("--write-file", required=True)
    plan.add_argument("--readback-file", required=True)
    plan.add_argument("--address", required=True)
    plan.add_argument("--access-method", choices=ACCESS_METHODS, required=True)

    materialize = subparsers.add_parser(
        "materialize", help="create a new offline fixture/transaction package"
    )
    materialize.add_argument("--output-dir", required=True)
    materialize.add_argument("--run-id", required=True)
    materialize.add_argument("--pattern", choices=PATTERN_NAMES, required=True)
    materialize.add_argument("--address", required=True)
    materialize.add_argument("--access-method", choices=ACCESS_METHODS, required=True)
    materialize.add_argument("--repetition", type=int, required=True)
    materialize.add_argument("--stage62-fixture")

    audit = subparsers.add_parser(
        "audit-r37", help="re-audit the immutable R37 prestart host path"
    )
    audit.add_argument("--evidence-dir", required=True)
    audit.add_argument("--command-file", required=True)
    audit.add_argument("--tcl-file", required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "analyze":
        print(
            _json_dump(
                analyze_files(
                    Path(args.expected),
                    Path(args.observed),
                    address=parse_hex32(args.address),
                )
            )
        )
        return 0
    if args.command == "matrix":
        print(_json_dump([case.as_dict() for case in build_minimum_matrix(args.run_prefix)]))
        return 0
    if args.command == "materialize":
        case = DiagnosticCase(
            run_id=args.run_id,
            pattern=args.pattern,
            address=parse_hex32(args.address),
            access_method=args.access_method,
            repetition=args.repetition,
        )
        print(
            _json_dump(
                materialize_case(
                    output_dir=Path(args.output_dir),
                    case=case,
                    stage62_fixture_path=(
                        Path(args.stage62_fixture) if args.stage62_fixture else None
                    ),
                )
            )
        )
        return 0
    if args.command == "audit-r37":
        result = audit_r37_prestart_evidence(
            evidence_dir=Path(args.evidence_dir),
            command_file=Path(args.command_file),
            tcl_file=Path(args.tcl_file),
        )
        print(_json_dump(result))
        return 0 if result["passed"] else 1

    write_path = Path(args.write_file)
    payload = write_path.read_bytes()
    commands = render_xsdb_transaction_plan(
        write_path=write_path,
        readback_path=Path(args.readback_file),
        payload=payload,
        address=parse_hex32(args.address),
        access_method=args.access_method,
    )
    print("\n".join(commands))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
