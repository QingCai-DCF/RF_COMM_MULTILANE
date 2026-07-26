from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "p9_runner", ROOT / "scripts/run_p9_z7010_stationary_2lane.py"
)
assert SPEC and SPEC.loader
P9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P9)


class P9AuthorizationTests(unittest.TestCase):
    def write_record(self, updates: dict | None = None) -> Path:
        source = json.loads((ROOT / "config/p9_current_run_authorization.json").read_text())
        source.update(updates or {})
        temporary = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(source, temporary)
        temporary.close()
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return Path(temporary.name)

    def validate(self, path: Path, **updates):
        values = {"stage": "P9-04", "max_runtime": 1800, "lane_mask": 1,
                  "require_bound_artifacts": True}
        values.update(updates)
        return P9.validate_authorization(path, **values)

    def test_no_authorization_fails(self):
        result = self.validate(Path("missing-authorization.json"))
        self.assertEqual(result["status"], "FAIL")

    def test_unbound_hardware_authorization_fails(self):
        result = self.validate(ROOT / "config/p9_current_run_authorization.json")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("phase-2" in error for error in result["errors"]))

    def test_lane_mask_0x4_fails(self):
        path = self.write_record({"artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path, lane_mask=4)["status"], "FAIL")

    def test_runtime_above_1800_fails(self):
        path = self.write_record({"artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path, max_runtime=1801)["status"], "FAIL")

    def test_wrong_scope_fails(self):
        path = self.write_record({"scope": "WRONG_SCOPE", "artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
