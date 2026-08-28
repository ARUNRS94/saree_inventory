import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { JobWorkIssue, JobWorkReceipt, Vendor, Saree, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { StatusBadge } from '@/components/StatusBadge';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { formatDate } from '@/utils/format';

export default function JobWorkPage() {
  const [tab, setTab] = useState<'issues' | 'receipts'>('issues');
  const [issues, setIssues] = useState<PaginatedResponse<JobWorkIssue>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [receipts, setReceipts] = useState<PaginatedResponse<JobWorkReceipt>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterVendor, setFilterVendor] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [sarees, setSarees] = useState<Saree[]>([]);
  const [openIssues, setOpenIssues] = useState<JobWorkIssue[]>([]);
  const [showIssueForm, setShowIssueForm] = useState(false);
  const [showReceiptForm, setShowReceiptForm] = useState(false);
  const [issueForm, setIssueForm] = useState({ vendor_id: '', saree_id: '', issued_qty: 1, remarks: '' });
  const [receiptForm, setReceiptForm] = useState({ issue_id: '', vendor_id: '', saree_id: '', received_qty: 0, rejected_qty: 0, process_cost: 0 });
  const [currentStock, setCurrentStock] = useState(0);
  const [pendingQty, setPendingQty] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, unknown> = { page, page_size: 50, search: search || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined };
    const p = tab === 'issues'
      ? api.get('/job-work/issues', { params: { ...params, status: filterStatus || undefined, vendor_id: filterVendor || undefined } }).then((r) => setIssues(r.data))
      : api.get('/job-work/receipts', { params }).then((r) => setReceipts(r.data));
    p.finally(() => setLoading(false));
  }, [tab, page, search, filterStatus, filterVendor, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get('/vendors', { params: { page_size: 200 } }).then((r) => setVendors(r.data.items));
    api.get('/sarees', { params: { page_size: 500 } }).then((r) => setSarees(r.data.items));
    api.get('/job-work/issues', { params: { page_size: 200 } }).then((r) => setOpenIssues(r.data.items.filter((i: JobWorkIssue) => i.status !== 'CLOSED')));
  }, []);

  useEffect(() => {
    if (issueForm.saree_id) api.get(`/inventory/stock/${issueForm.saree_id}`).then((r) => setCurrentStock(r.data.current_stock));
  }, [issueForm.saree_id]);

  useEffect(() => {
    if (receiptForm.issue_id && receiptForm.saree_id)
      api.get(`/job-work/issues/${receiptForm.issue_id}/pending-qty`, { params: { saree_id: receiptForm.saree_id } }).then((r) => setPendingQty(r.data.pending_qty));
  }, [receiptForm.issue_id, receiptForm.saree_id]);

  const saveIssue = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setError(''); setSuccess('');
    try {
      const res = await api.post('/job-work/issues', {
        vendor_id: Number(issueForm.vendor_id), remarks: issueForm.remarks || null,
        items: [{ saree_id: Number(issueForm.saree_id), issued_qty: issueForm.issued_qty }],
      });
      setSuccess(`Job Work Issue ${res.data.issue_no} saved.`);
      setShowIssueForm(false); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const saveReceipt = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setError(''); setSuccess('');
    try {
      const issue = openIssues.find((i) => i.issue_id === Number(receiptForm.issue_id));
      const res = await api.post('/job-work/receipts', {
        issue_id: Number(receiptForm.issue_id),
        vendor_id: issue?.vendor_id || Number(receiptForm.vendor_id),
        items: [{ saree_id: Number(receiptForm.saree_id), received_qty: receiptForm.received_qty, rejected_qty: receiptForm.rejected_qty, process_cost: receiptForm.process_cost }],
      });
      setSuccess(`Job Work Receipt ${res.data.receipt_no} saved.`);
      setShowReceiptForm(false); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader title="Job Work" actions={
        <div className="flex gap-2">
          <button className="btn-primary text-sm" onClick={() => { setShowIssueForm(true); setShowReceiptForm(false); setError(''); }}>+ Issue</button>
          <button className="btn-secondary text-sm" onClick={() => { setShowReceiptForm(true); setShowIssueForm(false); setError(''); }}>+ Receipt</button>
        </div>
      } />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {showIssueForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">New Job Work Issue</h3>
          <form onSubmit={saveIssue} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div><label className="label">Vendor *</label>
              <select className="input" value={issueForm.vendor_id} onChange={(e) => setIssueForm({ ...issueForm, vendor_id: e.target.value })} required>
                <option value="">Select</option>
                {vendors.map((v) => <option key={v.vendor_id} value={v.vendor_id}>{v.vendor_name} ({v.process_type})</option>)}
              </select>
            </div>
            <div><label className="label">Saree *</label>
              <select className="input" value={issueForm.saree_id} onChange={(e) => setIssueForm({ ...issueForm, saree_id: e.target.value })} required>
                <option value="">Select</option>
                {sarees.map((s) => <option key={s.saree_id} value={s.saree_id}>{s.saree_code} - {s.saree_name}</option>)}
              </select>
            </div>
            <div><label className="label">Available Stock</label><p className="input bg-gray-50">{currentStock} pcs</p></div>
            <div><label className="label">Issue Qty *</label><input className="input" type="number" min={1} value={issueForm.issued_qty} onChange={(e) => setIssueForm({ ...issueForm, issued_qty: Number(e.target.value) })} required /></div>
            <div className="sm:col-span-2 flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Saving...' : 'Issue'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowIssueForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {showReceiptForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">New Job Work Receipt</h3>
          <form onSubmit={saveReceipt} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div><label className="label">Issue *</label>
              <select className="input" value={receiptForm.issue_id} onChange={(e) => setReceiptForm({ ...receiptForm, issue_id: e.target.value })} required>
                <option value="">Select</option>
                {openIssues.map((i) => <option key={i.issue_id} value={i.issue_id}>{i.issue_no} ({i.vendor_name})</option>)}
              </select>
            </div>
            <div><label className="label">Saree *</label>
              <select className="input" value={receiptForm.saree_id} onChange={(e) => setReceiptForm({ ...receiptForm, saree_id: e.target.value })} required>
                <option value="">Select</option>
                {sarees.map((s) => <option key={s.saree_id} value={s.saree_id}>{s.saree_code} - {s.saree_name}</option>)}
              </select>
            </div>
            <div><label className="label">Pending Qty</label><p className="input bg-gray-50">{pendingQty}</p></div>
            <div><label className="label">Received Qty</label><input className="input" type="number" min={0} value={receiptForm.received_qty} onChange={(e) => setReceiptForm({ ...receiptForm, received_qty: Number(e.target.value) })} /></div>
            <div><label className="label">Rejected Qty</label><input className="input" type="number" min={0} value={receiptForm.rejected_qty} onChange={(e) => setReceiptForm({ ...receiptForm, rejected_qty: Number(e.target.value) })} /></div>
            <div><label className="label">Process Cost</label><input className="input" type="number" min={0} step={0.01} value={receiptForm.process_cost} onChange={(e) => setReceiptForm({ ...receiptForm, process_cost: Number(e.target.value) })} /></div>
            <div className="sm:col-span-2 lg:col-span-3 flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Saving...' : 'Receive'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowReceiptForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="flex gap-2 mb-4">
        <button className={tab === 'issues' ? 'btn-primary text-sm' : 'btn-secondary text-sm'} onClick={() => { setTab('issues'); setPage(1); }}>Issues</button>
        <button className={tab === 'receipts' ? 'btn-primary text-sm' : 'btn-secondary text-sm'} onClick={() => { setTab('receipts'); setPage(1); }}>Receipts</button>
      </div>

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          <FilterBar
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: tab === 'issues' ? 'Search issue no...' : 'Search receipt no...' }}
            filters={tab === 'issues' ? [
              { label: 'Status', value: filterStatus, onChange: (v) => { setFilterStatus(v); setPage(1); },
                options: [{ value: '', label: 'All' }, { value: 'OPEN', label: 'Open' }, { value: 'PARTIAL', label: 'Partial' }, { value: 'CLOSED', label: 'Closed' }] },
              { label: 'Vendor', value: filterVendor, onChange: (v) => { setFilterVendor(v); setPage(1); },
                options: [{ value: '', label: 'All Vendors' }, ...vendors.map((v) => ({ value: String(v.vendor_id), label: v.vendor_name }))] },
            ] : []}
            dateRange={{ from: dateFrom, to: dateTo, onFromChange: (v) => { setDateFrom(v); setPage(1); }, onToChange: (v) => { setDateTo(v); setPage(1); } }}
            onClear={() => { setSearch(''); setFilterStatus(''); setFilterVendor(''); setDateFrom(''); setDateTo(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : tab === 'issues' ? (
          issues.items.length === 0 ? <EmptyState /> : (
            <>
              <DataTable keyField="issue_id" data={issues.items} columns={[
                { header: 'Issue No', accessor: 'issue_no' },
                { header: 'Vendor', accessor: 'vendor_name' },
                { header: 'Date', accessor: (r) => formatDate(r.issue_date) },
                { header: 'Items', accessor: (r) => r.items.map((i) => `${i.saree_code} (${i.issued_qty})`).join(', '), hideOnMobile: true },
                { header: 'Status', accessor: (r) => <StatusBadge status={r.status} /> },
              ]} />
              <Pagination page={page} total={issues.total} pageSize={issues.page_size} onChange={setPage} />
            </>
          )
        ) : (
          receipts.items.length === 0 ? <EmptyState /> : (
            <>
              <DataTable keyField="receipt_id" data={receipts.items} columns={[
                { header: 'Receipt No', accessor: 'receipt_no' },
                { header: 'Issue No', accessor: 'issue_no' },
                { header: 'Vendor', accessor: 'vendor_name' },
                { header: 'Date', accessor: (r) => formatDate(r.receipt_date) },
                { header: 'Items', accessor: (r) => r.items.map((i) => `${i.saree_code} (${i.received_qty})`).join(', '), hideOnMobile: true },
              ]} />
              <Pagination page={page} total={receipts.total} pageSize={receipts.page_size} onChange={setPage} />
            </>
          )
        )}
      </div>
    </div>
  );
}
