# Duolingo Clone

A gamified language-learning web app — Duolingo's learning path, lesson player and
progression systems — built as a 24-hour full-stack assignment.

**Current status: Phase 9.5 complete — the app is feature-complete for the
assignment.** It is multi-user: learners register, log in and keep their own
progress, and the leaderboard ranks real accounts. A new learner is now taken
through onboarding — choose a course, say how much Spanish you know, and either
start from scratch or take a **real adaptive placement test** built from the
seeded course, which decides where on the path you begin. Learning path, lesson
player, leaderboard and profile with achievements all work; hearts regenerate so
a learner is never permanently stuck; match pairs is graded a pair at a time; and
the app has pronunciation audio, dark mode, component tests and a completed
accessibility, performance and security pass. See
[Current implementation status](#current-implementation-status).

Existing accounts are unaffected: anyone who registered before onboarding existed
goes straight to `/learn`, exactly as before.

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
| Frontend tests | Node's built-in runner (`node --test`) for pure logic; Vitest + jsdom + Testing Library for components | — / 3.x |
| Database | SQLite (stdlib `sqlite3` driver) | — |
| ORM | SQLAlchemy 2.0 (declarative, synchronous) | 2.0.52 |
| Password hashing | bcrypt | 5.0.0 |

**Runtime dependencies, in full:** the frameworks above plus `bcrypt`. Sessions
use `secrets` and `hashlib`, audio uses the browser's `SpeechSynthesis`, dark mode
is CSS variables, and there is no state-management library on either side.

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
│   │   │   ├── seed.py           idempotent, transactional seeding
│   │   │   └── migrate.py        idempotent, non-destructive schema migrations
│   │   ├── models/
│   │   │   ├── content.py        Course, Unit, Skill, Lesson, Exercise
│   │   │   ├── user.py           User (email + password hash), UserStats, Session
│   │   │   ├── progress.py       UserSkillProgress, LessonAttempt, LessonAttemptAnswer,
│   │   │   │                     LessonAttemptPair
│   │   │   ├── achievement.py    Achievement, UserAchievement
│   │   │   ├── onboarding.py     UserOnboarding + ProficiencyLevel, StartingMode
│   │   │   └── placement.py      PlacementTest, PlacementAnswer
│   │   ├── schemas/              API contracts (separate from the ORM models)
│   │   │   └── course.py  path.py  user.py  lesson.py  leaderboard.py
│   │   │       achievement.py  auth.py  onboarding.py  placement.py
│   │   ├── repositories/         all SQL lives here; nothing commits
│   │   │   └── course_repo.py  user_repo.py  progress_repo.py  lesson_repo.py
│   │   │       attempt_repo.py  leaderboard_repo.py  achievement_repo.py
│   │   │       onboarding_repo.py  placement_repo.py
│   │   ├── services/             business rules
│   │   │   ├── auth_service.py       hashing, sessions, registration, login
│   │   │   ├── grading.py            five pure answer validators
│   │   │   ├── gamification.py       pure XP / hearts / streak / crown rules
│   │   │   ├── presentation.py       decouples option order from the answer
│   │   │   ├── path_service.py       derived skill unlock state
│   │   │   ├── answer_service.py     answer submission (transaction owner)
│   │   │   ├── lesson_service.py     retrieval, start, completion (transaction owner)
│   │   │   ├── user_service.py       stats with lazy heart regeneration, profile
│   │   │   ├── achievement_service.py predicates, idempotent awarding
│   │   │   ├── leaderboard_service.py ranking, ordered in SQL
│   │   │   ├── onboarding_service.py  the onboarding state machine
│   │   │   ├── placement_engine.py    the placement algorithm — pure, no database
│   │   │   └── placement_service.py   running a test (transaction owner)
│   │   └── api/v1/
│   │       ├── router.py         aggregates v1 routers
│   │       ├── deps.py           get_db, get_current_user
│   │       └── routes/           health.py auth.py courses.py users.py lessons.py
│   │                             leaderboard.py onboarding.py placement.py
│   ├── tests/                    344 tests
│   │   ├── conftest.py               isolated test database via dependency override
│   │   ├── test_health.py  test_database.py
│   │   ├── test_api_courses.py  test_api_path.py  test_api_users.py
│   │   ├── test_api_leaderboard.py
│   │   ├── test_grading.py           validator tests, no database
│   │   ├── test_gamification.py      pure rule tests
│   │   ├── test_hearts.py            regeneration rule as a specification
│   │   ├── test_api_lessons.py       lesson engine over HTTP
│   │   ├── test_answer_position.py   the answer must not leak by position
│   │   ├── test_error_envelope.py    one error shape, no internals
│   │   ├── test_auth.py              register, login, logout, sessions
│   │   ├── test_multi_user.py        two learners, one database, no leakage
│   │   ├── test_match_pairs.py       incremental grading and the heart rules
│   │   ├── test_placement_engine.py  the algorithm, with no database at all
│   │   ├── test_onboarding.py        the flow, persistence, and the bypass rule
│   │   └── test_placement.py         the test, and everything it must not do
│   ├── duolingo.db               SQLite file (gitignored, rebuilt by the seed)
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
│
├── frontend/
│   ├── proxy.ts                  cookie-presence redirect (Next 16 convention)
│   ├── app/
│   │   ├── layout.tsx            root layout, Nunito Sans, pre-hydration theme script
│   │   ├── page.tsx              redirects to /learn
│   │   ├── login/page.tsx        + register/page.tsx — public
│   │   ├── onboarding/           course/ proficiency/ start/ placement/
│   │   ├── error.tsx             root error boundary
│   │   ├── globals.css           design tokens, three palettes, tactile base styles
│   │   ├── learn/page.tsx        the learning path (Server Component) + loading.tsx
│   │   ├── learn/lesson/[lessonId]/page.tsx   the lesson route
│   │   ├── leaderboard/page.tsx  + loading.tsx
│   │   └── profile/page.tsx      + loading.tsx
│   ├── components/
│   │   ├── auth/                 AuthCard, AuthField, LoginForm, RegisterForm, LogoutButton
│   │   ├── shell/                AppShell, Sidebar, MobileBottomNav, StatsBar, ThemeToggle
│   │   ├── learning-path/        LearningPath, UnitBanner, SkillNode, rings, SkillCard
│   │   ├── leaderboard/          LeaderboardRow
│   │   ├── profile/              AchievementCard
│   │   ├── lesson/               LessonPlayer, header, feedback, completion, SpeakButton
│   │   │   └── exercises/        the five exercise renderers
│   │   └── onboarding/           OnboardingLayout, the three pickers, PlacementRunner,
│   │                             PlacementProgress, PlacementResultCard
│   ├── lib/
│   │   ├── a11y/radioGroup.ts    the radio-group keyboard contract (pure)
│   │   ├── audio/speech.ts       the only code that touches speechSynthesis
│   │   ├── theme.ts              theme choice + the pre-hydration init script
│   │   ├── lesson/               narrowing, session reducer, pairing (all pure)
│   │   ├── learn/                path and profile presentation logic (pure)
│   │   ├── onboarding/           steps + options (pure), and the server-side guard
│   │   └── api/
│   │       ├── client.ts         typed fetch wrapper (the only place fetch is called)
│   │       ├── server.ts         cookie forwarding for Server Components
│   │       ├── types.ts          response types for every endpoint
│   │       └── health.ts auth.ts courses.ts users.ts lessons.ts leaderboard.ts
│   │           onboarding.ts placement.ts
│   ├── *.test.ts                 126 pure-logic tests (node --test)
│   ├── **/*.test.tsx             97 component tests (vitest + jsdom)
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

**Upgrading a database created before Phase 9 or 9.5:**

```bash
cd backend
.venv/Scripts/python.exe -m app.db.migrate
```

`create_all` creates missing tables but never *alters* an existing one. Phase 9
added columns to `users`; Phase 9.5 added `placed_out_at` to
`user_skill_progress`. This script does the alters, and `create_all` handles the
new tables. It is **idempotent** (a second run changes nothing) and
**non-destructive** (it adds columns and backfills only blanks; it never drops,
rewrites or deletes a row), so your local practice progress survives — deleting
and re-seeding also works but throws that away.

**It deliberately does not backfill onboarding rows.** A learner with no
`user_onboarding` row is treated as having finished onboarding, because rows only
exist from Phase 9.5 onward — so their absence is a true statement rather than a
default. Backfilling would have invented a course choice and a proficiency nobody
made, and would have made correct behaviour for existing learners depend on
someone remembering to run this command.

There is deliberately **no migration framework**. Alembic is the right tool for a
schema that keeps moving and is the next step this project would take; it is more
machinery than one migration on a single-file local database warrants. The
limitation is real: this script has no down-migration, no version table and no
ordering guarantee if a second one ever appears — which is exactly the point at
which Alembic stops being over-engineering.

Expected output:

```
Seed complete.
            users: 1
       user_stats: 1
     achievements: 6
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

Seventeen tables. Content on the left, per-user state on the right:

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
| `users` | A learner: unique email, bcrypt password hash, unique display name |
| `sessions` | One logged-in browser. Stores the **SHA-256** of the token, never the token |
| `user_stats` | Current XP, hearts, streak, daily goal, gems — one row per user |
| `user_skill_progress` | Lessons completed and crowns, per user per skill |
| `lesson_attempts` | History of lesson sessions |
| `lesson_attempt_answers` | One row per submitted answer; `UNIQUE(attempt_id, exercise_id)` makes resubmission harmless |
| `lesson_attempt_pairs` | One row per match-pairs selection; `UNIQUE(attempt_id, exercise_id, left_id, right_id)` makes a retried pair cost no second heart |
| `achievements` / `user_achievements` | The catalogue, and who has unlocked what |
| `user_onboarding` | One row per learner: course, proficiency, starting point, placement result. **A missing row means onboarding is complete** — rows only exist from Phase 9.5 onward, so their absence identifies a learner who predates the feature |
| `placement_tests` | One sitting of the placement test, with its stored result |
| `placement_answers` | One graded placement answer; `UNIQUE(test_id, exercise_id)` stops a retry from feeding the adaptive walk twice |

**Locked / available / completed / placed-out is not stored.** It is derived from
skill ordering, `user_skill_progress.crowns` and `placed_out_at`, so the states
can never disagree with the progress they summarise. Note that `crowns` and
`placed_out_at` are kept as *separate* facts: a crown means the learner completed
every lesson in the skill, and being placed out means they never did. The
full rationale, the ER diagram, constraints and index choices are in
[`docs/CODEBASE_LEARNING.md` §6](docs/CODEBASE_LEARNING.md).

**Seeded content:** 1 course, 3 units, 9 skills, 18 lessons, 90 original beginner
exercises (18 of each of the five types), 6 achievements, and 1 learner starting
at 0 XP with 5 hearts and a 30 XP daily goal. **Course content is shared; progress
is per-learner** — which is why registering someone is a handful of INSERTs rather
than a copy of the course.

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

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | — | Liveness check |
| POST | `/api/v1/auth/register` | — | Create an account and start a session |
| POST | `/api/v1/auth/login` | — | Sign in |
| POST | `/api/v1/auth/logout` | — | Delete the session row and clear the cookie |
| GET | `/api/v1/auth/me` | session | The caller's identity, including their own email |
| GET | `/api/v1/onboarding` | session | Which onboarding step the learner is on, and their choices |
| POST | `/api/v1/onboarding/course` | session | Enrol in a course — the id is checked against the table |
| POST | `/api/v1/onboarding/proficiency` | session | Record the self-reported level |
| POST | `/api/v1/onboarding/start` | session | "Start from scratch" or "find my level" |
| POST | `/api/v1/placement/start` | session | Open **or resume** the placement test |
| POST | `/api/v1/placement/answer` | session | Grade one answer, return the next question |
| POST | `/api/v1/placement/complete` | session | Score the test, place the learner, finish onboarding |
| GET | `/api/v1/courses` | session | List available courses |
| GET | `/api/v1/courses/{course_id}/path` | session | Full learning path with the learner's progress and derived skill state |
| GET | `/api/v1/users/me` | session | Current learner's identity |
| GET | `/api/v1/users/me/stats` | session | XP, hearts, streak, daily goal, gems |
| GET | `/api/v1/users/me/profile` | session | Identity, stats and lifetime aggregates |
| GET | `/api/v1/users/me/achievements` | session | The catalogue with this learner's unlock state |
| GET | `/api/v1/leaderboard` | session | Standings by lifetime XP |
| GET | `/api/v1/lessons/{lesson_id}` | session | A lesson and its exercises — **never its answers** |
| POST | `/api/v1/lessons/{lesson_id}/start` | session | Open a session, returns `attempt_id` |
| POST | `/api/v1/lessons/{lesson_id}/answer` | session | Grade one answer |
| POST | `/api/v1/lessons/{lesson_id}/pair` | session | Grade one match-pairs selection |
| POST | `/api/v1/lessons/{lesson_id}/complete` | session | Settle XP, streak, crowns, achievements |

Everything marked "session" answers **401** without a valid session cookie. The
identity always comes from that cookie — no endpoint accepts a user id.

**No placement endpoint can award anything.** None of their response models
declares an XP, heart, streak or crown field — not set to zero, absent — and the
service never creates a lesson attempt, which is what every gamification rule in
the codebase is written against.

### Examples

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok"}

# Sign in, keeping the session cookie. Every later call passes it back.
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login   -H "Content-Type: application/json"   -d '{"email":"learner@example.com","password":"duolingo123"}'
# {"user":{"id":1,"username":"learner","email":"learner@example.com", ...}}

curl -b cookies.txt http://localhost:8000/api/v1/courses
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
curl -b cookies.txt http://localhost:8000/api/v1/users/me/stats
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
curl -b cookies.txt http://localhost:8000/api/v1/courses/1/path
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
curl -i -b cookies.txt http://localhost:8000/api/v1/courses/999/path
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
curl -b cookies.txt -X POST http://localhost:8000/api/v1/lessons/1/start

# 2. Answer each exercise. Payload shape depends on the exercise type.
curl -b cookies.txt -X POST http://localhost:8000/api/v1/lessons/1/answer \
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
curl -b cookies.txt -X POST http://localhost:8000/api/v1/lessons/1/complete \
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
| **Placed out** | A placement test can carry a learner past a skill. That unlocks the next one exactly as a crown does, and is **stored and displayed separately**, because the learner did not do the lessons. No XP, no crown, no completion. |
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
/register                     a brand-new learner
  └── /onboarding/course          choose Spanish (the rest say "Coming soon")
        └── /onboarding/proficiency   how much do you already know?
              └── /onboarding/start   start from scratch, or find my level
                    ├── scratch    → /learn, beginning at the first skill
                    └── placement  → /onboarding/placement → /learn, placed

/learn                        the learning path, inside the application shell
  └── tap an available skill  → skill card naming the next lesson
        └── Start             → /learn/lesson/{id}
              └── finish      → back to /learn, updated
```

Signing in as an existing learner — including the seeded one — goes straight to
`/learn`; onboarding is only ever shown to accounts created since it existed.

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

## Accounts and signing in

The app is multi-user. Learners register, log in, and keep their own progress —
XP, hearts, streak, crowns, achievements and skill unlocks are all per-account.

### Signing in as the seeded learner

The seed creates one learner, and since Phase 9 it is a **normal account** that
logs in through the same endpoint as anyone else. Its credentials come from
configuration, not from a literal in the code:

| Setting | Default |
|---|---|
| `DEMO_EMAIL` | `learner@example.com` |
| `DEMO_USER_PASSWORD` | `duolingo123` |

Set either in `backend/.env` to change them. **These are not a secret.** They
protect a local SQLite file containing practice Spanish, and the default exists so
a fresh clone can be logged into without ceremony. Any deployment reachable by
anyone else must set `DEMO_USER_PASSWORD` — or delete the account.

### Creating your own account

Visit `/register`. Registration signs you in immediately (no second login step)
and creates:

- a stats row — 0 XP, 5 hearts, 0 streak, 0 gems, 0 daily XP
- a zeroed progress row for every skill in the course

The first skill is then `AVAILABLE` and the rest `LOCKED`, from the same rule
that has governed the path since Phase 3. There is no special case for new users,
and no course content is copied — content is shared, progress is per-learner.

### How authentication works

| Piece | Choice | Why |
|---|---|---|
| Password storage | **bcrypt**, cost 12 | Adaptive and salted; a hash must be slow, which is exactly what general-purpose digests are not |
| Session | A **row** in `sessions`; opaque random token in the cookie, SHA-256 in the database | A JWT cannot be revoked, so logout would either do nothing server-side or need a revocation list — which is a session table with extra steps |
| Cookie | `HttpOnly`, `SameSite=Lax`, `Secure` (configurable), 14 days | HttpOnly is why the token never reaches JavaScript or `localStorage`; SameSite is the CSRF defence |
| Identity | `get_current_user`, from the cookie only | There is no field in any request in which a client could claim to be someone else |

Failed logins return the **same** 401 and the same message whether the email is
unknown or the password is wrong — otherwise the form becomes a way to discover
which addresses are registered. The server even verifies a throwaway hash on the
unknown-email path, so the two do not differ in timing either.

**Logging out deletes the server-side session row.** Clearing the cookie alone
would leave a working key behind.

**Route protection has two layers, and only one is a boundary.** `frontend/proxy.ts`
redirects to `/login` when the session cookie is *absent* — a cheap check that
avoids a flash of loading UI. **The API is the actual boundary:** every learner
endpoint resolves the session and answers 401, so a forged cookie gets past the
proxy and is refused where it counts.

### What this deliberately is not

Local authentication for a demo, not an identity system. There is no OAuth, no
email verification, no password reset, no roles, no login rate limiting, no
account deletion and no audit log. `Secure` is off for local http and **must** be
enabled for https.

---

## Onboarding a new learner

A new account no longer lands on the learning path. It goes through four steps:

```
register → choose a course → how much do you know? → where to start?
                                                          │
                                    ┌─────────────────────┴─────────────────────┐
                            start from scratch                          find my level
                                    │                                           │
                                  /learn                            placement test → /learn
```

**Existing learners never see any of this.** Onboarding rows are created by
registration and only exist from Phase 9.5 onward, so a learner with no row
demonstrably predates the feature and is treated as finished. That needs no
migration step and no backfill — it is true of the data itself, which is why it
holds even on a database `python -m app.db.migrate` was never run against.

**The server owns the sequence.** `GET /api/v1/onboarding` computes which step
you are on from which columns are still null, and every page asks before
rendering. So a refresh, the back button, a logout and login the next day, or a
bookmarked deep link all put you back on the right step — and typing
`/onboarding/placement` before choosing a course redirects you to the course
screen.

### Choosing a course

Spanish (English → Spanish) is the one real course and the only selectable one.
The other languages are shown as disabled **Coming soon** tiles.

They are not merely greyed out. **No fake courses were seeded to fill the grid**,
so those tiles have no id — and `POST /onboarding/course` validates the id against
the `courses` table and answers 404 for anything else. A hand-written request
naming French cannot succeed, because there is nothing to name.

### Proficiency

Five options, matching the design:

| Option | Stored as |
|---|---|
| I'm new to Spanish | `BEGINNER` |
| I know some common words | `COMMON_WORDS` |
| I can have basic conversations | `BASIC_CONVERSATION` |
| I can talk about various topics | `VARIOUS_TOPICS` |
| I can discuss most topics in detail | `ADVANCED` |

The same five values appear in the database, the Pydantic schema, the TypeScript
types and the tests. The sentence on the card is copy and will be rewritten; the
stored value has to keep meaning the same thing.

**It is recorded and deliberately not used by the placement test.** Replacing a
self-report with evidence is the only reason the test exists — if the claim seeded
the test, the result would be partly a function of the claim.

### Start from scratch

Completes onboarding and **awards nothing**: no XP, no crowns, no lesson attempt,
no change to any progress row. The first skill is already `AVAILABLE` from the
rule that has governed the path since Phase 3, and registration already created
the zeroed progress rows. There is genuinely nothing to do except record the
decision.

---

## The placement test

Eight questions, drawn from the **real seeded course**, adapting as you answer,
scored entirely by the backend.

### How it works

**Difficulty comes from course order.** Nothing in the content stores a
difficulty, and hand-labelling 90 exercises would be a guess dressed as data. A
language course is written easiest-first, so the nine skills in course order are
cut into five bands:

| Band | Skills |
|---|---|
| 1 | Greetings, Introductions |
| 2 | Basics, Food |
| 3 | Family, Animals |
| 4 | Numbers, Common verbs |
| 5 | Simple sentences |

**It adapts.**

```
start at level 3 (the middle)
correct   → one level harder  (capped at 5)
incorrect → one level easier  (floored at 1)
stop after 8 answers
```

One step at a time, because a single answer is weak evidence. Starting in the
middle finds a learner at either extreme in about the same number of questions.

**Four exercise types are used** — multiple choice, translate, fill in the blank
and type the answer. Match pairs is excluded: since Phase 9 it is graded a pair at
a time against a heart budget, and the placement test has no hearts.

**Scoring.** A level is passed if at least half its questions were right. Your
result is the highest level such that it *and every level below it that was
asked* were passed — the top of an unbroken run. That last clause is what stops
one lucky hard answer from placing a beginner at the end of the course.

A weighted score (harder questions count for more) is also shown, but it does
**not** decide the level: a single number cannot tell "five easy questions right"
from "one hard question right", and that difference is the whole point of a
placement test.

**Then you are placed** at the first skill of the band above the level you
passed.

- **Did badly?** You start at the first skill — the same place "start from
  scratch" would have put you. Nothing is lost.
- **Did brilliantly?** You start at the last skill, and still have to complete it.

### What placement never does

| | |
|---|---|
| Spend a heart | Never — verified with eight wrong answers in a row |
| Award XP | Never |
| Extend your streak | Never |
| Unlock an achievement | Never |
| Complete a lesson | Never |

This is **structural, not a rule someone has to remember.** Placement has its own
tables (`placement_tests`, `placement_answers`) and creates no `lesson_attempts`
row — and every gamification rule in the codebase is written against "there is an
attempt". `placement_service.py` never imports `gamification` and never opens
`user_stats`. There is no code path from a placement answer to a reward.

### How placement affects your path

The skills before your starting point are marked **placed out** — a purple
fast-forward node on the path, not a gold crown.

That distinction is deliberate and it is enforced by the schema. A crown means
"you completed every lesson in this skill"; a placed-out learner never did. So
placement writes a separate `placed_out_at` column and the path reports a fourth
state, `PLACED_OUT`, alongside `LOCKED`, `AVAILABLE` and `COMPLETED`. Both unlock
what follows; only one of them is a claim about what you did.

Placed-out skills stay **playable**. You can go back and study any of them
properly whenever you like, and doing so earns XP and crowns normally.

```
Greetings          PLACED_OUT   crowns 0   lessons 0/2   xp 0
Introductions      PLACED_OUT   crowns 0   lessons 0/2   xp 0
…
Simple sentences   AVAILABLE    crowns 0   lessons 0/2   xp 0
```

### Trying it from the command line

```bash
# after registering, choosing a course and a proficiency:
curl -b cookies.txt -X POST http://localhost:8000/api/v1/onboarding/start \
  -H "Content-Type: application/json" -d '{"mode":"PLACEMENT"}'

curl -b cookies.txt -X POST http://localhost:8000/api/v1/placement/start
# {"test_id":1,"total_questions":8,"answered_count":0,"finished":false,
#  "question":{"exercise":{...},"difficulty":3,"number":1}}

curl -b cookies.txt -X POST http://localhost:8000/api/v1/placement/answer \
  -H "Content-Type: application/json" \
  -d '{"test_id":1,"exercise_id":41,"answer":{"option_id":"o2"}}'
# the verdict, and the next question — at a difficulty the server chose

curl -b cookies.txt -X POST http://localhost:8000/api/v1/placement/complete \
  -H "Content-Type: application/json" -d '{"test_id":1}'
# {"level":5,"score":37,"max_score":37,"skill_title":"Simple sentences",
#  "skills_placed_out":8, ...}
```

Note what the requests do **not** contain: a user id, a difficulty, or a level.
The cookie says who you are; the server decides everything else.

All three endpoints are idempotent. `start` resumes an open test rather than
beginning a second one, `answer` replays the recorded verdict for a question you
already answered, and `complete` returns the stored result rather than re-scoring.

---

## Match pairs

Match pairs is graded **one pair at a time**, the moment you form it.

Tap a Spanish word, then its meaning:

- **Correct** → both tiles lock, the pair is numbered, and you move to the next
- **Wrong** → the tiles flash red and release so you can try again, and you lose
  one heart
- **All pairs matched** → the exercise completes and you continue

There is no Check button — pressing one after the last pair would be a step that
does nothing.

### The heart rules

| Situation | Cost |
|---|---|
| Correct pair | nothing |
| Wrong pair | 1 heart |
| The **same** wrong pair again | nothing — idempotent |
| A **different** wrong pair | 1 heart (a second genuine guess is a second mistake) |
| A malformed submission | nothing, and 422 — a client bug is not a wrong answer |

The finished exercise earns XP **only if no pair was ever wrong**, which is the
same rule the other four exercise types follow: right first time earns XP, a
mistake does not.

### The API

```bash
curl -b cookies.txt -X POST http://localhost:8000/api/v1/lessons/1/pair \
  -H "Content-Type: application/json" \
  -d '{"attempt_id":1,"exercise_id":3,"left_id":"l1","right_id":"r3"}'

# {"correct":true,"pair_completed":true,"matched_pairs":[["l1","r3"]],
#  "exercise_complete":false,"exercise_correct":false,"hearts_remaining":5,
#  "xp_earned":0,"already_answered":false,"answered_count":0,"total_exercises":5}
```

The smallest request that lets the server grade one pair. It does not say which
pairs are already matched (the server knows), does not claim the pair is right
(the server decides), and does not say who is asking (the cookie does).

`matched_pairs` is the server's **complete** list every time, not a delta, so a
client that dropped a response cannot end up showing different tiles than the
server believes in.

Storage is a pair-level table with
`UNIQUE(attempt_id, exercise_id, left_id, right_id)` — uniqueness on the
*submission*, because trying `l1 → r2` and then `l1 → r3` are two real attempts,
while the same pair twice must never cost two hearts. When the last pair lands,
the server writes the ordinary answer row, so lesson completion is unchanged.

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
during Phases 5–7 refused to shrink the viewport below 1089px, and it has been
unavailable entirely since Phase 8. Dark mode and audio have likewise not been
seen or heard in a live browser — they are covered by component tests, by the
built stylesheet (all three palettes present), and by code review.

**The Phase 9.5 screens are in the same position.** The four onboarding screens,
the placement player and the placed-out path nodes have been verified over HTTP
and against the server-rendered HTML — the mascot, the speech bubble, the
progress rail at 0/25/50%, the five proficiency cards inside a `role="radiogroup"`,
the seven disabled "coming soon" tiles with their accessible names, and the
"Placed out" node labels are all present in the markup — and by 35 component
tests that drive them with a real DOM. They have not been *looked at*.

This is stated plainly because the alternative — claiming verification that did
not happen — is worse than the gap itself.

---

## Tests

```bash
cd backend  && .venv/Scripts/python.exe -m pytest       # 344 tests
cd frontend && npm test                                 # 126 pure-logic + 97 component tests
cd frontend && npm run test:unit                        # 126 pure-logic only (node --test)
cd frontend && npm run test:components                  # 97 component only (vitest)
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

Since Phase 9 the suite also **logs in for real**, through `POST /auth/login`,
rather than stubbing out the current-user dependency. Every pre-existing test
therefore exercises the cookie and the session lookup as a side effect of testing
something else. `BCRYPT_ROUNDS` is lowered to 4 in `conftest.py` — a password hash
is *designed* to be slow, and paying that per test would buy no coverage; the cost
factor lives inside each hash string, so production hashes are unaffected.

The Phase 9.5 tests are worth knowing about for two reasons. The placement
algorithm is a **pure module**, so `test_placement_engine.py` runs 23 tests
against it in under a second with no database at all — including three that read
as arguments rather than checks: that the banding and its inverse cannot drift
apart, that one lucky hard answer cannot place a beginner at the end of the
course, and that the weighted score does not decide the level. And
`test_placement.py` spends most of its effort on what must **not** happen: no XP,
no hearts spent after eight wrong answers, no streak, no achievement — and then
`test_placement_creates_no_lesson_attempt`, which is the assertion that makes the
other four structural rather than incidental.

---

## Current implementation status

**Implemented (Phase 9.5)**

- Four-step onboarding for new learners: course, proficiency, starting point,
  and optionally a placement test
- Existing learners bypass it entirely — a missing onboarding row means complete,
  so no backfill was needed and the rule holds even unmigrated
- Course picker: one real selectable course, seven honestly disabled "Coming
  soon" tiles that have no id and make no request
- Five controlled proficiency values, consistent across database, API, frontend
  types and tests
- "Start from scratch" completes onboarding and awards nothing at all
- A real adaptive placement test: eight questions drawn from the seeded course,
  starting at the middle band and moving one level per verdict
- Backend-only scoring — the request body has no level field to ask with
- Placement spends no hearts, awards no XP, extends no streak, unlocks no
  achievement and creates no lesson attempt
- A fourth skill state, `PLACED_OUT`, so "placed beyond" stays distinguishable
  from "completed" all the way to the path node the learner sees
- Server-side onboarding guard on every onboarding page and on `/learn`
- 80 new backend tests, 17 new frontend unit tests, 35 new component tests
- **No new dependencies**, runtime or dev, on either side

**Implemented (Phase 9)**

- Local authentication: register, log in, log out, `GET /auth/me`
- Passwords hashed with bcrypt; never stored, logged or returned
- Server-side sessions — an opaque token in an HttpOnly cookie, its SHA-256 in
  the database, so logging out actually invalidates it
- `get_current_user` resolves the session cookie; `demo_username` is no longer
  the runtime identity mechanism
- Registration creates the user, stats and every skill-progress row in one
  transaction, and signs the learner in — no second login step
- `/login` and `/register` pages with per-field validation and accessible errors
- Multi-user isolation: XP, hearts, streak, progress and achievements are
  per-account, proved by a dedicated test suite
- The leaderboard ranks every real account and exposes no email addresses
- Match pairs graded one pair at a time, with a heart per distinct wrong pair and
  idempotent retries
- One idempotent, non-destructive migration for the new schema
- 65 new backend tests, 5 new frontend unit tests, 19 new component tests
- One runtime dependency added (`bcrypt`) — the first since Phase 1

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
- **Authentication is local, not production identity.** No OAuth, no email
  verification, no password reset, no roles, no login rate limiting, no account
  deletion, no audit log. Each is a deliberate scope decision — see
  [Accounts and signing in](#accounts-and-signing-in). If you fix one first, make
  it rate limiting
- **`SESSION_COOKIE_SECURE` is off** for local http and **must** be enabled on
  https, or the session cookie travels in the clear
- **The two apps share a cookie namespace**, because cookies are scoped by domain
  and ignore the port. Convenient locally; a deployment on separate hosts would
  need a same-origin proxy or credentialed CORS
- **Expired sessions are not swept in bulk** — a stale row stops authenticating
  immediately and is deleted when next touched
- **No live browser verification in Phases 8 or 9.** Mobile viewports were never
  smaller than 1089px in Phases 5–7, and the browser tooling has been unavailable
  since. Dark mode, audio, the auth screens and the match-pairs interaction have
  been verified over HTTP and against server-rendered HTML, but not seen running.
  See [Responsive status](#responsive-status)
- **White on the brand fills fails WCAG AA** (green 2.09:1, blue 2.44:1, red
  3.30:1). Kept for design fidelity, measured and recorded rather than hidden
- **No migration framework.** Phase 9 added one hand-written, idempotent script
  (`python -m app.db.migrate`); Phase 9.5 added a second step to the same script.
  There is no down-migration, no version table and no ordering guarantee. That
  second step is exactly the moment Alembic stops being over-engineering, and it
  is the next step
- **Placement questions are deterministic**, so the test is memorisable: two
  learners at the same level see the same question. Reproducible and explainable
  was worth more than unpredictable for a test taken once per account
- **Placement difficulty is inferred from course order**, which assumes the course
  is written easiest-first. True of this content; it breaks the moment a course
  has a hard optional unit early on, at which point a real `difficulty` column
  earns its place
- **The `/learn` onboarding redirect is a `<meta refresh>`, not a 307**, because
  that route streams a loading skeleton before the guard fires. Correct, one
  paint slower. The onboarding pages have no loading file and redirect cleanly

*(Heart regeneration, component-render tests and authentication were each listed
here in earlier phases; all three are implemented now — see Phases 7, 8 and 9
above.)*

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
| 8 | Audio, dark mode, component tests, accessibility / performance / security pass |
| 9 | Local authentication, multi-user isolation, incremental match pairs |
| **9.5** | **New-user onboarding and an adaptive placement test** ← current |

Not scheduled: multiple *real* courses (the picker labels the rest "coming soon"
rather than faking them), the shop, legendary mode, weekly leaderboard periods, a
migration framework, and the production-identity features Phase 9 deliberately
left out (password reset, email verification, rate limiting, roles).

Full architecture, schema and API design: **`docs/PHASE_0_AUDIT.md`**.
File-by-file explanations: **`docs/CODEBASE_LEARNING.md`**.
