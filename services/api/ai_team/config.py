from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AI_TEAM_", env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    environment: Literal["development", "production", "test"] = "development"
    database_url: str = f"sqlite:///{ROOT / '.data' / 'ai-team.db'}"
    public_origin: str = "http://localhost:3000"
    session_ttl_seconds: int = 43200
    hermes_url: str = ""
    hermes_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def validate_hermes(self):
        if self.hermes_url:
            url = urlsplit(self.hermes_url)
            if (
                url.scheme not in {"http", "https"}
                or url.hostname not in {"localhost", "127.0.0.1", "::1", "hermes"}
                or url.username or url.password or url.query or url.fragment
                or url.path not in {"", "/"}
            ):
                raise ValueError("Hermes requer endereço local ou serviço privado hermes")
            # Accessing port also rejects malformed port values at startup.
            _ = url.port
        key = self.hermes_key.get_secret_value()
        if key and (len(key) < 32 or not key.isascii() or any(c.isspace() for c in key)):
            raise ValueError("Chave Hermes deve ter pelo menos 32 caracteres ASCII sem espaços")
        return self

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
