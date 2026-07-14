import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "software" / "ps_driver" / "p7_app_service.c"


class P7Stage62StartupClearTest(unittest.TestCase):
    def test_startup_clears_and_flushes_complete_diagnostic_record(self):
        source = SOURCE.read_text(encoding="utf-8")
        startup_clear = re.search(
            r"mailbox->failure_snapshot_magic_readback = 0U;(?P<body>.*?)"
            r"memset\(\(void \*\)\(uintptr_t\)P7_INPUT_REFERENCE_BASEADDR",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(startup_clear)
        body = startup_clear.group("body")
        self.assertRegex(
            body,
            r"memset\(\(void \*\)\(uintptr_t\)P7_FAILURE_SNAPSHOT_BASEADDR, 0,\s*"
            r"P7_FIRST_ERROR_DIAGNOSTIC_TOTAL_BYTES\);",
        )
        self.assertRegex(
            body,
            r"p7_flush\(\(const void \*\)\(uintptr_t\)P7_FAILURE_SNAPSHOT_BASEADDR,\s*"
            r"P7_FIRST_ERROR_DIAGNOSTIC_TOTAL_BYTES\);",
        )
        self.assertNotIn("P7_FAILURE_SNAPSHOT_TOTAL_BYTES", body)


if __name__ == "__main__":
    unittest.main()
