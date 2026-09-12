# Inventory Management

Web-based ERP for item/textile inventory: item and contact masters, purchase orders, goods receipt
notes, job work (vendor WIP), stock ledger, valuation and reports — with role-based access control.

```
React (TypeScript + Tailwind)  →  FastAPI (/api/v1)  →  SQLAlchemy 2.x async  →  PostgreSQL
```

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (async) |
| Database | PostgreSQL 14+ (SQLite for local development only) |
| Auth | JWT access + refresh, Argon2 hashing, optional Google Sign-In |
| Access control | Database-backed roles and permissions |
| Reports | CSV and PDF (ReportLab) |
| Migrations | Alembic |
| Deployment | Docker Compose (any VPS) or Vercel containers |

---

## Quick start (local)

Requires Python 3.12+ and Node 20+.

**Backend**

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
copy ..\.env.example .env      # Linux/macOS: cp ../.env.example .env
uvicorn app.main:app --reload --port 8001
```

With the default `DATABASE_URL` (SQLite) the tables are created automatically on first run, and the
database is seeded with roles, permissions and an `admin` / `admin123` account.

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to port 8001.

> Change the default admin password immediately on any shared or deployed instance.

---

## Configuration

All settings are environment variables, read from `backend/.env` locally or from the host
environment in production. See [.env.example](.env.example).

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite file | Postgres URL in any common format — see below |
| `DATABASE_URL_SYNC` | derived | Alembic only; defaults to `DATABASE_URL` with a sync driver |
| `SECRET_KEY` / `JWT_SECRET_KEY` | `change-me` | **Must** be unique random 32+ character values in production |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated site origins |
| `ENVIRONMENT` | `development` | Set to `production` to enable startup safety checks |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `5` / `5` | Per process — multiply by instance count |
| `DB_DISABLE_PREPARED_STATEMENTS` | auto | Forced on for PgBouncer / `-pooler` hosts |
| `GOOGLE_CLIENT_ID` | empty | Set to enable Google Sign-In; empty disables it |
| `GOOGLE_ALLOW_SIGNUP` | `true` | Allow self-service account creation |
| `GOOGLE_SIGNUP_ROLE` | `viewer` | Role given to self-provisioned accounts |
| `GOOGLE_ALLOWED_DOMAINS` | empty | Restrict sign-in to specific email domains |

### Database URLs are normalised automatically

Paste the connection string from any provider — Neon, Supabase, RDS, or a plain VPS — in whichever
format they give you. The app converts it to the correct driver at startup:

| You provide | App uses (async) | Alembic uses (sync) |
|---|---|---|
| `postgresql://…?sslmode=require` | `postgresql+asyncpg://…?ssl=require` | `postgresql+psycopg2://…?sslmode=require` |
| `postgres://…` | `postgresql+asyncpg://…` | `postgresql+psycopg2://…` |
| `postgresql+asyncpg://…` | unchanged | `postgresql+psycopg2://…` |

`sslmode` is translated to `ssl` and `channel_binding` is dropped, because asyncpg rejects
libpq-only parameters. Hosts containing `-pooler` or `pgbouncer` automatically disable prepared
statement caching. **Moving to a different PostgreSQL server means changing one variable.**

### Production safety checks

When `ENVIRONMENT=production` the app refuses to start if secrets are still defaults or too short,
if `DATABASE_URL` points at SQLite, or if `CORS_ORIGINS` is empty. Failing loudly at boot beats
running an instance whose JWTs anyone can forge.

Generate secrets with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Deploying

Both paths are documented step by step in [deployment_steps.md](deployment_steps.md). To move an
existing deployment to a different database or host, see [migration_steps.md](migration_steps.md).

### Any VPS (Docker Compose)

Ships PostgreSQL, the API, the built frontend and an Nginx reverse proxy:

```bash
cp .env.example .env      # set POSTGRES_PASSWORD, SECRET_KEY, JWT_SECRET_KEY, CORS_ORIGINS
docker compose up -d --build
```

Migrations run automatically when the backend starts. PostgreSQL is **not** published to the host —
only the backend can reach it. Put a TLS-terminating proxy (Caddy, or Nginx + certbot) in front.

To use a managed database instead of the bundled one, set `DATABASE_URL` and `DATABASE_URL_SYNC` in
`.env` and delete the `postgres` service from `docker-compose.yml`. Nothing else changes.

### Vercel (containers)

[vercel.json](vercel.json) defines two services built from `Dockerfile.vercel` files, served behind
one domain. The database must be external. Migrations are run manually, as Vercel has no release hook.

---

## Database migrations

Alembic owns the schema everywhere except local SQLite development.

```bash
cd backend
alembic upgrade head                      # apply
alembic revision --autogenerate -m "..."  # create after changing models
alembic downgrade -1                      # roll back one
```

Migrations use `batch_alter_table`, so they apply cleanly on both PostgreSQL and SQLite.

---

## Access control

Roles and permissions live in the database (`roles`, `permissions`, `role_permissions`) and can be
changed at runtime from **Access Management** without a redeploy.

| Permission | Grants |
|---|---|
| `users` | Create, edit and deactivate users |
| `roles` | Create roles, assign permissions |
| `masters` | Items, contacts, vendors |
| `imports` | Bulk CSV import (admin only by default) |
| `purchase` / `grn` / `jobwork` | Transaction entry |
| `inventory` | View and adjust stock |
| `reports` | View and export reports |
| `settings` | Company settings |

Built-in roles: **admin** (everything), **manager**, **operator**, **viewer**. Admin is reconciled
against the full permission catalogue on startup, so a newly added permission never leaves it
locked out of its own feature.

Users sign in with username/email and password, or with Google when `GOOGLE_CLIENT_ID` is set. A
Google account is linked to an existing user by email, or provisioned with `GOOGLE_SIGNUP_ROLE`.

---

## Bulk import and export

Master tables (Items, Contacts, Vendors, Process Types) support CSV import and export.

- **Import** requires the `imports` permission. Download the template from the dialog. Rows whose
  key already exists are **skipped, not overwritten**. Duplicates are detected both against the
  database and within the file, and each row is validated independently so a single bad row cannot
  fail the rest. Results show imported/skipped counts plus per-row errors with line numbers.
- **Export** is available to any signed-in user and respects the active search, filter and sort.

---

## Testing

```bash
cd backend
pytest -q
```

---

## Project layout

```
backend/
  app/
    api/routes/      REST endpoints
    core/            config, database, security, dependencies
    models/          SQLAlchemy models
    schemas/         Pydantic request/response models
    services/        business logic
  alembic/versions/  migrations
  tests/
  Dockerfile         VPS / Docker Compose image
  Dockerfile.vercel  Vercel container image
frontend/
  src/
    pages/           one folder per screen
    components/      DataTable, dialogs, shared UI
    contexts/        auth and settings
    services/        axios client
nginx/               reverse proxy config for Docker Compose
vercel.json          Vercel service and routing config
docker-compose.yml   full VPS stack
```
