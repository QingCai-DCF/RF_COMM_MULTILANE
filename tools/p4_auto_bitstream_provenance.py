#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from p4_auto_lib import BITSTREAM_DIR, GENERATED, ROOT, active_hashes, candidate_bitstream, git_value, now_iso, rel, sha256_or_missing, write_csv, write_json, write_markdown


STAGES = [
    "safe_idle",
    "tfdu_control_idle",
    "instrumented_idle",
    "raw_pulse",
    "raw_lane_matrix",
    "protocol_lane0",
    "protocol_lane0_ack",
    "protocol_lane1",
    "protocol_lane1_ack",
    "protocol_two_lane_minimal",
    "protocol_lane0_soak",
    "protocol_two_lane_soak",
]


def _immutable_path(stage: str, source: Path, digest: str) -> Path:
    head = git_value("rev-parse", "--short", "HEAD") or "unknown"
    return BITSTREAM_DIR / stage / f"{stage}_{head}_{digest[:16]}{source.suffix}"


def _safe_idle_debug_probe_integrated() -> bool:
    top = (ROOT / "rtl" / "ir_top_new.sv").read_text(encoding="utf-8", errors="ignore")
    probe = ROOT / "rtl" / "debug" / "tfdu_debug_probe.sv"
    return probe.exists() and "u_p4_auto_safe_idle_probe" in top and "tfdu_debug_probe" in top


def generate_bitstream_provenance(used_for_programming: bool = False, programmed_bitstream: str = "") -> dict:
    safe_cand = candidate_bitstream("safe_idle")
    stage_candidates = {
        "safe_idle": safe_cand,
        "instrumented_idle": safe_cand,
        "tfdu_control_idle": candidate_bitstream("tfdu_control_idle"),
        "raw_pulse": candidate_bitstream("raw_pulse"),
        "raw_lane_matrix": candidate_bitstream("raw_lane_matrix"),
        "protocol_lane0": candidate_bitstream("protocol_lane0"),
        "protocol_lane0_ack": candidate_bitstream("protocol_lane0_ack"),
        "protocol_lane1": candidate_bitstream("protocol_lane1"),
        "protocol_lane1_ack": candidate_bitstream("protocol_lane1_ack"),
        "protocol_two_lane_minimal": candidate_bitstream("protocol_two_lane_minimal"),
        "protocol_lane0_soak": candidate_bitstream("protocol_lane0_soak"),
        "protocol_two_lane_soak": candidate_bitstream("protocol_two_lane_soak"),
    }
    cand = safe_cand
    hashes = active_hashes()
    rows = []
    immutable_created = []
    programmed_rel = rel(ROOT / programmed_bitstream) if programmed_bitstream and not Path(programmed_bitstream).is_absolute() else rel(Path(programmed_bitstream)) if programmed_bitstream else ""
    debug_probe_integrated = _safe_idle_debug_probe_integrated()
    for stage in STAGES:
        stage_cand = stage_candidates.get(stage, {"source_bitstream_path": "MISSING", "build_log_path": "MISSING"})
        source_path = ROOT / stage_cand["source_bitstream_path"] if stage_cand["source_bitstream_path"] != "MISSING" else None
        debug_probes_rel = stage_cand.get("debug_probes_path", "MISSING")
        debug_probes_path = ROOT / debug_probes_rel if debug_probes_rel != "MISSING" else None
        debug_probes_sha = sha256_or_missing(debug_probes_path)
        has_stage_bitstream = stage in {"safe_idle", "instrumented_idle", "tfdu_control_idle", "raw_pulse", "raw_lane_matrix", "protocol_lane0", "protocol_lane0_ack", "protocol_lane1", "protocol_lane1_ack", "protocol_two_lane_minimal", "protocol_lane0_soak", "protocol_two_lane_soak"} and source_path and source_path.exists()
        if has_stage_bitstream and (stage != "instrumented_idle" or debug_probe_integrated):
            digest = sha256_or_missing(source_path)
            immutable = _immutable_path(stage, source_path, digest)
            immutable.parent.mkdir(parents=True, exist_ok=True)
            if not immutable.exists() or sha256_or_missing(immutable) != digest:
                shutil.copy2(source_path, immutable)
            status = "PASS"
            immutable_path = rel(immutable)
            immutable_sha = sha256_or_missing(immutable)
            immutable_created.append(immutable_path)
            build_log = stage_cand["build_log_path"]
            source = rel(source_path)
        else:
            status = "SKIP_WITH_REASON"
            immutable_path = "MISSING"
            immutable_sha = "MISSING"
            build_log = "SKIP_WITH_REASON: no stage-specific P4_AUTO bitstream has been built"
            source = "MISSING" if stage != "safe_idle" else cand["source_bitstream_path"]
        rows.append(
            {
                "stage": stage,
                "source_bitstream_path": source,
                "immutable_bitstream_path": immutable_path,
                "sha256": immutable_sha,
                "created_at_utc": now_iso() if status == "PASS" else "",
                "git_head": git_value("rev-parse", "HEAD"),
                "active_profile_path": "board_profiles/ACTIVE_PROFILE.json",
                "active_profile_sha256": hashes["active_profile"],
                "active_xdc_path": "constraints/active/PORT1.generated.xdc",
                "active_xdc_sha256": hashes["active_xdc"],
                "pinmap_path": "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
                "pinmap_sha256": hashes["pinmap"],
                "build_log_path": build_log,
                "debug_probes_path": debug_probes_rel if status == "PASS" and stage in {"safe_idle", "instrumented_idle", "tfdu_control_idle", "raw_pulse", "raw_lane_matrix", "protocol_lane0", "protocol_lane0_ack", "protocol_lane1", "protocol_lane1_ack", "protocol_two_lane_minimal", "protocol_lane0_soak", "protocol_two_lane_soak"} else "MISSING",
                "debug_probes_sha256": debug_probes_sha if status == "PASS" and stage in {"safe_idle", "instrumented_idle", "tfdu_control_idle", "raw_pulse", "raw_lane_matrix", "protocol_lane0", "protocol_lane0_ack", "protocol_lane1", "protocol_lane1_ack", "protocol_two_lane_minimal", "protocol_lane0_soak", "protocol_two_lane_soak"} else "MISSING",
                "used_for_programming": str(bool(used_for_programming and status == "PASS" and (not programmed_rel or programmed_rel == immutable_path))).lower(),
                "status": status,
            }
        )
    fieldnames = list(rows[0].keys())
    write_csv(BITSTREAM_DIR / "bitstream_manifest.csv", fieldnames, rows)
    write_json(BITSTREAM_DIR / "bitstream_manifest.json", rows)
    pass_rows = [row for row in rows if row["status"] == "PASS"]
    result = "PASS" if pass_rows else "SKIP_WITH_REASON"
    lines = [
        f"P4_AUTO_BITSTREAM_PROVENANCE: {result}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"GENERATED_BITSTREAM_PATH_FORBIDDEN_AS_AUTH_OBJECT: `{cand['source_bitstream_path']}`",
        f"GENERATED_BITSTREAM_SHA256: `{cand['source_bitstream_sha256']}`",
        f"BITSTREAM_MANIFEST_CSV: `{rel(BITSTREAM_DIR / 'bitstream_manifest.csv')}`",
        f"BITSTREAM_MANIFEST_JSON: `{rel(BITSTREAM_DIR / 'bitstream_manifest.json')}`",
        f"SAFE_IDLE_DEBUG_PROBE_INTEGRATED: {str(debug_probe_integrated).lower()}",
        f"SAFE_IDLE_DEBUG_PROBES: `{debug_probes_rel}`",
        f"SAFE_IDLE_DEBUG_PROBES_SHA256: `{debug_probes_sha}`",
        "",
        "## Immutable Bitstreams",
        "",
        *(f"- `{item}`" for item in immutable_created),
        *(["- none"] if not immutable_created else []),
        "",
        "## Stage Rows",
        "",
        "| Stage | Status | Immutable Path | SHA256 | Used For Programming |",
        "| --- | --- | --- | --- | --- |",
        *(f"| {row['stage']} | {row['status']} | `{row['immutable_bitstream_path']}` | `{row['sha256']}` | {row['used_for_programming']} |" for row in rows),
    ]
    write_markdown(
        GENERATED / "p4_auto_bitstream_provenance_summary.md",
        "P4 Auto Bitstream Provenance Summary",
        result,
        "generated safe-idle bitstream copied to an immutable P4_AUTO path" if result == "PASS" else "no bitstream candidate available",
        lines,
    )
    return {
        "P4_AUTO_BITSTREAM_PROVENANCE": result,
        "manifest_csv": rel(BITSTREAM_DIR / "bitstream_manifest.csv"),
        "manifest_json": rel(BITSTREAM_DIR / "bitstream_manifest.json"),
        "immutable_bitstreams": immutable_created,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create P4_AUTO immutable bitstream provenance without touching hardware.")
    parser.add_argument("--used-for-programming", action="store_true")
    parser.add_argument("--programmed-bitstream", default="")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = generate_bitstream_provenance(used_for_programming=args.used_for_programming, programmed_bitstream=args.programmed_bitstream)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload["P4_AUTO_BITSTREAM_PROVENANCE"] in {"PASS", "SKIP_WITH_REASON"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
