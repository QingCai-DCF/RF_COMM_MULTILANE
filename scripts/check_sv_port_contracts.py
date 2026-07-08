#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "evidence" / "generated"

EXPECTED_MODULES = [
    "tfdu_lane_phy",
    "tfdu6102_behavior_model",
    "ir_4ppm_codec",
    "ir_frame_l1",
    "ir_arq_l2",
    "ir_multilane_scheduler",
    "ir_axi_regs_new",
    "ir_top_new",
]
TOP_ONLY_MODULES = {"ir_top_new"}


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    return text


def find_matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    for idx in range(open_idx, len(text)):
        if text[idx] == "(":
            depth += 1
        elif text[idx] == ")":
            depth -= 1
            if depth == 0:
                return idx
    raise ValueError(f"Unbalanced parentheses at offset {open_idx}")


def split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    paren = 0
    bracket = 0
    brace = 0
    for idx, char in enumerate(text):
        if char == "(":
            paren += 1
        elif char == ")":
            paren -= 1
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket -= 1
        elif char == "{":
            brace += 1
        elif char == "}":
            brace -= 1
        elif char == "," and paren == 0 and bracket == 0 and brace == 0:
            parts.append(text[start:idx].strip())
            start = idx + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def parse_module_ports(path: Path) -> dict[str, list[str]]:
    text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
    modules: dict[str, list[str]] = {}
    for match in re.finditer(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", text):
        name = match.group(1)
        idx = match.end()
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx < len(text) and text[idx] == "#":
            idx += 1
            while idx < len(text) and text[idx].isspace():
                idx += 1
            if idx >= len(text) or text[idx] != "(":
                continue
            idx = find_matching_paren(text, idx) + 1
            while idx < len(text) and text[idx].isspace():
                idx += 1
        if idx >= len(text) or text[idx] != "(":
            continue
        end = find_matching_paren(text, idx)
        port_list = text[idx + 1 : end]
        ports: list[str] = []
        for part in split_top_level_commas(port_list):
            identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", part.split("=", 1)[0])
            if identifiers:
                ports.append(identifiers[-1])
        modules[name] = ports
    return modules


def parse_all_modules() -> dict[str, list[str]]:
    modules: dict[str, list[str]] = {}
    for path in [*sorted((ROOT / "rtl").glob("*.sv")), *sorted((ROOT / "sim/models").glob("*.sv"))]:
        modules.update(parse_module_ports(path))
    return modules


def find_instantiations(path: Path, module_name: str) -> list[dict]:
    text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
    instances: list[dict] = []
    for match in re.finditer(rf"\b{re.escape(module_name)}\b", text):
        prefix = text[max(0, match.start() - 16) : match.start()]
        if re.search(r"\bmodule\s+$", prefix):
            continue
        idx = match.end()
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx < len(text) and text[idx] == "#":
            idx += 1
            while idx < len(text) and text[idx].isspace():
                idx += 1
            if idx >= len(text) or text[idx] != "(":
                continue
            idx = find_matching_paren(text, idx) + 1
            while idx < len(text) and text[idx].isspace():
                idx += 1
        inst = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)", text[idx:])
        if not inst:
            continue
        instance_name = inst.group(1)
        idx += len(instance_name)
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text) or text[idx] != "(":
            continue
        end = find_matching_paren(text, idx)
        after = end + 1
        while after < len(text) and text[after].isspace():
            after += 1
        if after >= len(text) or text[after] != ";":
            continue
        body = text[idx + 1 : end]
        port_names = re.findall(r"\.([A-Za-z_][A-Za-z0-9_$]*)\s*\(", body)
        instances.append(
            {
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "module": module_name,
                "instance": instance_name,
                "named_ports": port_names,
                "uses_named_ports": bool(port_names),
            }
        )
    return instances


def main() -> int:
    errors: list[str] = []
    modules = parse_all_modules()
    selected_modules = {name: modules.get(name, []) for name in EXPECTED_MODULES}
    instances: list[dict] = []
    for path in sorted((ROOT / "sim/tb").glob("*.sv")):
        for module_name in EXPECTED_MODULES:
            instances.extend(find_instantiations(path, module_name))

    by_module: dict[str, list[dict]] = defaultdict(list)
    for item in instances:
        by_module[item["module"]].append(item)

    module_ports_present = all(selected_modules[name] for name in EXPECTED_MODULES)
    all_instances_named = all(item["uses_named_ports"] for item in instances)
    no_unknown = True
    no_missing = True
    no_duplicate = True
    instance_reports = []

    for item in instances:
        declared = set(selected_modules[item["module"]])
        connected = item["named_ports"]
        connected_set = set(connected)
        unknown = sorted(connected_set - declared)
        missing = sorted(declared - connected_set)
        duplicates = sorted(port for port, count in Counter(connected).items() if count > 1)
        no_unknown = no_unknown and not unknown
        no_missing = no_missing and not missing
        no_duplicate = no_duplicate and not duplicates
        instance_reports.append({**item, "unknown_ports": unknown, "missing_ports": missing, "duplicate_ports": duplicates})

    tb_coverage = all(name in TOP_ONLY_MODULES or by_module[name] for name in EXPECTED_MODULES)

    checks = {
        "SV_PORT_CONTRACT_MODULES_PARSED": module_ports_present,
        "SV_PORT_CONTRACT_ALL_INSTANCES_NAMED": all_instances_named,
        "SV_PORT_CONTRACT_NO_UNKNOWN_PORTS": no_unknown,
        "SV_PORT_CONTRACT_NO_MISSING_PORTS": no_missing,
        "SV_PORT_CONTRACT_NO_DUPLICATE_PORTS": no_duplicate,
        "SV_PORT_CONTRACT_TB_COVERAGE": tb_coverage,
    }
    for marker, ok in checks.items():
        print(f"{marker}={1 if ok else 0}")
        if not ok:
            errors.append(marker)

    status = "PASS" if not errors else "FAIL"
    print(f"SV_PORT_CONTRACT_STATIC={status}")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    data = {
        "status": status,
        "module_ports": selected_modules,
        "instances": instance_reports,
        "top_only_modules": sorted(TOP_ONLY_MODULES),
    }
    (OUTDIR / "sv_port_contracts.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# SystemVerilog Port Contracts",
        "",
        *[f"{marker}={1 if ok else 0}" for marker, ok in checks.items()],
        f"SV_PORT_CONTRACT_STATIC={status}",
        "",
        "| Module | Instance count | Declared ports |",
        "|---|---:|---:|",
    ]
    for module_name in EXPECTED_MODULES:
        lines.append(f"| `{module_name}` | {len(by_module[module_name])} | {len(selected_modules[module_name])} |")
    lines += [
        "",
        "This static gate checks named-port instance compatibility. It does not replace simulator or Vivado elaboration; tool discovery and simulator execution are recorded by `scripts/run_offline_gates.py`.",
        "",
    ]
    (OUTDIR / "sv_port_contracts.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
