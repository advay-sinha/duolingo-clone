# Duolingo Clone

A gamified language-learning web app — Duolingo's learning path, lesson player and
progression systems — built as a 24-hour full-stack assignment.

**Current status: Phase 2 (database) complete.** The frontend and backend run and
talk to each other, and a seeded SQLite database holds a full beginner course.
No API serves that content yet — see
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
│   │   ├── main.py               FastAPI factory: CORS, router mount
│   │   ├── core/config.py        typed settings from environment (incl. DATABASE_URL)
│   │   ├── db/
│   │   │   ├── base.py           DeclarativeBase
│   │   │   ├── session.py        engine, SessionLocal, get_db, FK pragma
│   │   │   ├── init_db.py        create_all
│   │   │   ├── seed_data.py      the course content, as plain data
│   │   │   └── seed.py           idempotent, transactional seeding
│   │   ├── models/
│   │   │   ├── content.py        Course, Unit, Skill, Lesson, Exercise
│   │   │   ├── user.py           User, UserStats
│   │   │   └── progress.py       UserSkillProgress, LessonAttempt
│   │   └── api/v1/
│   │       ├── router.py         aggregates v1 routers
│   │       └── routes/health.py  GET /api/v1/health
│   ├── tests/
│   │   ├── test_health.py        4 tests
│   │   └── test_database.py      20 tests
│   ├── duolingo.db               SQLite file (gitignored, rebuilt by the seed)
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx            root layout, Nunito Sans
│   │   ├── page.tsx              Phase 1 placeholder shell
│   │   └── globals.css           design tokens + tactile component base
│   ├── components/BackendStatus.tsx
│   ├── lib/api/
│   │   ├── client.ts             typed fetch wrapper (the only place fetch is called)
│   │   ├── health.ts             GET /health binding
│   │   └── client.test.ts
│   └── .env.example
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

Nine tables. Content on the left, per-user state on the right:

```
courses ──< units ──< skills ──< lessons ──< exercises
                        │           │
                        │           └──< lesson_attempts >── users
                        │                                      │
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

Run both at once, in two terminals. The backend must be running for the page's
connection indicator to show green.

---

## How the frontend connects to the backend

The browser calls the API directly across origins:

```
Browser (localhost:3000)
  → components/BackendStatus.tsx      (Client Component, useEffect)
  → lib/api/health.ts → lib/api/client.ts
  → fetch GET http://localhost:8000/api/v1/health
  → FastAPI CORSMiddleware → api_router → health route
  → { "status": "ok" }
  → React state → rendered indicator
```

Two rules keep this maintainable:

1. **The base URL is configuration, not a literal.** `lib/api/client.ts` reads
   `NEXT_PUBLIC_API_URL`, so deploying to a different backend is an env-var change.
2. **Only `client.ts` calls `fetch`.** Every feature module (`health.ts` today,
   `lessons.ts` later) goes through it, so headers, error shape and future auth
   are defined once.

**Why CORS is needed locally:** the page is served from `localhost:3000` and the
API lives on `localhost:8000`. A different port means a different *origin*, so
the browser's same-origin policy blocks the frontend from reading the response
unless the API explicitly allows that origin. `CORSMiddleware` adds the
`Access-Control-Allow-Origin` header for the two configured development origins
only — not `*`, so this configuration does not quietly become a permissive
production one.

---

## Health endpoint

```
GET /api/v1/health   →   200   { "status": "ok" }
```

```bash
curl http://localhost:8000/api/v1/health
```

---

## Tests

```bash
cd backend  && .venv/Scripts/python.exe -m pytest      # 24 tests: health/CORS + database
cd frontend && npm test                                # 4 tests: API client
cd frontend && npx tsc --noEmit && npm run lint         # types + lint
```

Database tests build a throwaway SQLite file per test and seed it with the same
`seed()` function the command uses, so they prove the seed works on an empty
database.

---

## Current implementation status

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

- **No learning-path API.** `GET /courses/{id}/path` does not exist (Phase 3)
- **No lesson API.** start / answer / complete do not exist (Phase 4)
- **No frontend database integration.** The frontend is still the Phase 1 shell
- XP, hearts, streak and unlock *rules* — the columns exist, the logic does not
  (Phases 3, 4)
- Lesson player and the five exercise renderers (Phase 7)
- Leaderboard, profile, achievements (Phase 8)
- The real component library and responsive shell (Phase 5)
- Authentication — deliberately simplified to a default learner
- Migrations: the schema is created with `create_all`, which creates missing
  tables but does not alter existing ones. A model change means deleting
  `backend/duolingo.db` and re-seeding. Alembic is the migration path.

---

## Roadmap

| Phase | Objective |
|---|---|
| 0 | Repository + Stitch audit, architecture plan — see `docs/PHASE_0_AUDIT.md` |
| 1 | Foundation: both apps running and connected |
| **2** | **Database schema, SQLAlchemy models, seed content** ← current |
| 3 | Learning path + user stats API |
| 4 | Lesson engine API: start / answer / complete, answer grading |
| 5 | Design system components + responsive app shell |
| 6 | Learning path screen |
| 7 | Lesson player with all five exercise types |
| 8 | Profile + leaderboard |
| 9 | Tests, documentation, polish |

Full architecture, schema and API design: **`docs/PHASE_0_AUDIT.md`**.
File-by-file explanations: **`docs/CODEBASE_LEARNING.md`**.
