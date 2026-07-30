# Untracked Content Disposition

The organization audit covers every file that was present under `hardware_AX7010/`, `hardware_AX7020/`, and `legacy/RF_COMM/docs/` at intake. Per-file size, SHA256, MIME/type assessment, duplicate results, provenance assessment, and disposition are in:

- `evidence/generated/repo_untracked_content_audit.json`
- `evidence/generated/repo_untracked_sha256_manifest.json`

## Decisions

| Input | Decision |
|---|---|
| AX7010 vendor schematic, PCB, mechanical, datasheet, and manual package | `LOCAL_ONLY_WITH_TRACKED_MANIFEST`; large binary/vendor material and redistribution terms are not suitable for automatic import. |
| AX7010 TFDU CAD package | Primary CAD sources are `AMBIGUOUS_HOLD`; generated history, previews, logs, and derived reports are `GENERATED_CACHE_DO_NOT_TRACK`. Nothing is promoted to canonical hardware design. |
| AX7010 TFDU6102 datasheet duplicate | `DUPLICATE_OF_TRACKED_FILE`; canonical tracked copy is `docs/datasheets/TFDU6102datasheet.pdf`. |
| AX7020 vendor reference package | `LOCAL_ONLY_WITH_TRACKED_MANIFEST`; reference inventory only, with no project pinmap/XDC/role output created. |
| Legacy ALINX training PDF | `LOCAL_ONLY_WITH_TRACKED_MANIFEST`; historical relevance is recorded, but redistribution permission is unverified. |
| P8 auxiliary derived audit | Kept only in its frozen auxiliary worktree because canonical P8E summaries already exist. |
| Detached-worktree design comparison | `AMBIGUOUS_HOLD_NO_CONTENT_ANALYSIS`; retained untouched and not imported. |
| Detached-worktree Git snapshot | Read as historical input, retained untouched, and replaced by a live mainline snapshot. |

Raw local inputs were neither deleted nor overwritten. Exact ignore rules make the main worktree clean without hiding canonical board profiles, XDC, project state, requirements, evidence, artifacts, manifests, failure logs, or current hardware design documents.
