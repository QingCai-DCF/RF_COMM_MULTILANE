#!/usr/bin/env python3
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CN = ROOT / "项目约束(目标）.txt"
ASCII = ROOT / "PROJECT_CONSTRAINTS.txt"

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def require(cond, msg, errors):
    print(f"{msg}={'1' if cond else '0'}")
    if not cond:
        errors.append(msg)

def main():
    errors = []
    require(ROOT.name != "RF_COMM", "CURRENT_DIR_IS_NOT_LEGACY_RF_COMM", errors)
    require(CN.exists(), "PROJECT_CONSTRAINTS_CN_EXISTS", errors)
    require(ASCII.exists() and CN.exists() and sha(CN) == sha(ASCII), "PROJECT_CONSTRAINTS_HASH_MATCH", errors)
    ag = ROOT / "AGENTS.md"
    require(ag.exists() and "SHUTDOWN_EXIT=0" in ag.read_text(encoding="utf-8", errors="ignore"), "AGENTS_MD_CREATED", errors)
    require((ROOT / "legacy/RF_COMM/import_manifest.json").exists(), "IMPORT_MANIFEST_EXISTS", errors)
    require((ROOT / "evidence/imported/evidence/final/current_usable_configuration.md").exists(), "LEGACY_EVIDENCE_IMPORTED", errors)
    require((ROOT / "board_profiles/ACTIVE_PROFILE.json").exists(), "ACTIVE_PROFILE_EXISTS", errors)
    require((ROOT / "constraints/active/PORT1.generated.xdc").exists(), "CANONICAL_XDC_EXISTS", errors)
    require((ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv").exists(), "PINMAP_EXISTS", errors)
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
