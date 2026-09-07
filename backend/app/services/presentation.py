"""Learner-visible ordering of exercise payloads.

**Why this module exists.** ``ExercisePublic`` guarantees the canonical answer
never appears as a *field* in a response. Phase 8's security review found that
this is not the whole story: the answer can also leak through *position*. In the
seeded course the correct multiple-choice option was ``options[0]`` in all 18
multiple-choice exercises, and the fill-blank answer was ``options[0]`` in all
18 fill-blank exercises, because that is the natural way to write seed data —
answer first, distractors after. Anyone who opened the network tab could have
scored 100% by always choosing the first option, without the response ever
containing a field named ``correct_answer``.

Fixing the seed data by hand would fix today's course and quietly break again
the next time someone adds an exercise. So the ordering is decoupled here, at
the one point where an exercise becomes a response: whatever order the author
wrote, the client sees a shuffled one.

**Why the shuffle is deterministic (seeded by exercise id).** A fresh shuffle
per request would reorder the options underneath a learner who refetches the
lesson — the same exercise would look different on a reload mid-session, and
responses would stop being comparable in tests. Seeding on the exercise id gives
each exercise one stable order that is nonetheless uncorrelated with the order
the answer was authored in.

**Why shuffling is safe.** Every validator in ``grading`` is order-independent:
multiple choice compares an option *id*, match-pairs compares a *set* of id
pairs, and the three text types normalise and compare strings. Nothing anywhere
grades by index. See ``grading.py``.

This module is pure and never mutates the ORM row — it builds copies. Mutating
``exercise.data`` in place would mark the object dirty and could persist the
shuffled order on the next flush.
"""

from __future__ import annotations

import random
from typing import Any

from app.models import Exercise, ExerciseType

# Which learner-visible list(s) of each exercise type carry an ordering that
# could reveal the answer. Types absent from this table (TYPE_ANSWER, whose
# `data` is only a language tag) are returned unchanged.
_SHUFFLED_KEYS: dict[ExerciseType, tuple[str, ...]] = {
    ExerciseType.MULTIPLE_CHOICE: ("options",),
    ExerciseType.FILL_BLANK: ("options",),
    ExerciseType.TRANSLATE: ("tokens",),
    ExerciseType.MATCH_PAIRS: ("left", "right"),
}


def public_data(exercise: Exercise) -> dict[str, Any]:
    """Return ``exercise.data`` with its option lists in a stable shuffled order.

    Args:
        exercise: The ORM row. Only ``id``, ``type`` and ``data`` are read; the
            row is not modified.

    Returns:
        A new dict. Lists named in ``_SHUFFLED_KEYS`` are new lists too; the
        items inside them are shared, which is fine because they are never
        mutated.
    """
    data = dict(exercise.data)
    keys = _SHUFFLED_KEYS.get(exercise.type, ())
    if not keys:
        return data

    # One generator for the whole exercise, so the two match-pairs columns do
    # not receive the same permutation.
    rng = random.Random(exercise.id)
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            shuffled = list(value)
            rng.shuffle(shuffled)
            data[key] = shuffled
    return data
