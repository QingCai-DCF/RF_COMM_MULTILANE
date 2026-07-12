#!/usr/bin/env python3
"""Fail-closed validation for P7 adaptive diagnostic suffix impact proofs.

The proof is deliberately a data artifact.  The plan generator creates it
from a prior immutable failed run and the executor independently re-hashes
every referenced historical/current input before accepting a shortened
diagnostic schedule.  It never grants hardware authorization or contributes
acceptance coverage.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "rf-comm-p7-diagnostic-impact-proof-v1"
MANDATORY_PREFIX = [1, 2, 3, 4]
MAX_DIAGNOSTIC_ORDINAL = 65
SOURCE_DEPENDENCIES = (
    "scripts/hw/run_p7_jtag_axi_stage_safe.py",
    "scripts/hw/p7_hw_preflight.tcl",
    "scripts/hw/p7_jtag_axi_transactions.tcl",
    "tools/p7_hardware_safety.py",
    "tools/p7_jtag_backend.py",
    "tools/p7_app_protocol.py",
    "tools/p7_app_transport.py",
    "tools/p7_contained_launcher.py",
    "config/register_map/generated/ir_regs.py",
)
SEQUENCE_IMPORTED_SYMBOLS = (
    "CANONICAL_FULL_PART",
    "CANONICAL_LIVE_DEVICE",
    "CANONICAL_LIVE_IDCODE_BINARY",
    "CANONICAL_LIVE_IDCODE_HEX",
    "CANONICAL_LIVE_PART",
    "build_preflight_command",
    "canonical_live_identity_failures",
    "evaluate_preflight",
    "is_exact_vivado_batch_launcher",
    "normalize_p7_idcode",
    "parse_markers",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_source_sha256(payload: bytes) -> str:
    """Hash text source independent of Git checkout newline materialization."""

    return sha256_bytes(payload.replace(b"\r\n", b"\n"))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def git_blob(root: Path, commit: str, relative_path: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError(
            f"unable to read historical Git blob {commit}:{relative_path}: "
            + process.stderr.decode("utf-8", errors="replace").strip()
        )
    return process.stdout


def symbol_sha256(source: bytes, symbol: str) -> str:
    text = source.decode("utf-8")
    tree = ast.parse(text)
    matches: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                matches.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == symbol for target in targets):
                matches.append(node)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one top-level definition for {symbol}, observed {len(matches)}")
    # AST dumps ignore comments and unrelated edits while binding the complete
    # executable/value definition imported by the JTAG wrapper.
    return sha256_bytes(ast.dump(matches[0], annotate_fields=True, include_attributes=False).encode("utf-8"))


def canonical_backend_manifest_sha256(path: Path) -> str:
    value = load_json(path)
    # The absolute generated input path is run-ID-specific provenance.  Its
    # content hash remains bound separately and every other manifest field is
    # compared byte-for-byte after canonical JSON serialization.
    if "input_file" not in value or "input_file_sha256" not in value or "transaction_file" not in value:
        raise ValueError(f"backend manifest lacks input provenance: {path}")
    value["input_file"] = "<RUN_LOCAL_STAGE_INPUT>"
    value["transaction_file"] = "<RUN_LOCAL_STAGE_TRANSACTIONS>"
    return sha256_bytes(
        (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    )


def expected_selected_ordinals(first_unresolved_ordinal: int) -> list[int]:
    if first_unresolved_ordinal < 5 or first_unresolved_ordinal > MAX_DIAGNOSTIC_ORDINAL:
        raise ValueError("first unresolved diagnostic ordinal must be in 5..65")
    return MANDATORY_PREFIX + list(range(first_unresolved_ordinal, MAX_DIAGNOSTIC_ORDINAL + 1))


def _record_error(record: Any, label: str) -> list[str]:
    if not isinstance(record, dict):
        return [f"{label} record is missing or malformed"]
    path_value = record.get("path")
    expected = str(record.get("sha256", "")).lower()
    if not isinstance(path_value, str) or not path_value or len(expected) != 64:
        return [f"{label} file record is incomplete"]
    path = Path(path_value).resolve(strict=False)
    if not path.is_file():
        return [f"{label} file is missing: {path}"]
    actual = sha256_file(path)
    return [] if actual == expected else [f"{label} SHA256 mismatch: expected={expected} actual={actual}"]


def validate_impact_proof(
    proof_path: Path,
    expected_sha256: str,
    *,
    root: Path,
    current_source_commit: str,
    selected_ordinals: list[int],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Revalidate one proof without trusting its recorded PASS booleans."""

    errors: list[str] = []
    proof_path = proof_path.resolve(strict=False)
    if not proof_path.is_file() or proof_path.is_symlink():
        return None, [f"diagnostic impact proof is missing or not a regular file: {proof_path}"]
    actual_proof_sha = sha256_file(proof_path)
    if actual_proof_sha != expected_sha256.lower():
        errors.append("diagnostic impact proof SHA256 mismatch")
    try:
        proof = load_json(proof_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, errors + [f"diagnostic impact proof JSON is invalid: {exc}"]
    if proof.get("schema") != SCHEMA or proof.get("status") != "PASS":
        errors.append("diagnostic impact proof schema/status is not PASS")
    if proof.get("coverage_claimed") is not False or proof.get("HARDWARE_ACCEPTANCE") != "PENDING_HW":
        errors.append("diagnostic impact proof improperly claims acceptance coverage")
    first = proof.get("first_unresolved_ordinal")
    try:
        expected_selected = expected_selected_ordinals(int(first))
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
        expected_selected = []
    if proof.get("mandatory_prefix_ordinals") != MANDATORY_PREFIX:
        errors.append("diagnostic impact proof mandatory prefix mismatch")
    if proof.get("selected_ordinals") != expected_selected or selected_ordinals != expected_selected:
        errors.append("diagnostic impact proof selected ordinal matrix mismatch")
    skipped = list(range(55, int(first))) if isinstance(first, int) and first >= 55 else []
    if not skipped or proof.get("skipped_ordinals") != skipped:
        errors.append("diagnostic impact proof skipped ordinal set is not the exact prior PASS suffix")
    if str(proof.get("current_source_commit", "")).lower() != current_source_commit.lower():
        errors.append("diagnostic impact proof current source commit mismatch")
    if proof.get("proof_errors") != []:
        errors.append("diagnostic impact proof contains generation errors")

    for key in ("prior_sequence_plan", "prior_execution_ledger"):
        errors.extend(_record_error(proof.get(key), key))

    try:
        prior_plan = load_json(Path(str(proof.get("prior_sequence_plan", {}).get("path", ""))))
        prior_ledger = load_json(Path(str(proof.get("prior_execution_ledger", {}).get("path", ""))))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"prior plan/ledger cannot be parsed: {exc}")
        prior_plan, prior_ledger = {}, {}
    if (
        prior_plan.get("plan_mode") != "DIAGNOSTIC_SUFFIX_55"
        or prior_plan.get("full_stage_ordinals") != MANDATORY_PREFIX + list(range(55, 66))
        or str(prior_plan.get("source_commit", "")).lower() != str(proof.get("prior_source_commit", "")).lower()
    ):
        errors.append("prior sequence plan is not the exact immutable suffix55 diagnostic matrix")
    if (
        prior_ledger.get("plan_mode") != "DIAGNOSTIC_SUFFIX_55"
        or prior_ledger.get("status") != "FAIL"
        or prior_ledger.get("failed_stage_index") != 11
        or prior_ledger.get("coverage_claimed") is not False
        or prior_ledger.get("HARDWARE_ACCEPTANCE") != "PENDING_HW"
    ):
        errors.append("prior execution ledger is not the exact zero-coverage stage-62 failure")

    prior_commit = str(proof.get("prior_source_commit", "")).lower()
    dependency_records = proof.get("source_dependencies")
    if not isinstance(dependency_records, list):
        errors.append("diagnostic impact proof source dependency list is missing")
        dependency_records = []
    by_path = {item.get("path"): item for item in dependency_records if isinstance(item, dict)}
    if set(by_path) != set(SOURCE_DEPENDENCIES):
        errors.append("diagnostic impact proof source dependency closure is incomplete")
    for relative in SOURCE_DEPENDENCIES:
        record = by_path.get(relative, {})
        current = (root / relative).resolve(strict=False)
        try:
            old_hash = normalized_source_sha256(git_blob(root, prior_commit, relative))
            current_hash = normalized_source_sha256(current.read_bytes())
        except (OSError, ValueError) as exc:
            errors.append(f"source dependency {relative} cannot be revalidated: {exc}")
            continue
        if old_hash != current_hash:
            errors.append(f"source dependency changed for skipped JTAG stages: {relative}")
        if record.get("prior_sha256") != old_hash or record.get("current_sha256") != current_hash:
            errors.append(f"source dependency proof record mismatch: {relative}")

    symbol_records = proof.get("sequence_import_symbols")
    if not isinstance(symbol_records, list):
        errors.append("sequence import symbol proof is missing")
        symbol_records = []
    by_symbol = {item.get("symbol"): item for item in symbol_records if isinstance(item, dict)}
    if set(by_symbol) != set(SEQUENCE_IMPORTED_SYMBOLS):
        errors.append("sequence import symbol dependency closure is incomplete")
    try:
        old_sequence = git_blob(root, prior_commit, "tools/run_p7_authorized_hardware_sequence.py")
        current_sequence = (root / "tools" / "run_p7_authorized_hardware_sequence.py").read_bytes()
        for symbol in SEQUENCE_IMPORTED_SYMBOLS:
            old_hash = symbol_sha256(old_sequence, symbol)
            current_hash = symbol_sha256(current_sequence, symbol)
            record = by_symbol.get(symbol, {})
            if old_hash != current_hash:
                errors.append(f"JTAG-wrapper imported sequence symbol changed: {symbol}")
            if record.get("prior_sha256") != old_hash or record.get("current_sha256") != current_hash:
                errors.append(f"sequence import symbol proof record mismatch: {symbol}")
    except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
        errors.append(f"sequence import symbol proof cannot be revalidated: {exc}")

    passes = proof.get("historical_exact_passes")
    if not isinstance(passes, list):
        errors.append("historical exact PASS records are missing")
        passes = []
    pass_by_ordinal = {item.get("ordinal"): item for item in passes if isinstance(item, dict)}
    if set(pass_by_ordinal) != set(skipped):
        errors.append("historical exact PASS record set does not equal skipped ordinals")
    for ordinal in skipped:
        record = pass_by_ordinal.get(ordinal, {})
        errors.extend(_record_error(record.get("summary"), f"historical stage {ordinal} summary"))
        if record.get("result") != "EXACT_HARDWARE_PASS" or record.get("coverage_contributed") is not False:
            errors.append(f"historical stage {ordinal} is not an exact zero-coverage diagnostic PASS")
        try:
            summary = load_json(Path(str(record.get("summary", {}).get("path", ""))))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"historical stage {ordinal} summary cannot be parsed: {exc}")
            summary = {}
        if (
            summary.get("P7_JTAG_AXI_SAFE_STAGE") != "PASS"
            or summary.get("hardware_actions_executed") is not True
            or summary.get("hardware_acceptance") != "PENDING_HW"
            or summary.get("ethernet_used") is not False
            or summary.get("motion_used") is not False
            or summary.get("shutdown_before", {}).get("passed") is not True
            or summary.get("shutdown_after", {}).get("passed") is not True
            or summary.get("stage_failures") != []
        ):
            errors.append(f"historical stage {ordinal} summary no longer proves an exact safe PASS")
        comparisons = record.get("consumed_inputs", []) if isinstance(record.get("consumed_inputs"), list) else []
        expected_roles = {
            "plan", "bitstream", "xsa", "elf", "profile", "active_xdc", "pinmap",
            "register_map", "shutdown_bitstream", "ltx",
        }
        if {item.get("role") for item in comparisons if isinstance(item, dict)} != expected_roles:
            errors.append(f"historical stage {ordinal} consumed-input closure is incomplete")
        for comparison in comparisons:
            if not isinstance(comparison, dict):
                errors.append(f"historical stage {ordinal} has malformed consumed-input proof")
                continue
            current_path = Path(str(comparison.get("current_path", ""))).resolve(strict=False)
            current_hash = str(comparison.get("current_sha256", "")).lower()
            if not current_path.is_file() or sha256_file(current_path) != current_hash:
                errors.append(f"historical stage {ordinal} current consumed input hash mismatch: {comparison.get('role')}")
            if comparison.get("prior_sha256") != current_hash or comparison.get("unchanged") is not True:
                errors.append(f"historical stage {ordinal} consumed input changed: {comparison.get('role')}")
        settings = record.get("authorization_settings")
        if not isinstance(settings, list) or not settings:
            errors.append(f"historical stage {ordinal} authorization/runtime setting proof is missing")
        else:
            for setting in settings:
                if (
                    not isinstance(setting, dict)
                    or setting.get("unchanged") is not True
                    or setting.get("prior") != setting.get("current")
                ):
                    errors.append(f"historical stage {ordinal} authorization/runtime setting changed")
        shadow = record.get("shadow_generated_inputs")
        if not isinstance(shadow, dict):
            errors.append(f"historical stage {ordinal} lacks shadow-generated input proof")
            continue
        for role in ("input", "transaction"):
            item = shadow.get(role)
            errors.extend(_record_error(item, f"historical stage {ordinal} shadow {role}"))
            if isinstance(item, dict) and item.get("prior_sha256") != item.get("sha256"):
                errors.append(f"historical stage {ordinal} shadow {role} differs from prior run")
        manifest = shadow.get("backend_manifest")
        errors.extend(_record_error(manifest, f"historical stage {ordinal} shadow backend manifest"))
        if isinstance(manifest, dict):
            try:
                canonical = canonical_backend_manifest_sha256(Path(str(manifest.get("path"))))
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"historical stage {ordinal} shadow backend manifest invalid: {exc}")
            else:
                if canonical != manifest.get("canonical_sha256") or canonical != manifest.get("prior_canonical_sha256"):
                    errors.append(f"historical stage {ordinal} backend manifest semantics changed")

    runtime = proof.get("runtime_identity")
    if not isinstance(runtime, dict):
        errors.append("diagnostic impact proof runtime identity is missing")
    else:
        for role in ("python", "vivado_launcher"):
            errors.extend(_record_error(runtime.get(role), f"runtime identity {role}"))
        python_record = runtime.get("python", {})
        vivado_record = runtime.get("vivado_launcher", {})
        if python_record.get("historical_path") != python_record.get("path"):
            errors.append("Python runtime path identity changed since prior run")
        if (
            vivado_record.get("historical_path") != vivado_record.get("path")
            or vivado_record.get("version_identity") != "Vivado v2023.1"
        ):
            errors.append("Vivado launcher path/version identity changed since prior run")
        helpers = runtime.get("vivado_helpers")
        if not isinstance(helpers, list) or not helpers:
            errors.append("diagnostic impact proof Vivado helper identity is missing")
        else:
            for helper in helpers:
                errors.extend(_record_error(helper, f"runtime helper {helper.get('role') if isinstance(helper, dict) else '?'}"))
                if isinstance(helper, dict) and helper.get("historical_sha256") != helper.get("sha256"):
                    errors.append(f"runtime helper identity changed: {helper.get('role')}")

    return proof, errors
