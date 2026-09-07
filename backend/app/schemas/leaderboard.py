"""API schemas for the leaderboard."""

from pydantic import BaseModel, Field


class LeaderboardEntry(BaseModel):
    """One row of the standings.

    Carries only what the screen renders. In particular there is no email, no
    created_at and no internal state — a leaderboard is the one place in the app
    where one learner's data is shown to another, so the schema is deliberately
    the narrowest in the codebase.
    """

    rank: int = Field(description="1-based position, highest XP first")
    user_id: int
    display_name: str
    avatar_url: str
    xp: int = Field(description="Lifetime XP, the ranking metric")
    current_streak: int
    #: Lets the client highlight the caller's own row without comparing ids
    #: itself, and without the server having to send who the caller is twice.
    is_current_user: bool


class LeaderboardResponse(BaseModel):
    """`GET /leaderboard`."""

    #: Stated in the response rather than assumed by the client, so changing the
    #: ranking period later does not silently mislabel the screen.
    period: str = Field(examples=["all-time"])
    metric: str = Field(examples=["total_xp"])
    entries: list[LeaderboardEntry]
    #: The caller's rank even if they fall outside the returned page. `None`
    #: only if they have no stats row at all.
    current_user_rank: int | None = None
