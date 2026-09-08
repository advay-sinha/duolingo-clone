"""Database access for a learner's onboarding row."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import UserOnboarding


def get(db: Session, user_id: int) -> UserOnboarding | None:
    """This learner's onboarding row, or ``None``.

    A primary-key lookup, because ``user_onboarding.user_id`` *is* the primary
    key — which is also what guarantees there is at most one row to find.

    ``None`` is a meaningful answer here and not an error: it means the learner
    registered before onboarding existed. See ``app/models/onboarding.py``.
    """
    return db.get(UserOnboarding, user_id)


def create(db: Session, user_id: int) -> UserOnboarding:
    """Start onboarding for a new learner.

    ``flush`` rather than ``commit``: registration owns the transaction, and the
    onboarding row must be written in the same one as the user it belongs to.
    """
    row = UserOnboarding(user_id=user_id)
    db.add(row)
    db.flush()
    return row
