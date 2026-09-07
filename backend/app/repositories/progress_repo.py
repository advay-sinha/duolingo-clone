"""Database access for a learner's progress.

Both functions return *lookup structures* rather than lists of rows, because
that is what the caller actually needs. ``PathService`` walks the content tree
and asks "what is this learner's progress for this skill?" at every node; handing
it a dict lets that be a constant-time lookup instead of a scan, and — more
importantly — means one query serves the entire tree instead of one query per
skill.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LessonAttempt, UserSkillProgress


def skill_progress_map(db: Session, user_id: int) -> dict[int, UserSkillProgress]:
    """All of a learner's skill progress, keyed by ``skill_id``.

    One query for the whole path. Served by ``ix_user_skill_progress_user_id``.
    """
    rows = db.scalars(
        select(UserSkillProgress).where(UserSkillProgress.user_id == user_id)
    ).all()
    return {row.skill_id: row for row in rows}


def get_or_create_skill_progress(
    db: Session, *, user_id: int, skill_id: int
) -> UserSkillProgress:
    """Fetch this learner's progress row for a skill, creating it if absent.

    The seed creates a zeroed row per skill, so this normally finds one. It
    creates on demand anyway, because completion must not fail for a skill added
    to the course after the learner was seeded — and because the service should
    not depend on a seeding detail for correctness.

    ``flush`` rather than ``commit``: the caller owns the transaction.
    """
    progress = db.scalar(
        select(UserSkillProgress).where(
            UserSkillProgress.user_id == user_id,
            UserSkillProgress.skill_id == skill_id,
        )
    )
    if progress is None:
        progress = UserSkillProgress(user_id=user_id, skill_id=skill_id)
        db.add(progress)
        db.flush()
    return progress


def completed_lesson_ids(db: Session, user_id: int) -> set[int]:
    """Ids of every lesson this learner has completed at least once.

    Lesson completion is **derived from history**: a lesson is completed if a
    completed attempt exists for it. There is no ``lessons.completed`` column,
    and there should not be — completion is per user, and the attempt row already
    records it.

    Only the id column is selected, not whole ``LessonAttempt`` objects: the
    caller needs a membership test, and hydrating ORM objects to throw them away
    would be wasted work. Served by ``ix_lesson_attempts_user_id``.
    """
    return set(
        db.scalars(
            select(LessonAttempt.lesson_id)
            .where(
                LessonAttempt.user_id == user_id,
                LessonAttempt.completed.is_(True),
            )
            .distinct()
        ).all()
    )
