"""Onboarding routes.

Four endpoints, all authenticated, all returning the same ``OnboardingStatus``.

**None of them takes a user id**, and that is the isolation guarantee: there is
no field in any of these requests in which one learner could name another. The
caller comes from the session cookie, exactly as everywhere else since Phase 9,
so "can user A change user B's onboarding?" is not a check that could be
forgotten — it is a question with nowhere to be asked.
"""

from fastapi import APIRouter

from app.api.v1.deps import CurrentUser, DbSession
from app.schemas.onboarding import (
    OnboardingStatus,
    SelectCourseRequest,
    SelectProficiencyRequest,
    SelectStartingModeRequest,
)
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get(
    "",
    response_model=OnboardingStatus,
    summary="Where this learner is in onboarding",
    responses={401: {"description": "Not signed in"}},
)
def get_onboarding(db: DbSession, user: CurrentUser) -> OnboardingStatus:
    """Return the learner's onboarding state and the step they are on.

    Every protected page calls this before rendering, which is what makes the
    flow resumable: the answer to "where should this person be?" is computed from
    the database on every request, not remembered by the browser.

    A learner who registered before Phase 9.5 has no onboarding row and is
    reported complete, so they go straight to `/learn` and are never shown a
    step. See `app/models/onboarding.py`.
    """
    return onboarding_service.status(db, user)


@router.post(
    "/course",
    response_model=OnboardingStatus,
    summary="Choose a course",
    responses={
        404: {"description": "No course with that id"},
        409: {"description": "Onboarding is already complete"},
    },
)
def select_course(
    payload: SelectCourseRequest, db: DbSession, user: CurrentUser
) -> OnboardingStatus:
    """Record the learner's course.

    The id is checked against the courses table, so the picker's "coming soon"
    tiles cannot be selected even by a hand-written request — they have no row.
    """
    return onboarding_service.select_course(db, user, payload.course_id)


@router.post(
    "/proficiency",
    response_model=OnboardingStatus,
    summary="Record self-reported proficiency",
    responses={
        409: {"description": "An earlier step has not been taken"},
        422: {"description": "Not one of the five proficiency values"},
    },
)
def select_proficiency(
    payload: SelectProficiencyRequest, db: DbSession, user: CurrentUser
) -> OnboardingStatus:
    """Record how much of the language the learner says they know."""
    return onboarding_service.select_proficiency(db, user, payload.proficiency)


@router.post(
    "/start",
    response_model=OnboardingStatus,
    summary="Choose a starting point",
    responses={
        409: {"description": "An earlier step has not been taken"},
        422: {"description": "Not a valid starting mode"},
    },
)
def select_starting_mode(
    payload: SelectStartingModeRequest, db: DbSession, user: CurrentUser
) -> OnboardingStatus:
    """Record "start from scratch" or "find my level".

    ``SCRATCH`` completes onboarding here and awards nothing. ``PLACEMENT``
    leaves onboarding open until the test is finished, which is what lets a
    learner close the tab mid-test and be returned to it.
    """
    return onboarding_service.select_starting_mode(db, user, payload.mode)
