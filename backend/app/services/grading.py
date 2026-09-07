"""Answer validation — five pure functions, one per exercise type.

**The frontend is not trusted.** It renders exercises and collects input; it
never decides correctness. Every validator here compares a submission against
the canonical answer stored in the database, which the client has never seen.

Everything in this module is **pure**: no database, no session, no HTTP, no
clock. Given an exercise's stored data and a submission, the same inputs always
produce the same verdict. That is what makes the rules testable in milliseconds
without a database, and it is where most of the backend's test value lives.

Normalisation rule, applied consistently by every text-comparing validator:

* strip leading and trailing whitespace
* collapse internal runs of whitespace to a single space
* casefold (a more aggressive lowercase that handles non-English text correctly)
* strip surrounding punctuation: ``. , ! ? ; :`` and quotes

Accents are **not** stripped: in Spanish they change meaning (``si`` vs ``sí``),
so folding them would mark a genuinely wrong answer correct. That is a
deliberate choice, not an omission.

No fuzzy matching, no edit distance, no NLP. A validator that "almost" accepts
an answer is one that cannot be explained to a learner or tested reliably.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from app.models import Exercise, ExerciseType

_PUNCTUATION = ".,!?;:\"'¡¿"


def normalize(text: str) -> str:
    """Apply the shared text normalisation rule.

    ``NFC`` normalisation first, so that an accented character typed as a single
    code point and one typed as letter-plus-combining-accent compare equal —
    they look identical to the learner and must behave identically.
    """
    text = unicodedata.normalize("NFC", text)
    text = " ".join(text.split())
    text = text.strip(_PUNCTUATION).strip()
    return text.casefold()


@dataclass(frozen=True)
class Verdict:
    """The outcome of grading one answer.

    ``correct_answer`` is a human-readable rendering of the canonical answer,
    used only to show feedback after an incorrect submission.
    """

    correct: bool
    correct_answer: str


class InvalidAnswerError(ValueError):
    """The submission is malformed for this exercise type.

    Distinct from "wrong": a wrong answer is a normal part of learning and costs
    a heart, whereas a malformed payload means the client sent something the
    exercise type cannot interpret — a bug, not a mistake. The route turns this
    into a 422 and no heart is lost.
    """


# --------------------------------------------------------------------------
# Validators
# --------------------------------------------------------------------------


def _validate_multiple_choice(
    data: dict[str, Any], answer: dict[str, Any], submitted: dict[str, Any]
) -> Verdict:
    """Compare the chosen option id against the stored one.

    The submission carries only an option *id*. It cannot carry a "correct"
    flag, because the client is never told which option is correct and the
    server would ignore such a field anyway.
    """
    option_id = submitted.get("option_id")
    if not isinstance(option_id, str):
        raise InvalidAnswerError("Expected an 'option_id' string.")

    options = {option["id"]: option["text"] for option in data["options"]}
    if option_id not in options:
        # An id that is not on this exercise means the client is out of sync or
        # tampering. Neither is a wrong answer.
        raise InvalidAnswerError(f"Option {option_id!r} is not part of this exercise.")

    correct_id = answer["option_id"]
    return Verdict(option_id == correct_id, options[correct_id])


def _validate_translate(
    data: dict[str, Any], answer: dict[str, Any], submitted: dict[str, Any]
) -> Verdict:
    """Join the chosen word-bank tokens and compare against accepted sentences.

    The client sends the tokens it placed, in order. Joining and normalising
    means the learner's spacing and capitalisation cannot make a right answer
    read as wrong.
    """
    tokens = submitted.get("tokens")
    if not isinstance(tokens, list) or not all(isinstance(t, str) for t in tokens):
        raise InvalidAnswerError("Expected 'tokens' to be a list of strings.")

    attempt = normalize(" ".join(tokens))
    accepted = answer["accepted"]
    return Verdict(
        any(attempt == normalize(candidate) for candidate in accepted),
        accepted[0],
    )


def _validate_match_pairs(
    data: dict[str, Any], answer: dict[str, Any], submitted: dict[str, Any]
) -> Verdict:
    """Compare submitted pairings as a set, so ordering cannot matter.

    Comparing sets rather than lists means the learner may match in any order.
    Because it is a set of ``(left, right)`` tuples, a missing pair, an extra
    pair, or a duplicated left-hand id all fail — set equality handles every one
    of those without a special case.
    """
    pairs = submitted.get("pairs")
    if not isinstance(pairs, list):
        raise InvalidAnswerError("Expected 'pairs' to be a list.")

    try:
        submitted_set = {(str(left), str(right)) for left, right in pairs}
    except (TypeError, ValueError) as exc:
        raise InvalidAnswerError("Each pair must be a [left_id, right_id].") from exc

    left_ids = {item["id"] for item in data["left"]}
    right_ids = {item["id"] for item in data["right"]}
    for left, right in submitted_set:
        if left not in left_ids or right not in right_ids:
            raise InvalidAnswerError(f"Pair ({left}, {right}) is not part of this exercise.")

    expected = {(left, right) for left, right in answer["pairs"]}
    texts = {item["id"]: item["text"] for item in data["left"] + data["right"]}
    readable = ", ".join(
        f"{texts[left]} = {texts[right]}" for left, right in answer["pairs"]
    )
    return Verdict(submitted_set == expected, readable)


def _validate_fill_blank(
    data: dict[str, Any], answer: dict[str, Any], submitted: dict[str, Any]
) -> Verdict:
    """Compare the filled-in text against the accepted answers."""
    text = submitted.get("text")
    if not isinstance(text, str):
        raise InvalidAnswerError("Expected a 'text' string.")

    attempt = normalize(text)
    accepted = answer["accepted"]
    return Verdict(
        any(attempt == normalize(candidate) for candidate in accepted),
        accepted[0],
    )


def _validate_type_answer(
    data: dict[str, Any], answer: dict[str, Any], submitted: dict[str, Any]
) -> Verdict:
    """Compare freely typed text against the accepted answers.

    Identical logic to fill-blank today. They are kept separate rather than
    aliased because they are different exercise types to a learner and will
    diverge — typed answers are the natural place for a future "almost correct,
    watch your accents" hint, which must never apply to a multiple-option blank.
    """
    text = submitted.get("text")
    if not isinstance(text, str):
        raise InvalidAnswerError("Expected a 'text' string.")

    attempt = normalize(text)
    accepted = answer["accepted"]
    return Verdict(
        any(attempt == normalize(candidate) for candidate in accepted),
        accepted[0],
    )


# Dispatch table rather than an if/elif chain: adding a sixth exercise type is
# one entry here plus one seed shape, and `validate` needs no change at all.
VALIDATORS: dict[
    ExerciseType,
    Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Verdict],
] = {
    ExerciseType.MULTIPLE_CHOICE: _validate_multiple_choice,
    ExerciseType.TRANSLATE: _validate_translate,
    ExerciseType.MATCH_PAIRS: _validate_match_pairs,
    ExerciseType.FILL_BLANK: _validate_fill_blank,
    ExerciseType.TYPE_ANSWER: _validate_type_answer,
}


def validate(exercise: Exercise, submitted: dict[str, Any]) -> Verdict:
    """Grade one submission against one exercise.

    Args:
        exercise: The ORM row, carrying both the learner-visible ``data`` and
            the canonical ``correct_answer``.
        submitted: The client's answer payload.

    Raises:
        InvalidAnswerError: if the payload is malformed for this type.
    """
    if not isinstance(submitted, dict):
        raise InvalidAnswerError("The answer payload must be an object.")

    validator = VALIDATORS[exercise.type]
    try:
        return validator(exercise.data, exercise.correct_answer, submitted)
    except InvalidAnswerError:
        raise
    except (KeyError, TypeError, AttributeError) as exc:
        # A payload shaped wrongly enough to break indexing is malformed, not
        # incorrect -- it must not silently cost the learner a heart.
        raise InvalidAnswerError(f"Malformed answer payload: {exc}") from exc
