"""Lesson engine routes.

Thin, like every route in this codebase: receive, delegate, return. Not one line
of grading, XP, heart or streak logic lives here — all of it is in the services,
so a second consumer of the engine could not end up with a different set of
rules.

The one thing these routes do own is translating a grading failure into HTTP:
``InvalidAnswerError`` means the client sent a payload the exercise type cannot
interpret, which is a 422, and — importantly — costs no heart.
"""

from fastapi import APIRouter, HTTPException

from app.api.v1.deps import CurrentUser, DbSession
from app.schemas.lesson import (
    CompleteLessonRequest,
    CompleteLessonResponse,
    LessonResponse,
    StartLessonResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    SubmitPairRequest,
    SubmitPairResponse,
)
from app.services import answer_service, lesson_service
from app.services.grading import InvalidAnswerError

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get(
    "/{lesson_id}",
    response_model=LessonResponse,
    summary="Get a lesson and its exercises",
    responses={404: {"description": "No lesson with that id"}},
)
def get_lesson(lesson_id: int, db: DbSession) -> LessonResponse:
    """Return a lesson with everything needed to render it.

    The response never contains canonical answers — `ExercisePublic` does not
    declare the field, so there is nothing to omit.
    """
    return lesson_service.get_lesson(db, lesson_id)


@router.post(
    "/{lesson_id}/start",
    response_model=StartLessonResponse,
    summary="Start a lesson session",
    responses={
        404: {"description": "No lesson with that id"},
        409: {"description": "No hearts remaining"},
    },
)
def start_lesson(
    lesson_id: int, db: DbSession, user: CurrentUser
) -> StartLessonResponse:
    """Create an attempt and return its id along with the lesson.

    Awards nothing and deducts nothing.
    """
    return lesson_service.start_lesson(db, lesson_id=lesson_id, user=user)


@router.post(
    "/{lesson_id}/answer",
    response_model=SubmitAnswerResponse,
    summary="Submit one answer for grading",
    responses={
        403: {"description": "The attempt belongs to another learner"},
        404: {"description": "Unknown attempt or exercise, or a mismatch"},
        409: {"description": "Attempt already completed, or no hearts remaining"},
        422: {"description": "Malformed answer payload for this exercise type"},
    },
)
def submit_answer(
    lesson_id: int,
    payload: SubmitAnswerRequest,
    db: DbSession,
    user: CurrentUser,
) -> SubmitAnswerResponse:
    """Grade one answer, deduct a heart if wrong, and record the result.

    Safe to retry: resubmitting the same exercise replays the original verdict
    with `already_answered: true` rather than grading — and charging — twice.
    """
    try:
        return answer_service.submit_answer(
            db, lesson_id=lesson_id, user=user, payload=payload
        )
    except InvalidAnswerError as exc:
        # 422, not 400: the request is syntactically valid JSON but semantically
        # wrong for this exercise type. No heart is deducted -- a client bug must
        # not cost the learner.
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{lesson_id}/pair",
    response_model=SubmitPairResponse,
    summary="Grade one match-pairs selection",
    responses={
        403: {"description": "The attempt belongs to another learner"},
        404: {"description": "Unknown attempt or exercise, or a mismatch"},
        409: {"description": "Attempt already completed, or no hearts remaining"},
        422: {"description": "Not a match-pairs exercise, or an id is not part of it"},
    },
)
def submit_pair(
    lesson_id: int,
    payload: SubmitPairRequest,
    db: DbSession,
    user: CurrentUser,
) -> SubmitPairResponse:
    """Grade a single left→right selection the moment it is made.

    **Why a separate endpoint rather than reusing `/answer`.** The two carry
    genuinely different things: `/answer` submits a finished answer to an
    exercise, this submits one move within an exercise that is still in progress.
    Overloading `/answer` would mean a payload whose meaning depended on the
    exercise type, and a response whose fields were half-irrelevant either way.

    The server remains authoritative for every pair: the client sends two ids and
    is *told* whether they match. It has never been sent the mapping, and — since
    Phase 8 — cannot infer it from the order the options arrive in either.

    Safe to retry: the same pair submitted twice replays the first verdict with
    `already_answered: true` and costs no second heart.
    """
    try:
        return answer_service.submit_pair(
            db, lesson_id=lesson_id, user=user, payload=payload
        )
    except InvalidAnswerError as exc:
        # 422 and, deliberately, no heart: an id that is not part of this
        # exercise is a client bug, not a wrong guess.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post(
    "/{lesson_id}/complete",
    response_model=CompleteLessonResponse,
    summary="Complete a lesson and settle rewards",
    responses={
        403: {"description": "The attempt belongs to another learner"},
        404: {"description": "Unknown attempt or lesson"},
        409: {"description": "Already completed, or not every exercise was answered"},
    },
)
def complete_lesson(
    lesson_id: int,
    payload: CompleteLessonRequest,
    db: DbSession,
    user: CurrentUser,
) -> CompleteLessonResponse:
    """Close the attempt and award XP, streak, progress and crowns atomically.

    The request body carries only an attempt id. Correctness and XP are read
    back from what the server itself recorded, never from the client.
    """
    return lesson_service.complete_lesson(
        db, lesson_id=lesson_id, user=user, attempt_id=payload.attempt_id
    )
