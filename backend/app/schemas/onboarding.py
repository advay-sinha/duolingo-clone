"""API schemas for onboarding.

One response model, ``OnboardingStatus``, returned by every onboarding endpoint.
That is deliberate: each step's response is the *whole* state, so the client
never has to merge a partial update into something it remembers. It asks, it is
told where it is, it navigates. See ADR-65.
"""

from __future__ import annotations

from datetime import datetime
import enum

from pydantic import BaseModel, ConfigDict, Field

from app.models import ProficiencyLevel, StartingMode


class OnboardingStep(str, enum.Enum):
    """The step the learner is on — **computed by the server, never stored**.

    Derived from which onboarding columns are still null, so it cannot disagree
    with the data it summarises. The frontend routes on this value rather than
    working the sequence out for itself, which is what makes the flow resumable
    after a refresh, a logout, or a login on another device: the server is the
    only thing that knows the order of the steps.
    """

    COURSE = "COURSE"
    PROFICIENCY = "PROFICIENCY"
    START = "START"
    PLACEMENT = "PLACEMENT"
    DONE = "DONE"


class PlacementSummary(BaseModel):
    """The stored outcome of a placement test, once one has been completed."""

    model_config = ConfigDict(from_attributes=True)

    level: int = Field(description="Highest consistently passed difficulty, 0-5")
    score: int
    max_score: int
    skill_id: int | None
    skill_title: str | None
    unit_title: str | None
    skills_placed_out: int = Field(
        description="How many skills the learner was placed beyond"
    )


class OnboardingStatus(BaseModel):
    """Where the learner is in onboarding, and what they have chosen so far."""

    completed: bool
    step: OnboardingStep
    course_id: int | None
    proficiency: ProficiencyLevel | None
    starting_mode: StartingMode | None
    #: Null unless the learner took a placement test.
    placement: PlacementSummary | None = None
    #: True for a learner who registered before onboarding existed. They have no
    #: onboarding row, and the correct thing to do with them is nothing.
    grandfathered: bool = False
    completed_at: datetime | None = None


class SelectCourseRequest(BaseModel):
    """`POST /onboarding/course`.

    A course *id*, validated against the courses table — not a language name.
    The "coming soon" cards on the picker have no row to point at, which is
    exactly what makes them unselectable: there is no id they could send.
    """

    course_id: int


class SelectProficiencyRequest(BaseModel):
    """`POST /onboarding/proficiency`.

    Typed as the enum, so FastAPI rejects anything that is not one of the five
    values with a 422 before the service runs. A free-form string would put that
    check in application code, where it could be forgotten.
    """

    proficiency: ProficiencyLevel


class SelectStartingModeRequest(BaseModel):
    """`POST /onboarding/start`."""

    mode: StartingMode
