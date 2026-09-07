"""Database access for lessons and their exercises."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Exercise, Lesson


def get_lesson(db: Session, lesson_id: int) -> Lesson | None:
    """One lesson without its exercises."""
    return db.get(Lesson, lesson_id)


def get_lesson_with_exercises(db: Session, lesson_id: int) -> Lesson | None:
    """One lesson with its exercises and parent skill loaded.

    ``selectinload`` for the exercises (a collection) and ``joinedload`` for the
    skill (a single parent, so a join adds one column set rather than
    multiplying rows). Three queries total, and the response needs all of it —
    unlike the path endpoint, which deliberately skips exercises.
    """
    return db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.exercises),
            joinedload(Lesson.skill),
        )
    )


def get_exercise(db: Session, exercise_id: int) -> Exercise | None:
    """One exercise, including its canonical answer (server-side only)."""
    return db.get(Exercise, exercise_id)


def count_exercises(db: Session, lesson_id: int) -> int:
    """How many exercises a lesson has.

    Used to decide whether an attempt has answered everything. A count rather
    than loading the rows: completion only needs the number.
    """
    return db.scalar(
        select(func.count())
        .select_from(Exercise)
        .where(Exercise.lesson_id == lesson_id)
    )


def lesson_ids_for_skill(db: Session, skill_id: int) -> list[int]:
    """Every lesson id belonging to a skill, in order."""
    return list(
        db.scalars(
            select(Lesson.id)
            .where(Lesson.skill_id == skill_id)
            .order_by(Lesson.order_index)
        ).all()
    )
