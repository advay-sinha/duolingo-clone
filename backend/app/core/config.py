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

    # --- gamification ---------------------------------------------------------
    # Every tunable number in the game lives here, so no service body contains a
    # magic constant and "what if XP were 15?" is a one-line change.
    xp_per_correct_answer: int = 10
    max_hearts: int = 5
    hearts_lost_per_mistake: int = 1
    # One heart back per this many minutes, applied lazily on read rather than
    # by a scheduler -- see services/gamification.regenerate_hearts.
    heart_regen_minutes: int = 30
    leaderboard_limit: int = 25
    default_daily_goal: int = 30

    # --- authentication -------------------------------------------------------
    # The cookie the session token travels in. HttpOnly and SameSite are set on
    # the response in `routes/auth.py`; these are the parts worth configuring.
    session_cookie_name: str = "duolingo_session"
    session_lifetime_days: int = 14
    # Off for local http development. A deployment over https must set this, or
    # the cookie will travel in the clear.
    session_cookie_secure: bool = False
    # bcrypt's cost factor: work doubles per increment. 12 is a sensible 2020s
    # default for a login people wait on. The test suite lowers it to 4 via the
    # environment -- a password hash is *designed* to be slow, and paying 250ms
    # of that per test would turn a fast suite into a slow one without testing
    # anything extra. Lowering it in tests is standard practice (Django ships
    # the same knob) and is safe precisely because the cost is recorded inside
    # each hash string, so production hashes are unaffected.
    bcrypt_rounds: int = 12

    # --- seeded demo learner --------------------------------------------------
    # The learner the seed creates, kept from Phase 2 as a convenient demo
    # account. It is now a *normal* account: it has a password hash and logs in
    # through the same endpoint as anyone else. It is no longer the runtime
    # identity mechanism -- `get_current_user` resolves a session, and does not
    # know this setting exists.
    #
    # The password is configuration, not a committed literal: set
    # DEMO_USER_PASSWORD in backend/.env to choose your own. The default exists
    # so a fresh clone can be logged into without ceremony, and is safe only
    # because this database is local and holds nothing but practice Spanish.
    demo_username: str = "learner"
    demo_email: str = "learner@example.com"
    demo_user_password: str = "duolingo123"

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
