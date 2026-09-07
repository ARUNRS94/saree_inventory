from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger("uvicorn.error")


async def _bootstrap() -> None:
    from sqlalchemy import func, select

    from app.core.database import async_session_factory
    from app.models.role import Role
    from app.services.auth_service import ensure_default_admin
    from app.services.rbac_service import seed_rbac

    async with async_session_factory() as session:
        if not await session.scalar(select(func.count()).select_from(Role)):
            await seed_rbac(session)
        await ensure_default_admin(session)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import Base
    import app.models  # noqa: F401  (register all mappers)

    # Alembic owns the schema everywhere except local SQLite development.
    if settings.DATABASE_URL.startswith("sqlite"):
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

from app.api.routes import access, auth, dashboard, sarees, suppliers, vendors, purchase_orders, grns, job_work, inventory, reports
from app.api.routes import settings as settings_routes

for router in [auth.router, access.router, dashboard.router, sarees.router, suppliers.router,
               vendors.router, purchase_orders.router, grns.router,
               job_work.router, inventory.router, reports.router, settings_routes.router]:
    app.include_router(router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
