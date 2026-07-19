from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Non-secret backend behavior plus values loaded from the local .env file."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TabSpace API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    )
    max_upload_bytes: int = 100 * 1024 * 1024
    allowed_audio_extensions: tuple[str, ...] = (".mp3", ".wav", ".flac", ".m4a", ".ogg")
    allowed_tunings: tuple[str, ...] = ("standard_e", "c_sharp", "drop_d")
    uploads_dir: Path = BACKEND_DIR / "storage/uploads"
    artifacts_dir: Path = BACKEND_DIR / "storage/artifacts"
    logs_dir: Path = BACKEND_DIR / "storage/logs"
    audio_processing_python: str = ""
    demucs_model_name: str = "htdemucs_6s"
    demucs_passes: int = 2
    model_serialization: str = "default"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "tabspace"
    mysql_user: str = "tabspace"
    mysql_password: SecretStr = SecretStr("")
    redis_url: str = "redis://127.0.0.1:6379/0"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value

        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False
        raise ValueError("DEBUG must be a boolean value or one of debug/release")

    @property
    def mysql_dsn(self) -> str:
        password = self.mysql_password.get_secret_value()
        return f"mysql+pymysql://{self.mysql_user}:{password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    @property
    def backend_dir(self) -> Path:
        return BACKEND_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
