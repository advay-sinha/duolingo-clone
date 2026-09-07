"""Course content models — the material the learner works through.

The chain is strictly one-to-many at every level:

    Course -> Unit -> Skill -> Lesson -> Exercise

Each level exists because the UI needs something it alone can provide:

* **Course** is the enrolment unit and the language pair; it is the root the
  learning path is queried from.
* **Unit** is the coloured banner and the grouping the path scrolls through.
* **Skill** is the path node — the thing that locks, unlocks and earns crowns.
* **Lesson** is one sitting: the unit of completion and of XP award.
* **Exercise** is one question.

Splitting Skill from Lesson is what makes crowns possible: a crown means "every
lesson in this skill is finished", which needs both levels to exist.

This content is **read-only at runtime**. Nothing here is per-user; user state
lives in ``app/models/progress.py`` and ``app/models/user.py``.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware creation timestamp helper."""
    return datetime.now(timezone.utc)


class ExerciseType(str, enum.Enum):
    """The five exercise types the lesson engine renders and grades.

    Inherits from ``str`` so the value stored in SQLite is a readable string
    ("MULTIPLE_CHOICE") rather than an integer — the database stays inspectable
    with a plain ``SELECT``.
    """

    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRANSLATE = "TRANSLATE"
    MATCH_PAIRS = "MATCH_PAIRS"
    FILL_BLANK = "FILL_BLANK"
    TYPE_ANSWER = "TYPE_ANSWER"


class Course(Base):
    """A language-learning course: one source/target language pair.

    The MVP seeds exactly one course (English -> Spanish). The table exists
    anyway because it is the root of the path query and because a single-course
    app with no course table cannot grow a second course without a schema change.
    """

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable natural key used by the seed to find an existing course instead of
    # inserting a duplicate. This is what makes seeding idempotent.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_language: Mapped[str] = mapped_column(String(40), nullable=False)
    target_language: Mapped[str] = mapped_column(String(40), nullable=False)
    flag_emoji: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    units: Mapped[list[Unit]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Unit.order_index",
    )


class Unit(Base):
    """A themed group of skills inside a course."""

    __tablename__ = "units"
    __table_args__ = (
        # Two units in the same course cannot claim the same position. This is
        # what makes the path order deterministic rather than incidental.
        UniqueConstraint("course_id", "order_index", name="uq_unit_order_in_course"),
        Index("ix_units_course_id", "course_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    color_key: Mapped[str] = mapped_column(String(24), default="green", nullable=False)

    course: Mapped[Course] = relationship(back_populates="units")
    skills: Mapped[list[Skill]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="Skill.order_index",
    )


class Skill(Base):
    """One node on the learning path.

    Deliberately stores **no** ``is_locked`` / ``is_available`` /
    ``is_completed`` columns. Those are per-user, derived states — see the
    "persisted vs derived" section of ``docs/CODEBASE_LEARNING.md``. Storing
    them would mean a row per user per skill that can silently disagree with the
    progress it is supposed to summarise.
    """

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("unit_id", "order_index", name="uq_skill_order_in_unit"),
        Index("ix_skills_unit_id", "unit_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Material Symbols icon name, so the path node's glyph is content, not code.
    icon: Mapped[str] = mapped_column(String(48), default="school", nullable=False)

    unit: Mapped[Unit] = relationship(back_populates="skills")
    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="Lesson.order_index",
    )
    progress_records: Mapped[list["UserSkillProgress"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )


class Lesson(Base):
    """One sitting inside a skill: the unit of completion and of XP award."""

    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("skill_id", "order_index", name="uq_lesson_order_in_skill"),
        Index("ix_lessons_skill_id", "skill_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Completion bonus, on top of the per-correct-answer XP. Stored per lesson so
    # a harder lesson can be worth more without touching application code.
    xp_reward: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    skill: Mapped[Skill] = relationship(back_populates="lessons")
    exercises: Mapped[list[Exercise]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="Exercise.order_index",
    )
    attempts: Mapped[list["LessonAttempt"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
    )


class Exercise(Base):
    """One question. **This table is the lesson engine.**

    Five exercise types share one table rather than getting a table each. The
    columns every type needs (type, prompt, instruction, ordering) are real
    columns; the parts that differ by type live in two JSON columns:

    * ``data`` — everything the learner is allowed to see: options, word-bank
      tokens, the pairs to match, the sentence with the blank.
    * ``correct_answer`` — the solution. **Never serialised to the client.** The
      response schema in Phase 4 simply will not declare this field, so it
      cannot leak by accident.

    **The trade-off, stated honestly.** JSON columns are not validated by the
    database and cannot be queried efficiently — a typo in a seed payload becomes
    a runtime error in the grader rather than an insert failure. What we buy is
    that adding a sixth exercise type needs no migration and no new table, and
    that a lesson is a single ordered read. For a content-driven app whose
    queries are always "give me the exercises for this lesson", that is the right
    side of the trade. Pydantic schemas in Phase 4 will validate each shape at
    the API boundary, which is where the checking actually belongs.
    """

    __tablename__ = "exercises"
    __table_args__ = (
        UniqueConstraint(
            "lesson_id", "order_index", name="uq_exercise_order_in_lesson"
        ),
        Index("ix_exercises_lesson_id", "lesson_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    # `native_enum=False` stores the value as VARCHAR and adds a CHECK
    # constraint listing the five valid values, so the database itself rejects
    # an unknown exercise type -- and the column stays readable in a plain
    # SELECT, unlike an integer enum.
    # `create_constraint=True` is required: SQLAlchemy defaults it to False, in
    # which case the column is a plain VARCHAR and the enum exists only in
    # Python. With it on, the CREATE TABLE carries a CHECK listing the five
    # valid values, so the database itself rejects an unknown exercise type.
    type: Mapped[ExerciseType] = mapped_column(
        Enum(
            ExerciseType,
            native_enum=False,
            length=24,
            create_constraint=True,
            validate_strings=True,
            name="ck_exercise_type",
        ),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # The eyebrow label above the question, e.g. "Select the translation".
    instruction: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # The question itself.
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    correct_answer: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    lesson: Mapped[Lesson] = relationship(back_populates="exercises")


# Imported at the bottom to keep the type annotations above resolvable without a
# circular import at module load time.
from app.models.progress import LessonAttempt, UserSkillProgress  # noqa: E402
