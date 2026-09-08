"""The placement test — an assessment, deliberately not a lesson.

**Why these are separate tables instead of reusing ``lesson_attempts``.** They
look similar on paper: a session, and a row per answer. Reusing the lesson tables
would have saved two ``CREATE TABLE`` statements and cost the single most
important property of this feature.

A ``LessonAttempt`` is the thing the gamification services act on. Completing one
awards XP, moves a streak, updates skill progress, and can unlock an achievement;
answering into one costs hearts. Every one of those rules is written against
"there is an attempt". If placement wrote attempt rows, keeping XP and hearts out
of an assessment would depend on remembering a flag in half a dozen services —
and a flag that must be checked in six places is a bug waiting for the seventh.

With separate tables the guarantee is **structural**: ``placement_service`` never
constructs a ``LessonAttempt``, never imports ``gamification``, and there is no
code path from a placement answer to ``user_stats``. That is the same reasoning
that keeps canonical answers out of responses by not declaring the field, applied
to state instead of to serialisation.

What is *shared* is the part worth sharing: the exercises themselves, the
``grading`` validators, and ``presentation.public_data``. Placement asks real
questions from the seeded course and grades them with the same pure functions the
lesson engine uses. There is no second lesson engine — there is a second
*consumer* of the first one.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware timestamp helper."""
    return datetime.now(timezone.utc)


class PlacementTest(Base):
    """One sitting of the placement test.

    A learner can have at most one *unfinished* test at a time, which is enforced
    by the service reusing an open row rather than by a partial unique index —
    SQLite supports one, but the rule ("at most one where completed_at is null")
    is easier to read as a sentence in the service than as an index predicate,
    and the consequence of a duplicate is a spare row, not corrupt state.

    The result columns are written once, by ``placement_service.complete``. They
    are stored rather than recomputed on read for the same reason ``user_stats``
    stores XP: the answer must not change if the scoring rules are later tuned.
    A learner placed at skill 5 last week was placed at skill 5, permanently.
    """

    __tablename__ = "placement_tests"
    __table_args__ = (
        Index("ix_placement_tests_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    #: The highest difficulty level the learner reliably passed, 0–5. Zero is a
    #: genuine outcome: it means no level was passed, and the learner starts at
    #: the first skill.
    result_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Weighted score, recorded for transparency. **Not** what decides the level
    #: — see ``placement_engine.score``.
    result_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_skill_id: Mapped[int | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), nullable=True
    )

    answers: Mapped[list["PlacementAnswer"]] = relationship(
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="PlacementAnswer.id",
    )


class PlacementAnswer(Base):
    """One graded answer inside a placement test.

    ``UNIQUE(test_id, exercise_id)`` for the same reason
    ``lesson_attempt_answers`` has one: a double-clicked button or a retried
    request must replay the recorded verdict rather than record a second one.
    Here it also protects something subtler — the adaptive rule reads this table
    to decide the next difficulty, so a duplicated answer would not just be an
    extra row, it would bend the test.

    ``difficulty`` is stored rather than recomputed from the exercise's position
    in the course. The banding is a rule that could be retuned; the level a
    question was *asked at* is a historical fact about this test, and scoring it
    later with a different rule than it was administered under would be wrong.
    """

    __tablename__ = "placement_answers"
    __table_args__ = (
        UniqueConstraint(
            "test_id", "exercise_id", name="uq_placement_answer_test_exercise"
        ),
        Index("ix_placement_answers_test_id", "test_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(
        ForeignKey("placement_tests.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )

    #: The difficulty level (1–5) this question was asked at.
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    test: Mapped[PlacementTest] = relationship(back_populates="answers")
