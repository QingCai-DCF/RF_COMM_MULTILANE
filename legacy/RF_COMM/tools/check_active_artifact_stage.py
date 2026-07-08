#!/usr/bin/env python3
"""Guard the currently active RF_COMM artifacts against stage mix-ups.

The script is read-only for design/project sources. It hashes the active bit,
LTX, XSA, BOOT.BIN, shutdown bitstream, and project constraint, then classifies
the active artifact set. Hardware runners can call it before programming so a
P1 physical-lane retry is not accidentally run with an ACK-only or stale image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CONSTRAINT = ROOT / "\u9879\u76ee\u7ea6\u675f(\u76ee\u6807\uff09.txt"

EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

ARTIFACTS = {
    "active_bit": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.bit",
    "active_ltx": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.ltx",
    "active_xsa": ROOT / "TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa",
    "active_boot": ROOT / "software/_boot/BOOT.BIN",
    "shutdown_bit": ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit",
    "constraint": CONSTRAINT,
}

P1_2LANE_ILA_BASELINE = {
    "active_bit": "96963E740D9B115C0E60A89B355C9EB775716F2DE06E30C0EB6048DF441DAA5B",
    "active_ltx": "32805D7AE4FDFB411F74E821A6CCF99702C879E825318548224640062F18913C",
    "active_xsa": "E7A137FA96507C1E1A3290B1A548711E4F560E68834FF490588946B8FFA3D17F",
    "active_boot": "4C753690E35F5D3ED2F611E3D83602BF4A94CE260E34FBF241F24378BBF7C30D",
    "shutdown_bit": "F72680DD3EDA852E64F0B844F54D372368FDB3BDEB775B75507623E6DC167765",
    "constraint": EXPECTED_CONSTRAINT_SHA256,
}

P1_CURRENT_MANIFESTS = [
    REPORTS / "p1_2lane_ila_baseline_manifest_current.json",
    ROOT / "evidence/manifest/current_baseline_manifest.json",
]

P1_CURRENT_MANIFEST_STAGE = "P1_2LANE_ILA_BASELINE_CURRENT"
P1_CURRENT_MANIFEST_OVERALL = "PASS_READY_FOR_P1_MATRIX"
P1_CURRENT_REQUIRED_HASHES = {"active_bit", "active_ltx", "active_xsa", "active_boot", "shutdown_bit", "constraint"}


@dataclass
class ArtifactRow:
    name: str
    path: str
    exists: bool
    sha256: str
    expected_p1_sha256: str
    p1_match: bool


@dataclass
class ManifestMatch:
    manifest: str
    matched_hash_count: int
    required_hash_count: int
    stage_hint: str


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if cell is None else str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def collect_artifacts() -> list[ArtifactRow]:
    rows: list[ArtifactRow] = []
    for name, path in ARTIFACTS.items():
        actual = sha256(path)
        expected = P1_2LANE_ILA_BASELINE.get(name, "")
        rows.append(
            ArtifactRow(
                name=name,
                path=rel(path),
                exists=path.exists(),
                sha256=actual,
                expected_p1_sha256=expected,
                p1_match=bool(expected and actual == expected),
            )
        )
    return rows


def classify_p1(rows: list[ArtifactRow]) -> bool:
    required = {"active_bit", "active_ltx", "active_xsa", "active_boot", "shutdown_bit", "constraint"}
    return all(row.name not in required or row.p1_match for row in rows)


def manifest_hashes(text: str) -> set[str]:
    return {match.group(0).upper() for match in re.finditer(r"\b[A-Fa-f0-9]{64}\b", text)}


def stage_hint(text: str) -> str:
    lowered = text.lower()
    if "ack" in lowered:
        return "P0_ACK_ONLY_ARTIFACT"
    if "2lane" in lowered or "2-lane" in lowered:
        return "P1_2LANE_ILA_BASELINE"
    return "MANIFEST_MATCH"


def collect_p1_current_manifest_matches(rows: list[ArtifactRow]) -> list[ManifestMatch]:
    active_hashes = {row.name: row.sha256 for row in rows}
    matches: list[ManifestMatch] = []
    for manifest in P1_CURRENT_MANIFESTS:
        if not manifest.exists():
            continue
        try:
            payload = json.loads(read_text(manifest))
        except (OSError, json.JSONDecodeError):
            continue

        meta = payload.get("meta", {})
        if meta.get("stage") != P1_CURRENT_MANIFEST_STAGE:
            continue
        if meta.get("overall") != P1_CURRENT_MANIFEST_OVERALL:
            continue
        if str(meta.get("constraint_sha256", "")).upper() != EXPECTED_CONSTRAINT_SHA256:
            continue

        checks = payload.get("source_checks", [])
        if not checks or any(check.get("status") != "PASS" for check in checks):
            continue

        manifest_hashes_by_name = {
            item.get("name"): str(item.get("sha256", "")).upper()
            for item in payload.get("artifacts", [])
            if item.get("name")
        }
        matched = 0
        for name in P1_CURRENT_REQUIRED_HASHES:
            manifest_hash = manifest_hashes_by_name.get(name, "")
            active_hash = active_hashes.get(name, "")
            if manifest_hash and active_hash and manifest_hash == active_hash and active_hash != "MISSING":
                matched += 1

        if matched:
            matches.append(
                ManifestMatch(
                    manifest=rel(manifest),
                    matched_hash_count=matched,
                    required_hash_count=len(P1_CURRENT_REQUIRED_HASHES),
                    stage_hint=P1_CURRENT_MANIFEST_STAGE,
                )
            )
    return matches


def collect_manifest_matches(rows: list[ArtifactRow]) -> list[ManifestMatch]:
    matches = collect_p1_current_manifest_matches(rows)
    manifests = sorted(ROOT.glob("reports/p0_ack_only_artifacts/**/p0_ack_only_manifest.txt"))
    active_hashes = {row.sha256 for row in rows if row.name in {"active_bit", "active_ltx", "active_xsa", "active_boot"}}
    active_hashes.discard("MISSING")
    for manifest in manifests:
        try:
            text = read_text(manifest)
        except OSError:
            continue
        present = manifest_hashes(text)
        matched = len(active_hashes & present)
        if matched:
            matches.append(
                ManifestMatch(
                    manifest=rel(manifest),
                    matched_hash_count=matched,
                    required_hash_count=len(active_hashes),
                    stage_hint=stage_hint(text),
                )
            )
    matches.sort(key=lambda item: (item.matched_hash_count, item.manifest), reverse=True)
    return matches


def classify(rows: list[ArtifactRow], matches: list[ManifestMatch]) -> tuple[str, str]:
    if classify_p1(rows):
        return "P1_2LANE_ILA_BASELINE", "All active artifacts match the known P1 2-lane ILA baseline hashes."
    full_current = next(
        (
            match
            for match in matches
            if match.stage_hint == P1_CURRENT_MANIFEST_STAGE
            and match.matched_hash_count == match.required_hash_count
        ),
        None,
    )
    if full_current is not None:
        return "P1_2LANE_ILA_BASELINE", f"Active hashes match current P1 2-lane ILA baseline manifest {full_current.manifest}."
    full_ack = next((match for match in matches if match.stage_hint == "P0_ACK_ONLY_ARTIFACT" and match.matched_hash_count == match.required_hash_count), None)
    if full_ack is not None:
        return "P0_ACK_ONLY_ARTIFACT", f"Active hashes match ACK-only manifest {full_ack.manifest}."
    missing = [row.name for row in rows if not row.exists]
    if missing:
        return "MISSING_ARTIFACTS", "Missing: " + ", ".join(missing)
    p1_mismatches = [row.name for row in rows if not row.p1_match]
    return "UNKNOWN_OR_MODIFIED_ARTIFACTS", "P1 hash mismatch: " + ", ".join(p1_mismatches)


def render_markdown(rows: list[ArtifactRow], matches: list[ManifestMatch], stage: str, reason: str, expect: str, result: str) -> str:
    manifest_rows = [
        [match.manifest, match.matched_hash_count, match.required_hash_count, match.stage_hint]
        for match in matches
    ]
    if not manifest_rows:
        manifest_rows = [["none", 0, 0, "none"]]

    return "\n".join(
        [
            "# RF_COMM Active Artifact Guard",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Verdict",
            "",
            f"- Stage: `{stage}`",
            f"- Expected: `{expect}`",
            f"- Result: `{result}`",
            f"- Reason: {reason}",
            "",
            "## Active Artifacts",
            "",
            md_table(
                ["name", "path", "exists", "sha256", "p1_match"],
                [[row.name, row.path, int(row.exists), row.sha256, int(row.p1_match)] for row in rows],
            ),
            "",
            "## Manifest Matches",
            "",
            md_table(["manifest", "matched_hashes", "required_hashes", "stage_hint"], manifest_rows),
            "",
            f"ACTIVE_ARTIFACT_GUARD stage={stage} expect={expect} result={result}",
            "",
        ]
    )


def expectation_pass(stage: str, expect: str) -> bool:
    if expect in {"ANY", "any", "*"}:
        return stage not in {"MISSING_ARTIFACTS", "UNKNOWN_OR_MODIFIED_ARTIFACTS"}
    return stage == expect


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", default="P1_2LANE_ILA_BASELINE")
    parser.add_argument("--out", type=Path, default=REPORTS / "active_artifact_guard_current_20260626.md")
    parser.add_argument("--json", type=Path, default=REPORTS / "active_artifact_guard_current_20260626.json")
    args = parser.parse_args()

    rows = collect_artifacts()
    matches = collect_manifest_matches(rows)
    stage, reason = classify(rows, matches)
    passed = expectation_pass(stage, args.expect)
    result = "PASS" if passed else "FAIL"

    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(rows, matches, stage, reason, args.expect, result), encoding="utf-8")

    json_out = args.json if args.json.is_absolute() else ROOT / args.json
    json_payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "expect": args.expect,
        "result": result,
        "reason": reason,
        "artifacts": [asdict(row) for row in rows],
        "manifest_matches": [asdict(match) for match in matches],
        "hardware_action": "none",
        "design_source_action": "none",
    }
    json_out.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"ACTIVE_ARTIFACT_STAGE={stage}")
    print(f"ACTIVE_ARTIFACT_GUARD_EXPECT={args.expect}")
    print(f"ACTIVE_ARTIFACT_GUARD_RESULT={result}")
    print(f"ACTIVE_ARTIFACT_GUARD_REASON={reason}")
    print(f"ACTIVE_ARTIFACT_GUARD_MARKDOWN={out}")
    print(f"ACTIVE_ARTIFACT_GUARD_JSON={json_out}")
    return 0 if passed else 12


if __name__ == "__main__":
    sys.exit(main())
