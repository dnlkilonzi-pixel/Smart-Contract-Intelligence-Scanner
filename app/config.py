"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: str = Field("development", alias="APP_ENV")
    app_debug: bool = Field(False, alias="APP_DEBUG")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    secret_key: str = Field("change_me_in_production", alias="SECRET_KEY")

    # --- Database ---
    database_url: str = Field(
        "postgresql+asyncpg://scanner:scanner@localhost:5432/smart_contract_scanner",
        alias="DATABASE_URL",
    )

    # --- Redis / Celery ---
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field("redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/1", alias="CELERY_RESULT_BACKEND")

    # --- Blockchain ---
    eth_rpc_url: str = Field("https://mainnet.infura.io/v3/demo", alias="ETH_RPC_URL")
    eth_testnet_rpc_url: Optional[str] = Field(None, alias="ETH_TESTNET_RPC_URL")
    etherscan_api_key: Optional[str] = Field(None, alias="ETHERSCAN_API_KEY")

    # --- Static analysis ---
    slither_timeout: int = Field(120, alias="SLITHER_TIMEOUT")
    mythril_timeout: int = Field(300, alias="MYTHRIL_TIMEOUT")

    # --- AI ---
    ai_model_path: str = Field("models/vuln_classifier.joblib", alias="AI_MODEL_PATH")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
