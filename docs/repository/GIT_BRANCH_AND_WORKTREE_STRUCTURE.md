# Git Branch and Worktree Structure

Snapshot timestamp: `2026-07-30T05:41:01Z`.

This file is a non-canonical operational snapshot. Branch heads, worktree dirt, and detached worktrees can change after the timestamp. Re-run `python scripts/audit_repository_structure.py --json-summary` for current state; do not use this document instead of live Git inspection.

## Shared repository

```text
main worktree:  C:\Users\user\Documents\RF_COMM_MULTILANE
common Git dir: C:\Users\user\Documents\RF_COMM_MULTILANE\.git
origin/main:    5006731277e49d9f2ddaa04a4726949674be5b27
```

All registered worktrees share refs and objects through the common Git directory. A branch or tag change is therefore visible to every worktree.

## Verified linear history

```text
origin/main 50067312
  └─ main start 451d7916
      └─ P8A–P8E / p8/integration / p8e-pass 57ff1079
          └─ P9 / p9/z7010-stationary-2lane / p9-z7010-2lane-pass 818d335c
              └─ main P9 post-checkpoint closeout 189d530b
```

The P9 branch contains P8A–P8E, so P8 was not separately merged. `main` was fast-forwarded from `451d7916...` to the verified P9 checkpoint `818d335c...` before the post-checkpoint closeout commit.

All stage tags are annotated and immutable:

| Tag | Target |
|---|---|
| `p8a-pass` | `3ed79e02baa2c60af86e752c79ad1d0c44e37fb4` |
| `p8b-pass` | `80c8433eac1a09a32c9018460f8b76286c4a72a7` |
| `p8c-pass` | `c44b0d45133bf75c9c71f53dde77f3dc186ad131` |
| `p8d-pass` | `435ca10b3ec9cb601753870f9220c40c439044e8` |
| `p8e-pass` | `57ff1079b10a5c0de156b621820774bbb111c5ee` |
| `p9-z7010-2lane-pass` | `818d335c229d7b92223c279159aab84a5207ef92` |

## Registered worktrees at snapshot

| Path | Branch/HEAD | Role | Snapshot state |
|---|---|---|---|
| `C:\Users\user\Documents\RF_COMM_MULTILANE` | `main` at `189d530b...` | Only long-lived mainline commit worktree | Organization changes in progress |
| `C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE` | `p8/integration` at `57ff1079...` | Frozen P8 checkpoint | Dirty only from untracked derived audit document |
| `C:\Users\user\.codex\worktrees\6780\RF_COMM_MULTILANE` | detached at `451d7916...` | Temporary Codex worktree | Dirty from one untracked design comparison document; retained untouched |
| `C:\Users\user\.codex\worktrees\7ae5\RF_COMM_MULTILANE` | detached at `57ff1079...` | Temporary/historical Codex worktree | Dirty from the earlier worktree snapshot document; retained untouched |
| `C:\Users\user\Documents\RF_COMM_MULTILANE_P9` | `p9/z7010-stationary-2lane` at `818d335c...` | Frozen P9 evidence worktree | Clean |

The local branch `codex/tech-grill` remains at `451d7916...`, has no registered worktree, and is reported as a warning rather than silently deleted.

Every registered worktree retains its existing sparse-checkout policy. The raw pattern lists are preserved in `evidence/generated/repo_worktree_status_raw.txt`; this organization task did not change any sparse-checkout pattern.

No P10 branch or worktree existed at the snapshot, and none is created by this organization task.
