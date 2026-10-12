from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables / .env. No secrets in code."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = Field(min_length=16)
    hr_api_key: str = Field(min_length=16)
    encryption_key: Optional[str] = None

    database_url: str = "sqlite:///./background_agent.db"
    cors_origins: str = ""  # comma separated
    public_base_url: str = "http://localhost:8000"

    slack_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@example.com"

    upload_dir: str = "./uploads"
    max_upload_bytes: int = 5 * 1024 * 1024

    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_seconds: int = 60
    employer_token_ttl_days: int = 14
    dci_max_age_days: int = 90

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
