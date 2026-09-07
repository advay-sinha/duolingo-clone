"""Unit tests for the five answer validators.

No database, no HTTP, no fixtures beyond a fake exercise — these run in
milliseconds because `grading.py` is pure. This is where most of the backend's
test value per second lives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.models import ExerciseType
from app.services import grading
from app.services.grading import InvalidAnswerError, normalize


@dataclass
class FakeExercise:
    """Stands in for the ORM row; the validators only read three attributes."""

    type: ExerciseType
    data: dict[str, Any]
    correct_answer: dict[str, Any]


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  hola  ", "hola"),
        ("HOLA", "hola"),
        ("Buenos   días", "buenos días"),
        ("¡Hola!", "hola"),
        ("adiós.", "adiós"),
        ("\tgracias\n", "gracias"),
    ],
)
def test_normalize_applies_the_documented_rule(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_preserves_accents() -> None:
    """Accents change meaning in Spanish, so folding them would be wrong.

    `si` means "if"; `sí` means "yes". Treating them as equal would mark a
    genuinely wrong answer correct.
    """
    assert normalize("sí") != normalize("si")


def test_normalize_treats_composed_and_decomposed_accents_as_equal() -> None:
    """The same character typed two ways must compare equal."""
    composed = "días"  # días with a single code point
    decomposed = "días"  # i + combining acute
    assert normalize(composed) == normalize(decomposed)


# --------------------------------------------------------------------------
# MULTIPLE_CHOICE
# --------------------------------------------------------------------------


def multiple_choice() -> FakeExercise:
    return FakeExercise(
        type=ExerciseType.MULTIPLE_CHOICE,
        data={
            "options": [
                {"id": "o1", "text": "Hola"},
                {"id": "o2", "text": "Adiós"},
            ]
        },
        correct_answer={"option_id": "o1"},
    )


def test_multiple_choice_accepts_the_right_option() -> None:
    verdict = grading.validate(multiple_choice(), {"option_id": "o1"})
    assert verdict.correct is True


def test_multiple_choice_rejects_the_wrong_option() -> None:
    verdict = grading.validate(multiple_choice(), {"option_id": "o2"})
    assert verdict.correct is False
    assert verdict.correct_answer == "Hola"


def test_multiple_choice_rejects_an_option_from_another_exercise() -> None:
    """An unknown id is malformed, not wrong — it must not cost a heart."""
    with pytest.raises(InvalidAnswerError):
        grading.validate(multiple_choice(), {"option_id": "o99"})


def test_multiple_choice_rejects_a_missing_option_id() -> None:
    with pytest.raises(InvalidAnswerError):
        grading.validate(multiple_choice(), {})


def test_multiple_choice_ignores_a_client_supplied_correct_flag() -> None:
    """The client cannot declare its own option correct."""
    verdict = grading.validate(
        multiple_choice(), {"option_id": "o2", "correct": True}
    )
    assert verdict.correct is False


# --------------------------------------------------------------------------
# TRANSLATE
# --------------------------------------------------------------------------


def translate() -> FakeExercise:
    return FakeExercise(
        type=ExerciseType.TRANSLATE,
        data={"tokens": ["buenos", "días", "noches", "hola"]},
        correct_answer={"accepted": ["buenos días"]},
    )


def test_translate_accepts_the_right_token_order() -> None:
    assert grading.validate(translate(), {"tokens": ["buenos", "días"]}).correct


def test_translate_is_case_insensitive() -> None:
    assert grading.validate(translate(), {"tokens": ["Buenos", "DÍAS"]}).correct


def test_translate_ignores_extra_whitespace() -> None:
    assert grading.validate(translate(), {"tokens": ["  buenos ", " días  "]}).correct


def test_translate_rejects_the_wrong_order() -> None:
    assert not grading.validate(translate(), {"tokens": ["días", "buenos"]}).correct


def test_translate_rejects_the_wrong_words() -> None:
    verdict = grading.validate(translate(), {"tokens": ["buenas", "noches"]})
    assert verdict.correct is False
    assert verdict.correct_answer == "buenos días"


def test_translate_accepts_any_listed_alternative() -> None:
    exercise = FakeExercise(
        type=ExerciseType.TRANSLATE,
        data={"tokens": ["i", "am", "tired", "sleepy"]},
        correct_answer={"accepted": ["i am tired", "i am sleepy"]},
    )
    assert grading.validate(exercise, {"tokens": ["i", "am", "sleepy"]}).correct


def test_translate_rejects_a_non_list_payload() -> None:
    with pytest.raises(InvalidAnswerError):
        grading.validate(translate(), {"tokens": "buenos días"})


# --------------------------------------------------------------------------
# MATCH_PAIRS
# --------------------------------------------------------------------------


def match_pairs() -> FakeExercise:
    return FakeExercise(
        type=ExerciseType.MATCH_PAIRS,
        data={
            "left": [
                {"id": "l1", "text": "hola"},
                {"id": "l2", "text": "adiós"},
            ],
            "right": [
                {"id": "r1", "text": "goodbye"},
                {"id": "r2", "text": "hello"},
            ],
        },
        correct_answer={"pairs": [["l1", "r2"], ["l2", "r1"]]},
    )


def test_match_pairs_accepts_the_right_mapping() -> None:
    verdict = grading.validate(
        match_pairs(), {"pairs": [["l1", "r2"], ["l2", "r1"]]}
    )
    assert verdict.correct is True


def test_match_pairs_ignores_the_order_pairs_were_made_in() -> None:
    """Compared as a set, so the learner may match in any order."""
    verdict = grading.validate(
        match_pairs(), {"pairs": [["l2", "r1"], ["l1", "r2"]]}
    )
    assert verdict.correct is True


def test_match_pairs_rejects_a_wrong_mapping() -> None:
    verdict = grading.validate(
        match_pairs(), {"pairs": [["l1", "r1"], ["l2", "r2"]]}
    )
    assert verdict.correct is False


def test_match_pairs_rejects_a_missing_pair() -> None:
    assert not grading.validate(match_pairs(), {"pairs": [["l1", "r2"]]}).correct


def test_match_pairs_rejects_a_duplicated_left_side() -> None:
    """Two pairings for one left item cannot equal the expected set."""
    verdict = grading.validate(
        match_pairs(), {"pairs": [["l1", "r2"], ["l1", "r1"]]}
    )
    assert verdict.correct is False


def test_match_pairs_rejects_ids_from_another_exercise() -> None:
    with pytest.raises(InvalidAnswerError):
        grading.validate(match_pairs(), {"pairs": [["l1", "r99"]]})


def test_match_pairs_rejects_a_malformed_pair() -> None:
    with pytest.raises(InvalidAnswerError):
        grading.validate(match_pairs(), {"pairs": [["l1"]]})


def test_match_pairs_feedback_names_the_expected_mapping() -> None:
    verdict = grading.validate(match_pairs(), {"pairs": [["l1", "r1"], ["l2", "r2"]]})
    assert "hola = hello" in verdict.correct_answer


# --------------------------------------------------------------------------
# FILL_BLANK
# --------------------------------------------------------------------------


def fill_blank() -> FakeExercise:
    return FakeExercise(
        type=ExerciseType.FILL_BLANK,
        data={"sentence": "___ días, señora.", "options": ["Buenos", "Buenas"]},
        correct_answer={"accepted": ["Buenos"]},
    )


def test_fill_blank_accepts_the_right_word() -> None:
    assert grading.validate(fill_blank(), {"text": "Buenos"}).correct


def test_fill_blank_is_case_insensitive() -> None:
    assert grading.validate(fill_blank(), {"text": "buenos"}).correct


def test_fill_blank_ignores_surrounding_whitespace() -> None:
    assert grading.validate(fill_blank(), {"text": "  Buenos  "}).correct


def test_fill_blank_rejects_the_wrong_word() -> None:
    verdict = grading.validate(fill_blank(), {"text": "Buenas"})
    assert verdict.correct is False
    assert verdict.correct_answer == "Buenos"


def test_fill_blank_rejects_a_non_string_payload() -> None:
    with pytest.raises(InvalidAnswerError):
        grading.validate(fill_blank(), {"text": ["Buenos"]})


# --------------------------------------------------------------------------
# TYPE_ANSWER
# --------------------------------------------------------------------------


def type_answer() -> FakeExercise:
    return FakeExercise(
        type=ExerciseType.TYPE_ANSWER,
        data={"language": "es"},
        correct_answer={"accepted": ["adiós", "adios"]},
    )


def test_type_answer_accepts_the_right_text() -> None:
    assert grading.validate(type_answer(), {"text": "adiós"}).correct


def test_type_answer_accepts_a_listed_alternative_spelling() -> None:
    assert grading.validate(type_answer(), {"text": "adios"}).correct


def test_type_answer_is_case_insensitive() -> None:
    assert grading.validate(type_answer(), {"text": "ADIÓS"}).correct


def test_type_answer_ignores_extra_whitespace() -> None:
    assert grading.validate(type_answer(), {"text": "  adiós  "}).correct


def test_type_answer_ignores_trailing_punctuation() -> None:
    assert grading.validate(type_answer(), {"text": "¡adiós!"}).correct


def test_type_answer_rejects_the_wrong_text() -> None:
    verdict = grading.validate(type_answer(), {"text": "hola"})
    assert verdict.correct is False
    assert verdict.correct_answer == "adiós"


def test_type_answer_rejects_an_empty_submission() -> None:
    assert not grading.validate(type_answer(), {"text": "   "}).correct


def test_type_answer_rejects_a_missing_text_field() -> None:
    with pytest.raises(InvalidAnswerError):
        grading.validate(type_answer(), {})


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------


def test_every_exercise_type_has_a_validator() -> None:
    """Adding a type without a validator would be a KeyError at runtime."""
    assert set(grading.VALIDATORS) == set(ExerciseType)


def test_a_non_object_payload_is_rejected() -> None:
    with pytest.raises(InvalidAnswerError):
        grading.validate(type_answer(), "adiós")
