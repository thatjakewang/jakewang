"""Application configuration (pydantic-settings).

All runtime configuration (DB connection, API key, timezone, site URL) is defined here and
loaded from .env or environment variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file.

    Sensitive values (keys) and deployment-specific values (DB URL) are kept out of
    source control. Pydantic-settings automatically validates types.
    """

    # No defaults: a deployment that forgot either of these fails to boot
    # instead of running against the wrong database or an open write API.
    database_url: str
    shortcut_api_key: str

    app_timezone: str = "Asia/Taipei"

    # The one origin search engines should index. Canonical links and the
    # sitemap are built from it, not from the request's Host header, so a
    # second hostname pointing here can't present itself as the original.
    site_url: str = "https://jakewang.dev"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from environment / .env file.

    Using lru_cache means the .env is read only once per process (good for performance
    and to avoid repeated file I/O). All configuration (DB URL, API keys, timezone, etc.)
    lives here.
    """
    return Settings()
