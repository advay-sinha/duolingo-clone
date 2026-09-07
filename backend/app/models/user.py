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

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware timestamp helper."""
    return datetime.now(timezone.utc)


class User(Base):
    """A learner.

    Authentication is deliberately out of scope for this assignment, so there is
    no password, no email and no session table. One learner is seeded and the
    API will resolve "the current user" through a single dependency in Phase 3 —
    which is the only place real auth would need to change.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Natural key: the seed looks a user up by username rather than by id, so
    # re-running it cannot create a second learner.
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

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


from app.models.progress import LessonAttempt, UserSkillProgress  # noqa: E402
