"""Database access for course content.

Every SQL query about courses lives here. Services call these functions and get
ORM objects back; they never build a ``select()`` themselves. That boundary is
what lets a service be read as business rules rather than as a mix of rules and
query construction.

These are plain functions taking a ``Session``, not a class. There is no
per-instance state to hold, and ``course_repo.get_tree(db, id)`` reads as well as
``CourseRepository(db).get_tree(id)`` while being simpler to call and to test.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Course, Skill, Unit


def list_courses(db: Session) -> list[Course]:
    """Every course, ordered by id for a stable response."""
    return list(db.scalars(select(Course).order_by(Course.id)).all())


def get_course(db: Session, course_id: int) -> Course | None:
    """One course, without its children. ``None`` if it does not exist."""
    return db.get(Course, course_id)


def get_course_tree(db: Session, course_id: int) -> Course | None:
    """One course with its units, skills and lessons eagerly loaded.

    **Loading strategy.** ``selectinload`` at each level, which emits one extra
    SELECT per level using ``WHERE parent_id IN (...)``:

        1. the course
        2. all units of that course
        3. all skills of those units
        4. all lessons of those skills

    Four queries, and — importantly — that count does not grow with the amount
    of content. The naive alternative is lazy loading, where iterating units then
    skills then lessons issues one query per parent: with 3 units and 9 skills
    that is 1 + 1 + 3 + 9 = 14 queries, and it degrades linearly as the course
    grows. That is the N+1 problem.

    ``joinedload`` would collapse it to a single query, but a chain of one-to-many
    joins multiplies rows (3 units x 3 skills x 2 lessons = 18 rows carrying the
    course's columns 18 times) and SQLAlchemy then de-duplicates them in Python.
    ``selectinload`` is the better fit for nested collections.

    **Exercises are deliberately not loaded.** The path screen never shows them,
    and eagerly loading 90 rows the response will discard would be waste. The
    lesson endpoint in Phase 4 loads them for one lesson at a time.
    """
    return db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.units)
            .selectinload(Unit.skills)
            .selectinload(Skill.lessons)
        )
    )
