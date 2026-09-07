"""Per-user progress: what the learner has achieved, and what they did.

Two tables with genuinely different jobs:

* ``user_skill_progress`` — **current state**, one row per user per skill. Read
  on every render of the learning path.
* ``lesson_attempts`` — **history**, one row per lesson session. Append-mostly,
  and never the source of a counter shown in the UI.

That distinction is the important idea in this module. It would be possible to
compute total XP by summing every attempt, but then the cost of loading the home
screen would grow with how much the learner has practised, and a change to the
XP rules would retroactively rewrite their past. Current state is stored;
history records what happened.

This module imports nothing from ``app.models.content`` — foreign keys and
relationships are declared by string name, which SQLAlchemy resolves from its
registry. That keeps the dependency one-directional and avoids a circular import.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware timestamp helper."""
    return datetime.now(timezone.utc)


class UserSkillProgress(Base):
    """How far one learner has got in one skill.

    **Persisted here:** lessons completed, crowns, XP earned in this skill, and
    when it was last touched.

    **Deliberately not persisted:** whether the skill is locked, available,
    active or completed. Those are computed in Phase 3 from skill ordering plus
    the ``crowns`` column below. A stored ``is_locked`` flag would be a second
    copy of a fact this row already implies, and the two can drift; a derived
    rule has exactly one implementation and cannot disagree with itself.

    ``total_lessons`` is also absent on purpose: it would duplicate
    ``len(skill.lessons)``, and would silently go stale if the seed content ever
    changed. The path query counts the skill's lessons instead.
    """

    __tablename__ = "user_skill_progress"
    __table_args__ = (
        # A learner has at most one progress row per skill. This is what makes
        # the row an upsert target on lesson completion and makes double-award
        # impossible at the storage level.
        UniqueConstraint("user_id", "skill_id", name="uq_progress_user_skill"),
        Index("ix_user_skill_progress_user_id", "user_id"),
        Index("ix_user_skill_progress_skill_id", "skill_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )

    lessons_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # A crown is awarded when every lesson in the skill has been completed.
    # It is also the unlock signal for the next skill.
    crowns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="skill_progress")
    skill: Mapped["Skill"] = relationship(back_populates="progress_records")


class LessonAttempt(Base):
    """One session of one lesson — the historical record.

    Created when a lesson starts and closed when it completes or is abandoned.
    From Phase 4 this row is what makes answer submission stateful: it gives the
    server a handle to attach graded answers to, so the client cannot replay a
    correct answer to farm XP.

    **This table is not the source of current stats.** ``user_stats`` is. An
    attempt records what happened in one sitting; it is read for history, for
    the profile's streak heatmap, and for debugging — never to compute the
    number in the header.
    """

    __tablename__ = "lesson_attempts"
    __table_args__ = (
        Index("ix_lesson_attempts_user_id", "user_id"),
        Index("ix_lesson_attempts_lesson_id", "lesson_id"),
        # Supports "has this learner ever completed this lesson?", the check that
        # stops a repeat completion from double-counting skill progress, and the
        # profile heatmap's date-ordered scan.
        Index("ix_lesson_attempts_user_lesson", "user_id", "lesson_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Explicit flag rather than "completed_at is not null" alone: it reads
    # clearly in a query and leaves room for an abandoned attempt that has an
    # end time but was never finished.
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    correct_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hearts_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship(back_populates="lesson_attempts")
    lesson: Mapped["Lesson"] = relationship(back_populates="attempts")
