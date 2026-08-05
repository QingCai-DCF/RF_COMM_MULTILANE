#!/usr/bin/env python3
"""Generate the deterministic P10.4 four-lane performance taxonomy."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from model_p10_1r import PerformanceInputs, performance_model


ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "evidence/generated/p10_4_model_reconciliation_offline.json"
MD_OUT = ROOT / "evidence/generated/p10_4_model_reconciliation_offline.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        raise SystemExit("P10_4_MODEL_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED")

    frozen_existing = None
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if args.check:
        if not JSON_OUT.is_file():
            return 1
        frozen_existing = json.loads(JSON_OUT.read_text(encoding="utf-8"))
        frozen_source = frozen_existing.get("source_commit")
        if not isinstance(frozen_source, str) or re.fullmatch(
            r"[0-9a-f]{40}", frozen_source
        ) is None:
            return 1
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", frozen_source, "HEAD"],
            cwd=ROOT,
            check=False,
        ).returncode != 0:
            return 1
        # A frozen model remains bound to the commit that produced it.  A
        # descendant host-runner/evidence change must not rewrite that
        # provenance merely to perform a semantic --check.
        source_commit = frozen_source

    inputs = PerformanceInputs(lane_count=4)
    physical = performance_model(inputs)
    # The runtime application counter measures committed command-object bytes,
    # which occupy the full 247-byte L1 payload.  It is not the narrower
    # 215-byte RFAP-useful projection.  Keeping the two taxonomies distinct
    # prevents an artificial ceiling below the immutable P10.3 measurement.
    application_object_ceiling = (
        physical["airtime_ceiling_bps"]
        * inputs.dma_ps_overlap_efficiency
        * (1.0 - inputs.packet_error_rate)
    )
    common = {
        "payload_bytes_per_data_frame": inputs.l1_payload_bytes,
        "rfap_useful_bytes_per_data_frame": inputs.rfap_useful_bytes,
        "data_frame_airtime_us": physical["data_frame_airtime_us"],
        "ack_frame_airtime_us": physical["ack_airtime_us"],
        "exact_duty_target_fraction": inputs.exact_target_duty,
        "ack_sack": "one cumulative 32-bit SACK ACK per 32-frame burst",
        "direction_quiet_us_each_boundary": inputs.direction_quiet_us,
        "retry_assumption_packet_error_rate": inputs.packet_error_rate,
    }
    ceilings = {
        "PHY_RAW_BPS": {
            **common,
            "ceiling_bps": inputs.lane_rate_bps * inputs.lane_count,
            "payload_bytes": 0,
            "meaning": "configured 4PPM raw bit capability before framing, duty, ACK, or retry",
        },
        "FRAME_GOODPUT_BPS": {
            **common,
            "ceiling_bps": physical["airtime_ceiling_bps"],
            "payload_bytes": inputs.l1_payload_bytes,
            "meaning": "deduplicated accepted L1 payload bits over the modeled bundle cycle",
        },
        "RFAP_USEFUL_BPS": {
            **common,
            "ceiling_bps": physical["application_ceiling_bps"],
            "payload_bytes": inputs.rfap_useful_bytes,
            "meaning": "useful RFAP bytes before retry and DMA/PS overlap efficiency",
        },
        "APPLICATION_GOODPUT_BPS": {
            **common,
            "ceiling_bps": application_object_ceiling,
            "payload_bytes": inputs.l1_payload_bytes,
            "meaning": "integrity-verified remotely committed command-object bytes",
        },
        "HOST_ORCHESTRATED_BPS": {
            **common,
            "ceiling_bps": application_object_ceiling,
            "payload_bytes": inputs.l1_payload_bytes,
            "meaning": "physical upper bound only; host connect/load/dump overhead can only reduce it",
            "acceptance_metric": False,
        },
    }
    status = "PASS" if (
        physical["duty_schedule_proof"]["pass"]
        and physical["boundary_ack_settle_proof"]["pass"]
        and ceilings["APPLICATION_GOODPUT_BPS"]["ceiling_bps"] >= 8_000_000
    ) else "FAIL"
    payload = {
        "schema_version": 1,
        "test_id": "P10_4-MODEL-001-OFFLINE",
        "status": status,
        "scope": "P10_4_OFFLINE_MODEL_NOT_HARDWARE_EVIDENCE",
        "source_commit": source_commit,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "ceilings": ceilings,
        "physical_model": physical,
        "mandatory_retention_8mbps_feasible": (
            ceilings["APPLICATION_GOODPUT_BPS"]["ceiling_bps"] >= 8_000_000
        ),
        "margin_9mbps_feasible_in_current_32_frame_model": (
            ceilings["APPLICATION_GOODPUT_BPS"]["ceiling_bps"] >= 9_000_000
        ),
        "stretch_9p6mbps_feasible_in_current_32_frame_model": (
            ceilings["APPLICATION_GOODPUT_BPS"]["ceiling_bps"] >= 9_600_000
        ),
        "measured_reconciliation": "PENDING_CURRENT_ARTIFACT_HARDWARE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if args.check:
        assert frozen_existing is not None
        existing = frozen_existing
        existing.pop("generated_at_utc", None)
        payload.pop("generated_at_utc", None)
        return 0 if existing == payload else 1
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(rendered, encoding="utf-8", newline="\n")
    rows = [
        "# P10.4 offline performance model",
        "",
        f"- Status: `{status}`",
        "- Hardware actions executed: `false`",
        "- Measured reconciliation: `PENDING_CURRENT_ARTIFACT_HARDWARE`",
        "",
        "| Metric | Ceiling (bit/s) | Payload bytes | Meaning |",
        "|---|---:|---:|---|",
    ]
    for name, item in ceilings.items():
        rows.append(
            f"| `{name}` | {item['ceiling_bps']:.3f} | {item['payload_bytes']} | {item['meaning']} |"
        )
    rows.extend([
        "",
        "The 8 Mbit/s retention target is model-feasible. The 9.0 and 9.6 Mbit/s targets are nonblocking and are not made feasible by weakening duty, guard, ACK/SACK, retry, or integrity assumptions.",
    ])
    MD_OUT.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_4_MODEL={status}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
