"""API schemas for the learning path.

This is the response the learn screen renders from. It is a *view of the domain*,
not a dump of tables: it carries computed state (`SkillState`) that exists in no
column, and omits everything the screen does not use.

**On progress representation.** The API returns `lessons_completed` and
`total_lessons`, and deliberately **not** a percentage. Those two numbers are the
facts; a percentage is a presentation of them. Sending both would mean shipping
the same information twice in two forms that can disagree if one is ever computed
differently, and the client needs the raw counts anyway to render "3 / 5". The
progress ring divides two integers it already has.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class SkillState(str, enum.Enum):
    """The three states a skill can be in for a given learner.

    **Not stored anywhere.** Computed by ``PathService`` from skill ordering and
    crowns — see ADR-14. A ``str`` enum so the JSON value is the readable
    `"AVAILABLE"` rather than an index.

    The Stitch design also distinguishes an "in progress" node visually. That is
    a rendering distinction, not a fourth domain state: the client shows it when
    ``lessons_completed > 0`` on an ``AVAILABLE`` skill, using numbers this
    response already carries. Keeping the server's vocabulary to three states
    avoids inventing domain concepts to serve a visual one.
    """

    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    COMPLETED = "COMPLETED"


class LessonNode(BaseModel):
    """One lesson within a skill."""

    id: int
    title: str
    order_index: int
    xp_reward: int
    # Derived from lesson_attempts, not stored on the lesson.
    completed: bool


class SkillNode(BaseModel):
    """One node on the path, with this learner's progress through it."""

    id: int
    title: str
    description: str
    order_index: int
    icon: str = Field(description="Material Symbols icon name for the node glyph")

    state: SkillState = Field(description="Derived; never stored in the database")
    crowns: int
    lessons_completed: int
    total_lessons: int
    xp_earned: int

    lessons: list[LessonNode]


class UnitNode(BaseModel):
    """A themed group of skills."""

    id: int
    title: str
    description: str
    order_index: int
    color_key: str = Field(description="Design-token key for the unit banner colour")
    skills: list[SkillNode]


class CoursePathResponse(BaseModel):
    """The whole learning path for one course and one learner.

    Everything the learn screen needs in a single request. The alternative — one
    call per unit, or a call per skill's progress — would mean the screen could
    render half-populated, and would multiply round trips for data that is always
    wanted together.
    """

    course_id: int
    course_title: str
    source_language: str
    target_language: str
    units: list[UnitNode]
