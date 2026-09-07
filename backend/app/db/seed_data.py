"""The seeded course content, as plain data.

Separated from ``seed.py`` on purpose: this module is *what* the course
contains, ``seed.py`` is *how* it gets into the database. Editing a sentence
should never mean touching transaction handling, and vice versa.

The course is **English → Spanish** for a beginner. All content here is original
and written for this project; nothing is copied from Duolingo.

Shape of the structure:

    COURSE -> units[] -> skills[] -> lessons[] -> exercises[]

Exercises are built by the five small constructors below rather than written as
raw dictionaries, so every payload of a given type has an identical shape. That
consistency is what lets the Phase 4 grader be five short pure functions.

Totals: 1 course, 3 units, 9 skills, 18 lessons, 90 exercises — every lesson
contains exactly one exercise of each of the five types.
"""

from typing import Any

from app.models.content import ExerciseType

# --------------------------------------------------------------------------
# Exercise constructors
#
# Each returns the dict that seed.py turns into an Exercise row. Two JSON
# payloads per exercise:
#   data           - everything the learner may see
#   correct_answer - the solution, never sent to the client
# --------------------------------------------------------------------------


def mc(
    prompt: str,
    options: list[str],
    correct_index: int,
    instruction: str = "Select the correct translation",
) -> dict[str, Any]:
    """Multiple choice: one prompt, several options, exactly one right."""
    ids = [f"o{i + 1}" for i in range(len(options))]
    return {
        "type": ExerciseType.MULTIPLE_CHOICE,
        "instruction": instruction,
        "prompt": prompt,
        "data": {
            "options": [
                {"id": oid, "text": text} for oid, text in zip(ids, options)
            ]
        },
        "correct_answer": {"option_id": ids[correct_index]},
    }


def translate(
    prompt: str,
    answer: str,
    distractors: list[str],
    instruction: str = "Translate this sentence",
) -> dict[str, Any]:
    """Word bank: build the answer sentence from a pool of tokens.

    The pool is the answer's words plus plausible distractors, sorted so the
    seed is deterministic and the correct order is never given away by the
    token order itself.
    """
    tokens = sorted(answer.split() + distractors, key=str.casefold)
    return {
        "type": ExerciseType.TRANSLATE,
        "instruction": instruction,
        "prompt": prompt,
        "data": {"tokens": tokens},
        "correct_answer": {"accepted": [answer]},
    }


def match(
    pairs: list[tuple[str, str]],
    instruction: str = "Match the pairs",
) -> dict[str, Any]:
    """Match pairs: two columns, one correct pairing.

    The right-hand column is reversed relative to the left so the puzzle is not
    solved by reading straight across — deterministic, but not trivial.
    """
    left = [{"id": f"l{i + 1}", "text": es} for i, (es, _) in enumerate(pairs)]
    order = list(reversed(range(len(pairs))))
    right = [
        {"id": f"r{position + 1}", "text": pairs[source][1]}
        for position, source in enumerate(order)
    ]
    right_id_for_source = {source: f"r{position + 1}" for position, source in enumerate(order)}
    return {
        "type": ExerciseType.MATCH_PAIRS,
        "instruction": instruction,
        "prompt": "Match each Spanish word to its meaning",
        "data": {"left": left, "right": right},
        "correct_answer": {
            "pairs": [[f"l{i + 1}", right_id_for_source[i]] for i in range(len(pairs))]
        },
    }


def fill(
    sentence: str,
    answer: str,
    options: list[str],
    prompt: str,
    instruction: str = "Fill in the blank",
) -> dict[str, Any]:
    """Fill in the blank: a sentence with ``___`` and a small set of options."""
    return {
        "type": ExerciseType.FILL_BLANK,
        "instruction": instruction,
        "prompt": prompt,
        "data": {"sentence": sentence, "options": options},
        "correct_answer": {"accepted": [answer]},
    }


def type_answer(
    prompt: str,
    accepted: list[str],
    instruction: str = "Type this in Spanish",
) -> dict[str, Any]:
    """Free text: the learner types the answer.

    ``accepted`` lists every spelling that counts as correct, so the Phase 4
    grader can accept "el agua" and "agua" without special-casing.
    """
    return {
        "type": ExerciseType.TYPE_ANSWER,
        "instruction": instruction,
        "prompt": prompt,
        "data": {"language": "es"},
        "correct_answer": {"accepted": accepted},
    }


# --------------------------------------------------------------------------
# The course
# --------------------------------------------------------------------------

COURSE: dict[str, Any] = {
    "slug": "spanish-for-english-speakers",
    "title": "Spanish",
    "description": "Learn everyday Spanish from English, one short lesson at a time.",
    "source_language": "English",
    "target_language": "Spanish",
    "flag_emoji": "🇪🇸",
    "units": [
        # ==================================================================
        # UNIT 1 — Greetings and basics
        # ==================================================================
        {
            "title": "Greetings and basics",
            "description": "Say hello, introduce yourself, and be polite.",
            "color_key": "green",
            "skills": [
                {
                    "title": "Greetings",
                    "description": "Hello, goodbye and the times of day.",
                    "icon": "waving_hand",
                    "lessons": [
                        {
                            "title": "Hello and goodbye",
                            "exercises": [
                                mc("Hello", ["Hola", "Adiós", "Gracias", "Noche"], 0),
                                translate(
                                    "Good morning",
                                    "buenos días",
                                    ["noches", "tardes", "hola"],
                                ),
                                match(
                                    [
                                        ("hola", "hello"),
                                        ("adiós", "goodbye"),
                                        ("buenas noches", "good night"),
                                    ]
                                ),
                                fill(
                                    "___ días, señora.",
                                    "Buenos",
                                    ["Buenos", "Buenas", "Bueno"],
                                    prompt="Complete the greeting",
                                ),
                                type_answer("Goodbye", ["adiós", "adios"]),
                            ],
                        },
                        {
                            "title": "Polite words",
                            "exercises": [
                                mc(
                                    "Thank you",
                                    ["Gracias", "Por favor", "Perdón", "Hola"],
                                    0,
                                ),
                                translate(
                                    "Thank you very much",
                                    "muchas gracias",
                                    ["por", "favor", "buenas"],
                                ),
                                match(
                                    [
                                        ("gracias", "thank you"),
                                        ("por favor", "please"),
                                        ("de nada", "you're welcome"),
                                    ]
                                ),
                                fill(
                                    "Un café, por ___.",
                                    "favor",
                                    ["favor", "gracias", "nada"],
                                    prompt="Complete the polite request",
                                ),
                                type_answer("Please", ["por favor"]),
                            ],
                        },
                    ],
                },
                {
                    "title": "Introductions",
                    "description": "Say your name and ask how someone is.",
                    "icon": "person",
                    "lessons": [
                        {
                            "title": "My name is",
                            "exercises": [
                                mc(
                                    "My name is Ana",
                                    [
                                        "Me llamo Ana",
                                        "Tengo Ana",
                                        "Soy de Ana",
                                        "Ana está",
                                    ],
                                    0,
                                ),
                                translate(
                                    "I am a student",
                                    "soy estudiante",
                                    ["eres", "un", "maestro"],
                                ),
                                match(
                                    [
                                        ("me llamo", "my name is"),
                                        ("soy", "I am"),
                                        ("mucho gusto", "nice to meet you"),
                                    ]
                                ),
                                fill(
                                    "Yo ___ llamo Carlos.",
                                    "me",
                                    ["me", "te", "se"],
                                    prompt="Complete the introduction",
                                ),
                                type_answer("Nice to meet you", ["mucho gusto"]),
                            ],
                        },
                        {
                            "title": "How are you?",
                            "exercises": [
                                mc(
                                    "How are you?",
                                    [
                                        "¿Cómo estás?",
                                        "¿Dónde estás?",
                                        "¿Qué comes?",
                                        "¿Quién eres?",
                                    ],
                                    0,
                                ),
                                translate(
                                    "I am very well",
                                    "estoy muy bien",
                                    ["mal", "eres", "poco"],
                                ),
                                match(
                                    [
                                        ("bien", "well"),
                                        ("mal", "badly"),
                                        ("más o menos", "so-so"),
                                    ]
                                ),
                                fill(
                                    "¿Cómo ___ usted?",
                                    "está",
                                    ["está", "estás", "estoy"],
                                    prompt="Complete the polite question",
                                ),
                                type_answer("And you?", ["¿y tú?", "y tú", "y usted"]),
                            ],
                        },
                    ],
                },
                {
                    "title": "Basics",
                    "description": "Yes, no, and asking simple questions.",
                    "icon": "school",
                    "lessons": [
                        {
                            "title": "Yes and no",
                            "exercises": [
                                mc("Yes", ["Sí", "No", "Tal vez", "Nunca"], 0),
                                translate(
                                    "I do not understand",
                                    "no entiendo",
                                    ["sí", "hablo", "mucho"],
                                ),
                                match(
                                    [
                                        ("sí", "yes"),
                                        ("no", "no"),
                                        ("tal vez", "maybe"),
                                    ]
                                ),
                                fill(
                                    "___, no hablo español.",
                                    "No",
                                    ["No", "Sí", "Ya"],
                                    prompt="Complete the answer",
                                ),
                                type_answer("I don't know", ["no sé", "no se"]),
                            ],
                        },
                        {
                            "title": "Simple questions",
                            "exercises": [
                                mc(
                                    "Where is the bathroom?",
                                    [
                                        "¿Dónde está el baño?",
                                        "¿Qué es el baño?",
                                        "¿Cómo es el baño?",
                                        "¿Cuándo es el baño?",
                                    ],
                                    0,
                                ),
                                translate(
                                    "What is this",
                                    "qué es esto",
                                    ["cómo", "dónde", "ese"],
                                ),
                                match(
                                    [
                                        ("dónde", "where"),
                                        ("qué", "what"),
                                        ("cuándo", "when"),
                                    ]
                                ),
                                fill(
                                    "¿___ está la estación?",
                                    "Dónde",
                                    ["Dónde", "Qué", "Cómo"],
                                    prompt="Complete the question",
                                ),
                                type_answer("Who?", ["¿quién?", "quién", "quien"]),
                            ],
                        },
                    ],
                },
            ],
        },
        # ==================================================================
        # UNIT 2 — Everyday life
        # ==================================================================
        {
            "title": "Everyday life",
            "description": "Food, family and animals — the words you use daily.",
            "color_key": "blue",
            "skills": [
                {
                    "title": "Food",
                    "description": "Order a drink and name what you eat.",
                    "icon": "restaurant",
                    "lessons": [
                        {
                            "title": "Drinks",
                            "exercises": [
                                mc("Water", ["El agua", "El pan", "La leche", "El café"], 0),
                                translate(
                                    "I drink coffee",
                                    "yo bebo café",
                                    ["come", "leche", "tú"],
                                ),
                                match(
                                    [
                                        ("el agua", "water"),
                                        ("la leche", "milk"),
                                        ("el café", "coffee"),
                                    ]
                                ),
                                fill(
                                    "Yo ___ agua todos los días.",
                                    "bebo",
                                    ["bebo", "como", "hablo"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("The milk", ["la leche", "leche"]),
                            ],
                        },
                        {
                            "title": "At the table",
                            "exercises": [
                                mc(
                                    "The bread",
                                    ["El pan", "La manzana", "El queso", "La sopa"],
                                    0,
                                ),
                                translate(
                                    "I want an apple",
                                    "quiero una manzana",
                                    ["pan", "el", "comes"],
                                ),
                                match(
                                    [
                                        ("el pan", "bread"),
                                        ("la manzana", "apple"),
                                        ("el queso", "cheese"),
                                    ]
                                ),
                                fill(
                                    "Una mesa ___ dos personas.",
                                    "para",
                                    ["para", "por", "con"],
                                    prompt="Complete the request",
                                ),
                                type_answer(
                                    "I am hungry", ["tengo hambre", "yo tengo hambre"]
                                ),
                            ],
                        },
                    ],
                },
                {
                    "title": "Family",
                    "description": "Talk about the people closest to you.",
                    "icon": "group",
                    "lessons": [
                        {
                            "title": "Parents",
                            "exercises": [
                                mc(
                                    "The mother",
                                    ["La madre", "El padre", "La hija", "El hijo"],
                                    0,
                                ),
                                translate(
                                    "My father is tall",
                                    "mi padre es alto",
                                    ["madre", "baja", "son"],
                                ),
                                match(
                                    [
                                        ("la madre", "mother"),
                                        ("el padre", "father"),
                                        ("los padres", "parents"),
                                    ]
                                ),
                                fill(
                                    "___ madre se llama Elena.",
                                    "Mi",
                                    ["Mi", "Tu", "Su"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("My family", ["mi familia"]),
                            ],
                        },
                        {
                            "title": "Brothers and sisters",
                            "exercises": [
                                mc(
                                    "The sister",
                                    ["La hermana", "El hermano", "La abuela", "El primo"],
                                    0,
                                ),
                                translate(
                                    "I have two brothers",
                                    "tengo dos hermanos",
                                    ["hermanas", "tres", "eres"],
                                ),
                                match(
                                    [
                                        ("el hermano", "brother"),
                                        ("la hermana", "sister"),
                                        ("el abuelo", "grandfather"),
                                    ]
                                ),
                                fill(
                                    "Mi hermana ___ estudiante.",
                                    "es",
                                    ["es", "está", "son"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("The grandmother", ["la abuela", "abuela"]),
                            ],
                        },
                    ],
                },
                {
                    "title": "Animals",
                    "description": "Pets and common animals.",
                    "icon": "pets",
                    "lessons": [
                        {
                            "title": "Pets",
                            "exercises": [
                                mc("The dog", ["El perro", "El gato", "El pájaro", "El pez"], 0),
                                translate(
                                    "The cat is small",
                                    "el gato es pequeño",
                                    ["grande", "perro", "la"],
                                ),
                                match(
                                    [
                                        ("el gato", "cat"),
                                        ("el perro", "dog"),
                                        ("el pez", "fish"),
                                    ]
                                ),
                                fill(
                                    "Mi ___ come mucho.",
                                    "perro",
                                    ["perro", "pan", "padre"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("A bird", ["un pájaro", "un pajaro", "pájaro"]),
                            ],
                        },
                        {
                            "title": "On the farm",
                            "exercises": [
                                mc(
                                    "The horse",
                                    ["El caballo", "La vaca", "El pollo", "El cerdo"],
                                    0,
                                ),
                                translate(
                                    "The cow drinks water",
                                    "la vaca bebe agua",
                                    ["come", "el", "leche"],
                                ),
                                match(
                                    [
                                        ("el caballo", "horse"),
                                        ("la vaca", "cow"),
                                        ("el pollo", "chicken"),
                                    ]
                                ),
                                fill(
                                    "El caballo ___ grande.",
                                    "es",
                                    ["es", "son", "está"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("The animals", ["los animales", "animales"]),
                            ],
                        },
                    ],
                },
            ],
        },
        # ==================================================================
        # UNIT 3 — Numbers and actions
        # ==================================================================
        {
            "title": "Numbers and actions",
            "description": "Count, use common verbs, and build real sentences.",
            "color_key": "purple",
            "skills": [
                {
                    "title": "Numbers",
                    "description": "Count from one to ten.",
                    "icon": "tag",
                    "lessons": [
                        {
                            "title": "One to five",
                            "exercises": [
                                mc("Three", ["Tres", "Dos", "Cuatro", "Cinco"], 0),
                                translate(
                                    "I have two dogs",
                                    "tengo dos perros",
                                    ["tres", "gatos", "eres"],
                                ),
                                match(
                                    [
                                        ("uno", "one"),
                                        ("dos", "two"),
                                        ("tres", "three"),
                                    ]
                                ),
                                fill(
                                    "Uno, dos, ___, cuatro.",
                                    "tres",
                                    ["tres", "cinco", "seis"],
                                    prompt="Complete the sequence",
                                ),
                                type_answer("Five", ["cinco"]),
                            ],
                        },
                        {
                            "title": "Six to ten",
                            "exercises": [
                                mc("Ten", ["Diez", "Nueve", "Ocho", "Siete"], 0),
                                translate(
                                    "There are eight books",
                                    "hay ocho libros",
                                    ["siete", "mesas", "es"],
                                ),
                                match(
                                    [
                                        ("seis", "six"),
                                        ("ocho", "eight"),
                                        ("diez", "ten"),
                                    ]
                                ),
                                fill(
                                    "Siete, ocho, ___, diez.",
                                    "nueve",
                                    ["nueve", "seis", "cuatro"],
                                    prompt="Complete the sequence",
                                ),
                                type_answer("Seven", ["siete"]),
                            ],
                        },
                    ],
                },
                {
                    "title": "Common verbs",
                    "description": "Eat, drink, speak, live, have.",
                    "icon": "bolt",
                    "lessons": [
                        {
                            "title": "Everyday actions",
                            "exercises": [
                                mc("To eat", ["Comer", "Beber", "Hablar", "Vivir"], 0),
                                translate(
                                    "We speak Spanish",
                                    "hablamos español",
                                    ["hablo", "inglés", "ellos"],
                                ),
                                match(
                                    [
                                        ("comer", "to eat"),
                                        ("beber", "to drink"),
                                        ("hablar", "to speak"),
                                    ]
                                ),
                                fill(
                                    "Nosotros ___ pan.",
                                    "comemos",
                                    ["comemos", "como", "comen"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("I live in Madrid", ["vivo en madrid"]),
                            ],
                        },
                        {
                            "title": "To have and to be",
                            "exercises": [
                                mc("I have", ["Tengo", "Tienes", "Tiene", "Tenemos"], 0),
                                translate(
                                    "She is my friend",
                                    "ella es mi amiga",
                                    ["él", "amigo", "está"],
                                ),
                                match(
                                    [
                                        ("tengo", "I have"),
                                        ("tienes", "you have"),
                                        ("tenemos", "we have"),
                                    ]
                                ),
                                fill(
                                    "Ellos ___ un gato.",
                                    "tienen",
                                    ["tienen", "tengo", "tienes"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("We are friends", ["somos amigos"]),
                            ],
                        },
                    ],
                },
                {
                    "title": "Simple sentences",
                    "description": "Put the words together.",
                    "icon": "menu_book",
                    "lessons": [
                        {
                            "title": "Everyday sentences",
                            "exercises": [
                                mc(
                                    "The boy eats bread",
                                    [
                                        "El niño come pan",
                                        "El niño bebe pan",
                                        "La niña come pan",
                                        "El niño come agua",
                                    ],
                                    0,
                                ),
                                translate(
                                    "The girl drinks milk",
                                    "la niña bebe leche",
                                    ["el", "come", "agua"],
                                ),
                                match(
                                    [
                                        ("el niño", "the boy"),
                                        ("la niña", "the girl"),
                                        ("la casa", "the house"),
                                    ]
                                ),
                                fill(
                                    "La niña ___ en casa.",
                                    "vive",
                                    ["vive", "vives", "vivo"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer("I eat an apple", ["como una manzana"]),
                            ],
                        },
                        {
                            "title": "Putting it together",
                            "exercises": [
                                mc(
                                    "My sister has a cat",
                                    [
                                        "Mi hermana tiene un gato",
                                        "Mi hermano tiene un gato",
                                        "Mi hermana come un gato",
                                        "Mi hermana tiene un perro",
                                    ],
                                    0,
                                ),
                                translate(
                                    "We drink water at home",
                                    "bebemos agua en casa",
                                    ["comemos", "leche", "la"],
                                ),
                                match(
                                    [
                                        ("en casa", "at home"),
                                        ("todos los días", "every day"),
                                        ("por la mañana", "in the morning"),
                                    ]
                                ),
                                fill(
                                    "Mi padre ___ café por la mañana.",
                                    "bebe",
                                    ["bebe", "bebo", "beben"],
                                    prompt="Complete the sentence",
                                ),
                                type_answer(
                                    "Good night, see you tomorrow",
                                    ["buenas noches, hasta mañana", "buenas noches hasta mañana"],
                                ),
                            ],
                        },
                    ],
                },
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# The default learner
#
# One deterministic user, looked up by username so re-seeding never creates a
# second one. Gems are a mocked display value per the assignment brief; hearts
# start full; XP and streak start at zero because this learner has not practised
# yet -- the app must be able to show a genuine "day one" state.
# --------------------------------------------------------------------------

DEFAULT_USER: dict[str, Any] = {
    "username": "learner",
    "display_name": "Alex Mercer",
    "avatar_url": "/learner-avatar.png",
    "stats": {
        "total_xp": 0,
        "gems": 540,
        "hearts": 5,
        "current_streak": 0,
        "longest_streak": 0,
        "daily_goal": 30,
        "daily_xp": 0,
    },
}


# --------------------------------------------------------------------------
# Achievements
#
# A small, fixed catalogue. Every entry is evaluable from data the application
# already stores -- see services/achievement_service.PREDICATES, where each key
# below has a matching one-line predicate. Nothing here needs a new column, and
# no achievement was written that the data cannot support.
#
# `key` is the natural key: the seed finds rows by it, and the evaluator
# dispatches on it, so the two stay in step across reseeds.
# --------------------------------------------------------------------------

ACHIEVEMENTS: list[dict[str, Any]] = [
    {
        "key": "FIRST_LESSON",
        "title": "First steps",
        "description": "Complete your first lesson",
        "icon": "star",
        "color_key": "green",
    },
    {
        "key": "PERFECT_LESSON",
        "title": "Flawless",
        "description": "Complete a lesson without a single mistake",
        "icon": "target",
        "color_key": "blue",
    },
    {
        "key": "FIRST_SKILL",
        "title": "Crowned",
        "description": "Earn your first crown by finishing every lesson in a skill",
        "icon": "crown",
        "color_key": "gold",
    },
    {
        "key": "XP_100",
        "title": "Century",
        "description": "Earn 100 XP in total",
        "icon": "bolt",
        "color_key": "gold",
    },
    {
        "key": "STREAK_3",
        "title": "On a roll",
        "description": "Reach a 3-day streak",
        "icon": "flame",
        "color_key": "orange",
    },
    {
        "key": "STREAK_7",
        "title": "Unstoppable",
        "description": "Reach a 7-day streak",
        "icon": "flame",
        "color_key": "purple",
    },
]
