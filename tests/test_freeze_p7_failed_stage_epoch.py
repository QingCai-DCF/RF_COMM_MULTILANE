from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import freeze_p7_failed_stage_epoch as subject


class FreezeP7FailedStageEpochTests(unittest.TestCase):
    def _write_manifest(
        self,
        root: Path,
        bundle_name: str,
        *,
        source: str,
        plan_path: Path,
        plan_sha: str,
    ) -> Path:
        path = (
            root
            / "build/p7_authorized_sequence"
            / bundle_name
            / "p7_authorized_sequence_generation_manifest.json"
        )
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "schema": "rf-comm-p7-authorized-sequence-generator-v1",
                    "source_commit": source,
                    "sequence_plan": {"path": str(plan_path), "sha256": plan_sha},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_resolves_unique_manifest_by_executed_plan_not_bare_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_id = "p7_example_r13_diag_suffix55"
            old_plan = root / ".hardware_authorization/old.txt"
            live_plan = root / ".hardware_authorization/live.txt"
            old_plan.parent.mkdir(parents=True)
            old_plan.write_text("old", encoding="utf-8")
            live_plan.write_text("live", encoding="utf-8")
            self._write_manifest(
                root,
                run_id,
                source="1" * 40,
                plan_path=old_plan,
                plan_sha="a" * 64,
            )
            expected = self._write_manifest(
                root,
                f"{run_id}_replacement",
                source="2" * 40,
                plan_path=live_plan,
                plan_sha="b" * 64,
            )
            observed = subject.resolve_generation_manifest(
                root,
                run_id,
                source_commit="2" * 40,
                sequence_plan_path=live_plan,
                sequence_plan_sha256="b" * 64,
            )
            self.assertEqual(expected.resolve(), observed)

    def test_rejects_ambiguous_or_missing_plan_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_id = "p7_example_r13_diag_suffix55"
            plan = root / ".hardware_authorization/live.txt"
            plan.parent.mkdir(parents=True)
            plan.write_text("live", encoding="utf-8")
            kwargs = {
                "source_commit": "2" * 40,
                "sequence_plan_path": plan,
                "sequence_plan_sha256": "b" * 64,
            }
            with self.assertRaisesRegex(ValueError, "observed 0 matches"):
                subject.resolve_generation_manifest(root, run_id, **kwargs)
            for suffix in ("one", "two"):
                self._write_manifest(
                    root,
                    f"{run_id}_{suffix}",
                    source="2" * 40,
                    plan_path=plan,
                    plan_sha="b" * 64,
                )
            with self.assertRaisesRegex(ValueError, "observed 2 matches"):
                subject.resolve_generation_manifest(root, run_id, **kwargs)


if __name__ == "__main__":
    unittest.main()
