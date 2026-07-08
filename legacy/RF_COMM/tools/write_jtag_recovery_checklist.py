#!/usr/bin/env python3
"""Write a hardware-aware JTAG recovery checklist for the current AX7010 state.

The checklist combines local AX7010 manual evidence, Windows PnP properties,
and the latest JTAG blocker report. It is read-only: no driver install, no FPGA
programming, and no TFDU drive.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
MANUAL = ROOT / "hardware/AX7010_UserManual/AX7010_UserManual.rst"
FTDI_INSTANCE = r"USB\VID_0403&PID_6014\210512180081"


@dataclass
class Check:
    order: int
    item: str
    evidence: str
    reason: str
    expected: str


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def latest(pattern: str) -> Path | None:
    paths = list(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if cell is None else str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def run_pnputil_properties() -> tuple[str, int]:
    try:
        proc = subprocess.run(
            ["pnputil.exe", "/enum-devices", "/instanceid", FTDI_INSTANCE, "/properties"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        return proc.stdout, int(proc.returncode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc), 124


def line_no(text: str, pattern: str) -> str:
    for idx, line in enumerate(text.splitlines(), start=1):
        if pattern in line:
            return str(idx)
    return ""


def contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None


def extract(text: str, pattern: str, default: str = "") -> str:
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else default


def collect() -> dict[str, object]:
    manual = read_text(MANUAL)
    blocker_path = latest("reports/jtag_blocker_analysis_current_*.json")
    blocker = json.loads(read_text(blocker_path)) if blocker_path else {}
    pnp_text, pnp_exit = run_pnputil_properties()

    manual_ft232hl = "FT232HL" in manual
    manual_usb_jtag = "USB JTAG" in manual or "USB Cable" in manual
    manual_j13 = "J13" in manual and "JTAG" in manual
    pnp_started = contains(pnp_text, r"(?m)^Status:\s+Started\b")
    pnp_no_problem = contains(pnp_text, r"DEVPKEY_Device_ProblemCode.*?0x00000000 \(0\)")
    pnp_bus_digilent = contains(pnp_text, r"DEVPKEY_Device_BusReportedDeviceDesc.*?Digilent USB Device")
    pnp_ftdibus = contains(pnp_text, r"DEVPKEY_Device_Service.*?FTDIBUS")
    pnp_driver_version = extract(pnp_text, r"DEVPKEY_Device_DriverVersion \[String\]:\s*\n\s*([^\n]+)")
    pnp_driver_inf = extract(pnp_text, r"DEVPKEY_Device_DriverInfPath \[String\]:\s*\n\s*([^\n]+)")

    manual_refs = [
        ["integrated_usb_cable", rel(MANUAL), line_no(manual, "Xilinx USB Cable")],
        ["usb_jtag_port", rel(MANUAL), line_no(manual, "USB JTAG")],
        ["ft232hl_bridge", rel(MANUAL), line_no(manual, "FT232HL")],
        ["j13_boot_mode", rel(MANUAL), line_no(manual, "J13")],
    ]

    pnp_rows = [
        ["instance", FTDI_INSTANCE],
        ["pnputil_exit", str(pnp_exit)],
        ["status_started", str(int(pnp_started))],
        ["problem_code_zero", str(int(pnp_no_problem))],
        ["bus_reported_digilent", str(int(pnp_bus_digilent))],
        ["service_ftdibus", str(int(pnp_ftdibus))],
        ["driver_inf", pnp_driver_inf],
        ["driver_version", pnp_driver_version],
    ]

    checks = [
        Check(
            1,
            "AX7010 board main power and reset state",
            "Manual documents independent PS/PL supplies and JTAG debug through the board.",
            "Windows sees the FT232HL bridge, but Vivado sees zero hw targets; a powered bridge alone does not prove the Zynq JTAG chain is alive.",
            "Power indicators normal; Zynq not held in reset.",
        ),
        Check(
            2,
            "USB cable connected to AX7010 USB-JTAG/download connector",
            "Manual says AX7010 uses onboard FT232HL USB bridge for TCK/TDO/TMS/TDI.",
            "Current PnP device reports Digilent USB Device with VID_0403&PID_6014, which is consistent with the AX7010 JTAG bridge.",
            "Only the JTAG/download Micro-USB path is used for Vivado hardware manager.",
        ),
        Check(
            3,
            "J13 boot jumper position for JTAG debug",
            "Manual table lists J13 right-side jumper position as JTAG boot mode.",
            "JTAG chain often remains accessible in other boot modes, but for this recovery step the manual JTAG mode removes one variable.",
            "J13 set to JTAG/debug position while recovering hw target enumeration.",
        ),
        Check(
            4,
            "Vivado cable driver binding for FT232HL",
            f"PnP: service FTDIBUS={int(pnp_ftdibus)}, driver={pnp_driver_inf} {pnp_driver_version}, problem_code_zero={int(pnp_no_problem)}.",
            "Windows driver stack is healthy, but Vivado 2023.1 hw_server still reports target_count=0 at all tested frequencies.",
            "If physical checks pass, run elevated Xilinx/Digilent driver recovery and re-test preflight.",
        ),
        Check(
            5,
            "Post-recovery no-programming preflight",
            rel(blocker_path),
            "The project safety gate requires HW_PREFLIGHT_RESULT PASS plus HW_PREFLIGHT_ZYNQ before any bitstream/TFDU action.",
            "tools/check_hw_target.ps1 returns PASS and lists xc7z010.",
        ),
    ]

    if blocker.get("status") == "BLOCKED_NO_HW_TARGET" and manual_ft232hl and pnp_bus_digilent:
        classification = "EXPECTED_AX7010_FT232HL_VISIBLE_BUT_NO_VIVADO_TARGET"
    elif blocker.get("status") == "BLOCKED_NO_HW_TARGET":
        classification = "NO_VIVADO_TARGET"
    else:
        classification = str(blocker.get("status", "UNKNOWN"))

    if classification == "JTAG_READY":
        checks = [
            Check(
                1,
                "Current no-programming Vivado preflight",
                rel(blocker_path),
                "Latest JTAG blocker report records current HW pass evidence and zero current FAIL_NO_TARGET evidence.",
                "HW_PREFLIGHT_RESULT PASS and HW_PREFLIGHT_ZYNQ are present.",
            ),
            Check(
                2,
                "Windows USB/JTAG bridge remains visible",
                f"PnP: service FTDIBUS={int(pnp_ftdibus)}, driver={pnp_driver_inf} {pnp_driver_version}, problem_code_zero={int(pnp_no_problem)}.",
                "The expected AX7010 FTDI/Digilent bridge is still enumerated by Windows.",
                "Keep the board powered and USB-JTAG cable connected while running P2 debug gates.",
            ),
            Check(
                3,
                "Continue through P2 safety gates",
                "reports/P2_next_hardware_run_readiness.md",
                "JTAG recovery is no longer the active blocker; P2 lane0 repeatability stop conditions still apply.",
                "Run only the active P2 health-debug or guarded sequence commands.",
            ),
        ]

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "classification": classification,
        "manual_ft232hl": manual_ft232hl,
        "manual_usb_jtag": manual_usb_jtag,
        "manual_j13": manual_j13,
        "manual_refs": manual_refs,
        "pnp_rows": pnp_rows,
        "pnp_text": pnp_text,
        "pnp_exit": pnp_exit,
        "blocker": blocker,
        "blocker_path": blocker_path,
        "checks": checks,
    }


def render(report: dict[str, object]) -> str:
    checks: list[Check] = report["checks"]  # type: ignore[assignment]
    classification = str(report["classification"])
    if classification == "JTAG_READY":
        meaning = "Vivado hw_server currently enumerates the AX7010 JTAG target and Zynq device; no JTAG recovery is currently required."
        commands = [
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\check_hw_target.ps1 -ComPort COM3 -JtagFrequencyHz 1000000",
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p2_lane0_health_debug_safe.ps1",
        ]
    else:
        meaning = "AX7010's expected FT232HL/Digilent USB bridge is visible to Windows, but Vivado hw_server still enumerates zero Zynq/JTAG targets."
        commands = [
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_jtag_driver_recovery_then_resume.ps1 -LaunchElevated -InstallPcUsb -InstallDigilent",
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\check_hw_target.ps1 -ComPort COM3 -JtagFrequencyHz 1000000",
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p1_lane_mapping_matrix_safe.ps1 -StopOnFail",
        ]
    return "\n".join(
        [
            "# RF_COMM JTAG Recovery Checklist",
            "",
            f"Generated: {report['generated']}",
            "",
            "## Verdict",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Meaning: {meaning}",
            "- This report did not install drivers, program FPGA, run ILA, write UART, or drive TFDU.",
            "",
            "## AX7010 Manual Evidence",
            "",
            md_table(["fact", "path", "line"], report["manual_refs"]),  # type: ignore[arg-type]
            "",
            "## Windows PnP Evidence",
            "",
            md_table(["key", "value"], report["pnp_rows"]),  # type: ignore[arg-type]
            "",
            "## Ordered Checks",
            "",
            md_table(
                ["order", "check", "evidence", "reason", "expected"],
                [[check.order, check.item, check.evidence, check.reason, check.expected] for check in checks],
            ),
            "",
            "## Recovery Commands",
            "",
            "```powershell",
            *commands,
            "```",
            "",
            "JTAG_RECOVERY_CHECKLIST "
            f"classification={report['classification']} "
            "hardware_action=none programming=none tfdu_drive=none",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPORTS / "jtag_recovery_checklist_current_20260626.md")
    parser.add_argument("--json", type=Path, default=REPORTS / "jtag_recovery_checklist_current_20260626.json")
    parser.add_argument("--pnp-log", type=Path, default=REPORTS / "jtag_recovery_checklist_current_20260626.pnp.txt")
    args = parser.parse_args()

    report = collect()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(report), encoding="utf-8")

    json_out = args.json if args.json.is_absolute() else ROOT / args.json
    json_payload = {
        key: value
        for key, value in report.items()
        if key not in {"pnp_text", "checks", "blocker_path"}
    }
    json_payload["checks"] = [asdict(check) for check in report["checks"]]  # type: ignore[index]
    json_payload["blocker_path"] = rel(report["blocker_path"])  # type: ignore[arg-type]
    json_payload["hardware_action"] = "none"
    json_payload["programming"] = "none"
    json_payload["tfdu_drive"] = "none"
    json_out.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    pnp_out = args.pnp_log if args.pnp_log.is_absolute() else ROOT / args.pnp_log
    pnp_out.write_text(str(report["pnp_text"]), encoding="utf-8")

    print(f"JTAG_RECOVERY_CHECKLIST_CLASSIFICATION={report['classification']}")
    print(f"JTAG_RECOVERY_CHECKLIST_MARKDOWN={out}")
    print(f"JTAG_RECOVERY_CHECKLIST_JSON={json_out}")
    print(f"JTAG_RECOVERY_CHECKLIST_PNP_LOG={pnp_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
