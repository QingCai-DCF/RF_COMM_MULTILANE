#!/usr/bin/env python3
from p1_lib import ensure_static_artifacts, generate_manifests


if __name__ == "__main__":
    ensure_static_artifacts()
    result = generate_manifests()
    print(f"RESULT: {result['result']}")
    print(f"REASON: {result['reason']}")
    print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    raise SystemExit(0 if result["result"] == "PASS" else 1)
