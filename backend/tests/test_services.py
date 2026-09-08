import asyncio
from decimal import Decimal
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models import *  # noqa: F401,F403
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseLine, PurchaseService
from app.services.jobwork_service import JobWorkService
from app.services.inventory_service import InventoryService
from app.services.dashboard_service import DashboardService
from app.services.auth_service import AuthService
from app.services.rbac_service import seed_rbac

# Use SQLite for tests
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


# --- Master Data ---

@pytest.mark.asyncio
async def test_create_supplier(db: AsyncSession):
    svc = MasterService(db)
    # The legacy "RM vendor" spelling must still resolve to the current value.
    contact = await svc.create_contact("Test Contact", "RM vendor", phone="1234")
    assert contact.contact_id is not None
    assert contact.contact_name == "Test Contact"
    assert contact.contact_type == "Raw Material Vendor"


@pytest.mark.asyncio
async def test_create_vendor(db: AsyncSession):
    svc = MasterService(db)
    await svc.create_process_type("Finishing")
    vendor = await svc.create_vendor("Test Vendor", "Finishing")
    assert vendor.vendor_id is not None
    assert vendor.process_type == "Finishing"


@pytest.mark.asyncio
async def test_create_item(db: AsyncSession):
    svc = MasterService(db)
    item = await svc.create_item("RM001", "Raw Material 1", item_type="RM")
    assert item.item_id is not None
    assert item.item_code == "RM001"
    assert item.item_type == "RM"


@pytest.mark.asyncio
async def test_invalid_item_type(db: AsyncSession):
    svc = MasterService(db)
    with pytest.raises(ValueError, match="valid item type"):
        await svc.create_item("X001", "Bad", item_type="INVALID")


# --- Purchase Order ---

@pytest.mark.asyncio
async def test_create_po_and_grn(db: AsyncSession):
    master = MasterService(db)
    contact = await master.create_contact("RM Contact", "RM vendor")
    item = await master.create_item("RM001", "Raw Material", item_type="RM")
    await db.flush()

    purchase = PurchaseService(db)
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 100, Decimal("50"))])
    assert po.po_number.startswith("PO-")
    assert po.status == "OPEN"

    # Partial GRN
    grn = await purchase.receive_grn(po.po_id, [(item.item_id, 50, 0, Decimal("50"))])
    assert grn.grn_number.startswith("GRN-")
    await db.flush()
    await db.refresh(po)
    assert po.status == "PARTIAL"

    # Full GRN
    grn2 = await purchase.receive_grn(po.po_id, [(item.item_id, 50, 0, Decimal("50"))])
    await db.flush()
    await db.refresh(po)
    assert po.status == "CLOSED"

    # Stock check
    stock = await InventoryService(db).current_stock(item.item_id)
    assert stock == 100


@pytest.mark.asyncio
async def test_excess_grn_validation(db: AsyncSession):
    master = MasterService(db)
    contact = await master.create_contact("RM Contact", "RM vendor")
    item = await master.create_item("RM002", "Raw Material 2", item_type="RM")
    await db.flush()

    purchase = PurchaseService(db)
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("50"))])
    with pytest.raises(ValueError, match="exceeds pending"):
        await purchase.receive_grn(po.po_id, [(item.item_id, 15, 0, Decimal("50"))])


# --- Job Work ---

@pytest.mark.asyncio
async def test_jobwork_issue_and_receipt(db: AsyncSession):
    master = MasterService(db)
    contact = await master.create_contact("RM Sup", "RM vendor")
    item = await master.create_item("FG001", "Finished Good", item_type="RM")
    vendor = await master.create_vendor("JW Vendor", "Finishing")
    await db.flush()

    # Create stock
    purchase = PurchaseService(db)
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 50, Decimal("100"))])
    await purchase.receive_grn(po.po_id, [(item.item_id, 50, 0, Decimal("100"))])

    # Issue
    jw = JobWorkService(db)
    issue = await jw.issue(vendor.vendor_id, [(item.item_id, 20)])
    assert issue.issue_no.startswith("JWISS-")
    assert issue.status == "OPEN"

    stock_after_issue = await InventoryService(db).current_stock(item.item_id)
    assert stock_after_issue == 30

    # Receipt
    receipt = await jw.receive(issue.issue_id, vendor.vendor_id, [(item.item_id, 18, 2, Decimal("25"))])
    assert receipt.receipt_no.startswith("JWREC-")
    await db.flush()
    await db.refresh(issue)
    assert issue.status == "CLOSED"

    stock_after_receipt = await InventoryService(db).current_stock(item.item_id)
    assert stock_after_receipt == 48  # 30 + 18 received


@pytest.mark.asyncio
async def test_insufficient_stock_for_issue(db: AsyncSession):
    master = MasterService(db)
    item = await master.create_item("FG002", "FG Item", item_type="RM")
    vendor = await master.create_vendor("V1", "Finishing")
    await db.flush()

    jw = JobWorkService(db)
    with pytest.raises(ValueError, match="Insufficient stock"):
        await jw.issue(vendor.vendor_id, [(item.item_id, 10)])


@pytest.mark.asyncio
async def test_vendor_pending_qty(db: AsyncSession):
    master = MasterService(db)
    contact = await master.create_contact("Sup", "RM vendor")
    item = await master.create_item("IT001", "Item", item_type="RM")
    vendor = await master.create_vendor("V", "Finishing")
    await db.flush()

    purchase = PurchaseService(db)
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 20, Decimal("10"))])
    await purchase.receive_grn(po.po_id, [(item.item_id, 20, 0, Decimal("10"))])

    jw = JobWorkService(db)
    issue = await jw.issue(vendor.vendor_id, [(item.item_id, 15)])
    pending = await jw.pending_issue_qty(issue.issue_id, item.item_id)
    assert pending == 15

    await jw.receive(issue.issue_id, vendor.vendor_id, [(item.item_id, 10, 0, Decimal("5"))])
    pending2 = await jw.pending_issue_qty(issue.issue_id, item.item_id)
    assert pending2 == 5


# --- Cancel PO ---

@pytest.mark.asyncio
async def test_cancel_po(db: AsyncSession):
    master = MasterService(db)
    contact = await master.create_contact("Sup", "RM vendor")
    item = await master.create_item("RM010", "RM", item_type="RM")
    await db.flush()

    purchase = PurchaseService(db)
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("50"))])
    cancelled = await purchase.cancel_po(po.po_id)
    assert cancelled.status == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_po_after_grn_fails(db: AsyncSession):
    master = MasterService(db)
    contact = await master.create_contact("Sup", "RM vendor")
    item = await master.create_item("RM011", "RM", item_type="RM")
    await db.flush()

    purchase = PurchaseService(db)
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("50"))])
    await purchase.receive_grn(po.po_id, [(item.item_id, 5, 0, Decimal("50"))])
    with pytest.raises(ValueError, match="Cannot cancel"):
        await purchase.cancel_po(po.po_id)


# --- Dashboard ---

@pytest.mark.asyncio
async def test_dashboard(db: AsyncSession):
    master = MasterService(db)
    await master.create_contact("Sup", "RM vendor")
    await master.create_item("IT1", "Item", item_type="RM")
    await db.flush()

    dash = DashboardService(db)
    result = await dash.get_dashboard()
    assert result.cards.active_items >= 1
    assert result.cards.active_contacts >= 1


# --- Auth ---

@pytest.mark.asyncio
async def test_auth_register_and_login(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("testuser", "password123", "Test User", role="manager")
    assert user.username == "testuser"
    assert user.role == "manager"
    assert "reports" in user.permissions

    access, refresh, logged = await auth.login("testuser", "password123")
    assert access
    assert refresh


@pytest.mark.asyncio
async def test_auth_invalid_login(db: AsyncSession):
    auth = AuthService(db)
    await auth.register("testuser2", "password123", "Test")
    with pytest.raises(ValueError, match="Invalid"):
        await auth.login("testuser2", "wrongpassword")
