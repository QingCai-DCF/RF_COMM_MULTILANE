#!/usr/bin/env python3
"""Audit linked-worktree topology and optionally write repository-organization evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/generated"
LOCAL_INPUT_ROOTS = (
    Path("hardware_AX7010"),
    Path("hardware_AX7020"),
    Path("legacy/RF_COMM/docs"),
)
EXPECTED_TAGS = {
    "p8a-pass": {
        "object": "fa827fad7fdd781e3cc9ecbe4dfcedcd3c6a88e8",
        "target": "3ed79e02baa2c60af86e752c79ad1d0c44e37fb4",
        "tree": "01c8c881bca6cd48061e4611cf6d16b05a8cb645",
    },
    "p8b-pass": {
        "object": "71adb34ad00da71275e59f256128a3a8147eb76a",
        "target": "80c8433eac1a09a32c9018460f8b76286c4a72a7",
        "tree": "d16b04fefdc1cd969399896338655c2297a9d4e9",
    },
    "p8c-pass": {
        "object": "6b3aebe4552836639f1a72f29311c62c29985129",
        "target": "c44b0d45133bf75c9c71f53dde77f3dc186ad131",
        "tree": "3b785025c35f3000d7918a7b521c58ef0fbe7904",
    },
    "p8d-pass": {
        "object": "74a2e70ee67e81a8a3f1486379268f40cdb8ef96",
        "target": "435ca10b3ec9cb601753870f9220c40c439044e8",
        "tree": "8a11268d2f9581aee9e2d441bfcbf6e27dea2bad",
    },
    "p8e-pass": {
        "object": "a0c32296eea2fdeb333a313bb28fe4efbb60bea2",
        "target": "57ff1079b10a5c0de156b621820774bbb111c5ee",
        "tree": "44932c17cbfba98fcd7d67a04ffea7faf926c7a8",
    },
    "p9-z7010-2lane-pass": {
        "object": "5bc9493071b9ea3446ac27cdd117bc3d3f67bd91",
        "target": "818d335c229d7b92223c279159aab84a5207ef92",
        "tree": "d92ae2b97d30590dca634ac3032e1c6dabb40ca4",
    },
}
EXPECTED_BRANCHES = {"main", "p8/integration", "p9/z7010-stationary-2lane"}
TEXT_EXTENSIONS = {
    ".c", ".cfg", ".csv", ".h", ".htm", ".html", ".ini", ".json", ".log",
    ".md", ".prjpcb", ".prjpcbstructure", ".rst", ".sv", ".svh", ".tcl", ".txt",
    ".v", ".vhd", ".vhdl", ".xdc", ".xml", ".yaml", ".yml",
}
GENERATED_PARTS = {"history", "__previews", "project logs for ir_comm_tfdu6102"}
ABSOLUTE_PATH_RE = re.compile(r"(?i)(?:[a-z]:[\\/]|\\\\[^\\/]+[\\/]|/home/|/users/)")


def git(args: Iterable[str], cwd: Path = ROOT, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.rstrip("\n")


def git_ok(args: Iterable[str], cwd: Path = ROOT) -> bool:
    return subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def blob_oid(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # Git SHA-1 object format in this repository.


def parse_worktrees() -> list[dict[str, Any]]:
    blocks = git(["worktree", "list", "--porcelain"]).split("\n\n")
    worktrees: list[dict[str, Any]] = []
    for block in blocks:
        if not block.strip():
            continue
        item: dict[str, Any] = {"detached": False}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                item["path"] = value
            elif key == "HEAD":
                item["head"] = value
            elif key == "branch":
                item["branch"] = value.removeprefix("refs/heads/")
            elif key == "detached":
                item["detached"] = True
            elif key in {"locked", "prunable"}:
                item[key] = value or True
        path = Path(item["path"])
        item.setdefault("branch", "")
        item["git_dir"] = git(["rev-parse", "--git-dir"], path)
        item["status"] = git(["-c", "core.quotepath=false", "status", "--short", "--branch"], path)
        sparse = git(["sparse-checkout", "list"], path, check=False)
        item["sparse_checkout_patterns"] = sparse.splitlines() if sparse else []
        item["dirty"] = any(
            line and not line.startswith("##") for line in item["status"].splitlines()
        )
        worktrees.append(item)
    return worktrees


def tag_snapshot() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for name in EXPECTED_TAGS:
        result[name] = {
            "type": git(["cat-file", "-t", name], check=False),
            "object": git(["rev-parse", f"{name}^{{tag}}"], check=False),
            "target": git(["rev-parse", f"{name}^{{commit}}"], check=False),
            "tree": git(["rev-parse", f"{name}^{{tree}}"], check=False),
        }
    return result


def check_record(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def warn_record(warnings: list[dict[str, str]], name: str, detail: str) -> None:
    warnings.append({"check": name, "status": "WARN_WITH_REASON", "detail": detail})


def source_absolute_path_hits() -> list[dict[str, Any]]:
    prefixes = ("scripts/", "tools/", "config/", "board_profiles/", "constraints/", "rtl/", "software/", "sim/")
    audit_script = Path(__file__).resolve().relative_to(ROOT.resolve()).as_posix()
    hits: list[dict[str, Any]] = []
    for relative in git(["ls-files"]).splitlines():
        if relative == audit_script or not relative.startswith(prefixes):
            continue
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if ".codex\\worktrees" in line or ".codex/worktrees" in line or "RF_COMM_MULTILANE_P9" in line:
                hits.append({"path": relative, "line": number, "text": line.strip()[:240]})
    return hits


def repository_audit() -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    worktrees = parse_worktrees()
    tags = tag_snapshot()

    check_record(checks, "RUN_FROM_MAIN_WORKTREE", Path(git(["rev-parse", "--show-toplevel"])).resolve() == ROOT.resolve(), str(ROOT))
    current_branch = git(["branch", "--show-current"])
    check_record(checks, "MAIN_BRANCH_ACTIVE", current_branch == "main", current_branch or "DETACHED")
    check_record(checks, "P8_BRANCH_EXISTS", git_ok(["show-ref", "--verify", "refs/heads/p8/integration"]), "p8/integration")
    check_record(checks, "P9_BRANCH_EXISTS", git_ok(["show-ref", "--verify", "refs/heads/p9/z7010-stationary-2lane"]), "p9/z7010-stationary-2lane")
    check_record(checks, "P8_ANCESTOR_P9", git_ok(["merge-base", "--is-ancestor", "p8/integration", "p9/z7010-stationary-2lane"]), "p8/integration -> p9/z7010-stationary-2lane")
    check_record(checks, "P8E_ANCESTOR_P9", git_ok(["merge-base", "--is-ancestor", "p8e-pass", "p9/z7010-stationary-2lane"]), "p8e-pass -> P9")
    check_record(checks, "MAIN_CONTAINS_P9", git_ok(["merge-base", "--is-ancestor", "p9-z7010-2lane-pass", "main"]), "P9 tag -> main")

    for name, expected in EXPECTED_TAGS.items():
        actual = tags[name]
        passed = actual == {"type": "tag", **expected}
        check_record(checks, f"TAG_{name}", passed, json.dumps(actual, sort_keys=True))

    branches = git(["for-each-ref", "--format=%(refname:short)", "refs/heads"]).splitlines()
    p10_branches = [branch for branch in branches if re.search(r"(?i)(^|/)p10($|/|-)", branch)]
    p10_worktrees = [item["path"] for item in worktrees if re.search(r"(?i)(^|[\\/])p10([\\/]|$)", item["path"])]
    check_record(checks, "P10_BRANCH_ABSENT", not p10_branches, ", ".join(p10_branches) or "none")
    check_record(checks, "P10_WORKTREE_ABSENT", not p10_worktrees, ", ".join(p10_worktrees) or "none")

    unexpected = sorted(set(branches) - EXPECTED_BRANCHES)
    if unexpected:
        warn_record(warnings, "UNEXPECTED_LOCAL_BRANCHES", ", ".join(unexpected))
    detached = [item["path"] for item in worktrees if item["detached"]]
    if detached:
        warn_record(warnings, "DETACHED_WORKTREES", ", ".join(detached))
    dirty_aux = [item["path"] for item in worktrees if item["dirty"] and Path(item["path"]).resolve() != ROOT.resolve()]
    if dirty_aux:
        warn_record(warnings, "DIRTY_AUX_WORKTREES", ", ".join(dirty_aux))

    sparse_missing = [item["path"] for item in worktrees if not item["sparse_checkout_patterns"]]
    if sparse_missing:
        warn_record(warnings, "SPARSE_CHECKOUT_DISABLED_OR_EMPTY", ", ".join(sparse_missing))
    else:
        check_record(checks, "SPARSE_CHECKOUT_RECORDED", True, f"{len(worktrees)} worktrees")

    abs_hits = source_absolute_path_hits()
    if abs_hits:
        warn_record(
            warnings,
            "HARD_CODED_WORKTREE_PATHS",
            "; ".join(f"{hit['path']}:{hit['line']}" for hit in abs_hits),
        )
    build_roots = [str((Path(item["path"]) / "build").resolve()).lower() for item in worktrees]
    check_record(checks, "PER_WORKTREE_BUILD_ROOTS_DISTINCT", len(build_roots) == len(set(build_roots)), json.dumps(build_roots))

    untracked_evidence = git(["ls-files", "--others", "--exclude-standard", "--", "evidence"]).splitlines()
    if untracked_evidence:
        warn_record(warnings, "UNTRACKED_EVIDENCE", ", ".join(untracked_evidence[:20]))

    failures = [item for item in checks if item["status"] == "FAIL"]
    return {
        "schema_version": 1,
        "status": "FAIL" if failures else "PASS",
        "test_id": "REPOSITORY-STRUCTURE-AUDIT",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "common_git_dir": str((ROOT / git(["rev-parse", "--git-common-dir"])).resolve()),
        "branch": current_branch,
        "head": git(["rev-parse", "HEAD"]),
        "checks": checks,
        "warnings": warnings,
        "worktrees": worktrees,
        "branches": branches,
        "tags": tags,
        "hard_coded_path_hits": abs_hits,
        "hardware_actions_executed": False,
        "p10_actions_executed": False,
        "errors": [item["detail"] for item in failures],
    }


def tracked_blob_map() -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for line in git(["ls-tree", "-r", "HEAD"]).splitlines():
        match = re.match(r"^[0-7]+ blob ([0-9a-f]+)\t(.+)$", line)
        if match:
            result[match.group(1)].append(match.group(2))
    return result


def local_input_files() -> list[Path]:
    tracked_paths = set(git(["-c", "core.quotepath=false", "ls-files"]).splitlines())
    paths: list[Path] = []
    for relative_root in LOCAL_INPUT_ROOTS:
        root = ROOT / relative_root
        if root.is_dir():
            paths.extend(
                path for path in root.rglob("*")
                if path.is_file() and path.relative_to(ROOT).as_posix() not in tracked_paths
            )
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix().casefold())


def looks_text(path: Path, sample: bytes) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return b"\0" not in sample
    if b"\0" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return bool(sample)


def is_generated_cache(relative: str) -> bool:
    lowered_parts = {part.casefold() for part in Path(relative).parts}
    suffix = Path(relative).suffix.casefold()
    return bool(lowered_parts & GENERATED_PARTS) or suffix in {".log", ".prjpcbstructure", ".htm"}


def classify_local_input(relative: str, duplicate_tracked: list[str], generated: bool) -> tuple[str, str, str, str]:
    if duplicate_tracked:
        return (
            "DUPLICATE_OF_TRACKED_FILE",
            "Byte-identical content is already tracked; retain no second Git copy.",
            "existing tracked repository content",
            "duplicate reference",
        )
    if generated:
        return (
            "GENERATED_CACHE_DO_NOT_TRACK",
            "CAD history/preview/log or derived report; keep only in the local input package.",
            "local CAD tool output",
            "generated cache or history",
        )
    if relative.startswith("hardware_AX7010/TFDU6102电路/"):
        return (
            "AMBIGUOUS_HOLD",
            "Potentially useful CAD source, but ownership, authoritative revision, and redistribution terms are not established.",
            "user-provided or inherited TFDU CAD package; provenance unverified",
            "possible TFDU schematic/PCB source",
        )
    if relative.startswith("legacy/RF_COMM/docs/"):
        return (
            "LOCAL_ONLY_WITH_TRACKED_MANIFEST",
            "Historical vendor training PDF is unique, but redistribution permission is not established.",
            "legacy ALINX training material; redistribution license unverified",
            "historical vendor tutorial",
        )
    board = "AX7020" if relative.startswith("hardware_AX7020/") else "AX7010"
    return (
        "LOCAL_ONLY_WITH_TRACKED_MANIFEST",
        "Vendor board package remains local because binary size and redistribution terms are unsuitable for an automatic Git import.",
        f"{board} vendor/reference package; exact source URL and redistribution license unverified",
        f"{board} schematic/manual/mechanical/datasheet reference",
    )


def audit_local_inputs() -> dict[str, Any]:
    tracked = tracked_blob_map()
    records: list[dict[str, Any]] = []
    by_sha: dict[str, list[str]] = defaultdict(list)
    for path in local_input_files():
        relative = path.relative_to(ROOT).as_posix()
        source_root = next(
            root for root in LOCAL_INPUT_ROOTS if path.is_relative_to(ROOT / root)
        )
        size = path.stat().st_size
        sha = sha256_file(path)
        by_sha[sha].append(relative)
        oid = blob_oid(path)
        duplicates = tracked.get(oid, [])
        with path.open("rb") as handle:
            sample = handle.read(min(size, 1024 * 1024))
        text = looks_text(path, sample)
        decoded = ""
        if text and size <= 2 * 1024 * 1024:
            try:
                decoded = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                decoded = ""
        generated = is_generated_cache(relative)
        disposition, reason, source, use = classify_local_input(relative, duplicates, generated)
        mime, _ = mimetypes.guess_type(path.name)
        records.append({
            "source_path": relative,
            "relative_path": path.relative_to(ROOT / source_root).as_posix(),
            "size_bytes": size,
            "sha256": sha,
            "git_blob_oid": oid,
            "extension": path.suffix.lower(),
            "mime": mime or "application/octet-stream",
            "is_text": text,
            "duplicate_of_tracked_file": bool(duplicates),
            "duplicate_tracked_paths": duplicates,
            "possible_use": use,
            "possible_source": source,
            "contains_absolute_path": bool(decoded and ABSOLUTE_PATH_RE.search(decoded)),
            "contains_generated_cache": generated,
            "contains_binary_or_vendor_material": not text or relative.startswith(("hardware_AX7010/", "hardware_AX7020/", "legacy/RF_COMM/docs/")),
            "redistribution_license": "UNVERIFIED",
            "recommended_disposition": disposition,
            "recommendation_reason": reason,
        })
    for record in records:
        record["duplicate_untracked_paths"] = [
            path for path in by_sha[record["sha256"]] if path != record["source_path"]
        ]
    counts = Counter(record["recommended_disposition"] for record in records)
    roots: dict[str, dict[str, int]] = {}
    for root in LOCAL_INPUT_ROOTS:
        prefix = root.as_posix() + "/"
        subset = [record for record in records if record["source_path"].startswith(prefix)]
        roots[root.as_posix()] = {
            "file_count": len(subset),
            "total_bytes": sum(record["size_bytes"] for record in subset),
        }
    return {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "REPOSITORY-UNTRACKED-CONTENT-AUDIT",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(records),
        "total_bytes": sum(record["size_bytes"] for record in records),
        "classification_counts": dict(sorted(counts.items())),
        "roots": roots,
        "files": records,
        "raw_files_modified": False,
        "raw_files_deleted": False,
        "hardware_actions_executed": False,
    }


def audit_aux_worktrees(worktrees: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for item in worktrees:
        path = Path(item["path"])
        if path.resolve() == ROOT.resolve():
            continue
        untracked = git(["-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard"], path).splitlines()
        for relative in untracked:
            file_path = path / relative
            if not file_path.is_file():
                continue
            if relative == "docs/audit/P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING_AUDIT.md":
                disposition = "KEEP_IN_AUX_WORKTREE_ONLY"
                reason = "Useful derived P8E narrative, but canonical P8E summaries already exist; avoid creating a second acceptance authority."
            elif relative == "docs/design/AX7010_AX7020_HARDWARE_COMPARISON.md":
                disposition = "AMBIGUOUS_HOLD_NO_CONTENT_ANALYSIS"
                reason = "Unexpected unique file outside the snapshot; retained untouched and not analyzed because wiring work is out of scope."
            elif relative == "docs/GIT_BRANCH_AND_WORKTREE_STRUCTURE.md":
                disposition = "HISTORICAL_INPUT_KEEP_IN_AUX_WORKTREE"
                reason = "Read as historical input; the canonical live snapshot is regenerated on main."
            elif relative.startswith("tmp/"):
                disposition = "GENERATED_CACHE_DO_NOT_TRACK"
                reason = "Temporary Codex worktree output."
            else:
                disposition = "AMBIGUOUS_HOLD"
                reason = "Untracked auxiliary-worktree material retained for owner review."
            records.append({
                "worktree": str(path),
                "worktree_head": item["head"],
                "worktree_branch": item["branch"] or None,
                "detached_head": item["detached"],
                "path": relative,
                "size_bytes": file_path.stat().st_size,
                "sha256": sha256_file(file_path),
                "disposition": disposition,
                "reason": reason,
                "modified": False,
            })
    return {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "REPOSITORY-AUX-WORKTREE-UNTRACKED-AUDIT",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_expected_tmp_path": "C:/Users/user/.codex/worktrees/6780/RF_COMM_MULTILANE/tmp",
        "snapshot_tmp_files_found": sum(1 for record in records if record["worktree"].replace("\\", "/").endswith("/6780/RF_COMM_MULTILANE") and record["path"].startswith("tmp/")),
        "actual_snapshot_deviations": [
            "The 6780 worktree has no untracked tmp/ file; it has one untracked docs/design comparison file.",
            "The 7ae5 worktree has an untracked historical Git/worktree structure document.",
        ],
        "files": records,
        "aux_worktrees_modified": False,
        "aux_worktrees_deleted": False,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def md_table_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_intake(audit: dict[str, Any], args: argparse.Namespace) -> None:
    start_tree = git(["rev-parse", f"{args.main_start_commit}^{{tree}}"])
    intake = {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "REPOSITORY-ORGANIZATION-INTAKE",
        "audit_start_utc": args.audit_start_utc,
        "run_location": str(ROOT),
        "common_git_dir": audit["common_git_dir"],
        "no_hardware": os.environ.get("NO_HARDWARE", "1"),
        "current_run_hardware_authorization": os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"),
        "main": {
            "branch": "main",
            "start_commit": args.main_start_commit,
            "start_tree": start_tree,
            "origin_main_at_start": args.origin_main_at_start,
            "fast_forward_target": args.main_fast_forward_target,
            "current_head": git(["rev-parse", "main"]),
            "upstream": git(["rev-parse", "--abbrev-ref", "main@{upstream}"], check=False),
        },
        "initial_main_status": [
            "## main...origin/main [ahead 1]",
            "?? hardware_AX7010/",
            "?? hardware_AX7020/",
            "?? legacy/RF_COMM/docs/",
        ],
        "p8": {"branch": "p8/integration", "head": git(["rev-parse", "p8/integration"])},
        "p9": {"branch": "p9/z7010-stationary-2lane", "head": git(["rev-parse", "p9/z7010-stationary-2lane"])},
        "worktrees": audit["worktrees"],
        "tags": audit["tags"],
        "topology_checks": [item for item in audit["checks"] if item["check"] in {"P8_ANCESTOR_P9", "P8E_ANCESTOR_P9", "MAIN_CONTAINS_P9"}],
        "initial_untracked_p9_exact_path_collisions": 0,
        "hardware_actions_executed": False,
        "p10_actions_executed": False,
    }
    write_json(EVIDENCE / "repo_organization_intake.json", intake)
    lines = [
        "# Repository Organization Intake", "",
        f"- Audit start (UTC): `{args.audit_start_utc}`",
        f"- Run location: `{ROOT}`",
        f"- Common Git dir: `{audit['common_git_dir']}`",
        f"- Main start: `{args.main_start_commit}`",
        f"- Origin/main at start: `{args.origin_main_at_start}`",
        f"- Fast-forward target: `{args.main_fast_forward_target}`",
        f"- Current main: `{git(['rev-parse', 'main'])}`",
        "- Initial untracked/P9 exact-path collisions: `0`",
        "- `NO_HARDWARE=1` and `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`",
        "", "## Worktrees", "",
        "| Path | Branch | HEAD | Detached | Dirty | Sparse patterns |",
        "|---|---|---|---:|---:|---|",
    ]
    for item in audit["worktrees"]:
        lines.append(
            f"| `{md_table_escape(item['path'])}` | `{item['branch'] or 'DETACHED'}` | `{item['head']}` | "
            f"`{str(item['detached']).lower()}` | `{str(item['dirty']).lower()}` | "
            f"`{md_table_escape(', '.join(item['sparse_checkout_patterns']))}` |"
        )
    lines += ["", "This is a non-canonical audit snapshot; branch and worktree state may change after the recorded timestamp.", ""]
    (EVIDENCE / "repo_organization_intake.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_raw_git_outputs(args: argparse.Namespace, audit: dict[str, Any]) -> None:
    worktree_lines = [
        "INITIAL_AUDIT_SNAPSHOT",
        f"MAIN_HEAD={args.main_start_commit}",
        "MAIN_STATUS=## main...origin/main [ahead 1]",
        "MAIN_UNTRACKED=hardware_AX7010/;hardware_AX7020/;legacy/RF_COMM/docs/",
        "INITIAL_UNTRACKED_P9_EXACT_PATH_COLLISIONS=0",
        "",
        "CURRENT_RESCAN",
    ]
    for item in audit["worktrees"]:
        worktree_lines += [
            f"WORKTREE={item['path']}", f"HEAD={item['head']}",
            f"BRANCH={item['branch'] or ''}", f"DETACHED_HEAD={str(item['detached']).lower()}",
            f"GIT_DIR={item['git_dir']}", "STATUS_BEGIN", item["status"], "STATUS_END",
            "SPARSE_CHECKOUT_BEGIN", *item["sparse_checkout_patterns"], "SPARSE_CHECKOUT_END", "",
        ]
    (EVIDENCE / "repo_worktree_status_raw.txt").write_text("\n".join(worktree_lines), encoding="utf-8", newline="\n")

    commands = [
        ["rev-parse", "--show-toplevel"], ["rev-parse", "--git-common-dir"],
        ["worktree", "list", "--porcelain"], ["branch", "-vv", "--all"],
        ["tag", "--list", "--sort=creatordate"],
        ["log", "--graph", "--decorate", "--oneline", "--all", "--date-order", "-n", "200"],
        ["status", "--short", "--branch"], ["sparse-checkout", "list"],
    ]
    branch_lines = ["INITIAL_MAIN_HEAD=" + args.main_start_commit, "CURRENT_RESCAN"]
    for command in commands:
        branch_lines += [f"$ git {' '.join(command)}", git(command, check=False), ""]
    (EVIDENCE / "repo_branch_graph_raw.txt").write_text("\n".join(branch_lines), encoding="utf-8", newline="\n")


def write_local_input_evidence(payload: dict[str, Any]) -> None:
    write_json(EVIDENCE / "repo_untracked_content_audit.json", payload)
    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "REPOSITORY-UNTRACKED-SHA256-MANIFEST",
        "generated_utc": payload["generated_utc"],
        "file_count": payload["file_count"],
        "files": [
            {"path": item["source_path"], "bytes": item["size_bytes"], "sha256": item["sha256"]}
            for item in payload["files"]
        ],
    }
    write_json(EVIDENCE / "repo_untracked_sha256_manifest.json", manifest)
    lines = [
        "# Untracked Content Audit", "",
        f"- Files: `{payload['file_count']}`",
        f"- Bytes: `{payload['total_bytes']}`",
        "- Raw inputs modified/deleted: `false` / `false`",
        "", "## Classification counts", "",
        "| Classification | Files |", "|---|---:|",
    ]
    for key, count in payload["classification_counts"].items():
        lines.append(f"| `{key}` | {count} |")
    lines += ["", "## Per-file disposition", "", "| Path | Bytes | SHA256 | Text | Tracked duplicate | Disposition |", "|---|---:|---|---:|---|---|"]
    for item in payload["files"]:
        duplicate = ", ".join(item["duplicate_tracked_paths"]) or "—"
        lines.append(
            f"| `{md_table_escape(item['source_path'])}` | {item['size_bytes']} | `{item['sha256']}` | "
            f"`{str(item['is_text']).lower()}` | `{md_table_escape(duplicate)}` | `{item['recommended_disposition']}` |"
        )
    lines += ["", "Full MIME, provenance, absolute-path, cache, binary/vendor, duplicate, and rationale fields are in the JSON audit.", ""]
    (EVIDENCE / "repo_untracked_content_audit.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")

    destinations = {
        "hardware_AX7010/": ROOT / "docs/hardware/boards/AX7010/reference/manifest.json",
        "hardware_AX7020/": ROOT / "docs/hardware/boards/AX7020/reference/manifest.json",
        "legacy/RF_COMM/docs/": ROOT / "legacy/RF_COMM/docs/LOCAL_ONLY_MANIFEST.json",
    }
    for prefix, destination in destinations.items():
        subset = [item for item in payload["files"] if item["source_path"].startswith(prefix)]
        board_manifest = {
            "schema_version": 1,
            "status": "LOCAL_ONLY_WITH_TRACKED_MANIFEST",
            "generated_utc": payload["generated_utc"],
            "source_root": prefix.rstrip("/"),
            "raw_files_tracked": False,
            "raw_files_modified": False,
            "redistribution_license": "UNVERIFIED",
            "file_count": len(subset),
            "total_bytes": sum(item["size_bytes"] for item in subset),
            "files": [
                {
                    "path": item["source_path"], "bytes": item["size_bytes"],
                    "sha256": item["sha256"], "disposition": item["recommended_disposition"],
                    "duplicate_tracked_paths": item["duplicate_tracked_paths"],
                }
                for item in subset
            ],
        }
        write_json(destination, board_manifest)


def write_aux_evidence(payload: dict[str, Any]) -> None:
    write_json(EVIDENCE / "repo_aux_worktree_untracked_audit.json", payload)
    lines = [
        "# Auxiliary Worktree Untracked Audit", "",
        "No auxiliary worktree was modified, cleaned, committed, removed, or reconfigured.", "",
        "| Worktree | Path | HEAD/branch | Bytes | SHA256 | Disposition |",
        "|---|---|---|---:|---|---|",
    ]
    for item in payload["files"]:
        lines.append(
            f"| `{md_table_escape(item['worktree'])}` | `{md_table_escape(item['path'])}` | "
            f"`{item['worktree_head']} / {item['worktree_branch'] or 'DETACHED'}` | {item['size_bytes']} | "
            f"`{item['sha256']}` | `{item['disposition']}` |"
        )
    lines += ["", "Snapshot deviations:", ""]
    lines.extend(f"- {item}" for item in payload["actual_snapshot_deviations"])
    lines.append("")
    (EVIDENCE / "repo_aux_worktree_untracked_audit.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument("--audit-start-utc", default="2026-07-30T05:29:00.7749037Z")
    parser.add_argument("--main-start-commit", default="451d79164ea0033f3905b06a905f11b5cab33c00")
    parser.add_argument("--origin-main-at-start", default="5006731277e49d9f2ddaa04a4726949674be5b27")
    parser.add_argument("--main-fast-forward-target", default="818d335c229d7b92223c279159aab84a5207ef92")
    args = parser.parse_args()

    if os.environ.get("NO_HARDWARE", "1") != "1":
        print("ERROR: NO_HARDWARE must be 1", file=sys.stderr)
        return 1
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("ERROR: CURRENT_RUN_HARDWARE_AUTHORIZATION must be false", file=sys.stderr)
        return 1

    audit = repository_audit()
    if args.write_evidence:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        write_intake(audit, args)
        write_raw_git_outputs(args, audit)
        local_inputs = audit_local_inputs()
        write_local_input_evidence(local_inputs)
        aux = audit_aux_worktrees(audit["worktrees"])
        write_aux_evidence(aux)

    if args.json_summary:
        compact = {
            "schema_version": audit["schema_version"],
            "status": audit["status"],
            "test_id": audit["test_id"],
            "generated_utc": audit["generated_utc"],
            "root": audit["root"],
            "common_git_dir": audit["common_git_dir"],
            "branch": audit["branch"],
            "head": audit["head"],
            "checks": audit["checks"],
            "warnings": audit["warnings"],
            "worktree_count": len(audit["worktrees"]),
            "detached_worktree_count": sum(1 for item in audit["worktrees"] if item["detached"]),
            "dirty_aux_worktree_count": sum(
                1 for item in audit["worktrees"]
                if item["dirty"] and Path(item["path"]).resolve() != ROOT.resolve()
            ),
            "hardware_actions_executed": False,
            "p10_actions_executed": False,
            "errors": audit["errors"],
        }
        print(json.dumps(compact, sort_keys=True, ensure_ascii=False))
    else:
        print(f"REPOSITORY_STRUCTURE_AUDIT={audit['status']}")
        for warning in audit["warnings"]:
            print(f"WARN_WITH_REASON: {warning['check']}: {warning['detail']}")
        for error in audit["errors"]:
            print(f"FAIL: {error}")
    return 0 if audit["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
