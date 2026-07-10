#!/usr/bin/env python3
"""Internal handshake launcher for Windows Job Object containment.

The parent wrapper starts this process first, assigns it to a kill-on-close
Job Object, and only then sends ``P7_GO`` on stdin.  The fixed argv payload is
JSON encoded with URL-safe base64 and is always launched with ``shell=False``.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys


def decode_command(value: str) -> list[str]:
    padding = "=" * ((4 - len(value) % 4) % 4)
    raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    command = json.loads(raw.decode("utf-8"))
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(item, str) or not item or "\x00" in item for item in command)
    ):
        raise ValueError("contained command must be a nonempty string argv vector")
    return command


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 126
    try:
        command = decode_command(argv[1])
        if sys.stdin.buffer.readline(16).replace(b"\r\n", b"\n") != b"P7_GO\n":
            return 125
        child = subprocess.Popen(command, shell=False)
        return int(child.wait())
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
