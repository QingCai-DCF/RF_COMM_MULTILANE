#!/usr/bin/env python3
from __future__ import annotations

import argparse

from p8a_common import ROOT, STATE_PATH, STATUS_PATH, load_json, render_project_status, validate_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify PROJECT_STATUS.md from project_state.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    state = load_json(STATE_PATH)
    errors = validate_state(state, ROOT)
    expected = render_project_status(state)
    if args.write and not errors:
        STATUS_PATH.write_text(expected, encoding="utf-8", newline="\n")
    if args.check:
        if not STATUS_PATH.is_file() or STATUS_PATH.read_bytes() != expected.encode("utf-8"):
            errors.append("PROJECT_STATUS.md is stale or not generated from config/project_state.json")

    for error in errors:
        print(f"ERROR: {error}")
    print(f"PROJECT_STATUS_GENERATION={'PASS' if not errors else 'FAIL'}")
    print(f"PROJECT_STATUS_PATH={STATUS_PATH.relative_to(ROOT).as_posix()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
