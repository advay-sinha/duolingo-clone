"""Course routes.

Both endpoints are thin by design: take the request, get dependencies, call one
function, return the result. No SQL, and no business rules — the unlock logic
lives in ``PathService`` where a second consumer could reuse it.
"""

from fastapi import APIRouter

from app.api.v1.deps import CurrentUser, DbSession
from app.repositories import course_repo
from app.schemas.course import CourseListResponse, CourseSummary
from app.schemas.path import CoursePathResponse
from app.services import path_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get(
    "",
    response_model=CourseListResponse,
    summary="List available courses",
)
def list_courses(db: DbSession) -> CourseListResponse:
    """Return every course the learner can study.

    No service layer here on purpose: there is no rule to apply, only a read and
    a shape change. Inserting a ``CourseService`` that forwarded one call would
    be an empty abstraction. It appears the moment a real decision does —
    filtering by enrolment, say.
    """
    courses = course_repo.list_courses(db)
    return CourseListResponse(
        courses=[CourseSummary.model_validate(course) for course in courses]
    )


@router.get(
    "/{course_id}/path",
    response_model=CoursePathResponse,
    summary="Get the learning path for a course",
    responses={
        404: {"description": "No course with that id exists"},
        503: {"description": "The database has not been seeded"},
    },
)
def get_course_path(
    course_id: int, db: DbSession, user: CurrentUser
) -> CoursePathResponse:
    """Return the course's units, skills and lessons with this learner's state.

    Everything the learn screen needs in one request, including each skill's
    derived ``LOCKED`` / ``AVAILABLE`` / ``COMPLETED`` state.

    ``course_id`` is annotated as ``int``, so FastAPI validates and converts it
    before this function runs — a request for ``/courses/abc/path`` is rejected
    with a 422 that names the offending parameter, and the code below can trust
    its type.
    """
    return path_service.build_path(db, course_id, user)
