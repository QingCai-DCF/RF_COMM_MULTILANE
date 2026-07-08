#!/usr/bin/env python3
import json

from p1_lib import ACTIVE_XDC, parse_xdc


if __name__ == "__main__":
    data = parse_xdc(ACTIVE_XDC)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    raise SystemExit(0 if data else 1)
