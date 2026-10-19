from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS265"
    access_tokens_minutes: int = 60
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:3000"
    cors_origin_regex: Optional[str] = None

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        return "postgresql://" + v[len("postgres://"):] if v.startswith("postgres://") else v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()