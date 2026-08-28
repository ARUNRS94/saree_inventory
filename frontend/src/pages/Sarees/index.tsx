import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { Saree, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';

export default function SareesPage() {
  const [data, setData] = useState<PaginatedResponse<Saree>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [search, setSearch] = useState('');
  const [itemType, setItemType] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Saree | null>(null);
  const [form, setForm] = useState({ saree_code: '', saree_name: '', fabric: 'FG', design_name: '', color: '', category: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    api.get('/sarees', { params: { search, item_type: itemType || undefined, page, page_size: 50 } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [search, itemType, page]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm({ saree_code: '', saree_name: '', fabric: 'FG', design_name: '', color: '', category: '' }); setShowForm(true); setError(''); };
  const openEdit = (s: Saree) => { setEditing(s); setForm({ saree_code: s.saree_code, saree_name: s.saree_name, fabric: s.fabric || 'FG', design_name: s.design_name || '', color: s.color || '', category: s.category || '' }); setShowForm(true); setError(''); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    try {
      if (editing) {
        await api.put(`/sarees/${editing.saree_id}`, form);
        setSuccess('Item updated successfully.');
      } else {
        await api.post('/sarees', form);
        setSuccess('Item added successfully.');
      }
      setShowForm(false); load();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader title="Sarees / Items" actions={<button className="btn-primary text-sm" onClick={openNew}>+ Add Item</button>} />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">{editing ? 'Edit Item' : 'New Item'}</h3>
          {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}
          <form onSubmit={save} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div><label className="label">Code *</label><input className="input" value={form.saree_code} onChange={(e) => setForm({ ...form, saree_code: e.target.value })} required /></div>
            <div><label className="label">Name *</label><input className="input" value={form.saree_name} onChange={(e) => setForm({ ...form, saree_name: e.target.value })} required /></div>
            <div><label className="label">Type *</label>
              <select className="input" value={form.fabric} onChange={(e) => setForm({ ...form, fabric: e.target.value })}>
                <option value="FG">FG</option><option value="RM">RM</option><option value="Sub process">Sub process</option>
              </select>
            </div>
            <div><label className="label">Category</label><input className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></div>
            <div><label className="label">Design / Remarks</label><input className="input" value={form.design_name} onChange={(e) => setForm({ ...form, design_name: e.target.value })} /></div>
            <div><label className="label">Color</label><input className="input" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} /></div>
            <div className="sm:col-span-2 lg:col-span-3 flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          <FilterBar
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search code, name, design, color...' }}
            filters={[{
              label: 'Type', value: itemType, onChange: (v) => { setItemType(v); setPage(1); },
              options: [{ value: '', label: 'All Types' }, { value: 'RM', label: 'RM' }, { value: 'FG', label: 'FG' }, { value: 'Sub process', label: 'Sub process' }],
            }]}
            onClear={() => { setSearch(''); setItemType(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState message="No items found." /> : (
          <>
            <DataTable
              keyField="saree_id"
              data={data.items}
              onRowClick={openEdit}
              columns={[
                { header: 'Code', accessor: 'saree_code' },
                { header: 'Name', accessor: 'saree_name' },
                { header: 'Type', accessor: 'fabric' },
                { header: 'Category', accessor: 'category', hideOnMobile: true },
                { header: 'Color', accessor: 'color', hideOnMobile: true },
                { header: 'Design', accessor: 'design_name', hideOnMobile: true },
              ]}
            />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
