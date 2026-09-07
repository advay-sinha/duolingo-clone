"""API schemas for course listing.

**ORM model vs API schema — why both exist.**

``app/models/content.Course`` describes a *table*: every column, including
``slug``, ``created_at`` and ``flag_emoji``. ``CourseSummary`` below describes a
*response*: the fields a client needs to show and pick a course.

They are deliberately different objects, for three reasons:

1. **They change for different reasons.** Adding a column to support a future
   feature should not silently change what the API returns to existing clients.
2. **Not every column belongs in a response.** ``exercises.correct_answer`` is
   the sharpest example — Phase 4 must never serialise it, and the safest way to
   guarantee that is a schema that does not declare the field.
3. **A schema is a documented contract.** FastAPI turns these classes into the
   OpenAPI document, so the response shape is generated from the same definition
   that validates it, and the two cannot drift.

Returning ORM objects directly would make the database schema the public API,
so any refactor would become a breaking change for the frontend.
"""

from pydantic import BaseModel, ConfigDict, Field


class CourseSummary(BaseModel):
    """One course, as the client sees it."""

    # from_attributes lets Pydantic build this from an ORM object's attributes
    # rather than requiring a dict -- the bridge between the two worlds.
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str = Field(examples=["Spanish"])
    description: str
    source_language: str = Field(examples=["English"])
    target_language: str = Field(examples=["Spanish"])
    flag_emoji: str = Field(examples=["🇪🇸"])


class CourseListResponse(BaseModel):
    """Envelope for the course list.

    Wrapped in an object rather than returned as a bare JSON array so the
    response can gain fields later (a total, pagination) without changing its
    type from array to object — which would be a breaking change.
    """

    courses: list[CourseSummary]
