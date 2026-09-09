# E-Panchayat

An AI-assisted decision support system for Gram Panchayat administration.
Citizen records, welfare schemes and eligibility, grievances, development
projects, Gram Sabha minutes, GIS and analytics — for 23 villages of Haveli
block, Pune district, Maharashtra.

Sem-7 capstone, Group BCC28, MIT School of Computing, MIT-ADT University Pune.
Guide: Prof. Jyoti Gavhane.

> **All resident data in this system is synthetic.** The villages, LGD codes and
> welfare schemes are real and cited; the ten residents, their incomes, families
> and documents are invented for demonstration. No real citizen record has ever
> been loaded, and none should be.

---

## What it does

**Multi-village and permission-scoped.** A real state → district → block →
village hierarchy with official LGD codes. An officer sees one Gram Panchayat;
an admin sees the block and the district rollup; a citizen sees their own file
and nothing else. Every list endpoint is scoped server-side, and a set of tests
exists specifically to prove one village's officer cannot read another's.

**Eligibility as data, not code.** Each of the 29 seeded schemes carries its
rules in a `criteria` dictionary — age bands, income ceilings, social category,
BPL and ration-card gates, land holdings, and `any_of` groups for schemes with
alternative qualifying routes. Adding a scheme is an insert. The engine returns
one of four verdicts (Eligible, Missing Documents, Needs Review, Ineligible) and
says which rule produced it. Where a rule needs a document the record cannot
settle, it says so rather than guessing.

**Retrieval-augmented assistant.** Questions are answered from the Panchayat's
own records: semantic search over an embedded index, then a walk across the
links between records, then generation constrained to what was retrieved. Scoped
by the asker's permissions — the retrieval layer cannot surface what the API
would refuse. With no API key it still answers from the same records in plainer
language rather than inventing.

**The model may see the village, never the villager.** Questions about the
Panchayat — projects, budgets, schemes, meetings, the grievance queue — are
answered by the model. Questions that turn on one resident's own record are
answered from the database directly, with no external call at all, because the
facts involved are that person's income, social category, BPL status,
disability assessment and documents. No resident is in the embedded index
either, so nothing about one is sent away even when nobody is asking. See
[Privacy](#privacy-what-leaves-this-server) below.

**Document readers.** Upload Gram Sabha minutes and get the decisions and action
items extracted from the file's actual text. Upload a Government Resolution and
get a proposed scheme with machine-readable eligibility rules — saved as
*pending*, reaching no resident until an officer approves it.

**Resident sign-up with verification.** A resident applies for an account; an
officer matches them against the village register from a ranked candidate list
and approves. Applying never creates a working login. Officer and admin accounts
are created by an admin, never self-registered.

---

## Honest capability statement

For the report and the viva. Every line here survives being clicked on.

| Feature | What it actually is |
|---|---|
| Assistant | Retrieval-augmented generation. Semantic retrieval over embedded records plus graph expansion across record links; generation by Gemini 2.5 Flash constrained to retrieved facts. Falls back to keyword routing when unindexed, and to a template — no model call — for anything about an individual resident. |
| Eligibility engine | A deterministic rule engine over data-driven criteria. No model involved. |
| Grievance classification | A transparent rule-based classifier over bilingual keyword sets. **Not** a trained model. |
| Transcript reader | Real text extraction plus an LLM call with a response schema. |
| Scheme reader | Same, with a closed criteria vocabulary and a mandatory human approval gate. |
| Vector storage | Embeddings stored as JSON, cosine similarity computed in Python. Correct at village scale (67 chunks — villages, schemes, projects, facilities, grievances and meetings, no residents); see `KnowledgeChunk` in `app/models.py` for what changes at district scale. |

Things this system does **not** have, stated plainly: no trained or fine-tuned
model of our own, no OCR for scanned documents, no Aadhaar or DigiLocker
integration, no SMS or payment gateway, and only two languages.

---

## Running it locally

Requires Python 3.11+, Node 20+, and a Postgres database (Supabase works).

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
cp .env.example .env            # then fill it in — see below
alembic upgrade head
python -m app.seed --reset
python -m app.index             # builds the semantic index; needs GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>

### Frontend

```bash
npm install
npm run dev
```

<http://localhost:5173>

### Configuration

Everything lives in `backend/.env`, which is gitignored and must stay that way.

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Supabase session pooler string, prefix changed to `postgresql+psycopg://`, `sslmode=require` kept |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` — never the example value |
| `GEMINI_API_KEY` | Server-side only. **Never** prefix with `VITE_` — that compiles it into the browser bundle |
| `CORS_ORIGINS` | Exact frontend origin, comma-separated, no trailing slash |
| `SEED_DEFAULT_PASSWORD` | Password given to every demo account |

### Demo accounts

All use the password in `SEED_DEFAULT_PASSWORD` (`Panchayat@2026` by default).

| Account | Role | Sees |
|---|---|---|
| `admin@panchayat.gov.in` | admin | Every village in Haveli block, plus the district rollup |
| `officer@panchayat.gov.in` | officer | Loni Kalbhor only |
| `officer.theur@panchayat.gov.in` | officer | Theur only — exists to demonstrate isolation |
| `savita@citizen.panchayat.gov.in` | citizen | Her own record, documents, grievances and eligibility |

Any seeded resident signs in as `<firstname>@citizen.panchayat.gov.in`. Two
residents — Sunita Jadhav and Sunil Ghadge — deliberately have **no** account,
so the sign-up and officer-approval flow can be demonstrated end to end.

### Tests

```bash
cd backend && python -m pytest        # 186 tests
npm run build                          # typecheck + production build
```

---

## Deployment

Two services on Render, defined by `render.yaml`, plus the Supabase database
where it already lives.

Everything is deployed from this repository rather than configured by hand in a
dashboard, so the infrastructure is reviewable, versioned, and rebuildable after
an accident.

### 1. Database

Nothing to move. The existing Supabase project is production.

> Supabase pauses free projects after about 7 days of low activity, and a paused
> project must be resumed by hand from the dashboard. The GitHub Action in step 4
> prevents that.

### 2. Both services on Render

1. Push this repository to GitHub.
2. Render dashboard → **New → Blueprint** → select the repository. It reads
   `render.yaml` and creates two services: `epanchayat-api` and `epanchayat-web`.
3. Render prompts for the secrets. Fill in `DATABASE_URL`, `SECRET_KEY` and
   `GEMINI_API_KEY`. For the two URL settings you do not have the values yet —
   put anything for now and fix them in step 3.
4. Let both deploy. Note the two URLs Render assigns.

Migrations run automatically when the API container starts. The seed and the
search index do not — run them once from the API service's **Shell** tab:

```bash
python -m app.seed --reset
python -m app.index
```

### 3. Point the two services at each other

This is the step that goes wrong, so do it deliberately.

| Service | Setting | Value |
|---|---|---|
| `epanchayat-web` | `VITE_API_URL` | `https://epanchayat-api.onrender.com/api/v1` |
| `epanchayat-api` | `CORS_ORIGINS` | `https://epanchayat-web.onrender.com` |

Use your own URLs, exactly as Render shows them — scheme and host, no trailing
slash. Then redeploy both.

`VITE_API_URL` is read at build time and compiled into the JavaScript, so
changing it needs a **rebuild**, not a restart.

If you skip the `CORS_ORIGINS` half, the site loads, every request fails, the
browser console shows a CORS error, and the API log shows nothing at all —
because the browser blocked the request before it was ever sent.

### 4. Keep it awake

`.github/workflows/keepalive.yml` pings the API every six hours, which stops
Supabase pausing and Render sleeping. Add one repository secret:

**Settings → Secrets and variables → Actions → New repository secret**
Name `API_URL`, value `https://epanchayat-api.onrender.com`

Run it once by hand from the Actions tab to confirm it works.

### Known limitation: the API sleeps

A free Render **web service** spins down after 15 minutes of inactivity, and the
next request waits roughly a minute while the container boots. The static site
does not sleep — only the API.

Nothing free solves this. Fly.io withdrew its free tier in October 2024, and
every comparable platform now wants a card. The options are:

- **Mitigate** — the keep-alive job above, plus opening the site yourself a few
  minutes before presenting. GitHub's scheduler runs cron jobs late under load,
  so do not rely on it alone for a timed demo.
- **Pay** — Render's cheapest paid instance removes spin-down for a few dollars a
  month. Worth it for the month around a demo; cancel afterwards.

### Before the demo

- Open the site five minutes early and click one page, so the API is warm.
- Check the Actions tab — a failing keepalive run means the database paused.
- Use one machine. A single free Gemini key is rate-limited, and four people
  demoing at once will hit it.

## Architecture

```
React 19 + TypeScript + Vite + Tailwind 4      Render (static site)
        │  fetch, JWT in Authorization header
        ▼
FastAPI + SQLAlchemy 2.0 + Alembic              Render (Docker web service)
        │                    │
        │                    └── Gemini API — generation and embeddings
        ▼
PostgreSQL                                       Supabase
```

Backend layout:

```
backend/app/
  api/routes/     endpoints, one module per resource
  core/           config, security, dependency guards (RBAC, village scoping)
  services/
    eligibility.py    the rule engine
    retrieval.py      question → records
    graph.py          semantic search and graph expansion
    indexer.py        records → embeddable linked chunks
    scheme_reader.py  Government Resolution → proposed scheme
    transcript.py     minutes → decisions and action items
    classifier.py     grievance → category, priority, department
    llm.py            the only place that talks to Gemini
```

Frontend state is deliberately plain: a typed client (`src/lib/api.ts`), two
hooks (`useQuery`, `useMutation`), and an auth context. No Redux, no React Query
— the app is a few dozen screens over one API and did not need them.

---

## Security notes

- Passwords are bcrypt-hashed. Authentication is JWT access + refresh.
- Every role check runs server-side as a FastAPI dependency. The frontend hides
  buttons; the server is what refuses.
- Village scoping is a WHERE clause on every list endpoint, and semantic search
  scopes its candidate set *before* ranking, so a similar vector is never a
  route around permissions.
- Self-registration cannot assign a role and does not create a usable login.
- `POST /auth/register` returns an identical response whether or not the email
  exists, so it cannot be used to discover who holds an account.
- The Gemini key is server-side only.

### Sign-in throttling

`/auth/login` is metered, because otherwise it is an unlimited password oracle:
slow per guess, but free to repeat. Five wrong guesses against one address, or
twenty from one source, and further attempts get a `429` for the rest of a
fifteen-minute window. The thresholds are settings, not constants.

The count lives in the `auth_attempts` table rather than in the process. That is
specific to this deployment: the API sleeps after fifteen minutes of inactivity,
so an in-memory counter would be cleared by every cold start — the throttle
could be reset by waiting rather than defeated, and the sleep window is about
the length of the lockout.

Three details that are easy to get wrong, and are tested:

- **A refusal does not extend the lockout.** Only a genuinely wrong guess counts,
  so a throttled retry cannot renew the window. Otherwise a lockout would never
  expire — for the honest user as much as the attacker.
- **Unknown addresses are throttled identically to real ones.** Metering only
  real accounts would make the throttle answer the question the login response
  carefully refuses: whether an address is registered.
- **An applicant checking a pending application is not throttled.** They prove
  their password every time, so it is not a guess.

The honest cost: someone who knows an officer's address can spend five
deliberate failures to lock it for fifteen minutes. That is the accepted trade
against leaving the oracle open, and the short window is what makes it bearable.
A production deployment would add a CAPTCHA or an out-of-band unlock rather than
raise the numbers.

`auth_attempts` also doubles as the authentication audit trail — it records
successes, not only failures, so it can answer "who signed in" as well as "who
has been trying". It pairs an email with an IP, which is personal data, so
`services.ratelimit.prune()` drops anything older than ninety days. Nothing
calls it automatically; there is no scheduler here, and claiming an enforced
retention policy that nothing enforces would be worse than running it by hand.

### Password reset, over the counter

There is no email or SMS gateway in this deployment, so "we have sent you a
link" is not available — and a reset flow whose message silently never arrives
is worse than none. This uses the channel a Gram Panchayat actually has.

A resident who cannot sign in goes to the office. An officer identifies them
against the village register — the same check that already gates account
approval — and issues a one-time code. The system shows it once; the officer
writes it down and hands it over. The resident redeems it for a password of
their own choosing, so **the officer never learns the password**, only that a
reset was permitted.

| Who | May reset |
|---|---|
| Officer | Residents of their own village |
| Admin | Anyone, including officers |
| Anyone | Not themselves — that is `change-password` |

An officer who could reset another officer, or an admin, would hold a route from
one village login to the whole block. That is the check most worth reading in
`auth.py`, and it has tests.

The code is stored only as a bcrypt hash, expires after 24 hours, works once,
and is voided by issuing another. Its alphabet drops `O I L S 0 1`, because it
is read off a slip of paper and a resident who types `0` for `O` has hit a bad
alphabet rather than failed a security check. Redeeming is metered like signing
in, since a code is the same kind of guessable secret.

**Resetting ends existing sessions.** Access and refresh tokens are stateless
JWTs with no server-side session to close, so without this a reset would leave
whoever already had the account signed in for the week a refresh token lasts —
which is precisely the situation a reset exists for. `users.tokens_valid_from`
records the moment of revocation and `core.deps` refuses any token issued
before it. Changing your own password does the same, and returns a fresh token
pair so the caller is not signed out by their own success.

Known gap: a resident must reach the office. There is no way to start a reset
from the portal, because there is no channel to deliver a code over. That is a
missing integration, not a missing design.

### Audit trail

`audit_events` records who did what, to whose record, and when — so a resident
can be told who opened their file, and an officer who rejected a document can be
asked why.

It is written by **middleware**, not by calls at the top of each route. That is
the design decision worth defending: a trail assembled from `audit.record(...)`
lines scattered through the routers is only as complete as the last person to
add a route remembered to be, and the endpoint that gets forgotten is always the
new one nobody reviewed. Here a request is recorded because it was *served*, so
a router added next term is covered without its author knowing the module
exists.

| Recorded | Not recorded |
|---|---|
| Every state change by a signed-in user | Anything unauthenticated — there is nobody to attribute it to |
| Every read that names one record | List endpoints |
| Refused attempts, with their status code | Request bodies, ever |

Two of those are deliberate limits rather than gaps:

- **List endpoints are not recorded.** An officer opens the resident directory
  on every page load; recording that buries the events worth finding. The trail
  answers "who opened Savita's file", not "who could have".
- **No request bodies.** This table is designed to be kept and read later, which
  is the last place a resident's income, a document's contents, or a password
  being set should end up. Method, path, outcome and the record named answer the
  question without holding any of that.

Reading it is **admin only**, and that is a privacy decision rather than a
hierarchy one: the trail says which residents an officer's colleagues have been
looking at, which is more revealing than most of what it describes. There is no
endpoint to edit or delete an event — a trail its subjects can amend is not one
— and `services.audit.prune()` drops rows past a year.

Recording can never break a request: a failure to write the trail is logged and
swallowed. Losing one audit row is bad; refusing a resident's grievance because
the audit table is full is worse.

---

## Privacy: what leaves this server

Google's terms state that content submitted on the Gemini free tier may be used
to improve their products. A resident applying for a widow's pension cannot
meaningfully consent to that, and a Panchayat cannot consent on their behalf.

The answer here is not to rely on a tier upgrade. A paid tier is a contractual
promise about data already handed over; the stronger guarantee is not to hand it
over. So the rule is enforced in code, in one place, as a hard rule rather than
a setting:

**The model may see the village, never the villager.**

| Sent to Gemini | Never sent |
|---|---|
| Village facts, LGD codes, Census figures | Resident names |
| Scheme rules, benefits, required documents | Income, social category, BPL status, ration card |
| Project names, budgets, progress | Disability assessments |
| Grievance titles, wards, categories, status | Which documents sit in a resident's file |
| Gram Sabha minutes and decisions | Any eligibility verdict about a named person |

Three things enforce it:

1. **Residents are not in the index.** `services/indexer.py` builds no chunk for
   any resident, so no part of the register is embedded. This matters most,
   because indexing runs over every row whether or not anyone asks a question —
   a resident in the index is exported as a standing cost of the feature.
2. **Personal facts are flagged as they are retrieved.** `services/retrieval.py`
   marks any fact describing one identified resident, and
   `api/routes/assistant.py` refuses to build a prompt from a set containing
   one. The question that asked for them is not sent either.
3. **The decision was never the model's anyway.** Eligibility is decided by
   `services/eligibility.py`, a deterministic rule engine. The model was only
   ever phrasing an answer the engine had already reached, so withholding the
   record costs phrasing and nothing else.

The resident is told, rather than left to assume: an answer about their own file
carries a badge reading *"Your data — kept in the Panchayat"*, and the answer
itself closes by saying their income, category and documents were not sent
outside the system.

> **If you indexed before this change, re-run the indexer.** Excluding residents
> from `build_drafts` stops new ones being written; it does not delete rows
> already stored. One run removes them, and needs no API key because the
> deletion happens before anything is embedded:
>
> ```bash
> python -m app.index
> ```
>
> The `removed:` figure it prints is how many chunks it deleted. Expect it to
> match your resident count on the first run after upgrading.

**Why not just anonymise the records instead?** It was considered and rejected.
At village scale it does not work — "a 52-year-old female agricultural labourer
in ward 3" identifies one person in a population of a few hundred, so stripping
the name leaves the record re-identifiable from the quasi-identifiers around it.
De-identification is a defence at district scale and an illusion at this one.

### What still reaches Google, honestly

- **The text of non-personal questions.** An officer asking "which ward has the
  worst water complaints" sends that sentence.
- **Grievance descriptions**, which are free text. A resident who writes a
  neighbour's name into a complaint puts that name in the index. Structured
  fields are controlled; prose is not.
- **Uploaded Gram Sabha minutes and Government Resolutions**, whose text is sent
  for extraction. Gram Sabha proceedings are public records by law, and a GR is
  a published government document, so neither is private — but minutes naming a
  resident who spoke would carry that name.

None of these is solved by the boundary above, and a deployment holding real
resident data should say so plainly rather than claim more than it does.
