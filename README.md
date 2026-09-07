# Duolingo Clone

A gamified language-learning web app — Duolingo's learning path, lesson player and
progression systems — built as a 24-hour full-stack assignment.

**Current status: Phase 8 complete — the app is feature-complete for the
assignment.** Learning path, lesson player, leaderboard and profile with
achievements all work; hearts regenerate over time so a learner is never
permanently stuck; and Phase 8 added pronunciation audio, dark mode, component
tests and a full accessibility, performance and security pass. See
[Current implementation status](#current-implementation-status).

---

## Technology stack

| Layer | Choice | Version |
|---|---|---|
| Frontend | Next.js (App Router) + React + TypeScript | 16.3.4 / 19.2.8 / 5.x |
| Styling | Tailwind CSS v4 (`@theme` tokens ported from the Stitch design system) | 4.x |
| Backend | Python + FastAPI | 3.13.2 / 0.121.2 |
| Server | Uvicorn | 0.42.0 |
| Config | pydantic-settings | 2.13.1 |
| Backend tests | pytest + FastAPI TestClient | 8.4.2 |
| Frontend tests | Node's built-in test runner (`node --test`) | — |
| Database | SQLite (stdlib `sqlite3` driver) | — |
| ORM | SQLAlchemy 2.0 (declarative, synchronous) | 2.0.52 |

---

## Repository structure

```
duolingo/
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI factory: CORS, router mount, 3 error handlers
│   │   ├── core/
│   │   │   ├── config.py         typed settings from environment (incl. DATABASE_URL)
│   │   │   └── errors.py         domain errors -> HTTP status, one response envelope
│   │   ├── db/
│   │   │   ├── base.py           DeclarativeBase
│   │   │   ├── session.py        engine, SessionLocal, get_db, FK pragma
│   │   │   ├── init_db.py        create_all
│   │   │   ├── seed_data.py      the course content and achievements, as plain data
│   │   │   └── seed.py           idempotent, transactional seeding
│   │   ├── models/
│   │   │   ├── content.py        Course, Unit, Skill, Lesson, Exercise
│   │   │   ├── user.py           User, UserStats
│   │   │   ├── progress.py       UserSkillProgress, LessonAttempt, LessonAttemptAnswer
│   │   │   └── achievement.py    Achievement, UserAchievement
│   │   ├── schemas/              API contracts (separate from the ORM models)
│   │   │   └── course.py  path.py  user.py  lesson.py  leaderboard.py  achievement.py
│   │   ├── repositories/         all SQL lives here; nothing commits
│   │   │   └── course_repo.py  user_repo.py  progress_repo.py  lesson_repo.py
│   │   │       attempt_repo.py  leaderboard_repo.py  achievement_repo.py
│   │   ├── services/             business rules
│   │   │   ├── grading.py            five pure answer validators
│   │   │   ├── gamification.py       pure XP / hearts / streak / crown rules
│   │   │   ├── presentation.py       decouples option order from the answer
│   │   │   ├── path_service.py       derived skill unlock state
│   │   │   ├── answer_service.py     answer submission (transaction owner)
│   │   │   ├── lesson_service.py     retrieval, start, completion (transaction owner)
│   │   │   ├── user_service.py       stats with lazy heart regeneration, profile
│   │   │   ├── achievement_service.py predicates, idempotent awarding
│   │   │   └── leaderboard_service.py ranking, ordered in SQL
│   │   └── api/v1/
│   │       ├── router.py         aggregates v1 routers
│   │       ├── deps.py           get_db, get_current_user
│   │       └── routes/           health.py courses.py users.py lessons.py leaderboard.py
│   ├── tests/                    199 tests
│   │   ├── conftest.py               isolated test database via dependency override
│   │   ├── test_health.py  test_database.py
│   │   ├── test_api_courses.py  test_api_path.py  test_api_users.py
│   │   ├── test_api_leaderboard.py
│   │   ├── test_grading.py           validator tests, no database
│   │   ├── test_gamification.py      pure rule tests
│   │   ├── test_hearts.py            regeneration rule as a specification
│   │   ├── test_api_lessons.py       lesson engine over HTTP
│   │   ├── test_answer_position.py   the answer must not leak by position
│   │   └── test_error_envelope.py    one error shape, no internals
│   ├── duolingo.db               SQLite file (gitignored, rebuilt by the seed)
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx            root layout, Nunito Sans, pre-hydration theme script
│   │   ├── page.tsx              redirects to /learn
│   │   ├── error.tsx             root error boundary
│   │   ├── globals.css           design tokens, three palettes, tactile base styles
│   │   ├── learn/page.tsx        the learning path (Server Component) + loading.tsx
│   │   ├── learn/lesson/[lessonId]/page.tsx   the lesson route
│   │   ├── leaderboard/page.tsx  + loading.tsx
│   │   └── profile/page.tsx      + loading.tsx
│   ├── components/
│   │   ├── shell/                AppShell, Sidebar, MobileBottomNav, StatsBar, ThemeToggle
│   │   ├── learning-path/        LearningPath, UnitBanner, SkillNode, rings, SkillCard
│   │   ├── leaderboard/          LeaderboardRow
│   │   ├── profile/              AchievementCard
│   │   └── lesson/               LessonPlayer, header, feedback, completion, SpeakButton
│   │       └── exercises/        the five exercise renderers
│   ├── lib/
│   │   ├── a11y/radioGroup.ts    the radio-group keyboard contract (pure)
│   │   ├── audio/speech.ts       the only code that touches speechSynthesis
│   │   ├── theme.ts              theme choice + the pre-hydration init script
│   │   ├── lesson/               narrowing, session reducer, pairing (all pure)
│   │   ├── learn/                path and profile presentation logic (pure)
│   │   └── api/
│   │       ├── client.ts         typed fetch wrapper (the only place fetch is called)
│   │       ├── types.ts          response types for every endpoint
│   │       └── health.ts courses.ts users.ts lessons.ts leaderboard.ts
│   ├── *.test.ts                 104 pure-logic tests (node --test)
│   ├── **/*.test.tsx             43 component tests (vitest + jsdom)
│   ├── vitest.config.ts  vitest.setup.ts
│   └── .env.example
│
├── docs/
│   ├── PHASE_0_AUDIT.md          repository + Stitch audit, architecture plan
│   └── CODEBASE_LEARNING.md      the master learning document
├── stitch/                       read-only reference designs
└── README.md
```

---

## Prerequisites

- **Node.js 20+** (developed on 23.7.0) and npm
- **Python 3.11+** (developed on 3.13.2)

---

## How to start the backend

```bash
cd backend

# first time only
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS / Linux

# create the database and seed the course (first time, and any time you want to reset)
.venv/Scripts/python.exe -m app.db.seed

# run
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Backend runs at **http://localhost:8000**. Interactive API docs: http://localhost:8000/docs

Optional: copy `.env.example` to `.env` to override the allowed CORS origins.

---

## Database

**Location:** `backend/duolingo.db` — a single SQLite file, gitignored, rebuilt
by the seed command.

**Setup and reset:**

```bash
cd backend
.venv/Scripts/python.exe -m app.db.seed     # creates tables + seeds content
```

The seed is **idempotent** — running it repeatedly inserts nothing new and never
destroys learner progress. To start completely fresh, delete the file first:

```bash
rm backend/duolingo.db && .venv/Scripts/python.exe -m app.db.seed
```

Expected output:

```
Seed complete.
            users: 1
       user_stats: 1
          courses: 1
            units: 3
           skills: 9
          lessons: 18
        exercises: 90
  user_skill_progress: 9
```

**`DATABASE_URL`.** Set in `app/core/config.py`, overridable by the environment
variable of the same name. The default is an *absolute* path computed from the
module's own location, so the same database is found whether you launch uvicorn
from `backend/` or pytest from the repository root — a relative URL would quietly
open two different files. Pointing at Postgres later is this one variable plus
Alembic; no model or query changes.

### Schema overview

Ten tables. Content on the left, per-user state on the right:

```
courses ──< units ──< skills ──< lessons ──< exercises
                        │           │
                        │           └──< lesson_attempts >── users
                        │                      │               │
                        │                      └──< lesson_attempt_answers
                        └──< user_skill_progress >─────────────┤
                                                               │
                                              user_stats ──────┘  (one row per user)
```

| Table | Holds |
|---|---|
| `courses` | The language pair — one course: English → Spanish |
| `units` | Themed groups of skills, ordered within the course |
| `skills` | The path nodes, ordered within a unit |
| `lessons` | One sitting; two per skill |
| `exercises` | One question; five per lesson, 90 total, all five types |
| `users` | The learner (no authentication — one seeded user) |
| `user_stats` | Current XP, hearts, streak, daily goal, gems — one row per user |
| `user_skill_progress` | Lessons completed and crowns, per user per skill |
| `lesson_attempts` | History of lesson sessions |
| `lesson_attempt_answers` | One row per submitted answer; `UNIQUE(attempt_id, exercise_id)` makes resubmission harmless |

**Locked / available / completed is not stored.** It is derived from skill
ordering plus `user_skill_progress.crowns`, so the two can never disagree. The
full rationale, the ER diagram, constraints and index choices are in
[`docs/CODEBASE_LEARNING.md` §6](docs/CODEBASE_LEARNING.md).

**Seeded content:** 1 course, 3 units, 9 skills, 18 lessons, 90 original beginner
exercises (18 of each of the five types), 1 learner starting at 0 XP with 5
hearts and a 30 XP daily goal.

## How to start the frontend

```bash
cd frontend

# first time only
npm install
cp .env.example .env.local

npm run dev
```

Frontend runs at **http://localhost:3000**.

Run both at once, in two terminals. The backend must be running: `/` redirects to
`/learn`, which loads the course from the API on the server, and shows an error
screen with a retry link if the API cannot be reached.

---

## How the frontend connects to the backend

The browser calls the API directly across origins:

Most screens fetch on the **server**, so the browser never makes the call:

```
Next.js server (localhost:3000)
  → app/learn/page.tsx                (Server Component)
  → lib/api/courses.ts → lib/api/client.ts
  → fetch GET http://localhost:8000/api/v1/courses/1/path
  → api_router → route → service → repository → SQLite
  → rendered HTML sent to the browser
```

The lesson player is the exception — it is interactive, so it runs in the
browser and calls the API across origins, which is what the CORS configuration
is for:

```
Browser (localhost:3000)
  → components/lesson/LessonPlayer.tsx  (Client Component)
  → lib/api/lessons.ts → lib/api/client.ts
  → fetch POST http://localhost:8000/api/v1/lessons/1/answer
  → FastAPI CORSMiddleware → api_router → grading → verdict
```

Three rules keep this maintainable:

1. **The base URL is configuration, not a literal.** `lib/api/client.ts` reads
   `NEXT_PUBLIC_API_URL`, so deploying to a different backend is an env-var change.
2. **Only `client.ts` calls `fetch`.** Every feature module goes through it, so
   headers, caching and error handling are defined once — and future auth would
   be added in exactly one place.
3. **Errors have one shape.** Every failure returns
   `{"error": {"code", "message"}}`, including FastAPI's own validation and
   404 responses, so `client.ts` has one thing to parse and can show the
   backend's own wording to the learner.

**Why CORS is needed locally:** the page is served from `localhost:3000` and the
API lives on `localhost:8000`. A different port means a different *origin*, so
the browser's same-origin policy blocks the frontend from reading the response
unless the API explicitly allows that origin. `CORSMiddleware` adds the
`Access-Control-Allow-Origin` header for the two configured development origins
only — not `*`, so this configuration does not quietly become a permissive
production one.

---

## API

All endpoints live under `/api/v1`. Interactive documentation, generated from the
Pydantic schemas, is at **http://localhost:8000/docs**.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness check |
| GET | `/api/v1/courses` | List available courses |
| GET | `/api/v1/courses/{course_id}/path` | Full learning path with the learner's progress and derived skill state |
| GET | `/api/v1/users/me` | Current learner's identity |
| GET | `/api/v1/users/me/stats` | XP, hearts, streak, daily goal, gems |
| GET | `/api/v1/lessons/{lesson_id}` | A lesson and its exercises — **never its answers** |
| POST | `/api/v1/lessons/{lesson_id}/start` | Open a session, returns `attempt_id` |
| POST | `/api/v1/lessons/{lesson_id}/answer` | Grade one answer |

### Examples

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok"}

curl http://localhost:8000/api/v1/courses
```
```json
{
  "courses": [
    {
      "id": 1,
      "title": "Spanish",
      "description": "Learn everyday Spanish from English, one short lesson at a time.",
      "source_language": "English",
      "target_language": "Spanish",
      "flag_emoji": "🇪🇸"
    }
  ]
}
```

```bash
curl http://localhost:8000/api/v1/users/me/stats
```
```json
{
  "total_xp": 0,
  "gems": 540,
  "hearts": 5,
  "max_hearts": 5,
  "current_streak": 0,
  "longest_streak": 0,
  "daily_goal": 30,
  "daily_xp": 0
}
```

```bash
curl http://localhost:8000/api/v1/courses/1/path
```
```jsonc
{
  "course_id": 1,
  "course_title": "Spanish",
  "source_language": "English",
  "target_language": "Spanish",
  "units": [
    {
      "id": 1,
      "title": "Greetings and basics",
      "description": "Say hello, introduce yourself, and be polite.",
      "order_index": 0,
      "color_key": "green",
      "skills": [
        {
          "id": 1,
          "title": "Greetings",
          "description": "Hello, goodbye and the times of day.",
          "order_index": 0,
          "icon": "waving_hand",
          "state": "AVAILABLE",     // derived, never stored
          "crowns": 0,
          "lessons_completed": 0,
          "total_lessons": 2,
          "xp_earned": 0,
          "lessons": [
            { "id": 1, "title": "Hello and goodbye", "order_index": 0,
              "xp_reward": 10, "completed": false }
            // ...
          ]
        }
        // ... two more skills, then two more units
      ]
    }
  ]
}
```

An unknown course id returns 404 rather than an empty path:

```bash
curl -i http://localhost:8000/api/v1/courses/999/path
# HTTP/1.1 404 Not Found
# {"error":{"code":"not_found","message":"Course 999 does not exist."}}
```

### Skill state

`state` is one of `LOCKED`, `AVAILABLE`, `COMPLETED`, and is **computed on every
request** — there is no state column anywhere in the database:

> A skill with `crowns >= 1` is `COMPLETED`. Otherwise the first skill of the
> course is `AVAILABLE`, and any later skill is `AVAILABLE` when the skill
> immediately before it (ordered globally by unit then skill) has `crowns >= 1`.
> Otherwise it is `LOCKED`.

The Stitch design also draws an "in progress" node; the frontend derives that
from `lessons_completed > 0` on an `AVAILABLE` skill. The API returns counts, not
a percentage — one representation, owned by one side.

### The lesson loop

```bash
# 1. Open a session. Returns attempt_id and the lesson (with no answers).
curl -X POST http://localhost:8000/api/v1/lessons/1/start

# 2. Answer each exercise. Payload shape depends on the exercise type.
curl -X POST http://localhost:8000/api/v1/lessons/1/answer \
  -H "Content-Type: application/json" \
  -d '{"attempt_id":1,"exercise_id":1,"answer":{"option_id":"o1"}}'
```
```json
{
  "correct": false,
  "correct_answer": "Hola",
  "xp_earned": 0,
  "hearts_remaining": 4,
  "already_answered": false,
  "answered_count": 1,
  "total_exercises": 5
}
```
```bash
# 3. Finish. The body carries only the attempt id — the server already knows
#    what was answered.
curl -X POST http://localhost:8000/api/v1/lessons/1/complete \
  -H "Content-Type: application/json" -d '{"attempt_id":1}'
```
```json
{
  "correct_answers": 4, "incorrect_answers": 1, "accuracy": 0.8,
  "xp_earned": 50, "first_completion": true,
  "total_xp": 50, "daily_xp": 50, "daily_goal": 30, "hearts_remaining": 4,
  "current_streak": 1, "longest_streak": 1, "streak_extended": true,
  "skill_id": 1, "lessons_completed": 1, "total_lessons": 2,
  "crowns": 0, "crown_earned": false
}
```

Answer payloads, by exercise type:

| Type | Payload |
|---|---|
| `MULTIPLE_CHOICE` | `{"option_id": "o2"}` |
| `TRANSLATE` | `{"tokens": ["buenos", "días"]}` |
| `MATCH_PAIRS` | `{"pairs": [["l1","r3"], ["l2","r1"]]}` |
| `FILL_BLANK` | `{"text": "Buenos"}` |
| `TYPE_ANSWER` | `{"text": "adiós"}` |

### Answers never leave the server

`GET /lessons/{id}` returns each exercise's learner-visible `data` but has **no
field at all** for the canonical answer — the response schema does not declare
one, so it cannot be serialised even by mistake. Correctness is decided entirely
server-side; a client that posts `{"correct": true}` is ignored. Two tests scan
lesson responses recursively for answer-shaped keys.

**The answer must not leak by position either.** The Phase 8 security review
found that although no field carried the answer, the seeded content was authored
answer-first — so the correct multiple-choice option was `options[0]` in 18 of 18
exercises. Always picking the first option scored 100%. Option lists are now
shuffled at the single point where an exercise becomes a response
(`services/presentation.py`), deterministically per exercise id so the order is
stable across requests but uncorrelated with the authored one. Shuffling is safe
because no validator grades by index: multiple choice compares an option *id*,
match-pairs compares a *set* of id pairs, and the text types normalise and
compare strings.

### Gamification rules

| Rule | Behaviour |
|---|---|
| **XP** | +10 per correct answer, + `lesson.xp_reward` (10) on completion. Recorded per answer, **credited once at completion**. A perfect 5-exercise lesson = 60 XP. |
| **Repeat XP** | Replaying a completed lesson awards **0** — practice is allowed, farming is not. |
| **Hearts** | Max 5. −1 per wrong answer, floored at 0. At 0, both `/answer` and `/start` return 409. |
| **Streak** | First activity → 1. Same day → unchanged. Next day → +1. Missed a day → back to 1. `longest_streak` only rises. UTC date basis. |
| **Daily XP** | Resets when the stored activity date is not today — no scheduled job. |
| **Crowns** | One per skill, awarded when every lesson in it is complete. The crown is what unlocks the next skill. |
| **Progress** | Recomputed from completed attempts, never incremented, so `0 <= lessons_completed <= total_lessons` holds by construction. |

Idempotency: resubmitting an answer returns **200 with `already_answered: true`**
and the original verdict — no second heart, no second XP, no second row. Backed
by `UNIQUE(attempt_id, exercise_id)`. Completing twice returns **409**.

Completion writes `lesson_attempts`, `user_stats` and `user_skill_progress` in
**one transaction**; any failure rolls back all of it.

---

## The app

Start both servers, then open **http://localhost:3000/learn**.

```
/learn                        the learning path, inside the application shell
  └── tap an available skill  → skill card naming the next lesson
        └── Start             → /learn/lesson/{id}
              └── finish      → back to /learn, updated
```

### Application shell

| Width | Navigation |
|---|---|
| ≥ 1024px | 256px fixed sidebar with the mascot and destinations |
| < 1024px | 64px bottom tab bar; sidebar hidden |

Both render from one shared list, so they cannot drift. **Learn** is the only
built destination; **Leaderboard**, **Profile** and **Shop** appear disabled and
marked "Soon" — showing the product's shape without pretending they work.

The header carries live streak, gems, hearts and XP from
`GET /users/me/stats`, plus a daily-goal bar. Nothing there is computed on the
client.

The shell is a **component**, not a `layout.tsx`: the lesson player is nested at
`/learn/lesson/[id]` and must stay chrome-free, so a layout would wrap it.

### Learning path

Rendered entirely from `GET /courses/{id}/path`. Unit banners, skill titles,
icons and colours all come from the seeded database — nothing is hardcoded.

**Skill states.** The server sends three; the UI draws four:

| Server `state` | Condition | Node |
|---|---|---|
| `LOCKED` | — | grey, disabled button, not clickable |
| `AVAILABLE` | no lessons done | blue, empty ring |
| `AVAILABLE` | some lessons done | green, partial ring |
| `COMPLETED` | — | gold, crown glyph, full ring |

"In progress" is **not** a backend state — it is `AVAILABLE` with
`lessons_completed > 0`, a presentation distinction only. The frontend contains
**no unlocking logic**: there is not one `crowns >= 1` comparison in React, and a
test feeds in a deliberately contradictory skill to prove the UI follows the
server's `state` rather than re-deriving it.

**Progress rings** use `lessons_completed / total_lessons` — the API sends
counts, the client renders the ratio, and no `progress_percentage` exists
anywhere in the system.

**Which lesson opens:** the first lesson where `completed === false`. If every
lesson is done, the last one is offered as practice — a real backend capability
(a repeat completion is accepted and awards 0 XP), labelled honestly rather than
dressed up as new content.

**After a lesson**, the player calls `router.refresh()` on the way back, so the
Server Component re-runs and the path shows the new XP, streak, crowns and
unlocks. No store, no cache library.

---

## Lesson player

The first real screen: **`/learn/lesson/[lessonId]`** — try
http://localhost:3000/learn/lesson/1 with both servers running.

**The user flow**

```
open  → POST /lessons/{id}/start        creates an attempt, returns the exercises
      → render exercise 1 of 5
      → learner answers, presses Check
      → POST /lessons/{id}/answer       server grades it
      → feedback bar: green or red, hearts updated from the response
      → Continue → next exercise … repeat
      → on the last exercise, Continue reads "Finish"
      → POST /lessons/{id}/complete     server settles XP, streak, progress, crowns
      → celebration screen
```

**The five exercise types**

| Type | Interaction |
|---|---|
| Multiple choice | Tap one of four extruded tiles |
| Translate | Build the sentence from a word bank; used words leave ghost placeholders so the bank never reflows |
| Match pairs | Tap a Spanish word then its meaning; numbered badges link the columns, and tapping again unlinks |
| Fill in the blank | Pick the word that completes the sentence, shown inline in the gap |
| Type the answer | Free text, autofocused, `Enter` submits |

**What the frontend does and does not decide.** It decides whether an answer is
*complete enough to submit* — nothing selected, empty input, unmatched pairs.
It never decides whether an answer is **correct**, how much **XP** was earned,
how many **hearts** remain, or whether the lesson is **complete**. Every one of
those is read from the API response. A client that posts `{"correct": true}` is
ignored, and the lesson response contains no answer field at all.

**Architecture.** `LessonPlayer` is the only lesson component that calls the API;
the five renderers receive a payload and report a draft answer upward. Session
state is a pure reducer in `lib/lesson/session.ts`, local to the route — no
store, no context. Exercise payloads are narrowed into a discriminated union at
the boundary, so renderers are precisely typed and the dispatch is
exhaustiveness-checked.

---

## Leaderboard, profile and achievements

**`/leaderboard`** ranks learners by **lifetime XP**, ordered by the database.
The current learner's row is flagged by the server and highlighted with a border,
a colour *and* a "YOU" badge. With one seeded learner it shows one learner and
says so — no fabricated opponents.

**`/profile`** shows identity, the daily goal, nine statistics and the
achievement grid. The lifetime aggregates (lessons done, crowns, perfect lessons,
skills complete) are **counted in SQL**, not totalled in the browser.

**Achievements** — six, each a one-line predicate over data the app already
stores:

| Achievement | Unlocks when |
|---|---|
| First steps | You complete your first lesson |
| Flawless | You complete a lesson with no mistakes |
| Crowned | You earn your first crown |
| Century | You reach 100 XP |
| On a roll / Unstoppable | You reach a 3- / 7-day streak |

They are evaluated **inside the lesson-completion transaction**, so an
achievement can never disagree with the lesson that earned it, and awards are
idempotent — enforced in code and by `UNIQUE(user_id, achievement_id)`.

---

## Hearts and how they come back

Max 5. A wrong answer costs one. **Hearts regenerate at one per 30 minutes**, so
reaching zero is a pause, not a dead end.

Regeneration is **lazy**: there is no scheduler, no cron and no background
worker. Hearts are a pure function of `hearts` and `hearts_updated_at`, computed
when state is read — which also means it is correct after the server has been off
for a week. It is applied by one service, used by the stats endpoint, the profile
and lesson start, so a learner who has waited out the interval can start a lesson
directly without visiting another screen first.

The timestamp advances by **whole intervals consumed**, leaving the remainder to
carry forward; setting it to "now" would silently discard partial progress.
Everything is UTC, matching the streak rule. Regeneration touches hearts only —
never XP, streak or crowns.

### Authentication

There is none, deliberately. Every request is attributed to the seeded learner,
resolved by a single dependency (`app/api/v1/deps.py:get_current_user`). That is
why the endpoints are `/users/me` rather than `/users/{id}`, and it is the one
function real authentication would replace.

---

## Audio, dark mode and accessibility

### Pronunciation audio

Tap the speaker next to a Spanish word, option or sentence and the browser reads
it aloud. No audio files, no speech provider, no API key, no backend endpoint —
`window.speechSynthesis` is a Web API every current browser ships.

Every call goes through one module, `frontend/lib/audio/speech.ts`, which owns
availability, language, rate, cancellation and failure. `speak()` cancels
anything already playing before it starts, so tapping a second speaker replaces
the first instead of queueing behind it. When speech is unavailable the control
is not rendered at all rather than rendered dead.

Speakers appear on multiple choice (each option), match pairs (the Spanish
column) and fill-blank (the sentence). Each one is a sibling of its answer
control, not a child, so keyboard navigation still works and the HTML stays
valid — and it never submits the answer.

### Dark mode

A Light / Dark / System control on `/profile`. The colours come from three CSS
palettes in `app/globals.css`; components did not change, because they were
already written against tokens (`bg-surface`, `text-text-secondary`) rather than
literal colours.

Brand colours are identical in both themes — green still means correct, red
still means wrong. What changes is the ground beneath them: surfaces, borders and
the feedback bar backgrounds.

The choice is stored in `localStorage` and applied as `data-theme` on `<html>` by
a small inline script that runs **before first paint and before React hydrates**.
That is what avoids both a flash of the wrong theme and a hydration mismatch:
React never renders the theme, so it cannot disagree with the server about it.
`System` removes the attribute entirely and lets `prefers-color-scheme` decide.

### Accessibility

Audited screen by screen in Phase 8 and fixed where it was wrong, not where it
was easy:

- Multiple-choice and fill-blank options claimed `role="radiogroup"` but did not
  implement it. They now support arrow keys (which move *and* select, wrapping),
  Home/End, Space, and a single roving tab stop for the whole group.
- `aria-label` on plain `<div>`s was being ignored by assistive technology; those
  containers now carry `role="group"`.
- The translate prompt was rendered twice — once as the heading, once in the
  mascot's bubble — so it was read out twice. Now once.
- The lesson loading screen announces itself (`role="status"`); the decorative
  pulse is hidden from assistive technology.
- The small speaker button went from 32px to 40px.
- `--text-secondary` was 4.48:1 on white; it is now 5.33:1. Feedback-bar text
  used the brand depth colours at 2.91:1 and 3.46:1 on the pale feedback grounds
  and now uses dedicated tokens at 6.21:1 and 6.19:1 (9.28:1 and 7.98:1 in dark).

Already in place and unchanged: one `<h1>` per screen with no skipped levels;
`<main>`, `<nav>`, `<header>` and `<aside>` landmarks; `aria-current` on the
active navigation item; labelled `role="progressbar"` with all three value
attributes; `role="status"` on the answer verdict; every state also stated in
words ("Locked", "Completed", "You", "Unlocked") so nothing depends on colour
alone; no positive `tabindex`.

**Known contrast limitation.** White text on the brand fills fails WCAG AA —
green 2.09:1, blue 2.44:1, red 3.30:1 (measured from the actual tokens). These
are the primary buttons and the reference design's colours; changing them enough
to pass would visibly change the product. The failure is recorded rather than
fixed, and rather than hidden.

---

## Responsive status

**Verified structurally. Not verified visually at a phone viewport.**

The layout is mobile-first Tailwind with two breakpoints. Every container is
`max-w-*` — there is no fixed pixel width anywhere in the app — so no screen can
overflow a 375px viewport horizontally. The desktop sidebar and the mobile bottom
tab bar are separate components, each hidden at the other's breakpoint. Answer
tiles are 56–64px tall and the smallest interactive control is 40px.

What has **not** been done: opening the app at 375×812, 390×844, 768×1024 or
1280×800 in a real browser and looking at it. The browser tooling available
during Phases 5–7 refused to shrink the viewport below 1089px, and during Phase 8
it was unavailable entirely. Dark mode and audio have likewise not been seen or
heard in a live browser — they are covered by component tests, by the built
stylesheet (all three palettes present), and by code review.

This is stated plainly because the alternative — claiming verification that did
not happen — is worse than the gap itself.

---

## Tests

```bash
cd backend  && .venv/Scripts/python.exe -m pytest       # 199 tests
cd frontend && npm test                                 # 104 pure-logic + 43 component tests
cd frontend && npm run test:unit                        # 104 pure-logic only (node --test)
cd frontend && npm run test:components                  # 43 component only (vitest)
cd frontend && npx tsc --noEmit && npm run lint          # types + lint
cd frontend && npm run build                             # production build
```

Three layers, deliberately:

| Layer | Tool | What it covers |
|---|---|---|
| Pure logic | `node --test` on `.ts` | Reducers, payload builders, the radio-group keyboard contract, the API client. No DOM. |
| Components | Vitest + jsdom + Testing Library on `.tsx` | What a learner sees and can do — which control appears, what a click reports, what a key press selects. |
| API | pytest + FastAPI `TestClient` | Status codes, shapes, ownership, idempotency, transactions, and the answer-leak guarantees. |

Every backend test builds a throwaway SQLite file in pytest's temp directory and
seeds it with the same `seed()` function the command uses. API tests inject that
database by overriding the `get_db` dependency, so **the suite never opens
`backend/duolingo.db`** and cannot destroy local progress.

---

## Current implementation status

**Implemented (Phase 8)**

- Pronunciation audio via `window.speechSynthesis`, behind one module, on
  multiple choice, match pairs and fill-blank
- Dark mode across every screen, with a Light / Dark / System toggle and no
  flash or hydration mismatch
- Component tests (Vitest + jsdom + Testing Library) — 43 of them
- Real radio-group keyboard navigation, `role="group"` fixes, contrast fixes
- Loading skeletons for `/leaderboard` and `/profile`; a root error boundary
- Security review found and fixed a **positional answer leak**: the correct
  option was `options[0]` in 18 of 18 multiple-choice exercises, so the answer
  was inferable without ever being sent. Ordering is now decoupled from the
  authored order at the single serialisation point
- One error envelope for every failure, including FastAPI's own; learners see
  the backend's domain message instead of "failed with status 409"
- Three sequential server fetches per screen made parallel
- 13 new backend tests, 13 new frontend unit tests, 43 component tests
- Three dev dependencies added; **zero runtime dependencies**

**Implemented (Phase 7)**

- `/leaderboard` ranked by lifetime XP, ordered in SQL, current learner flagged
- `/profile` with identity, nine statistics and the achievement grid
- Six achievements, evaluated transactionally and awarded idempotently
- Lazy heart regeneration (+1 / 30 min, capped at 5, UTC, no scheduler)
- Zero-heart recovery, applied on both stats read and lesson start
- Navigation: Leaderboard and Profile enabled; Shop still disabled
- 35 new backend tests, 14 new frontend tests

**Implemented (Phase 6)**

- `/learn` — the learning path, loaded server-side from the API
- Application shell: desktop sidebar + mobile bottom navigation, one shared list
- Live learner stats in the header and a daily-goal card
- Unit banners, skill nodes in four visual variants, progress rings, crowns
- Skill card naming the next lesson; launch into the lesson player
- Path refreshes on return so new XP, streak, crowns and unlocks appear
- Loading skeleton, error screen with retry, graceful empty states
- No unlocking or gamification logic anywhere in the frontend
- 27 new tests; no new dependencies; no backend changes

**Implemented (Phase 5)**

- Lesson player at `/learn/lesson/[lessonId]`, in the Stitch visual language
- All five exercise types rendered and playable
- Progress bar, live heart count, correct/incorrect feedback bar
- Celebration screen with XP, accuracy, streak and skill progress
- Out-of-hearts blocking state, loading and error states
- Discriminated-union exercise typing — no `any`, exhaustiveness-checked dispatch
- Pure session reducer; the client never computes correctness, XP or hearts
- 35 new frontend tests, no new dependencies

**Implemented (Phase 4)**

- Full backend lesson engine: retrieve, start, answer, complete
- Five server-side answer validators with a documented normalisation rule
- Canonical answers structurally unable to reach the client
- Answer idempotency via a service check plus `UNIQUE(attempt_id, exercise_id)`
- Attempt ownership and cross-lesson protection
- Hearts, XP, streak, daily-XP rollover, skill progress and crowns
- Transactional completion across three tables, with rollback proven by test
- Typed frontend API client for the lesson loop (no UI yet)
- 101 new backend tests, 6 new frontend tests

**Implemented (Phase 3)**

- Course listing API
- Learning path API with derived `LOCKED` / `AVAILABLE` / `COMPLETED` skill state
- User stats API
- Layered backend: route → service → repository → SQLAlchemy → SQLite
- Pydantic response schemas separate from the ORM models
- Demo current-user dependency (no authentication, by design)
- Domain errors mapped centrally to 404 / 503 with a consistent body shape
- Eager loading measured at 6 queries for the whole path, constant with content size
- Typed frontend API client functions for every endpoint (not yet used by any UI)
- 26 API tests, including the full skill-unlock sequence

**Implemented (Phase 2)**

- SQLite database with nine tables, foreign keys enforced, unique and CHECK
  constraints, and indexes on every lookup path
- SQLAlchemy 2.0 declarative models with relationships in both directions
- `DATABASE_URL` configuration with a safe absolute default
- Idempotent, transactional seed: `python -m app.db.seed`
- 90 original beginner exercises covering all five exercise types
- 20 database tests covering schema, seed counts, determinism, relationships and
  every constraint

**Implemented (Phase 1)**

- Next.js App Router frontend with TypeScript, building and linting clean
- FastAPI backend with a versioned `/api/v1` prefix and a health endpoint
- Environment-driven API base URL; typed API client with a typed error class
- CORS configured for local development, with tests covering allowed and
  rejected origins
- Stitch design tokens (colors with depth pairs, 12 semantic type sizes,
  layout measurements) as Tailwind v4 `@theme` tokens
- Tactile/extruded button and card base styles — the interaction language the
  real component library will inherit
- Minimal application shell proving the frontend↔backend connection

**Not implemented yet**

- **Shop** is a disabled placeholder; no purchases, no Super
- **Single course only.** `/learn` uses the first course the API returns
- **The path does not auto-scroll** to the learner's current position
- **The leaderboard is lifetime-only** — no weekly period, so early learners
  cannot catch established ones
- **Achievements are binary** — no "2 of 3 days" progress, since no progress is
  persisted for locked achievements
- **Achievements are evaluated at lesson completion**, so a purely time-based
  achievement would not fire until the next completion (none of the six behave
  that way today)
- **No authentication** — one seeded learner, by design
- **No live browser verification in Phase 8.** Mobile viewports were never
  smaller than 1089px in Phases 5–7, and the browser tooling was unavailable in
  Phase 8, so dark mode, audio and phone layout have not been seen or heard
  running. See [Responsive status](#responsive-status)
- **White on the brand fills fails WCAG AA** (green 2.09:1, blue 2.44:1, red
  3.30:1). Kept for design fidelity, measured and recorded rather than hidden
- **No migrations.** The schema is created with `create_all`, which creates
  missing tables but does not alter existing ones. A model change means deleting
  `backend/duolingo.db` and re-seeding; Alembic is the migration path

*(Heart regeneration and component-render tests were listed here through Phase 6
and Phase 7; both are implemented now — see Phase 7 and Phase 8 above.)*

---

## Roadmap

| Phase | Objective |
|---|---|
| 0 | Repository + Stitch audit, architecture plan — see `docs/PHASE_0_AUDIT.md` |
| 1 | Foundation: both apps running and connected |
| 2 | Database schema, SQLAlchemy models, seed content |
| 3 | Learning path + user stats API |
| 4 | Lesson engine API: start / answer / complete, answer grading |
| 5 | Lesson player UI: five exercise renderers, hearts, feedback, completion |
| 6 | Learning path screen + application shell |
| 7 | Leaderboard, profile, achievements, heart regeneration |
| **8** | **Audio, dark mode, component tests, accessibility / performance / security pass** ← current |

Not scheduled: authentication, multiple courses, the shop, legendary mode,
weekly leaderboard periods, migrations.

Full architecture, schema and API design: **`docs/PHASE_0_AUDIT.md`**.
File-by-file explanations: **`docs/CODEBASE_LEARNING.md`**.
