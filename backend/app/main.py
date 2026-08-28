from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.security import hash_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import Base, async_session_factory
    from app.models import User  # noqa: F811

    # Auto-create tables when using SQLite (local dev without Alembic)
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        from sqlalchemy import text
        result = await session.execute(text("SELECT count(*) FROM users"))
        count = result.scalar()
        if count == 0:
            session.add(User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="Administrator",
                role="admin",
            ))
            await session.commit()
    yield
    await engine.dispose()


app = FastAPI(title="TextiLedger API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import auth, dashboard, sarees, suppliers, vendors, purchase_orders, grns, job_work, inventory, reports
from app.api.routes import settings as settings_routes

for router in [auth.router, dashboard.router, sarees.router, suppliers.router,
               vendors.router, purchase_orders.router, grns.router,
               job_work.router, inventory.router, reports.router, settings_routes.router]:
    app.include_router(router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
