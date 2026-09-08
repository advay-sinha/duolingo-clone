"""Running a placement test: choosing questions, grading them, and placing.

This module is the *stateful* half of placement. All of the judgement lives next
door in ``placement_engine.py``, which is pure and has no idea a database exists;
everything here is loading rows, writing rows, and owning the transaction.

**Three properties this file is written to guarantee, structurally:**

1. **No reward can leak out of an assessment.** No ``LessonAttempt`` is created,
   ``gamification`` is never imported, ``user_stats`` is never opened, and no
   response model here declares an XP, heart or streak field. Keeping XP out of
   placement is not a rule anyone has to remember — there is no code path.
2. **The learner never decides their own level.** The client sends two things:
   which test, and an answer. Difficulty, correctness, score, level and starting
   skill are all computed here from rows the server wrote.
3. **The current question is never stored.** It is derived from the answers
   already recorded, so a refresh, a dropped response or a second tab all
   converge on the same question rather than losing the learner's place.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import (
    Exercise,
    PlacementAnswer,
    PlacementTest,
    Skill,
    StartingMode,
    User,
    UserOnboarding,
)
from app.repositories import lesson_repo, placement_repo, progress_repo
from app.schemas.lesson import ExercisePublic
from app.schemas.placement import (
    PlacementQuestion,
    PlacementResultResponse,
    PlacementStateResponse,
    SubmitPlacementAnswerResponse,
)
from app.services import grading, onboarding_service, placement_engine, presentation
from app.services.grading import InvalidAnswerError
from app.services.placement_engine import (
    AnsweredQuestion,
    QUESTION_COUNT,
    STARTING_LEVEL,
)


# --------------------------------------------------------------------------
# Question selection
# --------------------------------------------------------------------------


def _pool(db: DbSession, course_id: int) -> tuple[dict[int, list[Exercise]], int]:
    """The question pool, grouped by difficulty band.

    Returns ``({difficulty: [exercise, ...]}, skill_count)``, each band's list in
    course order. Built once per request rather than queried per question: the
    whole eligible pool for the seeded course is 72 rows, and the alternative is
    a query inside the fallback loop below.
    """
    skill_ids = placement_repo.ordered_skill_ids_for_course(db, course_id)
    skill_count = len(skill_ids)
    if skill_count == 0:
        raise NotFoundError("This course has no skills to place against.")

    bands: dict[int, list[Exercise]] = {}
    for exercise, skill_index in placement_repo.eligible_exercises(db, course_id):
        level = placement_engine.difficulty_of(skill_index, skill_count)
        bands.setdefault(level, []).append(exercise)
    return bands, skill_count


def _target_difficulty(answers: list[PlacementAnswer]) -> int:
    """The band the next question should come from.

    Replayed from history rather than stored: the walk is
    ``STARTING_LEVEL`` then one step per verdict, so the answers *are* the state.
    Nothing can drift, and there is no "current level" column to get out of sync
    with the answers that produced it.
    """
    if not answers:
        return STARTING_LEVEL
    last = answers[-1]
    return placement_engine.next_difficulty(last.difficulty, last.is_correct)


def _select(
    bands: dict[int, list[Exercise]], target: int, used: set[int]
) -> tuple[Exercise, int] | None:
    """Pick an unused exercise as close to ``target`` difficulty as possible.

    The fallback matters more than it looks. A band can run dry — a short course,
    or a long test that keeps returning to the same level — and the learner must
    never be shown a question twice, because the adaptive rule reads its own
    history and a repeat would bend the test. Searching outward from the target
    keeps the question as close to the intended difficulty as the content allows.

    Ties are broken toward the **easier** band. On an assessment, guessing low is
    the recoverable mistake: an easy question the learner gets right pushes the
    walk straight back up, whereas a too-hard one costs them a level.
    """
    for distance in range(0, placement_engine.LEVELS):
        for level in (target - distance, target + distance):
            if level < 1 or level > placement_engine.LEVELS:
                continue
            for exercise in bands.get(level, ()):
                if exercise.id not in used:
                    return exercise, level
    return None


def _question(
    db: DbSession, test: PlacementTest, answers: list[PlacementAnswer]
) -> PlacementQuestion | None:
    """The question to show right now, or ``None`` when the test is over."""
    bands, _ = _pool(db, test.course_id)
    used = {answer.exercise_id for answer in answers}
    picked = _select(bands, _target_difficulty(answers), used)

    if placement_engine.is_finished(len(answers), picked is not None):
        return None
    if picked is None:
        return None

    exercise, difficulty = picked
    return PlacementQuestion(
        # The same public projection the lesson engine uses, which is what keeps
        # the canonical answer out of the payload *and* shuffles the options so
        # the answer cannot be inferred from its position (Phase 8).
        exercise=ExercisePublic(
            id=exercise.id,
            type=exercise.type,
            order_index=exercise.order_index,
            instruction=exercise.instruction,
            prompt=exercise.prompt,
            data=presentation.public_data(exercise),
        ),
        difficulty=difficulty,
        number=len(answers) + 1,
    )


def _state(
    db: DbSession, test: PlacementTest, answers: list[PlacementAnswer]
) -> PlacementStateResponse:
    question = _question(db, test, answers)
    return PlacementStateResponse(
        test_id=test.id,
        total_questions=QUESTION_COUNT,
        answered_count=len(answers),
        finished=question is None,
        question=question,
    )


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


def _owned_test(db: DbSession, user: User, test_id: int) -> PlacementTest:
    """Load a test and prove it belongs to the caller.

    The id in the request body names a row; it does **not** name a person. Who is
    asking comes from the session, and these two lines are what stop one learner
    from answering into — or completing — another learner's placement test.
    """
    test = placement_repo.get_test(db, test_id)
    if test is None:
        raise NotFoundError(f"Placement test {test_id} does not exist.")
    if test.user_id != user.id:
        raise ForbiddenError("That placement test belongs to another learner.")
    return test


def _onboarding_for_placement(db: DbSession, user: User) -> UserOnboarding:
    """The learner's open onboarding row, ready for placement.

    Refuses a learner who has finished onboarding, and one who chose "start from
    scratch" — the placement endpoints are not a back door into re-placing an
    account that is already learning.
    """
    row = onboarding_service.open_row(db, user)
    if row.course_id is None:
        raise ConflictError("Choose a course first.")
    if row.starting_mode is not StartingMode.PLACEMENT:
        raise ConflictError("Choose 'Find my level' first.")
    return row


# --------------------------------------------------------------------------
# The three operations
# --------------------------------------------------------------------------


def start(db: DbSession, user: User) -> PlacementStateResponse:
    """Open a placement test, or return the one already in progress.

    **Idempotent on purpose.** The placement screen calls this every time it
    mounts, so a refresh, a back-navigation or a second tab all resume the same
    test rather than starting a new one and losing the answers already given.
    """
    row = _onboarding_for_placement(db, user)

    test = placement_repo.open_test(db, user.id)
    if test is None:
        test = placement_repo.create_test(
            db, user_id=user.id, course_id=row.course_id
        )
        db.commit()

    return _state(db, test, placement_repo.answers_for(db, test.id))


def submit_answer(
    db: DbSession, user: User, *, test_id: int, exercise_id: int, answer: dict
) -> SubmitPlacementAnswerResponse:
    """Grade one placement answer and hand back the next question.

    Graded by ``grading.validate`` — the *same* five pure validators the lesson
    engine uses, against the same canonical answers. Placement is a different
    domain, not a different definition of "correct".

    Raises:
        ForbiddenError: the test belongs to another learner.
        ConflictError: the test is already finished.
        NotFoundError: unknown test or exercise.
        InvalidAnswerError: the payload is malformed for this exercise type. The
            route turns it into a 422, and — as in a lesson — it is not recorded
            as a wrong answer. A client bug must not move the learner's level.
    """
    test = _owned_test(db, user, test_id)
    if test.completed_at is not None:
        raise ConflictError("This placement test is already finished.")

    answers = placement_repo.answers_for(db, test.id)

    # Idempotency, before anything is graded or written. A retried request after
    # a dropped response replays the recorded verdict instead of adding a second
    # answer — which would not merely duplicate a row, it would feed the adaptive
    # walk an extra data point and change the test.
    existing = placement_repo.get_answer(
        db, test_id=test.id, exercise_id=exercise_id
    )
    if existing is not None:
        exercise = lesson_repo.get_exercise(db, exercise_id)
        verdict_answer = (
            grading.validate(exercise, existing.submitted).correct_answer
            if exercise
            else None
        )
        replayed = _question(db, test, answers)
        return SubmitPlacementAnswerResponse(
            test_id=test.id,
            correct=existing.is_correct,
            correct_answer=None if existing.is_correct else verdict_answer,
            already_answered=True,
            answered_count=len(answers),
            total_questions=QUESTION_COUNT,
            finished=replayed is None,
            question=replayed,
        )

    question = _question(db, test, answers)
    if question is None:
        raise ConflictError("This placement test has no questions left.")
    if question.exercise.id != exercise_id:
        # The client answered something other than the question it was asked.
        # Refused rather than graded: accepting it would let a caller choose
        # which difficulty to be assessed at, which is the whole test.
        raise ConflictError("That is not the current placement question.")

    exercise = lesson_repo.get_exercise(db, exercise_id)
    if exercise is None:
        raise NotFoundError(f"Exercise {exercise_id} does not exist.")

    verdict = grading.validate(exercise, answer)

    db.add(
        PlacementAnswer(
            test_id=test.id,
            exercise_id=exercise.id,
            difficulty=question.difficulty,
            submitted=answer,
            is_correct=verdict.correct,
        )
    )
    db.commit()

    answers = placement_repo.answers_for(db, test.id)
    next_question = _question(db, test, answers)

    return SubmitPlacementAnswerResponse(
        test_id=test.id,
        correct=verdict.correct,
        # Shown only after a mistake, exactly as in a lesson: revealing it after
        # a correct answer would tell the learner nothing they did not just
        # demonstrate.
        correct_answer=None if verdict.correct else verdict.correct_answer,
        already_answered=False,
        answered_count=len(answers),
        total_questions=QUESTION_COUNT,
        finished=next_question is None,
        question=next_question,
    )


def _result_response(
    db: DbSession, test: PlacementTest, user: User
) -> PlacementResultResponse:
    """Build the result payload from a completed test's stored columns."""
    skill = db.get(Skill, test.result_skill_id)
    if skill is None:
        raise NotFoundError("The placed skill no longer exists.")

    answers = placement_repo.answers_for(db, test.id)
    skill_ids = placement_repo.ordered_skill_ids_for_course(db, test.course_id)
    placed_out = skill_ids.index(skill.id) if skill.id in skill_ids else 0

    return PlacementResultResponse(
        test_id=test.id,
        level=test.result_level or 0,
        score=test.result_score or 0,
        max_score=test.result_max_score or 0,
        total_questions=len(answers),
        correct_answers=sum(1 for a in answers if a.is_correct),
        skill_id=skill.id,
        skill_title=skill.title,
        unit_title=skill.unit.title,
        skills_placed_out=placed_out,
        onboarding=onboarding_service.status(db, user),
    )


def complete(db: DbSession, user: User, test_id: int) -> PlacementResultResponse:
    """Score the test, place the learner, and finish onboarding.

    **Idempotent.** A completed test returns its stored result without
    recalculating anything. That is not just double-click protection: the score
    is a historical fact, and re-deriving it later under retuned rules would
    silently change a result the learner was already shown.

    **What "placing" writes, and what it does not.** Every skill before the
    placed skill gets ``placed_out_at`` set on the learner's existing progress
    row. Nothing else changes: no crowns, no XP, no ``lessons_completed``, no
    lesson attempt. ``path_service`` reads that column and reports those skills
    as ``PLACED_OUT`` — a state the learner can see and tell apart from one they
    actually finished.

    One transaction: the test result, the placed-out rows and the onboarding
    completion all land together. A crash between them would leave a learner
    placed but still stuck in onboarding, or finished with no path to show for it.

    Raises:
        ForbiddenError: the test belongs to another learner.
        ConflictError: the test still has questions to answer.
    """
    test = _owned_test(db, user, test_id)
    if test.completed_at is not None:
        return _result_response(db, test, user)

    row = _onboarding_for_placement(db, user)
    answers = placement_repo.answers_for(db, test.id)

    if _question(db, test, answers) is not None:
        raise ConflictError("Answer every placement question first.")

    _, skill_count = _pool(db, test.course_id)
    result = placement_engine.evaluate(
        [AnsweredQuestion(a.difficulty, a.is_correct) for a in answers],
        skill_count,
    )

    skill_ids = placement_repo.ordered_skill_ids_for_course(db, test.course_id)
    placed_skill_id = skill_ids[result.skill_index]

    try:
        now = datetime.now(timezone.utc)

        # Everything strictly *before* the placed skill is material the learner
        # has demonstrated. The placed skill itself is left untouched: it becomes
        # AVAILABLE because its predecessor is placed out, and the learner
        # actually studies it.
        for skill_id in skill_ids[: result.skill_index]:
            progress = progress_repo.get_or_create_skill_progress(
                db, user_id=user.id, skill_id=skill_id
            )
            progress.placed_out_at = now

        test.completed_at = now
        test.result_level = result.level
        test.result_score = result.score
        test.result_max_score = result.max_score
        test.result_skill_id = placed_skill_id

        onboarding_service.complete_with_placement(
            db, row, level=result.level, skill_id=placed_skill_id
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _result_response(db, test, user)


__all__ = [
    "InvalidAnswerError",
    "complete",
    "start",
    "submit_answer",
]
