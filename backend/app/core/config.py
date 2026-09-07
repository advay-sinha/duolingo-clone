"""Application configuration.

Every value the app needs from its environment is declared here once, as a typed
field, instead of being read with ``os.getenv`` at the point of use. That gives us
one place to look when asking "what can be configured?", and it fails loudly at
startup on a bad value rather than silently at request time.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Absolute path so the database is found no matter which directory the process
# was started from. A relative "sqlite:///duolingo.db" would silently create a
# second, empty database when uvicorn and pytest are launched from different
# working directories -- a confusing failure worth designing out.
DEFAULT_SQLITE_URL = f"sqlite:///{(BACKEND_DIR / 'duolingo.db').as_posix()}"


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

    # --- database -------------------------------------------------------------
    # One source of truth for where the data lives. Every other module asks
    # settings for this rather than building a path of its own, so pointing the
    # app at a different database (a test file, or Postgres later) is a single
    # environment variable and no code change.
    database_url: str = DEFAULT_SQLITE_URL

    # Echo every SQL statement to stdout. Off by default; useful when learning
    # what the ORM actually emits.
    database_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance.

    Cached so the ``.env`` file is parsed once per process rather than on every
    request, and so every caller observes the same object.
    """
    return Settings()
