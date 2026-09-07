"""Answer submission: validate, record, deduct hearts.

This service owns one transaction: grading a submission and persisting its
consequences. It is where the "never trust the client" rule is enforced, in four
checks that run *before* any grading happens.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import (
    ExerciseType,
    LessonAttempt,
    LessonAttemptAnswer,
    LessonAttemptPair,
    User,
)
from app.repositories import attempt_repo, lesson_repo, user_repo
from app.schemas.lesson import (
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    SubmitPairRequest,
    SubmitPairResponse,
)
from app.services import gamification, grading


def _load_owned_attempt(
    db: Session, *, attempt_id: int, lesson_id: int, user: User
) -> LessonAttempt:
    """Load an attempt and prove the caller may write to it.

    Four checks, in this order, each rejecting a different attack or mistake:

    1. **Exists** -> 404.
    2. **Belongs to the caller** -> 403. The user id comes from the dependency,
       never from the request body, so a client cannot claim to be someone else.
    3. **Belongs to the lesson in the URL** -> 404. Stops an attempt for one
       lesson being used to answer another lesson's exercises.
    4. **Not already completed** -> 409. A finished attempt is immutable; without
       this, a learner could keep answering after completion and re-trigger
       rewards.
    """
    attempt = attempt_repo.get_attempt(db, attempt_id)
    if attempt is None:
        raise NotFoundError(f"Attempt {attempt_id} does not exist.")
    if attempt.user_id != user.id:
        raise ForbiddenError("This attempt belongs to another learner.")
    if attempt.lesson_id != lesson_id:
        raise NotFoundError(f"Attempt {attempt_id} is not for lesson {lesson_id}.")
    if attempt.completed:
        raise ConflictError("This attempt is already completed.")
    return attempt


def submit_answer(
    db: Session, *, lesson_id: int, user: User, payload: SubmitAnswerRequest
) -> SubmitAnswerResponse:
    """Grade one answer and persist its consequences atomically.

    Raises:
        NotFoundError: unknown attempt or exercise, or a mismatch between them.
        ForbiddenError: the attempt belongs to another learner.
        ConflictError: the attempt is finished, or the learner has no hearts.
        grading.InvalidAnswerError: malformed payload (route maps it to 422).
    """
    settings = get_settings()
    attempt = _load_owned_attempt(
        db, attempt_id=payload.attempt_id, lesson_id=lesson_id, user=user
    )

    exercise = lesson_repo.get_exercise(db, payload.exercise_id)
    if exercise is None:
        raise NotFoundError(f"Exercise {payload.exercise_id} does not exist.")
    if exercise.lesson_id != lesson_id:
        # Cross-lesson submission: the exercise is real but belongs elsewhere.
        raise NotFoundError(
            f"Exercise {payload.exercise_id} is not part of lesson {lesson_id}."
        )

    total_exercises = lesson_repo.count_exercises(db, lesson_id)

    # --- idempotency -------------------------------------------------------
    # A resubmission replays the original verdict rather than grading again.
    # Returning 200 with `already_answered` instead of 409 is deliberate: a
    # retried request after a dropped response is not a client error, and this
    # makes the endpoint safe to retry -- which is what idempotency is for. The
    # UNIQUE(attempt_id, exercise_id) constraint backs this up if two requests
    # race past the check simultaneously.
    existing = attempt_repo.get_answer(
        db, attempt_id=attempt.id, exercise_id=exercise.id
    )
    if existing is not None:
        stats = user_repo.get_stats(db, user.id)
        verdict_answer = (
            None
            if existing.is_correct
            else grading.validate(exercise, existing.submitted).correct_answer
        )
        return SubmitAnswerResponse(
            correct=existing.is_correct,
            correct_answer=verdict_answer,
            xp_earned=existing.xp_earned,
            hearts_remaining=stats.hearts,
            already_answered=True,
            answered_count=attempt_repo.count_answers(db, attempt.id),
            total_exercises=total_exercises,
        )

    # --- hearts gate -------------------------------------------------------
    # Checked before grading, so a learner with no hearts cannot keep playing.
    stats = user_repo.get_stats(db, user.id)
    if stats is None:
        raise NotFoundError(f"No stats row exists for user {user.id}.")
    if stats.hearts <= 0:
        raise ConflictError(
            "No hearts remaining. Hearts must be restored before answering again."
        )

    # --- grade -------------------------------------------------------------
    # InvalidAnswerError propagates: a malformed payload is a client bug, not a
    # wrong answer, and must not cost a heart.
    verdict = grading.validate(exercise, payload.answer)

    xp = settings.xp_per_correct_answer if verdict.correct else 0
    hearts_lost = 0 if verdict.correct else settings.hearts_lost_per_mistake

    try:
        db.add(
            LessonAttemptAnswer(
                attempt_id=attempt.id,
                exercise_id=exercise.id,
                submitted=payload.answer,
                is_correct=verdict.correct,
                xp_earned=xp,
                hearts_lost=hearts_lost,
            )
        )

        if verdict.correct:
            attempt.correct_answers += 1
        else:
            attempt.incorrect_answers += 1
            attempt.hearts_lost += hearts_lost
            stats.hearts = gamification.hearts_after_mistake(
                hearts=stats.hearts, cost=hearts_lost
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return SubmitAnswerResponse(
        correct=verdict.correct,
        # Shown only after a wrong answer -- the moment teaching happens.
        correct_answer=None if verdict.correct else verdict.correct_answer,
        xp_earned=xp,
        hearts_remaining=stats.hearts,
        already_answered=False,
        answered_count=attempt_repo.count_answers(db, attempt.id),
        total_exercises=total_exercises,
    )


# --------------------------------------------------------------------------
# Match pairs — incremental grading (Phase 9)
# --------------------------------------------------------------------------
#
# THE HEART MODEL, stated before the code.
#
# Match pairs used to be graded like every other exercise: build the whole
# mapping, press Check, one verdict, one heart at most. Grading each pair as it
# is formed changes what "an answer" is, so the rules have to be restated:
#
# 1. A *wrong pair* is a mistake. It costs one heart, like any wrong answer.
# 2. The **same** wrong pair submitted again costs nothing. Idempotency is keyed
#    on (attempt, exercise, left_id, right_id) and enforced by a UNIQUE
#    constraint, so a double-click or a retried request cannot charge twice.
# 3. A *different* wrong pair is a different mistake and costs its own heart.
#    That is not double-charging: the learner genuinely guessed twice.
# 4. A correct pair never costs a heart.
# 5. A malformed submission — an id that is not on this exercise — is a client
#    bug, not a wrong answer. 422, no heart, no row.
# 6. The exercise is finished only when every left item has a correct match. At
#    that moment the server writes the ordinary `lesson_attempt_answers` row, so
#    completion, XP and accuracy work unchanged and nothing double-counts.
# 7. That row is `is_correct=True` only if **no** wrong pair was submitted, which
#    is exactly the rule the other four exercise types follow: right first time
#    earns XP, a mistake does not.
#
# The worst case is bounded: an exercise can cost at most one heart per distinct
# wrong combination the learner actually tries, and the hearts gate stops them at
# zero regardless.


def _pair_state(
    db: Session, *, attempt_id: int, exercise_id: int
) -> list[tuple[str, str]]:
    """The pairs the server has accepted so far, as (left, right) tuples."""
    return [
        (row.left_id, row.right_id)
        for row in attempt_repo.matched_pairs(
            db, attempt_id=attempt_id, exercise_id=exercise_id
        )
    ]


def submit_pair(
    db: Session, *, lesson_id: int, user: User, payload: SubmitPairRequest
) -> SubmitPairResponse:
    """Grade one match-pairs selection immediately.

    Same four ownership checks as ``submit_answer`` — the attempt must exist,
    belong to this learner, belong to this lesson, and not be finished — because
    this is another way to write to an attempt and must not be a weaker door.

    Raises:
        NotFoundError: unknown attempt or exercise, or a mismatch between them.
        ForbiddenError: the attempt belongs to another learner.
        ConflictError: the attempt is finished, or the learner has no hearts.
        grading.InvalidAnswerError: the exercise is not match-pairs, or an id is
            not part of it (422, and no heart).
    """
    settings = get_settings()
    attempt = _load_owned_attempt(
        db, attempt_id=payload.attempt_id, lesson_id=lesson_id, user=user
    )

    exercise = lesson_repo.get_exercise(db, payload.exercise_id)
    if exercise is None:
        raise NotFoundError(f"Exercise {payload.exercise_id} does not exist.")
    if exercise.lesson_id != lesson_id:
        raise NotFoundError(
            f"Exercise {payload.exercise_id} is not part of lesson {lesson_id}."
        )
    if exercise.type is not ExerciseType.MATCH_PAIRS:
        raise grading.InvalidAnswerError(
            "This endpoint only grades match-pairs exercises."
        )

    left_ids = {item["id"] for item in exercise.data["left"]}
    right_ids = {item["id"] for item in exercise.data["right"]}
    if payload.left_id not in left_ids or payload.right_id not in right_ids:
        # An id that is not on this exercise means a client out of sync or
        # tampering. Neither is a wrong answer, so neither costs a heart.
        raise grading.InvalidAnswerError(
            f"Pair ({payload.left_id}, {payload.right_id}) is not part of "
            "this exercise."
        )

    total_pairs = len(exercise.correct_answer["pairs"])

    # --- idempotency (rule 2) ----------------------------------------------
    existing = attempt_repo.get_pair(
        db,
        attempt_id=attempt.id,
        exercise_id=exercise.id,
        left_id=payload.left_id,
        right_id=payload.right_id,
    )
    if existing is not None:
        stats = user_repo.get_stats(db, user.id)
        matched = _pair_state(db, attempt_id=attempt.id, exercise_id=exercise.id)
        answer = attempt_repo.get_answer(
            db, attempt_id=attempt.id, exercise_id=exercise.id
        )
        return SubmitPairResponse(
            correct=existing.is_correct,
            pair_completed=existing.is_correct,
            matched_pairs=matched,
            exercise_complete=answer is not None,
            exercise_correct=answer.is_correct if answer is not None else False,
            hearts_remaining=stats.hearts,
            xp_earned=answer.xp_earned if answer is not None else 0,
            already_answered=True,
            answered_count=attempt_repo.count_answers(db, attempt.id),
            total_exercises=lesson_repo.count_exercises(db, lesson_id),
        )

    # --- hearts gate --------------------------------------------------------
    stats = user_repo.get_stats(db, user.id)
    if stats is None:
        raise NotFoundError(f"No stats row exists for user {user.id}.")
    if stats.hearts <= 0:
        raise ConflictError(
            "No hearts remaining. Hearts must be restored before answering again."
        )

    # --- grade one pair -----------------------------------------------------
    # The server decides, from an answer the client has never been sent.
    expected = {(left, right) for left, right in exercise.correct_answer["pairs"]}
    is_correct = (payload.left_id, payload.right_id) in expected
    hearts_lost = 0 if is_correct else settings.hearts_lost_per_mistake

    try:
        db.add(
            LessonAttemptPair(
                attempt_id=attempt.id,
                exercise_id=exercise.id,
                left_id=payload.left_id,
                right_id=payload.right_id,
                is_correct=is_correct,
                hearts_lost=hearts_lost,
            )
        )
        if not is_correct:
            # `incorrect_answers` counts *exercises*, not pairs, and is
            # incremented once when the exercise finishes. Only hearts are
            # charged per pair.
            attempt.hearts_lost += hearts_lost
            stats.hearts = gamification.hearts_after_mistake(
                hearts=stats.hearts, cost=hearts_lost
            )

        # The new row must be visible to the queries below, which run against
        # this session before the commit. The application's SessionLocal sets
        # autoflush=False (ADR-49), so this has to be explicit — the Phase 7 bug
        # that hid achievements was exactly this mistake.
        db.flush()

        matched = _pair_state(db, attempt_id=attempt.id, exercise_id=exercise.id)
        exercise_complete = len(matched) >= total_pairs
        xp = 0
        exercise_correct = False

        if exercise_complete:
            # Rules 6 and 7: hand the finished exercise to the existing engine,
            # exactly once. `get_answer` is checked first so a replayed request
            # cannot write a second row — and UNIQUE(attempt_id, exercise_id)
            # would refuse it anyway.
            already = attempt_repo.get_answer(
                db, attempt_id=attempt.id, exercise_id=exercise.id
            )
            if already is None:
                flawless = (
                    attempt_repo.count_wrong_pairs(
                        db, attempt_id=attempt.id, exercise_id=exercise.id
                    )
                    == 0
                )
                xp = settings.xp_per_correct_answer if flawless else 0
                exercise_correct = flawless
                db.add(
                    LessonAttemptAnswer(
                        attempt_id=attempt.id,
                        exercise_id=exercise.id,
                        submitted={"pairs": [list(pair) for pair in matched]},
                        is_correct=flawless,
                        xp_earned=xp,
                        # Hearts were charged per wrong pair already; charging
                        # again here would count the same mistakes twice.
                        hearts_lost=0,
                    )
                )
                if flawless:
                    attempt.correct_answers += 1
                else:
                    attempt.incorrect_answers += 1
            else:
                xp = already.xp_earned
                exercise_correct = already.is_correct

        db.commit()
    except Exception:
        db.rollback()
        raise

    return SubmitPairResponse(
        correct=is_correct,
        pair_completed=is_correct,
        matched_pairs=matched,
        exercise_complete=exercise_complete,
        exercise_correct=exercise_correct,
        hearts_remaining=stats.hearts,
        xp_earned=xp,
        already_answered=False,
        answered_count=attempt_repo.count_answers(db, attempt.id),
        total_exercises=lesson_repo.count_exercises(db, lesson_id),
    )
