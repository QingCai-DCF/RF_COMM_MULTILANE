#!/usr/bin/env python3
from pathlib import Path
import re, sys

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl/tfdu_lane_phy.sv"
PKG = ROOT / "rtl/tfdu_lane_phy_pkg.sv"

def has(pattern, text):
    return re.search(pattern, text, re.IGNORECASE | re.MULTILINE) is not None

def main():
    errors = []
    text = RTL.read_text(encoding="utf-8", errors="ignore") if RTL.exists() else ""
    pkg = PKG.read_text(encoding="utf-8", errors="ignore") if PKG.exists() else ""
    checks = {
        "TXD_DEFAULT_LOW": has(r"txd\s*<=\s*1'b0|assign\s+Txd\s*=", text),
        "SD_DEFAULT_SHUTDOWN_HIGH": has(r"sd\s*<=\s*1'b1|shutdown_active", text),
        "MODE_STATIC_HIGH_ONLY": has(r"MODE_STATIC_HIGH|mode_static_high|Mode=1", text + pkg),
        "STARTUP_TIMER_500US": has(r"TFDU_STARTUP_US\s*=\s*500|STARTUP_US.*500", text + pkg),
        "TX_STUCK_HIGH_PROTECTION": "tx_stuck_high" in text.lower() or "fault_stuck_high" in text.lower(),
        "DUTY_LIMIT_PROTECTION": "duty_limit" in text.lower() or "DUTY_MAX_PERMILLE" in text,
        "RX_LOW_ACTIVE_CONVERSION": "~rxd_sync" in text or "rx_pulse_active" in text,
    }
    for name, ok in checks.items():
        print(f"{name}={'1' if ok else '0'}")
        if not ok:
            errors.append(name)
    print(f"TFDU_SAFETY_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
