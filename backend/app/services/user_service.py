"""Learner state: heart regeneration, and the composed profile.

**This module is the single owner of heart regeneration.** The rule itself is
the pure `gamification.regenerate_hearts`; applying it to a database row and
persisting the result happens here and nowhere else. Every caller that needs
current hearts — the stats endpoint, lesson start — goes through
`current_stats()`, so the calculation cannot drift between them and the frontend
never implements it at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.models import LessonAttempt, User, UserSkillProgress, UserStats
from app.services import gamification


def current_stats(db: Session, user: User, *, now: datetime | None = None) -> UserStats:
    """Return the learner's stats with heart regeneration applied.

    **This is a read that can write**, which is worth being explicit about: it
    persists regenerated hearts so the refill is durable rather than being
    recomputed — and re-granted — on every request.

    It commits only when hearts actually changed, so an ordinary read of a full
    or unchanged heart count issues no write at all.

    Args:
        now: Injectable for tests, so time boundaries can be checked
            deterministically rather than with `sleep()`.
    """
    settings = get_settings()
    stats = db.get(UserStats, user.id)
    if stats is None:
        raise NotFoundError(f"No stats row exists for user {user.id}.")

    moment = now or datetime.now(timezone.utc)

    result = gamification.regenerate_hearts(
        hearts=stats.hearts,
        # Stored naive by SQLite; `as_utc` states the assumption once.
        hearts_updated_at=gamification.as_utc(stats.hearts_updated_at),
        now=moment,
        max_hearts=settings.max_hearts,
        interval_minutes=settings.heart_regen_minutes,
    )

    if result.changed:
        try:
            stats.hearts = result.hearts
            stats.hearts_updated_at = result.updated_at
            db.commit()
        except Exception:
            db.rollback()
            raise

    return stats


@dataclass(frozen=True)
class LearnerProfile:
    """Everything the profile screen shows, assembled server-side."""

    user: User
    stats: UserStats
    lessons_completed: int
    skills_completed: int
    total_crowns: int
    perfect_lessons: int


def profile(db: Session, user: User) -> LearnerProfile:
    """Compose the learner's profile.

    The aggregates are counted in SQL rather than by shipping attempt rows to the
    client and letting it total them: the backend owns persistent statistics, and
    the frontend stays a renderer. It also keeps the payload constant-sized no
    matter how much the learner has practised.

    Applies heart regeneration on the way through, so the profile agrees with
    every other surface rather than showing a stale heart count.
    """
    stats = current_stats(db, user)

    lessons_completed = db.scalar(
        select(func.count())
        .select_from(LessonAttempt)
        .where(LessonAttempt.user_id == user.id, LessonAttempt.completed.is_(True))
    )
    perfect_lessons = db.scalar(
        select(func.count())
        .select_from(LessonAttempt)
        .where(
            LessonAttempt.user_id == user.id,
            LessonAttempt.completed.is_(True),
            LessonAttempt.incorrect_answers == 0,
            LessonAttempt.correct_answers > 0,
        )
    )
    skills_completed = db.scalar(
        select(func.count())
        .select_from(UserSkillProgress)
        .where(UserSkillProgress.user_id == user.id, UserSkillProgress.crowns >= 1)
    )
    total_crowns = db.scalar(
        select(func.coalesce(func.sum(UserSkillProgress.crowns), 0)).where(
            UserSkillProgress.user_id == user.id
        )
    )

    return LearnerProfile(
        user=user,
        stats=stats,
        lessons_completed=lessons_completed or 0,
        skills_completed=skills_completed or 0,
        total_crowns=total_crowns or 0,
        perfect_lessons=perfect_lessons or 0,
    )
