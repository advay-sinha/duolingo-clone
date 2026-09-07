"""API schemas for the lesson engine.

**The security-critical file in this codebase.**

``ExercisePublic`` is the only shape an exercise ever takes on its way to a
client, and it does not declare ``correct_answer``. That is a *structural*
guarantee rather than a remembered rule: there is no field for the answer to
occupy, so no future edit to a route or service can leak it by forgetting to
strip it. Pydantic drops any attribute the model does not declare.

The alternative — building a dict and popping the answer key — would work until
the day someone adds a code path that forgets. Two tests
(`test_lesson_never_exposes_the_answer`, and a recursive scan of the whole
response body) exist to keep this property true.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import ExerciseType


class ExercisePublic(BaseModel):
    """One exercise, as the renderer sees it.

    ``data`` carries only the learner-visible payload the seed put there —
    options, word-bank tokens, the pairs to match, the sentence with the blank.
    The canonical answer lives in a different column and has no field here.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: ExerciseType
    order_index: int
    instruction: str
    prompt: str
    data: dict[str, Any] = Field(
        description="Learner-visible payload; never contains the answer"
    )


class LessonSkillRef(BaseModel):
    """Just enough of the parent skill for the lesson header."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class LessonResponse(BaseModel):
    """`GET /lessons/{id}` — everything needed to render the lesson."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order_index: int
    xp_reward: int
    skill: LessonSkillRef
    exercises: list[ExercisePublic]


class StartLessonResponse(BaseModel):
    """`POST /lessons/{id}/start` — the session handle plus the exercises.

    Returns the exercises too, so the client makes one request rather than two
    to begin. ``attempt_id`` is the handle every subsequent answer must carry.
    """

    attempt_id: int
    lesson_id: int
    started_at: datetime
    hearts: int
    max_hearts: int
    lesson: LessonResponse


class SubmitAnswerRequest(BaseModel):
    """`POST /lessons/{id}/answer` request body.

    ``answer`` is a free-form object rather than a discriminated union of five
    shapes. That is a deliberate trade: a union would let Pydantic validate each
    payload at the boundary, but it would duplicate — in a second place, in a
    second notation — knowledge the graders already own, and the two would drift.
    Instead the grader validates the shape and raises ``InvalidAnswerError`` for
    a malformed payload, which the route turns into a 422. One definition of what
    each type accepts, living next to the code that interprets it.

    Shapes accepted, by exercise type:

    * ``MULTIPLE_CHOICE`` — ``{"option_id": "o2"}``
    * ``TRANSLATE``       — ``{"tokens": ["buenos", "días"]}``
    * ``MATCH_PAIRS``     — ``{"pairs": [["l1", "r3"], ["l2", "r1"]]}``
    * ``FILL_BLANK``      — ``{"text": "Buenos"}``
    * ``TYPE_ANSWER``     — ``{"text": "adiós"}``
    """

    attempt_id: int
    exercise_id: int
    answer: dict[str, Any]


class SubmitAnswerResponse(BaseModel):
    """`POST /lessons/{id}/answer` — immediate feedback.

    ``correct_answer`` is populated **only when the submission was wrong**. That
    is a deliberate decision: revealing it before the learner answers would make
    the exercise pointless, but revealing it afterwards is the moment teaching
    actually happens, and Duolingo does exactly this. Because it is sent only in
    response to a graded submission, it cannot be used to look answers up — a
    heart has already been spent to see it.
    """

    correct: bool
    correct_answer: str | None = Field(
        default=None,
        description="The expected answer; sent only after an incorrect submission",
    )
    xp_earned: int = Field(
        description="XP this answer is worth; credited to the learner at completion"
    )
    hearts_remaining: int
    #: True when this exercise had already been answered in this attempt and the
    #: original result is being replayed. No new XP, no new heart deduction.
    already_answered: bool = False
    answered_count: int
    total_exercises: int


class SubmitPairRequest(BaseModel):
    """`POST /lessons/{id}/pair` — one match-pairs selection.

    **The smallest request that lets the server grade one pair.** The client
    sends the two ids it just linked and nothing else: not which pairs are
    already matched (the server has that), not whether it believes the pair is
    right (that is the server's decision), and not who is asking (that is the
    session cookie's job).
    """

    attempt_id: int
    exercise_id: int
    left_id: str = Field(max_length=32, examples=["l1"])
    right_id: str = Field(max_length=32, examples=["r3"])


class SubmitPairResponse(BaseModel):
    """`POST /lessons/{id}/pair` — the verdict on one pair.

    ``matched_pairs`` is returned in full every time rather than as a delta. It
    is a handful of ids, and sending the complete server-side truth means a
    client that dropped a response cannot end up rendering a different set of
    locked tiles than the server believes in.
    """

    correct: bool
    #: True once this pair is part of the completed set — i.e. it was correct.
    pair_completed: bool
    #: Every left→right pair the server has accepted for this exercise so far.
    matched_pairs: list[tuple[str, str]]
    #: True when the last remaining pair has just been matched, which is what
    #: lets the client move on. The server has written the exercise's answer row
    #: by then, so completion sees a fully answered lesson.
    exercise_complete: bool
    #: Whether the finished exercise counts as correct — i.e. no wrong pair was
    #: submitted. False until the exercise is complete. Sent explicitly rather
    #: than left for the client to infer from `xp_earned`, so the feedback bar
    #: reports the server's verdict instead of deriving one.
    exercise_correct: bool = False
    hearts_remaining: int
    #: XP the finished exercise is worth; 0 until it is finished, and 0 forever
    #: if any pair was wrong — the same rule every other exercise type follows.
    xp_earned: int = 0
    #: True when this exact pair had already been graded and the original verdict
    #: is being replayed. No second heart, no second row.
    already_answered: bool = False
    #: The same two counters `/answer` returns, so a client that finished this
    #: exercise has everything the shared feedback UI needs without a second
    #: request — and without computing anything itself.
    answered_count: int = 0
    total_exercises: int = 0


class CompleteLessonRequest(BaseModel):
    """`POST /lessons/{id}/complete` request body.

    Deliberately carries **only** the attempt id. No score, no correct count, no
    "completed": true. Everything needed to settle rewards is already in
    ``lesson_attempt_answers``, written by the server. Accepting a client-supplied
    score would hand the client authority over its own rewards.
    """

    attempt_id: int


class CompleteLessonResponse(BaseModel):
    """`POST /lessons/{id}/complete` — the settled result."""

    attempt_id: int
    lesson_id: int
    correct_answers: int
    incorrect_answers: int
    total_exercises: int
    accuracy: float = Field(description="correct / total, 0.0 to 1.0")

    xp_earned: int = Field(description="XP credited by this completion")
    #: False when this lesson had been completed before. Repeat completions are
    #: allowed for practice but award no XP -- see ADR-30.
    first_completion: bool

    total_xp: int
    daily_xp: int
    daily_goal: int
    hearts_remaining: int

    current_streak: int
    longest_streak: int
    streak_extended: bool

    skill_id: int
    lessons_completed: int
    total_lessons: int
    crowns: int
    crown_earned: bool

    #: Titles of achievements unlocked by this completion, so the celebration
    #: screen can mention them. Empty on most completions.
    achievements_unlocked: list[str] = Field(default_factory=list)
