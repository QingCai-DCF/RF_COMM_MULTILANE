#!/usr/bin/env python3
"""Classify 2-lane ILA matrix results without touching hardware."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def expected_link(analysis: dict[str, Any]) -> dict[str, Any] | None:
    expected = str(analysis.get("expected", ""))
    links = analysis.get("links", {})
    link = links.get(expected)
    return link if isinstance(link, dict) else None


def classify_one(analysis: dict[str, Any]) -> dict[str, Any]:
    expected = str(analysis.get("expected", "UNKNOWN"))
    trigger = str(analysis.get("trigger_mode", "UNKNOWN"))
    verdict = str(analysis.get("verdict", "UNKNOWN"))
    link = expected_link(analysis)

    if link is None:
        return {
            "trigger": trigger,
            "expected": expected,
            "classification": "EVIDENCE_MISSING_EXPECTED_LINK",
            "tx_pulses": None,
            "rx_pulses": None,
            "reason": "expected link is absent from analyzer output",
        }

    tx_pulses = int(link.get("tx_pulses") or 0)
    rx_pulses = int(link.get("rx_pulses") or 0)
    near_rx_pulses = int(link.get("near_rx_pulses") or 0)
    tx_edges = int(link.get("tx_edges") or 0)
    rx_edges = int(link.get("rx_edges") or 0)
    near_rx_edges = int(link.get("near_rx_edges") or 0)
    link_verdict = str(link.get("verdict", "UNKNOWN"))

    if verdict.startswith("PASS") and link_verdict.startswith("PASS"):
        classification = "PASS_PHYSICAL_RAW_PULSE"
        reason = "expected TX and RX pulse activity are both present"
    elif tx_pulses > 0 and rx_pulses == 0:
        classification = "FAIL_PHYSICAL_RX_MISSING"
        if near_rx_pulses > 0:
            reason = "expected TX pulses exist but far-end RX is absent; near-end RX echo is present"
        else:
            reason = "expected TX pulses exist but corresponding RX pulses are absent"
    elif tx_pulses == 0:
        classification = "FAIL_TEST_OR_TX_MISSING"
        reason = "expected TX pulses are absent, so the physical link was not exercised"
    elif rx_pulses > 0 and not link_verdict.startswith("PASS"):
        classification = "WARN_RX_PRESENT_BUT_ANALYZER_FAILED"
        reason = f"RX pulses exist but link verdict is {link_verdict}"
    else:
        classification = "INCONCLUSIVE"
        reason = f"unclassified analyzer state: capture={verdict}, link={link_verdict}"

    return {
        "trigger": trigger,
        "expected": expected,
        "classification": classification,
        "tx_pulses": tx_pulses,
        "rx_pulses": rx_pulses,
        "near_rx_pulses": near_rx_pulses,
        "tx_edges": tx_edges,
        "rx_edges": rx_edges,
        "near_rx_edges": near_rx_edges,
        "reason": reason,
    }


def overall(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "NO_EVIDENCE"
    classes = {str(row["classification"]) for row in rows}
    if classes == {"PASS_PHYSICAL_RAW_PULSE"}:
        return "PASS_ALL_EXPECTED_LINKS"
    if "FAIL_PHYSICAL_RX_MISSING" in classes:
        return "FAIL_PHYSICAL_RX_MISSING"
    if "FAIL_TEST_OR_TX_MISSING" in classes:
        return "FAIL_TEST_OR_TX_MISSING"
    if "EVIDENCE_MISSING_EXPECTED_LINK" in classes:
        return "FAIL_EVIDENCE_MISSING"
    if any(item.startswith("WARN_") for item in classes):
        return "WARN_REVIEW_REQUIRED"
    return "INCONCLUSIVE"


def normalize_required(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for item in raw.split(","):
        name = item.strip().upper()
        if name:
            out.append(name)
    return out


def apply_required_links(
    rows: list[dict[str, Any]], required_links: list[str]
) -> tuple[list[dict[str, Any]], str]:
    if not required_links:
        return rows, overall(rows)

    gated_rows = list(rows)
    missing: list[str] = []
    failing: list[str] = []

    for link_name in required_links:
        matches = [row for row in rows if str(row["expected"]).upper() == link_name]
        if not matches:
            missing.append(link_name)
            gated_rows.append(
                {
                    "trigger": "MISSING",
                    "expected": link_name,
                    "classification": "EVIDENCE_MISSING_REQUIRED_LINK",
                    "tx_pulses": None,
                    "rx_pulses": None,
                    "near_rx_pulses": None,
                    "tx_edges": None,
                    "rx_edges": None,
                    "near_rx_edges": None,
                    "reason": "required link is absent from this matrix",
                }
            )
            continue
        if not any(row["classification"] == "PASS_PHYSICAL_RAW_PULSE" for row in matches):
            failing.append(link_name)

    if missing:
        return gated_rows, "BLOCK_REQUIRED_LINK_EVIDENCE_MISSING"
    if failing:
        return gated_rows, "BLOCK_REQUIRED_LINK_NOT_PASSING"
    return gated_rows, "PASS_REQUIRED_LINKS"


def latest_by_expected(
    rows: list[dict[str, Any]], required_links: list[str] | None = None
) -> list[dict[str, Any]]:
    required_set = {item.upper() for item in required_links or []}
    by_expected: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for row in rows:
        expected = str(row.get("expected", "")).upper()
        if required_set and expected not in required_set:
            continue
        if not expected or expected == "UNKNOWN":
            passthrough.append(row)
            continue
        previous = by_expected.get(expected)
        if previous is None or float(row.get("source_mtime", 0.0)) > float(previous.get("source_mtime", 0.0)):
            by_expected[expected] = row
    return passthrough + [by_expected[key] for key in sorted(by_expected)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "json_paths",
        nargs="+",
        help="Path(s) to analyze_2lane_ila_csv.py JSON output",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--require-links",
        help="Comma-separated required links, e.g. A_TO_B_LANE0,A_TO_B_LANE1,B_TO_A_LANE0,B_TO_A_LANE1",
    )
    parser.add_argument(
        "--latest-by-link",
        action="store_true",
        help="For duplicate expected links, keep only the newest source row before gating",
    )
    args = parser.parse_args()

    source_paths = [resolve_path(raw) for raw in args.json_paths]
    rows: list[dict[str, Any]] = []
    for json_path in source_paths:
        analyses = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(analyses, list):
            raise SystemExit(f"Expected top-level JSON list: {json_path}")
        for item in analyses:
            if not isinstance(item, dict):
                continue
            row = classify_one(item)
            row["source"] = str(json_path)
            row["source_mtime"] = json_path.stat().st_mtime
            rows.append(row)

    required_links = normalize_required(args.require_links)
    if args.latest_by_link:
        rows = latest_by_expected(rows, required_links)

    gated_rows, gated_overall = apply_required_links(rows, required_links)
    result = {
        "sources": [str(path) for path in source_paths],
        "overall": gated_overall,
        "required_links": required_links,
        "results": gated_rows,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"PHYSICAL_MATRIX_SOURCES={';'.join(str(path) for path in source_paths)}")
        print(f"PHYSICAL_MATRIX_OVERALL={result['overall']}")
        if required_links:
            print(f"PHYSICAL_MATRIX_REQUIRED_LINKS={','.join(required_links)}")
        for row in gated_rows:
            source_name = Path(str(row.get("source", ""))).name if row.get("source") else ""
            print(
                "PHYSICAL_MATRIX_ROW "
                f"source={source_name} trigger={row['trigger']} expected={row['expected']} "
                f"classification={row['classification']} "
                f"tx_pulses={row['tx_pulses']} rx_pulses={row['rx_pulses']} "
                f"near_rx_pulses={row.get('near_rx_pulses')} "
                f"reason={row['reason']}"
            )

    return 0 if result["overall"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
