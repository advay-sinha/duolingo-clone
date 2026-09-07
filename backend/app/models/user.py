"""User identity and live gamification state.

Two tables, deliberately:

* ``users`` holds identity — written once, at signup (here, at seed time).
* ``user_stats`` holds the counters — written on almost every answer.

Splitting them keeps the hot, frequently-updated row narrow, and means a query
that only needs a display name does not read XP, hearts and streak with it. It
also makes the lifetimes obvious to a reader: one is a fact about a person, the
other is the state of a game in progress.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware timestamp helper."""
    return datetime.now(timezone.utc)


class User(Base):
    """A learner, with local credentials (Phase 9).

    Phases 1–8 had no password, no email and no session: one seeded learner was
    resolved by username. Phase 9 makes the app genuinely multi-user, so this row
    now carries what is needed to authenticate someone.

    **What is deliberately absent:** roles, email verification state, password
    reset tokens, OAuth identities, last-login tracking. Every one of them is a
    real feature of a real identity system and none is needed to let several
    learners keep separate progress on one machine.

    ``password_hash`` is a bcrypt hash and is **never** serialised. No response
    schema in the codebase declares a field for it — the same structural
    guarantee used for exercise answers, for the same reason.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Natural key: the seed looks a user up by username rather than by id, so
    # re-running it cannot create a second learner. Registration derives one
    # from the email, so a learner never has to invent two names.
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Unique, because it is the login identifier. Stored casefolded (see
    # `auth_service.normalize_email`) so "Alex@x.com" and "alex@x.com" are one
    # account rather than two.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # bcrypt output: algorithm, cost and salt are all encoded in this string, so
    # no separate salt column is needed and the cost can be raised later without
    # invalidating existing hashes.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Unique too: it is what other learners see on the leaderboard, and two
    # identical names there would be actively confusing.
    display_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # uselist=False makes this a genuine one-to-one: a user has exactly one
    # stats row, not a list containing one.
    stats: Mapped["UserStats"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    skill_progress: Mapped[list["UserSkillProgress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    lesson_attempts: Mapped[list["LessonAttempt"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserStats(Base):
    """The learner's current gamification state — one row per user.

    **This is the authoritative source of current state**, not an aggregate over
    ``lesson_attempts``. Reading total XP means reading one column, not summing a
    growing history table on every page load. The attempt history exists to
    answer "what happened", this row answers "where am I now".

    Every column here is *persisted* state. Nothing in this table is derived.
    """

    __tablename__ = "user_stats"
    __table_args__ = (
        # Hearts can never go negative or exceed the maximum, enforced by the
        # database rather than trusted to application code.
        CheckConstraint("hearts >= 0 AND hearts <= 5", name="ck_user_stats_hearts"),
    )

    # The user id is the primary key, not a separate surrogate id. That single
    # choice enforces "exactly one stats row per user" -- no extra unique
    # constraint needed, and a duplicate is impossible by construction.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    total_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gems: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    hearts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # When hearts last changed. Phase 4 regenerates hearts lazily by comparing
    # this to "now" on read, which avoids needing a scheduler or a background
    # worker for a purely time-based rule.
    hearts_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # A date, not a timestamp: the streak rule is "did they practise yesterday",
    # which is a calendar-day question. Storing a datetime would invite
    # comparing instants and getting timezone-dependent answers.
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    daily_goal: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    daily_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="stats")


class Session(Base):
    """One logged-in browser.

    **Why a database session rather than a JWT.** A JWT is self-contained, which
    is exactly the problem for a logout button: a signed token stays valid until
    it expires, so "log out" either does nothing server-side or needs a
    revocation list — which is a session table with extra steps. A row that can
    be deleted makes logout mean what the word says. At this scale the extra
    lookup per request is one indexed primary-key read.

    **Why the token is stored hashed.** ``id`` holds the SHA-256 of the token,
    never the token itself. Anyone who reads the database therefore cannot use
    what they find to impersonate a learner. A fast hash is correct here — unlike
    a password, the token is 32 bytes of `secrets` randomness, so there is
    nothing to brute-force.

    **Why expiry is a column, not a scheduler.** Same reasoning as heart
    regeneration: expiry is a pure function of a stored timestamp and the clock,
    checked on read. Nothing needs to sweep the table for the rule to be correct.
    """

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)

    #: SHA-256 hex digest of the opaque session token. The token itself exists
    #: only in the cookie and never on this server's disk.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


from app.models.progress import LessonAttempt, UserSkillProgress  # noqa: E402
