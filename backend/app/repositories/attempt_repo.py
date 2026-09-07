"""Database access for lesson attempts and their answers.

None of these functions commit. That is deliberate and important: a commit
inside a repository would make multi-write transactions impossible, because the
first write would be durable before the rest were even attempted. The service
layer owns the transaction boundary — see ADR-31.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LessonAttempt, LessonAttemptAnswer, LessonAttemptPair


def create_attempt(db: Session, *, user_id: int, lesson_id: int) -> LessonAttempt:
    """Add a new attempt to the session and flush so it has an id.

    ``flush`` rather than ``commit``: the caller may still have work to do in the
    same transaction, and the id is needed either way.
    """
    attempt = LessonAttempt(user_id=user_id, lesson_id=lesson_id)
    db.add(attempt)
    db.flush()
    return attempt


def get_attempt(db: Session, attempt_id: int) -> LessonAttempt | None:
    """One attempt by id, or ``None``."""
    return db.get(LessonAttempt, attempt_id)


def get_answer(
    db: Session, *, attempt_id: int, exercise_id: int
) -> LessonAttemptAnswer | None:
    """The existing answer for one exercise in one attempt, if any.

    This lookup is the first half of idempotency: a resubmission finds the
    original row and returns it instead of grading again. The
    ``UNIQUE(attempt_id, exercise_id)`` constraint is the second half — the part
    that holds even if two requests race past this check simultaneously.
    """
    return db.scalar(
        select(LessonAttemptAnswer).where(
            LessonAttemptAnswer.attempt_id == attempt_id,
            LessonAttemptAnswer.exercise_id == exercise_id,
        )
    )


def list_answers(db: Session, attempt_id: int) -> list[LessonAttemptAnswer]:
    """Every answer recorded for an attempt."""
    return list(
        db.scalars(
            select(LessonAttemptAnswer)
            .where(LessonAttemptAnswer.attempt_id == attempt_id)
            .order_by(LessonAttemptAnswer.id)
        ).all()
    )


def count_answers(db: Session, attempt_id: int) -> int:
    """How many exercises this attempt has answered."""
    return db.scalar(
        select(func.count())
        .select_from(LessonAttemptAnswer)
        .where(LessonAttemptAnswer.attempt_id == attempt_id)
    )


def completed_lesson_ids_in(
    db: Session, *, user_id: int, lesson_ids: list[int]
) -> set[int]:
    """Which of these lessons the learner has ever completed.

    Used to recompute a skill's progress from persisted state rather than
    incrementing a counter — see ``lesson_service.complete_lesson``.
    """
    if not lesson_ids:
        return set()
    return set(
        db.scalars(
            select(LessonAttempt.lesson_id)
            .where(
                LessonAttempt.user_id == user_id,
                LessonAttempt.lesson_id.in_(lesson_ids),
                LessonAttempt.completed.is_(True),
            )
            .distinct()
        ).all()
    )


def has_completed_lesson(db: Session, *, user_id: int, lesson_id: int) -> bool:
    """Whether the learner has ever completed this lesson before.

    Drives the "first completion only" XP rule, so replaying a lesson cannot
    farm unlimited XP.
    """
    return (
        db.scalar(
            select(LessonAttempt.id)
            .where(
                LessonAttempt.user_id == user_id,
                LessonAttempt.lesson_id == lesson_id,
                LessonAttempt.completed.is_(True),
            )
            .limit(1)
        )
        is not None
    )


def get_pair(
    db: Session, *, attempt_id: int, exercise_id: int, left_id: str, right_id: str
) -> LessonAttemptPair | None:
    """One previously graded pair submission, if this exact pair was tried.

    Keyed on the *submission*, not on the left item: trying ``l1 → r2`` and then
    ``l1 → r3`` are two different attempts and both are recorded. See the
    ``LessonAttemptPair`` docstring.
    """
    return db.scalar(
        select(LessonAttemptPair).where(
            LessonAttemptPair.attempt_id == attempt_id,
            LessonAttemptPair.exercise_id == exercise_id,
            LessonAttemptPair.left_id == left_id,
            LessonAttemptPair.right_id == right_id,
        )
    )


def matched_pairs(
    db: Session, *, attempt_id: int, exercise_id: int
) -> list[LessonAttemptPair]:
    """Every pair correctly matched so far in this exercise, oldest first.

    This is the progress record the client renders as "locked" tiles, and the
    server's own answer to "is this exercise finished yet?".
    """
    return list(
        db.scalars(
            select(LessonAttemptPair)
            .where(
                LessonAttemptPair.attempt_id == attempt_id,
                LessonAttemptPair.exercise_id == exercise_id,
                LessonAttemptPair.is_correct.is_(True),
            )
            .order_by(LessonAttemptPair.id)
        ).all()
    )


def count_wrong_pairs(db: Session, *, attempt_id: int, exercise_id: int) -> int:
    """How many distinct wrong pairs have been submitted for this exercise.

    Decides whether the finished exercise counts as correct: a match-pairs
    exercise completed without a single wrong pair earns XP, exactly like any
    other exercise answered right first time.
    """
    return (
        db.scalar(
            select(func.count())
            .select_from(LessonAttemptPair)
            .where(
                LessonAttemptPair.attempt_id == attempt_id,
                LessonAttemptPair.exercise_id == exercise_id,
                LessonAttemptPair.is_correct.is_(False),
            )
        )
        or 0
    )
