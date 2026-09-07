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

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
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
    answers: Mapped[list["LessonAttemptAnswer"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class LessonAttemptAnswer(Base):
    """One submitted answer within one attempt.

    **Added in Phase 4, deliberately not earlier** (ADR-16). Phase 2 left it out
    because nothing wrote or read it; every reason for it to exist is a Phase 4
    reason, and all three arrive at once:

    1. **Idempotency.** ``UNIQUE(attempt_id, exercise_id)`` is what makes a
       resubmitted answer harmless. Without it, a double-clicked Check button or
       a retried request would deduct a second heart for the same mistake. The
       constraint is the mechanism — the service checks first, but the database
       is what actually guarantees it under a race.
    2. **Server-authoritative completion.** The server must decide whether a
       lesson is finished from data it produced itself, not from a client
       claiming "I answered everything". These rows are that data.
    3. **XP the server can trust.** Completion sums the XP recorded here rather
       than accepting a score from the client.

    Storing ``submitted`` costs little and makes an attempt reviewable — useful
    for debugging a disputed grading, and the raw material for a "review your
    mistakes" screen later.
    """

    __tablename__ = "lesson_attempt_answers"
    __table_args__ = (
        # The whole point of the table. One answer per exercise per attempt.
        UniqueConstraint(
            "attempt_id", "exercise_id", name="uq_answer_attempt_exercise"
        ),
        Index("ix_lesson_attempt_answers_attempt_id", "attempt_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_attempts.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )

    # What the learner sent, stored verbatim as JSON. Shapes differ per exercise
    # type, and the grader is the only thing that needs to interpret them.
    submitted: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # XP this answer is worth. Recorded now, credited to user_stats only at
    # completion -- see the XP ownership table in CODEBASE_LEARNING.md.
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hearts_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempt: Mapped[LessonAttempt] = relationship(back_populates="answers")


class LessonAttemptPair(Base):
    """One pair the learner tried to match, in one match-pairs exercise.

    **Why this table exists (Phase 9).** Match pairs used to be graded like every
    other exercise: build the whole mapping, press Check, get one verdict. The
    Duolingo interaction grades each pair the moment it is formed, which needs a
    record per *pair submission* — and ``lesson_attempt_answers`` cannot hold
    that, because ``UNIQUE(attempt_id, exercise_id)`` allows exactly one row per
    exercise.

    **Why not store the progress as JSON in that one row instead.** It would work
    and it would need no migration, but idempotency would then rest on the
    service reading and rewriting a JSON blob — two racing double-click requests
    could both read "not yet charged" and both deduct a heart. The whole reason
    ``lesson_attempt_answers`` has a unique constraint is that the database, not
    the service, is what actually guarantees idempotency. The same argument
    applies here, so the same mechanism is used.

    **The uniqueness rule is on the submission, not on the left item.** A learner
    may try ``l1 → r2`` (wrong, one heart), then ``l1 → r3`` (right). Those are
    two different attempts at the same left item and both must be recorded. What
    must never happen twice is the *same* pair being charged twice, which is
    exactly ``UNIQUE(attempt_id, exercise_id, left_id, right_id)``.

    **This table does not replace the exercise-level answer row.** When the last
    pair is matched, the service writes the usual ``lesson_attempt_answers`` row,
    so completion, XP and accuracy all work exactly as before and there is no
    second lesson engine.
    """

    __tablename__ = "lesson_attempt_pairs"
    __table_args__ = (
        # One charge per distinct submission. A retried request finds the row and
        # replays its verdict instead of grading — and losing a second heart.
        UniqueConstraint(
            "attempt_id",
            "exercise_id",
            "left_id",
            "right_id",
            name="uq_pair_attempt_exercise_pair",
        ),
        Index(
            "ix_lesson_attempt_pairs_attempt_exercise", "attempt_id", "exercise_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_attempts.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )

    # The ids from the exercise's public payload ("l1", "r3"), not database ids.
    left_id: Mapped[str] = mapped_column(String(32), nullable=False)
    right_id: Mapped[str] = mapped_column(String(32), nullable=False)

    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hearts_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempt: Mapped[LessonAttempt] = relationship()
