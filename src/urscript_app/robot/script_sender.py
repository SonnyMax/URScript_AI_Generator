"""Send URScript programs to the robot via the primary/script port (30002)."""
from __future__ import annotations
import socket
from urscript_app.config import get_settings


class ScriptSendError(Exception):
    pass


def _ensure_wrapped(code: str) -> str:
    stripped = code.strip()
    if not stripped.startswith("def "):
        stripped = f"def program():\n{stripped}\nend"
    if not stripped.endswith("\n"):
        stripped += "\n"
    return stripped


def send_script(code: str, host: str | None = None, port: int | None = None) -> None:
    s = get_settings()
    host = host or s.ursim_host
    port = port or s.script_port
    payload = _ensure_wrapped(code).encode("utf-8")
    try:
        with socket.create_connection((host, port), timeout=5.0) as sock:
            sock.sendall(payload)
    except OSError as e:
        raise ScriptSendError(f"Failed to send script to {host}:{port} — {e}") from e
