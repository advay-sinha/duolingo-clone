# Duolingo Clone

A gamified language-learning web app — Duolingo's learning path, lesson player and
progression systems — built as a 24-hour full-stack assignment.

**Current status: Phase 1 (foundation) complete.** The frontend and backend run,
talk to each other, and carry the Stitch design tokens. None of the learning
features exist yet — see [Current implementation status](#current-implementation-status).

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
| Database | SQLite — **not yet implemented (Phase 2)** | — |

---

## Repository structure

```
duolingo/
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI factory: CORS, router mount
│   │   ├── core/config.py        typed settings from environment
│   │   └── api/v1/
│   │       ├── router.py         aggregates v1 routers
│   │       └── routes/health.py  GET /api/v1/health
│   ├── tests/test_health.py
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

# run
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Backend runs at **http://localhost:8000**. Interactive API docs: http://localhost:8000/docs

Optional: copy `.env.example` to `.env` to override the allowed CORS origins.

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
cd backend  && .venv/Scripts/python.exe -m pytest      # 4 tests: health + CORS
cd frontend && npm test                                # 4 tests: API client
cd frontend && npx tsc --noEmit && npm run lint         # types + lint
```

---

## Current implementation status

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

- Database, ORM models, migrations, seed data (Phase 2)
- Learning path / skill tree, units, skills, lessons (Phases 3, 6)
- Lesson player and the five exercise types (Phases 4, 7)
- XP, hearts, streaks, daily goal, gems (Phases 3, 4)
- Leaderboard, profile, achievements (Phase 8)
- Authentication — deliberately simplified to a default learner in a later phase
- The real component library and responsive shell (Phase 5)

---

## Roadmap

| Phase | Objective |
|---|---|
| 0 | Repository + Stitch audit, architecture plan — see `docs/PHASE_0_AUDIT.md` |
| **1** | **Foundation: both apps running and connected** ← current |
| 2 | Database schema, SQLAlchemy models, seed content |
| 3 | Learning path + user stats API |
| 4 | Lesson engine API: start / answer / complete, answer grading |
| 5 | Design system components + responsive app shell |
| 6 | Learning path screen |
| 7 | Lesson player with all five exercise types |
| 8 | Profile + leaderboard |
| 9 | Tests, documentation, polish |

Full architecture, schema and API design: **`docs/PHASE_0_AUDIT.md`**.
File-by-file explanations: **`docs/CODEBASE_LEARNING.md`**.
