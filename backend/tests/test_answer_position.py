"""The answer must not leak through *position*, not just through field names.

Phase 8's security review found a real leak that every existing test missed.
``test_lesson_response_never_exposes_the_answer`` proves no field named
``correct_answer`` reaches the client — and it was true. But the seed data was
written the natural way, answer first and distractors after, so across the whole
seeded course:

* the correct multiple-choice option was ``options[0]`` in 18 of 18 exercises
* the fill-blank answer was ``options[0]`` in 18 of 18 exercises

A learner with the network tab open could have scored 100% without the response
ever carrying an answer field. ``services/presentation.py`` fixes it by shuffling
the learner-visible lists on the way out, deterministically per exercise id.

These tests are written against the *whole seeded course* rather than one
exercise on purpose: a single exercise says nothing about a positional bias, and
the bug was a property of the corpus.
"""

from __future__ import annotations

from collections import Counter

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise, ExerciseType
from app.services import presentation


def _exercises(db: Session, exercise_type: ExerciseType) -> list[Exercise]:
    return list(
        db.execute(
            select(Exercise).where(Exercise.type == exercise_type)
        ).scalars()
    )


def _public(client: TestClient, lesson_id: int, exercise_id: int) -> dict:
    body = client.get(f"/api/v1/lessons/{lesson_id}").json()
    return next(e for e in body["exercises"] if e["id"] == exercise_id)


# --------------------------------------------------------------------------
# The leak itself
# --------------------------------------------------------------------------


def test_the_correct_choice_is_not_always_the_first_option(
    client: TestClient, db_session: Session
) -> None:
    """Across the course, the correct option must move around.

    The assertion is deliberately weak — "more than one distinct index" — rather
    than demanding a uniform distribution. A shuffle is random; pinning it to
    exact positions would test the seed of the RNG, not the property that
    matters.
    """
    positions: Counter[int] = Counter()
    for exercise in _exercises(db_session, ExerciseType.MULTIPLE_CHOICE):
        public = _public(client, exercise.lesson_id, exercise.id)
        ids = [option["id"] for option in public["data"]["options"]]
        positions[ids.index(exercise.correct_answer["option_id"])] += 1

    assert sum(positions.values()) > 0, "no multiple-choice exercises were seeded"
    assert len(positions) > 1, (
        f"the answer sits at a single position every time: {dict(positions)} — "
        "a client could score 100% by always picking that index"
    )


def test_the_fill_blank_answer_is_not_always_the_first_option(
    client: TestClient, db_session: Session
) -> None:
    first = 0
    total = 0
    for exercise in _exercises(db_session, ExerciseType.FILL_BLANK):
        public = _public(client, exercise.lesson_id, exercise.id)
        options = public["data"]["options"]
        total += 1
        if options and options[0] == exercise.correct_answer["accepted"][0]:
            first += 1

    assert total > 0
    assert first < total, "the fill-blank answer is options[0] in every exercise"


def test_match_pairs_are_not_paired_by_position(
    client: TestClient, db_session: Session
) -> None:
    """`left[i]` must not systematically be the partner of `right[i]`."""
    positional = 0
    total = 0
    for exercise in _exercises(db_session, ExerciseType.MATCH_PAIRS):
        public = _public(client, exercise.lesson_id, exercise.id)
        left = [item["id"] for item in public["data"]["left"]]
        right = [item["id"] for item in public["data"]["right"]]
        expected = {tuple(pair) for pair in exercise.correct_answer["pairs"]}
        total += 1
        if set(zip(left, right)) == expected:
            positional += 1

    assert total > 0
    # Not `positional == 0`: with three pairs a shuffle lands on the answer
    # ordering one time in six by chance, and a single coincidence tells a
    # guesser nothing. The corpus-level bias is what matters.
    assert positional < total, "every match-pairs exercise is aligned by position"


# --------------------------------------------------------------------------
# The properties the shuffle must not break
# --------------------------------------------------------------------------


def test_the_public_order_is_stable_across_requests(
    client: TestClient, db_session: Session
) -> None:
    """Two GETs return the same order.

    A fresh shuffle per request would reorder the options underneath a learner
    who refetched the lesson mid-session.
    """
    first = client.get("/api/v1/lessons/1").json()
    second = client.get("/api/v1/lessons/1").json()

    assert first == second


def test_shuffling_preserves_every_option(
    client: TestClient, db_session: Session
) -> None:
    """A permutation, not a filter: nothing added, nothing dropped."""
    for exercise in _exercises(db_session, ExerciseType.MULTIPLE_CHOICE):
        public = _public(client, exercise.lesson_id, exercise.id)
        assert sorted(
            option["id"] for option in public["data"]["options"]
        ) == sorted(option["id"] for option in exercise.data["options"])


def test_public_data_does_not_mutate_the_stored_row(db_session: Session) -> None:
    """The ORM row keeps its authored order.

    If ``public_data`` shuffled in place, SQLAlchemy would see a dirty attribute
    and the shuffled order could be written back to the database — turning a
    presentation concern into a permanent data change.
    """
    exercise = _exercises(db_session, ExerciseType.MULTIPLE_CHOICE)[0]
    before = [option["id"] for option in exercise.data["options"]]

    presentation.public_data(exercise)

    assert [option["id"] for option in exercise.data["options"]] == before


def test_type_answer_data_passes_through_unchanged(db_session: Session) -> None:
    """A type-answer exercise has no option list, so there is nothing to shuffle."""
    exercise = _exercises(db_session, ExerciseType.TYPE_ANSWER)[0]

    assert presentation.public_data(exercise) == exercise.data


def test_grading_still_accepts_an_answer_chosen_from_the_shuffled_payload(
    client: TestClient, db_session: Session
) -> None:
    """End-to-end proof that shuffling did not break correctness.

    Grading compares option *ids*, never indices — this test is what makes that
    claim more than a comment.
    """
    exercise = _exercises(db_session, ExerciseType.MULTIPLE_CHOICE)[0]
    lesson_id = exercise.lesson_id

    start = client.post(f"/api/v1/lessons/{lesson_id}/start").json()
    public = next(
        e for e in start["lesson"]["exercises"] if e["id"] == exercise.id
    )
    correct_id = exercise.correct_answer["option_id"]
    # The id is present in the shuffled payload, just not at a known index.
    assert correct_id in [option["id"] for option in public["data"]["options"]]

    verdict = client.post(
        f"/api/v1/lessons/{lesson_id}/answer",
        json={
            "attempt_id": start["attempt_id"],
            "exercise_id": exercise.id,
            "answer": {"option_id": correct_id},
        },
    ).json()

    assert verdict["correct"] is True
