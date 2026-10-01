"""Configuração central da suíte, carregada de variáveis de ambiente e do arquivo `.env`.

Todas as variáveis usam o prefixo ``ORANGEHRM_`` (ex.: ``ORANGEHRM_BASE_URL``).
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ambientes compartilhados onde a suíte nunca pode gravar dados.
SHARED_HOSTS = frozenset({"opensource-demo.orangehrmlive.com"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORANGEHRM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: HttpUrl = Field(
        default=HttpUrl("https://opensource-demo.orangehrmlive.com"),
        description="URL raiz da instância, sem o sufixo /web/index.php.",
    )
    admin_username: str = "Admin"
    admin_password: SecretStr = SecretStr("admin123")

    allow_write: bool = Field(
        default=False,
        description=(
            "Habilita cenários que gravam dados (candidatura real + limpeza). "
            "Só é aceito em ambiente isolado."
        ),
    )

    default_timeout_ms: int = Field(default=15_000, ge=1_000)
    navigation_timeout_ms: int = Field(default=30_000, ge=1_000)
    api_timeout_ms: int = Field(default=30_000, ge=1_000)

    locale: str = "en-US"
    timezone_id: str = "America/Sao_Paulo"

    @property
    def app_url(self) -> str:
        """Base usada por todas as rotas da aplicação (UI e API)."""
        return f"{str(self.base_url).rstrip('/')}/web/index.php"

    @property
    def host(self) -> str:
        return urlparse(str(self.base_url)).hostname or ""

    @property
    def is_shared_environment(self) -> bool:
        return self.host in SHARED_HOSTS

    @model_validator(mode="after")
    def _forbid_writes_on_shared_env(self) -> Settings:
        if self.allow_write and self.is_shared_environment:
            raise ValueError(
                f"ORANGEHRM_ALLOW_WRITE=true não é permitido em {self.host}: "
                "o ambiente é compartilhado. Use uma instância isolada (infra/)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
