# E-Panchayat AI — Backend

FastAPI service for the Loni Kalbhor Gram Panchayat decision support system.
Owns the database, authentication, role-based access, the scheme eligibility
engine, grievance classification, Gram Sabha transcript processing and the
analytics the dashboards read.

---

## Why this exists

Before this service, the React app kept its data in browser `localStorage` and
wrote to Supabase on a best-effort basis. Four of the five tables rejected
every write because the schema and the TypeScript models described different
data, and the failures were swallowed into `console.warn`. There was no
authentication — the officer password was compared in client-side JavaScript,
and typing any citizen ID at the login screen opened that resident's file.

This service makes the database the source of truth, enforces access rules
server-side where they cannot be bypassed, and fails loudly when something
does not work.

---

## Setup

**1. Create a virtual environment and install dependencies**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

**2. Configure the environment**

```bash
copy .env.example .env          # Windows
cp .env.example .env            # macOS / Linux
```

Fill in `.env`:

- `DATABASE_URL` — from Supabase, **Project Settings → Database → Connection
  string → Session pooler**. Change the prefix from `postgresql://` to
  `postgresql+psycopg://` and keep `?sslmode=require`.
- `SECRET_KEY` — generate one:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `GEMINI_API_KEY` — optional. Without it the API still runs; the assistant and
  transcript endpoints return a clear 503 explaining what is missing, rather
  than pretending to work.

**3. Create the tables**

```bash
alembic upgrade head
```

**4. Load the demo village**

```bash
python -m app.seed
```

This inserts 10 citizens across 5 households, 6 schemes, 5 grievances,
4 projects, 1 Gram Sabha meeting with action items, 5 map facilities, and one
login per citizen plus an officer and an admin account.

**5. Run it**

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive API documentation: <http://localhost:8000/docs>. Every endpoint is
listed there with its request shape and role requirement, which is a useful
thing to have open during a demo.

---

## Demo accounts

Password for all of them is whatever `SEED_DEFAULT_PASSWORD` is set to
(`Panchayat@2026` by default — change it before deploying anywhere).

| Account | Role | Sees |
| --- | --- | --- |
| `admin@panchayat.gov.in` | admin | Everything, plus user management |
| `officer@panchayat.gov.in` | officer | All village records and analytics |
| `anandrao@citizen.panchayat.gov.in` | citizen | Only Anandrao Patil's own file |
| `savita@citizen.panchayat.gov.in` | citizen | Only Savita Patil's own file |

One citizen account exists per seeded resident, named after their first name.

---

## Layout

```
backend/
├── alembic/              Database migrations
├── app/
│   ├── api/routes/       One module per domain
│   ├── core/             Settings, JWT and password hashing, RBAC guards
│   ├── db/               Engine, session, declarative base
│   ├── services/         Eligibility rules, classifier, LLM client, transcripts
│   ├── models.py         SQLAlchemy models — the single source of truth
│   ├── schemas.py        Pydantic request/response models (camelCase output)
│   ├── seed.py           Demo data loader
│   └── main.py           Application entry point
└── tests/                pytest suite
```

`app/models.py` is the file to read first. It replaces `supabase_schema.sql`,
which should be deleted once the migration has run — keeping both is how the
schema drifted from the code in the first place.

---

## Access control

Roles are checked in `app/core/deps.py` and applied per route:

- **Officer / admin** — full read and write across village records, analytics,
  document verification and Gram Sabha processing.
- **Citizen** — reads only their own citizen record, their own documents, their
  own grievances and their own eligibility. Can file a grievance and upload a
  document. Cannot resolve anything or see anyone else.
- **Unauthenticated** — nothing. Every route depends on a guard.

A route without one of these dependencies is public, and there is no other way
in, so that is the list to check when reviewing security.

---

## Eligibility rules are data, not code

Each scheme carries a `criteria` dictionary that the engine in
`app/services/eligibility.py` evaluates:

```json
{"min_age": 60, "max_income": 100000, "gender": "Female",
 "occupation_any": ["farmer", "शेतकरी"]}
```

Supported keys: `min_age`, `max_age`, `min_income`, `max_income`, `gender`,
`ward_in`, `occupation_any`, `occupation_none`, `is_head`.

Adding a scheme is an insert, not a code change. The previous version keyed its
rules on scheme id in a chain of `if` statements, so any scheme the chain did
not recognise silently fell through to a bare income test.

Every result carries a generated explanation in English and Marathi, built from
the same facts the engine used. There is no LLM in this path — a welfare
decision has to be reproducible and auditable.

---

## Tests

```bash
pytest
```

36 tests run against a throwaway SQLite database seeded from the same data as
the demo. The access-control tests are the ones worth reading: they pin the
behaviour the previous build got wrong.

---

## API summary

All routes are prefixed `/api/v1`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/change-password`, `GET POST /auth/users` |
| Citizens | `GET POST /citizens`, `GET PATCH DELETE /citizens/{id}`, `GET /families` |
| Schemes | `GET POST /schemes`, `PATCH /schemes/{id}`, `GET /schemes/feed`, `POST /schemes/{id}/decision` |
| Eligibility | `GET /schemes/{id}/eligibility`, `GET /citizens/{id}/eligibility` |
| Grievances | `GET POST /grievances`, `GET PATCH /grievances/{id}`, `POST /grievances/classify` |
| Projects | `GET POST /projects`, `GET PATCH DELETE /projects/{id}` |
| Documents | `GET POST /documents`, `POST /documents/{id}/review` |
| Gram Sabha | `GET POST /sabha/meetings`, `POST /sabha/meetings/process`, `GET PATCH /sabha/action-items` |
| Analytics | `GET /analytics/dashboard`, `/age-distribution`, `/grievances-by-department`, `/grievances-by-ward`, `/project-budgets`, `GET /facilities` |
| Meta | `GET /health` |

Responses are camelCase (`nameMr`, `submittedDate`) so the React components
keep the field names they already use.
