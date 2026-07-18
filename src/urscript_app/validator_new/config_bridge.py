"""Single source of truth for motion limits, bridged from the app `Settings`.

Limit values (max joint/TCP velocity and acceleration) live in
`urscript_app.config.Settings`; this module is the only place the validator
reads them from, so the app and the validator can never disagree.

The validator must stay importable stand-alone (e.g. inside a dataset
pipeline without the FastAPI app configured), so any failure to import or
instantiate the app settings falls back to conservative defaults that
mirror the `Settings` field defaults.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionLimits:
    """Motion limits used by bounds checking (Stage 4)."""

    max_joint_velocity: float  # rad/s
    max_joint_accel: float  # rad/s^2
    max_tcp_velocity: float  # m/s
    max_tcp_accel: float  # m/s^2


# Mirrors the defaults of `urscript_app.config.Settings`; used only when the
# app config cannot be loaded (stand-alone validator usage).
FALLBACK_LIMITS = MotionLimits(
    max_joint_velocity=1.05,
    max_joint_accel=1.4,
    max_tcp_velocity=0.5,
    max_tcp_accel=1.2,
)


def get_motion_limits() -> MotionLimits:
    """Return the active motion limits, preferring the app `Settings`."""
    try:
        from urscript_app.config import get_settings

        settings = get_settings()
    except Exception:
        # Import or instantiation failed (missing deps, bad .env, ...):
        # keep the validator usable stand-alone with safe defaults.
        return FALLBACK_LIMITS
    return MotionLimits(
        max_joint_velocity=settings.max_joint_velocity,
        max_joint_accel=settings.max_joint_accel,
        max_tcp_velocity=settings.max_tcp_velocity,
        max_tcp_accel=settings.max_tcp_accel,
    )
