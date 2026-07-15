from __future__ import annotations

import re
import tkinter
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTE_TCL = ROOT / "scripts/hw/p7_ps_application_execute.tcl"
R41_LATENCIES = (17_875_676_347, 26_957_722_756, 51_321_168_692, 45_147_234_789)


def _procedure(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^proc {re.escape(name)} \{{[^\n]*\}} \{{\n.*?^\}}$",
        text,
    )
    if match is None:
        raise AssertionError(f"missing Tcl procedure: {name}")
    return match.group(0)


class P7StationaryWideLatencyTests(unittest.TestCase):
    def test_r41_latencies_are_above_xsct_signed_32_bit_limit(self) -> None:
        self.assertTrue(all(value > 0x7FFFFFFF for value in R41_LATENCIES))
        self.assertEqual(
            R41_LATENCIES,
            (
                17_966_539_615 - 90_863_268,
                44_924_346_787 - 17_966_624_031,
                96_245_599_869 - 44_924_431_177,
                141_392_918_989 - 96_245_684_200,
            ),
        )

    def test_production_latency_summary_uses_wide_integer_comparator(self) -> None:
        text = EXECUTE_TCL.read_text(encoding="utf-8", errors="strict")
        latency_proc = _procedure(text, "p7_latency_summary")
        self.assertIn(
            "set sorted [lsort -command p7_compare_wide_integer $values]",
            latency_proc,
        )
        self.assertNotIn("lsort -integer $values", latency_proc)

    def test_production_tcl_sorts_and_summarizes_r41_wide_latencies(self) -> None:
        text = EXECUTE_TCL.read_text(encoding="utf-8", errors="strict")
        interpreter = tkinter.Tcl()
        for name in (
            "p7_percentile",
            "p7_compare_wide_integer",
            "p7_latency_summary",
        ):
            interpreter.eval(_procedure(text, name))

        values = " ".join(str(value) for value in R41_LATENCIES)
        raw_summary = interpreter.call("p7_latency_summary", values)
        fields = interpreter.splitlist(raw_summary)
        summary = {fields[index]: int(fields[index + 1]) for index in range(0, len(fields), 2)}

        ordered = sorted(R41_LATENCIES)
        self.assertEqual(4, summary["count"])
        self.assertEqual(ordered[0], summary["min"])
        self.assertEqual(sum(ordered) // len(ordered), summary["mean"])
        self.assertEqual(ordered[1], summary["p50"])
        self.assertEqual(ordered[-1], summary["p95"])
        self.assertEqual(ordered[-1], summary["p99"])
        self.assertEqual(ordered[-1], summary["max"])


if __name__ == "__main__":
    unittest.main()
