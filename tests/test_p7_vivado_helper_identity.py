import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "tools"))
import p7_vivado_helper_identity as subject  # noqa: E402


VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")


def exact_probe_payload() -> dict:
    profile = subject._MANIFEST["profiles"][  # type: ignore[attr-defined]
        subject.CURRENT_VIVADO_HELPER_HASH_PROFILE_ID
    ]
    records = []
    for role in subject.EXPECTED_VIVADO_HELPER_ROLES:
        record = dict(profile["records"][role])
        record.pop("sha256")
        records.append({"role": role, **record})
    host = dict(subject._MANIFEST["probe_host"])  # type: ignore[attr-defined]
    host.pop("sha256")
    return {
        "schema": subject.PROBE_SCHEMA,
        "probe_host": {"role": "probe_host", **host},
        "records": records,
    }


def runner_for(payload: dict, *, returncode: int = 0, stderr: str = ""):
    def run(argv, _env):
        return subprocess.CompletedProcess(
            argv,
            returncode,
            stdout=json.dumps(payload, separators=(",", ":")),
            stderr=stderr,
        )

    return run


class P7VivadoHelperIdentityTests(unittest.TestCase):
    def test_manifest_probe_and_current_profile_are_exactly_source_bound(self) -> None:
        self.assertEqual(
            subject.EXPECTED_MANIFEST_SHA256,
            subject.sha256_file(subject.MANIFEST_PATH),
        )
        probe = subject._MANIFEST["identity_probe"]  # type: ignore[attr-defined]
        probe_path = (ROOT / probe["path"]).resolve()
        self.assertEqual(probe["sha256"], subject.sha256_file(probe_path))
        self.assertEqual(
            [subject.CURRENT_VIVADO_HELPER_HASH_PROFILE_ID],
            [
                profile_id
                for profile_id, profile in subject._MANIFEST["profiles"].items()  # type: ignore[attr-defined]
                if profile["runtime_eligible"]
            ],
        )

    def test_complete_hash_profiles_accept_current_and_history_but_never_mix(self) -> None:
        profiles = subject.APPROVED_VIVADO_HELPER_SHA256_PROFILES
        self.assertEqual(2, len(profiles))
        for profile_id, hashes in profiles.items():
            self.assertEqual(profile_id, subject.approved_vivado_helper_hash_profile_id(hashes))
        ids = list(profiles)
        mixed = dict(profiles[ids[0]])
        mixed["cmd"] = profiles[ids[1]]["cmd"]
        self.assertIsNone(subject.approved_vivado_helper_hash_profile_id(mixed))
        unknown = dict(subject.EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE)
        unknown["cmd"] = "0" * 64
        self.assertIsNone(subject.approved_vivado_helper_hash_profile_id(unknown))

    @unittest.skipUnless(VIVADO.is_file(), "Vivado 2023.1 launcher unavailable")
    def test_current_live_identity_passes_exact_sha_path_version_and_signature(self) -> None:
        report = subject.validate_vivado_helper_identity(
            VIVADO, probe_runner=runner_for(exact_probe_payload())
        )
        self.assertEqual("PASS", report["status"])
        self.assertEqual("NONE", report["error_code"])
        self.assertFalse(report["hardware_actions_executed"])
        self.assertFalse(report["campaign_attempt_created"])
        self.assertEqual([], subject.validate_identity_validation_report(report))
        for mutation in ("hash", "version", "signer", "path", "manifest"):
            tampered = copy.deepcopy(report)
            if mutation == "hash":
                tampered["observed_sha256_by_role"]["cmd"] = "0" * 64
            elif mutation == "version":
                tampered["probe_payload"]["records"][2]["file_version"] = "0.0.0.0"
            elif mutation == "signer":
                tampered["probe_payload"]["records"][2]["signer_thumbprint"] = "0" * 40
            elif mutation == "path":
                tampered["observed_file_records"]["cmd"]["path"] = r"C:\Windows\Temp\cmd.exe"
            else:
                tampered["manifest"]["sha256"] = "0" * 64
            with self.subTest(mutation=mutation):
                self.assertTrue(subject.validate_identity_validation_report(tampered))

    @unittest.skipUnless(VIVADO.is_file(), "Vivado 2023.1 launcher unavailable")
    def test_version_signature_and_path_mismatches_fail_closed(self) -> None:
        mutations = []
        version = exact_probe_payload()
        version["records"][2]["file_version"] = "0.0.0.0"
        mutations.append((version, "VIVADO_HELPER_METADATA_MISMATCH"))
        signature = exact_probe_payload()
        signature["records"][2]["signature_status"] = "NotSigned"
        mutations.append((signature, "VIVADO_HELPER_METADATA_MISMATCH"))
        path = exact_probe_payload()
        path["records"][2]["path"] = r"C:\Windows\Temp\cmd.exe"
        mutations.append((path, "VIVADO_HELPER_METADATA_MISMATCH"))
        host = exact_probe_payload()
        host["probe_host"]["signer_thumbprint"] = "0" * 40
        mutations.append((host, "PROBE_HOST_METADATA_MISMATCH"))
        for payload, expected_code in mutations:
            with self.subTest(expected_code=expected_code):
                report = subject.validate_vivado_helper_identity(
                    VIVADO, probe_runner=runner_for(payload)
                )
                codes = {item["error_code"] for item in report["errors"]}
                self.assertIn(expected_code, codes)
                self.assertEqual("FAIL", report["status"])

    @unittest.skipUnless(VIVADO.is_file(), "Vivado 2023.1 launcher unavailable")
    def test_unknown_or_tampered_hash_fails_before_metadata_probe(self) -> None:
        expected_records = {
            role: {
                "path": record["path"],
                "sha256": record["sha256"],
                "bytes": record["bytes"],
            }
            for role, record in subject._MANIFEST["profiles"][  # type: ignore[attr-defined]
                subject.CURRENT_VIVADO_HELPER_HASH_PROFILE_ID
            ]["records"].items()
        }
        tampered = copy.deepcopy(expected_records)
        tampered["cmd"]["sha256"] = "0" * 64
        probe = mock.Mock(side_effect=AssertionError("metadata probe must not run"))
        with mock.patch.object(subject, "_hash_records", return_value=(tampered, [])):
            report = subject.validate_vivado_helper_identity(VIVADO, probe_runner=probe)
        self.assertEqual("VIVADO_HELPER_RUNTIME_HASH_PROFILE_MISMATCH", report["error_code"])
        self.assertEqual("FAIL", report["status"])
        probe.assert_not_called()

    def test_windows_helper_paths_are_literal_absolute_and_not_shell_expressions(self) -> None:
        paths = subject.derive_helper_paths(VIVADO)
        self.assertEqual(set(subject.EXPECTED_VIVADO_HELPER_ROLES), set(paths))
        self.assertTrue(all(Path(value).is_absolute() for value in paths.values()))
        self.assertTrue(all("Join-Path" not in value and "Test-Path" not in value for value in paths.values()))
        self.assertEqual("cmd.exe", Path(paths["cmd"]).name.lower())
        self.assertEqual("conhost.exe", Path(paths["conhost"]).name.lower())

    def test_jtag_wrapper_revalidates_shared_identity_inside_lock_before_vivado(self) -> None:
        source = (ROOT / "scripts" / "hw" / "run_p7_jtag_axi_stage_safe.py").read_text(
            encoding="utf-8"
        )
        main_source = source[source.index("def main(argv:") :]
        self.assertLess(
            main_source.index("HardwareExecutionLock.acquire"),
            main_source.index("validate_vivado_helper_identity(args.vivado_path)"),
        )
        self.assertLess(
            main_source.index("validate_vivado_helper_identity(args.vivado_path)"),
            main_source.index("build_preflight_command(args, preflight_result_file)"),
        )


if __name__ == "__main__":
    unittest.main()
