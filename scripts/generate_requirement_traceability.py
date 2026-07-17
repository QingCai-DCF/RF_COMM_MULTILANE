#!/usr/bin/env python3
from __future__ import annotations

import argparse

from p8a_common import (
    REQUIREMENTS_PATH,
    ROOT,
    TRACEABILITY_PATH,
    load_yaml,
    render_traceability,
    validate_requirements,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the requirement traceability matrix")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    document = load_yaml(REQUIREMENTS_PATH)
    errors = validate_requirements(document, ROOT)
    expected = render_traceability(document)
    if args.write and not errors:
        TRACEABILITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRACEABILITY_PATH.write_text(expected, encoding="utf-8", newline="\n")
    if args.check:
        if not TRACEABILITY_PATH.is_file() or TRACEABILITY_PATH.read_bytes() != expected.encode("utf-8"):
            errors.append("requirement traceability matrix is stale")

    for error in errors:
        print(f"ERROR: {error}")
    print(f"REQUIREMENT_TRACEABILITY_GENERATION={'PASS' if not errors else 'FAIL'}")
    print(f"REQUIREMENT_TRACEABILITY_PATH={TRACEABILITY_PATH.relative_to(ROOT).as_posix()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
