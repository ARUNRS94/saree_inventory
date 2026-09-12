# Migration guide

How to move **Inventory Management** off Neon and off Vercel, onto any other PostgreSQL and any
other VPS. The two halves are independent — you can do either one alone, or both at once.

- [Part A — Neon → any other PostgreSQL](#part-a--neon--any-other-postgresql)
- [Part B — Vercel → any other VPS](#part-b--vercel--any-other-vps)
- [Part C — Doing both at once (recommended order)](#part-c--doing-both-at-once)
- [Appendix — environment variable reference](#appendix--environment-variable-reference)
- [Appendix — troubleshooting](#appendix--troubleshooting)

---

## Why this is easy

The app was deliberately built with no provider lock-in:

| Concern | How it stays portable |
| --- | --- |
| Database | Plain PostgreSQL. No Neon-specific extensions, no `pg_vector`, no serverless driver. |
| Connection string | [`backend/app/core/config.py`](backend/app/core/config.py) normalises whatever URL you paste — `postgres://`, `postgresql://`, `sslmode=`, `channel_binding=` are all rewritten for the right driver. |
| Schema | Owned by Alembic, one baseline at [`backend/alembic/versions/001_initial.py`](backend/alembic/versions/001_initial.py). |
| Hosting | Two ordinary Docker images. Vercel uses `Dockerfile.vercel`; everything else uses the plain `Dockerfile`. |
| State on disk | None that matters. The app keeps no session files, and the company logo is a **URL**, not an upload. |

The only thing you must get right is the pair of connection URLs and the migration state. Everything
else is configuration.

---

# Part A — Neon → any other PostgreSQL

Works for: self-hosted Postgres in Docker on your VPS, Supabase, Amazon RDS/Aurora, DigitalOcean
Managed Postgres, Azure Database for PostgreSQL, Google Cloud SQL, Railway, Render, Hostinger's
managed Postgres — anything speaking the real PostgreSQL wire protocol.

## A0. Decide: migrate the data, or start clean?

**If you are still setting up and the data is disposable**, skip the dump/restore entirely. Point
`DATABASE_URL_SYNC` at the new empty database, run `alembic upgrade head`, start the app, and it
seeds roles, permissions and the default `admin` / `admin123` account by itself. Jump to
[A6](#a6-create-the-database-role-and-database-on-the-target).

**If you have real data**, do the full dump/restore below.

## A1. Take stock of the source

Get your Neon connection string from the Neon console (**Dashboard → Connection Details**). You want
the **direct/unpooled** host for the dump — the one *without* `-pooler` in it. Poolers are for
application traffic, not for `pg_dump`.

```powershell
# PowerShell — keep the password out of your shell history where you can
$env:PGSOURCE = "postgresql://neondb_owner:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require"
```

Record the server version, because your target must be **the same major version or newer**:

```powershell
psql $env:PGSOURCE -c "SHOW server_version;"
```

Record what you expect to move — you will compare these numbers again after the restore:

```powershell
psql $env:PGSOURCE -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;"
psql $env:PGSOURCE -c "SELECT version_num FROM alembic_version;"
```

The `alembic_version` value is the single most important row in the database. If it doesn't arrive
at the target, Alembic will think the database is empty and try to create every table again.

## A2. Install matching client tools

Your `pg_dump` must be **>= the source server version**. A Postgres 15 `pg_dump` cannot dump a
Postgres 17 server.

```powershell
winget install PostgreSQL.PostgreSQL.17     # gives you psql, pg_dump, pg_restore
```

Then confirm the binaries on your `PATH` are the new ones:

```powershell
pg_dump --version
psql --version
```

If Windows keeps picking an older copy, call the versioned path directly, e.g.
`& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"`.

## A3. Freeze writes

Data written between the dump and the cutover is lost. Pick one:

- **Simplest** — announce a short maintenance window and tell users to stop.
- **Enforced** — scale the Vercel deployment down, or on a VPS run `docker compose stop backend`.
  The frontend will show errors, which is the point.

Do the dump *after* writes have stopped, not before.

## A4. Dump the database

Two dumps, because they serve different purposes:

```powershell
# 1. Custom format - what you will actually restore from. Compressed, parallel-restorable.
pg_dump $env:PGSOURCE --format=custom --no-owner --no-privileges --no-acl `
        --file=neon-backup.dump

# 2. Plain SQL - human-readable, so you can grep it if the restore misbehaves.
pg_dump $env:PGSOURCE --format=plain --no-owner --no-privileges --no-acl `
        --file=neon-backup.sql
```

Why each flag matters:

| Flag | Reason |
| --- | --- |
| `--no-owner` | The target won't have a role called `neondb_owner`. Without this the restore errors on every `ALTER TABLE ... OWNER TO`. |
| `--no-privileges` / `--no-acl` | Drops Neon's `GRANT` statements, which reference roles that don't exist on the target. |
| `--format=custom` | Lets `pg_restore` run selectively and in parallel, and survives partial failures. |

Check the file is real before you trust it:

```powershell
Get-Item neon-backup.dump | Select-Object Length, LastWriteTime
pg_restore --list neon-backup.dump | Select-String "TABLE DATA"
```

You should see `TABLE DATA` lines for `users`, `roles`, `permissions`, `role_permissions`,
`user_identities`, `items`, `contacts`, `vendors`, `vendor_process_types`, `purchase_orders`,
`purchase_order_items`, `grns`, `grn_items`, `job_work_issues`, `job_work_issue_items`,
`job_work_receipts`, `job_work_receipt_items`, `stock_ledger`, `company_settings` and
`alembic_version`.

**Store `neon-backup.dump` somewhere off your laptop before continuing.** This is your rollback.

## A5. Provision the target server

### Option 1 — Postgres in Docker on your own VPS

Already defined in [`docker-compose.yml`](docker-compose.yml) as the `postgres` service. It is
deliberately **not** published to the host — only the backend container can reach it. Nothing to do
here beyond setting `POSTGRES_PASSWORD` in `.env`.

### Option 2 — A managed provider

Create the instance and note four things: **host, port, database name, and whether it requires
TLS**. Almost every managed provider does; you will need `?sslmode=require` on the URL.

Also check two provider-specific traps:

- **Is the host you were given a connection pooler?** Supabase's port `6543`, anything with
  `pgbouncer` in the name, and Neon's `-pooler` hosts are transaction-mode poolers. See
  [A9](#a9-handle-connection-poolers).
- **Is there an IP allow-list?** RDS, Cloud SQL and DigitalOcean default to closed. Add your VPS's
  public IP, and your own IP for the restore.

## A6. Create the role and database on the target

Skip if your provider already created them for you (most managed ones do).

```sql
CREATE ROLE inventory WITH LOGIN PASSWORD 'a-long-random-password';
CREATE DATABASE inventory OWNER inventory;
```

Then connect to the new database and make sure the role owns the default schema:

```sql
\c inventory
GRANT ALL ON SCHEMA public TO inventory;
ALTER SCHEMA public OWNER TO inventory;
```

That last line matters on **PostgreSQL 15 and newer**, where non-owners can no longer create objects
in `public` by default. Skipping it produces `permission denied for schema public` during restore.

## A7. Restore

```powershell
$env:PGTARGET = "postgresql://inventory:PASSWORD@new-host:5432/inventory?sslmode=require"

pg_restore --dbname=$env:PGTARGET --no-owner --no-privileges `
           --exit-on-error --single-transaction `
           neon-backup.dump
```

`--single-transaction` means you either get the whole database or nothing — no half-restored state
to untangle. Combined with `--exit-on-error` it stops at the first real problem.

If it fails partway and you need to retry, start from a genuinely empty database:

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO inventory;
```

## A8. Verify the restore

Compare against the numbers you recorded in [A1](#a1-take-stock-of-the-source). All three must match.

```powershell
# 1. Same tables, same row counts
psql $env:PGTARGET -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;"

# 2. Same migration state - this is the one people forget
psql $env:PGTARGET -c "SELECT version_num FROM alembic_version;"

# 3. Sequences are past their max id, or the next insert collides
psql $env:PGTARGET -c "SELECT sequencename, last_value FROM pg_sequences ORDER BY sequencename;"
```

> `pg_stat_user_tables` counts are approximate until the table is analysed. If a count looks wrong,
> run `ANALYZE;` first, or verify precisely with `SELECT count(*) FROM items;` on the few tables you
> care most about.

Sequences are the classic silent failure. `pg_restore` does carry them over, but if you ever
hand-copied data with `INSERT`s instead, fix them now:

```sql
SELECT setval(
  pg_get_serial_sequence('items', 'item_id'),
  COALESCE((SELECT MAX(item_id) FROM items), 1)
);
```

Repeat for every table with a generated primary key. Symptom of getting this wrong: the app works
fine for reads, then throws `duplicate key value violates unique constraint` on the first create.

## A9. Handle connection poolers

Transaction-mode poolers reject asyncpg's prepared statements. The app auto-detects Neon's
`-pooler` hosts, Supabase's transaction pooler (port `6543`), and any URL containing `pgbouncer`.
If you run your own PgBouncer on a non-standard port, set it yourself:

```
DB_DISABLE_PREPARED_STATEMENTS=true
```

Symptom of getting this wrong: intermittent, load-dependent
`prepared statement "__asyncpg_stmt_1__" already exists`.

Also point Alembic at a **session-mode or direct** endpoint, never a transaction pooler — migrations
need session state that transaction pooling discards:

```
DATABASE_URL=postgresql+asyncpg://user:pass@pooled-host:6543/db      # app traffic
DATABASE_URL_SYNC=postgresql+psycopg2://user:pass@direct-host:5432/db # migrations
```

On Supabase those are the **transaction pooler** (`...pooler.supabase.com:6543`) and the **session
pooler** (`...pooler.supabase.com:5432`) respectively. Prefer the session pooler over the direct
`db.<ref>.supabase.co` host, which is IPv6-only unless you buy the IPv4 add-on.

## A10. Size the connection pool

Every running instance keeps its own pool. The arithmetic you must satisfy:

```
(DB_POOL_SIZE + DB_MAX_OVERFLOW) × number_of_instances  <  the server's max_connections
```

Defaults are `5 + 5 = 10` per instance. On a single-container VPS that's fine against almost any
server. On a small managed instance capped at 25 connections, one instance already uses 40% of it —
drop `DB_MAX_OVERFLOW` to `2` and leave room for `psql` and backups.

Check what you're working with:

```powershell
psql $env:PGTARGET -c "SHOW max_connections;"
```

## A11. Point the app at the new database

Set both URLs. They differ by **driver**, not by destination:

```
DATABASE_URL=postgresql+asyncpg://inventory:PASSWORD@new-host:5432/inventory?sslmode=require
DATABASE_URL_SYNC=postgresql+psycopg2://inventory:PASSWORD@new-host:5432/inventory?sslmode=require
```

You may paste the raw provider string too — `_rewrite_pg_url()` in
[`backend/app/core/config.py`](backend/app/core/config.py) will convert `postgres://` and
`postgresql://` to the right driver, translate `sslmode` into asyncpg's `ssl`, and drop
`channel_binding`, which asyncpg rejects. Being explicit is still clearer for the next person.

Where you set them:

- **Vercel** — Project → Settings → Environment Variables → Production, then **redeploy**. Vercel
  bakes env vars at deploy time; editing them alone changes nothing.
- **VPS** — edit `.env`, then `docker compose up -d` to recreate the containers.

## A12. Apply any pending migrations

The restored database is at whatever revision Neon was on. If you have since added migrations:

```powershell
cd backend
$env:DATABASE_URL_SYNC = "postgresql+psycopg2://inventory:PASSWORD@new-host:5432/inventory?sslmode=require"
alembic current      # what the database thinks it is
alembic heads        # what the code expects
alembic upgrade head
```

If `current` and `heads` already match, this is a no-op — run it anyway to prove connectivity.

## A13. Smoke-test, then cut over

```powershell
curl https://your-domain/api/health/db     # {"status":"ok"} - proves the app reached Postgres
curl https://your-domain/api/health        # {"status":"ok", ...}
```

If `/api/health/db` returns `503`, the `detail` field names the exception type — see
[troubleshooting](#appendix--troubleshooting).

Then in the UI: sign in, open Dashboard (exercises aggregate queries across most tables), open
Inventory, and create one throwaway purchase order to prove writes and sequences work. Delete it
after.

Only now unfreeze writes.

## A14. Decommission Neon — after a grace period

Wait until you have at least one full business day of clean operation and one verified backup of the
*new* database. Then:

1. Keep `neon-backup.dump` archived for a few weeks regardless.
2. Remove `DATABASE_URL` values pointing at Neon from every environment, including Preview.
3. **Rotate the Neon password before deleting anything** — that credential has been shared around
   during this migration.
4. Delete the Neon project.

## A15. Set up backups on the new database

Neon did this invisibly. Your new host probably does not. On a VPS, a nightly dump:

```bash
# /etc/cron.daily/inventory-backup  (chmod +x)
#!/bin/sh
set -e
BACKUP_DIR=/var/backups/inventory
mkdir -p "$BACKUP_DIR"
cd /opt/inventory-management
docker compose exec -T postgres pg_dump -U inventory --format=custom inventory \
  > "$BACKUP_DIR/inventory-$(date +%F).dump"
find "$BACKUP_DIR" -name 'inventory-*.dump' -mtime +14 -delete
```

Then copy off-box — `rclone` to S3/Backblaze, or `restic`. **A backup on the same server as the
database is not a backup.** Test a restore into a scratch database once, now, while you still
remember how.

---

# Part B — Vercel → any other VPS

Works for: Hostinger, DigitalOcean, Hetzner, Linode, Vultr, AWS Lightsail/EC2, Oracle Cloud, or any
Ubuntu box you can SSH into.

## What actually changes

| | Vercel | VPS |
| --- | --- | --- |
| Build | `Dockerfile.vercel` × 2, port 80 | plain `Dockerfile` × 2, backend on 8000 |
| Routing | `rewrites` in `vercel.json` | nginx containers in [`nginx/nginx.conf`](nginx/nginx.conf) |
| TLS | automatic | your job — Certbot |
| Idle behaviour | scales to zero, cold starts | always warm |
| Database | must be external | can live in the same compose stack |
| Deploys | `git push` | `git pull && docker compose up -d --build` |

The big practical win: **cold starts disappear**. That is the dominant cause of the slow sign-ins on
Vercel — the container sleeps after 5 minutes idle and Neon's free tier suspends compute alongside
it.

## B1. Provision the VPS

Minimum realistic sizing for this stack (Postgres + FastAPI + nginx, plus a Node build):

| Users | Spec |
| --- | --- |
| Light / internal, < 10 concurrent | 1 vCPU, 2 GB RAM, 40 GB SSD |
| Comfortable, room for the build | 2 vCPU, 4 GB RAM |

Choose **Ubuntu 24.04 LTS**. Note the public IP.

> If you pick 1 GB RAM the `npm run build` step will be OOM-killed. If you are stuck with 1 GB,
> either add swap or build the frontend image elsewhere and push it to a registry.

## B2. Point DNS — but keep Vercel live

Create an **A record** for `app.yourdomain.com` → your VPS IP, with a **low TTL (300s)** so you can
reverse it quickly. Leave your existing Vercel domain untouched; you will run both in parallel and
switch at the end.

```powershell
nslookup app.yourdomain.com
```

Wait for it to resolve before requesting a TLS certificate — Certbot validates over HTTP and will
fail otherwise.

## B3. Harden the server

```bash
ssh root@YOUR_VPS_IP

adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy      # copy your key across

apt update && apt upgrade -y
```

Now disable password and root login in `/etc/ssh/sshd_config`:

```
PermitRootLogin no
PasswordAuthentication no
```

```bash
systemctl restart ssh
```

**Before closing this session, open a second terminal and confirm `ssh deploy@YOUR_VPS_IP` works.**
Locking yourself out of a fresh VPS is recoverable only through the provider's console.

Firewall — note that Postgres port 5432 is deliberately absent:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

Optional but worth the two minutes:

```bash
apt install -y fail2ban unattended-upgrades
systemctl enable --now fail2ban
dpkg-reconfigure --priority=low unattended-upgrades
```

## B4. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker deploy
sudo apt install -y docker-compose-plugin
```

Log out and back in so the `docker` group applies, then:

```bash
docker compose version
```

## B5. Get the code onto the server

```bash
sudo mkdir -p /opt/inventory-management
sudo chown deploy:deploy /opt/inventory-management
cd /opt/inventory-management
git clone <your-repo-url> .
git checkout main            # or whichever branch is production
```

For a private repo, generate a deploy key on the VPS (`ssh-keygen -t ed25519`) and add the public
key to the repository's **Deploy keys** with read-only access. Do not paste a personal access token
onto the server.

## B6. Write the `.env`

```bash
cp .env.example .env
nano .env
```

Generate the secrets on the server — never reuse the Vercel ones if they have ever been pasted into
a chat, an issue, or a screenshot:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice
```

Fill in:

```ini
ENVIRONMENT=production
APP_NAME=Inventory Management

SECRET_KEY=<first generated value>
JWT_SECRET_KEY=<second, different value>

CORS_ORIGINS=https://app.yourdomain.com

POSTGRES_USER=inventory
POSTGRES_PASSWORD=<strong random password>
POSTGRES_DB=inventory

HTTP_PORT=8080
```

Two things that will bite you:

1. **`ENVIRONMENT=production` is enforced.** `validate_for_production()` in
   [`backend/app/core/config.py`](backend/app/core/config.py) refuses to start if either secret is a
   placeholder or shorter than 32 characters, if `DATABASE_URL` is SQLite, or if `CORS_ORIGINS` is
   empty. This is intentional — the container will exit with the reason printed.
2. **`CORS_ORIGINS` must be the browser-facing origin**, `https://` included, no trailing slash.

### Which database?

- **Postgres inside compose** — leave `DATABASE_URL` out of `.env` entirely. Compose builds it from
  `POSTGRES_*` and injects it, using the service hostname `postgres`, which only resolves on the
  compose network.
- **External / managed Postgres** — set `DATABASE_URL` and `DATABASE_URL_SYNC` explicitly, and
  delete the `postgres` service plus the `depends_on` and `environment` overrides from
  [`docker-compose.yml`](docker-compose.yml) so compose stops overriding your values.

> Compose's `environment:` block wins over `env_file:`. Setting `DATABASE_URL` in `.env` while the
> `postgres` service is still defined does nothing — a genuinely confusing failure mode.

Lock the file down:

```bash
chmod 600 .env
```

## B7. Build and start

```bash
docker compose up -d --build
docker compose ps
```

The first build takes a few minutes — `npm install` and the Vite build dominate. Every service
should read `running` and the ones with health checks should reach `healthy`.

The backend's compose `command` runs `alembic upgrade head` before uvicorn, so an empty database is
migrated automatically. Watch it happen:

```bash
docker compose logs -f backend
```

Look for Alembic's `Running upgrade -> 001` (first boot only) followed by
`Uvicorn running on http://0.0.0.0:8000`. If you see
`RBAC bootstrap skipped - run 'alembic upgrade head'`, migrations did not apply — the app stays up
deliberately, but nothing will work until you fix the database connection.

Confirm it from inside the box before involving the internet:

```bash
curl http://127.0.0.1:8080/api/health
curl http://127.0.0.1:8080/api/health/db
```

## B8. Restore your data (only if migrating existing data)

If you also did [Part A](#part-a--neon--any-other-postgresql) and are restoring into the compose
Postgres, copy the dump up and restore into the container:

```bash
# from your laptop
scp neon-backup.dump deploy@YOUR_VPS_IP:/tmp/

# on the VPS
cd /opt/inventory-management
docker compose exec -T postgres psql -U inventory -d inventory -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -T postgres pg_restore --dbname=postgresql://inventory:PASSWORD@localhost/inventory \
  --no-owner --no-privileges --single-transaction < /tmp/neon-backup.dump
docker compose restart backend
```

Dropping the schema first removes the empty tables Alembic just created, so the restore has a clean
target. Then re-run the checks in [A8](#a8-verify-the-restore), and delete `/tmp/neon-backup.dump`
from the server afterwards.

## B9. TLS with host nginx + Certbot

The compose stack listens on `127.0.0.1:8080` in plain HTTP. A system nginx terminates TLS in front
of it.

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/inventory-management`:

```nginx
server {
    listen 80;
    server_name app.yourdomain.com;

    # Report exports can be large; don't let the proxy truncate them.
    client_max_body_size 20m;
    proxy_read_timeout 120s;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/inventory-management /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Issue the certificate — Certbot edits the file above to add the `listen 443 ssl` block and an
HTTP→HTTPS redirect:

```bash
sudo certbot --nginx -d app.yourdomain.com
sudo systemctl list-timers | grep certbot     # renewal timer should be active
sudo certbot renew --dry-run
```

## B10. Survive reboots

Every service in [`docker-compose.yml`](docker-compose.yml) already carries
`restart: unless-stopped`, and Docker's own unit is enabled by default. Verify rather than assume:

```bash
sudo systemctl is-enabled docker
sudo reboot
# ... reconnect ...
docker compose -f /opt/inventory-management/docker-compose.yml ps
```

## B11. Update Google sign-in (if enabled)

In the Google Cloud console → **APIs & Services → Credentials → your OAuth 2.0 Web client**, add
`https://app.yourdomain.com` to **Authorised JavaScript origins**. Keep the Vercel origin listed
until the cutover is complete, then remove it.

Symptom of skipping this: the Google button renders but silently does nothing, with an origin
mismatch error in the browser console.

## B12. Verify everything before switching traffic

Against `https://app.yourdomain.com`, while Vercel is still serving live users:

- [ ] `/api/health` → `{"status":"ok","environment":"production"}`
- [ ] `/api/health/db` → `{"status":"ok"}`
- [ ] `/api/docs` → Swagger UI loads
- [ ] Sign in with a real account (or `admin` / `admin123` on a fresh install)
- [ ] Dashboard cards populate — this exercises aggregates across most tables
- [ ] Inventory list loads and sorts
- [ ] Create a purchase order, receive a GRN against it, confirm the stock ledger moves
- [ ] Export a report as CSV **and** as PDF
- [ ] Import a small CSV as admin
- [ ] Hard-refresh on a deep link like `/inventory` — proves the SPA fallback works
- [ ] Sign in again after 10 minutes idle and confirm it is fast (no cold start)

Delete the test purchase order afterwards.

## B13. Cut over

1. Lower the TTL on the old DNS record if you haven't (do this hours ahead).
2. Repoint the production domain's A record from Vercel to the VPS IP.
3. Watch `sudo tail -f /var/log/nginx/access.log` for real traffic arriving.
4. Keep the Vercel deployment running for 24–48 hours as a fallback.

**Rollback**: point the A record back at Vercel. Nothing else to undo — which is exactly why you run
both in parallel first.

## B14. Decommission Vercel

Only after a clean day or two:

1. Remove the custom domain from the Vercel project.
2. Delete the Vercel project.
3. Rotate any secret that was ever a Vercel environment variable, since it now exists in two places.

You can leave `vercel.json`, `backend/Dockerfile.vercel` and `frontend/Dockerfile.vercel` in the
repo. They cost nothing and keep the option open. Delete them only if you want the repo tidier.

## B15. Day-two operations

**Deploy an update:**

```bash
cd /opt/inventory-management
git pull
docker compose up -d --build
docker compose logs -f backend      # confirm migrations applied cleanly
```

**Add a schema migration:** the backend's compose `command` runs `alembic upgrade head` on every
start, so a rebuild applies it. **Take a database backup before deploying a migration** — Alembic
downgrades are not always lossless.

**Logs:**

```bash
docker compose logs -f backend
docker compose logs --tail=200 nginx
```

Cap Docker's log growth in `/etc/docker/daemon.json`, or a chatty container will eventually fill the
disk:

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
```

```bash
sudo systemctl restart docker
```

**Disk pressure:** old images accumulate with every rebuild.

```bash
docker system df
docker image prune -a -f       # safe: rebuilds pull what they need
```

**Monitoring:** point any uptime checker (UptimeRobot, Better Stack, Healthchecks.io) at
`https://app.yourdomain.com/api/health/db` every 5 minutes. It catches a wedged database, which
`/api/health` alone will not.

---

# Part C — Doing both at once

Order matters. Databases first, hosting second, DNS last:

1. **Part B, steps B1–B7** — build the VPS with its own empty Postgres and prove the stack runs on
   a temporary hostname or the raw IP.
2. **Part A, steps A1–A4** — freeze writes on Vercel and dump Neon.
3. **Part B, step B8** — restore the dump into the VPS Postgres.
4. **Part A, steps A8, A12** — verify counts and `alembic_version`, apply pending migrations.
5. **Part B, steps B9–B12** — TLS, Google origins, full verification checklist.
6. **Part B, step B13** — flip DNS. Users are back.
7. **Parts A14 / B14** — decommission Neon and Vercel after a grace period.

Total write-freeze window is roughly steps 2–4 — typically 15–30 minutes for a database this size.

---

# Appendix — environment variable reference

Every variable the backend reads, from [`backend/app/core/config.py`](backend/app/core/config.py).

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | Runtime. Any Postgres form accepted; rewritten to `+asyncpg`. |
| `DATABASE_URL_SYNC` | *(derived)* | Alembic. Set separately when your app URL points at a pooler. |
| `DB_POOL_SIZE` | `5` | Per instance. |
| `DB_MAX_OVERFLOW` | `5` | Per instance. |
| `DB_POOL_RECYCLE_SECONDS` | `300` | Recycle before an idle proxy drops the socket. |
| `DB_DISABLE_PREPARED_STATEMENTS` | `false` | Auto-on for Neon `-pooler` hosts, port `6543`, and `pgbouncer` URLs. |
| `SECRET_KEY` | `change-me` | ≥32 random chars in production; startup fails otherwise. |
| `JWT_SECRET_KEY` | `change-me` | Must differ from `SECRET_KEY`. Changing it invalidates all sessions. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated. Exact scheme + host, no trailing slash. |
| `ENVIRONMENT` | `development` | `production` activates the startup guardrails. |
| `APP_NAME` | `Inventory Management` | Shown in the UI and API title. |
| `ARGON2_TIME_COST` | `2` | OWASP minimum. Raise only if you measure spare CPU. |
| `ARGON2_MEMORY_KIB` | `19456` | 19 MiB. |
| `ARGON2_PARALLELISM` | `1` | Match available cores; `4` on a 1-vCPU box only causes contention. |
| `GOOGLE_CLIENT_ID` | *(empty)* | Empty disables Google sign-in entirely. |
| `GOOGLE_ALLOW_SIGNUP` | `true` | `false` = admins must create accounts first. |
| `GOOGLE_SIGNUP_ROLE` | `viewer` | Role for self-provisioned accounts. |
| `GOOGLE_ALLOWED_DOMAINS` | *(empty)* | Comma-separated; empty allows any domain. |

Compose-only, read by [`docker-compose.yml`](docker-compose.yml):

| Variable | Default | Notes |
| --- | --- | --- |
| `POSTGRES_USER` | `inventory` | |
| `POSTGRES_PASSWORD` | *(required)* | Compose refuses to start without it. |
| `POSTGRES_DB` | `inventory` | |
| `HTTP_PORT` | `8080` | Host port the proxy binds. |

Argon2 parameters are encoded inside each stored hash, so changing the cost settings never locks
anyone out — existing hashes still verify, and each user's hash is transparently upgraded on their
next successful sign-in.

---

# Appendix — troubleshooting

**`The asyncio extension requires an async driver to be used`**
`DATABASE_URL` reached SQLAlchemy as a plain `postgresql://` URL. Normally
[`_rewrite_pg_url()`](backend/app/core/config.py) handles this — so check for a stray leading space
or quote in the value, which stops the URL parser from recognising the scheme.

**`invalid connection option "channel_binding"` / unexpected keyword argument `pgbouncer`**
Provider-specific query parameters reaching asyncpg. [`_rewrite_pg_url()`](backend/app/core/config.py)
keeps only the parameters asyncpg understands, so check for a stray leading space or quote in the
value that stopped the URL parser recognising the scheme.

**`prepared statement "__asyncpg_stmt_1__" already exists`**
A transaction-mode pooler that wasn't auto-detected. Set `DB_DISABLE_PREPARED_STATEMENTS=true`.

**`permission denied for schema public`** during restore
PostgreSQL 15+ default. Run the `GRANT ALL ON SCHEMA public` / `ALTER SCHEMA public OWNER TO` pair
from [A6](#a6-create-the-database-role-and-database-on-the-target).

**`role "neondb_owner" does not exist`**
The dump was taken without `--no-owner`. Re-dump with the flags in
[A4](#a4-dump-the-database), or add `--no-owner` to `pg_restore`.

**App starts, every endpoint 500s, logs say `RBAC bootstrap skipped`**
The schema isn't there. Run `alembic upgrade head` with `DATABASE_URL_SYNC` set, then restart.

**`Unsafe production configuration` and the container exits**
Working as intended — the message lists exactly which variables are wrong. Fix them in `.env`.

**`duplicate key value violates unique constraint` on the first create after a migration**
Sequences are behind. Run the `setval` fix in [A8](#a8-verify-the-restore).

**Frontend loads, API calls 404**
nginx isn't forwarding `/api/`. Check [`frontend/nginx.conf`](frontend/nginx.conf) and
[`nginx/nginx.conf`](nginx/nginx.conf) reached the containers: `docker compose exec nginx nginx -t`.

**Frontend loads, API calls blocked by CORS**
`CORS_ORIGINS` doesn't match the browser's origin exactly. `https://app.example.com` and
`https://app.example.com/` are different values; so are the `http` and `https` forms.

**Deep links 404 on refresh but work when navigated to**
The SPA fallback is missing. `try_files $uri $uri/ /index.html;` must be present in
[`frontend/nginx.conf`](frontend/nginx.conf).

**`npm run build` killed during `docker compose build`**
Out of memory. Add swap:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
