"""Reusable test data.

`SampleData` is a small textile business: raw materials, sub-process items and finished
goods, the three kinds of contact, and vendors for each process. `DataBuilder` turns that
into rows, and also builds the transactions that put stock on the shelf.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.item import Item
from app.models.vendor import Vendor
from app.services.inventory_service import InventoryService
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseLine, PurchaseService

# --- catalogue -------------------------------------------------------------

ITEMS: list[tuple[str, str, str, str | None, str | None]] = [
    # code, name, type, colour, remarks
    ("RM-COT-01", "Cotton Grey Fabric", "RM", "White", "Plain weave"),
    ("RM-SLK-01", "Silk Yarn", "RM", "Gold", "22 denier"),
    ("SP-DYE-01", "Dyeing Process", "Sub process", None, "Reactive dye"),
    ("SP-PRT-01", "Printing Process", "Sub process", None, "Screen print"),
    ("FG-SAR-01", "Cotton Saree", "FG", "Red", "6 yard"),
    ("FG-SAR-02", "Silk Saree", "FG", "Maroon", "6.5 yard"),
]

CONTACTS: list[tuple[str, str, str, str]] = [
    # name, type, contact person, phone
    ("Alpha Mills", "Raw Material Vendor", "Ravi", "9800000001"),
    ("Bharat Yarns", "Raw Material Vendor", "Suresh", "9800000002"),
    ("Sri Dyeing Works", "Sub vendor", "Kumar", "9800000003"),
    ("Kumar Printers", "Sub vendor", "Anita", "9800000004"),
    ("Retail Hub", "Customer", "Meena", "9800000005"),
]

PROCESS_TYPES = ["Dyeing", "Printing", "Finishing"]

VENDORS: list[tuple[str, str]] = [
    ("Sri Dyeing Works", "Dyeing"),
    ("Kumar Printers", "Printing"),
]


@dataclass
class SampleData:
    """Named handles for everything the builder created."""

    items: dict[str, Item]
    contacts: dict[str, Contact]
    vendors: dict[str, Vendor]

    # Convenience accessors, so tests read as prose rather than dictionary lookups.
    @property
    def cotton(self) -> Item:
        return self.items["RM-COT-01"]

    @property
    def silk(self) -> Item:
        return self.items["RM-SLK-01"]

    @property
    def dyeing(self) -> Item:
        return self.items["SP-DYE-01"]

    @property
    def printing(self) -> Item:
        return self.items["SP-PRT-01"]

    @property
    def cotton_saree(self) -> Item:
        return self.items["FG-SAR-01"]

    @property
    def silk_saree(self) -> Item:
        return self.items["FG-SAR-02"]

    @property
    def alpha(self) -> Contact:
        return self.contacts["Alpha Mills"]

    @property
    def bharat(self) -> Contact:
        return self.contacts["Bharat Yarns"]

    @property
    def dye_house(self) -> Contact:
        return self.contacts["Sri Dyeing Works"]

    @property
    def printer(self) -> Contact:
        return self.contacts["Kumar Printers"]

    @property
    def customer(self) -> Contact:
        return self.contacts["Retail Hub"]


# --- builder ---------------------------------------------------------------

class DataBuilder:
    """Creates rows through the real services, so test data obeys the same rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.master = MasterService(session)
        self.purchase = PurchaseService(session)
        self.inventory = InventoryService(session)

    async def item(self, code: str, name: str | None = None, item_type: str = "FG", **values) -> Item:
        item = await self.master.create_item(code, name or code, item_type=item_type, **values)
        await self.session.flush()
        return item

    async def contact(self, name: str, contact_type: str, **values) -> Contact:
        contact = await self.master.create_contact(name, contact_type, **values)
        await self.session.flush()
        return contact

    async def vendor(self, name: str, process_type: str, **values) -> Vendor:
        vendor = await self.master.create_vendor(name, process_type, **values)
        await self.session.flush()
        return vendor

    async def masters(self) -> SampleData:
        """The full catalogue above, with no transactions against it."""
        items = {}
        for code, name, item_type, colour, remarks in ITEMS:
            items[code] = await self.master.create_item(
                code, name, item_type=item_type, color=colour, remarks=remarks,
            )
        contacts = {}
        for name, contact_type, person, phone in CONTACTS:
            contacts[name] = await self.master.create_contact(
                name, contact_type, contact_person=person, phone=phone,
            )
        for process_type in PROCESS_TYPES:
            await self.master.create_process_type(process_type)
        vendors = {}
        for name, process_type in VENDORS:
            vendors[name] = await self.master.create_vendor(name, process_type)
        await self.session.flush()
        return SampleData(items=items, contacts=contacts, vendors=vendors)

    async def buy(self, contact: Contact, item: Item, qty: int, rate: str | Decimal,
                  receive: int | None = None, damaged: int = 0, po_date: date | None = None):
        """Raise a Raw Material Vendor PO and optionally receive against it."""
        po = await self.purchase.create_po(
            contact.contact_id, [PurchaseLine(item.item_id, qty, Decimal(str(rate)))], po_date=po_date,
        )
        await self.session.flush()
        if receive or damaged:
            await self.purchase.receive_grn(
                po.po_id, [(item.item_id, receive or 0, damaged, Decimal(str(rate)))], grn_date=po_date,
            )
            await self.session.flush()
        return po

    async def send_for_processing(self, sub_vendor: Contact, wip_item: Item, qty: int,
                                  rate: str | Decimal, stock_out: Item, target_fg: Item):
        """Raise a Sub vendor PO: stock_out leaves, wip_item is parked with the vendor."""
        po = await self.purchase.create_po(sub_vendor.contact_id, [
            PurchaseLine(wip_item.item_id, qty, Decimal(str(rate)),
                         stock_out_item_id=stock_out.item_id, target_fg_item_id=target_fg.item_id),
        ])
        await self.session.flush()
        return po

    async def opening_stock(self, item: Item, qty: int, rate: str | Decimal = "0"):
        """Seed stock directly, bypassing the purchase cycle."""
        await self.inventory.post_ledger(
            transaction_date=date.today(), transaction_type="PURCHASE",
            reference_no="OPENING", item_id=item.item_id, qty_in=qty, rate=Decimal(str(rate)),
        )
        await self.session.flush()


# --- CSV helpers -----------------------------------------------------------

def csv_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue().encode("utf-8")


def csv_rows(content: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content)))


ITEMS_CSV = csv_bytes([
    ["code", "name", "type", "remarks", "color"],
    *[[code, name, {"RM": "Raw Material", "Sub process": "Sub Process", "FG": "Finished Goods"}[item_type],
       remarks or "", colour or ""] for code, name, item_type, colour, remarks in ITEMS],
])

CONTACTS_CSV = csv_bytes([
    ["name", "type", "contact_person", "phone", "gst_no", "address"],
    *[[name, contact_type, person, phone, "", ""] for name, contact_type, person, phone in CONTACTS],
])

PROCESS_TYPES_CSV = csv_bytes([["process_type"], *[[p] for p in PROCESS_TYPES]])

VENDORS_CSV = csv_bytes([
    ["name", "process_type", "contact_person", "phone", "gst_no", "address"],
    *[[name, process_type, "", "", "", ""] for name, process_type in VENDORS],
])
