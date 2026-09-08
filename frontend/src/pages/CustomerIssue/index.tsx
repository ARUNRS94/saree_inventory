import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { Item, Contact, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { LoadingState } from '@/components/LoadingState';
import { itemTypeLabel } from '@/utils/itemTypes';
import { CUSTOMER } from '@/utils/contactTypes';

const EMPTY = { customer_id: '', item_id: '', quantity: '1', reference: '', remarks: '' };

export default function CustomerIssuePage() {
  const [customers, setCustomers] = useState<Contact[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [available, setAvailable] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    Promise.all([
      api.get('/contacts', { params: { contact_type: CUSTOMER, page_size: 200 } })
        .then((r) => setCustomers((r.data as PaginatedResponse<Contact>).items)),
      api.get('/items', { params: { item_type: 'FG', page_size: 200 } })
        .then((r) => setItems((r.data as PaginatedResponse<Item>).items)),
    ]).catch(() => setError('Could not load customers or finished goods.'))
      .finally(() => setLoading(false));
  }, []);

  // Show the item's stock up front, rather than only failing on submit.
  const loadStock = useCallback((itemId: string) => {
    if (!itemId) { setAvailable(null); return; }
    api.get(`/inventory/stock/${itemId}`)
      .then((r) => setAvailable(r.data.current_stock))
      .catch(() => setAvailable(null));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    try {
      await api.post('/inventory/customer-issue', {
        customer_id: Number(form.customer_id),
        item_id: Number(form.item_id),
        quantity: Number(form.quantity),
        reference: form.reference || null,
        remarks: form.remarks || null,
      });
      setSuccess('Customer issue saved and finished goods stock reduced.');
      setForm(EMPTY);
      setAvailable(null);
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Could not save the customer issue.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState />;

  const noMasters = customers.length === 0 || items.length === 0;

  return (
    <div>
      <PageHeader title="Issue to Customer" subtitle="Stock out finished goods against a customer" />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {noMasters && (
        <div className="bg-amber-50 text-amber-800 text-sm px-4 py-3 rounded-lg mb-4">
          Add a contact of type <strong>Customer</strong> and at least one <strong>Finished Goods</strong> item before issuing stock.
        </div>
      )}

      <div className="card p-4 sm:p-6 max-w-2xl">
        <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Customer *</label>
            <select className="input" value={form.customer_id} required
              onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
              <option value="">Select customer</option>
              {customers.map((c) => <option key={c.contact_id} value={c.contact_id}>{c.contact_name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Finished Goods Item *</label>
            <select className="input" value={form.item_id} required
              onChange={(e) => { setForm({ ...form, item_id: e.target.value }); loadStock(e.target.value); }}>
              <option value="">Select item</option>
              {items.map((s) => (
                <option key={s.item_id} value={s.item_id}>
                  {s.item_code} - {s.item_name} ({itemTypeLabel(s.item_type)})
                </option>
              ))}
            </select>
            {available !== null && (
              <p className={`text-xs mt-1 ${available > 0 ? 'text-gray-500' : 'text-red-600'}`}>
                Available stock: <strong>{available}</strong>
              </p>
            )}
          </div>
          <div>
            <label className="label">Qty Out *</label>
            <input className="input" type="number" min={1} value={form.quantity} required
              onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </div>
          <div>
            <label className="label">Reference</label>
            <input className="input" value={form.reference} placeholder="Auto-generated if left blank"
              onChange={(e) => setForm({ ...form, reference: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Remarks</label>
            <input className="input" value={form.remarks}
              onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <button type="submit" className="btn-primary text-sm" disabled={saving || noMasters}>
              {saving ? 'Saving...' : 'Save Customer Issue'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
