import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { GRN, PurchaseOrder, Item, Contact, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { useConfirmDialog } from '@/components/ConfirmDialog';
import { Modal, DetailField } from '@/components/Modal';
import { formatCurrency, formatDate, sumBy, toNumber } from '@/utils/format';
import { RM_VENDOR, SUB_VENDOR } from '@/utils/contactTypes';

const RAW_MATERIAL = 'RM';
const SUB_VENDOR_GRN = 'SUB';

type GRNLineForm = {
  item_id: string;
  label: string;
  ordered_qty: number;
  received_qty: string;
  damaged_qty: string;
  short_qty: string;
  rate: string;
  lr_number: string;
  po_number: string;
};

const emptyInwardLine = (): GRNLineForm => ({
  item_id: '', label: '', ordered_qty: 0, received_qty: '', damaged_qty: '',
  short_qty: '', rate: '', lr_number: '', po_number: '',
});

export default function GRNPage() {
  const [data, setData] = useState<PaginatedResponse<GRN>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [openPOs, setOpenPOs] = useState<PurchaseOrder[]>([]);
  const [allItems, setAllItems] = useState<Item[]>([]);
  const [rmVendors, setRmVendors] = useState<Contact[]>([]);
  // Sub vendor vouchers track pending quantity at voucher level; RM vendor POs track it per item.
  const [poPendingQty, setPoPendingQty] = useState<number | null>(null);
  const [itemPendingQty, setItemPendingQty] = useState<Record<number, number>>({});
  // Numeric fields are held as strings so the box can be cleared instead of snapping back to 0.
  const [form, setForm] = useState({ grn_type: RAW_MATERIAL, po_id: '', contact_id: '', vendor_voucher_number: '', remarks: '' });
  const [lines, setLines] = useState<GRNLineForm[]>([]);
  const [draft, setDraft] = useState<GRNLineForm>(emptyInwardLine());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [detail, setDetail] = useState<GRN | null>(null);
  const { confirm, dialog } = useConfirmDialog();

  const isRawMaterial = form.grn_type === RAW_MATERIAL;

  const load = useCallback(() => {
    setLoading(true);
    api.get('/grns', { params: { page, page_size: 50, search: search || undefined, grn_type: filterType || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined } }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [page, search, filterType, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get('/purchase-orders', { params: { page_size: 200 } }).then((r) => {
      setOpenPOs(r.data.items.filter((po: PurchaseOrder) => po.status !== 'CLOSED' && po.status !== 'CANCELLED'));
    });
    api.get('/items', { params: { page_size: 500 } }).then((r) => setAllItems(r.data.items));
    api.get('/contacts', { params: { page_size: 200, contact_type: RM_VENDOR } }).then((r) => setRmVendors(r.data.items));
  }, []);

  const rawMaterialItems = allItems.filter((s) => s.item_type === 'RM');
  const selectedPO = openPOs.find((po) => po.po_id === Number(form.po_id));
  const isSubVendorPO = selectedPO?.contact_type === SUB_VENDOR;

  // Every voucher line becomes a receipt row; sub vendor vouchers are received as their target FG item.
  useEffect(() => {
    if (isRawMaterial) return;
    if (!selectedPO) { setLines([]); return; }
    setLines(selectedPO.items.map((poItem) => {
      const isSub = selectedPO.contact_type === SUB_VENDOR;
      const stockInId = isSub ? poItem.target_fg_item_id : poItem.item_id;
      const match = allItems.find((s) => s.item_id === stockInId);
      return {
        item_id: stockInId ? String(stockInId) : '',
        label: match?.item_name ?? poItem.item_name ?? '',
        ordered_qty: poItem.ordered_qty,
        received_qty: '',
        damaged_qty: '',
        short_qty: '',
        rate: String(poItem.rate),
        lr_number: poItem.lr_number ?? '',
        po_number: selectedPO.voucher_number ?? selectedPO.po_number,
      };
    }));
  }, [selectedPO, allItems, isRawMaterial]);

  useEffect(() => {
    if (isRawMaterial || !selectedPO) { setPoPendingQty(null); setItemPendingQty({}); return; }
    const poId = selectedPO.po_id;
    api.get(`/purchase-orders/${poId}/pending-qty`).then((r) => setPoPendingQty(r.data.pending_qty));
    if (selectedPO.contact_type === SUB_VENDOR) { setItemPendingQty({}); return; }
    const itemIds = Array.from(new Set(selectedPO.items.map((i) => i.item_id)));
    Promise.all(itemIds.map((id) =>
      api.get(`/purchase-orders/${poId}/pending-qty`, { params: { item_id: id } })
        .then((r) => [id, r.data.pending_qty] as const)
    )).then((entries) => setItemPendingQty(Object.fromEntries(entries)));
  }, [selectedPO, isRawMaterial]);

  const lineTotal = (line: GRNLineForm) => toNumber(line.received_qty) + toNumber(line.damaged_qty) + toNumber(line.short_qty);
  const lineAmount = (line: GRNLineForm) => toNumber(line.received_qty) * toNumber(line.rate);

  // Pending is shared across rows drawing on the same pool, so other rows' entries come off it.
  const pendingFor = (index: number) => {
    const row = lines[index];
    if (!row?.item_id) return null;
    const reported = isSubVendorPO ? poPendingQty : itemPendingQty[Number(row.item_id)] ?? null;
    if (reported === null) return null;
    const claimedElsewhere = lines.reduce(
      (sum, other, i) => (i !== index && (isSubVendorPO || other.item_id === row.item_id) ? sum + lineTotal(other) : sum),
      0,
    );
    return Math.max(reported - claimedElsewhere, 0);
  };

  const updateLine = (index: number, patch: Partial<GRNLineForm>) =>
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));

  const receiveAllPending = () =>
    setLines((prev) => prev.map((line, i) => {
      const remaining = pendingFor(i);
      return remaining === null ? line : { ...line, received_qty: String(remaining) };
    }));

  const removeLine = (index: number) => setLines((prev) => prev.filter((_, i) => i !== index));

  const addInwardLine = () => {
    if (!draft.item_id) { setError('Select a stock in item.'); return; }
    if (toNumber(draft.received_qty) <= 0) { setError('Quantity must be greater than zero.'); return; }
    if (!draft.po_number.trim()) { setError('PO Number is required.'); return; }
    const match = allItems.find((s) => s.item_id === Number(draft.item_id));
    setError('');
    setLines((prev) => [...prev, { ...draft, label: match?.item_name ?? '' }]);
    setDraft({ ...emptyInwardLine(), lr_number: draft.lr_number, po_number: draft.po_number });
  };

  const switchType = (grn_type: string) => {
    setForm({ grn_type, po_id: '', contact_id: '', vendor_voucher_number: '', remarks: '' });
    setLines([]); setDraft(emptyInwardLine()); setError('');
  };

  const openNew = () => { switchType(RAW_MATERIAL); setShowForm(true); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const received = lines.filter((line) => lineTotal(line) > 0);
    if (received.length === 0) { setError('Enter a quantity on at least one item.'); return; }
    if (!isRawMaterial) {
      const overBooked = lines.findIndex((line, i) => {
        const remaining = pendingFor(i);
        return remaining !== null && lineTotal(line) > remaining;
      });
      if (overBooked >= 0) { setError(`${lines[overBooked].label} exceeds the pending quantity on this voucher.`); return; }
    }
    if (!(await confirm('Save GRN', `Save this GRN with ${received.length} item(s) and post stock movements?`))) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      const res = await api.post('/grns', {
        grn_type: form.grn_type,
        po_id: isRawMaterial ? null : Number(form.po_id),
        contact_id: isRawMaterial && form.contact_id ? Number(form.contact_id) : null,
        grn_date: null,
        vendor_voucher_number: form.vendor_voucher_number || null,
        remarks: form.remarks || null,
        items: received.map((line) => ({
          item_id: Number(line.item_id),
          received_qty: Number(line.received_qty || 0),
          damaged_qty: Number(line.damaged_qty || 0),
          short_qty: Number(line.short_qty || 0),
          rate: Number(line.rate || 0),
          lr_number: line.lr_number || null,
          po_number: line.po_number || null,
        })),
      });
      setSuccess(`GRN ${res.data.grn_number} saved and stock updated.`);
      setShowForm(false); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  return (
    <div>
      {dialog}
      <PageHeader title="Goods Receipt Notes" actions={<button className="btn-primary text-sm" onClick={openNew}>+ Create GRN</button>} />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">New GRN</h3>
          <form onSubmit={save}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div><label className="label">Inward Type *</label>
                <select className="input" value={form.grn_type} onChange={(e) => switchType(e.target.value)}>
                  <option value={RAW_MATERIAL}>Raw Material</option>
                  <option value={SUB_VENDOR_GRN}>Sub Vendor</option>
                </select>
              </div>
              {isRawMaterial ? (
                <div><label className="label">Raw Material Vendor</label>
                  <select className="input" value={form.contact_id} onChange={(e) => setForm({ ...form, contact_id: e.target.value })}>
                    <option value="">Select</option>
                    {rmVendors.map((c) => <option key={c.contact_id} value={c.contact_id}>{c.contact_name}</option>)}
                  </select>
                </div>
              ) : (
                <>
                  <div><label className="label">Voucher *</label>
                    <select className="input" value={form.po_id} onChange={(e) => { setForm({ ...form, po_id: e.target.value }); setError(''); }} required>
                      <option value="">Select</option>
                      {openPOs.map((po) => <option key={po.po_id} value={po.po_id}>{po.voucher_number ?? po.po_number} - {po.contact_name}</option>)}
                    </select>
                  </div>
                  <div><label className="label">Vendor Voucher Number</label>
                    <input className="input" maxLength={50} value={form.vendor_voucher_number}
                      onChange={(e) => setForm({ ...form, vendor_voucher_number: e.target.value })} />
                  </div>
                </>
              )}
              <div className="sm:col-span-2 lg:col-span-3"><label className="label">Remarks (applies to whole GRN)</label>
                <input className="input" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
              </div>
            </div>

            {isRawMaterial && (
              <div className="mt-6 border border-gray-200 rounded-lg p-3">
                <h4 className="font-medium text-sm mb-3">Add Item</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div><label className="label">Stock In Item *</label>
                    <select className="input" value={draft.item_id} onChange={(e) => setDraft({ ...draft, item_id: e.target.value })}>
                      <option value="">Select</option>
                      {rawMaterialItems.map((s) => <option key={s.item_id} value={s.item_id}>{s.item_name}</option>)}
                    </select>
                  </div>
                  <div><label className="label">Quantity *</label>
                    <input className="input" type="number" min={1} value={draft.received_qty}
                      onChange={(e) => setDraft({ ...draft, received_qty: e.target.value })} />
                  </div>
                  <div><label className="label">Rate / Process Charges</label>
                    <input className="input" type="number" min={0} step={0.01} value={draft.rate}
                      onChange={(e) => setDraft({ ...draft, rate: e.target.value })} />
                  </div>
                  <div><label className="label">LR Number</label>
                    <input className="input" maxLength={50} value={draft.lr_number}
                      onChange={(e) => setDraft({ ...draft, lr_number: e.target.value })} />
                  </div>
                  <div><label className="label">Amount</label><p className="input bg-gray-50">{formatCurrency(lineAmount(draft))}</p></div>
                  <div><label className="label">PO Number *</label>
                    <input className="input" maxLength={50} value={draft.po_number}
                      onChange={(e) => setDraft({ ...draft, po_number: e.target.value })} />
                  </div>
                  <div className="flex items-end">
                    <button type="button" className="btn-primary text-sm w-full" onClick={addInwardLine}>+ Add to Inward Items</button>
                  </div>
                </div>
              </div>
            )}

            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-sm">{isRawMaterial ? `Inward items (${lines.length})` : `Items on this voucher (${lines.length})`}</h4>
                {!isRawMaterial && lines.length > 0 && (
                  <button type="button" className="btn-secondary text-xs" onClick={receiveAllPending}>Receive all pending</button>
                )}
              </div>
              {lines.length === 0 ? (
                <p className="text-sm text-gray-500 border border-dashed border-gray-300 rounded-lg px-3 py-6 text-center">
                  {isRawMaterial
                    ? 'No inward items yet. Fill the fields above and choose "Add to Inward Items".'
                    : 'Select a voucher to load its items.'}
                </p>
              ) : (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">#</th>
                        <th className="px-3 py-2 text-left font-medium">Stock In Item</th>
                        {!isRawMaterial && <th className="px-3 py-2 text-right font-medium">Ordered</th>}
                        {!isRawMaterial && <th className="px-3 py-2 text-right font-medium">Pending</th>}
                        <th className="px-3 py-2 text-right font-medium">{isRawMaterial ? 'Quantity' : 'Received'}</th>
                        {!isRawMaterial && <th className="px-3 py-2 text-right font-medium">Damaged/NC</th>}
                        {!isRawMaterial && <th className="px-3 py-2 text-right font-medium">Short Of</th>}
                        <th className="px-3 py-2 text-right font-medium">Rate</th>
                        <th className="px-3 py-2 text-left font-medium">LR No</th>
                        <th className="px-3 py-2 text-right font-medium">Amount</th>
                        <th className="px-3 py-2 text-left font-medium">{isRawMaterial ? 'PO Number' : 'Voucher Number'}</th>
                        {isRawMaterial && <th className="px-3 py-2" />}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {lines.map((line, index) => (
                        <tr key={index}>
                          <td className="px-3 py-2 text-gray-500">{index + 1}</td>
                          <td className="px-3 py-2">{line.label}</td>
                          {!isRawMaterial && <td className="px-3 py-2 text-right text-gray-500">{line.ordered_qty}</td>}
                          {!isRawMaterial && <td className="px-3 py-2 text-right font-medium">{pendingFor(index) ?? '-'}</td>}
                          <td className="px-3 py-2">
                            {isRawMaterial ? (
                              <span className="block text-right">{line.received_qty}</span>
                            ) : (
                              <input className="input text-right" type="number" min={0} value={line.received_qty}
                                onChange={(e) => updateLine(index, { received_qty: e.target.value })} />
                            )}
                          </td>
                          {!isRawMaterial && (
                            <td className="px-3 py-2">
                              <input className="input text-right" type="number" min={0} value={line.damaged_qty}
                                onChange={(e) => updateLine(index, { damaged_qty: e.target.value })} />
                            </td>
                          )}
                          {!isRawMaterial && (
                            <td className="px-3 py-2">
                              <input className="input text-right" type="number" min={0} value={line.short_qty}
                                onChange={(e) => updateLine(index, { short_qty: e.target.value })} />
                            </td>
                          )}
                          <td className="px-3 py-2">
                            {isRawMaterial ? (
                              <span className="block text-right">{formatCurrency(line.rate || 0)}</span>
                            ) : (
                              <input className="input text-right" type="number" min={0} step={0.01} value={line.rate}
                                onChange={(e) => updateLine(index, { rate: e.target.value })} />
                            )}
                          </td>
                          <td className="px-3 py-2">
                            {isRawMaterial ? (line.lr_number || '-') : (
                              <input className="input" maxLength={50} value={line.lr_number}
                                onChange={(e) => updateLine(index, { lr_number: e.target.value })} />
                            )}
                          </td>
                          <td className="px-3 py-2 text-right font-medium">{formatCurrency(lineAmount(line))}</td>
                          <td className="px-3 py-2">{line.po_number || '-'}</td>
                          {isRawMaterial && (
                            <td className="px-3 py-2 text-right">
                              <button type="button" className="text-red-600 text-xs hover:underline" onClick={() => removeLine(index)}>Remove</button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!isRawMaterial && lines.length > 0 && (
                <p className="text-xs text-gray-500 mt-2">Leave a row at zero to receive it on a later GRN.</p>
              )}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-4">
              <span className="text-sm font-medium">
                Total received: {sumBy(lines, (l) => l.received_qty)}
                {!isRawMaterial && ` | damaged/NC: ${sumBy(lines, (l) => l.damaged_qty)} | short of: ${sumBy(lines, (l) => l.short_qty)}`}
              </span>
              <div className="flex gap-2">
                <button type="submit" className="btn-primary text-sm" disabled={saving || lines.length === 0}>{saving ? 'Saving...' : 'Save GRN'}</button>
                <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
              </div>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          <FilterBar
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search GRN or vendor voucher number...' }}
            filters={[{
              label: 'Inward Type', value: filterType, onChange: (v) => { setFilterType(v); setPage(1); },
              options: [{ value: '', label: 'All' }, { value: RAW_MATERIAL, label: 'Raw Material' }, { value: SUB_VENDOR_GRN, label: 'Sub Vendor' }],
            }]}
            dateRange={{ from: dateFrom, to: dateTo, onFromChange: (v) => { setDateFrom(v); setPage(1); }, onToChange: (v) => { setDateTo(v); setPage(1); } }}
            onClear={() => { setSearch(''); setFilterType(''); setDateFrom(''); setDateTo(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState /> : (
          <>
            <DataTable keyField="grn_id" data={data.items} onRowClick={setDetail} columns={[
              { header: 'GRN No', accessor: 'grn_number' },
              { header: 'Type', accessor: (r) => (r.grn_type === RAW_MATERIAL ? 'Raw Material' : 'Sub Vendor') },
              { header: 'Vendor', accessor: (r) => r.contact_name || '-' },
              { header: 'Voucher', accessor: (r) => r.voucher_number ?? r.po_number ?? '-', hideOnMobile: true },
              { header: 'Date', accessor: (r) => formatDate(r.grn_date) },
              { header: 'Items', accessor: (r) => r.items.map((i) => `${i.item_name} (${i.received_qty})`).join(', '), hideOnMobile: true },
              { header: 'LR No', accessor: (r) => r.items.map((i) => i.lr_number).filter(Boolean).join(', ') || '-', hideOnMobile: true },
              { header: 'Total Received', accessor: (r) => sumBy(r.items, (i) => i.received_qty) },
              { header: '', accessor: (r) => (
                <div className="flex justify-end">
                  <button className="text-primary-600 text-xs hover:underline" onClick={(e) => { e.stopPropagation(); setDetail(r); }}>View</button>
                </div>
              ) },
            ]} />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>

      <Modal
        open={!!detail}
        title={detail ? `GRN ${detail.grn_number}` : ''}
        subtitle={detail ? (detail.grn_type === RAW_MATERIAL ? 'Raw Material inward' : `Against voucher ${detail.voucher_number ?? detail.po_number ?? '-'}`) : undefined}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <DetailField label="GRN Date" value={formatDate(detail.grn_date)} />
              <DetailField label="Vendor" value={detail.contact_name || '-'} />
              <DetailField label="Total Received" value={sumBy(detail.items, (i) => i.received_qty)} />
              <DetailField label="Items" value={detail.items.length} />
              {detail.grn_type !== RAW_MATERIAL && (
                <>
                  <DetailField label="Total Damaged/NC" value={sumBy(detail.items, (i) => i.damaged_qty)} />
                  <DetailField label="Total Short Of" value={sumBy(detail.items, (i) => i.short_qty)} />
                  <DetailField label="Vendor Voucher No" value={detail.vendor_voucher_number || '-'} />
                </>
              )}
              <div className="col-span-2 sm:col-span-4">
                <DetailField label="Remarks" value={detail.remarks || '-'} />
              </div>
            </div>

            <h4 className="font-medium text-sm mb-2">Items ({detail.items.length})</h4>
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">#</th>
                    <th className="px-3 py-2 text-left font-medium">Stock In Item</th>
                    <th className="px-3 py-2 text-right font-medium">Received</th>
                    {detail.grn_type !== RAW_MATERIAL && <th className="px-3 py-2 text-right font-medium">Damaged/NC</th>}
                    {detail.grn_type !== RAW_MATERIAL && <th className="px-3 py-2 text-right font-medium">Short Of</th>}
                    <th className="px-3 py-2 text-right font-medium">Rate</th>
                    <th className="px-3 py-2 text-left font-medium">LR No</th>
                    <th className="px-3 py-2 text-left font-medium">{detail.grn_type === RAW_MATERIAL ? 'PO Number' : 'Voucher Number'}</th>
                    <th className="px-3 py-2 text-right font-medium">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {detail.items.map((item, index) => (
                    <tr key={item.grn_item_id}>
                      <td className="px-3 py-2 text-gray-500">{index + 1}</td>
                      <td className="px-3 py-2">{item.item_name}</td>
                      <td className="px-3 py-2 text-right font-medium">{item.received_qty}</td>
                      {detail.grn_type !== RAW_MATERIAL && <td className="px-3 py-2 text-right">{item.damaged_qty}</td>}
                      {detail.grn_type !== RAW_MATERIAL && <td className="px-3 py-2 text-right">{item.short_qty}</td>}
                      <td className="px-3 py-2 text-right">{formatCurrency(item.rate)}</td>
                      <td className="px-3 py-2">{item.lr_number || '-'}</td>
                      <td className="px-3 py-2">{item.po_number || '-'}</td>
                      <td className="px-3 py-2 text-right">{formatCurrency(toNumber(item.received_qty) * toNumber(item.rate))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
