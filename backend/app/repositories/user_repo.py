"""Database access for the learner and their stats."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserStats


def get_by_username(db: Session, username: str) -> User | None:
    """Find a user by their natural key. ``None`` if absent."""
    return db.scalar(select(User).where(User.username == username))


def get_by_email(db: Session, email: str) -> User | None:
    """Find a user by their login identifier. ``None`` if absent.

    The caller normalises the address first (``auth_service.normalize_email``);
    this is a plain equality match, which is what the unique index supports.
    """
    return db.scalar(select(User).where(User.email == email))


def get_by_display_name(db: Session, display_name: str) -> User | None:
    """Find a user by the name other learners see. ``None`` if absent."""
    return db.scalar(select(User).where(User.display_name == display_name))


def all_users(db: Session) -> list[User]:
    """Every learner, ordered by id.

    Used only by the Phase 9 migration, which must visit each row to backfill
    credentials. Nothing on a request path loads every user.
    """
    return list(db.scalars(select(User).order_by(User.id)).all())


def get_stats(db: Session, user_id: int) -> UserStats | None:
    """The learner's current gamification counters.

    A primary-key lookup, because ``user_stats.user_id`` *is* the primary key —
    which is also what guarantees there is at most one row to find.
    """
    return db.get(UserStats, user_id)
