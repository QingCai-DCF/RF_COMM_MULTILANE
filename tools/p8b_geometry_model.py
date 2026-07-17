#!/usr/bin/env python3
"""P8B nominal closed-form and configurable 3-D optical geometry model."""

from __future__ import annotations

import itertools
import math
import random
from pathlib import Path
from statistics import fmean
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/geometry/optical_geometry.yaml"


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "schema_version", "geometry_profile", "rotor_radius_mm", "stator_radius_mm",
        "radial_gap_mm", "rotating_module_count", "fixed_module_count",
        "logical_lane_count", "sector_bank_count", "modules_per_bank",
        "rotating_spacing_deg", "fixed_spacing_deg", "fov_design_half_angle_deg",
        "max_abs_speed_rpm", "tolerances",
    }
    missing = sorted(required - set(data or {}))
    if missing:
        raise ValueError(f"missing geometry keys: {missing}")
    if data["schema_version"] != 1:
        raise ValueError("unsupported geometry schema")
    if data["rotor_radius_mm"] <= 0 or data["stator_radius_mm"] <= data["rotor_radius_mm"]:
        raise ValueError("radii must satisfy 0 < rotor < stator")
    if not math.isclose(
        data["stator_radius_mm"] - data["rotor_radius_mm"], data["radial_gap_mm"], abs_tol=1e-12
    ):
        raise ValueError("radial_gap_mm must equal stator_radius_mm - rotor_radius_mm")
    if (data["rotating_module_count"], data["fixed_module_count"], data["logical_lane_count"],
            data["sector_bank_count"], data["modules_per_bank"]) != (8, 32, 8, 8, 4):
        raise ValueError("P8B geometry must be 8 rotating / 32 fixed / 8 banks x 4")
    for name, record in data["tolerances"].items():
        if not isinstance(record, dict) or "value" not in record or "status" not in record:
            raise ValueError(f"invalid tolerance record: {name}")
        if record["value"] is None and not str(record["status"]).startswith("PENDING"):
            raise ValueError(f"unknown tolerance must remain PENDING: {name}")
    return data


def closed_form(r_mm: float, R_mm: float, delta_deg: float) -> dict[str, float]:
    delta = math.radians(delta_deg)
    length = math.sqrt(R_mm * R_mm + r_mm * r_mm - 2.0 * R_mm * r_mm * math.cos(delta))
    rot_arg = max(-1.0, min(1.0, (R_mm * math.cos(delta) - r_mm) / length))
    fix_arg = max(-1.0, min(1.0, (R_mm - r_mm * math.cos(delta)) / length))
    return {
        "path_length_mm": length,
        "rotating_incidence_angle_deg": math.degrees(math.acos(rot_arg)),
        "fixed_incidence_angle_deg": math.degrees(math.acos(fix_arg)),
    }


def _solve_delta_for_rotating_angle(r_mm: float, R_mm: float, limit_deg: float) -> float:
    lo, hi = 0.0, 45.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if closed_form(r_mm, R_mm, mid)["rotating_incidence_angle_deg"] < limit_deg:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def nominal_summary(config: dict[str, Any]) -> dict[str, Any]:
    r, R = float(config["rotor_radius_mm"]), float(config["stator_radius_mm"])
    delta_max = float(config["fixed_spacing_deg"]) / 2.0
    worst = closed_form(r, R, delta_max)
    limit_delta = _solve_delta_for_rotating_angle(r, R, float(config["fov_design_half_angle_deg"]))
    overlap = 2.0 * limit_delta - float(config["fixed_spacing_deg"])
    speed_deg_s = float(config["max_abs_speed_rpm"]) * 6.0
    return {
        "status": "PASS",
        "scope": "NOMINAL_MODEL_ONLY",
        "delta_max_nearest_deg": delta_max,
        "nominal_worst_path_length_mm": worst["path_length_mm"],
        "nominal_worst_rotating_angle_deg": worst["rotating_incidence_angle_deg"],
        "nominal_worst_fixed_angle_deg": worst["fixed_incidence_angle_deg"],
        "single_module_rotating_angle_limit_delta_deg": limit_delta,
        "nominal_two_module_overlap_deg": overlap,
        "nominal_overlap_time_at_600rpm_us": overlap / speed_deg_s * 1e6,
        "fixed_module_pitch_time_at_600rpm_us": float(config["fixed_spacing_deg"]) / speed_deg_s * 1e6,
    }


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = math.sqrt(sum(x * x for x in v))
    if n == 0:
        raise ValueError("zero optical-axis vector")
    return tuple(x / n for x in v)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _angle(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(_unit(a), _unit(b))))))


def evaluate_3d(config: dict[str, Any], delta_deg: float, perturb: dict[str, float] | None = None) -> dict[str, float]:
    """Evaluate positions/axis vectors with explicit 3-D perturbations.

    Perturbation keys are bounded inputs supplied by a caller; no missing canonical
    tolerance is converted to zero for acceptance. Zero defaults here describe the
    mathematical nominal evaluation only.
    """
    p = perturb or {}
    r = float(config["rotor_radius_mm"]) + p.get("thermal_radial_growth_mm", 0.0)
    R = float(config["stator_radius_mm"])
    rotor_angle = math.radians(p.get("rotor_module_angle_error_deg", 0.0))
    stator_angle = math.radians(delta_deg + p.get("stator_module_angle_error_deg", 0.0))
    cx = p.get("center_offset_x_mm", 0.0) + p.get("radial_eccentricity_x_mm", 0.0)
    cy = p.get("center_offset_y_mm", 0.0) + p.get("radial_eccentricity_y_mm", 0.0)
    z = p.get("axial_runout_mm", 0.0)
    rotor_pos = (cx + r * math.cos(rotor_angle), cy + r * math.sin(rotor_angle), z)
    fixed_pos = (R * math.cos(stator_angle), R * math.sin(stator_angle), 0.0)
    ray = tuple(f - q for f, q in zip(fixed_pos, rotor_pos))
    reverse_ray = tuple(-x for x in ray)
    rot_axis_angle = rotor_angle + math.radians(
        p.get("rotating_axis_error_deg", 0.0) + p.get("rotating_pcb_tilt_deg", 0.0)
    )
    fix_axis_angle = stator_angle + math.pi + math.radians(
        p.get("fixed_axis_error_deg", 0.0) + p.get("fixed_pcb_tilt_deg", 0.0)
    )
    rot_tilt_z = math.radians(p.get("rotating_tilt_z_deg", 0.0))
    fix_tilt_z = math.radians(p.get("fixed_tilt_z_deg", 0.0))
    rot_axis = _unit((math.cos(rot_axis_angle) * math.cos(rot_tilt_z), math.sin(rot_axis_angle) * math.cos(rot_tilt_z), math.sin(rot_tilt_z)))
    fix_axis = _unit((math.cos(fix_axis_angle) * math.cos(fix_tilt_z), math.sin(fix_axis_angle) * math.cos(fix_tilt_z), math.sin(fix_tilt_z)))
    effective = p.get("window_refraction_effective_deg", 0.0)
    baffle = p.get("baffle_occlusion_mask_deg", 0.0)
    return {
        "path_length_mm": math.sqrt(_dot(ray, ray)),
        "rotating_incidence_angle_deg": _angle(rot_axis, ray) + effective + baffle,
        "fixed_incidence_angle_deg": _angle(fix_axis, reverse_ray) + effective + baffle,
    }


def bounded_corner_sweep(config: dict[str, Any], bounds: dict[str, tuple[float, float]]) -> dict[str, Any]:
    if not bounds:
        return {"status": "PENDING_WITH_EXPLICIT_GAPS", "corner_count": 0, "reason": "no frozen finite tolerance bounds"}
    if len(bounds) > 16:
        raise ValueError("exact corner sweep limited to 16 independent bounded parameters")
    for name, bound in bounds.items():
        if len(bound) != 2 or not all(math.isfinite(float(x)) for x in bound) or bound[0] > bound[1]:
            raise ValueError(f"invalid finite bound for {name}")
    samples = []
    for values in itertools.product(*[(lo, hi) for lo, hi in bounds.values()]):
        perturb = dict(zip(bounds, values))
        samples.append((evaluate_3d(config, config["fixed_spacing_deg"] / 2.0, perturb), perturb))
    worst = max(samples, key=lambda x: max(x[0]["rotating_incidence_angle_deg"], x[0]["fixed_incidence_angle_deg"]))
    return {"status": "PASS", "method": "EXACT_FINITE_CORNER_ENUMERATION", "corner_count": len(samples), "worst": worst[0], "worst_parameters": worst[1]}


def deterministic_monte_carlo(config: dict[str, Any], bounds: dict[str, tuple[float, float]], seed: int, sample_count: int) -> dict[str, Any]:
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    if not bounds:
        return {"status": "PENDING_WITH_EXPLICIT_GAPS", "seed": seed, "sample_count": 0, "reason": "no frozen finite tolerance bounds"}
    rng = random.Random(seed)
    rows = []
    worst_row = None
    for _ in range(sample_count):
        p = {name: rng.uniform(float(lo), float(hi)) for name, (lo, hi) in bounds.items()}
        result = evaluate_3d(config, config["fixed_spacing_deg"] / 2.0, p)
        metric = max(result["rotating_incidence_angle_deg"], result["fixed_incidence_angle_deg"])
        rows.append(metric)
        if worst_row is None or metric > worst_row[0]:
            worst_row = (metric, p, result)
    ordered = sorted(rows)
    def percentile(q: float) -> float:
        pos = q * (len(ordered) - 1)
        lo, hi = int(math.floor(pos)), int(math.ceil(pos))
        return ordered[lo] if lo == hi else ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)
    return {
        "status": "PASS",
        "purpose": "RISK_AND_SENSITIVITY_NOT_WORST_CASE_GUARANTEE",
        "seed": seed,
        "sample_count": sample_count,
        "min": ordered[0], "max": ordered[-1], "mean": fmean(ordered),
        "p1": percentile(0.01), "p5": percentile(0.05), "p50": percentile(0.50),
        "p95": percentile(0.95), "p99": percentile(0.99),
        "worst_parameters": worst_row[1], "worst_result": worst_row[2],
    }


def gap_ledger(config: dict[str, Any]) -> list[dict[str, Any]]:
    sensitivity = {
        "radial_eccentricity_mm": "path length and both incidence angles",
        "axial_runout_mm": "3-D path length and out-of-plane incidence",
        "rotor_stator_center_offset_mm": "all lane phase and incidence symmetry",
        "rotor_module_angle_error_deg": "rotating-axis alignment and overlap",
        "stator_module_angle_error_deg": "nearest-module delta and overlap",
        "rotating_pcb_tilt_deg": "rotating incidence",
        "fixed_pcb_tilt_deg": "fixed incidence",
        "optical_axis_error_deg": "effective FOV margin",
        "window_refraction_model": "effective ray direction",
        "baffle_occlusion_angular_mask_deg": "usable overlap interval",
        "thermal_radial_growth_mm": "radial gap and incidence",
    }
    return [
        {
            "parameter": name,
            "current_status": record["status"],
            "value": record["value"],
            "why_needed": sensitivity.get(name, "3-D tolerance stack-up"),
            "later_gate": record.get("later_gate", "PENDING_OWNER"),
            "sensitivity": sensitivity.get(name, "geometry acceptance"),
            "blocking_scope": "FINAL_ROTATING_OPTICAL_HARDWARE_ACCEPTANCE",
        }
        for name, record in config["tolerances"].items() if record["value"] is None
    ]


if __name__ == "__main__":
    import json
    cfg = load_config()
    print(json.dumps(nominal_summary(cfg), indent=2))

