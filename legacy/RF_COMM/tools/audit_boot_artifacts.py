#!/usr/bin/env python3
"""Audit RF_COMM Zynq BOOT.BIN packages against their BIF components."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Component:
    role: str
    path: str
    exists: bool
    size: int
    mtime: str
    sha256: str


@dataclass
class BootAudit:
    package: str
    boot_bin: str
    bif: str
    status: str
    boot_exists: bool
    boot_size: int
    boot_mtime: str
    boot_sha256: str
    components: list[Component]
    stale_inputs: list[str]
    app_markers_found: list[str]
    app_markers_missing: list[str]
    notes: list[str]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_bif(path: Path) -> list[tuple[str, Path]]:
    components: list[tuple[str, Path]] = []
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line in {"the_ROM_image:", "{", "}"}:
            continue
        role = "unknown"
        if "[bootloader]" in line:
            role = "fsbl"
            line = line.replace("[bootloader]", "").strip()
        line = line.strip().strip('"')
        if not line:
            continue
        comp_path = Path(line)
        if comp_path.suffix.lower() == ".bit":
            role = "bitstream"
        elif comp_path.suffix.lower() == ".elf" and role != "fsbl":
            role = "application"
        components.append((role, comp_path))
    return components


def component_info(role: str, path: Path) -> Component:
    if not path.exists():
        return Component(role, str(path), False, 0, "", "MISSING")
    item = path.stat()
    return Component(
        role=role,
        path=rel(path),
        exists=True,
        size=item.st_size,
        mtime=datetime.fromtimestamp(item.st_mtime).isoformat(timespec="seconds"),
        sha256=sha256(path),
    )


def binary_contains(path: Path, marker: str) -> bool:
    if not path.exists():
        return False
    data = path.read_bytes()
    return marker.encode("ascii", errors="ignore") in data


def audit_package(
    name: str,
    boot_bin: Path,
    bif: Path,
    expected_markers: list[str],
) -> BootAudit:
    notes: list[str] = []
    boot_exists = boot_bin.exists()
    boot_size = boot_bin.stat().st_size if boot_exists else 0
    boot_mtime_ts = boot_bin.stat().st_mtime if boot_exists else 0.0
    boot_mtime = datetime.fromtimestamp(boot_mtime_ts).isoformat(timespec="seconds") if boot_exists else ""
    boot_hash = sha256(boot_bin) if boot_exists else "MISSING"

    parsed = parse_bif(bif)
    components = [component_info(role, path) for role, path in parsed]
    if not bif.exists():
        notes.append("BIF missing")
    if not parsed:
        notes.append("No components parsed from BIF")

    stale_inputs: list[str] = []
    for role, path in parsed:
        if path.exists() and boot_exists and path.stat().st_mtime > boot_mtime_ts:
            stale_inputs.append(rel(path))

    app_paths = [path for role, path in parsed if role == "application"]
    app_path = app_paths[0] if app_paths else None
    markers_found: list[str] = []
    markers_missing: list[str] = []
    for marker in expected_markers:
        if app_path is not None and binary_contains(app_path, marker):
            markers_found.append(marker)
        else:
            markers_missing.append(marker)

    roles = {component.role for component in components if component.exists}
    required_roles = {"fsbl", "bitstream", "application"}
    missing_roles = sorted(required_roles - roles)
    for role in missing_roles:
        notes.append(f"Missing role: {role}")
    if stale_inputs:
        notes.append("BOOT.BIN older than one or more BIF inputs")
    if markers_missing:
        notes.append("Application ELF is missing one or more expected UART/protocol markers")

    status = "PASS"
    if not boot_exists or boot_size <= 0 or any(not c.exists or c.size <= 0 for c in components):
        status = "FAIL_MISSING_OR_EMPTY"
    elif missing_roles:
        status = "FAIL_MISSING_ROLE"
    elif stale_inputs:
        status = "WARN_STALE_BOOT_BIN"
    elif markers_missing:
        status = "WARN_MARKER_MISSING"

    return BootAudit(
        package=name,
        boot_bin=rel(boot_bin),
        bif=rel(bif),
        status=status,
        boot_exists=boot_exists,
        boot_size=boot_size,
        boot_mtime=boot_mtime,
        boot_sha256=boot_hash,
        components=components,
        stale_inputs=stale_inputs,
        app_markers_found=markers_found,
        app_markers_missing=markers_missing,
        notes=notes,
    )


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def render_markdown(audits: list[BootAudit]) -> str:
    summary_rows = [
        [
            audit.package,
            audit.status,
            audit.boot_bin,
            str(audit.boot_size),
            audit.boot_sha256,
            "; ".join(audit.notes) if audit.notes else "OK",
        ]
        for audit in audits
    ]
    sections = [
        "# RF_COMM BOOT Artifact Audit",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        markdown_table(["package", "status", "boot_bin", "bytes", "sha256", "notes"], summary_rows),
    ]
    for audit in audits:
        component_rows = [
            [c.role, c.path, "1" if c.exists else "0", str(c.size), c.mtime, c.sha256]
            for c in audit.components
        ]
        sections.extend(
            [
                "",
                f"## {audit.package}",
                "",
                markdown_table(["role", "path", "exists", "bytes", "mtime", "sha256"], component_rows),
                "",
                f"- BIF: `{audit.bif}`",
                f"- BOOT.BIN mtime: `{audit.boot_mtime}`",
                f"- stale inputs: `{', '.join(audit.stale_inputs) if audit.stale_inputs else 'none'}`",
                f"- app markers found: `{', '.join(audit.app_markers_found) if audit.app_markers_found else 'none'}`",
                f"- app markers missing: `{', '.join(audit.app_markers_missing) if audit.app_markers_missing else 'none'}`",
            ]
        )
    sections.append("")
    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    audits = [
        audit_package(
            "ps_lwip_bridge",
            ROOT / "software/_boot/BOOT.BIN",
            ROOT / "software/_boot/rf_comm_boot.bif",
            [
                "RF_COMM PS lwIP bridge",
                "Board IP:",
                "RF TCP bridge listening on port",
                "rf_comm_ps_bridge",
            ],
        ),
        audit_package(
            "ps_ps_loopback",
            ROOT / "software/_boot_ps_ps_loopback/BOOT.BIN",
            ROOT / "software/_boot_ps_ps_loopback/rf_comm_ps_ps_loopback.bif",
            [
                "RF_COMM PS-PS loopback experiment",
                "PSPS_INIT_OK",
                "PSPS_STAGE_SUMMARY",
            ],
        ),
    ]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or (ROOT / "reports" / f"boot_artifact_audit_{stamp}.md")
    out = out if out.is_absolute() else ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(audits), encoding="utf-8")
    print(f"WROTE_MARKDOWN={out}")

    if args.json:
        json_out = args.json if args.json.is_absolute() else ROOT / args.json
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps([asdict(audit) for audit in audits], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WROTE_JSON={json_out}")

    pass_count = sum(1 for audit in audits if audit.status == "PASS")
    warn_count = sum(1 for audit in audits if audit.status.startswith("WARN"))
    fail_count = len(audits) - pass_count - warn_count
    print(f"BOOT_AUDIT_SUMMARY pass={pass_count} warn={warn_count} fail={fail_count} total={len(audits)}")
    for audit in audits:
        print(f"BOOT_AUDIT_ITEM package={audit.package} status={audit.status} boot={audit.boot_bin}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
