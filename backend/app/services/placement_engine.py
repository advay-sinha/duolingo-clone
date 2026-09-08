"""The placement algorithm, as pure functions.

Nothing in this module touches a database, a session, HTTP or the clock. Given
the number of skills in a course and a list of graded answers, the same inputs
always produce the same test and the same result. That is deliberate and it is
the same choice ``grading.py`` makes: the rules that are hardest to argue about
are the ones worth being able to test in milliseconds.

===========================================================================
THE ALGORITHM, IN FULL
===========================================================================

**1. Where difficulty comes from.**

Nothing in the seeded course records a difficulty. Inventing a column and hand-
labelling 90 exercises would be a guess dressed as data. What the course *does*
have is an order: units, then skills, then lessons, then exercises, each with an
``order_index``, and a course is written easiest-first. So order is the
difficulty signal, and it is the honest one — "later in the course" is exactly
what "harder" means for a language course.

The course's skills, flattened into one global order, are cut into
``LEVELS`` (5) contiguous bands:

    level(i) = floor(i * 5 / n) + 1        for skill at global index i of n

With the seeded course's 9 skills that gives bands of [2, 2, 2, 2, 1] skills.
The formula generalises: any course with at least 5 skills gets 5 non-empty
bands, and the bands stay contiguous and ordered.

**2. Which questions get asked.**

Exercises are considered in course order within their band, and only four of the
five types are eligible (``ELIGIBLE_TYPES``). ``MATCH_PAIRS`` is excluded: it is
graded one pair at a time against a heart budget, and placement has no hearts, so
including it would mean either a second grading path or an assessment question
that behaves unlike the rest. Every other type is a single submission with a
single verdict, which is exactly what an assessment needs.

Selection is a pure function of the content — no randomness, not even seeded.
Two learners at the same level see the same question. That is a real limitation
(the test is memorisable) and a deliberate MVP trade: it makes every placement
reproducible in a test and explainable in a sentence. Randomising within a band
is a small change to ``pick_exercise`` when it is wanted.

**3. How the test adapts.**

    Start at level 3, the middle.
    Correct  -> next question one level harder (capped at 5)
    Incorrect -> next question one level easier (floored at 1)
    Stop after QUESTION_COUNT (8) answers, or when no unused eligible
    exercise remains anywhere.

Eight questions is enough for the walk to reach either extreme from the middle
and then confirm it, and short enough that nobody abandons the test. If a band is
exhausted, the nearest band with an unused question is used instead — a learner
must never be shown the same exercise twice, because the adaptive rule reads its
own history and a repeat would bend the test.

**4. How the result is calculated.**

For each level L that was asked at least once:

    passed(L)  <=>  2 * correct(L) >= asked(L)        (at least half right)

    result_level = the largest L such that L and *every asked level below L*
                   were passed.  0 if level 1 was asked and not passed.

The "every level below" clause is the word "consistently". Without it, one lucky
answer at level 5 after failing levels 1–3 would place a beginner at the end of
the course. With it, the result is the top of an unbroken run.

A **weighted score** — the sum of the difficulty of every correct answer, out of
the sum of the difficulty of every question asked — is also computed. It is
reported to the learner and stored, and it deliberately does **not** decide the
level: a single number cannot distinguish "five easy questions right" from "one
hard question right", and that distinction is the entire job of a placement test.
It is transparency, not the mechanism.

**5. Which skill they start at.**

    result_level = 0  ->  the first skill (index 0)
    result_level = L  ->  the first skill of band L+1, capped at the last skill

So passing level 2 means "you have shown you know the level-1 and level-2
material", and the learner starts at the beginning of band 3. Passing the top
level places them at the last skill of the course — there is nothing beyond it,
and the cap says so rather than pretending there is.

**Poor performance** is not a failure state: ``result_level = 0`` places the
learner at the first skill, which is precisely where "start from scratch" would
have put them. The test costs them nothing.

**Extreme performance** is capped at the final skill. A learner who passes every
level skips to the last skill and still has to complete it — placement never
completes anything on the learner's behalf.

**6. What proficiency has to do with it: nothing.**

The self-reported proficiency from the previous screen is stored and never read
here. Letting it seed the starting difficulty would make the outcome partly a
function of the learner's own claim, and replacing that claim with evidence is
the only reason the placement test exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import ExerciseType

#: How many difficulty bands the course is cut into.
LEVELS = 5

#: How many questions one placement test asks.
QUESTION_COUNT = 8

#: Where the adaptive walk begins: the middle band, so a learner at either
#: extreme is found in roughly the same number of questions.
STARTING_LEVEL = 3

#: Exercise types the placement test will ask. See the module docstring for why
#: MATCH_PAIRS is absent.
ELIGIBLE_TYPES: tuple[ExerciseType, ...] = (
    ExerciseType.MULTIPLE_CHOICE,
    ExerciseType.TRANSLATE,
    ExerciseType.FILL_BLANK,
    ExerciseType.TYPE_ANSWER,
)


@dataclass(frozen=True)
class AnsweredQuestion:
    """One graded placement answer, as the engine needs to see it."""

    difficulty: int
    is_correct: bool


@dataclass(frozen=True)
class PlacementResult:
    """The outcome of a completed placement test."""

    #: Highest consistently passed difficulty band, 0–5.
    level: int
    #: Global index of the skill the learner starts at.
    skill_index: int
    #: Sum of the difficulty of every correct answer.
    score: int
    #: Sum of the difficulty of every question asked.
    max_score: int


def difficulty_of(skill_index: int, skill_count: int) -> int:
    """The difficulty band a skill belongs to, 1–``LEVELS``.

    Args:
        skill_index: The skill's position in the course's global skill order.
        skill_count: How many skills the course has.

    A course with fewer skills than levels still works — bands simply hold at
    most one skill each and the top bands go empty, which the selection step
    handles by falling back to the nearest non-empty band.
    """
    if skill_count <= 0:
        raise ValueError("A course with no skills cannot be placed against.")
    index = max(0, min(skill_index, skill_count - 1))
    return min(LEVELS, index * LEVELS // skill_count + 1)


def band_start(level: int, skill_count: int) -> int:
    """The global index of the first skill in a difficulty band.

    The inverse of :func:`difficulty_of`. ``ceil((level - 1) * n / LEVELS)``,
    written with integer arithmetic so there is no float rounding to reason
    about. A level above the top band returns the last skill index, which is what
    makes "placed past the end of the course" mean "the last skill".
    """
    if skill_count <= 0:
        raise ValueError("A course with no skills cannot be placed against.")
    if level <= 1:
        return 0
    if level > LEVELS:
        return skill_count - 1
    index = -((-(level - 1) * skill_count) // LEVELS)  # ceil division
    return min(index, skill_count - 1)


def next_difficulty(current: int, was_correct: bool) -> int:
    """Where the adaptive walk goes after one verdict.

    One step up on a correct answer, one step down on an incorrect one, clamped
    to the available bands. Deliberately not a bigger jump: a single answer is
    weak evidence, and a two-step move would let one careless mistake drop a
    learner two bands with nothing in between to correct it.
    """
    step = 1 if was_correct else -1
    return max(1, min(LEVELS, current + step))


def levels_asked(answers: list[AnsweredQuestion]) -> dict[int, tuple[int, int]]:
    """Per level, ``(asked, correct)`` — the raw material for the result."""
    tally: dict[int, tuple[int, int]] = {}
    for answer in answers:
        asked, correct = tally.get(answer.difficulty, (0, 0))
        tally[answer.difficulty] = (asked + 1, correct + (1 if answer.is_correct else 0))
    return tally


def passed(asked: int, correct: int) -> bool:
    """Whether a level counts as passed: at least half of its questions right.

    Written as ``2 * correct >= asked`` rather than ``correct / asked >= 0.5`` to
    keep it in integers — no float comparison, and the two-of-three case is
    exactly what it looks like.
    """
    return asked > 0 and 2 * correct >= asked


def score(answers: list[AnsweredQuestion]) -> tuple[int, int]:
    """The weighted score and the maximum it could have been.

    A correct answer is worth the difficulty it was asked at, so getting a
    level-5 question right counts for five times a level-1 question. Reported,
    never used to decide the level — see the module docstring.
    """
    earned = sum(a.difficulty for a in answers if a.is_correct)
    possible = sum(a.difficulty for a in answers)
    return earned, possible


def evaluate(answers: list[AnsweredQuestion], skill_count: int) -> PlacementResult:
    """Turn a completed test's answers into a level and a starting skill.

    An empty answer list places the learner at the first skill with level 0,
    which is the same outcome as "start from scratch" — the honest result for a
    test that produced no evidence.
    """
    tally = levels_asked(answers)

    # Walk upward and stop at the first asked level that was not passed. The
    # result is the top of an unbroken run of passes, which is what
    # "consistently passed" means. A level that was never asked is skipped
    # rather than treated as a failure: the adaptive walk simply never went
    # there, and that is not evidence against the learner.
    level = 0
    for candidate in range(1, LEVELS + 1):
        if candidate not in tally:
            continue
        asked, correct = tally[candidate]
        if not passed(asked, correct):
            break
        level = candidate

    earned, possible = score(answers)
    return PlacementResult(
        level=level,
        skill_index=band_start(level + 1, skill_count) if level > 0 else 0,
        score=earned,
        max_score=possible,
    )


def is_finished(answered_count: int, candidates_remaining: bool) -> bool:
    """Whether the test is over.

    Two ways to end, and both matter: the question budget is spent, or the course
    has run out of unused eligible exercises. The second is not hypothetical for
    a small course, and ending cleanly is far better than looping on the same
    question.
    """
    return answered_count >= QUESTION_COUNT or not candidates_remaining
