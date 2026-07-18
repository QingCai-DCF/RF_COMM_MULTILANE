# P8D repository intake — fail closed

- Status: `FAIL`
- First blocker: `WORKTREE_NOT_CLEAN_BEFORE_P8D`
- Decision: `STOP_P8D_IMPLEMENTATION_PENDING_USER_DIRECTION_ON_PREEXISTING_UNTRACKED_FILE`
- Start timestamp (UTC): `2026-07-18T03:29:54.9731990Z`
- Hardware actions executed: `false`

## Baseline

| Field | Observed |
| --- | --- |
| Worktree | `C:/Users/user/.codex/worktrees/3765/RF_COMM_MULTILANE` |
| Worktree selection | Current user-selected P8 worktree override |
| Branch | `p8/integration` |
| HEAD | `c44b0d45133bf75c9c71f53dde77f3dc186ad131` |
| `p8c-pass^{}` | `c44b0d45133bf75c9c71f53dde77f3dc186ad131` |
| P8C source commit | `e8be6ffddd1b59b13b6bf3e0c32c02c6a66b6134` |
| `NO_HARDWARE` | `1` |
| `CURRENT_RUN_HARDWARE_AUTHORIZATION` | `false` |

## Initial worktree differences

The worktree was not clean before any P8D modification:

```text
?? docs/P8C_COMPLETION_SUMMARY.md
```

The pre-existing untracked file is 8,116 bytes with SHA256
`05882864481922927d28660baed7ea4ab4c8545f4ecd0953c34ed52153f6d9d7`.
It has Git blob ID `5b13d14f4d19179f7028858595cca3e176e9f411`. It is absent
from the project branch/tag commit history, while the exact blob is present in
the Codex pre-turn capture
`refs/codex/turn-diffs/captures/1784345487966/2dc630c5-3622-4541-b051-6f19dbca45a6/base`.
This independently confirms that it predates P8D edits in this task. It was
preserved without editing, deleting, moving, staging, or committing it.

## Required intake checks

| Check | Result |
| --- | --- |
| Branch is `p8/integration` | `PASS` |
| `p8c-pass` exists | `PASS` |
| `p8c-pass` resolves to expected checkpoint | `PASS` |
| HEAD is base or known clean descendant | `FAIL` (HEAD matches base, worktree is dirty) |
| Worktree clean before P8D | `FAIL` |
| Project constraints SHA256 matches | `PASS` |
| P8C verify-existing | `FAIL` (`worktree is not clean`) |

The P8C verifier's component commands all returned zero, and it reported
`NO_HARDWARE_ACTIONS_EXECUTED=true`; its aggregate result correctly failed on
the cleanliness requirement.

## Canonical hashes

| Artifact | SHA256 |
| --- | --- |
| `PROJECT_CONSTRAINTS.txt` | `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758` |
| `AGENTS.md` | `6677e4589355aa96dd434f8eb5ab9567c97efcb87ca5b3aae137efbd6776aebb` |
| `config/project_state.json` | `e52f7e46a9f4ada89b083e9c318748a25c694069227f47a6ccf4a00e42eab175` |
| `config/project_requirements.yaml` | `d7c19fe0a67fa6807a456d132e8a538bc0f7800ceb7e5ba16fc2445bd13dfd95` |
| `config/tfdu_safety.yaml` | `e9069e49c1fd835ac7d1aee7e75b8e5b5cb13533fd703ddddf2ac3d8da61fb06` |
| `config/register_map/ir_axi_regs.yaml` | `9993ae99c883a921f61bf1af8f1aca54b8a89fa7cd53452f435a6ed992c7fd2d` |
| `evidence/generated/p8c_final_summary.json` | `161d89e30eb6bcc607cbb1732fcccd739519e5d92e014e3530199d8b92dc819e` |
| `evidence/generated/p8c_final_summary.md` | `41f104ffda9512dd844872c211b9ee3dd7826bf9422d0c37d87192f620921b88` |

## Tool inventory

| Tool | Version/status |
| --- | --- |
| Python | `3.14.3` |
| Git | `2.54.0.windows.1` |
| Vivado | `NOT_FOUND` |
| XSIM | `NOT_FOUND` |
| GCC | `NOT_FOUND` |
| ARM cross GCC | `NOT_FOUND` |

## Fail-closed disposition

P8D implementation did not start. The goal requires a clean worktree before
P8D and explicitly prohibits silently absorbing unknown differences. User
direction is required for the pre-existing untracked completion summary before
the baseline can be rechecked.
