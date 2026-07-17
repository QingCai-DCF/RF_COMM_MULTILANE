#!/usr/bin/env python3
"""Materialize immutable P8B checkpoint evidence away from mutable gate paths."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TAG = "p8b-pass"
EXPECTED_TAG_TARGET = "80c8433eac1a09a32c9018460f8b76286c4a72a7"
SNAPSHOTS = {
    "evidence/generated/p8b_acceptance_core.json": (
        "evidence/generated/p8b_checkpoint_acceptance_core.json",
        "33ef5c0eaea36ae79ca7753374966af4caed6af022adc512955b6619c5ec6870",
    ),
    "evidence/generated/offline_gate_summary.json": (
        "evidence/generated/p8b_checkpoint_offline_gate_summary.json",
        "669fb52ee5c5506bca06a77e39fc9700c42fb600f165eb1a1ee4ab413ab78470",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_output(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    tag_target = git_output("rev-parse", f"{TAG}^{{}}").decode("ascii").strip()
    if tag_target != EXPECTED_TAG_TARGET:
        raise RuntimeError(f"{TAG} target mismatch: {tag_target}")

    for source, (destination, expected_hash) in SNAPSHOTS.items():
        blob = git_output("show", f"{TAG}:{source}")
        actual_hash = sha256_bytes(blob)
        if actual_hash != expected_hash:
            raise RuntimeError(f"{TAG}:{source} hash mismatch: {actual_hash}")
        destination_path = ROOT / destination
        if args.verify:
            if not destination_path.is_file():
                raise RuntimeError(f"missing immutable checkpoint evidence: {destination}")
            destination_hash = hashlib.sha256(destination_path.read_bytes()).hexdigest()
            if destination_hash != expected_hash:
                raise RuntimeError(f"immutable checkpoint evidence mismatch: {destination}")
        else:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(blob)
        print(f"P8B_CHECKPOINT_EVIDENCE={destination} SHA256={expected_hash}")

    print(f"P8B_CHECKPOINT_TAG_TARGET={tag_target}")
    print("P8B_CHECKPOINT_EVIDENCE_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
