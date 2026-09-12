from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger("uvicorn.error")


async def _bootstrap() -> None:
    from sqlalchemy import func, select

    from app.core.database import async_session_factory
    from app.models.role import PERMISSION_CATALOGUE, Permission
    from app.services.auth_service import ensure_default_admin
    from app.services.rbac_service import seed_rbac

    async with async_session_factory() as session:
        # One cheap check: a short catalogue means new permissions need seeding and granting.
        known = await session.scalar(select(func.count()).select_from(Permission)) or 0
        if known < len(PERMISSION_CATALOGUE):
            await seed_rbac(session)
        await ensure_default_admin(session)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import Base
    import app.models  # noqa: F401  (register all mappers)

    problems = settings.validate_for_production()
    if problems:
        raise RuntimeError("Unsafe production configuration:\n  - " + "\n  - ".join(problems))

    logger.info("Database target: %s (prepared statements %s)", settings.database_target,
                "off" if settings.disable_prepared_statements else "on")

    # Alembic owns the schema everywhere except local SQLite development.
    if settings.is_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    try:
        await _bootstrap()
    except Exception:
        logger.exception("RBAC bootstrap skipped - run 'alembic upgrade head' against this database.")
    yield
    await engine.dispose()


app = FastAPI(title=f"{settings.APP_NAME} API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import access, auth, dashboard, items, contacts, vendors, purchase_orders, grns, job_work, inventory, reports, imports
from app.api.routes import settings as settings_routes

for router in [auth.router, access.router, dashboard.router, items.router, contacts.router,
               vendors.router, purchase_orders.router, grns.router,
               job_work.router, inventory.router, reports.router,
               imports.router, imports.export_router, settings_routes.router]:
    app.include_router(router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.get("/api/health/db")
async def health_db():
    """Readiness probe: confirms the database is reachable."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        # Logged per-request so the target is visible even where start-up logs are not.
        logger.error("Database unreachable at %s -> %s: %s", settings.database_target,
                     type(exc).__name__, exc)
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": type(exc).__name__})
    return {"status": "ok"}
