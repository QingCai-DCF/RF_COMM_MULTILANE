from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from tools.ax7010_ps7_board_contract import (
    EXPECTED_DEVICE,
    EXPECTED_PS7_PARAMETERS,
    validate_generated_board_contract,
    validate_vitis_artifacts,
    validate_vivado_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]
BUILD_TCL = ROOT / "scripts/build_p6_ps_candidate.tcl"
BUILD_PY = ROOT / "scripts/build_p6_ps_candidate.py"


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_p6_ps_candidate", BUILD_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load P6 build module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parameter_xml() -> bytes:
    root = ET.Element("SYSTEM")
    module = ET.SubElement(root, "MODULE", MODTYPE="processing_system7")
    parameters = ET.SubElement(module, "PARAMETERS")
    for name, value in EXPECTED_PS7_PARAMETERS.items():
        ET.SubElement(parameters, "PARAMETER", NAME=name, VALUE=value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _fixture(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    tcl = root / "build.tcl"
    shutil.copy2(BUILD_TCL, tcl)
    xci = root / "ps7.xci"
    xci.write_text(
        json.dumps(
            {
                "ip_inst": {
                    "parameters": {
                        "project_parameters": {
                            "DEVICE": [{"value": "xc7z010"}],
                            "PACKAGE": [{"value": "clg400"}],
                            "SPEEDGRADE": [{"value": "-1"}],
                        },
                        "component_parameters": {
                            key: [{"value": value}]
                            for key, value in EXPECTED_PS7_PARAMETERS.items()
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    bd = root / "ps7.bd"
    bd.write_text(
        json.dumps(
            {
                "design": {
                    "design_info": {"device": EXPECTED_DEVICE},
                    "components": {
                        "processing_system7_0": {
                            "xci_name": "p6_ps_system_processing_system7_0_0",
                            "xci_path": (
                                "ip\\p6_ps_system_processing_system7_0_0\\"
                                "p6_ps_system_processing_system7_0_0.xci"
                            ),
                            "parameters": {
                                key: {"value": value}
                                for key, value in EXPECTED_PS7_PARAMETERS.items()
                            }
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    init_tcl_bytes = b"proc ps7_init {} {}\nproc ps7_post_config {} {}\n"
    init_c_bytes = b"int ps7_init(void){return 0;}\nint ps7_post_config(void){return 0;}\n"
    xsa = root / "ps7.xsa"
    with zipfile.ZipFile(xsa, "w") as archive:
        archive.writestr("p6_ps_system.hwh", _parameter_xml())
        archive.writestr(
            "sysdef.xml",
            ET.tostring(
                ET.Element("SYSTEMINFO", PART=EXPECTED_DEVICE),
                encoding="utf-8",
                xml_declaration=True,
            ),
        )
        archive.writestr("ps7_init.tcl", init_tcl_bytes)
        archive.writestr("ps7_init.c", init_c_bytes)
    generated_tcl = root / "generated_ps7_init.tcl"
    generated_c = root / "generated_ps7_init.c"
    generated_tcl.write_bytes(init_tcl_bytes)
    generated_c.write_bytes(init_c_bytes)
    platform_xsa = root / "platform.xsa"
    shutil.copy2(xsa, platform_xsa)
    parameters_xml = root / "ps7_parameters.xml"
    parameters_xml.write_bytes(_parameter_xml())
    platform_tcl = root / "platform_ps7_init.tcl"
    platform_c = root / "platform_ps7_init.c"
    fsbl_c = root / "fsbl_ps7_init.c"
    platform_tcl.write_bytes(init_tcl_bytes)
    platform_c.write_bytes(init_c_bytes)
    fsbl_c.write_bytes(init_c_bytes)
    return {
        "build_tcl": tcl,
        "xci": xci,
        "block_design": bd,
        "xsa": xsa,
        "ps7_init_tcl": generated_tcl,
        "ps7_init_c": generated_c,
        "platform_xsa": platform_xsa,
        "ps7_parameters": parameters_xml,
        "platform_ps7_init_tcl": platform_tcl,
        "platform_ps7_init_c": platform_c,
        "fsbl_ps7_init_c": fsbl_c,
    }


def _mutate_xci(paths: dict[str, Path], field: str, value: str | None) -> None:
    data = json.loads(paths["xci"].read_text(encoding="utf-8"))
    parameters = data["ip_inst"]["parameters"]["component_parameters"]
    if value is None:
        del parameters[field]
    else:
        parameters[field][0]["value"] = value
    paths["xci"].write_text(json.dumps(data), encoding="utf-8")


def _mutate_bd(paths: dict[str, Path], field: str, value: str) -> None:
    data = json.loads(paths["block_design"].read_text(encoding="utf-8"))
    data["design"]["components"]["processing_system7_0"]["parameters"][field][
        "value"
    ] = value
    paths["block_design"].write_text(json.dumps(data), encoding="utf-8")


def _mutate_xml_parameter(path: Path, field: str, value: str) -> None:
    root = ET.parse(path).getroot()
    for element in root.iter():
        if element.attrib.get("NAME") == field:
            element.attrib["VALUE"] = value
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
            return
    raise AssertionError(f"missing XML fixture field {field}")


class P6PsBoardContractTests(unittest.TestCase):
    def _vivado(self, paths: dict[str, Path]) -> dict:
        return validate_vivado_artifacts(
            build_tcl=paths["build_tcl"],
            xci=paths["xci"],
            block_design=paths["block_design"],
            xsa=paths["xsa"],
            ps7_init_tcl=paths["ps7_init_tcl"],
            ps7_init_c=paths["ps7_init_c"],
        )

    def _vitis(self, paths: dict[str, Path]) -> dict:
        return validate_vitis_artifacts(
            xsa=paths["xsa"],
            platform_xsa=paths["platform_xsa"],
            ps7_parameters=paths["ps7_parameters"],
            platform_ps7_init_tcl=paths["platform_ps7_init_tcl"],
            platform_ps7_init_c=paths["platform_ps7_init_c"],
            fsbl_ps7_init_c=paths["fsbl_ps7_init_c"],
        )

    def _xci_mutation_fails(self, field: str, value: str | None) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = _fixture(Path(temp))
            _mutate_xci(paths, field, value)
            report = self._vivado(paths)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(
                any(error["artifact"] == "vivado_xci" and error["field"] == field for error in report["errors"]),
                report["errors"],
            )

    def test_build_tcl_locks_full_contract_after_automation(self) -> None:
        text = BUILD_TCL.read_text(encoding="utf-8")
        automation = text.index("apply_bd_automation -rule xilinx.com:bd_rule:processing_system7")
        first_contract = text.index("CONFIG.PCW_CRYSTAL_PERIPHERAL_FREQMHZ", automation)
        validation = text.index("validate_bd_design")
        self.assertLess(automation, first_contract)
        self.assertLess(first_contract, validation)
        for key, value in EXPECTED_PS7_PARAMETERS.items():
            self.assertIn(f"CONFIG.{key} {{{value}}}", text)

    def test_python_gate_requires_complete_generated_contract(self) -> None:
        module = load_build_module()
        self.assertEqual(EXPECTED_DEVICE, module.EXPECTED_BOARD_CONFIGURATION["P6_PS7_DEVICE"])
        for key, value in EXPECTED_PS7_PARAMETERS.items():
            self.assertEqual(value, module.EXPECTED_BOARD_CONFIGURATION[f"CONFIG.{key}"])
        source = BUILD_PY.read_text(encoding="utf-8")
        self.assertIn("and board_contract_verified", source)
        self.assertIn('"ps7_board_contract_verified": board_contract_verified', source)

    def test_correct_serialized_vivado_and_vitis_artifacts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = _fixture(Path(temp))
            self.assertEqual("PASS", self._vivado(paths)["status"])
            self.assertEqual("PASS", self._vitis(paths)["status"])

    def test_bank1_3v3_regression_fails(self) -> None:
        self._xci_mutation_fails("PCW_PRESET_BANK1_VOLTAGE", "LVCMOS 3.3V")

    def test_old_x8_1024_mbit_topology_regression_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = _fixture(Path(temp))
            _mutate_xci(paths, "PCW_UIPARAM_DDR_PARTNO", "MT41J128M8 JP-125")
            _mutate_xci(paths, "PCW_UIPARAM_DDR_DRAM_WIDTH", "8 Bits")
            _mutate_xci(paths, "PCW_UIPARAM_DDR_DEVICE_CAPACITY", "1024 MBits")
            report = self._vivado(paths)
            self.assertEqual("FAIL", report["status"])
            self.assertGreaterEqual(len(report["errors"]), 3)

    def test_bus_width_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_UIPARAM_DDR_BUS_WIDTH", "16 Bit")

    def test_ddr_frequency_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_UIPARAM_DDR_FREQ_MHZ", "400.000000")

    def test_ecc_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_UIPARAM_DDR_ECC", "Enabled")

    def test_read_gate_training_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_UIPARAM_DDR_TRAIN_READ_GATE", "0")

    def test_read_data_eye_training_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_UIPARAM_DDR_TRAIN_DATA_EYE", "0")

    def test_write_level_training_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_UIPARAM_DDR_TRAIN_WRITE_LEVEL", "0")

    def test_ps_input_clock_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_CRYSTAL_PERIPHERAL_FREQMHZ", "50.000000")

    def test_cpu_clock_change_fails(self) -> None:
        self._xci_mutation_fails("PCW_APU_PERIPHERAL_FREQMHZ", "650.000000")

    def test_missing_field_fails_closed(self) -> None:
        self._xci_mutation_fails("PCW_UIPARAM_DDR_ECC", None)

    def test_unparseable_xci_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = _fixture(Path(temp))
            paths["xci"].write_text("{not-json", encoding="utf-8")
            report = self._vivado(paths)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(any(error["reason"] == "UNPARSEABLE" for error in report["errors"]))

    def test_block_design_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = _fixture(Path(temp))
            _mutate_bd(paths, "PCW_PRESET_BANK1_VOLTAGE", "LVCMOS 3.3V")
            report = self._vivado(paths)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(any(error["artifact"] == "vivado_block_design" for error in report["errors"]))

    def test_vitis_parameter_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = _fixture(Path(temp))
            _mutate_xml_parameter(
                paths["ps7_parameters"], "PCW_PRESET_BANK1_VOLTAGE", "LVCMOS 3.3V"
            )
            report = self._vitis(paths)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(any(error["artifact"] == "vitis_ps7_parameters" for error in report["errors"]))

    def test_ps7_init_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = _fixture(Path(temp))
            paths["platform_ps7_init_c"].write_bytes(
                paths["platform_ps7_init_c"].read_bytes() + b"/* changed */\n"
            )
            report = self._vitis(paths)
            self.assertEqual("FAIL", report["status"])
            self.assertTrue(any(error["reason"] == "HASH_MISMATCH" for error in report["errors"]))

    def test_report_parser_rejects_duplicate_keys(self) -> None:
        module = load_build_module()
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "report.txt"
            report.write_text("A=1\nA=2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                module.read_key_value_report(report)

    def test_real_generated_artifacts_pass_contract(self) -> None:
        report = validate_generated_board_contract(ROOT, include_vitis=True)
        self.assertEqual("PASS", report["status"], report["errors"])


if __name__ == "__main__":
    unittest.main()
