#!/usr/bin/env python3
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "docs/legacy/项目约束(目标）.txt"
CANONICAL = ROOT / "PROJECT_CONSTRAINTS.txt"
CHANGELOG = ROOT / "PROJECT_CONSTRAINTS_CHANGELOG.md"
AGENTS = ROOT / "AGENTS.md"

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

def changelog_metadata(path):
    metadata = {}
    if not path.exists():
        return metadata
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition(":")
        if separator and key and key == key.upper():
            metadata[key] = value.strip()
    return metadata

def main():
    errors = []
    require(ROOT.name != "RF_COMM", "CURRENT_DIR_IS_NOT_LEGACY_RF_COMM", errors)
    require(LEGACY.exists(), "LEGACY_PROJECT_CONSTRAINT_EXISTS", errors)
    require(CANONICAL.exists(), "CANONICAL_PROJECT_CONSTRAINT_EXISTS", errors)
    canonical_text = CANONICAL.read_text(encoding="utf-8", errors="ignore") if CANONICAL.exists() else ""
    require(
        "CANONICAL_PROJECT_CONSTRAINT: PROJECT_CONSTRAINTS.txt" in canonical_text,
        "CANONICAL_PROJECT_CONSTRAINT_DECLARED",
        errors,
    )
    require(
        "LEGACY_PROJECT_CONSTRAINT_STATUS: SUPERSEDED" in canonical_text,
        "LEGACY_PROJECT_CONSTRAINT_SUPERSEDED",
        errors,
    )
    require(CHANGELOG.exists(), "PROJECT_CONSTRAINTS_CHANGELOG_EXISTS", errors)
    metadata = changelog_metadata(CHANGELOG)
    legacy_hash = sha(LEGACY) if LEGACY.exists() else ""
    require(
        metadata.get("PREVIOUS_REPOSITORY_PROJECT_CONSTRAINT_SHA256", "").lower() == legacy_hash,
        "PREVIOUS_PROJECT_CONSTRAINT_HASH_RECORDED",
        errors,
    )
    require(
        metadata.get("LEGACY_PROJECT_CONSTRAINT_SHA256", "").lower() == legacy_hash,
        "LEGACY_PROJECT_CONSTRAINT_HASH_RECORDED",
        errors,
    )
    require(
        CANONICAL.exists()
        and metadata.get("NEW_PROJECT_CONSTRAINT_SHA256", "").lower() == sha(CANONICAL),
        "CANONICAL_PROJECT_CONSTRAINT_HASH_RECORDED",
        errors,
    )
    require(
        AGENTS.exists() and metadata.get("NEW_AGENTS_SHA256", "").lower() == sha(AGENTS),
        "AGENTS_HASH_RECORDED",
        errors,
    )
    require(AGENTS.exists() and "SHUTDOWN_EXIT=0" in AGENTS.read_text(encoding="utf-8", errors="ignore"), "AGENTS_MD_CREATED", errors)
    require((ROOT / "legacy/RF_COMM/import_manifest.json").exists(), "IMPORT_MANIFEST_EXISTS", errors)
    require((ROOT / "evidence/imported/evidence/final/current_usable_configuration.md").exists(), "LEGACY_EVIDENCE_IMPORTED", errors)
    require((ROOT / "board_profiles/ACTIVE_PROFILE.json").exists(), "ACTIVE_PROFILE_EXISTS", errors)
    require((ROOT / "constraints/active/PORT1.generated.xdc").exists(), "CANONICAL_XDC_EXISTS", errors)
    require((ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv").exists(), "PINMAP_EXISTS", errors)
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
