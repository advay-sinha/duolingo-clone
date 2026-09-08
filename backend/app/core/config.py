"""Application configuration.

Every value the app needs from its environment is declared here once, as a typed
field, instead of being read with ``os.getenv`` at the point of use. That gives us
one place to look when asking "what can be configured?", and it fails loudly at
startup on a bad value rather than silently at request time.
"""

import enum
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from sqlalchemy.engine import make_url
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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


def _redact_url(database_url: str) -> str:
    """Mask credentials in a database URL so it is safe to put in a message.

    **This exists because of a real credential leak.** The `libsql://` check
    below used to build the corrected URL and include it verbatim, so that a
    developer could paste it straight into their dashboard. That was a good
    intention and a bad idea: a hosted libSQL URL carries the database's auth
    token as a query parameter, so the "helpful" error wrote a live read-write
    credential into the platform's logs, where it is retained and widely
    readable.

    A configuration error must never print the configuration's secrets. The URL
    still identifies itself — scheme, host and the shape of the fix are all
    visible — but the token is replaced.
    """
    for key in ("authToken", "auth_token", "password", "token"):
        marker = f"{key}="
        while marker in database_url:
            start = database_url.index(marker) + len(marker)
            end = len(database_url)
            for terminator in ("&", "#"):
                position = database_url.find(terminator, start)
                if position != -1:
                    end = min(end, position)
            if start == end:
                break
            database_url = database_url[:start] + "***" + database_url[end:]
            if database_url[start : start + 3] == "***" and marker not in database_url[end:]:
                break
    # A userinfo section (scheme://user:secret@host) is a credential too.
    if "://" in database_url and "@" in database_url.split("://", 1)[1]:
        scheme, rest = database_url.split("://", 1)
        userinfo, host = rest.split("@", 1)
        if ":" in userinfo:
            user = userinfo.split(":", 1)[0]
            database_url = f"{scheme}://{user}:***@{host}"
    return database_url


def _is_local_sqlite_file(database_url: str) -> bool:
    """Whether this URL is a SQLite database stored on the local filesystem.

    **This check exists because of a real production outage.** The deployed
    backend answered ``GET /health`` with 200 and then returned 500 from the
    first endpoint that touched the database:
    ``sqlite3.OperationalError: unable to open database file``. The cause was a
    local-file SQLite URL on a serverless filesystem that is neither writable nor
    durable, and nothing in the application objected until a learner tried to
    register. Turning it into a refusal to start moves the discovery from "a user
    hit an error" to "the deploy failed loudly" (ADR-81, and the same reasoning as
    every other check in `_validate_production`).

    **The check is deliberately narrow: it fires only when the database file sits
    inside the deployed application directory** — that is, when nobody chose a
    path and the built-in default applied. That is exactly the mistake that
    caused the outage, and it is never right in production.

    A file elsewhere is left alone, because it is a deliberate operator decision
    this function cannot second-guess: ``sqlite:////data/duolingo.db`` on a
    mounted volume is a perfectly good production database, and refusing it would
    be a false positive that teaches people to disable the check.

    ``sqlite+libsql://`` is not a local file at all — it is the hosted libSQL
    dialect, which reaches Turso over the network and stores nothing on this
    host. In-memory databases are excluded for the obvious reason.
    """
    try:
        url = make_url(database_url)
    except Exception:
        # An unparseable URL is a different problem, reported by whatever tries
        # to connect. This check has nothing useful to say about it.
        return False

    if url.get_backend_name() != "sqlite":
        return False

    # sqlite+libsql:// and friends are network dialects, not files on this host.
    # `make_url` splits the driver out for us, so no string surgery is needed --
    # which matters, because "sqlite:///relative" and "sqlite:////absolute"
    # differ by a single slash and are easy to mishandle by hand.
    if url.get_driver_name() not in ("pysqlite", ""):
        return False

    database = url.database
    if not database or database == ":memory:":
        return False

    try:
        return Path(database).resolve().is_relative_to(BACKEND_DIR)
    except (OSError, ValueError):
        return False


def _validate_origin(origin: str) -> str:
    """Check one CORS origin and return it normalised.

    An *origin* is scheme + host + optional port, and nothing else — no path, no
    query, no trailing slash. The browser compares the `Origin` header against
    this list as an exact string, so `https://app.example.com/` (with a slash)
    silently matches nothing at all. That is the failure worth catching here:
    it is not an error anywhere, it simply means every cross-origin request is
    rejected, which looks like a bug in the application rather than a typo in
    configuration.

    Raises:
        ValueError: naming the offending value and what is wrong with it. This is
            the "deliberate validation error with a useful message" the fix is
            for — as opposed to the JSONDecodeError it replaces.
    """
    if origin == "*":
        raise ValueError(
            'CORS_ORIGINS may not contain "*". A wildcard origin and '
            "credentialed requests are incompatible by specification, and this "
            "API authenticates with a cookie — the browser would reject every "
            "response. List the exact origins instead."
        )

    parsed = urlparse(origin)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"CORS_ORIGINS entry {origin!r} must start with http:// or https:// "
            f"(an origin is scheme + host + optional port)."
        )
    if not parsed.netloc:
        raise ValueError(f"CORS_ORIGINS entry {origin!r} has no host.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError(
            f"CORS_ORIGINS entry {origin!r} must be an origin, not a URL: no "
            f"path, query or fragment. Use {parsed.scheme}://{parsed.netloc}"
        )

    # A trailing slash is the single most common way to get this wrong, and it
    # fails silently rather than loudly, so it is normalised rather than refused.
    return f"{parsed.scheme}://{parsed.netloc}"


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
    #
    # `NoDecode` is the load-bearing part of this line. See `_parse_cors_origins`
    # below for what it prevents.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("database_url", mode="after")
    @classmethod
    def _check_database_url_scheme(cls, value: str) -> str:
        """Reject a database URL SQLAlchemy cannot load a dialect for.

        **This exists because of a real deployment failure**, and the mistake is
        one almost everyone makes once. The Turso CLI prints the database URL in
        its own scheme::

            $ turso db show my-db --url
            libsql://my-db-org.turso.io

        Pasting that straight into ``DATABASE_URL`` gives SQLAlchemy a URL whose
        *backend* is ``libsql``, and there is no such SQLAlchemy backend. The
        driver is a **dialect of sqlite**, so the URL has to name both::

            sqlite+libsql://my-db-org.turso.io/?authToken=...&secure=true
            ▲      ▲
            │      └── driver   → sqlalchemy.dialects:sqlite.libsql
            └───────── backend

        Without this check the failure is
        ``NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:libsql``,
        raised from ``create_engine`` at *import* time — so the whole application
        fails to start, and the message names a plugin rather than the setting
        that is wrong or what to put in it.

        Note the two failures are distinguishable, and the difference is worth
        knowing when debugging:

        * ``...dialects:libsql``        → the URL is missing the ``sqlite+`` prefix
        * ``...dialects:sqlite.libsql`` → the prefix is right, the driver is not
          installed
        """
        if value.startswith("libsql://"):
            # Redacted: a hosted libSQL URL carries the database auth token as a
            # query parameter, and this message goes straight into the platform's
            # logs. See `_redact_url`.
            raise ValueError(
                "DATABASE_URL starts with 'libsql://', which is the scheme the "
                "Turso CLI prints -- but SQLAlchemy has no 'libsql' backend, so "
                "the application cannot start. libSQL is a *dialect of sqlite*: "
                "add the 'sqlite+' prefix, keeping the rest of the URL as it is. "
                f"Yours becomes:  sqlite+{_redact_url(value)}"
            )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        """Accept JSON, a comma-separated list, or nothing at all.

        **The bug this fixes.** ``pydantic-settings`` treats any "complex" field
        type — and ``list[str]`` is one — as JSON, calling ``json.loads()`` on the
        raw environment string inside ``EnvSettingsSource`` *before* validation
        runs. So a perfectly reasonable value typed into a deployment dashboard::

            CORS_ORIGINS=https://my-app.vercel.app

        never reaches a validator. It fails in the settings *source* with::

            SettingsError: error parsing value for field "cors_origins"
                           from source "EnvSettingsSource"

        which names the field but not the format, and — because settings are built
        at import time — surfaces as an application that will not start. An
        **empty** value fails the same way, which is the sharp edge: this
        project's own documentation recommends "no origins" for the deployment
        topology it recommends, and the obvious way to express that in a dashboard
        text box is to leave it blank.

        ``NoDecode`` on the field turns that JSON step off, so the raw string
        arrives here and this function decides what it means.

        **Permissive about the container, strict about the contents.** How the
        list is written is a matter of taste and of what a given dashboard makes
        easy; what each entry *is* genuinely matters, because a wrong origin is
        either a security hole or a broken app. So all three of these are
        accepted:

        ============================================ =========================
        ``CORS_ORIGINS=["https://a.dev","https://b"]``  JSON — as before
        ``CORS_ORIGINS=https://a.dev,https://b``        comma-separated
        ``CORS_ORIGINS=``                               empty: no origins
        ============================================ =========================

        and every entry is then checked by :func:`_validate_origin`.

        Empty means **no cross-origin access**, not "allow everything". That is a
        deliberate and safe reading: it is the correct setting for the recommended
        topology, where the frontend proxies the API under its own origin and no
        cross-origin request exists. Reading it as "allow everything" would turn a
        blank text box into an open API.
        """
        if value is None:
            return []

        if isinstance(value, (list, tuple)):
            origins = [str(item).strip() for item in value]
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text[0] in "[{":
                # Looks like JSON, so it was meant as JSON: report *why* it did
                # not parse rather than falling through to comma-splitting and
                # producing a nonsense origin like `["https://a.dev"`. A leading
                # `{` counts too — someone who wrote an object meant JSON, and
                # "must be a list of origins" is a far better answer than
                # "must start with http://".
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"CORS_ORIGINS looks like JSON but could not be parsed: "
                        f"{exc}. Either fix the JSON — "
                        f'["https://app.example.com","https://www.example.com"] — '
                        f"or use the simpler comma-separated form: "
                        f"https://app.example.com,https://www.example.com"
                    ) from exc
                if not isinstance(parsed, list):
                    raise ValueError(
                        f"CORS_ORIGINS must be a list of origins, got "
                        f"{type(parsed).__name__}. Example: "
                        f'["https://app.example.com"]'
                    )
                origins = [str(item).strip() for item in parsed]
            else:
                # Commas are the separator; newlines are tolerated because
                # multi-line dashboard textareas add them.
                origins = [
                    part.strip()
                    for part in text.replace("\n", ",").split(",")
                ]
        else:
            raise ValueError(
                f"CORS_ORIGINS must be a string or a list, got "
                f"{type(value).__name__}."
            )

        # Drop blanks so a trailing comma is a typo rather than an error.
        return [_validate_origin(origin) for origin in origins if origin]

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

        if _is_local_sqlite_file(self.database_url):
            problems.append(
                "DATABASE_URL points at a local SQLite file "
                f"({_redact_url(self.database_url)!r}). A serverless or container "
                "filesystem "
                "is not durable, so learner accounts and progress would be lost "
                "on every restart or cold start -- and on a read-only filesystem "
                "the first query fails with 'unable to open database file'. Set a "
                "hosted libSQL/Turso URL (sqlite+libsql://...) or point at a "
                "persistent volume."
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
