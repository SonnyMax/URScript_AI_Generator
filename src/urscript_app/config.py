from pydantic_settings import BaseSettings, SettingsConfigDict


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


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
