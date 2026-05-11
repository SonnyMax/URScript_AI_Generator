"""Orchestrates: connect → validate-state → send-script → monitor → done."""
from __future__ import annotations
import time
from dataclasses import dataclass

from urscript_app.config import get_settings
from urscript_app.robot.rtde_client import get_rtde_client, RTDEConnectionError
from urscript_app.robot.script_sender import send_script, ScriptSendError
from urscript_app.robot.safety import get_supervisor


class ExecutionError(Exception):
    pass


class SafetyStopError(ExecutionError):
    pass


@dataclass
class ExecutionResult:
    success: bool
    message: str
    stopped_by_safety: bool = False


def execute_program(code: str) -> ExecutionResult:
    s = get_settings()
    supervisor = get_supervisor()
    client = get_rtde_client()

    if supervisor.is_stop_requested():
        return ExecutionResult(
            False, "Stop requested — clear safety stop before executing", stopped_by_safety=True
        )

    # Try RTDE connect (best-effort — script sending works without it)
    rtde_available = client.is_connected()
    if not rtde_available:
        try:
            client.connect()
            supervisor.start_watchdog()
            rtde_available = True
        except RTDEConnectionError:
            rtde_available = False

    # If RTDE connected, check safety mode before sending
    if rtde_available:
        state = client.refresh_state()
        if not state.is_normal:
            raise ExecutionError(
                f"Robot safety mode {state.safety_mode} is not NORMAL — cannot execute"
            )

    # Send script via port 30002 (always works, RTDE not required)
    try:
        send_script(code)
    except ScriptSendError as e:
        raise ExecutionError(str(e)) from e

    if not rtde_available:
        return ExecutionResult(True, "Script sent (no RTDE — execution monitoring unavailable)")

    # Monitor execution via RTDE
    deadline = time.monotonic() + s.execution_timeout_s
    first_state: int | None = None

    while time.monotonic() < deadline:
        if supervisor.is_stop_requested():
            return ExecutionResult(False, "Execution stopped by safety request", stopped_by_safety=True)

        state = client.refresh_state()
        if not state.connected:
            return ExecutionResult(True, "Script sent (RTDE lost during monitoring)")

        rt = state.runtime_state

        if first_state is None:
            first_state = rt
            time.sleep(0.1)
            continue

        if rt != first_state:
            # PolyscopeX: idle(STOPPING=1) → running(STOPPED=2) — keep waiting
            if first_state == 1 and rt == 2:
                first_state = rt
                time.sleep(0.1)
                continue
            # Classic: idle(STOPPED=2) → running(PLAYING=3) — keep waiting
            if first_state == 2 and rt == 3:
                first_state = rt
                time.sleep(0.1)
                continue
            # Any other transition away from running = done
            return ExecutionResult(True, "Program completed")

        time.sleep(0.1)

    return ExecutionResult(False, f"Execution timed out after {s.execution_timeout_s}s")
