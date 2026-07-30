#!/usr/bin/env python3
"""Generate the read-only P10 AX7020 reference-file inventory.

The generator hashes source files only.  It never writes below either reference
root; all outputs are confined to evidence/generated in the P10 worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_AX7020_ROOT = Path(r"C:\Users\user\Documents\RF_COMM_MULTILANE\hardware_AX7020")
DEFAULT_COMPARISON = Path(r"C:\Users\user\Desktop\AX7010_AX7020_HARDWARE_COMPARISON.md")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(relative_path: str) -> tuple[str, str, str]:
    normalized = relative_path.replace("\\", "/")
    name = Path(relative_path).name
    if normalized.startswith("AX7020UserManualV2.2/"):
        return (
            "OFFICIAL_VENDOR_BOARD_DOCUMENT",
            "ALINX AX7020 User Manual V2.2 source bundle",
            "EXACT_AX7020_DOCUMENT_SET",
        )
    if normalized.startswith("01_SCH/"):
        if name == "AX7020开发板原理图V2.0.pdf":
            return (
                "OFFICIAL_VENDOR_BOARD_DOCUMENT",
                "ALINX AX7010/AX7020 board schematic distributed as AX7020 V2.0",
                "EXACT_AX7020_REFERENCE_NOT_PHYSICAL_REVISION_PROOF",
            )
        if name == "AX7010_AX7020管脚.xlsx":
            return (
                "OFFICIAL_VENDOR_BOARD_DOCUMENT",
                "ALINX AX7010/AX7020 package-pin workbook",
                "EXACT_AX7020_FAMILY_MAPPING",
            )
        return (
            "OFFICIAL_VENDOR_DESIGN_ASSET",
            "ALINX AX7020 OrCAD library",
            "SUPPORTING_ASSET_NOT_IDENTITY_PROOF",
        )
    if normalized.startswith("02_PCB/"):
        return (
            "OFFICIAL_VENDOR_BOARD_DOCUMENT",
            "ALINX AX7020 PCB design package",
            "EXACT_AX7020_REFERENCE_NOT_PHYSICAL_REVISION_PROOF",
        )
    if normalized.startswith("03_structure size/"):
        return (
            "OFFICIAL_VENDOR_BOARD_DOCUMENT",
            "ALINX AX7020 mechanical drawing",
            "EXACT_AX7020_REFERENCE",
        )
    if normalized.startswith("04_datasheet/"):
        if name == "H5TQ4G63AFR.pdf":
            match = "EXACT_DOCUMENTED_DDR_DEVICE"
        elif name == "H5TQ2G63FFR.pdf":
            match = "ALTERNATE_DDR_DEVICE_NOT_AX7020_IDENTITY_PROOF"
        elif name == "ds187-XC7Z010-XC7Z020-Data-Sheet.pdf":
            match = "EXACT_FPGA_FAMILY_DOCUMENT"
        elif name in {
            "ug480_7Series_XADC.pdf",
            "ug585-Zynq-7000-TRM.pdf",
            "ug821-zynq-7000-swdev.pdf",
            "ug865-Zynq-7000-Pkg-Pinout.pdf",
            "ug933-Zynq-7000-PCB.pdf",
        }:
            match = "OFFICIAL_FPGA_FAMILY_REFERENCE"
        else:
            match = "COMPONENT_REFERENCE_NOT_BOARD_REVISION_PROOF"
        return (
            "OFFICIAL_COMPONENT_MANUFACTURER_DOCUMENT",
            "Component-manufacturer datasheet bundled with AX7020 references",
            match,
        )
    return ("UNCLASSIFIED", "No provenance classification rule", "UNRESOLVED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_AX7020_ROOT)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("evidence/generated/p10_board_reference_file_inventory.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("evidence/generated/p10_board_reference_file_inventory.md"),
    )
    args = parser.parse_args()

    root = args.root.resolve(strict=True)
    files = sorted((path for path in root.rglob("*") if path.is_file()), key=lambda p: p.as_posix())
    entries = []
    for path in files:
        relative = str(path.relative_to(root))
        official_status, document_role, model_match = classify(relative)
        entries.append(
            {
                "relative_path": relative.replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "official_status": official_status,
                "document_role": document_role,
                "model_match": model_match,
            }
        )

    comparison = None
    if args.comparison.is_file():
        comparison = {
            "path": str(args.comparison.resolve()),
            "bytes": args.comparison.stat().st_size,
            "sha256": sha256_file(args.comparison),
            "official_status": "USER_SUPPLIED_SECONDARY_COMPARISON",
            "model_match": "CORROBORATION_ONLY_NOT_PIN_AUTHORITY",
        }

    payload = {
        "schema_version": 1,
        "test_id": "P10-BOARD-DOC-FILE-INVENTORY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root),
        "source_root_read_only": True,
        "file_count": len(entries),
        "total_bytes": sum(item["bytes"] for item in entries),
        "all_files_hashed_sha256": True,
        "reference_files": entries,
        "secondary_comparison": comparison,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# P10 AX7020 board-reference per-file inventory",
        "",
        f"- Test ID: `{payload['test_id']}`",
        f"- Read-only root: `{root}`",
        f"- File count: `{payload['file_count']}`",
        f"- Total bytes: `{payload['total_bytes']}`",
        "- Every listed file has a direct SHA256; classification does not make a physical-PCB-revision claim.",
        "",
        "| Relative path | Bytes | SHA256 | Provenance | Model/revision applicability |",
        "|---|---:|---|---|---|",
    ]
    for item in entries:
        lines.append(
            f"| `{item['relative_path']}` | {item['bytes']} | `{item['sha256']}` | "
            f"{item['official_status']} | {item['model_match']} |"
        )
    if comparison:
        lines.extend(
            [
                "",
                "## Secondary user-supplied comparison",
                "",
                f"`{comparison['path']}` — SHA256 `{comparison['sha256']}`. "
                "It is corroboration only and is not used as pin authority.",
            ]
        )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "file_count": len(entries), "total_bytes": payload["total_bytes"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
