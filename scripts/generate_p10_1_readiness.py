#!/usr/bin/env python3
"""Generate the offline P11-readiness package evidence for P10.1."""

from __future__ import annotations

from p10_1_common import ROOT, evidence_base, rel, sha256, write_pair


DOCUMENTS = [
    ROOT / "docs/P11_HARDWARE_PREREQUISITES.md",
    ROOT / "docs/P11_FIXTURE_REQUIREMENTS.md",
    ROOT / "docs/P11_ABZ_INPUT_REQUIREMENTS.md",
    ROOT / "docs/P11_FIVE_MODULE_INVENTORY_PLAN.md",
    ROOT / "docs/plans/P10_2_CROSSTALK_AND_1PLUS1_PLAN.md",
    ROOT / "config/p10_2_crosstalk_matrix.yaml",
]


def main() -> int:
    errors: list[str] = []
    records = []
    for path in DOCUMENTS:
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
        else:
            records.append(
                {
                    "path": rel(path),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    payload = evidence_base(
        "P10_1-P11-READINESS-PACKAGE",
        status="PASS" if not errors else "FAIL",
        p11_official_stage_status="NOT_STARTED",
        p11_hardware_ready=False,
        current_tfdu_module_count=4,
        minimum_required_tfdu_module_count=5,
        documents=records,
        abz_candidate_ppr=[1024, 2048, 4096],
        fixture_definition={
            "fixed_modules": 4,
            "fixed_spacing_degrees": 11.25,
            "rotating_modules": 1,
            "geometry": "canonical nominal D200/D600",
        },
        missing_prerequisites=[
            "one additional compatible TFDU6102 small board",
            "as-built four-fixed-module fixture",
            "as-built one-rotating-module fixture",
            "selected and electrically verified ABZ/phase input",
            "bounded controllable bidirectional motion source",
            "P11-specific wiring/profile/pinmap/XDC",
            "new current-run hardware authorization",
        ],
        hardware_scope_promoted=False,
        errors=errors,
    )
    write_pair(
        "p10_1_p11_readiness",
        "P10.1 P11 prerequisite design-input package",
        payload,
    )
    print(f"P10_1_P11_READINESS_PACKAGE={payload['status']}")
    print("P11_OFFICIAL_STAGE_STATUS=NOT_STARTED")
    print("P11_HARDWARE_READY=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
