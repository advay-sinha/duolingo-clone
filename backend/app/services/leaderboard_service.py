"""Leaderboard standings."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.repositories import leaderboard_repo
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse

#: Lifetime XP, stated in the response so the screen can label itself honestly.
PERIOD = "all-time"
METRIC = "total_xp"


def standings(db: Session, current_user: User) -> LeaderboardResponse:
    """Rank learners by lifetime XP.

    **Lifetime rather than weekly.** A weekly board would need a reset — either a
    scheduled job or a windowed query over attempt history — and the brief rules
    both out. Lifetime XP is already a single indexed column, is meaningful from
    day one, and needs no infrastructure. The response says `all-time` so the UI
    never implies a period the backend does not enforce.

    **No filler.** With one seeded learner this returns one row. Inventing
    opponents would make the screen look better and every number on it a lie.

    Ranks are assigned from the database's ordering; the query does the sorting.
    """
    settings = get_settings()
    rows = leaderboard_repo.top_by_xp(db, settings.leaderboard_limit)

    entries: list[LeaderboardEntry] = []
    current_rank: int | None = None

    for index, (user, stats) in enumerate(rows, start=1):
        is_current = user.id == current_user.id
        if is_current:
            current_rank = index
        entries.append(
            LeaderboardEntry(
                rank=index,
                user_id=user.id,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                xp=stats.total_xp,
                current_streak=stats.current_streak,
                is_current_user=is_current,
            )
        )

    return LeaderboardResponse(
        period=PERIOD,
        metric=METRIC,
        entries=entries,
        # None when the learner is outside the returned page -- the UI can then
        # say so rather than implying they are unranked.
        current_user_rank=current_rank,
    )
