"""Placement test routes.

Three endpoints, and none of them can award anything. That is worth stating at
the route layer as well as the service layer, because this is the file someone
skims when they ask "what does placement do to my account?": it starts a test,
grades an answer, and computes a level. No response model here declares XP,
hearts, streak or crowns.

Like the lesson routes, these are thin — and they own exactly one translation:
``InvalidAnswerError`` becomes a 422, because a payload the exercise type cannot
interpret is a client bug, not a wrong answer, and must not move the learner's
placement level.
"""

from fastapi import APIRouter, HTTPException

from app.api.v1.deps import CurrentUser, DbSession
from app.schemas.placement import (
    CompletePlacementRequest,
    PlacementResultResponse,
    PlacementStateResponse,
    SubmitPlacementAnswerRequest,
    SubmitPlacementAnswerResponse,
)
from app.services import placement_service
from app.services.grading import InvalidAnswerError

router = APIRouter(prefix="/placement", tags=["placement"])


@router.post(
    "/start",
    response_model=PlacementStateResponse,
    summary="Start (or resume) the placement test",
    responses={
        401: {"description": "Not signed in"},
        409: {"description": "Onboarding is complete, or 'Find my level' was not chosen"},
    },
)
def start_placement(db: DbSession, user: CurrentUser) -> PlacementStateResponse:
    """Open a placement test, or return the one already in progress.

    Deliberately idempotent: the placement screen calls this on every mount, so a
    refresh resumes the same test with the same answers rather than starting a
    new one.
    """
    return placement_service.start(db, user)


@router.post(
    "/answer",
    response_model=SubmitPlacementAnswerResponse,
    summary="Answer the current placement question",
    responses={
        403: {"description": "The test belongs to another learner"},
        404: {"description": "Unknown test or exercise"},
        409: {"description": "The test is finished, or that is not the current question"},
        422: {"description": "Malformed answer payload for this exercise type"},
    },
)
def submit_placement_answer(
    payload: SubmitPlacementAnswerRequest, db: DbSession, user: CurrentUser
) -> SubmitPlacementAnswerResponse:
    """Grade one answer and return the next question.

    The next question's difficulty is chosen by the server from the verdict it
    just recorded. The client is told what to render; it never asks for a level.
    """
    try:
        return placement_service.submit_answer(
            db,
            user,
            test_id=payload.test_id,
            exercise_id=payload.exercise_id,
            answer=payload.answer,
        )
    except InvalidAnswerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/complete",
    response_model=PlacementResultResponse,
    summary="Score the placement test and finish onboarding",
    responses={
        403: {"description": "The test belongs to another learner"},
        404: {"description": "Unknown test"},
        409: {"description": "There are still questions to answer"},
    },
)
def complete_placement(
    payload: CompletePlacementRequest, db: DbSession, user: CurrentUser
) -> PlacementResultResponse:
    """Compute the learner's level, place them, and complete onboarding.

    Idempotent: a second call returns the stored result rather than re-scoring.
    """
    return placement_service.complete(db, user, payload.test_id)
