"""Database tests: schema, relationships, constraints and the seed.

Every test runs against a **throwaway SQLite file** created in pytest's tmp
directory, never the development database. Each test seeds from scratch, so the
suite proves the seed works on an empty database — which is exactly what a
reviewer cloning the repository will do.
"""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 -- registers models on Base.metadata
from app.db.base import Base
from app.db.seed import seed
from app.models import (
    Course,
    Exercise,
    ExerciseType,
    Lesson,
    Skill,
    Unit,
    User,
    UserSkillProgress,
    UserStats,
)

# Expected seed shape. Written as constants so a content change that alters the
# course size fails loudly here rather than silently changing what the app ships.
EXPECTED_UNITS = 3
EXPECTED_SKILLS = 9
EXPECTED_LESSONS = 18
EXPECTED_EXERCISES = 90


@pytest.fixture
def db(tmp_path) -> Session:
    """A seeded, isolated database session.

    Builds a real SQLite *file* (not in-memory) so the test exercises the same
    driver and the same foreign-key behaviour as the running application.
    """
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )

    # The application enables this per connection in app/db/session.py; the test
    # engine is separate, so it must do the same or foreign keys would go
    # unenforced here and the constraint tests would pass for the wrong reason.
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def count(db: Session, model) -> int:
    """Row count for a model."""
    return db.scalar(select(func.count()).select_from(model))


# --------------------------------------------------------------------------
# Initialisation and table creation
# --------------------------------------------------------------------------


def test_all_expected_tables_are_created(db: Session) -> None:
    names = set(Base.metadata.tables)
    assert names == {
        "users",
        "user_stats",
        "courses",
        "units",
        "skills",
        "lessons",
        "exercises",
        "user_skill_progress",
        "lesson_attempts",
    }


# --------------------------------------------------------------------------
# Seed counts
# --------------------------------------------------------------------------


def test_seed_creates_exactly_one_user_and_one_course(db: Session) -> None:
    assert count(db, User) == 1
    assert count(db, Course) == 1


def test_seed_creates_the_expected_content_counts(db: Session) -> None:
    assert count(db, Unit) == EXPECTED_UNITS
    assert count(db, Skill) == EXPECTED_SKILLS
    assert count(db, Lesson) == EXPECTED_LESSONS
    assert count(db, Exercise) == EXPECTED_EXERCISES


def test_every_exercise_type_is_represented(db: Session) -> None:
    """All five types must exist, or the lesson engine cannot be demonstrated."""
    present = set(db.scalars(select(Exercise.type).distinct()).all())
    assert present == set(ExerciseType)


def test_each_skill_has_two_lessons_and_each_lesson_five_exercises(
    db: Session,
) -> None:
    for skill in db.scalars(select(Skill)).all():
        assert len(skill.lessons) == 2, f"{skill.title} has {len(skill.lessons)}"
    for lesson in db.scalars(select(Lesson)).all():
        assert len(lesson.exercises) == 5


# --------------------------------------------------------------------------
# Seed determinism
# --------------------------------------------------------------------------


def test_seeding_twice_does_not_duplicate_anything(db: Session) -> None:
    """The whole point of natural-key lookups: a second run is a no-op."""
    before = {
        model.__name__: count(db, model)
        for model in (User, Course, Unit, Skill, Lesson, Exercise, UserSkillProgress)
    }

    seed(db)
    seed(db)

    after = {
        model.__name__: count(db, model)
        for model in (User, Course, Unit, Skill, Lesson, Exercise, UserSkillProgress)
    }
    assert before == after


# --------------------------------------------------------------------------
# Relationships and referential integrity
# --------------------------------------------------------------------------


def test_the_content_tree_is_navigable_in_both_directions(db: Session) -> None:
    course = db.scalar(select(Course))
    assert len(course.units) == EXPECTED_UNITS

    unit = course.units[0]
    assert unit.course is course

    skill = unit.skills[0]
    assert skill.unit is unit

    lesson = skill.lessons[0]
    assert lesson.skill is skill

    exercise = lesson.exercises[0]
    assert exercise.lesson is lesson


def test_children_are_ordered_deterministically(db: Session) -> None:
    """Relationships declare order_by, so the path never renders shuffled."""
    course = db.scalar(select(Course))
    assert [u.order_index for u in course.units] == list(range(EXPECTED_UNITS))
    for unit in course.units:
        assert [s.order_index for s in unit.skills] == list(range(len(unit.skills)))
        for skill in unit.skills:
            assert [l.order_index for l in skill.lessons] == [0, 1]


def test_no_orphans_exist_anywhere_in_the_tree(db: Session) -> None:
    """Every child row resolves to a real parent."""
    assert db.scalar(
        select(func.count()).select_from(Unit).where(~Unit.course_id.in_(select(Course.id)))
    ) == 0
    assert db.scalar(
        select(func.count()).select_from(Skill).where(~Skill.unit_id.in_(select(Unit.id)))
    ) == 0
    assert db.scalar(
        select(func.count()).select_from(Lesson).where(~Lesson.skill_id.in_(select(Skill.id)))
    ) == 0
    assert db.scalar(
        select(func.count())
        .select_from(Exercise)
        .where(~Exercise.lesson_id.in_(select(Lesson.id)))
    ) == 0


def test_user_has_a_one_to_one_stats_row(db: Session) -> None:
    user = db.scalar(select(User))
    assert isinstance(user.stats, UserStats)
    assert user.stats.hearts == 5
    assert user.stats.gems == 540
    assert user.stats.total_xp == 0
    assert user.stats.current_streak == 0
    assert user.stats.daily_goal == 30
    # A brand-new learner has never practised; the app must render that state.
    assert user.stats.last_activity_date is None


def test_skill_progress_is_initialised_to_zero_for_every_skill(db: Session) -> None:
    user = db.scalar(select(User))
    progress = db.scalars(
        select(UserSkillProgress).where(UserSkillProgress.user_id == user.id)
    ).all()

    assert len(progress) == EXPECTED_SKILLS
    assert {p.skill_id for p in progress} == set(db.scalars(select(Skill.id)).all())
    assert all(p.lessons_completed == 0 and p.crowns == 0 for p in progress)
    assert all(p.xp_earned == 0 and p.last_completed_at is None for p in progress)


# --------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------


def test_username_must_be_unique(db: Session) -> None:
    db.add(User(username="learner", display_name="Impostor"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_user_cannot_have_two_progress_rows_for_one_skill(db: Session) -> None:
    user = db.scalar(select(User))
    skill = db.scalar(select(Skill))

    db.add(UserSkillProgress(user_id=user.id, skill_id=skill.id))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_two_units_cannot_share_a_position_in_a_course(db: Session) -> None:
    course = db.scalar(select(Course))
    db.add(Unit(course_id=course.id, title="Duplicate", order_index=0))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_foreign_keys_are_enforced(db: Session) -> None:
    """SQLite only enforces foreign keys when the pragma is on.

    Without the PRAGMA hook this insert would succeed and the schema's foreign
    keys would be decorative, so this test protects that hook specifically.
    """
    db.add(
        Lesson(skill_id=999_999, title="Lesson in a skill that does not exist",
               order_index=0)
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_hearts_cannot_exceed_the_maximum(db: Session) -> None:
    user = db.scalar(select(User))
    user.stats.hearts = 99
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_an_unknown_exercise_type_is_rejected_by_the_database(db: Session) -> None:
    """The enum CHECK constraint, verified through the raw driver.

    Going around the ORM on purpose: SQLAlchemy would reject the bad value in
    Python before it reached SQLite, which would prove the Python enum works but
    say nothing about the database.
    """
    lesson_id = db.scalar(select(Lesson.id))
    db.commit()

    raw: sqlite3.Connection = db.get_bind().raw_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(
                "INSERT INTO exercises "
                "(lesson_id, type, order_index, instruction, prompt, data, correct_answer) "
                "VALUES (?, 'SING_A_SONG', 99, '', 'x', '{}', '{}')",
                (lesson_id,),
            )
            raw.commit()
    finally:
        raw.rollback()
        raw.close()


# --------------------------------------------------------------------------
# Content sanity
# --------------------------------------------------------------------------


def test_exercise_payloads_have_the_right_shape_for_their_type(db: Session) -> None:
    """A malformed payload would only surface in the Phase 4 grader otherwise.

    JSON columns are not validated by the database — this test is what buys back
    that safety for the seeded content.
    """
    for exercise in db.scalars(select(Exercise)).all():
        data, answer = exercise.data, exercise.correct_answer

        if exercise.type is ExerciseType.MULTIPLE_CHOICE:
            ids = {o["id"] for o in data["options"]}
            assert len(ids) == len(data["options"]), "duplicate option ids"
            assert answer["option_id"] in ids

        elif exercise.type is ExerciseType.TRANSLATE:
            accepted = answer["accepted"][0]
            # Every word of the answer must be available in the word bank, or
            # the exercise is unsolvable.
            for word in accepted.split():
                assert word in data["tokens"], f"{word!r} missing from token pool"

        elif exercise.type is ExerciseType.MATCH_PAIRS:
            left_ids = {item["id"] for item in data["left"]}
            right_ids = {item["id"] for item in data["right"]}
            assert len(data["left"]) == len(data["right"])
            for left, right in answer["pairs"]:
                assert left in left_ids and right in right_ids
            # Each side is used exactly once.
            assert len({p[0] for p in answer["pairs"]}) == len(left_ids)
            assert len({p[1] for p in answer["pairs"]}) == len(right_ids)

        elif exercise.type is ExerciseType.FILL_BLANK:
            assert "___" in data["sentence"]
            assert answer["accepted"][0] in data["options"]

        elif exercise.type is ExerciseType.TYPE_ANSWER:
            assert answer["accepted"], "no accepted answer"
            assert all(a.strip() for a in answer["accepted"])


def test_match_pairs_are_not_solvable_by_reading_straight_across(
    db: Session,
) -> None:
    """The right column is deliberately reordered, so l1->r1 is not the answer."""
    for exercise in db.scalars(
        select(Exercise).where(Exercise.type == ExerciseType.MATCH_PAIRS)
    ).all():
        pairs = exercise.correct_answer["pairs"]
        assert any(left[1:] != right[1:] for left, right in pairs)


def test_spanish_characters_survive_the_round_trip(db: Session) -> None:
    """Accented characters must not be mangled by encoding."""
    prompts = " ".join(
        db.scalars(select(Exercise.prompt)).all()
        + [a for e in db.scalars(select(Exercise)).all() for a in e.correct_answer.get("accepted", [])]
    )
    assert "adiós" in prompts or "días" in prompts or "ó" in prompts
