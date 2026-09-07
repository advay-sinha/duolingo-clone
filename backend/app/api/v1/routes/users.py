"""User routes."""

from fastapi import APIRouter

from app.api.v1.deps import CurrentUser, DbSession
from app.schemas.achievement import AchievementItem, AchievementListResponse
from app.schemas.user import (
    LearnerProfileResponse,
    UserStatsResponse,
    UserSummary,
)
from app.services import achievement_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserSummary,
    summary="Get the current learner",
    responses={503: {"description": "The database has not been seeded"}},
)
def get_me(user: CurrentUser) -> UserSummary:
    """Identity of the learner making the request.

    ``/me`` rather than ``/users/{id}`` because the server decides who the caller
    is — today from configuration, later from a token. A client that had to send
    its own id could ask for someone else's.
    """
    return UserSummary.model_validate(user)


@router.get(
    "/me/stats",
    response_model=UserStatsResponse,
    summary="Get the current learner's gamification stats",
    responses={503: {"description": "The database has not been seeded"}},
)
def get_my_stats(db: DbSession, user: CurrentUser) -> UserStatsResponse:
    """Return XP, hearts, streak, daily goal and gems.

    **Applies heart regeneration before responding**, which is why this read can
    write: refilled hearts are persisted rather than recomputed on every request.
    That makes this endpoint the learner's recovery path from zero hearts — wait
    thirty minutes, read stats, and a heart is back.

    XP, streak and crowns are untouched by that: regeneration only ever changes
    `hearts` and `hearts_updated_at`.
    """
    stats = user_service.current_stats(db, user)
    return UserStatsResponse.model_validate(stats)


@router.get(
    "/me/profile",
    response_model=LearnerProfileResponse,
    summary="Get the current learner's profile and lifetime statistics",
    responses={503: {"description": "The database has not been seeded"}},
)
def get_my_profile(db: DbSession, user: CurrentUser) -> LearnerProfileResponse:
    """Everything the profile screen shows, in one request.

    The aggregates are counted in SQL rather than derived in the browser, so the
    payload stays constant-sized however much the learner has practised.
    """
    result = user_service.profile(db, user)
    return LearnerProfileResponse(
        user=UserSummary.model_validate(result.user),
        stats=UserStatsResponse.model_validate(result.stats),
        lessons_completed=result.lessons_completed,
        skills_completed=result.skills_completed,
        total_crowns=result.total_crowns,
        perfect_lessons=result.perfect_lessons,
    )


@router.get(
    "/me/achievements",
    response_model=AchievementListResponse,
    summary="Get the current learner's achievements",
    responses={503: {"description": "The database has not been seeded"}},
)
def get_my_achievements(db: DbSession, user: CurrentUser) -> AchievementListResponse:
    """The full catalogue with this learner's unlock state.

    Locked achievements are included — a learner should be able to see what
    there is to earn — but the unlock *condition* is not exposed as data. The
    human-readable `description` is what the UI needs; the predicate stays on
    the server.
    """
    pairs = achievement_service.list_for_user(db, user)

    items = [
        AchievementItem(
            id=achievement.id,
            key=achievement.key,
            title=achievement.title,
            description=achievement.description,
            icon=achievement.icon,
            color_key=achievement.color_key,
            unlocked=unlock is not None,
            unlocked_at=unlock.unlocked_at if unlock else None,
        )
        for achievement, unlock in pairs
    ]

    return AchievementListResponse(
        achievements=items,
        unlocked_count=sum(1 for item in items if item.unlocked),
        total_count=len(items),
    )
