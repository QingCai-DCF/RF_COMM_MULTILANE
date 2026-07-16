from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_offline_gates_subject", ROOT / "scripts/run_offline_gates.py"
)
assert SPEC is not None and SPEC.loader is not None
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)


class OfflineGateEntrypointTests(unittest.TestCase):
    def test_help_exits_before_any_gate_subprocess_or_output(self) -> None:
        stdout = io.StringIO()
        with mock.patch.object(subject.subprocess, "run") as subprocess_run:
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as raised:
                    subject.main(["--help"])
        self.assertEqual(0, raised.exception.code)
        self.assertIn("canonical no-hardware", stdout.getvalue())
        subprocess_run.assert_not_called()

    def test_unknown_argument_fails_before_any_gate_subprocess(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(subject.subprocess, "run") as subprocess_run:
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    subject.main(["--not-a-real-option"])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("unrecognized arguments", stderr.getvalue())
        subprocess_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
