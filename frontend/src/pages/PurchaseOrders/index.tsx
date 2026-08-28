import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { PurchaseOrder, Supplier, Saree, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { StatusBadge } from '@/components/StatusBadge';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { useConfirmDialog } from '@/components/ConfirmDialog';
import { formatDate, formatCurrency } from '@/utils/format';

export default function PurchaseOrdersPage() {
  const [data, setData] = useState<PaginatedResponse<PurchaseOrder>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSupplier, setFilterSupplier] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [sarees, setSarees] = useState<Saree[]>([]);
  const [allSarees, setAllSarees] = useState<Saree[]>([]);
  const [form, setForm] = useState({ supplier_id: '', saree_id: '', stock_out_saree_id: '', target_fg_saree_id: '', quantity: 1, rate: 0, remarks: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { confirm, dialog } = useConfirmDialog();

  const load = useCallback(() => {
    setLoading(true);
    api.get('/purchase-orders', { params: {
      page, page_size: 50, search: search || undefined,
      status: filterStatus || undefined, supplier_id: filterSupplier || undefined,
      date_from: dateFrom || undefined, date_to: dateTo || undefined,
    } }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [page, search, filterStatus, filterSupplier, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get('/suppliers', { params: { page_size: 200 } }).then((r) => setSuppliers(r.data.items.filter((s: Supplier) => s.contact_type !== 'Customer')));
    api.get('/sarees', { params: { page_size: 500 } }).then((r) => setAllSarees(r.data.items));
  }, []);

  const selectedSupplier = suppliers.find((s) => s.supplier_id === Number(form.supplier_id));
  const isSubVendor = selectedSupplier?.contact_type === 'Sub vendor';

  useEffect(() => {
    const itemType = isSubVendor ? 'Sub process' : 'RM';
    setSarees(allSarees.filter((s) => s.fabric === itemType));
  }, [form.supplier_id, allSarees, isSubVendor]);

  const openNew = () => { setForm({ supplier_id: '', saree_id: '', stock_out_saree_id: '', target_fg_saree_id: '', quantity: 1, rate: 0, remarks: '' }); setShowForm(true); setError(''); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!(await confirm('Create Purchase Order', 'Create this purchase order and post stock movements?'))) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      const body = {
        supplier_id: Number(form.supplier_id),
        remarks: form.remarks || null,
        items: [{
          saree_id: Number(form.saree_id),
          quantity: form.quantity,
          rate: form.rate,
          stock_out_saree_id: isSubVendor && form.stock_out_saree_id ? Number(form.stock_out_saree_id) : null,
          target_fg_saree_id: isSubVendor && form.target_fg_saree_id ? Number(form.target_fg_saree_id) : null,
        }],
      };
      const res = await api.post('/purchase-orders', body);
      setSuccess(`Purchase Order ${res.data.po_number} created.`);
      setShowForm(false); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const cancelPO = async (po: PurchaseOrder) => {
    if (!(await confirm('Cancel Purchase Order', `Cancel ${po.po_number} and reverse any Sub vendor WIP/stock issue movements?`, true))) return;
    try {
      await api.post(`/purchase-orders/${po.po_id}/cancel`);
      setSuccess(`PO ${po.po_number} cancelled.`); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
  };

  const fgSarees = allSarees.filter((s) => s.fabric === 'FG');
  const rmFgSarees = allSarees.filter((s) => s.fabric === 'RM' || s.fabric === 'FG');

  return (
    <div>
      {dialog}
      <PageHeader title="Purchase Orders" actions={<button className="btn-primary text-sm" onClick={openNew}>+ Create PO</button>} />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">New Purchase Order</h3>
          <form onSubmit={save} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div><label className="label">RM/Sub Vendor *</label>
              <select className="input" value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })} required>
                <option value="">Select</option>
                {suppliers.map((s) => <option key={s.supplier_id} value={s.supplier_id}>{s.supplier_name} ({s.contact_type})</option>)}
              </select>
            </div>
            <div><label className="label">Stock In Item *</label>
              <select className="input" value={form.saree_id} onChange={(e) => setForm({ ...form, saree_id: e.target.value })} required>
                <option value="">Select</option>
                {sarees.map((s) => <option key={s.saree_id} value={s.saree_id}>{s.saree_code} - {s.saree_name}</option>)}
              </select>
            </div>
            {isSubVendor && (
              <>
                <div><label className="label">Stock Out Item (RM/FG) *</label>
                  <select className="input" value={form.stock_out_saree_id} onChange={(e) => setForm({ ...form, stock_out_saree_id: e.target.value })} required>
                    <option value="">Select</option>
                    {rmFgSarees.map((s) => <option key={s.saree_id} value={s.saree_id}>{s.saree_code} - {s.saree_name} ({s.fabric})</option>)}
                  </select>
                </div>
                <div><label className="label">Target FG Item *</label>
                  <select className="input" value={form.target_fg_saree_id} onChange={(e) => setForm({ ...form, target_fg_saree_id: e.target.value })} required>
                    <option value="">Select</option>
                    {fgSarees.map((s) => <option key={s.saree_id} value={s.saree_id}>{s.saree_code} - {s.saree_name}</option>)}
                  </select>
                </div>
              </>
            )}
            <div><label className="label">Quantity *</label><input className="input" type="number" min={1} value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} required /></div>
            <div><label className="label">Rate / Process Charges *</label><input className="input" type="number" min={0} step={0.01} value={form.rate} onChange={(e) => setForm({ ...form, rate: Number(e.target.value) })} required /></div>
            <div><label className="label">Amount</label><p className="input bg-gray-50">{formatCurrency(form.quantity * form.rate)}</p></div>
            <div><label className="label">Remarks</label><input className="input" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} /></div>
            <div className="sm:col-span-2 lg:col-span-3 flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Creating...' : 'Create PO'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          <FilterBar
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search PO number, supplier...' }}
            filters={[
              { label: 'Status', value: filterStatus, onChange: (v) => { setFilterStatus(v); setPage(1); },
                options: [{ value: '', label: 'All' }, { value: 'OPEN', label: 'Open' }, { value: 'PARTIAL', label: 'Partial' }, { value: 'CLOSED', label: 'Closed' }, { value: 'CANCELLED', label: 'Cancelled' }] },
              { label: 'Supplier', value: filterSupplier, onChange: (v) => { setFilterSupplier(v); setPage(1); },
                options: [{ value: '', label: 'All Suppliers' }, ...suppliers.map((s) => ({ value: String(s.supplier_id), label: s.supplier_name }))] },
            ]}
            dateRange={{ from: dateFrom, to: dateTo, onFromChange: (v) => { setDateFrom(v); setPage(1); }, onToChange: (v) => { setDateTo(v); setPage(1); } }}
            onClear={() => { setSearch(''); setFilterStatus(''); setFilterSupplier(''); setDateFrom(''); setDateTo(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState /> : (
          <>
            <DataTable keyField="po_id" data={data.items} columns={[
              { header: 'PO No', accessor: 'po_number' },
              { header: 'Supplier', accessor: 'supplier_name' },
              { header: 'Type', accessor: 'contact_type', hideOnMobile: true },
              { header: 'Date', accessor: (r) => formatDate(r.po_date) },
              { header: 'Items', accessor: (r) => r.items.map((i) => i.saree_code).join(', '), hideOnMobile: true },
              { header: 'Qty', accessor: (r) => r.items.reduce((s, i) => s + i.ordered_qty, 0) },
              { header: 'Amount', accessor: (r) => formatCurrency(r.items.reduce((s, i) => s + i.amount, 0)), hideOnMobile: true },
              { header: 'Status', accessor: (r) => <StatusBadge status={r.status} /> },
              { header: '', accessor: (r) => r.status !== 'CANCELLED' && r.status !== 'CLOSED' ? (
                <button className="text-red-600 text-xs hover:underline" onClick={(e) => { e.stopPropagation(); cancelPO(r); }}>Cancel</button>
              ) : null },
            ]} />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
