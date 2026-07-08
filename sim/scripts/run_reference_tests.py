#!/usr/bin/env python3
import argparse
import importlib.util
import json
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = ROOT / "sim/tests/test_tfdu6102_reference.py"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dependency-free TFDU6102 reference tests.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    module = load_module(TEST_PATH)
    results = []
    for name in sorted(dir(module)):
        if not name.startswith("test_"):
            continue
        func = getattr(module, name)
        if not callable(func):
            continue
        try:
            func()
        except Exception as exc:
            results.append({"name": name, "result": "FAIL", "reason": str(exc), "traceback": traceback.format_exc()})
        else:
            results.append({"name": name, "result": "PASS", "reason": "ok"})

    status = "PASS" if all(item["result"] == "PASS" for item in results) else "FAIL"
    payload = {
        "status": status,
        "tests": results,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"TFDU6102_REFERENCE_MODEL: {status}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
        for item in results:
            print(f"{item['name']}: {item['result']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
