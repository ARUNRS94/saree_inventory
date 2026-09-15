"""Shared fixtures. Every test gets a fresh in-memory SQLite schema with RBAC seeded."""
from __future__ import annotations

from types import SimpleNamespace

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models import *  # noqa: F401,F403  (register every mapper)
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.services.rbac_service import seed_rbac
from factories import DataBuilder, SampleData

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
async def build(db: AsyncSession) -> DataBuilder:
    return DataBuilder(db)


@pytest_asyncio.fixture
async def sample(build: DataBuilder) -> SampleData:
    """The full master catalogue, with no transactions against it."""
    return await build.masters()


@pytest_asyncio.fixture
async def scenario(db: AsyncSession, build: DataBuilder):
    """Masters plus a realistic spread of purchase orders.

    Leaves cotton at 70 on hand (100 received, 30 sent for dyeing), silk at 25,
    dyeing at 30 in WIP, and one PO in each of CLOSED / PARTIAL / OPEN.
    """
    data = await build.masters()
    closed_po = await build.buy(data.alpha, data.cotton, 100, "50", receive=100)
    partial_po = await build.buy(data.bharat, data.silk, 60, "120", receive=25)
    open_po = await build.buy(data.alpha, data.cotton, 40, "55")
    sub_po = await build.send_for_processing(
        data.dye_house, data.dyeing, 30, "15",
        stock_out=data.cotton, target_fg=data.cotton_saree,
    )
    await db.flush()
    return SimpleNamespace(
        data=data, closed_po=closed_po, partial_po=partial_po, open_po=open_po, sub_po=sub_po,
    )


@pytest_asyncio.fixture
async def stocked_rm(build: DataBuilder):
    """An RM item holding 100 units, received against a Raw Material Vendor PO at rate 50."""
    contact = await build.contact("RM Vendor A", "Raw Material Vendor")
    item = await build.item("RM100", "Grey Fabric", item_type="RM")
    po = await build.buy(contact, item, 100, "50", receive=100)
    return {"contact": contact, "item": item, "po": po}
