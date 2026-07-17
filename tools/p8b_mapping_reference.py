#!/usr/bin/env python3
"""Independent P8B 8-lane/32-fixed-module mapping reference model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum
from typing import Iterable


LANES = 8
FIXED_MODULES = 32
MODULES_PER_BANK = 4
BANKS = 8


class Direction(IntEnum):
    UNKNOWN = 0
    STOPPED = 1
    FORWARD = 2
    REVERSE = 3


@dataclass(frozen=True)
class Path:
    lane: int
    fixed_index: int
    bank: int
    slot: int


def _checked_m0(m0: int) -> int:
    if not isinstance(m0, int) or not 0 <= m0 < FIXED_MODULES:
        raise ValueError("m0 must be an integer in [0,31]")
    return m0


def _checked_lane(lane: int) -> int:
    if not isinstance(lane, int) or not 0 <= lane < LANES:
        raise ValueError("lane must be an integer in [0,7]")
    return lane


def path_for_fixed(lane: int, fixed_index: int) -> Path:
    _checked_lane(lane)
    if not 0 <= fixed_index < FIXED_MODULES:
        raise ValueError("fixed_index must be in [0,31]")
    return Path(lane, fixed_index, fixed_index // MODULES_PER_BANK, fixed_index % MODULES_PER_BANK)


def current_path(m0: int, lane: int) -> Path:
    m0 = _checked_m0(m0)
    lane = _checked_lane(lane)
    return path_for_fixed(lane, (m0 + MODULES_PER_BANK * lane) % FIXED_MODULES)


def candidate_path(m0: int, lane: int, direction: Direction | int) -> Path:
    current = current_path(m0, lane)
    try:
        direction = Direction(direction)
    except ValueError as exc:
        raise ValueError("invalid direction") from exc
    if direction == Direction.FORWARD:
        delta = 1
    elif direction == Direction.REVERSE:
        delta = -1
    else:
        raise ValueError("candidate requires FORWARD or REVERSE")
    return path_for_fixed(lane, (current.fixed_index + delta) % FIXED_MODULES)


def current_mapping(m0: int) -> tuple[Path, ...]:
    return tuple(current_path(m0, lane) for lane in range(LANES))


def candidate_mapping(m0: int, direction: Direction | int) -> tuple[Path, ...]:
    return tuple(candidate_path(m0, lane, direction) for lane in range(LANES))


def inverse_bank_owners(paths: Iterable[Path]) -> tuple[int, ...]:
    owners = [-1] * BANKS
    lane_seen = set()
    for path in paths:
        if path.lane in lane_seen or owners[path.bank] != -1:
            raise ValueError("mapping is not a lane/bank permutation")
        lane_seen.add(path.lane)
        owners[path.bank] = path.lane
    if len(lane_seen) != LANES or any(owner < 0 for owner in owners):
        raise ValueError("mapping is incomplete")
    return tuple(owners)


def validate_mapping(paths: Iterable[Path]) -> bool:
    paths = tuple(paths)
    if len(paths) != LANES:
        return False
    if sorted(path.lane for path in paths) != list(range(LANES)):
        return False
    if len({path.fixed_index for path in paths}) != LANES:
        return False
    if sorted(path.bank for path in paths) != list(range(BANKS)):
        return False
    return all(
        path.bank == path.fixed_index // MODULES_PER_BANK
        and path.slot == path.fixed_index % MODULES_PER_BANK
        for path in paths
    )


def exhaustive_records() -> list[dict]:
    records: list[dict] = []
    for m0 in range(FIXED_MODULES):
        current = current_mapping(m0)
        assert validate_mapping(current)
        assert inverse_bank_owners(current)
        q, s = m0 % MODULES_PER_BANK, (m0 // MODULES_PER_BANK) % BANKS
        for path in current:
            assert path.bank == (s + path.lane) % BANKS
            assert path.slot == q
        for direction in (Direction.FORWARD, Direction.REVERSE):
            candidate = candidate_mapping(m0, direction)
            assert validate_mapping(candidate)
            inverse_bank_owners(candidate)
            for lane, (cur, cand) in enumerate(zip(current, candidate)):
                records.append(
                    {
                        "m0": m0,
                        "direction": direction.name,
                        "direction_code": int(direction),
                        "lane": lane,
                        "current": asdict(cur),
                        "candidate": asdict(cand),
                    }
                )
    return records


def exhaustive_summary() -> dict:
    records = exhaustive_records()
    boundaries = {
        "q3_forward_to_slot0": candidate_path(3, 0, Direction.FORWARD).slot == 0,
        "q3_forward_bank_wrap": candidate_path(31, 0, Direction.FORWARD).bank == 0,
        "q0_reverse_to_slot3": candidate_path(0, 0, Direction.REVERSE).slot == 3,
        "q0_reverse_bank_wrap": candidate_path(0, 0, Direction.REVERSE).bank == 7,
        "s7_forward_to_s0": candidate_path(31, 0, Direction.FORWARD).fixed_index == 0,
        "s0_reverse_to_s7": candidate_path(0, 0, Direction.REVERSE).fixed_index == 31,
    }
    if not all(boundaries.values()):
        raise AssertionError(boundaries)
    return {
        "status": "PASS",
        "m0_states": FIXED_MODULES,
        "direction_specific_states": FIXED_MODULES * 2,
        "lane_current_tuples": FIXED_MODULES * LANES,
        "lane_candidate_tuples": len(records),
        "bank_inverse_maps_checked": FIXED_MODULES * 3,
        "q_values_checked": [0, 1, 2, 3],
        "s_values_checked": list(range(8)),
        "boundaries": boundaries,
    }


class EpochCommitModel:
    """Edge-qualified, modulo path-epoch commit reference model."""

    def __init__(self, width: int = 32):
        if width < 2:
            raise ValueError("epoch width must be at least 2")
        self.mask = (1 << width) - 1
        self.epoch = 0
        self._request_seen = False

    def step(self, request: bool, conditions_ok: bool) -> tuple[bool, bool]:
        accept = reject = False
        if not request:
            self._request_seen = False
        elif not self._request_seen:
            self._request_seen = True
            if conditions_ok:
                self.epoch = (self.epoch + 1) & self.mask
                accept = True
            else:
                reject = True
        return accept, reject

    def metadata_current(self, metadata_epoch: int) -> bool:
        return (metadata_epoch & self.mask) == self.epoch


if __name__ == "__main__":
    import json

    print(json.dumps(exhaustive_summary(), indent=2))

