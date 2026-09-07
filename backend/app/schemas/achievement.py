"""API schemas for achievements."""

from datetime import datetime

from pydantic import BaseModel, Field


class AchievementItem(BaseModel):
    """One achievement, with this learner's unlock state.

    Locked and unlocked achievements use the same shape — `unlocked` is the
    discriminator — so the client renders one list and styles by that flag,
    rather than merging two collections.

    The unlock *condition* is not exposed as data. `description` is the
    human-readable requirement ("Reach a 3-day streak"), which is all the UI
    needs; the predicate stays server-side where it is evaluated.
    """

    id: int
    key: str = Field(examples=["FIRST_LESSON"])
    title: str
    description: str
    icon: str
    color_key: str
    unlocked: bool
    unlocked_at: datetime | None = None


class AchievementListResponse(BaseModel):
    """`GET /users/me/achievements`."""

    achievements: list[AchievementItem]
    unlocked_count: int
    total_count: int
