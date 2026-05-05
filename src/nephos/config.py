"""Configuration applicative typée (Pydantic Settings)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de Nephos chargée depuis l'environnement et `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="NEPHOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql://nephos:nephos@localhost:5432/nephos_dev"),
        description="DSN de connexion à la base PostgreSQL.",
    )
    log_level: str = Field(
        default="INFO",
        description="Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    log_format: str = Field(
        default="text",
        description="Format de log : 'text' (humain) ou 'json' (structuré).",
    )
    work_dir: Path = Field(
        default=Path("./var"),
        description="Dossier de travail (caches, fichiers temporaires d'import).",
    )
    uri_base: str = Field(
        default="https://w3id.org/nephos/vocab",
        description="Préfixe canonique des URI Nephos (voir ADR 0003).",
    )


def get_settings() -> Settings:
    """Construit la configuration. Appelée par les commandes CLI."""
    return Settings()
