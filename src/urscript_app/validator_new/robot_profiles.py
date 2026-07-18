"""Per-robot geometry profiles: reach, z-floor, joint limits.

Values are configurable defaults taken from public Universal Robots
datasheets. Verify against the official datasheet before relying on a
profile for a robot you actually deploy on; treat `z_floor_m` and
`min_reach_m` as site-specific tuning knobs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RobotProfile:
    """Static geometry of one robot model used by bounds checking (Stage 4)."""

    name: str
    reach_m: float
    min_reach_m: float | None = None
    # Below this z (in the base frame) the TCP is assumed to hit the table.
    z_floor_m: float = 0.0
    # Placeholder until Stage 4 wires joint-range checking; every e-Series
    # joint travels +/- 2*pi radians.
    joint_range_rad: tuple[float, float] = (-math.tau, math.tau)


DEFAULT_ROBOT = "UR5e"  # project default (see Stage 0 spec)

_PROFILES: dict[str, RobotProfile] = {
    "UR3e": RobotProfile(name="UR3e", reach_m=0.500),
    "UR5e": RobotProfile(name="UR5e", reach_m=0.850),
    "UR10e": RobotProfile(name="UR10e", reach_m=1.300),
    "UR16e": RobotProfile(name="UR16e", reach_m=0.900),
    "UR20": RobotProfile(name="UR20", reach_m=1.750),
    "UR30": RobotProfile(name="UR30", reach_m=1.300),
}


def get_profile(name: str = DEFAULT_ROBOT) -> RobotProfile:
    """Return the profile for `name`, raising `ValueError` on unknown robots."""
    try:
        return _PROFILES[name]
    except KeyError:
        raise ValueError(
            f"Unknown robot profile '{name}'. Valid: {sorted(_PROFILES)}"
        ) from None


def available_robots() -> tuple[str, ...]:
    """Sorted names of all known robot profiles."""
    return tuple(sorted(_PROFILES))
