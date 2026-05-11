"""
Pure Python RTDE (Real-Time Data Exchange) client for Universal Robots.

Implements the RTDE protocol v2 for monitoring robot state during
script execution. No external dependencies required.

Reference: Universal Robots RTDE Guide
https://www.universal-robots.com/articles/ur/interface-communication/real-time-data-exchange-rtde-guide/
"""

import struct
import socket
import logging
from enum import IntEnum

logger = logging.getLogger(__name__)


# ── Protocol constants ────────────────────────────────────────

class PacketType(IntEnum):
    REQUEST_PROTOCOL_VERSION = 86       # 'V'
    GET_URCONTROL_VERSION = 118         # 'v'
    TEXT_MESSAGE = 77                   # 'M'
    DATA_PACKAGE = 85                   # 'U'
    CONTROL_PACKAGE_SETUP_OUTPUTS = 79  # 'O'
    CONTROL_PACKAGE_SETUP_INPUTS = 73   # 'I'
    CONTROL_PACKAGE_START = 83          # 'S'
    CONTROL_PACKAGE_PAUSE = 80          # 'P'


class RuntimeState(IntEnum):
    STOPPING = 1
    STOPPED = 2
    PLAYING = 3
    PAUSING = 4
    PAUSED = 5
    RESUMING = 6


class RobotMode(IntEnum):
    NO_CONTROLLER = -1
    DISCONNECTED = 0
    CONFIRM_SAFETY = 1
    BOOTING = 2
    POWER_OFF = 3
    POWER_ON = 4
    IDLE = 5
    BACKDRIVE = 6
    RUNNING = 7


# RTDE data type → (byte size, struct format)
RTDE_TYPE_INFO: dict[str, tuple[int, str]] = {
    "BOOL":         (1,  ">?"),
    "UINT8":        (1,  ">B"),
    "UINT32":       (4,  ">I"),
    "UINT64":       (8,  ">Q"),
    "INT32":        (4,  ">i"),
    "DOUBLE":       (8,  ">d"),
    "VECTOR3D":     (24, ">3d"),
    "VECTOR6D":     (48, ">6d"),
    "VECTOR6INT32": (24, ">6i"),
    "VECTOR6UINT32":(24, ">6I"),
}


# ── RTDE Client ───────────────────────────────────────────────

class RTDEClient:
    """Pure Python RTDE client for monitoring Universal Robots state."""

    PROTOCOL_VERSION = 2
    DEFAULT_FREQUENCY = 10.0  # Hz

    def __init__(self, host: str, port: int = 30004, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._connected = False
        self._output_recipe: list[str] = []
        self._output_types: list[str] = []
        self._recipe_id: int = 0

    # ── Public API ────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to RTDE interface and negotiate protocol."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))

            if not self._negotiate_protocol():
                logger.warning("RTDE protocol negotiation failed")
                self.disconnect()
                return False

            self._connected = True
            logger.info("RTDE connected to %s:%d", self.host, self.port)
            return True

        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            logger.warning("RTDE connection failed: %s", e)
            return False

    def disconnect(self):
        """Disconnect from RTDE interface."""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._connected = False
        self._output_recipe = []
        self._output_types = []

    def setup_monitoring(
        self,
        variables: list[str] | None = None,
        frequency: float = DEFAULT_FREQUENCY,
    ) -> bool:
        """Setup output recipe and start synchronization.

        Default variables monitor runtime_state and robot_mode, which is
        enough to track script execution start/stop.
        """
        if not self._connected:
            return False

        if variables is None:
            variables = ["runtime_state", "robot_mode"]

        if not self._setup_output_recipe(variables, frequency):
            return False

        return self._start_synchronization()

    def receive_state(self) -> dict | None:
        """Receive one data package from RTDE. Returns parsed dict or None."""
        if not self._connected:
            return None
        try:
            pkt_type, payload = self._recv_packet()
            if pkt_type == PacketType.DATA_PACKAGE and payload:
                return self._parse_data_package(payload)
        except (TimeoutError, OSError):
            pass
        return None

    def get_controller_version(self) -> str | None:
        """Query URControl version string."""
        self._send_packet(PacketType.GET_URCONTROL_VERSION)
        pkt_type, payload = self._recv_packet()
        if pkt_type == PacketType.GET_URCONTROL_VERSION and payload and len(payload) >= 16:
            major, minor, bugfix, build = struct.unpack(">IIII", payload[:16])
            return f"{major}.{minor}.{bugfix}.{build}"
        return None

    # ── Private protocol methods ──────────────────────────────

    def _send_packet(self, pkt_type: int, payload: bytes = b""):
        """Send an RTDE packet: [uint16 size][uint8 type][payload]."""
        size = 3 + len(payload)
        header = struct.pack(">HB", size, pkt_type)
        self._sock.sendall(header + payload)

    def _recv_packet(self) -> tuple[int | None, bytes | None]:
        """Receive one RTDE packet. Returns (type, payload)."""
        header = self._recv_exact(3)
        if not header:
            return None, None
        size, pkt_type = struct.unpack(">HB", header)
        payload_size = size - 3
        payload = self._recv_exact(payload_size) if payload_size > 0 else b""
        return pkt_type, payload

    def _recv_exact(self, n: int) -> bytes | None:
        """Receive exactly n bytes from the socket."""
        data = b""
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _negotiate_protocol(self) -> bool:
        """Negotiate RTDE protocol version with the controller."""
        payload = struct.pack(">H", self.PROTOCOL_VERSION)
        self._send_packet(PacketType.REQUEST_PROTOCOL_VERSION, payload)
        pkt_type, resp = self._recv_packet()
        if pkt_type == PacketType.REQUEST_PROTOCOL_VERSION and resp:
            return resp[0] == 1  # 1 = accepted
        return False

    def _setup_output_recipe(self, variables: list[str], frequency: float) -> bool:
        """Register which variables we want to receive from the controller."""
        recipe_str = ",".join(variables)
        # Protocol v2: frequency (double, 8 bytes) + variable names
        payload = struct.pack(">d", frequency) + recipe_str.encode("utf-8")
        self._send_packet(PacketType.CONTROL_PACKAGE_SETUP_OUTPUTS, payload)

        pkt_type, resp = self._recv_packet()
        if pkt_type != PacketType.CONTROL_PACKAGE_SETUP_OUTPUTS or not resp:
            return False

        self._recipe_id = resp[0]
        types_str = resp[1:].decode("utf-8")

        if "NOT_FOUND" in types_str:
            logger.warning("Some RTDE variables not available: %s", types_str)
            return False

        self._output_recipe = variables
        self._output_types = types_str.split(",")
        return True

    def _start_synchronization(self) -> bool:
        """Start RTDE data synchronization."""
        self._send_packet(PacketType.CONTROL_PACKAGE_START)
        pkt_type, resp = self._recv_packet()
        if pkt_type == PacketType.CONTROL_PACKAGE_START and resp:
            return resp[0] == 1
        return False

    def _parse_data_package(self, payload: bytes) -> dict:
        """Unpack a DATA_PACKAGE according to the output recipe types."""
        result = {}
        offset = 1  # skip recipe_id byte

        for var, dtype in zip(self._output_recipe, self._output_types):
            type_info = RTDE_TYPE_INFO.get(dtype)
            if not type_info:
                logger.warning("Unknown RTDE type: %s", dtype)
                break

            size, fmt = type_info
            if offset + size > len(payload):
                break

            raw = struct.unpack(fmt, payload[offset:offset + size])
            result[var] = list(raw) if len(raw) > 1 else raw[0]
            offset += size

        return result
