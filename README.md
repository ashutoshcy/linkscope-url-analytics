# Linkscope — URL Shortener & Click Analytics

**Short links. A bigger picture.** A full-stack, multi-user link management application with a visual analytics workspace, privacy-conscious click tracking, and an API you can actually build on.

![Linkscope overview](docs/screenshots/dashboard-desktop.png)

| Analytics | Mobile dashboard |
| --- | --- |
| ![Analytics view](docs/screenshots/analytics-desktop.png) | ![Responsive mobile dashboard](docs/screenshots/dashboard-mobile.png) |

Built as an engineering portfolio project, with **FastAPI + SQLAlchemy + PostgreSQL/SQLite + optional Redis**, and a custom responsive UI. No frontend build step is needed.

## What it does

- **Accounts and private workspaces** — registration, Argon2 password hashing, signed 7-day sessions in HttpOnly cookies, CSRF protection, and access isolation between users.
- **Short links with personality** — cryptographically generated aliases, optional custom aliases, title/description/tag, expiry date, pause/resume, editing, deletion, search, filters and sorting.
- **Reliable redirects** — server-side `302` redirect, noncacheable redirects, atomic link counters, appropriate 404/410 status responses, optional Redis slug cache with invalidation.
- **Click analytics** — traffic over time, aggregate clicks, unique daily link visits, top referrers, desktop/mobile/tablet breakdown, browsers, tracked UTM campaigns, top links and per-link insights.
- **Handy sharing tools** — a generated QR code for every link, one-click copy, and CSV analytics export.
- **Workspace dashboard** — bespoke light UI and dark sidebar, interactive area chart, status indicators, empty/loading/error states, desktop and mobile navigation, keyboard shortcuts and keyboard-accessible modals.
- **Developer workflow** — Pydantic validation, Alembic migrations, Docker Compose for PostgreSQL/Redis/app, 32 automated tests, GitHub Actions, a reproducible Chromium smoke test and example data.

### Important precision about metrics

“Unique visits” is an **estimate of one visitor per link per UTC day**, identified using an HMAC of request IP + user agent + link ID + date. The database **does not store raw visitor IPs**. A repeat visit on a different day or another link is counted separately; this metric is not a cross-device or cross-link unique-person identifier. Common bots are excluded through heuristic user-agent detection, which is not perfect.

## How it works

```mermaid
flowchart TD
    B[Browser dashboard] -->|Session cookie + CSRF| API[FastAPI API]
    API -->|SQLAlchemy ORM| SQL[(SQLite or PostgreSQL)]
    R[Visitor scans QR / clicks short URL] -->|GET /r/alias| RED[Redirect service]
    RED -->|Optional TTL cache| C[(Redis)]
    RED -->|Click event + atomic count| SQL
    RED -->|302| SITE[Destination website]
    SQL --> A[Analytics aggregation]
    A --> API
    API --> B
```

**A single request:** A visitor opens `/r/summer-launch`. The service finds the link (using a 60-second Redis cache if configured), checks pause/expiry status, classifies referrer and user agent, records a pseudonymous click event, increments the click counter atomically, and returns a `302` response with a `Location` header. The analytics API aggregates human events into chart-ready JSON. Pausing, editing, or deleting links invalidates the corresponding cached slug.

### Repository structure

```text
app/
  api/
    auth.py            # Registration, login, session management
    links.py           # CRUD, redirects, QR codes
    stats.py           # Analytics and CSV export
  core/
    analytics.py       # Visitor classification and time-series rollups
    cache.py           # Optional Redis cache and rate limiting
    config.py          # Environment configuration
    security.py        # Argon2, JWT, CSRF, database dependency
    validation.py      # Pydantic request validation
  db/
    models.py          # Users, links, click events
  static/
    index.html         # Full dashboard markup
    styles.css         # Responsive visual design
    app.js             # Dashboard API client and interactions
alembic/versions/     # Initial migration
scripts/               # Demo data and Chromium browser test
tests/                 # API, auth, redirect, security, analytics tests
docs/screenshots/      # Real browser screenshots
.github/workflows/    # CI
```

## Quick start — SQLite

**Requirements:** Python 3.11+ and pip. No Docker, Redis or frontend tooling required.

```bash
# From the project root
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` if you want a reference. The app reads **environment variables**, not `.env` files automatically, so set a unique secret in the shell before using it outside a private local test. For example:

```bash
# macOS / Linux
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
# Windows PowerShell:
# $env:SECRET_KEY = py -c "import secrets; print(secrets.token_urlsafe(48))"

alembic upgrade head
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/**. Create an account or optionally load demonstration data:

```bash
# In another terminal, in the same project root, with the virtual environment activated
python -m scripts.seed_demo
```

You can then use **Explore sample workspace** on the sign-in screen. The local-only demo credentials are `demo@linkscope.dev` / `DemoPass123!`. Do **not** seed demo credentials in any public or production database.

> If you run the app before `alembic upgrade head`, development auto-table-creation makes the UI work but does not create an Alembic version record. Start with migrations on a clean database. For a database initialized without migrations, back up your data and use `alembic stamp head` only after confirming the schema matches the current models.

## Full-stack Docker Compose (PostgreSQL + Redis + API)

The local-first Docker setup exposes PostgreSQL and Redis only on loopback, and hosts FastAPI at `127.0.0.1:8000`.

```bash
# Choose a private secret in your terminal for your installation
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker compose up --build -d
```

To use PostgreSQL from a local (non-Docker) Python process, start the database services with `docker compose up -d db redis` and set:

```text
DATABASE_URL=postgresql+psycopg://linkscope:dev_password_change_me@localhost:5432/linkscope
REDIS_URL=redis://localhost:6379/0
```

Then run `alembic upgrade head` and `uvicorn app.main:app --reload`. Change all local example passwords before hosting anywhere. A Dockerfile is included for deployment, but no live service is deployed by this repository.

### Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./linkscope.db` | SQLite local database or PostgreSQL connection |
| `SECRET_KEY` | Insecure dev-only fallback | Sign JWTs and HMAC click fingerprints; **set it in production** |
| `APP_ENV` | `development` | `production` enforces a 32+-character non-default secret |
| `REDIS_URL` | Not set | Optional Redis cache and distributed rate limiting |
| `PUBLIC_BASE_URL` | Current request host | Public origin included in generated short URLs |
| `COOKIE_SECURE` | Auto on HTTPS | Force Secure flag for auth cookies |

**`.env` is not loaded automatically.** Set environment variables in your shell, process manager, Docker Compose, or hosting platform. Keep secrets outside version control.

## API overview

Interactive documentation: **http://127.0.0.1:8000/api/docs**

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Create a user and session |
| `POST` | `/api/auth/login` | Start session |
| `GET` | `/api/auth/me` | Current user and session-bound CSRF token |
| `POST` | `/api/auth/logout` | Clear browser session |
| `POST` | `/api/links` | Create a tracked link |
| `GET` | `/api/links` | List, search, filter, sort and paginate |
| `GET` | `/api/links/{id}` | Link details |
| `PATCH` | `/api/links/{id}` | Update destination, metadata, expiry, or active state |
| `DELETE` | `/api/links/{id}` | Delete link and associated clicks |
| `GET` | `/api/links/{id}/qr` | Generate QR PNG |
| `GET` | `/r/{slug}` | Visit destination and record click |
| `GET` | `/api/analytics/overview?days=14` | Workspace time series and aggregate breakdowns |
| `GET` | `/api/analytics/links/{id}?days=30` | Per-link analytics |
| `GET` | `/api/analytics/export.csv?days=30` | CSV download |
| `GET` | `/api/health` | Health response |

**Authentication details:** Browser requests use HttpOnly `linkscope_session` cookie with an `X-CSRF-Token` header for mutations (the token comes from login or `/me`). The underlying verifier also supports an `Authorization: Bearer <JWT>` header for API clients. `/r/{slug}` is intentionally public. The session cookie is `Secure` over HTTPS and SameSite=Lax.

Example creation body:

```json
{
  "target_url": "https://example.com/campaign",
  "title": "Campaign landing page",
  "slug": "spring-launch",
  "tags": "Marketing",
  "description": "Launch trackable landing page"
}
```

## Verification

```bash
python -m pytest -q
alembic upgrade head
alembic check
node --check app/static/app.js   # Node.js optional, only needed for syntax check
```

The `tests/` suite covers registration, password validation, cross-account isolation, CSRF, aliases, malicious/invalid URL schemes, click logging, human/bot handling, cached redirect invalidation, pause/delete, pagination, filters, QR PNG, exports, and rate limiting. GitHub Actions runs the Python tests and schema migration check on each push.

A **Chromium browser smoke test** runs the actual HTML/CSS/JavaScript with a Python bridge to the real FastAPI application. The bridge is needed because some automated sandboxes disallow local HTTP navigation. It validates desktop/mobile rendering, create/edit/delete, search, analytics, QR details, and sign out. Install Playwright (`pip install playwright`) and a Chromium browser to run:

```bash
python -m scripts.browser_check
```

It generates a disposable SQLite test database with demo data; it does not use your personal workspace. This smoke test isn't part of CI because Chromium isn't installed in the default job. It does not substitute for full load, penetration, cross-browser, or live Docker/PostgreSQL/Redis testing.

## Design decisions and limitations

- **No mandatory Node build tool:** Plain JS/CSS ships alongside the FastAPI backend. This simplifies reproducibility without sacrificing a styled dashboard.
- **Atomic click counters:** The redirect path updates counters in SQL atomically. Event storage preserves richer dimensions for chart queries.
- **Redis optional by design:** Cached redirects live for 60 seconds and cache entries are invalidated on edit/delete; if Redis is down, redirects continue via SQL. Redis also enables distributed throttling for login, registration and link creation. With no Redis configured, those distributed rate limits are not active.
- **No false geographic analytics:** The app doesn't purchase GeoIP data or collect locations, so it doesn't pretend to know countries or cities.
- **Privacy:** No raw IP is persisted. Referrer data is reduced to domain only. Unique visits are approximate and device classification is heuristic. Consult applicable consent and data-retention requirements before production use.
- **Security work before public internet launch:** Add email verification/recovery, account and session revocation, anti-phishing/abuse monitoring, content-security policies, link reputation checks, audit logs, backup policy, distributed load tests, security review, cookie/domain review and a dedicated production deployment pipeline. Public URL shorteners are attractive targets for malicious links.

## Engineering status

This repository is a **locally verified portfolio project**, not a claim of zero defects or a production security certification. The API tests, schema check, JS syntax check and Chromium workflow passed in the development environment. PostgreSQL/Redis Docker integration and a live HTTPS deployment require infrastructure-specific verification.

---

Made to demonstrate backend engineering, relational modeling, analytics, full-stack UI work, and engineering tradeoffs.
