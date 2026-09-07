"""Leaderboard queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserStats


def top_by_xp(db: Session, limit: int) -> list[tuple[User, UserStats]]:
    """Learners ordered by lifetime XP, highest first.

    **One query, ordered by the database.** Loading every learner into Python to
    sort them there would work for one seeded user and fall over at any real
    size — ordering and limiting are what a database is for, and `total_xp` is a
    column on a table with one row per user, so there is nothing to aggregate.

    Ties are broken by user id so the order is stable between requests; without
    it, two learners on equal XP could swap places on every refresh.

    Ranks are assigned by the caller from this order rather than by a SQL window
    function: `ROW_NUMBER()` would be equivalent here but adds a construct that
    is harder to read for no gain at this scale.
    """
    rows = db.execute(
        select(User, UserStats)
        .join(UserStats, UserStats.user_id == User.id)
        .order_by(UserStats.total_xp.desc(), User.id.asc())
        .limit(limit)
    ).all()
    return [(user, stats) for user, stats in rows]
