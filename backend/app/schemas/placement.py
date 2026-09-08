"""API schemas for the placement test.

``ExercisePublic`` is imported from ``schemas/lesson.py`` rather than redeclared.
That is not laziness — it is the point. The security property that matters most
in this codebase is that a canonical answer has no field to travel in, and reusing
the one model that already guarantees it means placement inherits the guarantee
instead of having to re-earn it.

What is deliberately **absent** from every response here: XP, hearts, streak,
crowns, gems. Not "set to zero" — absent. A placement response has no field in
which a reward could appear, so no future edit can accidentally make an
assessment pay out.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.lesson import ExercisePublic
from app.schemas.onboarding import OnboardingStatus


class PlacementQuestion(BaseModel):
    """One question, with where it sits in the test."""

    exercise: ExercisePublic
    #: The difficulty band this question was drawn from, 1-5. Shown to the
    #: learner as "Level 3 of 5" so the test explains itself while it runs.
    difficulty: int
    #: 1-based, for "Question 3 of 8".
    number: int


class PlacementStateResponse(BaseModel):
    """`POST /placement/start` — the test, and the question to show now.

    Idempotent by design: called again it returns the *same* open test and the
    same current question, which is what makes a browser refresh mid-test a
    non-event. The current question is not stored anywhere; it is derived from
    the answers already recorded, so there is no "where was I" state to lose.
    """

    test_id: int
    total_questions: int
    answered_count: int
    finished: bool
    #: Null once the test is finished and there is nothing left to ask.
    question: PlacementQuestion | None


class SubmitPlacementAnswerRequest(BaseModel):
    """`POST /placement/answer`.

    Carries no user id and no difficulty. The caller is the cookie; the
    difficulty is whatever the server asked the question at, which it knows and
    the client cannot influence.
    """

    test_id: int
    exercise_id: int
    #: Same free-form shape as a lesson answer, and graded by the same
    #: validators. See ``SubmitAnswerRequest`` for the per-type payloads.
    answer: dict = Field(default_factory=dict)


class SubmitPlacementAnswerResponse(BaseModel):
    """The verdict on one placement answer, plus the next question.

    Note what a learner is told and when: ``correct`` and ``correct_answer``
    arrive only in response to an answer they have already given, exactly as in a
    lesson. Nothing about the *next* question reveals anything about its answer.
    """

    #: Echoed so this response and ``PlacementStateResponse`` carry the same
    #: fields. The client can then feed either one to the same render function
    #: instead of merging a verdict into remembered state.
    test_id: int
    correct: bool
    correct_answer: str | None
    #: True when this exercise had already been answered and the recorded verdict
    #: is being replayed. No second row, and the adaptive walk is unaffected.
    already_answered: bool = False
    answered_count: int
    total_questions: int
    finished: bool
    question: PlacementQuestion | None


class CompletePlacementRequest(BaseModel):
    """`POST /placement/complete`."""

    test_id: int


class PlacementResultResponse(BaseModel):
    """`POST /placement/complete` — the result, and the onboarding state it produced.

    Returning the onboarding status too means the client needs one round trip to
    learn both "here is your level" and "onboarding is over, go to /learn".
    """

    test_id: int
    level: int
    score: int
    max_score: int
    total_questions: int
    correct_answers: int
    #: The skill the learner starts at. Never null on a completed test.
    skill_id: int
    skill_title: str
    unit_title: str
    #: How many skills the learner was placed *beyond*. Zero for a learner who
    #: placed at the beginning — which is a normal outcome, not a failure.
    skills_placed_out: int
    onboarding: OnboardingStatus
