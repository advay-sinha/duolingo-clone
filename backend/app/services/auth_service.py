"""Registration, login, logout, and resolving a session back to a learner.

**Scope, stated up front.** This is local authentication for a single-machine
demo. It is deliberately *not* an identity system: no OAuth, no email
verification, no password reset, no roles, no refresh tokens, no rate limiting.
What it does provide is the property the rest of the application actually needs —
several learners, each with their own progress, and a request that can be
attributed to exactly one of them.

Three ideas carry the whole module:

1. **Passwords are hashed with bcrypt, never stored or logged.** The plaintext
   exists only inside one request, as an argument to ``verify_password`` or
   ``hash_password``, and is never written anywhere.
2. **Sessions are rows, not tokens.** The cookie holds an opaque random string;
   the database holds its SHA-256. Deleting the row logs the browser out — which
   is what makes logout mean something (see the ``Session`` model for the JWT
   comparison).
3. **Authentication answers one question:** which ``User`` is making this
   request. Everything downstream — routes, services, repositories — takes a
   ``User`` and knows nothing about cookies.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import get_settings
from app.core.errors import ConflictError, DomainError
from app.models import Session, User, UserStats, UserSkillProgress
from app.models.content import Skill
from app.repositories import onboarding_repo, user_repo
from app.services.gamification import as_utc

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class AuthenticationError(DomainError):
    """The caller is not authenticated, or their credentials did not match.

    401 rather than 403: 403 means "we know who you are and you may not", 401
    means "we do not know who you are". The distinction is what lets the frontend
    decide to redirect to the login page rather than show an error.
    """

    status_code = 401
    code = "unauthenticated"


class ValidationError(DomainError):
    """A registration field is unusable. 422, like every other bad payload."""

    status_code = 422
    code = "invalid_request"


# The generic message used for *every* failed login. See `login()`.
INVALID_CREDENTIALS = "Email or password is incorrect."


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------

#: Short enough not to annoy, long enough to matter. Length is the only password
#: rule enforced: composition rules ("one digit, one symbol") are known to push
#: people toward predictable substitutions without adding real entropy.
MIN_PASSWORD_LENGTH = 8
#: bcrypt truncates at 72 *bytes* and silently ignores the rest, which would make
#: two different long passwords interchangeable. Rejecting is honest.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a password for storage.

    **Why bcrypt.** A password hash must be *slow* — that is its whole job.
    General-purpose digests (SHA-256, and certainly MD5) are designed to be fast,
    which is exactly wrong: it makes a stolen database cheap to attack offline.
    bcrypt is a purpose-built adaptive hash: it embeds a cost factor, so the work
    can be raised as hardware gets faster, and it generates and stores its own
    per-password salt inside the output string. That means no salt column, no
    chance of forgetting to salt, and two learners with the same password still
    get different hashes.

    The alternative considered was ``hashlib.pbkdf2_hmac``, which is in the
    standard library and would have added no dependency. bcrypt was chosen
    because it is the single-purpose tool, its output format is self-describing,
    and one small, ubiquitous, well-audited wheel is a fair price for the thing
    the whole security story rests on.
    """
    rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against a stored hash.

    ``bcrypt.checkpw`` compares in constant time, so the comparison itself does
    not leak how much of the hash matched. A malformed stored hash returns
    ``False`` rather than raising — a corrupt row must fail the login, not the
    request.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------
# Field validation
# --------------------------------------------------------------------------

# Deliberately permissive: "something@something.something, no spaces". Trying to
# fully validate an email address with a regular expression is a well-known way
# to reject valid addresses; the only real test is sending a message to it, which
# is out of scope here.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    """Trim and casefold, so one person cannot register the same address twice."""
    return email.strip().casefold()


def validate_registration(*, email: str, password: str, display_name: str) -> None:
    """Reject unusable registration input.

    Raises:
        ValidationError: with a message written for the person filling the form.
    """
    if not _EMAIL_RE.match(email):
        raise ValidationError("Enter a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValidationError("Password is too long.")
    if not display_name.strip():
        raise ValidationError("Display name cannot be empty.")
    if len(display_name.strip()) > 80:
        raise ValidationError("Display name is too long.")


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


def _digest(token: str) -> str:
    """SHA-256 of a session token, hex encoded.

    A fast hash, unlike passwords, and deliberately so: the token is 32 bytes of
    ``secrets`` randomness, so there is no dictionary to run against it. What the
    hash buys is that a database copy contains no usable session.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: DbSession, user: User) -> str:
    """Open a session for a user and return the token for the cookie.

    The token is returned once and never stored in plaintext. Committing here
    rather than leaving it to the caller keeps "the session exists" true before
    the response carrying the cookie is built.
    """
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(
        days=settings.session_lifetime_days
    )
    db.add(Session(id=_digest(token), user_id=user.id, expires_at=expires))
    db.commit()
    return token


def resolve_session(db: DbSession, token: str | None) -> User | None:
    """Return the learner a token belongs to, or ``None``.

    Expiry is checked here rather than swept by a job: a stale row simply stops
    authenticating anyone. It is also deleted on sight, so the table does not
    grow without bound in normal use.
    """
    if not token:
        return None

    session = db.get(Session, _digest(token))
    if session is None:
        return None

    if as_utc(session.expires_at) <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None

    return db.get(User, session.user_id)


def destroy_session(db: DbSession, token: str | None) -> bool:
    """Invalidate one session. Returns whether there was one to invalidate.

    Only this browser's session is removed, not every session the learner has —
    logging out on a laptop must not log them out on a phone.
    """
    if not token:
        return False
    session = db.get(Session, _digest(token))
    if session is None:
        return False
    db.delete(session)
    db.commit()
    return True


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def _derive_username(db: DbSession, email: str) -> str:
    """Build a unique internal username from an email address.

    ``username`` predates registration: it is the seed's natural key and the
    handle shown as ``@name`` on the profile. Rather than asking a new learner
    for a third identifier they do not care about, it is derived from the local
    part of their email and suffixed if taken.
    """
    base = re.sub(r"[^a-z0-9_.-]", "", email.split("@")[0].casefold()) or "learner"
    base = base[:40]
    candidate = base
    suffix = 2
    while user_repo.get_by_username(db, candidate) is not None:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def initialize_learner(db: DbSession, user: User) -> None:
    """Give a new learner the rows every screen assumes exist.

    A stats row (5 hearts, everything else zero) and a zeroed progress row for
    every skill in the course. **No course content is copied** — content is
    shared and progress is per-user, which is the whole reason they are separate
    tables.

    Creating the progress rows up front rather than lazily keeps the path query a
    plain join, exactly as the seed does for the demo learner. With them in place
    the existing ``path_service`` rule makes the first skill AVAILABLE and the
    rest LOCKED, with no special case for "new user".

    Since Phase 9.5 it also opens an onboarding row, so the learner is asked
    which course, how much they know, and where to start before they reach the
    path.

    Does not commit: the caller owns the transaction.
    """
    settings = get_settings()
    db.add(
        UserStats(
            user_id=user.id,
            total_xp=0,
            gems=0,
            hearts=settings.max_hearts,
            current_streak=0,
            longest_streak=0,
            daily_goal=settings.default_daily_goal,
            daily_xp=0,
        )
    )
    for skill_id in db.scalars(select(Skill.id).order_by(Skill.id)).all():
        db.add(UserSkillProgress(user_id=user.id, skill_id=skill_id))

    # Phase 9.5: every new learner starts onboarding. The row is written in the
    # same transaction as the user, which is what makes "no onboarding row" mean
    # exactly one thing -- this learner registered before onboarding existed --
    # and therefore what lets existing learners bypass it safely.
    onboarding_repo.create(db, user.id)


def register(
    db: DbSession, *, email: str, password: str, display_name: str
) -> tuple[User, str]:
    """Create a learner, initialise their progress, and log them in.

    One transaction: the user, their stats and their skill-progress rows are all
    written together or not at all. A half-registered learner — a row in
    ``users`` with no ``user_stats`` — would break every screen, and a 500 in the
    middle of registration is exactly when that could otherwise happen.

    Returns:
        The new user and their session token.

    Raises:
        ValidationError: unusable field.
        ConflictError: the email or display name is taken.
    """
    email = normalize_email(email)
    display_name = display_name.strip()
    validate_registration(email=email, password=password, display_name=display_name)

    if user_repo.get_by_email(db, email) is not None:
        raise ConflictError("An account with that email already exists.")
    if user_repo.get_by_display_name(db, display_name) is not None:
        raise ConflictError("That display name is taken.")

    try:
        user = User(
            username=_derive_username(db, email),
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            avatar_url="",
        )
        db.add(user)
        db.flush()  # the progress rows need the user's id
        initialize_learner(db, user)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return user, create_session(db, user)


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


def login(db: DbSession, *, email: str, password: str) -> tuple[User, str]:
    """Verify credentials and open a session.

    **Both failure modes return the same message.** "No such account" and "wrong
    password" are answered identically, because distinguishing them turns the
    login form into a tool for discovering which email addresses are registered.

    A hash is verified even when no user was found, against a throwaway hash of
    the submitted password. Skipping it would make the "unknown email" path
    measurably faster than the "wrong password" path, and that timing difference
    leaks the same information the shared message is there to hide.
    """
    user = user_repo.get_by_email(db, normalize_email(email))

    if user is None:
        verify_password(password, hash_password(password))
        raise AuthenticationError(INVALID_CREDENTIALS)

    if not verify_password(password, user.password_hash):
        raise AuthenticationError(INVALID_CREDENTIALS)

    return user, create_session(db, user)
