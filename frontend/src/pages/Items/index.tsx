import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { Item, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination, type SortState } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { ImportDialog } from '@/components/ImportDialog';
import { useAuth } from '@/contexts/AuthContext';
import { downloadFile } from '@/utils/download';
import { ITEM_TYPE_OPTIONS, SUB_PROCESS, SUB_PROCESS_CATEGORY_OPTIONS, itemTypeLabel } from '@/utils/itemTypes';

const emptyForm = { item_name: '', item_type: 'FG', category: '', remarks: '' };

export default function ItemsPage() {
  const { can } = useAuth();
  const [showImport, setShowImport] = useState(false);
  const [data, setData] = useState<PaginatedResponse<Item>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [search, setSearch] = useState('');
  const [itemType, setItemType] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortState>({ sort_by: 'item_name', sort_dir: 'asc' });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Item | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    api.get('/items', { params: { search, item_type: itemType || undefined, page, page_size: 50, ...sort } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [search, itemType, page, sort]);

  useEffect(() => { load(); }, [load]);

  const isSubProcess = form.item_type === SUB_PROCESS;

  const openNew = () => { setEditing(null); setForm(emptyForm); setShowForm(true); setError(''); };
  const openEdit = (s: Item) => {
    setEditing(s);
    setForm({ item_name: s.item_name, item_type: s.item_type || 'FG', category: s.category || '', remarks: s.remarks || '' });
    setShowForm(true); setError('');
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    const body = { ...form, category: isSubProcess ? form.category || null : null };
    try {
      if (editing) {
        await api.put(`/items/${editing.item_id}`, body);
        setSuccess('Item updated successfully.');
      } else {
        const res = await api.post('/items', body);
        setSuccess(`Item ${res.data.item_code} added successfully.`);
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
      <PageHeader title="Item Master" actions={
        <>
          <button className="btn-secondary text-sm" onClick={() => downloadFile('/exports/items', 'item_master.csv', { search, filter_value: itemType || undefined, ...sort })}>Export CSV</button>
          {can('imports') && (
            <button className="btn-secondary text-sm" onClick={() => setShowImport(true)}>Import CSV</button>
          )}
          <button className="btn-primary text-sm" onClick={openNew}>+ Add Item</button>
        </>
      } />
      {showImport && (
        <ImportDialog
          entity="items"
          title="Items"
          onClose={() => setShowImport(false)}
          onImported={load}
        />
      )}
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">{editing ? 'Edit Item' : 'New Item'}</h3>
          {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}
          <form onSubmit={save} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div><label className="label">Type *</label>
              <select className="input" value={form.item_type} onChange={(e) => setForm({ ...form, item_type: e.target.value, category: '' })}>
                {ITEM_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            {isSubProcess && (
              <div><label className="label">Category *</label>
                <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} required>
                  <option value="">Select</option>
                  {SUB_PROCESS_CATEGORY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            )}
            <div><label className="label">Name *</label><input className="input" value={form.item_name} onChange={(e) => setForm({ ...form, item_name: e.target.value })} required /></div>
            <div><label className="label">Remarks</label><input className="input" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} /></div>
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
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search name, type, category, remarks...' }}
            filters={[{
              label: 'Type', value: itemType, onChange: (v) => { setItemType(v); setPage(1); },
              options: [{ value: '', label: 'All Types' }, ...ITEM_TYPE_OPTIONS],
            }]}
            onClear={() => { setSearch(''); setItemType(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState message="No items found." /> : (
          <>
            <DataTable
              keyField="item_id"
              data={data.items}
              onRowClick={openEdit}
              sort={sort}
              onSortChange={(s) => { setSort(s); setPage(1); }}
              columns={[
                { header: 'Type', accessor: (s) => itemTypeLabel(s.item_type), sortKey: 'item_type' },
                { header: 'Category', accessor: (s) => s.category || '-', sortKey: 'category' },
                { header: 'Name', accessor: 'item_name', sortKey: 'item_name' },
                { header: 'Remarks', accessor: 'remarks', hideOnMobile: true, sortKey: 'remarks' },
              ]}
            />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
