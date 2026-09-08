"""Application configuration.

Every value the app needs from its environment is declared here once, as a typed
field, instead of being read with ``os.getenv`` at the point of use. That gives us
one place to look when asking "what can be configured?", and it fails loudly at
startup on a bad value rather than silently at request time.
"""

import enum
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Absolute path so the database is found no matter which directory the process
# was started from. A relative "sqlite:///duolingo.db" would silently create a
# second, empty database when uvicorn and pytest are launched from different
# working directories -- a confusing failure worth designing out.
DEFAULT_SQLITE_URL = f"sqlite:///{(BACKEND_DIR / 'duolingo.db').as_posix()}"

#: The seeded learner's password when nothing overrides it. Named here rather
#: than written inline so the production check can compare against it — "is this
#: still the value everyone can read in the repository?" is the question worth
#: asking, and it needs the literal in one place.
_DEFAULT_DEMO_PASSWORD = "duolingo123"


class Environment(str, enum.Enum):
    """Which deployment this process is.

    Three values, and each one changes something real:

    * ``development`` — permissive defaults, a local SQLite file, http cookies.
    * ``test`` — the same, plus a bcrypt cost the suite can afford.
    * ``production`` — the settings below are *validated* rather than defaulted,
      because the dangerous configuration mistakes are all silent ones.

    A ``str`` enum so ``ENVIRONMENT=production`` in a dashboard is the whole
    configuration, and a typo is a startup error rather than a quiet fallback to
    development behaviour.
    """

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


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

    #: Which deployment this is. Drives the production checks at the bottom of
    #: this class. Defaults to development, so nothing about running locally
    #: changes and nobody has to remember to set it to be safe — only to be
    #: *deployed*.
    environment: Environment = Environment.DEVELOPMENT

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

    # --- login rate limiting (Phase 10) ---------------------------------------
    # Failed logins allowed per (email, client IP) per window before the endpoint
    # answers 429. Five is enough to absorb a person mistyping a password and
    # small enough to make guessing expensive. Counting is per *failure*: a
    # successful login clears the key, so a legitimate learner is never blocked.
    login_max_attempts: int = 5
    login_window_seconds: int = 300
    # Whether to believe `X-Forwarded-For` when identifying the client.
    #
    # **Off by default, and that default is a security decision.** The header is
    # attacker-controlled: if it is trusted with no proxy in front, anyone can put
    # a fresh value on every request and the rate limit becomes decorative. Turn
    # it on ONLY when this app sits behind a proxy that overwrites the header
    # (every managed platform does). With it off, `request.client.host` is used —
    # which behind a proxy is the proxy, so every client shares one bucket.
    trust_proxy_headers: bool = False

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
    demo_user_password: str = _DEFAULT_DEMO_PASSWORD

    # --- database -------------------------------------------------------------
    # One source of truth for where the data lives. Every other module asks
    # settings for this rather than building a path of its own, so pointing the
    # app at a different database (a test file, or Postgres later) is a single
    # environment variable and no code change.
    database_url: str = DEFAULT_SQLITE_URL

    # Echo every SQL statement to stdout. Off by default; useful when learning
    # what the ORM actually emits.
    database_echo: bool = False

    # --- production safety ----------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        """Refuse to start a production process that is configured unsafely.

        **Every check here is for a mistake that is otherwise silent.** A cookie
        without ``Secure`` still works — it just travels in the clear. SQL echo
        still works — it just prints every statement, including the ones carrying
        an email address, into the platform's log aggregator. The demo password
        still works — it is just published in this repository. None of these
        announce themselves; the application looks healthy while being wrong,
        which is exactly the class of failure worth converting into a crash at
        startup.

        Refusing to boot is the right severity. A deployment that fails visibly
        gets fixed in minutes; one that succeeds insecurely can run for months.
        """
        if not self.is_production:
            return self

        problems: list[str] = []

        if not self.session_cookie_secure:
            problems.append(
                "SESSION_COOKIE_SECURE must be true in production, or the session "
                "cookie is sent over plain http and anyone on the network can "
                "read it."
            )

        if self.demo_user_password == _DEFAULT_DEMO_PASSWORD:
            problems.append(
                "DEMO_USER_PASSWORD is still the committed default, which is "
                "published in this repository. Set it, or do not seed the demo "
                "learner in production."
            )

        if self.database_echo:
            problems.append(
                "DATABASE_ECHO must be off in production: it writes every SQL "
                "statement, including parameters, to the logs."
            )

        if any("localhost" in origin for origin in self.cors_origins):
            problems.append(
                "CORS_ORIGINS still contains localhost. Set it to the real "
                "frontend origin, or to an empty list if the frontend proxies the "
                "API under its own origin (the recommended topology, in which "
                "case no cross-origin request exists)."
            )

        if problems:
            bullets = "".join(f"\n  - {problem}" for problem in problems)
            raise ValueError(f"Unsafe production configuration:{bullets}")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance.

    Cached so the ``.env`` file is parsed once per process rather than on every
    request, and so every caller observes the same object.
    """
    return Settings()
