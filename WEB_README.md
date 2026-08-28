# Saree Inventory & Job Work Management System

A responsive web-based ERP application for managing saree inventory, purchases, goods receipts, and job work operations. Converted from a PySide6 desktop application to a modern web stack.

## Architecture

```
React (TypeScript + Tailwind CSS)
        ↓
   Axios API Client
        ↓
  FastAPI REST API (/api/v1/)
        ↓
   Service Layer
        ↓
   SQLAlchemy 2.x
        ↓
    PostgreSQL 16
```

## Tech Stack

| Layer          | Technology                          |
|----------------|-------------------------------------|
| Frontend       | React 18, TypeScript, Vite, Tailwind CSS |
| Backend        | Python, FastAPI, Pydantic, SQLAlchemy 2.x |
| Database       | PostgreSQL 16                       |
| Auth           | JWT (access + refresh), Argon2      |
| Reports        | ReportLab (PDF), CSV export         |
| Migrations     | Alembic                             |
| Deployment     | Docker, Docker Compose, Nginx       |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── core/                # Config, database, security
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # Business logic
│   │   └── api/routes/          # REST endpoints
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # pytest tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # React pages
│   │   ├── components/          # Reusable UI components
│   │   ├── layouts/             # App layout with sidebar
│   │   ├── contexts/            # Auth context
│   │   ├── services/            # API client
│   │   ├── types/               # TypeScript interfaces
│   │   └── utils/               # Formatters
│   ├── package.json
│   └── Dockerfile
├── nginx/                       # Reverse proxy config
├── docker-compose.yml
├── migrate_sqlite_to_postgres.py
└── .env.example
```

## Quick Start (Docker)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start all services
docker compose up -d

# 3. Access the application
#    Frontend: http://localhost:80
#    API:      http://localhost:8000/docs
#    Nginx:    http://localhost:8080
```

Default credentials: `admin` / `admin123`

## Local Development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

# Start PostgreSQL (via Docker or local install)
docker compose up postgres -d

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173, proxies /api to backend
```

### Running Tests

```bash
cd backend
pip install pytest pytest-asyncio aiosqlite
pytest tests/ -v
```

## Database Setup

The application uses PostgreSQL. Alembic handles schema migrations:

```bash
cd backend
alembic upgrade head       # Apply migrations
alembic revision --autogenerate -m "description"  # Generate new migration
```

## SQLite Migration

To migrate data from the existing SQLite database:

```bash
# Ensure PostgreSQL is running and migrations are applied
python migrate_sqlite_to_postgres.py --sqlite inventory.db
```

The script will:
1. Back up the original SQLite file
2. Copy all data to PostgreSQL
3. Validate record counts for all tables
4. Compare stock balances by saree

## Environment Variables

| Variable                     | Description                |
|------------------------------|----------------------------|
| `DATABASE_URL`               | PostgreSQL async URL       |
| `SECRET_KEY`                 | Application secret         |
| `JWT_SECRET_KEY`             | JWT signing key            |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Access token TTL           |
| `REFRESH_TOKEN_EXPIRE_DAYS`  | Refresh token TTL          |
| `CORS_ORIGINS`               | Allowed CORS origins       |
| `POSTGRES_USER`              | PostgreSQL user            |
| `POSTGRES_PASSWORD`          | PostgreSQL password        |
| `POSTGRES_DB`                | PostgreSQL database name   |

## Key Business Rules (Preserved)

- **Contact types**: RM vendor, Sub vendor, Customer
- **Item types**: RM (raw material), Sub process (WIP), FG (finished good)
- **RM vendor PO**: Stocks in RM items only
- **Sub vendor PO**: Issues RM/FG stock out → WIP stock in → GRN receives FG
- **GRN**: Validates against pending PO quantity
- **Job work issue**: Checks stock availability before issuing
- **Job work receipt**: Validates against pending issue quantity
- **PO cancel**: Only allowed if no GRN received; reverses WIP movements for sub vendors
- **Stock ledger**: Immutable transaction log with polymorphic reference_no
- **Inventory valuation**: Current stock × latest PO rate (cascading fallback)
- **Document numbering**: PREFIX-YYYY-NNNN format

## API Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Production Deployment

```bash
# Build and start in detached mode
docker compose up -d --build

# Nginx routes:
#   /       → React frontend
#   /api/   → FastAPI backend
```

## Backup

```bash
# Database backup
docker compose exec postgres pg_dump -U saree_user saree_inventory > backup.sql

# Restore
docker compose exec -T postgres psql -U saree_user saree_inventory < backup.sql
```
