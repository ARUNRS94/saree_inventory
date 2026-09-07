# Deployment guides

- [Deploying to Vercel (containers)](#deploying-inventory-management-to-vercel) — recommended
- [Deploying to a Hostinger VPS](#deploying-inventory-management-to-a-hostinger-vps)

---

## Deploying Inventory Management to Vercel

Vercel Functions can run OCI container images built from a `Dockerfile.vercel`. Using
[Services](https://vercel.com/docs/services), the React frontend and the FastAPI backend run as two
containers inside a **single** Vercel project, behind one domain:

```
Vercel project (one domain)
├── service "frontend"  frontend/Dockerfile.vercel   nginx + React build
├── service "backend"   backend/Dockerfile.vercel    uvicorn + FastAPI
└── rewrites            /api/* → backend,  /* → frontend

Neon / Vercel Postgres (external, managed)   ← the database cannot live in the container
```

> **The database must be external.** Container filesystems are ephemeral and instances scale to zero,
> so Postgres cannot run inside the deployment. Anything written to disk is lost on scale-down —
> which is why the logo *upload* feature was replaced with a logo *URL* field.

### 1. Create the database
Add a Postgres store from the Vercel dashboard (**Storage → Create → Neon**), or sign up at
[neon.tech](https://neon.tech) directly. Copy two connection strings:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db` — used by the app at runtime |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://user:pass@host/db` — used by Alembic |

If the host contains `-pooler` (Neon's PgBouncer endpoint), also set `DB_DISABLE_PREPARED_STATEMENTS=true`.
Transaction-mode poolers reject asyncpg's prepared statements, and you'll otherwise hit
`prepared statement "__asyncpg_stmt_1__" already exists` under load.

### 2. Run migrations
Vercel has no release hook, so run migrations yourself before the first deploy and after any schema change:

```bash
cd backend
$env:DATABASE_URL_SYNC="postgresql+psycopg2://user:pass@host/db"   # PowerShell
alembic upgrade head
```

The app tolerates an unmigrated database on boot — it logs
`RBAC bootstrap skipped - run 'alembic upgrade head'` instead of crash-looping — but no endpoint will
work until this succeeds. Once the tables exist, the first boot seeds the roles, permissions and the
default `admin` / `admin123` account.

### 3. Set environment variables
In **Project → Settings → Environment Variables**, add for Production (and Preview if you use it):

```
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
DATABASE_URL_SYNC=postgresql+psycopg2://user:pass@host/db
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
JWT_SECRET_KEY=<a second, different value>
CORS_ORIGINS=https://your-project.vercel.app
ENVIRONMENT=production
APP_NAME=Inventory Management
```

Optional Google sign-in — add `https://your-project.vercel.app` to the Authorised JavaScript origins
of your OAuth client first:

```
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_ALLOW_SIGNUP=false
GOOGLE_SIGNUP_ROLE=viewer
GOOGLE_ALLOWED_DOMAINS=yourdomain.com
```

Do **not** set `PORT`. Vercel routes to port `80`, which both containers already listen on.

### 4. Deploy
```bash
npm i -g vercel
vercel link
vercel --prod
```

Vercel reads [vercel.json](vercel.json), builds both `Dockerfile.vercel` images, pushes them to the
Vercel Container Registry, and wires up the rewrites. Connecting the Git repo instead gives you the
same build on every push, with preview deployments per branch.

To test the exact container images locally first (requires a running Docker daemon):

```bash
vercel dev
```

### 5. Post-deploy checks
1. `https://your-project.vercel.app/api/health` → `{"status":"ok"}`
2. Sign in with `admin` / `admin123`, then **immediately** change the password under User Management.
3. Check **Observability → Logs** for the container's stdout if anything 500s.

### Operational notes

| Topic | Behaviour |
| --- | --- |
| **Cold starts** | Instances scale to zero after 5 min idle (30 s on preview). The first request afterwards pays container startup plus a DB connection. |
| **Shutdown** | Vercel sends `SIGTERM` with a 30 s grace period; uvicorn's lifespan disposes the connection pool so Neon connections are released cleanly. |
| **Pooling** | Each instance holds its own pool. `DB_POOL_SIZE` (default 5) × concurrent instances must stay under your Postgres connection limit — use Neon's pooled endpoint if you scale out. |
| **PDF/Excel exports** | Bound by the Vercel Functions max duration (see your plan's limits). Large report exports are the most likely thing to hit it. |
| **Billing** | Active CPU pricing — you're billed for CPU while code runs, not while idle or waiting on I/O. |
| **Not supported** | Secure Compute and Static IPs do not currently work with custom container images. |

---

## Deploying Inventory Management to a Hostinger VPS

Your app is already Docker-composed (Postgres + FastAPI backend + React/nginx frontend + reverse-proxy nginx), so the cleanest path is Docker Compose on the VPS, fronted by a host-level Nginx + Let's Encrypt for HTTPS. Steps below.

### 1. Provision the VPS
- In Hostinger hPanel, create a VPS (Ubuntu 22.04/24.04 LTS recommended). Note the public IP.
- Point your domain's DNS **A record** to that IP (e.g. `app.yourdomain.com`), and wait for propagation (`nslookup app.yourdomain.com`).

### 2. Initial server hardening
```bash
ssh root@YOUR_VPS_IP
adduser deploy && usermod -aG sudo deploy
# copy your SSH key to the new user, then disable root/password SSH login in /etc/ssh/sshd_config
apt update && apt upgrade -y
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
```

### 3. Install Docker & Compose
```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
apt install -y docker-compose-plugin
```
Log out/in as `deploy` so the docker group applies.

### 4. Get the code onto the server
```bash
sudo mkdir -p /opt/inventory-management && sudo chown deploy:deploy /opt/inventory-management
cd /opt/inventory-management
git clone <your-repo-url> .
```

### 5. Configure production environment
Copy `.env.example` to `.env` and edit it — this is the most important step:

```bash
cp .env.example .env
nano .env
```
Set:
- `POSTGRES_PASSWORD` → a strong random password
- `DATABASE_URL` → keep `postgresql+asyncpg://<user>:<pass>@postgres:5432/<db>` (note: **host must be `postgres`**, the compose service name, not `localhost`)
- `SECRET_KEY` / `JWT_SECRET_KEY` → generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `CORS_ORIGINS=https://app.yourdomain.com`
- `ENVIRONMENT=production`

Optional — Google sign-in / sign-up:
- `GOOGLE_CLIENT_ID` → OAuth 2.0 Web client ID from the Google Cloud console. Add `https://app.yourdomain.com` under *Authorised JavaScript origins*.
- `GOOGLE_ALLOW_SIGNUP=false` → set to `false` to require an administrator to create accounts before anyone can sign in.
- `GOOGLE_SIGNUP_ROLE=viewer` → role granted to self-provisioned accounts.
- `GOOGLE_ALLOWED_DOMAINS=yourdomain.com` → restrict sign-in to your own Google Workspace domain(s).

### 6. Fix production-unsafe defaults in `docker-compose.yml`
Two changes needed before going live, in `docker-compose.yml`:
1. Remove `--reload` from the backend `command` (auto-reload is for dev only, wastes resources).
2. Don't publish Postgres port `5432:5432` to the internet — remove that `ports:` entry so Postgres is only reachable from other containers on the compose network.

I can make these edits now if you'd like — say the word and I'll apply them.

### 7. Build and start
```bash
docker compose up -d --build
docker compose ps          # confirm all healthy
docker compose logs -f backend   # check migrations ran clean
```
This runs `alembic upgrade head` automatically (per the backend `command` in compose), then starts uvicorn.

### 8. Put a host-level Nginx + HTTPS in front
Your compose already has an internal `nginx` proxy on port `8080`, routing `/` → frontend and `/api/` → backend. On the VPS, install a system Nginx that terminates TLS and forwards to that port:
```bash
apt install -y nginx certbot python3-certbot-nginx
```
Create `/etc/nginx/sites-available/inventory-management`:
```nginx
server {
    listen 80;
    server_name app.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
ln -s /etc/nginx/sites-available/inventory-management /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d app.yourdomain.com   # issues + auto-configures HTTPS, sets up renewal
```

### 9. Verify
- `https://app.yourdomain.com` → frontend
- `https://app.yourdomain.com/api/docs` → Swagger UI
- Log in with default `admin` / `admin123`, then **change that password immediately**.

### 10. Ongoing operations
- **Deploy updates**: `git pull && docker compose up -d --build`
- **Backups**: cron a nightly `docker compose exec postgres pg_dump -U saree_user saree_inventory > backup-$(date +%F).sql`, copy off-box (e.g. rclone to S3/Backblaze).
- **Logs**: `docker compose logs -f <service>`
- **Restart on reboot**: add `restart: unless-stopped` to each service in compose (currently missing).
- **Resource sizing**: Postgres + FastAPI + Node build + Nginx comfortably runs on Hostinger's smallest KVM plan (1 vCPU/4GB) for light traffic; go 2 vCPU/8GB if concurrent users grow.

Want me to apply the compose/security fixes (remove `--reload`, unpublish Postgres port, add `restart: unless-stopped`) directly to the repo now?