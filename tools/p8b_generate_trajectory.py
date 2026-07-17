#!/usr/bin/env python3
"""Generate deterministic phase/direction validity trajectories for P8B tests."""

from __future__ import annotations

import argparse
import json
import random

try:
    from tools.p8b_mapping_reference import Direction
except ModuleNotFoundError:  # Direct execution from tools/.
    from p8b_mapping_reference import Direction


DEFAULT_SEEDS = (1, 7, 17, 31, 127, 1024, 20260717)


def generate(seed: int, steps: int = 256) -> list[dict]:
    if steps < 32:
        raise ValueError("steps must be at least 32")
    rng = random.Random(seed)
    phase_mdeg = rng.randrange(360_000)
    direction = Direction.STOPPED
    rows = []
    for step in range(steps):
        if step % 37 == 0:
            direction = Direction.FORWARD
        elif step % 53 == 0:
            direction = Direction.REVERSE
        elif step % 29 == 0:
            direction = Direction.STOPPED
        rpm = 0 if direction == Direction.STOPPED else rng.randint(1, 600)
        sign = 1 if direction == Direction.FORWARD else -1 if direction == Direction.REVERSE else 0
        dt_us = 50 + rng.randint(-5, 5)
        phase_mdeg = (phase_mdeg + round(sign * rpm * 6.0 * dt_us)) % 360_000
        phase_valid = step % 43 != 0
        age_us = 300 if step % 61 == 0 else rng.randint(0, 60)
        encoder_fault = step % 97 == 0
        rows.append({
            "step": step, "seed": seed, "phase_mdeg": phase_mdeg,
            "phase_valid": phase_valid, "direction": direction.name,
            "direction_code": int(direction), "speed_abs_rpm": rpm,
            "sample_period_us": dt_us, "phase_data_age_us": age_us,
            "phase_uncertainty_mdeg": rng.randint(0, 100),
            "encoder_fault": encoder_fault,
        })
    return rows


def all_trajectories(steps: int = 256) -> dict:
    return {str(seed): generate(seed, steps) for seed in DEFAULT_SEEDS}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--steps", type=int, default=256)
    args = parser.parse_args()
    print(json.dumps(generate(args.seed, args.steps), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
