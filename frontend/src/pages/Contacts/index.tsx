import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { Contact, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination, type SortState } from '@/components/DataTable';
import { ImportDialog } from '@/components/ImportDialog';
import { useAuth } from '@/contexts/AuthContext';
import { downloadFile } from '@/utils/download';
import { CONTACT_TYPE_OPTIONS, RM_VENDOR } from '@/utils/contactTypes';
import { LoadingState, EmptyState } from '@/components/LoadingState';

export default function ContactsPage() {
  const { can } = useAuth();
  const [showImport, setShowImport] = useState(false);
  const [data, setData] = useState<PaginatedResponse<Contact>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortState>({ sort_by: 'contact_name', sort_dir: 'asc' });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Contact | null>(null);
  const [form, setForm] = useState({ contact_name: '', contact_type: RM_VENDOR, contact_person: '', phone: '', gst_no: '', address: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    api.get('/contacts', { params: { search, contact_type: filterType || undefined, page, page_size: 50, ...sort } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [search, filterType, page, sort]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm({ contact_name: '', contact_type: RM_VENDOR, contact_person: '', phone: '', gst_no: '', address: '' }); setShowForm(true); setError(''); };
  const openEdit = (s: Contact) => {
    setEditing(s);
    setForm({ contact_name: s.contact_name, contact_type: s.contact_type, contact_person: s.contact_person || '', phone: s.phone || '', gst_no: s.gst_no || '', address: s.address || '' });
    setShowForm(true); setError('');
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    try {
      if (editing) {
        await api.put(`/contacts/${editing.contact_id}`, form);
        setSuccess('Contact updated.');
      } else {
        await api.post('/contacts', form);
        setSuccess('Contact added.');
      }
      setShowForm(false); load();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader title="Contact Master" actions={
        <>
          <button className="btn-secondary text-sm" onClick={() => downloadFile('/exports/contacts', 'contact_master.csv', { search, filter_value: filterType || undefined, ...sort })}>Export CSV</button>
          {can('imports') && (
            <button className="btn-secondary text-sm" onClick={() => setShowImport(true)}>Import CSV</button>
          )}
          <button className="btn-primary text-sm" onClick={openNew}>+ Add Contact</button>
        </>
      } />
      {showImport && (
        <ImportDialog
          entity="contacts"
          title="Contacts"
          columns={['name*', 'type*', 'contact_person', 'phone', 'gst_no', 'address']}
          onClose={() => setShowImport(false)}
          onImported={load}
        />
      )}
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">{editing ? 'Edit Contact' : 'New Contact'}</h3>
          {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}
          <form onSubmit={save} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div><label className="label">Name *</label><input className="input" value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} required /></div>
            <div><label className="label">Type *</label>
              <select className="input" value={form.contact_type} onChange={(e) => setForm({ ...form, contact_type: e.target.value })}>
                {CONTACT_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div><label className="label">Contact Person</label><input className="input" value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })} /></div>
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
            <div><label className="label">GST No</label><input className="input" value={form.gst_no} onChange={(e) => setForm({ ...form, gst_no: e.target.value })} /></div>
            <div><label className="label">Address</label><textarea className="input" rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></div>
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
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search name, phone, GST...' }}
            filters={[{
              label: 'Type', value: filterType, onChange: (v) => { setFilterType(v); setPage(1); },
              options: [{ value: '', label: 'All Types' }, ...CONTACT_TYPE_OPTIONS],
            }]}
            onClear={() => { setSearch(''); setFilterType(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState /> : (
          <>
            <DataTable
              keyField="contact_id"
              data={data.items}
              onRowClick={openEdit}
              sort={sort}
              onSortChange={(s) => { setSort(s); setPage(1); }}
              columns={[
                { header: 'Name', accessor: 'contact_name', sortKey: 'contact_name' },
                { header: 'Type', accessor: 'contact_type', sortKey: 'contact_type' },
                { header: 'Contact', accessor: 'contact_person', hideOnMobile: true, sortKey: 'contact_person' },
                { header: 'Phone', accessor: 'phone', hideOnMobile: true, sortKey: 'phone' },
                { header: 'GST', accessor: 'gst_no', hideOnMobile: true, sortKey: 'gst_no' },
                { header: 'Address', accessor: 'address', hideOnMobile: true },
              ]}
            />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
