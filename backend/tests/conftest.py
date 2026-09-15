"""Shared fixtures. Every test gets a fresh in-memory SQLite schema with RBAC seeded."""
from __future__ import annotations

from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models import *  # noqa: F401,F403  (register every mapper)
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseLine, PurchaseService
from app.services.rbac_service import seed_rbac

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        await seed_rbac(session)
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def masters(db: AsyncSession) -> MasterService:
    return MasterService(db)


@pytest_asyncio.fixture
async def purchase(db: AsyncSession) -> PurchaseService:
    return PurchaseService(db)


@pytest_asyncio.fixture
async def stocked_rm(db: AsyncSession):
    """An RM item holding 100 units, received against a Raw Material Vendor PO at rate 50."""
    master = MasterService(db)
    contact = await master.create_contact("RM Vendor A", "Raw Material Vendor")
    item = await master.create_item("RM100", "Grey Fabric", item_type="RM")
    await db.flush()

    svc = PurchaseService(db)
    po = await svc.create_po(contact.contact_id, [PurchaseLine(item.item_id, 100, Decimal("50"))])
    await svc.receive_grn(po.po_id, [(item.item_id, 100, 0, Decimal("50"))])
    await db.flush()
    return {"contact": contact, "item": item, "po": po}
