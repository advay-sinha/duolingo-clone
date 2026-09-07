"""API schemas for the learner and their stats."""

from pydantic import BaseModel, ConfigDict, Field


class UserSummary(BaseModel):
    """Identity, for the profile header and the HUD avatar."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    avatar_url: str


class LearnerProfileResponse(BaseModel):
    """`GET /users/me/profile` — everything the profile screen shows.

    One composed response rather than three round trips. More importantly, the
    aggregates below are **counted in SQL**: the alternative is shipping every
    lesson attempt to the browser and letting it total them, which grows without
    bound and would put a persistent statistic in the client's hands. The
    backend owns statistics; the frontend renders them.
    """

    user: UserSummary
    stats: "UserStatsResponse"

    lessons_completed: int = Field(description="Distinct lessons ever completed")
    skills_completed: int = Field(description="Skills with at least one crown")
    total_crowns: int
    perfect_lessons: int = Field(description="Completed lessons with no mistakes")


class UserStatsResponse(BaseModel):
    """Every gamification counter the UI shows, in one response.

    Read straight from the ``user_stats`` row — **not** aggregated from
    ``lesson_attempts``. That row is the authoritative current state (ADR-15);
    the attempt history answers "what happened", this answers "where am I now".

    ``max_hearts`` is included even though it is a constant today: the client
    renders "4 of 5" and should not hard-code the 5, so the server states the
    rule it owns.
    """

    model_config = ConfigDict(from_attributes=True)

    total_xp: int = Field(examples=[0])
    gems: int
    hearts: int
    max_hearts: int = Field(default=5, description="Maximum hearts a learner can hold")

    current_streak: int
    longest_streak: int

    daily_goal: int = Field(description="Daily XP target")
    daily_xp: int = Field(description="XP earned today, toward the daily goal")


# `LearnerProfileResponse` references `UserStatsResponse`, which is defined
# below it for readability; this resolves the forward reference.
LearnerProfileResponse.model_rebuild()
