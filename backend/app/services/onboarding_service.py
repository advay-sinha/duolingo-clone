"""The onboarding state machine.

Four decisions, taken in order, each persisted the moment it is made:

    course -> proficiency -> starting point -> (placement) -> done

**The server owns the sequence.** ``status()`` computes which step the learner is
on from the columns that are still null, and every endpoint returns that status.
The frontend renders the step it is told and never works the order out for
itself. That is what makes the flow survive a refresh, a logout, a login on
another device, and a learner who bookmarks ``/onboarding/placement`` and comes
back tomorrow — none of which a client-side wizard with local state would.

**Existing learners are not touched.** A learner with no onboarding row predates
the feature, and ``status()`` reports them complete. That is the whole mechanism:
no migration step, no backfill, no flag to set. See ``app/models/onboarding.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.core.errors import ConflictError, NotFoundError
from app.models import (
    PlacementTest,
    ProficiencyLevel,
    Skill,
    StartingMode,
    User,
    UserOnboarding,
    UserSkillProgress,
)
from app.repositories import course_repo, onboarding_repo, placement_repo
from app.schemas.onboarding import (
    OnboardingStatus,
    OnboardingStep,
    PlacementSummary,
)


class OnboardingCompleteError(ConflictError):
    """The learner has already finished onboarding.

    409 rather than 403: nothing is wrong with the request or the caller, the
    state simply forbids it. Same reasoning as completing a lesson twice.
    """


def _step(row: UserOnboarding | None) -> OnboardingStep:
    """Which step a learner is on.

    Reads the columns in the order they are filled and returns the first one that
    is still null. **No step is stored**, for the same reason no skill stores
    ``is_locked``: a stored step would be a second copy of what these columns
    already say, and the two could drift.
    """
    if row is None or row.completed_at is not None:
        return OnboardingStep.DONE
    if row.course_id is None:
        return OnboardingStep.COURSE
    if row.proficiency is None:
        return OnboardingStep.PROFICIENCY
    if row.starting_mode is None:
        return OnboardingStep.START
    # The only mode that leaves onboarding open is PLACEMENT: choosing SCRATCH
    # completes it in the same transaction. A SCRATCH row that is somehow still
    # open is a bug, and sending the learner back to the starting-point screen is
    # the recoverable answer.
    if row.starting_mode is StartingMode.PLACEMENT:
        return OnboardingStep.PLACEMENT
    return OnboardingStep.START


def _placement_summary(
    db: DbSession, row: UserOnboarding
) -> PlacementSummary | None:
    """Describe the learner's placement result, if they took a test."""
    if row.placement_level is None:
        return None

    skill = db.get(Skill, row.placement_skill_id) if row.placement_skill_id else None
    test: PlacementTest | None = placement_repo.latest_completed_test(db, row.user_id)

    placed_out = (
        db.query(UserSkillProgress)
        .filter(
            UserSkillProgress.user_id == row.user_id,
            UserSkillProgress.placed_out_at.is_not(None),
        )
        .count()
    )

    return PlacementSummary(
        level=row.placement_level,
        score=test.result_score if test and test.result_score is not None else 0,
        max_score=(
            test.result_max_score if test and test.result_max_score is not None else 0
        ),
        skill_id=skill.id if skill else None,
        skill_title=skill.title if skill else None,
        unit_title=skill.unit.title if skill else None,
        skills_placed_out=placed_out,
    )


def status(db: DbSession, user: User) -> OnboardingStatus:
    """Where this learner is in onboarding.

    The one read every onboarding screen and the learn page make. A learner with
    no row is reported complete and flagged ``grandfathered`` — the frontend does
    not need to know the difference, but a person reading the API response
    should be able to tell "finished onboarding" from "was never asked to".
    """
    row = onboarding_repo.get(db, user.id)

    if row is None:
        return OnboardingStatus(
            completed=True,
            step=OnboardingStep.DONE,
            course_id=None,
            proficiency=None,
            starting_mode=None,
            placement=None,
            grandfathered=True,
            completed_at=None,
        )

    return OnboardingStatus(
        completed=row.completed_at is not None,
        step=_step(row),
        course_id=row.course_id,
        proficiency=row.proficiency,
        starting_mode=row.starting_mode,
        placement=_placement_summary(db, row),
        grandfathered=False,
        completed_at=row.completed_at,
    )


def open_row(db: DbSession, user: User) -> UserOnboarding:
    """The learner's in-progress onboarding row, or a 409.

    Both refusals are deliberate. A learner with **no row** is one who registered
    before onboarding existed; creating one for them now would drop them into a
    flow they finished the day they signed up, which is exactly the failure the
    brief calls out. A learner with a **completed row** has already chosen.
    """
    row = onboarding_repo.get(db, user.id)
    if row is None or row.completed_at is not None:
        raise OnboardingCompleteError("Onboarding is already complete.")
    return row


def select_course(db: DbSession, user: User, course_id: int) -> OnboardingStatus:
    """Record the course the learner enrolled in.

    Raises:
        NotFoundError: no course with that id. This is what makes the picker's
            "coming soon" tiles genuinely unselectable rather than merely
            disabled in CSS — there is no row for them, so there is no id that
            would get past this check.
        OnboardingCompleteError: onboarding is already finished.
    """
    row = open_row(db, user)

    if course_repo.get_course(db, course_id) is None:
        raise NotFoundError(f"Course {course_id} does not exist.")

    row.course_id = course_id
    db.commit()
    return status(db, user)


def select_proficiency(
    db: DbSession, user: User, proficiency: ProficiencyLevel
) -> OnboardingStatus:
    """Record the learner's self-reported proficiency.

    Stored, and deliberately never read by the placement engine — replacing a
    self-report with evidence is the only reason the placement test exists. It is
    kept because it is genuine signal about the learner's *intent*, and a later
    phase that recommends content has an obvious use for it.

    Raises:
        ConflictError: a course has not been chosen yet. Steps are ordered, and
            the server enforces the order rather than trusting the client to
            navigate correctly.
    """
    row = open_row(db, user)
    if row.course_id is None:
        raise ConflictError("Choose a course first.")

    row.proficiency = proficiency
    db.commit()
    return status(db, user)


def select_starting_mode(
    db: DbSession, user: User, mode: StartingMode
) -> OnboardingStatus:
    """Record the starting-point choice, and finish onboarding if it was SCRATCH.

    **"Start from scratch" awards nothing.** No XP, no crowns, no lesson attempt,
    no progress row is modified. The first skill is already ``AVAILABLE`` from the
    rule ``path_service`` has applied since Phase 3, and registration already
    created the zeroed progress rows. There is genuinely nothing to do except
    write the decision down — which is the strongest possible sign that the
    earlier design was right.

    Raises:
        ConflictError: an earlier step has not been taken.
    """
    row = open_row(db, user)
    if row.course_id is None:
        raise ConflictError("Choose a course first.")
    if row.proficiency is None:
        raise ConflictError("Choose your proficiency first.")

    row.starting_mode = mode
    if mode is StartingMode.SCRATCH:
        row.completed_at = datetime.now(timezone.utc)
    db.commit()
    return status(db, user)


def complete_with_placement(
    db: DbSession,
    row: UserOnboarding,
    *,
    level: int,
    skill_id: int,
) -> None:
    """Close onboarding with a placement result.

    Called by ``placement_service`` inside its transaction, so the placement
    test's result and the onboarding completion are written together or not at
    all. Does not commit, for that reason.
    """
    row.placement_level = level
    row.placement_skill_id = skill_id
    row.completed_at = datetime.now(timezone.utc)
