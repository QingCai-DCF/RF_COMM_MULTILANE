# Project constraints

`项目约束(目标）.txt` in the workspace root is a hard project constraint.

All work in this project must follow it. Before changing RTL, Vivado block design files, XDC constraints, PS software, host software, tests, or documentation, check that the change supports or at least does not conflict with the goals in that file.

Do not modify `项目约束(目标）.txt` unless the user explicitly asks for a constraint change and confirms the exact change. If a task appears to require changing the project constraints, ask the user first.

# Hardware shutdown safety

Any task that programs hardware, starts a PS ELF, drives TFDU pins, runs Vivado/XSCT hardware probes, or otherwise leaves the infrared transmitter/receiver outputs active must program the TFDU shutdown image after each hardware run. Use the existing safe wrapper shutdown path when available; otherwise run `tools\program_tfdu_shutdown.tcl` explicitly before further analysis or any next hardware attempt.

Do not treat a hardware run as complete until the logs show `SHUTDOWN_EXIT=0` or an explicit `TFDU_SHUTDOWN_PROGRAMMED` equivalent. If programming, capture, or the wrapper fails after hardware may have been driven, attempt shutdown immediately and report the shutdown result. Dry runs, build-only runs, and JTAG/UART preflight checks that do not program or drive the TFDU hardware do not require shutdown.

# Safe Git automation

Codex may help manage Git for this project when the user asks for Git automation, commit, push, or end-to-end task handling. Use a conservative workflow:

- Before editing or committing, run `git status -sb` and inspect the relevant diff.
- Treat existing uncommitted changes as user-owned unless Codex made them in the current task. Do not overwrite, revert, restage, or reformat unrelated changes.
- Stage only files that are directly related to the current user request. Prefer explicit paths over `git add .`.
- Before committing source, script, or documentation changes, run the smallest relevant checks or tests available for the touched area. If tests cannot be run, state that clearly.
- Use clear commit messages that describe the actual change, for example `feat: add N03 network-first acceptance modes` or `docs: add safe git automation policy`.
- Push only after a successful commit and only to the configured project remote/branch unless the user asks otherwise.

Codex must not run destructive or history-rewriting Git commands unless the user explicitly asks for that exact operation and confirms the risk. This includes:

- `git reset --hard`
- `git checkout -- .`
- `git restore` for user-owned changes
- `git clean`
- `git push --force` or `git push --force-with-lease`
- interactive rebases or history rewrites

When synchronizing with GitHub, prefer `git fetch` first. Use `git pull --rebase` only when the working tree is clean or when the user explicitly approves handling local changes. If the branch is behind and the working tree is dirty, stop and report the situation instead of trying to auto-merge.
