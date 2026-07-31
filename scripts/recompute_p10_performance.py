#!/usr/bin/env python3
"""Recompute frozen P10 performance without modifying any P10 evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from p10_1_common import (
    GENERATED,
    RAW,
    ROOT,
    evidence_base,
    rel,
    sha256,
    statistics,
    write_json,
    write_pair,
    write_text,
)
from p10_1_metrics import finalize_metrics, make_metric_record


RUN_ID = "p10_formal_20260730T181535Z_03"
RUN_ROOT = ROOT / f"evidence/hardware/p10/{RUN_ID}"
FINAL = ROOT / "evidence/generated/p10_fasttrack_final_summary.json"
AUDIT = ROOT / "evidence/generated/p10_goodput_measurement_audit.json"
CSV_OUT = GENERATED / "p10_1_historical_metrics.csv"
VECTOR_OUT = RAW / "p10_1_finalizer_vectors.json"
EXPECTED_FINAL = {
    "F_TO_R": 5767.861069534447,
    "R_TO_F": 5785.116365442897,
}


def stage_summary(letter: str) -> tuple[Path, dict[str, Any]]:
    path = RUN_ROOT / f"stages/p10_{letter}/stage_summary.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def direction_name(value: int) -> str:
    if value == 0:
        return "F_TO_R"
    if value == 1:
        return "R_TO_F"
    raise ValueError(f"invalid P10 direction {value}")


def historical_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for letter in "cdefghij":
        path, summary = stage_summary(letter)
        detail_by_key = {
            (item.get("label"), item.get("direction")): item
            for item in summary.get("details", [])
            if item.get("command") == 3
        }
        for perf in summary.get("performance", []):
            key = (perf.get("label"), perf.get("direction"))
            detail = detail_by_key.get(key)
            if not detail:
                raise ValueError(f"P10-{letter.upper()} performance row lacks raw detail: {key}")
            sender_role = detail["end_to_end"]["sender_role"]
            sender = detail[sender_role]
            requested = int(detail["requested_size"])
            encoded = int(detail["end_to_end"]["transfer_bytes"])
            ticks = int(sender["elapsed_ticks"])
            frequency = int(sender["counts_per_second"])
            reported = float(perf["application_goodput_bps"])
            reproduced = encoded * 8.0 * frequency / ticks
            if abs(reproduced - reported) > max(1e-6, reported * 1e-10):
                raise ValueError(f"P10-{letter.upper()} formula mismatch for {key}")
            diagnostic = requested == 1
            rows.append(
                {
                    "stage": f"P10-{letter.upper()}",
                    "label": str(perf["label"]),
                    "direction": direction_name(int(perf["direction"])),
                    "lane_mask": int(detail["lane_mask"]),
                    "requested_useful_bytes": requested,
                    "encoded_transfer_bytes": encoded,
                    "sender_role": sender_role,
                    "elapsed_ticks": ticks,
                    "timer_frequency_hz": frequency,
                    "elapsed_seconds": ticks / frequency,
                    "reported_legacy_bps": reported,
                    "recomputed_encoded_ps_command_bps": reproduced,
                    "recomputed_useful_ps_command_bps": requested * 8.0 * frequency / ticks,
                    "measurement_class": (
                        "DIAGNOSTIC_MICROTRANSFER"
                        if diagnostic
                        else ("SOAK_WINDOW" if letter == "j" else "OBJECT_SINGLE")
                    ),
                    "diagnostic_only": diagnostic,
                    "eligible_for_scaling": False,
                    "source_path": rel(path),
                    "source_sha256": sha256(path),
                }
            )
    return rows


def stage_i_views(rows: list[dict[str, Any]]) -> dict[str, Any]:
    _, stage_i = stage_summary("i")
    by_key = {
        (item["label"], item["direction"]): item
        for item in rows
        if item["stage"] == "P10-I"
    }
    result_rows: list[dict[str, Any]] = []
    for detail in stage_i["details"]:
        if detail.get("command") != 3:
            continue
        direction = direction_name(int(detail["direction"]))
        row = dict(by_key[(detail["label"], direction)])
        # The immutable closeout audit extracted the explicit bounded XSDB
        # case window from the raw observation log. Reuse that explicit field;
        # never infer a unit from a filename or wall-clock text.
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        match = next(
            item for item in audit["stage_i_characterization"]["rows"]
            if item["label"] == detail["label"]
        )
        wall_seconds = float(match["xsdb_case_wall_seconds"])
        row["xsdb_case_wall_seconds"] = wall_seconds
        row["recomputed_useful_xsdb_case_wall_bps"] = (
            row["requested_useful_bytes"] * 8.0 / wall_seconds
        )
        result_rows.append(row)
    return {
        "rows": result_rows,
        "ps_command_useful_bps": statistics(
            [item["recomputed_useful_ps_command_bps"] for item in result_rows]
        ),
        "host_wall_useful_bps": statistics(
            [item["recomputed_useful_xsdb_case_wall_bps"] for item in result_rows]
        ),
    }


def soak_view() -> dict[str, Any]:
    _, stage_j = stage_summary("j")
    elapsed_ms = int(stage_j["markers"]["P10_SOAK_ACTIVE_ELAPSED_MS"])
    elapsed_seconds = elapsed_ms / 1000.0
    directions: list[dict[str, Any]] = []
    for direction in (0, 1):
        details = [
            item for item in stage_j["details"]
            if item.get("command") == 3 and int(item["direction"]) == direction
        ]
        useful = sum(int(item["requested_size"]) for item in details)
        directions.append(
            {
                "direction": direction_name(direction),
                "object_count": len(details),
                "committed_application_bytes": useful,
                "elapsed_seconds": elapsed_seconds,
                "application_goodput_bps": useful * 8.0 / elapsed_seconds,
                "measurement_class": "SOAK_WINDOW",
                "idle_included": True,
                "host_staging_included": True,
                "eligible_for_scaling": False,
            }
        )
    aggregate = sum(item["committed_application_bytes"] for item in directions)
    return {
        "active_window_seconds": elapsed_seconds,
        "directions": directions,
        "aggregate_committed_application_bytes": aggregate,
        "aggregate_application_goodput_bps": aggregate * 8.0 / elapsed_seconds,
        "interpretation": "serialized workload window including intentional idle and host orchestration",
    }


def finalizer_vectors() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    artifact = sha256(Path(__file__))
    frequency = 64_000_000
    vectors = [
        make_metric_record(
            metric_name="APPLICATION_GOODPUT_BPS",
            measurement_class="DIAGNOSTIC_MICROTRANSFER",
            direction="F_TO_R",
            committed_application_bytes=1,
            elapsed_ticks=11_096,
            timer_frequency=frequency,
            run_id="P10_1_OFFLINE_VECTOR",
            case_id="one_byte_diagnostic",
            artifact_sha256=artifact,
            diagnostic_only=True,
        ),
        make_metric_record(
            metric_name="APPLICATION_GOODPUT_BPS",
            measurement_class="OBJECT_SINGLE",
            direction="R_TO_F",
            committed_application_bytes=1024 * 1024,
            elapsed_ticks=12_800_000,
            timer_frequency=frequency,
            run_id="P10_1_OFFLINE_VECTOR",
            case_id="one_mib_single",
            artifact_sha256=artifact,
            warmup_included=True,
        ),
        make_metric_record(
            metric_name="HOST_ORCHESTRATED_GOODPUT_BPS",
            measurement_class="HOST_ORCHESTRATED",
            direction="F_TO_R",
            committed_application_bytes=1024 * 1024,
            elapsed_ticks=64_000_000,
            timer_frequency=frequency,
            run_id="P10_1_OFFLINE_VECTOR",
            case_id="host_staging",
            artifact_sha256=artifact,
            host_staging_included=True,
            timer_source="HOST_MONOTONIC",
        ),
    ]
    for direction, seconds in (("F_TO_R", 52.0), ("F_TO_R", 50.0), ("R_TO_F", 51.0), ("R_TO_F", 49.0)):
        vectors.append(
            make_metric_record(
                metric_name="APPLICATION_GOODPUT_BPS",
                measurement_class="APPLICATION_SUSTAINED",
                direction=direction,
                committed_application_bytes=32 * 1024 * 1024,
                elapsed_ticks=int(seconds * frequency),
                timer_frequency=frequency,
                run_id="P10_1_OFFLINE_VECTOR",
                case_id=f"sustained_{direction}_{seconds:g}s",
                artifact_sha256=artifact,
                object_count=32,
            )
        )
    result = finalize_metrics(vectors, formal_run_id="P10_1_OFFLINE_VECTOR")
    return [item.to_dict() for item in vectors], result


def write_csv(rows: list[dict[str, Any]]) -> None:
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with CSV_OUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Recompute and compare existing outputs")
    args = parser.parse_args()
    errors: list[str] = []
    before_hashes = {
        rel(path): sha256(path)
        for path in (FINAL, AUDIT, RUN_ROOT / "final/orchestrator_result.json")
    }
    rows = historical_rows()
    minima = {
        direction: min(
            (item for item in rows if item["direction"] == direction),
            key=lambda item: item["reported_legacy_bps"],
        )
        for direction in ("F_TO_R", "R_TO_F")
    }
    for direction, expected in EXPECTED_FINAL.items():
        actual = minima[direction]["reported_legacy_bps"]
        if abs(actual - expected) > 1e-9:
            errors.append(f"{direction} historical minimum {actual} != {expected}")
        if minima[direction]["measurement_class"] != "DIAGNOSTIC_MICROTRANSFER":
            errors.append(f"{direction} historical minimum is not classified diagnostic")
        if minima[direction]["requested_useful_bytes"] != 1:
            errors.append(f"{direction} historical minimum is not a one-byte case")
    stage_i = stage_i_views(rows)
    soak = soak_view()
    vectors, finalizer = finalizer_vectors()
    RAW.mkdir(parents=True, exist_ok=True)
    write_json(VECTOR_OUT, {"schema_version": 2, "records": vectors, "finalizer": finalizer})
    write_csv(rows)
    after_hashes = {
        rel(path): sha256(path)
        for path in (FINAL, AUDIT, RUN_ROOT / "final/orchestrator_result.json")
    }
    if before_hashes != after_hashes:
        errors.append("frozen P10 input changed during recomputation")
    payload = evidence_base(
        "P10_1-HISTORICAL-PERFORMANCE-RECOMPUTE",
        status="PASS" if not errors else "FAIL",
        run_id=RUN_ID,
        frozen_input_sha256=before_hashes,
        frozen_inputs_unchanged=before_hashes == after_hashes,
        historical_row_count=len(rows),
        historical_final_fields={
            direction: {
                "value_bps": minima[direction]["reported_legacy_bps"],
                "stage": minima[direction]["stage"],
                "case_id": minima[direction]["label"],
                "requested_useful_bytes": minima[direction]["requested_useful_bytes"],
                "measurement_class": minima[direction]["measurement_class"],
                "eligible_for_scaling": False,
            }
            for direction in minima
        },
        stage_i=stage_i,
        soak_window=soak,
        raw_csv={"path": rel(CSV_OUT), "sha256": sha256(CSV_OUT)},
        errors=errors,
    )
    body = [
        "## Historical 5.7 kbit/s fields",
        "",
        "| Direction | Value (bit/s) | Provenance | Class | Scaling eligible |",
        "|---|---:|---|---|---|",
    ]
    for direction in ("F_TO_R", "R_TO_F"):
        row = minima[direction]
        body.append(
            f"| {direction} | {row['reported_legacy_bps']:.12f} | "
            f"{row['stage']}/{row['label']} ({row['requested_useful_bytes']} byte) | "
            "DIAGNOSTIC_MICROTRANSFER | false |"
        )
    body.extend(
        [
            "",
            "The legacy arithmetic is exact; the semantic error was heterogeneous global-minimum selection. "
            "No frozen P10 file was edited.",
        ]
    )
    write_pair("p10_1_historical_recompute_summary", "P10.1 historical performance recomputation", payload, body)
    write_pair("p10_1_historical_recompute", "P10.1 historical performance recomputation", payload, body)

    finalizer_payload = evidence_base(
        "P10_1-DETERMINISTIC-GOODPUT-FINALIZER",
        status="PASS" if finalizer["status"] == "PASS" else "FAIL",
        schema_version=2,
        compatibility={
            "frozen_p10_summary_modified": False,
            "frozen_p10_raw_evidence_modified": False,
            "legacy_schema_adapter_requires_explicit_classification": True,
        },
        selection_rule=finalizer["selection_rule"],
        aggregation=finalizer["aggregation"],
        diagnostic_exclusion="PASS",
        missing_metric_behavior="PENDING_MISSING_ELIGIBLE_DIRECTION; never numeric zero",
        vectors={"path": rel(VECTOR_OUT), "sha256": sha256(VECTOR_OUT), "record_count": len(vectors)},
        result=finalizer,
        errors=[] if finalizer["status"] == "PASS" else finalizer["missing_directions"],
    )
    write_pair(
        "p10_1_finalizer_fix_summary",
        "P10.1 deterministic goodput finalizer",
        finalizer_payload,
        [
            "## Selection",
            "",
            "Records are selected by exact run ID, metric name, measurement class, direction, and eligibility. "
            "All selected records are retained and min/median/max are reported per direction.",
        ],
    )
    write_pair(
        "p10_1_finalizer_fix",
        "P10.1 deterministic goodput finalizer",
        finalizer_payload,
    )
    if args.check:
        # All outputs above are deterministic. Re-reading their declared hashes
        # provides a direct integrity check without comparing timestamps.
        for path in (CSV_OUT, VECTOR_OUT):
            if not path.is_file() or not sha256(path):
                errors.append(f"missing deterministic output {rel(path)}")
    print(f"P10_1_HISTORICAL_RECOMPUTE={'PASS' if not errors else 'FAIL'}")
    print("P10_1_HISTORICAL_5P7K_CLASS=DIAGNOSTIC_MICROTRANSFER")
    print(f"P10_1_GOODPUT_FINALIZER_FIX={finalizer['status']}")
    return 0 if not errors and finalizer["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
