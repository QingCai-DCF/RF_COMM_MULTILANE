#!/usr/bin/env python3
"""Read-only verification of the immutable P9 acceptance checkpoint.

This entry point never connects to hardware and never regenerates evidence.  It
verifies the annotated checkpoint, hashes the files named by the frozen P9
manifests directly from the tag, and checks the post-checkpoint closeout state
carried by main.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TAG = "p9-z7010-2lane-pass"
P9_BRANCH = "p9/z7010-stationary-2lane"
RUN_ID = "p9_20260729T134551Z_6d88b7854219_ac75bfe61bfc"
TAG_OBJECT = "5bc9493071b9ea3446ac27cdd117bc3d3f67bd91"
TAG_TARGET = "818d335c229d7b92223c279159aab84a5207ef92"
TAG_TREE = "d92ae2b97d30590dca634ac3032e1c6dabb40ca4"
P8E_TARGET = "57ff1079b10a5c0de156b621820774bbb111c5ee"
SOURCE_COMMIT = "6d88b7854219c8b514ef36109a456ffbda4972d8"

RUN_MANIFEST = (
    f"evidence/hardware/p9/{RUN_ID}/final/run_evidence_sha256_manifest.json"
)
AUTHORIZATION_RECORD = (
    f"evidence/hardware/p9/{RUN_ID}/authorization/authorization_record.json"
)
FINAL_SHUTDOWN = (
    f"evidence/hardware/p9/{RUN_ID}/shutdown/p9_26_final/shutdown_summary.json"
)

FROZEN_FILES = {
    "evidence/generated/p9_final_summary.json":
        "c57ca47169f9d53178ed3dde9d8ddc0bb334b5cd79f05b43f8777fb98596bcef",
    "evidence/generated/p9_evidence_consistency_summary.json":
        "6d0ac181bb47cafdc7906319784f46275407030a52144ab9a48dc16994eacfd6",
    "evidence/generated/p9_artifact_freeze_summary.json":
        "ed030b098778bc9a5b8300cdeaecf6415e82d138a50b5955fcd4e2d0625b6bf6",
    RUN_MANIFEST:
        "39c23a34ac553167691e323ee48f39c3e813f05dd93dfc6e6fa33a4a2fac70ea",
    AUTHORIZATION_RECORD:
        "1b9e166c596bf68cda218089d5dd8abd47486290790ea78aa00bc3883e6135fe",
    FINAL_SHUTDOWN:
        "7fe6ccdf626b78b0fad2eda8975e819d02fc96910c61b13bf3633c18e27ef2b2",
}


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_value(*args: str) -> str:
    return git(*args).stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class TaggedBlobReader:
    """Read blobs from one Git object through a single cat-file process."""

    def __init__(self, revision: str) -> None:
        self.revision = revision
        self.process = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.observed: dict[str, dict[str, Any]] = {}

    def close(self) -> None:
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        self.process.wait(timeout=30)
        if self.process.returncode:
            detail = b""
            if self.process.stderr:
                detail = self.process.stderr.read()
            raise RuntimeError(
                "git cat-file failed: " + detail.decode("utf-8", errors="replace")
            )

    def read(self, path: str, *, capture: bool = False) -> tuple[dict[str, Any], bytes | None]:
        cached = self.observed.get(path)
        if cached is not None and not capture:
            return cached, None
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("git cat-file pipes are unavailable")

        spec = f"{self.revision}:{path}".encode("utf-8")
        self.process.stdin.write(spec + b"\n")
        self.process.stdin.flush()
        header = self.process.stdout.readline().rstrip(b"\n")
        if not header or header.endswith(b" missing"):
            raise FileNotFoundError(f"{self.revision}:{path}")
        fields = header.rsplit(b" ", 2)
        if len(fields) != 3 or fields[1] != b"blob":
            raise RuntimeError(
                f"unexpected cat-file response for {path}: "
                + header.decode("utf-8", errors="replace")
            )
        size = int(fields[2])
        remaining = size
        digest = hashlib.sha256()
        captured = bytearray() if capture else None
        while remaining:
            block = self.process.stdout.read(min(1024 * 1024, remaining))
            if not block:
                raise EOFError(f"short blob read for {path}")
            digest.update(block)
            if captured is not None:
                captured.extend(block)
            remaining -= len(block)
        if self.process.stdout.read(1) != b"\n":
            raise RuntimeError(f"missing cat-file separator for {path}")
        record = {
            "bytes": size,
            "git_object": fields[0].decode("ascii"),
            "sha256": digest.hexdigest(),
        }
        self.observed[path] = record
        return record, bytes(captured) if captured is not None else None


def json_bytes(data: bytes, path: str) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def add_expected(
    expected: dict[str, dict[str, Any]],
    errors: list[str],
    path: str,
    sha256: str,
    size: int | None,
    source: str,
) -> None:
    path = path.replace("\\", "/")
    new = {"sha256": str(sha256).lower(), "bytes": size, "source": source}
    prior = expected.get(path)
    if prior is None:
        expected[path] = new
        return
    if prior["sha256"] != new["sha256"]:
        errors.append(
            f"conflicting SHA256 for {path}: {prior['source']} vs {source}"
        )
    if prior["bytes"] is not None and size is not None and prior["bytes"] != size:
        errors.append(f"conflicting byte count for {path}: {prior['source']} vs {source}")
    if prior["bytes"] is None and size is not None:
        prior["bytes"] = size


def require_equal(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, observed {actual!r}")


def verify_json_status(
    errors: list[str],
    label: str,
    data: dict[str, Any],
    *,
    require_source_commit: bool = True,
) -> None:
    require_equal(errors, f"{label}.status", data.get("status"), "PASS")
    require_equal(errors, f"{label}.run_id", data.get("run_id"), RUN_ID)
    if require_source_commit:
        require_equal(errors, f"{label}.source_commit", data.get("source_commit"), SOURCE_COMMIT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify immutable P9 evidence from the annotated tag without hardware"
    )
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    require_equal(errors, "NO_HARDWARE", os.environ.get("NO_HARDWARE"), "1")
    require_equal(
        errors,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION",
        os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "").lower(),
        "false",
    )

    topology: dict[str, Any] = {}
    try:
        topology = {
            "tag_type": git_value("cat-file", "-t", TAG),
            "tag_object": git_value("rev-parse", f"refs/tags/{TAG}"),
            "tag_target": git_value("rev-list", "-n", "1", TAG),
            "tag_tree": git_value("rev-parse", f"{TAG}^{{tree}}"),
            "p9_branch": git_value("rev-parse", P9_BRANCH),
            "main": git_value("rev-parse", "main"),
        }
        require_equal(errors, "P9 tag type", topology["tag_type"], "tag")
        require_equal(errors, "P9 tag object", topology["tag_object"], TAG_OBJECT)
        require_equal(errors, "P9 tag target", topology["tag_target"], TAG_TARGET)
        require_equal(errors, "P9 tag tree", topology["tag_tree"], TAG_TREE)
        require_equal(errors, "P9 branch", topology["p9_branch"], TAG_TARGET)
        if git("merge-base", "--is-ancestor", SOURCE_COMMIT, TAG_TARGET, check=False).returncode:
            errors.append("P9 source commit is not an ancestor of the P9 checkpoint")
        if git("merge-base", "--is-ancestor", P8E_TARGET, TAG_TARGET, check=False).returncode:
            errors.append("P8E checkpoint is not an ancestor of the P9 checkpoint")
        if git("merge-base", "--is-ancestor", TAG_TARGET, "main", check=False).returncode:
            errors.append("main does not contain the P9 checkpoint")
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"Git topology check failed: {exc}")

    expected: dict[str, dict[str, Any]] = {}
    for path, digest in FROZEN_FILES.items():
        add_expected(expected, errors, path, digest, None, "immutable baseline")

    reader: TaggedBlobReader | None = None
    checked_bytes = 0
    parsed: dict[str, dict[str, Any]] = {}
    try:
        reader = TaggedBlobReader(TAG)

        seed_paths = [
            "evidence/generated/p9_final_summary.json",
            "evidence/generated/p9_evidence_consistency_summary.json",
            "evidence/generated/p9_artifact_freeze_summary.json",
            RUN_MANIFEST,
            AUTHORIZATION_RECORD,
            FINAL_SHUTDOWN,
        ]
        for path in seed_paths:
            observed, content = reader.read(path, capture=True)
            baseline = expected[path]
            if observed["sha256"] != baseline["sha256"]:
                errors.append(f"frozen SHA256 mismatch: {path}")
            if content is None:
                raise RuntimeError(f"capture failed for {path}")
            parsed[path] = json_bytes(content, path)

        final = parsed["evidence/generated/p9_final_summary.json"]
        consistency = parsed["evidence/generated/p9_evidence_consistency_summary.json"]
        freeze = parsed["evidence/generated/p9_artifact_freeze_summary.json"]
        run_manifest = parsed[RUN_MANIFEST]
        authorization = parsed[AUTHORIZATION_RECORD]
        shutdown = parsed[FINAL_SHUTDOWN]

        for label, document in (
            ("final", final),
            ("consistency", consistency),
            ("artifact freeze", freeze),
            ("authorization", authorization),
        ):
            verify_json_status(errors, label, document)
        verify_json_status(
            errors,
            "run manifest",
            run_manifest,
            require_source_commit=False,
        )

        require_equal(errors, "final.test_id", final.get("test_id"), "P9-FINAL")
        require_equal(errors, "final.P9_STATUS", final.get("P9_STATUS"), "PASS")
        require_equal(errors, "consistency.test_id", consistency.get("test_id"), "P9-EVID-001")
        require_equal(errors, "consistency.shutdown_after", consistency.get("shutdown_after"), "PASS")
        require_equal(errors, "consistency.shutdown_before", consistency.get("shutdown_before"), "PASS")
        require_equal(errors, "artifact freeze.test_id", freeze.get("test_id"), "P9-02-IMMUTABLE-ARTIFACT-FREEZE")
        require_equal(errors, "run manifest.test_id", run_manifest.get("test_id"), "P9-EVID-001-MANIFEST")
        require_equal(errors, "authorization.test_id", authorization.get("test_id"), "P9-HW-003")
        require_equal(errors, "shutdown.status", shutdown.get("status"), "PASS")
        markers = shutdown.get("markers", {})
        require_equal(errors, "shutdown.SHUTDOWN_EXIT", markers.get("SHUTDOWN_EXIT"), "0")
        require_equal(
            errors,
            "shutdown.TFDU_SHUTDOWN_PROGRAMMED",
            markers.get("TFDU_SHUTDOWN_PROGRAMMED"),
            "1",
        )
        require_equal(errors, "shutdown.ENDPOINT_ARMED", markers.get("P9_SHUTDOWN_ENDPOINT_ARMED"), "0")
        require_equal(errors, "shutdown.ACTIVE_TX_MASK", markers.get("P9_SHUTDOWN_ACTIVE_TX_MASK"), "0")

        manifest_files = run_manifest.get("files", [])
        manifest_generated = run_manifest.get("generated_summaries", [])
        require_equal(errors, "run manifest.file_count", run_manifest.get("file_count"), len(manifest_files))
        require_equal(
            errors,
            "run manifest.generated_summary_count",
            run_manifest.get("generated_summary_count"),
            len(manifest_generated),
        )
        for group_name, rows in (
            ("run manifest files", manifest_files),
            ("run manifest generated summaries", manifest_generated),
            ("run manifest canonical state", run_manifest.get("canonical_state_files", [])),
        ):
            if not isinstance(rows, list):
                errors.append(f"{group_name} is not a list")
                continue
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or not all(k in row for k in ("path", "sha256", "bytes")):
                    errors.append(f"invalid {group_name} record {index}")
                    continue
                add_expected(
                    expected,
                    errors,
                    str(row["path"]),
                    str(row["sha256"]),
                    int(row["bytes"]),
                    f"{group_name}[{index}]",
                )

        artifact_record = freeze.get("artifact_manifest", {})
        artifact_path = str(artifact_record.get("path", ""))
        if not artifact_path:
            errors.append("artifact freeze does not name an artifact manifest")
        else:
            add_expected(
                expected,
                errors,
                artifact_path,
                str(artifact_record.get("sha256", "")),
                int(artifact_record["bytes"]) if "bytes" in artifact_record else None,
                "artifact freeze",
            )
            observed, content = reader.read(artifact_path, capture=True)
            if observed["sha256"] != str(artifact_record.get("sha256", "")).lower():
                errors.append(f"artifact manifest SHA256 mismatch: {artifact_path}")
            if content is None:
                raise RuntimeError("artifact manifest capture failed")
            artifact_manifest = json_bytes(content, artifact_path)
            verify_json_status(errors, "artifact manifest", artifact_manifest)
            require_equal(errors, "artifact manifest.test_id", artifact_manifest.get("test_id"), "P9-02-IMMUTABLE-ARTIFACT-FREEZE")
            for group_name in ("artifacts", "reports"):
                rows = artifact_manifest.get(group_name, [])
                if not isinstance(rows, list):
                    errors.append(f"artifact manifest {group_name} is not a list")
                    continue
                for index, row in enumerate(rows):
                    if not isinstance(row, dict) or not all(k in row for k in ("path", "sha256", "bytes")):
                        errors.append(f"invalid artifact manifest {group_name} record {index}")
                        continue
                    add_expected(
                        expected,
                        errors,
                        str(row["path"]),
                        str(row["sha256"]),
                        int(row["bytes"]),
                        f"artifact manifest {group_name}[{index}]",
                    )
            source_manifest = artifact_manifest.get("source_manifest", {})
            if isinstance(source_manifest, dict) and all(
                key in source_manifest for key in ("path", "sha256", "bytes")
            ):
                add_expected(
                    expected,
                    errors,
                    str(source_manifest["path"]),
                    str(source_manifest["sha256"]),
                    int(source_manifest["bytes"]),
                    "artifact source manifest",
                )
            else:
                errors.append("artifact source manifest record is invalid")

        for path, baseline in sorted(expected.items()):
            observed, _ = reader.read(path)
            if observed["sha256"] != baseline["sha256"]:
                errors.append(
                    f"SHA256 mismatch for {path}: expected {baseline['sha256']}, "
                    f"observed {observed['sha256']}"
                )
            if baseline["bytes"] is not None and observed["bytes"] != baseline["bytes"]:
                errors.append(
                    f"byte count mismatch for {path}: expected {baseline['bytes']}, "
                    f"observed {observed['bytes']}"
                )
        checked_bytes = sum(int(row["bytes"]) for row in reader.observed.values())
    except (OSError, ValueError, RuntimeError, EOFError, json.JSONDecodeError) as exc:
        errors.append(f"frozen evidence verification failed: {exc}")
    finally:
        if reader is not None:
            try:
                reader.close()
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                errors.append(f"tagged blob reader close failed: {exc}")

    closeout_checks = 0
    try:
        state_path = ROOT / "config/project_state.json"
        closeout_path = ROOT / "evidence/generated/p9_post_checkpoint_closeout.json"
        checkpoint_path = ROOT / "evidence/generated/p9_git_checkpoint_metadata.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        closeout = json.loads(closeout_path.read_text(encoding="utf-8"))
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checks = {
            "state.p9_status": (state.get("p9_status"), "PASS"),
            "state.current_z7010_platform_status": (
                state.get("current_z7010_platform_status"),
                "PLATFORM_LIMITED_PASS",
            ),
            "state.current_run_hardware_authorization": (
                state.get("current_run_hardware_authorization"),
                False,
            ),
            "state.last_hardware_authorization_consumed": (
                state.get("last_hardware_authorization_consumed"),
                True,
            ),
            "state.z7020_target_status": (
                state.get("z7020_target_status"),
                "PENDING_Z7020_HW",
            ),
            "state.rotation_status": (
                state.get("rotation_status"),
                "PENDING_FINAL_MECHANICAL",
            ),
            "state.final_product_status": (
                state.get("final_product_status"),
                "PENDING_HW",
            ),
            "state.AB_L1 legacy": (
                state.get("ab_l1_status", {}).get("legacy_status"),
                "BAD_DIR",
            ),
            "state.AB_L1 current P9": (
                state.get("ab_l1_status", {}).get("current_p9_stationary_status"),
                "PASS",
            ),
            "state.external duty": (
                state.get("architecture_status", {}).get("external_tfdu_duty_measurement"),
                "PENDING_EXTERNAL_MEASUREMENT",
            ),
            "state.physical GLOBAL_PERMIT": (
                state.get("architecture_status", {}).get("global_permit_physical_implementation"),
                "PENDING_D17",
            ),
            "closeout.status": (closeout.get("status"), "PASS"),
            "closeout.hardware_actions_executed": (
                closeout.get("hardware_actions_executed"),
                False,
            ),
            "checkpoint.status": (checkpoint.get("status"), "PASS"),
            "checkpoint.hardware_actions_executed": (
                checkpoint.get("hardware_actions_executed"),
                False,
            ),
            "checkpoint.p10_actions_executed": (
                checkpoint.get("p10_actions_executed"),
                False,
            ),
        }
        for label, (actual, wanted) in checks.items():
            require_equal(errors, label, actual, wanted)
        allowed_program_stages = {
            "P9_COMPLETE_P10_NOT_STARTED",
            "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET",
            "P10_POST_ACCEPTANCE_ANALYSIS",
            "P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE",
            "P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE",
            "P10_1_PERFORMANCE_REMEDIATION",
            "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION",
            "P11_PREREQUISITE_ACQUISITION",
            "P11_SINGLE_LOGICAL_LANE_FOUR_FIXED_MODULE_HANDOVER",
        }
        if state.get("current_program_stage") not in allowed_program_stages:
            errors.append(
                "state.current_program_stage: expected a P9-or-later compatible stage, "
                f"observed {state.get('current_program_stage')!r}"
            )
        closeout_checks = len(checks)
        require_equal(
            errors,
            "state closeout SHA256",
            state.get("p9_post_checkpoint_closeout", {}).get("evidence_sha256"),
            sha256_file(closeout_path),
        )
        require_equal(
            errors,
            "state checkpoint metadata SHA256",
            state.get("p9_post_checkpoint_closeout", {}).get("git_metadata_sha256"),
            sha256_file(checkpoint_path),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"post-checkpoint closeout verification failed: {exc}")

    summary = {
        "status": "PASS" if not errors else "FAIL",
        "test_id": "P9-VERIFY-EXISTING",
        "mode": "READ_ONLY_TAGGED_EVIDENCE",
        "tag": TAG,
        "tag_object": topology.get("tag_object"),
        "tag_target": topology.get("tag_target"),
        "tag_tree": topology.get("tag_tree"),
        "run_id": RUN_ID,
        "verified_unique_file_count": len(reader.observed) if reader else 0,
        "verified_bytes": checked_bytes,
        "closeout_check_count": closeout_checks,
        "hardware_actions_executed": False,
        "errors": errors,
    }
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"P9_VERIFY_EXISTING: {summary['status']}")
        print(f"TAG_TARGET: {summary['tag_target']}")
        print(f"VERIFIED_UNIQUE_FILE_COUNT: {summary['verified_unique_file_count']}")
        print(f"VERIFIED_BYTES: {summary['verified_bytes']}")
        for error in errors:
            print(f"FAIL: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
