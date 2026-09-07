"""Idempotent database seeding.

Run it with::

    python -m app.db.seed

It creates the tables if they do not exist, then inserts the course content and
the default learner. **Running it repeatedly is safe** — the second run inserts
nothing and changes nothing.

How idempotency is achieved
---------------------------
Every entity is found by a **natural key** — something meaningful and stable in
the domain — instead of by its auto-increment id, which the seed does not know
in advance:

* course  -> ``slug``
* unit    -> ``(course_id, order_index)``
* skill   -> ``(unit_id, order_index)``
* lesson  -> ``(skill_id, order_index)``
* exercise-> ``(lesson_id, order_index)``
* user    -> ``username``
* stats   -> ``user_id`` (it is the primary key)
* progress-> ``(user_id, skill_id)``

Each of those pairs is backed by a real ``UNIQUE`` constraint in the schema, so
even if this logic had a bug the database itself would refuse a duplicate. The
"look it up, insert only if missing" pattern and the constraint reinforce each
other rather than the code being trusted alone.

**Why not delete-then-insert?** It is simpler to write, but it throws away user
progress every time it runs, and re-seeding is something you do *while*
developing — losing the learner's XP on every schema tweak would make the app
harder to work on, not easier. Non-destructive seeding is the safer default.

Transaction boundary
--------------------
The whole seed runs inside **one** transaction: one ``commit()`` at the very
end, ``rollback()`` on any exception. That matters because the content is a
tree. A failure halfway through a partial commit would leave a course with two
of its three units, and the next run would treat the two existing units as
already-seeded and never repair the third — a silently broken database. All or
nothing means a failure leaves exactly the state you started from.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.init_db import create_tables
from app.db.seed_data import COURSE, DEFAULT_USER
from app.db.session import SessionLocal
from app.models import (
    Course,
    Exercise,
    Lesson,
    Skill,
    Unit,
    User,
    UserSkillProgress,
    UserStats,
)


def _seed_course(db: Session) -> Course:
    """Insert the course tree, skipping anything already present."""
    course = db.scalar(select(Course).where(Course.slug == COURSE["slug"]))
    if course is None:
        course = Course(
            slug=COURSE["slug"],
            title=COURSE["title"],
            description=COURSE["description"],
            source_language=COURSE["source_language"],
            target_language=COURSE["target_language"],
            flag_emoji=COURSE["flag_emoji"],
        )
        db.add(course)
        # flush() sends the INSERT so `course.id` is populated for the children
        # below, without committing -- the transaction is still open and can
        # still be rolled back as a whole.
        db.flush()

    for unit_index, unit_data in enumerate(COURSE["units"]):
        unit = db.scalar(
            select(Unit).where(
                Unit.course_id == course.id, Unit.order_index == unit_index
            )
        )
        if unit is None:
            unit = Unit(
                course_id=course.id,
                title=unit_data["title"],
                description=unit_data["description"],
                color_key=unit_data["color_key"],
                order_index=unit_index,
            )
            db.add(unit)
            db.flush()

        for skill_index, skill_data in enumerate(unit_data["skills"]):
            skill = db.scalar(
                select(Skill).where(
                    Skill.unit_id == unit.id, Skill.order_index == skill_index
                )
            )
            if skill is None:
                skill = Skill(
                    unit_id=unit.id,
                    title=skill_data["title"],
                    description=skill_data["description"],
                    icon=skill_data["icon"],
                    order_index=skill_index,
                )
                db.add(skill)
                db.flush()

            for lesson_index, lesson_data in enumerate(skill_data["lessons"]):
                lesson = db.scalar(
                    select(Lesson).where(
                        Lesson.skill_id == skill.id,
                        Lesson.order_index == lesson_index,
                    )
                )
                if lesson is None:
                    lesson = Lesson(
                        skill_id=skill.id,
                        title=lesson_data["title"],
                        order_index=lesson_index,
                    )
                    db.add(lesson)
                    db.flush()

                for exercise_index, exercise_data in enumerate(
                    lesson_data["exercises"]
                ):
                    exists = db.scalar(
                        select(Exercise).where(
                            Exercise.lesson_id == lesson.id,
                            Exercise.order_index == exercise_index,
                        )
                    )
                    if exists is None:
                        db.add(
                            Exercise(
                                lesson_id=lesson.id,
                                type=exercise_data["type"],
                                order_index=exercise_index,
                                instruction=exercise_data["instruction"],
                                prompt=exercise_data["prompt"],
                                data=exercise_data["data"],
                                correct_answer=exercise_data["correct_answer"],
                            )
                        )

    return course


def _seed_user(db: Session) -> User:
    """Insert the default learner and their stats row, if absent."""
    user = db.scalar(select(User).where(User.username == DEFAULT_USER["username"]))
    if user is None:
        user = User(
            username=DEFAULT_USER["username"],
            display_name=DEFAULT_USER["display_name"],
            avatar_url=DEFAULT_USER["avatar_url"],
        )
        db.add(user)
        db.flush()

    stats = db.get(UserStats, user.id)
    if stats is None:
        db.add(UserStats(user_id=user.id, **DEFAULT_USER["stats"]))

    return user


def _seed_skill_progress(db: Session, user: User) -> None:
    """Create a zeroed progress row for every skill the learner has not started.

    Seeding these up front rather than creating them lazily on first completion
    means the Phase 3 path query is a plain join instead of a join plus a
    "missing row means zero" special case. The rows carry no state that matters
    yet — they are all zeros — so this costs nothing and removes a branch from
    the code that will be read most often.
    """
    skill_ids = db.scalars(select(Skill.id).order_by(Skill.id)).all()
    existing = set(
        db.scalars(
            select(UserSkillProgress.skill_id).where(
                UserSkillProgress.user_id == user.id
            )
        ).all()
    )

    for skill_id in skill_ids:
        if skill_id not in existing:
            db.add(UserSkillProgress(user_id=user.id, skill_id=skill_id))


def seed(db: Session) -> None:
    """Seed everything inside a single transaction.

    Args:
        db: An open session. The caller owns its lifetime; this function owns
            the transaction.
    """
    try:
        _seed_course(db)
        user = _seed_user(db)
        db.flush()  # ensure skills and the user have ids before pairing them
        _seed_skill_progress(db, user)
        db.commit()
    except Exception:
        # Leave the database exactly as it was rather than half-populated.
        db.rollback()
        raise


def main() -> None:
    """Entry point for ``python -m app.db.seed``."""
    create_tables()

    with SessionLocal() as db:
        seed(db)

        counts = {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in (
                User,
                UserStats,
                Course,
                Unit,
                Skill,
                Lesson,
                Exercise,
                UserSkillProgress,
            )
        }

    print("Seed complete.")
    for name, value in counts.items():
        print(f"  {name:>15}: {value}")


if __name__ == "__main__":
    main()
