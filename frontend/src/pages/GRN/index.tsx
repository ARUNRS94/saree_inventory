import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { GRN, PurchaseOrder, Item, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { useConfirmDialog } from '@/components/ConfirmDialog';
import { Modal, DetailField } from '@/components/Modal';
import { formatCurrency, formatDate, sumBy, toNumber } from '@/utils/format';
import { SUB_VENDOR } from '@/utils/contactTypes';

type GRNLineForm = {
  item_id: string;
  label: string;
  ordered_qty: number;
  received_qty: string;
  damaged_qty: string;
  rate: string;
  lr_number: string;
};

export default function GRNPage() {
  const [data, setData] = useState<PaginatedResponse<GRN>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [openPOs, setOpenPOs] = useState<PurchaseOrder[]>([]);
  const [allItems, setAllItems] = useState<Item[]>([]);
  // Sub vendor POs track pending quantity at PO level; RM vendor POs track it per item.
  const [poPendingQty, setPoPendingQty] = useState<number | null>(null);
  const [itemPendingQty, setItemPendingQty] = useState<Record<number, number>>({});
  // Numeric fields are held as strings so the box can be cleared instead of snapping back to 0.
  const [form, setForm] = useState({ po_id: '', remarks: '' });
  const [lines, setLines] = useState<GRNLineForm[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [detail, setDetail] = useState<GRN | null>(null);
  const { confirm, dialog } = useConfirmDialog();

  const load = useCallback(() => {
    setLoading(true);
    api.get('/grns', { params: { page, page_size: 50, search: search || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined } }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [page, search, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get('/purchase-orders', { params: { page_size: 200 } }).then((r) => {
      setOpenPOs(r.data.items.filter((po: PurchaseOrder) => po.status !== 'CLOSED' && po.status !== 'CANCELLED'));
    });
    api.get('/items', { params: { page_size: 500 } }).then((r) => setAllItems(r.data.items));
  }, []);

  const selectedPO = openPOs.find((po) => po.po_id === Number(form.po_id));
  const isSubVendorPO = selectedPO?.contact_type === SUB_VENDOR;

  // Every PO line becomes a receipt row; sub vendor POs are received as their target FG item.
  useEffect(() => {
    if (!selectedPO) { setLines([]); return; }
    setLines(selectedPO.items.map((poItem) => {
      const isSub = selectedPO.contact_type === SUB_VENDOR;
      const stockInId = isSub ? poItem.target_fg_item_id : poItem.item_id;
      const match = allItems.find((s) => s.item_id === stockInId);
      const label = match
        ? `${match.item_code} - ${match.item_name}`
        : `${poItem.item_code ?? ''} - ${poItem.item_name ?? ''}`;
      return {
        item_id: stockInId ? String(stockInId) : '',
        label: `${label} (${isSub ? 'FG' : 'RM'})`,
        ordered_qty: poItem.ordered_qty,
        received_qty: '',
        damaged_qty: '',
        rate: String(poItem.rate),
        lr_number: poItem.lr_number ?? '',
      };
    }));
  }, [selectedPO, allItems]);

  useEffect(() => {
    if (!selectedPO) { setPoPendingQty(null); setItemPendingQty({}); return; }
    const poId = selectedPO.po_id;
    api.get(`/purchase-orders/${poId}/pending-qty`).then((r) => setPoPendingQty(r.data.pending_qty));
    if (selectedPO.contact_type === SUB_VENDOR) { setItemPendingQty({}); return; }
    const itemIds = Array.from(new Set(selectedPO.items.map((i) => i.item_id)));
    Promise.all(itemIds.map((id) =>
      api.get(`/purchase-orders/${poId}/pending-qty`, { params: { item_id: id } })
        .then((r) => [id, r.data.pending_qty] as const)
    )).then((entries) => setItemPendingQty(Object.fromEntries(entries)));
  }, [selectedPO]);

  const lineTotal = (line: GRNLineForm) => toNumber(line.received_qty) + toNumber(line.damaged_qty);

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

  const openNew = () => { setForm({ po_id: '', remarks: '' }); setLines([]); setShowForm(true); setError(''); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const received = lines.filter((line) => lineTotal(line) > 0);
    if (received.length === 0) { setError('Enter a received or damaged quantity on at least one item.'); return; }
    const overBooked = lines.findIndex((line, i) => {
      const remaining = pendingFor(i);
      return remaining !== null && lineTotal(line) > remaining;
    });
    if (overBooked >= 0) { setError(`${lines[overBooked].label} exceeds the pending quantity on this PO.`); return; }
    if (!(await confirm('Save GRN', `Save this GRN with ${received.length} item(s) and post stock movements?`))) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      const res = await api.post('/grns', {
        po_id: Number(form.po_id), grn_date: null, remarks: form.remarks || null,
        items: received.map((line) => ({
          item_id: Number(line.item_id),
          received_qty: Number(line.received_qty || 0),
          damaged_qty: Number(line.damaged_qty || 0),
          rate: Number(line.rate || 0),
          lr_number: line.lr_number || null,
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
              <div><label className="label">Purchase Order *</label>
                <select className="input" value={form.po_id} onChange={(e) => { setForm({ ...form, po_id: e.target.value }); setError(''); }} required>
                  <option value="">Select</option>
                  {openPOs.map((po) => <option key={po.po_id} value={po.po_id}>{po.po_number} - {po.contact_name} ({po.contact_type})</option>)}
                </select>
              </div>
              <div className="sm:col-span-1 lg:col-span-2"><label className="label">Remarks (applies to whole GRN)</label>
                <input className="input" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
              </div>
            </div>

            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-sm">Items on this PO ({lines.length})</h4>
                {lines.length > 0 && (
                  <button type="button" className="btn-secondary text-xs" onClick={receiveAllPending}>Receive all pending</button>
                )}
              </div>
              {!selectedPO ? (
                <p className="text-sm text-gray-500 border border-dashed border-gray-300 rounded-lg px-3 py-6 text-center">
                  Select a purchase order to load its items.
                </p>
              ) : lines.length === 0 ? (
                <p className="text-sm text-gray-500 border border-dashed border-gray-300 rounded-lg px-3 py-6 text-center">
                  This purchase order has no items.
                </p>
              ) : (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">#</th>
                        <th className="px-3 py-2 text-left font-medium">Stock In Item</th>
                        <th className="px-3 py-2 text-right font-medium">Ordered</th>
                        <th className="px-3 py-2 text-right font-medium">Pending</th>
                        <th className="px-3 py-2 text-right font-medium">Received</th>
                        <th className="px-3 py-2 text-right font-medium">Damaged</th>
                        <th className="px-3 py-2 text-right font-medium">Rate</th>
                        <th className="px-3 py-2 text-left font-medium">LR No</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {lines.map((line, index) => (
                        <tr key={index}>
                          <td className="px-3 py-2 text-gray-500">{index + 1}</td>
                          <td className="px-3 py-2">{line.label}</td>
                          <td className="px-3 py-2 text-right text-gray-500">{line.ordered_qty}</td>
                          <td className="px-3 py-2 text-right font-medium">{pendingFor(index) ?? '-'}</td>
                          <td className="px-3 py-2">
                            <input className="input text-right" type="number" min={0} value={line.received_qty}
                              onChange={(e) => updateLine(index, { received_qty: e.target.value })} />
                          </td>
                          <td className="px-3 py-2">
                            <input className="input text-right" type="number" min={0} value={line.damaged_qty}
                              onChange={(e) => updateLine(index, { damaged_qty: e.target.value })} />
                          </td>
                          <td className="px-3 py-2">
                            <input className="input text-right" type="number" min={0} step={0.01} value={line.rate}
                              onChange={(e) => updateLine(index, { rate: e.target.value })} />
                          </td>
                          <td className="px-3 py-2">
                            <input className="input" maxLength={50} value={line.lr_number}
                              onChange={(e) => updateLine(index, { lr_number: e.target.value })} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {lines.length > 0 && (
                <p className="text-xs text-gray-500 mt-2">Leave a row at zero to receive it on a later GRN.</p>
              )}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-4">
              <span className="text-sm font-medium">
                Total received: {sumBy(lines, (l) => l.received_qty)} | damaged: {sumBy(lines, (l) => l.damaged_qty)}
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
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search GRN number...' }}
            dateRange={{ from: dateFrom, to: dateTo, onFromChange: (v) => { setDateFrom(v); setPage(1); }, onToChange: (v) => { setDateTo(v); setPage(1); } }}
            onClear={() => { setSearch(''); setDateFrom(''); setDateTo(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState /> : (
          <>
            <DataTable keyField="grn_id" data={data.items} onRowClick={setDetail} columns={[
              { header: 'GRN No', accessor: 'grn_number' },
              { header: 'PO', accessor: 'po_number' },
              { header: 'Date', accessor: (r) => formatDate(r.grn_date) },
              { header: 'Items', accessor: (r) => r.items.map((i) => `${i.item_code} (${i.received_qty})`).join(', '), hideOnMobile: true },
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
        subtitle={detail ? `Against PO ${detail.po_number ?? '-'}` : undefined}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <DetailField label="GRN Date" value={formatDate(detail.grn_date)} />
              <DetailField label="Total Received" value={sumBy(detail.items, (i) => i.received_qty)} />
              <DetailField label="Total Damaged" value={sumBy(detail.items, (i) => i.damaged_qty)} />
              <DetailField label="Items" value={detail.items.length} />
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
                    <th className="px-3 py-2 text-right font-medium">Damaged</th>
                    <th className="px-3 py-2 text-right font-medium">Rate</th>
                    <th className="px-3 py-2 text-left font-medium">LR No</th>
                    <th className="px-3 py-2 text-right font-medium">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {detail.items.map((item, index) => (
                    <tr key={item.grn_item_id}>
                      <td className="px-3 py-2 text-gray-500">{index + 1}</td>
                      <td className="px-3 py-2">{item.item_code} - {item.item_name}</td>
                      <td className="px-3 py-2 text-right font-medium">{item.received_qty}</td>
                      <td className="px-3 py-2 text-right">{item.damaged_qty}</td>
                      <td className="px-3 py-2 text-right">{formatCurrency(item.rate)}</td>
                      <td className="px-3 py-2">{item.lr_number || '-'}</td>
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
