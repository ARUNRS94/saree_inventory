import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { Vendor, VendorProcessType, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';

export default function VendorsPage() {
  const [data, setData] = useState<PaginatedResponse<Vendor>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [processTypes, setProcessTypes] = useState<VendorProcessType[]>([]);
  const [search, setSearch] = useState('');
  const [filterPT, setFilterPT] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showPTForm, setShowPTForm] = useState(false);
  const [editing, setEditing] = useState<Vendor | null>(null);
  const [form, setForm] = useState({ vendor_name: '', process_type: '', phone: '', contact_person: '', gst_no: '', address: '' });
  const [ptForm, setPtForm] = useState({ process_type: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadPTs = () => api.get('/vendors/process-types').then((r) => setProcessTypes(r.data));

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get('/vendors', { params: { search, process_type: filterPT || undefined, page, page_size: 50 } }).then((r) => setData(r.data)),
      loadPTs(),
    ]).finally(() => setLoading(false));
  }, [search, filterPT, page]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm({ vendor_name: '', process_type: processTypes[0]?.process_type || '', phone: '', contact_person: '', gst_no: '', address: '' }); setShowForm(true); setError(''); };
  const openEdit = (v: Vendor) => { setEditing(v); setForm({ vendor_name: v.vendor_name, process_type: v.process_type, phone: v.phone || '', contact_person: v.contact_person || '', gst_no: v.gst_no || '', address: v.address || '' }); setShowForm(true); setError(''); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setError(''); setSuccess('');
    try {
      if (editing) { await api.put(`/vendors/${editing.vendor_id}`, form); setSuccess('Vendor updated.'); }
      else { await api.post('/vendors', form); setSuccess('Vendor added.'); }
      setShowForm(false); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const savePT = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setSuccess('');
    try {
      await api.post('/vendors/process-types', ptForm);
      setSuccess('Process type added.'); setShowPTForm(false); setPtForm({ process_type: '' }); loadPTs();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Save failed'); }
  };

  return (
    <div>
      <PageHeader title="Vendors" actions={
        <div className="flex gap-2">
          <button className="btn-secondary text-sm" onClick={() => { setShowPTForm(!showPTForm); setError(''); }}>+ Process Type</button>
          <button className="btn-primary text-sm" onClick={openNew}>+ Add Vendor</button>
        </div>
      } />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {showPTForm && (
        <div className="card p-4 mb-4">
          <form onSubmit={savePT} className="flex gap-3 items-end">
            <div className="flex-1"><label className="label">Process Type</label><input className="input" value={ptForm.process_type} onChange={(e) => setPtForm({ process_type: e.target.value })} required /></div>
            <button type="submit" className="btn-primary text-sm">Add</button>
          </form>
          {processTypes.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {processTypes.map((pt) => <span key={pt.process_type_id} className="bg-gray-100 text-gray-700 text-xs px-2.5 py-1 rounded-full">{pt.process_type}</span>)}
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">{editing ? 'Edit Vendor' : 'New Vendor'}</h3>
          <form onSubmit={save} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div><label className="label">Name *</label><input className="input" value={form.vendor_name} onChange={(e) => setForm({ ...form, vendor_name: e.target.value })} required /></div>
            <div><label className="label">Process Type *</label>
              <select className="input" value={form.process_type} onChange={(e) => setForm({ ...form, process_type: e.target.value })} required>
                <option value="">Select</option>
                {processTypes.map((pt) => <option key={pt.process_type_id} value={pt.process_type}>{pt.process_type}</option>)}
              </select>
            </div>
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
            <div><label className="label">Contact Person</label><input className="input" value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })} /></div>
            <div className="sm:col-span-2 flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          <FilterBar
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search name, phone...' }}
            filters={[{
              label: 'Process Type', value: filterPT, onChange: (v) => { setFilterPT(v); setPage(1); },
              options: [{ value: '', label: 'All Types' }, ...processTypes.map((pt) => ({ value: pt.process_type, label: pt.process_type }))],
            }]}
            onClear={() => { setSearch(''); setFilterPT(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState /> : (
          <>
            <DataTable keyField="vendor_id" data={data.items} onRowClick={openEdit} columns={[
              { header: 'Name', accessor: 'vendor_name' },
              { header: 'Process Type', accessor: 'process_type' },
              { header: 'Phone', accessor: 'phone', hideOnMobile: true },
            ]} />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
