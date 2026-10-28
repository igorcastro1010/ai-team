from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_TEAM_", env_file=ROOT / ".env", extra="ignore")
    environment: Literal["development", "production", "test"] = "development"
    database_url: str = f"sqlite:///{ROOT / '.data' / 'ai-team.db'}"
    public_origin: str = "http://localhost:3000"
    session_ttl_seconds: int = 43200

    @model_validator(mode="after")
    def validate_deployment(self):
        if self.environment == "production":
            if not self.public_origin.startswith("https://"):
                raise ValueError("Produção requer HTTPS")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Produção requer PostgreSQL com psycopg")
        if not 300 <= self.session_ttl_seconds <= 86400:
            raise ValueError("Sessão deve durar entre 5 minutos e 24 horas")
        return self
