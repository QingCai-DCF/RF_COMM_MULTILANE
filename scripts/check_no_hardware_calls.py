#!/usr/bin/env python3
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = [
    "open_hw",
    "connect_hw_server",
    "program_hw_devices",
    "xsct",
]
ALLOW_DIRS = {"legacy_safe_tools"}
SKIP_FILES = {"check_no_hardware_calls.py"}

def main():
    errors = []
    for path in (ROOT / "scripts").rglob("*"):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if any(part in ALLOW_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for token in FORBIDDEN:
            if token in text and "--allow-hardware" not in text and "-allowhardware" not in text:
                errors.append(f"{path.relative_to(ROOT)} contains {token} without explicit allow-hardware gate")
    if errors:
        print("NO_HARDWARE_ACTIONS_EXECUTED=0")
        for e in errors:
            print(e)
        return 1
    print("NO_HARDWARE_ACTIONS_EXECUTED=1")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
