from __future__ import annotations

import unittest

from scripts.finalize_p10_1_led_offline import offline_execution_fields


class FinalizeP101LedOfflineTests(unittest.TestCase):
    def test_modern_offline_execution_fields(self) -> None:
        self.assertEqual(
            offline_execution_fields(
                {
                    "hardware_actions_executed": False,
                    "current_run_hardware_authorization": False,
                }
            ),
            (False, False),
        )

    def test_legacy_p8c_offline_execution_fields(self) -> None:
        self.assertEqual(
            offline_execution_fields(
                {
                    "NO_HARDWARE_ACTIONS_EXECUTED": True,
                    "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
                }
            ),
            (False, False),
        )

    def test_missing_execution_markers_fail_closed(self) -> None:
        self.assertEqual(offline_execution_fields({}), (None, None))


if __name__ == "__main__":
    unittest.main()
