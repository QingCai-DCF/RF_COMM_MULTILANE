#!/usr/bin/env python3
"""Bind the two enumerated P10 AX7020 JTAG serials to fixed/rotating roles.

This is an offline inventory update.  It never connects to JTAG and never uses
target enumeration order as a role signal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "config/hardware/p10_jtag_identity_inventory.json"


EXPLICIT_SOURCE = "USER_EXPLICIT_FIXED_JTAG_SERIAL"
ARBITRARY_SOURCE = "USER_AUTHORIZED_AGENT_SELECTED_STABLE_JTAG_SERIAL_BINDING"


def bind_inventory(
    inventory: dict[str, Any],
    fixed_serial: str,
    *,
    role_binding_source: str = EXPLICIT_SOURCE,
    selection_rule: str = "USER_SELECTED_FIXED_SERIAL",
) -> dict[str, Any]:
    if inventory.get("inventory_id") != "P10_DUAL_AX7020_JTAG_IDENTITY":
        raise ValueError("unexpected P10 JTAG inventory id")
    if inventory.get("role_binding_method") != "JTAG_CABLE_SERIAL":
        raise ValueError("role binding method must be JTAG_CABLE_SERIAL")
    serials = inventory.get("observed_cable_serials")
    if not isinstance(serials, list) or len(serials) != 2 or len(set(serials)) != 2:
        raise ValueError("inventory must contain exactly two distinct observed cable serials")
    if fixed_serial not in serials:
        raise ValueError(f"fixed serial {fixed_serial!r} is not in the observed inventory")
    rotating_serial = next(serial for serial in serials if serial != fixed_serial)
    result = dict(inventory)
    result.update({
        "status": "BOUND_EXPLICIT_SERIAL_TO_ROLE",
        "fixed_board_serial": fixed_serial,
        "rotating_board_serial": rotating_serial,
        "target_order_used_for_role_binding": False,
        "role_binding_source": role_binding_source,
        "role_binding_selection_rule": selection_rule,
        "role_binding_recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--fixed-serial")
    choice.add_argument(
        "--arbitrary-stable",
        action="store_true",
        help="Use the lexicographically smallest observed cable serial as AX7020-F.",
    )
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1":
        print("P10_ROLE_BIND_ERROR: NO_HARDWARE=1 is required", file=sys.stderr)
        return 2
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print(
            "P10_ROLE_BIND_ERROR: CURRENT_RUN_HARDWARE_AUTHORIZATION=false is required for the offline binding step",
            file=sys.stderr,
        )
        return 2
    path = args.inventory.resolve()
    if not path.is_file():
        print(f"P10_ROLE_BIND_ERROR: missing inventory: {path}", file=sys.stderr)
        return 1
    try:
        inventory = json.loads(path.read_text(encoding="utf-8"))
        if args.arbitrary_stable:
            observed = inventory.get("observed_cable_serials")
            if not isinstance(observed, list) or len(observed) != 2 or len(set(observed)) != 2:
                raise ValueError("inventory must contain exactly two distinct observed cable serials")
            fixed_serial = sorted(observed)[0]
            source = ARBITRARY_SOURCE
            selection_rule = "LEXICOGRAPHICALLY_SMALLEST_OBSERVED_SERIAL_AS_FIXED"
        else:
            fixed_serial = args.fixed_serial
            source = EXPLICIT_SOURCE
            selection_rule = "USER_SELECTED_FIXED_SERIAL"
        bound = bind_inventory(
            inventory,
            fixed_serial,
            role_binding_source=source,
            selection_rule=selection_rule,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"P10_ROLE_BIND_ERROR: {exc}", file=sys.stderr)
        return 1
    if not args.dry_run:
        path.write_text(json.dumps(bound, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": bound["status"],
        "fixed_board_serial": bound["fixed_board_serial"],
        "rotating_board_serial": bound["rotating_board_serial"],
        "role_binding_source": bound["role_binding_source"],
        "role_binding_selection_rule": bound["role_binding_selection_rule"],
        "target_order_used_for_role_binding": False,
        "dry_run": args.dry_run,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
