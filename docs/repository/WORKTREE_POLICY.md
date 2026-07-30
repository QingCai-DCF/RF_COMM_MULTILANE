# Worktree Policy

## Shared refs and frozen checkpoints

- Linked worktrees share branches, tags, refs, and objects through the common Git directory.
- Annotated stage tags are immutable evidence checkpoints. Do not move, replace, delete, or force-update them.
- A frozen stage worktree is retained for audit/reproduction and is not a place for continued development.
- Long-lived commits belong on an attached, named branch—normally the main worktree—not on detached HEAD.
- A future stage starts only from its separately verified checkpoint or annotated tag and only after its own authorization and scope are established.

## Build and cache isolation

- Each worktree owns its build, simulation, Vivado run, `.Xil`, `xsim.dir`, and temporary cache paths.
- Never share a writable Vivado run directory or `.Xil` directory across worktrees.
- Do not infer tracked state from whether sparse checkout expanded a path. Use `git ls-files`, `git ls-tree`, and `git show <commit>:<path>`.
- Do not globally disable sparse checkout or change another worktree's patterns as part of routine organization.

## Evidence and cleanup

- Never run `git clean` before untracked content is inventoried, hashed, classified, and assigned an explicit disposition.
- Evidence, failed runs, raw logs, authorization records, shutdown records, and artifact manifests are records—not caches—and must not be deleted as cleanup.
- Auxiliary-worktree dirt is reported. It does not authorize modifying, committing in, or deleting that worktree.
- Local-only board/vendor inputs remain outside canonical build inputs and are represented by tracked SHA256 manifests.
- Destructive cleanup, worktree removal, frozen-branch deletion, rebase, or tag movement requires a separate, explicit request and a fresh audit.

## Hardware boundary

Repository and worktree maintenance is offline. It never reuses a historical hardware authorization and must run with `NO_HARDWARE=1` and `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`.
