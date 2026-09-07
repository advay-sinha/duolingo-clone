"""Application configuration.

Every value the app needs from its environment is declared here once, as a typed
field, instead of being read with ``os.getenv`` at the point of use. That gives us
one place to look when asking "what can be configured?", and it fails loudly at
startup on a bad value rather than silently at request time.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from environment variables.

    Values are read from the process environment first and from ``backend/.env``
    as a fallback, so a developer can keep local overrides in a file that is not
    committed. No secrets live here today — only local development wiring.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- application metadata -------------------------------------------------
    app_name: str = "Duolingo Clone API"
    api_v1_prefix: str = "/api/v1"

    # --- CORS -----------------------------------------------------------------
    # The exact origins the browser is allowed to call this API from. Kept as a
    # narrow list rather than "*" so the development config does not quietly
    # become a permissive production config.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance.

    Cached so the ``.env`` file is parsed once per process rather than on every
    request, and so every caller observes the same object.
    """
    return Settings()
