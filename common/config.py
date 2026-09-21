from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    redis_host: str = "127.0.0.1"
    redis_port: int = 6204
    redis_password: str = ""
    redis_channel: str = "DadeKavan-PD-X"
    redis_stream: str = "DadeKavan-PD-X-stream"
    redis_consumer_group: str = "workerB"
    redis_consumer_name: str = "worker-b"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 6206
    mysql_user: str = "DadeKavan-PD-X-USER"
    mysql_password: str = ""
    mysql_database: str = "DadeKavan-PD-X"

    api_key: str = Field(min_length=16)
    api_key_header: str = "X-API-Key"

    tsetmc_base_url: str = "https://cdn.tsetmc.com/api"
    tsetmc_poll_interval_ms: int = Field(default=350, ge=100)
    tsetmc_timeout_seconds: float = Field(default=2.5, gt=0)
    tsetmc_mock: bool = False
    tsetmc_proxy_url: str | None = None

    worker_b_batch_size: int = Field(default=100, ge=1, le=1000)
    worker_b_block_ms: int = Field(default=1000, ge=1, le=60_000)
    media_root: str = "media"
    log_level: str = "INFO"

    @property
    def redis_url(self) -> str:
        from urllib.parse import quote

        return f"redis://:{quote(self.redis_password, safe='')}@{self.redis_host}:{self.redis_port}/0"

    @property
    def media_path(self) -> Path:
        path = Path(self.media_root)
        return path if path.is_absolute() else ROOT_DIR / path


@lru_cache

def get_settings() -> Settings:
    return Settings()