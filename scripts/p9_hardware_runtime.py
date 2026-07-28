#!/usr/bin/env python3
"""Fail-closed P9 stationary Z7010 two-lane hardware campaign.

This module is reached through ``run_p9_z7010_stationary_2lane.py
--execute-hardware``.  It defaults to dry-run, validates a phase-2 immutable
authorization before opening a hardware tool, executes P9-04..P9-26 in order,
and independently programs the shutdown image before and after every
candidate stage.  No Ethernet, motion, motor, Z7020, or lane mask above 0x3 is
implemented by this runner.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
HW_ROOT = ROOT / "evidence/hardware/p9"
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
HW_SERVER = Path(r"D:\Xilinx\Vivado\2023.1\bin\hw_server.bat")
XSDB = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsdb.bat")
PREFLIGHT_TCL = ROOT / "scripts/hw/p9_hw_preflight.tcl"
SHUTDOWN_TCL = ROOT / "scripts/hw/p9_program_shutdown.tcl"
STAGE_TCL = ROOT / "scripts/hw/p9_xsdb_stage.tcl"
DEFAULT_PHASE1 = ROOT / "config/p9_current_run_authorization.json"
EXPECTED_SCOPE = "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION"
EXPECTED_PART = "xc7z010clg400-1"
EXPECTED_PROFILE = "Z7010_2LANE_DEV"
EXPECTED_BOARD_ID = "210512180081"
EXPECTED_TARGET = "localhost:3121/xilinx_tcf/Digilent/210512180081"
HW_SERVER_URL = "localhost:3121"
XSDB_URL = "tcp:localhost:3121"
MAILBOX_WORDS = 256
PL_SNAPSHOT_START = 116
P9_DUTY_WINDOW_CYCLES = 64_000
P9_DUTY_HARD_MAX_HIGH_CYCLES = 12_799
P9_DUTY_TARGET_MAX_HIGH_CYCLES = 11_520
P9_FRAME_DUTY_GUARD_CYCLES = 20_480
P9_FRAME_DUTY_GUARD_US = 320
PL_SNAPSHOT_WORDS = 99
P9_MAILBOX_SCHEMA = 5
P9_FIRMWARE_BUILD_ID = 0x50090009
P9_PL_BUILD_ID = 0x50090008
PERFORMANCE_START = 215
PERMIT_START = 227
RFAP_START = 245
TERMINAL_WINDOW_START = 252
P9_TERMINAL_WINDOW_VALID = 0x5457494E
P9_DMA_MAX_TRANSFER = 0x03FFFFFF
# The current stationary Z7010 fixture exposes each selected-lane optical
# pulse at both physical receivers on that lane.  The protocol decoder still
# consumes only the direction-selected destination receiver (see
# p9_optical_transport_core.g_receive).  Raw acceptance therefore requires an
# exact count at both same-lane receivers and zero counts on the unselected
# lane; it must not misclassify the deterministic near-end observation as an
# extra destination pulse.  This policy is P9/Z7010-profile-specific and may
# not be extrapolated to Z7020 or the final mechanical geometry.
P9_RAW_RX_OBSERVATION_POLICY = "BOTH_ENDPOINTS_EXACT_SELECTED_LANE"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
RUN_RE = re.compile(r"^p9_[A-Za-z0-9_.-]+$")
STAGE_RE = re.compile(r"^P9-(?:0[4-9]|1[0-9]|2[0-6])$")
P9_FAULTS_WITHOUT_REQUIRED_RETRY = frozenset({
    "fault_drop_ack",
    "fault_duplicate_ack",
    "fault_reorder",
})
P9_FAULT_RETRY_EXEMPT_CASES = P9_FAULTS_WITHOUT_REQUIRED_RETRY | frozenset({
    "fault_retry_exhausted",
    "fault_recovery_soft_reset",
    "fault_post_recovery_clean",
})


def p9_fault_requires_retry_evidence(case_label: str) -> bool:
    """Return whether a P9-18 injected-fault case must show a TX retry."""
    return (case_label.startswith("fault_")
            and case_label not in P9_FAULT_RETRY_EXEMPT_CASES)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


REGISTER_MAP_SHA256 = sha256(ROOT / "config/register_map/ir_axi_regs.yaml")
EXPECTED_REGISTER_MAP_HASH_LOW = int(REGISTER_MAP_SHA256[-8:], 16)
EXPECTED_REGISTER_MAP_VERSION = 0x09000003


def rfap_transfer_bytes(row: dict[str, Any]) -> int:
    useful = int(row["size"])
    flags = int(row["flags"])
    if flags & 4:
        return useful + 32 * math.ceil(useful / 215)
    if flags & 8:
        return useful + 48 * math.ceil(useful / 65536)
    return useful


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_pair(stem: str, title: str, payload: dict[str, Any]) -> None:
    payload.setdefault("generated_utc", utc_now())
    write_json(GENERATED / f"{stem}.json", payload)
    lines = [
        f"# {title}", "", f"- Status: `{payload.get('status', 'UNKNOWN')}`",
        f"- Test ID: `{payload.get('test_id', 'UNKNOWN')}`",
        f"- Run ID: `{payload.get('run_id', 'UNKNOWN')}`",
        f"- Source commit: `{payload.get('source_commit', 'UNKNOWN')}`", "",
        "The adjacent JSON is authoritative; raw evidence remains in the run directory.", "",
    ]
    for key, value in payload.get("highlights", {}).items():
        rendered = json.dumps(value, sort_keys=True, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        lines.append(f"- `{key}`: `{rendered}`")
    (GENERATED / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class Case:
    label: str
    command: int
    expected_status: int = 0
    flags: int = 0
    lane: int = 0
    direction: int = 0
    rate: int = 0
    weights: int = 0x0101
    size: int = 0
    ring: int = 8
    cache: int = 0
    txoff: int = 0
    rxoff: int = 0
    timeout: int = 10_000
    session: int = 1
    path: int = 1
    object: int = 1
    dropdata: int = 0
    dropack: int = 0
    unavailable: int = 0
    rawtarget: int = 0
    spacing: int = 1024
    stale: int = 0
    initialseq: int = 0
    faultflags: int = 0
    idle: int = 0
    injectmask: int = 0
    injectdelay: int = 0

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.label):
            raise ValueError(f"unsafe case label: {self.label}")
        if not 0 <= self.lane <= 3 or not 0 <= self.unavailable <= 3 or not 0 <= self.injectmask <= 3:
            raise ValueError(f"lane mask outside 0x0..0x3: {self.label}")
        if not 1 <= self.timeout <= 1_800_000:
            raise ValueError(f"timeout outside authorized maximum: {self.label}")
        if self.command in {2, 3, 12} and self.lane not in {1, 2, 3}:
            raise ValueError(f"transmit command lacks authorized lane mask: {self.label}")
        if self.direction not in {0, 1} or self.rate not in {0, 1, 2}:
            raise ValueError(f"direction/rate invalid: {self.label}")
        if self.command == 3 and not (1 <= self.size <= 0x04000000):
            raise ValueError(f"object size invalid: {self.label}")

    def plan_line(self) -> str:
        self.validate()
        values = [
            "CASE", self.label, self.command, self.expected_status, self.flags,
            self.lane, self.direction, self.rate, self.weights, self.size,
            self.ring, self.cache, self.txoff, self.rxoff, self.timeout,
            self.session, self.path, self.object, self.dropdata, self.dropack,
            self.unavailable, self.rawtarget, self.spacing, self.stale,
            self.initialseq, self.faultflags, self.idle, self.injectmask,
            self.injectdelay,
        ]
        return " ".join(str(value) for value in values)


def object_case(label: str, *, lane: int, direction: int, rate: int, size: int,
                object_id: int, ring: int = 32, cache: int = 1,
                weights: int = 0x0101, timeout: int = 120_000,
                initial: int = 0, fault: int = 0, dropdata: int = 0,
                dropack: int = 0, unavailable: int = 0,
                expected_status: int = 0, allow_failure: bool = False,
                txoff: int = 0, rxoff: int = 0, injectmask: int = 0,
                injectdelay: int = 0, session: int = 0x90090001,
                path: int = 9, rfap: int = 0) -> Case:
    if rfap not in {0, 1, 2}:
        raise ValueError(f"invalid RFAP mode: {rfap}")
    rfap_flag = 4 if rfap == 1 else 8 if rfap == 2 else 0
    return Case(
        label=label, command=3, expected_status=expected_status,
        flags=2 | rfap_flag | (1 if allow_failure else 0), lane=lane,
        direction=direction, rate=rate, weights=weights, size=size,
        ring=ring, cache=cache, txoff=txoff, rxoff=rxoff,
        timeout=timeout, session=session, path=path, object=object_id,
        dropdata=dropdata, dropack=dropack, unavailable=unavailable,
        initialseq=initial, faultflags=fault, injectmask=injectmask,
        injectdelay=injectdelay,
    )


def raw_cases(prefix: str, lane: int, direction: int) -> list[Case]:
    return [
        Case(label=f"{prefix}_{count}", command=2, lane=lane,
             direction=direction, rawtarget=count, spacing=1024,
             timeout=30_000)
        for count in (64, 1000, 4096)
    ]


def rate_ladder(stage: str, lane: int, seed: int) -> list[Case]:
    cases: list[Case] = []
    object_id = seed
    for direction in (0, 1):
        for rate in (0, 1, 2):
            # One fixed short frame, five maximum-payload patterns, a 100-frame
            # smoke and a 10,000-frame acceptance case.
            cases.append(object_case(
                f"{stage}_d{direction}_r{rate}_fixed_short", lane=lane,
                direction=direction, rate=rate, size=31,
                object_id=0x40000000 | object_id, timeout=30_000,
            ))
            object_id += 1
            for mode, suffix in enumerate(("prbs", "zero", "one", "increment", "binary")):
                cases.append(object_case(
                    f"{stage}_d{direction}_r{rate}_{suffix}", lane=lane,
                    direction=direction, rate=rate, size=247,
                    object_id=(mode << 28) | object_id, timeout=30_000,
                ))
                object_id += 1
            cases.append(object_case(
                f"{stage}_d{direction}_r{rate}_100f", lane=lane,
                direction=direction, rate=rate, size=247 * 100,
                object_id=object_id, timeout=60_000,
            ))
            object_id += 1
            cases.append(object_case(
                f"{stage}_d{direction}_r{rate}_10000f", lane=lane,
                direction=direction, rate=rate, size=247 * 10_000,
                object_id=object_id, timeout=180_000,
            ))
            object_id += 1
    return cases


def build_plans() -> dict[str, list[Case | tuple[str, ...]]]:
    plans: dict[str, list[Case | tuple[str, ...]]] = {}
    plans["P9-06"] = [Case("p9_06_identity", 1, timeout=10_000)]
    plans["P9-07"] = [
        Case("p9_07_idle_safety", 11, idle=250, timeout=10_000),
        Case("p9_07_permit_drop_mid_raw", 12, lane=3, direction=0,
             rawtarget=100000, spacing=128, timeout=10_000),
        Case("p9_07_rearm_a", 2, lane=1, direction=0, rawtarget=16, spacing=1024, timeout=10_000),
        Case("p9_07_rearm_b", 2, lane=1, direction=1, rawtarget=16, spacing=1024, timeout=10_000),
    ]
    plans["P9-08"] = [Case("p9_08_idle_noise_5000ms", 11, idle=5000, timeout=15_000)]
    plans["P9-09"] = raw_cases("ab_l0", 1, 0)
    plans["P9-10"] = raw_cases("ba_l0", 1, 1)
    plans["P9-11"] = raw_cases("ab_l1", 2, 0)
    plans["P9-12"] = raw_cases("ba_l1", 2, 1)
    plans["P9-13"] = rate_ladder("lane0", 1, 0x1300)
    plans["P9-14"] = rate_ladder("lane1", 2, 0x1400)
    plans["P9-15"] = [
        object_case("two_lane_d0_10000f", lane=3, direction=0, rate=2,
                    size=247 * 10_000, object_id=0x1500, timeout=180_000),
        object_case("two_lane_d1_10000f", lane=3, direction=1, rate=2,
                    size=247 * 10_000, object_id=0x1501, timeout=180_000),
    ]
    clean: list[Case | tuple[str, ...]] = []
    oid = 0x1600
    for lane in (1, 2, 3):
        for direction in (0, 1):
            clean.append(object_case(f"sr_clean_m{lane}_d{direction}", lane=lane,
                                     direction=direction, rate=2, size=247 * 128,
                                     object_id=oid, timeout=60_000))
            oid += 1
    for direction in (0, 1):
        clean.append(object_case(f"sr_wrap_d{direction}", lane=3,
                                 direction=direction, rate=2, size=247 * 96,
                                 object_id=oid, initial=0xFFFE, timeout=60_000))
        oid += 1
    plans["P9-16"] = clean
    plans["P9-17"] = [
        object_case("sack_ack_clean", lane=3, direction=0, rate=2,
                    size=247 * 256, object_id=0x1700),
        object_case("sack_ack_loss_recovery", lane=3, direction=1, rate=2,
                    size=247 * 256, object_id=0x1701, dropack=1),
        object_case("sack_duplicate_ack", lane=3, direction=0, rate=2,
                    size=247 * 256, object_id=0x1702, fault=1 << 5),
        object_case("sack_reorder", lane=3, direction=1, rate=2,
                    size=247 * 256, object_id=0x1703, fault=1 << 6),
        object_case("sack_ack_bitmap_loss", lane=3, direction=0, rate=2,
                    size=247 * 256, object_id=0x1704, fault=1 << 7),
    ]
    faults = [
        ("drop_one_data", 247 * 96, dict(dropdata=1)),
        ("drop_burst_data", 247 * 96, dict(dropdata=3)),
        ("drop_ack", 247 * 96, dict(dropack=1)),
        # With multiple DATA frames a later cumulative ACK can legitimately
        # cover one lost ACK before RTO.  Use one DATA frame here so loss of
        # its sole ACK must exercise timeout, retransmission, duplicate DATA
        # rejection, and re-ACK without weakening the separate cumulative-ACK
        # recovery case above.
        ("duplicate_data_by_ack_loss", 247, dict(dropack=1)),
        ("stale_session", 247 * 96, dict(fault=1 << 0)),
        ("stale_path", 247 * 96, dict(fault=1 << 1)),
        ("future_sequence", 247 * 96, dict(fault=1 << 2)),
        ("old_sequence", 247 * 96, dict(fault=1 << 3)),
        ("duplicate_ack", 247 * 96, dict(fault=1 << 5)),
        ("reorder", 247 * 96, dict(fault=1 << 6)),
        # Keep the intentional parser CRC/frame-bad counters after all other
        # successful fault cases.  The explicit recovery soft reset below
        # then clears that cumulative parser telemetry together with the
        # controlled retry-exhaustion state before the final clean object.
        ("crc_corruption", 247 * 96, dict(fault=1 << 4)),
    ]
    plans["P9-18"] = [
        object_case(f"fault_{name}", lane=3, direction=index & 1, rate=2,
                    size=case_size, object_id=0x1800 + index,
                    timeout=90_000, **kwargs)
        for index, (name, case_size, kwargs) in enumerate(faults)
    ]
    plans["P9-18"].extend([
        object_case("fault_retry_exhausted", lane=3, direction=0, rate=2,
                    size=247 * 8, object_id=0x18F0, dropdata=255,
                    expected_status=12, timeout=120_000),
        Case("fault_recovery_soft_reset", 8, timeout=10_000),
        object_case("fault_post_recovery_clean", lane=3, direction=1, rate=2,
                    size=64 * 1024, object_id=0x18FF, timeout=90_000),
    ])

    dma: list[Case | tuple[str, ...]] = [
        Case("ring_depth_8", 4, ring=8, timeout=10_000),
        Case("ring_depth_32", 4, ring=32, timeout=10_000),
    ]
    sizes = (1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 191,
             247, 256, 1024, 4096, 65536, 1048576)
    for index, size in enumerate(sizes):
        dma.append(object_case(f"dma_size_{size}", lane=3, direction=index & 1,
                               rate=2, size=size, object_id=0x1900 + index,
                               ring=32, cache=1, timeout=120_000))
    for index, size in enumerate((1, 247, 4096, 1048576)):
        dma.append(object_case(f"dma_cache_off_{size}", lane=3, direction=index & 1,
                               rate=2, size=size, object_id=0x1980 + index,
                               ring=32, cache=0, timeout=120_000))
    dma.append(object_case("dma_misaligned_handled", lane=3, direction=0,
                           rate=2, size=4096, object_id=0x1988, ring=32,
                           cache=1, txoff=1, rxoff=3))
    for index in range(12):
        dma.append(object_case(f"dma_ring32_wrap_{index:02d}", lane=3,
                               direction=index & 1, rate=2, size=1,
                               object_id=0x19A0 + index, ring=32, cache=1,
                               timeout=30_000))
    dma.extend([
        Case("dma_reset_idle", 5, ring=32, timeout=10_000),
        Case("dma_reset_queued", 6, lane=3, direction=0, rate=2,
             size=4096, ring=32, cache=1, timeout=30_000),
        Case("dma_abort_outstanding", 7, lane=3, direction=0, rate=2,
             size=1048576, ring=32, cache=1, timeout=30_000),
        Case("pl_soft_reset", 8, timeout=10_000),
        Case("stale_completion", 9, stale=0xDEADBEEF, timeout=10_000),
        ("REBOOT", "ps_application_restart"),
        object_case("dma_post_reset_clean", lane=3, direction=1, rate=2,
                    size=65536, object_id=0x19FE, ring=32, cache=1),
    ])
    plans["P9-19"] = dma
    plans["P9-20"] = [
        object_case("sched_lane0", lane=1, direction=0, rate=2,
                    size=247 * 256, object_id=0x2000),
        object_case("sched_lane1", lane=2, direction=1, rate=2,
                    size=247 * 256, object_id=0x2001),
        object_case("sched_equal", lane=3, direction=0, rate=2,
                    size=247 * 512, object_id=0x2002, weights=0x0101),
        object_case("sched_1_to_3", lane=3, direction=1, rate=2,
                    size=247 * 512, object_id=0x2003, weights=0x0301),
        object_case("sched_3_to_1", lane=3, direction=0, rate=2,
                    size=247 * 512, object_id=0x2004, weights=0x0103),
        object_case("retry_migration", lane=3, direction=1, rate=2,
                    size=247 * 256, object_id=0x2005, dropdata=1),
        object_case("lane0_unavailable", lane=3, direction=0, rate=2,
                    size=247 * 256, object_id=0x2006, unavailable=1),
        object_case("lane1_unavailable", lane=3, direction=1, rate=2,
                    size=247 * 256, object_id=0x2007, unavailable=2),
        object_case("lane0_mapping_invalid", lane=3, direction=0, rate=2,
                    size=247 * 256, object_id=0x200B, fault=1 << 8),
        object_case("lane1_mapping_invalid", lane=3, direction=1, rate=2,
                    size=247 * 256, object_id=0x200C, fault=1 << 9),
        object_case("lane0_duty_throttle", lane=3, direction=0, rate=2,
                    size=247 * 256, object_id=0x200D, fault=1 << 10),
        object_case("lane1_duty_throttle", lane=3, direction=1, rate=2,
                    size=247 * 256, object_id=0x200E, fault=1 << 11),
        object_case("lane_fault_in_flight", lane=3, direction=0, rate=2,
                    size=1048576, object_id=0x2008, injectmask=1,
                    injectdelay=100, timeout=120_000),
        object_case("all_lanes_unavailable", lane=3, direction=0, rate=2,
                    size=4096, object_id=0x2009, unavailable=3,
                    allow_failure=True, timeout=30_000),
        object_case("scheduler_recovery", lane=3, direction=1, rate=2,
                    size=65536, object_id=0x200A),
    ]
    plans["P9-21"] = [
        object_case("rfap_v1_4k", lane=3, direction=0, rate=2,
                    size=4096, object_id=0x2100, rfap=1),
        object_case("rfap_v1_64k", lane=3, direction=1, rate=2,
                    size=65536, object_id=0x10002101, rfap=1),
        object_case("rfap_v1_1m", lane=3, direction=0, rate=2,
                    size=1048576, object_id=0x40002102, timeout=180_000,
                    rfap=1),
        object_case("rfap_v1_boundary_215", lane=3, direction=0, rate=2,
                    size=215, object_id=0x30002105, rfap=1),
        object_case("rfap_v1_boundary_216", lane=3, direction=1, rate=2,
                    size=216, object_id=0x20002106, rfap=1),
        Case("rfap_v1_abort", 7, lane=3, direction=0, rate=2,
             flags=6, size=1048576, ring=32, cache=1, session=0x90090001,
             path=9, object=0x2103, timeout=30_000),
        object_case("rfap_v1_restart_clean", lane=3, direction=1, rate=2,
                    size=65536, object_id=0x2104, rfap=1),
    ]
    plans["P9-22"] = [
        object_case("rfap_vnext_4k", lane=3, direction=0, rate=2,
                    size=4096, object_id=0x2200, session=0x90090022, path=22,
                    rfap=2),
        object_case("rfap_vnext_64k", lane=3, direction=1, rate=2,
                    size=65536, object_id=0x2201, session=0x90090022, path=22,
                    rfap=2),
        object_case("rfap_vnext_1m", lane=3, direction=0, rate=2,
                    size=1048576, object_id=0x2202, session=0x90090022,
                    path=22, timeout=180_000, rfap=2),
        object_case("rfap_vnext_16m", lane=3, direction=1, rate=2,
                    size=16 * 1024 * 1024, object_id=0x2203,
                    session=0x90090022, path=22, timeout=600_000, rfap=2),
        object_case("rfap_vnext_stale_session", lane=3, direction=0, rate=2,
                    size=65536, object_id=0x2204, session=0x90090022,
                    path=22, fault=1 << 0, rfap=2),
        object_case("rfap_vnext_stale_path", lane=3, direction=1, rate=2,
                    size=65536, object_id=0x2205, session=0x90090022,
                    path=22, fault=1 << 1, rfap=2),
    ]
    plans["P9-23"] = [
        object_case("object_a_to_b", lane=3, direction=0, rate=2,
                    size=1048576, object_id=0x2300, timeout=180_000, rfap=2),
        object_case("object_b_to_a", lane=3, direction=1, rate=2,
                    size=1048576, object_id=0x2301, timeout=180_000, rfap=2),
    ]
    perf: list[Case | tuple[str, ...]] = []
    oid = 0x2400
    for lane in (1, 2, 3):
        for direction in (0, 1):
            for size, suffix in ((4096, "short"), (1048576, "large")):
                perf.append(object_case(f"perf_m{lane}_d{direction}_{suffix}",
                                        lane=lane, direction=direction, rate=2,
                                        size=size, object_id=oid, timeout=180_000,
                                        rfap=2))
                oid += 1
    plans["P9-24"] = perf
    plans["P9-25"] = [("SOAK", "stationary_30min", "1800")]
    return plans


def write_plans(run_root: Path) -> dict[str, dict[str, Any]]:
    plan_root = run_root / "authorization/plans"
    plan_root.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, Any]] = {}
    for stage, entries in build_plans().items():
        lines = ["# P9 fixed execution plan; parsed completely before hardware connect."]
        json_entries: list[dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, Case):
                lines.append(entry.plan_line())
                json_entries.append({"kind": "CASE", **asdict(entry)})
            else:
                lines.append(" ".join(entry))
                json_entries.append({"kind": entry[0], "fields": list(entry[1:])})
        path = plan_root / f"{stage}.plan.txt"
        path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
        meta_path = plan_root / f"{stage}.plan.json"
        write_json(meta_path, {"stage": stage, "entries": json_entries, "sha256": sha256(path)})
        records[stage] = {"path": path, "sha256": sha256(path), "meta": meta_path,
                          "entry_count": len(entries)}
    return records


def artifact_path(record: dict[str, Any], key: str, errors: list[str]) -> Path:
    item = record.get(key, {})
    raw = item.get("path", "") if isinstance(item, dict) else ""
    path = ROOT / raw
    expected = str(item.get("sha256", "")).lower() if isinstance(item, dict) else ""
    if not raw or not path.is_file():
        errors.append(f"{key} immutable file missing")
    elif not inside(path, ROOT / "artifacts/p9"):
        errors.append(f"{key} path is outside content-addressed artifacts/p9")
    elif not SHA_RE.fullmatch(expected) or sha256(path) != expected:
        errors.append(f"{key} SHA-256 mismatch")
    return path


def validate_phase2(path: Path) -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {}, [f"phase-2 authorization unreadable: {exc}"]
    if record.get("authorized") is not True: errors.append("authorization is not true")
    if record.get("scope") != EXPECTED_SCOPE: errors.append("scope mismatch")
    if record.get("artifact_binding_phase") != "PHASE2_IMMUTABLE_ARTIFACTS_BOUND":
        errors.append("immutable phase-2 binding missing")
    if record.get("part") != EXPECTED_PART or record.get("profile") != EXPECTED_PROFILE:
        errors.append("part/profile mismatch")
    if record.get("maximum_single_test_seconds") != 1800:
        errors.append("maximum single test must be 1800 seconds")
    if record.get("maximum_runtime_seconds") != 1800:
        errors.append("authorized maximum runtime must be 1800 seconds")
    if record.get("lane_masks") != [1, 2, 3] or record.get("maximum_lane_mask") != 3:
        errors.append("authorized lane masks are not exactly 0x1/0x2/0x3")
    if record.get("allowed_lane_masks") != [1, 2, 3] or record.get("lane_count") != 2:
        errors.append("phase-1 lane authorization is not exactly two lanes / 0x1,0x2,0x3")
    if record.get("stationary") is not True or \
            record.get("hardware_stationary_immutable") is not True or \
            record.get("movement_allowed") is not False or \
            record.get("rotation_allowed") is not False or \
            record.get("network_allowed") is not False or \
            record.get("ethernet_required") is not False:
        errors.append("stationary/no-movement/no-rotation/no-network authorization mismatch")
    run_id = str(record.get("run_id", ""))
    if not RUN_RE.fullmatch(run_id): errors.append("invalid bound run id")
    manifest_path = ROOT / str(record.get("artifact_manifest_path", ""))
    manifest_hash = str(record.get("artifact_manifest_sha256", "")).lower()
    manifest: dict[str, Any] = {}
    if not manifest_path.is_file() or not inside(manifest_path, ROOT / "artifacts/p9"):
        errors.append("artifact manifest missing or outside artifacts/p9")
    elif sha256(manifest_path) != manifest_hash:
        errors.append("artifact manifest SHA-256 mismatch")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"artifact manifest unreadable: {exc}")
    paths = {
        "candidate": artifact_path(record, "candidate_bitstream", errors),
        "shutdown": artifact_path(record, "shutdown_bitstream", errors),
        "elf": artifact_path(record, "ps_elf", errors),
        "ps7_init": artifact_path(record, "ps7_init_tcl", errors),
        "bsp": artifact_path(record, "bsp_archive", errors),
        "runner": artifact_path(record, "runner_package", errors),
        "hardware_config": artifact_path(record, "hardware_config", errors),
        "source_manifest": artifact_path(record, "source_manifest", errors),
        "manifest": manifest_path,
    }
    source = str(record.get("source_commit", ""))
    try:
        if git("rev-parse", "HEAD") != source:
            errors.append("current HEAD does not equal frozen source commit")
    except subprocess.CalledProcessError:
        errors.append("unable to resolve current HEAD")
    if manifest:
        if manifest.get("status") != "PASS" or manifest.get("source_commit") != source or \
                manifest.get("part") != EXPECTED_PART or manifest.get("profile") != EXPECTED_PROFILE or \
                manifest.get("top") != "p9_ps_system_wrapper":
            errors.append("artifact manifest identity/status mismatch")
        for item in manifest.get("artifacts", []):
            if not isinstance(item, dict):
                errors.append("artifact manifest entry is not an object")
                continue
            artifact_file = ROOT / str(item.get("path", ""))
            expected_hash = str(item.get("sha256", "")).lower()
            if not artifact_file.is_file() or not inside(artifact_file, ROOT / "artifacts/p9") or \
                    not SHA_RE.fullmatch(expected_hash) or sha256(artifact_file) != expected_hash or \
                    artifact_file.parent.name.lower() != expected_hash:
                errors.append(f"content-addressed manifest artifact mismatch: {item.get('logical_name')}")
        build_hashes = manifest.get("build_audit", {}).get("build_input_sha256", {})
        if not isinstance(build_hashes, dict) or not build_hashes:
            errors.append("artifact manifest build-input hashes missing")
        else:
            for relative, expected_hash in build_hashes.items():
                current = ROOT / str(relative)
                if not current.is_file() or not inside(current, ROOT) or \
                        sha256(current) != str(expected_hash).lower():
                    errors.append(f"current build input differs from frozen manifest: {relative}")
        canonical_hashes = {
            "xdc_sha256": sha256(ROOT / "constraints/active/PORT1.generated.xdc"),
            "pinmap_sha256": sha256(ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"),
            "register_map_sha256": sha256(ROOT / "config/register_map/ir_axi_regs.yaml"),
        }
        for key, expected_hash in canonical_hashes.items():
            if manifest.get(key) != expected_hash:
                errors.append(f"artifact manifest canonical {key} mismatch")
    bound_files = [
        (ROOT / "config/project_state.json", record.get("project_state_sha256"), "project state"),
        (ROOT / "config/project_requirements.yaml", record.get("project_requirements_sha256"), "project requirements"),
        (ROOT / "config/p9_z7010_stationary_2lane.yaml", record.get("p9_config_sha256"), "P9 config"),
        (ROOT / "constraints/active/PORT1.generated.xdc", record.get("active_xdc_sha256"), "active XDC"),
        (ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv", record.get("pinmap_sha256"), "pinmap"),
        (ROOT / "config/register_map/ir_axi_regs.yaml", record.get("register_map_sha256"), "register map"),
        (ROOT / str(record.get("authorization_verbatim_utf8_path", "")),
         record.get("authorization_verbatim_utf8_sha256"), "verbatim authorization"),
    ]
    for bound_path, expected_hash, label in bound_files:
        if not bound_path.is_file() or not SHA_RE.fullmatch(str(expected_hash or "").lower()) or \
                sha256(bound_path) != str(expected_hash).lower():
            errors.append(f"{label} SHA-256 binding mismatch")
    goal_path = Path(str(record.get("goal_path", "")))
    if not goal_path.is_file() or sha256(goal_path) != str(record.get("goal_sha256", "")).lower():
        errors.append("goal SHA-256 binding mismatch")
    if record.get("two_lane_application_model") != \
            "PENDING_NO_CREDIBLE_FROZEN_2LANE_APPLICATION_MODEL" or \
            record.get("modeled_application_goodput_bps") is not None or \
            record.get("application_goodput_target_bps") is not None:
        errors.append("explicit frozen two-lane performance-model gap changed")
    for tool in (VIVADO, HW_SERVER, XSDB, PREFLIGHT_TCL, SHUTDOWN_TCL, STAGE_TCL):
        if not tool.is_file(): errors.append(f"required tool/script missing: {tool}")
    return record, paths, errors


def parse_markers(path: Path) -> dict[str, str]:
    markers: dict[str, str] = {}
    if not path.is_file(): return markers
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if re.fullmatch(r"[A-Z0-9_]+", key.strip()): markers[key.strip()] = value.strip()
    return markers


def terminate_tree(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None: return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
    else:
        proc.terminate()
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired: proc.kill()


def run_bounded(command: list[str], stdout_path: Path, stderr_path: Path,
                *, timeout: float, env: dict[str, str], abort_file: Path,
                active_limit: float | None = None) -> dict[str, Any]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic(); interrupted = False; timed_out = False
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc: subprocess.Popen[Any] | None = None
    error = ""
    try:
        with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
            proc = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err,
                                    text=True, shell=False, env=env,
                                    creationflags=creationflags)
            while proc.poll() is None:
                elapsed = time.monotonic() - started
                if elapsed >= timeout:
                    timed_out = True
                    abort_file.parent.mkdir(parents=True, exist_ok=True)
                    abort_file.write_text(f"timeout at {utc_now()}\n", encoding="ascii")
                    time.sleep(1)
                    terminate_tree(proc)
                    break
                time.sleep(0.1)
    except KeyboardInterrupt:
        interrupted = True
        abort_file.parent.mkdir(parents=True, exist_ok=True)
        abort_file.write_text(f"Ctrl+C at {utc_now()}\n", encoding="ascii")
        if proc is not None: terminate_tree(proc)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        if proc is not None: terminate_tree(proc)
    returncode = 130 if interrupted else 124 if timed_out else 127 if error else (
        int(proc.returncode) if proc is not None and proc.returncode is not None else 125)
    return {
        "command": command, "returncode": returncode, "timed_out": timed_out,
        "interrupted": interrupted, "error": error,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "stdout": rel(stdout_path), "stderr": rel(stderr_path),
        "stdout_sha256": sha256(stdout_path) if stdout_path.is_file() else None,
        "stderr_sha256": sha256(stderr_path) if stderr_path.is_file() else None,
        "active_limit_seconds": active_limit,
    }


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5): return True
    except OSError:
        return False


def start_hw_server(raw_logs: Path) -> tuple[subprocess.Popen[Any] | None, dict[str, Any]]:
    if port_open("127.0.0.1", 3121):
        return None, {"status": "PASS", "reused": True, "started": False}
    stdout = (raw_logs / "hw_server.stdout.log").open("w", encoding="utf-8")
    stderr = (raw_logs / "hw_server.stderr.log").open("w", encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    proc = subprocess.Popen([str(HW_SERVER), "-s", "tcp::3121"], cwd=ROOT,
                            stdout=stdout, stderr=stderr, text=True, shell=False,
                            creationflags=flags)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and proc.poll() is None:
        if port_open("127.0.0.1", 3121):
            return proc, {"status": "PASS", "reused": False, "started": True,
                          "pid": proc.pid, "stdout": rel(raw_logs / "hw_server.stdout.log"),
                          "stderr": rel(raw_logs / "hw_server.stderr.log")}
        time.sleep(0.2)
    terminate_tree(proc)
    return None, {"status": "FAIL", "reused": False, "started": True,
                  "reason": "hw_server did not open tcp/3121"}


def invoke_shutdown(run_root: Path, phase2: Path, shutdown_bit: Path,
                    label: str, env: dict[str, str], abort_file: Path) -> dict[str, Any]:
    directory = run_root / "shutdown" / label
    result_file = directory / "shutdown_result.txt"
    stdout = run_root / "raw_logs" / f"shutdown_{label}.stdout.log"
    stderr = run_root / "raw_logs" / f"shutdown_{label}.stderr.log"
    command = [str(VIVADO), "-mode", "batch", "-source", str(SHUTDOWN_TCL),
               "-tclargs", HW_SERVER_URL, EXPECTED_TARGET, EXPECTED_BOARD_ID,
               EXPECTED_PART, str(phase2), str(shutdown_bit), str(result_file)]
    process = run_bounded(command, stdout, stderr, timeout=180, env=env,
                          abort_file=abort_file)
    markers = parse_markers(result_file)
    passed = (process["returncode"] == 0
              and markers.get("TFDU_SHUTDOWN_PROGRAMMED") == "1"
              and markers.get("SHUTDOWN_EXIT") == "0"
              and markers.get("P9_SHUTDOWN_EXACT_FPGA_MATCH_COUNT") == "1"
              and markers.get("P9_SHUTDOWN_UNEXPECTED_HW_OBJECT_COUNT") == "0")
    payload = {"status": "PASS" if passed else "FAIL", "label": label,
               "process": process, "markers": markers,
               "result_path": rel(result_file) if result_file.is_file() else None}
    write_json(directory / "shutdown_summary.json", payload)
    return payload


def invoke_preflight(run_root: Path, phase2: Path, env: dict[str, str],
                     abort_file: Path) -> dict[str, Any]:
    result_file = run_root / "target_identity/target_identity_raw.txt"
    stdout = run_root / "raw_logs/p9_04_preflight.stdout.log"
    stderr = run_root / "raw_logs/p9_04_preflight.stderr.log"
    command = [str(VIVADO), "-mode", "batch", "-source", str(PREFLIGHT_TCL),
               "-tclargs", HW_SERVER_URL, EXPECTED_TARGET, EXPECTED_BOARD_ID,
               EXPECTED_PART, str(phase2), str(result_file)]
    process = run_bounded(command, stdout, stderr, timeout=180, env=env,
                          abort_file=abort_file)
    markers = parse_markers(result_file)
    passed = (process["returncode"] == 0
              and markers.get("P9_TARGET_IDENTITY_RESULT") == "PASS"
              and markers.get("P9_TARGET_IDENTITY_SINGLE_TARGET") == "1"
              and markers.get("P9_TARGET_IDENTITY_EXACT_FPGA_MATCH_COUNT") == "1"
              and markers.get("P9_TARGET_IDENTITY_UNEXPECTED_HW_OBJECT_COUNT") == "0"
              and markers.get("P9_TARGET_IDENTITY_LIVE_IDCODE_NORMALIZED") == "13722093")
    return {"status": "PASS" if passed else "FAIL", "test_id": "P9-04-TARGET-IDENTITY",
            "process": process, "markers": markers,
            "raw": rel(result_file) if result_file.is_file() else None}


def parse_mailbox(path: Path) -> list[int]:
    data = path.read_bytes()
    if len(data) != 1024: raise ValueError(f"mailbox dump size is {len(data)}, expected 1024")
    return list(struct.unpack("<256I", data))


def load_observations(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        for row in reader:
            converted: dict[str, Any] = dict(row)
            for key in row:
                if key not in {"label", "window", "dump_path"}:
                    converted[key] = int(row[key], 0)
            rows.append(converted)
    return rows


def pl(words: list[int], index: int) -> int:
    return words[PL_SNAPSHOT_START + index]


def digest(words: list[int], start: int) -> str:
    return "".join(f"{value:08x}" for value in words[start:start + 8])


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("NO_ROWS\n", encoding="ascii", newline="\n")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def evaluate_observation(row: dict[str, Any], words: list[int]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    label = row["label"]
    command = row["command"]
    expected_status = row["expected_status"]
    expected_state = 6 if command == 10 else 4 if expected_status == 0 else 5
    checks = {
        "mailbox_magic": words[0] == 0x424D3950,
        "mailbox_schema": words[1] == P9_MAILBOX_SCHEMA,
        "firmware_build": words[2] == P9_FIRMWARE_BUILD_ID,
        "service_state": words[3] == expected_state,
        "response_sequence": words[7] == row["sequence"],
        "command_status": words[8] == expected_status,
        "pl_id": words[32] == 0x50395A10,
        "pl_build_id": words[33] == P9_PL_BUILD_ID,
        "pl_profile_id": words[34] == 0x00701022,
        "pl_register_map_version": words[35] == EXPECTED_REGISTER_MAP_VERSION,
        "pl_register_map_hash": words[36] == EXPECTED_REGISTER_MAP_HASH_LOW,
        "pl_capabilities": words[37] == 0xF7204221,
        "dma_base": words[39] == 0x40400000,
        "dma_scatter_gather": words[40] == 1,
        "descriptor_alignment": words[49] == 64,
        "cache_line": words[50] == 32,
        "pl_snapshot_id": pl(words, 0) == 0x50395A10,
    }
    for key, ok in checks.items():
        if not ok: errors.append(f"{label}: {key}")
    status = pl(words, 7)
    if status & 0x1: errors.append(f"{label}: endpoint remained armed")
    if not status & 0x2: errors.append(f"{label}: final TX kill was not active")
    if status & ((1 << 2) | (1 << 7) | (1 << 9)):
        errors.append(f"{label}: object/raw/receiver remained active after command")
    phy = pl(words, 8)
    if (phy >> 8) & 0xF: errors.append(f"{label}: sticky physical safety fault")
    high_max = [pl(words, i) for i in range(61, 65)]
    duty_max = [pl(words, i) for i in range(65, 69)]
    hard_faults = [pl(words, i) for i in range(81, 85)]
    window_cycles = pl(words, 85)
    hard_limit, target_limit = pl(words, 86), pl(words, 87)
    if any(value > 64 for value in high_max): errors.append(f"{label}: >1us continuous-high observation")
    if any(hard_faults): errors.append(f"{label}: hard duty fault count nonzero")
    if (window_cycles, hard_limit, target_limit) != (
            P9_DUTY_WINDOW_CYCLES, P9_DUTY_HARD_MAX_HIGH_CYCLES,
            P9_DUTY_TARGET_MAX_HIGH_CYCLES):
        errors.append(f"{label}: exact duty telemetry is not 64000/12799/11520 cycles")
    if any(value > hard_limit for value in duty_max): errors.append(f"{label}: strict 20% duty boundary violated")
    if any(value > target_limit for value in duty_max): errors.append(f"{label}: 18% design target exceeded")
    if words[96] or words[97] or words[98]: errors.append(f"{label}: descriptor double completion/leak")

    post_shutdown_tx_sequence_base = pl(words, 22)
    post_shutdown_window_status = pl(words, 23)
    terminal_window_valid = (
        words[TERMINAL_WINDOW_START] == P9_TERMINAL_WINDOW_VALID
        and words[TERMINAL_WINDOW_START + 1] == words[6]
    )
    terminal_tx_sequence_base = (
        words[TERMINAL_WINDOW_START + 2]
        if terminal_window_valid else post_shutdown_tx_sequence_base
    )
    terminal_window_status = (
        words[TERMINAL_WINDOW_START + 3]
        if terminal_window_valid else post_shutdown_window_status
    )
    detail: dict[str, Any] = {
        "label": label, "command": command, "expected_status": expected_status,
        "lane_mask": row["lane"], "direction": row["direction"],
        "rate_select": row["rate"], "requested_size": row["size"],
        "window": row.get("window", "NA"),
        "observed_status": words[8], "service_state": words[3],
        "elapsed_ticks": (words[58] << 32) | words[57],
        "counts_per_second": words[59], "actual_rx_length": words[60],
        "input_crc32": words[61], "output_crc32": words[62],
        "input_sha256": digest(words, 63), "output_sha256": digest(words, 71),
        "first_mismatch_offset": words[79], "descriptor_leak": words[98],
        "cache_flush_count": words[100], "cache_invalidate_count": words[101],
        "memory_barrier_count": words[102], "dma_reset_count": words[106],
        "cache_enabled_exercised": words[103], "cache_disabled_exercised": words[104],
        "misaligned_transfer_handled": words[105],
        "dma_reset_while_queued_count": words[107],
        "object_abort_count": words[108], "pl_soft_reset_count": words[109],
        "shutdown_attempt_count": words[110], "shutdown_verified_count": words[111],
        "pl_status": status, "phy_status": phy, "tx_high_max_cycles": high_max,
        "object_config_readback": pl(words, 10),
        "lane_weights_readback": pl(words, 11),
        "raw_config_readback": pl(words, 16),
        "duty_window_cycles": window_cycles,
        "duty_hard_max_high_cycles": hard_limit,
        "duty_target_max_high_cycles": target_limit,
        "duty_max_cycles": duty_max, "duty_hard_faults": hard_faults,
        "raw_rx": [pl(words, i) for i in range(53, 57)],
        "physical_tx": [pl(words, i) for i in range(57, 61)],
        "physical_data_good": pl(words, 39), "physical_ack_good": pl(words, 40),
        "physical_crc_bad": pl(words, 41), "physical_frame_bad": pl(words, 96),
        "physical_symbol_errors": pl(words, 98), "tx_attempts": pl(words, 25),
        "tx_retries": pl(words, 26), "retry_exhausted": pl(words, 27),
        "tx_timeouts": pl(words, 28), "tx_migrations": pl(words, 29),
        "rx_duplicates": pl(words, 30), "ack_aggregation": pl(words, 31),
        "ack_frames": pl(words, 33), "scheduler_frames": [pl(words, 44), pl(words, 45)],
        "scheduler_bytes": [pl(words, 46), pl(words, 47)],
        "scheduler_retries": [pl(words, 48), pl(words, 49)],
        "scheduler_migrations": [pl(words, 50), pl(words, 51)],
        "tx_ring_indices": [words[84], words[85]],
        "rx_ring_indices": [words[86], words[87]],
        "tx_ring_generations": [words[88], words[89]],
        "rx_ring_generations": [words[90], words[91]],
        "ring_full_observed": [words[92], words[93]],
        "ring_empty_observed": [words[94], words[95]],
        "terminal_window_valid": terminal_window_valid,
        "terminal_window_command_sequence": words[TERMINAL_WINDOW_START + 1],
        "terminal_tx_sequence_base": words[TERMINAL_WINDOW_START + 2],
        "terminal_window_status": words[TERMINAL_WINDOW_START + 3],
        "post_shutdown_tx_sequence_base": post_shutdown_tx_sequence_base,
        "post_shutdown_window_status": post_shutdown_window_status,
        "window_status": terminal_window_status, "sack_bitmap": pl(words, 24),
        "outstanding_count": (terminal_window_status >> 16) & 0x3F,
        "outstanding_high_watermark": (terminal_window_status >> 22) & 0x3F,
        "tx_next_sequence": terminal_tx_sequence_base & 0xFFFF,
        "tx_ack_base": (terminal_tx_sequence_base >> 16) & 0xFFFF,
        "rx_base_sequence": terminal_window_status & 0xFFFF,
        "rx_stale_session": pl(words, 37), "rx_stale_path": pl(words, 38),
        "rx_out_of_order": pl(words, 90), "rx_old": pl(words, 91),
        "rx_future": pl(words, 92), "rx_delivery": pl(words, 94),
        "rx_protocol_errors": pl(words, 95),
        "physical_preamble": pl(words, 97),
        "dropped_data": pl(words, 42), "dropped_ack": pl(words, 43),
        "duplicate_acks": pl(words, 34), "stale_acks": pl(words, 35),
        "out_of_window_acks": pl(words, 36), "rx_gaps": pl(words, 93),
        "payload_prepare_ticks": (words[216] << 32) | words[215],
        "dma_tx_completion_ticks": (words[218] << 32) | words[217],
        "dma_rx_completion_ticks": (words[220] << 32) | words[219],
        "pl_completion_ticks": (words[222] << 32) | words[221],
        "integrity_verify_ticks": (words[224] << 32) | words[223],
        "object_runtime_ticks": (words[226] << 32) | words[225],
        "permit_tx_before_drop": words[227:231],
        "permit_tx_after_drop": words[231:235],
        "permit_tx_after_rearm": words[235:239],
        "permit_status_after_drop": words[239],
        "permit_status_after_rearm": words[240],
        "permit_raw_sent": words[241:244],
        "permit_result_flags": words[244],
        "rfap_mode": words[245], "rfap_fragment_count": words[246],
        "rfap_useful_bytes": words[247], "rfap_validation_pass": words[248],
        "rfap_partial_publish_count": words[249],
        "rfap_atomic_publish_count": words[250],
        "rfap_useful_crc32": words[251],
    }

    if command == 2 and expected_status == 0:
        target, lane, direction = row["rawtarget"], row["lane"], row["direction"]
        if detail["raw_config_readback"] != ((lane & 3) | ((direction & 1) << 8)):
            errors.append(f"{label}: raw lane/direction readback mismatch")
        if pl(words, 19) != target: errors.append(f"{label}: raw sent count mismatch")
        expected_tx = [0, 0, 0, 0]; expected_rx = [0, 0, 0, 0]
        for lane_index in range(2):
            if lane & (1 << lane_index):
                expected_tx[(2 if direction else 0) + lane_index] = target
                # The frozen current-board profile has deterministic same-lane
                # visibility at both endpoint receivers.  Requiring both
                # counts to equal the transmitted target also proves that the
                # destination count has neither loss nor extras while keeping
                # the opposite logical lane at zero.
                expected_rx[lane_index] = target
                expected_rx[2 + lane_index] = target
        detail["raw_rx_observation_policy"] = P9_RAW_RX_OBSERVATION_POLICY
        detail["expected_raw_rx"] = expected_rx
        if detail["physical_tx"] != expected_tx: errors.append(f"{label}: physical TX raw vector mismatch")
        if detail["raw_rx"] != expected_rx: errors.append(f"{label}: physical RX raw vector mismatch")
    if command == 3 and expected_status == 0 and not (row["flags"] & 1 and words[60] == 0):
        if not terminal_window_valid:
            errors.append(f"{label}: pre-shutdown terminal window snapshot missing or unbound")
        size = row["size"]
        transfer_bytes = rfap_transfer_bytes(row)
        expected_config = (row["lane"] & 3) | ((row["rate"] & 3) << 8) | \
            ((row["direction"] & 1) << 16)
        if detail["object_config_readback"] != expected_config or \
                detail["lane_weights_readback"] != (row["weights"] & 0xFFFF):
            errors.append(f"{label}: lane/rate/direction/weight readback mismatch")
        if words[60] != transfer_bytes or pl(words, 20) != transfer_bytes or pl(words, 21) != transfer_bytes:
            errors.append(f"{label}: object byte count mismatch")
        if words[61] != words[62] or digest(words, 63) != digest(words, 71):
            errors.append(f"{label}: CRC/SHA mismatch")
        if words[79] != 0xFFFFFFFF: errors.append(f"{label}: payload mismatch offset set")
        intentional_crc_injection = bool(row["faultflags"] & (1 << 4))
        if detail["physical_symbol_errors"] or (
                not intentional_crc_injection and
                (detail["physical_crc_bad"] or detail["physical_frame_bad"])):
            errors.append(f"{label}: physical frame/CRC/symbol error")
        if detail["retry_exhausted"]: errors.append(f"{label}: retry exhausted in successful object")
        expected_frames = math.ceil(transfer_bytes / 247)
        if row["dropdata"] == 0 and row["dropack"] == 0 and row["faultflags"] == 0 and row["unavailable"] == 0 and row["injectmask"] == 0:
            if detail["physical_data_good"] != expected_frames:
                errors.append(f"{label}: clean physical data-frame count mismatch")
        expected_rfap_mode = 1 if row["flags"] & 4 else 2 if row["flags"] & 8 else 0
        if expected_rfap_mode:
            expected_fragments = math.ceil(size / (215 if expected_rfap_mode == 1 else 65536))
            if detail["rfap_mode"] != expected_rfap_mode or \
                    detail["rfap_fragment_count"] != expected_fragments or \
                    detail["rfap_useful_bytes"] != size or \
                    detail["rfap_validation_pass"] != 1 or \
                    detail["rfap_partial_publish_count"] != 0 or \
                    detail["rfap_atomic_publish_count"] != 1:
                errors.append(f"{label}: RFAP parser/reassembly/atomic-publish evidence mismatch")
    elif command == 3 and expected_status == 0 and row["flags"] & 1:
        if words[60] != 0 or pl(words, 21) != 0:
            errors.append(f"{label}: expected object failure published output")
        if not (pl(words, 7) & (1 << 4)) and pl(words, 9) == 0:
            errors.append(f"{label}: expected object failure lacked PL failure evidence")
    if command == 7 and row["flags"] & (4 | 8):
        expected_mode = 1 if row["flags"] & 4 else 2
        if detail["rfap_mode"] != expected_mode or \
                detail["rfap_partial_publish_count"] != 0 or \
                detail["rfap_atomic_publish_count"] != 0:
            errors.append(f"{label}: aborted RFAP object was partially/atomically published")
    if command == 12 and expected_status == 0:
        if detail["permit_result_flags"] != 0x3F:
            errors.append(f"{label}: permit-drop diagnostic flags incomplete")
        if not detail["permit_status_after_drop"] & 0x2 or \
                detail["permit_status_after_drop"] & (0x1 | 0x80):
            errors.append(f"{label}: disarm did not force kill and stop raw transmission")
        if not detail["permit_status_after_rearm"] & 0x1 or \
                detail["permit_status_after_rearm"] & 0x80:
            errors.append(f"{label}: explicit re-arm state/no-resume check failed")
        if detail["permit_tx_after_drop"] != detail["permit_tx_after_rearm"] or \
                detail["permit_raw_sent"][1] != detail["permit_raw_sent"][2]:
            errors.append(f"{label}: partial raw train resumed after re-arm")
    return errors, detail


def ack_loss_recovery_errors(detail: dict[str, Any], expected_frames: int,
                             initial_sequence: int = 0) -> list[str]:
    """Require direct loss plus an exactly drained selective-repeat object.

    A later cumulative ACK may cover a lost ACK before the oldest frame reaches
    RTO, so retry_count is intentionally not part of this proof.  Cases that
    specifically require a retransmission impose that requirement separately.
    """
    errors: list[str] = []
    label = detail["label"]
    expected_final = (initial_sequence + expected_frames) & 0xFFFF
    if detail["dropped_ack"] == 0:
        errors.append(f"{label}: injected ACK loss was not directly counted")
    if detail["ack_aggregation"] == 0 or detail["physical_ack_good"] == 0:
        errors.append(f"{label}: cumulative ACK recovery was not directly observed")
    if detail["ack_frames"] != detail["physical_ack_good"] + detail["dropped_ack"]:
        errors.append(f"{label}: emitted/received/dropped ACK accounting mismatch")
    if detail["tx_attempts"] != expected_frames + detail["tx_retries"]:
        errors.append(f"{label}: DATA attempt/retry accounting mismatch")
    if detail["rx_delivery"] != expected_frames:
        errors.append(f"{label}: exactly-once delivery count mismatch")
    if detail["outstanding_count"] != 0:
        errors.append(f"{label}: terminal TX window did not drain")
    if (detail["tx_next_sequence"], detail["tx_ack_base"],
            detail["rx_base_sequence"]) != (expected_final,) * 3:
        errors.append(
            f"{label}: terminal sequence state did not drain to "
            f"0x{expected_final:04X}"
        )
    if detail["retry_exhausted"] != 0:
        errors.append(f"{label}: ACK-loss recovery exhausted retries")
    return errors


def write_stage_raw_evidence(stage: str, stage_dir: Path,
                             rows: list[dict[str, Any]],
                             details: list[dict[str, Any]]) -> dict[str, str]:
    by_label = {detail["label"]: detail for detail in details}
    paths: dict[str, str] = {}
    if stage in {"P9-08", "P9-09", "P9-10", "P9-11", "P9-12"}:
        records = []
        for row in rows:
            detail = by_label.get(row["label"])
            if detail is None or row["command"] == 10:
                continue
            records.append({
                "label": row["label"], "lane_mask": row["lane"],
                "direction": row["direction"], "target": row["rawtarget"],
                "raw_sent": detail["permit_raw_sent"][0] if row["command"] == 12 else
                            (row["rawtarget"] if row["command"] == 2 else 0),
                **{f"raw_rx_module_{i}": value for i, value in enumerate(detail["raw_rx"])},
                **{f"physical_tx_module_{i}": value for i, value in enumerate(detail["physical_tx"])},
                "preamble_count": detail["physical_preamble"],
                "data_frames_good": detail["physical_data_good"],
                "ack_frames_good": detail["physical_ack_good"],
                "crc_bad": detail["physical_crc_bad"],
                "frame_bad": detail["physical_frame_bad"],
                "symbol_errors": detail["physical_symbol_errors"],
            })
        path = stage_dir / "raw_counter_matrix.csv"
        write_csv(path, records); paths["raw_counter_matrix"] = rel(path)

    object_records = []
    for row in rows:
        detail = by_label.get(row["label"])
        if detail is None or row["command"] not in {3, 7}:
            continue
        object_records.append({
            "label": row["label"], "command": row["command"],
            "direction": row["direction"], "lane_mask": row["lane"],
            "rate_select": row["rate"], "object_id": row["object"],
            "requested_useful_bytes": row["size"],
            "actual_dma_rx_bytes": detail["actual_rx_length"],
            "input_crc32": detail["input_crc32"], "output_crc32": detail["output_crc32"],
            "input_sha256": detail["input_sha256"], "output_sha256": detail["output_sha256"],
            "first_mismatch_offset": detail["first_mismatch_offset"],
            "rfap_mode": detail["rfap_mode"],
            "rfap_fragment_count": detail["rfap_fragment_count"],
            "rfap_validation_pass": detail["rfap_validation_pass"],
            "partial_publish_count": detail["rfap_partial_publish_count"],
            "atomic_publish_count": detail["rfap_atomic_publish_count"],
            "rfap_useful_crc32": detail["rfap_useful_crc32"],
            "descriptor_leak": detail["descriptor_leak"],
        })
    if object_records:
        path = stage_dir / "object_integrity_manifest.json"
        write_json(path, {"schema_version": 1, "stage": stage,
                          "objects": object_records})
        paths["object_integrity_manifest"] = rel(path)

    if stage == "P9-18":
        records = []
        for row in rows:
            detail = by_label.get(row["label"])
            if detail is None or row["command"] == 10:
                continue
            records.append({
                "label": row["label"], "fault_flags": row["faultflags"],
                "drop_data_request": row["dropdata"], "drop_ack_request": row["dropack"],
                **{key: detail[key] for key in (
                    "dropped_data", "dropped_ack", "tx_attempts", "tx_retries",
                    "retry_exhausted", "tx_timeouts", "duplicate_acks",
                    "rx_duplicates", "rx_stale_session", "rx_stale_path",
                    "rx_out_of_order", "rx_old", "rx_future", "rx_gaps",
                    "physical_crc_bad", "rx_protocol_errors")},
            })
        path = stage_dir / "fault_injection_trace.csv"
        write_csv(path, records); paths["fault_injection_trace"] = rel(path)

    if stage in {"P9-13", "P9-14", "P9-15", "P9-24"}:
        rate_table = {
            0: (1_000_000, 32, 8, 0, 31),
            1: (2_000_000, 16, 8, 0, 15),
            2: (4_000_000, 8, 8, 3, 4),
        }
        records = []
        for row in rows:
            detail = by_label.get(row["label"])
            if detail is None or row["command"] != 3:
                continue
            raw_bps, chip_cycles, pulse_cycles, rx_start, rx_end = \
                rate_table[row["rate"]]
            seconds = detail["object_runtime_ticks"] / detail["counts_per_second"] \
                if detail["counts_per_second"] and detail["object_runtime_ticks"] else 0.0
            transfer_bytes = rfap_transfer_bytes(row)
            data_frames = math.ceil(transfer_bytes / 247)
            data_air_bits = data_frames * 256 + transfer_bytes * 8
            ack_air_bits = detail["ack_frames"] * 192
            records.append({
                "label": row["label"], "lane_mask": row["lane"],
                "active_lane_count": int(row["lane"]).bit_count(),
                "direction": row["direction"], "rate_select": row["rate"],
                "configured_raw_bps_per_lane": raw_bps,
                "configured_aggregate_raw_bps": raw_bps * int(row["lane"]).bit_count(),
                "chip_cycles": chip_cycles, "tx_pulse_cycles": pulse_cycles,
                "rx_pulse_window_min_cycles": rx_start,
                "rx_pulse_window_max_cycles": rx_end,
                "frame_admission_duty_guard_cycles": P9_FRAME_DUTY_GUARD_CYCLES,
                "frame_admission_duty_guard_us": P9_FRAME_DUTY_GUARD_US,
                "useful_bytes": row["size"], "encoded_transfer_bytes": transfer_bytes,
                "data_frames": data_frames, "ack_frames": detail["ack_frames"],
                "theoretical_data_air_bits": data_air_bits,
                "theoretical_ack_air_bits": ack_air_bits,
                "theoretical_serial_airtime_seconds": (data_air_bits + ack_air_bits) / raw_bps,
                "ps_command_seconds": detail["elapsed_ticks"] / detail["counts_per_second"]
                    if detail["counts_per_second"] else 0.0,
                "object_runtime_seconds": seconds,
                "frame_goodput_bps": transfer_bytes * 8 / seconds if seconds else 0.0,
                "application_goodput_bps": row["size"] * 8 / seconds if seconds else 0.0,
                "ps_to_ps_useful_goodput_bps": row["size"] * 8 / seconds if seconds else 0.0,
                "payload_prepare_ticks": detail["payload_prepare_ticks"],
                "dma_tx_completion_ticks": detail["dma_tx_completion_ticks"],
                "dma_rx_completion_ticks": detail["dma_rx_completion_ticks"],
                "pl_completion_ticks": detail["pl_completion_ticks"],
                "integrity_verify_ticks": detail["integrity_verify_ticks"],
                "window_high_watermark": (detail["window_status"] >> 22) & 0x3F,
                "tx_attempts": detail["tx_attempts"], "tx_retries": detail["tx_retries"],
                "scheduler_lane0_frames": detail["scheduler_frames"][0],
                "scheduler_lane1_frames": detail["scheduler_frames"][1],
            })
        path = stage_dir / ("performance_characterization.csv" if stage == "P9-24"
                            else "phy_rate_characterization.csv")
        write_csv(path, records); paths["rate_performance"] = rel(path)
        if stage == "P9-24":
            skip = stage_dir / "CPU_LOAD_SKIPPED.txt"
            skip.write_text("CPU_LOAD=SKIP_WITH_REASON_BAREMETAL_NOT_INSTRUMENTED\n",
                            encoding="ascii", newline="\n")
            paths["cpu_load"] = rel(skip)
    return paths


def evaluate_stage(stage: str, stage_dir: Path, process: dict[str, Any],
                   raw_result: Path) -> dict[str, Any]:
    errors: list[str] = []
    markers = parse_markers(raw_result)
    if process["returncode"] != 0: errors.append(f"XSDB return code {process['returncode']}")
    if markers.get("P9_XSDB_STAGE_RESULT") != "PASS": errors.append("XSDB PASS marker absent")
    if markers.get("P9_CANDIDATE_PROGRAMMED") != "1": errors.append("candidate program marker absent")
    if markers.get("P9_PS_ELF_DOWNLOADED") != "1": errors.append("PS ELF download marker absent")
    if markers.get("P9_ENDPOINT_SHUTDOWN") != "PASS": errors.append("endpoint shutdown marker absent")
    observation_path = stage_dir / "mailbox/observations.psv"
    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    if not observation_path.is_file():
        errors.append("mailbox observation index missing")
    else:
        try:
            rows = load_observations(observation_path)
            for row in rows:
                dump = Path(row["dump_path"])
                if not dump.is_absolute(): dump = ROOT / dump
                if not dump.is_file():
                    errors.append(f"{row['label']}: mailbox dump missing")
                    continue
                case_errors, detail = evaluate_observation(row, parse_mailbox(dump))
                errors.extend(case_errors); details.append(detail)
        except (OSError, ValueError, KeyError, struct.error) as exc:
            errors.append(f"observation parse failure: {exc}")
    non_shutdown = [row for row in rows if row.get("command") != 10]
    if not non_shutdown: errors.append("stage executed no test commands")

    if stage in {"P9-09", "P9-10", "P9-11", "P9-12"}:
        if [row.get("rawtarget") for row in non_shutdown] != [64, 1000, 4096]:
            errors.append("raw 64/1000/4096 progression missing")
    if stage == "P9-08":
        idle = [detail for detail in details if detail["label"] == "p9_08_idle_noise_5000ms"]
        if len(idle) != 1:
            errors.append("frozen 5-second raw-idle observation missing")
        else:
            observation = idle[0]
            if any(value > 16 for value in observation["raw_rx"]):
                errors.append("raw-idle pulse threshold exceeded (frozen maximum 16/module/5s)")
            if any((observation["physical_preamble"], observation["physical_data_good"],
                    observation["physical_ack_good"], observation["physical_crc_bad"],
                    observation["physical_frame_bad"], observation["physical_symbol_errors"])):
                errors.append("raw-idle false preamble/frame/CRC/symbol threshold exceeded")
    if stage in {"P9-13", "P9-14"}:
        acceptance = [row for row in non_shutdown if row["size"] == 247 * 10_000]
        if len(acceptance) != 6: errors.append("not all direction/rate 10,000-frame cases ran")
        expected_lane = 1 if stage == "P9-13" else 2
        required_suffixes = {"fixed_short", "prbs", "zero", "one", "increment",
                             "binary", "100f", "10000f"}
        for direction in (0, 1):
            for rate in (0, 1, 2):
                matching = [row for row in non_shutdown if row["direction"] == direction and
                            row["rate"] == rate and row["lane"] == expected_lane]
                suffixes = {next((suffix for suffix in required_suffixes
                                  if row["label"].endswith("_" + suffix)), "")
                            for row in matching}
                if suffixes != required_suffixes:
                    errors.append(f"direction {direction} rate {rate}: frozen PHY pattern matrix incomplete")
    if stage == "P9-15":
        for detail in details:
            if detail["command"] == 3 and (detail["scheduler_frames"][0] == 0 or detail["scheduler_frames"][1] == 0):
                errors.append(f"{detail['label']}: both lanes were not scheduled")
    if stage == "P9-16":
        protocol = [detail for detail in details if detail["command"] == 3]
        if not protocol or max(detail["outstanding_high_watermark"] for detail in protocol) != 32:
            errors.append("selective-repeat outstanding high-watermark did not reach exactly 32")
        for detail in protocol:
            expected_frames = math.ceil(detail["requested_size"] / 247)
            if detail["rx_delivery"] != expected_frames:
                errors.append(f"{detail['label']}: exactly-once delivery count mismatch")
            if detail["label"].startswith("sr_wrap_"):
                expected_final = (0xFFFE + expected_frames) & 0xFFFF
                if (detail["tx_next_sequence"], detail["tx_ack_base"],
                        detail["rx_base_sequence"]) != (expected_final,) * 3:
                    errors.append(f"{detail['label']}: modular wrap did not drain to 0x{expected_final:04X}")
    if stage == "P9-17":
        if not any(detail["ack_aggregation"] > 0 and detail["physical_data_good"] > detail["ack_frames"] for detail in details):
            errors.append("ACK aggregation was not directly observed")
        by_label = {detail["label"]: detail for detail in details}
        ack_loss = by_label.get("sack_ack_loss_recovery")
        bitmap_loss = by_label.get("sack_ack_bitmap_loss")
        duplicate = by_label.get("sack_duplicate_ack")
        reorder = by_label.get("sack_reorder")
        if not ack_loss:
            errors.append("ACK-loss recovery observation absent")
        else:
            errors.extend(ack_loss_recovery_errors(
                ack_loss, math.ceil(ack_loss["requested_size"] / 247)))
        if not bitmap_loss or bitmap_loss["dropped_ack"] == 0:
            errors.append("SACK/ACK bitmap-loss injection counter absent")
        if not duplicate or duplicate["duplicate_acks"] == 0:
            errors.append("duplicate-ACK rejection counter absent")
        if not reorder or reorder["rx_out_of_order"] == 0:
            errors.append("SACK reorder evidence absent")
    if stage == "P9-18":
        by_label = {detail["label"]: detail for detail in details}
        direct_requirements = {
            "fault_drop_one_data": ("dropped_data", 1),
            "fault_drop_burst_data": ("dropped_data", 3),
            "fault_drop_ack": ("dropped_ack", 1),
            "fault_duplicate_data_by_ack_loss": ("rx_duplicates", 1),
            "fault_stale_session": ("rx_stale_session", 1),
            "fault_stale_path": ("rx_stale_path", 1),
            "fault_future_sequence": ("rx_future", 1),
            "fault_old_sequence": ("rx_old", 1),
            "fault_crc_corruption": ("physical_crc_bad", 1),
            "fault_duplicate_ack": ("duplicate_acks", 1),
            "fault_reorder": ("rx_out_of_order", 1),
        }
        for case_label, (field, minimum) in direct_requirements.items():
            detail = by_label.get(case_label)
            if not detail or detail[field] < minimum:
                errors.append(f"{case_label}: direct {field} counter evidence absent")
        for case_label in ("fault_drop_ack", "fault_duplicate_data_by_ack_loss"):
            detail = by_label.get(case_label)
            if detail:
                errors.extend(ack_loss_recovery_errors(
                    detail, math.ceil(detail["requested_size"] / 247)))
        for case_label, detail in by_label.items():
            # Receive-side idempotence/SACK cases can drain cumulatively, and
            # recovery-control/clean-verification cases do not inject a fault.
            if (p9_fault_requires_retry_evidence(case_label)
                    and detail["tx_retries"] == 0):
                errors.append(f"{case_label}: injected fault did not exercise bounded retry")
        exhausted = [detail for detail in details if detail["label"] == "fault_retry_exhausted"]
        if not exhausted or exhausted[0]["retry_exhausted"] == 0 or exhausted[0]["tx_timeouts"] == 0:
            errors.append("controlled retry exhaustion evidence absent")
        recovery_reset = [detail for detail in details
                          if detail["label"] == "fault_recovery_soft_reset"]
        if not recovery_reset or recovery_reset[0]["pl_soft_reset_count"] == 0:
            errors.append("post-fault PL recovery reset evidence absent")
        recovery = [detail for detail in details if detail["label"] == "fault_post_recovery_clean"]
        if not recovery or any((recovery[0]["physical_crc_bad"], recovery[0]["retry_exhausted"],
                                recovery[0]["descriptor_leak"])):
            errors.append("post-fault clean recovery absent")
    if stage == "P9-19":
        dma_details = [detail for detail in details if detail["command"] != 10]
        if not dma_details or max(detail["cache_flush_count"] for detail in dma_details) == 0 or max(detail["cache_invalidate_count"] for detail in dma_details) == 0 or max(detail["memory_barrier_count"] for detail in dma_details) == 0:
            errors.append("cache ownership operations not observed")
        if not dma_details or max(detail["cache_enabled_exercised"] for detail in dma_details) == 0 or max(detail["cache_disabled_exercised"] for detail in dma_details) == 0:
            errors.append("both cache-enabled and cache-disabled paths were not exercised")
        if not dma_details or max(detail["misaligned_transfer_handled"] for detail in dma_details) == 0:
            errors.append("misaligned DMA transfer was not handled")
        if not dma_details or max(min(detail["tx_ring_generations"] + detail["rx_ring_generations"]) for detail in dma_details) < 1:
            errors.append("producer/consumer ring wrap generation was not observed")
        if not dma_details or not all(max(detail["ring_full_observed"][index] if index < 2 else detail["ring_empty_observed"][index - 2] for detail in dma_details) for index in range(4)):
            errors.append("ring full/empty observations incomplete")
        if not dma_details or any(max(detail[field] for detail in dma_details) == 0 for field in ("dma_reset_count", "dma_reset_while_queued_count", "object_abort_count", "pl_soft_reset_count")):
            errors.append("DMA reset/queued reset/abort/PL reset recovery coverage incomplete")
        for name in ("tx_bd_ring.bin", "rx_bd_ring.bin"):
            descriptor_dump = stage_dir / "mailbox" / name
            if not descriptor_dump.is_file() or descriptor_dump.stat().st_size != 4096:
                errors.append(f"real descriptor memory snapshot missing: {name}")
        if markers.get("P9_REBOOT_PASS") != "ps_application_restart": errors.append("PS application restart marker absent")
    if stage == "P9-20":
        by_label = {detail["label"]: detail for detail in details}
        equal = by_label.get("sched_equal")
        if not equal or abs(equal["scheduler_bytes"][0] - equal["scheduler_bytes"][1]) > 247 * 4:
            errors.append("equal-weight scheduler fairness outside frozen bound")
        one_three = by_label.get("sched_1_to_3")
        three_one = by_label.get("sched_3_to_1")
        if not one_three or one_three["scheduler_bytes"][1] <= one_three["scheduler_bytes"][0]:
            errors.append("1:3 scheduler ordering absent")
        if not three_one or three_one["scheduler_bytes"][0] <= three_one["scheduler_bytes"][1]:
            errors.append("3:1 scheduler ordering absent")
        if one_three and one_three["scheduler_bytes"][0] and not 2.5 <= \
                one_three["scheduler_bytes"][1] / one_three["scheduler_bytes"][0] <= 3.5:
            errors.append("1:3 scheduler ratio outside frozen tolerance")
        if three_one and three_one["scheduler_bytes"][1] and not 2.5 <= \
                three_one["scheduler_bytes"][0] / three_one["scheduler_bytes"][1] <= 3.5:
            errors.append("3:1 scheduler ratio outside frozen tolerance")
        migration = by_label.get("retry_migration")
        if not migration or migration["tx_migrations"] == 0:
            errors.append("unacknowledged retry migration absent")
        lane_expectations = {
            "sched_lane0": (True, False), "sched_lane1": (False, True),
            "lane0_unavailable": (False, True), "lane1_unavailable": (True, False),
            "lane0_mapping_invalid": (False, True), "lane1_mapping_invalid": (True, False),
            "lane0_duty_throttle": (False, True), "lane1_duty_throttle": (True, False),
        }
        for case_label, active in lane_expectations.items():
            detail = by_label.get(case_label)
            if not detail:
                errors.append(f"{case_label}: scheduler evidence missing")
                continue
            for lane_index, should_be_active in enumerate(active):
                observed = detail["scheduler_frames"][lane_index] > 0
                if observed != should_be_active:
                    errors.append(f"{case_label}: lane {lane_index} scheduling mismatch")
        inflight = by_label.get("lane_fault_in_flight")
        if not inflight or inflight["scheduler_frames"][1] == 0 or inflight["actual_rx_length"] == 0:
            errors.append("in-flight lane-unavailable migration did not complete on healthy lane")
        all_down = by_label.get("all_lanes_unavailable")
        if not all_down or all_down["actual_rx_length"] != 0 or all_down["rfap_atomic_publish_count"] != 0:
            errors.append("all-lanes-unavailable case published output")
        recovery = by_label.get("scheduler_recovery")
        if not recovery or min(recovery["scheduler_frames"]) == 0 or recovery["tx_migrations"] != 0:
            errors.append("scheduler clean recovery evidence absent")
        for case_label in ("sched_lane0", "sched_lane1", "sched_equal", "sched_1_to_3", "sched_3_to_1"):
            detail = by_label.get(case_label)
            if detail and detail["tx_migrations"] != 0:
                errors.append(f"{case_label}: acknowledged/clean frame migration observed")
    if stage in {"P9-21", "P9-22", "P9-23"}:
        rfap_details = [detail for detail in details if detail["rfap_mode"] in {1, 2}]
        if not rfap_details:
            errors.append("runtime RFAP parser/reassembly evidence absent")
        for detail in rfap_details:
            if detail["command"] == 3 and (detail["rfap_validation_pass"] != 1 or
                    detail["rfap_atomic_publish_count"] != 1 or
                    detail["rfap_partial_publish_count"] != 0):
                errors.append(f"{detail['label']}: RFAP atomic publish contract failed")
        if stage == "P9-21":
            rfap_by_label = {detail["label"]: detail for detail in details}
            aborted = rfap_by_label.get("rfap_v1_abort")
            restarted = rfap_by_label.get("rfap_v1_restart_clean")
            if not aborted or aborted["rfap_atomic_publish_count"] != 0 or \
                    aborted["rfap_partial_publish_count"] != 0:
                errors.append("RFAP v1 abort published a partial object")
            if not restarted or restarted["rfap_atomic_publish_count"] != 1:
                errors.append("RFAP v1 restart did not publish exactly once")
        if stage == "P9-22":
            sizes = {row["size"] for row in non_shutdown if row["command"] == 3}
            if not {4096, 65536, 1048576, 16 * 1024 * 1024}.issubset(sizes):
                errors.append("RFAP vNext 4KiB/64KiB/1MiB/16MiB matrix incomplete")
        if stage == "P9-23":
            directions = {row["direction"] for row in non_shutdown if row["command"] == 3}
            if directions != {0, 1}:
                errors.append("fresh bidirectional RFAP object matrix incomplete")
    if stage == "P9-24":
        perf = [detail for detail in details if detail["command"] == 3]
        if len(perf) != 12:
            errors.append("performance lane/direction/short/large matrix incomplete")
        for detail in perf:
            if any(detail[field] == 0 for field in (
                    "payload_prepare_ticks", "dma_tx_completion_ticks",
                    "dma_rx_completion_ticks", "pl_completion_ticks",
                    "integrity_verify_ticks", "object_runtime_ticks")):
                errors.append(f"{detail['label']}: direct PS/DMA/PL latency telemetry incomplete")
    if stage == "P9-25":
        elapsed = int(markers.get("P9_SOAK_ACTIVE_ELAPSED_MS", "0") or 0)
        active_start = int(markers.get("P9_SOAK_ACTIVE_START_MS", "0") or 0)
        warmup_end = int(markers.get("P9_SOAK_WARMUP_END_MS", "0") or 0)
        acceptance = [row for row in rows if row.get("window") == "ACCEPTANCE"]
        if not 1_800_000 <= elapsed <= 1_800_500: errors.append("30-minute active window not exact/bounded")
        if warmup_end - active_start < 300_000 or warmup_end - active_start > 300_500:
            errors.append("formal warm-up boundary was not 300 seconds")
        if markers.get("P9_SOAK_ACCEPTANCE_SECONDS") != "1500":
            errors.append("formal clean acceptance interval is not 1500 seconds")
        if not acceptance: errors.append("formal 1500-second clean acceptance subwindow absent")
        if any(row["started_ms"] < warmup_end for row in acceptance):
            errors.append("acceptance object began before the clean 1500-second boundary")
        for detail in details:
            if detail["label"].startswith("soak_") and "_acceptance_" in detail["label"]:
                if any((detail["physical_crc_bad"], detail["retry_exhausted"], detail["descriptor_leak"],
                        sum(detail["duty_hard_faults"]))):
                    errors.append(f"{detail['label']}: clean soak violation")
    raw_evidence = write_stage_raw_evidence(stage, stage_dir, rows, details)
    payload = {
        "schema_version": 1, "status": "PASS" if not errors else "FAIL",
        "test_id": f"{stage}-HARDWARE", "stage": stage,
        "process": process, "markers": markers, "observations": details,
        "observation_count": len(non_shutdown), "errors": errors,
        "raw_evidence": raw_evidence,
        "raw_result": rel(raw_result) if raw_result.is_file() else None,
        "observation_index": rel(observation_path) if observation_path.is_file() else None,
    }
    write_json(stage_dir / "stage_summary.json", payload)
    return payload


def invoke_stage(stage: str, run_root: Path, phase2: Path, paths: dict[str, Path],
                 plan: dict[str, Any], env: dict[str, str], abort_file: Path) -> dict[str, Any]:
    stage_dir = run_root / {
        "P9-06": "safe_idle", "P9-07": "safe_idle", "P9-08": "raw_lane_matrix",
        "P9-09": "raw_lane_matrix", "P9-10": "raw_lane_matrix",
        "P9-11": "raw_lane_matrix", "P9-12": "raw_lane_matrix",
        "P9-13": "phy_rate", "P9-14": "phy_rate", "P9-15": "phy_rate",
        "P9-16": "selective_repeat", "P9-17": "sack_ack",
        "P9-18": "fault_injection", "P9-19": "dma_ddr_cache",
        "P9-20": "scheduler", "P9-21": "rfap", "P9-22": "rfap",
        "P9-23": "rfap", "P9-24": "performance", "P9-25": "stationary_30min",
    }[stage] / stage.replace("-", "_").lower()
    mailbox = stage_dir / "mailbox"
    raw_result = stage_dir / "xsdb_stage_result.txt"
    stdout = run_root / "raw_logs" / f"{stage.lower().replace('-', '_')}.stdout.log"
    stderr = run_root / "raw_logs" / f"{stage.lower().replace('-', '_')}.stderr.log"
    command = [str(XSDB), str(STAGE_TCL), XSDB_URL, EXPECTED_BOARD_ID,
               str(paths["candidate"]), str(paths["elf"]), str(paths["ps7_init"]),
               str(plan["path"]), str(mailbox), str(abort_file), str(raw_result),
               stage, str(phase2), str(json.loads(phase2.read_text(encoding="utf-8"))["run_id"])]
    # P9-25 contains an exact 1800 s active window plus immutable programming,
    # PS boot, mailbox capture and endpoint shutdown outside that active test.
    timeout = 2100 if stage == "P9-25" else 900 if stage in {"P9-13", "P9-14", "P9-22"} else 600
    process = run_bounded(command, stdout, stderr, timeout=timeout, env=env,
                          abort_file=abort_file,
                          active_limit=1800 if stage == "P9-25" else None)
    return evaluate_stage(stage, stage_dir, process, raw_result)


def evidence_manifest(run_root: Path) -> dict[str, Any]:
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    files = [{"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
             for path in sorted(item for item in run_root.rglob("*")
                                if item.is_file() and item != manifest_path)]
    generated = [{"path": rel(path), "bytes": path.stat().st_size,
                  "sha256": sha256(path)}
                 for path in sorted(list(GENERATED.glob("p9_*.json")) +
                                    list(GENERATED.glob("p9_*.md")))]
    canonical_paths = [
        ROOT / "config/project_state.json",
        ROOT / "config/project_requirements.yaml",
        ROOT / "PROJECT_STATUS.md",
        ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md",
    ]
    canonical = [{"path": rel(path), "bytes": path.stat().st_size,
                  "sha256": sha256(path)} for path in canonical_paths if path.is_file()]
    payload = {"schema_version": 1, "status": "PASS", "test_id": "P9-EVID-001-MANIFEST",
               "generated_utc": utc_now(), "run_id": run_root.name,
               "files": files, "file_count": len(files),
               "generated_summaries": generated,
               "generated_summary_count": len(generated),
               "canonical_state_files": canonical,
               "canonical_state_file_count": len(canonical)}
    write_json(manifest_path, payload)
    return payload


def summary_status(stage_results: dict[str, dict[str, Any]], stages: Iterable[str]) -> str:
    values = [stage_results.get(stage, {}).get("status", "NOT_RUN") for stage in stages]
    return "PASS" if values and all(value == "PASS" for value in values) else "FAIL" if any(value == "FAIL" for value in values) else "NOT_RUN"


def write_final_summary_files(run_root: Path, final: dict[str, Any]) -> None:
    """Keep the run-local and canonical P9 final JSON/Markdown byte-aligned."""
    write_json(run_root / "final/p9_final_summary.json", final)
    markdown_lines = ["# P9 Z7010 Stationary 2-lane Final", "", "```text"]
    for key, value in final.items():
        if key in {"PASS", "FAIL", "SKIP_WITH_REASON", "GENERATED_SUMMARIES",
                   "UNCHANGED_PENDING_SCOPES", "mandatory_gates", "stage_status"}:
            continue
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
        markdown_lines.append(f"{key}: {rendered}")
    pass_list = final.get("PASS", [])
    fail_list = final.get("FAIL", [])
    skips = final.get("SKIP_WITH_REASON", {})
    pending = final.get("UNCHANGED_PENDING_SCOPES", {})
    markdown_lines += ["```", "", "## PASS", ""] + [f"- `{item}`" for item in pass_list]
    markdown_lines += ["", "## FAIL", ""] + ([f"- `{item}`" for item in fail_list] or ["- None"])
    markdown_lines += ["", "## SKIP_WITH_REASON", ""] + [f"- `{key}={value}`" for key, value in skips.items()]
    markdown_lines += ["", "## Unchanged pending scopes", ""] + [f"- `{key}={value}`" for key, value in pending.items()]
    markdown = "\n".join(markdown_lines) + "\n"
    (run_root / "final/p9_final_summary.md").write_text(
        markdown, encoding="utf-8", newline="\n")
    write_pair("p9_final_summary", "P9 Z7010 Stationary 2-lane Final", final)
    (GENERATED / "p9_final_summary.md").write_text(
        markdown, encoding="utf-8", newline="\n")


def publish_summaries(record: dict[str, Any], paths: dict[str, Path], run_root: Path,
                      stage_results: dict[str, dict[str, Any]], shutdowns: list[dict[str, Any]],
                      preflight: dict[str, Any], campaign_errors: list[str],
                      hardware_actions_executed: bool) -> dict[str, Any]:
    run_id = record["run_id"]; source = record["source_commit"]
    common = {"schema_version": 1, "run_id": run_id, "source_commit": source,
              "profile": EXPECTED_PROFILE, "part": EXPECTED_PART,
              "candidate_sha256": record["candidate_bitstream"]["sha256"],
              "shutdown_sha256": record["shutdown_bitstream"]["sha256"],
              "ps_elf_sha256": record["ps_elf"]["sha256"]}
    before_shutdowns = [item for item in shutdowns if item.get("label") == "p9_05_shutdown_image"
                        or str(item.get("label", "")).endswith("_before")]
    after_shutdowns = [item for item in shutdowns if item.get("label") == "p9_26_final"
                       or str(item.get("label", "")).endswith("_after")
                       or item.get("label") == "finally_emergency"]
    shutdown_before_status = "PASS" if before_shutdowns and all(
        item.get("status") == "PASS" for item in before_shutdowns) else "FAIL"
    shutdown_after_status = "PASS" if after_shutdowns and all(
        item.get("status") == "PASS" for item in after_shutdowns) else "FAIL"
    safe_boot_status = summary_status(stage_results, ["P9-06"])
    shutdown_status = "PASS" if shutdown_before_status == shutdown_after_status == \
        safe_boot_status == "PASS" and all(
            item.get("status") == "PASS" for item in shutdowns) else "FAIL"

    write_pair("p9_authorization_summary", "P9 Current-run Authorization", {
        **common, "status": "PASS", "test_id": "P9-HW-003",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": True,
        "HARDWARE_ACTIONS_EXECUTED": hardware_actions_executed,
        "phase2_authorization": rel(run_root / "authorization/phase2_immutable_artifacts.json"),
        "phase2_sha256": sha256(run_root / "authorization/phase2_immutable_artifacts.json"),
        "maximum_single_test_seconds": 1800, "lane_masks": [1, 2, 3],
    })
    specifications = [
        ("p9_target_identity_summary", "P9 Target Identity", "P9-04-TARGET-IDENTITY", preflight.get("status", "NOT_RUN"), {"target_identity": preflight}),
        ("p9_safe_idle_summary", "P9 Safe Idle and Boot", "P9-HW-002", summary_status(stage_results, ["P9-06", "P9-08"]), {"stages": {k: stage_results.get(k) for k in ("P9-06", "P9-08")}}),
        ("p9_tfdu_safety_summary", "P9 TFDU Safety", "P9-SAFE-001", summary_status(stage_results, ["P9-07"]), {"stages": {"P9-07": stage_results.get("P9-07")}, "GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION": "PENDING_D17"}),
        ("p9_raw_lane_matrix_summary", "P9 Raw Lane Matrix", "P9-PHY-001", summary_status(stage_results, ["P9-08", "P9-09", "P9-10", "P9-11", "P9-12"]), {"stages": {k: stage_results.get(k) for k in ("P9-08", "P9-09", "P9-10", "P9-11", "P9-12")}}),
        ("p9_phy_4mbps_summary", "P9 4 Mbit/s per Lane PHY", "P9-PHY-002", summary_status(stage_results, ["P9-13", "P9-14", "P9-15"]), {"stages": {k: stage_results.get(k) for k in ("P9-13", "P9-14", "P9-15")}, "aggregate_raw_capability_bps": 8_000_000}),
        ("p9_selective_repeat_summary", "P9 Selective Repeat", "P9-L2-001", summary_status(stage_results, ["P9-16"]), {"stages": {"P9-16": stage_results.get("P9-16")}}),
        ("p9_sack_ack_summary", "P9 SACK and ACK Aggregation", "P9-L2-002", summary_status(stage_results, ["P9-17", "P9-18"]), {"stages": {k: stage_results.get(k) for k in ("P9-17", "P9-18")}}),
        ("p9_dma_ddr_cache_summary", "P9 Real DMA DDR Cache", "P9-DMA-001", summary_status(stage_results, ["P9-19"]), {"stages": {"P9-19": stage_results.get("P9-19")}}),
        ("p9_scheduler_migration_summary", "P9 Scheduler and Migration", "P9-L3-001", summary_status(stage_results, ["P9-20"]), {"stages": {"P9-20": stage_results.get("P9-20")}}),
        ("p9_rfap_runtime_summary", "P9 RFAP Runtime", "P9-RFAP-001", summary_status(stage_results, ["P9-21", "P9-22", "P9-23"]), {"stages": {k: stage_results.get(k) for k in ("P9-21", "P9-22", "P9-23")}, "rfap_64m": "SKIP_WITH_REASON_AXI_DMA_26_BIT_MAX_TRANSFER_IS_0x03ffffff"}),
        ("p9_performance_summary", "P9 Performance Characterization", "P9-PERF-001", summary_status(stage_results, ["P9-24"]), {"stages": {"P9-24": stage_results.get("P9-24")}, "application_goodput_target": "PENDING_WITH_EXPLICIT_2LANE_MODEL_GAP"}),
        ("p9_stationary_30min_summary", "P9 Stationary 30-minute Soak", "P9-SOAK-001", summary_status(stage_results, ["P9-25"]), {"stages": {"P9-25": stage_results.get("P9-25")}}),
    ]
    for stem, title, test_id, status, extra in specifications:
        write_pair(stem, title, {**common, "status": status, "test_id": test_id, **extra})
    write_pair("p9_shutdown_summary", "P9 Shutdown", {**common, "status": shutdown_status,
               "test_id": "P9-HW-002-SHUTDOWN", "shutdown_attempts": shutdowns,
               "SAFE_BOOT": safe_boot_status,
               "SHUTDOWN_BEFORE": shutdown_before_status,
               "SHUTDOWN_AFTER": shutdown_after_status,
               "SHUTDOWN_EXIT": 0 if shutdown_status == "PASS" else 1})
    required_pairs = [item[0] for item in specifications] + [
        "p9_authorization_summary", "p9_shutdown_summary"]
    missing_pairs = [stem for stem in required_pairs if not (GENERATED / f"{stem}.json").is_file() or not (GENERATED / f"{stem}.md").is_file()]
    required_stages = [f"P9-{number:02d}" for number in range(4, 27)]
    evidence_status = "PASS" if hardware_actions_executed and not campaign_errors and \
        not missing_pairs and shutdown_status == "PASS" and all(
            stage_results.get(stage, {}).get("status") == "PASS"
            for stage in required_stages) else "FAIL"
    consistency = {**common, "status": evidence_status, "test_id": "P9-EVID-001",
                   "run_manifest_path": rel(run_root / "final/run_evidence_sha256_manifest.json"),
                   "manifest_written_last": True,
                   "required_summary_pairs": required_pairs,
                   "missing_summary_pairs": missing_pairs,
                   "required_stages": required_stages,
                   "stage_status": {stage: stage_results.get(stage, {}).get("status", "NOT_RUN")
                                    for stage in required_stages},
                   "shutdown_before": shutdown_before_status,
                   "shutdown_after": shutdown_after_status,
                   "single_formal_run_id": run_id,
                   "campaign_errors": campaign_errors}
    write_json(run_root / "final/p9_evidence_consistency.json", consistency)
    write_pair("p9_evidence_consistency_summary", "P9 Evidence Consistency", consistency)

    all_details = [detail for result in stage_results.values()
                   for detail in result.get("observations", [])]
    soak_details = stage_results.get("P9-25", {}).get("observations", [])
    soak_markers = stage_results.get("P9-25", {}).get("markers", {})
    perf_details = [detail for detail in stage_results.get("P9-24", {}).get("observations", [])
                    if detail.get("command") == 3 and detail.get("lane_mask") == 3 and
                    detail.get("requested_size", 0) >= 1_048_576]
    frame_rates: list[float] = []
    application_rates: list[float] = []
    for detail in perf_details:
        ticks = detail.get("object_runtime_ticks", 0)
        frequency = detail.get("counts_per_second", 0)
        if ticks and frequency:
            seconds = ticks / frequency
            frame_rates.append(detail.get("actual_rx_length", 0) * 8 / seconds)
            application_rates.append(detail.get("rfap_useful_bytes", 0) * 8 / seconds)
    frame_goodput = sum(frame_rates) / len(frame_rates) if frame_rates else None
    application_goodput = sum(application_rates) / len(application_rates) if application_rates else None
    runtime_seconds = int(soak_markers.get("P9_SOAK_ACTIVE_ELAPSED_MS", "0") or 0) / 1000
    objects_completed = sum(1 for detail in soak_details
                            if detail.get("command") == 3 and
                            detail.get("rfap_atomic_publish_count") == 1)
    bytes_committed = sum(detail.get("rfap_useful_bytes", 0) for detail in soak_details
                          if detail.get("command") == 3 and
                          detail.get("rfap_atomic_publish_count") == 1)

    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    artifact_hashes = {item.get("logical_name"): item.get("sha256")
                       for item in manifest.get("artifacts", []) if isinstance(item, dict)}
    gate_values = {
        "P8E_BASELINE_RECHECK": "PASS",
        "P9_OFFLINE_REGRESSION": "PASS",
        "P9_ARTIFACT_PROVENANCE": "PASS",
        "P9_CURRENT_RUN_AUTHORIZATION": "PASS",
        "P9_TARGET_IDENTITY": preflight.get("status", "NOT_RUN"),
        "P9_SAFE_IDLE": summary_status(stage_results, ["P9-08"]),
        "P9_SAFE_BOOT": summary_status(stage_results, ["P9-06"]),
        "P9_SHUTDOWN_BEFORE": shutdown_before_status,
        "P9_SHUTDOWN_AFTER": shutdown_after_status,
        "Z7010_TFDU_STARTUP_WAIT": summary_status(stage_results, ["P9-07"]),
        "Z7010_CONTINUOUS_HIGH_GUARD": summary_status(stage_results, ["P9-07"]),
        "Z7010_EXACT_DUTY_INTERNAL_ACCOUNTING": summary_status(stage_results, ["P9-07"]),
        "Z7010_FINAL_RTL_TX_KILL": summary_status(stage_results, ["P9-07"]),
        "AB_L0_RAW": summary_status(stage_results, ["P9-09"]),
        "BA_L0_RAW": summary_status(stage_results, ["P9-10"]),
        "AB_L1_RAW": summary_status(stage_results, ["P9-11"]),
        "BA_L1_RAW": summary_status(stage_results, ["P9-12"]),
        "LANE0_4MBPS_RAW_CAPABILITY": summary_status(stage_results, ["P9-13"]),
        "LANE1_4MBPS_RAW_CAPABILITY": summary_status(stage_results, ["P9-14"]),
        "TWO_LANE_8MBPS_RAW_CAPABILITY": summary_status(stage_results, ["P9-15"]),
        "SELECTIVE_REPEAT_32_OUTSTANDING": summary_status(stage_results, ["P9-16"]),
        "SACK_WINDOW_32": summary_status(stage_results, ["P9-16", "P9-17"]),
        "SEQUENCE_WRAP": summary_status(stage_results, ["P9-16"]),
        "ACK_AGGREGATION": summary_status(stage_results, ["P9-17"]),
        "ACK_LOSS_RECOVERY": summary_status(stage_results, ["P9-17", "P9-18"]),
        "DUPLICATE_APPLICATION_DELIVERY_ZERO": summary_status(stage_results, ["P9-16", "P9-18"]),
        "STALE_SESSION_PATH_COMMIT_ZERO": summary_status(stage_results, ["P9-18"]),
        "REAL_AXI_DMA_DDR_RUNTIME": summary_status(stage_results, ["P9-19"]),
        "REAL_CACHE_OWNERSHIP": summary_status(stage_results, ["P9-19"]),
        "DESCRIPTOR_SINGLE_COMPLETION": summary_status(stage_results, ["P9-19"]),
        "DESCRIPTOR_LEAK_ZERO": summary_status(stage_results, ["P9-19"]),
        "RESET_ABORT_RECOVERY": summary_status(stage_results, ["P9-19"]),
        "TWO_LANE_SCHEDULER": summary_status(stage_results, ["P9-20"]),
        "LANE_FAULT_ISOLATION": summary_status(stage_results, ["P9-20"]),
        "RETRY_MIGRATION": summary_status(stage_results, ["P9-20"]),
        "ACKED_FRAME_NEVER_MIGRATES": summary_status(stage_results, ["P9-20"]),
        "PS_PL_PHY_PL_PS_RUNTIME": summary_status(stage_results, ["P9-21", "P9-22", "P9-23"]),
        "RFAP_V1_RUNTIME": summary_status(stage_results, ["P9-21"]),
        "RFAP_VNEXT_RUNTIME": summary_status(stage_results, ["P9-22"]),
        "A_TO_B_OBJECT": summary_status(stage_results, ["P9-23"]),
        "B_TO_A_OBJECT": summary_status(stage_results, ["P9-23"]),
        "OBJECT_CRC32": summary_status(stage_results, ["P9-21", "P9-22", "P9-23"]),
        "OBJECT_SHA256": summary_status(stage_results, ["P9-21", "P9-22", "P9-23"]),
        "PARTIAL_OBJECT_COMMIT_ZERO": summary_status(stage_results, ["P9-21", "P9-22", "P9-23"]),
        "PERFORMANCE_CHARACTERIZATION": summary_status(stage_results, ["P9-24"]),
        "STATIONARY_30MIN": summary_status(stage_results, ["P9-25"]),
        "EVIDENCE_CONSISTENCY": evidence_status,
    }
    pass_list = sorted(key for key, value in gate_values.items() if value == "PASS")
    fail_list = sorted(key for key, value in gate_values.items() if value != "PASS")
    pending = {
        "ETHERNET_LWIP_RUNTIME": "DEFERRED_NOT_REQUIRED_FOR_P9",
        "GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION": "PENDING_D17",
        "EXTERNAL_TFDU_DUTY_MEASUREMENT": "PENDING_EXTERNAL_MEASUREMENT",
        "REAL_OPTICAL_LINK_BUDGET": "PENDING_FINAL_GEOMETRY_AND_MEASUREMENT",
        "ABZ": "PENDING_HARDWARE", "PHYSICAL_HANDOVER": "PENDING_P11",
        "Z7020_TARGET_ACCEPTANCE": "PENDING_Z7020_HW",
        "ROTATION_ACCEPTANCE": "PENDING_FINAL_MECHANICAL",
        "FINAL_PRODUCT_HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    skips = {
        "CPU_LOAD": "SKIP_WITH_REASON_BAREMETAL_NOT_INSTRUMENTED",
        "UART": "SKIP_WITH_REASON_NO_UART_CORE_IN_FROZEN_CANDIDATE",
        "ILA_VIO": "SKIP_WITH_REASON_NO_ILA_OR_VIO_CORE_IN_FROZEN_CANDIDATE",
        "RFAP_64M": "SKIP_WITH_REASON_AXI_DMA_26_BIT_MAX_TRANSFER_IS_0x03ffffff",
    }
    generated_summaries = [f"evidence/generated/{stem}.json"
                           for stem in required_pairs + [
                               "p9_evidence_consistency_summary", "p9_final_summary"]]
    final_status = "PASS" if evidence_status == "PASS" and not fail_list else "FAIL"
    final = {**common, "generated_utc": utc_now(), "status": final_status,
             "test_id": "P9-FINAL", "P9_STATUS": final_status,
             "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION": final_status,
             "P8E_BASE_TAG": "p8e-pass",
             "P8E_BASE_CHECKPOINT": "57ff1079b10a5c0de156b621820774bbb111c5ee",
             "P9_SOURCE_COMMIT": source, "P9_EVIDENCE_CHECKPOINT": None,
             "P9_TAG": None, "BRANCH": git("branch", "--show-current"),
             "WORKTREE_CLEAN": False, "scope": EXPECTED_SCOPE,
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": True,
             "HARDWARE_ACTIONS_EXECUTED": hardware_actions_executed,
             "NO_HARDWARE_MOVEMENT": True, "MOTION_EXECUTED": False,
             "ROTATION_EXECUTED": False, "NETWORK_USED": False,
             "LOCALHOST_HW_SERVER_USED": True,
             "AVAILABLE_LANES": 2, "MAX_LANE_MASK_USED": "0x3",
             "TARGET_IDENTITY": gate_values["P9_TARGET_IDENTITY"],
             "ARTIFACT_PROVENANCE": gate_values["P9_ARTIFACT_PROVENANCE"],
             "SAFE_BOOT": gate_values["P9_SAFE_BOOT"],
             "SHUTDOWN_BEFORE": shutdown_before_status,
             "SHUTDOWN_AFTER": shutdown_after_status,
             "AB_L0_RAW": gate_values["AB_L0_RAW"], "BA_L0_RAW": gate_values["BA_L0_RAW"],
             "AB_L1_RAW": gate_values["AB_L1_RAW"], "BA_L1_RAW": gate_values["BA_L1_RAW"],
             "LANE0_4MBPS_RAW": gate_values["LANE0_4MBPS_RAW_CAPABILITY"],
             "LANE1_4MBPS_RAW": gate_values["LANE1_4MBPS_RAW_CAPABILITY"],
             "TWO_LANE_8MBPS_RAW_CAPABILITY": gate_values["TWO_LANE_8MBPS_RAW_CAPABILITY"],
             "SELECTIVE_REPEAT_32_OUTSTANDING": gate_values["SELECTIVE_REPEAT_32_OUTSTANDING"],
             "SACK_WINDOW_32": gate_values["SACK_WINDOW_32"],
             "SEQUENCE_WRAP": gate_values["SEQUENCE_WRAP"],
             "ACK_AGGREGATION": gate_values["ACK_AGGREGATION"],
             "RETRY_MIGRATION": gate_values["RETRY_MIGRATION"],
             "LANE_FAULT_ISOLATION": gate_values["LANE_FAULT_ISOLATION"],
             "REAL_AXI_DMA_DDR_RUNTIME": gate_values["REAL_AXI_DMA_DDR_RUNTIME"],
             "REAL_CACHE_OWNERSHIP": gate_values["REAL_CACHE_OWNERSHIP"],
             "DESCRIPTOR_SINGLE_COMPLETION": gate_values["DESCRIPTOR_SINGLE_COMPLETION"],
             "DESCRIPTOR_LEAK_ZERO": gate_values["DESCRIPTOR_LEAK_ZERO"],
             "PS_PL_PHY_PL_PS_RUNTIME": gate_values["PS_PL_PHY_PL_PS_RUNTIME"],
             "RFAP_V1_RUNTIME": gate_values["RFAP_V1_RUNTIME"],
             "RFAP_VNEXT_RUNTIME": gate_values["RFAP_VNEXT_RUNTIME"],
             "A_TO_B_OBJECT": gate_values["A_TO_B_OBJECT"],
             "B_TO_A_OBJECT": gate_values["B_TO_A_OBJECT"],
             "OBJECT_CRC32": gate_values["OBJECT_CRC32"],
             "OBJECT_SHA256": gate_values["OBJECT_SHA256"],
             "PARTIAL_OBJECT_COMMIT_ZERO": gate_values["PARTIAL_OBJECT_COMMIT_ZERO"],
             "PHY_RAW_BPS_LANE0": 4_000_000 if gate_values["LANE0_4MBPS_RAW_CAPABILITY"] == "PASS" else None,
             "PHY_RAW_BPS_LANE1": 4_000_000 if gate_values["LANE1_4MBPS_RAW_CAPABILITY"] == "PASS" else None,
             "TWO_LANE_RAW_CAPABILITY_BPS": 8_000_000 if gate_values["TWO_LANE_8MBPS_RAW_CAPABILITY"] == "PASS" else None,
             "FRAME_GOODPUT_BPS": frame_goodput,
             "APPLICATION_GOODPUT_BPS": application_goodput,
             "MODELED_APPLICATION_GOODPUT_BPS": None,
             "MEASURED_TO_MODEL_RATIO": None,
             "STATIONARY_30MIN": gate_values["STATIONARY_30MIN"],
             "RUNTIME_SECONDS": runtime_seconds,
             "OBJECTS_COMPLETED": objects_completed, "BYTES_COMMITTED": bytes_committed,
             "CRC_BAD": sum(detail.get("physical_crc_bad", 0) for detail in soak_details),
             "SHA_MISMATCH": sum(1 for detail in soak_details
                                  if detail.get("input_sha256") != detail.get("output_sha256")),
             "RETRY_EXHAUSTED": sum(detail.get("retry_exhausted", 0) for detail in soak_details),
             "DUTY_VIOLATION": sum(sum(detail.get("duty_hard_faults", [])) for detail in soak_details),
             "CONTINUOUS_HIGH_VIOLATION": sum(1 for detail in soak_details
                                               if max(detail.get("tx_high_max_cycles", [0])) > 64),
             "DESCRIPTOR_LEAK": sum(detail.get("descriptor_leak", 0) for detail in soak_details),
             "DEADLOCK": 0 if gate_values["STATIONARY_30MIN"] == "PASS" else 1,
             "BITSTREAM_SHA256": record["candidate_bitstream"]["sha256"],
             "SHUTDOWN_BITSTREAM_SHA256": record["shutdown_bitstream"]["sha256"],
             "XSA_SHA256": artifact_hashes.get("ir_p9_z7010_2lane.xsa"),
             "PS_ELF_SHA256": record["ps_elf"]["sha256"],
             "ACTIVE_XDC_SHA256": record["active_xdc_sha256"],
             "PINMAP_SHA256": record["pinmap_sha256"],
             "REGISTER_MAP_SHA256": record["register_map_sha256"],
             "PROJECT_STATE_SHA256": record["project_state_sha256"],
             "PROJECT_REQUIREMENTS_SHA256": record["project_requirements_sha256"],
             "PASS": pass_list, "FAIL": fail_list,
             "SKIP_WITH_REASON": skips, "GENERATED_SUMMARIES": generated_summaries,
             "UNCHANGED_PENDING_SCOPES": pending,
             "NEXT_RECOMMENDED_STAGE": "P10A_Z7020_SINGLE_BOARD_MIGRATION"
                 if final_status == "PASS" else "P9_DIAGNOSTIC_REMEDIATION",
             "mandatory_gates": gate_values,
             "campaign_errors": campaign_errors,
             "stage_status": {**{k: v.get("status") for k, v in stage_results.items()},
                              "P9-27": evidence_status},
             "evidence_manifest": rel(run_root / "final/run_evidence_sha256_manifest.json")}
    write_final_summary_files(run_root, final)
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--authorize-from", type=Path, required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--bitstream", type=Path)
    parser.add_argument("--shutdown-bitstream", type=Path)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--max-runtime", type=int, default=0)
    parser.add_argument("--lane-mask", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--stage", default="P9-04")
    parser.add_argument("--resume-diagnostic-from", default="")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    phase2 = args.authorize_from.resolve()
    record, paths, errors = validate_phase2(phase2)
    run_id = args.run_id or str(record.get("run_id", ""))
    if run_id != record.get("run_id"): errors.append("CLI run id differs from immutable authorization")
    if not RUN_RE.fullmatch(run_id): errors.append("run id invalid")
    if args.build_only: errors.append("--build-only is invalid in the hardware execution path")
    if args.stage != "P9-04": errors.append("formal hardware campaign must start at P9-04")
    if args.resume_diagnostic_from:
        errors.append("formal run cannot resume/stitch diagnostic evidence")
    if args.max_runtime != 1800:
        errors.append("formal maximum runtime must be explicitly 1800 seconds")
    if args.lane_mask != 3:
        errors.append("formal full two-lane campaign requires maximum lane mask 0x3")
    for supplied, key, label in (
        (args.bitstream, "candidate", "candidate bitstream"),
        (args.shutdown_bitstream, "shutdown", "shutdown bitstream"),
        (args.elf, "elf", "PS ELF"),
    ):
        if supplied is None:
            errors.append(f"formal CLI requires explicit {label} path")
        else:
            try:
                if supplied.resolve() != paths.get(key, Path("__missing__")).resolve():
                    errors.append(f"CLI {label} differs from phase-2 immutable path")
            except OSError:
                errors.append(f"CLI {label} path cannot be resolved")
    if args.formal and args.dry_run:
        errors.append("--formal and --dry-run are mutually exclusive")
    run_root = HW_ROOT / (run_id or "invalid_run_id")
    for directory in ("authorization", "artifacts", "target_identity", "safe_idle",
                      "raw_lane_matrix", "phy_rate", "selective_repeat", "sack_ack",
                      "dma_ddr_cache", "scheduler", "fault_injection", "rfap",
                      "performance", "stationary_30min", "shutdown", "raw_logs", "final"):
        (run_root / directory).mkdir(parents=True, exist_ok=True)
    abort_file = run_root / "authorization/ABORT_NOW.txt"
    if abort_file.exists(): errors.append("abort sentinel exists before campaign")
    plans = write_plans(run_root)
    auth_payload = {
        "schema_version": 1, "status": "PASS" if not errors else "FAIL",
        "test_id": "P9-HW-003", "run_id": run_id,
        "phase2_authorization": rel(phase2) if phase2.is_file() and inside(phase2, ROOT) else str(phase2),
        "phase2_sha256": sha256(phase2) if phase2.is_file() else None,
        "source_commit": record.get("source_commit"), "scope": record.get("scope"),
        "maximum_single_test_seconds": record.get("maximum_single_test_seconds"),
        "lane_masks": record.get("lane_masks"), "plan_sha256": {k: v["sha256"] for k, v in plans.items()},
        "errors": errors, "hardware_actions_executed": False,
    }
    write_json(run_root / "authorization/authorization_record.json", auth_payload)
    if DEFAULT_PHASE1.is_file(): shutil.copy2(DEFAULT_PHASE1, run_root / "authorization/phase1_user_authorization.json")
    if phase2.is_file() and phase2.resolve() != (run_root / "authorization/phase2_immutable_artifacts.json").resolve():
        shutil.copy2(phase2, run_root / "authorization/phase2_immutable_artifacts.json")
    write_pair("p9_authorization_summary", "P9 Current-run Authorization", auth_payload)

    if errors or args.dry_run or not args.execute_hardware or not args.formal:
        status = "PASS" if not errors and args.dry_run else "FAIL" if errors else "DRY_RUN_REQUIRED"
        summary = {**auth_payload, "status": status,
                   "test_id": "P9-03-AUTHORIZATION-DRY-RUN",
                   "dry_run": True, "hardware_actions_executed": False,
                   "refusal_reason": None if args.dry_run else "--execute-hardware --formal required"}
        write_json(run_root / "final/orchestrator_result.json", summary)
        write_pair("p9_authorization_summary", "P9 Current-run Authorization", summary)
        if args.json_summary: print(json.dumps(summary, sort_keys=True))
        return 0 if status == "PASS" else 1

    if os.environ.get("NO_HARDWARE", "1") != "0":
        summary = {**auth_payload, "status": "FAIL", "test_id": "P9-03-HARDWARE-ENABLE",
                   "errors": ["NO_HARDWARE must be explicitly set to 0 by the authorized wrapper"],
                   "hardware_actions_executed": False}
        write_json(run_root / "final/orchestrator_result.json", summary)
        if args.json_summary: print(json.dumps(summary, sort_keys=True))
        return 1

    (run_root / "raw_logs/UART_SKIPPED.txt").write_text(
        "UART=SKIP_WITH_REASON_NO_UART_CORE_IN_FROZEN_CANDIDATE\n",
        encoding="ascii", newline="\n")
    (run_root / "raw_logs/ILA_VIO_SKIPPED.txt").write_text(
        "ILA_VIO=SKIP_WITH_REASON_NO_ILA_OR_VIO_CORE_IN_FROZEN_CANDIDATE\n",
        encoding="ascii", newline="\n")
    (run_root / "authorization/NO_MOVEMENT_NETWORK_ATTESTATION.txt").write_text(
        "NO_HARDWARE_MOVEMENT=true\nROTATION_EXECUTED=false\n"
        "EXTERNAL_NETWORK_USED=false\nLOCALHOST_HW_SERVER_USED=true\n"
        "ETHERNET_REQUIRED=false\n",
        encoding="ascii", newline="\n")

    env = os.environ.copy(); env["RF_COMM_P9_HW_AUTH"] = "P9_PHASE2_IMMUTABLE_AUTHORIZED"
    stage_results: dict[str, dict[str, Any]] = {}
    shutdowns: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    preflight: dict[str, Any] = {"status": "NOT_RUN"}
    server_proc: subprocess.Popen[Any] | None = None
    hardware_actions = False
    try:
        server_proc, server = start_hw_server(run_root / "raw_logs")
        write_json(run_root / "target_identity/hw_server.json", server)
        if server["status"] != "PASS": raise RuntimeError(server.get("reason", "hw_server failed"))
        hardware_actions = True
        preflight = invoke_preflight(run_root, phase2, env, abort_file)
        stage_results["P9-04"] = preflight
        if preflight["status"] != "PASS": raise RuntimeError("P9-04 target identity failed")
        first_shutdown = invoke_shutdown(run_root, phase2, paths["shutdown"], "p9_05_shutdown_image", env, abort_file)
        shutdowns.append(first_shutdown); stage_results["P9-05"] = first_shutdown
        if first_shutdown["status"] != "PASS": raise RuntimeError("P9-05 shutdown image failed")
        for stage in (f"P9-{number:02d}" for number in range(6, 26)):
            before = invoke_shutdown(run_root, phase2, paths["shutdown"], f"{stage.lower().replace('-', '_')}_before", env, abort_file)
            shutdowns.append(before)
            if before["status"] != "PASS": raise RuntimeError(f"{stage} shutdown-before failed")
            result: dict[str, Any] = {"status": "FAIL", "errors": ["stage launch did not complete"]}
            after: dict[str, Any] = {"status": "FAIL", "errors": ["shutdown-after did not complete"]}
            try:
                result = invoke_stage(stage, run_root, phase2, paths, plans[stage], env, abort_file)
                stage_results[stage] = result
            finally:
                after = invoke_shutdown(run_root, phase2, paths["shutdown"], f"{stage.lower().replace('-', '_')}_after", env, abort_file)
                shutdowns.append(after)
            if result.get("status") != "PASS": raise RuntimeError(f"{stage} hardware validation failed")
            if after.get("status") != "PASS": raise RuntimeError(f"{stage} shutdown-after failed")
        final_shutdown = invoke_shutdown(run_root, phase2, paths["shutdown"], "p9_26_final", env, abort_file)
        shutdowns.append(final_shutdown); stage_results["P9-26"] = final_shutdown
        if final_shutdown["status"] != "PASS": raise RuntimeError("P9-26 final shutdown failed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except BaseException as exc:
        campaign_errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        emergency = invoke_shutdown(run_root, phase2, paths.get("shutdown", Path("missing")), "finally_emergency", env, abort_file) if paths.get("shutdown", Path()).is_file() else {"status": "FAIL", "reason": "shutdown artifact unavailable"}
        shutdowns.append(emergency)
        if emergency.get("status") != "PASS": campaign_errors.append("finally shutdown unconfirmed")
        if server_proc is not None: terminate_tree(server_proc)
    auth_payload["hardware_actions_executed"] = hardware_actions
    write_json(run_root / "authorization/authorization_record.json", auth_payload)
    final = publish_summaries(record, paths, run_root, stage_results, shutdowns,
                              preflight, campaign_errors, hardware_actions)
    write_json(run_root / "final/orchestrator_result.json", final)
    manifest = evidence_manifest(run_root)
    if args.json_summary: print(json.dumps(final, sort_keys=True))
    else: print(f"P9_STATUS={final['P9_STATUS']}\nP9_RUN_ID={run_id}")
    return 0 if final["P9_STATUS"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
