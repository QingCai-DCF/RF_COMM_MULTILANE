# P8B geometry and mapping specification

## Scope

This specification defines the offline logic model for 8 rotating modules, 32 fixed modules, eight logical lanes and eight four-module sector banks. It is not final mechanical, optical, rotating or Z7020 hardware acceptance. The canonical numeric input is `config/geometry/optical_geometry.yaml`.

## Coordinate system

- The nominal stator center and rotation axis share the origin.
- Positive Z points toward an observer for whom positive angle is counter-clockwise.
- Every angle is normalized to `[0 deg, 360 deg)`.
- Rotating module `Rk` is at `theta + 45 deg*k`; fixed module `Fi` is at `11.25 deg*i`.
- The rotating optical axis points radially outward; the fixed optical axis points radially inward.
- Internal phase-to-module selection uses nearest fixed-module center. An exact half-pitch tie selects the lower fixed index. The selected integer is `m0`.
- `Lk` permanently denotes `Rk`; direction never renumbers a logical lane.

## Mapping equations

For `q=m0 mod 4` and `s=floor(m0/4) mod 8`:

```text
current_fixed(k) = (m0 + 4*k) mod 32
current_bank(k)  = (s + k) mod 8
current_slot(k)  = q
forward_candidate_fixed(k) = (current_fixed(k) + 1) mod 32
reverse_candidate_fixed(k) = (current_fixed(k) - 1) mod 32
```

Both current and direction-specific candidate mappings must be permutations of the eight banks and of eight distinct fixed modules. Inverse owners are derived explicitly; bank number is never assumed to equal lane number. The direct boundaries are `q=3 -> slot 0` forward and `q=0 -> slot 3` reverse, including `F31 -> F0` and `F0 -> F31`.

Direction is the four-state enum `UNKNOWN`, `STOPPED`, `FORWARD`, `REVERSE`. Current mapping depends only on absolute phase. A predictive candidate is prepared only for `FORWARD` or `REVERSE`; `STOPPED` is deliberately non-predictive and `UNKNOWN` is invalid. Reversal invalidates the old shadow context and requires a new prepare plus atomic commit.

## Geometry equations

With rotor radius `r`, stator radius `R` and center-angle difference `delta`:

```text
path_length = sqrt(R^2 + r^2 - 2*R*r*cos(delta))
rotating_incidence = acos((R*cos(delta)-r)/path_length)
fixed_incidence    = acos((R-r*cos(delta))/path_length)
```

At `r=100 mm`, `R=300 mm` and the nearest-module worst delta `5.625 deg`, the model directly checks 200.720991 mm, 8.424011 deg and 2.799011 deg. Solving the rotating incidence equation at the provisional 12 deg design line gives delta 8.025994 deg, nominal adjacent-module overlap 4.801987 deg, overlap time 1333.885 us at 600 rpm, and fixed pitch time 3125 us.

The 3-D model uses position and optical-axis vectors. It accepts eccentricity X/Y, axial runout Z, center offset, module placement errors, PCB tilt, optical-axis error, effective window refraction, baffle mask and thermal radial growth. Exact corner enumeration is performed only when every swept input has a finite bound. Seeded Monte Carlo is sensitivity evidence, never a mathematical worst-case guarantee.

All current canonical tolerance values are `null/PENDING`. Therefore nominal model implementation may pass while worst-case geometry acceptance remains `PENDING_WITH_EXPLICIT_GAPS`.

