from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/bind_p10_jtag_roles.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bind_p10_jtag_roles", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P10BindJtagRolesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.inventory = {
            "inventory_id": "P10_DUAL_AX7020_JTAG_IDENTITY",
            "status": "ENUMERATED_UNASSIGNED",
            "role_binding_method": "JTAG_CABLE_SERIAL",
            "observed_cable_serials": ["SERIAL_A", "SERIAL_B"],
            "fixed_board_serial": "PENDING_EXPLICIT_SERIAL_TO_ROLE_BINDING",
            "rotating_board_serial": "PENDING_EXPLICIT_SERIAL_TO_ROLE_BINDING",
            "target_order_used_for_role_binding": False,
        }

    def test_explicit_fixed_serial_binds_other_serial_as_rotating(self) -> None:
        result = self.module.bind_inventory(self.inventory, "SERIAL_B")
        self.assertEqual("BOUND_EXPLICIT_SERIAL_TO_ROLE", result["status"])
        self.assertEqual("SERIAL_B", result["fixed_board_serial"])
        self.assertEqual("SERIAL_A", result["rotating_board_serial"])
        self.assertFalse(result["target_order_used_for_role_binding"])
        self.assertEqual("USER_EXPLICIT_FIXED_JTAG_SERIAL", result["role_binding_source"])
        self.assertEqual("USER_SELECTED_FIXED_SERIAL", result["role_binding_selection_rule"])

    def test_user_authorized_arbitrary_binding_records_agent_selection_basis(self) -> None:
        result = self.module.bind_inventory(
            self.inventory,
            "SERIAL_A",
            role_binding_source=self.module.ARBITRARY_SOURCE,
            selection_rule="LEXICOGRAPHICALLY_SMALLEST_OBSERVED_SERIAL_AS_FIXED",
        )
        self.assertEqual("SERIAL_A", result["fixed_board_serial"])
        self.assertEqual("SERIAL_B", result["rotating_board_serial"])
        self.assertEqual(self.module.ARBITRARY_SOURCE, result["role_binding_source"])
        self.assertEqual(
            "LEXICOGRAPHICALLY_SMALLEST_OBSERVED_SERIAL_AS_FIXED",
            result["role_binding_selection_rule"],
        )

    def test_unobserved_serial_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not in the observed inventory"):
            self.module.bind_inventory(self.inventory, "SERIAL_C")

    def test_duplicate_inventory_is_rejected(self) -> None:
        self.inventory["observed_cable_serials"] = ["SERIAL_A", "SERIAL_A"]
        with self.assertRaisesRegex(ValueError, "exactly two distinct"):
            self.module.bind_inventory(self.inventory, "SERIAL_A")


if __name__ == "__main__":
    unittest.main()
