"""Database access for placement tests, their answers, and their question pool.

The interesting function here is :func:`eligible_exercises`, which is the only
query in the codebase that walks the whole content tree for one course and comes
back with a flat, ordered list. It is what turns "the course is written
easiest-first" into a difficulty scale.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Exercise,
    Lesson,
    PlacementAnswer,
    PlacementTest,
    Skill,
    Unit,
)
from app.services.placement_engine import ELIGIBLE_TYPES


def open_test(db: Session, user_id: int) -> PlacementTest | None:
    """The learner's unfinished placement test, if they have one.

    Ordered newest-first so that a database which somehow holds two open tests
    (a crash between two requests, say) resolves to the most recent rather than
    to an arbitrary one.
    """
    return db.scalar(
        select(PlacementTest)
        .where(
            PlacementTest.user_id == user_id,
            PlacementTest.completed_at.is_(None),
        )
        .order_by(PlacementTest.id.desc())
    )


def get_test(db: Session, test_id: int) -> PlacementTest | None:
    """One placement test by id, without checking who it belongs to.

    Ownership is the service's decision, not the repository's — and it is
    checked there, on every call, before anything is read from the row.
    """
    return db.get(PlacementTest, test_id)


def latest_completed_test(db: Session, user_id: int) -> PlacementTest | None:
    """The learner's most recent finished test, for replaying a stored result."""
    return db.scalar(
        select(PlacementTest)
        .where(
            PlacementTest.user_id == user_id,
            PlacementTest.completed_at.is_not(None),
        )
        .order_by(PlacementTest.id.desc())
    )


def create_test(db: Session, *, user_id: int, course_id: int) -> PlacementTest:
    """Open a placement test. ``flush`` so the caller owns the transaction."""
    test = PlacementTest(user_id=user_id, course_id=course_id)
    db.add(test)
    db.flush()
    return test


def answers_for(db: Session, test_id: int) -> list[PlacementAnswer]:
    """Every answer in one test, in the order they were given.

    Order matters: the adaptive walk replays this list to work out which
    difficulty the next question should be asked at.
    """
    return list(
        db.scalars(
            select(PlacementAnswer)
            .where(PlacementAnswer.test_id == test_id)
            .order_by(PlacementAnswer.id)
        ).all()
    )


def get_answer(db: Session, *, test_id: int, exercise_id: int) -> PlacementAnswer | None:
    """One recorded answer, used to replay a resubmitted verdict."""
    return db.scalar(
        select(PlacementAnswer).where(
            PlacementAnswer.test_id == test_id,
            PlacementAnswer.exercise_id == exercise_id,
        )
    )


def eligible_exercises(db: Session, course_id: int) -> list[tuple[Exercise, int]]:
    """Every exercise the placement test may ask, with its skill's position.

    Returns ``(exercise, skill_index)`` pairs, where ``skill_index`` is the
    skill's position in the course's **global** skill order — across units, not
    within one. That global index is what the difficulty banding is computed
    from, so it has to be produced by the same ordering the path uses.

    The ordering is ``unit -> skill -> lesson -> exercise``, all by
    ``order_index``, which is the order a learner would meet them in. Filtering
    to ``ELIGIBLE_TYPES`` happens in SQL rather than in Python so the query
    returns only rows that can actually be used.

    One query with three joins. The alternative — loading the course tree and
    walking it — would work and would pull in every lesson and exercise the
    placement test will never ask.
    """
    rows = db.execute(
        select(Exercise, Skill.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Skill, Lesson.skill_id == Skill.id)
        .join(Unit, Skill.unit_id == Unit.id)
        .where(Unit.course_id == course_id, Exercise.type.in_(ELIGIBLE_TYPES))
        .order_by(
            Unit.order_index,
            Skill.order_index,
            Lesson.order_index,
            Exercise.order_index,
        )
    ).all()

    # A second, tiny query gives the global skill order. Deriving it from the
    # rows above would be wrong: a skill whose exercises are all ineligible would
    # silently vanish from the ordering and shift every later skill's index.
    ordered_skill_ids = ordered_skill_ids_for_course(db, course_id)
    position = {skill_id: index for index, skill_id in enumerate(ordered_skill_ids)}

    return [(exercise, position[skill_id]) for exercise, skill_id in rows]


def ordered_skill_ids_for_course(db: Session, course_id: int) -> list[int]:
    """Every skill id in the course, in the order a learner meets them.

    The same flattening ``path_service`` does when it walks units then skills —
    and it must stay the same, because the placement result is an index into
    this list.
    """
    return list(
        db.scalars(
            select(Skill.id)
            .join(Unit, Skill.unit_id == Unit.id)
            .where(Unit.course_id == course_id)
            .order_by(Unit.order_index, Skill.order_index)
        ).all()
    )
