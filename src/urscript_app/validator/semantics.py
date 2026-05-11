"""Semantic checks: dangerous functions, motion parameter bounds."""
from __future__ import annotations
import re
import math
from urscript_app.validator.result import Diagnostic
from urscript_app.config import get_settings

# Functions explicitly banned regardless of 'include all commands'
_BANNED = {
    "socket_open", "socket_close", "socket_send_string", "socket_read_string",
    "socket_send_byte", "socket_read_byte", "socket_send_int", "socket_read_int",
    "exec", "eval",
}

# Motion functions whose 'a' and 'v' kwargs we validate
_MOTION_FUNCS = {"movej", "movel", "movep", "movec", "speedj", "speedl"}

_CALL_RE = re.compile(r'\b(\w+)\s*\(')
_KW_RE = re.compile(r'\b(a|v)\s*=\s*(-?\d+\.?\d*(?:e[+-]?\d+)?)')
_LIST_RE = re.compile(r'\[([^\]]*)\]')


def _parse_floats(s: str) -> list[float]:
    nums = re.findall(r'-?\d+\.?\d*(?:e[+-]?\d+)?', s)
    return [float(n) for n in nums]


def check_semantics(source: str) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    s = get_settings()

    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # Banned function calls
        for m in _CALL_RE.finditer(stripped):
            fname = m.group(1)
            if fname in _BANNED:
                diags.append(Diagnostic("error", f"Disallowed function '{fname}'", lineno))

        # Motion parameter bounds
        for m in _CALL_RE.finditer(stripped):
            fname = m.group(1)
            if fname not in _MOTION_FUNCS:
                continue
            kwargs = dict((k, float(v)) for k, v in _KW_RE.findall(stripped))
            if "a" in kwargs:
                limit = s.max_joint_accel if fname in {"movej", "speedj"} else s.max_tcp_accel
                if kwargs["a"] > limit:
                    diags.append(Diagnostic("error", f"'{fname}' acceleration {kwargs['a']} exceeds limit {limit}", lineno))
            if "v" in kwargs:
                limit = s.max_joint_velocity if fname in {"movej", "speedj"} else s.max_tcp_velocity
                if kwargs["v"] > limit:
                    diags.append(Diagnostic("error", f"'{fname}' velocity {kwargs['v']} exceeds limit {limit}", lineno))

        # Joint position list bounds (6 floats, each within ±2π)
        for m in _LIST_RE.finditer(stripped):
            nums = _parse_floats(m.group(1))
            if len(nums) == 6:
                for idx, val in enumerate(nums):
                    if abs(val) > 2 * math.pi + 0.001:
                        diags.append(Diagnostic("warning", f"Joint value {val:.3f} at index {idx} may exceed ±2π", lineno))

        # Pose list workspace radius (first 3 of 6 floats = XYZ translation)
        # Pose literal: p[...] or just [...] assigned to pose var
        for m in re.finditer(r'p\s*\[([^\]]*)\]', stripped):
            nums = _parse_floats(m.group(1))
            if len(nums) >= 3:
                radius = math.sqrt(sum(x**2 for x in nums[:3]))
                if radius > s.max_workspace_radius:
                    diags.append(Diagnostic("error", f"Pose translation radius {radius:.3f} m exceeds workspace limit {s.max_workspace_radius} m", lineno))

    return diags
