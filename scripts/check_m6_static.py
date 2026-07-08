#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


def main() -> int:
    errors: list[str] = []
    scripts = {
        "RUN_LANE0_RAW_MATRIX": ROOT / "scripts/hw/run_lane0_raw_matrix_safe.ps1",
        "RUN_G1_LANE0_REPLAY": ROOT / "scripts/hw/run_g1_lane0_replay_safe.ps1",
        "PROGRAM_TFDU_SHUTDOWN": ROOT / "scripts/hw/program_tfdu_shutdown_safe.ps1",
    }

    for marker, path in scripts.items():
        require(path.exists(), f"M6_{marker}_SCRIPT_EXISTS", errors)
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        require("AllowHardware" in text, f"M6_{marker}_REQUIRES_ALLOW_HARDWARE_PARAM", errors)
        require("REFUSED_NO_ALLOW_HARDWARE" in text, f"M6_{marker}_DEFAULT_REFUSAL_MARKER", errors)
        require("NO_HARDWARE_ACTIONS_EXECUTED=1" in text, f"M6_{marker}_REFUSAL_NO_HW_MARKER", errors)
        require("PROFILE_SHA256" in text, f"M6_{marker}_PRINTS_PROFILE_HASH", errors)
        require("hash_manifest.json" in text and "hash_manifest.csv" in text, f"M6_{marker}_WRITES_HASH_MANIFEST", errors)
        require("TFDU_SHUTDOWN_PROGRAMMED" in text or "SHUTDOWN_EXIT=0" in text, f"M6_{marker}_CHECKS_SHUTDOWN_MARKERS", errors)

    raw_text = scripts["RUN_LANE0_RAW_MATRIX"].read_text(encoding="utf-8", errors="ignore")
    g1_text = scripts["RUN_G1_LANE0_REPLAY"].read_text(encoding="utf-8", errors="ignore")
    shutdown_text = scripts["PROGRAM_TFDU_SHUTDOWN"].read_text(encoding="utf-8", errors="ignore")

    require("program_tfdu_shutdown_safe.ps1" in raw_text and "finally" in raw_text, "M6_RAW_MATRIX_FORCES_SHUTDOWN_AFTER_RUN", errors)
    require("program_tfdu_shutdown_safe.ps1" in g1_text and "finally" in g1_text, "M6_G1_REPLAY_FORCES_SHUTDOWN_AFTER_RUN", errors)
    require("program_tfdu_shutdown.tcl" in shutdown_text, "M6_SHUTDOWN_WRAPPER_CALLS_SHUTDOWN_TCL", errors)
    require("legacy/RF_COMM/tools/run_2lane_matrix_safe.ps1" in raw_text, "M6_RAW_MATRIX_USES_SAFE_REFERENCE_WRAPPER", errors)
    require("legacy/RF_COMM/tools/run_g1_lane0_hw_smoke_safe.ps1" in g1_text, "M6_G1_REPLAY_USES_SAFE_REFERENCE_WRAPPER", errors)
    require("config/profiles/G1_LANE0_BASELINE.json" in raw_text and "config/profiles/G1_LANE0_BASELINE.json" in g1_text, "M6_WRAPPERS_DEFAULT_G1_PROFILE", errors)

    print(f"M6_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
