import threading
from pydantic_settings import BaseSettings, SettingsConfigDict

ROBOT_TARGETS: dict[str, str] = {
    "localhost": "127.0.0.1",
    "Pepa":      "192.168.0.94",
    "Tom":       "192.168.0.96",
    "Olda":      "192.168.0.98",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LM Studio
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "qwen3.5-4b"
    lm_studio_api_key: str = "lm-studio"
    lm_studio_timeout: float = 60.0
    lm_studio_max_tokens: int = 2048
    lm_studio_temperature: float = 0.2

    # URSim / Robot
    ursim_host: str = "127.0.0.1"
    rtde_port: int = 30004
    script_port: int = 30002
    rtde_frequency: float = 10.0
    execution_timeout_s: float = 60.0

    # Safety limits
    max_joint_velocity: float = 1.05   # rad/s
    max_joint_accel: float = 1.4       # rad/s^2
    max_tcp_velocity: float = 0.5      # m/s
    max_tcp_accel: float = 1.2         # m/s^2
    max_workspace_radius: float = 1.5  # metres from base


_settings: Settings | None = None
_active_target: str = "localhost"
_target_lock = threading.Lock()


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_active_host() -> str:
    with _target_lock:
        return ROBOT_TARGETS[_active_target]


def get_active_target() -> str:
    with _target_lock:
        return _active_target


def set_active_target(name: str) -> None:
    if name not in ROBOT_TARGETS:
        raise ValueError(f"Unknown target '{name}'. Valid: {list(ROBOT_TARGETS)}")
    with _target_lock:
        global _active_target
        _active_target = name
