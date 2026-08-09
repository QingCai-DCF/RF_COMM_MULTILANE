from __future__ import annotations

import re
import unittest
from pathlib import Path

from config.generated import p10_5_dual_direction as cfg


ROOT = Path(__file__).resolve().parents[1]


class P10_5FirmwareContractTests(unittest.TestCase):
    def test_generated_autonomous_runtime_contract(self) -> None:
        self.assertEqual(cfg.AUTONOMOUS_DUAL_STREAM_COMMAND, 15)
        self.assertEqual(cfg.MAX_STREAM_BYTES, 0x70000000)
        self.assertEqual(cfg.INTERNAL_OBJECT_BYTES, 262_144)
        self.assertEqual(cfg.DESCRIPTOR_BYTES, 65_536)
        self.assertEqual(cfg.RUNTIME_RING_DEPTH, 32)
        self.assertEqual(cfg.RUNTIME_BUFFER_COUNT, 4)
        self.assertEqual(cfg.RUNTIME_DESCRIPTOR_BATCH, 8)

    def test_command_is_append_only_and_dispatched(self) -> None:
        protocol = (ROOT / "software/ps_driver/p9_runtime_protocol.h").read_text(
            encoding="utf-8"
        )
        runtime = (ROOT / "software/ps_driver/p9_runtime_main.c").read_text(
            encoding="utf-8"
        )
        match = re.search(
            r"P9_COMMAND_P10_5_AUTONOMOUS_DUAL_STREAM\s*=\s*(\d+)",
            protocol,
        )
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), cfg.AUTONOMOUS_DUAL_STREAM_COMMAND)
        self.assertIn(
            "case P9_COMMAND_P10_5_AUTONOMOUS_DUAL_STREAM:", runtime
        )
        self.assertIn("return p10_1_command_autonomous_stream(m);", runtime)

    def test_dual_stream_owns_both_dma_directions(self) -> None:
        extension = (
            ROOT / "software/ps_driver/p10_1_runtime_extension.inc"
        ).read_text(encoding="utf-8")
        prepare = extension[
            extension.index("static int p10_1_prepare_slot(") :
            extension.index("static int p10_1_validate_stream_args(")
        ]
        self.assertIn("if (local_tx != 0U)", prepare)
        self.assertIn("if (local_rx != 0U)", prepare)
        self.assertIn("p10_1_submit_chain(\n        1U", prepare)
        self.assertIn("p10_1_submit_chain(\n        0U", prepare)
        self.assertIn("p10_5_program_dual_object_context", extension)
        self.assertIn("p10_5_commit_role_masks", extension)

    def test_result_tail_is_append_only_and_bounded(self) -> None:
        header = (
            ROOT / "software/ps_driver/p10_1_runtime_protocol.h"
        ).read_text(encoding="utf-8")
        self.assertIn("p10_5_dual_direction_mode) == 176U * 4U", header)
        self.assertIn("p10_5_application_committed_bytes) == 203U * 4U", header)
        self.assertIn(
            "p10_5_prefetched_objects_reclaimed) == 207U * 4U", header
        )
        self.assertIn("sizeof(p10_1_runtime_result_t) <= 2048U", header)

    def test_duration_mode_stops_at_object_boundary_and_reclaims_prefetch(self) -> None:
        extension = (
            ROOT / "software/ps_driver/p10_1_runtime_extension.inc"
        ).read_text(encoding="utf-8")
        self.assertIn("if (duration_stop != 0U)\n      break;", extension)
        self.assertIn("now > duration_deadline", extension)
        self.assertIn(
            "result->p10_5_prefetched_objects_reclaimed =", extension
        )
        self.assertIn("status = p9_shutdown();", extension)
        self.assertIn("complete TFDU-active interval", extension)
        self.assertIn("Expensive CRC/SHA finalization happens only", extension)
        duration_tail = extension[extension.index(
            "Expensive CRC/SHA finalization happens only"):]
        self.assertLess(
            duration_tail.index("status = p9_shutdown();"),
            duration_tail.index("p9_sha256_final(&input_sha_context"),
        )
        self.assertIn(
            "status = p9_reset_stream_path(result->ring_depth, 1U, 1U);",
            extension,
        )


if __name__ == "__main__":
    unittest.main()
