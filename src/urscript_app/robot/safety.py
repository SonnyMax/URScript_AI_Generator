"""Thread-safe safety supervisor with stop request and watchdog."""
from __future__ import annotations
import threading
import time
from urscript_app.robot.rtde_client import get_rtde_client


class SafetySupervisor:
    SAFE_SAFETY_MODE = 1  # NORMAL

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._watchdog_thread: threading.Thread | None = None
        self._running = False

    def start_watchdog(self, poll_interval: float = 0.2) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        t = threading.Thread(target=self._watchdog_loop, args=(poll_interval,), daemon=True)
        self._watchdog_thread = t
        t.start()

    def stop_watchdog(self) -> None:
        with self._lock:
            self._running = False

    def _watchdog_loop(self, interval: float) -> None:
        client = get_rtde_client()
        while True:
            with self._lock:
                if not self._running:
                    break
            if client.is_connected():
                state = client.refresh_state()
                if state.safety_mode not in (self.SAFE_SAFETY_MODE, -1):
                    self._stop_event.set()
            time.sleep(interval)

    def request_stop(self) -> None:
        self._stop_event.set()
        # stop_motion() sends stopj(2.0) via script port 30002
        get_rtde_client().stop_motion(decel=2.0)

    def is_stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def clear(self) -> None:
        self._stop_event.clear()


_supervisor: SafetySupervisor | None = None
_sup_lock = threading.Lock()


def get_supervisor() -> SafetySupervisor:
    global _supervisor
    with _sup_lock:
        if _supervisor is None:
            _supervisor = SafetySupervisor()
    return _supervisor
