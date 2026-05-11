"""RTDE state monitoring using pure-Python RTDE (no external libraries).

Tries extended variable set first; falls back to minimal (runtime_state,
robot_mode) if PolyscopeX doesn't expose the extra vars.

PolyscopeX runtime_state is inverted vs classic UR:
  Classic:      STOPPED(2)=idle, PLAYING(3)=running
  PolyscopeX:   STOPPING(1)=idle, STOPPED(2)=running
"""
from __future__ import annotations
import threading
from dataclasses import dataclass, field

from urscript_app.robot.rtde_pure import RTDEClient as _PureRTDE, RuntimeState
from urscript_app.config import get_settings, get_active_host


class RTDEConnectionError(Exception):
    pass


@dataclass
class RobotState:
    connected: bool = False
    robot_mode: int = -1
    safety_mode: int = -1
    runtime_state: int = -1
    joint_positions: list[float] = field(default_factory=lambda: [0.0] * 6)
    tcp_pose: list[float] = field(default_factory=lambda: [0.0] * 6)
    is_executing: bool = False

    @property
    def is_normal(self) -> bool:
        # If safety_mode unavailable (-1), assume normal so execution isn't blocked
        return self.safety_mode in (1, -1)

    @property
    def is_playing(self) -> bool:
        return self.is_executing


_VARS_EXTENDED = ["runtime_state", "robot_mode", "safety_mode", "actual_q", "actual_TCP_pose"]
_VARS_MINIMAL  = ["runtime_state", "robot_mode"]


class RTDEClient:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._con: _PureRTDE | None = None
        self._state = RobotState()
        self._polyscopex: bool | None = None
        self._extended: bool = False   # whether extended vars are available

    def connect(self) -> None:
        s = get_settings()
        host = get_active_host()
        con = _PureRTDE(host, s.rtde_port)
        if not con.connect():
            raise RTDEConnectionError(
                f"RTDE connect failed to {host}:{s.rtde_port}"
            )

        # Try extended first, fall back to minimal
        ok = con.setup_monitoring(_VARS_EXTENDED, frequency=s.rtde_frequency)
        extended = ok
        if not ok:
            # Reconnect — setup_monitoring failure may leave socket in bad state
            con.disconnect()
            con = _PureRTDE(host, s.rtde_port)
            if not con.connect():
                raise RTDEConnectionError(
                    f"RTDE reconnect failed to {host}:{s.rtde_port}"
                )
            ok = con.setup_monitoring(_VARS_MINIMAL, frequency=s.rtde_frequency)
            if not ok:
                con.disconnect()
                raise RTDEConnectionError(
                    "RTDE output recipe setup failed — robot may not be fully booted"
                )

        with self._lock:
            self._con = con
            self._extended = extended
            self._state.connected = True

    def disconnect(self) -> None:
        with self._lock:
            con = self._con
            self._con = None
            self._state = RobotState(connected=False)
        if con:
            try:
                con.disconnect()
            except Exception:
                pass

    def is_connected(self) -> bool:
        with self._lock:
            return self._state.connected and self._con is not None

    def refresh_state(self) -> RobotState:
        con = self._con
        if con is None:
            return self._state
        try:
            data = con.receive_state()
            if data is None:
                with self._lock:
                    self._state.connected = False
                return self._state

            rt  = int(data.get("runtime_state", -1))
            rm  = int(data.get("robot_mode", -1))
            sm  = int(data.get("safety_mode", -1))
            q   = data.get("actual_q", [0.0] * 6)
            tcp = data.get("actual_TCP_pose", [0.0] * 6)

            if self._polyscopex is None:
                if rt == RuntimeState.STOPPING:
                    self._polyscopex = True
                elif rt == RuntimeState.PLAYING:
                    self._polyscopex = False

            executing = self._is_executing(rt)

            with self._lock:
                self._state.runtime_state  = rt
                self._state.robot_mode     = rm
                self._state.safety_mode    = sm
                self._state.joint_positions = list(q) if isinstance(q, (list, tuple)) else [0.0] * 6
                self._state.tcp_pose        = list(tcp) if isinstance(tcp, (list, tuple)) else [0.0] * 6
                self._state.is_executing    = executing
        except Exception:
            with self._lock:
                self._state.connected = False
        return self._state

    def _is_executing(self, rt: int) -> bool:
        if self._polyscopex:
            return rt == int(RuntimeState.STOPPED)   # PolyscopeX: STOPPED=running
        return rt == int(RuntimeState.PLAYING)        # Classic: PLAYING=running

    def get_state(self) -> RobotState:
        with self._lock:
            return self._state

    def stop_motion(self, decel: float = 2.0) -> None:
        try:
            from urscript_app.robot.script_sender import send_script
            send_script(
                f"def stop_now():\n"
                f"  stopj({decel})\n"
                f"  sync()\n"
                f"  halt\n"
                f"end\n"
                f"stop_now()\n"
            )
        except Exception:
            pass


_client: RTDEClient | None = None
_client_lock = threading.Lock()


def get_rtde_client() -> RTDEClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = RTDEClient()
    return _client
