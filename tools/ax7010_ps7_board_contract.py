#!/usr/bin/env python3
"""Fail-closed AX7010 PS7/DDR generated-artifact contract.

This module is deliberately offline-only.  It parses the files emitted by
Vivado and Vitis and never opens a hardware target.  A source-level Tcl check
is included, but it is not sufficient by itself: the generated XCI, block
design, XSA/HWH, Vitis parameter file, and ps7_init copies must agree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPECTED_DEVICE = "xc7z010clg400-1"
EXPECTED_XCI_PROJECT = {
    "DEVICE": "xc7z010",
    "PACKAGE": "clg400",
    "SPEEDGRADE": "-1",
}
EXPECTED_PS7_PARAMETERS = {
    "PCW_CRYSTAL_PERIPHERAL_FREQMHZ": "33.333333",
    "PCW_APU_PERIPHERAL_FREQMHZ": "666.666666",
    "PCW_PRESET_BANK0_VOLTAGE": "LVCMOS 3.3V",
    "PCW_PRESET_BANK1_VOLTAGE": "LVCMOS 1.8V",
    "PCW_UIPARAM_DDR_PARTNO": "MT41J128M16 HA-125",
    "PCW_UIPARAM_DDR_DRAM_WIDTH": "16 Bits",
    "PCW_UIPARAM_DDR_DEVICE_CAPACITY": "2048 MBits",
    "PCW_UIPARAM_DDR_BUS_WIDTH": "32 Bit",
    "PCW_UIPARAM_DDR_FREQ_MHZ": "533.333333",
    "PCW_UIPARAM_DDR_T_FAW": "40.0",
    "PCW_UIPARAM_DDR_ECC": "Disabled",
    "PCW_UIPARAM_DDR_TRAIN_READ_GATE": "1",
    "PCW_UIPARAM_DDR_TRAIN_DATA_EYE": "1",
    # Zynq-7000 names write-data-eye training "write leveling" in the PS7 IP.
    "PCW_UIPARAM_DDR_TRAIN_WRITE_LEVEL": "1",
}
# Vivado 2023.1 deliberately omits disabled/derived PS7 properties from the
# sparse .bd JSON even when Tcl explicitly sets and reads them.  They remain
# mandatory in Tcl, XCI, XSA/HWH, and Vitis ps7_parameters.xml.  The .bd must
# serialize every user-editable value below and must bind the exact XCI that
# carries the complete resolved parameter set.
BD_DERIVED_PARAMETERS = frozenset(
    {
        "PCW_UIPARAM_DDR_DRAM_WIDTH",
        "PCW_UIPARAM_DDR_DEVICE_CAPACITY",
        "PCW_UIPARAM_DDR_T_FAW",
        "PCW_UIPARAM_DDR_ECC",
    }
)
EXPECTED_BD_PARAMETERS = {
    key: value
    for key, value in EXPECTED_PS7_PARAMETERS.items()
    if key not in BD_DERIVED_PARAMETERS
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        return {
            "absolute_path": str(resolved),
            "exists": False,
            "size": None,
            "sha256": None,
        }
    return {
        "absolute_path": str(resolved),
        "exists": True,
        "size": resolved.stat().st_size,
        "sha256": sha256(resolved),
    }


def _record_mismatch(
    errors: list[dict[str, Any]],
    artifact: str,
    field: str,
    expected: Any,
    observed: Any,
    *,
    reason: str = "VALUE_MISMATCH",
) -> None:
    errors.append(
        {
            "artifact": artifact,
            "field": field,
            "reason": reason,
            "expected": expected,
            "observed": observed,
        }
    )


def _single_value(entry: Any) -> Any:
    if not isinstance(entry, list) or len(entry) != 1:
        return None
    item = entry[0]
    if not isinstance(item, dict) or "value" not in item:
        return None
    return str(item["value"])


def _xml_parameters(root: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for element in root.iter():
        if not element.tag.endswith("PARAMETER"):
            continue
        name = element.attrib.get("NAME")
        value = element.attrib.get("VALUE")
        if name is not None and value is not None:
            values[name] = value
    return values


def _check_parameter_values(
    errors: list[dict[str, Any]],
    artifact: str,
    observed: dict[str, str],
    expected_values: dict[str, str] = EXPECTED_PS7_PARAMETERS,
) -> None:
    for field, expected in expected_values.items():
        if field not in observed:
            _record_mismatch(
                errors,
                artifact,
                field,
                expected,
                None,
                reason="MISSING_FIELD",
            )
        elif observed[field] != expected:
            _record_mismatch(errors, artifact, field, expected, observed[field])


def _load_json(
    path: Path, artifact: str, errors: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if not path.is_file():
        _record_mismatch(errors, artifact, "file", "present", None, reason="MISSING_FILE")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _record_mismatch(
            errors,
            artifact,
            "serialization",
            "parseable JSON",
            type(exc).__name__,
            reason="UNPARSEABLE",
        )
        return None
    if not isinstance(value, dict):
        _record_mismatch(
            errors,
            artifact,
            "serialization",
            "JSON object",
            type(value).__name__,
            reason="UNPARSEABLE",
        )
        return None
    return value


def _load_xml_bytes(
    data: bytes, artifact: str, errors: list[dict[str, Any]]
) -> ET.Element | None:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        _record_mismatch(
            errors,
            artifact,
            "serialization",
            "parseable XML",
            str(exc),
            reason="UNPARSEABLE",
        )
        return None


def _load_xml_file(
    path: Path, artifact: str, errors: list[dict[str, Any]]
) -> ET.Element | None:
    if not path.is_file():
        _record_mismatch(errors, artifact, "file", "present", None, reason="MISSING_FILE")
        return None
    try:
        return _load_xml_bytes(path.read_bytes(), artifact, errors)
    except OSError as exc:
        _record_mismatch(
            errors,
            artifact,
            "file",
            "readable",
            type(exc).__name__,
            reason="UNREADABLE",
        )
        return None


def validate_build_tcl(path: Path, errors: list[dict[str, Any]]) -> None:
    artifact = "build_tcl"
    if not path.is_file():
        _record_mismatch(errors, artifact, "file", "present", None, reason="MISSING_FILE")
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _record_mismatch(
            errors, artifact, "file", "readable UTF-8", type(exc).__name__, reason="UNREADABLE"
        )
        return
    part_pattern = re.escape(f"-part {EXPECTED_DEVICE}")
    if re.search(part_pattern, text) is None:
        _record_mismatch(errors, artifact, "device", EXPECTED_DEVICE, None, reason="MISSING_FIELD")
    for field, expected in EXPECTED_PS7_PARAMETERS.items():
        pattern = rf"\bCONFIG\.{re.escape(field)}\s+\{{{re.escape(expected)}\}}"
        if re.search(pattern, text) is None:
            _record_mismatch(
                errors,
                artifact,
                field,
                expected,
                None,
                reason="MISSING_FIELD",
            )
    automation = text.find("apply_bd_automation -rule xilinx.com:bd_rule:processing_system7")
    bank0 = text.find("CONFIG.PCW_PRESET_BANK0_VOLTAGE")
    bank1 = text.find("CONFIG.PCW_PRESET_BANK1_VOLTAGE")
    if automation < 0 or bank0 <= automation or bank1 <= automation:
        _record_mismatch(
            errors,
            artifact,
            "MIO_voltage_override_order",
            "after PS7 automation",
            {"automation": automation, "bank0": bank0, "bank1": bank1},
            reason="ORDER_MISMATCH",
        )


def validate_xci(path: Path, errors: list[dict[str, Any]]) -> None:
    artifact = "vivado_xci"
    value = _load_json(path, artifact, errors)
    if value is None:
        return
    try:
        parameters = value["ip_inst"]["parameters"]
        component = parameters["component_parameters"]
        project = parameters["project_parameters"]
    except (KeyError, TypeError) as exc:
        _record_mismatch(
            errors,
            artifact,
            "schema",
            "ip_inst.parameters component/project parameters",
            str(exc),
            reason="UNPARSEABLE",
        )
        return
    observed_project = {key: _single_value(project.get(key)) for key in EXPECTED_XCI_PROJECT}
    for field, expected in EXPECTED_XCI_PROJECT.items():
        if observed_project[field] != expected:
            _record_mismatch(errors, artifact, field, expected, observed_project[field])
    observed = {field: _single_value(component.get(field)) for field in EXPECTED_PS7_PARAMETERS}
    _check_parameter_values(errors, artifact, observed)


def validate_bd(path: Path, errors: list[dict[str, Any]]) -> None:
    artifact = "vivado_block_design"
    value = _load_json(path, artifact, errors)
    if value is None:
        return
    try:
        design = value["design"]
        observed_device = design["design_info"]["device"]
        component = design["components"]["processing_system7_0"]
        parameters = component["parameters"]
    except (KeyError, TypeError) as exc:
        _record_mismatch(
            errors,
            artifact,
            "schema",
            "PS7 block-design serialization",
            str(exc),
            reason="UNPARSEABLE",
        )
        return
    if observed_device != EXPECTED_DEVICE:
        _record_mismatch(errors, artifact, "device", EXPECTED_DEVICE, observed_device)
    expected_xci_name = "p6_ps_system_processing_system7_0_0"
    observed_xci_name = component.get("xci_name")
    observed_xci_path = str(component.get("xci_path", "")).replace("\\", "/")
    if observed_xci_name != expected_xci_name:
        _record_mismatch(errors, artifact, "xci_name", expected_xci_name, observed_xci_name)
    expected_xci_suffix = f"ip/{expected_xci_name}/{expected_xci_name}.xci"
    if not observed_xci_path.endswith(expected_xci_suffix):
        _record_mismatch(
            errors, artifact, "xci_path", expected_xci_suffix, observed_xci_path
        )
    observed: dict[str, str] = {}
    for field in EXPECTED_PS7_PARAMETERS:
        entry = parameters.get(field)
        if isinstance(entry, dict) and "value" in entry:
            observed[field] = str(entry["value"])
    _check_parameter_values(errors, artifact, observed, EXPECTED_BD_PARAMETERS)
    # A derived property is normally absent from sparse .bd JSON.  If Vivado
    # does serialize it, it must still match rather than being silently ignored.
    for field in BD_DERIVED_PARAMETERS:
        if field in observed and observed[field] != EXPECTED_PS7_PARAMETERS[field]:
            _record_mismatch(
                errors,
                artifact,
                field,
                EXPECTED_PS7_PARAMETERS[field],
                observed[field],
            )


def _find_ps7_module(root: ET.Element) -> ET.Element | None:
    for element in root.iter():
        if element.tag.endswith("MODULE") and element.attrib.get("MODTYPE") == "processing_system7":
            return element
    return None


def _check_init_payload(
    errors: list[dict[str, Any]], artifact: str, name: str, data: bytes
) -> None:
    if not data:
        _record_mismatch(errors, artifact, name, "non-empty", 0, reason="EMPTY_FILE")
        return
    text = data.decode("utf-8", errors="replace")
    if name.endswith(".tcl"):
        required = ("proc ps7_init", "proc ps7_post_config")
    else:
        required = ("ps7_init", "ps7_post_config")
    for marker in required:
        if marker not in text:
            _record_mismatch(
                errors,
                artifact,
                name,
                f"contains {marker}",
                "marker absent",
                reason="MISSING_ENTRYPOINT",
            )


def validate_xsa(
    path: Path,
    errors: list[dict[str, Any]],
) -> dict[str, bytes]:
    artifact = "vivado_xsa"
    payloads: dict[str, bytes] = {}
    if not path.is_file():
        _record_mismatch(errors, artifact, "file", "present", None, reason="MISSING_FILE")
        return payloads
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            for required in ("p6_ps_system.hwh", "sysdef.xml", "ps7_init.tcl", "ps7_init.c"):
                if required not in names:
                    _record_mismatch(
                        errors,
                        artifact,
                        required,
                        "present",
                        None,
                        reason="MISSING_FILE",
                    )
                else:
                    payloads[required] = archive.read(required)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        _record_mismatch(
            errors,
            artifact,
            "serialization",
            "parseable XSA ZIP",
            type(exc).__name__,
            reason="UNPARSEABLE",
        )
        return {}
    if "sysdef.xml" in payloads:
        sysdef = _load_xml_bytes(payloads["sysdef.xml"], "xsa_sysdef", errors)
        observed_device = None
        if sysdef is not None:
            for element in sysdef.iter():
                if "PART" in element.attrib:
                    observed_device = element.attrib["PART"]
                    break
        if observed_device != EXPECTED_DEVICE:
            _record_mismatch(errors, "xsa_sysdef", "device", EXPECTED_DEVICE, observed_device)
    if "p6_ps_system.hwh" in payloads:
        hwh = _load_xml_bytes(payloads["p6_ps_system.hwh"], "xsa_hwh", errors)
        if hwh is not None:
            module = _find_ps7_module(hwh)
            if module is None:
                _record_mismatch(
                    errors,
                    "xsa_hwh",
                    "processing_system7",
                    "present",
                    None,
                    reason="MISSING_FIELD",
                )
            else:
                _check_parameter_values(errors, "xsa_hwh", _xml_parameters(module))
    for name in ("ps7_init.tcl", "ps7_init.c"):
        if name in payloads:
            _check_init_payload(errors, "xsa_ps7_init", name, payloads[name])
    return payloads


def _compare_file_to_bytes(
    path: Path,
    expected: bytes | None,
    artifact: str,
    field: str,
    errors: list[dict[str, Any]],
) -> None:
    if not path.is_file():
        _record_mismatch(errors, artifact, field, "present", None, reason="MISSING_FILE")
        return
    data = path.read_bytes()
    _check_init_payload(errors, artifact, field, data)
    if expected is None:
        _record_mismatch(
            errors,
            artifact,
            field,
            "XSA reference available",
            None,
            reason="REFERENCE_MISSING",
        )
    elif data != expected:
        _record_mismatch(
            errors,
            artifact,
            field,
            hashlib.sha256(expected).hexdigest(),
            hashlib.sha256(data).hexdigest(),
            reason="HASH_MISMATCH",
        )


def validate_ps7_parameters(path: Path, errors: list[dict[str, Any]]) -> None:
    artifact = "vitis_ps7_parameters"
    root = _load_xml_file(path, artifact, errors)
    if root is None:
        return
    module = _find_ps7_module(root)
    if module is None:
        _record_mismatch(
            errors,
            artifact,
            "processing_system7",
            "present",
            None,
            reason="MISSING_FIELD",
        )
        return
    _check_parameter_values(errors, artifact, _xml_parameters(module))


def _base_report(phase: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": phase,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expected_device": EXPECTED_DEVICE,
        "expected_ps7_parameters": EXPECTED_PS7_PARAMETERS,
        "errors": [],
        "artifacts": {},
        "hardware_action_taken": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def validate_vivado_artifacts(
    *,
    build_tcl: Path,
    xci: Path,
    block_design: Path,
    xsa: Path,
    ps7_init_tcl: Path,
    ps7_init_c: Path,
) -> dict[str, Any]:
    report = _base_report("vivado")
    errors: list[dict[str, Any]] = report["errors"]
    paths = {
        "build_tcl": build_tcl,
        "vivado_xci": xci,
        "vivado_block_design": block_design,
        "vivado_xsa": xsa,
        "vivado_ps7_init_tcl": ps7_init_tcl,
        "vivado_ps7_init_c": ps7_init_c,
    }
    report["artifacts"] = {name: _artifact(path) for name, path in paths.items()}
    validate_build_tcl(build_tcl, errors)
    validate_xci(xci, errors)
    validate_bd(block_design, errors)
    xsa_payloads = validate_xsa(xsa, errors)
    _compare_file_to_bytes(
        ps7_init_tcl,
        xsa_payloads.get("ps7_init.tcl"),
        "vivado_ps7_init",
        "ps7_init.tcl",
        errors,
    )
    _compare_file_to_bytes(
        ps7_init_c,
        xsa_payloads.get("ps7_init.c"),
        "vivado_ps7_init",
        "ps7_init.c",
        errors,
    )
    report["status"] = "PASS" if not errors else "FAIL"
    return report


def validate_vitis_artifacts(
    *,
    xsa: Path,
    platform_xsa: Path,
    ps7_parameters: Path,
    platform_ps7_init_tcl: Path,
    platform_ps7_init_c: Path,
    fsbl_ps7_init_c: Path,
) -> dict[str, Any]:
    report = _base_report("vitis")
    errors: list[dict[str, Any]] = report["errors"]
    paths = {
        "vivado_xsa": xsa,
        "vitis_platform_xsa": platform_xsa,
        "vitis_ps7_parameters": ps7_parameters,
        "vitis_platform_ps7_init_tcl": platform_ps7_init_tcl,
        "vitis_platform_ps7_init_c": platform_ps7_init_c,
        "vitis_fsbl_ps7_init_c": fsbl_ps7_init_c,
    }
    report["artifacts"] = {name: _artifact(path) for name, path in paths.items()}
    xsa_payloads = validate_xsa(xsa, errors)
    if not platform_xsa.is_file():
        _record_mismatch(
            errors, "vitis_platform_xsa", "file", "present", None, reason="MISSING_FILE"
        )
    elif not xsa.is_file() or sha256(platform_xsa) != sha256(xsa):
        _record_mismatch(
            errors,
            "vitis_platform_xsa",
            "sha256",
            None if not xsa.is_file() else sha256(xsa),
            sha256(platform_xsa),
            reason="HASH_MISMATCH",
        )
    validate_ps7_parameters(ps7_parameters, errors)
    _compare_file_to_bytes(
        platform_ps7_init_tcl,
        xsa_payloads.get("ps7_init.tcl"),
        "vitis_platform_ps7_init",
        "ps7_init.tcl",
        errors,
    )
    _compare_file_to_bytes(
        platform_ps7_init_c,
        xsa_payloads.get("ps7_init.c"),
        "vitis_platform_ps7_init",
        "ps7_init.c",
        errors,
    )
    _compare_file_to_bytes(
        fsbl_ps7_init_c,
        xsa_payloads.get("ps7_init.c"),
        "vitis_fsbl_ps7_init",
        "ps7_init.c",
        errors,
    )
    report["status"] = "PASS" if not errors else "FAIL"
    return report


def _only(paths: Iterable[Path], label: str) -> Path:
    candidates = sorted(path for path in paths if path.is_file())
    if len(candidates) != 1:
        # Return an impossible, stable path so normal fail-closed reporting can
        # identify the missing/ambiguous input without guessing.
        return Path(f"__{label}_expected_exactly_one__")
    return candidates[0]


def validate_generated_board_contract(root: Path, *, include_vitis: bool) -> dict[str, Any]:
    root = root.resolve()
    bd_root = root / "build/p6_ps_candidate/project/p6_ps_candidate.srcs/sources_1/bd/p6_ps_system"
    generated_ip = (
        root
        / "build/p6_ps_candidate/project/p6_ps_candidate.gen/sources_1/bd/p6_ps_system/ip"
        / "p6_ps_system_processing_system7_0_0"
    )
    vivado = validate_vivado_artifacts(
        build_tcl=root / "scripts/build_p6_ps_candidate.tcl",
        xci=(
            bd_root
            / "ip/p6_ps_system_processing_system7_0_0"
            / "p6_ps_system_processing_system7_0_0.xci"
        ),
        block_design=bd_root / "p6_ps_system.bd",
        xsa=root / "evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate.xsa",
        ps7_init_tcl=generated_ip / "ps7_init.tcl",
        ps7_init_c=generated_ip / "ps7_init.c",
    )
    combined = _base_report("all" if include_vitis else "vivado")
    combined["vivado"] = vivado
    combined["errors"] = [dict(error, phase="vivado") for error in vivado["errors"]]
    combined["artifacts"] = {f"vivado.{key}": value for key, value in vivado["artifacts"].items()}
    if include_vitis:
        hw = root / "build/p7_ps_vitis_workspace/p7_platform/hw"
        vitis = validate_vitis_artifacts(
            xsa=root / "evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate.xsa",
            platform_xsa=_only(hw.glob("*.xsa"), "vitis_platform_xsa"),
            ps7_parameters=(
                root
                / "build/p7_ps_vitis_workspace/p7_platform/zynq_fsbl/ps7_parameters.xml"
            ),
            platform_ps7_init_tcl=hw / "ps7_init.tcl",
            platform_ps7_init_c=hw / "ps7_init.c",
            fsbl_ps7_init_c=(
                root / "build/p7_ps_vitis_workspace/p7_platform/zynq_fsbl/ps7_init.c"
            ),
        )
        combined["vitis"] = vitis
        combined["errors"].extend(dict(error, phase="vitis") for error in vitis["errors"])
        combined["artifacts"].update(
            {f"vitis.{key}": value for key, value in vitis["artifacts"].items()}
        )
    combined["status"] = "PASS" if not combined["errors"] else "FAIL"
    return combined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--include-vitis", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = validate_generated_board_contract(args.root, include_vitis=args.include_vitis)
    if args.output is not None:
        output = args.output if args.output.is_absolute() else args.root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
