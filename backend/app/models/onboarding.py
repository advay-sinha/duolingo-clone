"""New-learner onboarding: the enrolment decisions made before learning starts.

**Why a separate table rather than columns on ``users``.** ``app/models/user.py``
already argues the case for splitting identity from state: ``users`` is a fact
about a person, written once; ``user_stats`` is the state of a game in progress,
written on almost every answer. Onboarding is a third lifetime again — four
decisions taken once, in the first minute, then never touched. Putting them on
``users`` would add four nullable columns to the row every login, every
leaderboard render and every session lookup reads, to carry data none of those
paths ever wants.

There is a second, sharper reason. ``users`` is the identity row, and the
password hash lives there. Every column added to it is a column some future
response model might serialise by accident. Keeping onboarding out of it keeps
that row as small as its job.

**The rule that makes existing learners safe: no row means onboarding is
complete.** Rows in this table are only ever created by registration, and only
from Phase 9.5 onward. So a learner with no row is, by construction, one who
predates onboarding — and the correct thing to do with them is exactly what they
expect: send them to ``/learn``. That is a true statement about the data rather
than a backfilled guess, it needs no migration step at all, and it means the
"do not break existing users" rule holds *even on a database the migration was
never run against*. See ADR-64.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware timestamp helper."""
    return datetime.now(timezone.utc)


class ProficiencyLevel(str, enum.Enum):
    """How much of the target language the learner says they already know.

    Five controlled values, one per card on the proficiency screen. A controlled
    enum rather than the card's English label because the label is copy — it will
    be rewritten, translated and A/B tested — while the stored value has to keep
    meaning the same thing forever.

    Inherits ``str`` for the same reason ``ExerciseType`` does: the column stays
    readable in a plain ``SELECT``.

    **This is self-report, and it is stored as self-report.** It does not feed
    the placement test and does not influence the learner's starting skill. See
    ``services/placement_engine.py`` for why.
    """

    BEGINNER = "BEGINNER"
    COMMON_WORDS = "COMMON_WORDS"
    BASIC_CONVERSATION = "BASIC_CONVERSATION"
    VARIOUS_TOPICS = "VARIOUS_TOPICS"
    ADVANCED = "ADVANCED"


class StartingMode(str, enum.Enum):
    """Which of the two starting-point cards the learner chose.

    ``SCRATCH`` completes onboarding immediately. ``PLACEMENT`` does not: it
    records the intent, and onboarding stays incomplete until the placement test
    is finished — which is what lets a learner close the tab mid-test and be
    returned to it.
    """

    SCRATCH = "SCRATCH"
    PLACEMENT = "PLACEMENT"


class UserOnboarding(Base):
    """One learner's progress through the onboarding flow.

    Every decision column is nullable, and **that nullability is the state
    machine**: the first null field, read in order, is the step the learner is
    on. There is no ``current_step`` column, because a stored step would be a
    second representation of something these columns already say — and the two
    could disagree. Same argument as the absent ``is_locked`` column on
    ``skills``.

    ``completed_at`` is a nullable timestamp rather than a boolean flag. It
    answers "is onboarding done?" exactly as well as a boolean and also answers
    "when?", which is worth having and costs nothing. ``LessonAttempt`` carries
    both a flag and a timestamp because an attempt can be *ended without being
    completed*; onboarding has no such state, so one column is enough.
    """

    __tablename__ = "user_onboarding"
    __table_args__ = (Index("ix_user_onboarding_course_id", "course_id"),)

    # The user id is the primary key, exactly as in `user_stats`: one row per
    # learner, guaranteed by the schema rather than by a service remembering to
    # check.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    #: The course the learner enrolled in. Nullable until they choose one.
    #: A real foreign key, not a language string: the "coming soon" languages on
    #: the picker are presentation only and have no row here to point at, which
    #: is precisely why they cannot be selected.
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )

    proficiency: Mapped[ProficiencyLevel | None] = mapped_column(
        Enum(
            ProficiencyLevel,
            native_enum=False,
            length=24,
            create_constraint=True,
            validate_strings=True,
            name="ck_proficiency_level",
        ),
        nullable=True,
    )

    starting_mode: Mapped[StartingMode | None] = mapped_column(
        Enum(
            StartingMode,
            native_enum=False,
            length=16,
            create_constraint=True,
            validate_strings=True,
            name="ck_starting_mode",
        ),
        nullable=True,
    )

    #: The level the placement test concluded, 0–5. ``0`` means "no level was
    #: passed", which is a real result and not a missing one — it is why this is
    #: distinct from ``None`` (no placement test was taken at all).
    placement_level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: The skill the learner was placed at. Null for ``SCRATCH``, where the
    #: answer is "the beginning" and the existing path rule already says so
    #: without anything being stored.
    placement_skill_id: Mapped[int | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="onboarding")

    @property
    def is_complete(self) -> bool:
        """Whether the learner has finished onboarding."""
        return self.completed_at is not None


from app.models.user import User  # noqa: E402
