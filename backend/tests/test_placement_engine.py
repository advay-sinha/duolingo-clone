"""The placement algorithm, tested without a database.

Everything in ``placement_engine`` is pure, so these run in milliseconds and
assert the *rules* rather than their plumbing. If the banding, the adaptive walk
or the scoring is ever wrong, it should be wrong here first — a failure in this
file names the rule, whereas a failure in an API test names a request.
"""

from __future__ import annotations

import pytest

from app.services import placement_engine as engine
from app.services.placement_engine import AnsweredQuestion


def answers(*pairs: tuple[int, bool]) -> list[AnsweredQuestion]:
    """Build an answer list from ``(difficulty, was_correct)`` pairs."""
    return [AnsweredQuestion(difficulty, correct) for difficulty, correct in pairs]


# --------------------------------------------------------------------------
# Difficulty banding
# --------------------------------------------------------------------------


def test_the_seeded_course_splits_into_five_contiguous_bands() -> None:
    """9 skills become bands of [2, 2, 2, 2, 1], in order."""
    levels = [engine.difficulty_of(index, 9) for index in range(9)]
    assert levels == [1, 1, 2, 2, 3, 3, 4, 4, 5]


def test_difficulty_never_leaves_the_valid_range() -> None:
    for skill_count in (1, 5, 9, 40):
        for index in range(skill_count):
            level = engine.difficulty_of(index, skill_count)
            assert 1 <= level <= engine.LEVELS


def test_band_start_is_the_inverse_of_difficulty_of() -> None:
    """The first skill of band L must actually be in band L."""
    for skill_count in (5, 9, 12, 40):
        for level in range(1, engine.LEVELS + 1):
            index = engine.band_start(level, skill_count)
            assert engine.difficulty_of(index, skill_count) == level


def test_band_start_above_the_top_band_is_the_last_skill() -> None:
    """There is nothing past the end of the course, and the cap says so."""
    assert engine.band_start(engine.LEVELS + 1, 9) == 8


def test_a_course_with_no_skills_is_refused_rather_than_guessed_at() -> None:
    with pytest.raises(ValueError):
        engine.difficulty_of(0, 0)
    with pytest.raises(ValueError):
        engine.band_start(1, 0)


# --------------------------------------------------------------------------
# The adaptive walk
# --------------------------------------------------------------------------


def test_correct_moves_up_and_incorrect_moves_down() -> None:
    assert engine.next_difficulty(3, True) == 4
    assert engine.next_difficulty(3, False) == 2


def test_the_walk_is_clamped_at_both_ends() -> None:
    assert engine.next_difficulty(5, True) == 5
    assert engine.next_difficulty(1, False) == 1


def test_the_walk_moves_one_band_at_a_time() -> None:
    """A single answer is weak evidence; a two-step jump would over-react."""
    for level in range(1, engine.LEVELS + 1):
        for correct in (True, False):
            assert abs(engine.next_difficulty(level, correct) - level) <= 1


# --------------------------------------------------------------------------
# Passing a level
# --------------------------------------------------------------------------


def test_half_right_passes() -> None:
    assert engine.passed(asked=2, correct=1) is True
    assert engine.passed(asked=4, correct=2) is True


def test_less_than_half_fails() -> None:
    assert engine.passed(asked=3, correct=1) is False
    assert engine.passed(asked=1, correct=0) is False


def test_a_level_that_was_never_asked_is_not_passed() -> None:
    assert engine.passed(asked=0, correct=0) is False


# --------------------------------------------------------------------------
# Scoring and the final level
# --------------------------------------------------------------------------


def test_the_weighted_score_values_harder_questions_more() -> None:
    earned, possible = engine.score(answers((1, True), (5, True), (3, False)))
    assert (earned, possible) == (6, 9)


def test_a_learner_who_gets_everything_wrong_places_at_the_first_skill() -> None:
    result = engine.evaluate(answers((3, False), (2, False), (1, False)), 9)
    assert result.level == 0
    assert result.skill_index == 0


def test_a_learner_who_passes_everything_places_at_the_last_skill() -> None:
    result = engine.evaluate(
        answers((3, True), (4, True), (5, True), (5, True)), 9
    )
    assert result.level == 5
    assert result.skill_index == 8


def test_passing_up_to_level_three_starts_the_learner_at_band_four() -> None:
    result = engine.evaluate(
        answers((3, True), (4, False), (3, True), (2, True), (1, True)), 9
    )
    # Levels 1, 2 and 3 were asked and passed; level 4 was asked and failed.
    assert result.level == 3
    assert result.skill_index == engine.band_start(4, 9) == 6


def test_a_broken_run_stops_at_the_break_not_at_the_top() -> None:
    """This is the word 'consistently' in the rule, under test.

    One lucky answer at level 5 after failing level 2 must not place a beginner
    at the end of the course.
    """
    result = engine.evaluate(
        answers((1, True), (2, False), (2, False), (5, True)), 9
    )
    assert result.level == 1


def test_a_level_that_was_never_asked_does_not_break_the_run() -> None:
    """The walk simply never visited it; that is not evidence against anyone."""
    result = engine.evaluate(answers((1, True), (3, True)), 9)
    assert result.level == 3


def test_a_test_with_no_answers_places_at_the_beginning() -> None:
    result = engine.evaluate([], 9)
    assert result == engine.PlacementResult(
        level=0, skill_index=0, score=0, max_score=0
    )


def test_the_weighted_score_does_not_decide_the_level() -> None:
    """Five easy answers outscore one hard one, and still place lower.

    This is the reason the score is reported rather than used: a single number
    cannot tell "knows a lot of easy material" from "knows some hard material",
    and that distinction is the entire job of a placement test.
    """
    lots_of_easy = engine.evaluate(answers(*[(1, True)] * 8), 9)
    one_hard = engine.evaluate(answers((1, True), (2, True), (3, True)), 9)

    assert lots_of_easy.score > one_hard.score
    assert lots_of_easy.level < one_hard.level


# --------------------------------------------------------------------------
# Stopping
# --------------------------------------------------------------------------


def test_the_test_stops_after_the_question_budget() -> None:
    assert engine.is_finished(engine.QUESTION_COUNT, candidates_remaining=True)


def test_the_test_stops_when_the_course_runs_out_of_questions() -> None:
    assert engine.is_finished(2, candidates_remaining=False)


def test_the_test_continues_while_there_is_budget_and_content() -> None:
    assert not engine.is_finished(2, candidates_remaining=True)


def test_match_pairs_is_not_asked() -> None:
    """It is graded a pair at a time against a heart budget placement has not."""
    from app.models import ExerciseType

    assert ExerciseType.MATCH_PAIRS not in engine.ELIGIBLE_TYPES
    assert len(engine.ELIGIBLE_TYPES) == 4
