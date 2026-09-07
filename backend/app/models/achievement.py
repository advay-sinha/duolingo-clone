"""Achievements: the catalogue, and who has unlocked what.

Two tables rather than a JSON column on the user, for the usual reason: the
catalogue is content (seeded, shared, translatable later) while an unlock is a
per-user fact with a timestamp. Splitting them means adding an achievement is a
seed change, and the unique constraint below can do the work of preventing a
double award.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Achievement(Base):
    """One achievement in the catalogue. Content, not user state."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Natural key: the seed finds achievements by this, and the evaluator
    # dispatches on it. Stable across reseeds and readable in the database.
    key: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # A design-token colour key and a glyph name, so presentation is content.
    icon: Mapped[str] = mapped_column(String(32), default="star", nullable=False)
    color_key: Mapped[str] = mapped_column(String(24), default="gold", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    unlocks: Mapped[list["UserAchievement"]] = relationship(
        back_populates="achievement", cascade="all, delete-orphan"
    )


class UserAchievement(Base):
    """One learner has unlocked one achievement.

    A row exists only once unlocked — there is no "locked" row and no progress
    column. Locked state is the *absence* of a row, which the API composes
    against the catalogue. That keeps the table append-only and means an
    achievement can never be half-awarded.
    """

    __tablename__ = "user_achievements"
    __table_args__ = (
        # The idempotency guarantee. Evaluating twice cannot award twice, even
        # if two requests race past the service's own check.
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
        Index("ix_user_achievements_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    achievement: Mapped[Achievement] = relationship(back_populates="unlocks")
