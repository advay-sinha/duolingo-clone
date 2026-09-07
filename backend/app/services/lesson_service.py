"""Lesson retrieval, session start, and completion.

``complete_lesson`` is the most important function in the backend: it is the one
place that credits XP, advances the streak, updates skill progress and awards
crowns — and it does all of it inside a single transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.models import Lesson, User, UserSkillProgress
from app.repositories import attempt_repo, lesson_repo, progress_repo, user_repo
from app.services import achievement_service, user_service
from app.schemas.lesson import (
    CompleteLessonResponse,
    ExercisePublic,
    LessonResponse,
    LessonSkillRef,
    StartLessonResponse,
)
from app.services import gamification, presentation
from app.services.answer_service import _load_owned_attempt


def _lesson_response(lesson: Lesson) -> LessonResponse:
    """Serialise a lesson through the safe schema.

    Every path that sends a lesson to a client goes through here, so both
    guarantees apply uniformly: ``ExercisePublic`` has no field for the answer,
    and ``presentation.public_data`` breaks the correlation between an option's
    position and its correctness. See ``presentation.py`` for why the second one
    is needed — the Phase 8 review found the answer was leaking by *position*
    even though no field carried it.
    """
    return LessonResponse(
        id=lesson.id,
        title=lesson.title,
        order_index=lesson.order_index,
        xp_reward=lesson.xp_reward,
        skill=LessonSkillRef.model_validate(lesson.skill),
        exercises=[
            ExercisePublic(
                id=exercise.id,
                type=exercise.type,
                order_index=exercise.order_index,
                instruction=exercise.instruction,
                prompt=exercise.prompt,
                data=presentation.public_data(exercise),
            )
            for exercise in lesson.exercises
        ],
    )


def get_lesson(db: Session, lesson_id: int) -> LessonResponse:
    """Return a lesson and its exercises, without any canonical answers."""
    lesson = lesson_repo.get_lesson_with_exercises(db, lesson_id)
    if lesson is None:
        raise NotFoundError(f"Lesson {lesson_id} does not exist.")
    return _lesson_response(lesson)


def start_lesson(db: Session, *, lesson_id: int, user: User) -> StartLessonResponse:
    """Open a lesson session.

    Creates a ``lesson_attempts`` row and returns its id — the handle every
    subsequent answer must carry. Starting deliberately changes nothing else:
    no XP, no crowns, no streak, no heart deduction. A learner who opens a lesson
    and immediately closes it has altered nothing but their attempt history.

    Refuses to start at zero hearts (409), so the client cannot open a session it
    could not answer a single question in.

    A fresh attempt is created on every call rather than resuming an unfinished
    one. That keeps the model simple and honest — each row is one sitting — and
    means an abandoned attempt stays in history as exactly that.
    """
    settings = get_settings()

    lesson = lesson_repo.get_lesson_with_exercises(db, lesson_id)
    if lesson is None:
        raise NotFoundError(f"Lesson {lesson_id} does not exist.")

    # Regenerate *before* the gate, so a learner who has waited out the interval
    # can start immediately rather than having to load the stats screen first.
    # This is the whole zero-heart recovery path.
    stats = user_service.current_stats(db, user)
    if stats.hearts <= 0:
        raise ConflictError("No hearts remaining. Cannot start a lesson.")

    try:
        attempt = attempt_repo.create_attempt(
            db, user_id=user.id, lesson_id=lesson_id
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return StartLessonResponse(
        attempt_id=attempt.id,
        lesson_id=lesson_id,
        started_at=attempt.started_at,
        hearts=stats.hearts,
        max_hearts=settings.max_hearts,
        lesson=_lesson_response(lesson),
    )


def complete_lesson(
    db: Session, *, lesson_id: int, user: User, attempt_id: int
) -> CompleteLessonResponse:
    """Close an attempt and settle every reward, atomically.

    **Server-authoritative.** Nothing about the outcome comes from the client:
    the request carries only an attempt id. Correctness, XP and completion are
    all read back from ``lesson_attempt_answers``, which only this server writes.

    **The transaction.** Four tables are written — ``lesson_attempts``,
    ``user_stats``, ``user_skill_progress``, and implicitly the answers already
    recorded. One ``commit()`` at the end, ``rollback()`` on any exception. If
    the skill-progress update failed after XP had been credited, a learner would
    have XP for a lesson their path still showed as unfinished, and no later run
    would repair it. All or nothing.

    Raises:
        NotFoundError: unknown attempt, or it belongs to a different lesson.
        ForbiddenError: the attempt belongs to another learner.
        ConflictError: already completed, or not every exercise was answered.
    """
    settings = get_settings()

    # Same four ownership checks as answering, including "not already completed"
    # -- which is what makes completion idempotent: the second call gets a 409
    # rather than a second helping of XP.
    attempt = _load_owned_attempt(
        db, attempt_id=attempt_id, lesson_id=lesson_id, user=user
    )

    lesson = lesson_repo.get_lesson(db, lesson_id)
    if lesson is None:
        raise NotFoundError(f"Lesson {lesson_id} does not exist.")

    total_exercises = lesson_repo.count_exercises(db, lesson_id)
    answers = attempt_repo.list_answers(db, attempt.id)

    # Completion is earned, not claimed: every exercise must have a recorded
    # answer. Right or wrong -- getting one wrong still costs a heart and still
    # counts as attempted.
    if len(answers) < total_exercises:
        raise ConflictError(
            f"Lesson not finished: {len(answers)} of {total_exercises} "
            "exercises answered."
        )

    correct = sum(1 for answer in answers if answer.is_correct)
    incorrect = len(answers) - correct
    answer_xp = sum(answer.xp_earned for answer in answers)

    stats = user_repo.get_stats(db, user.id)
    if stats is None:
        raise NotFoundError(f"No stats row exists for user {user.id}.")

    # Repeat completions are allowed (practice) but award nothing, so replaying a
    # lesson cannot farm unlimited XP. Checked before this attempt is marked
    # completed, or it would always see itself.
    first_completion = not attempt_repo.has_completed_lesson(
        db, user_id=user.id, lesson_id=lesson_id
    )
    xp_earned = (answer_xp + lesson.xp_reward) if first_completion else 0

    today = datetime.now(timezone.utc).date()
    streak = gamification.apply_streak(
        current_streak=stats.current_streak,
        longest_streak=stats.longest_streak,
        last_activity_date=stats.last_activity_date,
        today=today,
    )
    new_daily_xp = gamification.daily_xp_after(
        daily_xp=stats.daily_xp,
        last_activity_date=stats.last_activity_date,
        today=today,
        earned=xp_earned,
    )

    try:
        # --- the attempt ---------------------------------------------------
        attempt.completed = True
        attempt.completed_at = datetime.now(timezone.utc)
        attempt.correct_answers = correct
        attempt.incorrect_answers = incorrect
        attempt.xp_earned = xp_earned

        # --- the learner's stats -------------------------------------------
        stats.total_xp += xp_earned
        stats.daily_xp = new_daily_xp
        stats.current_streak = streak.current_streak
        stats.longest_streak = streak.longest_streak
        stats.last_activity_date = today

        # --- skill progress ------------------------------------------------
        # Recomputed from persisted state rather than incremented. Counting the
        # distinct lessons of this skill the learner has actually completed makes
        # the update naturally idempotent and enforces
        # 0 <= lessons_completed <= total_lessons by construction -- an
        # increment could drift past the total if it ever ran twice.
        skill_lesson_ids = lesson_repo.lesson_ids_for_skill(db, lesson.skill_id)
        completed_ids = attempt_repo.completed_lesson_ids_in(
            db, user_id=user.id, lesson_ids=skill_lesson_ids
        )
        completed_ids.add(lesson_id)  # this attempt, not yet visible to the query

        lessons_completed = len(completed_ids)
        total_lessons = len(skill_lesson_ids)
        crowns = gamification.crowns_for_skill(
            lessons_completed=lessons_completed, total_lessons=total_lessons
        )

        progress = progress_repo.get_or_create_skill_progress(
            db, user_id=user.id, skill_id=lesson.skill_id
        )
        crown_earned = crowns > progress.crowns
        progress.lessons_completed = lessons_completed
        progress.crowns = max(progress.crowns, crowns)
        progress.xp_earned += xp_earned
        progress.last_completed_at = attempt.completed_at

        # Flush before evaluating. The session runs with `autoflush=False`, so
        # without this the achievement queries would run against the database as
        # it was *before* this completion -- and "complete your first lesson"
        # would never fire on the completion that earned it. Still inside the
        # transaction, so nothing is durable yet.
        db.flush()

        # Evaluated inside the same transaction as the completion that earned
        # them: a learner can never end up with a completed lesson whose
        # achievement was lost, nor an achievement for a completion that rolled
        # back. `evaluate` is idempotent, so this is safe on every call.
        newly_unlocked = achievement_service.evaluate(db, user)

        db.commit()
    except Exception:
        # No partial state: XP without progress, or a crown without a completed
        # attempt, would both be silently wrong forever.
        db.rollback()
        raise

    return CompleteLessonResponse(
        attempt_id=attempt.id,
        lesson_id=lesson_id,
        correct_answers=correct,
        incorrect_answers=incorrect,
        total_exercises=total_exercises,
        accuracy=round(correct / total_exercises, 4) if total_exercises else 0.0,
        xp_earned=xp_earned,
        first_completion=first_completion,
        total_xp=stats.total_xp,
        daily_xp=stats.daily_xp,
        daily_goal=stats.daily_goal,
        hearts_remaining=stats.hearts,
        current_streak=stats.current_streak,
        longest_streak=stats.longest_streak,
        streak_extended=streak.extended,
        skill_id=lesson.skill_id,
        lessons_completed=lessons_completed,
        total_lessons=total_lessons,
        crowns=progress.crowns,
        crown_earned=crown_earned,
        achievements_unlocked=[a.title for a in newly_unlocked],
    )
