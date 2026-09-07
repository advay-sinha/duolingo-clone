"""Leaderboard route."""

from fastapi import APIRouter

from app.api.v1.deps import CurrentUser, DbSession
from app.schemas.leaderboard import LeaderboardResponse
from app.services import leaderboard_service

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get(
    "",
    response_model=LeaderboardResponse,
    summary="Learner standings by lifetime XP",
    responses={503: {"description": "The database has not been seeded"}},
)
def get_leaderboard(db: DbSession, user: CurrentUser) -> LeaderboardResponse:
    """Return learners ranked by lifetime XP, with the caller's row flagged.

    The caller is resolved from the current-user dependency, never from a query
    parameter, so a client cannot ask to be highlighted as somebody else.
    """
    return leaderboard_service.standings(db, user)
