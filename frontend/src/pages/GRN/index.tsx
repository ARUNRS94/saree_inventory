import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { GRN, PurchaseOrder, Saree, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { useConfirmDialog } from '@/components/ConfirmDialog';
import { formatDate, formatCurrency } from '@/utils/format';

export default function GRNPage() {
  const [data, setData] = useState<PaginatedResponse<GRN>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [openPOs, setOpenPOs] = useState<PurchaseOrder[]>([]);
  const [stockInItems, setStockInItems] = useState<{ id: number; label: string }[]>([]);
  const [pendingQty, setPendingQty] = useState(0);
  const [form, setForm] = useState({ po_id: '', saree_id: '', received_qty: 0, damaged_qty: 0, rate: 0, remarks: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
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
  }, []);

  const selectedPO = openPOs.find((po) => po.po_id === Number(form.po_id));

  useEffect(() => {
    if (!selectedPO) { setStockInItems([]); return; }
    if (selectedPO.contact_type === 'Sub vendor') {
      const fgIds = new Set(selectedPO.items.map((i) => i.target_fg_saree_id).filter(Boolean));
      api.get('/sarees', { params: { page_size: 500 } }).then((r) => {
        setStockInItems(r.data.items.filter((s: Saree) => fgIds.has(s.saree_id)).map((s: Saree) => ({ id: s.saree_id, label: `${s.saree_code} - ${s.saree_name} (FG)` })));
      });
    } else {
      setStockInItems(selectedPO.items.map((i) => ({ id: i.saree_id, label: `${i.saree_code} - ${i.saree_name} (RM)` })));
    }
  }, [selectedPO]);

  useEffect(() => {
    if (!form.po_id || !form.saree_id) { setPendingQty(0); return; }
    const isSubVendor = selectedPO?.contact_type === 'Sub vendor';
    api.get(`/purchase-orders/${form.po_id}/pending-qty`, { params: isSubVendor ? {} : { saree_id: form.saree_id } })
      .then((r) => setPendingQty(r.data.pending_qty));
    // Set rate from PO
    if (selectedPO) {
      const poItem = selectedPO.items[0];
      if (poItem) setForm((f) => ({ ...f, rate: poItem.rate }));
    }
  }, [form.po_id, form.saree_id, selectedPO]);

  const openNew = () => { setForm({ po_id: '', saree_id: '', received_qty: 0, damaged_qty: 0, rate: 0, remarks: '' }); setShowForm(true); setError(''); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!(await confirm('Save GRN', 'Save this GRN and post stock movements?'))) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      const res = await api.post('/grns', {
        po_id: Number(form.po_id), grn_date: null, remarks: form.remarks || null,
        items: [{ saree_id: Number(form.saree_id), received_qty: form.received_qty, damaged_qty: form.damaged_qty, rate: form.rate }],
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
          <form onSubmit={save} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div><label className="label">Purchase Order *</label>
              <select className="input" value={form.po_id} onChange={(e) => setForm({ ...form, po_id: e.target.value, saree_id: '' })} required>
                <option value="">Select</option>
                {openPOs.map((po) => <option key={po.po_id} value={po.po_id}>{po.po_number} - {po.supplier_name} ({po.contact_type})</option>)}
              </select>
            </div>
            <div><label className="label">Stock In Item *</label>
              <select className="input" value={form.saree_id} onChange={(e) => setForm({ ...form, saree_id: e.target.value })} required>
                <option value="">Select</option>
                {stockInItems.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </div>
            <div><label className="label">Pending Qty</label><p className="input bg-gray-50">{pendingQty}</p></div>
            <div><label className="label">Received Qty *</label><input className="input" type="number" min={0} value={form.received_qty} onChange={(e) => setForm({ ...form, received_qty: Number(e.target.value) })} required /></div>
            <div><label className="label">Damaged Qty</label><input className="input" type="number" min={0} value={form.damaged_qty} onChange={(e) => setForm({ ...form, damaged_qty: Number(e.target.value) })} /></div>
            <div><label className="label">Rate</label><input className="input" type="number" min={0} step={0.01} value={form.rate} onChange={(e) => setForm({ ...form, rate: Number(e.target.value) })} /></div>
            <div className="sm:col-span-2 lg:col-span-3 flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Saving...' : 'Save GRN'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
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
            <DataTable keyField="grn_id" data={data.items} columns={[
              { header: 'GRN No', accessor: 'grn_number' },
              { header: 'PO', accessor: 'po_number' },
              { header: 'Date', accessor: (r) => formatDate(r.grn_date) },
              { header: 'Items', accessor: (r) => r.items.map((i) => `${i.saree_code} (${i.received_qty})`).join(', '), hideOnMobile: true },
              { header: 'Total Received', accessor: (r) => r.items.reduce((s, i) => s + i.received_qty, 0) },
            ]} />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
